from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import List, Optional

from sally.core.event_bus import SyncEventHandler
from sally.core.service_telemetry import ServiceNames
from sally.domain.events import RuleTriggeredEvent

# Try to import telemetry
_TELEMETRY_AVAILABLE = False
try:
    from sally.core.telemetry import get_telemetry, TelemetryManager
    _TELEMETRY_AVAILABLE = True
except ImportError:
    pass


@dataclass
class TriggeredRuleInfo:
    rule_id: str
    timestamp: float


class RuleManagerSyncService(SyncEventHandler):
    """
    Sync service for tracking rule triggers.

    Service Name: SAlly.Rules
    """

    def __init__(self, history_seconds: int = 30):
        self._history_seconds = history_seconds
        self._triggered: List[TriggeredRuleInfo] = []
        self._lock = threading.Lock()
        self._service_name = ServiceNames.RULES

        # OTEL telemetry
        self._telemetry: Optional[TelemetryManager] = None
        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
            except Exception:
                pass

    @property
    def event_types(self) -> List[str]:
        return ["rule_triggered"]

    def handle_sync(self, event):
        if not isinstance(event, RuleTriggeredEvent):
            return

        # Create span for rule triggered event handling
        span = None
        if self._telemetry and self._telemetry.enabled:
            span = self._telemetry.start_span(
                "rules.event.triggered",
                kind="consumer",
                attributes={
                    "rule_id": event.rule_id,
                    "entity_name": event.entity_name if hasattr(event, 'entity_name') else "",
                    "variable_name": event.variable_name if hasattr(event, 'variable_name') else "",
                }
            )

        try:
            with self._lock:
                self._triggered.append(TriggeredRuleInfo(rule_id=event.rule_id, timestamp=event.timestamp))
                self._prune_locked()

            # Record OTEL counter
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.counter(
                    "rules.events.triggered.total",
                    1,
                    {"rule_id": event.rule_id}
                )
        finally:
            if span:
                span.end()

    def get_recent_triggered_rule_ids(self) -> List[str]:
        with self._lock:
            self._prune_locked()
            return [t.rule_id for t in self._triggered]

    def _prune_locked(self) -> None:
        cutoff = time.time() - self._history_seconds
        self._triggered = [t for t in self._triggered if t.timestamp >= cutoff]

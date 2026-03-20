"""
sally/infrastructure/services/setpoint_service.py

Dedicated Setpoint Service for managing grid control setpoints with OTEL instrumentation.
Provides centralized setpoint management, validation, and tracking.

Service Name: SAlly.Setpoints
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable

from sally.core.event_bus import EventBus, SyncEventHandler
from sally.core.service_telemetry import ServiceNames
from sally.domain.events import SetpointChangeEvent
from sally.core.logger import get_logger

logger = get_logger(__name__)

# Try to import telemetry
_TELEMETRY_AVAILABLE = False
try:
    from sally.core.telemetry import get_telemetry, TelemetryManager
    _TELEMETRY_AVAILABLE = True
except ImportError:
    pass


@dataclass
class SetpointRecord:
    """Record of a setpoint value with metadata."""
    entity: str
    variable: str
    value: float
    source: str
    timestamp: float = field(default_factory=time.time)
    previous_value: Optional[float] = None


class SetpointService(SyncEventHandler):
    """
    Centralized service for setpoint management with OTEL instrumentation.

    Provides:
    - Setpoint application and tracking
    - Setpoint history and audit trail
    - OTEL metrics for setpoint operations
    - Event publishing for setpoint changes

    Service Name: SAlly.Setpoints
    """

    __slots__ = (
        '_event_bus', '_setpoints', '_history', '_lock', '_telemetry',
        '_service_name', '_apply_callback', '_setpoints_applied',
        '_setpoints_cleared', '_max_history'
    )

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        apply_callback: Optional[Callable[[str, str, float], bool]] = None,
        max_history: int = 1000,
    ):
        """
        Initialize the SetpointService.

        Args:
            event_bus: EventBus for publishing setpoint events
            apply_callback: Optional callback to apply setpoint to simulation/grid
            max_history: Maximum number of setpoint changes to keep in history
        """
        self._event_bus = event_bus
        self._apply_callback = apply_callback
        self._max_history = max_history

        self._setpoints: Dict[str, SetpointRecord] = {}
        self._history: List[SetpointRecord] = []
        self._lock = threading.Lock()
        self._service_name = ServiceNames.SETPOINTS

        # Metrics counters
        self._setpoints_applied = 0
        self._setpoints_cleared = 0

        # OTEL telemetry
        self._telemetry: Optional[TelemetryManager] = None
        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
                self._register_metrics()
            except Exception as e:
                logger.warning("Failed to initialize setpoint service telemetry: %s", e)

        logger.info(
            "SetpointService initialized: service=%s max_history=%d",
            self._service_name, self._max_history
        )

    def _register_metrics(self) -> None:
        """Register OTEL metrics for setpoint service."""
        if not self._telemetry or not self._telemetry.enabled:
            return

        try:
            self._telemetry.gauge(
                "setpoints.active.count",
                lambda: len(self._setpoints),
                "Number of active setpoints"
            )
            self._telemetry.gauge(
                "setpoints.history.count",
                lambda: len(self._history),
                "Number of setpoint changes in history"
            )
            logger.debug("Setpoint service OTEL metrics registered")
        except Exception as e:
            logger.warning("Failed to register setpoint service metrics: %s", e)

    @property
    def event_types(self) -> List[str]:
        """Event types this service handles."""
        return ["setpoint_change"]

    def handle_sync(self, event) -> None:
        """Handle setpoint change events from the event bus."""
        if isinstance(event, SetpointChangeEvent):
            # Update internal tracking when setpoint changes come from elsewhere
            with self._lock:
                key = f"{event.entity}.{event.variable}"
                record = SetpointRecord(
                    entity=event.entity,
                    variable=event.variable,
                    value=event.new_value,
                    source=event.source,
                    timestamp=event.timestamp,
                    previous_value=event.old_value if not (event.old_value != event.old_value) else None,  # Check for NaN
                )
                self._setpoints[key] = record
                self._add_to_history(record)

    def apply_setpoint(
        self,
        entity: str,
        variable: str,
        value: float,
        source: str = "setpoint_service",
    ) -> bool:
        """
        Apply a setpoint to the specified entity/variable.

        Args:
            entity: Entity name (e.g., "GEN_1")
            variable: Variable name (e.g., "p_setpoint")
            value: New setpoint value
            source: Source of the setpoint change

        Returns:
            True if setpoint was applied successfully
        """
        key = f"{entity}.{variable}"
        start_time = time.perf_counter()

        # Create span for setpoint application
        span = None
        if self._telemetry and self._telemetry.enabled:
            span = self._telemetry.start_span(
                "setpoints.apply",
                kind="internal",
                attributes={
                    "entity": entity,
                    "variable": variable,
                    "value": value,
                    "source": source,
                }
            )

        try:
            with self._lock:
                previous_value = None
                if key in self._setpoints:
                    previous_value = self._setpoints[key].value

                # Create record
                record = SetpointRecord(
                    entity=entity,
                    variable=variable,
                    value=value,
                    source=source,
                    previous_value=previous_value,
                )

                # Apply via callback if provided
                if self._apply_callback:
                    success = self._apply_callback(entity, variable, value)
                    if not success:
                        logger.warning(
                            "Setpoint application failed: entity=%s variable=%s value=%s",
                            entity, variable, value
                        )
                        if self._telemetry and self._telemetry.enabled:
                            self._telemetry.counter(
                                "setpoints.apply.failed",
                                1,
                                {"entity": entity, "variable": variable}
                            )
                        return False

                # Store setpoint
                self._setpoints[key] = record
                self._add_to_history(record)
                self._setpoints_applied += 1

            # Publish event
            if self._event_bus:
                event = SetpointChangeEvent(
                    entity=entity,
                    variable=variable,
                    old_value=previous_value if previous_value is not None else float("nan"),
                    new_value=value,
                    source=source,
                )
                self._event_bus.publish_sync(event)

            # Record metrics
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.counter(
                    "setpoints.applied.total",
                    1,
                    {"entity": entity, "variable": variable, "source": source}
                )
                self._telemetry.histogram(
                    "setpoints.apply.duration_ms",
                    elapsed_ms,
                    {"entity": entity, "variable": variable}
                )
                self._telemetry.histogram(
                    "setpoints.value",
                    value,
                    {"entity": entity, "variable": variable}
                )

            logger.debug(
                "Setpoint applied: %s.%s = %s (source=%s, previous=%s)",
                entity, variable, value, source, previous_value
            )
            return True

        finally:
            if span:
                span.end()

    def get_setpoint(self, entity: str, variable: str) -> Optional[float]:
        """
        Get the current setpoint value for an entity/variable.

        Args:
            entity: Entity name
            variable: Variable name

        Returns:
            Current setpoint value or None if not set
        """
        key = f"{entity}.{variable}"
        with self._lock:
            record = self._setpoints.get(key)
            return record.value if record else None

    def get_setpoint_record(self, entity: str, variable: str) -> Optional[SetpointRecord]:
        """
        Get the full setpoint record for an entity/variable.

        Args:
            entity: Entity name
            variable: Variable name

        Returns:
            SetpointRecord or None if not set
        """
        key = f"{entity}.{variable}"
        with self._lock:
            return self._setpoints.get(key)

    def get_all_setpoints(self) -> Dict[str, SetpointRecord]:
        """Get all active setpoints."""
        with self._lock:
            return dict(self._setpoints)

    def clear_setpoint(self, entity: str, variable: str) -> bool:
        """
        Clear a specific setpoint.

        Args:
            entity: Entity name
            variable: Variable name

        Returns:
            True if setpoint was cleared
        """
        key = f"{entity}.{variable}"

        span = None
        if self._telemetry and self._telemetry.enabled:
            span = self._telemetry.start_span(
                "setpoints.clear",
                kind="internal",
                attributes={"entity": entity, "variable": variable}
            )

        try:
            with self._lock:
                if key in self._setpoints:
                    del self._setpoints[key]
                    self._setpoints_cleared += 1

                    if self._telemetry and self._telemetry.enabled:
                        self._telemetry.counter(
                            "setpoints.cleared.total",
                            1,
                            {"entity": entity, "variable": variable}
                        )

                    logger.debug("Setpoint cleared: %s.%s", entity, variable)
                    return True
                return False
        finally:
            if span:
                span.end()

    def clear_setpoints(self, entity: Optional[str] = None) -> int:
        """
        Clear setpoints, optionally for a specific entity.

        Args:
            entity: If provided, only clear setpoints for this entity

        Returns:
            Number of setpoints cleared
        """
        span = None
        if self._telemetry and self._telemetry.enabled:
            span = self._telemetry.start_span(
                "setpoints.clear_all",
                kind="internal",
                attributes={"entity": entity or "all"}
            )

        try:
            with self._lock:
                if entity:
                    keys_to_remove = [k for k in self._setpoints if k.startswith(f"{entity}.")]
                    for key in keys_to_remove:
                        del self._setpoints[key]
                    count = len(keys_to_remove)
                else:
                    count = len(self._setpoints)
                    self._setpoints.clear()

                self._setpoints_cleared += count

                if self._telemetry and self._telemetry.enabled:
                    self._telemetry.counter("setpoints.cleared.total", count)

                logger.info("Setpoints cleared: count=%d entity=%s", count, entity or "all")
                return count
        finally:
            if span:
                span.end()

    def get_history(self, limit: int = 100) -> List[SetpointRecord]:
        """
        Get recent setpoint change history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of recent setpoint changes
        """
        with self._lock:
            return list(self._history[-limit:])

    def get_entity_history(self, entity: str, limit: int = 50) -> List[SetpointRecord]:
        """
        Get setpoint history for a specific entity.

        Args:
            entity: Entity name to filter by
            limit: Maximum number of records to return

        Returns:
            List of setpoint changes for the entity
        """
        with self._lock:
            entity_history = [r for r in self._history if r.entity == entity]
            return entity_history[-limit:]

    def _add_to_history(self, record: SetpointRecord) -> None:
        """Add a record to history, maintaining max size."""
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            return {
                "active_setpoints": len(self._setpoints),
                "history_size": len(self._history),
                "total_applied": self._setpoints_applied,
                "total_cleared": self._setpoints_cleared,
                "service_name": self._service_name,
            }

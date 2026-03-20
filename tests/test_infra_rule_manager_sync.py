"""
Tests for sally.infrastructure.services.rule_manager_sync_service

Covers: TriggeredRuleInfo, RuleManagerSyncService.handle_sync,
        get_recent_triggered_rule_ids, history pruning.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from tests.diag.metrics import record_metric


@pytest.fixture()
def rule_sync_svc():
    """Create RuleManagerSyncService with mocked telemetry."""
    with patch("sally.infrastructure.services.rule_manager_sync_service._TELEMETRY_AVAILABLE", False):
        from sally.infrastructure.services.rule_manager_sync_service import RuleManagerSyncService
        svc = RuleManagerSyncService(history_seconds=5)
    return svc


class TestTriggeredRuleInfo:
    def test_fields(self):
        from sally.infrastructure.services.rule_manager_sync_service import TriggeredRuleInfo
        info = TriggeredRuleInfo(rule_id="R1", timestamp=1000.0)
        assert info.rule_id == "R1"
        assert info.timestamp == 1000.0
        record_metric("triggered_info_fields", 1, "bool")


class TestRuleManagerSyncService:
    def test_event_types(self, rule_sync_svc):
        assert "rule_triggered" in rule_sync_svc.event_types
        record_metric("rmsync_event_types", 1, "bool")

    def test_handle_sync_adds_rule(self, rule_sync_svc):
        from sally.domain.events import RuleTriggeredEvent
        ev = RuleTriggeredEvent(
            timestamp=time.time(),
            rule_id="R1",
            entity_name="GEN_1",
            variable_name="P",
            threshold=100.0,
            actual_value=120.0,
            action="shed_load",
        )
        rule_sync_svc.handle_sync(ev)
        ids = rule_sync_svc.get_recent_triggered_rule_ids()
        assert "R1" in ids
        record_metric("rmsync_handle", len(ids), "rules")

    def test_ignores_non_rule_event(self, rule_sync_svc):
        rule_sync_svc.handle_sync("not_an_event")
        ids = rule_sync_svc.get_recent_triggered_rule_ids()
        assert len(ids) == 0
        record_metric("rmsync_ignore", 1, "bool")

    def test_prune_old_entries(self):
        with patch("sally.infrastructure.services.rule_manager_sync_service._TELEMETRY_AVAILABLE", False):
            from sally.infrastructure.services.rule_manager_sync_service import (
                RuleManagerSyncService,
                TriggeredRuleInfo,
            )
            svc = RuleManagerSyncService(history_seconds=2)

        # Add old entries directly
        old_time = time.time() - 10
        svc._triggered.append(TriggeredRuleInfo(rule_id="OLD", timestamp=old_time))
        svc._triggered.append(TriggeredRuleInfo(rule_id="NEW", timestamp=time.time()))

        ids = svc.get_recent_triggered_rule_ids()
        assert "OLD" not in ids
        assert "NEW" in ids
        record_metric("rmsync_prune", len(ids), "rules")

    def test_multiple_rules(self, rule_sync_svc):
        from sally.domain.events import RuleTriggeredEvent

        for i in range(5):
            ev = RuleTriggeredEvent(
                timestamp=time.time(),
                rule_id=f"R{i}",
                entity_name="GEN_1",
                variable_name="P",
                threshold=100.0,
                actual_value=120.0 + i,
                action="alert",
            )
            rule_sync_svc.handle_sync(ev)

        ids = rule_sync_svc.get_recent_triggered_rule_ids()
        assert len(ids) == 5
        record_metric("rmsync_multi", len(ids), "rules")

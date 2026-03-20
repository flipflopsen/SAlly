"""
Tests for sally.infrastructure.services.setpoint_service

Covers: SetpointRecord dataclass, SetpointService CRUD, history,
        thread-safe apply/clear, handle_sync, get_stats.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from tests.diag.metrics import record_metric


@pytest.fixture()
def setpoint_svc():
    """Create SetpointService with mocked telemetry."""
    with patch("sally.infrastructure.services.setpoint_service._TELEMETRY_AVAILABLE", False):
        from sally.infrastructure.services.setpoint_service import SetpointService
        svc = SetpointService(event_bus=None, apply_callback=None, max_history=50)
    return svc


@pytest.fixture()
def setpoint_svc_with_bus():
    """SetpointService with a mock EventBus."""
    with patch("sally.infrastructure.services.setpoint_service._TELEMETRY_AVAILABLE", False):
        from sally.infrastructure.services.setpoint_service import SetpointService
        bus = MagicMock()
        svc = SetpointService(event_bus=bus, apply_callback=None, max_history=50)
    return svc, bus


class TestSetpointRecord:
    def test_fields(self):
        from sally.infrastructure.services.setpoint_service import SetpointRecord
        rec = SetpointRecord(entity="GEN_1", variable="p_setpoint", value=42.0, source="test")
        assert rec.entity == "GEN_1"
        assert rec.variable == "p_setpoint"
        assert rec.value == 42.0
        assert rec.source == "test"
        assert rec.previous_value is None
        record_metric("setpoint_record_fields", 1, "bool")


class TestSetpointServiceApply:
    def test_apply_setpoint_basic(self, setpoint_svc):
        ok = setpoint_svc.apply_setpoint("GEN_1", "p_setpoint", 100.0, "test")
        assert ok is True
        assert setpoint_svc.get_setpoint("GEN_1", "p_setpoint") == 100.0
        record_metric("sp_apply_basic", 1, "bool")

    def test_apply_updates_previous(self, setpoint_svc):
        setpoint_svc.apply_setpoint("GEN_1", "p", 10.0)
        setpoint_svc.apply_setpoint("GEN_1", "p", 20.0)
        rec = setpoint_svc.get_setpoint_record("GEN_1", "p")
        assert rec.value == 20.0
        assert rec.previous_value == 10.0
        record_metric("sp_apply_prev", 1, "bool")

    def test_apply_publishes_event(self, setpoint_svc_with_bus):
        svc, bus = setpoint_svc_with_bus
        svc.apply_setpoint("GEN_1", "p", 50.0)
        bus.publish_sync.assert_called_once()
        event = bus.publish_sync.call_args[0][0]
        assert event.new_value == 50.0
        record_metric("sp_apply_publish", 1, "bool")

    def test_apply_with_callback_success(self):
        cb = MagicMock(return_value=True)
        with patch("sally.infrastructure.services.setpoint_service._TELEMETRY_AVAILABLE", False):
            from sally.infrastructure.services.setpoint_service import SetpointService
            svc = SetpointService(event_bus=None, apply_callback=cb)
        ok = svc.apply_setpoint("GEN_1", "p", 10.0)
        assert ok is True
        cb.assert_called_once_with("GEN_1", "p", 10.0)
        record_metric("sp_callback_ok", 1, "bool")

    def test_apply_with_callback_failure(self):
        cb = MagicMock(return_value=False)
        with patch("sally.infrastructure.services.setpoint_service._TELEMETRY_AVAILABLE", False):
            from sally.infrastructure.services.setpoint_service import SetpointService
            svc = SetpointService(event_bus=None, apply_callback=cb)
        ok = svc.apply_setpoint("GEN_1", "p", 10.0)
        assert ok is False
        assert svc.get_setpoint("GEN_1", "p") is None
        record_metric("sp_callback_fail", 1, "bool")


class TestSetpointServiceClear:
    def test_clear_single(self, setpoint_svc):
        setpoint_svc.apply_setpoint("GEN_1", "p", 10.0)
        assert setpoint_svc.clear_setpoint("GEN_1", "p") is True
        assert setpoint_svc.get_setpoint("GEN_1", "p") is None
        record_metric("sp_clear_single", 1, "bool")

    def test_clear_nonexistent(self, setpoint_svc):
        assert setpoint_svc.clear_setpoint("NOPE", "x") is False
        record_metric("sp_clear_none", 1, "bool")

    def test_clear_all(self, setpoint_svc):
        setpoint_svc.apply_setpoint("GEN_1", "p", 10.0)
        setpoint_svc.apply_setpoint("GEN_2", "q", 20.0)
        count = setpoint_svc.clear_setpoints()
        assert count == 2
        assert setpoint_svc.get_all_setpoints() == {}
        record_metric("sp_clear_all", count, "cleared")

    def test_clear_entity(self, setpoint_svc):
        setpoint_svc.apply_setpoint("GEN_1", "p", 10.0)
        setpoint_svc.apply_setpoint("GEN_1", "q", 20.0)
        setpoint_svc.apply_setpoint("GEN_2", "p", 30.0)
        count = setpoint_svc.clear_setpoints(entity="GEN_1")
        assert count == 2
        assert setpoint_svc.get_setpoint("GEN_2", "p") == 30.0
        record_metric("sp_clear_entity", count, "cleared")


class TestSetpointServiceHistory:
    def test_history_recorded(self, setpoint_svc):
        for i in range(5):
            setpoint_svc.apply_setpoint("GEN_1", "p", float(i))
        hist = setpoint_svc.get_history(limit=10)
        assert len(hist) == 5
        record_metric("sp_history_len", len(hist), "entries")

    def test_history_limit(self, setpoint_svc):
        for i in range(10):
            setpoint_svc.apply_setpoint("GEN_1", "p", float(i))
        hist = setpoint_svc.get_history(limit=3)
        assert len(hist) == 3
        record_metric("sp_history_limit", len(hist), "entries")

    def test_entity_history(self, setpoint_svc):
        for i in range(5):
            setpoint_svc.apply_setpoint("GEN_1", "p", float(i))
            setpoint_svc.apply_setpoint("GEN_2", "q", float(i * 10))
        hist = setpoint_svc.get_entity_history("GEN_1")
        assert all(h.entity == "GEN_1" for h in hist)
        assert len(hist) == 5
        record_metric("sp_entity_hist", len(hist), "entries")

    def test_max_history_cap(self):
        with patch("sally.infrastructure.services.setpoint_service._TELEMETRY_AVAILABLE", False):
            from sally.infrastructure.services.setpoint_service import SetpointService
            svc = SetpointService(event_bus=None, max_history=5)
        for i in range(20):
            svc.apply_setpoint("GEN_1", "p", float(i))
        hist = svc.get_history(limit=100)
        assert len(hist) == 5
        record_metric("sp_max_cap", len(hist), "entries")


class TestSetpointServiceStats:
    def test_stats(self, setpoint_svc):
        setpoint_svc.apply_setpoint("GEN_1", "p", 10.0)
        setpoint_svc.apply_setpoint("GEN_2", "q", 20.0)
        setpoint_svc.clear_setpoint("GEN_1", "p")
        stats = setpoint_svc.get_stats()
        assert stats["active_setpoints"] == 1
        assert stats["total_applied"] == 2
        assert stats["total_cleared"] == 1
        record_metric("sp_stats", stats["total_applied"], "applied")


class TestSetpointServiceHandleSync:
    def test_handle_sync_event(self, setpoint_svc):
        from sally.domain.events import SetpointChangeEvent
        ev = SetpointChangeEvent(
            entity="GEN_1", variable="p", old_value=0.0, new_value=99.0, source="external",
        )
        setpoint_svc.handle_sync(ev)
        rec = setpoint_svc.get_setpoint_record("GEN_1", "p")
        assert rec is not None
        assert rec.value == 99.0
        record_metric("sp_handle_sync", 1, "bool")


class TestSetpointServiceThreadSafety:
    def test_concurrent_apply(self, setpoint_svc):
        errors = []

        def worker(entity_id):
            try:
                for i in range(50):
                    setpoint_svc.apply_setpoint(f"GEN_{entity_id}", "p", float(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        total = len(setpoint_svc.get_all_setpoints())
        assert total == 4  # 4 distinct entities
        record_metric("sp_thread_safety", total, "setpoints")

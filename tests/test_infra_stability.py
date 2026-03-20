"""
Tests for sally.infrastructure.services.stability_monitoring_service

Covers: StabilityMonitoringService thresholds, _check_voltage_stability,
        _is_persistent_voltage_issue, _check_frequency_stability, handle,
        _comprehensive_stability_check, _estimate_frequency.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.diag.metrics import record_metric


@pytest.fixture()
def stab_svc():
    """Create StabilityMonitoringService with mock DB and EventBus."""
    from sally.infrastructure.services.stability_monitoring_service import StabilityMonitoringService
    db = AsyncMock()
    bus = AsyncMock()
    svc = StabilityMonitoringService(db=db, event_bus=bus)
    return svc, db, bus


class TestStabilityMonitoringInit:
    def test_thresholds(self, stab_svc):
        svc, _, _ = stab_svc
        assert svc.voltage_thresholds["nominal"] == 1.0
        assert svc.frequency_thresholds["nominal"] == 50.0
        assert svc.angle_threshold == 30.0
        record_metric("stab_thresholds", 1, "bool")

    def test_event_types(self, stab_svc):
        svc, _, _ = stab_svc
        assert "grid_data_update" in svc.event_types
        record_metric("stab_event_types", 1, "bool")


class TestVoltageStability:
    @pytest.mark.asyncio
    async def test_high_voltage_critical_alarm(self, stab_svc):
        svc, db, bus = stab_svc
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        # Feed persistent high-voltage readings
        for i in range(10):
            m = GridMeasurement(
                entity="NODE_01", entity_type=EntityType.PYPOWER_NODE,
                timestamp=time.time() + i, vm=1.12, va=0.1,  # > critical_high=1.1
            )
            ev = GridDataEvent(measurement=m, timestamp=m.timestamp)
            await svc.handle(ev)

        # Should have published alarm(s)
        assert bus.publish.await_count > 0
        record_metric("stab_high_v", bus.publish.await_count, "alarms")

    @pytest.mark.asyncio
    async def test_normal_voltage_no_alarm(self, stab_svc):
        svc, db, bus = stab_svc
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="NODE_01", entity_type=EntityType.PYPOWER_NODE,
            timestamp=time.time(), vm=1.0, va=0.0,
        )
        ev = GridDataEvent(measurement=m, timestamp=m.timestamp)
        await svc.handle(ev)

        # No alarm published for normal voltage
        bus.publish.assert_not_awaited()
        record_metric("stab_normal_v", 1, "bool")


class TestPersistentVoltageIssue:
    @pytest.mark.asyncio
    async def test_first_measurement_is_persistent(self, stab_svc):
        svc, _, _ = stab_svc
        result = await svc._is_persistent_voltage_issue("NEW_NODE", 1.15, "voltage_high_critical")
        assert result is True
        record_metric("stab_first_persist", 1, "bool")

    @pytest.mark.asyncio
    async def test_sporadic_not_persistent(self, stab_svc):
        svc, _, _ = stab_svc
        # Add 10 normal voltage measurements
        svc.voltage_measurements["NODE_01"] = [
            {"timestamp": time.time() + i, "vm": 1.0, "va": 0.0} for i in range(10)
        ]
        result = await svc._is_persistent_voltage_issue("NODE_01", 1.06, "voltage_high_warning")
        assert result is False  # <60% exceeding
        record_metric("stab_sporadic", 1, "bool")


class TestFrequencyStability:
    @pytest.mark.asyncio
    async def test_low_frequency_alarm(self, stab_svc):
        svc, db, bus = stab_svc
        await svc._check_frequency_stability(49.4, time.time())  # below critical_low=49.5
        assert bus.publish.await_count >= 2  # StabilityEvent + GridAlarmEvent
        record_metric("stab_low_freq", bus.publish.await_count, "events")

    @pytest.mark.asyncio
    async def test_normal_frequency_no_alarm(self, stab_svc):
        svc, db, bus = stab_svc
        await svc._check_frequency_stability(50.0, time.time())
        bus.publish.assert_not_awaited()
        record_metric("stab_normal_freq", 1, "bool")


class TestComprehensiveStabilityCheck:
    @pytest.mark.asyncio
    async def test_comprehensive_with_violations(self, stab_svc):
        svc, db, bus = stab_svc
        ts = time.time()
        # Add measurements: >20% buses with voltage violations
        for i in range(10):
            entity = f"NODE_{i:02d}"
            vm = 0.88 if i < 4 else 1.0  # 4 out of 10 = 40% violating
            svc.voltage_measurements[entity] = [{"timestamp": ts, "vm": vm, "va": 0.0}]

        await svc._comprehensive_stability_check()
        assert bus.publish.await_count >= 1
        record_metric("stab_comprehensive", bus.publish.await_count, "events")

    @pytest.mark.asyncio
    async def test_comprehensive_no_violations(self, stab_svc):
        svc, db, bus = stab_svc
        ts = time.time()
        for i in range(10):
            svc.voltage_measurements[f"NODE_{i:02d}"] = [
                {"timestamp": ts, "vm": 1.0, "va": 0.0}
            ]
        await svc._comprehensive_stability_check()
        bus.publish.assert_not_awaited()
        record_metric("stab_comp_ok", 1, "bool")


class TestStabilityStop:
    @pytest.mark.asyncio
    async def test_stop(self, stab_svc):
        svc, _, _ = stab_svc
        svc.running = True
        await svc.stop()
        assert svc.running is False
        record_metric("stab_stop", 1, "bool")

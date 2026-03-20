"""
Tests for sally.infrastructure.services.load_forecasting_service

Covers: LoadForecastingService handle, _ar_forecast, _forecast_entity_load,
        history management, event publishing.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from tests.diag.metrics import record_metric


@pytest.fixture()
def forecast_svc():
    from sally.infrastructure.services.load_forecasting_service import LoadForecastingService
    db = AsyncMock()
    bus = AsyncMock()
    svc = LoadForecastingService(db=db, event_bus=bus)
    return svc, db, bus


class TestLoadForecastingInit:
    def test_event_types(self, forecast_svc):
        svc, _, _ = forecast_svc
        assert "grid_data_update" in svc.event_types
        record_metric("lfs_event_types", 1, "bool")

    def test_initial_state(self, forecast_svc):
        svc, _, _ = forecast_svc
        assert len(svc.load_entities) == 0
        assert len(svc.historical_data) == 0
        assert svc.running is False
        record_metric("lfs_init", 1, "bool")


class TestLoadForecastingHandle:
    @pytest.mark.asyncio
    async def test_handle_tracks_load_entity(self, forecast_svc):
        svc, _, _ = forecast_svc
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="LOAD_01", entity_type=EntityType.LOAD_BUS,
            timestamp=time.time(), p=50.0,
        )
        ev = GridDataEvent(measurement=m, timestamp=m.timestamp)
        await svc.handle(ev)

        assert "LOAD_01" in svc.load_entities
        assert "LOAD_01" in svc.historical_data
        assert len(svc.historical_data["LOAD_01"]) == 1
        record_metric("lfs_track", 1, "bool")

    @pytest.mark.asyncio
    async def test_handle_household_entity(self, forecast_svc):
        svc, _, _ = forecast_svc
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="HOUSE_001", entity_type=EntityType.HOUSEHOLD_SIM,
            timestamp=time.time(), p_out=3.5,
        )
        ev = GridDataEvent(measurement=m, timestamp=m.timestamp)
        await svc.handle(ev)

        assert "HOUSE_001" in svc.load_entities
        data_point = svc.historical_data["HOUSE_001"][0]
        assert data_point["load"] == 3.5  # abs(p_out)
        record_metric("lfs_household", 1, "bool")

    @pytest.mark.asyncio
    async def test_handle_ignores_generator(self, forecast_svc):
        svc, _, _ = forecast_svc
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="GEN_1", entity_type=EntityType.PYPOWER_NODE,
            timestamp=time.time(), p=100.0,
        )
        ev = GridDataEvent(measurement=m, timestamp=m.timestamp)
        await svc.handle(ev)

        assert "GEN_1" not in svc.load_entities
        record_metric("lfs_ignore_gen", 1, "bool")

    @pytest.mark.asyncio
    async def test_history_cutoff(self, forecast_svc):
        svc, _, _ = forecast_svc
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        now = time.time()
        # Insert old measurement
        m_old = GridMeasurement(
            entity="LOAD_01", entity_type=EntityType.LOAD_BUS,
            timestamp=now - 90000, p=10.0,  # >24h ago
        )
        await svc.handle(GridDataEvent(measurement=m_old, timestamp=m_old.timestamp))

        # Insert recent measurement
        m_new = GridMeasurement(
            entity="LOAD_01", entity_type=EntityType.LOAD_BUS,
            timestamp=now, p=20.0,
        )
        await svc.handle(GridDataEvent(measurement=m_new, timestamp=m_new.timestamp))

        # Old measurement should be pruned
        assert len(svc.historical_data["LOAD_01"]) == 1
        assert svc.historical_data["LOAD_01"][0]["load"] == 20.0
        record_metric("lfs_cutoff", 1, "bool")


class TestARForecast:
    def test_short_data_returns_mean(self, forecast_svc):
        svc, _, _ = forecast_svc
        data = np.array([10.0, 20.0, 30.0])
        result = svc._ar_forecast(data, horizon_minutes=15)
        assert abs(result - np.mean(data)) < 0.01
        record_metric("lfs_ar_short", result, "forecast")

    def test_long_data_returns_value(self, forecast_svc):
        svc, _, _ = forecast_svc
        # Generate enough data points
        data = np.sin(np.linspace(0, 10 * np.pi, 200)) * 0.5 + 0.5
        result = svc._ar_forecast(data, horizon_minutes=60)
        assert isinstance(result, (float, np.floating))
        assert np.isfinite(result)
        record_metric("lfs_ar_long", float(result), "forecast")


class TestForecastEntityLoad:
    @pytest.mark.asyncio
    async def test_insufficient_history_returns_none(self, forecast_svc):
        svc, _, _ = forecast_svc
        history = [{"timestamp": i, "load": float(i)} for i in range(5)]
        result = await svc._forecast_entity_load("LOAD_01", history, 15, time.time())
        assert result is None  # <ar_order points
        record_metric("lfs_insuff", 1, "bool")

    @pytest.mark.asyncio
    async def test_sufficient_history_returns_forecast(self, forecast_svc):
        svc, _, _ = forecast_svc
        now = time.time()
        history = [{"timestamp": now - 200 + i, "load": 50.0 + i * 0.1} for i in range(200)]
        result = await svc._forecast_entity_load("LOAD_01", history, 15, now)
        assert result is not None
        assert result["prediction"] >= 0
        assert "confidence" in result
        record_metric("lfs_forecast_ok", result["prediction"], "MW")


class TestLoadForecastingStop:
    @pytest.mark.asyncio
    async def test_stop(self, forecast_svc):
        svc, _, _ = forecast_svc
        svc.running = True
        await svc.stop()
        assert svc.running is False
        record_metric("lfs_stop", 1, "bool")

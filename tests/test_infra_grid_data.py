"""
Tests for sally.infrastructure.services.grid_data_service

Covers: GridDataService init, _initialize_grid_topology, event_types,
        handle (batching & flush), _flush_batch, stop, get_entity_states.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.diag.metrics import record_metric


@pytest.fixture()
def grid_data_svc():
    """Create GridDataService in 'generate' mode with mock DB and EventBus."""
    with patch("sally.infrastructure.services.grid_data_service._TELEMETRY_AVAILABLE", False):
        from sally.infrastructure.services.grid_data_service import GridDataService
        db = AsyncMock()
        bus = MagicMock()
        svc = GridDataService(db=db, event_bus=bus, stream_mode="generate")
    return svc, db, bus


@pytest.fixture()
def grid_data_svc_batch():
    """Create GridDataService in 'batch' mode (no generate topology)."""
    with patch("sally.infrastructure.services.grid_data_service._TELEMETRY_AVAILABLE", False):
        from sally.infrastructure.services.grid_data_service import GridDataService
        db = AsyncMock()
        bus = MagicMock()
        svc = GridDataService(db=db, event_bus=bus, stream_mode="batch")
    return svc, db, bus


class TestGridDataServiceInit:
    def test_generate_mode_has_entities(self, grid_data_svc):
        svc, _, _ = grid_data_svc
        assert len(svc.grid_entities) > 0
        record_metric("gds_entities", len(svc.grid_entities), "count")

    def test_batch_mode_no_entities(self, grid_data_svc_batch):
        svc, _, _ = grid_data_svc_batch
        assert len(svc.grid_entities) == 0
        record_metric("gds_batch_noent", 1, "bool")

    def test_initial_counters(self, grid_data_svc):
        svc, _, _ = grid_data_svc
        assert svc._events_processed == 0
        assert svc._batches_flushed == 0
        assert svc._total_records_flushed == 0
        record_metric("gds_counters", 1, "bool")

    def test_event_types(self, grid_data_svc):
        svc, _, _ = grid_data_svc
        assert "grid_data_update" in svc.event_types
        record_metric("gds_event_types", 1, "bool")


class TestGridDataServiceTopology:
    def test_topology_entity_types(self, grid_data_svc):
        """Topology should contain generators, nodes, lines, PV, wind, BESS, households, loads."""
        svc, _, _ = grid_data_svc
        from sally.domain.grid_entities import EntityType

        types_present = set(svc.grid_entities.values())
        assert EntityType.PYPOWER_NODE in types_present
        assert EntityType.PYPOWER_BRANCH in types_present
        assert EntityType.CSV_PV in types_present
        assert EntityType.HOUSEHOLD_SIM in types_present
        record_metric("gds_topo_types", len(types_present), "types")

    def test_topology_entity_counts(self, grid_data_svc):
        svc, _, _ = grid_data_svc
        gen_count = sum(1 for k in svc.grid_entities if k.startswith("GEN_"))
        assert gen_count == 5
        house_count = sum(1 for k in svc.grid_entities if k.startswith("HOUSE_"))
        assert house_count == 50
        record_metric("gds_topo_gens", gen_count, "count")


class TestGridDataServiceHandle:
    @pytest.mark.asyncio
    async def test_handle_adds_to_batch(self, grid_data_svc):
        svc, db, _ = grid_data_svc
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="GEN_1", entity_type=EntityType.PYPOWER_NODE,
            timestamp=time.time(), p=100.0, q=10.0, vm=1.02,
        )
        ev = GridDataEvent(measurement=m, timestamp=m.timestamp)

        svc._batch_size = 999  # prevent auto-flush
        svc._flush_interval = 9999

        await svc.handle(ev)

        assert svc._events_processed == 1
        assert len(svc._batch_buffer) == 1
        assert svc._entity_states["GEN_1"] is m
        record_metric("gds_handle_batch", len(svc._batch_buffer), "buffered")

    @pytest.mark.asyncio
    async def test_handle_flushes_at_batch_size(self, grid_data_svc):
        svc, db, _ = grid_data_svc
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        svc._batch_size = 2
        svc._flush_interval = 9999

        for i in range(3):
            m = GridMeasurement(
                entity=f"GEN_{i}", entity_type=EntityType.PYPOWER_NODE,
                timestamp=time.time(), p=float(i * 10),
            )
            await svc.handle(GridDataEvent(measurement=m, timestamp=m.timestamp))

        # At least one flush should have occurred
        assert db.insert_grid_data_batch.await_count >= 1
        record_metric("gds_flush_count", db.insert_grid_data_batch.await_count, "flushes")

    @pytest.mark.asyncio
    async def test_handle_ignores_non_grid_event(self, grid_data_svc):
        svc, db, _ = grid_data_svc
        await svc.handle("not_a_grid_event")
        assert svc._events_processed == 0
        record_metric("gds_ignore", 1, "bool")


class TestGridDataServiceFlush:
    @pytest.mark.asyncio
    async def test_flush_empty_noop(self, grid_data_svc):
        svc, db, _ = grid_data_svc
        await svc._flush_batch()
        db.insert_grid_data_batch.assert_not_awaited()
        record_metric("gds_flush_empty", 1, "bool")

    @pytest.mark.asyncio
    async def test_flush_sends_and_clears(self, grid_data_svc):
        svc, db, _ = grid_data_svc
        svc._batch_buffer = [{"time": 1, "entity": "GEN_1"}] * 5
        await svc._flush_batch()
        db.insert_grid_data_batch.assert_awaited_once()
        assert len(svc._batch_buffer) == 0
        assert svc._batches_flushed == 1
        assert svc._total_records_flushed == 5
        record_metric("gds_flush_ok", 5, "records")

    @pytest.mark.asyncio
    async def test_flush_error_tracks_errors(self, grid_data_svc):
        svc, db, _ = grid_data_svc
        db.insert_grid_data_batch.side_effect = Exception("DB error")
        svc._batch_buffer = [{"time": 1}]
        await svc._flush_batch()
        assert svc._flush_errors == 1
        # buffer NOT cleared on error (by design – retry opportunity)
        assert len(svc._batch_buffer) == 1
        record_metric("gds_flush_err", svc._flush_errors, "errors")


class TestGridDataServiceStop:
    @pytest.mark.asyncio
    async def test_stop_flushes_remaining(self, grid_data_svc):
        svc, db, _ = grid_data_svc
        svc.running = True
        svc._batch_buffer = [{"time": 1}]
        await svc.stop()
        assert svc.running is False
        db.insert_grid_data_batch.assert_awaited_once()
        record_metric("gds_stop_flush", 1, "bool")


class TestGridDataServiceEntityStates:
    @pytest.mark.asyncio
    async def test_get_entity_states(self, grid_data_svc):
        svc, _, _ = grid_data_svc
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(entity="GEN_1", entity_type=EntityType.PYPOWER_NODE, timestamp=1.0)
        svc._entity_states["GEN_1"] = m

        states = svc.get_entity_states()
        assert "GEN_1" in states
        assert states["GEN_1"] is m
        record_metric("gds_entity_states", len(states), "entities")

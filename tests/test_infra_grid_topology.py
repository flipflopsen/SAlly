"""
Tests for sally.infrastructure.services.grid_topology_service

Covers: GridTopologyService init, event_types, handle (entity + connection upsert),
        get_metrics, error handling.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.diag.metrics import record_metric


@pytest.fixture()
def topo_svc():
    """Create GridTopologyService with mock DB and EventBus."""
    with patch("sally.infrastructure.services.grid_topology_service._TELEMETRY_AVAILABLE", False):
        from sally.infrastructure.services.grid_topology_service import GridTopologyService
        db = AsyncMock()
        bus = MagicMock()
        svc = GridTopologyService(db=db, event_bus=bus)
    return svc, db, bus


class TestGridTopologyServiceInit:
    def test_event_types(self, topo_svc):
        svc, _, _ = topo_svc
        assert "entity_relational_data" in svc.event_types
        record_metric("topo_event_types", 1, "bool")

    def test_initial_metrics(self, topo_svc):
        svc, _, _ = topo_svc
        metrics = svc.get_metrics()
        assert metrics["events_processed"] == 0
        assert metrics["entities_upserted"] == 0
        assert metrics["connections_upserted"] == 0
        assert metrics["errors"] == 0
        record_metric("topo_init_metrics", 1, "bool")


class TestGridTopologyServiceHandle:
    @pytest.mark.asyncio
    async def test_handle_entities_upsert(self, topo_svc):
        svc, db, _ = topo_svc
        from sally.domain.events import EntityRelationalDataEvent, GridEntityData

        entity = GridEntityData(
            entity_id="GEN_1",
            entity_name="Generator 1",
            entity_type="generator",
            rated_power=100.0,
        )
        event = EntityRelationalDataEvent(
            timestamp=1000.0,
            entities=[entity],
            connections=[],
            operation="upsert",
        )

        await svc.handle(event)

        db.upsert_grid_entities.assert_awaited_once()
        metrics = svc.get_metrics()
        assert metrics["events_processed"] == 1
        assert metrics["entities_upserted"] == 1
        record_metric("topo_upsert_ent", metrics["entities_upserted"], "entities")

    @pytest.mark.asyncio
    async def test_handle_connections_upsert(self, topo_svc):
        svc, db, _ = topo_svc
        from sally.domain.events import EntityRelationalDataEvent, GridConnectionData

        conn = GridConnectionData(
            from_entity_id="GEN_1",
            to_entity_id="NODE_01",
            connection_type="power_line",
        )
        event = EntityRelationalDataEvent(
            timestamp=1000.0,
            entities=[],
            connections=[conn],
            operation="upsert",
        )

        await svc.handle(event)

        db.upsert_grid_connections.assert_awaited_once()
        metrics = svc.get_metrics()
        assert metrics["connections_upserted"] == 1
        record_metric("topo_upsert_conn", metrics["connections_upserted"], "connections")

    @pytest.mark.asyncio
    async def test_handle_ignores_non_matching_event(self, topo_svc):
        svc, db, _ = topo_svc
        await svc.handle("not_a_real_event")
        db.upsert_grid_entities.assert_not_awaited()
        record_metric("topo_ignore", 1, "bool")

    @pytest.mark.asyncio
    async def test_handle_db_error_increments_errors(self, topo_svc):
        svc, db, _ = topo_svc
        from sally.domain.events import EntityRelationalDataEvent, GridEntityData

        db.upsert_grid_entities.side_effect = Exception("DB down")

        entity = GridEntityData(entity_id="X", entity_name="X", entity_type="bus")
        event = EntityRelationalDataEvent(
            timestamp=1000.0, entities=[entity], connections=[], operation="upsert",
        )

        await svc.handle(event)

        assert svc.get_metrics()["errors"] == 1
        record_metric("topo_error", 1, "bool")

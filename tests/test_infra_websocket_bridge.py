"""
Tests for sally.infrastructure.services.websocket_bridge_service (unit-testable parts)

Covers: WebSocketBridgeConfig, event_types, _get_device_category,
        _extract_device_id, _build_sensor_payload, _handle_grid_data,
        _handle_step_event, set_topology.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from tests.diag.metrics import record_metric


@pytest.fixture()
def ws_bridge():
    """Create WebSocketBridgeService with mocked socketio."""
    mock_sio_module = MagicMock()
    mock_sio_module.AsyncServer = MagicMock
    with patch.dict("sys.modules", {"socketio": mock_sio_module}):
        import importlib
        import sally.infrastructure.services.websocket_bridge_service as mod
        importlib.reload(mod)
        mod.SOCKETIO_AVAILABLE = True
        mod.sio = mock_sio_module

        bus = MagicMock()
        svc = mod.WebSocketBridgeService(event_bus=bus)
    return svc


class TestWebSocketBridgeConfig:
    def test_defaults(self):
        from sally.infrastructure.services.websocket_bridge_service import WebSocketBridgeConfig
        cfg = WebSocketBridgeConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 3001
        assert cfg.cors_allowed_origins == "*"
        record_metric("ws_cfg_default", 1, "bool")


class TestWebSocketBridgeEventTypes:
    def test_event_types(self, ws_bridge):
        types = ws_bridge.event_types
        assert "grid_data_update" in types
        assert "rule_triggered" in types
        assert "simulation_step" in types
        record_metric("ws_event_types", len(types), "types")


class TestWebSocketDeviceCategory:
    @pytest.mark.parametrize("et_name,expected", [
        ("PANDAPOWER_BUS", "bus"),
        ("PANDAPOWER_LOAD", "load"),
        ("PANDAPOWER_SGEN", "sgen"),
        ("CSV_PV", "sgen"),
        ("HOUSEHOLD_SIM", "load"),
    ])
    def test_mapping(self, ws_bridge, et_name, expected):
        from sally.domain.grid_entities import EntityType
        result = ws_bridge._get_device_category(EntityType[et_name])
        assert result == expected
        record_metric(f"ws_cat_{et_name}", 1, "bool")


class TestWebSocketExtractDeviceId:
    def test_numeric_suffix(self, ws_bridge):
        assert ws_bridge._extract_device_id("GEN_1") == "1"
        record_metric("ws_devid_num", 1, "bool")

    def test_no_suffix(self, ws_bridge):
        assert ws_bridge._extract_device_id("SYSTEM") == "system"
        record_metric("ws_devid_str", 1, "bool")


class TestWebSocketBuildPayload:
    def test_bus_payload_radians_to_degrees(self, ws_bridge):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="BUS_1", entity_type=EntityType.PANDAPOWER_BUS,
            timestamp=1.0, vm=1.01, va=0.5, p=100.0, q=20.0,
        )
        payload = ws_bridge._build_sensor_payload(m, "bus")
        assert abs(payload["va_degree"] - math.degrees(0.5)) < 0.01
        assert payload["vm_pu"] == 1.01
        assert payload["p_mw"] == 100.0
        record_metric("ws_payload_bus", len(payload), "fields")

    def test_sgen_payload(self, ws_bridge):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="PV_01", entity_type=EntityType.CSV_PV,
            timestamp=1.0, p=25.0, q=2.0,
        )
        payload = ws_bridge._build_sensor_payload(m, "sgen")
        assert payload["p_mw"] == 25.0
        assert payload["q_mvar"] == 2.0
        record_metric("ws_payload_sgen", len(payload), "fields")


class TestWebSocketHandleGridData:
    def test_accumulates_data(self, ws_bridge):
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="BUS_01", entity_type=EntityType.PANDAPOWER_BUS,
            timestamp=1.0, vm=1.0, p=50.0,
        )
        ev = GridDataEvent(measurement=m, timestamp=1.0)
        ws_bridge._handle_grid_data(ev)
        assert len(ws_bridge._current_step_data["bus"]) >= 1
        record_metric("ws_accum", 1, "bool")


class TestWebSocketSetTopology:
    def test_stores_topology(self, ws_bridge):
        topo = {"buses": ["BUS_1", "BUS_2"], "lines": ["LINE_1"]}
        ws_bridge._loop = None  # skip emit
        ws_bridge._sio = None
        ws_bridge.set_topology(topo)
        assert ws_bridge._topology == topo
        record_metric("ws_topo", 1, "bool")

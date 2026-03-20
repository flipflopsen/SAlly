"""
Tests for sally.infrastructure.services.mqtt_bridge_service (unit-testable parts)

Covers: MqttBridgeConfig, event_types, _get_device_category,
        _extract_device_id, _build_sensor_payload, _handle_grid_data,
        _handle_rule_triggered, _handle_step_event.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from tests.diag.metrics import record_metric


@pytest.fixture()
def mqtt_bridge():
    """Create MqttBridgeService with mocked paho-mqtt and EventBus."""
    with patch.dict("sys.modules", {"paho.mqtt.client": MagicMock(), "paho.mqtt": MagicMock(), "paho": MagicMock()}):
        # Force reload so MQTT_AVAILABLE becomes True
        import importlib
        import sally.infrastructure.services.mqtt_bridge_service as mod
        importlib.reload(mod)
        mod.MQTT_AVAILABLE = True
        mod.paho_mqtt = MagicMock()

        bus = MagicMock()
        # Provide a minimal ScadaMqttConfig mock
        mqtt_conf = MagicMock()
        mqtt_conf.host = "localhost"
        mqtt_conf.port = 1883
        mqtt_conf.client_id = "test-bridge"
        mqtt_conf.keepalive = 60
        mqtt_conf.qos = 1
        mqtt_conf.retain_topology = True

        svc = mod.MqttBridgeService(event_bus=bus, conf=mqtt_conf)
    return svc


class TestMqttBridgeConfig:
    def test_default_config(self):
        from sally.infrastructure.services.mqtt_bridge_service import MqttBridgeConfig
        cfg = MqttBridgeConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 1883
        assert cfg.qos == 1
        record_metric("mqtt_cfg_default", 1, "bool")


class TestMqttBridgeEventTypes:
    def test_event_types(self, mqtt_bridge):
        types = mqtt_bridge.event_types
        assert "grid_data_update" in types
        assert "simulation_step" in types
        assert "rule_triggered" in types
        record_metric("mqtt_event_types", len(types), "types")


class TestMqttBridgeDeviceCategory:
    @pytest.mark.parametrize("et_name,expected", [
        ("PANDAPOWER_BUS", "bus"),
        ("PANDAPOWER_LOAD", "load"),
        ("PANDAPOWER_SGEN", "sgen"),
        ("PANDAPOWER_TRAFO", "trafo"),
        ("PANDAPOWER_LINE", "line"),
        ("PYPOWER_NODE", "bus"),
        ("PYPOWER_BRANCH", "line"),
        ("CSV_PV", "sgen"),
        ("HOUSEHOLD_SIM", "load"),
    ])
    def test_category_mapping(self, mqtt_bridge, et_name, expected):
        from sally.domain.grid_entities import EntityType
        et = EntityType[et_name]
        result = mqtt_bridge._get_device_category(et)
        assert result == expected
        record_metric(f"mqtt_cat_{et_name}", 1, "bool")

    def test_unknown_type_returns_none(self, mqtt_bridge):
        result = mqtt_bridge._get_device_category("UNKNOWN")
        assert result is None
        record_metric("mqtt_cat_none", 1, "bool")


class TestMqttBridgeExtractDeviceId:
    def test_numeric_suffix(self, mqtt_bridge):
        assert mqtt_bridge._extract_device_id("GEN_1") == "1"
        assert mqtt_bridge._extract_device_id("HOUSE_042") == "042"
        record_metric("mqtt_devid_num", 1, "bool")

    def test_no_numeric_suffix(self, mqtt_bridge):
        result = mqtt_bridge._extract_device_id("SYSTEM")
        assert result == "system"
        record_metric("mqtt_devid_str", 1, "bool")


class TestMqttBridgeBuildSensorPayload:
    def test_bus_payload(self, mqtt_bridge):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="BUS_01", entity_type=EntityType.PANDAPOWER_BUS,
            timestamp=1.0, vm=1.02, va=0.1, p=50.0, q=10.0,
        )
        payload = mqtt_bridge._build_sensor_payload(m, "bus")
        assert "vm_pu" in payload
        assert "p_mw" in payload
        record_metric("mqtt_payload_bus", len(payload), "fields")

    def test_load_payload(self, mqtt_bridge):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="LOAD_01", entity_type=EntityType.PANDAPOWER_LOAD,
            timestamp=1.0, p=30.0, q=5.0,
        )
        payload = mqtt_bridge._build_sensor_payload(m, "load")
        assert "p_mw" in payload
        assert "q_mvar" in payload
        record_metric("mqtt_payload_load", len(payload), "fields")

    def test_trafo_payload(self, mqtt_bridge):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="TRAFO_01", entity_type=EntityType.PANDAPOWER_TRAFO,
            timestamp=1.0,
        )
        payload = mqtt_bridge._build_sensor_payload(m, "trafo")
        assert "loading_percent" in payload
        record_metric("mqtt_payload_trafo", 1, "bool")


class TestMqttBridgeHandleGridData:
    def test_accumulates_data(self, mqtt_bridge):
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="BUS_01", entity_type=EntityType.PANDAPOWER_BUS,
            timestamp=1.0, vm=1.0, p=50.0,
        )
        ev = GridDataEvent(measurement=m, timestamp=1.0)
        mqtt_bridge._handle_grid_data(ev)
        assert "01" in mqtt_bridge._current_step_data["bus"] or "BUS_01" in str(mqtt_bridge._current_step_data)
        record_metric("mqtt_accum", 1, "bool")


class TestMqttBridgeHandleRuleTriggered:
    def test_publishes_anomaly(self, mqtt_bridge):
        from sally.domain.events import RuleTriggeredEvent

        mqtt_bridge._client = MagicMock()
        mqtt_bridge._connected = MagicMock()
        mqtt_bridge._connected.is_set.return_value = True
        mqtt_bridge._client.publish.return_value = MagicMock(rc=0)

        ev = RuleTriggeredEvent(
            timestamp=1.0, rule_id="R1", entity_name="GEN_1",
            variable_name="P", threshold=100.0, actual_value=120.0,
            action="shed_load",
        )
        mqtt_bridge._handle_rule_triggered(ev)
        mqtt_bridge._client.publish.assert_called_once()
        topic = mqtt_bridge._client.publish.call_args[0][0]
        assert "anomaly" in topic
        record_metric("mqtt_rule_pub", 1, "bool")

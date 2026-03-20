"""
MQTT Bridge Service

Bridges Sally's EventBus events to an MQTT broker for scada_web integration.
Publishes events in Guardian-compatible format for seamless frontend consumption.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from typing import Dict, List, Optional, Any

from sally.core.config import ScadaMqttConfig
from sally.core.event_bus import EventBus, SyncEventHandler
from sally.core.logger import get_logger
from sally.core.config import config
from sally.domain.events import (
    GridDataEvent,
    RuleTriggeredEvent,
    SimulationStepEvent,
    SimulationStateEvent,
    SetpointChangeEvent,
)
from sally.domain.grid_entities import EntityType, GridMeasurement

# Try to import paho-mqtt
try:
    import paho.mqtt.client as paho_mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    paho_mqtt = None  # type: ignore


# MQTT Topic constants (Guardian-compatible format)
TOPIC_SENSOR_PREFIX = "sensor"
TOPIC_STEP_FINISHED = "meta/simulation/step-finished"
TOPIC_TERMINATE = "meta/simulation/terminate"
TOPIC_TOPOLOGY = "topology"
TOPIC_ANOMALY_PREFIX = "anomaly"


class MqttBridgeConfig:
    """Configuration for MQTT bridge service."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        client_id: str = "sally-bridge",
        keepalive: int = 60,
        qos: int = 1,
        retain_topology: bool = True,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.keepalive = keepalive
        self.qos = qos
        self.retain_topology = retain_topology


class MqttBridgeService(SyncEventHandler):
    """
    Bridges Sally EventBus events to MQTT broker.

    Converts Sally's event format to Guardian's MQTT topic structure:
    - sensor/{device_category}/{device_id} → sensor readings
    - meta/simulation/step-finished → step completion signal
    - meta/simulation/terminate → simulation end
    - topology → grid topology (retained)
    - anomaly/{detector} → anomaly detection results
    """

    def __init__(
        self,
        event_bus: EventBus,
        conf: Optional[ScadaMqttConfig] = None,
    ):
        if not MQTT_AVAILABLE:
            raise ImportError(
                "paho-mqtt is required for MqttBridgeService. "
                "Install it with: pip install paho-mqtt"
            )

        self.event_bus = event_bus
        self.config = conf or config.scada.web.mqtt
        self._logger = get_logger(__name__)

        self._client: Optional[Any] = None  # paho.mqtt.client.Client
        self._connected = threading.Event()
        self._running = False
        self._lock = threading.Lock()

        # Batch sensor data per step
        self._current_step_data: Dict[str, Dict[str, Any]] = {
            "load": {},
            "sgen": {},
            "bus": {},
            "trafo": {},
            "line": {},
        }
        self._current_timestamp: float = 0.0

        self._logger.info(
            "MqttBridgeService initialized: host=%s:%d",
            self.config.host, self.config.port
        )

    @property
    def event_types(self) -> List[str]:
        """Event types this handler subscribes to."""
        return [
            "grid_data_update",
            "rule_triggered",
            "simulation_step",
            "simulation_state",
            "setpoint_change",
        ]

    def start(self) -> None:
        """Start the MQTT bridge service."""
        if self._running:
            return

        self._running = True
        self._setup_client()
        self._subscribe_to_events()
        self._logger.info("MqttBridgeService started")

    def stop(self) -> None:
        """Stop the MQTT bridge service and send termination signal."""
        if not self._running:
            return

        self._running = False

        # Send termination message
        if self._client and self._connected.is_set():
            self._publish(TOPIC_TERMINATE, "")
            self._client.disconnect()

        self._logger.info("MqttBridgeService stopped")

    def _setup_client(self) -> None:
        """Setup MQTT client with callbacks."""
        self._client = paho_mqtt.Client(
            client_id=self.config.client_id,
            protocol=paho_mqtt.MQTTv311,
        )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        try:
            self._client.connect(
                self.config.host,
                self.config.port,
                self.config.keepalive,
            )
            self._client.loop_start()
        except Exception as e:
            self._logger.error("Failed to connect to MQTT broker: %s", e)
            raise

    def _on_connect(self, client, userdata, flags, rc) -> None:
        """Callback when connected to MQTT broker."""
        if rc == 0:
            self._connected.set()
            self._logger.info("Connected to MQTT broker at %s:%d",
                            self.config.host, self.config.port)
        else:
            self._logger.error("MQTT connection failed with code: %d", rc)

    def _on_disconnect(self, client, userdata, rc) -> None:
        """Callback when disconnected from MQTT broker."""
        self._connected.clear()
        if rc != 0:
            self._logger.warning("Unexpected MQTT disconnection (rc=%d)", rc)

    def _subscribe_to_events(self) -> None:
        """Subscribe to EventBus events."""
        self.event_bus.subscribe_to_all_without_removal(self)

    def _publish(self, topic: str, payload: str, retain: bool = False) -> bool:
        """Publish message to MQTT broker."""
        if not self._client or not self._connected.is_set():
            self._logger.warning("Cannot publish: not connected to MQTT broker")
            return False

        try:
            result = self._client.publish(
                topic,
                payload,
                qos=self.config.qos,
                retain=retain,
            )
            return result.rc == paho_mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            self._logger.error("Failed to publish to %s: %s", topic, e)
            return False

    def handle_sync(self, event) -> None:
        """Handle events synchronously from EventBus."""
        if isinstance(event, GridDataEvent):
            self._handle_grid_data(event)
        elif isinstance(event, SimulationStepEvent):
            self._handle_step_event(event)
        elif isinstance(event, SimulationStateEvent):
            self._handle_state_event(event)
        elif isinstance(event, RuleTriggeredEvent):
            self._handle_rule_triggered(event)
        elif isinstance(event, SetpointChangeEvent):
            self._handle_setpoint_change(event)

    def _handle_grid_data(self, event: GridDataEvent) -> None:
        """Handle grid data event - accumulate for batch publish."""
        measurement = event.measurement
        if not measurement:
            return

        # Determine device category from entity type
        category = self._get_device_category(measurement.entity_type)
        if not category:
            return

        # Extract device ID from entity name
        device_id = self._extract_device_id(measurement.entity)

        # Build sensor data payload
        data = self._build_sensor_payload(measurement, category)
        data["timestamp"] = measurement.timestamp

        with self._lock:
            self._current_step_data[category][device_id] = data
            self._current_timestamp = measurement.timestamp

    def _handle_step_event(self, event: SimulationStepEvent) -> None:
        """Handle simulation step event - publish batched sensor data."""
        with self._lock:
            # Publish individual sensor messages
            for category, devices in self._current_step_data.items():
                for device_id, data in devices.items():
                    topic = f"{TOPIC_SENSOR_PREFIX}/{category}/{device_id}"
                    self._publish(topic, json.dumps(data))

            # Publish step-finished signal
            self._publish(TOPIC_STEP_FINISHED, str(event.simulation_time))

            # Clear batch data for next step
            self._current_step_data = {
                "load": {},
                "sgen": {},
                "bus": {},
                "trafo": {},
                "line": {},
            }

    def _handle_state_event(self, event: SimulationStateEvent) -> None:
        """Handle full simulation state event."""
        # This could be used for topology updates
        pass

    def _handle_rule_triggered(self, event: RuleTriggeredEvent) -> None:
        """Handle rule triggered event - publish as anomaly."""
        anomaly_data = {
            "infected_bus": f"{event.entity_name}",
            "p_anomaly": 0.0,  # Not applicable for rule-based detection
            "correct_guess": True,
            "timestamp": event.timestamp,
            "detector": f"rule_{event.rule_id}",
            "details": {
                "variable": event.variable_name,
                "threshold": event.threshold,
                "actual_value": event.actual_value,
                "action": event.action,
            },
        }

        topic = f"{TOPIC_ANOMALY_PREFIX}/rules"
        self._publish(topic, json.dumps(anomaly_data))

    def _handle_setpoint_change(self, event: SetpointChangeEvent) -> None:
        """Handle setpoint change event."""
        # Could add a setpoint topic if needed by frontend
        pass

    def _get_device_category(self, entity_type: EntityType) -> Optional[str]:
        """Map EntityType to Guardian device category."""
        category_map = {
            # PandaPower types
            EntityType.PANDAPOWER_BUS: "bus",
            EntityType.PANDAPOWER_LOAD: "load",
            EntityType.PANDAPOWER_SGEN: "sgen",
            EntityType.PANDAPOWER_TRAFO: "trafo",
            EntityType.PANDAPOWER_LINE: "line",
            EntityType.PANDAPOWER_SWITCH: "switch",
            EntityType.PANDAPOWER_EXT_GRID: "ext_grid",
            # PyPower types mapped to closest equivalent
            EntityType.PYPOWER_NODE: "bus",
            EntityType.PYPOWER_BRANCH: "line",
            EntityType.PYPOWER_TRANSFORMER: "trafo",
            EntityType.PYPOWER_TR_PRI: "trafo",
            EntityType.PYPOWER_TR_SEC: "trafo",
            # Generation types
            EntityType.CSV_PV: "sgen",
            EntityType.WIND_TURBINE: "sgen",
            EntityType.BATTERY_ESS: "sgen",
            # Load types
            EntityType.HOUSEHOLD_SIM: "load",
            EntityType.LOAD_BUS: "load",
        }
        return category_map.get(entity_type)

    def _extract_device_id(self, entity_name: str) -> str:
        """Extract device ID from entity name."""
        # Try to extract numeric ID or use entity name
        parts = entity_name.split("_")
        if parts and parts[-1].isdigit():
            return parts[-1]
        return entity_name.replace(" ", "_").lower()

    def _build_sensor_payload(
        self,
        measurement: GridMeasurement,
        category: str
    ) -> Dict[str, Any]:
        """Build sensor payload matching Guardian format."""
        payload: Dict[str, Any] = {}

        if category == "bus":
            # Bus: vm_pu, va_degree, p_mw, q_mvar
            if measurement.vm_pu is not None:
                payload["vm_pu"] = measurement.vm_pu
            elif measurement.vm is not None:
                payload["vm_pu"] = measurement.vm

            if measurement.va_degree is not None:
                payload["va_degree"] = measurement.va_degree
            elif measurement.va is not None:
                # Convert radians to degrees
                import math
                payload["va_degree"] = math.degrees(measurement.va)

            if measurement.p_mw is not None:
                payload["p_mw"] = measurement.p_mw
            elif measurement.p is not None:
                payload["p_mw"] = measurement.p

            if measurement.q_mvar is not None:
                payload["q_mvar"] = measurement.q_mvar
            elif measurement.q is not None:
                payload["q_mvar"] = measurement.q

        elif category in ("load", "sgen"):
            # Load/Sgen: p_mw, q_mvar
            if measurement.p_mw is not None:
                payload["p_mw"] = measurement.p_mw
            elif measurement.p is not None:
                payload["p_mw"] = measurement.p
            elif measurement.p_out is not None:
                payload["p_mw"] = measurement.p_out

            if measurement.q_mvar is not None:
                payload["q_mvar"] = measurement.q_mvar
            elif measurement.q is not None:
                payload["q_mvar"] = measurement.q

        elif category in ("trafo", "line"):
            # Trafo/Line: loading_percent
            if measurement.loading_percent is not None:
                payload["loading_percent"] = measurement.loading_percent
            else:
                # Calculate from power if available
                payload["loading_percent"] = 0.0

        return payload

    def publish_topology(self, topology: Dict[str, Any]) -> bool:
        """Publish grid topology (retained message)."""
        return self._publish(
            TOPIC_TOPOLOGY,
            json.dumps(topology),
            retain=self.config.retain_topology,
        )

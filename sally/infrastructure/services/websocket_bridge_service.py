"""
WebSocket Bridge Service

Alternative to MQTT bridge for direct WebSocket communication with scada_web frontend.
Useful for local development without requiring an MQTT broker.
"""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import asdict
from typing import Dict, List, Optional, Any, Set
import math

from sally.core.event_bus import EventBus, SyncEventHandler
from sally.core.logger import get_logger
from sally.domain.events import (
    GridDataEvent,
    RuleTriggeredEvent,
    SimulationStepEvent,
    SimulationStateEvent,
    SetpointChangeEvent,
)
from sally.domain.grid_entities import EntityType, GridMeasurement

# Try to import socketio
try:
    import socketio as sio
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    sio = None  # type: ignore


class WebSocketBridgeConfig:
    """Configuration for WebSocket bridge service."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 3001,
        cors_allowed_origins: str = "*",
    ):
        self.host = host
        self.port = port
        self.cors_allowed_origins = cors_allowed_origins


class WebSocketBridgeService(SyncEventHandler):
    """
    Direct WebSocket bridge from Sally EventBus to scada_web frontend.

    Runs a Socket.IO server that emits events in Guardian-compatible format:
    - 'step' → (timestamp, sensor_data) tuple
    - 'anomaly' → anomaly detection results
    - 'topology' → grid topology on connect
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: Optional[WebSocketBridgeConfig] = None,
    ):
        if not SOCKETIO_AVAILABLE:
            raise ImportError(
                "python-socketio[asyncio_server] is required for WebSocketBridgeService. "
                "Install it with: pip install python-socketio[asyncio_server] aiohttp"
            )

        self.event_bus = event_bus
        self.config = config or WebSocketBridgeConfig()
        self._logger = get_logger(__name__)

        self._sio: Optional[Any] = None  # socketio.AsyncServer
        self._app = None
        self._runner = None
        self._site = None
        self._server_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._lock = threading.Lock()

        self._connected_clients: Set[str] = set()

        # Batch sensor data per step
        self._current_step_data: Dict[str, Dict[str, Dict[str, Any]]] = {
            "load": {},
            "sgen": {},
            "bus": {},
            "trafo": {},
            "line": {},
        }
        self._current_timestamp: float = 0.0

        # Cached topology for new connections
        self._topology: Optional[Dict[str, Any]] = None

        self._logger.info(
            "WebSocketBridgeService initialized: port=%d",
            self.config.port
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
        """Start the WebSocket bridge service."""
        if self._running:
            return

        self._running = True
        self._setup_server()
        self._subscribe_to_events()

        # Start server in background thread
        self._server_thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="WebSocketBridge",
        )
        self._server_thread.start()

        self._logger.info("WebSocketBridgeService started on port %d", self.config.port)

    def stop(self) -> None:
        """Stop the WebSocket bridge service."""
        if not self._running:
            return

        self._running = False

        # Emit termination to all clients
        if self._loop and self._sio:
            asyncio.run_coroutine_threadsafe(
                self._emit_to_all("terminate", {}),
                self._loop,
            )

        # Stop the event loop
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._server_thread:
            self._server_thread.join(timeout=5.0)

        self._logger.info("WebSocketBridgeService stopped")

    def _setup_server(self) -> None:
        """Setup Socket.IO server."""
        self._sio = sio.AsyncServer(
            async_mode='aiohttp',
            cors_allowed_origins=self.config.cors_allowed_origins,
        )

        @self._sio.event
        async def connect(sid, environ):
            self._connected_clients.add(sid)
            self._logger.info("Client connected: %s", sid)

            # Send cached topology to new client
            if self._topology:
                await self._sio.emit('topology', self._topology, room=sid)

        @self._sio.event
        async def disconnect(sid):
            self._connected_clients.discard(sid)
            self._logger.info("Client disconnected: %s", sid)

    def _run_server(self) -> None:
        """Run the aiohttp server in a dedicated thread."""
        from aiohttp import web

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._app = web.Application()
        self._sio.attach(self._app)

        async def start_server():
            self._runner = web.AppRunner(self._app)
            await self._runner.setup()
            self._site = web.TCPSite(
                self._runner,
                self.config.host,
                self.config.port
            )
            await self._site.start()

        self._loop.run_until_complete(start_server())
        self._loop.run_forever()

        # Cleanup
        self._loop.run_until_complete(self._runner.cleanup())

    def _subscribe_to_events(self) -> None:
        """Subscribe to EventBus events."""
        self.event_bus.subscribe_sync(self, self.event_types)

    async def _emit_to_all(self, event: str, data: Any) -> None:
        """Emit event to all connected clients."""
        if self._sio:
            await self._sio.emit(event, data)

    def _schedule_emit(self, event: str, data: Any) -> None:
        """Schedule an emit on the event loop."""
        if self._loop and self._sio:
            asyncio.run_coroutine_threadsafe(
                self._emit_to_all(event, data),
                self._loop,
            )

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
        """Handle grid data event - accumulate for batch emit."""
        measurement = event.measurement
        if not measurement:
            return

        category = self._get_device_category(measurement.entity_type)
        if not category:
            return

        device_id = self._extract_device_id(measurement.entity)
        data = self._build_sensor_payload(measurement, category)

        with self._lock:
            self._current_step_data[category][device_id] = data
            self._current_timestamp = measurement.timestamp

    def _handle_step_event(self, event: SimulationStepEvent) -> None:
        """Handle simulation step event - emit batched sensor data."""
        with self._lock:
            sensor_data = {
                category: dict(devices)
                for category, devices in self._current_step_data.items()
            }
            timestamp = event.simulation_time

            # Clear batch data
            self._current_step_data = {
                "load": {},
                "sgen": {},
                "bus": {},
                "trafo": {},
                "line": {},
            }

        # Emit step event (matches Guardian format)
        self._schedule_emit("step", (timestamp, sensor_data))

    def _handle_state_event(self, event: SimulationStateEvent) -> None:
        """Handle simulation state event."""
        pass

    def _handle_rule_triggered(self, event: RuleTriggeredEvent) -> None:
        """Handle rule triggered event - emit as anomaly."""
        anomaly_data = {
            "infected_bus": event.entity_name,
            "p_anomaly": 0.0,
            "correct_guess": True,
            "timestamp": event.timestamp,
            "detector": f"rule_{event.rule_id}",
        }

        self._schedule_emit("anomaly", anomaly_data)

    def _handle_setpoint_change(self, event: SetpointChangeEvent) -> None:
        """Handle setpoint change event."""
        pass

    def _get_device_category(self, entity_type: EntityType) -> Optional[str]:
        """Map EntityType to Guardian device category."""
        category_map = {
            EntityType.PANDAPOWER_BUS: "bus",
            EntityType.PANDAPOWER_LOAD: "load",
            EntityType.PANDAPOWER_SGEN: "sgen",
            EntityType.PANDAPOWER_TRAFO: "trafo",
            EntityType.PANDAPOWER_LINE: "line",
            EntityType.PANDAPOWER_SWITCH: "switch",
            EntityType.PANDAPOWER_EXT_GRID: "ext_grid",
            EntityType.PYPOWER_NODE: "bus",
            EntityType.PYPOWER_BRANCH: "line",
            EntityType.PYPOWER_TRANSFORMER: "trafo",
            EntityType.PYPOWER_TR_PRI: "trafo",
            EntityType.PYPOWER_TR_SEC: "trafo",
            EntityType.CSV_PV: "sgen",
            EntityType.WIND_TURBINE: "sgen",
            EntityType.BATTERY_ESS: "sgen",
            EntityType.HOUSEHOLD_SIM: "load",
            EntityType.LOAD_BUS: "load",
        }
        return category_map.get(entity_type)

    def _extract_device_id(self, entity_name: str) -> str:
        """Extract device ID from entity name."""
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
            if measurement.vm_pu is not None:
                payload["vm_pu"] = measurement.vm_pu
            elif measurement.vm is not None:
                payload["vm_pu"] = measurement.vm

            if measurement.va_degree is not None:
                payload["va_degree"] = measurement.va_degree
            elif measurement.va is not None:
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
            if measurement.loading_percent is not None:
                payload["loading_percent"] = measurement.loading_percent
            else:
                payload["loading_percent"] = 0.0

        return payload

    def set_topology(self, topology: Dict[str, Any]) -> None:
        """Set the grid topology for new client connections."""
        self._topology = topology
        # Emit to all connected clients
        self._schedule_emit("topology", topology)

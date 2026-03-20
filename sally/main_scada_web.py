"""
SCADA Web Entry Point

Launches Sally with SCADA Web integration (Guardian-compatible web frontend).
Supports both MQTT and WebSocket bridge modes for scada_web communication.

Usage:
    python -m sally.main_scada_web [--with-gui] [--bridge-mode mqtt|websocket]

Environment Variables:
    SALLY_MODE=true                    - Enable Sally mode in backend
    SALLY_MQTT_HOST=localhost          - MQTT broker host
    SALLY_MQTT_PORT=1883               - MQTT broker port
    SALLY_SCADA_WEB_BRIDGE=mqtt        - Bridge mode: mqtt or websocket
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from typing import Optional

from sally.core.event_bus import EventBus
from sally.core.service_telemetry import init_service_telemetry, ServiceNames
from sally.core.logger import get_logger
from sally.core.config import config
from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager
from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation
from sally.infrastructure.services.scada_orchestration_service import (
    SCADAOrchestrationService,
    SCADAOrchestrationConfig,
)

logger = get_logger(__name__)


def create_mqtt_bridge(event_bus: EventBus):
    """Create and configure MQTT bridge service."""
    from sally.infrastructure.services.mqtt_bridge_service import (
        MqttBridgeService,
        MqttBridgeConfig,
    )

    web_cfg = config.scada.web
    mqtt_cfg = web_cfg.mqtt

    bridge_config = MqttBridgeConfig(
        host=mqtt_cfg.host,
        port=mqtt_cfg.port,
        client_id=mqtt_cfg.client_id,
        keepalive=mqtt_cfg.keepalive,
        qos=mqtt_cfg.qos,
        retain_topology=mqtt_cfg.retain_topology
    )

    return MqttBridgeService(event_bus, bridge_config)


def create_websocket_bridge(event_bus: EventBus):
    """Create and configure WebSocket bridge service."""
    from sally.infrastructure.services.websocket_bridge_service import (
        WebSocketBridgeService,
        WebSocketBridgeConfig,
    )

    web_cfg = config.scada.web
    ws_cfg = web_cfg.websocket

    bridge_config = WebSocketBridgeConfig(
        host=ws_cfg.host,
        port=ws_cfg.port,
        cors_allowed_origins=ws_cfg.cors_allowed_origins,
    )

    return WebSocketBridgeService(event_bus, bridge_config)


def get_bridge_mode() -> str:
    """Get bridge mode from config or environment."""
    # Environment variable takes precedence
    env_mode = os.environ.get("SALLY_SCADA_WEB_BRIDGE")
    if env_mode:
        return env_mode.lower()

    # Check config
    web_cfg = config.scada.web
    return web_cfg.bridge_mode


def main(with_gui: bool = False, bridge_mode: Optional[str] = None) -> None:
    """
    Main entry point for SCADA Web.

    Args:
        with_gui: If True, also launch the tkinter SCADA GUI
        bridge_mode: Override bridge mode ("mqtt" or "websocket")
    """
    logger.info("Starting SCADA Web application...")

    # Set Sally mode environment variable for Node.js backend
    os.environ["SALLY_MODE"] = "true"

    # Determine bridge mode
    bridge = bridge_mode or get_bridge_mode()
    logger.info("Bridge mode: %s", bridge)

    # Load orchestration config
    scada_cfg = config.scada.orchestration
    orchestration_config = SCADAOrchestrationConfig(
        update_interval_ms=scada_cfg.update_interval_ms,
        max_triggered_rules_history=scada_cfg.max_triggered_rules_history,
        event_buffer_size=scada_cfg.event_buffer_size,
        default_step_interval_s=scada_cfg.default_step_interval_s,
    )
    config_path = config.get_path("config_dir") / "default.yml"

    # Initialize telemetry
    init_service_telemetry(
        ServiceNames.ORCHESTRATOR,
        config_path=config_path,
        extra_attributes={"component": "scada_web", "bridge_mode": bridge}
    )
    logger.info("Telemetry initialized")

    # Create event bus
    event_bus = EventBus(
        buffer_size=orchestration_config.event_buffer_size,
        batch_size=config.event_bus.batch_size,
        worker_count=config.event_bus.worker_count,
    )
    logger.info("Event bus initialized")

    # Load rules
    rule_manager = SmartGridRuleManager()
    rules_path = config.get_path("default_rules_file")
    if rules_path.exists():
        with rules_path.open("r") as fh:
            rules_data = json.load(fh)
        if isinstance(rules_data, list):
            rule_manager.load_rules(rules_data)
        logger.info("Loaded %d rules from %s", len(rules_data) if isinstance(rules_data, list) else 0, rules_path)

    # Load simulation
    hdf5_path = config.get_path("default_hdf5_file")
    logger.info("Loading simulation from HDF5: %s", hdf5_path)

    simulation = SmartGridSimulation(
        str(hdf5_path),
        rule_manager,
        event_bus=event_bus,
        publish_scada_events=True
    )
    logger.info("Simulation initialized with %d timesteps", simulation.total_timesteps)

    # Create bridge service
    bridge_service = None
    try:
        if bridge == "mqtt":
            bridge_service = create_mqtt_bridge(event_bus)
            logger.info("MQTT bridge created")
        elif bridge == "websocket":
            bridge_service = create_websocket_bridge(event_bus)
            logger.info("WebSocket bridge created")
        else:
            logger.warning("Unknown bridge mode '%s', defaulting to mqtt", bridge)
            bridge_service = create_mqtt_bridge(event_bus)
    except ImportError as e:
        logger.error("Failed to create bridge service: %s", e)
        logger.error("Make sure required dependencies are installed:")
        if bridge == "mqtt":
            logger.error("  pip install paho-mqtt")
        else:
            logger.error("  pip install python-socketio[asyncio_server] aiohttp")
        sys.exit(1)

    # Create orchestration service
    orchestration = SCADAOrchestrationService(
        event_bus=event_bus,
        simulation=simulation,
        rule_manager=rule_manager,
        config=orchestration_config,
    )
    orchestration.start()
    logger.info("Orchestration service started")

    # Start bridge service
    if bridge_service:
        bridge_service.start()
        logger.info("Bridge service started")

        # Publish initial topology
        topology = _build_topology(simulation)
        if hasattr(bridge_service, 'publish_topology'):
            bridge_service.publish_topology(topology)
        elif hasattr(bridge_service, 'set_topology'):
            bridge_service.set_topology(topology)
        logger.info("Topology published")

    # Print connection instructions
    _print_connection_info(bridge)

    if with_gui:
        # Launch tkinter SCADA GUI
        from sally.presentation.gui.scada.scada import create_scada_window
        logger.info("Creating SCADA window...")
        scada_window = create_scada_window(orchestration)
        logger.info("SCADA window created")

        try:
            scada_window.mainloop()
        finally:
            _shutdown(orchestration, simulation, bridge_service)
    else:
        # Run in headless mode (for use with scada_web frontend only)
        logger.info("Running in headless mode. Press Ctrl+C to stop.")
        try:
            # Keep running until interrupted
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            _shutdown(orchestration, simulation, bridge_service)


def _build_topology(simulation: SmartGridSimulation) -> dict:
    """Build topology dict for scada_web frontend."""
    # Build a simple topology from simulation entities
    topology = {
        "busses": [],
        "loads": [],
        "sgens": [],
        "trafos": [],
        "lines": [],
        "switches": [],
        "ext_grids": [],
        "ac_line_segments": [],
    }

    # Extract entity names and categorize them
    bus_id = 0
    load_id = 0
    sgen_id = 0

    for entity_name in simulation.entities:
        name_lower = entity_name.lower()

        if "bus" in name_lower or "node" in name_lower:
            topology["busses"].append({
                "cim_id": entity_name,
                "name": entity_name,
                "id": bus_id,
                "vn_kv": 0.4,
            })
            bus_id += 1
        elif "load" in name_lower or "house" in name_lower:
            topology["loads"].append({
                "cim_id": entity_name,
                "name": entity_name,
                "id": load_id,
                "bus": 0,
                "p_mw": 0.01,
                "q_mvar": 0.005,
                "sn_mva": None,
            })
            load_id += 1
        elif "gen" in name_lower or "pv" in name_lower:
            topology["sgens"].append({
                "cim_id": entity_name,
                "name": entity_name,
                "id": sgen_id,
                "bus": 0,
                "p_mw": 0.005,
                "q_mvar": 0.0,
                "sn_mva": 0.01,
                "min_p_mw": 0.0,
                "max_p_mw": 0.01,
            })
            sgen_id += 1

    return topology


def _print_connection_info(bridge: str) -> None:
    """Print connection instructions."""
    web_cfg = config.scada.web
    backend_cfg = web_cfg.backend
    frontend_cfg = web_cfg.frontend

    print("\n" + "=" * 60)
    print("SALLY SCADA WEB")
    print("=" * 60)
    print(f"Bridge Mode: {bridge.upper()}")
    print()

    if bridge == "mqtt":
        mqtt_cfg = web_cfg.mqtt
        print(f"MQTT Broker: {mqtt_cfg.host}:{mqtt_cfg.port}")
    else:
        ws_cfg = web_cfg.websocket
        print(f"WebSocket: ws://localhost:{ws_cfg.port}")

    print()
    print("To start the web frontend:")
    print("  1. cd sally/presentation/gui/scada_web")
    print("  2. npm install (if first time)")
    print("  3. npm run dev")
    print()
    print(f"Then open: http://localhost:{frontend_cfg.port}")
    print("=" * 60 + "\n")


def _shutdown(orchestration, simulation, bridge_service) -> None:
    """Clean shutdown of all services."""
    logger.info("Shutting down...")

    if bridge_service:
        bridge_service.stop()
        logger.info("Bridge service stopped")

    orchestration.stop()
    logger.info("Orchestration stopped")

    simulation.close()
    logger.info("Simulation closed")

    logger.info("Shutdown complete")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Sally SCADA Web - Guardian-compatible web visualization"
    )
    parser.add_argument(
        "--with-gui",
        action="store_true",
        help="Also launch the tkinter SCADA GUI"
    )
    parser.add_argument(
        "--bridge-mode",
        choices=["mqtt", "websocket"],
        default=None,
        help="Bridge mode for scada_web communication"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(with_gui=args.with_gui, bridge_mode=args.bridge_mode)

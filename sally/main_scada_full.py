from __future__ import annotations

import json

from sally.core.event_bus import EventBus
from sally.core.service_telemetry import init_service_telemetry, ServiceNames
from sally.core.logger import get_logger
from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager
from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation
from sally.infrastructure.services.scada_orchestration_service import (
    SCADAOrchestrationService,
    SCADAOrchestrationConfig,
)
from sally.presentation.gui.scada.scada import create_scada_window
from sally.presentation.gui.rule_manager import rule_manager_gui
from sally.core.config import config

logger = get_logger(__name__)


def main() -> None:
    logger.info("Starting SCADA Full application...")

    scada_cfg = config.scada.orchestration
    orchestration_config = SCADAOrchestrationConfig(
        update_interval_ms=scada_cfg.update_interval_ms,
        max_triggered_rules_history=scada_cfg.max_triggered_rules_history,
        event_buffer_size=scada_cfg.event_buffer_size,
        default_step_interval_s=scada_cfg.default_step_interval_s,
    )
    config_path = config.get_path("config_dir") / "default.yml"

    # Initialize telemetry for SCADA Orchestrator
    init_service_telemetry(
        ServiceNames.ORCHESTRATOR,
        config_path=config_path,
        extra_attributes={"component": "scada_full"}
    )
    logger.info("Telemetry initialized")

    event_bus = EventBus(
        buffer_size=orchestration_config.event_buffer_size,
        batch_size=config.event_bus.batch_size,
        worker_count=config.event_bus.worker_count,
    )
    logger.info("Event bus initialized")

    rule_manager = SmartGridRuleManager()
    rules_path = config.get_path("default_rules_file")
    if rules_path.exists():
        with rules_path.open("r") as fh:
            rules_data = json.load(fh)
        if isinstance(rules_data, list):
            rule_manager.load_rules(rules_data)
        logger.info("Loaded %d rules from %s", len(rules_data) if isinstance(rules_data, list) else 0, rules_path)

    hdf5_path = config.get_path("default_hdf5_file")
    logger.info("Loading simulation from HDF5: %s", hdf5_path)

    simulation = SmartGridSimulation(str(hdf5_path), rule_manager, event_bus=event_bus, publish_scada_events=True)
    logger.info("Simulation initialized")

    orchestration = SCADAOrchestrationService(
        event_bus=event_bus,
        simulation=simulation,
        rule_manager=rule_manager,
        config=orchestration_config,
    )
    orchestration.start()
    logger.info("Orchestration service started")

    # Create SCADA window (main window)
    logger.info("Creating SCADA window...")
    scada_window = create_scada_window(orchestration)
    logger.info("SCADA window created")

    # Create Rule Manager as Toplevel window - schedule it after the main window is ready
    def open_rule_manager():
        logger.info("Opening Rule Manager window...")
        rule_manager_gui.create_rule_manager_window(scada_window, event_bus=event_bus, rule_manager=rule_manager)
        logger.info("Rule Manager window opened")

    # Use after_idle to ensure SCADA window is fully initialized before opening Rule Manager
    scada_window.after(100, open_rule_manager)

    logger.info("Starting main GUI loop...")
    try:
        scada_window.mainloop()
    finally:
        logger.info("GUI loop ended, shutting down...")
        orchestration.stop()
        simulation.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()

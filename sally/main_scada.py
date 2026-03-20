from __future__ import annotations

import json

from sally.core.event_bus import EventBus
from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager
from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation
from sally.infrastructure.services.scada_orchestration_service import (
    SCADAOrchestrationService,
    SCADAOrchestrationConfig,
)
from sally.presentation.gui.scada.scada import create_scada_gui
from sally.core.config import config


def main() -> None:
    scada_cfg = config.scada.orchestration
    orchestration_config = SCADAOrchestrationConfig(
        update_interval_ms=scada_cfg.update_interval_ms,
        max_triggered_rules_history=scada_cfg.max_triggered_rules_history,
        event_buffer_size=scada_cfg.event_buffer_size,
        default_step_interval_s=scada_cfg.default_step_interval_s,
    )

    event_bus = EventBus(buffer_size=orchestration_config.event_buffer_size)

    rule_manager = SmartGridRuleManager()
    rules_path = config.get_path("default_rules_file")
    if rules_path.exists():
        with rules_path.open("r") as fh:
            rules_data = json.load(fh)
        if isinstance(rules_data, list):
            rule_manager.load_rules(rules_data)

    hdf5_path = config.get_path("default_hdf5_file")

    simulation = SmartGridSimulation(str(hdf5_path), rule_manager, event_bus=event_bus, publish_scada_events=True)

    orchestration = SCADAOrchestrationService(
        event_bus=event_bus,
        simulation=simulation,
        rule_manager=rule_manager,
        config=orchestration_config,
    )
    orchestration.start()

    try:
        create_scada_gui(orchestration)
    finally:
        orchestration.stop()
        simulation.close()


if __name__ == "__main__":
    main()

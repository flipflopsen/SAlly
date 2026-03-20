import time
from pathlib import Path

import h5py
import pytest


pytestmark = [pytest.mark.integration, pytest.mark.hdf5]

from sally.core.event_bus import EventBus
from sally.domain.events import GridDataEvent, RuleTriggeredEvent, SimulationStepEvent
from sally.domain.grid_entities import GridMeasurement, EntityType
from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager
from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation
from sally.infrastructure.services.scada_orchestration_service import SCADAOrchestrationService


@pytest.fixture()
def temp_hdf5(tmp_path: Path):
    file_path = tmp_path / "scada_test.h5"
    with h5py.File(file_path, "w") as hdf:
        grp = hdf.create_group("Generator1")
        grp.create_dataset("P_MW_out", data=[1.0, 1.1, 1.2])
    return file_path


def test_orchestration_event_handling(temp_hdf5: Path):
    event_bus = EventBus(buffer_size=128)
    rule_manager = SmartGridRuleManager()
    simulation = SmartGridSimulation(str(temp_hdf5), rule_manager, event_bus=event_bus)
    service = SCADAOrchestrationService(event_bus, simulation, rule_manager)

    measurement = GridMeasurement(entity="Generator1", entity_type=EntityType.PYPOWER_NODE, timestamp=time.time(), p_out=1.0)
    service.handle_sync(GridDataEvent(measurement=measurement))
    service.handle_sync(SimulationStepEvent(timestep=1, simulation_time=1.0))
    service.handle_sync(
        RuleTriggeredEvent(
            rule_id="rule1",
            entity_name="Generator1",
            variable_name="P_MW_out",
            threshold=1.0,
            actual_value=1.2,
            action="shed",
            timestamp=time.time(),
        )
    )

    state = service.get_current_state()
    assert state.grid_measurements["Generator1"].p_out == 1.0
    assert state.simulation_time == 1.0
    assert state.triggered_rules


def test_setpoint_application_flow(temp_hdf5: Path):
    event_bus = EventBus(buffer_size=128)
    rule_manager = SmartGridRuleManager()
    simulation = SmartGridSimulation(str(temp_hdf5), rule_manager, event_bus=event_bus)
    service = SCADAOrchestrationService(event_bus, simulation, rule_manager)
    service.start()

    try:
        service.apply_setpoint("Generator1", "P_MW_out", 2.5)
        timeout = time.time() + 2.0
        while time.time() < timeout:
            if service.get_current_state().setpoints.get("Generator1.P_MW_out") == 2.5:
                break
            time.sleep(0.05)
        assert service.get_current_state().setpoints.get("Generator1.P_MW_out") == 2.5
    finally:
        service.stop()


def test_gui_queue_updates_from_simulation(temp_hdf5: Path):
    event_bus = EventBus(buffer_size=256)
    rule_manager = SmartGridRuleManager()
    simulation = SmartGridSimulation(str(temp_hdf5), rule_manager, event_bus=event_bus)
    service = SCADAOrchestrationService(event_bus, simulation, rule_manager)
    service.start()

    try:
        service.request_step()
        timeout = time.time() + 2.0
        while time.time() < timeout:
            try:
                state = service.get_gui_queue().get_nowait()
                if state:
                    assert state.simulation_time >= 0.0
                    return
            except Exception:
                time.sleep(0.05)
        pytest.fail("No state update received from orchestration service")
    finally:
        service.stop()

"""
Tests for sally.domain — SCADAState, events, grid_entities.

Covers: SCADAState (thread-safe updates, snapshot, setpoints),
        all domain event types, GridMeasurement, EntityType.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import fields

import pytest

from tests.diag.metrics import record_metric


# ===========================================================================
# SCADAState
# ===========================================================================


class TestSCADAState:
    def _make_measurement(self, entity="GEN_1", p=100.0):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        return GridMeasurement(
            entity=entity,
            entity_type=EntityType.PYPOWER_NODE,
            timestamp=time.time(),
            p=p,
            q=10.0,
            vm=1.0,
        )

    def test_initial_state(self):
        from sally.domain.scada_state import SCADAState

        s = SCADAState()
        assert s.simulation_time == 0.0
        assert len(s.grid_measurements) == 0
        assert len(s.triggered_rules) == 0
        assert len(s.anomalies) == 0
        assert len(s.setpoints) == 0
        record_metric("scada_state_initial", 1, "bool")

    def test_update_measurement(self):
        from sally.domain.scada_state import SCADAState

        s = SCADAState()
        m = self._make_measurement()
        s.update_measurement(m)
        assert "GEN_1" in s.grid_measurements
        assert s.grid_measurements["GEN_1"].p == 100.0
        record_metric("scada_state_measurement", 1, "bool")

    def test_add_triggered_rule(self):
        from sally.domain.scada_state import SCADAState, RuleStatus

        s = SCADAState()
        rule = RuleStatus(
            rule_id="R1", entity_name="GEN_1",
            variable_name="P", action="shed_load",
            timestamp=time.time(),
        )
        s.add_triggered_rule(rule)
        assert len(s.triggered_rules) == 1
        assert s.triggered_rules[0].rule_id == "R1"
        record_metric("scada_state_rule", 1, "bool")

    def test_triggered_rules_max_history(self):
        from sally.domain.scada_state import SCADAState, RuleStatus

        s = SCADAState()
        for i in range(60):
            s.add_triggered_rule(
                RuleStatus(
                    rule_id=f"R{i}", entity_name="E",
                    variable_name="V", action="A",
                    timestamp=time.time(),
                ),
                max_history=50,
            )
        assert len(s.triggered_rules) == 50
        record_metric("scada_state_rule_max", 50, "rules")

    def test_add_anomaly(self):
        from sally.domain.scada_state import SCADAState, AnomalyInfo

        s = SCADAState()
        s.add_anomaly(AnomalyInfo(
            entity="NODE_1", anomaly_type="voltage_dip",
            severity="WARNING", timestamp=time.time(),
        ))
        assert len(s.anomalies) == 1
        record_metric("scada_state_anomaly", 1, "bool")

    def test_anomaly_max_history(self):
        from sally.domain.scada_state import SCADAState, AnomalyInfo

        s = SCADAState()
        for i in range(60):
            s.add_anomaly(
                AnomalyInfo(entity="E", anomaly_type="x", severity="INFO", timestamp=0.0),
                max_history=50,
            )
        assert len(s.anomalies) == 50
        record_metric("scada_state_anomaly_max", 50, "items")

    def test_setpoints(self):
        from sally.domain.scada_state import SCADAState

        s = SCADAState()
        s.update_setpoint("GEN_1.P_MW", 150.0)
        assert s.setpoints["GEN_1.P_MW"] == 150.0
        s.update_setpoint("GEN_1.P_MW", 200.0)
        assert s.setpoints["GEN_1.P_MW"] == 200.0
        record_metric("scada_state_setpoint", 1, "bool")

    def test_remove_setpoint(self):
        from sally.domain.scada_state import SCADAState

        s = SCADAState()
        s.update_setpoint("key", 42.0)
        assert s.remove_setpoint("key") is True
        assert s.remove_setpoint("key") is False  # already gone
        record_metric("scada_state_remove_sp", 1, "bool")

    def test_clear_setpoints(self):
        from sally.domain.scada_state import SCADAState

        s = SCADAState()
        s.update_setpoint("a", 1.0)
        s.update_setpoint("b", 2.0)
        s.clear_setpoints()
        assert len(s.setpoints) == 0
        record_metric("scada_state_clear_sp", 1, "bool")

    def test_simulation_time(self):
        from sally.domain.scada_state import SCADAState

        s = SCADAState()
        s.update_simulation_time(123.456)
        assert s.simulation_time == 123.456
        record_metric("scada_state_simtime", 1, "bool")

    def test_snapshot(self):
        from sally.domain.scada_state import SCADAState

        s = SCADAState()
        m = self._make_measurement()
        s.update_measurement(m)
        s.update_setpoint("gen.p", 100.0)
        snap = s.snapshot()
        assert snap is not s
        assert "GEN_1" in snap.grid_measurements
        assert snap.setpoints["gen.p"] == 100.0
        record_metric("scada_state_snapshot", 1, "bool")

    def test_thread_safety(self):
        from sally.domain.scada_state import SCADAState

        s = SCADAState()
        errors = []

        def writer():
            for i in range(200):
                try:
                    m = self._make_measurement(f"E_{i}", float(i))
                    s.update_measurement(m)
                    s.update_setpoint(f"sp_{i}", float(i))
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        record_metric("scada_state_threads", len(s.grid_measurements), "entities")


# ===========================================================================
# Domain Events
# ===========================================================================


class TestDomainEvents:
    def test_grid_data_event(self):
        from sally.domain.events import GridDataEvent
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(entity="N1", entity_type=EntityType.PYPOWER_NODE, timestamp=1.0, p=50.0)
        e = GridDataEvent(measurement=m)
        assert e.event_type == "grid_data_update"
        assert e.measurement.p == 50.0
        record_metric("event_grid_data", 1, "bool")

    def test_grid_alarm_event(self):
        from sally.domain.events import GridAlarmEvent

        e = GridAlarmEvent(entity="LINE_01", alarm_type="overload", severity="CRITICAL")
        assert e.event_type == "grid_alarm"
        assert e.severity == "CRITICAL"
        record_metric("event_grid_alarm", 1, "bool")

    def test_load_forecast_event(self):
        from sally.domain.events import LoadForecastEvent

        e = LoadForecastEvent(entity="LOAD_1", horizon_minutes=30, predicted_load=45.0)
        assert e.event_type == "load_forecast"
        assert e.predicted_load == 45.0
        record_metric("event_load_forecast", 1, "bool")

    def test_stability_event(self):
        from sally.domain.events import StabilityEvent

        e = StabilityEvent(
            affected_entities=["GEN_1", "GEN_2"],
            stability_metric="frequency",
            deviation_magnitude=0.5,
            risk_level="HIGH",
        )
        assert e.event_type == "stability_alert"
        assert len(e.affected_entities) == 2
        record_metric("event_stability", 1, "bool")

    def test_control_action_event(self):
        from sally.domain.events import ControlActionEvent

        e = ControlActionEvent(target_entity="GEN_1", action_type="voltage_regulation", control_value=1.05)
        assert e.event_type == "control_action"
        record_metric("event_control_action", 1, "bool")

    def test_rule_triggered_event(self):
        from sally.domain.events import RuleTriggeredEvent

        e = RuleTriggeredEvent(entity_name="PV_01", variable_name="P", threshold=100.0, actual_value=120.0)
        assert e.event_type == "rule_triggered"
        assert e.actual_value == 120.0
        record_metric("event_rule_triggered", 1, "bool")

    def test_simulation_step_event(self):
        from sally.domain.events import SimulationStepEvent

        e = SimulationStepEvent(timestep=42, simulation_time=630.0)
        assert e.event_type == "simulation_step"
        assert e.timestep == 42
        record_metric("event_sim_step", 1, "bool")

    def test_simulation_state_event(self):
        from sally.domain.events import SimulationStateEvent

        e = SimulationStateEvent(timestep=1, snapshot={"key": "val"})
        assert e.event_type == "simulation_state"
        assert e.snapshot["key"] == "val"
        record_metric("event_sim_state", 1, "bool")

    def test_setpoint_change_event(self):
        from sally.domain.events import SetpointChangeEvent

        e = SetpointChangeEvent(entity="GEN_1", variable="P_MW", old_value=100.0, new_value=150.0, source="gui")
        assert e.event_type == "setpoint_change"
        assert e.new_value == 150.0
        record_metric("event_setpoint_change", 1, "bool")

    def test_entity_relational_data_event(self):
        from sally.domain.events import EntityRelationalDataEvent, GridEntityData, GridConnectionData

        entities = [GridEntityData(entity_id=1, entity_name="GEN_1", entity_type="generator")]
        connections = [GridConnectionData(from_entity_id=1, to_entity_id=2, connection_type="line")]
        e = EntityRelationalDataEvent(entities=entities, connections=connections, operation="upsert")
        assert e.event_type == "entity_relational_data"
        assert len(e.entities) == 1
        assert len(e.connections) == 1
        record_metric("event_entity_relational", 1, "bool")


# ===========================================================================
# GridMeasurement & EntityType
# ===========================================================================


class TestGridMeasurement:
    def test_validate_pypower_node(self):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="NODE_01", entity_type=EntityType.PYPOWER_NODE, timestamp=1.0,
            p=50.0, q=10.0, va=0.01, vl=138.0, vm=1.0,
        )
        assert m.validate_measurements() is True
        record_metric("grid_meas_valid_node", 1, "bool")

    def test_validate_missing_required(self):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="NODE_01", entity_type=EntityType.PYPOWER_NODE, timestamp=1.0,
            p=50.0,  # missing q, va, vl, vm
        )
        assert m.validate_measurements() is False
        record_metric("grid_meas_invalid", 1, "bool")

    def test_validate_branch(self):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="LINE_01", entity_type=EntityType.PYPOWER_BRANCH, timestamp=1.0,
            p_from=100.0, p_to=98.0, q_from=20.0,
        )
        assert m.validate_measurements() is True
        record_metric("grid_meas_branch", 1, "bool")

    def test_validate_pandapower_bus(self):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="BUS_1", entity_type=EntityType.PANDAPOWER_BUS, timestamp=1.0,
            vm_pu=1.02, va_degree=0.5,
        )
        assert m.validate_measurements() is True
        record_metric("grid_meas_pp_bus", 1, "bool")

    def test_to_guardian_bus_format(self):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="BUS_1", entity_type=EntityType.PANDAPOWER_BUS, timestamp=1.0,
            vm_pu=1.02, va_degree=2.5, p_mw=50.0, q_mvar=10.0,
        )
        gf = m.to_guardian_format("bus")
        assert gf["vm_pu"] == 1.02
        assert gf["va_degree"] == 2.5
        assert gf["p_mw"] == 50.0
        record_metric("grid_meas_guardian_bus", 1, "bool")

    def test_to_guardian_load_format(self):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="LOAD_1", entity_type=EntityType.PANDAPOWER_LOAD, timestamp=1.0,
            p_mw=25.0, q_mvar=5.0,
        )
        gf = m.to_guardian_format("load")
        assert gf["p_mw"] == 25.0
        assert gf["q_mvar"] == 5.0
        record_metric("grid_meas_guardian_load", 1, "bool")

    def test_to_guardian_trafo_format(self):
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="TR_1", entity_type=EntityType.PANDAPOWER_TRAFO, timestamp=1.0,
            loading_percent=85.0,
        )
        gf = m.to_guardian_format("trafo")
        assert gf["loading_percent"] == 85.0
        record_metric("grid_meas_guardian_trafo", 1, "bool")

    def test_to_guardian_py_to_pp_conversion(self):
        """PyPower-style measurements converted to PandaPower fields."""
        from sally.domain.grid_entities import GridMeasurement, EntityType

        m = GridMeasurement(
            entity="BUS_X", entity_type=EntityType.PYPOWER_NODE, timestamp=1.0,
            p=75.0, q=15.0, vm=1.01, va=0.05,
        )
        gf = m.to_guardian_format("bus")
        assert gf["vm_pu"] == 1.01
        assert gf["p_mw"] == 75.0
        assert gf["q_mvar"] == 15.0
        # va converted from radians to degrees
        assert gf["va_degree"] == pytest.approx(math.degrees(0.05), abs=0.01)
        record_metric("grid_meas_py_to_pp", 1, "bool")


class TestEntityType:
    def test_all_entity_types_exist(self):
        from sally.domain.grid_entities import EntityType

        expected = [
            "PYPOWER_NODE", "PYPOWER_BRANCH", "PYPOWER_TR_PRI", "PYPOWER_TR_SEC",
            "PYPOWER_TRANSFORMER", "PANDAPOWER_BUS", "PANDAPOWER_LOAD",
            "PANDAPOWER_SGEN", "PANDAPOWER_TRAFO", "PANDAPOWER_LINE",
            "PANDAPOWER_SWITCH", "PANDAPOWER_EXT_GRID",
            "HOUSEHOLD_SIM", "CSV_PV", "WIND_TURBINE", "BATTERY_ESS", "LOAD_BUS",
        ]
        for name in expected:
            assert hasattr(EntityType, name), f"Missing EntityType.{name}"
        record_metric("entity_types_count", len(expected), "types")

    def test_enum_values_are_strings(self):
        from sally.domain.grid_entities import EntityType

        for et in EntityType:
            assert isinstance(et.value, str)
        record_metric("entity_type_values", len(EntityType), "types")

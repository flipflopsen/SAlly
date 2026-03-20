from random import random
from typing import Dict, Any, List
from dependency_injector.wiring import inject
from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator

# TODO: Move this into constructor or some setter
STEP_SIZE = 1

LINE_SIM_ID = 'LineSim'
LINE_META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'TransmissionLine': {
            'public': True,
            'params': ['from_node_eid', 'to_node_eid', 'resistance_ohm', 'reactance_ohm', 'thermal_limit_kA',
                        'length_km', 'base_voltage_kV'],
            'attrs': ['P_MW_flow', 'Q_MVAR_flow', 'current_kA', 'status', 'loading_percent'],
            # status: 'in_service', 'tripped_overload', 'tripped_fault'
        },
    },
    'extra_methods': ['trigger_trip_ext'],
}

class LineSim(BaseMosaikSimulator):
    @inject
    def __init__(self, logger=None, event_bus=None):
        super().__init__(LINE_META, logger, event_bus)
        self.eid_prefix = "Line"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0):
        return super().init(sid, time_resolution, eid_prefix, sim_start_time)

    def create(self, num: int, model: str, **model_params) -> List[Dict[str, Any]]:
        # Validate required parameters
        required_params = ['from_node_eid', 'to_node_eid', 'resistance_ohm', 'reactance_ohm', 'thermal_limit_kA', 'base_voltage_kV']
        if not self.validate_entity_params(model_params, required_params):
            return []

        entities = []
        for i in range(num):
            eid = self.get_entity_id(model)
            self.entities[eid] = {
                'type': model,
                'from_node_eid': model_params['from_node_eid'],
                # Informational, not directly used in this simplified step
                'to_node_eid': model_params['to_node_eid'],  # Informational
                'R_ohm': model_params['resistance_ohm'],
                'X_ohm': model_params['reactance_ohm'],
                'thermal_limit_kA': model_params['thermal_limit_kA'],
                'base_voltage_kV': model_params['base_voltage_kV'],
                'P_MW_flow': 0.0,  # Positive from 'from_node' to 'to_node'
                'Q_MVAR_flow': 0.0,
                'current_kA': 0.0,
                'status': 'in_service',
                'loading_percent': 0.0,
            }
            entities.append({'eid': eid, 'type': model})
            self.log_info(f"Created Line {eid} from {model_params['from_node_eid']} to {model_params['to_node_eid']}")
        return entities

    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        self.log_info(f"Step at time {time}. Inputs: {inputs}")
        for eid, attrs in inputs.items():
            entity = self.entities[eid]
            if entity['status'] != 'in_service':
                entity['P_MW_flow'] = 0.0
                entity['Q_MVAR_flow'] = 0.0
                entity['current_kA'] = 0.0
                entity['loading_percent'] = 0.0
                continue

            # Simplified power flow: P = (V_from - V_to) / X (DC power flow approximation on X for P)
            # This is a MAJOR simplification. Real power flow is needed for accuracy.
            # We'd need voltage magnitude and angle from both connected nodes.
            # For now, let's assume MonitorSim or NodeSim provides an estimate of flow or we make it up.
            # Let's assume the 'inputs' might contain P_flow_calc from a (non-existent) power flow engine

            # Placeholder: Get P_demand and P_generation from connected nodes (passed via Monitor or Scenario)
            # P_node_from_supply = attrs.get('node_from_P_supply', {}).get(0.0, 0.0)
            # P_node_to_demand = attrs.get('node_to_P_demand', {}).get(0.0, 0.0)
            # This model is too simple to calculate flow accurately based on node states directly.
            # Let's make the line flow a fraction of connected generation/load for demo purposes.
            # This is NOT a physical model.

            # A slightly more plausible placeholder:
            # Assume flow is externally calculated and passed in, or set randomly for now
            # This attribute would be set by a PowerFlow simulator in a real scenario.
            # For this example, let's assume NodeSim calculates some imbalance that this line might carry.

            V_from_mag_pu = attrs.get('V_from_node_mag_pu', {}).get(1.0, 1.0)
            V_to_mag_pu = attrs.get('V_to_node_mag_pu', {}).get(1.0, 1.0)
            # Angle_from_rad = attrs.get('Angle_from_node_rad', {}).get(0.0, 0.0) # Need angles for AC flow
            # Angle_to_rad = attrs.get('Angle_to_node_rad', {}).get(0.0, 0.0)

            # Super simplified P flow: proportional to voltage difference, assuming X dominates R
            # P_MW = (V_from_mag_pu - V_to_mag_pu) * 100 # Arbitrary scaling factor
            # This is still very crude.
            # Let's make flow responsive to some imbalance signal for demo.
            # P_imbalance_signal = attrs.get('node_imbalance_MW', {}).get(0.0, 0.0) # From a connected node
            # entity['P_MW_flow'] = P_imbalance_signal * 0.3 # Line carries 30% of some fictive imbalance

            # Let's make the line model respond to a 'P_schedule_MW' input, which would typically come from an EMS or OPF
            # This way, we can control the flow for demonstration purposes.
            entity['P_MW_flow'] = attrs.get('P_schedule_MW', {}).get(random.uniform(-5, 5), random.uniform(-5,
                                                                                                           5))  # Default random flow if not scheduled
            entity['Q_MVAR_flow'] = entity['P_MW_flow'] * 0.1  # Arbitrary Q

            # Calculate current and loading
            S_MVA = (entity['P_MW_flow'] ** 2 + entity['Q_MVAR_flow'] ** 2) ** 0.5
            if entity['base_voltage_kV'] > 0:
                entity['current_kA'] = S_MVA / ((3 ** 0.5) * entity['base_voltage_kV']) if entity[
                                                                                               'base_voltage_kV'] > 0 else 0
            else:
                entity['current_kA'] = 0

            if entity['thermal_limit_kA'] > 0:
                entity['loading_percent'] = (entity['current_kA'] / entity['thermal_limit_kA']) * 100
            else:
                entity['loading_percent'] = 0

            # Check for overload trip (internal logic)
            if entity['loading_percent'] > 110.0:  # Trip if overloaded beyond 110%
                entity['status'] = 'tripped_overload'
                self.log_info(f"Entity {eid}: TRIPPED due to overload! Loading: {entity['loading_percent']:.1f}%")
                # This is part of cascading failure initiation

            self.log_info(f"Entity {eid}: P_flow: {entity['P_MW_flow']:.2f} MW, I: {entity['current_kA']:.3f} kA, Load: {entity['loading_percent']:.1f}%, Status: {entity['status']}")

        return time + STEP_SIZE

    def get_data(self, outputs: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        data = {}
        for eid, attrs in outputs.items():
            if eid in self.entities:
                data[eid] = {}
                for attr in attrs:
                    if attr in self.entities[eid]:
                        data[eid][attr] = self.entities[eid][attr]
                    else:
                        self.log_warning(f"Attribute {attr} not found for entity {eid}")
        return data

    def trigger_trip_ext(self, time: int, eid: str, cause: str = "external_fault") -> Dict[str, Any]:
        if eid in self.entities:
            self.entities[eid]['status'] = f'tripped_{cause}'
            self.log_info(f"Entity {eid}: Line tripped by external command at {time} due to {cause}.")
        else:
            self.log_warning(f"Entity {eid} not found for trip command")
        return {}

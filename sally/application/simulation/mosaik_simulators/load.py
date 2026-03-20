from random import random
from typing import Dict, Any, List
from dependency_injector.wiring import inject
from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator

# TODO: Move this into constructor or some setter
STEP_SIZE = 1

LOAD_SIM_ID = 'LoadSim'
LOAD_META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'ResidentialLoad': {
            'public': True,
            'params': ['base_P_MW_profile', 'base_Q_MVAR_profile', 'voltage_sensitivity_P', 'voltage_sensitivity_Q'],
            'attrs': ['P_MW_actual', 'Q_MVAR_actual', 'node_voltage_kV'],
        },
    },
    'extra_methods': ['trigger_demand_spike'],
}


class LoadSim(BaseMosaikSimulator):
    @inject
    def __init__(self, logger=None, event_bus=None):
        super().__init__(LOAD_META, logger, event_bus)
        self.eid_prefix = "Load"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0, nominal_voltage_kV=1.0):
        super().init(sid, time_resolution, eid_prefix, sim_start_time)
        self.nominal_voltage_kV = nominal_voltage_kV  # Used for voltage sensitivity calc
        return self.meta

    def create(self, num: int, model: str, **model_params) -> List[Dict[str, Any]]:
        entities = []
        for i in range(num):
            eid = self.get_entity_id(model)

            # Create default profiles if not provided
            default_P_profile = [0.5 + 0.5 * random.uniform(0.8, 1.2) * (i % 2 + 1) for _ in
                                  range(24 * 3600 // STEP_SIZE + 1)]  # 24 hours worth of data
            default_Q_profile = [p * 0.1 for p in default_P_profile]

            self.entities[eid] = {
                'type': model,
                'base_P_MW_profile': model_params.get('base_P_MW_profile', default_P_profile),
                'base_Q_MVAR_profile': model_params.get('base_Q_MVAR_profile', default_Q_profile),
                'voltage_sensitivity_P': model_params.get('voltage_sensitivity_P', 0.5),  # e.g., P = P0 * (V/V0)^alpha
                'voltage_sensitivity_Q': model_params.get('voltage_sensitivity_Q', 1.0),
                'P_MW_actual': 0.0,
                'Q_MVAR_actual': 0.0,
                'spike_factor': 1.0,
                'spike_duration_steps': 0,
            }
            entities.append({'eid': eid, 'type': model})
            self.log_info(f"Created Load {eid}")
        return entities

    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        self.log_info(f"Step at time {time}. Inputs: {inputs}")
        sim_step_idx = int((time - self.sim_start_time) / STEP_SIZE)

        for eid, attrs in inputs.items():
            entity = self.entities[eid]

            # Get base load for current time step
            p_profile_len = len(entity['base_P_MW_profile'])
            q_profile_len = len(entity['base_Q_MVAR_profile'])

            base_P = entity['base_P_MW_profile'][sim_step_idx % p_profile_len] if p_profile_len > 0 else 0.5
            base_Q = entity['base_Q_MVAR_profile'][sim_step_idx % q_profile_len] if q_profile_len > 0 else 0.1

            # Apply voltage sensitivity (simplified ZIP model component)
            # Assuming V_nominal is implicitly handled by the profile being at nominal voltage
            # Here, voltage_kV is the actual voltage from the node.
            voltage_kV_actual = attrs.get('node_voltage_kV', {}).get(self.nominal_voltage_kV, self.nominal_voltage_kV)
            voltage_pu = voltage_kV_actual / self.nominal_voltage_kV if self.nominal_voltage_kV > 0 else 1.0

            P_MW = base_P * (voltage_pu ** entity['voltage_sensitivity_P'])
            Q_MVAR = base_Q * (voltage_pu ** entity['voltage_sensitivity_Q'])

            # Apply spike if active
            if entity['spike_duration_steps'] > 0:
                P_MW *= entity['spike_factor']
                Q_MVAR *= entity['spike_factor']
                entity['spike_duration_steps'] -= 1
                if entity['spike_duration_steps'] == 0:
                    entity['spike_factor'] = 1.0  # Reset spike
                    self.log_info(f"Entity {eid}: Demand spike ended.")

            entity['P_MW_actual'] = P_MW
            entity['Q_MVAR_actual'] = Q_MVAR

            self.log_info(f"Entity {eid}: P_actual: {P_MW:.2f} MW, Q_actual: {Q_MVAR:.2f} MVAR (V_pu: {voltage_pu:.3f})")
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

    def trigger_demand_spike(self, time: int, eid: str, factor: float, duration_steps: int) -> Dict[str, Any]:
        if eid in self.entities:
            self.entities[eid]['spike_factor'] = float(factor)
            self.entities[eid]['spike_duration_steps'] = int(duration_steps)
            self.log_info(f"Entity {eid}: Demand spike triggered: factor {factor}, duration {duration_steps} steps at {time}.")
        else:
            self.log_warning(f"Entity {eid} not found for demand spike trigger")
        return {}

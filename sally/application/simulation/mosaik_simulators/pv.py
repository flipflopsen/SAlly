from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator
from typing import Dict, Any, List
from dependency_injector.wiring import inject

# TODO: Move this into constructor or some setter
STEP_SIZE = 1

PV_SIM_ID = 'PVSim'
PV_META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'PVSystem': {
            'public': True,
            'params': ['max_P_MW', 'irradiance_profile'],  # irradiance_profile is list of factors (0-1)
            'attrs': ['P_MW_out', 'Q_MVAR_out', 'curtailment_MW'],
        },
    },
    'extra_methods': ['set_curtailment'],
}


class PVSim(BaseMosaikSimulator):
    @inject
    def __init__(self, logger=None, event_bus=None):
        super().__init__(PV_META, logger, event_bus)
        self.eid_prefix = "PV"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0):
        return super().init(sid, time_resolution, eid_prefix, sim_start_time)

    def create(self, num: int, model: str, **model_params) -> List[Dict[str, Any]]:
        # Validate required parameters
        required_params = ['max_P_MW']
        if not self.validate_entity_params(model_params, required_params):
            return []

        entities = []
        for i in range(num):
            eid = self.get_entity_id(model)

            # Create default irradiance profile if not provided
            default_irradiance = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 0.9, 0.7, 0.5, 0.3] * (
                        24 * 3600 // 10 + 1)  # Simple daily pattern for 24 hours
            irradiance_profile = model_params.get('irradiance_profile', default_irradiance)

            self.entities[eid] = {
                'type': model,
                'max_P_MW': model_params['max_P_MW'],
                'irradiance_profile': irradiance_profile,
                'P_MW_out': 0.0,
                'Q_MVAR_out': 0.0,  # Simplified Q
                'curtailment_MW': 0.0,  # Amount of power being curtailed
            }
            entities.append({'eid': eid, 'type': model})
            self.log_info(f"Created PVSystem {eid} with P_max: {model_params['max_P_MW']} MW")
        return entities

    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        self.log_info(f"Step at time {time}")
        sim_step_idx = int((time - self.sim_start_time) / STEP_SIZE)  # Assuming step_size matches time_resolution

        for eid, entity in self.entities.items():
            # Get irradiance for current time step
            profile_len = len(entity['irradiance_profile'])
            irradiance_factor = entity['irradiance_profile'][sim_step_idx % profile_len] if profile_len > 0 else 0.5

            available_P_MW = entity['max_P_MW'] * irradiance_factor

            # Apply curtailment
            actual_P_MW = max(0, available_P_MW - entity['curtailment_MW'])

            entity['P_MW_out'] = actual_P_MW
            entity['Q_MVAR_out'] = actual_P_MW * 0.05  # Arbitrary Q, typically close to unity PF

            self.log_info(f"Entity {eid}: Irradiance factor: {irradiance_factor:.2f}, Available P: {available_P_MW:.2f} MW, Curtailed P: {entity['curtailment_MW']:.2f} MW, P_out: {entity['P_MW_out']:.2f} MW")
        return time + STEP_SIZE

    def get_data(self, outputs: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        data = {}
        self.log_info(f"Get_data called. Outputs: {outputs}")
        for eid, attrs in outputs.items():
            if eid in self.entities:
                data[eid] = {}
                for attr in attrs:
                    if attr in self.entities[eid]:
                        data[eid][attr] = self.entities[eid][attr]
                    else:
                        self.log_warning(f"Attribute {attr} not found for entity {eid}")
        return data

    def set_curtailment(self, time: int, eid: str, curtail_P_MW: float) -> Dict[str, Any]:
        if eid in self.entities:
            self.entities[eid]['curtailment_MW'] = float(curtail_P_MW)
            self.log_info(f"Entity {eid}: Received curtailment command: {curtail_P_MW:.2f} MW at {time}")
        else:
            self.log_warning(f"Entity {eid} not found for curtailment command")
        return {}

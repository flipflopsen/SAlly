from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator
from sally.core.logger import Pprint
from typing import Dict, Any, List, Optional


STEP_SIZE = 1

GEN_SIM_ID = 'GeneratorSim'
GEN_META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'Generator': {
            'public': True,
            'params': ['max_P_MW', 'min_P_MW', 'ramping_rate_MW_per_step', 'base_voltage_kV', 'droop_coeff'],
            'attrs': ['P_MW_out', 'Q_MVAR_out', 'voltage_kV', 'frequency_Hz', 'status', 'P_setpoint_MW', 'grid_frequency_Hz'],
        },
    },
    'extra_methods': ['trigger_trip', 'set_power_setpoint'],
}


class GeneratorSim(BaseMosaikSimulator):
    """Enhanced Generator simulator with dependency injection support"""

    def __init__(self, logger=None, event_bus=None):
        super().__init__(GEN_META, logger, event_bus)
        self.eid_prefix = "Gen"
        self.grid_frequency_nominal = 50.0

    def init(self, sid: str, time_resolution: float, eid_prefix: Optional[str] = None,
             sim_start_time: float = 0, grid_frequency_nominal: float = 50.0, **kwargs) -> Dict[str, Any]:
        # Call parent init
        result = super().init(sid, time_resolution, eid_prefix, sim_start_time, **kwargs)

        # Set generator-specific parameters
        self.grid_frequency_nominal = grid_frequency_nominal

        self.log_info(f"GeneratorSim initialized. Time resolution: {time_resolution}, "
                     f"Start time: {sim_start_time}, Nominal frequency: {grid_frequency_nominal} Hz")

        return result

    def create(self, num: int, model: str, **model_params) -> List[Dict[str, Any]]:
        """Create generator entities with validation"""
        required_params = ['max_P_MW', 'min_P_MW', 'ramping_rate_MW_per_step', 'base_voltage_kV']

        if not self.validate_entity_params(model_params, required_params):
            return []

        entities = []
        for i in range(num):
            eid = self.get_entity_id(model)

            # Create entity data with validation
            entity_data = {
                'type': model,
                'max_P_MW': model_params['max_P_MW'],
                'min_P_MW': model_params['min_P_MW'],
                'ramping_rate': model_params['ramping_rate_MW_per_step'],
                'base_voltage_kV': model_params['base_voltage_kV'],
                'droop_coeff': model_params.get('droop_coeff', 0.05),  # 5% droop
                'P_MW_out': model_params['min_P_MW'],  # Start at min output
                'Q_MVAR_out': 0.0,  # Simplified Q
                'voltage_kV': model_params['base_voltage_kV'],
                'frequency_Hz': self.grid_frequency_nominal,
                'status': 'online',  # 'online', 'tripped', 'ramping'
                'P_setpoint_MW': model_params['min_P_MW'],
                'target_P_MW': model_params['min_P_MW'],  # For ramping
            }

            self.entities[eid] = entity_data
            entities.append({'eid': eid, 'type': model})

            self.log_info(f"Created Generator {eid} with capacity {model_params['max_P_MW']} MW")

        return entities

    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        """Advance simulation by one step with enhanced logging"""
        self.log_info(f"Step at time {time}. Processing {len(inputs)} inputs")

        for eid, attrs in inputs.items():
            entity = self.get_entity_by_id(eid)
            if not entity:
                self.log_warning(f"Entity {eid} not found")
                continue

            if entity['status'] == 'tripped':
                entity['P_MW_out'] = 0.0
                entity['Q_MVAR_out'] = 0.0
                continue

            # Process inputs (e.g., frequency from grid for droop, external setpoints)
            grid_freq = attrs.get('grid_frequency_Hz', {}).get(self.grid_frequency_nominal,
                                                               self.grid_frequency_nominal)

            # Droop control (simplified)
            if entity['droop_coeff'] > 0:
                delta_f = self.grid_frequency_nominal - grid_freq
                # Simplified droop response - in practice this would be more complex
                pass  # Droop logic would be more complex; simplify by relying on external setpoint

            # Ramping to target_P_MW
            current_P = entity['P_MW_out']
            target_P = entity['target_P_MW']

            if abs(target_P - current_P) < 0.01:  # Close enough
                entity['P_MW_out'] = target_P
            elif target_P > current_P:
                entity['P_MW_out'] = min(target_P, current_P + entity['ramping_rate'])
            else:  # target_P < current_P
                entity['P_MW_out'] = max(target_P, current_P - entity['ramping_rate'])

            entity['P_MW_out'] = max(entity['min_P_MW'], min(entity['max_P_MW'], entity['P_MW_out']))
            entity['P_setpoint_MW'] = entity['target_P_MW']  # Update current working setpoint

            # Simplified voltage and Q (would depend on AVR and grid interaction)
            entity['voltage_kV'] = entity['base_voltage_kV']  # Assume constant for now
            entity['Q_MVAR_out'] = entity['P_MW_out'] * 0.1  # Arbitrary Q

            self.log_info(f"Generator {eid}: P_out={entity['P_MW_out']:.2f} MW, Status={entity['status']}")

        return time + STEP_SIZE

    def get_data(self, outputs: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        """Get data for specified entities and attributes with enhanced logging"""
        self.log_info(f"Get_data called for {len(outputs)} entities")
        return super().get_data(outputs)

    def trigger_trip(self, time: int, eid: str, cause: str = "unknown") -> Dict[str, Any]:
        """Trigger generator trip with enhanced logging"""
        if eid in self.entities:
            entity = self.entities[eid]
            entity['status'] = 'tripped'
            entity['P_MW_out'] = 0.0
            entity['Q_MVAR_out'] = 0.0
            self.log_info(f"Generator {eid} tripped at {time} due to {cause}")

            # Publish trip event
            self.publish_event("generator_trip", {
                "generator_id": eid,
                "time": time,
                "cause": cause
            })
        else:
            self.log_warning(f"Generator {eid} not found for trip command")
        return {}

    def set_power_setpoint(self, time: int, eid: str, P_setpoint_MW: float) -> Dict[str, Any]:
        """Set power setpoint with validation and logging"""
        entity = self.get_entity_by_id(eid)
        if not entity:
            self.log_warning(f"Generator {eid} not found for setpoint command")
            return {}

        if entity['status'] != 'online':
            self.log_warning(f"Generator {eid} is not online (status: {entity['status']})")
            return {}

        target_P = float(P_setpoint_MW)
        entity['target_P_MW'] = max(entity['min_P_MW'], min(entity['max_P_MW'], target_P))

        self.log_info(f"Generator {eid} setpoint updated to {target_P:.2f} MW at {time}")

        # Publish setpoint change event
        self.publish_event("generator_setpoint_change", {
            "generator_id": eid,
            "time": time,
            "old_setpoint": entity.get('P_setpoint_MW', 0),
            "new_setpoint": target_P
        })

        return {}

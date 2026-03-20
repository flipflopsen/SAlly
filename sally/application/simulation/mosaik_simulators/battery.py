from typing import Dict, Any, List
from dependency_injector.wiring import inject
from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator

# TODO: Move this into constructor or some setter
STEP_SIZE = 1

BATTERY_SIM_ID = 'BatterySim'
BATTERY_META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'BatteryStorage': {
            'public': True,
            'params': ['capacity_MWh', 'max_P_charge_MW', 'max_P_discharge_MW', 'efficiency_pct', 'initial_SoC_pct'],
            'attrs': ['P_MW_out', 'Q_MVAR_out', 'SoC_pct', 'status', 'grid_frequency_Hz'],  # P_out > 0 for discharge, < 0 for charge
        },
    },
    'extra_methods': ['set_power_dispatch'],  # P_dispatch_MW: + for discharge, - for charge
}


class BatterySim(BaseMosaikSimulator):
    @inject
    def __init__(self, logger=None, event_bus=None):
        super().__init__(BATTERY_META, logger, event_bus)
        self.eid_prefix = "Batt"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0):
        super().init(sid, time_resolution, eid_prefix, sim_start_time)
        self.time_resolution_seconds = time_resolution  # Assuming Mosaik gives this in seconds
        return self.meta

    def create(self, num: int, model: str, **model_params) -> List[Dict[str, Any]]:
        # Validate required parameters
        required_params = ['capacity_MWh', 'max_P_charge_MW', 'max_P_discharge_MW']
        if not self.validate_entity_params(model_params, required_params):
            return []

        entities = []
        for i in range(num):
            eid = self.get_entity_id(model)
            self.entities[eid] = {
                'type': model,
                'capacity_MWh': model_params['capacity_MWh'],
                'max_P_charge_MW': abs(model_params['max_P_charge_MW']),  # Ensure positive
                'max_P_discharge_MW': abs(model_params['max_P_discharge_MW']),
                'efficiency': model_params.get('efficiency_pct', 90.0) / 100.0,
                'SoC_MWh': model_params['capacity_MWh'] * (model_params.get('initial_SoC_pct', 50.0) / 100.0),
                'P_MW_out': 0.0,  # Current power output/input
                'Q_MVAR_out': 0.0,  # Simplified Q
                'SoC_pct': model_params.get('initial_SoC_pct', 50.0),
                'status': 'idle',  # 'charging', 'discharging', 'idle', 'full', 'empty'
                'P_dispatch_MW': 0.0,  # Requested power
            }
            entities.append({'eid': eid, 'type': model})
            self.log_info(f"Created Battery {eid} with {model_params['capacity_MWh']} MWh capacity")
        return entities

    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        self.log_info(f"Step at time {time}. Inputs: {inputs}")
        delta_t_hours = self.time_resolution_seconds / 3600.0

        for eid, attrs in inputs.items():  # Inputs are for control signals here
            entity = self.entities[eid]

            # Get dispatch signal (might come from RemediationSim)
            # P_dispatch_MW is set by the extra_method 'set_power_dispatch'
            requested_P_MW = entity['P_dispatch_MW']

            # Add frequency response logic (simplified)
            grid_freq = attrs.get('grid_frequency_Hz', {}).get(50.0, 50.0)  # Default to nominal
            freq_deadband = 0.05  # Hz
            freq_droop = 0.05  # 5% droop for full power

            P_freq_response = 0.0
            if abs(grid_freq - 50.0) > freq_deadband:
                # If freq low, discharge; if freq high, charge (if possible)
                # P_support = (50.0 - grid_freq) / (freq_droop * 50.0) * entity['max_P_discharge_MW'] # Proportional
                # Simplified fixed response for demo
                if grid_freq < (50.0 - freq_deadband):  # Under-frequency
                    P_freq_response = entity['max_P_discharge_MW'] * 0.2  # Discharge at 20% of max rate
                elif grid_freq > (50.0 + freq_deadband):  # Over-frequency
                    P_freq_response = -entity['max_P_charge_MW'] * 0.2  # Charge at 20% of max rate

            # Combine dispatch and freq response (dispatch takes precedence if conflicting for simplicity)
            # A more robust system would coordinate these.
            final_P_MW_target = requested_P_MW + P_freq_response

            actual_P_MW = 0.0

            if final_P_MW_target > 0:  # Requesting discharge
                available_energy_MWh = entity['SoC_MWh']
                potential_discharge_P_MW = min(final_P_MW_target, entity['max_P_discharge_MW'],
                                               available_energy_MWh / (delta_t_hours / entity['efficiency']))
                actual_P_MW = potential_discharge_P_MW
                entity['SoC_MWh'] -= actual_P_MW * delta_t_hours / entity['efficiency']
                entity['status'] = 'discharging' if actual_P_MW > 0.01 else 'idle'
            elif final_P_MW_target < 0:  # Requesting charge
                required_energy_MWh = entity['capacity_MWh'] - entity['SoC_MWh']
                potential_charge_P_MW = min(abs(final_P_MW_target), entity['max_P_charge_MW'],
                                            required_energy_MWh / (delta_t_hours * entity['efficiency']))
                actual_P_MW = -potential_charge_P_MW  # Negative for charging
                entity['SoC_MWh'] += abs(actual_P_MW) * delta_t_hours * entity['efficiency']
                entity['status'] = 'charging' if actual_P_MW < -0.01 else 'idle'
            else:
                entity['status'] = 'idle'

            entity['SoC_MWh'] = max(0, min(entity['capacity_MWh'], entity['SoC_MWh']))
            entity['SoC_pct'] = (entity['SoC_MWh'] / entity['capacity_MWh']) * 100 if entity['capacity_MWh'] > 0 else 0

            if entity['SoC_pct'] >= 99.9: entity['status'] = 'full'
            if entity['SoC_pct'] <= 0.1: entity['status'] = 'empty'

            entity['P_MW_out'] = actual_P_MW
            entity['Q_MVAR_out'] = actual_P_MW * 0.02  # Small arbitrary Q

            self.log_info(f"Entity {eid}: Target P: {final_P_MW_target:.2f}, Actual P_out: {entity['P_MW_out']:.2f} MW, SoC: {entity['SoC_pct']:.1f}%, Status: {entity['status']}")

            # Reset dispatch for next step, expecting new command
            entity['P_dispatch_MW'] = 0.0

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

    def set_power_dispatch(self, time: int, eid: str, P_dispatch_MW: float) -> Dict[str, Any]:
        if eid in self.entities:
            self.entities[eid]['P_dispatch_MW'] = float(P_dispatch_MW)
            self.log_info(f"Entity {eid}: Received power dispatch: {P_dispatch_MW:.2f} MW at {time}")
        else:
            self.log_warning(f"Entity {eid} not found for power dispatch command")
        return {}

from typing import Dict, Any, List
from dependency_injector.wiring import inject
from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator

# TODO: Move this into constructor or some setter
STEP_SIZE = 1

NODE_SIM_ID = 'NodeSim'
NODE_META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'BusNode': {
            'public': True,
            'params': ['base_voltage_kV', 'is_slack_bus'],
            'attrs': [
                'voltage_kV', 'voltage_pu', 'frequency_Hz', 'P_imbalance_MW',
                'connected_generators', 'connected_loads', 'connected_lines_from', 'connected_lines_to',

                'gen_sum_P_MW', 'gen_sum_Q_MVAR',
                'load_sum_P_MW', 'load_sum_Q_MVAR',
                'line_sum_P_in_MW', 'line_sum_Q_in_MVAR',
                'line_sum_P_out_MW', 'line_sum_Q_out_MVAR',
                'system_total_P_imbalance_MW',
            ],
        },
    },
}


class NodeSim(BaseMosaikSimulator):
    @inject
    def __init__(self, logger=None, event_bus=None):
        super().__init__(NODE_META, logger, event_bus)
        self.eid_prefix = "Node"
        self.nominal_freq = 50.0

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0, nominal_frequency_Hz=50.0):
        super().init(sid, time_resolution, eid_prefix, sim_start_time)
        self.nominal_freq = nominal_frequency_Hz
        return self.meta

    def create(self, num: int, model: str, **model_params) -> List[Dict[str, Any]]:
        # Validate required parameters
        required_params = ['base_voltage_kV']
        if not self.validate_entity_params(model_params, required_params):
            return []

        entities = []
        for i in range(num):
            eid = self.get_entity_id(model)
            self.entities[eid] = {
                'type': model,
                'base_voltage_kV': model_params['base_voltage_kV'],
                'is_slack_bus': model_params.get('is_slack_bus', False),
                'voltage_kV': model_params['base_voltage_kV'],
                'voltage_pu': 1.0,
                'frequency_Hz': self.nominal_freq,
                'P_imbalance_MW': 0.0,
                'Q_imbalance_MVAR': 0.0,  # Added for reactive power balance
                'P_gen_total_MW': 0.0,
                'Q_gen_total_MVAR': 0.0,
                'P_load_total_MW': 0.0,
                'Q_load_total_MVAR': 0.0,
                'P_line_flow_in_MW': 0.0,
                'Q_line_flow_in_MVAR': 0.0,
                'P_line_flow_out_MW': 0.0,
                'Q_line_flow_out_MVAR': 0.0,
                'system_P_imbalance_MW_input': 0.0,  # Store input from monitor
                'connected_generators': [],
                'connected_loads': [],
                'connected_lines_from': [],
                'connected_lines_to': [],
            }
            entities.append({'eid': eid, 'type': model})
            self.log_info(f"Created Node {eid} (Base V: {model_params['base_voltage_kV']} kV)")
        return entities

    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        self.log_info(f"Step at time {time}. Inputs: {inputs}")

        for eid, entity_inputs_from_mosaik in inputs.items():
            entity = self.entities[eid]

            # Reset sums for the current step
            current_P_gen_total = 0.0
            current_Q_gen_total = 0.0
            current_P_load_total = 0.0
            current_Q_load_total = 0.0
            current_P_line_in_total = 0.0
            current_Q_line_in_total = 0.0
            current_P_line_out_total = 0.0
            current_Q_line_out_total = 0.0
            # No need to reset entity['system_P_imbalance_MW_input'] as it's overwritten

            for input_key, data_map in entity_inputs_from_mosaik.items():
                if not data_map:  # Skip if data_map is empty
                    self.log_warning(f"Entity {eid}: Empty data_map for input_key '{input_key}'")
                    continue

                # Mosaik passes input test_data as a dictionary, typically {'value': actual_value}
                # when time_shifted=True or for async_requests.
                # Or it could be {'source_sim.source_entity.source_attr': actual_value}
                actual_value = None
                if 'value' in data_map:  # Common case
                    actual_value = data_map['value']
                elif len(data_map) == 1:  # If it's like {'full.path.to.source.attr': val}
                    actual_value = list(data_map.values())[0]
                else:
                    self.log_warning(f"Entity {eid}: Unexpected data_map structure for input_key '{input_key}': {data_map}")
                    continue  # Skip this input if structure is not recognized

                if actual_value is None: continue

                # Accumulate based on the destination attribute name (input_key)
                if input_key == 'gen_sum_P_MW':
                    current_P_gen_total += actual_value
                elif input_key == 'gen_sum_Q_MVAR':
                    current_Q_gen_total += actual_value
                elif input_key == 'load_sum_P_MW':
                    current_P_load_total += actual_value
                elif input_key == 'load_sum_Q_MVAR':
                    current_Q_load_total += actual_value
                elif input_key == 'line_sum_P_in_MW':
                    current_P_line_in_total += actual_value
                elif input_key == 'line_sum_Q_in_MVAR':
                    current_Q_line_in_total += actual_value
                elif input_key == 'line_sum_P_out_MW':
                    current_P_line_out_total += actual_value
                elif input_key == 'line_sum_Q_out_MVAR':
                    current_Q_line_out_total += actual_value
                elif input_key == 'system_total_P_imbalance_MW':
                    entity['system_P_imbalance_MW_input'] = actual_value

            # Update entity state with accumulated sums
            entity['P_gen_total_MW'] = current_P_gen_total
            entity['Q_gen_total_MVAR'] = current_Q_gen_total
            entity['P_load_total_MW'] = current_P_load_total
            entity['Q_load_total_MVAR'] = current_Q_load_total
            entity['P_line_flow_in_MW'] = current_P_line_in_total
            entity['Q_line_flow_in_MVAR'] = current_Q_line_in_total
            entity['P_line_flow_out_MW'] = current_P_line_out_total
            entity['Q_line_flow_out_MVAR'] = current_Q_line_out_total

            # Calculate power imbalance at the node
            entity['P_imbalance_MW'] = (entity['P_gen_total_MW'] + entity['P_line_flow_in_MW']) - \
                                       (entity['P_load_total_MW'] + entity['P_line_flow_out_MW'])
            entity['Q_imbalance_MVAR'] = (entity['Q_gen_total_MVAR'] + entity['Q_line_flow_in_MVAR']) - \
                                         (entity['Q_load_total_MVAR'] + entity['Q_line_flow_out_MVAR'])

            system_P_imbalance_for_freq_calc = entity.get('system_P_imbalance_MW_input', 0.0)

            if entity['is_slack_bus']:
                entity['voltage_pu'] = 1.0
                entity['frequency_Hz'] = self.nominal_freq
            else:
                entity['frequency_Hz'] = self.nominal_freq + (system_P_imbalance_for_freq_calc * -0.01)
                entity['frequency_Hz'] = max(47.0, min(53.0, entity['frequency_Hz']))

                # Simplified voltage response to local Q_imbalance (example)
                # A positive Q_imbalance means excess reactive power supply (or less demand), voltage might rise.
                # A negative Q_imbalance means deficit reactive power supply (or more demand), voltage might fall.
                # This is highly simplified.
                entity['voltage_pu'] = 1.0 - (entity['Q_imbalance_MVAR'] * 0.0005)  # Smaller factor for Q
                entity['voltage_pu'] = max(0.8, min(1.2, entity['voltage_pu']))

            entity['voltage_kV'] = entity['voltage_pu'] * entity['base_voltage_kV']

            self.log_info(f"Entity {eid}: V_pu: {entity['voltage_pu']:.3f} ({entity['voltage_kV']:.2f} kV), Freq: {entity['frequency_Hz']:.2f} Hz, P_imb: {entity['P_imbalance_MW']:.2f} MW, Q_imb: {entity['Q_imbalance_MVAR']:.2f} MVAR")
            self.log_info(f"Entity {eid}: P_Totals: Gen={entity['P_gen_total_MW']:.2f}, Load={entity['P_load_total_MW']:.2f}, LineIn={entity['P_line_flow_in_MW']:.2f}, LineOut={entity['P_line_flow_out_MW']:.2f}")
            self.log_info(f"Entity {eid}: Q_Totals: Gen={entity['Q_gen_total_MVAR']:.2f}, Load={entity['Q_load_total_MVAR']:.2f}, LineIn={entity['Q_line_flow_in_MVAR']:.2f}, LineOut={entity['Q_line_flow_out_MVAR']:.2f}")

        return time + STEP_SIZE

    def get_data(self, outputs: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:  # Ensure get_data only provides actual output attributes
        data = {}
        for eid, attrs_to_get in outputs.items():
            if eid in self.entities:
                data[eid] = {}
                entity_data = self.entities[eid]
                for attr_name in attrs_to_get:
                    # Only return attributes that NodeSim actually calculates and outputs
                    # Exclude the "input sum" attributes like 'gen_sum_P_MW' unless specifically designed as pass-through
                    if attr_name in ['voltage_kV', 'voltage_pu', 'frequency_Hz', 'P_imbalance_MW', 'Q_imbalance_MVAR',
                                     'connected_generators', 'connected_loads', 'connected_lines_from',
                                     'connected_lines_to']:
                        data[eid][attr_name] = entity_data.get(attr_name)
                    # else:
                    #     self.log_warning(f"Entity {eid}: Attribute '{attr_name}' not available or not an output for get_data.")
        return data

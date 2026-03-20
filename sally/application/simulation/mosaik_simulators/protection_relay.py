from typing import Dict, Any, List
from dependency_injector.wiring import inject
from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator

# TODO: Move this into constructor or some setter
STEP_SIZE = 1

RELAY_SIM_ID = 'ProtectionRelaySim'
RELAY_META = {
    'api_version': '3.0',
    'type': 'time-based',  # Could be event-based if it only acts on events
    'models': {
        'OvercurrentRelay': {
            'public': True,
            'params': ['monitored_line_eid', 'monitored_gen_eid', 'current_threshold_kA', 'voltage_threshold_kV_low',
                        'trip_delay_steps'],
            'attrs': ['trip_signal_line', 'trip_signal_gen', 'relay_status', 'line_current_kA', 'gen_voltage_pu', 'gen_status'],  # trip_signal is boolean
        },
    },
}


class ProtectionRelaySim(BaseMosaikSimulator):
    @inject
    def __init__(self, logger=None, event_bus=None):
        super().__init__(RELAY_META, logger, event_bus)
        self.eid_prefix = "Relay"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0):
        return super().init(sid, time_resolution, eid_prefix, sim_start_time)

    def create(self, num: int, model: str, **model_params) -> List[Dict[str, Any]]:
        entities = []
        for i in range(num):
            eid = self.get_entity_id(model)
            self.entities[eid] = {
                'type': model,
                'monitored_line_eid': model_params.get('monitored_line_eid'),
                'monitored_gen_eid': model_params.get('monitored_gen_eid'),
                'current_threshold_kA': model_params.get('current_threshold_kA', 1.0),
                'voltage_threshold_kV_low': model_params.get('voltage_threshold_kV_low', 0.85),
                # Per unit on component base
                'trip_delay_steps': model_params.get('trip_delay_steps', 0),  # Immediate trip if 0
                'trip_signal_line': False,
                'trip_signal_gen': False,
                'relay_status': 'monitoring',  # 'monitoring', 'pending_trip', 'tripped'
                'pending_trip_countdown': 0,
                'fault_detected_on': None,  # 'line' or 'gen'
            }
            entities.append({'eid': eid, 'type': model})
            self.log_info(f"Created Relay {eid} for Line: {model_params.get('monitored_line_eid')} / Gen: {model_params.get('monitored_gen_eid')}")
        return entities

    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        self.log_info(f"Step at time {time}. Inputs: {inputs}")
        for eid, attrs_map in inputs.items():
            entity = self.entities[eid]
            entity['trip_signal_line'] = False  # Reset trip signal each step
            entity['trip_signal_gen'] = False

            if entity['relay_status'] == 'tripped':  # Already tripped, do nothing
                continue

            current_kA = 0
            voltage_kV = 999  # Default to high value
            gen_status = 'online'

            # Get inputs for the specific monitored components
            # Input structure example: {'line_current_kA': {'LineSim-Line-1': {'current_kA': 0.5}}}
            # This needs careful setup in connect statements.
            # We assume the input attribute names are descriptive enough, e.g. 'line_current_input', 'gen_voltage_input'

            if entity['monitored_line_eid']:
                current_kA = attrs_map.get('line_current_kA', {}).get(0.0, 0.0)
                # self.log_info(f"Entity {eid}: Line {entity['monitored_line_eid']} current: {current_kA} kA")

            if entity['monitored_gen_eid']:
                # Assuming gen provides its terminal voltage or associated node voltage is used
                voltage_kV = attrs_map.get('gen_voltage_kV', {}).get(entity['voltage_threshold_kV_low'] * 1.1, entity[
                    'voltage_threshold_kV_low'] * 1.1)  # Default normal voltage
                gen_status = attrs_map.get('gen_status', {}).get('online', 'online')
                # self.log_info(f"Entity {eid}: Gen {entity['monitored_gen_eid']} voltage: {voltage_kV} kV, status: {gen_status}")

            fault_condition = False
            tripping_target = None

            if entity['monitored_line_eid'] and current_kA > entity['current_threshold_kA']:
                fault_condition = True
                tripping_target = 'line'
                self.log_info(f"Entity {eid}: OVERCURRENT on line {entity['monitored_line_eid']}: {current_kA:.3f} kA > {entity['current_threshold_kA']:.3f} kA")

            # Example for undervoltage trip for a generator (or its connected bus)
            # This logic would typically be more complex (e.g. considering duration of undervoltage)
            if entity['monitored_gen_eid'] and gen_status == 'online':
                # Assuming voltage_kV is pu and threshold is also pu for this comparison for simplicity
                # This needs consistent unit handling based on actual connections
                # Let's assume the input 'gen_voltage_kV' is actually 'gen_voltage_pu' from a node
                voltage_pu_val = attrs_map.get('gen_voltage_pu', {}).get(1.0, 1.0)
                if voltage_pu_val < entity[
                    'voltage_threshold_kV_low']:  # Assuming threshold_kV_low is actually pu for gen
                    fault_condition = True
                    tripping_target = 'gen'
                    self.log_info(f"Entity {eid}: UNDERVOLTAGE for gen {entity['monitored_gen_eid']}: {voltage_pu_val:.3f} pu < {entity['voltage_threshold_kV_low']:.3f} pu")

            if fault_condition:
                if entity['relay_status'] == 'monitoring':
                    entity['relay_status'] = 'pending_trip'
                    entity['pending_trip_countdown'] = entity['trip_delay_steps']
                    entity['fault_detected_on'] = tripping_target
                    self.log_info(f"Entity {eid}: Fault detected on {tripping_target}. Trip pending in {entity['pending_trip_countdown']} steps.")

                if entity['relay_status'] == 'pending_trip' and entity['fault_detected_on'] == tripping_target:
                    if entity['pending_trip_countdown'] <= 0:
                        if tripping_target == 'line':
                            entity['trip_signal_line'] = True
                        elif tripping_target == 'gen':
                            entity['trip_signal_gen'] = True
                        entity['relay_status'] = 'tripped'
                        self.log_info(f"Entity {eid}: TRIPPED {tripping_target}!")
                    else:
                        entity['pending_trip_countdown'] -= 1
            else:  # No fault condition, or fault cleared
                if entity['relay_status'] == 'pending_trip':
                    entity['relay_status'] = 'monitoring'  # Reset if fault clears during delay
                    entity['pending_trip_countdown'] = 0
                    entity['fault_detected_on'] = None
                    self.log_info(f"Entity {eid}: Pending trip cancelled, fault cleared.")

            self.log_info(f"Entity {eid}: Status: {entity['relay_status']}, Line Trip: {entity['trip_signal_line']}, Gen Trip: {entity['trip_signal_gen']}")

        return time + STEP_SIZE

    def get_data(self, outputs: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid].get(attr)
        return data

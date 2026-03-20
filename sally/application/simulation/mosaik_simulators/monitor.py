import collections
from typing import Dict, List, Any, Optional

from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator

# TODO: Move this into constructor or some setter
STEP_SIZE = 1

MONITOR_SIM_ID = 'MonitorSim'
MONITOR_META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'GridMonitor': {
            'public': True,
            'params': ['voltage_low_pu', 'voltage_high_pu', 'freq_low_hz', 'freq_high_hz', 'line_loading_warn_pct',
                       'line_loading_crit_pct', 'cascade_trigger_count', 'cascade_time_window_steps'],
            'attrs': ['system_frequency_avg_hz', 'min_voltage_pu', 'max_voltage_pu', 'overall_status',
                      'active_alarms_count', 'is_cascade_active', 'system_P_imbalance_MW', 'voltage_pu'],
        },
    },
}


class MonitorSim(BaseMosaikSimulator):
    def __init__(self, logger=None, event_bus=None):
        super().__init__(MONITOR_META, logger, event_bus)
        self.eid_prefix = "Monitor"

    def init(self, sid: str, time_resolution: int, eid_prefix: Optional[str] = None, sim_start_time: int = 0) -> Dict[str, Any]:
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.sim_start_time = sim_start_time
        self.sid = sid
        self.log_info(f"Initialized MonitorSim.")
        return MONITOR_META

    def create(self, num: int, model: str, **model_params: Any) -> List[Dict[str, Any]]:  # Expect num=1 for centralized monitor
        eid = self.get_entity_id(model)
        self.entities[eid] = {
            'type': model,
            'voltage_low_pu': model_params.get('voltage_low_pu', 0.95),
            'voltage_high_pu': model_params.get('voltage_high_pu', 1.05),
            'voltage_pu': model_params.get('voltage_high_pu', 1.00),
            'freq_low_hz': model_params.get('freq_low_hz', 49.8),
            'freq_high_hz': model_params.get('freq_high_hz', 50.2),
            'line_loading_warn_pct': model_params.get('line_loading_warn_pct', 80.0),
            'line_loading_crit_pct': model_params.get('line_loading_crit_pct', 100.0),
            'cascade_trigger_count': model_params.get('cascade_trigger_count', 2),  # Num trips to flag cascade
            'cascade_time_window_steps': model_params.get('cascade_time_window_steps', 5),  # Within this many steps

            'system_frequency_avg_hz': 50.0,
            'min_voltage_pu': 1.0,
            'max_voltage_pu': 1.0,
            'overall_status': 'normal',  # 'normal', 'warning', 'critical', 'cascade'
            'active_alarms_count': 0,
            'active_alarms_list': [],  # List of alarm dicts {type, component_eid, value, severity}
            'is_cascade_active': False,
            'system_P_imbalance_MW': 0.0,

            'component_statuses': {},  # eid -> {type, status_val, last_update_time}
            'line_trip_history': collections.deque(maxlen=model_params.get('cascade_trigger_count', 2) * 3),
            # (time, line_eid)
        }
        self.log_info(f"Entity {eid}: Created GridMonitor.")
        return [{'eid': eid, 'type': model}]

    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        self.log_info(f"Step at time {time}. Inputs: {inputs}")
        monitor_entity = self.entities[list(self.entities.keys())[0]]  # Assuming single monitor entity

        # Reset for this step
        monitor_entity['active_alarms_list'] = []
        monitor_entity['overall_status'] = 'normal'

        all_node_voltages_pu = []
        all_node_frequencies_hz = []
        total_gen_P = 0
        total_load_P = 0
        # total_pv_P = 0 # Could add specific tracking
        # total_battery_P = 0

        # Process all inputs - Mosaik groups inputs by source simulator and then entity
        # e.g., inputs[monitor_eid]['NodeSim-Node-1_voltage_pu'] = {'value': 0.98}
        # Or if multiple attrs from same source:
        # inputs[monitor_eid]['NodeSim-Node-1_attrs'] = {'voltage_pu': 0.98, 'frequency_Hz': 49.9}
        # Need to iterate through connected entity test_data

        current_component_states = {}  # Store current values for analysis
        # Let's use a more direct input parsing based on known input attribute names in Monitor:
        node_data_list = inputs.get(list(self.entities.keys())[0], {}).get('node_data_points',
                                                                           [])  # Expect list of dicts
        for node_data in node_data_list:  # node_data = {'eid': 'Node-1', 'voltage_pu': 0.99, 'frequency_Hz': 50.0, 'P_imbalance_MW': 0.5}
            all_node_voltages_pu.append(node_data.get('voltage_pu', 1.0))
            all_node_frequencies_hz.append(node_data.get('frequency_Hz', 50.0))
            current_component_states[node_data['eid']] = node_data

        line_data_list = inputs.get(list(self.entities.keys())[0], {}).get('line_data_points', [])
        for line_data in line_data_list:  # line_data = {'eid': 'Line-1', 'loading_percent': 80, 'status': 'in_service'}
            current_component_states[line_data['eid']] = line_data
            if line_data.get('status') != 'in_service' and \
                    (time, line_data['eid']) not in monitor_entity['line_trip_history'] and \
                    monitor_entity['component_statuses'].get(line_data['eid'], {}).get(
                        'status') == 'in_service':  # New trip
                monitor_entity['line_trip_history'].append((time, line_data['eid']))
                self.log_info(f"Monitor {list(self.entities.keys())[0]}: Line {line_data['eid']} tripped at {time}. Status: {line_data.get('status')}")

        gen_data_list = inputs.get(list(self.entities.keys())[0], {}).get('gen_data_points', [])
        for gen_data in gen_data_list:  # gen_data = {'eid': 'Gen-1', 'P_MW_out': 50, 'status': 'online'}
            current_component_states[gen_data['eid']] = gen_data
            if gen_data.get('status') == 'online':
                total_gen_P += gen_data.get('P_MW_out', 0)
            elif gen_data.get('status') == 'tripped' and \
                    monitor_entity['component_statuses'].get(gen_data['eid'], {}).get(
                        'status') == 'online':  # New trip
                self.log_info(f"Monitor {list(self.entities.keys())[0]}: Generator {gen_data['eid']} tripped at {time}.")

        load_data_list = inputs.get(list(self.entities.keys())[0], {}).get('load_data_points', [])
        for load_data in load_data_list:  # load_data = {'eid': 'Load-1', 'P_MW_actual': 10}
            current_component_states[load_data['eid']] = load_data
            total_load_P += load_data.get('P_MW_actual', 0)

        # Update component_statuses for next step comparison
        monitor_entity['component_statuses'] = current_component_states

        # --- Aggregate System Stats ---
        if all_node_frequencies_hz:
            monitor_entity['system_frequency_avg_hz'] = sum(all_node_frequencies_hz) / len(all_node_frequencies_hz)
        else:
            monitor_entity['system_frequency_avg_hz'] = 50.0  # Default if no nodes reporting

        if all_node_voltages_pu:
            monitor_entity['min_voltage_pu'] = min(all_node_voltages_pu)
            monitor_entity['max_voltage_pu'] = max(all_node_voltages_pu)
        else:
            monitor_entity['min_voltage_pu'] = 1.0
            monitor_entity['max_voltage_pu'] = 1.0

        monitor_entity[
            'system_P_imbalance_MW'] = total_gen_P - total_load_P  # Simplified, ignores line losses, storage etc for this global metric

        # --- Alarm Generation ---
        # Frequency Alarms
        if monitor_entity['system_frequency_avg_hz'] < monitor_entity['freq_low_hz']:
            monitor_entity['active_alarms_list'].append(
                {'type': 'low_frequency', 'value': monitor_entity['system_frequency_avg_hz'], 'severity': 'critical'})
        elif monitor_entity['system_frequency_avg_hz'] > monitor_entity['freq_high_hz']:
            monitor_entity['active_alarms_list'].append(
                {'type': 'high_frequency', 'value': monitor_entity['system_frequency_avg_hz'], 'severity': 'critical'})

        # Voltage Alarms (based on min/max observed)
        if monitor_entity['min_voltage_pu'] < monitor_entity['voltage_low_pu']:
            monitor_entity['active_alarms_list'].append(
                {'type': 'low_voltage', 'value': monitor_entity['min_voltage_pu'], 'severity': 'critical',
                 'location': 'system_min_node'})  # Location needs better tracking
        if monitor_entity['max_voltage_pu'] > monitor_entity['voltage_high_pu']:
            monitor_entity['active_alarms_list'].append(
                {'type': 'high_voltage', 'value': monitor_entity['max_voltage_pu'], 'severity': 'warning',
                 'location': 'system_max_node'})

        # Line Loading Alarms
        for line_data in line_data_list:  # Iterate again for specific line alarms
            if line_data.get('status') == 'in_service':
                loading = line_data.get('loading_percent', 0)
                if loading > monitor_entity['line_loading_crit_pct']:
                    monitor_entity['active_alarms_list'].append(
                        {'type': 'line_overload_critical', 'component_eid': line_data['eid'], 'value': loading,
                         'severity': 'critical'})
                elif loading > monitor_entity['line_loading_warn_pct']:
                    monitor_entity['active_alarms_list'].append(
                        {'type': 'line_overload_warning', 'component_eid': line_data['eid'], 'value': loading,
                         'severity': 'warning'})

        # Generator Trip Alarms
        for gen_data in gen_data_list:
            if gen_data.get('status') == 'tripped':
                monitor_entity['active_alarms_list'].append(
                    {'type': 'generator_trip', 'component_eid': gen_data['eid'], 'severity': 'critical'})

        monitor_entity['active_alarms_count'] = len(monitor_entity['active_alarms_list'])

        # --- Cascading Failure Detection ---
        monitor_entity['is_cascade_active'] = False  # Reset from previous step
        if len(monitor_entity['line_trip_history']) >= monitor_entity['cascade_trigger_count']:
            # Check if recent trips fall within the time window
            recent_trips_in_window = 0
            last_trip_time = monitor_entity['line_trip_history'][-1][0]
            for trip_time, _ in reversed(monitor_entity['line_trip_history']):
                if (last_trip_time - trip_time) <= (monitor_entity['cascade_time_window_steps'] * STEP_SIZE):
                    recent_trips_in_window += 1
                else:
                    break  # History is ordered by time

            if recent_trips_in_window >= monitor_entity['cascade_trigger_count']:
                monitor_entity['is_cascade_active'] = True
                monitor_entity['overall_status'] = 'cascade'
                self.log_info(f"Monitor {list(self.entities.keys())[0]}: CASCADE DETECTED! {recent_trips_in_window} line trips in window.")

        # Determine overall status
        if not monitor_entity['is_cascade_active']:  # Cascade status overrides others
            if any(a['severity'] == 'critical' for a in monitor_entity['active_alarms_list']):
                monitor_entity['overall_status'] = 'critical'
            elif any(a['severity'] == 'warning' for a in monitor_entity['active_alarms_list']):
                monitor_entity['overall_status'] = 'warning'
            else:
                monitor_entity['overall_status'] = 'normal'

        self.log_info(f"Monitor {list(self.entities.keys())[0]}: Stepped. Freq: {monitor_entity['system_frequency_avg_hz']:.2f} Hz, V_min: {monitor_entity['min_voltage_pu']:.3f} pu, V_max: {monitor_entity['max_voltage_pu']:.3f} pu, P_imbalance: {monitor_entity['system_P_imbalance_MW']:.2f} MW, Status: {monitor_entity['overall_status']}, Alarms: {monitor_entity['active_alarms_count']}")
        if monitor_entity['active_alarms_count'] > 0:
            for alarm in monitor_entity['active_alarms_list']:
                self.log_info(f"Monitor {list(self.entities.keys())[0]}:   ALARM: {alarm}")

        return time + STEP_SIZE

    def get_data(self, outputs: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        data = {}
        # Assuming single monitor entity
        monitor_eid = list(self.entities.keys())[0]
        data[monitor_eid] = {}
        for attr in outputs[monitor_eid]:
            data[monitor_eid][attr] = self.entities[monitor_eid].get(attr)

        # Also output the raw alarm list if requested by RemediationSim
        if 'active_alarms_list' in outputs[monitor_eid]:  # Check if RemediationSim requests this specific attribute
            data[monitor_eid]['active_alarms_list'] = self.entities[monitor_eid]['active_alarms_list']

        return data

from typing import Dict, List, Any, Optional
from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator
from sally.application.simulation.mosaik_simulators.battery import BATTERY_SIM_ID
from sally.application.simulation.mosaik_simulators.generator import GEN_SIM_ID
from sally.application.simulation.mosaik_simulators.pv import PV_SIM_ID

# TODO: Move this into constructor or some setter
STEP_SIZE = 1

REMEDIATION_SIM_ID = 'RemediationSim'
REMEDIATION_META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'RemediationController': {
            'public': True,
            'params': ['control_interval_steps', 'gen_redispatch_increment_MW', 'battery_dispatch_increment_MW'],
            'attrs': ['last_action_summary', 'actions_taken_count'],  # Output for logging/tracking
        },
    },
    # No extra_methods needed for outputs, it will call extra_methods of other simulators
}


class RemediationSim(BaseMosaikSimulator):
    def __init__(self, logger=None, event_bus=None,):
        super().__init__(REMEDIATION_META, logger, event_bus)
        self.eid_prefix = "RemCtrl"

    def init(self, sid: str, time_resolution: int, eid_prefix: Optional[str] = None, sim_start_time: int = 0, controllable_gens: Optional[List[str]] = None,
             controllable_batteries: Optional[List[str]] = None, controllable_loads: Optional[List[str]] = None, controllable_pvs: Optional[List[str]] = None) -> Dict[str, Any]:
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.controllable_gens_eids = controllable_gens if controllable_gens else []
        self.controllable_batteries_eids = controllable_batteries if controllable_batteries else []
        self.controllable_loads_eids = controllable_loads if controllable_loads else []  # For demand response
        self.controllable_pvs_eids = controllable_pvs if controllable_pvs else []  # For curtailment
        self.sid = sid
        self.log_info(f"Initialized RemediationSim.")
        return REMEDIATION_META

    def create(self, num: int, model: str, **model_params: Any) -> List[Dict[str, Any]]:  # Expect num=1
        eid = self.get_entity_id(model)
        self.entities[eid] = {
            'type': model,
            'control_interval_steps': model_params.get('control_interval_steps', 1),  # Act every step by default
            'gen_redispatch_increment_MW': model_params.get('gen_redispatch_increment_MW', 5.0),
            'battery_dispatch_increment_MW': model_params.get('battery_dispatch_increment_MW', 2.0),
            'last_action_summary': 'None',
            'actions_taken_count': 0,
            'steps_since_last_action': 0,
            'current_gen_setpoints': {gen_eid: 0 for gen_eid in self.controllable_gens_eids},  # Track setpoints
            'current_pv_curtailment': {pv_eid: 0 for pv_eid in self.controllable_pvs_eids},
        }
        self.log_info(f"Entity {eid}: Created RemediationController.")
        return [{'eid': eid, 'type': model}]

    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        self.log_info(f"Step at time {time}. Inputs: {inputs}")
        controller_entity = self.entities[list(self.entities.keys())[0]]  # Assuming single controller
        controller_entity['last_action_summary'] = 'No action this step.'

        controller_entity['steps_since_last_action'] += 1
        if controller_entity['steps_since_last_action'] < controller_entity['control_interval_steps']:
            return time + STEP_SIZE  # Skip action if not yet time

        # Get monitor test_data
        # Assuming inputs[controller_eid] contains all test_data from MonitorSim, like:
        # { 'MonitorSim-Monitor-1_overall_status': {'value':'warning'},
        #   'MonitorSim-Monitor-1_active_alarms_list': {'value': [{'type':'low_freq', ...}]} }

        # A better way is to define clear input attributes for RemediationSim, e.g.,
        # 'monitor_status', 'monitor_alarms', 'monitor_frequency'
        # And connect MonitorSim outputs to these.

        monitor_inputs = inputs.get(list(self.entities.keys())[0], {})
        overall_status = monitor_inputs.get('monitor_overall_status', {}).get('normal', 'normal')
        active_alarms_list = monitor_inputs.get('monitor_active_alarms', [])  # Expect a list of dicts
        system_frequency = monitor_inputs.get('monitor_system_frequency', {}).get(50.0, 50.0)
        is_cascade = monitor_inputs.get('monitor_is_cascade', {}).get(False, False)

        # Also get current states of controllable devices if needed (passed directly or via monitor)
        # For now, assume RemediationSim has a list of controllable EIDs and will call their methods.
        # It might need to query their current P_out before deciding on new setpoints.
        # For simplicity, we'll make relative adjustments or set absolute targets.

        actions = []  # List of (target_sim_id, target_eid, method_name, method_args_dict)

        if is_cascade:
            actions.append(('CASCADE: Emergency Actions - Reduce load if possible, Maximize available generation'))
            # Example: shed some load (if controllable loads are defined)
            # for load_eid in self.controllable_loads_eids:
            #    actions.append((LOAD_SIM_ID, load_eid, 'reduce_demand_percentage', {'percentage': 20}))
            # For now, just log and rely on other critical actions.

        elif overall_status == 'critical' or overall_status == 'warning':
            for alarm in active_alarms_list:
                if alarm['type'] == 'low_frequency':
                    actions.append(f"Low Frequency ({alarm['value']:.2f} Hz) detected.")
                    # Increase generation
                    for gen_eid in self.controllable_gens_eids:
                        # This needs current P_setpoint of gen. Assume RemediationSim gets it or tracks it.
                        # For simplicity, just increment. A real controller would be smarter.
                        new_setpoint = controller_entity['current_gen_setpoints'].get(gen_eid, 0) + controller_entity[
                            'gen_redispatch_increment_MW']
                        actions.append((GEN_SIM_ID, gen_eid, 'set_power_setpoint', {'P_setpoint_MW': new_setpoint}))
                        controller_entity['current_gen_setpoints'][gen_eid] = new_setpoint  # Update tracked setpoint
                    # Discharge batteries
                    for batt_eid in self.controllable_batteries_eids:
                        actions.append((BATTERY_SIM_ID, batt_eid, 'set_power_dispatch',
                                        {'P_dispatch_MW': controller_entity['battery_dispatch_increment_MW']}))

                elif alarm['type'] == 'high_frequency':
                    actions.append(f"High Frequency ({alarm['value']:.2f} Hz) detected.")
                    # Decrease generation
                    for gen_eid in self.controllable_gens_eids:
                        new_setpoint = controller_entity['current_gen_setpoints'].get(gen_eid, 0) - controller_entity[
                            'gen_redispatch_increment_MW']
                        actions.append((GEN_SIM_ID, gen_eid, 'set_power_setpoint', {'P_setpoint_MW': new_setpoint}))
                        controller_entity['current_gen_setpoints'][gen_eid] = new_setpoint
                    # Charge batteries
                    for batt_eid in self.controllable_batteries_eids:
                        actions.append((BATTERY_SIM_ID, batt_eid, 'set_power_dispatch',
                                        {'P_dispatch_MW': -controller_entity['battery_dispatch_increment_MW']}))

                elif alarm['type'] == 'low_voltage':
                    actions.append(f"Low Voltage ({alarm['value']:.3f} pu) detected.")
                    # Discharge batteries (for VAR support if modeled, or P support)
                    for batt_eid in self.controllable_batteries_eids:
                        actions.append((BATTERY_SIM_ID, batt_eid, 'set_power_dispatch', {
                            'P_dispatch_MW': controller_entity[
                                                 'battery_dispatch_increment_MW'] / 2}))  # Less aggressive for voltage
                    # Could also try to adjust transformer taps if modeled.

                elif alarm['type'] == 'high_voltage':
                    actions.append(f"High Voltage ({alarm['value']:.3f} pu) detected.")
                    # Curtail PVs
                    for pv_eid in self.controllable_pvs_eids:
                        # Simple: curtail a fixed amount or percentage. This needs PV's current output.
                        # For demo, just set a fixed curtailment value.
                        new_curtailment = controller_entity['current_pv_curtailment'].get(pv_eid,
                                                                                          0) + 0.5  # Curtail 0.5 MW more
                        actions.append((PV_SIM_ID, pv_eid, 'set_curtailment', {'curtail_P_MW': new_curtailment}))
                        controller_entity['current_pv_curtailment'][pv_eid] = new_curtailment
                    # Charge batteries
                    for batt_eid in self.controllable_batteries_eids:
                        actions.append((BATTERY_SIM_ID, batt_eid, 'set_power_dispatch',
                                        {'P_dispatch_MW': -controller_entity['battery_dispatch_increment_MW'] / 2}))


                elif alarm['type'] == 'line_overload_critical' or alarm['type'] == 'line_overload_warning':
                    line_eid = alarm['component_eid']
                    loading_val = alarm['value']
                    actions.append(f"Line {line_eid} Overload ({loading_val:.1f}%) detected.")
                    # Attempt to re-dispatch generation or curtail load around the overloaded line.
                    # This requires topology knowledge, which this simple controller doesn't have.
                    # Simplistic: reduce overall generation slightly if overload, or specific gens if known.
                    if self.controllable_gens_eids:
                        gen_to_adjust = self.controllable_gens_eids[0]  # Pick first one
                        new_setpoint = controller_entity['current_gen_setpoints'].get(gen_to_adjust, 0) - (
                                    controller_entity['gen_redispatch_increment_MW'] * 0.5)
                        actions.append(
                            (GEN_SIM_ID, gen_to_adjust, 'set_power_setpoint', {'P_setpoint_MW': new_setpoint}))
                        controller_entity['current_gen_setpoints'][gen_to_adjust] = new_setpoint

        if actions:
            controller_entity['last_action_summary'] = "; ".join(
                [str(a) if isinstance(a, str) else f"{a[2]} on {a[1]}" for a in actions])
            controller_entity['actions_taken_count'] += 1
            self.log_info(f"Controller {list(self.entities.keys())[0]}: ACTIONS: {controller_entity['last_action_summary']}")

            # Mosaik's scheduler handles sending these calls to other simulators
            # This is done by returning a list of calls for the mosaik world.
            # However, extra_methods are typically called directly from the scenario script.
            # For a controller sim to call other sims' extra_methods, it needs to be scheduled *before* them
            # OR, it needs to set output attributes that the scenario script then uses to make those calls.
            # The direct call from within a simulator's step() to another is not standard Mosaik practice.
            # Instead, RemediationSim should output 'control_signals' attribute.
            # The scenario script then reads this and performs the actual calls using world.call()

            # Let's adjust: RemediationSim will set an output attribute 'control_commands'
            # This attribute will be a list of dictionaries:
            # [{'target_sim_id': ..., 'target_eid': ..., 'method': ..., 'args': {...}}, ...]
            # The main scenario loop will need to process this.
            # For now, for simplicity within this file structure, we'll *simulate* the effect by directly calling
            # (knowing this isn't pure Mosaik style for sim-to-sim calls during step)
            # This would require access to the `world` object, which is not available here.

            self.output_commands = []  # Store commands to be fetched by get_data
            for act in actions:
                if not isinstance(act, str):  # Filter out summary strings
                    self.output_commands.append({
                        'target_sim_id': act[0],
                        'target_eid': act[1],
                        'method_name': act[2],
                        'kwargs': act[3]
                    })
            controller_entity['steps_since_last_action'] = 0  # Reset counter

        return time + STEP_SIZE

    def get_data(self, outputs: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        data = {}
        controller_eid = list(self.entities.keys())[0]
        data[controller_eid] = {}
        for attr in outputs[controller_eid]:
            if attr == 'control_commands_list':  # Special handling for our action list
                data[controller_eid][attr] = self.output_commands
                self.output_commands = []  # Clear after fetching
            else:
                data[controller_eid][attr] = self.entities[controller_eid].get(attr)
        return data

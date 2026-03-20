import mosaik
import mosaik_api_v3
import random
from mosaik.util import connect_randomly, connect_many_to_one
import time
import collections

# --- Simulator IDs ---
GEN_SIM_ID = 'GeneratorSim'
PV_SIM_ID = 'PVSim'
LOAD_SIM_ID = 'LoadSim'
LINE_SIM_ID = 'LineSim'
NODE_SIM_ID = 'NodeSim'
BATTERY_SIM_ID = 'BatterySim'
RELAY_SIM_ID = 'ProtectionRelaySim'
MONITOR_SIM_ID = 'MonitorSim'
REMEDIATION_SIM_ID = 'RemediationSim'


# COMM_SIM_ID = 'CommunicationSim' # Future extension

# --- Helper Functions ---
def Pprint(sim_id, eid, message):
    """Pretty print with simulator ID and entity ID."""
    # print(f"[{time.strftime('%H:%M:%S')}|{sim_id}|{eid}] {message}")
    pass  # Quieter for long runs


# --- Base Simulator Class (Optional, for common methods) ---
class BaseSim(mosaik_api_v3.Simulator):
    def __init__(self, meta):
        super().__init__(meta)
        self.eid_prefix = ""
        self.entities = {}  # sid -> entity_data
        self.entity_idx = 0

    def get_entity_id(self, model_name):
        self.entity_idx += 1
        return f"{self.eid_prefix}-{self.entity_idx}"


# --- 1. Generator Simulator ---
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


class GeneratorSim(BaseSim):
    def __init__(self):
        super().__init__(GEN_META)
        self.sid = GEN_META.get('sid')
        self.eid_prefix = "Gen"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0, grid_frequency_nominal=50.0):
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.sim_start_time = sim_start_time
        self.sid = sid
        self.grid_frequency_nominal = grid_frequency_nominal
        Pprint(sid, "WORLD",
               f"Initialized GeneratorSim. Time resolution: {time_resolution}, Start time: {sim_start_time}")
        return GEN_META

    def create(self, num, model, **model_params):
        entities = []
        for _ in range(num):
            eid = self.get_entity_id(model)

            self.entities[eid] = {
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
            entities.append({'eid': eid, 'type': model})
            Pprint(GEN_SIM_ID, eid, f"Created Generator with params: {model_params}")
        return entities

    def step(self, time, inputs, max_advance):
        Pprint(GEN_SIM_ID, "WORLD", f"Step at time {time}. Inputs: {inputs}")
        for eid, attrs in inputs.items():
            entity = self.entities[eid]
            if entity['status'] == 'tripped':
                entity['P_MW_out'] = 0.0
                entity['Q_MVAR_out'] = 0.0
                continue

            # Process inputs (e.g., frequency from grid for droop, external setpoints)
            grid_freq = attrs.get('grid_frequency_Hz', {}).get(self.grid_frequency_nominal,
                                                               self.grid_frequency_nominal)  # Default if not connected
            # Droop control
            if entity['droop_coeff'] > 0:
                delta_f = self.grid_frequency_nominal - grid_freq
                # P_droop = P_nominal * (delta_f / (droop_coeff * f_nominal))
                # Simplified: change setpoint based on droop
                # This would normally adjust governor, here we adjust setpoint directly for simplicity
                # If freq low, increase P; if freq high, decrease P
                # P_adj_droop = (delta_f / (entity['droop_coeff'] * self.grid_frequency_nominal)) * entity['max_P_MW'] # Theoretical change
                # entity['target_P_MW'] = entity['P_setpoint_MW'] + P_adj_droop # Simplified droop response
                # Let's assume remediation controller provides P_setpoint_MW which might include droop calculations or other factors.
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

            Pprint(GEN_SIM_ID, eid, f"Stepped. P_out: {entity['P_MW_out']:.2f} MW, Status: {entity['status']}")

        return time + STEP_SIZE

    def get_data(self, outputs):
        data = {}
        Pprint(GEN_SIM_ID, "WORLD", f"Get_data called. Outputs: {outputs}")
        for eid, attrs in outputs.items():
            if eid not in self.entities:
                Pprint(GEN_SIM_ID, "WORLD", f"Warning: EID {eid} not found in get_data.")
                continue
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid].get(attr)
        return data

    def trigger_trip(self, time, eid, cause="unknown"):
        if eid in self.entities:
            self.entities[eid]['status'] = 'tripped'
            self.entities[eid]['P_MW_out'] = 0.0
            self.entities[eid]['Q_MVAR_out'] = 0.0
            Pprint(GEN_SIM_ID, eid, f"Generator tripped at {time} due to {cause}.")
        return {}

    def set_power_setpoint(self, time, eid, P_setpoint_MW):
        if eid in self.entities and self.entities[eid]['status'] == 'online':
            target_P = float(P_setpoint_MW)
            self.entities[eid]['target_P_MW'] = max(self.entities[eid]['min_P_MW'],
                                                    min(self.entities[eid]['max_P_MW'], target_P))
            Pprint(GEN_SIM_ID, eid, f"Received new P_setpoint_MW: {target_P:.2f} at {time}")
        return {}


# --- 2. PV Simulator ---
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


class PVSim(BaseSim):
    def __init__(self):
        super().__init__(PV_META)
        self.sid = PV_META.get('sid')
        self.eid_prefix = "PV"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0):
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.time_resolution = time_resolution
        self.sid = sid
        self.sim_start_time = sim_start_time
        Pprint(sid, "WORLD", f"Initialized PVSim. Time resolution: {time_resolution}")
        return PV_META

    def create(self, num, model, **model_params):
        entities = []
        for i in range(num):
            eid = self.get_entity_id(model)

            default_irradiance = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 0.9, 0.7, 0.5, 0.3] * (
                        SIM_DURATION // 10 + 1)  # Simple daily pattern
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
            Pprint(PV_SIM_ID, eid, f"Created PVSystem with P_max: {model_params['max_P_MW']} MW")
        return entities

    def step(self, time, inputs, max_advance):
        Pprint(PV_SIM_ID, "WORLD", f"Step at time {time}.")
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

            Pprint(PV_SIM_ID, eid,
                   f"Stepped. Irradiance factor: {irradiance_factor:.2f}, Available P: {available_P_MW:.2f} MW, Curtailed P: {entity['curtailment_MW']:.2f} MW, P_out: {entity['P_MW_out']:.2f} MW")
        return time + STEP_SIZE

    def get_data(self, outputs):
        data = {}
        Pprint(PV_SIM_ID, "WORLD", f"Get_data called. Outputs: {outputs}")
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid].get(attr)
        return data

    def set_curtailment(self, time, eid, curtail_P_MW):
        if eid in self.entities:
            self.entities[eid]['curtailment_MW'] = float(curtail_P_MW)
            Pprint(PV_SIM_ID, eid, f"Received curtailment command: {curtail_P_MW:.2f} MW at {time}")
        return {}


# --- 3. Load Simulator ---
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


class LoadSim(BaseSim):
    def __init__(self):
        super().__init__(LOAD_META)
        self.eid_prefix = "Load"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0, nominal_voltage_kV=1.0):
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.time_resolution = time_resolution
        self.sim_start_time = sim_start_time
        self.sid = sid
        self.nominal_voltage_kV = nominal_voltage_kV  # Used for voltage sensitivity calc
        Pprint(sid, "WORLD", f"Initialized LoadSim.")
        return LOAD_META

    def create(self, num, model, **model_params):
        entities = []
        for i in range(num):
            eid = self.get_entity_id(model)

            # Default profile: simple sine wave for P, constant for Q
            default_P_profile = [0.5 + 0.5 * random.uniform(0.8, 1.2) * (i % 2 + 1) for _ in
                                 range(SIM_DURATION // STEP_SIZE + 1)]
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
            Pprint(LOAD_SIM_ID, eid, f"Created Load.")
        return entities

    def step(self, time, inputs, max_advance):
        Pprint(LOAD_SIM_ID, "WORLD", f"Step at time {time}. Inputs: {inputs}")
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
                    Pprint(LOAD_SIM_ID, eid, "Demand spike ended.")

            entity['P_MW_actual'] = P_MW
            entity['Q_MVAR_actual'] = Q_MVAR

            Pprint(LOAD_SIM_ID, eid,
                   f"Stepped. P_actual: {P_MW:.2f} MW, Q_actual: {Q_MVAR:.2f} MVAR (V_pu: {voltage_pu:.3f})")
        return time + STEP_SIZE

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid].get(attr)
        return data

    def trigger_demand_spike(self, time, eid, factor, duration_steps):
        if eid in self.entities:
            self.entities[eid]['spike_factor'] = float(factor)
            self.entities[eid]['spike_duration_steps'] = int(duration_steps)
            Pprint(LOAD_SIM_ID, eid,
                   f"Demand spike triggered: factor {factor}, duration {duration_steps} steps at {time}.")
        return {}


# --- 4. Line Simulator ---
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


class LineSim(BaseSim):
    def __init__(self):
        super().__init__(LINE_META)
        self.eid_prefix = "Line"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0):
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.sid = sid
        Pprint(sid, "WORLD", f"Initialized LineSim.")
        return LINE_META

    def create(self, num, model, **model_params):
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
            Pprint(LINE_SIM_ID, eid,
                   f"Created Line from {model_params['from_node_eid']} to {model_params['to_node_eid']}.")
        return entities

    def step(self, time, inputs, max_advance):
        Pprint(LINE_SIM_ID, "WORLD", f"Step at time {time}. Inputs: {inputs}")
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
                Pprint(LINE_SIM_ID, eid, f"TRIPPED due to overload! Loading: {entity['loading_percent']:.1f}%")
                # This is part of cascading failure initiation

            Pprint(LINE_SIM_ID, eid,
                   f"Stepped. P_flow: {entity['P_MW_flow']:.2f} MW, I: {entity['current_kA']:.3f} kA, Load: {entity['loading_percent']:.1f}%, Status: {entity['status']}")

        return time + STEP_SIZE

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid].get(attr)
        return data

    def trigger_trip_ext(self, time, eid, cause="external_fault"):
        if eid in self.entities:
            self.entities[eid]['status'] = f'tripped_{cause}'
            Pprint(LINE_SIM_ID, eid, f"Line tripped by external command at {time} due to {cause}.")
        return {}


# --- 5. Node Simulator (Bus) ---
# --- 5. Node Simulator (Bus) ---
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


class NodeSim(BaseSim):
    def __init__(self):
        super().__init__(NODE_META)
        self.eid_prefix = "Node"
        self.nominal_freq = 50.0

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0, nominal_frequency_Hz=50.0):
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.nominal_freq = nominal_frequency_Hz
        self.sid = sid
        Pprint(sid, "WORLD", f"Initialized NodeSim.")
        return NODE_META

    def create(self, num, model, **model_params):
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
            Pprint(NODE_SIM_ID, eid, f"Created Node {eid} (Base V: {model_params['base_voltage_kV']} kV).")
        return entities

    def step(self, time, inputs, max_advance):
        Pprint(NODE_SIM_ID, "WORLD", f"Step at time {time}. Inputs: {inputs}")

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
                    Pprint(NODE_SIM_ID, eid, f"Warning: Empty data_map for input_key '{input_key}'")
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
                    Pprint(NODE_SIM_ID, eid,
                           f"Warning: Unexpected data_map structure for input_key '{input_key}': {data_map}")
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

            Pprint(NODE_SIM_ID, eid,
                   f"Stepped. V_pu: {entity['voltage_pu']:.3f} ({entity['voltage_kV']:.2f} kV), Freq: {entity['frequency_Hz']:.2f} Hz, P_imb: {entity['P_imbalance_MW']:.2f} MW, Q_imb: {entity['Q_imbalance_MVAR']:.2f} MVAR")
            Pprint(NODE_SIM_ID, eid,
                   f"  P_Totals: Gen={entity['P_gen_total_MW']:.2f}, Load={entity['P_load_total_MW']:.2f}, LineIn={entity['P_line_flow_in_MW']:.2f}, LineOut={entity['P_line_flow_out_MW']:.2f}")
            Pprint(NODE_SIM_ID, eid,
                   f"  Q_Totals: Gen={entity['Q_gen_total_MVAR']:.2f}, Load={entity['Q_load_total_MVAR']:.2f}, LineIn={entity['Q_line_flow_in_MVAR']:.2f}, LineOut={entity['Q_line_flow_out_MVAR']:.2f}")

        return time + STEP_SIZE

    def get_data(self, outputs):  # Ensure get_data only provides actual output attributes
        data = {}
        for eid, attrs_to_get in outputs.items():
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
                #     Pprint(NODE_SIM_ID, eid, f"Warning: Attribute '{attr_name}' not available or not an output for get_data.")
        return data


# --- 6. Battery Storage Simulator ---
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


class BatterySim(BaseSim):
    def __init__(self):
        super().__init__(BATTERY_META)
        self.eid_prefix = "Batt"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0):
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.time_resolution_seconds = time_resolution  # Assuming Mosaik gives this in seconds
        self.sid = sid
        Pprint(sid, "WORLD", f"Initialized BatterySim.")
        return BATTERY_META

    def create(self, num, model, **model_params):
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
            Pprint(BATTERY_SIM_ID, eid, f"Created Battery {eid} with {model_params['capacity_MWh']} MWh capacity.")
        return entities

    def step(self, time, inputs, max_advance):
        Pprint(BATTERY_SIM_ID, "WORLD", f"Step at time {time}. Inputs: {inputs}")
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

            Pprint(BATTERY_SIM_ID, eid,
                   f"Stepped. Target P: {final_P_MW_target:.2f}, Actual P_out: {entity['P_MW_out']:.2f} MW, SoC: {entity['SoC_pct']:.1f}%, Status: {entity['status']}")

            # Reset dispatch for next step, expecting new command
            entity['P_dispatch_MW'] = 0.0

        return time + STEP_SIZE

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid].get(attr)
        return data

    def set_power_dispatch(self, time, eid, P_dispatch_MW):
        if eid in self.entities:
            self.entities[eid]['P_dispatch_MW'] = float(P_dispatch_MW)
            Pprint(BATTERY_SIM_ID, eid, f"Received power dispatch: {P_dispatch_MW:.2f} MW at {time}.")
        return {}


# --- 7. Protection Relay Simulator ---
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


class ProtectionRelaySim(BaseSim):
    def __init__(self):
        super().__init__(RELAY_META)
        self.eid_prefix = "Relay"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0):
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.sid = sid
        Pprint(sid, "WORLD", f"Initialized ProtectionRelaySim.")
        return RELAY_META

    def create(self, num, model, **model_params):
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
            Pprint(RELAY_SIM_ID, eid,
                   f"Created Relay for Line: {model_params.get('monitored_line_eid')} / Gen: {model_params.get('monitored_gen_eid')}.")
        return entities

    def step(self, time, inputs, max_advance):
        Pprint(RELAY_SIM_ID, "WORLD", f"Step at time {time}. Inputs: {inputs}")
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
                # Pprint(RELAY_SIM_ID, eid, f"Line {entity['monitored_line_eid']} current: {current_kA} kA")

            if entity['monitored_gen_eid']:
                # Assuming gen provides its terminal voltage or associated node voltage is used
                voltage_kV = attrs_map.get('gen_voltage_kV', {}).get(entity['voltage_threshold_kV_low'] * 1.1, entity[
                    'voltage_threshold_kV_low'] * 1.1)  # Default normal voltage
                gen_status = attrs_map.get('gen_status', {}).get('online', 'online')
                # Pprint(RELAY_SIM_ID, eid, f"Gen {entity['monitored_gen_eid']} voltage: {voltage_kV} kV, status: {gen_status}")

            fault_condition = False
            tripping_target = None

            if entity['monitored_line_eid'] and current_kA > entity['current_threshold_kA']:
                fault_condition = True
                tripping_target = 'line'
                Pprint(RELAY_SIM_ID, eid,
                       f"OVERCURRENT on line {entity['monitored_line_eid']}: {current_kA:.3f} kA > {entity['current_threshold_kA']:.3f} kA")

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
                    Pprint(RELAY_SIM_ID, eid,
                           f"UNDERVOLTAGE for gen {entity['monitored_gen_eid']}: {voltage_pu_val:.3f} pu < {entity['voltage_threshold_kV_low']:.3f} pu")

            if fault_condition:
                if entity['relay_status'] == 'monitoring':
                    entity['relay_status'] = 'pending_trip'
                    entity['pending_trip_countdown'] = entity['trip_delay_steps']
                    entity['fault_detected_on'] = tripping_target
                    Pprint(RELAY_SIM_ID, eid,
                           f"Fault detected on {tripping_target}. Trip pending in {entity['pending_trip_countdown']} steps.")

                if entity['relay_status'] == 'pending_trip' and entity['fault_detected_on'] == tripping_target:
                    if entity['pending_trip_countdown'] <= 0:
                        if tripping_target == 'line':
                            entity['trip_signal_line'] = True
                        elif tripping_target == 'gen':
                            entity['trip_signal_gen'] = True
                        entity['relay_status'] = 'tripped'
                        Pprint(RELAY_SIM_ID, eid, f"TRIPPED {tripping_target}!")
                    else:
                        entity['pending_trip_countdown'] -= 1
            else:  # No fault condition, or fault cleared
                if entity['relay_status'] == 'pending_trip':
                    entity['relay_status'] = 'monitoring'  # Reset if fault clears during delay
                    entity['pending_trip_countdown'] = 0
                    entity['fault_detected_on'] = None
                    Pprint(RELAY_SIM_ID, eid, "Pending trip cancelled, fault cleared.")

            # Pprint(RELAY_SIM_ID, eid, f"Stepped. Status: {entity['relay_status']}, Line Trip: {entity['trip_signal_line']}, Gen Trip: {entity['trip_signal_gen']}")

        return time + STEP_SIZE

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.entities[eid].get(attr)
        return data


# --- 8. Centralized Monitoring Simulator ---
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


class MonitorSim(BaseSim):
    def __init__(self):
        super().__init__(MONITOR_META)
        self.eid_prefix = "Monitor"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0):
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.sim_start_time = sim_start_time
        self.sid = sid
        Pprint(sid, "WORLD", f"Initialized MonitorSim.")
        return MONITOR_META

    def create(self, num, model, **model_params):  # Expect num=1 for centralized monitor
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
        Pprint(MONITOR_SIM_ID, eid, f"Created GridMonitor.")
        return [{'eid': eid, 'type': model}]

    def step(self, time, inputs, max_advance):
        Pprint(MONITOR_SIM_ID, "WORLD", f"Step at time {time}. Inputs: {inputs}")
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
                Pprint(MONITOR_SIM_ID, list(self.entities.keys())[0],
                       f"Line {line_data['eid']} tripped at {time}. Status: {line_data.get('status')}")

        gen_data_list = inputs.get(list(self.entities.keys())[0], {}).get('gen_data_points', [])
        for gen_data in gen_data_list:  # gen_data = {'eid': 'Gen-1', 'P_MW_out': 50, 'status': 'online'}
            current_component_states[gen_data['eid']] = gen_data
            if gen_data.get('status') == 'online':
                total_gen_P += gen_data.get('P_MW_out', 0)
            elif gen_data.get('status') == 'tripped' and \
                    monitor_entity['component_statuses'].get(gen_data['eid'], {}).get(
                        'status') == 'online':  # New trip
                Pprint(MONITOR_SIM_ID, list(self.entities.keys())[0],
                       f"Generator {gen_data['eid']} tripped at {time}.")

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
                Pprint(MONITOR_SIM_ID, list(self.entities.keys())[0],
                       f"CASCADE DETECTED! {recent_trips_in_window} line trips in window.")

        # Determine overall status
        if not monitor_entity['is_cascade_active']:  # Cascade status overrides others
            if any(a['severity'] == 'critical' for a in monitor_entity['active_alarms_list']):
                monitor_entity['overall_status'] = 'critical'
            elif any(a['severity'] == 'warning' for a in monitor_entity['active_alarms_list']):
                monitor_entity['overall_status'] = 'warning'
            else:
                monitor_entity['overall_status'] = 'normal'

        Pprint(MONITOR_SIM_ID, list(self.entities.keys())[0],
               f"Stepped. Freq: {monitor_entity['system_frequency_avg_hz']:.2f} Hz, V_min: {monitor_entity['min_voltage_pu']:.3f} pu, V_max: {monitor_entity['max_voltage_pu']:.3f} pu, P_imbalance: {monitor_entity['system_P_imbalance_MW']:.2f} MW, Status: {monitor_entity['overall_status']}, Alarms: {monitor_entity['active_alarms_count']}")
        if monitor_entity['active_alarms_count'] > 0:
            for alarm in monitor_entity['active_alarms_list']:
                Pprint(MONITOR_SIM_ID, list(self.entities.keys())[0], f"  ALARM: {alarm}")

        return time + STEP_SIZE

    def get_data(self, outputs):
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


# --- 9. Automated Remediation Simulator ---
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


class RemediationSim(BaseSim):
    def __init__(self):
        super().__init__(REMEDIATION_META)
        self.eid_prefix = "RemCtrl"

    def init(self, sid, time_resolution, eid_prefix=None, sim_start_time=0, controllable_gens=None,
             controllable_batteries=None, controllable_loads=None, controllable_pvs=None):
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix
        self.controllable_gens_eids = controllable_gens if controllable_gens else []
        self.controllable_batteries_eids = controllable_batteries if controllable_batteries else []
        self.controllable_loads_eids = controllable_loads if controllable_loads else []  # For demand response
        self.controllable_pvs_eids = controllable_pvs if controllable_pvs else []  # For curtailment
        self.sid = sid
        Pprint(sid, "WORLD", f"Initialized RemediationSim.")
        return REMEDIATION_META

    def create(self, num, model, **model_params):  # Expect num=1
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
        Pprint(REMEDIATION_SIM_ID, eid, f"Created RemediationController.")
        return [{'eid': eid, 'type': model}]

    def step(self, time, inputs, max_advance):
        Pprint(REMEDIATION_SIM_ID, "WORLD", f"Step at time {time}. Inputs: {inputs}")
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
            Pprint(REMEDIATION_SIM_ID, list(self.entities.keys())[0],
                   f"ACTIONS: {controller_entity['last_action_summary']}")

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
            # ----
            # Correct Mosaik way: output these as test_data.
            # This simulator will output a list of desired actions.
            # The scenario script will then iterate these and use world.remote_call() or similar.
            # To make this runnable as-is, I'll make this attribute an output.
            # The main scenario will need to handle these calls.
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

    def get_data(self, outputs):
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


# --- Main Simulation Scenario ---
SIM_CONFIG = {
    GEN_SIM_ID: {'python': f'{__name__}:{GeneratorSim.__name__}'},
    PV_SIM_ID: {'python': f'{__name__}:{PVSim.__name__}'},
    LOAD_SIM_ID: {'python': f'{__name__}:{LoadSim.__name__}'},
    LINE_SIM_ID: {'python': f'{__name__}:{LineSim.__name__}'},
    NODE_SIM_ID: {'python': f'{__name__}:{NodeSim.__name__}'},
    BATTERY_SIM_ID: {'python': f'{__name__}:{BatterySim.__name__}'},
    RELAY_SIM_ID: {'python': f'{__name__}:{ProtectionRelaySim.__name__}'},
    MONITOR_SIM_ID: {'python': f'{__name__}:{MonitorSim.__name__}'},
    REMEDIATION_SIM_ID: {'python': f'{__name__}:{RemediationSim.__name__}'},
    'WebVis': { 'cmd': 'mosaik-web -s 127.0.0.1:8080 %(addr)s', },
}


def run_simulation():
    """Optimized mosaik simulation with WebVis integration"""
    world = mosaik.World(SIM_CONFIG)

    # Start simulators
    pv_sim = world.start('PVSim', eid_prefix='PV')
    load_sim = world.start('LoadSim', eid_prefix='Load')
    gen_sim = world.start('GeneratorSim', eid_prefix='Gen')
    line_sim = world.start('LineSim', eid_prefix='Line')
    node_sim = world.start('NodeSim', eid_prefix='Node')
    battery_sim = world.start('BatterySim', eid_prefix='Batt')
    relay_sim = world.start('ProtectionRelaySim', eid_prefix='Relay')
    monitor_sim = world.start('MonitorSim', eid_prefix='Monitor')


    # Create entities
    nodes = create_nodes(node_sim)
    generators = create_generators(gen_sim)
    pv_systems = create_pv_systems(pv_sim)
    loads = create_loads(load_sim)
    lines = create_lines(line_sim, nodes)
    batteries = create_batteries(battery_sim)
    relays = create_relays(relay_sim, lines, generators)
    monitor = create_monitor(monitor_sim)

    # Connect entities
    connect_power_flow(world, generators, pv_systems, loads, batteries, nodes)
    connect_lines(world, lines, nodes)
    connect_monitoring(world, monitor, nodes, lines, generators, batteries, pv_systems)
    connect_protection(world, relays, lines, generators, nodes)

    # Connect to WebVis and HDF5
    webvis = world.start('WebVis', start_date=START, step_size=60)
    """Connect all components to WebVis and HDF5 for visualization and data storage"""

    # Collect all entities for visualization
    all_entities = {}
    all_entities.update(nodes)
    all_entities.update(generators)
    all_entities.update(loads)
    all_entities.update(lines)
    all_entities.update(batteries)
    all_entities.update(pv_systems)

    webvis.set_config(ignore_types=['Topology',
                                    'Database'])

    vis_topo = webvis.Topology()

    connect_many_to_one(world, nodes.values(), vis_topo, 'line_sum_P_out_MW', 'line_sum_Q_out_MVAR')
    webvis.set_etypes({
        'RefBus': {
            'cls': 'refbus',
            'attr': 'line_sum_P_out_MW',
            'unit': 'P [W]',
            'default': 0,
            'min': 0,
            'max': 30000,
        },
        'PQBus': {
            'cls': 'pqbus',
            'attr': 'line_sum_Q_out_MVAR',
            'unit': 'U [V]',
            'default': 230,
            'min': 0.99 * 230,
            'max': 1.01 * 230,
        },
    })
    #connect_visualization(world, webvis, nodes, generators, loads, lines, batteries, pv_systems)

    print(f"Starting simulation from {START} to {END} seconds")

    # Run simulation with events
    world.run(until=END)  # Real-time factor for visualization

    print("Simulation completed successfully")


def create_nodes(node_sim):
    """Create electrical nodes (buses)"""
    nodes = {
        'hv_bus': node_sim.BusNode(
            base_voltage_kV=132.0,
            is_slack_bus=True
        ),
        'mv_bus': node_sim.BusNode(
            base_voltage_kV=11.0,
            is_slack_bus=False
        ),
        'lv_bus': node_sim.BusNode(
            base_voltage_kV=0.4,
            is_slack_bus=False
        )
    }
    return nodes


def create_generators(gen_sim):
    """Create generators with realistic parameters"""
    generators = {
        'gen_1': gen_sim.Generator(
            max_P_MW=100,
            min_P_MW=20,
            ramping_rate_MW_per_step=5,
            base_voltage_kV=132.0,
            droop_coeff=0.04
        ),
        'gen_2': gen_sim.Generator(
            max_P_MW=50,
            min_P_MW=10,
            ramping_rate_MW_per_step=3,
            base_voltage_kV=132.0,
            droop_coeff=0.05
        )
    }
    return generators


def create_pv_systems(pv_sim):
    """Create PV systems with irradiance profiles"""
    # Create realistic daily irradiance profile
    irradiance_profile = []
    for hour in range(24):
        if 6 <= hour <= 18:  # Daylight hours
            irradiance = 0.8 * (1 - abs(hour - 12) / 6)  # Peak at noon
        else:
            irradiance = 0.0
        irradiance_profile.extend([irradiance] * 3600)  # Hourly to seconds

    pv_systems = {
        'pv_1': pv_sim.PVSystem(
            max_P_MW=30,
            irradiance_profile=irradiance_profile[:END]
        )
    }
    return pv_systems


def create_loads(load_sim):
    """Create residential loads with demand profiles"""
    # Create realistic load profiles
    base_profile_1 = [10 + 5 * random.random() for _ in range(END)]
    base_profile_2 = [15 + 8 * random.random() for _ in range(END)]

    loads = {
        'load_1': load_sim.ResidentialLoad(
            base_P_MW_profile=base_profile_1,
            base_Q_MVAR_profile=[p * 0.2 for p in base_profile_1],
            voltage_sensitivity_P=0.8
        ),
        'load_2': load_sim.ResidentialLoad(
            base_P_MW_profile=base_profile_2,
            base_Q_MVAR_profile=[p * 0.2 for p in base_profile_2],
            voltage_sensitivity_P=0.8
        )
    }
    return loads


def create_lines(line_sim, nodes):
    """Create transmission lines"""
    lines = {
        'line_1': line_sim.TransmissionLine(
            from_node_eid=nodes['hv_bus'].eid,
            to_node_eid=nodes['mv_bus'].eid,
            resistance_ohm=0.1,
            reactance_ohm=0.5,
            thermal_limit_kA=0.5,
            length_km=50,
            base_voltage_kV=132.0
        ),
        'line_2': line_sim.TransmissionLine(
            from_node_eid=nodes['mv_bus'].eid,
            to_node_eid=nodes['lv_bus'].eid,
            resistance_ohm=0.05,
            reactance_ohm=0.2,
            thermal_limit_kA=0.8,
            length_km=20,
            base_voltage_kV=11.0
        )
    }
    return lines


def create_batteries(battery_sim):
    """Create battery storage systems"""
    batteries = {
        'battery_1': battery_sim.BatteryStorage(
            capacity_MWh=20,
            max_P_charge_MW=5,
            max_P_discharge_MW=5,
            initial_SoC_pct=60
        )
    }
    return batteries


def create_relays(relay_sim, lines, generators):
    """Create protection relays"""
    relays = {
        'relay_line_1': relay_sim.OvercurrentRelay(
            monitored_line_eid=lines['line_1'].eid,
            current_threshold_kA=0.45,
            trip_delay_steps=1
        ),
        'relay_gen_1': relay_sim.OvercurrentRelay(
            monitored_gen_eid=generators['gen_1'].eid,
            voltage_threshold_kV_low=0.90,
            trip_delay_steps=2
        )
    }
    return relays


def create_monitor(monitor_sim):
    """Create grid monitoring system"""
    monitor = monitor_sim.GridMonitor(
        voltage_low_pu=0.92,
        voltage_high_pu=1.08,
        freq_low_hz=49.5,
        freq_high_hz=50.5,
        line_loading_crit_pct=95.0,
        cascade_trigger_count=2,
        cascade_time_window_steps=3
    )
    return monitor


def connect_power_flow(world, generators, pv_systems, loads, batteries, nodes):
    """Connect power flow between components and nodes"""
    # Generators to nodes
    world.connect(generators['gen_1'], nodes['hv_bus'],
                  ('P_MW_out', 'gen_sum_P_MW'), ('Q_MVAR_out', 'gen_sum_Q_MVAR'))
    world.connect(generators['gen_2'], nodes['mv_bus'],
                  ('P_MW_out', 'gen_sum_P_MW'), ('Q_MVAR_out', 'gen_sum_Q_MVAR'))

    # PV to node
    world.connect(pv_systems['pv_1'], nodes['mv_bus'],
                  ('P_MW_out', 'gen_sum_P_MW'), ('Q_MVAR_out', 'gen_sum_Q_MVAR'))

    # Batteries to node
    world.connect(batteries['battery_1'], nodes['lv_bus'],
                  ('P_MW_out', 'gen_sum_P_MW'), ('Q_MVAR_out', 'gen_sum_Q_MVAR'))

    # Loads to nodes
    world.connect(loads['load_1'], nodes['mv_bus'],
                  ('P_MW_actual', 'load_sum_P_MW'), ('Q_MVAR_actual', 'load_sum_Q_MVAR'))
    world.connect(loads['load_2'], nodes['lv_bus'],
                  ('P_MW_actual', 'load_sum_P_MW'), ('Q_MVAR_actual', 'load_sum_Q_MVAR'))

    # Node voltage feedback to loads
    #world.connect(nodes['mv_bus'], loads['load_1'], ('voltage_kV', 'node_voltage_kV'))
    #world.connect(nodes['lv_bus'], loads['load_2'], ('voltage_kV', 'node_voltage_kV'))


def connect_lines(world, lines, nodes):
    """Connect transmission lines to nodes"""
    # Line 1 connections
    world.connect(lines['line_1'], nodes['hv_bus'],
                  ('P_MW_flow', 'line_sum_P_out_MW'), ('Q_MVAR_flow', 'line_sum_Q_out_MVAR'))
    world.connect(lines['line_1'], nodes['mv_bus'],
                  ('P_MW_flow', 'line_sum_P_in_MW'), ('Q_MVAR_flow', 'line_sum_Q_in_MVAR'))

    # Line 2 connections
    world.connect(lines['line_2'], nodes['mv_bus'],
                  ('P_MW_flow', 'line_sum_P_out_MW'), ('Q_MVAR_flow', 'line_sum_Q_out_MVAR'))
    world.connect(lines['line_2'], nodes['lv_bus'],
                  ('P_MW_flow', 'line_sum_P_in_MW'), ('Q_MVAR_flow', 'line_sum_Q_in_MVAR'))


def connect_monitoring(world, monitor, nodes, lines, generators, batteries, pv_systems):
    """Connect monitoring system to all components"""
    # Monitor all nodes - use simple attribute names that exist in the monitor
    for node_name, node in nodes.items():
        world.connect(node, monitor,
                      ('voltage_pu', 'voltage_pu'))

    # Monitor all lines - use simple attribute names
    #for line_name, line in lines.items():
    #    world.connect(line, monitor,
    #                  ('loading_percent', 'loading_percent'),
    #                  ('current_kA', 'current_kA'))

    # Monitor generators - use simple attribute names
    #for gen_name, gen in generators.items():
    #    world.connect(gen, monitor,
    #                  ('P_MW_out', 'P_MW_out'),
    #                  ('status', 'status'))


def connect_protection(world, relays, lines, generators, nodes):
    """Connect protection systems"""
    # Line protection
    world.connect(lines['line_1'], relays['relay_line_1'], ('current_kA', 'line_current_kA'))
    #world.connect(relays['relay_line_1'], lines['line_1'], ('trip_signal', 'status'))

    # Generator protection
    world.connect(nodes['hv_bus'], relays['relay_gen_1'], ('voltage_pu', 'gen_voltage_pu'))
    #world.connect(relays['relay_gen_1'], generators['gen_1'], ('trip_signal', 'status'))


def connect_visualization(world, webvis, nodes, generators, loads, lines, batteries, pv_systems):
    """Connect all components to WebVis and HDF5 for visualization and data storage"""

    # Collect all entities for visualization
    all_entities = {}
    all_entities.update(nodes)
    all_entities.update(generators)
    all_entities.update(loads)
    all_entities.update(lines)
    all_entities.update(batteries)
    all_entities.update(pv_systems)

    webvis.set_config(ignore_types=['Topology',
                                    'Database'])

    vis_topo = webvis.Topology()

    connect_many_to_one(world, nodes.values(), vis_topo, 'line_sum_P_out_MW', 'line_sum_Q_out_MVAR')
    webvis.set_etypes({
        'RefBus': {
            'cls': 'refbus',
            'attr': 'line_sum_P_out_MW',
            'unit': 'P [W]',
            'default': 0,
            'min': 0,
            'max': 30000,
        },
        'PQBus': {
            'cls': 'pqbus',
            'attr': 'line_sum_Q_out_MVAR',
            'unit': 'U [V]',
            'default': 230,
            'min': 0.99 * 230,
            'max': 1.01 * 230,
        },
    })



START = '2014-01-01 00:00:00'
END = 1000000  # 100 seconds
STEP_SIZE = 1
SIM_DURATION = 31 * 24 * 3600

if __name__ == '__main__':
    try:
        run_simulation()
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user")
    except Exception as e:
        print(f"Simulation error: {e}")
        raise


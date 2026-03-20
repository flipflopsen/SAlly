import mosaik_api_v3
from typing import Dict, List, Tuple, Set, Optional, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class GridConnection:
    """Represents a connection between two simulators with specific attributes."""

    def __init__(self, source_sim: str, source_eid: str, source_attr: str,
                 target_sim: str, target_eid: str, target_attr: str):
        self.source_sim = source_sim
        self.source_eid = source_eid
        self.source_attr = source_attr
        self.target_sim = target_sim
        self.target_eid = target_eid
        self.target_attr = target_attr

    def __repr__(self):
        return f"GridConnection({self.source_sim}.{self.source_eid}.{self.source_attr} -> {self.target_sim}.{self.target_eid}.{self.target_attr})"


class GridConnector:
    """
    Connector class for managing connections between different Mosaik simulators.

    This class handles the creation and management of connections between various
    grid simulators (generators, loads, lines, nodes, batteries, etc.) and keeps
    track of all connections to form the complete grid topology.
    """

    def __init__(self):
        self.connections: List[GridConnection] = []
        self.simulator_entities: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.connection_matrix: Dict[str, Dict[str, List[GridConnection]]] = defaultdict(lambda: defaultdict(list))

        # Define connection rules for different simulator types
        self._setup_connection_rules()

    def _setup_connection_rules(self):
        """Set up the rules for connecting different simulator types."""

        # Power flow connections: sources to nodes
        self.power_flow_rules = {
            'GeneratorSim': {
                'target_sims': ['NodeSim'],
                'source_attrs': ['P_MW_out', 'Q_MVAR_out'],
                'target_attrs': ['gen_sum_P_MW', 'gen_sum_Q_MVAR']
            },
            'PVSim': {
                'target_sims': ['NodeSim'],
                'source_attrs': ['P_MW_out', 'Q_MVAR_out'],
                'target_attrs': ['gen_sum_P_MW', 'gen_sum_Q_MVAR']
            },
            'BatterySim': {
                'target_sims': ['NodeSim'],
                'source_attrs': ['P_MW_out', 'Q_MVAR_out'],
                'target_attrs': ['gen_sum_P_MW', 'gen_sum_Q_MVAR']
            }
        }

        # Load connections: loads to nodes
        self.load_rules = {
            'LoadSim': {
                'target_sims': ['NodeSim'],
                'source_attrs': ['P_MW_actual', 'Q_MVAR_actual'],
                'target_attrs': ['load_sum_P_MW', 'load_sum_Q_MVAR']
            }
        }

        # Line connections: lines to nodes
        self.line_rules = {
            'LineSim': {
                'target_sims': ['NodeSim'],
                'source_attrs': ['P_MW_flow', 'Q_MVAR_flow'],
                'target_attrs': ['line_sum_P_out_MW', 'line_sum_Q_out_MVAR', 'line_sum_P_in_MW', 'line_sum_Q_in_MVAR']
            }
        }

        # Node connections: nodes to other components
        self.node_rules = {
            'NodeSim': {
                'target_sims': ['LoadSim', 'LineSim', 'GeneratorSim', 'BatterySim', 'PVSim', 'ProtectionRelaySim', 'MonitorSim'],
                'source_attrs': ['voltage_kV', 'voltage_kV', 'voltage_pu', 'frequency_Hz', 'frequency_Hz'],
                'target_attrs': ['node_voltage_kV', 'voltage_kV', 'voltage_pu', 'grid_frequency_Hz', 'frequency_Hz']
            }
        }

        # Protection relay connections
        self.protection_rules = {
            'LineSim': {
                'target_sims': ['ProtectionRelaySim'],
                'source_attrs': ['current_kA'],
                'target_attrs': ['line_current_kA']
            },
            'NodeSim': {
                'target_sims': ['ProtectionRelaySim'],
                'source_attrs': ['voltage_pu'],
                'target_attrs': ['gen_voltage_pu']
            },
            'GeneratorSim': {
                'target_sims': ['ProtectionRelaySim'],
                'source_attrs': ['status'],
                'target_attrs': ['gen_status']
            }
        }

        # Monitor connections
        self.monitor_rules = {
            'NodeSim': {
                'target_sims': ['MonitorSim'],
                'source_attrs': ['voltage_pu', 'frequency_Hz', 'P_imbalance_MW'],
                'target_attrs': ['voltage_pu', 'system_frequency_avg_hz', 'system_P_imbalance_MW']
            },
            'MonitorSim': {
                'target_sims': ['NodeSim'],
                'source_attrs': ['system_P_imbalance_MW'],
                'target_attrs': ['system_total_P_imbalance_MW']
            }
        }

        # Remediation controller connections
        self.remediation_rules = {
            'MonitorSim': {
                'target_sims': ['RemediationSim'],
                'source_attrs': ['overall_status', 'active_alarms_count'],
                'target_attrs': ['last_action_summary', 'actions_taken_count']
            }
        }

    def register_simulator(self, sim_id: str, simulator: mosaik_api_v3.Simulator):
        """
        Register a simulator instance with the connector.

        Args:
            sim_id: Unique identifier for the simulator
            simulator: The mosaik simulator instance
        """
        self.simulator_entities[sim_id] = {
            'simulator': simulator,
            'entities': {}
        }
        logger.info(f"Registered simulator: {sim_id}")

    def register_entity(self, sim_id: str, eid: str, entity_data: Dict[str, Any]):
        """
        Register an entity created by a simulator.

        Args:
            sim_id: Simulator ID
            eid: Entity ID
            entity_data: Entity data dictionary
        """
        if sim_id in self.simulator_entities:
            self.simulator_entities[sim_id]['entities'][eid] = entity_data
            logger.debug(f"Registered entity: {sim_id}.{eid}")

    def connect(self, source_sim: mosaik_api_v3.Simulator, target_sim: mosaik_api_v3.Simulator,
                world: Any = None) -> bool:
        """
        Connect two simulators based on their types and available entities.

        Args:
            source_sim: Source simulator instance
            target_sim: Target simulator instance
            world: Mosaik world object (optional, for actual connection)

        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            # Get simulator IDs from instances
            source_id_sid = self.get_sim_id_from_eid(source_sim._sid)
            target_id_sid = self.get_sim_id_from_eid(target_sim._sid)
            source_id = source_id_sid
            target_id = target_id_sid

            logger.info(f"Attempting to connect {source_id} -> {target_id}")

            # Get entities for both simulators
            source_entities = self.simulator_entities.get(source_id, {}).get('entities', {})
            target_entities = self.simulator_entities.get(target_id, {}).get('entities', {})

            if not source_entities or not target_entities:
                logger.warning(f"No entities found for {source_id} or {target_id}")
                return False

            # Determine connection rules based on simulator types
            connections_made = 0

            # Try power flow connections (source to target)
            if source_id in self.power_flow_rules and target_id in self.power_flow_rules[source_id]['target_sims']:
                connections_made += self._connect_power_flow(source_id, target_id, source_entities, target_entities, world)

            # Try load connections
            if source_id in self.load_rules and target_id in self.load_rules[source_id]['target_sims']:
                connections_made += self._connect_loads(source_id, target_id, source_entities, target_entities, world)

            # Try line connections
            if source_id in self.line_rules and target_id in self.line_rules[source_id]['target_sims']:
                connections_made += self._connect_lines(source_id, target_id, source_entities, target_entities, world)

            # Try node connections (bidirectional)
            if source_id in self.node_rules and target_id in self.node_rules[source_id]['target_sims']:
                connections_made += self._connect_nodes(source_id, target_id, source_entities, target_entities, world)

            # Try protection connections
            if source_id in self.protection_rules and target_id in self.protection_rules[source_id]['target_sims']:
                connections_made += self._connect_protection(source_id, target_id, source_entities, target_entities, world)

            # Try monitor connections
            if source_id in self.monitor_rules and target_id in self.monitor_rules[source_id]['target_sims']:
                connections_made += self._connect_monitoring(source_id, target_id, source_entities, target_entities, world)

            # Try remediation connections
            if source_id in self.remediation_rules and target_id in self.remediation_rules[source_id]['target_sims']:
                connections_made += self._connect_remediation(source_id, target_id, source_entities, target_entities, world)

            success = connections_made > 0
            logger.info(f"Connection {source_id} -> {target_id}: {'SUCCESS' if success else 'FAILED'} ({connections_made} connections made)")

            return success

        except Exception as e:
            logger.error(f"Error connecting {source_id} -> {target_id}: {e}")
            return False

    def _connect_power_flow(self, source_id: str, target_id: str, source_entities: Dict, target_entities: Dict, world: Any) -> int:
        """Connect power sources (generators, PV, batteries) to nodes."""
        rules = self.power_flow_rules[source_id]
        connections_made = 0

        for source_eid, source_data in source_entities.items():
            for target_eid, target_data in target_entities.items():
                # Create connections for each attribute pair
                for src_attr, tgt_attr in zip(rules['source_attrs'], rules['target_attrs']):
                    if self._can_connect(source_data, src_attr, target_data, tgt_attr):
                        connection = GridConnection(source_id, source_eid, src_attr, target_id, target_eid, tgt_attr)
                        self._record_connection(connection)

                        if world:
                            try:
                                world.connect(source_data['entity_ref'], target_data['entity_ref'],
                                            (src_attr, tgt_attr))
                                connections_made += 1
                            except Exception as e:
                                logger.warning(f"Failed to create world connection: {e}")

        return connections_made

    def _connect_loads(self, source_id: str, target_id: str, source_entities: Dict, target_entities: Dict, world: Any) -> int:
        """Connect loads to nodes."""
        return self._connect_power_flow(source_id, target_id, source_entities, target_entities, world)

    def _connect_lines(self, source_id: str, target_id: str, source_entities: Dict, target_entities: Dict, world: Any) -> int:
        """Connect lines to nodes."""
        rules = self.line_rules[source_id]
        connections_made = 0

        for source_eid, source_data in source_entities.items():
            for target_eid, target_data in target_entities.items():
                # Lines connect to nodes in both directions (in and out)
                for i in range(2):  # 0 for 'out', 1 for 'in'
                    src_attr = rules['source_attrs'][i % len(rules['source_attrs'])]
                    tgt_attr = rules['target_attrs'][i + 2] if i > 0 else rules['target_attrs'][i]

                    if self._can_connect(source_data, src_attr, target_data, tgt_attr):
                        connection = GridConnection(source_id, source_eid, src_attr, target_id, target_eid, tgt_attr)
                        self._record_connection(connection)

                        if world:
                            try:
                                world.connect(source_data['entity_ref'], target_data['entity_ref'],
                                            (src_attr, tgt_attr))
                                connections_made += 1
                            except Exception as e:
                                logger.warning(f"Failed to create world connection: {e}")

        return connections_made

    def _connect_nodes(self, source_id: str, target_id: str, source_entities: Dict, target_entities: Dict, world: Any) -> int:
        """Connect nodes to other components (loads, generators, etc.)."""
        rules = self.node_rules[source_id]
        connections_made = 0

        for source_eid, source_data in source_entities.items():
            for target_eid, target_data in target_entities.items():
                # Create connections for each attribute pair
                for src_attr, tgt_attr in zip(rules['source_attrs'], rules['target_attrs']):
                    if self._can_connect(source_data, src_attr, target_data, tgt_attr):
                        connection = GridConnection(source_id, source_eid, src_attr, target_id, target_eid, tgt_attr)
                        self._record_connection(connection)

                        if world:
                            try:
                                world.connect(source_data['entity_ref'], target_data['entity_ref'],
                                            (src_attr, tgt_attr))
                                connections_made += 1
                            except Exception as e:
                                logger.warning(f"Failed to create world connection: {e}")

        return connections_made

    def _connect_protection(self, source_id: str, target_id: str, source_entities: Dict, target_entities: Dict, world: Any) -> int:
        """Connect protection relays to monitored components."""
        rules = self.protection_rules[source_id]
        connections_made = 0

        for source_eid, source_data in source_entities.items():
            for target_eid, target_data in target_entities.items():
                # Create connections for each attribute pair
                for src_attr, tgt_attr in zip(rules['source_attrs'], rules['target_attrs']):
                    if self._can_connect(source_data, src_attr, target_data, tgt_attr):
                        connection = GridConnection(source_id, source_eid, src_attr, target_id, target_eid, tgt_attr)
                        self._record_connection(connection)

                        if world:
                            try:
                                world.connect(source_data['entity_ref'], target_data['entity_ref'],
                                            (src_attr, tgt_attr))
                                connections_made += 1
                            except Exception as e:
                                logger.warning(f"Failed to create world connection: {e}")

        return connections_made

    def _connect_monitoring(self, source_id: str, target_id: str, source_entities: Dict, target_entities: Dict, world: Any) -> int:
        """Connect components to monitoring system."""
        rules = self.monitor_rules[source_id]
        connections_made = 0

        for source_eid, source_data in source_entities.items():
            for target_eid, target_data in target_entities.items():
                # Create connections for each attribute pair
                for src_attr, tgt_attr in zip(rules['source_attrs'], rules['target_attrs']):
                    if self._can_connect(source_data, src_attr, target_data, tgt_attr):
                        connection = GridConnection(source_id, source_eid, src_attr, target_id, target_eid, tgt_attr)
                        self._record_connection(connection)

                        if world:
                            try:
                                world.connect(source_data['entity_ref'], target_data['entity_ref'],
                                            (src_attr, tgt_attr))
                                connections_made += 1
                            except Exception as e:
                                logger.warning(f"Failed to create world connection: {e}")

        return connections_made

    def _connect_remediation(self, source_id: str, target_id: str, source_entities: Dict, target_entities: Dict, world: Any) -> int:
        """Connect monitoring to remediation controller."""
        rules = self.remediation_rules[source_id]
        connections_made = 0

        for source_eid, source_data in source_entities.items():
            for target_eid, target_data in target_entities.items():
                # Create connections for each attribute pair
                for src_attr, tgt_attr in zip(rules['source_attrs'], rules['target_attrs']):
                    if self._can_connect(source_data, src_attr, target_data, tgt_attr):
                        connection = GridConnection(source_id, source_eid, src_attr, target_id, target_eid, tgt_attr)
                        self._record_connection(connection)

                        if world:
                            try:
                                world.connect(source_data['entity_ref'], target_data['entity_ref'],
                                            (src_attr, tgt_attr))
                                connections_made += 1
                            except Exception as e:
                                logger.warning(f"Failed to create world connection: {e}")

        return connections_made

    def _can_connect(self, source_data: Dict, source_attr: str, target_data: Dict, target_attr: str) -> bool:
        """Check if a connection between two attributes is possible."""
        # Check if source has the attribute
        if source_attr not in source_data.get('attrs', []):
            return False

        # TODO: It fails the following check all the time because our defined attributes in the META are not present in the 'attrs' list.
        # Check if target has the attribute
        if target_attr not in target_data.get('attrs', []):
            return False

        return True

    def _record_connection(self, connection: GridConnection):
        """Record a connection in the internal data structures."""
        self.connections.append(connection)
        self.connection_matrix[connection.source_sim][connection.target_sim].append(connection)
        logger.debug(f"Recorded connection: {connection}")

    def get_connections(self) -> List[GridConnection]:
        """Get all recorded connections."""
        return self.connections.copy()

    def get_connections_between(self, source_sim: str, target_sim: str) -> List[GridConnection]:
        """Get connections between two specific simulators."""
        return self.connection_matrix.get(source_sim, {}).get(target_sim, [])

    def get_grid_topology(self) -> Dict[str, Any]:
        """
        Get the complete grid topology as a dictionary.

        Returns:
            Dict containing nodes, connections, and metadata
        """
        topology = {
            'simulators': dict(self.simulator_entities),
            'connections': [conn.__dict__ for conn in self.connections],
            'connection_count': len(self.connections),
            'simulator_types': list(self.simulator_entities.keys())
        }

        return topology

    def print_topology_summary(self):
        """Print a summary of the current grid topology."""
        print("\n=== Grid Topology Summary ===")
        print(f"Total connections: {len(self.connections)}")
        print(f"Simulator types: {list(self.simulator_entities.keys())}")

        print("\nConnections by simulator pair:")
        for source_sim, targets in self.connection_matrix.items():
            for target_sim, connections in targets.items():
                print(f"  {source_sim} -> {target_sim}: {len(connections)} connections")

        print("\nDetailed connections:")
        for conn in self.connections:
            print(f"  {conn}")

    def save_topology(self, filename: str):
        """Save the grid topology to a JSON file."""
        import json

        topology = self.get_grid_topology()

        with open(filename, 'w') as f:
            json.dump(topology, f, indent=2, default=str)

        logger.info(f"Grid topology saved to {filename}")

    def load_topology(self, filename: str):
        """Load a grid topology from a JSON file."""
        import json

        with open(filename, 'r') as f:
            topology = json.load(f)

        # Restore connections
        self.connections = []
        for conn_data in topology.get('connections', []):
            conn = GridConnection(**conn_data)
            self._record_connection(conn)

        logger.info(f"Grid topology loaded from {filename}")



    def get_sim_id_from_eid(self, eid: str) -> str:
            """Extract simulator ID from entity ID."""
            # This is a simple mapping based on prefix - in practice you'd have better tracking
            prefix_map = {
                'Gen': 'GeneratorSim',
                'PV': 'PVSim',
                'Load': 'LoadSim',
                'Node': 'NodeSim',
                'Line': 'LineSim',
                'Batt': 'BatterySim',
                'Relay': 'ProtectionRelaySim',
                'Monitor': 'MonitorSim',
                'RemCtrl': 'RemediationSim'
            }

            for prefix, sim_id in prefix_map.items():
                if eid.lower().startswith(prefix.lower()):
                    return sim_id

            return 'unknown'

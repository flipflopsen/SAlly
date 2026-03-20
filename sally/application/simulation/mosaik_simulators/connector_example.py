#!/usr/bin/env python3
"""
Example usage of the GridConnector class for connecting Mosaik simulators.

This example demonstrates how to use the GridConnector to automatically
connect different types of grid simulators based on their types and
available attributes.
"""

import mosaik
import mosaik_api_v3
from typing import Dict, Any
import logging

# Import the simulators (these would normally be imported from their respective files)
from sally.application.simulation.mosaik_simulators.generator import GeneratorSim, GEN_SIM_ID
from sally.application.simulation.mosaik_simulators.pv import PVSim, PV_SIM_ID
from sally.application.simulation.mosaik_simulators.load import LoadSim, LOAD_SIM_ID
from sally.application.simulation.mosaik_simulators.node import NodeSim, NODE_SIM_ID
from sally.application.simulation.mosaik_simulators.line import LineSim, LINE_SIM_ID
from sally.application.simulation.mosaik_simulators.battery import BatterySim, BATTERY_SIM_ID
from sally.application.simulation.mosaik_simulators.monitor import MonitorSim, MONITOR_SIM_ID
from sally.application.simulation.mosaik_simulators.protection_relay import ProtectionRelaySim, RELAY_SIM_ID
from sally.application.simulation.mosaik_simulators.remediation import RemediationSim, REMEDIATION_SIM_ID
from sally.application.simulation.mosaik_simulators.connector import GridConnector, GridConnection
from sally.application.simulation.mosaik_simulators.simulation_config_manager import SimulationConfigurationManager
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExampleGridConnector:
    """Example class demonstrating how to use the GridConnector."""

    def __init__(self, config_manager: Optional[SimulationConfigurationManager] = None):
        self.connector = GridConnector()
        self.config_manager = config_manager or SimulationConfigurationManager()
        self.world = None
        self.simulators = {}

    def setup_simulation(self):
        """Set up the Mosaik simulation environment."""
        # Get simulation configuration from config manager
        sim_config = self.config_manager.get_sim_config()

        self.world = mosaik.World(sim_config)

        # Start simulators using configuration
        self.simulators = {}
        for sim_id in sim_config.keys():
            eid_prefix = self.config_manager.get_simulator_eid_prefix(sim_id)
            self.simulators[sim_id] = self.world.start(sim_id, eid_prefix=eid_prefix)

        # Register simulators with the connector
        for sim_id, sim_instance in self.simulators.items():
            self.connector.register_simulator(sim_id, sim_instance)

        logger.info("Simulation environment set up successfully")

    def create_entities(self):
        """Create entities for each simulator using configuration manager."""
        # Get all entities from configuration
        entities = {}

        # Create nodes
        nodes = self._create_entities_from_config('nodes', 'BusNode')
        entities.update(nodes)

        # Create generators
        generators = self._create_entities_from_config('generators', 'Generator')
        entities.update(generators)

        # Create PV systems
        pv_systems = self._create_entities_from_config('pv_systems', 'PVSystem')
        entities.update(pv_systems)

        # Create loads
        loads = self._create_entities_from_config('loads', 'ResidentialLoad')
        entities.update(loads)

        # Create lines
        lines = self._create_entities_from_config('lines', 'TransmissionLine')
        entities.update(lines)

        # Create batteries
        batteries = self._create_entities_from_config('batteries', 'BatteryStorage')
        entities.update(batteries)

        # Create relays
        relays = self._create_entities_from_config('relays', 'OvercurrentRelay')
        entities.update(relays)

        # Create monitors
        monitors = self._create_entities_from_config('monitors', 'GridMonitor')
        entities.update(monitors)

        # Create remediation controllers
        remediation_controllers = self._create_entities_from_config('remediation_controllers', 'RemediationController')
        entities.update(remediation_controllers)

        # Register entities with the connector
        for eid, entity in entities.items():
            sim_id = self._get_sim_id_from_eid(entity)
            if sim_id:
                self.connector.register_entity(sim_id, eid, {
                    'entity_ref': entity,
                    'attrs': self.config_manager.get_attribute_mapping(self._get_entity_type_from_eid(eid)),
                    'type': sim_id
                })

        logger.info(f"Created {len(entities)} entities")
        return entities

    def _create_entities_from_config(self, entity_type: str, model_name: str) -> Dict[str, Any]:
        """Create entities of a specific type from configuration."""
        entities = {}
        entity_configs = self.config_manager.get_all_entities_of_type(entity_type)

        for entity_id, config in entity_configs.items():
            # Get the appropriate simulator
            sim_id = self._get_sim_id_from_entity_type(entity_type)
            if sim_id not in self.simulators:
                logger.warning(f"No simulator found for entity type: {entity_type}")
                continue

            simulator = self.simulators[sim_id]

            # Get creation parameters from config
            creation_params = self.config_manager.get_entity_creation_params(entity_type, entity_id)

            # Create the entity
            try:
                entity = simulator._sid
                # TODO: Check if entities already contain
                entities[entity_id] = entity
                logger.info(f"Created {entity_type}.{entity_id}")
            except Exception as e:
                logger.error(f"Failed to create {entity_type}.{entity_id}: {e}")

        return entities

    def _get_sim_id_from_eid(self, eid: str) -> str:
        """Extract simulator ID from entity ID."""
        # This is a simple mapping based on prefix - in practice you'd have better tracking
        prefix_map = {
            'Gen': 'generator',
            'PV': 'pv',
            'Load': 'load',
            'Node': 'node',
            'Line': 'line',
            'Batt': 'battery',
            'Relay': 'relay',
            'Monitor': 'monitor',
            'RemCtrl': 'remediation'
        }

        for prefix, sim_id in prefix_map.items():
            if eid.startswith(prefix):
                return sim_id

        return 'unknown'

    def _get_entity_attributes(self, entity) -> list:
        """Get the attributes available for an entity."""
        # This would normally be determined from the simulator's meta data
        # For this example, we'll return common attributes
        return ['P_MW_out', 'Q_MVAR_out', 'voltage_kV', 'frequency_Hz', 'status']

    def connect_simulators(self):
        """Connect all simulators using the GridConnector."""
        logger.info("Starting automatic connection process...")

        # Get connection pairs from configuration manager
        connection_pairs = self.config_manager.get_connection_pairs()

        successful_connections = 0
        total_connections = 0

        for source_id, target_id in connection_pairs:
            source_sim_id = self._get_sim_id_from_eid(source_id)
            target_sim_id = self._get_sim_id_from_eid(target_id)
            if source_sim_id in self.simulators and target_sim_id in self.simulators:
                source_sim = self.simulators[source_sim_id]
                target_sim = self.simulators[target_sim_id]

                success = self.connector.connect(source_sim, target_sim, self.world)
                if success:
                    successful_connections += 1
                total_connections += 1

                logger.info(f"Connected {source_id} -> {target_id}: {'✓' if success else '✗'}")

        logger.info(f"Connection process complete: {successful_connections}/{total_connections} successful")

        return successful_connections == total_connections

    def run_simulation(self, duration: Optional[int] = None):
        """Run the simulation for the specified duration."""
        # Use duration from config if not specified
        if duration is None:
            duration = self.config_manager.get_simulation_params().get('duration', 100)

        logger.info(f"Running simulation for {duration} time steps...")

        try:
            self.world.run(until=duration)
            logger.info("Simulation completed successfully")
            return True
        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            return False

    def analyze_topology(self):
        """Analyze and display the grid topology."""
        logger.info("Analyzing grid topology...")

        # Get topology information
        topology = self.connector.get_grid_topology()

        print("\n" + "="*50)
        print("GRID TOPOLOGY ANALYSIS")
        print("="*50)

        print(f"Total simulators: {len(topology['simulator_types'])}")
        print(f"Total connections: {topology['connection_count']}")

        print("\nSimulator types:")
        for sim_type in topology['simulator_types']:
            print(f"  - {sim_type}")

        print("\nConnections by type:")
        connections_by_type = {}
        for conn in self.connector.get_connections():
            pair = f"{conn.source_sim} -> {conn.target_sim}"
            connections_by_type[pair] = connections_by_type.get(pair, 0) + 1

        for pair, count in sorted(connections_by_type.items()):
            print(f"  {pair}: {count} connections")

        print("\nDetailed connection list:")
        for i, conn in enumerate(self.connector.get_connections()[:10], 1):  # Show first 10
            print(f"  {i}. {conn}")

        if len(self.connector.get_connections()) > 10:
            print(f"  ... and {len(self.connector.get_connections()) - 10} more connections")

        # Save topology to file
        self.connector.save_topology('grid_topology.json')
        logger.info("Topology saved to grid_topology.json")

    def demonstrate_usage(self):
        """Demonstrate the GridConnector usage."""
        print("\n" + "="*60)
        print("GRID CONNECTOR DEMONSTRATION")
        print("="*60)

        # Show configuration summary
        print("1. Configuration loaded:")
        self.config_manager.print_config_summary()

        # Set up simulation
        print("\n2. Setting up simulation environment...")
        self.setup_simulation()

        # Create entities
        print("\n3. Creating entities...")
        entities = self.create_entities()

        # Connect simulators
        print("\n4. Connecting simulators automatically...")
        success = self.connect_simulators()

        if success:
            print("✓ All simulators connected successfully!")
        else:
            print("⚠ Some connections may have failed")

        # Analyze topology
        print("\n5. Analyzing grid topology...")
        self.analyze_topology()

        # Show connection details
        print("\n6. Connection details:")
        self.connector.print_topology_summary()

        return success

    def _get_sim_id_from_eid(self, eid: str) -> str:
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

    def _get_entity_type_from_eid(self, eid: str) -> str:
        """Extract entity type from entity ID."""
        type_map = {
            'Gen': 'generators',
            'PV': 'pv_systems',
            'Load': 'loads',
            'Node': 'nodes',
            'Line': 'lines',
            'Batt': 'batteries',
            'Relay': 'relays',
            'Monitor': 'monitors',
            'RemCtrl': 'remediation_controllers'
        }

        for prefix, entity_type in type_map.items():
            if eid.startswith(prefix):
                return entity_type

        return 'unknown'

    def _get_sim_id_from_entity_type(self, entity_type: str) -> str:
        """Get simulator ID from entity type."""
        sim_map = {
            'nodes': 'NodeSim',
            'generators': 'GeneratorSim',
            'pv_systems': 'PVSim',
            'loads': 'LoadSim',
            'lines': 'LineSim',
            'batteries': 'BatterySim',
            'relays': 'ProtectionRelaySim',
            'monitors': 'MonitorSim',
            'remediation_controllers': 'RemediationSim'
        }

        return sim_map.get(entity_type, 'unknown')

    def _get_entity_attributes(self, entity) -> list:
        """Get the attributes available for an entity."""
        # This would normally be determined from the simulator's meta data
        # For this example, we'll return common attributes
        return ['P_MW_out', 'Q_MVAR_out', 'voltage_kV', 'frequency_Hz', 'status']


def main():
    """Main function to run the example."""
    print("GridConnector Example")
    print("This example demonstrates how to use the GridConnector class")
    print("with the centralized SimulationConfigurationManager.\n")

    try:
        # Demonstrate configuration manager usage
        print("Loading configuration...")
        config_manager = SimulationConfigurationManager()
        config_manager.print_config_summary()

        # Create example with configuration manager
        example = ExampleGridConnector(config_manager)
        success = example.demonstrate_usage()

        if success:
            print("\n✓ Example completed successfully!")
        else:
            print("\n⚠ Example completed with some issues")

    except KeyboardInterrupt:
        print("\n\nExample interrupted by user")
    except Exception as e:
        print(f"\n\nExample failed with error: {e}")
        logger.exception("Example error")


if __name__ == '__main__':
    main()

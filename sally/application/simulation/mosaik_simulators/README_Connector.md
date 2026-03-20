# GridConnector Documentation

## Overview

The `GridConnector` class provides an automated way to connect different Mosaik simulators in a power grid simulation. It handles the complex task of establishing connections between various types of grid components (generators, loads, lines, nodes, batteries, etc.) based on their types and available attributes.

The system uses a centralized `SimulationConfigurationManager` that reads configuration from YAML files, eliminating redundant SIM_CONFIG definitions and providing a single source of truth for all simulation parameters.

## Features

- **Automatic Connection**: Intelligently connects simulators based on their types
- **Connection Tracking**: Memorizes all connections made to form the complete grid topology
- **Flexible Rules**: Configurable connection rules for different simulator types
- **Topology Analysis**: Provides detailed analysis of the grid structure
- **Persistence**: Can save and load grid topologies to/from JSON files

## Architecture

### SimulationConfigurationManager

The `SimulationConfigurationManager` class provides centralized configuration management:

- **YAML Configuration**: Reads all settings from `simulation_config.yml`
- **Entity Management**: Handles creation parameters for all entity types
- **Connection Management**: Defines connection pairs between simulators
- **Profile Management**: Manages default profiles for loads, PV systems, etc.
- **Validation**: Validates configuration completeness and consistency

### GridConnector

The `GridConnector` class handles automatic connection of simulators:

- **Intelligent Connection**: Uses predefined rules for different simulator types
- **Topology Tracking**: Records all connections for grid analysis
- **Attribute Mapping**: Maps compatible attributes between simulators
- **Error Handling**: Robust error handling with detailed logging

## Quick Start

### Basic Usage with Configuration Manager

```python
from SAlly.simulation.mosaik_simulators.connector import GridConnector
from SAlly.simulation.mosaik_simulators.simulation_config_manager import SimulationConfigurationManager
from SAlly.simulation.mosaik_simulators.connector_example import ExampleGridConnector
import mosaik

# Method 1: Use configuration manager directly
config_manager = SimulationConfigurationManager()
sim_config = config_manager.get_sim_config()
world = mosaik.World(sim_config)

# Method 2: Use the example class (recommended)
example = ExampleGridConnector(config_manager)
example.setup_simulation()
entities = example.create_entities()
success = example.connect_simulators()
```

### Configuration File Structure

The system uses a YAML configuration file (`simulation_config.yml`) that contains:

```yaml
# Simulator configurations
simulators:
  GeneratorSim:
    python_class: 'SAlly.simulation.mosaik_simulators.generator:GeneratorSim'
    eid_prefix: 'Gen'

# Entity configurations
entities:
  generators:
    gen_1:
      max_P_MW: 100
      min_P_MW: 20
      # ... other parameters

# Connection pairs
connections:
  pairs:
    - ['generator', 'node']
    - ['pv', 'node']
    # ... more connections
```

### Using the Example

Run the complete example with configuration management:

```bash
cd SAlly/simulation/mosaik_simulators
python connector_example.py
```

## Architecture

### SimulationConfigurationManager Class

Centralized configuration management class with the following key methods:

- `load_config(config_file)`: Load configuration from YAML file
- `save_config(config_file)`: Save configuration to YAML file
- `get_sim_config()`: Get Mosaik simulator configuration
- `get_entity_config(entity_type, entity_id)`: Get entity configuration
- `get_connection_pairs()`: Get connection pairs
- `get_simulation_params()`: Get simulation parameters
- `get_attribute_mapping(entity_type)`: Get attribute mappings
- `validate_config()`: Validate configuration completeness

### GridConnection Class

Represents a single connection between two simulators:

```python
connection = GridConnection(
    source_sim='GeneratorSim',
    source_eid='Gen-1',
    source_attr='P_MW_out',
    target_sim='NodeSim',
    target_eid='Node-1',
    target_attr='gen_sum_P_MW'
)
```

### GridConnector Class

Main connector class with the following key methods:

- `register_simulator(sim_id, simulator)`: Register a simulator instance
- `register_entity(sim_id, eid, entity_data)`: Register an entity
- `connect(source_sim, target_sim, world)`: Connect two simulators
- `get_connections()`: Get all recorded connections
- `get_grid_topology()`: Get complete topology as dictionary
- `save_topology(filename)`: Save topology to JSON file
- `load_topology(filename)`: Load topology from JSON file

## Connection Rules

The connector uses predefined rules for different simulator types:

### Power Flow Connections
- **GeneratorSim** → **NodeSim**: P_MW_out, Q_MVAR_out → gen_sum_P_MW, gen_sum_Q_MVAR
- **PVSim** → **NodeSim**: P_MW_out, Q_MVAR_out → gen_sum_P_MW, gen_sum_Q_MVAR
- **BatterySim** → **NodeSim**: P_MW_out, Q_MVAR_out → gen_sum_P_MW, gen_sum_Q_MVAR

### Load Connections
- **LoadSim** → **NodeSim**: P_MW_actual, Q_MVAR_actual → load_sum_P_MW, load_sum_Q_MVAR

### Line Connections
- **LineSim** → **NodeSim**: P_MW_flow, Q_MVAR_flow → line_sum_P_out_MW, line_sum_Q_out_MVAR, line_sum_P_in_MW, line_sum_Q_in_MVAR

### Node Connections
- **NodeSim** → **LoadSim**: voltage_kV, voltage_pu, frequency_Hz → node_voltage_kV, voltage_pu, grid_frequency_Hz
- **NodeSim** → **GeneratorSim**: voltage_kV, voltage_pu, frequency_Hz → node_voltage_kV, voltage_pu, grid_frequency_Hz
- **NodeSim** → **BatterySim**: voltage_kV, voltage_pu, frequency_Hz → node_voltage_kV, voltage_pu, grid_frequency_Hz
- **NodeSim** → **PVSim**: voltage_kV, voltage_pu, frequency_Hz → node_voltage_kV, voltage_pu, grid_frequency_Hz

### Protection Connections
- **LineSim** → **ProtectionRelaySim**: current_kA, status → line_current_kA, line_status
- **NodeSim** → **ProtectionRelaySim**: voltage_pu, frequency_Hz → gen_voltage_pu, gen_frequency_Hz

### Monitoring Connections
- **NodeSim** → **MonitorSim**: voltage_pu, frequency_Hz, P_imbalance_MW → voltage_pu, frequency_Hz, P_imbalance_MW
- **LineSim** → **MonitorSim**: loading_percent, status, current_kA → loading_percent, status, current_kA
- **GeneratorSim** → **MonitorSim**: P_MW_out, status → P_MW_out, status
- **LoadSim** → **MonitorSim**: P_MW_actual → P_MW_actual

### Remediation Connections
- **MonitorSim** → **RemediationSim**: overall_status, system_frequency_avg_hz, active_alarms_list → monitor_overall_status, monitor_system_frequency, monitor_active_alarms

## Advanced Usage

### Custom Connection Rules

You can extend the connector with custom rules:

```python
# Add custom connection rules
connector.power_flow_rules['CustomSim'] = {
    'target_sims': ['NodeSim'],
    'source_attrs': ['custom_P', 'custom_Q'],
    'target_attrs': ['custom_sum_P', 'custom_sum_Q']
}
```

### Manual Connections

For special cases, you can create manual connections:

```python
# Create manual connection
manual_connection = GridConnection(
    source_sim='CustomSim',
    source_eid='Custom-1',
    source_attr='special_output',
    target_sim='NodeSim',
    target_eid='Node-1',
    target_attr='special_input'
)

connector._record_connection(manual_connection)

# Apply in Mosaik world
world.connect(source_entity, target_entity, ('special_output', 'special_input'))
```

### Topology Analysis

Analyze the grid structure:

```python
# Get topology
topology = connector.get_grid_topology()

# Print summary
connector.print_topology_summary()

# Get connections between specific simulators
gen_to_node_connections = connector.get_connections_between('GeneratorSim', 'NodeSim')

# Save/load topology
connector.save_topology('my_grid_topology.json')
connector.load_topology('my_grid_topology.json')
```

## Integration with Existing Code

### With BigSim Example

The connector can be integrated into existing simulation setups like `bigsim.py`:

```python
# In your simulation setup
connector = GridConnector()

# After creating simulators and entities
for sim_id, sim_instance in simulators.items():
    connector.register_simulator(sim_id, sim_instance)

for eid, entity in entities.items():
    sim_id = get_sim_id_from_eid(eid)  # Your logic to map entity to simulator
    connector.register_entity(sim_id, eid, entity_data)

# Connect all simulators
for source_sim, target_sim in connection_pairs:
    connector.connect(simulators[source_sim], simulators[target_sim], world)
```

## Error Handling

The connector provides comprehensive error handling:

- Returns `False` if connection fails
- Logs detailed error messages
- Continues with other connections if one fails
- Validates attribute compatibility before connecting

## Performance Considerations

- Connection rules are evaluated for each simulator pair
- Entity registration should happen after entity creation
- For large grids, consider batch operations
- Topology analysis is performed on demand

## File Structure

```
SAlly/simulation/mosaik_simulators/
├── connector.py                    # Main GridConnector class
├── connector_example.py            # Usage example with configuration manager
├── simulation_config_manager.py    # Centralized configuration management
├── simulation_config.yml           # YAML configuration file
├── README_Connector.md             # This documentation
├── base.py                         # Base simulator class
├── generator.py                    # Generator simulator
├── pv.py                           # PV simulator
├── load.py                         # Load simulator
├── line.py                         # Line simulator
├── node.py                         # Node simulator
├── battery.py                      # Battery simulator
├── monitor.py                      # Monitor simulator
├── protection_relay.py             # Protection relay simulator
└── remediation.py                  # Remediation controller simulator
```

## Dependencies

- mosaik_api_v3
- typing
- collections
- logging
- json (for topology persistence)
- yaml (for configuration management)
- pathlib (for file path handling)

## Testing

Run the example to test the connector:

```bash
cd SAlly/simulation/mosaik_simulators
python connector_example.py
```

This will create a sample grid, connect all simulators automatically, and display the resulting topology.

## Future Enhancements

Potential improvements for the GridConnector:

1. **Dynamic Rule Configuration**: Allow runtime modification of connection rules
2. **Connection Validation**: Validate connections against simulator metadata
3. **Visualization**: Generate visual representations of grid topology
4. **Optimization**: Suggest optimal connection patterns
5. **Multi-step Connections**: Handle complex connection patterns requiring intermediate steps
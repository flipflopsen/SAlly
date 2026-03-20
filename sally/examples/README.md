# SAlly Examples

This directory contains example scripts demonstrating various features and patterns in the SAlly framework.

## Available Examples

### 1. Observer Pattern (`example_observer_pattern.py`)
**Status**: ✅ **WORKING**

**Purpose**: Demonstrates the Observer pattern implementation with dependency injection for smart grid data monitoring.

**What It Shows**:
- Observer/Subject pattern implementation
- DataCollector that polls SmartGridDatabase and notifies observers
- DataEvaluator for analysis
- AppContainer for dependency injection wiring

**Dependencies**: `dependency_injector` package

**How to Run**:
```bash
python -m SAlly.examples.example_observer_pattern
```

**Key Classes**: Observer, Subject, SmartGridDatabase, DataCollector, DataEvaluator, GridObserver, AppContainer

---

### 2. Mosaik Integration (`example_mosaik_integration.py`)
**Status**: ⚠️ **REQUIRES MOSAIK**

**Purpose**: Large-scale Mosaik co-simulation with multiple grid components.

**What It Shows**:
- Complete Mosaik integration
- 9 different simulator types (Generator, PV, Load, Line, Node, Battery, Protection Relay, Monitor, Remediation)
- Entity creation and connection management
- Visualization with WebVis

**Dependencies**: `mosaik`, `mosaik-api` packages

**How to Run**:
```bash
pip install mosaik mosaik-api
python -m SAlly.examples.example_mosaik_integration
```

**Simulation Scenario**: Creates 4 generators, 3 PV systems, 6 loads, 8 transmission lines, 5 nodes, 2 batteries, 4 protection relays, 1 monitor, 1 remediation controller

---

### 3. SimulationBuilder Examples (`example_simulation_builder.py`)
**Status**: ✅ **WORKING** (after Phase 2 fixes)

**Purpose**: Demonstrates SimulationBuilder pattern with 7 different scenarios.

**What It Shows**:

#### Example 1: Basic HDF5 Simulation
- Basic HDF5 simulation with default services
- Uses `ContainerType.SIMULATION`
- Requires: `SAlly/simulation/simdata/demo.hdf5`

#### Example 2: Custom Database
- Simulation with custom TimescaleDBConnection
- Requires: Running TimescaleDB instance

#### Example 3: Custom Rule Manager
- Simulation with DummySmartGridRuleManager and rule configuration
- Demonstrates rule creation via GUI dict format

#### Example 4: Full Integration
- Full integration with EventBus, TimescaleDB, and all services
- Demonstrates complete service interactions
- Requires: TimescaleDB instance

#### Example 5: Random Data Provider
- Simulation using RandomDataProvider for generated data
- No HDF5 file required

#### Example 6: Sinusoidal Data Provider
- Simulation using SinusoidalDataProvider for periodic data
- Useful for testing with predictable patterns

#### Example 7: Mosaik Simulation
- Mosaik integration using SimulationBuilder
- Requires: `mosaik`, `mosaik-api` packages

**How to Run**:
```bash
# Run all examples (only example 7 is uncommented by default)
python -m SAlly.examples.example_simulation_builder

# Or modify main() to run specific examples
```

**Dependencies**:
- Core: `asyncio`, `h5py`, `pandas`, `numpy`
- Optional: `mosaik`, `mosaik-api` (for example 7)
- Database: PostgreSQL with TimescaleDB (for examples 2, 4)

---

## Quick Start

For first-time users, we recommend starting with:

1. **`example_observer_pattern.py`** - Simple, self-contained, no external dependencies
2. **`example_simulation_builder.py`** (examples 1, 5, 6) - Core simulation patterns without external services
3. **`example_mosaik_integration.py`** - Advanced co-simulation (requires mosaik installation)

## Common Issues

### Missing Dependencies
If you encounter import errors, install required packages:
```bash
pip install dependency-injector structlog asyncpg h5py pandas numpy
```

### TimescaleDB Connection
Examples requiring TimescaleDB will fail if the database is not running. Either:
- Install and start TimescaleDB locally
- Skip database-dependent examples
- Mock the database connection in the code

### HDF5 File Not Found
Some examples require `SAlly/simulation/simdata/demo.hdf5`. If missing:
- Use `SAlly.core.hdf5_builder.HDF5Builder` to create test data
- Or use data provider examples (5, 6) which don't require HDF5 files

## Contributing

When adding new examples:
1. Follow the naming convention: `example_<descriptive_name>.py`
2. Add comprehensive docstrings explaining purpose and usage
3. Update this README with example details and status
4. Include error handling and clear output messages
5. Document all dependencies and requirements

## Related Documentation

- `docs/SIMULATION_APPROACHES.md` - Detailed explanation of simulation modes
- `docs/EXAMPLES_STATUS.md` - Technical analysis of example implementations
- `docs/ARCHITECTURE_INVENTORY.md` - Complete module documentation
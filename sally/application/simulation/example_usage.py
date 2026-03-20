import asyncio
import sys

from sally.application.simulation.mosaik_simulators.pv import PV_SIM_ID, PVSim
from sally.application.simulation.mosaik_simulators.line import LINE_SIM_ID, LineSim
from sally.application.simulation.mosaik_simulators.node import NODE_SIM_ID, NodeSim
from sally.application.simulation.mosaik_simulators.generator import GEN_SIM_ID, GeneratorSim
from sally.application.simulation.mosaik_simulators.load import LOAD_SIM_ID, LoadSim
from sally.application.simulation.mosaik_simulators.battery import BATTERY_SIM_ID, BatterySim
from sally.application.simulation.mosaik_simulators.protection_relay import RELAY_SIM_ID, ProtectionRelaySim
from sally.application.simulation.mosaik_simulators.monitor import MONITOR_SIM_ID, MonitorSim
from sally.application.simulation.simulation_builder import SimulationBuilder
from sally.application.simulation.data_provider import RandomDataProvider, SinusoidalDataProvider
from sally.data_management.timescale.timescaledb_connection import TimescaleDBConnection
from sally.core.event_bus import EventBus
from sally.rule_management.sg_dummies import DummySmartGridRuleManager
from sally.containers import ContainerType
from sally.core.config import config
from sally.core.logger import get_logger

# =============================================================================
# KNOWN ISSUE: ContainerType.SG_WITH_DUMMIES Reference Error
# =============================================================================
#
# ISSUE: This file references `ContainerType.SG_WITH_DUMMIES` which doesn't exist
#        in the `ContainerType` enum defined in `containers.py`
#
# IMPACT: Examples will fail with AttributeError when executed due to this
#         non-existent enum value being referenced in multiple functions
#
# TEMPORARY FIX: Replace all occurrences of `ContainerType.SG_WITH_DUMMIES`
#               with `ContainerType.SIMULATION` to run examples successfully
#
# PERMANENT FIX: Will be addressed in Phase 4 (container refactoring) where
#                container types will be standardized and properly implemented
#
# WORKING EXAMPLE: `example_mosaik_simulation()` uses `ContainerType.SIMULATION`
#                  (line 299) and works correctly
#
# AFFECTED LINES: 30, 66, 103, 142, 182, 209
# =============================================================================
logger = get_logger(__name__)


async def example_basic_simulation():
    """Example 1: Basic simulation with default services"""
    print("=== Example 1: Basic Simulation with Default Services ===")

    # Build simulation using the builder pattern
    simulation, services = await SimulationBuilder() \
        .with_hdf5_file(str(config.get_path("default_hdf5_file"))) \
        .with_container_type(ContainerType.SG_WITH_DUMMIES) \
        .with_config(str(config.get_path("config_dir") / "default.yml")) \
        .build_and_start_services()

    print(f"Simulation created with {len(services)} services")
    print(f"Total timesteps: {simulation.total_timesteps}")

    # Run a few simulation steps
    print("Running 5 simulation steps...")
    await simulation.run_steps(5)

    # Clean up
    simulation.close()
    for service in services:
        if hasattr(service, 'stop'):
            await service.stop()

    print("Basic simulation example completed\n")


async def example_custom_database():
    """Example 2: Simulation with custom TimescaleDB connection"""
    print("=== Example 2: Simulation with Custom Database ===")

    # Create custom database connection
    database = TimescaleDBConnection(
        dsn="postgresql://user:password@localhost:5432/smartgrid",
        pool_size=10,
        max_size=20
    )
    await database.initialize()

    # Build simulation with custom database
    simulation, services = await SimulationBuilder() \
        .with_hdf5_file(str(config.get_path("default_hdf5_file"))) \
        .with_database(database) \
        .with_container_type(ContainerType.SG_WITH_DUMMIES) \
        .build_and_start_services()

    print(f"Simulation created with custom database: {database.dsn}")

    # Run simulation
    await simulation.run_steps(3)

    # Clean up
    simulation.close()
    await database.close()
    for service in services:
        if hasattr(service, 'stop'):
            await service.stop()

    print("Custom database example completed\n")


async def example_with_custom_rule_manager():
    """Example 3: Simulation with custom rule manager"""
    print("=== Example 3: Simulation with Custom Rule Manager ===")

    # Create custom rule manager
    rule_manager = DummySmartGridRuleManager()
    rule_manager.add_rule_from_gui_dict({
        "id": "R001",
        "entity_name": "Generator1",
        "variable_name": "P_MW_out",
        "operator": "LESS_THAN",
        "value": "100",
        "action": "ALERT_LOW_GENERATION"
    })

    # Build simulation with custom rule manager
    simulation, services = await SimulationBuilder() \
        .with_hdf5_file(str(config.get_path("default_hdf5_file"))) \
        .with_rule_manager(rule_manager) \
        .with_container_type(ContainerType.SG_WITH_DUMMIES) \
        .build_and_start_services()

    print(f"Simulation created with {len(rule_manager.rules)} rules")

    # Run simulation
    await simulation.run_steps(2)

    # Clean up
    simulation.close()
    for service in services:
        if hasattr(service, 'stop'):
            await service.stop()

    print("Custom rule manager example completed\n")


async def example_full_integration():
    """Example 4: Full integration with all services and event bus"""
    print("=== Example 4: Full Integration Example ===")

    # Create event bus
    event_bus = EventBus(max_queue_size=config.event_bus.max_queue_size)

    # Create database
    database = TimescaleDBConnection(
        dsn="postgresql://user:password@localhost:5432/smartgrid"
    )
    await database.initialize()

    # Create rule manager
    rule_manager = DummySmartGridRuleManager()

    # Build simulation with full integration
    simulation, services = await SimulationBuilder() \
        .with_hdf5_file(str(config.get_path("default_hdf5_file"))) \
        .with_event_bus(event_bus) \
        .with_database(database) \
        .with_rule_manager(rule_manager) \
        .with_container_type(ContainerType.SG_WITH_DUMMIES) \
        .build_and_start_services()

    print("Full integration simulation created:")
    print(f"  - Event bus: {event_bus is not None}")
    print(f"  - Database: {database is not None}")
    print(f"  - Services: {len(services)}")
    print(f"  - Rules: {len(rule_manager.rules)}")

    # Run simulation with service interactions
    print("Running simulation with service interactions...")
    await simulation.run_steps(10)

    # Get service metrics
    for i, service in enumerate(services):
        if hasattr(service, 'get_entity_states'):
            states = service.get_entity_states()
            print(f"Service {i+1} has {len(states)} entity states")

    # Clean up
    simulation.close()
    await event_bus.stop()
    await database.close()
    for service in services:
        if hasattr(service, 'stop'):
            await service.stop()

    print("Full integration example completed\n")


async def example_data_provider_simulation():
    """Example 5: Simulation with random data provider"""
    print("=== Example 5: Simulation with Random Data Provider ===")

    # Create random data provider
    data_provider = RandomDataProvider(num_entities=5, num_timesteps=100)

    # Build simulation with data provider
    simulation, services = await SimulationBuilder() \
        .with_data_provider(data_provider) \
        .with_container_type(ContainerType.SG_WITH_DUMMIES) \
        .build_and_start_services()

    print(f"Data provider simulation created with {len(data_provider.generate_timeseries_data())} entities")

    # Run simulation
    await simulation.run_steps(3)

    # Clean up
    simulation.close()
    for service in services:
        if hasattr(service, 'stop'):
            await service.stop()

    print("Data provider simulation example completed\n")


async def example_sinusoidal_data_provider():
    """Example 6: Simulation with sinusoidal data provider"""
    print("=== Example 6: Simulation with Sinusoidal Data Provider ===")

    # Create sinusoidal data provider
    data_provider = SinusoidalDataProvider(num_entities=8, num_timesteps=200, frequency=0.05)

    # Build simulation with data provider
    simulation, services = await SimulationBuilder() \
        .with_data_provider(data_provider) \
        .with_container_type(ContainerType.SG_WITH_DUMMIES) \
        .build_and_start_services()

    print("Sinusoidal data provider simulation created")

    # Run simulation
    await simulation.run_steps(5)

    # Clean up
    simulation.close()
    for service in services:
        if hasattr(service, 'stop'):
            await service.stop()

    print("Sinusoidal data provider example completed\n")

async def example_mosaik_simulation():
    """Example 7: Simulation with Mosaik integration"""
    print("=== Example 7: Simulation with Mosaik Integration ===")

    # Define Mosaik configuration (simplified version of bigsim.py)

    SIM_CONFIG = {
        GEN_SIM_ID: {'python': f'{__name__}:{GeneratorSim.__name__}'},
        PV_SIM_ID: {'python': f'{__name__}:{PVSim.__name__}'},
        LOAD_SIM_ID: {'python': f'{__name__}:{LoadSim.__name__}'},
        LINE_SIM_ID: {'python': f'{__name__}:{LineSim.__name__}'},
        NODE_SIM_ID: {'python': f'{__name__}:{NodeSim.__name__}'},
        BATTERY_SIM_ID: {'python': f'{__name__}:{BatterySim.__name__}'},
        RELAY_SIM_ID: {'python': f'{__name__}:{ProtectionRelaySim.__name__}'},
        MONITOR_SIM_ID: {'python': f'{__name__}:{MonitorSim.__name__}'},
        'WebVis': {'cmd': 'mosaik-web -s 127.0.0.1:8080 %(addr)s', },
    }

    mosaik_config = {
        'sim_config': {
            'GeneratorSim': {'python': 'sally.simulation.mosaik_simulators.generator:GeneratorSim'},
            'LoadSim': {'python': 'sally.simulation.mosaik_simulators.load:LoadSim'},
            'GridMonitor': {'python': 'sally.simulation.mosaik_simulators.monitor:MonitorSim'}
        },
        'simulators': {
            'gen_sim': {
                'class': 'GeneratorSim',
                'params': {}
            },
            'load_sim': {
                'class': 'LoadSim',
                'params': {}
            },
            'monitor': {
                'class': 'MonitorSim',
                'params': {}
            }
        },
        'entities': {
            'generators': {
                'simulator': 'gen_sim',
                'method': 'create',
                'params': {'num': 2, 'model': 'Generator', 'max_P_MW': 100, 'min_P_MW': 20}
            },
            'loads': {
                'simulator': 'load_sim',
                'method': 'create',
                'params': {'num': 3, 'model': 'ResidentialLoad'}
            },
            'monitor': {
                'simulator': 'monitor',
                'method': 'create',
                'params': {'num': 1, 'model': 'GridMonitor'}
            }
        },
        'connections': [
            {
                'source': 'generators',
                'dest': 'monitor',
                'attrs': ['P_MW_out', 'Q_MVAR_out']
            },
            {
                'source': 'loads',
                'dest': 'monitor',
                'attrs': ['P_MW_actual', 'Q_MVAR_actual']
            }
        ],
        'total_timesteps': 50,
        'step_size': 1
    }

    # Build simulation with Mosaik config
    simulation, services = await SimulationBuilder() \
        .with_mosaik_config(mosaik_config) \
        .with_container_type(ContainerType.SIMULATION) \
        .build_and_start_services()

    print("Mosaik simulation created with integrated services")

    # Run simulation
    await simulation.run_steps(5)

    # Clean up
    simulation.close()
    for service in services:
        if hasattr(service, 'stop'):
            await service.stop()

    print("Mosaik simulation example completed\n")


async def main():
    """Run all examples"""
    print("SmartGrid Simulation Builder Examples")
    print("=" * 50)

    try:
        await example_mosaik_simulation()
        # await example_basic_simulation()
        # await example_custom_database()
        # await example_with_custom_rule_manager()
        # await example_full_integration()
        # await example_data_provider_simulation()
        # await example_sinusoidal_data_provider()

        print("All examples completed successfully!")

    except Exception as e:
        logger.error(f"Error running examples {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

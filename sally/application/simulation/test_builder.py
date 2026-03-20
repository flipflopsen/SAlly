"""
Simple test for the SimulationBuilder to verify it works correctly.
"""

import asyncio
import sys
from sally.application.simulation.simulation_builder import SimulationBuilder
from sally.application.simulation.data_provider import RandomDataProvider, SinusoidalDataProvider
from sally.containers import ContainerType
from sally.core.config import config
from sally.core.logger import get_logger

logger = get_logger(__name__)


def test_builder_basic():
    """Test basic builder functionality"""
    print("Testing basic SimulationBuilder functionality...")

    try:
        # Test 1: Build simulation with minimal configuration
        simulation = SimulationBuilder() \
            .with_hdf5_file(str(config.get_path("default_hdf5_file"))) \
            .with_container_type(ContainerType.SG_WITH_DUMMIES) \
            .build()

        assert simulation is not None, "Simulation should not be None"
        assert simulation.total_timesteps > 0, "Simulation should have timesteps"
        assert simulation.rule_manager is not None, "Simulation should have rule manager"

        print("✓ Basic builder test passed")

        # Test 2: Check simulation properties
        assert hasattr(simulation, 'step'), "Simulation should have step method"
        assert hasattr(simulation, 'run_steps'), "Simulation should have run_steps method"
        assert hasattr(simulation, 'close'), "Simulation should have close method"

        print("✓ Simulation properties test passed")

        # Test 3: Run a single step
        result = simulation.step()
        assert result is True, "First step should succeed"

        print("✓ Single step test passed")

        # Clean up
        simulation.close()

        print("All basic tests passed!\n")

    except Exception as e:
        logger.error("Basic builder test failed")
        return False

    return True


def test_builder_with_services():
    """Test builder with services"""
    print("Testing SimulationBuilder with services...")

    try:
        # Build simulation with services
        simulation, services = SimulationBuilder() \
            .with_hdf5_file(str(config.get_path("default_hdf5_file"))) \
            .with_container_type(ContainerType.SG_WITH_DUMMIES) \
            .build_and_start_services()

        assert simulation is not None, "Simulation should not be None"
        assert len(services) > 0, "Should have services"
        assert simulation.event_bus is not None, "Should have event bus"

        print(f"✓ Services integration test passed ({len(services)} services)")

        # Clean up
        simulation.close()
        for service in services:
            if hasattr(service, 'stop'):
                service.stop()

        print("Services test passed!\n")

    except Exception as e:
        logger.error("Services builder test failed")
        return False

    return True


async def test_builder_validation():
    """Test builder validation"""
    print("Testing SimulationBuilder validation...")

    try:
        # Test missing HDF5 file
        try:
            SimulationBuilder().build()
            assert False, "Should raise ValueError for missing configuration"
        except ValueError:
            print("✓ Validation test passed (missing configuration)")

        # Test missing data provider
        try:
            SimulationBuilder().with_data_provider(None).build()
            assert False, "Should raise ValueError for missing data provider"
        except ValueError:
            print("✓ Validation test passed (missing data provider)")

        # Test missing Mosaik config
        try:
            SimulationBuilder().with_mosaik_config({}).build()
            assert False, "Should raise ValueError for missing Mosaik config"
        except ValueError:
            print("✓ Validation test passed (missing Mosaik config)")

    except Exception as e:
        logger.error("Validation test failed", error=str(e))
        return False

    return True


async def test_data_provider():
    """Test data provider functionality"""
    print("Testing data provider functionality...")

    try:
        # Test random data provider
        data_provider = RandomDataProvider(num_entities=3, num_timesteps=50)
        timeseries_data = data_provider.generate_timeseries_data()
        relational_data = data_provider.generate_relational_data()

        assert len(timeseries_data) > 0, "Should generate timeseries data"
        assert len(relational_data) > 0, "Should generate relational data"

        print(f"✓ Random data provider test passed ({len(timeseries_data)} entities)")

        # Test sinusoidal data provider
        sinusoidal_provider = SinusoidalDataProvider(num_entities=2, num_timesteps=30)
        sin_timeseries_data = sinusoidal_provider.generate_timeseries_data()
        sin_relational_data = sinusoidal_provider.generate_relational_data()

        assert len(sin_timeseries_data) > 0, "Should generate sinusoidal timeseries data"
        assert len(sin_relational_data) > 0, "Should generate sinusoidal relational data"

        print(f"✓ Sinusoidal data provider test passed ({len(sin_timeseries_data)} entities)")

    except Exception as e:
        logger.error("Data provider test failed", error=str(e))
        return False

    return True


async def test_data_provider_simulation():
    """Test simulation with data provider"""
    print("Testing simulation with data provider...")

    try:
        # Test with random data provider
        data_provider = RandomDataProvider(num_entities=2, num_timesteps=20)
        simulation = SimulationBuilder() \
            .with_data_provider(data_provider) \
            .with_container_type(ContainerType.SG_WITH_DUMMIES) \
            .build()

        assert simulation is not None, "Simulation should not be None"
        assert simulation.total_timesteps == 20, "Should have correct timesteps"

        print("✓ Data provider simulation test passed")

        # Clean up
        simulation.close()

    except Exception as e:
        logger.error("Data provider simulation test failed", error=str(e))
        return False

    return True


async def main():
    """Run all tests"""
    print("SimulationBuilder Test Suite")
    print("=" * 30)

    tests_passed = 0
    total_tests = 5

    if await test_builder_basic():
        tests_passed += 1

    if await test_builder_with_services():
        tests_passed += 1

    if await test_builder_validation():
        tests_passed += 1

    if await test_data_provider():
        tests_passed += 1

    if await test_data_provider_simulation():
        tests_passed += 1

    print(f"\nTest Results: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

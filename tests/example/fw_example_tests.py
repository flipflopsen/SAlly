import os
import unittest
import sys

import numpy as np
from dependency_injector import providers

from sally.core.hdf5_builder import HDF5Builder, HDF5Mode
from tests.framework.base_test import BaseSimulationTest
from tests.framework.test_builder import SimulationTestBuilder
from tests.framework.assertions import *
from tests.framework.dataclasses import *


class TestFrameworkCapabilities(BaseSimulationTest):
    """Comprehensive test suite demonstrating framework capabilities"""

    def setUp(self):
        super().setUp()
        # Setup dependency injection container for integration tests
        from sally.containers import ContainerFactory, ContainerType
        self.container = ContainerFactory().with_config("../config/sally.yml").create(ContainerType.SG_WITH_DUMMIES)
        self.original_providers = {
            'rule_manager': self.container.rule_manager,
            'database': self.container.database,
            'data_collector': self.container.data_collector
        }

    def setup_container_with_mocks(self, mocks):
        """Setup container with mock overrides for dependency injection"""
        if 'rule_manager' in mocks:
            self.container.rule_manager.override(
                providers.Singleton(lambda: mocks['rule_manager'])
            )
        if 'database' in mocks:
            self.container.database.override(
                providers.Singleton(lambda: mocks['database'])
            )
        if 'data_collector' in mocks:
            self.container.data_collector.override(
                providers.Singleton(lambda: mocks['data_collector'])
            )
        self.container.wire(modules=[sys.modules[__name__]])

    def test_manual_hdf5_with_complex_scenario(self):
        """Test 1: Manual HDF5 creation with complex multi-entity scenario"""

        def setup_complex_simulation(builder: SimulationTestBuilder):
            hdf5_builder = builder.with_manual_hdf5()

            # Create a smart grid scenario with generators, loads, and storage
            hdf5_builder.add_mosaik_style_entity("PyPower", "0.0-gen_1", {
                "P": [100.0, 120.0, 150.0, 180.0, 200.0],
                "Q": [50.0, 60.0, 75.0, 90.0, 100.0],
                "V": [1.05, 1.04, 1.03, 1.02, 1.01]
            }).add_mosaik_style_entity("PyPower", "0.0-load_1", {
                "P": [80.0, 85.0, 90.0, 95.0, 100.0],
                "Q": [40.0, 42.0, 45.0, 47.0, 50.0]
            }).add_mosaik_style_entity("Battery", "0.storage_1", {
                "P": [-10.0, -5.0, 0.0, 5.0, 10.0],  # Negative = charging
                "SOC": [0.8, 0.75, 0.7, 0.65, 0.6]  # State of charge
            }).add_relation("grid_topology", [
                [1, 1, 0],  # Generator connected to load and storage
                [1, 0, 1],  # Load connected to generator and storage
                [0, 1, 1]  # Storage connected to load and generator
            ])

            # Add multiple rules for different scenarios
            builder.with_rule({
                "id": "GEN_OVERLOAD",
                "entity_name": "PyPower-0.0-gen_1",
                "variable_name": "P",
                "operator": "LESS_THAN",
                "value": "175",
                "action": "INCREASE_GENERATION"
            }).with_rule({
                "id": "VOLTAGE_LOW",
                "entity_name": "PyPower-0.0-gen_1",
                "variable_name": "V",
                "operator": "LESS_THAN",
                "value": "1.03",
                "action": "VOLTAGE_REGULATION"
            }).with_rule({
                "id": "BATTERY_LOW",
                "entity_name": "Battery-0.storage_1",
                "variable_name": "SOC",
                "operator": "LESS_THAN",
                "value": "0.7",
                "action": "BATTERY_CHARGE"
            })

        # Configure comprehensive assertions
        self.add_assertion(StepCountAssertion(5))
        self.add_assertion(RuleTriggeredAssertion("GEN_OVERLOAD", 3))
        self.add_assertion(RuleTriggeredAssertion("VOLTAGE_LOW", 2))
        self.add_assertion(RuleTriggeredAssertion("BATTERY_LOW", 2))
        self.add_assertion(DataValueAssertion(0, "PyPower-0.0-gen_1", "P", 100.0))
        self.add_assertion(DataValueAssertion(4, "Battery-0.storage_1", "SOC", 0.6))

        self.run_simulation_test("complex_manual_hdf5", setup_complex_simulation)

    def test_hybrid_hdf5_modification(self):
        """Test 2: Hybrid HDF5 mode - modifying existing simulation data"""
        base_path = "../test_data/mosaik_demo.hdf5"
        # First create a base HDF5 file
        base_builder = HDF5Builder(HDF5Mode.HYBRID_HDF5, base_path)
        base_builder.add_entity("OriginalGenerator", {
            "P": [200.0, 220.0, 240.0],
            "Q": [100.0, 110.0, 120.0]
        })

        def setup_hybrid_simulation(builder: SimulationTestBuilder):
            builder.with_given_builder(base_builder)
            # Modify existing data and add new entities
            base_builder.modify_entity_data("OriginalGenerator", "P", [250.0, 275.0, 300.0])
            base_builder.add_entity("NewRenewableSource", {
                "P": [50.0, 60.0, 70.0],
                "Q": [25.0, 30.0, 35.0]
            })
            # .add_relation("NewRenewableSource-0.OriginalGenerator_0", [
            #    ["/Relations/NewRenewableSource", "/Relations/OriginalGenerator"],
            #    ["/Series/NewRenewableSource", "/Series/OriginalGenerator" ]
            #]))

            builder.with_maximum_steps(4)
            builder.with_rule({
                "id": "RENEWABLE_CHECK",
                "entity_name": "NewRenewableSource",
                "variable_name": "P",
                "operator": "LESS_THAN",
                "value": "65",
                "action": "FORECAST_UPDATE"
            })

        self.add_assertion(StepCountAssertion(4))
        self.add_assertion(RuleTriggeredAssertion("RENEWABLE_CHECK", 2))  # Steps 0, 1
        self.add_assertion(DataValueAssertion(0, "OriginalGenerator", "P", 250.0))  # Modified value

        self.run_simulation_test("hybrid_modification", setup_hybrid_simulation)


    def test_dependency_injection_integration(self):
        """Test 3: Full dependency injection integration with real container"""

        def setup_di_simulation(builder: SimulationTestBuilder):
            builder.with_real_hdf5("../test_data/mosaik_demo.hdf5")
            builder.with_maximum_steps(4)
            builder.with_rule({
                "id": "R001",
                "entity_name": "PyPower-0.0-node_a1",
                "variable_name": "P",
                "operator": "LESS_THAN",
                "value": "260",
                "action": "ALERT_HIGH_POWER_G1"
            })

        self.add_assertion(StepCountAssertion(4))
        self.add_assertion(RuleTriggeredAssertion("R001", 4))

        self.run_simulation_test("dependency_injection", setup_di_simulation)

        # Verify that dependency injection worked correctly
        injected_rule_manager = self.container.rule_manager()
        injected_rule_manager.add_rule_from_gui_dict.assert_called()

    def test_custom_assertion_validation(self):
        """Test 4: Custom assertion creation and validation"""

        class PowerBalanceAssertion(SimulationAssertion):
            """Custom assertion to check power balance in the grid"""

            def __init__(self, tolerance: float = 5.0):
                self.tolerance = tolerance

            def assert_condition(self, trace: SimulationTrace) -> bool:
                for step in trace.steps:
                    total_generation = 0
                    total_consumption = 0

                    for entity_name, entity_data in step.output_data.items():
                        if "gen" in entity_name.lower():
                            total_generation += entity_data.get("P", 0)
                        elif "load" in entity_name.lower():
                            total_consumption += entity_data.get("P", 0)

                    if abs(total_generation - total_consumption) > self.tolerance:
                        return False
                return True

            def get_error_message(self, trace: SimulationTrace) -> str:
                return f"Power balance exceeded tolerance of {self.tolerance} MW"

        class VoltageStabilityAssertion(SimulationAssertion):
            """Custom assertion to check voltage stability"""

            def __init__(self, min_voltage: float = 0.95, max_voltage: float = 1.05):
                self.min_voltage = min_voltage
                self.max_voltage = max_voltage

            def assert_condition(self, trace: SimulationTrace) -> bool:
                for step in trace.steps:
                    for entity_name, entity_data in step.output_data.items():
                        voltage = entity_data.get("V")
                        if voltage and (voltage < self.min_voltage or voltage > self.max_voltage):
                            return False
                return True

            def get_error_message(self, trace: SimulationTrace) -> str:
                return f"Voltage outside acceptable range [{self.min_voltage}, {self.max_voltage}]"

        def setup_power_balance_simulation(builder: SimulationTestBuilder):
            hdf5_builder = builder.with_manual_hdf5()
            hdf5_builder.add_entity("Generator_1", {
                "P": [100.0, 110.0, 120.0],
                "V": [1.02, 1.01, 1.00]
            }).add_entity("Generator_2", {
                "P": [80.0, 85.0, 90.0],
                "V": [1.03, 1.02, 1.01]
            }).add_entity("Load_1", {
                "P": [90.0, 95.0, 100.0]
            }).add_entity("Load_2", {
                "P": [85.0, 95.0, 105.0]
            })

        # Add custom assertions
        self.add_assertion(PowerBalanceAssertion(tolerance=10.0))
        self.add_assertion(VoltageStabilityAssertion(min_voltage=0.98, max_voltage=1.05))
        self.add_assertion(StepCountAssertion(3))

        self.run_simulation_test("custom_assertions", setup_power_balance_simulation)

    def test_error_handling_and_edge_cases(self):
        """Test 5: Error handling and edge cases"""

        def setup_edge_case_simulation(builder: SimulationTestBuilder):
            hdf5_builder = builder.with_manual_hdf5()

            # Create scenario with edge cases
            hdf5_builder.add_entity("EdgeCase_Entity", {
                "P": [0.0, -10.0, 1000.0, float('inf')],  # Edge values
                "status": [1, 0, 1, 0]  # Binary status
            })

            builder.with_rule({
                "id": "ZERO_POWER",
                "entity_name": "EdgeCase_Entity",
                "variable_name": "P",
                "operator": "LESS_THAN",
                "value": "1",
                "action": "POWER_ALERT"
            })

        class EdgeCaseAssertion(SimulationAssertion):
            """Custom assertion for handling edge cases"""

            def assert_condition(self, trace: SimulationTrace) -> bool:
                # Check that simulation handled edge cases gracefully
                return trace.success and len(trace.steps) > 0

            def get_error_message(self, trace: SimulationTrace) -> str:
                return f"Simulation failed to handle edge cases: {trace.error_message}"

        self.add_assertion(EdgeCaseAssertion())
        self.add_assertion(RuleTriggeredAssertion("ZERO_POWER", 2))  # Steps with P < 1

        self.run_simulation_test("edge_cases", setup_edge_case_simulation)

    def test_performance_and_scalability(self):
        """Test 6: Performance test with large dataset"""

        def setup_large_simulation(builder: SimulationTestBuilder):
            hdf5_builder = builder.with_manual_hdf5()

            num_entities = 10
            num_timesteps = 100

            for i in range(num_entities):
                base_power = 100 + i * 20
                power_profile = [base_power + np.sin(t * 0.1) * 20 for t in range(num_timesteps)]

                hdf5_builder.add_entity(f"Generator_{i}", {
                    "P": power_profile,
                    "Q": [p * 0.3 for p in power_profile]  # Q = 30% of P
                })

            for i in range(0, num_entities, 3):  # Every third generator
                builder.with_rule({
                    "id": f"PERF_RULE_{i}",
                    "entity_name": f"Generator_{i}",
                    "variable_name": "P",
                    "operator": "LESS_THAN",
                    "value": str(110 + i * 20),
                    "action": f"ACTION_{i}"
                })

        class PerformanceAssertion(SimulationAssertion):
            def assert_condition(self, trace: SimulationTrace) -> bool:
                return len(trace.steps) == 100 and trace.success

            def get_error_message(self, trace: SimulationTrace) -> str:
                return f"Performance test failed: {len(trace.steps)} steps completed, success: {trace.success}"

        import time
        start_time = time.time()

        self.add_assertion(PerformanceAssertion())
        self.add_assertion(StepCountAssertion(100))

        self.run_simulation_test("performance_test", setup_large_simulation)

        end_time = time.time()
        execution_time = end_time - start_time

        # Performance assertion - should complete within reasonable time
        self.assertLess(execution_time, 10.0, f"Performance test took too long: {execution_time:.2f}s")

    def test_real_hdf5_file_integration(self):
        """Test 7: Integration with real HDF5 file (if available)"""

        # This test would use a real HDF5 file if available
        real_hdf5_path = "../test_data/mosaik_demo.hdf5"

        if not os.path.exists(real_hdf5_path):
            self.skipTest(f"Real HDF5 file not available at {real_hdf5_path}")

        def setup_real_file_simulation(builder: SimulationTestBuilder):
            builder.with_real_hdf5(real_hdf5_path)
            builder.with_maximum_steps(3)
            # Add rules that work with the real data structure
            builder.with_rule({
                "id": "REAL_DATA_RULE",
                "entity_name": "RealEntity",  # Would need to match actual entity names
                "variable_name": "P",
                "operator": "LESS_THAN",
                "value": "500",
                "action": "REAL_ACTION"
            })

        # This test demonstrates how to work with real files
        # Assertions would depend on the actual file content
        self.run_simulation_test("real_hdf5_integration", setup_real_file_simulation)


if __name__ == '__main__':
    # Run specific test methods to demonstrate capabilities
    suite = unittest.TestSuite()

    # Add specific tests to showcase different capabilities
    suite.addTest(TestFrameworkCapabilities('test_manual_hdf5_with_complex_scenario'))
    suite.addTest(TestFrameworkCapabilities('test_hybrid_hdf5_modification'))
    suite.addTest(TestFrameworkCapabilities('test_dependency_injection_integration'))
    suite.addTest(TestFrameworkCapabilities('test_custom_assertion_validation'))
    suite.addTest(TestFrameworkCapabilities('test_error_handling_and_edge_cases'))
    suite.addTest(TestFrameworkCapabilities('test_performance_and_scalability'))

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

import unittest
from pathlib import Path

from tests.framework.base_test import BaseSimulationTest
from tests.framework.test_builder import SimulationTestBuilder
from tests.framework.assertions import *


_TEST_HDF5 = str(Path(__file__).resolve().parent / "test_data" / "mosaik_demo.hdf5")


class TestHDF5Modes(BaseSimulationTest):
    """Test different HDF5 modes"""

    def test_real_hdf5_mode(self):
        def setup_simulation(builder: SimulationTestBuilder):
            (builder.with_real_hdf5(_TEST_HDF5)
                    .with_rule({
                        "id": "R001",
                        "entity_name": "Generator1",
                        "variable_name": "P",
                        "operator": "LESS_THAN",
                        "value": "100",
                        "action": "ALERT"})
                    .with_maximum_steps(5)
            )

        self.run_simulation_test("real_hdf5", setup_simulation)

    def test_manual_hdf5_mode(self):
        """Test creating HDF5 file from scratch"""

        def setup_simulation(builder: SimulationTestBuilder):
            hdf5_builder = builder.with_manual_hdf5()
            hdf5_builder.add_entity("Generator1", {
                "P": [100.0, 150.0, 200.0],
                "Q": [50.0, 75.0, 100.0]
            }).add_entity("Load1", {
                "P": [80.0, 90.0, 85.0],
                "Q": [40.0, 45.0, 42.0]
            }).add_relation("connection_matrix", [
                [1, 0, 1],
                [0, 1, 0],
                [1, 0, 1]
            ])

            builder.with_rule({
                "id": "R002",
                "entity_name": "Generator1",
                "variable_name": "P",
                "operator": "LESS_THAN",
                "value": "175",
                "action": "INCREASE_GEN"
            }).with_maximum_steps(3)

        self.add_assertion(StepCountAssertion(3))
        self.run_simulation_test("manual_hdf5", setup_simulation)

    def test_hybrid_hdf5_mode(self):
        """Test modifying existing HDF5 file"""

        def setup_simulation(builder: SimulationTestBuilder):
            hdf5_builder = builder.with_hybrid_hdf5(_TEST_HDF5)
            hdf5_builder.add_entity("NewGenerator", {
                "P": [300.0, 350.0, 400.0]
            }).modify_entity_data("ExistingGenerator", "P", [250.0, 275.0, 300.0])

            builder.with_rule({
                "id": "R003",
                "entity_name": "NewGenerator",
                "variable_name": "P",
                "operator": "LESS_THAN",
                "value": "375",
                "action": "ALERT_NEW_GEN"
            }).with_maximum_steps(3)

        self.run_simulation_test("hybrid_hdf5", setup_simulation)

    def test_mosaik_style_entities(self):
        """Test mosaik-style entity naming"""

        def setup_simulation(builder: SimulationTestBuilder):
            hdf5_builder = builder.with_manual_hdf5()
            hdf5_builder.add_mosaik_style_entity("PyPower", "0.0-node_a1", {
                "P": [250.0, 270.0, 240.0],
                "Q": [100.0, 105.0, 95.0]
            }).add_mosaik_style_entity("CSV", "0.PV_0", {
                "P": [50.0, 60.0, 55.0]
            })

            builder.with_rule({
                "id": "R004",
                "entity_name": "PyPower-0.0-node_a1",
                "variable_name": "P",
                "operator": "LESS_THAN",
                "value": "260",
                "action": "POWER_ALERT"
            }).with_maximum_steps(3)

        self.add_assertion(DataValueAssertion(0, "PyPower-0.0-node_a1", "P", 250.0))
        self.run_simulation_test("mosaik_style", setup_simulation)


if __name__ == '__main__':
    unittest.main()

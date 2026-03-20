from typing import Optional, Dict, Any

from sally.core.hdf5_builder import HDF5Builder, HDF5Mode


class SimulationTestBuilder:
    """Simulation test builder with HDF5Builder integration"""

    def __init__(self):
        self.mock_data_steps = []
        self.mock_rules = []
        self.hdf5_builder = None
        self.expected_total_timesteps = 0
        self.total_timesteps = 0
        self.maximum_timesteps = 0

    def with_hdf5_file(self, mode: HDF5Mode, path: Optional[str] = None) -> HDF5Builder:
        """Initialize HDF5Builder and return it for chaining"""
        self.hdf5_builder = HDF5Builder(mode, path)
        return self.hdf5_builder

    def with_real_hdf5(self, path: str) -> 'SimulationTestBuilder':
        """Use an existing real HDF5 file"""
        self.hdf5_builder = HDF5Builder(HDF5Mode.REAL_HDF5, path)
        return self

    def with_manual_hdf5(self) -> HDF5Builder:
        """Create a manual HDF5 file from scratch"""
        self.hdf5_builder = HDF5Builder(HDF5Mode.MANUAL_HDF5)
        return self.hdf5_builder

    def with_hybrid_hdf5(self, base_path: str) -> HDF5Builder:
        """Modify an existing HDF5 file"""
        self.hdf5_builder = HDF5Builder(HDF5Mode.HYBRID_HDF5, base_path)
        return self.hdf5_builder

    def with_random_hdf5(self) -> HDF5Builder:
        """Generate a random HDF5 file"""
        self.hdf5_builder = HDF5Builder(HDF5Mode.RANDOM_HDF5)
        return self.hdf5_builder

    def with_rule(self, rule_dict: Dict[str, Any]) -> 'SimulationTestBuilder':
        """Add a mock rule to the simulation"""
        self.mock_rules.append(rule_dict)
        return self

    def with_maximum_steps(self, maximum_steps: int) -> 'SimulationTestBuilder':
        self.maximum_timesteps = maximum_steps
        return self

    def with_given_builder(self, hdf5_builder: HDF5Builder) -> 'SimulationTestBuilder':
        self.hdf5_builder = hdf5_builder
        return self

    def build_hdf5_file(self) -> str:
        """Build the HDF5 file and return the path"""
        if not self.hdf5_builder:
            raise ValueError("No HDF5 builder configured. Use with_hdf5_file() first.")

        return self.hdf5_builder.build()

    def cleanup(self):
        """Cleanup resources"""
        if self.hdf5_builder:
            self.hdf5_builder.cleanup()

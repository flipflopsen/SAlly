"""
Tests for sally.core.mosaik_hdf5_parser — HDF5Parser structure discovery.

Covers: discover_structure_from_file, get_data_snapshot, error handling.
"""

from __future__ import annotations

import pytest

from tests.diag.metrics import record_metric

h5py = pytest.importorskip("h5py")


@pytest.fixture
def sample_hdf5(tmp_path):
    """Create a small HDF5 file with known structure."""
    path = tmp_path / "test_grid.hdf5"
    with h5py.File(str(path), "w") as f:
        # Entity1 with two variables
        f.create_dataset("Entity1/P_MW", data=[10.0, 20.0, 30.0])
        f.create_dataset("Entity1/Q_MVAR", data=[1.0, 2.0, 3.0])
        # Entity2 with one variable
        f.create_dataset("Entity2/VM", data=[0.98, 1.01, 1.02])
        # Nested deeper
        f.create_dataset("Group/Entity3/VA", data=[0.01, 0.02, 0.03])
    return str(path)


class TestHDF5Parser:
    def test_discover_structure(self, sample_hdf5):
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        parser = HDF5Parser(sample_hdf5)
        structure = parser.discover_structure_from_file()
        assert "Entity1" in structure
        assert sorted(structure["Entity1"]) == ["P_MW", "Q_MVAR"]
        assert "Entity2" in structure
        assert structure["Entity2"] == ["VM"]
        record_metric("hdf5_parser_entities", len(structure), "count")

    def test_discover_with_filepath_argument(self, sample_hdf5):
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        parser = HDF5Parser()
        structure = parser.discover_structure_from_file(filepath=sample_hdf5)
        assert len(structure) >= 2
        record_metric("hdf5_parser_filepath_arg", 1, "bool")

    def test_discover_no_filepath(self):
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        parser = HDF5Parser()
        result = parser.discover_structure_from_file()
        assert result == {}
        record_metric("hdf5_parser_no_filepath", 1, "bool")

    def test_discover_missing_file(self, tmp_path):
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        parser = HDF5Parser(str(tmp_path / "nonexistent.hdf5"))
        result = parser.discover_structure_from_file()
        assert result == {}
        record_metric("hdf5_parser_missing_file", 1, "bool")

    def test_get_data_snapshot(self, sample_hdf5):
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        parser = HDF5Parser(sample_hdf5)
        val = parser.get_data_snapshot("Entity1", "P_MW", 0)
        assert val == pytest.approx(10.0)
        val2 = parser.get_data_snapshot("Entity1", "P_MW", 2)
        assert val2 == pytest.approx(30.0)
        record_metric("hdf5_parser_snapshot", 2, "reads")

    def test_get_data_snapshot_out_of_range(self, sample_hdf5):
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        parser = HDF5Parser(sample_hdf5)
        val = parser.get_data_snapshot("Entity1", "P_MW", 999)
        assert val is None
        record_metric("hdf5_parser_snapshot_oor", 1, "bool")

    def test_get_data_snapshot_no_filepath(self):
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        parser = HDF5Parser()
        assert parser.get_data_snapshot("Entity1", "P_MW", 0) is None
        record_metric("hdf5_parser_snapshot_nofp", 1, "bool")

    def test_get_data_snapshot_nonexistent_entity(self, sample_hdf5):
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        parser = HDF5Parser(sample_hdf5)
        val = parser.get_data_snapshot("NoSuchEntity", "P_MW", 0)
        assert val is None
        record_metric("hdf5_parser_snapshot_noent", 1, "bool")

    def test_variables_sorted(self, sample_hdf5):
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        parser = HDF5Parser(sample_hdf5)
        structure = parser.discover_structure_from_file()
        for entity, vars_list in structure.items():
            assert vars_list == sorted(vars_list), f"Variables for {entity} not sorted"
        record_metric("hdf5_parser_sorted", 1, "bool")

    def test_clear_between_discoveries(self, sample_hdf5, tmp_path):
        """Parser state should be clear between discoveries."""
        from sally.core.mosaik_hdf5_parser import HDF5Parser

        # Create a second different HDF5
        path2 = tmp_path / "other.hdf5"
        with h5py.File(str(path2), "w") as f:
            f.create_dataset("OtherEntity/X", data=[1.0])

        parser = HDF5Parser(sample_hdf5)
        s1 = parser.discover_structure_from_file()
        assert "Entity1" in s1

        s2 = parser.discover_structure_from_file(filepath=str(path2))
        assert "OtherEntity" in s2
        assert "Entity1" not in s2  # old state cleared
        record_metric("hdf5_parser_clear", 1, "bool")

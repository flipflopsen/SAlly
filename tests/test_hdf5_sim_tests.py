"""Collect the simulation HDF5 mode tests.

The original test module is `tests/hdf5_sim_tests.py`, which doesn't match the
pytest discovery pattern (it doesn't start with `test_`).

This wrapper makes those tests discoverable while keeping the original file
intact.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hdf5]

# Re-export unittest.TestCase class so pytest will collect it from this module.
from tests.hdf5_sim_tests import TestHDF5Modes  # noqa: F401,E402

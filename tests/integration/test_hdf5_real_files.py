"""Integration tests that load real HDF5 files shipped with the repo.

These tests are intentionally data-driven to generate lots of evaluation data
and diagrams. They focus on:
- the mosaik demo HDF5
- MIDAS-produced HDF5 files (including BHV datasets, if present)

They do not modify production code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List
from unittest.mock import MagicMock

import pytest

from tests.diag.metrics import record_metric

from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation

pytestmark = [pytest.mark.integration, pytest.mark.hdf5]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_hdf5_files() -> Iterable[Path]:
    root = _repo_root()

    candidates: List[Path] = []

    # Repo data sets
    candidates += sorted((root / "data" / "hdf5").glob("*.hdf5"))
    candidates += sorted((root / "data" / "hdf5").glob("*.h5"))

    # MIDAS-related datasets
    candidates += sorted((root / "data" / "midas" / "hdf5").glob("*.hdf5"))
    candidates += sorted((root / "data" / "midas" / "hdf5").glob("*.h5"))

    # Test fixtures
    candidates += sorted((root / "tests" / "test_data").glob("*.hdf5"))
    candidates += sorted((root / "tests" / "test_data").glob("*.h5"))

    # De-dup while preserving order
    seen = set()
    for p in candidates:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        if rp.is_file():
            yield rp


def _params():
    params = []
    for p in _iter_hdf5_files():
        marks = []

        lower = p.name.lower()
        if "midas" in str(p).lower() or "data\\midas" in str(p).lower().replace("/", "\\"):
            marks.append(pytest.mark.midas)
        if "bhv" in lower:
            marks.append(pytest.mark.bhv)

        params.append(pytest.param(p, marks=marks, id=str(p.relative_to(_repo_root()))))

    if not params:
        params = [pytest.param(None, id="no_hdf5_files")]

    return params


@pytest.mark.parametrize("hdf5_path", _params())
def test_can_load_and_step_real_hdf5(hdf5_path: Path | None):
    if hdf5_path is None:
        pytest.skip("No HDF5 files found in expected locations")

    rule_manager = MagicMock()
    rule_manager.evaluate_rules.return_value = []

    sim = SmartGridSimulation(
        str(hdf5_path),
        rule_manager,
        event_bus=None,
        publish_scada_events=False,
    )

    try:
        record_metric("hdf5_total_timesteps", float(sim.total_timesteps or 0), "count")
        record_metric("hdf5_entities", float(len(sim.entity_variable_timeseries_data or {})), "count")
        record_metric("hdf5_relations", float(len(sim.relation_data or {})), "count")

        assert sim.total_timesteps >= 0
        assert isinstance(sim.entity_variable_timeseries_data, dict)
        assert isinstance(sim.relation_data, dict)

        # Step a few iterations if there is data.
        steps = min(3, int(sim.total_timesteps or 0))
        for _ in range(steps):
            ok = sim.step()
            assert ok is True

        record_metric("hdf5_steps_executed", float(steps), "count")

        if sim.total_timesteps > 0:
            assert sim.current_timestep == steps
    finally:
        sim.close()

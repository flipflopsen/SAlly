"""
High-level facade for MIDAS scenario ingestion into SAlly.

Delegates to the real MIDAS ``Configurator`` / ``midas.run()`` API for
building and running mosaik co‑simulations, while using SAlly's own
parser and mapper for inspection and GUI display.

Usage::

    from sally.application.simulation.midas import MidasSimulationAdapter

    adapter = MidasSimulationAdapter()

    # Inspect / preview for the GUI
    scenario = adapter.parse("four_bus.yml")
    sally_def = adapter.map(scenario)

    # Actually run via MIDAS
    adapter.run_scenario("four_bus", config="path/to/four_bus.yml")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sally.infrastructure.midas.midas_mapper import (
    MidasToSallyMapper,
    SallyScenarioDef,
)
from sally.infrastructure.midas.midas_parser import MidasScenarioParser, MidasScenario

logger = logging.getLogger(__name__)


class MidasSimulationAdapter:
    """
    Orchestrate MIDAS scenario ingestion into the SAlly simulation pipeline.

    This class serves as the single entry point for the GUI and the
    application layer.  It:

    1. Parses a MIDAS ``.yml`` file via :class:`MidasScenarioParser`.
    2. Maps the parsed result to SAlly display types via
       :class:`MidasToSallyMapper` (for GUI preview).
    3. Delegates actual scenario execution to ``midas.run()`` or the
       ``midas.scenario.configurator.Configurator``.
    """

    def __init__(
        self,
        parser: Optional[MidasScenarioParser] = None,
        mapper: Optional[MidasToSallyMapper] = None,
    ) -> None:
        self._parser = parser or MidasScenarioParser()
        self._mapper = mapper or MidasToSallyMapper()

    # ── Public API — inspection ──────────────────────────────────────────

    def parse(self, path: Path | str) -> MidasScenario:
        """Parse only — useful for inspection / validation in the GUI."""
        return self._parser.parse_file(path)

    def parse_all(self, path: Path | str) -> List[MidasScenario]:
        """Parse all scenario blocks from a YAML file."""
        return self._parser.parse_all(path)

    def map(self, scenario: MidasScenario) -> SallyScenarioDef:
        """Map only — useful for previewing the translation."""
        return self._mapper.map(scenario)

    # ── Public API — execution ───────────────────────────────────────────

    def run_scenario(
        self,
        scenario_name: str,
        *,
        config: Optional[str | Path] = None,
        params: Optional[Dict[str, Any]] = None,
        no_run: bool = False,
    ) -> Any:
        """
        Run a MIDAS scenario using the native MIDAS API.

        Parameters
        ----------
        scenario_name:
            Top‑level key in the YAML (e.g. ``"four_bus"``, ``"midasmv"``).
        config:
            Path to a custom YAML file.  If ``None``, MIDAS searches its
            built‑in ``default_scenarios`` directory.
        params:
            Extra scenario params passed to ``midas.run()``.
        no_run:
            If ``True``, configure and build but don't start the simulation.
            Useful for testing.

        Returns
        -------
        midas.scenario.scenario.Scenario
            The MIDAS Scenario object (contains ``world``, ``base``, etc.).
        """
        import midas

        run_params = dict(params or {})

        config_arg = str(config) if config else None

        logger.info(
            "Running MIDAS scenario '%s' via midas.run() (config=%s)",
            scenario_name,
            config_arg,
        )

        scenario = midas.run(
            scenario_name=scenario_name,
            params=run_params,
            config=config_arg,
            no_run=no_run,
            skip_download=True,
        )

        logger.info("MIDAS scenario '%s' completed successfully", scenario_name)
        return scenario

    def configure_scenario(
        self,
        scenario_name: str,
        *,
        config: Optional[str | Path] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Configure (but don't build/run) a MIDAS scenario.

        Returns the MIDAS ``Configurator`` for further control.
        """
        from midas.scenario.configurator import Configurator

        cfg = Configurator()
        config_arg = (str(config),) if config else None

        scenario = cfg.configure(
            scenario_name,
            params or {},
            config_arg,
        )

        if not scenario.success:
            raise RuntimeError(
                f"MIDAS configuration failed for '{scenario_name}'"
            )

        return cfg

    # ── Public API — listing ─────────────────────────────────────────────

    def list_available_scenarios(
        self, search_dir: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """
        Discover MIDAS YAML files and return metadata for each scenario block.

        Returns a list of dicts with ``name``, ``path``, ``duration``,
        ``simulator_count``, etc. — suitable for rendering in the GUI.
        """
        if search_dir is None:
            try:
                import midas.scenario.default_scenarios as _mod
                search_dir = Path(_mod.__path__[0])
            except (ImportError, IndexError):
                from sally.core.config import config
                search_dir = config.get_path("midas_dir")

        results: List[Dict[str, Any]] = []
        for yml_file in sorted(search_dir.glob("*.yml")):
            try:
                scenarios = self._parser.parse_all(yml_file)
                for scenario in scenarios:
                    results.append(
                        {
                            "name": scenario.name,
                            "path": str(yml_file),
                            "duration": scenario.duration,
                            "step_size": scenario.step_size,
                            "module_count": len(scenario.modules),
                            "modules": scenario.modules,
                            "entity_count": len(scenario.entities),
                            "start_date": scenario.start_date,
                            "parent": scenario.parent,
                        }
                    )
            except Exception as exc:
                logger.warning("Could not parse %s: %s", yml_file, exc)
        return results

    # ── GUI helpers ──────────────────────────────────────────────────────

    def to_gui_dict(self, sally_def: SallyScenarioDef) -> Dict[str, Any]:
        """
        Serialize a :class:`SallyScenarioDef` to a plain dict for the GUI.
        """
        return {
            "name": sally_def.name,
            "duration": sally_def.duration,
            "step_size": sally_def.step_size,
            "start_date": sally_def.start_date,
            "simulators": {
                k: {
                    "module": v.sally_module,
                    "class": v.sally_class,
                    "step_size": v.step_size,
                    "type": v.sim_type,
                    "params": v.params,
                }
                for k, v in sally_def.simulators.items()
            },
            "entities": [
                {
                    "sim_key": e.sim_key,
                    "model": e.model,
                    "count": e.count,
                    "params": e.params,
                    "entity_id": e.entity_id,
                }
                for e in sally_def.entities
            ],
            "connections": [
                {
                    "src": c.src,
                    "dst": c.dst,
                    "attrs": c.attrs,
                    "async": c.async_request,
                }
                for c in sally_def.connections
            ],
            "metadata": sally_def.metadata,
        }

"""
SAlly SCADA — MIDAS scenario mode.

Launches the SCADA GUI after running a MIDAS co-simulation scenario.
The scenario is executed using the native MIDAS API (``midas.run()``),
which produces output data (CSV/HDF5).  The SCADA GUI then replays
that data via the standard ``SmartGridSimulation`` pipeline.

Usage (CLI)::

    python -m sally.main_scada_midas                          # uses GUI file picker
    python -m sally.main_scada_midas --scenario four_bus      # by scenario name
    python -m sally.main_scada_midas --scenario four_bus_der  # DER variant
    python -m sally.main_scada_midas --scenario midasmv       # medium voltage

The ``--scenario`` flag accepts a **scenario name** (top-level YAML key),
*not* a file path.  MIDAS resolves the file from its built-in defaults
unless ``--config`` is also given to point to a custom YAML.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sally.core.config import config
from sally.core.event_bus import EventBus
from sally.core.logger import get_logger
from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager
from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation
from sally.application.simulation.midas import MidasSimulationAdapter
from sally.infrastructure.services.scada_orchestration_service import (
    SCADAOrchestrationService,
    SCADAOrchestrationConfig,
)
from sally.presentation.gui.scada.scada import create_scada_gui

logger = get_logger(__name__)

# Try telemetry — optional
try:
    from sally.core.service_telemetry import init_service_telemetry, ServiceNames

    _TELEMETRY_AVAILABLE = True
except ImportError:
    _TELEMETRY_AVAILABLE = False


# ── helpers ──────────────────────────────────────────────────────────────────


def _pick_scenario_gui() -> str | None:
    """Open a simple tk dialog to pick a MIDAS scenario name."""
    try:
        import tkinter as tk
        from tkinter import simpledialog

        adapter = MidasSimulationAdapter()
        available = adapter.list_available_scenarios()

        if not available:
            logger.warning("No MIDAS scenarios found")
            return None

        root = tk.Tk()
        root.withdraw()

        names = [s["name"] for s in available]
        choice = simpledialog.askstring(
            "MIDAS Scenario",
            f"Available scenarios:\n{chr(10).join(f'  • {n}' for n in names)}\n\nEnter scenario name:",
            initialvalue=names[0] if names else "",
            parent=root,
        )
        root.destroy()
        return choice
    except Exception as exc:
        logger.warning("GUI picker failed: %s", exc)
        return None


def _build_midas_simulation(
    scenario_name: str,
    event_bus: EventBus,
    rule_manager: SmartGridRuleManager,
    *,
    config_file: str | None = None,
    override_duration: int | None = None,
) -> SmartGridSimulation:
    """Run a MIDAS scenario and wrap the output in a SmartGridSimulation.

    The flow is:
      1. Run the MIDAS scenario via ``midas.run()`` — this creates a
         mosaik World, executes the co-simulation, and writes output files.
      2. Locate the output HDF5 / CSV produced by MIDAS.
      3. Open it with :class:`SmartGridSimulation` for GUI replay.
    """
    adapter = MidasSimulationAdapter()

    logger.info("Running MIDAS scenario: %s", scenario_name)

    params: dict = {}
    if override_duration is not None:
        params["end"] = override_duration

    # Output file: tell MIDAS store to write here
    hdf5_out = config.get_path("hdf5_dir") / f"midas_{scenario_name}.hdf5"
    params.setdefault("store_params", {})
    params["store_params"]["filename"] = str(hdf5_out)

    midas_scenario = adapter.run_scenario(
        scenario_name,
        config=config_file,
        params=params,
    )

    logger.info("MIDAS co-simulation complete")

    # Find the produced output file
    # MIDAS stores write CSV by default; check if HDF5 exists
    if hdf5_out.exists():
        output_path = hdf5_out
    else:
        # Fall back: check for CSV output in the working directory
        csv_candidate = Path(f"{scenario_name}.csv")
        if csv_candidate.exists():
            logger.info("MIDAS produced CSV output: %s", csv_candidate)
            # For now, try to use a pre-existing HDF5 if available
            fallback = config.get_path("hdf5_dir") / f"midas_{scenario_name}.hdf5"
            if not fallback.exists():
                # Use default HDF5 as fallback
                fallback = config.get_path("default_hdf5_file")
                logger.warning(
                    "No HDF5 output from MIDAS; falling back to %s", fallback
                )
            output_path = fallback
        else:
            output_path = config.get_path("default_hdf5_file")
            logger.warning(
                "No output from MIDAS; falling back to %s", output_path
            )

    simulation = SmartGridSimulation(
        str(output_path),
        rule_manager,
        event_bus=event_bus,
        publish_scada_events=True,
    )
    return simulation


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SAlly SCADA — MIDAS scenario mode",
    )
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        default=None,
        help=(
            "Name of a MIDAS scenario (top-level YAML key). "
            "E.g. 'four_bus', 'midasmv', 'four_bus_der'. "
            "If omitted the GUI picker will be used."
        ),
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to a custom MIDAS YAML file (optional).",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Override scenario duration (seconds).",
    )
    args = parser.parse_args()

    logger.info("Starting SAlly SCADA in MIDAS mode …")

    # ── telemetry ────────────────────────────────────────────────────────
    if _TELEMETRY_AVAILABLE:
        config_path = config.get_path("config_dir") / "default.yml"
        init_service_telemetry(
            ServiceNames.ORCHESTRATOR,
            config_path=config_path,
            extra_attributes={"component": "scada_midas"},
        )
        logger.info("Telemetry initialised")

    # ── orchestration config ─────────────────────────────────────────────
    scada_cfg = config.scada.orchestration
    orchestration_config = SCADAOrchestrationConfig(
        update_interval_ms=scada_cfg.update_interval_ms,
        max_triggered_rules_history=scada_cfg.max_triggered_rules_history,
        event_buffer_size=scada_cfg.event_buffer_size,
        default_step_interval_s=scada_cfg.default_step_interval_s,
    )

    event_bus = EventBus(
        buffer_size=orchestration_config.event_buffer_size,
        batch_size=config.event_bus.batch_size,
        worker_count=config.event_bus.worker_count,
    )

    # ── rules ────────────────────────────────────────────────────────────
    rule_manager = SmartGridRuleManager()
    rules_path = config.get_path("default_rules_file")
    if rules_path.exists():
        with rules_path.open("r") as fh:
            rules_data = json.load(fh)
        if isinstance(rules_data, list):
            rule_manager.load_rules(rules_data)
        logger.info("Loaded %d rules from %s", len(rules_data) if isinstance(rules_data, list) else 0, rules_path)

    # ── resolve scenario ─────────────────────────────────────────────────
    scenario_name = args.scenario

    if scenario_name is None:
        scenario_name = _pick_scenario_gui()

    if scenario_name is None:
        logger.error("No scenario selected — exiting")
        sys.exit(1)

    # Run MIDAS and create simulation
    try:
        simulation = _build_midas_simulation(
            scenario_name,
            event_bus,
            rule_manager,
            config_file=args.config,
            override_duration=args.duration,
        )
    except Exception as exc:
        logger.error("Failed to run MIDAS scenario '%s': %s", scenario_name, exc)
        logger.info("Falling back to default HDF5 replay")
        hdf5_path = config.get_path("default_hdf5_file")
        simulation = SmartGridSimulation(
            str(hdf5_path), rule_manager,
            event_bus=event_bus, publish_scada_events=True,
        )

    # ── orchestration + GUI ──────────────────────────────────────────────
    orchestration = SCADAOrchestrationService(
        event_bus=event_bus,
        simulation=simulation,
        rule_manager=rule_manager,
        config=orchestration_config,
    )
    orchestration.start()
    logger.info("Orchestration service started")

    try:
        create_scada_gui(orchestration)
    finally:
        logger.info("Shutting down …")
        orchestration.stop()
        simulation.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()

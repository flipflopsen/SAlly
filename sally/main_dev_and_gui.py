"""
sally/main_dev_and_gui.py

Entry point for the Sally Simulation and GUI Rule Manager.
Refactored to use explicit path management and dependency injection.
"""
import logging
import sys
import json
from pathlib import Path
from typing import Optional

# 3rd Party
from dependency_injector.wiring import Provide, inject

# Local Imports
from sally.containers import ContainerFactory, ContainerType
from sally.infrastructure.data_management.sg.smartgrid_db_adapter import (
    SmartGridDatabase,
    SGDataCollector
)
from sally.core.logger import get_logger
from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager
from sally.presentation.gui.rule_manager import rule_manager_gui
from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation

# Path Definitions
from sally.core.config import config

from opentelemetry import trace
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor


AsyncPGInstrumentor().instrument()
LoggingInstrumentor().instrument(set_logging_format=True)

# Initialize Module Logger
logger = logging.getLogger(__name__) # This is for OTEL
#mlogger = get_logger(__name__)

class SallyBootstrapper:
    """
    Handles application initialization, container wiring, and execution modes.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self.container = None
        self.logger = logger

        self._initialize_container()

    def _initialize_container(self):
        """Initializes the DI container and wires it to the current module."""
        if not self.config_path.exists():
            self.logger.warning(f"Config file not found at {self.config_path}. System may be unstable.")

        self.logger.info(f"Bootstrapping with config: {self.config_path}")

        fac = ContainerFactory()
        self.container = (
            fac.with_config(str(self.config_path))
               .create(ContainerType.SIMULATION)
        )

        # Wire this module to allow @inject decorators if needed in standalone functions
        # or just use the container attributes directly.
        self.container.wire(modules=[sys.modules[__name__]])

    def run_simulation(self, steps: int, hdf5_path: Path) -> None:
        """
        Executes the Smart Grid Simulation headless.

        Args:
            steps (int): Number of steps to execute.
            hdf5_path (Path): Path to the HDF5 source file.
        """
        # Resolve Components from Container
        rule_manager = self.container.rule_manager()
        event_bus = self.container.event_bus()


        # Validate Inputs
        rules_path = config.get_path("default_rules_file")
        if not rules_path.exists():
            self.logger.critical(f"Rules artifact missing: {rules_path}")
            return

        if not hdf5_path.exists():
            self.logger.critical(f"HDF5 Artifact missing: {hdf5_path}")
            return

        self.logger.info("Starting Simulation Sequence")
        self.logger.info(f"Loading Rules: {rules_path}")

        # Load Rules
        try:
            with rules_path.open('r') as fh:
                rules_data = json.load(fh)
                rule_manager.load_rules(rules_data)
        except (json.JSONDecodeError, OSError) as e:
            self.logger.exception(f"Failed to load rules: {e}")
            return

        # Initialize Simulation
        self.logger.info(f"Mounting HDF5: {hdf5_path}")
        simulation = SmartGridSimulation(str(hdf5_path), rule_manager, event_bus=event_bus)

        try:
            # Execution Loop
            # > [!NOTE]
            # The original logic used a for-else loop which printed failure on success.
            # I have inverted this to standard explicit logic.
            step_count = 0
            for i in range(steps):
                if not simulation.step():
                    self.logger.warning(f"Simulation halted early at step {i}")
                    break
                step_count += 1

            self.logger.info(f"Simulation finalized. Steps executed: {step_count}/{steps}")

        except Exception as e:
            self.logger.error(f"Runtime simulation error: {e}")
        finally:
            simulation.close()

    def start_gui(self):
        """Launches the Rule Manager GUI."""
        self.logger.info("Initializing GUI Subsystem...")
        rule_manager_gui.create_gui()


# --- CLI Entry Point ---

if __name__ == "__main__":
    WITH_GUI: bool = False
    WITH_SIM: bool = True
    SIM_STEPS: int = 1000

    logger.info(f"Project Root: {config.paths.project_root}")

    config_path = Path(str(config.get("paths.config_dir")) + "\default.yml")

    # 1. Bootstrap
    app = SallyBootstrapper(config_path)



    # 2. GUI Mode
    if WITH_GUI:
        app.start_gui()

    # 3. Simulation Mode
    if WITH_SIM:
        # Determine HDF5 path (Allow override via args if extended later)
        target_hdf5 = config.get_path("default_hdf5_file")

        app.run_simulation(steps=SIM_STEPS, hdf5_path=target_hdf5)

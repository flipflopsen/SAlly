"""
SmartGrid HDF5 Simulation

High-performance simulation engine that reads HDF5 time series data and
publishes events to the event bus with full OTEL tracing and metrics.
"""

import time
import asyncio
import h5py  # For reading HDF5 files
import numpy as np
from typing import Dict, Any, List, Optional, Callable

from sally.application.simulation.base_sim import BaseSimulation
from sally.core.logger import get_logger
from sally.core.event_bus import EventBus, EventHandler
import sally.core.waitress as waitress
from sally.domain.events import (
    GridDataEvent,
    ControlActionEvent,
    RuleTriggeredEvent,
    SimulationStepEvent,
    SimulationStateEvent,
    SetpointChangeEvent,
)
from sally.domain.grid_entities import GridMeasurement, EntityType
from sally.core.logger import getLogger

# Try to import telemetry
_TELEMETRY_AVAILABLE = True
try:
    from sally.core.telemetry import get_telemetry, TelemetryManager
    from sally.core.service_telemetry import ServiceNames
    _TELEMETRY_AVAILABLE = True
except ImportError:
    pass


class SmartGridSimulation(BaseSimulation, EventHandler):
    """
    HDF5-based smart grid simulation with OTEL instrumentation.

    Reads time series data from HDF5 files and publishes grid events.
    Supports rule evaluation, setpoint management, and control actions.
    """

    def __init__(
        self,
        hdf5_filepath: str,
        rule_manager,
        event_bus: EventBus = None,
        sim_timeout_seconds: float = 1.0,
        publish_scada_events: bool = True,
    ):
        super().__init__(rule_manager)
        self.logger = getLogger(__name__)
        self.hdf5_filepath = hdf5_filepath
        self.event_bus = event_bus
        self.publish_scada_events = publish_scada_events

        self.rule_manager = rule_manager
        self.current_timestep = 0
        self.total_timesteps = 0
        self._hdf5_file_handle = None
        self._load_hdf5_data()
        self.current_timestep_data = None
        self._setpoints: Dict[str, float] = {}
        self._step_callbacks: List[Callable] = []
        self.entities = set(self.entity_variable_timeseries_data.keys()) if self.entity_variable_timeseries_data else set()

        # OTEL telemetry
        self._telemetry: Optional[TelemetryManager] = None
        self._metrics_registered = False
        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
                self._register_metrics()
            except Exception as e:
                self.logger.warning("Failed to initialize simulation telemetry: %s", e)

        # Subscribe to event bus if provided
        if self.event_bus:
            self.event_bus.subscribe(self)
            self.logger.debug("Simulation subscribed to event bus")

        self.sim_timeout_seconds = sim_timeout_seconds

        self.logger.info(
            "SmartGridSimulation initialized: hdf5=%s, timesteps=%d, entities=%d",
            hdf5_filepath, self.total_timesteps, len(self.entity_variable_timeseries_data)
        )

    def _register_metrics(self) -> None:
        """Register OTEL metrics for the simulation."""
        if not self._telemetry or not self._telemetry.enabled or self._metrics_registered:
            return

        try:
            # Simulation timestep gauges
            self._telemetry.gauge(
                "scada.simulation.timestep",
                lambda: self.current_timestep,
                "Current simulation timestep"
            )
            self._telemetry.gauge(
                "simulation.total_timesteps",
                lambda: self.total_timesteps,
                "Total simulation timesteps"
            )

            # Grid data metrics (for sally-scada dashboard)
            self._telemetry.gauge(
                "grid_data.entities_monitored",
                lambda: len(self.entity_variable_timeseries_data),
                "Number of grid entities being monitored"
            )

            # Setpoint metrics
            self._telemetry.gauge(
                "scada.setpoints.active_count",
                lambda: len(self._setpoints),
                "Active setpoint overrides"
            )

            self._metrics_registered = True
            self.logger.debug("Simulation OTEL metrics registered")
        except Exception as e:
            self.logger.warning("Failed to register simulation metrics: %s", e)

    @property
    def event_types(self) -> list[str]:
        return ["control_action"]

    async def handle(self, event):
        """Handle control actions from services"""
        if isinstance(event, ControlActionEvent):
            self.logger.info(
                "Received control action: type=%s target=%s value=%s",
                event.action_type, event.target_entity, event.control_value
            )
            # Implement control logic here
            # For now, just log the action

    def _load_hdf5_data(self):
        if not self.hdf5_filepath:
            self.logger.error("HDF5 filepath not provided for simulation")
            return

        self.entity_variable_timeseries_data = {}
        self.relation_data = {}
        self.total_timesteps = 0
        self.entities = set(self.entity_variable_timeseries_data.keys())

        load_start = time.perf_counter()
        self.logger.debug("Loading HDF5 data from: %s", self.hdf5_filepath)

        try:
            self._hdf5_file_handle = h5py.File(self.hdf5_filepath, 'r')

            def visitor_function(name, obj):
                # name is the full HDF5 path, e.g., "Relations/CSV-0.PV_0" or "Generator1/P_MW_out"
                path_parts = name.split('/')

                if isinstance(obj, h5py.Dataset):
                    if path_parts[0] == "Relations" and len(path_parts) == 2:
                        # This is a relation dataset, e.g., Relations/CSV-0.PV_0
                        relation_name = path_parts[1]
                        self.relation_data[relation_name] = obj[:]  # Load the entire matrix/data
                        self.logger.debug("Loaded relation: %s", relation_name)

                    elif path_parts[0] != "Relations":  # Process as potential "Series" data
                        # This part relies on your previously working "Series" parsing logic.
                        # Assuming EntityName/VariableName structure for series:
                        if len(path_parts) >= 2:
                            entity_name = path_parts[-2]
                            variable_name = path_parts[-1]

                            # Prevent misinterpreting something like "OtherGroup/Relations/Dataset"
                            if entity_name == "Relations":
                                return  # Skip if the immediate parent group is "Relations"

                            if entity_name not in self.entity_variable_timeseries_data:
                                self.entity_variable_timeseries_data[entity_name] = {}

                            self.entity_variable_timeseries_data[entity_name][variable_name] = obj[:]

                            # Determine total_timesteps from Series data
                            current_len = len(obj[:])
                            if current_len > 0:
                                if self.total_timesteps == 0:
                                    self.total_timesteps = current_len
                                elif current_len != self.total_timesteps:
                                    self.logger.warning(f"Warning: Inconsistent dataset length for Series data '{name}'. "
                                          f"Expected {self.total_timesteps}, found {current_len}. "
                                          f"Using previously determined total_timesteps: {self.total_timesteps}.")

            self._hdf5_file_handle.visititems(visitor_function)

            if self.entity_variable_timeseries_data and self.total_timesteps == 0:
                self.logger.warning("Warning: 'Series' data found, but total_timesteps is 0 (all series datasets might be empty).")
            elif self.entity_variable_timeseries_data:
                self.logger.info(f"HDF5 'Series' data loaded. Total simulation timesteps: {self.total_timesteps}")

            if self.relation_data:
                self.logger.info(f"HDF5 'Relations' data loaded for {len(self.relation_data)} items.")
            else:
                self.logger.error("No 'Relations' data found or loaded from HDF5.")

        except FileNotFoundError:
            self.logger.critical(f"Error: HDF5 file not found at '{self.hdf5_filepath}'")
            self.total_timesteps = 0
        except Exception as e:
            self.logger.critical(f"Error loading HDF5 file '{self.hdf5_filepath}': {e}")
            self.total_timesteps = 0
        # File handle remains open for potential future partial reads (though currently all is loaded)
        # It will be closed by self.close()

    def set_total_timesteps(self, total_timesteps: int):
        self.total_timesteps = total_timesteps

    def step(self) -> bool:
        """
        Advances the simulation by one timestep with OTEL tracing.

        - Gets current data.
        - Publishes data events to services.
        - Evaluates rules.
        - Calls on_rule_triggered for any triggered actions.
        - Increments timestep.

        Returns:
            bool: True if the step was successful, False if simulation has ended.
        """
        if self.current_timestep >= self.total_timesteps:
            self.logger.info("Simulation finished: timestep=%d/%d", self.current_timestep, self.total_timesteps)
            return False

        # Execute step with or without telemetry span
        if self._telemetry and self._telemetry.enabled:
            return self._step_with_telemetry()
        else:
            return self._step_internal()

    def _step_with_telemetry(self) -> bool:
        """Execute step wrapped in OTEL span for trace context propagation."""
        with self._telemetry.span(
            "simulation.step",
            kind="server",
            attributes={
                "timestep": self.current_timestep,
                "total_timesteps": self.total_timesteps,
                "entity_count": len(self.entity_variable_timeseries_data),
            },
            service_name=ServiceNames.SIMULATION if _TELEMETRY_AVAILABLE else None,
        ):
            return self._step_internal()

    def _step_internal(self) -> bool:
        """Internal step execution logic."""
        step_start = time.perf_counter()

        try:
            self.logger.debug(
                "Simulation step: %d/%d (%.1f%%)",
                self.current_timestep + 1,
                self.total_timesteps,
                (self.current_timestep + 1) / self.total_timesteps * 100
            )

            current_data = self.get_current_data_snapshot()
            self.current_timestep_data = current_data

            if not current_data and self.total_timesteps > 0:
                self.logger.warning("Empty data snapshot at timestep %d", self.current_timestep)

            # Publish data events to connected services
            events_published = 0
            if self.event_bus and self.publish_scada_events:
                events_published = self._publish_data_events(current_data)
                self.logger.debug("Published %d grid data events", events_published)

            # Evaluate rules with OTEL span
            triggered_actions = self._evaluate_rules_with_telemetry(current_data)

            if triggered_actions:
                self.logger.info("Rules triggered at step %d: %d", self.current_timestep, len(triggered_actions))
                for action_info in triggered_actions:
                    self.on_rule_triggered(action_info)
                    if self.event_bus and self.publish_scada_events:
                        event = RuleTriggeredEvent(
                            rule_id=action_info.get("triggering_rule_id", ""),
                            entity_name=action_info.get("triggering_entity", ""),
                            variable_name=action_info.get("triggering_variable", ""),
                            threshold=float(action_info.get("rule_threshold", 0) or 0),
                            actual_value=float(action_info.get("triggering_value", 0) or 0),
                            action=action_info.get("action_command", ""),
                            timestamp=time.time(),
                        )
                        self.event_bus.publish_sync(event)

                # Record triggered rules metric
                if self._telemetry and self._telemetry.enabled:
                    self._telemetry.counter(
                        "simulation.rules_triggered",
                        len(triggered_actions),
                        {"timestep": str(self.current_timestep)}
                    )
            else:
                self.logger.debug("No rules triggered at step %d", self.current_timestep)

            self.current_timestep += 1

            # Execute step callbacks
            for callback in list(self._step_callbacks):
                try:
                    callback(self.current_timestep)
                except Exception as e:
                    self.logger.warning("Step callback error: %s", e)

            if self.event_bus and self.publish_scada_events:
                step_event = SimulationStepEvent(
                    timestep=self.current_timestep,
                    simulation_time=float(self.current_timestep),
                )
                self.event_bus.publish_sync(step_event)
                state_event = SimulationStateEvent(
                    timestep=self.current_timestep,
                    simulation_time=float(self.current_timestep),
                    snapshot=current_data,
                )
                self.event_bus.publish_sync(state_event)

            if self.current_timestep >= self.total_timesteps:
                self.logger.info("Simulation completed: %d timesteps", self.total_timesteps)

            # Record step duration
            step_duration_ms = (time.perf_counter() - step_start) * 1000
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.histogram(
                    "simulation.step_duration_ms",
                    step_duration_ms,
                    {"timestep": str(self.current_timestep - 1)}
                )

            waitress.high_precision_wait(self.sim_timeout_seconds)

            return True
        except Exception as e:
            self.logger.error("Step execution failed: %s", e)
            raise

    def _evaluate_rules_with_telemetry(self, current_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate rules, wrapped in OTEL span if telemetry is enabled."""
        if self._telemetry and self._telemetry.enabled:
            with self._telemetry.span(
                "simulation.evaluate_rules",
                kind="internal",
                attributes={"timestep": self.current_timestep},
                service_name=ServiceNames.SIMULATION if _TELEMETRY_AVAILABLE else None,
            ) as span:
                triggered_actions = self.evaluate_rules_at_timestep(current_data)
                span.set_attribute("rules_triggered", len(triggered_actions) if triggered_actions else 0)
                return triggered_actions
        else:
            return self.evaluate_rules_at_timestep(current_data)

    def on_rule_triggered(self, action_info: dict):
        """
        Callback method when a rule is triggered.
        action_info is a dictionary from SmartGridRuleManager.evaluate_rules_at_timestep
        """
        entity_name = action_info.get('triggering_entity', 'N/A')
        variable_name = action_info.get('triggering_variable', 'N/A')
        rule_id = action_info.get('triggering_rule_id', 'N/A')
        action = action_info.get('action_command', 'N/A')
        value = action_info.get('triggering_value')
        operator = action_info.get('rule_operator')
        threshold = action_info.get('rule_threshold')

        self.logger.info(
            "Rule triggered: \n rule_id=%s \n entity=%s.%s \n action=%s \n condition=%s%s%s",
            rule_id, entity_name, variable_name, action, value, operator, threshold
        )

        # Record to OTEL span if available
        if self._telemetry and self._telemetry.enabled:
            self._telemetry.counter(
                "simulation.rule_triggered",
                1,
                {
                    "rule_id": str(rule_id),
                    "entity": entity_name,
                    "variable": variable_name,
                    "action": str(action),
                }
            )

    def get_current_data_snapshot(self) -> dict:
        """Get the current timestep data snapshot with setpoints applied."""
        snapshot = {}

        # Populate "Series" data for the current timestep
        if self.current_timestep < self.total_timesteps or (
                self.total_timesteps == 0 and self.entity_variable_timeseries_data):
            for entity_name, variables_dict in self.entity_variable_timeseries_data.items():
                snapshot[entity_name] = {}
                for variable_name, timeseries_data in variables_dict.items():
                    if self.current_timestep < len(timeseries_data):
                        snapshot[entity_name][variable_name] = timeseries_data[self.current_timestep]
                    else:
                        snapshot[entity_name][variable_name] = None  # Series is shorter

        # Add "Relations" data (static, not per timestep)
        if self.relation_data:
            relations_copy = {}
            for key, value in self.relation_data.items():
                if isinstance(value, np.ndarray):
                    relations_copy[key] = value.tolist()
                else:
                    relations_copy[key] = value
            snapshot['Relations'] = relations_copy

        # Apply any active setpoints to override values
        self._apply_setpoints_to_snapshot(snapshot)

        return snapshot

    def _publish_data_events(self, current_data: dict) -> int:
        """
        Publish grid data events to connected services.

        Returns:
            int: Number of events published
        """
        current_time = time.time()
        events_published = 0

        for entity_name, variables in current_data.items():
            if entity_name == 'Relations':
                continue  # Skip relations for now

            if isinstance(variables, dict):
                measurement = self._create_measurement_from_data(entity_name, variables, current_time)
                if measurement:
                    event = GridDataEvent(
                        measurement=measurement,
                        timestamp=current_time,
                        correlation_id=f"sim_{entity_name}_{self.current_timestep}"
                    )
                    if self.event_bus.publish_sync(event):
                        events_published += 1

        return events_published

    def _create_measurement_from_data(self, entity_name: str, variables: dict, timestamp: float) -> GridMeasurement:
        """Create GridMeasurement from simulation data"""
        # Infer entity type from entity name
        entity_type = self._infer_entity_type(entity_name)

        # Map variables to measurement fields
        measurement_kwargs = {
            'entity': entity_name,
            'entity_type': entity_type,
            'timestamp': timestamp
        }

        # Map common variable names to measurement fields
        var_mapping = {
            'P_MW_out': 'p_out',
            'P_MW': 'p',
            'Q_MVAR': 'q',
            'VA': 'va',
            'VL': 'vl',
            'VM': 'vm'
        }

        for var_name, value in variables.items():
            if value is not None:
                field_name = var_mapping.get(var_name, var_name.lower())
                if field_name in ['p', 'p_out', 'q', 'va', 'vl', 'vm', 'humidity']:
                    measurement_kwargs[field_name] = float(value)

        return GridMeasurement(**measurement_kwargs)

    def _infer_entity_type(self, entity_name: str) -> EntityType:
        """Infer EntityType from entity name"""
        name_lower = entity_name.lower()
        if 'gen' in name_lower or 'node' in name_lower:
            return EntityType.PYPOWER_NODE
        elif 'pv' in name_lower:
            return EntityType.CSV_PV
        elif 'wind' in name_lower:
            return EntityType.WIND_TURBINE
        elif 'house' in name_lower:
            return EntityType.HOUSEHOLD_SIM
        elif 'load' in name_lower:
            return EntityType.LOAD_BUS
        elif 'bess' in name_lower:
            return EntityType.BATTERY_ESS
        elif 'line' in name_lower:
            return EntityType.PYPOWER_BRANCH
        elif 'trans' in name_lower:
            return EntityType.PYPOWER_TRANSFORMER
        else:
            return EntityType.PYPOWER_NODE  # Default

    def close(self):
        """Closes the HDF5 file if it's open."""
        if self._hdf5_file_handle:
            try:
                self._hdf5_file_handle.close()
                self.logger.info(f"HDF5 file '{self.hdf5_filepath}' closed.")
                self._hdf5_file_handle = None
            except Exception as e:
                self.logger.info(f"Error closing HDF5 file: {e}")
        self.entity_variable_timeseries_data = {}  # Clear loaded data
        self.total_timesteps = 0
        self.current_timestep = 0

        async def run_with_pause(self, pause_seconds: float = 1.0):
            """Runs the entire simulation from the current step, with a pause between each step."""
            if pause_seconds < 0:
                pause_seconds = 0
            self.logger.info(f"Running simulation with a {pause_seconds:.2f}s pause between steps...")
            while self.current_timestep < self.total_timesteps:
                if not await self.step():
                    break  # Simulation ended
                if self.current_timestep < self.total_timesteps:  # Don't sleep after the last step
                    await asyncio.sleep(pause_seconds)
            self.logger.info("Simulation run with pause completed.")

    def reset(self):
        """Resets the simulation to the beginning."""
        self.current_timestep = 0
        self.logger.info("Simulation reset to timestep 0.")

    async def run_steps(self, num_steps: int):
        """Runs a specified number of simulation steps."""
        self.logger.info(f"Running simulation for {num_steps} steps.")
        for _ in range(num_steps):
            if not await self.step():  # If step returns False (simulation ended)
                break
        self.logger.info("Finished requested number of steps or simulation ended.")

    async def run_all(self):
        """Runs the entire simulation from the current step without pause."""
        self.logger.info("Running entire simulation...")
        while self.current_timestep < self.total_timesteps:
            if not await self.step():
                break
        self.logger.info("Entire simulation completed.")

    def set_data(self, timeseries_data, relational_data) -> None:
        self.entity_variable_timeseries_data = timeseries_data
        self.relation_data = relational_data

    def set_setpoint(self, entity: str, variable: str, value: float) -> None:
        if not entity or not variable:
            return

        # Wrap in telemetry span if available
        if self._telemetry and self._telemetry.enabled:
            with self._telemetry.span(
                "simulation.set_setpoint",
                kind="server",
                attributes={"entity": entity, "variable": variable, "value": value},
                service_name=ServiceNames.SIMULATION if _TELEMETRY_AVAILABLE else None,
            ):
                self._set_setpoint_internal(entity, variable, value)
        else:
            self._set_setpoint_internal(entity, variable, value)

    def _set_setpoint_internal(self, entity: str, variable: str, value: float) -> None:
        """Internal setpoint storage with metrics."""
        key = f"{entity}.{variable}"
        old_value = self._setpoints.get(key)
        self._setpoints[key] = value
        self.logger.info("Setpoint stored: %s = %s (old=%s). Current setpoints: %s", key, value, old_value, self._setpoints)

        # Record setpoint value as metric (use histogram for point-in-time values)
        if self._telemetry and self._telemetry.enabled:
            self._telemetry.histogram(
                "setpoints.value",
                value,
                {"entity": entity, "variable": variable}
            )
            self._telemetry.counter(
                "setpoints.applied.total",
                1,
                {"entity": entity, "variable": variable}
            )

        if self.event_bus and self.publish_scada_events:
            event = SetpointChangeEvent(
                entity=entity,
                variable=variable,
                old_value=float(old_value) if old_value is not None else float("nan"),
                new_value=value,
                source="external",
            )
            self.event_bus.publish_sync(event)

    def clear_setpoints(self) -> None:
        self._setpoints.clear()

    def remove_setpoint(self, entity: str, variable: str) -> bool:
        """Remove a single setpoint. Returns True if removed, False if not found."""
        key = f"{entity}.{variable}"
        if key in self._setpoints:
            del self._setpoints[key]
            self.logger.info("Setpoint removed: %s. Remaining setpoints: %s", key, self._setpoints)
            return True
        return False

    def register_step_callback(self, callback) -> None:
        if callback not in self._step_callbacks:
            self._step_callbacks.append(callback)

    def _apply_setpoints_to_snapshot(self, snapshot: dict) -> None:
        if self._setpoints:
            self.logger.info("Applying %d setpoints to snapshot. Keys: %s", len(self._setpoints), list(self._setpoints.keys()))
        for key, value in self._setpoints.items():
            # Use rsplit to split on the LAST dot since entity names contain dots (e.g., "CSV-0.PV_0")
            parts = key.rsplit(".", 1)
            if len(parts) != 2:
                self.logger.warning("Invalid setpoint key format: %s", key)
                continue
            entity, variable = parts
            if entity not in snapshot:
                self.logger.info("Creating new entity in snapshot for setpoint: %s", entity)
                snapshot[entity] = {}
            self.logger.debug("Setpoint applied: %s.%s = %s", entity, variable, value)
            snapshot[entity][variable] = value

    def __del__(self):
        # Ensure file is closed when the object is garbage collected, as a fallback
        self.close()

"""
SCADA Orchestration Service

Coordinates simulation execution, event processing, and GUI state updates.
Provides high-performance event handling with OTEL instrumentation.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import trio
from opentelemetry.trace import Status, StatusCode

from sally.core.event_bus import EventBus, SyncEventHandler
from sally.core.service_telemetry import ServiceNames
from sally.domain.events import (
    GridDataEvent,
    ControlActionEvent,
    RuleTriggeredEvent,
    SimulationStepEvent,
    SimulationStateEvent,
    SetpointChangeEvent,
)
from sally.domain.scada_state import SCADAState, RuleStatus, AnomalyInfo
from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation
from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager
from sally.core.logger import get_logger

# Try to import telemetry
_TELEMETRY_AVAILABLE = False
try:
    from sally.core.telemetry import get_telemetry, TelemetryManager
    _TELEMETRY_AVAILABLE = True
except ImportError:
    pass


@dataclass
class SCADAOrchestrationConfig:
    """Configuration for SCADA orchestration service."""
    update_interval_ms: int = 100
    max_triggered_rules_history: int = 50
    event_buffer_size: int = 1000
    default_step_interval_s: float = 1.0


class SCADAOrchestrationService(SyncEventHandler):
    """
    SCADA orchestration service with OTEL instrumentation.

    Coordinates:
    - Simulation execution and stepping
    - Event bus communication
    - GUI state updates
    - Command processing from GUI
    """

    def __init__(
        self,
        event_bus: EventBus,
        simulation: SmartGridSimulation,
        rule_manager: SmartGridRuleManager,
        config: Optional[SCADAOrchestrationConfig] = None,
        gui_queue: Optional[queue.Queue] = None,
    ):
        self.event_bus = event_bus
        self.simulation = simulation
        self.rule_manager = rule_manager
        self.config = config or SCADAOrchestrationConfig()

        self._state = SCADAState()
        self._state_queue: queue.Queue = gui_queue or queue.Queue(maxsize=self.config.event_buffer_size)
        self._command_queue: queue.Queue = queue.Queue()

        self._playback = False
        self._step_interval_s = self.config.default_step_interval_s

        self._trio_thread: Optional[threading.Thread] = None
        self._event_bus_thread: Optional[threading.Thread] = None
        self._stop_event_loop = threading.Event()
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        self._trio_token: Optional[trio.lowlevel.TrioToken] = None
        self._trio_stop_event: Optional[trio.Event] = None
        self._last_ui_push = 0.0
        self._logger = get_logger(__name__)

        # OTEL telemetry
        self._telemetry: Optional[TelemetryManager] = None
        self._events_handled = 0
        self._commands_processed = 0

        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
                self._register_metrics()
            except Exception as e:
                self._logger.warning("Failed to initialize orchestration telemetry: %s", e)

        self._logger.info(
            "SCADAOrchestrationService initialized: update_interval=%dms, buffer_size=%d",
            self.config.update_interval_ms, self.config.event_buffer_size
        )

    def _register_metrics(self) -> None:
        """Register OTEL metrics."""
        if not self._telemetry or not self._telemetry.enabled:
            return

        try:
            self._telemetry.gauge(
                "scada.queue_size",
                lambda: self._state_queue.qsize(),
                "GUI state queue size"
            )
            self._telemetry.gauge(
                "scada.command_queue_size",
                lambda: self._command_queue.qsize(),
                "Command queue size"
            )
            self._telemetry.gauge(
                "scada.setpoints.active.count",
                lambda: len(self._state._setpoints) if hasattr(self._state, '_setpoints') else 0,
                "Active setpoints count"
            )
            self._logger.debug("SCADA orchestration OTEL metrics registered")
        except Exception as e:
            self._logger.warning("Failed to register SCADA metrics: %s", e)

    @property
    def event_types(self) -> List[str]:
        return [
            "grid_data_update",
            "control_action",
            "rule_triggered",
            "simulation_step",
            "simulation_state",
            "setpoint_change",
        ]

    def handle_sync(self, event) -> None:
        """Handle events synchronously with OTEL tracing."""
        self._events_handled += 1

        if isinstance(event, GridDataEvent):
            self._state.update_measurement(event.measurement)
            self._logger.debug(
                "GridDataEvent: entity=%s timestamp=%s",
                event.measurement.entity if event.measurement else "N/A",
                event.timestamp
            )
        elif isinstance(event, RuleTriggeredEvent):
            status = RuleStatus(
                rule_id=event.rule_id,
                entity_name=event.entity_name,
                variable_name=event.variable_name,
                action=event.action,
                timestamp=event.timestamp,
                severity="CRITICAL" if event.action else "WARNING",
            )
            self._state.add_triggered_rule(status, max_history=self.config.max_triggered_rules_history)
            anomaly = AnomalyInfo(
                entity=event.entity_name,
                anomaly_type=event.action or "rule_triggered",
                severity="CRITICAL",
                timestamp=event.timestamp,
                details=f"{event.variable_name}={event.actual_value} (>{event.threshold})",
            )
            self._state.add_anomaly(anomaly, max_history=self.config.max_triggered_rules_history)
        elif isinstance(event, SimulationStepEvent):
            self._state.update_simulation_time(event.simulation_time)
        elif isinstance(event, SimulationStateEvent):
            self._state.update_simulation_time(event.simulation_time)
        elif isinstance(event, SetpointChangeEvent):
            key = f"{event.entity}.{event.variable}"
            self._state.update_setpoint(key, event.new_value)
        elif isinstance(event, ControlActionEvent):
            key = event.target_entity
            self._state.update_setpoint(key, event.control_value)

        self._enqueue_state_update(throttled=True)

    def start(self) -> None:
        """Start the orchestration service."""
        if self._trio_thread:
            self._logger.debug("Orchestration service already running")
            return

        self._logger.info("Starting SCADA orchestration service")
        self.event_bus.subscribe(self)
        self._start_event_bus_thread()

        self._trio_thread = threading.Thread(target=self._run_trio, name="scada-orchestration", daemon=True)
        self._trio_thread.start()
        self._logger.info("SCADA orchestration service started")

    def stop(self) -> None:
        """Stop the orchestration service gracefully."""
        self._logger.info("Stopping SCADA orchestration service")

        if self._trio_token is not None and self._trio_stop_event is not None:
            try:
                trio.from_thread.run_sync(self._trio_stop_event.set, trio_token=self._trio_token)
            except trio.RunFinishedError:
                pass

        if self._trio_thread:
            self._trio_thread.join(timeout=5)
            self._trio_thread = None
            self._logger.debug("Trio thread stopped")

        if self._event_loop:
            try:
                future = asyncio.run_coroutine_threadsafe(self.event_bus.stop(), self._event_loop)
                future.result(timeout=5)
            except Exception as exc:
                self._logger.warning("Error stopping event bus: %s", exc)
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)

        if self._event_bus_thread:
            self._event_bus_thread.join(timeout=5)
            self._event_bus_thread = None
            self._logger.debug("Event bus thread stopped")

        self._logger.info(
            "SCADA orchestration stopped: events_handled=%d commands_processed=%d",
            self._events_handled, self._commands_processed
        )

    def get_current_state(self) -> SCADAState:
        return self._state.snapshot()

    def get_gui_queue(self) -> queue.Queue:
        return self._state_queue

    def request_step(self) -> None:
        self._command_queue.put(("step", None))

    def set_playing(self, playing: bool) -> None:
        self._command_queue.put(("play", playing))

    def set_step_interval(self, seconds: float) -> None:
        self._command_queue.put(("interval", max(0.0, seconds)))

    def apply_setpoint(self, entity: str, variable: str, value: float, source: str = "scada_gui") -> None:
        self._command_queue.put(("setpoint", (entity, variable, value, source)))

    def reset_setpoints(self) -> None:
        self._command_queue.put(("reset_setpoints", None))

    def remove_setpoint(self, entity: str, variable: str) -> None:
        """Remove a single setpoint."""
        self._command_queue.put(("remove_setpoint", (entity, variable)))

    def _run_trio(self) -> None:
        trio.run(self._run)

    async def _run(self) -> None:
        self._trio_token = trio.lowlevel.current_trio_token()
        self._trio_stop_event = trio.Event()

        async with trio.open_nursery() as nursery:
            nursery.start_soon(self._command_processor)
            nursery.start_soon(self._auto_stepper)
            nursery.start_soon(self._gui_update_dispatcher)
            nursery.start_soon(self._event_bus_listener)
            nursery.start_soon(self._rule_manager_observer)
            await self._trio_stop_event.wait()
            nursery.cancel_scope.cancel()

    async def _command_processor(self) -> None:
        """Process commands from GUI with OTEL tracing."""
        self._logger.debug("Command processor started")
        while True:
            command, payload = await trio.to_thread.run_sync(self._command_queue.get)
            self._commands_processed += 1
            await self._process_command_with_telemetry(command, payload)

    async def _process_command_with_telemetry(self, command: str, payload) -> None:
        """Process a single command, wrapped in OTEL span if enabled."""
        start_time = time.perf_counter()

        if self._telemetry and self._telemetry.enabled:
            with self._telemetry.span(
                f"scada.command.{command}",
                kind="server",
                attributes={
                    "command": command,
                    "payload": str(payload)[:100] if payload else "",
                },
                service_name=ServiceNames.ORCHESTRATOR,
            ):
                await self._process_command_internal(command, payload, start_time)
        else:
            await self._process_command_internal(command, payload, start_time)

    async def _process_command_internal(self, command: str, payload, start_time: float) -> None:
        """Internal command processing logic."""
        try:
                self._logger.debug("Processing command: %s payload=%s", command, payload)

                if command == "step":
                    await self._run_step()
                elif command == "play":
                    self._playback = bool(payload)
                    self._logger.info("Playback state changed: %s", self._playback)
                elif command == "interval":
                    self._step_interval_s = float(payload)
                    self._logger.info("Step interval changed: %.3fs", self._step_interval_s)
                elif command == "setpoint" and payload:
                    entity, variable, value, source = payload
                    self._logger.info(
                        "Applying setpoint: %s.%s = %s (source=%s)",
                        entity, variable, value, source
                    )
                    # Create client span for calling simulation service
                    if self._telemetry and self._telemetry.enabled:
                        with self._telemetry.span(
                            "call_simulation.set_setpoint",
                            kind="client",
                            attributes={
                                "peer.service": ServiceNames.SIMULATION,
                                "entity": entity,
                                "variable": variable,
                            },
                            service_name=ServiceNames.ORCHESTRATOR,
                        ):
                            await trio.to_thread.run_sync(self.simulation.set_setpoint, entity, variable, value)
                    else:
                        await trio.to_thread.run_sync(self.simulation.set_setpoint, entity, variable, value)
                    
                    self._state.update_setpoint(f"{entity}.{variable}", value)
                    event = SetpointChangeEvent(
                        entity=entity,
                        variable=variable,
                        old_value=float("nan"),
                        new_value=value,
                        source=source,
                    )
                    self.event_bus.publish_sync(event)

                    if self._telemetry and self._telemetry.enabled:
                        self._telemetry.counter(
                            "scada.setpoints.applied.total",
                            1,
                            {"entity": entity, "variable": variable, "source": source}
                        )

                elif command == "remove_setpoint" and payload:
                    entity, variable = payload
                    self._logger.info("Removing setpoint: %s.%s", entity, variable)
                    await trio.to_thread.run_sync(self.simulation.remove_setpoint, entity, variable)
                    key = f"{entity}.{variable}"
                    self._state.remove_setpoint(key)
                    self._enqueue_state_update()

                elif command == "reset_setpoints":
                    self._logger.info("Resetting all setpoints")
                    await trio.to_thread.run_sync(self.simulation.clear_setpoints)
                    self._state.clear_setpoints()
                    self._enqueue_state_update()

                    if self._telemetry and self._telemetry.enabled:
                        self._telemetry.counter("scada.setpoints.cleared.total")

                # Record command processing metrics
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                if self._telemetry and self._telemetry.enabled:
                    self._telemetry.counter(
                        "scada.commands.total",
                        1,
                        {"command_type": command}
                    )
                    self._telemetry.histogram(
                        "scada.commands.duration_ms",
                        elapsed_ms,
                        {"command_type": command}
                    )

        except Exception as exc:
            self._logger.exception("SCADA command processor error: %s", exc)
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.counter("scada.command_errors", 1, {"command_type": command})
            raise

    async def _auto_stepper(self) -> None:
        """Automatic simulation stepper."""
        self._logger.debug("Auto-stepper started")
        while True:
            if self._playback:
                await self._run_step()
                await trio.sleep(self._step_interval_s)
            else:
                await trio.sleep(0.1)

    async def _run_step(self) -> None:
        """Execute a single simulation step with timing metrics."""
        if self._telemetry and self._telemetry.enabled:
            with self._telemetry.span(
                "scada.run_step",
                kind="server",
                attributes={
                    "timestep": self.simulation.current_timestep if hasattr(self.simulation, 'current_timestep') else 0,
                },
                service_name=ServiceNames.ORCHESTRATOR,
            ):
                await self._run_step_internal()
        else:
            await self._run_step_internal()

    async def _run_step_internal(self) -> None:
        """Internal step execution logic."""
        start_time = time.perf_counter()
        try:
            # Create client span for calling simulation service
            if self._telemetry and self._telemetry.enabled:
                with self._telemetry.span(
                    "call_simulation.step",
                    kind="client",
                    attributes={"peer.service": ServiceNames.SIMULATION},
                    service_name=ServiceNames.ORCHESTRATOR,
                ):
                    success = await trio.to_thread.run_sync(self.simulation.step)
            else:
                success = await trio.to_thread.run_sync(self.simulation.step)
            
            elapsed = (time.perf_counter() - start_time) * 1000

            if not success:
                self._playback = False
                self._logger.warning("Simulation step failed, stopping playback")
            else:
                self._logger.debug(
                    "Simulation step completed: timestep=%d elapsed=%.2fms",
                    self.simulation.current_timestep, elapsed
                )

            self._state.update_simulation_time(self.simulation.current_timestep)
            self._enqueue_state_update()

            if self._telemetry and self._telemetry.enabled:
                self._telemetry.histogram(
                    "scada.step_duration_ms",
                    elapsed,
                    {"success": str(success)}
                )
                self._telemetry.counter(
                    "scada.steps.total",
                    1,
                    {"success": str(success)}
                )
                # Record simulation time as gauge metric
                if hasattr(self.simulation, 'current_timestep'):
                    self._telemetry.gauge(
                        "scada.simulation.timestep",
                        float(self.simulation.current_timestep)
                    )

        except Exception as e:
            self._logger.exception("Simulation step failed: %s", e)
            raise

    async def _gui_update_dispatcher(self) -> None:
        """Periodic GUI state dispatcher."""
        interval = self.config.update_interval_ms / 1000.0
        self._logger.debug("GUI update dispatcher started: interval=%.3fs", interval)
        while True:
            self._enqueue_state_update()
            await trio.sleep(interval)

    async def _event_bus_listener(self) -> None:
        """Event bus health check listener."""
        self._logger.debug("Event bus listener started")
        while True:
            await trio.sleep(0.5)

    async def _rule_manager_observer(self) -> None:
        """Rule manager state observer."""
        self._logger.debug("Rule manager observer started")
        while True:
            await trio.sleep(1.0)
            self._enqueue_state_update()

    def _enqueue_state_update(self, throttled: bool = False) -> None:
        """Enqueue state snapshot for GUI consumption."""
        if throttled:
            now = time.time()
            interval = self.config.update_interval_ms / 1000.0
            if now - self._last_ui_push < interval:
                return
            self._last_ui_push = now
        snapshot = self._state.snapshot()
        try:
            if self._state_queue.full():
                self._state_queue.get_nowait()
                self._logger.debug("State queue full, dropped oldest entry")
            self._state_queue.put_nowait(snapshot)
        except queue.Empty:
            pass
        except queue.Full:
            self._logger.debug("Failed to enqueue state update - queue full")

    def _start_event_bus_thread(self) -> None:
        """Start the event bus processing thread."""
        if self._event_bus_thread:
            return

        self._logger.debug("Starting event bus thread")
        self._event_bus_thread = threading.Thread(target=self._run_event_bus_loop, name="scada-eventbus", daemon=True)
        self._event_bus_thread.start()

    def _run_event_bus_loop(self) -> None:
        """Run the asyncio event loop for the event bus."""
        self._logger.debug("Event bus loop starting")
        self._event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._event_loop)
        self._event_loop.run_until_complete(self.event_bus.start())
        self._logger.info("Event bus started successfully")
        self._event_loop.run_forever()

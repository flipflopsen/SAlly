"""
SCADA Main Window

Main GUI window for SCADA display with simulation controls,
rule status monitoring, and single-line diagram visualization.
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Optional

import ttkbootstrap as bstrap
from ttkbootstrap.constants import BOTH, HORIZONTAL, LEFT, RIGHT, VERTICAL, X, Y, SECONDARY, PRIMARY, SUCCESS

from sally.infrastructure.services.scada_orchestration_service import SCADAOrchestrationService
from sally.core.logger import get_logger
from sally.core.config import config
from sally.presentation.gui.scada.sld_display_v2 import SLDCanvasV2
from sally.presentation.gui.scada.sld_adapter_v2 import SLDDataAdapterV2
from sally.presentation.gui.scada.setpoint_panel import SetpointPanel
from sally.presentation.gui.scada.applied_setpoints_panel import AppliedSetpointsPanel
from sally.presentation.gui.scada.midas.midas_panel import MidasImportPanel

# Telemetry imports
try:
    from sally.core.telemetry import get_telemetry, TelemetryManager
    from sally.core.service_telemetry import ServiceNames
    _TELEMETRY_AVAILABLE = True
except ImportError:
    _TELEMETRY_AVAILABLE = False


class SCADAMainWindow(bstrap.Window):
    def __init__(self, orchestration_service: SCADAOrchestrationService):
        super().__init__(themename="cosmo", title="Sally SCADA", size=(1600, 900), minsize=(1280, 720))

        self._orchestration = orchestration_service
        self._state_queue: queue.Queue = orchestration_service.get_gui_queue()
        self._event_bus = orchestration_service.event_bus
        self._logger = get_logger(__name__)

        # Threading & State Management
        self._running = True
        self._latest_state = None
        self._state_lock = threading.Lock()
        self._last_render_time = 0.0
        self._render_interval = 1/144  # Limit to 144 FPS (~6.94ms)
        self._is_new_data_available = False

        self._is_collapsed = False
        self._playing = False
        self._entity_variable_map = {}
        self._populate_entity_variable_map()

        # Initialize telemetry
        self._telemetry: Optional[TelemetryManager] = None
        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
            except Exception as e:
                self._logger.warning("Failed to get telemetry: %s", e)

        self._build_ui()

        # Start Background Data Consumer
        self._data_thread = threading.Thread(target=self._data_ingestion_loop, daemon=True)
        self._data_thread.start()

        # Start Main Thread Render Loop
        self._start_render_loop()

        self._logger.info("SCADA window optimized initialized")

    def _data_ingestion_loop(self):
        """
        Background thread that continually drains the queue.
        It merges partial updates if your simulation sends them,
        or simply keeps the latest full state.
        """
        while self._running:
            try:
                # Block briefly to wait for data, preventing 100% CPU on empty loop
                # If we get data, we try to drain the REST of the queue immediately
                # to handle the "134 events" burst in one go.
                first_item = self._state_queue.get(timeout=0.1)

                # We have at least one item. Drain the rest to get the absolute latest.
                latest_batch_item = first_item
                count = 1

                while True:
                    try:
                        latest_batch_item = self._state_queue.get_nowait()
                        count += 1
                    except queue.Empty:
                        break

                # Update shared state safely (thread-safe flag only, no Tkinter calls!)
                with self._state_lock:
                    self._latest_state = latest_batch_item
                    self._is_new_data_available = True

                if count > 10:
                    self._logger.debug(f"Consumer thread merged {count} updates")

            except queue.Empty:
                continue
            except Exception as e:
                self._logger.error(f"Error in data ingestion loop: {e}")

    def _start_render_loop(self):
        """Standard Tkinter loop pattern using .after()"""
        self._render_frame()

    def _render_frame(self):
        """
        Called by Tkinter main loop. Checks if new data is available
        and if enough time has passed to warrant a redraw.
        """
        if not self._running:
            return

        current_time = time.time()

        # Check throttling
        #if current_time - self._last_render_time >= self._render_interval:
        # Check for new data
        state_snapshot = None
        with self._state_lock:
            if self._is_new_data_available:
                state_snapshot = self._latest_state
                self._is_new_data_available = False

        # Render if we have a snapshot
        if state_snapshot:
            self._refresh_ui(state_snapshot)
            self._last_render_time = current_time

        # Schedule next check - MUST use after() for proper Tkinter main loop integration
        self.after(16, self._render_frame)  # ~60 FPS polling rate

    def _populate_entity_variable_map(self) -> None:
        """Populate entity-variable map from simulation data."""
        sim = self._orchestration.simulation
        self._entity_variable_map = {
            entity: list(vars_dict.keys())
            for entity, vars_dict in sim.entity_variable_timeseries_data.items()
        }
        self._logger.debug(
            "Entity-variable map populated: entities=%d",
            len(self._entity_variable_map)
        )

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=8)
        main_frame.pack(fill=BOTH, expand=True)
        main_frame.pack(fill=BOTH, expand=True)
        self._paned = ttk.PanedWindow(main_frame, orient=HORIZONTAL)
        self._paned.pack(fill=BOTH, expand=True)

        self._sidebar = ttk.Frame(self._paned, width=320)
        self._sidebar.pack_propagate(False)

        self._header = ttk.Frame(self._sidebar)
        self._header.pack(fill=X, pady=(0, 10))
        self._header_label = ttk.Label(self._header, text="SCADA Controls", font=("-size", 16, "-family", "bold"))
        self._header_label.pack(side=LEFT, padx=5)
        self._sidebar_toggle_btn = bstrap.Button(
            self._header,
            text="⮜",
            bootstyle=SECONDARY,
            command=self._toggle_sidebar,
        )
        self._sidebar_toggle_btn.pack(side=RIGHT)

        # MIDAS / Simulation Source panel
        self._midas_panel = MidasImportPanel(
            self._sidebar,
            on_import=self._on_midas_import,
            on_mode_change=self._on_simulation_mode_change,
            initial_mode=getattr(config.simulation, "simulation_mode", "hdf5"),
        )
        self._midas_panel.pack(fill=X, pady=(0, 12))

        self._setpoint_panel = SetpointPanel(
            self._sidebar,
            self._apply_setpoint,
            self._reset_setpoints,
            get_variables_for_entity=self.get_variables_for_entity,
        )
        self._setpoint_panel.pack(fill=X, pady=(0, 12))
        self._setpoint_panel.update_entities(sorted(self._entity_variable_map.keys()))

        # Applied Setpoints table
        self._applied_setpoints_panel = AppliedSetpointsPanel(
            self._sidebar,
            on_toggle_setpoint=self._on_toggle_setpoint,
        )
        self._applied_setpoints_panel.pack(fill=X, pady=(0, 12))

        self._sim_frame = ttk.LabelFrame(self._sidebar, text="Simulation Control", padding=8)
        self._sim_frame.pack(fill=X, pady=(0, 12))

        self._timestep_var = tk.StringVar(value="0")
        ttk.Label(self._sim_frame, text="Timestep:").pack(anchor="w")
        ttk.Label(self._sim_frame, textvariable=self._timestep_var, font=("-size", 12, "-family", "bold")).pack(anchor="w")

        btn_row = ttk.Frame(self._sim_frame)
        btn_row.pack(fill=X, pady=(8, 4))
        bstrap.Button(btn_row, text="Step", bootstyle=PRIMARY, command=self._request_step).pack(side=LEFT, padx=4)
        self._play_button = bstrap.Button(btn_row, text="Play", bootstyle=SUCCESS, command=self._toggle_play)
        self._play_button.pack(side=LEFT, padx=4)

        ttk.Label(self._sim_frame, text="Speed (s)").pack(anchor="w", pady=(8, 0))
        self._speed_var = tk.DoubleVar(value=1.0)
        speed_slider = ttk.Scale(self._sim_frame, from_=0.1, to=5.0, orient=HORIZONTAL,
                                    variable=self._speed_var, command=self._update_speed)
        speed_slider.pack(fill=X, pady=(0, 4))

        self._rules_frame = ttk.LabelFrame(self._sidebar, text="Rule Status", padding=8)
        self._rules_frame.pack(fill=BOTH, expand=True)

        # Container for tree + scrollbar
        rules_container = ttk.Frame(self._rules_frame)
        rules_container.pack(fill=BOTH, expand=True)

        self._rules_tree = ttk.Treeview(rules_container, columns=("rule", "entity", "action", "time"), show="headings")
        self._rules_tree.heading("rule", text="Rule")
        self._rules_tree.heading("entity", text="Entity")
        self._rules_tree.heading("action", text="Action")
        self._rules_tree.heading("time", text="Time")
        self._rules_tree.column("rule", width=80)
        self._rules_tree.column("entity", width=120)
        self._rules_tree.column("action", width=120)
        self._rules_tree.column("time", width=80)
        self._rules_tree.tag_configure("critical", background="#b71c1c", foreground="#ffffff")
        self._rules_tree.tag_configure("warning", background="#f9a825", foreground="#000000")

        # Scrollbar for rules tree
        rules_scrollbar = ttk.Scrollbar(rules_container, orient=VERTICAL, command=self._rules_tree.yview)
        self._rules_tree.configure(yscrollcommand=rules_scrollbar.set)
        self._rules_tree.pack(side=LEFT, fill=BOTH, expand=True)
        rules_scrollbar.pack(side=RIGHT, fill=Y)

        # Track displayed rule timestamps to avoid duplicates
        self._displayed_rule_keys: set[str] = set()
        self._max_rule_entries = 100

        self._paned.add(self._sidebar, weight=1)

        self._display_frame = ttk.Frame(self._paned)
        self._sld_canvas = SLDCanvasV2(self._display_frame)
        self._sld_canvas.pack(fill=BOTH, expand=True)
        self._paned.add(self._display_frame, weight=4)
        self._sld_adapter = SLDDataAdapterV2()

        status_bar = ttk.Frame(main_frame)
        status_bar.pack(fill=X, pady=(6, 0))
        #bstrap.Button(status_bar, text="Step", bootstyle=PRIMARY, command=self._request_step).pack(side=LEFT)
        self._status_var = tk.StringVar(value="SAlly Connection Status: Disconnected")
        ttk.Label(status_bar, textvariable=self._status_var).pack(side=LEFT, padx=10)
        self._last_update_var = tk.StringVar(value="Last update: --")
        ttk.Label(status_bar, textvariable=self._last_update_var).pack(side=RIGHT)

    def _toggle_sidebar(self) -> None:
        """Toggle sidebar collapse/expand state."""
        self._logger.debug("Toggle sidebar: collapsed=%s", self._is_collapsed)
        if self._is_collapsed:
            self._sidebar.configure(width=320)
            self._header_label.pack(side=LEFT, padx=5)
            self._midas_panel.pack(fill=X, pady=(0, 12))
            self._setpoint_panel.pack(fill=X, pady=(0, 12))
            self._applied_setpoints_panel.pack(fill=X, pady=(0, 12))
            self._sim_frame.pack(fill=X, pady=(0, 12))
            self._rules_frame.pack(fill=BOTH, expand=True)
            self._sidebar_toggle_btn.configure(text="⮜")
            self._is_collapsed = False
            try:
                self._paned.sashpos(0, 320)
            except Exception:
                pass
            self._logger.debug("Sidebar expanded")
        else:
            self._header_label.pack_forget()
            self._midas_panel.pack_forget()
            self._setpoint_panel.pack_forget()
            self._applied_setpoints_panel.pack_forget()
            self._sim_frame.pack_forget()
            self._rules_frame.pack_forget()
            self._sidebar.configure(width=50)
            self._sidebar_toggle_btn.configure(text="⮞")
            self._is_collapsed = True
            try:
                self._paned.sashpos(0, 50)
            except Exception:
                pass
            self._logger.debug("Sidebar collapsed")
        self.update_idletasks()

    def _request_step(self) -> None:
        """Request a single simulation step."""
        self._logger.debug("Manual step requested")
        self._orchestration.request_step()

    def _toggle_play(self) -> None:
        """Toggle simulation play/pause state."""
        if self._telemetry and self._telemetry.enabled:
            with self._telemetry.span(
                "scada.gui.toggle_play",
                kind="client",
                attributes={
                    "new_state": not self._playing,
                    "peer.service": ServiceNames.ORCHESTRATOR if _TELEMETRY_AVAILABLE else "SAlly.Orchestrator"
                },
                service_name=ServiceNames.SCADA_GUI if _TELEMETRY_AVAILABLE else None
            ):
                self._toggle_play_internal()
        else:
            self._toggle_play_internal()

    def _toggle_play_internal(self) -> None:
        """Internal toggle play implementation."""
        self._playing = not self._playing
        self._orchestration.set_playing(self._playing)
        self._play_button.configure(text="Pause" if self._playing else "Play")
        self._logger.info("Playback toggled: playing=%s", self._playing)

    def _update_speed(self, _value) -> None:
        """Update simulation speed."""
        speed = self._speed_var.get()
        self._orchestration.set_step_interval(speed)
        self._logger.debug("Speed updated: interval=%.2fs", speed)

    def _apply_setpoint(self, entity: str, variable: str, value: float) -> None:
        """Apply a setpoint change to an entity."""
        if not entity or not variable:
            self._logger.warning("Invalid setpoint: entity=%s variable=%s", entity, variable)
            return

        if self._telemetry and self._telemetry.enabled:
            with self._telemetry.span(
                "scada.gui.apply_setpoint",
                kind="client",
                attributes={
                    "entity": entity,
                    "variable": variable,
                    "value": value,
                    "peer.service": ServiceNames.ORCHESTRATOR if _TELEMETRY_AVAILABLE else "SAlly.Orchestrator"
                },
                service_name=ServiceNames.SCADA_GUI if _TELEMETRY_AVAILABLE else None
            ):
                self._apply_setpoint_internal(entity, variable, value)
        else:
            self._apply_setpoint_internal(entity, variable, value)

    def _apply_setpoint_internal(self, entity: str, variable: str, value: float) -> None:
        """Internal setpoint application."""
        try:
            self._logger.info("Applying setpoint: %s.%s = %.4f", entity, variable, value)
            # Just queue the command - orchestration service handles event publishing
            self._orchestration.apply_setpoint(entity, variable, value)
            self._logger.debug("Setpoint command queued")

            # Record setpoint value metric (use histogram for point-in-time values)
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.histogram(
                    "setpoints.value",
                    value,
                    {"entity": entity, "variable": variable}
                )
        except Exception as e:
            self._logger.exception("Failed to apply setpoint: %s", e)

    def _reset_setpoints(self) -> None:
        """Reset all setpoints to defaults."""
        if self._telemetry and self._telemetry.enabled:
            with self._telemetry.span(
                "scada.gui.reset_setpoints",
                service_name=ServiceNames.SCADA_GUI if _TELEMETRY_AVAILABLE else None
            ):
                self._reset_setpoints_internal()
        else:
            self._reset_setpoints_internal()

    def _reset_setpoints_internal(self) -> None:
        """Internal reset setpoints implementation."""
        self._logger.info("Resetting all setpoints")
        self._orchestration.reset_setpoints()
        self._applied_setpoints_panel.clear()

    def _on_toggle_setpoint(self, entity: str, variable: str, active: bool) -> None:
        """Handle setpoint active/inactive toggle from the Applied Setpoints panel."""
        if active:
            # Re-apply the setpoint - get the value from the panel
            setpoints = self._applied_setpoints_panel._setpoints
            key = f"{entity}.{variable}"
            if key in setpoints:
                _, _, value, _ = setpoints[key]
                self._logger.info("Re-activating setpoint: %s.%s = %.4f", entity, variable, value)
                self._orchestration.apply_setpoint(entity, variable, value)
        else:
            # Remove the setpoint
            self._logger.info("Deactivating setpoint: %s.%s", entity, variable)
            self._orchestration.remove_setpoint(entity, variable)

    def _poll_state_queue(self) -> None:
        """Poll the state queue for updates from the orchestration service."""
        updated = False
        poll_count = 0
        while True:
            try:
                self._latest_state = self._state_queue.get_nowait()
                updated = True
                poll_count += 1
            except queue.Empty:
                break

        if updated and self._latest_state:
            if poll_count > 1:
                self._logger.debug("Consumed %d state updates (batched)", poll_count)
            self._refresh_ui(self._latest_state)

        self.after(100, self._poll_state_queue)

    def _refresh_ui(self, state) -> None:
        """Refresh UI with new state data."""
        # This runs on Main Thread, so we can touch GUI elements safely

        self._status_var.set("SAlly Connection Status: Connected")
        self._timestep_var.set(str(int(state.simulation_time)))
        self._last_update_var.set(f"Last update: {time.strftime('%H:%M:%S', time.localtime(state.last_update))}")

        # Update Applied Setpoints panel
        if hasattr(state, 'setpoints'):
            self._applied_setpoints_panel.update_setpoints(state.setpoints)

        # Convert state to SLD components (fast - uses caching)
        components = self._sld_adapter.convert(state)

        # Update SLD canvas (ultra-fast - only values update after first render)
        self._sld_canvas.update_components(components)

        # Update Rule Tree incrementally with FIFO at 100 entries
        for rule in state.triggered_rules:
            # Create unique key for this rule event
            rule_key = f"{rule.rule_id}:{rule.entity_name}:{rule.timestamp}"
            if rule_key in self._displayed_rule_keys:
                continue  # Already displayed

            # Remove oldest entries if at capacity
            children = self._rules_tree.get_children()
            while len(children) >= self._max_rule_entries:
                oldest = children[0]
                # Remove from tracking set (extract key from item values)
                old_values = self._rules_tree.item(oldest, "values")
                if old_values:
                    # Reconstruct approximate key for removal
                    self._displayed_rule_keys.discard(f"{old_values[0]}:{old_values[1]}:{rule.timestamp}")
                self._rules_tree.delete(oldest)
                children = self._rules_tree.get_children()

            # Insert new rule
            tag = "critical" if rule.severity == "CRITICAL" else "warning"
            self._rules_tree.insert("", "end",
                                    values=(rule.rule_id, rule.entity_name, rule.action, time.strftime("%H:%M:%S", time.localtime(rule.timestamp))),
                                    tags=(tag,))
            self._displayed_rule_keys.add(rule_key)

            # Auto-scroll to show latest entry
            self._rules_tree.yview_moveto(1.0)

    def get_variables_for_entity(self, entity_name: str):
        """Get available variables for a given entity."""
        variables = self._entity_variable_map.get(entity_name, [])
        self._logger.debug("Variables for entity %s: count=%d", entity_name, len(variables))
        return variables

    # ── MIDAS / simulation-mode callbacks ─────────────────────────────

    def _on_simulation_mode_change(self, mode: str) -> None:
        """Handle simulation mode change from the MidasImportPanel."""
        self._logger.info("Simulation mode changed to: %s", mode)
        config.simulation.simulation_mode = mode  # type: ignore[assignment]

    def _on_midas_import(self, gui_dict: dict, builder: Any) -> None:
        """Handle a successful MIDAS scenario import."""
        self._logger.info(
            "MIDAS scenario imported: %s (%d simulators)",
            gui_dict.get("name", "?"),
            len(gui_dict.get("simulators", {})),
        )
        # Refresh entity list so setpoint panel reflects new topology
        entities = [
            f"{e['sim_key']}.{e.get('entity_id', e['model'])}_{i}"
            for e in gui_dict.get("entities", [])
            for i in range(e.get("count", 1))
        ]
        if entities:
            self._setpoint_panel.update_entities(sorted(entities))

    def destroy(self):
        self._running = False
        super().destroy()



def create_scada_gui(orchestration_service: SCADAOrchestrationService) -> None:
        """Create and run the SCADA GUI main loop."""
        logger = get_logger(__name__)
        logger.info("Creating SCADA GUI")
        app = SCADAMainWindow(orchestration_service)
        logger.info("Starting SCADA GUI mainloop")
        app.mainloop()
        logger.info("SCADA GUI closed")


def create_scada_window(orchestration_service: SCADAOrchestrationService) -> SCADAMainWindow:
    """Create SCADA window without starting mainloop."""
    logger = get_logger(__name__)
    logger.info("Creating SCADA window instance")
    return SCADAMainWindow(orchestration_service)

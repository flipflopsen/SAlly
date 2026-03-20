"""
GUI panel for importing MIDAS scenarios into SAlly.

Provides a ttkbootstrap-based panel that lets operators:
  1. Browse for MIDAS ``.yml`` files or scan default directories.
  2. Preview the parsed scenario (simulators, entities, connections).
  3. Override duration and step size before import.
  4. Import into the :class:`SimulationBuilder` and open in the scenario editor.

Designed to be embedded in the SCADA main window sidebar and styled
consistently with the existing ``SetpointPanel`` and ``AppliedSetpointsPanel``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

import ttkbootstrap as bstrap
from ttkbootstrap.constants import (
    BOTH,
    HORIZONTAL,
    LEFT,
    RIGHT,
    X,
    Y,
    PRIMARY,
    SECONDARY,
    SUCCESS,
    INFO,
    WARNING,
)

logger = logging.getLogger(__name__)


class MidasImportPanel(ttk.LabelFrame):
    """
    Collapsible panel for MIDAS scenario discovery, preview, and import.

    The panel adapts its layout to the sidebar width of the SCADA main
    window and publishes an ``on_import`` callback so the host can wire it
    into the :class:`SCADAOrchestrationService`.

    Parameters
    ----------
    parent:
        Tk parent widget.
    on_import:
        ``(gui_dict, builder) -> None`` — called after a successful import.
    on_mode_change:
        ``(mode: str) -> None`` — called when the user changes the
        simulation-mode dropdown (``"hdf5"`` | ``"midas"`` | ``"timescale"``).
    initial_mode:
        The simulation mode to pre-select (read from ``config.simulation.simulation_mode``).
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_import: Optional[Callable[[Dict[str, Any], Any], None]] = None,
        on_mode_change: Optional[Callable[[str], None]] = None,
        initial_mode: str = "hdf5",
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, text="Simulation Source", padding=8, **kwargs)
        self._on_import = on_import
        self._on_mode_change = on_mode_change
        self._adapter: Optional[Any] = None  # lazy init
        self._current_preview: Optional[Dict[str, Any]] = None
        self._scenarios: List[Dict[str, Any]] = []

        # --- Mode selector (shared across all modes) ---
        self._mode_var = tk.StringVar(value=initial_mode)
        self._build_ui()

    # ── Lazy adapter ─────────────────────────────────────────────────────

    @property
    def adapter(self) -> "MidasSimulationAdapter":
        if self._adapter is None:
            from sally.application.simulation.midas import MidasSimulationAdapter

            self._adapter = MidasSimulationAdapter()
        return self._adapter

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # ---------- Simulation Mode row ----------
        mode_frame = ttk.Frame(self)
        mode_frame.pack(fill=X, pady=(0, 6))

        ttk.Label(mode_frame, text="Mode", font=("-size", 10)).pack(
            side=LEFT, padx=(0, 6)
        )
        mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self._mode_var,
            values=["hdf5", "midas", "timescale"],
            state="readonly",
            width=12,
        )
        mode_combo.pack(side=LEFT, fill=X, expand=True)
        mode_combo.bind("<<ComboboxSelected>>", self._on_mode_selected)

        # ---------- MIDAS-specific controls ----------
        # These are shown/hidden depending on the selected mode.
        self._midas_frame = ttk.Frame(self)

        # File row
        file_row = ttk.Frame(self._midas_frame)
        file_row.pack(fill=X, pady=(4, 2))
        self._path_var = tk.StringVar()
        ttk.Entry(file_row, textvariable=self._path_var).pack(
            side=LEFT, fill=X, expand=True, padx=(0, 4)
        )
        bstrap.Button(
            file_row,
            text="Browse…",
            bootstyle=SECONDARY,
            command=self._browse,
            width=8,
        ).pack(side=LEFT)

        # Scan button
        bstrap.Button(
            self._midas_frame,
            text="Scan MIDAS Defaults",
            bootstyle=INFO,
            command=self._scan_defaults,
        ).pack(fill=X, pady=(2, 4))

        # Scenario list
        list_container = ttk.Frame(self._midas_frame)
        list_container.pack(fill=BOTH, expand=True, pady=2)

        columns = ("name", "dur", "sims")
        self._tree = ttk.Treeview(
            list_container, columns=columns, show="headings", height=4
        )
        self._tree.heading("name", text="Scenario")
        self._tree.heading("dur", text="Duration")
        self._tree.heading("sims", text="Sims")
        self._tree.column("name", width=110, anchor=tk.W)
        self._tree.column("dur", width=60, anchor=tk.CENTER)
        self._tree.column("sims", width=40, anchor=tk.CENTER)
        self._tree.pack(side=LEFT, fill=BOTH, expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        tree_scroll = ttk.Scrollbar(
            list_container, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=RIGHT, fill=Y)

        # Override row
        override_frame = ttk.Frame(self._midas_frame)
        override_frame.pack(fill=X, pady=2)

        ttk.Label(override_frame, text="Dur (s)").grid(row=0, column=0, padx=2)
        self._duration_var = tk.StringVar()
        ttk.Entry(override_frame, textvariable=self._duration_var, width=8).grid(
            row=0, column=1, padx=2
        )
        ttk.Label(override_frame, text="Step (s)").grid(row=0, column=2, padx=2)
        self._step_var = tk.StringVar()
        ttk.Entry(override_frame, textvariable=self._step_var, width=8).grid(
            row=0, column=3, padx=2
        )
        override_frame.columnconfigure(1, weight=1)
        override_frame.columnconfigure(3, weight=1)

        # Preview text
        self._preview_text = tk.Text(
            self._midas_frame, height=6, wrap=tk.WORD, state=tk.DISABLED,
            font=("Consolas", 8),
        )
        self._preview_text.pack(fill=BOTH, expand=True, pady=2)

        # Action buttons
        btn_frame = ttk.Frame(self._midas_frame)
        btn_frame.pack(fill=X, pady=(4, 0))
        bstrap.Button(
            btn_frame, text="Preview", bootstyle=SECONDARY, command=self._preview
        ).pack(side=LEFT, padx=(0, 4))
        bstrap.Button(
            btn_frame,
            text="Import to SAlly",
            bootstyle=SUCCESS,
            command=self._import,
        ).pack(side=LEFT, padx=(0, 4))
        bstrap.Button(
            btn_frame, text="Import & Run", bootstyle=PRIMARY, command=self._import_and_run
        ).pack(side=LEFT)

        # ---------- Status label (always visible) ----------
        self._status_var = tk.StringVar(value="")
        self._status_label = ttk.Label(
            self, textvariable=self._status_var, font=("-size", 8),
            wraplength=280,
        )
        self._status_label.pack(fill=X, pady=(4, 0))

        # Show/hide the midas frame based on initial mode
        self._toggle_midas_frame()

    # ── Mode handling ────────────────────────────────────────────────────

    def _on_mode_selected(self, _event: Any) -> None:
        mode = self._mode_var.get()
        self._toggle_midas_frame()
        if self._on_mode_change:
            self._on_mode_change(mode)
        self._status_var.set(f"Simulation mode → {mode}")

    def _toggle_midas_frame(self) -> None:
        """Show the MIDAS controls only when mode == 'midas'."""
        if self._mode_var.get() == "midas":
            self._midas_frame.pack(fill=BOTH, expand=True, before=self._status_label)
        else:
            self._midas_frame.pack_forget()

    def get_mode(self) -> str:
        """Return the currently selected simulation mode."""
        return self._mode_var.get()

    def set_mode(self, mode: str) -> None:
        """Programmatically change the selected mode."""
        if mode in ("hdf5", "midas", "timescale"):
            self._mode_var.set(mode)
            self._toggle_midas_frame()

    # ── MIDAS actions ────────────────────────────────────────────────────

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select MIDAS Scenario",
            filetypes=[("YAML files", "*.yml *.yaml"), ("All files", "*.*")],
        )
        if path:
            self._path_var.set(path)
            self._load_single(path)

    def _scan_defaults(self) -> None:
        try:
            self._scenarios = self.adapter.list_available_scenarios()
            self._populate_tree()
            self._status_var.set(f"Found {len(self._scenarios)} MIDAS scenarios")
        except ImportError:
            messagebox.showwarning(
                "MIDAS not found",
                "Could not import midas.scenario.default_scenarios.\n"
                "Make sure MIDAS is installed in the current environment.",
            )
        except Exception as exc:
            messagebox.showerror("Scan Error", str(exc))

    def _load_single(self, path: str) -> None:
        try:
            scenario = self.adapter.parse(path)
            mapped = self.adapter.map(scenario)
            info = {
                "name": scenario.name,
                "path": path,
                "duration": scenario.duration,
                "step_size": scenario.step_size,
                "simulator_count": len(scenario.simulators),
                "entity_count": len(scenario.entities),
            }
            self._scenarios = [info]
            self._populate_tree()
            self._duration_var.set(str(scenario.duration))
            self._step_var.set(str(scenario.step_size))
            self._show_preview(self.adapter.to_gui_dict(mapped))
            self._status_var.set(f"Loaded: {scenario.name}")
        except Exception as exc:
            messagebox.showerror("Parse Error", str(exc))

    def _populate_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for sc in self._scenarios:
            self._tree.insert(
                "",
                tk.END,
                values=(
                    sc["name"],
                    sc.get("duration", "?"),
                    sc.get("simulator_count", "?"),
                ),
            )

    def _on_tree_select(self, _event: Any) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        idx = self._tree.index(selection[0])
        if idx < len(self._scenarios):
            sc = self._scenarios[idx]
            self._path_var.set(sc.get("path", ""))
            self._duration_var.set(str(sc.get("duration", "")))
            self._step_var.set(str(sc.get("step_size", "")))

    def _preview(self) -> None:
        path = self._path_var.get()
        if not path:
            messagebox.showinfo("No file", "Please select a MIDAS scenario file.")
            return
        try:
            scenario = self.adapter.parse(path)
            mapped = self.adapter.map(scenario)
            gui_dict = self.adapter.to_gui_dict(mapped)
            self._show_preview(gui_dict)
            self._current_preview = gui_dict
        except Exception as exc:
            messagebox.showerror("Preview Error", str(exc))

    def _show_preview(self, gui_dict: Dict[str, Any]) -> None:
        self._preview_text.configure(state=tk.NORMAL)
        self._preview_text.delete("1.0", tk.END)

        lines = [
            f"Scenario: {gui_dict['name']}",
            f"Duration: {gui_dict['duration']}s | Step: {gui_dict['step_size']}s",
            f"Date: {gui_dict.get('start_date', 'N/A')}",
            "",
            "── Simulators ──",
        ]
        for key, sim in gui_dict.get("simulators", {}).items():
            lines.append(f"  {key}: {sim['class']} (Δt={sim['step_size']}s)")
        lines.append("")
        lines.append("── Entities ──")
        for ent in gui_dict.get("entities", []):
            lines.append(
                f"  {ent['sim_key']}.{ent.get('entity_id', '*')}: "
                f"{ent['model']} ×{ent['count']}"
            )
        conns = gui_dict.get("connections", [])
        lines.append("")
        lines.append(f"── Connections ({len(conns)}) ──")
        for conn in conns[:10]:
            lines.append(f"  {conn['src']} → {conn['dst']}")
        if len(conns) > 10:
            lines.append(f"  … +{len(conns) - 10} more")

        self._preview_text.insert("1.0", "\n".join(lines))
        self._preview_text.configure(state=tk.DISABLED)
        self._current_preview = gui_dict

    def _import(self) -> None:
        import datetime
        import tempfile
        import yaml
        path = self._path_var.get()
        if not path:
            messagebox.showinfo("No file", "Please select a scenario first.")
            return
        try:
            # Determine scenario name from preview or from the file
            scenario_name = None
            if self._current_preview:
                scenario_name = self._current_preview.get("name")

            if not scenario_name:
                # Parse to get the first scenario name
                scenario = self.adapter.parse(path)
                scenario_name = scenario.name

            # Always append unique suffix to avoid duplicate key errors
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_name = f"{scenario_name}_sally_{now_str}"

            # Load YAML, replace top-level key, write to temp file
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict) or len(data) != 1:
                raise ValueError("Scenario YAML must have exactly one top-level key.")
            orig_key = next(iter(data))
            scenario_dict = data[orig_key]
            new_data = {unique_name: scenario_dict}
            with tempfile.NamedTemporaryFile('w', delete=False, suffix='.yml', encoding='utf-8') as tf:
                yaml.safe_dump(new_data, tf, sort_keys=False)
                temp_path = tf.name

            override_duration = (
                int(self._duration_var.get()) if self._duration_var.get() else None
            )

            params = {}
            if override_duration:
                params["end"] = override_duration

            override_step = (
                int(self._step_var.get()) if self._step_var.get() else None
            )
            if override_step:
                params["step_size"] = override_step

            # Run via native MIDAS API with temp YAML
            self.adapter.run_scenario(
                unique_name,
                config=temp_path,
                params=params if params else None,
                no_run=True,  # configure + build only for import
            )

            scenario = self.adapter.parse(temp_path)
            mapped = self.adapter.map(scenario)
            gui_dict = self.adapter.to_gui_dict(mapped)

            if self._on_import:
                self._on_import(gui_dict, None)

            self._status_var.set(
                f"✓ Imported '{mapped.name}' — "
                f"{len(mapped.simulators)} sims, {len(mapped.entities)} entities"
            )
        except Exception as exc:
            logger.exception("Import failed")
            messagebox.showerror("Import Error", str(exc))

    def _import_and_run(self) -> None:
        import datetime
        import tempfile
        import yaml
        path = self._path_var.get()
        if not path:
            messagebox.showinfo("No file", "Please select a scenario first.")
            return
        try:
            scenario_name = None
            if self._current_preview:
                scenario_name = self._current_preview.get("name")

            if not scenario_name:
                scenario = self.adapter.parse(path)
                scenario_name = scenario.name

            # Always append unique suffix to avoid duplicate key errors
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_name = f"{scenario_name}_sally_{now_str}"

            # Load YAML, replace top-level key, write to temp file
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict) or len(data) != 1:
                raise ValueError("Scenario YAML must have exactly one top-level key.")
            orig_key = next(iter(data))
            scenario_dict = data[orig_key]
            new_data = {unique_name: scenario_dict}
            with tempfile.NamedTemporaryFile('w', delete=False, suffix='.yml', encoding='utf-8') as tf:
                yaml.safe_dump(new_data, tf, sort_keys=False)
                temp_path = tf.name

            override_duration = (
                int(self._duration_var.get()) if self._duration_var.get() else None
            )

            params = {}
            if override_duration:
                params["end"] = override_duration

            override_step = (
                int(self._step_var.get()) if self._step_var.get() else None
            )
            if override_step:
                params["step_size"] = override_step

            self.adapter.run_scenario(
                unique_name,
                config=temp_path,
                params=params if params else None,
            )
            self._status_var.set(f"✓ Run complete: {unique_name}")
        except Exception as exc:
            logger.exception("Run failed")
            messagebox.showerror("Run Error", str(exc))

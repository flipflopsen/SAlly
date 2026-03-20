"""
Applied Setpoints Panel

Displays a table of currently active setpoints with the ability to
deactivate individual setpoints via checkboxes.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Tuple

import ttkbootstrap as bstrap
from ttkbootstrap.constants import BOTH, X


class AppliedSetpointsPanel(ttk.LabelFrame):
    """Panel showing active setpoints with toggle functionality."""

    def __init__(
        self,
        master,
        on_toggle_setpoint: Callable[[str, str, bool], None],
        *args,
        **kwargs
    ):
        """
        Args:
            master: Parent widget
            on_toggle_setpoint: Callback(entity, variable, active) when checkbox toggled
        """
        super().__init__(master, text="Applied Setpoints", padding=8, *args, **kwargs)
        self._on_toggle = on_toggle_setpoint

        # Track setpoints: key -> (entity, variable, value, active)
        self._setpoints: Dict[str, Tuple[str, str, float, bool]] = {}
        # Track checkbox variables
        self._check_vars: Dict[str, tk.BooleanVar] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        # Create Treeview with columns
        columns = ("entity", "variable", "value", "active")
        self._tree = ttk.Treeview(
            self,
            columns=columns,
            show="headings",
            height=6,
            selectmode="browse"
        )

        # Configure columns
        self._tree.heading("entity", text="Entity")
        self._tree.heading("variable", text="Variable")
        self._tree.heading("value", text="Value")
        self._tree.heading("active", text="Active")

        self._tree.column("entity", width=120, minwidth=80)
        self._tree.column("variable", width=80, minwidth=60)
        self._tree.column("value", width=70, minwidth=50)
        self._tree.column("active", width=50, minwidth=40, anchor="center")

        # Add scrollbar
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        # Pack widgets
        self._tree.pack(side="left", fill=BOTH, expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind click event for toggling
        self._tree.bind("<ButtonRelease-1>", self._on_click)
        self._tree.bind("<Double-1>", self._on_double_click)

        # Style for active/inactive rows
        self._tree.tag_configure("active", background="#1a472a", foreground="#ffffff")
        self._tree.tag_configure("inactive", background="#4a4a4a", foreground="#888888")

    def _on_click(self, event) -> None:
        """Handle single click - check if it's on the Active column."""
        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self._tree.identify_column(event.x)
        # Column #4 is the "active" column
        if column != "#4":
            return

        item = self._tree.identify_row(event.y)
        if not item:
            return

        self._toggle_item(item)

    def _on_double_click(self, event) -> None:
        """Handle double-click to toggle active state."""
        item = self._tree.identify_row(event.y)
        if item:
            self._toggle_item(item)

    def _toggle_item(self, item: str) -> None:
        """Toggle the active state of a setpoint."""
        if item not in self._setpoints:
            return

        entity, variable, value, active = self._setpoints[item]
        new_active = not active
        self._setpoints[item] = (entity, variable, value, new_active)

        # Update display
        active_text = "✓" if new_active else "✗"
        tag = "active" if new_active else "inactive"
        self._tree.item(item, values=(entity, variable, f"{value:.4f}", active_text), tags=(tag,))

        # Notify callback
        self._on_toggle(entity, variable, new_active)

    def update_setpoints(self, setpoints: Dict[str, float]) -> None:
        """
        Update the displayed setpoints from state.

        Args:
            setpoints: Dict of "entity.variable" -> value
        """
        # Build set of current keys
        current_keys = set()

        for key, value in setpoints.items():
            # Parse key using rsplit to handle entity names with dots
            parts = key.rsplit(".", 1)
            if len(parts) != 2:
                continue
            entity, variable = parts
            current_keys.add(key)

            if key in self._setpoints:
                # Update existing - preserve active state
                _, _, _, active = self._setpoints[key]
                self._setpoints[key] = (entity, variable, value, active)
                active_text = "✓" if active else "✗"
                tag = "active" if active else "inactive"
                self._tree.item(key, values=(entity, variable, f"{value:.4f}", active_text), tags=(tag,))
            else:
                # New setpoint - default to active
                self._setpoints[key] = (entity, variable, value, True)
                self._tree.insert(
                    "",
                    "end",
                    iid=key,
                    values=(entity, variable, f"{value:.4f}", "✓"),
                    tags=("active",)
                )

        # Remove setpoints that are no longer in state
        keys_to_remove = set(self._setpoints.keys()) - current_keys
        for key in keys_to_remove:
            if self._tree.exists(key):
                self._tree.delete(key)
            del self._setpoints[key]

    def get_active_setpoints(self) -> Dict[str, float]:
        """Return only the active setpoints."""
        return {
            key: data[2]  # value is at index 2
            for key, data in self._setpoints.items()
            if data[3]  # active is at index 3
        }

    def clear(self) -> None:
        """Clear all setpoints from the panel."""
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._setpoints.clear()

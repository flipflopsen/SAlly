from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List

import ttkbootstrap as bstrap
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, X, PRIMARY, SECONDARY


class SetpointPanel(ttk.Frame):
    def __init__(
        self,
        master,
        on_apply: Callable[[str, str, float], None],
        on_reset: Callable[[], None],
        get_variables_for_entity: Callable[[str], List[str]] | None = None,
        *args,
        **kwargs
    ):
        super().__init__(master, *args, **kwargs)
        self._on_apply = on_apply
        self._on_reset = on_reset
        self._get_variables_for_entity = get_variables_for_entity

        self.entity_var = tk.StringVar()
        self.variable_var = tk.StringVar()
        self.value_var = tk.StringVar()

        ttk.Label(self, text="Setpoints", font=("-size", 14)).pack(anchor="w", padx=5, pady=(0, 10))

        form = ttk.Frame(self)
        form.pack(fill=X)

        ttk.Label(form, text="Entity").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self.entity_combo = ttk.Combobox(form, textvariable=self.entity_var, state="readonly")
        self.entity_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=4)
        self.entity_combo.bind("<<ComboboxSelected>>", self._on_entity_selected)

        ttk.Label(form, text="Variable").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        self.variable_combo = ttk.Combobox(form, textvariable=self.variable_var, state="readonly")
        self.variable_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=4)

        ttk.Label(form, text="Value").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        self.value_entry = ttk.Entry(form, textvariable=self.value_var)
        self.value_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=4)

        form.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill=X, pady=10)
        bstrap.Button(button_frame, text="Apply Setpoint", bootstyle=PRIMARY, command=self._apply).pack(
            side=LEFT, padx=5
        )
        bstrap.Button(button_frame, text="Reset All", bootstyle=SECONDARY, command=self._on_reset).pack(
            side=LEFT, padx=5
        )

    def update_entities(self, entity_names: List[str]) -> None:
        self.entity_combo["values"] = entity_names
        if entity_names:
            self.entity_combo.current(0)
            self._on_entity_selected(None)

    def update_variables(self, variables: List[str]) -> None:
        self.variable_combo["values"] = variables
        if variables:
            self.variable_combo.current(0)

    def _on_entity_selected(self, _event):
        selected = self.entity_var.get()
        if selected and self._get_variables_for_entity:
            variables = self._get_variables_for_entity(selected)
            self.update_variables(variables)

    def _apply(self):
        entity = self.entity_var.get()
        variable = self.variable_var.get()
        try:
            value = float(self.value_var.get())
        except ValueError:
            return
        if entity and variable:
            self._on_apply(entity, variable, value)

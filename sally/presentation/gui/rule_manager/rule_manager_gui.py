import tkinter as tk
from tkinter import ttk, filedialog
import ttkbootstrap as bstrap
from ttkbootstrap.tableview import Tableview
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
import json
import uuid
import time

from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager
from sally.core.mosaik_hdf5_parser import HDF5Parser
from sally.infrastructure.services.rule_manager_sync_service import RuleManagerSyncService
from sally.core.event_bus import EventBus


OPERATORS = ["IS", "IS_NOT", "CONTAINS", "STARTS_WITH", "ENDS_WITH", "GREATER_THAN", "LESS_THAN", "EQUALS", "MATCHES_REGEX"]
LOGIC_OPERATORS = ["NONE", "AND", "OR", "XOR", "NAND"]

class RuleManagerApp(ttk.Frame):
    def __init__(self, master, event_bus: EventBus | None = None, rule_manager: SmartGridRuleManager | None = None):
        super().__init__(master)
        self._window = master

        self.rules_data = []
        self.current_edit_rule_id = None

        # State variables for Chaining Logic
        self.chain_context = {
            "active": False,
            "prev_id": None,
            "group": None
        }

        self.hdf5_parser = HDF5Parser()
        self.discovered_entity_to_variables_map = {}
        self.smartgrid_rule_manager = rule_manager or SmartGridRuleManager()
        self.existing_groups = set(["Default"])
        self.event_bus = event_bus
        self._sync_service = None
        self._sync_active = False
        self._sync_status_var = tk.StringVar(value="Disconnected")

        self._setup_ui()
        self._update_entity_names_combobox(list(self.discovered_entity_to_variables_map.keys()))

    def _setup_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)

        top_control_frame = ttk.Frame(main_frame)
        top_control_frame.pack(fill=X, pady=(0, 10))

        control_frame = ControlFrame(top_control_frame, app_commands=self, sync_status_var=self._sync_status_var)
        control_frame.pack(side=LEFT, fill=X, expand=False)

        hdf5_button = bstrap.Button(top_control_frame, text="Load HDF5",
                                    command=self._load_and_discover_from_hdf5, bootstyle=(INFO, OUTLINE))
        hdf5_button.pack(side=LEFT, padx=10)

        paned_window = ttk.PanedWindow(main_frame, orient=HORIZONTAL)
        paned_window.pack(fill=BOTH, expand=YES)

        # Rule Creator Frame
        creator_pane = ttk.Frame(paned_window, padding=10)
        initial_entity_names = list(self.discovered_entity_to_variables_map.keys())
        self.rule_creator_frame = RuleCreatorFrame(creator_pane, app_commands=self,
                                                   initial_entity_names=initial_entity_names,
                                                   operators_list=OPERATORS,
                                                   logic_list=LOGIC_OPERATORS)
        self.rule_creator_frame.pack(fill=BOTH, expand=YES)
        paned_window.add(creator_pane, weight=1)

        # Rules View Frame
        view_pane = ttk.Frame(paned_window, padding=10)
        self.rules_view_frame = RulesViewFrame(view_pane, app_commands=self)
        self.rules_view_frame.pack(fill=BOTH, expand=YES)
        paned_window.add(view_pane, weight=3)

    def _load_and_discover_from_hdf5(self):
        filepath = filedialog.askopenfilename(filetypes=[("HDF5 files", "*.hdf5;*.h5"), ("All files", "*.*")])
        if not filepath: return
        self.discovered_entity_to_variables_map = self.hdf5_parser.discover_structure_from_file(filepath)
        entity_names = sorted(list(self.discovered_entity_to_variables_map.keys()))
        self._update_entity_names_combobox(entity_names)

    def _update_entity_names_combobox(self, entity_names_list):
        if hasattr(self, 'rule_creator_frame') and self.rule_creator_frame:
            self.rule_creator_frame.update_entity_names_dropdown(entity_names_list)

    def get_variables_for_entity(self, entity_name: str) -> list:
        return self.discovered_entity_to_variables_map.get(entity_name, [])

    def get_existing_groups(self) -> list:
        return sorted(list(self.existing_groups))

    def get_rules_in_group(self, group_name):
        return [r["id"] for r in self.rules_data if r.get("group", "Default") == group_name]

    # --- CORE LOGIC START ---

    def add_rule(self, entity_name, variable_name, operator, value, action, is_active, group, logic_op, linked_rule_id):
        if not all([entity_name, variable_name, operator, action]):
            Messagebox.show_error("Input Error", "Entity, Variable, Operator, and Action are mandatory.")
            return

        if not group or group.strip() == "": group = "Default"
        self.existing_groups.add(group)
        self.rule_creator_frame.update_group_dropdown()

        # Build Rule Dict
        new_id = str(uuid.uuid4())[:8]
        gui_rule_dict = {
            "entity_name": entity_name,
            "variable_name": variable_name,
            "operator": operator,
            "value": value,
            "action": action,
            "active": is_active,
            "group": group,
            "logic_op": logic_op,
            "linked_rule_id": linked_rule_id
        }

        # UPDATE EXISTING RULE
        if self.current_edit_rule_id:
            gui_rule_dict["id"] = self.current_edit_rule_id
            for i, r_gui in enumerate(self.rules_data):
                if r_gui.get("id") == self.current_edit_rule_id:
                    self.rules_data[i] = gui_rule_dict
                    break

            self.rules_view_frame.refresh_tree(self.rules_data)
            self.smartgrid_rule_manager.load_rules(self.rules_data)
            Messagebox.show_info("Update Rule", "Rule updated successfully.")

            # FULL RESET after Update (as requested)
            self.reset_to_add_mode_completely()

        # ADD NEW RULE
        else:
            gui_rule_dict["id"] = new_id
            self.rules_data.append(gui_rule_dict)
            self.rules_view_frame.refresh_tree(self.rules_data)
            self.smartgrid_rule_manager.add_rule(gui_rule_dict)

            # HANDLE CHAINING LOGIC
            if logic_op != "NONE":
                # Enable chaining for the NEXT rule
                self.chain_context["active"] = True
                self.chain_context["prev_id"] = new_id
                self.chain_context["group"] = group
                # Partial reset: Keep group, show linked ID
                self.rule_creator_frame.reset_fields_for_next_in_chain(group, new_id)
            else:
                # No logic, full reset
                self.chain_context["active"] = False
                self.reset_to_add_mode_completely()

    def reset_to_add_mode_completely(self):
        """Resets everything to default 'Add Rule' state."""
        self.current_edit_rule_id = None
        self.chain_context["active"] = False
        self.rule_creator_frame.full_reset()

    # --- CORE LOGIC END ---

    def toggle_rule_active_state(self, rule_id):
        for rule in self.rules_data:
            if rule["id"] == rule_id:
                rule["active"] = not rule.get("active", True)
                self.rules_view_frame.refresh_tree(self.rules_data)
                self.smartgrid_rule_manager.load_rules(self.rules_data)
                return

    def populate_editor(self, rule_dict):
        self.current_edit_rule_id = rule_dict["id"]
        self.chain_context["active"] = False # Editing breaks the previous chain context
        self.rule_creator_frame.populate_inputs(rule_dict)

    def save_rules(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if filepath:
            with open(filepath, 'w') as f: json.dump(self.rules_data, f, indent=4)
            Messagebox.show_info("Saved", "Rules saved successfully!")

    def load_rules(self):
        filepath = filedialog.askopenfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if filepath:
            with open(filepath, 'r') as f:
                self.rules_data = json.load(f)
                for r in self.rules_data: self.existing_groups.add(r.get("group", "Default"))
            self.rules_view_frame.refresh_tree(self.rules_data)
            self.smartgrid_rule_manager.load_rules(self.rules_data)
            self.reset_to_add_mode_completely()

    def sync_with_simulation(self):
        if not self.event_bus:
            Messagebox.show_error("Synchronization", "No EventBus provided for synchronization.")
            return
        if self._sync_active:
            return
        self._sync_service = RuleManagerSyncService(history_seconds=30)
        self.event_bus.subscribe(self._sync_service)
        self._sync_active = True
        self._sync_status_var.set("Connected")
        self._poll_triggered_rules()

    def disconnect_sync(self):
        if self.event_bus and self._sync_service:
            self.event_bus.unsubscribe(self._sync_service)
        self._sync_service = None
        self._sync_active = False
        self._sync_status_var.set("Disconnected")
        self.rules_view_frame.refresh_tree(self.rules_data)

    def _poll_triggered_rules(self):
        if not self._sync_active or not self._sync_service:
            return
        triggered_ids = self._sync_service.get_recent_triggered_rule_ids()
        self.rules_view_frame.refresh_tree(self.rules_data, triggered_rule_ids=triggered_ids)
        self.after(500, self._poll_triggered_rules)

class ControlFrame(ttk.Frame):
    def __init__(self, master, app_commands, sync_status_var, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        bstrap.Button(self, text="Save", command=app_commands.save_rules, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        bstrap.Button(self, text="Load", command=app_commands.load_rules, bootstyle=INFO).pack(side=LEFT, padx=5)
        bstrap.Button(self, text="Synchronize", command=app_commands.sync_with_simulation, bootstyle=PRIMARY).pack(side=LEFT, padx=5)
        bstrap.Button(self, text="Disconnect", command=app_commands.disconnect_sync, bootstyle=SECONDARY).pack(side=LEFT, padx=5)
        ttk.Label(self, textvariable=sync_status_var).pack(side=LEFT, padx=10)

class RuleCreatorFrame(ttk.Frame):
    def __init__(self, master, app_commands, initial_entity_names, operators_list, logic_list, *args, **kwargs):
        super().__init__(master, padding=15, *args, **kwargs)
        self.app_commands = app_commands
        self.operators_list = operators_list
        self.logic_list = logic_list

        ttk.Label(self, text="Rule Editor", font=("-size", 16)).grid(row=0, column=0, columnspan=2, pady=(0, 15), sticky=W)

        # 1. Group
        ttk.Label(self, text="Group:").grid(row=1, column=0, sticky=W, padx=5, pady=5)
        self.group_var = tk.StringVar()
        self.group_combo = ttk.Combobox(self, textvariable=self.group_var)
        self.group_combo.grid(row=1, column=1, sticky=EW, padx=5, pady=5)
        self.group_combo.bind("<<ComboboxSelected>>", self._on_group_selected)
        self.group_combo.bind("<KeyRelease>", self._on_group_selected)

        # 2. Entity
        ttk.Label(self, text="Entity Name:").grid(row=2, column=0, sticky=W, padx=5, pady=5)
        self.entity_name_var = tk.StringVar()
        self.entity_name_combo = ttk.Combobox(self, textvariable=self.entity_name_var, values=initial_entity_names, state="readonly")
        self.entity_name_combo.grid(row=2, column=1, sticky=EW, padx=5, pady=5)
        self.entity_name_combo.bind("<<ComboboxSelected>>", self._on_entity_selected)

        # 3. Variable
        ttk.Label(self, text="Variable Name:").grid(row=3, column=0, sticky=W, padx=5, pady=5)
        self.variable_name_var = tk.StringVar()
        self.variable_name_combo = ttk.Combobox(self, textvariable=self.variable_name_var, state="readonly")
        self.variable_name_combo.grid(row=3, column=1, sticky=EW, padx=5, pady=5)

        # 4. Operator
        ttk.Label(self, text="Operator:").grid(row=4, column=0, sticky=W, padx=5, pady=5)
        self.operator_var = tk.StringVar()
        self.operator_combo = ttk.Combobox(self, textvariable=self.operator_var, values=self.operators_list, state="readonly")
        self.operator_combo.grid(row=4, column=1, sticky=EW, padx=5, pady=5)
        if self.operators_list: self.operator_combo.current(0)

        # 5. Value
        ttk.Label(self, text="Value:").grid(row=5, column=0, sticky=W, padx=5, pady=5)
        self.value_var = tk.StringVar()
        self.value_entry = ttk.Entry(self, textvariable=self.value_var)
        self.value_entry.grid(row=5, column=1, sticky=EW, padx=5, pady=5)

        # 6. Action
        ttk.Label(self, text="Action:").grid(row=6, column=0, sticky=W, padx=5, pady=5)
        self.action_var = tk.StringVar()
        self.action_entry = ttk.Entry(self, textvariable=self.action_var)
        self.action_entry.grid(row=6, column=1, sticky=EW, padx=5, pady=5)

        # 7. Logic Operator
        ttk.Label(self, text="Logic w/ Next:").grid(row=7, column=0, sticky=W, padx=5, pady=5)
        self.logic_var = tk.StringVar(value="NONE")
        self.logic_combo = ttk.Combobox(self, textvariable=self.logic_var, values=self.logic_list, state="readonly")
        self.logic_combo.grid(row=7, column=1, sticky=EW, padx=5, pady=5)

        # 8. Linked Rule ID (Evaluated Field)
        self.lbl_linked = ttk.Label(self, text="Linked Rule ID:")
        self.linked_rule_var = tk.StringVar()
        self.linked_rule_combo = ttk.Combobox(self, textvariable=self.linked_rule_var, state="readonly")

        # 9. Active
        self.active_var = tk.BooleanVar(value=True)
        self.active_chk = ttk.Checkbutton(self, text="Rule Active", variable=self.active_var, bootstyle="round-toggle")
        self.active_chk.grid(row=9, column=1, sticky=W, padx=5, pady=10)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=10, column=0, columnspan=2, pady=20)
        self.add_update_button_text = tk.StringVar(value="Add Rule")
        self.add_update_button = bstrap.Button(btn_frame, textvariable=self.add_update_button_text,
                                               command=self._on_add_or_update, bootstyle=PRIMARY)
        self.add_update_button.pack(side=LEFT, padx=5)

        # Cancel Button to exit Edit Mode
        bstrap.Button(btn_frame, text="Cancel / New", command=self.app_commands.reset_to_add_mode_completely,
                      bootstyle=SECONDARY).pack(side=LEFT, padx=5)

        self.columnconfigure(1, weight=1)
        self.update_group_dropdown()
        self._set_linked_visibility(False) # Default Hidden

    def _on_entity_selected(self, event):
        entity = self.entity_name_var.get()
        if entity:
            vars_list = self.app_commands.get_variables_for_entity(entity)
            self.update_variable_names_dropdown(vars_list)
        else:
            self.update_variable_names_dropdown([])

    def _on_group_selected(self, event):
        """If user changes group, check if we need to hide the linked ID (break chain)."""
        current_group = self.group_var.get()
        chain_ctx = self.app_commands.chain_context

        if chain_ctx["active"]:
            if current_group == chain_ctx["group"]:
                # Match: Show linking to previous rule
                self._set_linked_visibility(True)
                self._refresh_linked_rule_options(pre_select_id=chain_ctx["prev_id"])
            else:
                # Mismatch: Hide linking
                self._set_linked_visibility(False)
                self.linked_rule_var.set("")
        else:
            # If not chaining, ensure hidden
            self._set_linked_visibility(False)

    def _set_linked_visibility(self, visible):
        if visible:
            self.lbl_linked.grid(row=8, column=0, sticky=W, padx=5, pady=5)
            self.linked_rule_combo.grid(row=8, column=1, sticky=EW, padx=5, pady=5)
        else:
            self.lbl_linked.grid_remove()
            self.linked_rule_combo.grid_remove()

    def _refresh_linked_rule_options(self, pre_select_id=None):
        current_group = self.group_var.get()
        rule_ids = self.app_commands.get_rules_in_group(current_group)
        self.linked_rule_combo['values'] = rule_ids
        if pre_select_id and pre_select_id in rule_ids:
            self.linked_rule_var.set(pre_select_id)
        elif rule_ids:
            self.linked_rule_var.set(rule_ids[-1]) # Default to last added

    def _on_add_or_update(self):
        self.app_commands.add_rule(
            self.entity_name_var.get(),
            self.variable_name_var.get(),
            self.operator_var.get(),
            self.value_var.get(),
            self.action_var.get(),
            self.active_var.get(),
            self.group_var.get(),
            self.logic_var.get(),
            self.linked_rule_var.get()
        )

    # --- RESET LOGIC ---

    def full_reset(self):
        """Clears EVERYTHING. Used after Update or Cancel."""
        self._clear_definitions()
        self.logic_var.set("NONE")
        self.active_var.set(True)
        self.linked_rule_var.set("")
        self._set_linked_visibility(False)
        self.add_update_button_text.set("Add Rule")
        # Do not clear group, usually user stays in group.
        # But for 'Update' specifically prompt requested reset:
        # "fields... should reset to default/empty values" (Ambiguous if Group resets, keeping it safe)

    def reset_fields_for_next_in_chain(self, group, prev_id):
        """Called when a rule with Logic was added. Keep Group, Show LinkedID."""
        self._clear_definitions()
        self.logic_var.set("NONE")
        self.active_var.set(True)
        self.group_var.set(group)

        # Show Linked ID
        self._set_linked_visibility(True)
        self._refresh_linked_rule_options(pre_select_id=prev_id)
        self.add_update_button_text.set("Add Rule")

    def _clear_definitions(self):
        """Internal helper to clear the main data entry fields."""
        if self.entity_name_combo['values']:
            self.entity_name_combo.current(0)
            self._on_entity_selected(None)
        self.operator_combo.current(0)
        self.value_var.set("")
        self.action_var.set("")

    # --- EDIT POPULATE ---
    def populate_inputs(self, rule_dict):
        self.entity_name_var.set(rule_dict.get("entity_name", ""))
        self._on_entity_selected(None)
        self.variable_name_var.set(rule_dict.get("variable_name", ""))
        self.operator_var.set(rule_dict.get("operator", ""))
        self.value_var.set(rule_dict.get("value", ""))
        self.action_var.set(rule_dict.get("action", ""))
        self.group_var.set(rule_dict.get("group", "Default"))
        self.logic_var.set(rule_dict.get("logic_op", "NONE"))
        self.active_var.set(rule_dict.get("active", True))

        # Logic for linked_rule_id visibility in Edit Mode
        lid = rule_dict.get("linked_rule_id", "")
        self.linked_rule_var.set(lid)

        # If this rule HAS a link, we show the field so they can see/edit it
        if lid:
            self._set_linked_visibility(True)
            self._refresh_linked_rule_options(pre_select_id=lid)
        else:
            self._set_linked_visibility(False)

        self.add_update_button_text.set("Update Rule")

    # ... (Helpers like update_entity_names_dropdown remain the same) ...
    def update_entity_names_dropdown(self, names):
        self.entity_name_combo['values'] = names
        if names:
            self.entity_name_combo.current(0)
            self._on_entity_selected(None)

    def update_variable_names_dropdown(self, names):
        self.variable_name_combo['values'] = names
        if names: self.variable_name_combo.current(0)

    def update_group_dropdown(self):
        groups = self.app_commands.get_existing_groups()
        self.group_combo['values'] = groups
        if not self.group_var.get() and groups: self.group_var.set("Default")

class RulesViewFrame(ttk.Frame):
    def __init__(self, master, app_commands, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.app_commands = app_commands

        header = ttk.Frame(self)
        header.pack(fill=X, pady=(0,5))
        ttk.Label(header, text="Defined Rules", font=("-size", 16)).pack(side=LEFT)

        self.columns = ("active", "id", "entity", "variable", "operator", "value", "action", "logic", "link")
        self.tree = ttk.Treeview(self, columns=self.columns, show="tree headings", selectmode="browse")

        self.tree.heading("#0", text="Group", anchor=W)
        self.tree.heading("active", text="Act", anchor=CENTER)
        self.tree.heading("id", text="ID", anchor=W)
        self.tree.heading("entity", text="Entity", anchor=W)
        self.tree.heading("variable", text="Variable", anchor=W)
        self.tree.heading("operator", text="Operator", anchor=W)
        self.tree.heading("value", text="Value", anchor=W)
        self.tree.heading("action", text="Action", anchor=W)
        self.tree.heading("logic", text="Logic", anchor=CENTER)
        self.tree.heading("link", text="Linked ID", anchor=W)

        self.tree.column("#0", width=120)
        self.tree.column("active", width=40, anchor=CENTER)
        self.tree.column("id", width=60)
        self.tree.column("entity", width=100)
        self.tree.column("variable", width=90)
        self.tree.column("operator", width=90)
        self.tree.column("value", width=70)
        self.tree.column("action", width=70)
        self.tree.column("logic", width=60, anchor=CENTER)
        self.tree.column("link", width=70)

        scrollbar = ttk.Scrollbar(self, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<ButtonRelease-1>", self.on_single_click)

        self.tree.tag_configure("inactive", foreground="gray")
        self.tree.tag_configure("group", font=("", 10, "bold"), foreground="#4db6ac")
        self.tree.tag_configure("triggered", background="#fbc02d", foreground="#000000")

    def refresh_tree(self, rules_data, triggered_rule_ids=None):
        triggered_rule_ids = set(triggered_rule_ids or [])
        self.tree.delete(*self.tree.get_children())
        grouped_rules = {}
        for rule in rules_data:
            g = rule.get("group", "Default")
            if g not in grouped_rules: grouped_rules[g] = []
            grouped_rules[g].append(rule)

        for group_name in sorted(grouped_rules.keys()):
            gid = self.tree.insert("", "end", text=f" {group_name}", open=True, tags=("group",))
            for rule in grouped_rules[group_name]:
                act = "☑" if rule.get("active", True) else "☐"
                tag = "normal" if rule.get("active", True) else "inactive"
                if rule.get("id") in triggered_rule_ids:
                    tag = "triggered"
                vals = (act, rule["id"], rule["entity_name"], rule["variable_name"],
                        rule["operator"], rule["value"], rule["action"],
                        rule.get("logic_op", "NONE"), rule.get("linked_rule_id", ""))
                self.tree.insert(gid, "end", values=vals, tags=(tag,))

    def on_single_click(self, event):
        if self.tree.identify_column(event.x) == "#1":
            iid = self.tree.identify_row(event.y)
            if iid:
                vals = self.tree.item(iid, "values")
                if vals: self.app_commands.toggle_rule_active_state(vals[1])

    def on_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            vals = self.tree.item(iid, "values")
            if vals:
                rule = next((r for r in self.app_commands.rules_data if r["id"] == vals[1]), None)
                if rule: self.app_commands.populate_editor(rule)


def create_gui(event_bus: EventBus | None = None, rule_manager: SmartGridRuleManager | None = None):
    root = bstrap.Window(
        themename="cosmo",
        title="Rule Manager and Creator",
        size=(1680, 850),
        minsize=(1024, 700),
    )
    app = RuleManagerApp(root, event_bus=event_bus, rule_manager=rule_manager)
    app.pack(fill=BOTH, expand=YES)
    root.mainloop()


def create_rule_manager_window(master, event_bus: EventBus | None = None, rule_manager: SmartGridRuleManager | None = None):
    window = bstrap.Toplevel(master)
    window.themename = "cosmo"
    window.title("Rule Manager and Creator")
    window.geometry("1680x850")
    window.minsize(1024, 700)
    app = RuleManagerApp(window, event_bus=event_bus, rule_manager=rule_manager)
    app.pack(fill=BOTH, expand=YES)
    return window, app


if __name__ == "__main__":
    create_gui()

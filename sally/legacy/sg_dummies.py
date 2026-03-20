"""
[LEGACY] Dummy implementations for testing.

!!! WARNING: This module is DEPRECATED !!!
Use sally.application.rule_management.sg_rule and sg_rule_manager instead.

These minimal implementations were used for early testing and prototyping.
They lack the full feature set of the production implementations.

Migration notes:
- DummySmartGridRule -> sally.application.rule_management.sg_rule.SmartGridRule
- DummySmartGridRuleManager -> sally.application.rule_management.sg_rule_manager.SmartGridRuleManager

The production implementations include:
- Full operator support (>, <, >=, <=, ==, !=)
- Rule groups and logic operators (AND/OR chains)
- Active/inactive states
- OTEL instrumentation
"""
import warnings


class DummySmartGridRule:
    """
    [DEPRECATED] Minimal rule for testing simulation.

    Use sally.application.rule_management.sg_rule.SmartGridRule instead.
    """
    def __init__(self, rule_id, entity_name, variable_name, operator, threshold_value, action):
        warnings.warn(
            "DummySmartGridRule is deprecated. Use SmartGridRule instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.rule_id = rule_id
        self.entity_name = entity_name
        self.variable_name = variable_name
        self.operator = operator
        self.threshold_value = threshold_value
        self.action = action

    def evaluate(self, actual_value):
        """Simple evaluation - only supports LESS_THAN."""
        if self.operator == "LESS_THAN" and actual_value is not None:
            return float(actual_value) < float(self.threshold_value)
        if self.operator == "GREATER_THAN" and actual_value is not None:
            return float(actual_value) > float(self.threshold_value)
        if self.operator == "IS" and actual_value is not None:
            return float(actual_value) == float(self.threshold_value)
        return False


class DummySmartGridRuleManager:
    """
    [DEPRECATED] Minimal rule manager for testing simulation.

    Use sally.application.rule_management.sg_rule_manager.SmartGridRuleManager instead.
    """
    def __init__(self):
        warnings.warn(
            "DummySmartGridRuleManager is deprecated. Use SmartGridRuleManager instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.rules = []

    def add_rule_from_gui_dict(self, gui_rule_dict):
        if isinstance(gui_rule_dict, list):
            for rule in gui_rule_dict:
                self.rules.append(DummySmartGridRule(
                    rule.get("id"),
                    rule.get("entity_name"),
                    rule.get("variable_name"),
                    rule.get("operator"),
                    rule.get("value"),
                    rule.get("action")
                ))
        elif isinstance(gui_rule_dict, dict):
            self.rules.append(DummySmartGridRule(
                gui_rule_dict.get("id"),
                gui_rule_dict.get("entity_name"),
                gui_rule_dict.get("variable_name"),
                gui_rule_dict.get("operator"),
                gui_rule_dict.get("value"),
                gui_rule_dict.get("action")
            ))

    def evaluate_rules_at_timestep(self, current_data):
        triggered = []
        for rule in self.rules:
            entity_data = current_data.get(rule.entity_name)
            if entity_data:
                actual_val = entity_data.get(rule.variable_name)
                if rule.evaluate(actual_val):
                    triggered.append({
                        "action_command": rule.action,
                        "triggering_rule_id": rule.rule_id,
                        "triggering_entity": rule.entity_name,
                        "triggering_variable": rule.variable_name,
                        "triggering_value": actual_val,
                        "rule_operator": rule.operator,
                        "rule_threshold": rule.threshold_value
                    })
        return triggered

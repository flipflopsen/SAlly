class SmartGridRule:
    """
    Represents a single rule for smart grid monitoring and control.

    Supports both legacy format (entity_name contains 'Entity.Variable')
    and new format (separate entity_name and variable_name fields).

    New format fields:
        - active: Whether the rule is enabled (default: True)
        - group: Rule group for organization (default: 'Default')
        - logic_op: Logical operator for chaining rules ('AND', 'OR', 'NONE')
    """

    __slots__ = (
        'rule_id', 'entity_name', 'variable_name', 'operator',
        'threshold_value', 'action', 'active', 'group', 'logic_op',
        'linked_rule_id', 'original_gui_entity_str'
    )

    def __init__(
        self,
        rule_id: str,
        entity_name: str,
        variable_name: str,
        operator: str,
        threshold_value,
        action: str,
        active: bool = True,
        group: str = "Default",
        logic_op: str = "NONE",
        linked_rule_id: str = None,
        original_gui_entity_str: str = None
    ):
        self.rule_id = rule_id
        self.entity_name = entity_name  # e.g., "CSV-0.PV_0"
        self.variable_name = variable_name  # e.g., "P"
        self.operator = operator
        self.action = action

        # New fields for enhanced rule management
        self.active = active
        self.group = group
        self.logic_op = logic_op  # 'AND', 'OR', 'NONE'
        self.linked_rule_id = linked_rule_id or None  # ID of the rule this links to

        # Attempt to convert threshold to float for numeric comparisons
        try:
            self.threshold_value = float(threshold_value)
        except (ValueError, TypeError):
            # If conversion fails, keep it as string (for operators like IS, IS_NOT)
            self.threshold_value = str(threshold_value)

        # Store the original string used in the GUI for entity.variable, for reference
        self.original_gui_entity_str = original_gui_entity_str or f"{entity_name}.{variable_name}"

    def evaluate(self, actual_value):
        if actual_value is None:
            return False

        comparable_actual_value = actual_value
        is_numeric_threshold = isinstance(self.threshold_value, float)

        if is_numeric_threshold:
            try:
                comparable_actual_value = float(actual_value)
            except (ValueError, TypeError):
                return False
        else:
            comparable_actual_value = str(actual_value)


        if self.operator == 'GREATER_THAN':
            if (self.threshold_value == 0 ) or (comparable_actual_value == 0):
                return False  # Avoid division by zero or invalid comparison
            return comparable_actual_value > self.threshold_value
        elif self.operator == 'LESS_THAN':
            result = self.threshold_value < comparable_actual_value
            return result
        elif self.operator == 'EQUALS':
            if is_numeric_threshold:
                return comparable_actual_value == self.threshold_value
            else: # String comparison
                return comparable_actual_value == self.threshold_value
        elif self.operator == 'IS': # Primarily for string equality
            return actual_value == self.threshold_value
        elif self.operator == 'IS_NOT':
            return str(actual_value) != self.threshold_value
        # Other operators like 'CONTAINS', 'STARTS_WITH', 'MATCHES_REGEX' could be added here
        else:
            print(f"Warning: Unsupported operator '{self.operator}' for rule ID {self.rule_id} on entity {self.entity_name}.{self.variable_name}")
            return False

    def __repr__(self):
        linked = f", linked_to={self.linked_rule_id}" if self.linked_rule_id else ""
        return (f"SmartGridRule(ID: {self.rule_id}, Entity: {self.entity_name}, Var: {self.variable_name}, "
                f"{self.operator} {self.threshold_value} -> {self.action}{linked})")

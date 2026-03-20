from abc import ABC, abstractmethod
from typing import Any

from tests.framework.dataclasses import SimulationTrace


class SimulationAssertion(ABC):
    """Base class for simulation assertions"""

    @abstractmethod
    def assert_condition(self, trace: SimulationTrace) -> bool:
        pass

    @abstractmethod
    def get_error_message(self, trace: SimulationTrace) -> str:
        pass


class StepCountAssertion(SimulationAssertion):
    def __init__(self, expected_steps: int):
        self.expected_steps = expected_steps

    def assert_condition(self, trace: SimulationTrace) -> bool:
        return len(trace.steps) == self.expected_steps

    def get_error_message(self, trace: SimulationTrace) -> str:
        return f"Expected {self.expected_steps} steps, got {len(trace.steps)}"


class RuleTriggeredAssertion(SimulationAssertion):
    def __init__(self, rule_id: str, expected_count: int = 1):
        self.rule_id = rule_id
        self.expected_count = expected_count

    def assert_condition(self, trace: SimulationTrace) -> bool:
        count = sum(1 for step in trace.steps
                    for rule in step.triggered_rules
                    if rule.get("triggering_rule_id") == self.rule_id)
        return count == self.expected_count

    def get_error_message(self, trace: SimulationTrace) -> str:
        actual_count = sum(1 for step in trace.steps
                           for rule in step.triggered_rules
                           if rule.get("triggering_rule_id") == self.rule_id)
        return f"Rule {self.rule_id} expected to trigger {self.expected_count} times, got {actual_count}"


class DataValueAssertion(SimulationAssertion):
    def __init__(self, step_number: int, entity_name: str, variable_name: str,
                 expected_value: Any, tolerance: float = 0.001):
        self.step_number = step_number
        self.entity_name = entity_name
        self.variable_name = variable_name
        self.expected_value = expected_value
        self.tolerance = tolerance

    def assert_condition(self, trace: SimulationTrace) -> bool:
        if self.step_number >= len(trace.steps):
            return False

        step = trace.steps[self.step_number]
        entity_data = step.output_data.get(self.entity_name, {})
        actual_value = entity_data.get(self.variable_name)

        if actual_value is None:
            return self.expected_value is None

        if isinstance(self.expected_value, (int, float)) and isinstance(actual_value, (int, float)):
            return abs(float(actual_value) - float(self.expected_value)) <= self.tolerance

        return actual_value == self.expected_value

    def get_error_message(self, trace: SimulationTrace) -> str:
        if self.step_number >= len(trace.steps):
            return f"Step {self.step_number} not found in trace"

        step = trace.steps[self.step_number]
        entity_data = step.output_data.get(self.entity_name, {})
        actual_value = entity_data.get(self.variable_name)

        return (f"At step {self.step_number}, {self.entity_name}.{self.variable_name}: "
                f"expected {self.expected_value}, got {actual_value}")
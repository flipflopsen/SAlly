from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager


class BaseSimulation(ABC):
    """Base class for all simulations"""

    def __init__(self, rule_manager: SmartGridRuleManager):
        self.current_timestep = 0
        self.total_timesteps = 0
        self.entity_variable_timeseries_data = {}
        self.relation_data = {} # Stores {relation_key: matrix_data} for Relations
        self.rule_manager = rule_manager
        self.current_timestep_data = None


    @abstractmethod
    async def step(self) -> bool:
        """Advance simulation by one step. Returns True if successful, False if ended"""
        pass

    @abstractmethod
    def on_rule_triggered(self, action_info: dict):
        """
        Callback method when a rule is triggered.
        action_info is a dictionary from SmartGridRuleManager.evaluate_rules_at_timestep
        """
        pass

    @abstractmethod
    def get_current_data_snapshot(self) -> Dict[str, Any]:
        """Get current simulation data snapshot"""
        pass

    @abstractmethod
    def close(self):
        """Clean up simulation resources"""
        pass

    @abstractmethod
    def reset(self):
        """Reset simulation to beginning"""
        self.current_timestep = 0

    async def run_steps(self, num_steps: int):
        """Run specified number of steps"""
        for _ in range(num_steps):
            if not await self.step():
                break

    async def run_all(self):
        """Run entire simulation"""
        while self.current_timestep < self.total_timesteps:
            if not await self.step():
                break

    def evaluate_rules_at_timestep(self, current_timestep_data: dict):
        """
        Evaluates all loaded rules against a single snapshot (timestep).
        Uses the unified evaluate_rules method which handles:
        - Both single rules and chained rules
        - Grouping by rule group
        - Active flag filtering
        - AND/OR logic operators for chained rules
        """
        triggered_action_details = []

        # Use unified evaluation from rule manager (handles both single and chained rules)
        results = self.rule_manager.evaluate_rules(current_timestep_data)

        for chain, triggered, actions in results:
            if triggered and actions:
                # For each triggered chain/rule, create action details for all rules
                for i, action in enumerate(actions):
                    rule = chain[i] if i < len(chain) else chain[-1]
                    entity_specific_data = current_timestep_data.get(rule.entity_name, {})
                    actual_value = entity_specific_data.get(rule.variable_name)

                    action_detail = {
                        "action_command": action,
                        "triggering_rule_id": rule.rule_id,
                        "triggering_entity": rule.entity_name,
                        "triggering_variable": rule.variable_name,
                        "triggering_value": actual_value,
                        "rule_threshold": rule.threshold_value,
                        "rule_operator": rule.operator,
                        "rule_group": rule.group,
                        "is_chain": len(chain) > 1,
                        "chain_rule_ids": [r.rule_id for r in chain],
                    }
                    triggered_action_details.append(action_detail)

        return triggered_action_details

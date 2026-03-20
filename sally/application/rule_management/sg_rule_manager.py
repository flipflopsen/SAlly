"""
Smart Grid Rule Manager

Manages the lifecycle, parsing, and aggregation of SmartGridRule objects.
Supports rule chains with logic operators (AND/OR) and group-based organization.
"""

import uuid
from typing import List, Dict, Optional, Tuple, Any, Set

from sally.application.rule_management.sg_rule import SmartGridRule
from sally.core.logger import getLogger
from sally.core.service_telemetry import ServiceNames
from sally.core.metrics_registry import RULES, SPANS

logger = getLogger(__name__)

# Try to import telemetry
_TELEMETRY_AVAILABLE = True
try:
    from sally.core.telemetry import get_telemetry, TelemetryManager
    _TELEMETRY_AVAILABLE = True
except ImportError:
    pass


class SmartGridRuleManager:
    """
    Manages the lifecycle, parsing, and aggregation of SmartGridRule objects.
    Includes OTEL instrumentation for rule evaluation metrics.

    Service Name: SAlly.Rules
    """

    __slots__ = ('rules', '_telemetry', '_rules_evaluated', '_chains_triggered', '_service_name')

    def __init__(self):
        self.rules: List[SmartGridRule] = []
        self._telemetry: Optional[TelemetryManager] = None
        self._rules_evaluated = 0
        self._chains_triggered = 0
        self._service_name = ServiceNames.RULES

        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
                self._register_metrics()
            except Exception as e:
                logger.warning("Failed to initialize rule manager telemetry: %s", e)

        logger.info("SmartGridRuleManager initialized with service name: %s", self._service_name)

    def _register_metrics(self) -> None:
        """Register OTEL metrics."""
        if not self._telemetry or not self._telemetry.enabled:
            return

        try:
            self._telemetry.gauge(
                RULES.ACTIVE_COUNT,
                lambda: len([r for r in self.rules if r.active]),
                "Number of active rules"
            )
            self._telemetry.gauge(
                RULES.GROUPS_COUNT,
                lambda: len(self.get_groups()),
                "Number of rule groups"
            )
            logger.debug("Rule manager OTEL metrics registered")
        except Exception as e:
            logger.warning("Failed to register rule manager metrics: %s", e)

    def _parse_identifier(self, raw_str: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Splits a compound identifier 'Entity.Variable' into components.
        """
        if not raw_str or not isinstance(raw_str, str):
            return None, None

        parts = raw_str.split('.', 1)

        if len(parts) == 2:
            return parts[0], parts[1]

        logger.debug(f"Parsing failed: '{raw_str}' does not match 'Entity.Variable' format.")
        return None, None

    def add_rule(self, rule: Dict[str, Any]) -> bool:
        """
        Validates and converts a raw dictionary into a SmartGridRule object.
        """
        rule_id = rule.get("id") or str(uuid.uuid4())[:8]

        raw_entity = rule.get("entity_name")
        explicit_var = rule.get("variable_name")

        if explicit_var:
            entity_name = raw_entity
            var_name = explicit_var
        else:
            entity_name, var_name = self._parse_identifier(raw_entity)

        if not entity_name or not var_name:
            logger.warning(
                "Rule %s skipped: Invalid entity/variable. entity_name='%s'",
                rule_id, raw_entity
            )
            return False

        operator = rule.get("operator")
        threshold = rule.get("value")
        action = rule.get("action")

        if operator is None or threshold is None or action is None:
            logger.warning("Rule %s skipped: Missing mandatory fields.", rule_id)
            return False

        active = rule.get("active", True)
        group = rule.get("group", "Default")
        logic_op = rule.get("logic_op", "NONE")
        linked_rule_id = rule.get("linked_rule_id") or None

        if isinstance(active, str):
            active = active.lower() in ("true", "1", "yes")

        if linked_rule_id == "":
            linked_rule_id = None
        else:
            linked_rule_id = str(linked_rule_id)
            linked_rule = self.get_rule_by_id(linked_rule_id)
            if linked_rule:
                linked_rule.linked_rule_id = rule.get("rule_id")
                self.rules[self.rules.index(linked_rule)] = linked_rule

        try:
            rule = SmartGridRule(
                rule_id=rule_id,
                entity_name=entity_name,
                variable_name=var_name,
                operator=operator,
                threshold_value=threshold,
                action=action,
                active=active,
                group=group,
                logic_op=logic_op,
                linked_rule_id=linked_rule_id,
                original_gui_entity_str=f"{entity_name}.{var_name}"
            )
            self.rules.append(rule)
            return True

        except Exception as e:
            logger.error("Rule %s instantiation failed: %s", rule_id, e)
            return False

    def load_rules(self, rules_data: List[Dict[str, Any]]) -> None:
        """Replaces current rules with a new set."""
        logger.info("Loading rules: count=%d", len(rules_data))
        self.rules.clear()
        success_count = 0
        for data in rules_data:
            if self.add_rule(data):
                success_count += 1

        if self._telemetry and self._telemetry.enabled:
            self._telemetry.counter(RULES.LOADED_TOTAL, success_count)

    def get_discovery_map(self, hdf5_structure: Dict[str, Any]) -> List[str]:
        """Flattens a hierarchical HDF5 structure."""
        unique_paths = {
            f"{entity}.{var}"
            for entity, vars_map in hdf5_structure.items()
            if isinstance(vars_map, dict)
            for var in vars_map
        }
        return sorted(unique_paths)

    # --- Helper methods ---

    def get_active_rules(self) -> List[SmartGridRule]:
        return [r for r in self.rules if r.active]

    def get_groups(self) -> Set[str]:
        return {r.group for r in self.rules}

    def get_rule_by_id(self, rule_id: str) -> Optional[SmartGridRule]:
        for r in self.rules:
            if r.rule_id == rule_id:
                return r
        return None

    def _evaluate_single_rule(
        self,
        rule: SmartGridRule,
        data_snapshot: Dict[str, Dict[str, Any]]
    ) -> bool:
        """Evaluates a single rule against the data snapshot."""
        entity_data = data_snapshot.get(rule.entity_name, {})
        actual_value = entity_data.get(rule.variable_name)
        return rule.evaluate(actual_value)

    def _build_rule_chains(self, rules: List[SmartGridRule]) -> List[List[SmartGridRule]]:
        """Groups rules into chains based on linked_rule_id."""
        if not rules:
            return []

        rule_map = {r.rule_id: r for r in rules}

        # Identify parents
        parent_ids = set()
        for rule in rules:
            if rule.linked_rule_id and rule.linked_rule_id in rule_map:
                parent_ids.add(rule.linked_rule_id)

        # Map parents to children
        children_map = {}
        for rule in rules:
            if rule.linked_rule_id and rule.linked_rule_id in rule_map:
                if rule.linked_rule_id not in children_map:
                    children_map[rule.linked_rule_id] = []
                children_map[rule.linked_rule_id].append(rule)

        assigned_rule_ids = set()
        chains = []

        for rule in rules:
            if rule.rule_id in assigned_rule_ids:
                continue

            # If rule is a child, it will be picked up by its parent
            if rule.linked_rule_id and rule.linked_rule_id in rule_map:
                continue

            # If rule is a parent, it's the root of a chain
            if rule.rule_id in parent_ids:
                chain = self._collect_chain(rule, children_map, assigned_rule_ids)
                chains.append(chain)
            else:
                # Standalone rule
                chains.append([rule])
                assigned_rule_ids.add(rule.rule_id)

        # Handle orphaned rules
        for rule in rules:
            if rule.rule_id not in assigned_rule_ids:
                chains.append([rule])
                assigned_rule_ids.add(rule.rule_id)

        return chains

    def _collect_chain(
        self,
        root_rule: SmartGridRule,
        children_map: Dict[str, List[SmartGridRule]],
        assigned_rule_ids: Set[str]
    ) -> List[SmartGridRule]:
        """Recursively collects all rules in a chain."""
        chain = [root_rule]
        assigned_rule_ids.add(root_rule.rule_id)

        children = children_map.get(root_rule.rule_id, [])
        for child in children:
            if child.rule_id not in assigned_rule_ids:
                child_chain = self._collect_chain(child, children_map, assigned_rule_ids)
                chain.extend(child_chain)

        return chain

    def _evaluate_chain(
        self,
        chain: List[SmartGridRule],
        data_snapshot: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """
        Evaluates a chain of rules.
        Respects logic_op (AND/OR) defined in the rules.
        Includes OTEL span for chain evaluation.
        """
        if not chain:
            return False, []

        # Create span for chain evaluation
        span = None
        if self._telemetry and self._telemetry.enabled:
            logic_ops = [str(r.logic_op).upper() for r in chain]
            span = self._telemetry.start_span(
                SPANS.RULES_EVALUATE_CHAIN,
                kind="internal",
                attributes={
                    "chain_length": len(chain),
                    "logic_ops": ",".join(logic_ops),
                    "first_rule_id": chain[0].rule_id if chain else "",
                    "group": chain[0].group if chain else "",
                }
            )

        try:
            # 1. Evaluate individual results first
            results = [self._evaluate_single_rule(r, data_snapshot) for r in chain]

            if not results:
                return False, []

            # 2. Combine results based on logic_op
            # Logic: result = result[0] (OP) result[1] (OP) result[2] ...
            # The logic_op of rule[0] dictates how it combines with rule[1]

            final_result = results[0]

            for i in range(1, len(chain)):
                current_rule_result = results[i]
                # Use the logic operator of the PREVIOUS rule to link to this one
                parent_op = str(chain[i-1].logic_op).upper()

                if parent_op == "OR":
                    final_result = final_result or current_rule_result
                else:
                    # Default to AND for "AND" or "NONE" or invalid ops in a chain context
                    final_result = final_result and current_rule_result

            # 3. Collect actions
            actions = []
            if final_result:
                # We only execute actions if the chain logic is satisfied
                actions = [r.action for r in chain]

            # Record chain evaluation metrics
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.counter(
                    RULES.CHAINS_EVALUATED_TOTAL,
                    1,
                    {"group": chain[0].group if chain else "unknown"}
                )
                if final_result:
                    self._telemetry.counter(
                        RULES.CHAINS_TRIGGERED_TOTAL,
                        1,
                        {"group": chain[0].group if chain else "unknown"}
                    )

            return final_result, actions
        finally:
            if span:
                span.end()

    def evaluate_rules(
        self,
        data_snapshot: Dict[str, Dict[str, Any]],
        group: Optional[str] = None
    ) -> List[Tuple[List[SmartGridRule], bool, List[str]]]:
        """
        Evaluates all active rules against a data snapshot.

        This method ensures that standalone single rules (Logic=NONE, No Links)
        are processed but are NOT included in the main chained_results list
        if that was the intention of filtering.

        Includes OTEL span for overall evaluation.
        """
        import time
        start_time = time.perf_counter()

        if group:
            active_rules = [r for r in self.rules if r.active and r.group == group]
        else:
            active_rules = [r for r in self.rules if r.active]

        if not active_rules:
            return []

        # Create span for rule evaluation
        span = None
        if self._telemetry and self._telemetry.enabled:
            span = self._telemetry.start_span(
                SPANS.RULES_EVALUATE_RULES,
                kind="internal",
                attributes={
                    "group": group or "all",
                    "active_rules_count": len(active_rules),
                }
            )

        try:
            chains = self._build_rule_chains(active_rules)
            logger.debug("Built %d rule chains/single rules", len(chains))

            # Update span with chain count
            if span:
                span.set_attribute("chains_count", len(chains))

            chained_results = []
            single_rule_results = []

            for chain in chains:
                combined_result, actions = self._evaluate_chain(chain, data_snapshot)
                self._rules_evaluated += len(chain)

                # Record per-rule evaluation metrics
                if self._telemetry and self._telemetry.enabled:
                    for rule in chain:
                        self._telemetry.counter(
                            RULES.EVALUATIONS_TOTAL,
                            1,
                            {"rule_id": rule.rule_id, "group": rule.group}
                        )

                # --- logic restored from previous step ---
                first_rule = chain[0]
                is_standalone_single = (
                    len(chain) == 1 and
                    not first_rule.linked_rule_id and
                    str(first_rule.logic_op).upper() == "NONE"
                )

                result_tuple = (chain, combined_result, actions)

                if is_standalone_single:
                    single_rule_results.append(result_tuple)
                else:
                    chained_results.append(result_tuple)

                if combined_result:
                    self._chains_triggered += 1
                    type_lbl = "Single rule" if is_standalone_single else "Chain"
                    #logger.info(
                    #    "%s triggered: group=%s rules=%s actions=%s",
                    #     type_lbl, first_rule.group, [r.rule_id for r in chain], actions
                    #)

                    if self._telemetry and self._telemetry.enabled:
                        # Use registry constants for consistent naming
                        if is_standalone_single:
                            self._telemetry.counter(RULES.SINGLES_TRIGGERED_TOTAL)
                        else:
                            self._telemetry.counter(RULES.CHAINS_TRIGGERED_TOTAL)

                        # Record triggered event for each rule in chain
                        for rule in chain:
                            self._telemetry.counter(
                                RULES.TRIGGERED_TOTAL,
                                1,
                                {"rule_id": rule.rule_id, "group": rule.group}
                            )

            # Record evaluation duration
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.histogram(
                    RULES.EVALUATION_DURATION_MS,
                    elapsed_ms,
                    {"group": group or "all"}
                )

            # Combine results so the caller gets everything
            return chained_results + single_rule_results
        finally:
            if span:
                span.end()

    def evaluate_rules_by_group(
        self,
        data_snapshot: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[Tuple[List[SmartGridRule], bool, List[str]]]]:
        results_by_group = {}
        for group_name in self.get_groups():
            group_results = self.evaluate_rules(data_snapshot, group=group_name)
            if group_results:
                results_by_group[group_name] = group_results
        return results_by_group

    def get_triggered_actions(
        self,
        data_snapshot: Dict[str, Dict[str, Any]],
        group: Optional[str] = None
    ) -> List[str]:
        actions = []
        for _chain, triggered, chain_actions in self.evaluate_rules(data_snapshot, group=group):
            if triggered:
                actions.extend(chain_actions)
        return actions

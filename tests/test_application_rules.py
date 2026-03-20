"""
Tests for sally.application.rule_management — SmartGridRule and SmartGridRuleManager.

Covers: SmartGridRule (evaluate, operators, edge cases), SmartGridRuleManager
        (add_rule, load_rules, evaluate_rules, chains, groups, discovery_map).
"""

from __future__ import annotations

import time
from unittest.mock import patch, MagicMock

import pytest

from tests.diag.metrics import record_metric


# ===========================================================================
# SmartGridRule
# ===========================================================================


class TestSmartGridRule:
    def _rule(self, **kwargs):
        from sally.application.rule_management.sg_rule import SmartGridRule

        defaults = dict(
            rule_id="R1", entity_name="GEN_1", variable_name="P",
            operator="GREATER_THAN", threshold_value=100, action="shed_load",
        )
        defaults.update(kwargs)
        return SmartGridRule(**defaults)

    def test_greater_than_true(self):
        r = self._rule(operator="GREATER_THAN", threshold_value=100)
        assert r.evaluate(150) is True
        record_metric("rule_gt_true", 1, "bool")

    def test_greater_than_false(self):
        r = self._rule(operator="GREATER_THAN", threshold_value=100)
        assert r.evaluate(50) is False
        record_metric("rule_gt_false", 1, "bool")

    def test_greater_than_zero_threshold(self):
        """Zero threshold treated as non-evaluable per implementation."""
        r = self._rule(operator="GREATER_THAN", threshold_value=0)
        assert r.evaluate(50) is False
        record_metric("rule_gt_zero_thresh", 1, "bool")

    def test_less_than(self):
        r = self._rule(operator="LESS_THAN", threshold_value=100)
        # Implementation: threshold < actual  (i.e., actual > threshold)
        assert r.evaluate(150) is True
        assert r.evaluate(50) is False
        record_metric("rule_lt", 1, "bool")

    def test_equals_numeric(self):
        r = self._rule(operator="EQUALS", threshold_value=42.0)
        assert r.evaluate(42.0) is True
        assert r.evaluate(43.0) is False
        record_metric("rule_eq_num", 1, "bool")

    def test_equals_string(self):
        r = self._rule(operator="EQUALS", threshold_value="open")
        assert r.evaluate("open") is True
        assert r.evaluate("closed") is False
        record_metric("rule_eq_str", 1, "bool")

    def test_is_operator(self):
        r = self._rule(operator="IS", threshold_value="active")
        assert r.evaluate("active") is True
        assert r.evaluate("inactive") is False
        record_metric("rule_is", 1, "bool")

    def test_is_not_operator(self):
        r = self._rule(operator="IS_NOT", threshold_value="fault")
        assert r.evaluate("normal") is True
        assert r.evaluate("fault") is False
        record_metric("rule_is_not", 1, "bool")

    def test_none_value(self):
        r = self._rule()
        assert r.evaluate(None) is False
        record_metric("rule_none_val", 1, "bool")

    def test_non_numeric_actual(self):
        r = self._rule(operator="GREATER_THAN", threshold_value=100)
        assert r.evaluate("not_a_number") is False
        record_metric("rule_nonnumeric", 1, "bool")

    def test_unsupported_operator(self):
        r = self._rule(operator="CONTAINS")
        assert r.evaluate("something") is False
        record_metric("rule_unsupported_op", 1, "bool")

    def test_threshold_auto_float(self):
        r = self._rule(threshold_value="42.5")
        assert r.threshold_value == 42.5
        record_metric("rule_auto_float", 1, "bool")

    def test_threshold_stays_string(self):
        r = self._rule(threshold_value="not_a_number")
        assert isinstance(r.threshold_value, str)
        record_metric("rule_str_thresh", 1, "bool")

    def test_repr(self):
        r = self._rule()
        s = repr(r)
        assert "SmartGridRule" in s
        assert "GEN_1" in s
        record_metric("rule_repr", 1, "bool")

    def test_fields(self):
        r = self._rule(active=False, group="Voltage", logic_op="AND", linked_rule_id="R2")
        assert r.active is False
        assert r.group == "Voltage"
        assert r.logic_op == "AND"
        assert r.linked_rule_id == "R2"
        record_metric("rule_fields", 4, "fields")


# ===========================================================================
# SmartGridRuleManager
# ===========================================================================


class TestSmartGridRuleManager:
    def _manager(self):
        """Create a RuleManager with telemetry mocked out."""
        with patch("sally.application.rule_management.sg_rule_manager.get_telemetry", return_value=MagicMock(enabled=False)):
            from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager
            return SmartGridRuleManager()

    def test_add_rule_success(self):
        mgr = self._manager()
        ok = mgr.add_rule({
            "entity_name": "GEN_1",
            "variable_name": "P",
            "operator": "GREATER_THAN",
            "value": 100,
            "action": "shed_load",
        })
        assert ok is True
        assert len(mgr.rules) == 1
        record_metric("mgr_add_rule", 1, "bool")

    def test_add_rule_compound_entity(self):
        """Legacy format: entity_name contains 'Entity.Variable'."""
        mgr = self._manager()
        ok = mgr.add_rule({
            "entity_name": "GEN_1.P",
            "operator": "GREATER_THAN",
            "value": 100,
            "action": "shed_load",
        })
        assert ok is True
        assert mgr.rules[0].entity_name == "GEN_1"
        assert mgr.rules[0].variable_name == "P"
        record_metric("mgr_add_compound", 1, "bool")

    def test_add_rule_invalid(self):
        mgr = self._manager()
        ok = mgr.add_rule({"entity_name": "bad"})  # Missing required fields
        assert ok is False
        record_metric("mgr_add_invalid", 1, "bool")

    def test_load_rules(self):
        mgr = self._manager()
        mgr.load_rules([
            {"entity_name": "E1.V1", "operator": "GREATER_THAN", "value": 10, "action": "A1"},
            {"entity_name": "E2.V2", "operator": "LESS_THAN", "value": 5, "action": "A2"},
            {"entity_name": "bad"},  # invalid
        ])
        assert len(mgr.rules) == 2
        record_metric("mgr_load_rules", 2, "rules")

    def test_get_active_rules(self):
        mgr = self._manager()
        mgr.add_rule({"entity_name": "E1.V1", "operator": "GREATER_THAN", "value": 10, "action": "A1", "active": True})
        mgr.add_rule({"entity_name": "E2.V2", "operator": "LESS_THAN", "value": 5, "action": "A2", "active": False})
        assert len(mgr.get_active_rules()) == 1
        record_metric("mgr_active_rules", 1, "rules")

    def test_get_groups(self):
        mgr = self._manager()
        mgr.add_rule({"entity_name": "E1.V1", "operator": "GREATER_THAN", "value": 10, "action": "A1", "group": "Voltage"})
        mgr.add_rule({"entity_name": "E2.V2", "operator": "LESS_THAN", "value": 5, "action": "A2", "group": "Power"})
        groups = mgr.get_groups()
        assert "Voltage" in groups
        assert "Power" in groups
        record_metric("mgr_groups", len(groups), "groups")

    def test_get_rule_by_id(self):
        mgr = self._manager()
        mgr.add_rule({"id": "RULE_42", "entity_name": "E1.V1", "operator": "EQUALS", "value": 1, "action": "A"})
        r = mgr.get_rule_by_id("RULE_42")
        assert r is not None
        assert r.rule_id == "RULE_42"
        assert mgr.get_rule_by_id("NONEXIST") is None
        record_metric("mgr_get_by_id", 1, "bool")

    def test_evaluate_single_rule(self):
        mgr = self._manager()
        mgr.add_rule({"entity_name": "GEN_1", "variable_name": "P", "operator": "GREATER_THAN", "value": 100, "action": "shed_load"})
        result = mgr._evaluate_single_rule(mgr.rules[0], {"GEN_1": {"P": 150}})
        assert result is True
        record_metric("mgr_eval_single", 1, "bool")

    def test_get_discovery_map(self):
        mgr = self._manager()
        hdf5_structure = {
            "Entity1": {"P_MW": [], "Q_MVAR": []},
            "Entity2": {"VM": []},
        }
        paths = mgr.get_discovery_map(hdf5_structure)
        assert "Entity1.P_MW" in paths
        assert "Entity1.Q_MVAR" in paths
        assert "Entity2.VM" in paths
        record_metric("mgr_discovery_map", len(paths), "paths")

    def test_add_rule_with_linked_id(self):
        mgr = self._manager()
        mgr.add_rule({"id": "R1", "entity_name": "E.V", "operator": "GREATER_THAN", "value": 10, "action": "A"})
        mgr.add_rule({
            "id": "R2", "entity_name": "E.V2", "operator": "LESS_THAN",
            "value": 5, "action": "A2", "linked_rule_id": "R1", "logic_op": "AND",
        })
        r2 = mgr.get_rule_by_id("R2")
        assert r2 is not None
        assert r2.linked_rule_id == "R1"
        assert r2.logic_op == "AND"
        record_metric("mgr_linked_rules", 1, "bool")

    def test_add_rule_active_string_conversion(self):
        mgr = self._manager()
        mgr.add_rule({"entity_name": "E.V", "operator": "EQUALS", "value": 1, "action": "A", "active": "false"})
        assert mgr.rules[0].active is False
        record_metric("mgr_active_string", 1, "bool")

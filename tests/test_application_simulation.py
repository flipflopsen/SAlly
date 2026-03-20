"""
Tests for sally.application.simulation — BaseSimulation, DataProviders.

Covers: BaseSimulation (evaluate_rules_at_timestep, run_steps, run_all),
        RandomDataProvider, SinusoidalDataProvider.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from tests.diag.metrics import record_metric


# ===========================================================================
# DataProviders
# ===========================================================================


class TestRandomDataProvider:
    def test_generate_timeseries(self):
        from sally.application.simulation.data_provider import RandomDataProvider

        provider = RandomDataProvider(num_entities=5, num_timesteps=100)
        data = provider.generate_timeseries_data()
        assert len(data) == 5
        for entity, variables in data.items():
            for var_name, series in variables.items():
                assert len(series) == 100
        record_metric("random_dp_entities", len(data), "count")

    def test_generate_relational(self):
        from sally.application.simulation.data_provider import RandomDataProvider

        provider = RandomDataProvider(num_entities=10)
        rel = provider.generate_relational_data()
        assert len(rel) > 0
        for name, matrix in rel.items():
            assert len(matrix) > 0
            assert len(matrix[0]) > 0
        record_metric("random_dp_relations", len(rel), "count")

    def test_zero_entities(self):
        from sally.application.simulation.data_provider import RandomDataProvider

        provider = RandomDataProvider(num_entities=0, num_timesteps=10)
        data = provider.generate_timeseries_data()
        assert len(data) == 0
        record_metric("random_dp_zero", 1, "bool")

    def test_entity_types_variety(self):
        """With enough entities, should get multiple entity types."""
        from sally.application.simulation.data_provider import RandomDataProvider

        provider = RandomDataProvider(num_entities=50, num_timesteps=10)
        data = provider.generate_timeseries_data()
        all_vars = set()
        for entity, variables in data.items():
            all_vars.update(variables.keys())
        assert len(all_vars) > 1  # Multiple different variable names
        record_metric("random_dp_variety", len(all_vars), "var_types")


class TestSinusoidalDataProvider:
    def test_generate_timeseries(self):
        from sally.application.simulation.data_provider import SinusoidalDataProvider

        provider = SinusoidalDataProvider(num_entities=3, num_timesteps=50)
        data = provider.generate_timeseries_data()
        assert len(data) == 3
        for entity, variables in data.items():
            assert "P_MW" in variables
            assert "Q_MVAR" in variables
            assert "VM" in variables
            assert len(variables["P_MW"]) == 50
        record_metric("sinusoidal_dp_entities", len(data), "count")

    def test_generate_relational(self):
        from sally.application.simulation.data_provider import SinusoidalDataProvider

        provider = SinusoidalDataProvider(num_entities=5)
        rel = provider.generate_relational_data()
        assert "Adjacency_Matrix" in rel
        matrix = rel["Adjacency_Matrix"]
        assert len(matrix) == 5
        assert len(matrix[0]) == 5
        record_metric("sinusoidal_dp_relations", 1, "bool")


# ===========================================================================
# BaseSimulation evaluate_rules_at_timestep
# ===========================================================================


class TestBaseSimulationRuleEvaluation:
    def _make_sim_with_rules(self, rules_data, evaluate_results):
        """Create a concrete BaseSimulation with mocked rule manager."""
        from sally.application.simulation.base_sim import BaseSimulation

        class ConcreteSim(BaseSimulation):
            async def step(self):
                return True

            def on_rule_triggered(self, action_info):
                pass

            def get_current_data_snapshot(self):
                return {}

            def close(self):
                pass

            def reset(self):
                super().reset()

        mock_rm = MagicMock()
        mock_rm.evaluate_rules.return_value = evaluate_results
        sim = ConcreteSim(mock_rm)
        return sim

    def test_no_rules_triggered(self):
        sim = self._make_sim_with_rules([], [])
        results = sim.evaluate_rules_at_timestep({"GEN_1": {"P": 50}})
        assert results == []
        record_metric("basesim_no_trigger", 1, "bool")

    def test_rules_triggered(self):
        from sally.application.rule_management.sg_rule import SmartGridRule

        rule = SmartGridRule(
            rule_id="R1", entity_name="GEN_1", variable_name="P",
            operator="GREATER_THAN", threshold_value=100, action="shed_load",
        )
        evaluate_results = [
            ([rule], True, ["shed_load"]),
        ]
        sim = self._make_sim_with_rules([], evaluate_results)
        results = sim.evaluate_rules_at_timestep({"GEN_1": {"P": 150}})
        assert len(results) == 1
        assert results[0]["action_command"] == "shed_load"
        assert results[0]["triggering_entity"] == "GEN_1"
        assert results[0]["triggering_variable"] == "P"
        record_metric("basesim_triggered", len(results), "actions")

    def test_chain_rules(self):
        from sally.application.rule_management.sg_rule import SmartGridRule

        r1 = SmartGridRule(
            rule_id="R1", entity_name="GEN_1", variable_name="P",
            operator="GREATER_THAN", threshold_value=100, action="alert",
        )
        r2 = SmartGridRule(
            rule_id="R2", entity_name="GEN_1", variable_name="Q",
            operator="GREATER_THAN", threshold_value=50, action="shed_load",
        )
        evaluate_results = [
            ([r1, r2], True, ["alert", "shed_load"]),
        ]
        sim = self._make_sim_with_rules([], evaluate_results)
        results = sim.evaluate_rules_at_timestep({"GEN_1": {"P": 150, "Q": 60}})
        assert len(results) == 2
        assert results[0]["is_chain"] is True
        assert results[0]["chain_rule_ids"] == ["R1", "R2"]
        record_metric("basesim_chain", len(results), "actions")

    def test_reset(self):
        sim = self._make_sim_with_rules([], [])
        sim.current_timestep = 42
        sim.reset()
        assert sim.current_timestep == 0
        record_metric("basesim_reset", 1, "bool")

"""
Tests for sally.core.metrics_registry — Frozen dataclass metric constants.

Covers: all metric registry classes (EventBusMetrics, RulesMetrics, SetpointsMetrics,
        ScadaMetrics, GridDataMetrics, DatabaseMetrics, ServiceMetrics, GridTopologyMetrics,
        OtelCollectorMetrics), SpanNames, SpanAttributes, and singleton instances.
"""

from __future__ import annotations

import pytest

from tests.diag.metrics import record_metric


class TestEventBusMetrics:
    def test_constants_are_strings(self):
        from sally.core.metrics_registry import EVENTBUS

        assert isinstance(EVENTBUS.EVENTS_PUBLISHED, str)
        assert isinstance(EVENTBUS.EVENTS_PROCESSED, str)
        assert isinstance(EVENTBUS.EVENTS_DROPPED, str)
        assert isinstance(EVENTBUS.QUEUE_SIZE, str)
        assert isinstance(EVENTBUS.EVENT_LATENCY_MS, str)
        record_metric("eventbus_metrics_constants", 5, "fields")

    def test_frozen(self):
        from sally.core.metrics_registry import EVENTBUS

        with pytest.raises(AttributeError):
            EVENTBUS.EVENTS_PUBLISHED = "hacked"  # type: ignore
        record_metric("eventbus_metrics_frozen", 1, "bool")

    def test_prefix_consistency(self):
        from sally.core.metrics_registry import EVENTBUS

        for attr in ["EVENTS_PUBLISHED", "EVENTS_PROCESSED", "EVENTS_DROPPED",
                      "QUEUE_SIZE", "HANDLER_COUNT", "EVENT_LATENCY_MS", "BATCH_LATENCY_MS"]:
            val = getattr(EVENTBUS, attr)
            assert val.startswith("eventbus."), f"{attr} should start with 'eventbus.'"
        record_metric("eventbus_metrics_prefix", 1, "bool")


class TestRulesMetrics:
    def test_counter_names(self):
        from sally.core.metrics_registry import RULES

        assert "rules." in RULES.EVALUATIONS_TOTAL
        assert "rules." in RULES.TRIGGERED_TOTAL
        assert "rules." in RULES.CHAINS_TRIGGERED_TOTAL
        record_metric("rules_metrics_counters", 3, "fields")

    def test_frozen(self):
        from sally.core.metrics_registry import RULES

        with pytest.raises(AttributeError):
            RULES.EVALUATIONS_TOTAL = "hacked"  # type: ignore
        record_metric("rules_metrics_frozen", 1, "bool")


class TestSetpointsMetrics:
    def test_names(self):
        from sally.core.metrics_registry import SETPOINTS

        assert "setpoints." in SETPOINTS.APPLIED_TOTAL
        assert "setpoints." in SETPOINTS.ACTIVE_COUNT
        record_metric("setpoints_metrics", 2, "fields")


class TestScadaMetrics:
    def test_names(self):
        from sally.core.metrics_registry import SCADA

        assert "scada." in SCADA.SIMULATION_STEPS_TOTAL
        assert "scada." in SCADA.STEP_DURATION_MS
        record_metric("scada_metrics", 2, "fields")


class TestGridDataMetrics:
    def test_names(self):
        from sally.core.metrics_registry import GRID_DATA

        assert "grid_data." in GRID_DATA.COLLECTED_TOTAL
        assert "grid_data." in GRID_DATA.ENTITIES_MONITORED
        record_metric("grid_data_metrics", 2, "fields")


class TestDatabaseMetrics:
    def test_names(self):
        from sally.core.metrics_registry import DATABASE

        assert "db." in DATABASE.QUERIES_TOTAL
        assert "db." in DATABASE.POOL_SIZE
        assert "db." in DATABASE.QUERY_DURATION_MS
        record_metric("database_metrics", 3, "fields")


class TestServiceMetrics:
    def test_names(self):
        from sally.core.metrics_registry import SERVICE

        assert "service." in SERVICE.REQUESTS_TOTAL
        assert "service." in SERVICE.UPTIME_SECONDS
        assert "service." in SERVICE.OPERATION_DURATION_MS
        record_metric("service_metrics", 3, "fields")


class TestGridTopologyMetrics:
    def test_names(self):
        from sally.core.metrics_registry import GRID_TOPOLOGY

        assert "grid_topology." in GRID_TOPOLOGY.UPDATES_TOTAL
        assert "grid_topology." in GRID_TOPOLOGY.ENTITIES_TRACKED
        record_metric("grid_topology_metrics", 2, "fields")


class TestOtelCollectorMetrics:
    def test_names(self):
        from sally.core.metrics_registry import OTEL_COLLECTOR

        assert "otelcol_" in OTEL_COLLECTOR.RECEIVER_ACCEPTED_SPANS
        record_metric("otel_collector_metrics", 1, "fields")


class TestSpanNames:
    def test_span_names_consistency(self):
        from sally.core.metrics_registry import SPANS

        assert isinstance(SPANS.EVENTBUS_PUBLISH, str)
        assert isinstance(SPANS.SCADA_RUN_STEP, str)
        assert isinstance(SPANS.RULES_EVALUATE, str)
        assert isinstance(SPANS.SETPOINT_APPLY, str)
        assert isinstance(SPANS.GRID_DATA_COLLECT, str)
        assert isinstance(SPANS.DB_QUERY, str)
        assert isinstance(SPANS.SERVICE_INIT, str)
        record_metric("span_names", 7, "spans")

    def test_frozen(self):
        from sally.core.metrics_registry import SPANS

        with pytest.raises(AttributeError):
            SPANS.EVENTBUS_PUBLISH = "hacked"  # type: ignore
        record_metric("span_names_frozen", 1, "bool")


class TestSpanAttributes:
    def test_attributes(self):
        from sally.core.metrics_registry import ATTRS

        assert isinstance(ATTRS.CORRELATION_ID, str)
        assert isinstance(ATTRS.EVENT_TYPE, str)
        assert isinstance(ATTRS.TIMESTEP, str)
        assert isinstance(ATTRS.RULE_ID, str)
        assert isinstance(ATTRS.ENTITY_ID, str)
        record_metric("span_attributes", 5, "attrs")


class TestSingletonInstances:
    def test_all_singletons_exist(self):
        from sally.core.metrics_registry import (
            EVENTBUS, RULES, SETPOINTS, SCADA, GRID_DATA,
            OTEL_COLLECTOR, DATABASE, SERVICE, GRID_TOPOLOGY,
            SPANS, ATTRS,
        )

        assert EVENTBUS is not None
        assert RULES is not None
        assert SETPOINTS is not None
        assert SCADA is not None
        assert GRID_DATA is not None
        assert OTEL_COLLECTOR is not None
        assert DATABASE is not None
        assert SERVICE is not None
        assert GRID_TOPOLOGY is not None
        assert SPANS is not None
        assert ATTRS is not None
        record_metric("singleton_instances", 11, "count")

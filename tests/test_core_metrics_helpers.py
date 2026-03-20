"""
Tests for sally.core.metrics_helpers — convenience functions for telemetry recording.

Covers: timed_span, timed_operation, increment_counter, set_gauge, record_histogram,
        and all subsystem convenience functions.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from tests.diag.metrics import record_metric


class TestTimedSpan:
    def test_no_telemetry_yields_empty_dict(self):
        from sally.core.metrics_helpers import timed_span

        with patch("sally.core.metrics_helpers.get_telemetry", return_value=None):
            with timed_span("test_span") as attrs:
                attrs["extra"] = "value"
            # Should not raise
        record_metric("timed_span_no_telem", 1, "bool")

    def test_with_telemetry(self):
        from sally.core.metrics_helpers import timed_span

        mock_tm = MagicMock()
        mock_tm.span.return_value.__enter__ = MagicMock()
        mock_tm.span.return_value.__exit__ = MagicMock(return_value=False)

        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            with timed_span("my_span", {"key": "val"}) as attrs:
                pass
        mock_tm.span.assert_called_once()
        record_metric("timed_span_with_telem", 1, "bool")


class TestTimedOperation:
    def test_records_histogram(self):
        from sally.core.metrics_helpers import timed_operation

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            with timed_operation("test.duration_ms"):
                time.sleep(0.01)
        mock_tm.record_histogram.assert_called_once()
        args = mock_tm.record_histogram.call_args
        assert args[0][0] == "test.duration_ms"
        assert args[0][1] >= 10  # at least ~10ms
        record_metric("timed_op_histogram", args[0][1], "ms")

    def test_no_telemetry(self):
        from sally.core.metrics_helpers import timed_operation

        with patch("sally.core.metrics_helpers.get_telemetry", return_value=None):
            with timed_operation("noop_hist"):
                pass  # Should not raise
        record_metric("timed_op_no_telem", 1, "bool")


class TestIncrementCounter:
    def test_increments(self):
        from sally.core.metrics_helpers import increment_counter

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            increment_counter("my.counter", 5.0, {"label": "val"})
        mock_tm.increment_counter.assert_called_once_with("my.counter", 5.0, {"label": "val"})
        record_metric("increment_counter", 1, "bool")

    def test_no_telemetry(self):
        from sally.core.metrics_helpers import increment_counter

        with patch("sally.core.metrics_helpers.get_telemetry", return_value=None):
            increment_counter("my.counter")  # should not raise
        record_metric("increment_counter_noop", 1, "bool")


class TestSetGauge:
    def test_sets_value(self):
        from sally.core.metrics_helpers import set_gauge

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            set_gauge("my.gauge", 42.0)
        mock_tm.set_gauge.assert_called_once_with("my.gauge", 42.0, None)
        record_metric("set_gauge", 1, "bool")


class TestRecordHistogram:
    def test_records_value(self):
        from sally.core.metrics_helpers import record_histogram

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            record_histogram("my.hist", 99.5)
        mock_tm.record_histogram.assert_called_once_with("my.hist", 99.5, None)
        record_metric("record_histogram", 1, "bool")


# ---------------------------------------------------------------------------
# Subsystem convenience functions
# ---------------------------------------------------------------------------


class TestEventPublishedHelpers:
    def test_record_event_published(self):
        from sally.core.metrics_helpers import record_event_published

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            record_event_published("grid_data_update")
        mock_tm.increment_counter.assert_called_once()
        record_metric("event_published_helper", 1, "bool")

    def test_record_event_processed(self):
        from sally.core.metrics_helpers import record_event_processed

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            record_event_processed("grid_data_update")
        mock_tm.increment_counter.assert_called_once()
        record_metric("event_processed_helper", 1, "bool")

    def test_record_event_dropped(self):
        from sally.core.metrics_helpers import record_event_dropped

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            record_event_dropped("overflow")
        mock_tm.increment_counter.assert_called_once()
        record_metric("event_dropped_helper", 1, "bool")


class TestRuleEvaluationHelpers:
    def test_record_rule_evaluation_triggered(self):
        from sally.core.metrics_helpers import record_rule_evaluation

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            record_rule_evaluation("rule_001", triggered=True, duration_ms=5.5)
        assert mock_tm.increment_counter.call_count == 2  # evaluations + triggered
        mock_tm.record_histogram.assert_called_once()
        record_metric("rule_eval_triggered", 1, "bool")

    def test_record_rule_evaluation_not_triggered(self):
        from sally.core.metrics_helpers import record_rule_evaluation

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            record_rule_evaluation("rule_002", triggered=False, duration_ms=2.1)
        assert mock_tm.increment_counter.call_count == 1  # only evaluations
        record_metric("rule_eval_not_triggered", 1, "bool")


class TestSetpointHelpers:
    def test_record_setpoint_applied(self):
        from sally.core.metrics_helpers import record_setpoint_applied

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            record_setpoint_applied("GEN_1", "P_MW", 100.0)
        mock_tm.increment_counter.assert_called_once()
        mock_tm.set_gauge.assert_called_once()
        record_metric("setpoint_applied_helper", 1, "bool")

    def test_record_setpoint_cleared(self):
        from sally.core.metrics_helpers import record_setpoint_cleared

        mock_tm = MagicMock()
        with patch("sally.core.metrics_helpers.get_telemetry", return_value=mock_tm):
            record_setpoint_cleared("GEN_1", "P_MW")
        mock_tm.increment_counter.assert_called_once()
        record_metric("setpoint_cleared_helper", 1, "bool")

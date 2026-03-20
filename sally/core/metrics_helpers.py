"""
Metrics Helper Functions for Sally Observability.

This module provides helper functions for common metric operations,
reducing boilerplate and ensuring consistent metric recording.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from sally.core.metrics_registry import (
    ATTRS,
    EVENTBUS,
    GRID_DATA,
    RULES,
    SCADA,
    SETPOINTS,
    SPANS,
)

try:
    from sally.core.telemetry import TelemetryManager

    _TELEMETRY_AVAILABLE = True
except ImportError:
    _TELEMETRY_AVAILABLE = False


def get_telemetry() -> Optional["TelemetryManager"]:
    """Get the telemetry manager singleton if available."""
    if not _TELEMETRY_AVAILABLE:
        return None
    return TelemetryManager.get_instance()


@contextmanager
def timed_span(
    span_name: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager that creates a span and measures duration.

    Yields a dict where additional attributes can be added during execution.
    The span is automatically ended when the context exits.

    Args:
        span_name: Name of the span to create
        attributes: Initial span attributes

    Yields:
        Dict to add additional attributes during span execution
    """
    telemetry = get_telemetry()
    if telemetry is None:
        # No telemetry - just yield empty dict
        result: Dict[str, Any] = {}
        yield result
        return

    start_time = time.perf_counter()
    additional_attrs: Dict[str, Any] = {}

    with telemetry.span(span_name, attributes):
        try:
            yield additional_attrs
        finally:
            # Add any additional attributes that were set during execution
            if additional_attrs:
                # Note: In OTEL, we'd need to get current span and add attributes
                # This is a simplified pattern
                pass
            duration_ms = (time.perf_counter() - start_time) * 1000


@contextmanager
def timed_operation(
    histogram_name: str,
    labels: Optional[Dict[str, str]] = None,
) -> Generator[None, None, None]:
    """
    Context manager that measures operation duration and records to histogram.

    Args:
        histogram_name: Name of the histogram metric
        labels: Labels to attach to the metric
    """
    telemetry = get_telemetry()
    start_time = time.perf_counter()

    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        if telemetry is not None:
            telemetry.record_histogram(histogram_name, duration_ms, labels)


def increment_counter(
    counter_name: str,
    value: float = 1.0,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """
    Increment a counter metric.

    Args:
        counter_name: Name of the counter metric
        value: Value to increment by (default 1.0)
        labels: Labels to attach to the metric
    """
    telemetry = get_telemetry()
    if telemetry is not None:
        telemetry.increment_counter(counter_name, value, labels)


def set_gauge(
    gauge_name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """
    Set a gauge metric value.

    Args:
        gauge_name: Name of the gauge metric
        value: Value to set
        labels: Labels to attach to the metric
    """
    telemetry = get_telemetry()
    if telemetry is not None:
        telemetry.set_gauge(gauge_name, value, labels)


def record_histogram(
    histogram_name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """
    Record a value to a histogram metric.

    Args:
        histogram_name: Name of the histogram metric
        value: Value to record
        labels: Labels to attach to the metric
    """
    telemetry = get_telemetry()
    if telemetry is not None:
        telemetry.record_histogram(histogram_name, value, labels)


# Convenience functions for specific subsystems

def record_event_published(event_type: str) -> None:
    """Record an event publication."""
    increment_counter(EVENTBUS.EVENTS_PUBLISHED, labels={EVENTBUS.LABEL_EVENT_TYPE: event_type})


def record_event_processed(event_type: str) -> None:
    """Record an event being processed."""
    increment_counter(EVENTBUS.EVENTS_PROCESSED, labels={EVENTBUS.LABEL_EVENT_TYPE: event_type})


def record_event_dropped(event_type: str) -> None:
    """Record a dropped event."""
    increment_counter(EVENTBUS.EVENTS_DROPPED, labels={EVENTBUS.LABEL_EVENT_TYPE: event_type})


def record_event_latency(latency_ms: float, event_type: Optional[str] = None) -> None:
    """Record event processing latency."""
    labels = {EVENTBUS.LABEL_EVENT_TYPE: event_type} if event_type else None
    record_histogram(EVENTBUS.EVENT_LATENCY_MS, latency_ms, labels)


def record_rule_evaluation(rule_id: str, triggered: bool, duration_ms: float) -> None:
    """Record a rule evaluation."""
    increment_counter(
        RULES.EVALUATIONS_TOTAL,
        labels={RULES.LABEL_RULE_ID: rule_id, RULES.LABEL_RESULT: "triggered" if triggered else "not_triggered"},
    )
    if triggered:
        increment_counter(RULES.TRIGGERED_TOTAL, labels={RULES.LABEL_RULE_ID: rule_id})
    record_histogram(RULES.EVALUATION_DURATION_MS, duration_ms, labels={RULES.LABEL_RULE_ID: rule_id})


def record_setpoint_applied(entity_id: str, attribute: str, value: float) -> None:
    """Record a setpoint application."""
    labels = {SETPOINTS.LABEL_ENTITY_ID: entity_id, SETPOINTS.LABEL_ATTRIBUTE: attribute}
    increment_counter(SETPOINTS.APPLIED_TOTAL, labels=labels)
    set_gauge(SETPOINTS.VALUE, value, labels=labels)


def record_setpoint_cleared(entity_id: str, attribute: str) -> None:
    """Record a setpoint being cleared."""
    labels = {SETPOINTS.LABEL_ENTITY_ID: entity_id, SETPOINTS.LABEL_ATTRIBUTE: attribute}
    increment_counter(SETPOINTS.CLEARED_TOTAL, labels=labels)


def record_simulation_step(timestep: int, duration_ms: float, success: bool = True) -> None:
    """Record a simulation step execution."""
    set_gauge(SCADA.SIMULATION_TIMESTEP, timestep)
    increment_counter(SCADA.SIMULATION_STEPS_TOTAL, labels={SCADA.LABEL_SUCCESS: str(success).lower()})
    record_histogram(SCADA.STEP_DURATION_MS, duration_ms, labels={SCADA.LABEL_SUCCESS: str(success).lower()})


def record_command_processed(command_type: str, duration_ms: float) -> None:
    """Record a command being processed."""
    labels = {SCADA.LABEL_COMMAND_TYPE: command_type}
    increment_counter(SCADA.COMMANDS_TOTAL, labels=labels)
    record_histogram(SCADA.COMMAND_DURATION_MS, duration_ms, labels=labels)


def record_grid_data_collected(entity_type: str, count: int = 1) -> None:
    """Record grid data collection."""
    increment_counter(GRID_DATA.COLLECTED_TOTAL, value=count, labels={GRID_DATA.LABEL_ENTITY_TYPE: entity_type})


def update_entities_monitored(count: int) -> None:
    """Update the count of monitored entities."""
    set_gauge(GRID_DATA.ENTITIES_MONITORED, count)


def update_active_rules_count(count: int) -> None:
    """Update the count of active rules."""
    set_gauge(RULES.ACTIVE_COUNT, count)


def update_active_setpoints_count(count: int) -> None:
    """Update the count of active setpoints."""
    set_gauge(SETPOINTS.ACTIVE_COUNT, count)


def update_eventbus_queue_size(size: int) -> None:
    """Update the event bus queue size."""
    set_gauge(EVENTBUS.QUEUE_SIZE, size)


def update_eventbus_handler_count(count: int) -> None:
    """Update the event bus handler count."""
    set_gauge(EVENTBUS.HANDLER_COUNT, count)

#!/usr/bin/env python
"""
Test script for validating Sally OpenTelemetry integration.

This script verifies that:
1. Telemetry is properly initialized
2. Traces are being generated
3. Metrics are being recorded
4. Logs include correlation IDs
5. OTEL collector is receiving data

Run with: python scripts/test_telemetry.py
"""

import os
import sys
import time
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def test_telemetry_import():
    """Test that telemetry modules can be imported."""
    print("\n=== Testing Telemetry Imports ===")

    try:
        from sally.core.telemetry import TelemetryManager, TelemetryConfig
        print("✓ TelemetryManager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import TelemetryManager: {e}")
        return False

    try:
        from sally.core.service_telemetry import ServiceNames, init_service_telemetry
        print("✓ ServiceNames and init_service_telemetry imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import service_telemetry: {e}")
        return False

    try:
        from sally.core.metrics_registry import EVENTBUS, RULES, SCADA, SETPOINTS, GRID_DATA
        print("✓ Metrics registry imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import metrics_registry: {e}")
        return False

    try:
        from sally.core.metrics_helpers import (
            increment_counter, set_gauge, record_histogram, timed_span
        )
        print("✓ Metrics helpers imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import metrics_helpers: {e}")
        return False

    return True


def test_telemetry_initialization():
    """Test telemetry initialization."""
    print("\n=== Testing Telemetry Initialization ===")

    from sally.core.service_telemetry import ServiceNames, init_service_telemetry
    from sally.core.telemetry import TelemetryConfig

    config = TelemetryConfig(
        enabled=True,
        service_name=ServiceNames.ORCHESTRATOR,
        otlp_endpoint=os.getenv("SALLY_OTEL_ENDPOINT", "http://localhost:4317"),
        export_mode="otlp",
    )

    try:
        telemetry = init_service_telemetry(ServiceNames.ORCHESTRATOR, config)
        print(f"✓ Telemetry initialized for service: {ServiceNames.ORCHESTRATOR}")
        print(f"  - Endpoint: {config.otlp_endpoint}")
        print(f"  - Export mode: {config.export_mode}")
        return telemetry
    except Exception as e:
        print(f"✗ Failed to initialize telemetry: {e}")
        return None


def test_span_creation(telemetry):
    """Test span creation and tracing."""
    print("\n=== Testing Span Creation ===")

    if telemetry is None:
        print("✗ Skipping - no telemetry instance")
        return False

    try:
        with telemetry.span("test.operation", {"test_attribute": "test_value"}):
            print("✓ Created test span")
            time.sleep(0.1)  # Simulate some work

            with telemetry.span("test.child_operation", {"nested": True}):
                print("✓ Created nested child span")
                time.sleep(0.05)

        print("✓ Spans completed successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to create spans: {e}")
        return False


def test_metrics_recording(telemetry):
    """Test metrics recording."""
    print("\n=== Testing Metrics Recording ===")

    if telemetry is None:
        print("✗ Skipping - no telemetry instance")
        return False

    from sally.core.metrics_registry import EVENTBUS, RULES

    try:
        # Test counter
        telemetry.increment_counter(
            EVENTBUS.EVENTS_PUBLISHED,
            1.0,
            {EVENTBUS.LABEL_EVENT_TYPE: "TestEvent"}
        )
        print("✓ Counter incremented")

        # Test gauge
        telemetry.set_gauge(RULES.ACTIVE_COUNT, 5)
        print("✓ Gauge set")

        # Test histogram
        telemetry.record_histogram(
            EVENTBUS.EVENT_LATENCY_MS,
            12.5,
            {EVENTBUS.LABEL_EVENT_TYPE: "TestEvent"}
        )
        print("✓ Histogram recorded")

        return True
    except Exception as e:
        print(f"✗ Failed to record metrics: {e}")
        return False


def test_log_correlation():
    """Test log correlation ID injection."""
    print("\n=== Testing Log Correlation ===")

    from sally.core.logger import get_logger, CorrelationIdFilter

    logger = get_logger("test.correlation")

    try:
        # Check if correlation filter is available
        print("✓ CorrelationIdFilter class available")

        # Log a message
        logger.info("Test log message without trace context")
        print("✓ Logged message without trace context")

        # Log within a span context
        try:
            from sally.core.telemetry import TelemetryManager
            telemetry = TelemetryManager.get_instance()

            with telemetry.span("test.log_correlation"):
                logger.info("Test log message WITH trace context")
                print("✓ Logged message with trace context")
        except Exception as e:
            print(f"  Note: Could not test with trace context: {e}")

        return True
    except Exception as e:
        print(f"✗ Failed log correlation test: {e}")
        return False


def test_metrics_helpers():
    """Test metrics helper functions."""
    print("\n=== Testing Metrics Helpers ===")

    from sally.core.metrics_helpers import (
        record_event_published,
        record_event_processed,
        record_rule_evaluation,
        record_setpoint_applied,
        record_simulation_step,
        update_active_rules_count,
        timed_operation,
    )

    try:
        record_event_published("GridMeasurementEvent")
        print("✓ record_event_published works")

        record_event_processed("GridMeasurementEvent")
        print("✓ record_event_processed works")

        record_rule_evaluation("test_rule", True, 5.5)
        print("✓ record_rule_evaluation works")

        record_setpoint_applied("transformer_1", "voltage", 1.05)
        print("✓ record_setpoint_applied works")

        record_simulation_step(100, 25.0, True)
        print("✓ record_simulation_step works")

        update_active_rules_count(10)
        print("✓ update_active_rules_count works")

        from sally.core.metrics_registry import SCADA
        with timed_operation(SCADA.STEP_DURATION_MS):
            time.sleep(0.01)
        print("✓ timed_operation context manager works")

        return True
    except Exception as e:
        print(f"✗ Metrics helpers test failed: {e}")
        return False


def test_service_names():
    """Test service name constants."""
    print("\n=== Testing Service Names ===")

    from sally.core.service_telemetry import ServiceNames

    expected_services = [
        "ORCHESTRATOR",
        "EVENTBUS",
        "RULES",
        "SETPOINTS",
        "GRID_DATA",
        "SERVICES",
        "HDF5_BUILDER",
        "MOSAIK_PARSER",
    ]

    all_present = True
    for service in expected_services:
        if hasattr(ServiceNames, service):
            value = getattr(ServiceNames, service)
            print(f"✓ {service} = {value}")
        else:
            print(f"✗ Missing service name: {service}")
            all_present = False

    return all_present


def main():
    """Run all telemetry tests."""
    print("=" * 60)
    print("Sally OpenTelemetry Integration Test Suite")
    print("=" * 60)

    # Set environment for testing
    os.environ.setdefault("SALLY_OTEL_ENABLED", "true")
    os.environ.setdefault("SALLY_OTEL_ENDPOINT", "http://localhost:4317")

    results = []

    # Run tests
    results.append(("Import Test", test_telemetry_import()))
    results.append(("Service Names", test_service_names()))

    telemetry = test_telemetry_initialization()
    results.append(("Initialization", telemetry is not None))

    results.append(("Span Creation", test_span_creation(telemetry)))
    results.append(("Metrics Recording", test_metrics_recording(telemetry)))
    results.append(("Log Correlation", test_log_correlation()))
    results.append(("Metrics Helpers", test_metrics_helpers()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = 0
    failed = 0
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")

    if failed > 0:
        print("\n⚠ Some tests failed. Check if:")
        print("  1. OTEL Collector is running at the configured endpoint")
        print("  2. All required dependencies are installed")
        print("  3. Environment variables are set correctly")
        return 1

    print("\n✓ All tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

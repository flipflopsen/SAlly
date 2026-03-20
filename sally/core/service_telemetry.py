"""
sally/core/service_telemetry.py

Service-specific telemetry initialization for Sally services.
Provides consistent telemetry configuration across all service components.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any

import yaml

from sally.core.config import config as config_module
from sally.core.logger import get_logger
from sally.core.telemetry import (
    TelemetryConfig,
    TelemetryManager,
    TelemetryMode,
    init_telemetry,
    get_telemetry,
)

logger = get_logger(__name__)


# Service name constants for consistent naming across the application
class ServiceNames:
    """Standard service names for Sally components.

    These names are used for:
    - Tempo trace filtering (service.name attribute)
    - Loki log correlation (service label)
    - Prometheus metric labels
    """
    # Core services
    ORCHESTRATOR = "SAlly.Orchestrator"
    EVENTBUS = "SAlly.EventBus"
    MAIN = "SAlly.Main"

    # Data services
    GRID_DATA = "SAlly.GridData"
    TOPOLOGY = "SAlly.GridTopology"
    DATABASE = "SAlly.Database"

    # Processing services
    RULES = "SAlly.Rules"
    SETPOINTS = "SAlly.Setpoints"
    LOAD_FORECAST = "SAlly.LoadForecast"
    STABILITY = "SAlly.Stability"

    # Bridge/Integration services
    MQTT_BRIDGE = "SAlly.MQTTBridge"
    WEBSOCKET_BRIDGE = "SAlly.WebSocketBridge"

    # GUI services
    SCADA_GUI = "SAlly.SCADA.GUI"

    # Simulation services
    SIMULATION = "SAlly.Simulation"
    MOSAIK = "SAlly.Mosaik"

    # Legacy/general
    SERVICES = "SAlly.Services"


def load_telemetry_config_from_yaml(config_path: Path) -> Dict[str, Any]:
    """
    Load telemetry configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Dictionary with telemetry configuration values
    """
    if not config_path.exists():
        logger.debug("Telemetry config file not found: %s", config_path)
        return {}

    try:
        with config_path.open("r") as fh:
            data = yaml.safe_load(fh) or {}

        # Navigate to telemetry/otel section
        otel_config = data.get("otel", data.get("telemetry", {}))
        return otel_config
    except Exception as e:
        logger.warning("Failed to load telemetry config from %s: %s", config_path, e)
        return {}


def init_service_telemetry(
    service_name: str,
    config_path: Optional[Path] = None,
    instance_id: Optional[str] = None,
    extra_attributes: Optional[Dict[str, str]] = None,
) -> TelemetryManager:
    """
    Initialize telemetry for a specific service.

    Creates a TelemetryManager configured with service-specific attributes,
    loading configuration from YAML or environment variables.

    Args:
        service_name: Unique service identifier (e.g., "SAlly.Orchestrator")
        config_path: Optional path to YAML configuration file
        instance_id: Optional instance identifier (auto-generated if not provided)
        extra_attributes: Additional attributes to attach to all telemetry

    Returns:
        Configured TelemetryManager instance

    Example:
        telemetry = init_service_telemetry(
            ServiceNames.ORCHESTRATOR,
            config_path=Path("config/scada.yml"),
            extra_attributes={"deployment": "production"}
        )
    """
    # Start with environment configuration
    base_config = TelemetryConfig.from_env()

    # Override with YAML if provided
    yaml_config = {}
    if config_path:
        yaml_config = load_telemetry_config_from_yaml(config_path)

    # Build final configuration
    enabled = yaml_config.get("enabled", base_config.enabled)
    if isinstance(enabled, str):
        enabled = enabled.lower() in ("true", "1", "yes")

    mode_str = yaml_config.get("mode", base_config.mode.value)
    try:
        mode = TelemetryMode(mode_str) if isinstance(mode_str, str) else mode_str
    except ValueError:
        mode = TelemetryMode.OTLP_GRPC

    # Generate instance ID if not provided
    if instance_id is None:
        instance_id = f"{service_name.lower().replace('.', '-')}-{uuid.uuid4().hex[:8]}"

    # Merge extra attributes
    attributes = {
        "deployment.environment": config_module.env.SALLY_DEPLOYMENT_ENV,
        "service.namespace": "sally",
        **(extra_attributes or {}),
    }

    config = TelemetryConfig(
        enabled=enabled,
        mode=mode,
        otlp_endpoint=yaml_config.get("endpoint", base_config.otlp_endpoint),
        otlp_traces_endpoint=yaml_config.get("traces_endpoint", base_config.otlp_traces_endpoint),
        otlp_metrics_endpoint=yaml_config.get("metrics_endpoint", base_config.otlp_metrics_endpoint),
        otlp_logs_endpoint=yaml_config.get("logs_endpoint", base_config.otlp_logs_endpoint),
        service_name=service_name,
        service_version=yaml_config.get("version", base_config.service_version),
        service_instance_id=instance_id,
        metrics_export_interval_ms=int(yaml_config.get("metrics_interval_ms", base_config.metrics_export_interval_ms)),
        traces_sample_rate=float(yaml_config.get("sample_rate", base_config.traces_sample_rate)),
        extra_attributes=attributes,
    )

    telemetry = init_telemetry(config)

    logger.info(
        "Service telemetry initialized: service=%s enabled=%s mode=%s endpoint=%s instance=%s",
        service_name, config.enabled, config.mode.value, config.otlp_endpoint, instance_id
    )

    return telemetry


def get_service_telemetry() -> TelemetryManager:
    """
    Get the current telemetry manager instance.

    Returns:
        The global TelemetryManager instance
    """
    return get_telemetry()


# Convenience function for quick service initialization
def quick_init_telemetry(service_name: str) -> TelemetryManager:
    """
    Quick initialization with defaults from environment.

    Args:
        service_name: Service name to use

    Returns:
        Configured TelemetryManager
    """
    return init_service_telemetry(service_name)


import time
from sally.core.metrics_registry import SERVICE, SPANS, ATTRS, DATABASE


class ServiceTelemetryMixin:
    """
    Mixin class providing standardized telemetry for Sally services.

    Provides automatic tracking of:
    - Service uptime
    - Request/operation counts
    - Error rates
    - Operation duration histograms

    Usage:
        class MyService(ServiceTelemetryMixin):
            def __init__(self):
                self._init_service_telemetry(ServiceNames.MY_SERVICE)

            def do_operation(self):
                with self._track_operation("my_operation"):
                    # ... operation logic ...
    """

    _service_name: str = ""
    _telemetry: Optional[TelemetryManager] = None
    _start_time: float = 0.0
    _operations_active: int = 0
    _operations_total: int = 0
    _errors_total: int = 0

    def _init_service_telemetry(
        self,
        service_name: str,
        telemetry: Optional[TelemetryManager] = None
    ) -> None:
        """
        Initialize service telemetry tracking.

        Args:
            service_name: The service name from ServiceNames class
            telemetry: Optional existing TelemetryManager (will get global if None)
        """
        self._service_name = service_name
        self._start_time = time.time()
        self._operations_active = 0
        self._operations_total = 0
        self._errors_total = 0

        try:
            self._telemetry = telemetry or get_telemetry()
            if self._telemetry and self._telemetry.enabled:
                self._register_service_gauges()
        except Exception as e:
            logger.warning("Failed to initialize service telemetry for %s: %s", service_name, e)

    def _register_service_gauges(self) -> None:
        """Register observable gauges for service metrics."""
        if not self._telemetry:
            return

        try:
            self._telemetry.gauge(
                f"{self._service_name.lower().replace('.', '_')}.uptime_seconds",
                lambda: time.time() - self._start_time,
                f"Uptime in seconds for {self._service_name}"
            )
            self._telemetry.gauge(
                f"{self._service_name.lower().replace('.', '_')}.operations_active",
                lambda: self._operations_active,
                f"Active operations for {self._service_name}"
            )
        except Exception as e:
            logger.debug("Failed to register service gauges: %s", e)

    def _track_operation_start(self, operation_name: str) -> float:
        """
        Track the start of an operation.

        Args:
            operation_name: Name of the operation

        Returns:
            Start time for duration calculation
        """
        self._operations_active += 1
        self._operations_total += 1
        return time.perf_counter()

    def _track_operation_end(
        self,
        operation_name: str,
        start_time: float,
        success: bool = True,
        error_type: Optional[str] = None
    ) -> None:
        """
        Track the end of an operation.

        Args:
            operation_name: Name of the operation
            start_time: Start time from _track_operation_start
            success: Whether the operation succeeded
            error_type: Type of error if failed
        """
        self._operations_active = max(0, self._operations_active - 1)
        duration_ms = (time.perf_counter() - start_time) * 1000

        if not success:
            self._errors_total += 1

        if self._telemetry and self._telemetry.enabled:
            labels = {
                SERVICE.LABEL_SERVICE_NAME: self._service_name,
                SERVICE.LABEL_OPERATION: operation_name,
                SERVICE.LABEL_STATUS: "success" if success else "error"
            }
            if error_type:
                labels[SERVICE.LABEL_ERROR_TYPE] = error_type

            self._telemetry.counter(SERVICE.OPERATIONS_TOTAL, 1, labels)
            self._telemetry.histogram(SERVICE.OPERATION_DURATION_MS, duration_ms, labels)

            if not success:
                self._telemetry.counter(SERVICE.ERRORS_TOTAL, 1, labels)

    def _track_operation(self, operation_name: str):
        """
        Context manager for tracking an operation.

        Usage:
            with self._track_operation("process_data"):
                # ... operation logic ...
        """
        from contextlib import contextmanager

        @contextmanager
        def _tracker():
            start_time = self._track_operation_start(operation_name)
            success = True
            error_type = None
            try:
                yield
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                self._track_operation_end(operation_name, start_time, success, error_type)

        return _tracker()

    def _record_service_span(
        self,
        span_name: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Create a span for this service.

        Args:
            span_name: Name of the span
            attributes: Additional span attributes

        Returns:
            Span context manager
        """
        if not self._telemetry or not self._telemetry.enabled:
            from contextlib import nullcontext
            return nullcontext()

        attrs = {
            ATTRS.SERVICE_NAME: self._service_name,
            **(attributes or {})
        }
        return self._telemetry.span(span_name, attrs)

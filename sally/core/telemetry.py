"""
sally/core/telemetry.py

OpenTelemetry integration for Sally - Traces, Metrics, and Logs export to Grafana/OTEL Collector.
This module provides centralized telemetry configuration with automatic instrumentation.
"""

from __future__ import annotations

import atexit
import functools
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

# Conditional imports for OpenTelemetry
_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, SERVICE_INSTANCE_ID
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.trace import Status, StatusCode, SpanKind
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.context import Context
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    import opentelemetry._logs as otel_logs

    _OTEL_AVAILABLE = True
except ImportError:
    pass

# Type variable for decorator
F = TypeVar('F', bound=Callable[..., Any])


class TelemetryMode(Enum):
    """Telemetry operation modes."""
    DISABLED = "disabled"           # No telemetry
    CONSOLE = "console"             # Export to console (debugging)
    OTLP_GRPC = "otlp_grpc"        # Export via OTLP gRPC (production)
    OTLP_HTTP = "otlp_http"        # Export via OTLP HTTP
    BOTH = "both"                   # Console + OTLP


@dataclass
class TelemetryConfig:
    """Configuration for OpenTelemetry integration."""
    enabled: bool = False
    mode: TelemetryMode = TelemetryMode.OTLP_GRPC

    # OTLP endpoints
    otlp_endpoint: str = "http://localhost:4317"
    otlp_traces_endpoint: Optional[str] = None  # Override for traces
    otlp_metrics_endpoint: Optional[str] = None  # Override for metrics
    otlp_logs_endpoint: Optional[str] = None    # Override for logs

    # Service identification
    service_name: str = "sally"
    service_version: str = "0.7.3"
    service_instance_id: str = field(default_factory=lambda: f"sally-{os.getpid()}")

    # Export intervals
    metrics_export_interval_ms: int = 10000  # 10 seconds
    traces_batch_size: int = 512
    traces_max_queue_size: int = 2048
    logs_batch_size: int = 512

    # Sampling
    traces_sample_rate: float = 1.0  # 1.0 = 100% sampling

    # Additional attributes
    extra_attributes: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "TelemetryConfig":
        """Load telemetry config from environment variables."""
        from sally.core.config import get_config
        cfg = get_config()

        enabled = cfg.otel.enabled
        mode_str = cfg.env.SALLY_OTEL_MODE

        try:
            mode = TelemetryMode(mode_str)
        except ValueError:
            mode = TelemetryMode.OTLP_GRPC

        return cls(
            enabled=enabled,
            mode=mode,
            otlp_endpoint=cfg.otel.endpoint,
            otlp_traces_endpoint=cfg.otel.traces_endpoint,
            otlp_metrics_endpoint=cfg.otel.metrics_endpoint,
            otlp_logs_endpoint=cfg.otel.logs_endpoint,
            service_name=cfg.otel.service_name,
            service_version=cfg.otel.service_version,
            metrics_export_interval_ms=cfg.otel.metrics_interval_ms,
            traces_sample_rate=cfg.otel.sample_rate,
        )


class TelemetryManager:
    """
    Singleton manager for OpenTelemetry instrumentation.

    Provides:
    - Trace creation and management
    - Metrics recording
    - Log export to OTLP
    - Automatic span context propagation
    """

    _instance: Optional["TelemetryManager"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[TelemetryConfig] = None):
        if self._initialized:
            return

        self._config = config or TelemetryConfig.from_env()
        self._tracer: Optional[Any] = None
        self._meter: Optional[Any] = None
        self._log_handler: Optional[logging.Handler] = None

        # Metrics storage
        self._counters: Dict[str, Any] = {}
        self._histograms: Dict[str, Any] = {}
        self._gauges: Dict[str, Any] = {}

        # Noop implementations for when OTEL is disabled
        self._noop_span = NoopSpan()

        if self._config.enabled and _OTEL_AVAILABLE:
            self._initialize_otel()

        self._initialized = True

    def _initialize_otel(self) -> None:
        """Initialize OpenTelemetry providers and exporters."""
        # Create resource with service info
        resource = Resource.create({
            SERVICE_NAME: self._config.service_name,
            SERVICE_VERSION: self._config.service_version,
            SERVICE_INSTANCE_ID: self._config.service_instance_id,
            **self._config.extra_attributes
        })

        # Initialize Tracer Provider
        tracer_provider = TracerProvider(resource=resource)

        # Configure exporters based on mode
        if self._config.mode in (TelemetryMode.CONSOLE, TelemetryMode.BOTH):
            tracer_provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )

        if self._config.mode in (TelemetryMode.OTLP_GRPC, TelemetryMode.BOTH):
            endpoint = self._config.otlp_traces_endpoint or self._config.otlp_endpoint
            otlp_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    otlp_exporter,
                    max_queue_size=self._config.traces_max_queue_size,
                    max_export_batch_size=self._config.traces_batch_size,
                )
            )

        trace.set_tracer_provider(tracer_provider)
        self._tracer = trace.get_tracer(self._config.service_name, self._config.service_version)

        # Initialize Meter Provider
        metric_readers = []

        if self._config.mode in (TelemetryMode.CONSOLE, TelemetryMode.BOTH):
            metric_readers.append(
                PeriodicExportingMetricReader(
                    ConsoleMetricExporter(),
                    export_interval_millis=self._config.metrics_export_interval_ms,
                )
            )

        if self._config.mode in (TelemetryMode.OTLP_GRPC, TelemetryMode.BOTH):
            endpoint = self._config.otlp_metrics_endpoint or self._config.otlp_endpoint
            metric_readers.append(
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=endpoint, insecure=True),
                    export_interval_millis=self._config.metrics_export_interval_ms,
                )
            )

        if metric_readers:
            meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
            metrics.set_meter_provider(meter_provider)
            self._meter = metrics.get_meter(self._config.service_name, self._config.service_version)

        # Initialize Logger Provider for OTLP log export
        logger_provider = LoggerProvider(resource=resource)

        if self._config.mode in (TelemetryMode.OTLP_GRPC, TelemetryMode.BOTH):
            endpoint = self._config.otlp_logs_endpoint or self._config.otlp_endpoint
            log_exporter = OTLPLogExporter(endpoint=endpoint, insecure=True)
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(log_exporter, max_export_batch_size=self._config.logs_batch_size)
            )

        otel_logs.set_logger_provider(logger_provider)
        self._log_handler = LoggingHandler(
            level=logging.NOTSET,
            logger_provider=logger_provider,
        )

        # Register cleanup
        atexit.register(self._shutdown)

        logging.getLogger("sally").info(
            f"OpenTelemetry initialized: mode={self._config.mode.value}, "
            f"endpoint={self._config.otlp_endpoint}"
        )

    def _shutdown(self) -> None:
        """Shutdown telemetry providers gracefully."""
        if _OTEL_AVAILABLE and self._config.enabled:
            try:
                trace.get_tracer_provider().shutdown()
                metrics.get_meter_provider().shutdown()
            except Exception:
                pass

    @property
    def enabled(self) -> bool:
        """Check if telemetry is enabled and available."""
        return self._config.enabled and _OTEL_AVAILABLE

    @property
    def log_handler(self) -> Optional[logging.Handler]:
        """Get the OTEL log handler for integration with logging."""
        return self._log_handler

    # =========================================================================
    # Tracing API
    # =========================================================================

    def start_span(
        self,
        name: str,
        kind: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[Any] = None,
        service_name: Optional[str] = None,
    ) -> Any:
        """
        Start a new span.

        Args:
            name: Span name
            kind: Span kind (client, server, producer, consumer, internal)
            attributes: Initial span attributes
            parent: Parent context
            service_name: Optional service name to override default

        Returns:
            Span object (or NoopSpan if disabled)
        """
        if not self.enabled:
            return self._noop_span

        span_kind = SpanKind.INTERNAL
        if kind:
            kind_map = {
                "client": SpanKind.CLIENT,
                "server": SpanKind.SERVER,
                "producer": SpanKind.PRODUCER,
                "consumer": SpanKind.CONSUMER,
                "internal": SpanKind.INTERNAL,
            }
            span_kind = kind_map.get(kind.lower(), SpanKind.INTERNAL)

        # Add service.name to span attributes for Tempo filtering
        svc = service_name or self._config.service_name
        span_attrs = {"service.name": svc, **(attributes or {})}

        span = self._tracer.start_span(
            name,
            kind=span_kind,
            attributes=span_attrs,
        )
        return span

    @contextmanager
    def span(
        self,
        name: str,
        kind: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        service_name: Optional[str] = None,
    ):
        """
        Context manager for creating spans.

        Args:
            name: Span name
            kind: Span kind (client, server, producer, consumer, internal)
            attributes: Initial span attributes
            service_name: Optional service name to override default

        Usage:
            with telemetry.span("process_event", attributes={"event_type": "grid_data"}):
                # ... processing ...
        """
        if not self.enabled:
            yield self._noop_span
            return

        span_kind = SpanKind.INTERNAL
        if kind:
            kind_map = {
                "client": SpanKind.CLIENT,
                "server": SpanKind.SERVER,
                "producer": SpanKind.PRODUCER,
                "consumer": SpanKind.CONSUMER,
                "internal": SpanKind.INTERNAL,
            }
            span_kind = kind_map.get(kind.lower(), SpanKind.INTERNAL)

        # Add service.name to span attributes for Tempo filtering
        svc = service_name or self._config.service_name
        span_attrs = {"service.name": svc, **(attributes or {})}

        with self._tracer.start_as_current_span(
            name,
            kind=span_kind,
            attributes=span_attrs,
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def trace(
        self,
        name: Optional[str] = None,
        kind: str = "internal",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Callable[[F], F]:
        """
        Decorator for tracing function execution.

        Usage:
            @telemetry.trace("process_rule")
            def process_rule(rule_id: str):
                ...
        """
        def decorator(func: F) -> F:
            span_name = name or f"{func.__module__}.{func.__qualname__}"

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.span(span_name, kind=kind, attributes=attributes):
                    return func(*args, **kwargs)

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.span(span_name, kind=kind, attributes=attributes):
                    return await func(*args, **kwargs)

            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def get_current_span(self) -> Any:
        """Get the current active span."""
        if not self.enabled:
            return self._noop_span
        return trace.get_current_span()

    def add_span_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the current span."""
        if not self.enabled:
            return
        span = trace.get_current_span()
        span.add_event(name, attributes=attributes or {})

    def set_span_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span."""
        if not self.enabled:
            return
        span = trace.get_current_span()
        span.set_attribute(key, value)

    # =========================================================================
    # Metrics API
    # =========================================================================

    def counter(self, name: str, value: int = 1, attributes: Optional[Dict[str, Any]] = None) -> None:
        """
        Increment a counter metric.

        Args:
            name: Metric name (e.g., "events.published")
            value: Value to add
            attributes: Metric labels/attributes
        """
        if not self.enabled or not self._meter:
            return

        if name not in self._counters:
            self._counters[name] = self._meter.create_counter(
                name,
                description=f"Counter for {name}",
            )

        self._counters[name].add(value, attributes or {})

    def histogram(self, name: str, value: float, attributes: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a histogram metric (e.g., latencies).

        Args:
            name: Metric name (e.g., "event.processing.duration_ms")
            value: Value to record
            attributes: Metric labels/attributes
        """
        if not self.enabled or not self._meter:
            return

        if name not in self._histograms:
            self._histograms[name] = self._meter.create_histogram(
                name,
                description=f"Histogram for {name}",
            )

        self._histograms[name].record(value, attributes or {})

    def gauge(
        self,
        name: str,
        callback: Callable[[], Union[int, float]],
        description: str = "",
    ) -> None:
        """
        Register an observable gauge (asynchronously updated).

        Args:
            name: Metric name
            callback: Function returning current value
            description: Metric description
        """
        if not self.enabled or not self._meter:
            return

        if name not in self._gauges:
            def observable_callback(options):
                try:
                    value = callback()
                    yield metrics.Observation(value, {})
                except Exception:
                    pass

            self._gauges[name] = self._meter.create_observable_gauge(
                name,
                callbacks=[observable_callback],
                description=description or f"Gauge for {name}",
            )


class NoopSpan:
    """No-operation span for when telemetry is disabled."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def end(self, *args, **kwargs):
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attributes: Dict[str, Any]) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def is_recording(self) -> bool:
        return False


# Global telemetry instance
_telemetry: Optional[TelemetryManager] = None


def get_telemetry(config: Optional[TelemetryConfig] = None) -> TelemetryManager:
    """Get the global telemetry manager instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetryManager(config)
    return _telemetry


def init_telemetry(config: Optional[TelemetryConfig] = None) -> TelemetryManager:
    """Initialize telemetry with explicit configuration."""
    global _telemetry
    _telemetry = TelemetryManager(config)
    return _telemetry


# Convenience exports
span = lambda name, **kwargs: get_telemetry().span(name, **kwargs)
trace_fn = lambda **kwargs: get_telemetry().trace(**kwargs)
counter = lambda name, value=1, **kwargs: get_telemetry().counter(name, value, **kwargs)
histogram = lambda name, value, **kwargs: get_telemetry().histogram(name, value, **kwargs)

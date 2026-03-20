# Sally Observability Guide

This guide provides comprehensive documentation for the Sally observability infrastructure, including OpenTelemetry integration, metrics collection, distributed tracing, and visualization.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Service Telemetry](#service-telemetry)
5. [Metrics](#metrics)
6. [Distributed Tracing](#distributed-tracing)
7. [Logging](#logging)
8. [Dashboards](#dashboards)
9. [Alerting](#alerting)
10. [Best Practices](#best-practices)
11. [Troubleshooting](#troubleshooting)

## Overview

Sally uses OpenTelemetry (OTEL) for comprehensive observability, providing:

- **Metrics**: Quantitative measurements (counters, gauges, histograms)
- **Traces**: Distributed request tracing across services
- **Logs**: Structured logging with trace correlation

The observability stack consists of:

| Component | Purpose |
|-----------|---------|
| OpenTelemetry SDK | Instrumentation in Python |
| OTEL Collector | Central telemetry aggregation |
| Prometheus | Metrics storage and querying |
| Tempo | Trace storage and querying |
| Loki | Log aggregation |
| Grafana | Visualization and dashboards |

## Architecture

### Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                     Sally Application                        │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐      │
│  │Orchestrator│ | EventBus │ │  Rules   │ │ Setpoints │      │
│  └─────┬──────┘ └─────┬────┘ └────┬─────┘ └────┬──────┘      │
│        │            │           │            │               │
│        └────────────┴───────────┴────────────┘               │
│                           │                                  │
│                    TelemetryManager                          │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │ OTLP/gRPC
                            ▼
                 ┌──────────────────────┐
                 │    OTEL Collector    │
                 │   - Batch processing │
                 │   - Resource attrs   │
                 │   - Memory limiting  │
                 └──────────┬───────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
   ┌────────────┐   ┌────────────┐   ┌────────────┐
   │ Prometheus │   │   Tempo    │   │    Loki    │
   │  Metrics   │   │   Traces   │   │    Logs    │
   └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
                   ┌──────────────┐
                   │   Grafana    │
                   └──────────────┘
```

### Service Names

Sally uses standardized service names for telemetry identification:

| Constant | Value | Usage |
|----------|-------|-------|
| `ServiceNames.ORCHESTRATOR` | `SAlly.Orchestrator` | Main SCADA orchestration |
| `ServiceNames.EVENTBUS` | `SAlly.EventBus` | High-performance event bus |
| `ServiceNames.RULES` | `SAlly.Rules` | Rule evaluation engine |
| `ServiceNames.SETPOINTS` | `SAlly.Setpoints` | Setpoint management |
| `ServiceNames.GRID_DATA` | `SAlly.GridData` | Grid data collection |
| `ServiceNames.SERVICES` | `SAlly.Services` | Async services runner |
| `ServiceNames.HDF5_BUILDER` | `SAlly.HDF5Builder` | HDF5 file operations |
| `ServiceNames.MOSAIK_PARSER` | `SAlly.MosaikParser` | Mosaik data parsing |
| `ServiceNames.GRID_TOPOLOGY` | `SAlly.GridTopology` | Grid topology tracking |
| `ServiceNames.DATABASE` | `SAlly.Database` | Database operations |
| `ServiceNames.MQTT_BRIDGE` | `SAlly.MQTTBridge` | MQTT bridge connector |
| `ServiceNames.WEBSOCKET_BRIDGE` | `SAlly.WebSocketBridge` | WebSocket bridge |
| `ServiceNames.SIMULATION` | `SAlly.Simulation` | Simulation engine |
| `ServiceNames.MOSAIK` | `SAlly.Mosaik` | Mosaik co-simulation |

## Quick Start

### 1. Start the Observability Stack

```bash
cd docker/TT-Stack
cp .env.example .env
docker-compose up -d
```

### 2. Configure Sally

```python
from sally.core.service_telemetry import init_service_telemetry, ServiceNames
from sally.core.telemetry import TelemetryConfig

# Option 1: Environment-based configuration
import os
os.environ["SALLY_OTEL_ENABLED"] = "true"
os.environ["SALLY_OTEL_ENDPOINT"] = "http://localhost:4317"

# Initialize telemetry
telemetry = init_service_telemetry(ServiceNames.ORCHESTRATOR)

# Option 2: Programmatic configuration
config = TelemetryConfig(
    enabled=True,
    service_name=ServiceNames.ORCHESTRATOR,
    otlp_endpoint="http://localhost:4317",
    export_mode="otlp",
)
telemetry = init_service_telemetry(ServiceNames.ORCHESTRATOR, config)
```

### 3. Access Dashboards

- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

## Service Telemetry

### Initialization

Each Sally service should initialize telemetry at startup:

```python
from sally.core.service_telemetry import init_service_telemetry, ServiceNames

# In main entry point
telemetry = init_service_telemetry(ServiceNames.ORCHESTRATOR)
```

### Creating Spans

Use the `span` context manager to create trace spans:

```python
from sally.core.telemetry import TelemetryManager

telemetry = TelemetryManager.get_instance()

with telemetry.span("operation.name", {"attribute": "value"}):
    # Your code here
    result = do_work()
```

### Recording Metrics

Use the telemetry manager or helper functions:

```python
# Direct API
telemetry.increment_counter("my.counter", 1.0, {"label": "value"})
telemetry.set_gauge("my.gauge", 42.0)
telemetry.record_histogram("my.latency", 15.5)

# Helper functions (recommended)
from sally.core.metrics_helpers import (
    record_event_published,
    record_simulation_step,
    update_active_rules_count,
)

record_event_published("GridMeasurementEvent")
record_simulation_step(timestep=100, duration_ms=25.0)
update_active_rules_count(15)
```

## Metrics

### Naming Convention

All Sally metrics use the `sally_` prefix with dot-separated hierarchies:

```
sally_{subsystem}_{metric_name}_{unit}
```

Examples:
- `sally_eventbus_events_published_total`
- `sally_rules_evaluation_duration_ms`
- `sally_scada_simulation_timestep`

### Metric Types

| Type | Usage | Example |
|------|-------|---------|
| Counter | Cumulative values (always increase) | Events processed |
| Gauge | Point-in-time values | Active rules count |
| Histogram | Distribution of values | Latency measurements |

### Key Metrics Reference

#### Event Bus

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `eventbus.events.published` | Counter | event_type | Events published |
| `eventbus.events.processed` | Counter | event_type | Events processed |
| `eventbus.events.dropped` | Counter | event_type | Events dropped |
| `eventbus.queue.size` | Gauge | - | Current queue depth |
| `eventbus.event.latency_ms` | Histogram | event_type | Processing latency |

#### Rules Engine

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `rules.active.count` | Gauge | - | Number of active rules |
| `rules.groups.count` | Gauge | - | Number of rule groups |
| `rules.evaluations.total` | Counter | rule_id, result | Evaluations count |
| `rules.triggered.total` | Counter | rule_id | Triggered rules |
| `rules.evaluation.duration_ms` | Histogram | rule_id | Evaluation latency |

#### SCADA & Simulation

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `scada.simulation.timestep` | Gauge | - | Current timestep |
| `scada.simulation.steps.total` | Counter | success | Steps executed |
| `scada.step.duration_ms` | Histogram | success | Step duration |
| `scada.commands.total` | Counter | command_type | Commands processed |

#### Setpoints

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `setpoints.active.count` | Gauge | - | Active setpoints |
| `setpoints.applied.total` | Counter | entity_id, attribute | Applied setpoints |
| `setpoints.value` | Gauge | entity_id, attribute | Current values |
| `setpoints.apply.duration_ms` | Histogram | - | Apply duration |

#### Database

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `db.queries.total` | Counter | query_type, table | Total queries executed |
| `db.errors.total` | Counter | query_type, error_type | Query errors |
| `db.pool.size` | Gauge | - | Connection pool size |
| `db.pool.active` | Gauge | - | Active connections |
| `db.pool.idle` | Gauge | - | Idle connections |
| `db.query.duration_ms` | Histogram | query_type | Query latency |
| `db.batch_insert.duration_ms` | Histogram | table | Batch insert latency |

#### Grid Topology

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `grid_topology.updates.total` | Counter | - | Topology updates |
| `grid_topology.entities.tracked` | Gauge | - | Entities being tracked |
| `grid_topology.connections.tracked` | Gauge | - | Connections being tracked |
| `grid_topology.update.duration_ms` | Histogram | - | Update duration |

### Using Metrics Registry

Import metric names from the centralized registry:

```python
from sally.core.metrics_registry import (
    EVENTBUS,
    RULES,
    SCADA,
    SETPOINTS,
    GRID_DATA,
    DATABASE,
    SERVICE,
    GRID_TOPOLOGY,
)

# Use constants for metric names
telemetry.increment_counter(
    EVENTBUS.EVENTS_PUBLISHED,
    labels={EVENTBUS.LABEL_EVENT_TYPE: "GridMeasurement"}
)

telemetry.set_gauge(RULES.ACTIVE_COUNT, rule_count)

# Database metrics example
telemetry.increment_counter(
    DATABASE.QUERIES_TOTAL,
    labels={"query_type": "select", "table": "entity_states"}
)
telemetry.set_gauge(DATABASE.POOL_ACTIVE, pool.get_size())

# Grid topology metrics
telemetry.set_gauge(GRID_TOPOLOGY.ENTITIES_TRACKED, len(entities))
telemetry.set_gauge(GRID_TOPOLOGY.CONNECTIONS_TRACKED, len(connections))
```

### Using ServiceTelemetryMixin

For services that need common telemetry patterns, use the mixin:

```python
from sally.core.service_telemetry import ServiceTelemetryMixin, ServiceNames

class MyService(ServiceTelemetryMixin):
    def __init__(self):
        self._init_service_telemetry(ServiceNames.MY_SERVICE)

    async def process_item(self, item):
        # Automatically tracks operation start/end and duration
        async with self._track_operation("process_item"):
            result = await self._do_processing(item)
            return result

    def sync_operation(self, data):
        # For sync operations
        with self._record_service_span("sync_operation", {"data_size": len(data)}):
            return self._process_data(data)
```

## Distributed Tracing

### Span Naming Convention

Spans follow a hierarchical naming pattern:

```
{service}.{operation}
```

Examples:
- `eventbus.publish`
- `scada.run_step`
- `rules.evaluate`
- `setpoint.apply`

### Standard Span Attributes

Use consistent attribute names from the registry:

```python
from sally.core.metrics_registry import ATTRS

# Common attributes
ATTRS.CORRELATION_ID  # "correlation_id"
ATTRS.EVENT_TYPE      # "event_type"
ATTRS.ENTITY_ID       # "entity_id"
ATTRS.RULE_ID         # "rule_id"
ATTRS.TIMESTEP        # "timestep"
```

### Creating Child Spans

Spans automatically nest when created within another span:

```python
with telemetry.span("scada.run_step", {"timestep": 100}):
    # Collect data
    with telemetry.span("grid_data.collect"):
        data = collect_measurements()

    # Evaluate rules
    with telemetry.span("rules.evaluate"):
        triggered = evaluate_rules(data)

    # Apply setpoints
    for rule in triggered:
        with telemetry.span("setpoint.apply", {"rule_id": rule.id}):
            apply_setpoint(rule.action)
```

### Querying Traces

Use TraceQL in Grafana Tempo:

```traceql
# Find all Sally traces
{ resource.service.name =~ "SAlly.*" }

# Find slow operations
{ duration > 100ms }

# Find specific rule evaluations
{ name = "rules.evaluate" && span.rule_id = "voltage_high" }

# Find error traces
{ status = error }
```

See [tempo-queries.md](../docker/TT-Stack/tempo-queries.md) for more examples.

## Logging

### Log-Trace Correlation

Sally automatically injects trace context into log records:

```python
from sally.core.logger import get_logger

logger = get_logger(__name__)

# Within a span, logs include trace_id and span_id
with telemetry.span("my.operation"):
    logger.info("Processing data")  # Includes trace context
```

Log format includes trace IDs:
```
[2024-01-15 10:30:00] [INFO] [sally.core] [module.py:42] [trace_id=abc123... span_id=def456...] Processing data
```

### Structured JSON Logging for Loki

For Loki-compatible structured logging, use the StructuredJsonFormatter:

```python
from sally.core.logger import StructuredJsonFormatter, get_logger
import logging

# Create a handler with JSON formatting
handler = logging.StreamHandler()
handler.setFormatter(StructuredJsonFormatter())

# Add to your logger
logger = get_logger(__name__)
logger.addHandler(handler)

# Log with structured data - automatically extracted as Loki labels
logger.info(
    "Event processed",
    extra={
        "entity_id": "bus_001",
        "entity_type": "Bus",
        "event_type": "VoltageViolation",
        "rule_id": "voltage_check"
    }
)
```

JSON output format:
```json
{
    "timestamp": "2024-01-15T10:30:00.123456Z",
    "level": "INFO",
    "logger": "sally.core.rules",
    "message": "Event processed",
    "trace_id": "abc123def456...",
    "span_id": "789xyz...",
    "service": "SAlly.Rules",
    "entity_id": "bus_001",
    "entity_type": "Bus",
    "event_type": "VoltageViolation"
}
```

### Loki Log Queries

Use LogQL in Grafana to query logs:

```logql
# All Sally logs
{service=~"SAlly.*"}

# Filter by level
{service=~"SAlly.*"} |= "ERROR"

# Parse JSON and filter by entity
{service=~"SAlly.*"} | json | entity_id = "bus_001"

# Count events by type
sum by (event_type) (count_over_time({service=~"SAlly.*"} | json [5m]))
```

### Structured Logging

Use structured logging for better searchability:

```python
logger.info(
    "Rule triggered",
    extra={
        "rule_id": rule.id,
        "entity_id": entity.id,
        "new_value": value,
    }
)
```

## Dashboards

### Pre-built Dashboards

Sally includes pre-configured Grafana dashboards:

| Dashboard | Description |
|-----------|-------------|
| Sally Overview | High-level system health and summary |
| Sally Health | System health with database metrics |
| Sally EventBus | Event bus publish/process metrics |
| Sally Rules | Rule evaluation and triggers |
| Sally SCADA | Simulation step metrics |
| Sally Setpoints | Setpoint tracking and values |
| Sally Grid | Grid topology and entity metrics |

### Dashboard Panels

Each dashboard includes:

- **Stat panels**: Current values (active rules, setpoints)
- **Time series**: Trends over time (events/sec, latency)
- **Bar charts**: Top-N analysis (triggered rules)
- **Tables**: Current state (setpoint values)
- **Heatmaps**: Distribution analysis (latency percentiles)

### Custom Dashboards

Create custom dashboards using Prometheus queries:

```promql
# Event rate by type
rate(sally_eventbus_events_published_total[1m])

# P99 latency
histogram_quantile(0.99, rate(sally_eventbus_event_latency_ms_bucket[5m]))

# Active rules count
sally_rules_active_count

# Setpoint values
sally_setpoints_value{entity_id="transformer_1"}
```

## Alerting

### Example Alert Rules

Create alerts in Grafana or Prometheus:

```yaml
# High event drop rate
- alert: HighEventDropRate
  expr: rate(sally_eventbus_events_dropped_total[5m]) > 10
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: High event drop rate detected

# Slow simulation steps
- alert: SlowSimulationStep
  expr: histogram_quantile(0.99, rate(sally_scada_step_duration_ms_bucket[5m])) > 500
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: Simulation steps taking too long

# No events processed
- alert: NoEventsProcessed
  expr: rate(sally_eventbus_events_processed_total[5m]) == 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: No events being processed
```

## Best Practices

### 1. Use Consistent Naming

Always use constants from the metrics registry:

```python
from sally.core.metrics_registry import EVENTBUS, SPANS, ATTRS

# Good
telemetry.increment_counter(EVENTBUS.EVENTS_PUBLISHED)

# Bad
telemetry.increment_counter("my.custom.metric")
```

### 2. Add Context to Spans

Include relevant attributes for debugging:

```python
with telemetry.span(SPANS.SCADA_RUN_STEP, {
    ATTRS.TIMESTEP: timestep,
    ATTRS.SUCCESS: True,
    "entity_count": len(entities),
}):
    process_step()
```

### 3. Use Helper Functions

Prefer helper functions for common operations:

```python
from sally.core.metrics_helpers import record_simulation_step

# Good - uses helper
record_simulation_step(timestep=100, duration_ms=25.0)

# Verbose - manual recording
telemetry.increment_counter(SCADA.SIMULATION_STEPS_TOTAL)
telemetry.set_gauge(SCADA.SIMULATION_TIMESTEP, 100)
telemetry.record_histogram(SCADA.STEP_DURATION_MS, 25.0)
```

### 4. Mind Cardinality

Avoid high-cardinality labels that can explode metric storage:

```python
# Bad - unbounded cardinality
telemetry.increment_counter("requests", labels={"request_id": unique_id})

# Good - bounded cardinality
telemetry.increment_counter("requests", labels={"endpoint": "/api/data"})
```

### 5. Sample Long-Running Operations

For high-frequency operations, consider sampling:

```python
import random

if random.random() < 0.01:  # 1% sampling
    with telemetry.span("high_frequency.operation"):
        process()
else:
    process()
```

## Troubleshooting

### No Metrics Appearing

1. Verify telemetry is enabled:
   ```python
   from sally.core.telemetry import TelemetryManager
   tm = TelemetryManager.get_instance()
   print(tm.config.enabled)  # Should be True
   ```

2. Check OTEL Collector is running:
   ```bash
   curl http://localhost:8889/metrics | grep sally
   ```

3. Check Prometheus targets:
   - http://localhost:9090/targets

### No Traces Appearing

1. Verify spans are being created:
   ```python
   import logging
   logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
   ```

2. Check Tempo is receiving traces:
   ```bash
   docker-compose logs tempo | grep -i trace
   ```

### Log-Trace Correlation Not Working

1. Verify CorrelationIdFilter is added:
   ```python
   from sally.core.logger import LoggerFactory
   factory = LoggerFactory()
   # Check filters on root logger
   ```

2. Ensure logging happens within span context:
   ```python
   with telemetry.span("operation"):
       logger.info("This should have trace context")
   ```

### High Memory Usage

1. Reduce batch sizes in collector config
2. Reduce metric cardinality
3. Increase collector memory limits

### Running Tests

Validate telemetry setup:

```bash
# Unit tests
python scripts/test_telemetry.py

# Load tests
python scripts/load_test_telemetry.py --events 1000 --duration 30
```

## Further Resources

- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Querying](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Tempo TraceQL](https://grafana.com/docs/tempo/latest/traceql/)
- [TT-Stack README](../docker/TT-Stack/README.md)

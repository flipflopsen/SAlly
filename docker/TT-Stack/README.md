# TT-Stack

TT-Stack stands for **Telemetry and Timescale** stack, combining Grafana, Prometheus, OpenTelemetry, and TimescaleDB.

The architecture follows the industry-standard OTLP push model: Your Python app pushes telemetry (Metrics/Traces) via OTLP to the OTEL Collector. The Collector then exports metrics to a Prometheus scrape endpoint and traces to Tempo. Grafana visualizes both.

This is useful for us because network control centers often already have a running Grafana Instance and adding a new Dashboard to it and connecting to their Timeseries Database could be done without a lot of work, since it's already often used and proven technology.

## Quick Start

1. **Copy environment file and configure**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

2. **Start the stack**:
   ```bash
   docker-compose up -d
   ```

3. **Access services**:
   - Grafana: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090
   - OTEL Collector metrics: http://localhost:8889/metrics

4. **Configure Sally application**:
   ```bash
   export SALLY_OTEL_ENABLED=true
   export SALLY_OTEL_ENDPOINT=http://localhost:4317
   export SALLY_OTEL_SERVICE_NAME=SAlly.Orchestrator
   ```

5. **Run Sally**:
   ```bash
   python -m sally.main_scada_full
   ```

## Architecture

```
┌─────────────────┐     OTLP/gRPC      ┌──────────────────┐
│  Sally Python   │ ─────────────────► │  OTEL Collector  │
│  Application    │     :4317          │                  │
└─────────────────┘                    └────────┬─────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
            ┌───────────────┐           ┌───────────────┐           ┌───────────────┐
            │  Prometheus   │           │    Tempo      │           │    Loki       │
            │  (Metrics)    │           │   (Traces)    │           │   (Logs)      │
            └───────┬───────┘           └───────┬───────┘           └───────┬───────┘
                    │                           │                           │
                    └───────────────────────────┼───────────────────────────┘
                                                │
                                                ▼
                                        ┌───────────────┐
                                        │    Grafana    │
                                        │  (Dashboard)  │
                                        └───────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Grafana | 3000 | Visualization and dashboards |
| Prometheus | 9090 | Metrics storage and querying |
| OTEL Collector | 4317 | OTLP gRPC receiver |
| OTEL Collector | 4318 | OTLP HTTP receiver |
| OTEL Collector | 8889 | Prometheus metrics exporter |
| Tempo | 3200 | Trace storage and querying |
| Loki | 3100 | Log aggregation |

## Pre-configured Dashboards

The stack includes pre-configured Grafana dashboards:

- **Sally Overview** - High-level system health and performance
- **Sally EventBus** - Event bus throughput, latency, and queue depth
- **Sally Rules** - Rule evaluation metrics and triggered rules
- **Sally SCADA** - Simulation steps, commands, and grid data
- **Sally Setpoints** - Setpoint values and change history

Dashboards are auto-provisioned from the `dashboards/` directory.

## Sally Service Names

Sally uses standardized service names for telemetry:

| Service Name | Description |
|--------------|-------------|
| `SAlly.Orchestrator` | Main SCADA orchestration service |
| `SAlly.EventBus` | High-performance event bus |
| `SAlly.Rules` | Rule evaluation engine |
| `SAlly.Setpoints` | Setpoint management service |
| `SAlly.GridData` | Grid data collection service |
| `SAlly.Services` | Async services runner |

## Key Metrics

### Event Bus
- `sally_eventbus_events_published_total` - Events published by type
- `sally_eventbus_events_processed_total` - Events processed by type
- `sally_eventbus_events_dropped_total` - Dropped events
- `sally_eventbus_event_latency_ms` - Event processing latency

### Rules Engine
- `sally_rules_active_count` - Number of active rules
- `sally_rules_evaluations_total` - Rule evaluations by result
- `sally_rules_triggered_total` - Rules triggered by rule_id
- `sally_rules_evaluation_duration_ms` - Evaluation latency

### SCADA & Simulation
- `sally_scada_simulation_timestep` - Current simulation timestep
- `sally_scada_step_duration_ms` - Step execution duration
- `sally_scada_commands_total` - Commands by type

### Setpoints
- `sally_setpoints_active_count` - Active setpoints
- `sally_setpoints_applied_total` - Setpoints applied
- `sally_setpoints_value` - Current setpoint values

## TraceQL Queries

See [tempo-queries.md](tempo-queries.md) for TraceQL query examples.

Common queries:
```traceql
# Find all traces from Sally services
{ resource.service.name =~ "SAlly.*" }

# Find slow operations (>100ms)
{ duration > 100ms }

# Find rule evaluations
{ name = "rules.evaluate" }

# Find triggered rules
{ span.rule_triggered = true }
```

## Service Graph

**Tempo's Service Graph visualizes service-to-service relationships** by analyzing trace spans.

**View Service Graph:**
- Navigate to Grafana → Explore
- Select **Tempo** datasource
- Choose **Service Graph** query type

**Expected Services:**
- `SAlly.SCADA.GUI` → `SAlly.Orchestrator` → `SAlly.Simulation`
- `SAlly.EventBus` (producer)

**Metrics Generated:**
- `traces_service_graph_request_total` - Request rate between services
- `traces_service_graph_request_failed_total` - Error rate
- `traces_service_graph_request_server_seconds` - Latency histograms

For detailed setup and troubleshooting, see [SERVICE-GRAPH-SETUP.md](SERVICE-GRAPH-SETUP.md).

## Configuration

### OTEL Collector

The `otel-collector-config.yaml` specifies the 'scrape interval', which should always be lower than the simulation speed, in the best case half of it or even a little less.
So if simulation speed is values every 5 minutes, OTEL should scrape at least every minute in order to collect the User input of Setpoints, watch system health while the simulation(s) is/are running and check on the specified Rules (which will be Spans).

Key configuration sections:
- **receivers** - OTLP gRPC/HTTP endpoints
- **processors** - Batching, memory limits, resource attributes
- **exporters** - Prometheus, Tempo, Loki destinations
- **service/pipelines** - Route traces, metrics, logs to exporters

### Prometheus

The `prometheus.yaml` configures:
- Scrape targets (OTEL Collector metrics endpoint)
- Metric relabeling for service name extraction
- Retention settings (default: 7 days)

### Environment Variables

See `.env.example` for all available configuration:

```bash
# Sally OTEL Configuration
SALLY_OTEL_ENABLED=true
SALLY_OTEL_ENDPOINT=http://otel-collector:4317
SALLY_OTEL_EXPORT_MODE=otlp

# Collector Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

## Troubleshooting

### No data in Grafana

1. Check OTEL Collector is running:
   ```bash
   docker-compose logs otel-collector
   ```

2. Verify Sally is sending telemetry:
   ```bash
   curl http://localhost:8889/metrics | grep sally
   ```

3. Check Prometheus targets:
   - Go to http://localhost:9090/targets
   - Verify `otel-collector` target is UP

### No traces in Tempo

1. Check Tempo is receiving traces:
   ```bash
   docker-compose logs tempo
   ```

2. Verify Sally has tracing enabled:
   ```python
   from sally.core.telemetry import TelemetryManager
   tm = TelemetryManager.get_instance()
   print(tm.config.enabled)  # Should be True
   ```

### High memory usage

1. Reduce batch sizes in `otel-collector-config.yaml`
2. Increase memory limits for collector container
3. Reduce Prometheus retention period

## Testing Telemetry

Run the telemetry test suite:
```bash
python scripts/test_telemetry.py
```

Run load tests:
```bash
python scripts/load_test_telemetry.py --events 1000 --duration 30
```

## Further Reading

- [Observability Guide](../../doc/observability-guide.md) - Comprehensive observability documentation
- [Tempo Queries](tempo-queries.md) - TraceQL query examples
- [Grafana Explore Queries](grafana-explore-queries.json) - Saved query templates

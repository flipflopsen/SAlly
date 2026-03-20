# Service Graph Setup for Tempo

This document describes the Service Graph feature configuration for visualizing service-to-service relationships in Sally.

## What is Service Graph?

Service Graph visualizes the relationships between services by analyzing trace spans. It shows:
- Which services call which other services
- Request rates between services
- Error rates between services
- Latency distributions between services

## Architecture

```
┌─────────────┐  client   ┌──────────────────┐  client   ┌─────────────┐
│  SCADA GUI  │ ────────> │   Orchestrator   │ ────────> │ Simulation  │
└─────────────┘           └──────────────────┘           └─────────────┘
   (client)      peer.svc      (server)         peer.svc     (server)
                                    │
                                    │ producer
                                    ▼
                              ┌──────────┐
                              │ EventBus │
                              └──────────┘
```

## Configuration Components

### 1. Tempo Metrics Generator (`tempo.yaml`)

**Enabled Features:**
- `service_graphs`: Generates service-to-service metrics
- `span_metrics`: Generates per-span latency metrics

**Metrics Generated:**
- `traces_service_graph_request_total` - Total requests between services
- `traces_service_graph_request_failed_total` - Failed requests between services
- `traces_service_graph_request_server_seconds` - Server-side latency histogram
- `traces_service_graph_request_client_seconds` - Client-side latency histogram
- `traces_spanmetrics_latency_bucket` - Per-span latency histograms

**Key Configuration:**
```yaml
metrics_generator:
  processor:
    service_graphs:
      enabled: true
      histogram_buckets: [0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8]
      dimensions:
        - service.name
        - service.namespace
```

### 2. Prometheus Scrape Config (`prometheus.yaml`)

Prometheus scrapes metrics from Tempo's metrics generator endpoint:

```yaml
scrape_configs:
  - job_name: 'tempo'
    static_configs:
      - targets: ['tempo:3200']
```

### 3. Grafana Datasource Configuration (`grafana-datasources.yaml`)

Tempo datasource is configured to use Prometheus for service graph:

```yaml
jsonData:
  serviceMap:
    datasourceUid: "prometheus"
```

### 4. Application Instrumentation

**Span Kinds Used:**
- `CLIENT`: Service making a call to another service (e.g., GUI → Orchestrator)
- `SERVER`: Service handling an incoming request (e.g., Orchestrator handling commands)
- `PRODUCER`: Publishing events (e.g., EventBus)
- `INTERNAL`: Within-service operations

**Key Attributes:**
- `service.name`: Identifies the service (e.g., "SAlly.SCADA.GUI", "SAlly.Orchestrator", "SAlly.Simulation")
- `peer.service`: Identifies the target service in client spans

**Service Relationships Instrumented:**

1. **SCADA GUI → Orchestrator**
   - Client spans in GUI for `toggle_play`, `apply_setpoint`
   - Server spans in Orchestrator for command processing

2. **Orchestrator → Simulation**
   - Client spans when calling `simulation.step()`, `simulation.set_setpoint()`
   - Server spans at Simulation entry points

3. **EventBus → Consumers**
   - Producer spans when publishing events

## How to View Service Graph

### In Grafana:

1. **Explore View:**
   - Navigate to **Explore** tab
   - Select **Tempo** datasource
   - Choose **Service Graph** query type
   - View the interactive service map

2. **Service Graph Panel:**
   - Create a new dashboard or use existing one
   - Add a panel with visualization type: **Node Graph**
   - Set datasource to **Tempo**
   - Query: Use service graph metrics from Prometheus

3. **Metrics to Use:**
   ```promql
   # Request rate between services
   rate(traces_service_graph_request_total[5m])

   # Error rate between services
   rate(traces_service_graph_request_failed_total[5m])

   # P95 latency between services
   histogram_quantile(0.95,
     rate(traces_service_graph_request_server_seconds_bucket[5m]))
   ```

## Expected Service Nodes

When properly configured, you should see these services in the graph:

- **SAlly.SCADA.GUI** - User interface
- **SAlly.Orchestrator** - Main orchestration service
- **SAlly.Simulation** - Simulation engine
- **SAlly.EventBus** - Event publishing system

## Troubleshooting

### Service Graph is empty:

1. **Check Tempo metrics are being scraped by Prometheus:**
   ```
   # In Prometheus UI (localhost:9090)
   traces_service_graph_request_total
   ```

2. **Verify spans have proper attributes:**
   - Check traces in Tempo for `service.name` attribute
   - Client spans should have `peer.service` attribute
   - Span kinds should be set correctly (CLIENT, SERVER, PRODUCER)

3. **Check Tempo logs:**
   ```bash
   docker logs tt-stack-tempo-1
   ```

4. **Verify metrics generator is running:**
   - Tempo should expose metrics at `http://tempo:3200/metrics`
   - Check for `tempo_metrics_generator_*` metrics

### Services not connected:

1. Ensure client spans have `peer.service` attribute pointing to the target service
2. Verify span kinds are correct (CLIENT calling SERVER)
3. Check that both client and server spans have proper `service.name` attributes

### Restart Stack:

After configuration changes, restart the stack:
```powershell
.\docker\TT-Stack\Stop-TTStack.ps1
.\docker\TT-Stack\Start-TTStack.ps1
```

## Additional Resources

- [Grafana Tempo Service Graph Docs](https://grafana.com/docs/grafana/latest/datasources/tempo/service-graph/)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)

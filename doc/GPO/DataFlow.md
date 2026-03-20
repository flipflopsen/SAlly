# Summary of Data Flow

| Telemetry Type | Source (Python)                 | Collector Receiver | Collector Exporter  | Backend DB | Visualization |
| -------------- | ------------------------------- | ------------------ | ------------------- | ---------- | ------------- |
| Metrics        | opentelemetry-instrumentation-* | OTLP (4317)        | Prometheus Exporter | Prometheus | Grafana       |
| Traces         | opentelemetry-sdk               | OTLP (4317)        | OTLP Exporter       | Tempo      | Grafana       |
| Logs           | logging module                  | OTLP (4317)        | OTLP HTTP Exporter  | Loki       | Grafana       |

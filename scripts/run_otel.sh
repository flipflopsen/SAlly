#!/bin/bash

# --- Configuration ---
export OTEL_SERVICE_NAME="thesis-sally-repo"
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
export OTEL_EXPORTER_OTLP_PROTOCOL="grpc"

# Force exporters to use OTLP (Collector)
export OTEL_TRACES_EXPORTER="otlp"
export OTEL_METRICS_EXPORTER="otlp"
export OTEL_LOGS_EXPORTER="otlp"

# Enable Logging Instrumentation (ships logs to Loki via Collector)
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED="true"

# --- Execution ---
# Default to "sally-dev" if no arguments are passed
cd ../

CMD="${@:-sally-dev}"

echo -e "\033[1;36m🧠 Launching: $CMD\033[0m"
echo -e "\033[0;90m📡 Telemetry: $OTEL_EXPORTER_OTLP_ENDPOINT ($OTEL_EXPORTER_OTLP_PROTOCOL)\033[0m"

# Check if opentelemetry-instrument exists
if ! command -v opentelemetry-instrument &> /dev/null; then
    echo -e "\033[0;31mCRITICAL: 'opentelemetry-instrument' not found.\033[0m"
    echo "Run: uv pip install '.[otel]' and 'uv opentelemetry-bootstrap -a install'"
    exit 1
fi

# exec replaces the shell process with the python process (better signal handling)
exec uv opentelemetry-instrument $CMD

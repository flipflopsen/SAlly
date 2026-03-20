# Running the Stack
## Step 1: Start Infrastructure
Run this in your project root where docker-compose.yaml is located.

```bash
docker-compose up -d
```


## Step 2: Run Python Application
The opentelemetry-bootstrap command installs library-specific hooks (like for Flask/Requests).

Common Install Steps:

```bash
# Create venv
python -m venv venv
# Install deps
pip install -r requirements.txt
# Install auto-instrumentation libraries
opentelemetry-bootstrap -a install
```

Run Command (Windows PowerShell):>

```powershell
# Set Service Name and Endpoint
$env:OTEL_SERVICE_NAME = "python-backend-service"
$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"

# Run with instrumentation wrapper
opentelemetry-instrument `
    --traces_exporter otlp `
    --metrics_exporter otlp `
    --logs_exporter console `
    python main.py
```

Run Command (Linux / WSL2):

```bash
export OTEL_SERVICE_NAME="python-backend-service"
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"

opentelemetry-instrument \
    --traces_exporter otlp \
    --metrics_exporter otlp \
    --logs_exporter console \
    python main.py
```

> [!CAUTION]
Ensure your Docker ports (4317) are exposed to localhost. If running Python inside WSL2 and Docker on Windows, localhost works fine. If running Python in a separate Docker container, change the OTLP endpoint to http://otel-collector:4317.

<#
.SYNOPSIS
    Runs the Sally application with OpenTelemetry instrumentation using uv.
.DESCRIPTION
    This script navigates to the repository root, configures the OTEL environment variables,
    and uses 'uv run' to execute the target command inside the project's virtual environment.
.EXAMPLE
    .\scripts\run_otel.ps1
    .\scripts\run_otel.ps1 sally-web
    .\scripts\run_otel.ps1 python scripts/my_script.py
#>

param (
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

# --- Path Resolution ---
# Ensure we run from the Repo Root.
# Assuming this script is located in a subfolder (e.g., ./scripts/), we go up one level.
# If this script is in the root, remove the 'Split-Path -Parent' part.
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -Path $RepoRoot

Write-Host "📂 Working Directory: $RepoRoot" -ForegroundColor DarkGray

# --- Configuration ---
$env:OTEL_SERVICE_NAME = "thesis-sally-repo"
$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"
$env:OTEL_EXPORTER_OTLP_PROTOCOL = "grpc"

# Force exporters to use OTLP (Collector)
$env:OTEL_TRACES_EXPORTER = "otlp"
$env:OTEL_METRICS_EXPORTER = "otlp"
$env:OTEL_LOGS_EXPORTER = "otlp"

# Enable Logging Instrumentation (ships logs to Loki via Collector)
$env:OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED = "true"

# --- Execution ---
# Default to "sally-dev" if no arguments are passed
$TargetCommand = if ($CommandArgs) { $CommandArgs } else { "sally-dev" }

Write-Host "🧠 Launching via uv: $TargetCommand" -ForegroundColor Cyan
Write-Host "📡 Telemetry: $env:OTEL_EXPORTER_OTLP_ENDPOINT ($env:OTEL_EXPORTER_OTLP_PROTOCOL)" -ForegroundColor DarkGray

# Check if uv is installed
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Error "CRITICAL: 'uv' not found. Please install uv (https://github.com/astral-sh/uv)."
    exit 1
}

# 1. Use 'uv run' to execute inside the venv.
# 2. We inject 'opentelemetry-instrument' as the entry point.
# 3. We pass the user's target command as arguments to the instrumentor.
uv run opentelemetry-instrument $TargetCommand

if ($LASTEXITCODE -ne 0) {
    Write-Warning "⚠️ Process exited with code $LASTEXITCODE"
    # Optional: Suggest dependency check if it failed immediately
    if ($LASTEXITCODE -eq 1) {
        Write-Host "Hint: If the command failed to start, ensure you have run: uv sync --all-extras" -ForegroundColor Yellow
    }
}

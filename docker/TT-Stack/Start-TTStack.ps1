<#
.SYNOPSIS
    Starts the TT-Stack (Telemetry-Timescale-Stack) observability and data storage stack.

.DESCRIPTION
    This script starts the Docker Compose stack for Sally observability.
    It ensures the .env file exists, starts the containers, and optionally
    opens Grafana in the default browser.

.PARAMETER Down
    Stop and remove the stack instead of starting it.

.PARAMETER Restart
    Restart the stack (stop then start).

.PARAMETER Logs
    Follow the logs after starting.

.PARAMETER OpenBrowser
    Open Grafana in the default browser after starting.

.PARAMETER Build
    Force rebuild of containers before starting.

.EXAMPLE
    .\Start-TTStack.ps1
    Starts the TT-Stack.

.EXAMPLE
    .\Start-TTStack.ps1 -OpenBrowser
    Starts the TT-Stack and opens Grafana in browser.

.EXAMPLE
    .\Start-TTStack.ps1 -Down
    Stops and removes the TT-Stack.

.EXAMPLE
    .\Start-TTStack.ps1 -Logs
    Starts the stack and follows logs.
#>

[CmdletBinding()]
param(
    [switch]$Down,
    [switch]$Restart,
    [switch]$Logs,
    [switch]$OpenBrowser,
    [switch]$Build
)

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptDir

try {
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  TT-Stack - Sally Observability     " -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host ""

    # Check Docker is running
    $dockerStatus = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
        exit 1
    }

    # Ensure .env file exists
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
            Copy-Item ".env.example" ".env"
        } else {
            Write-Host "WARNING: No .env file found. Using defaults." -ForegroundColor Yellow
        }
    }

    # Handle Down
    if ($Down) {
        Write-Host "Stopping TT-Stack..." -ForegroundColor Yellow
        docker-compose down -v
        Write-Host "TT-Stack stopped." -ForegroundColor Green
        exit 0
    }

    # Handle Restart
    if ($Restart) {
        Write-Host "Restarting TT-Stack..." -ForegroundColor Yellow
        docker-compose down
        Start-Sleep -Seconds 2
    }

    # Build if requested
    $composeArgs = @("up", "-d")
    if ($Build) {
        $composeArgs += "--build"
    }

    # Start the stack
    Write-Host "Starting TT-Stack..." -ForegroundColor Yellow
    docker-compose @composeArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to start TT-Stack." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "TT-Stack started successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Services:" -ForegroundColor Cyan
    Write-Host "  Grafana:          http://localhost:3000  (admin/admin)" -ForegroundColor White
    Write-Host "  Prometheus:       http://localhost:9090" -ForegroundColor White
    Write-Host "  OTEL Collector:   localhost:4317 (gRPC), localhost:4318 (HTTP)" -ForegroundColor White
    Write-Host "  Tempo:            http://localhost:3200" -ForegroundColor White
    Write-Host "  Loki:             http://localhost:3100" -ForegroundColor White
    Write-Host "  TimescaleDB:      postgresql://localhost:5432/sally_grid (postgres/password)" -ForegroundColor White
    Write-Host ""

    # Open browser if requested
    if ($OpenBrowser) {
        Write-Host "Opening Grafana in browser..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3  # Wait for Grafana to be ready
        Start-Process "http://localhost:3000"
    }

    # Follow logs if requested
    if ($Logs) {
        Write-Host "Following logs (Ctrl+C to exit)..." -ForegroundColor Yellow
        Write-Host ""
        docker-compose logs -f
    }

    Write-Host "To configure Sally, set these environment variables:" -ForegroundColor Cyan
    Write-Host '  $env:SALLY_OTEL_ENABLED = "true"' -ForegroundColor White
    Write-Host '  $env:SALLY_OTEL_ENDPOINT = "http://localhost:4317"' -ForegroundColor White
    Write-Host ""

} finally {
    Pop-Location
}

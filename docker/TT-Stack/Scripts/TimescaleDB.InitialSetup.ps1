<#
.SYNOPSIS
    Initializes TimescaleDB with required tables and indexes for Sally grid data storage.

.DESCRIPTION
    This script sets up the TimescaleDB database for the Sally system by:
    1. Waiting for TimescaleDB to be ready
    2. Creating the sally_grid database if it doesn't exist
    3. Enabling the TimescaleDB extension
    4. Creating required tables (grid_data, grid_events, load_forecasts)
    5. Creating indexes for optimal query performance

.PARAMETER ContainerName
    The name of the TimescaleDB Docker container. Default: "tt-stack-timescaledb-1"

.PARAMETER Database
    The target database name. Default: "sally_grid"

.PARAMETER PostgresPassword
    The PostgreSQL password. Default: "password"

.PARAMETER MaxRetries
    Maximum number of connection retry attempts. Default: 30

.EXAMPLE
    .\TimescaleDB.InitialSetup.ps1
    Initializes the database using default settings.

.EXAMPLE
    .\TimescaleDB.InitialSetup.ps1 -ContainerName "timescaledb" -Database "my_grid"
    Initializes with custom container and database names.
#>

[CmdletBinding()]
param(
    [string]$ContainerName = "tt-stack-timescaledb-1",
    [string]$Database = "sally_grid",
    [string]$PostgresPassword = "password",
    [int]$MaxRetries = 30
)

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SqlDir = Join-Path $ScriptDir "sql"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  TimescaleDB Initial Setup          " -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if SQL directory exists
if (-not (Test-Path $SqlDir)) {
    Write-Host "ERROR: SQL directory not found at: $SqlDir" -ForegroundColor Red
    exit 1
}

# Wait for TimescaleDB to be ready
Write-Host "Waiting for TimescaleDB to be ready..." -ForegroundColor Yellow
$retries = 0
$ready = $false

while (-not $ready -and $retries -lt $MaxRetries) {
    $retries++
    try {
        $result = docker exec $ContainerName pg_isready -U postgres 2>&1
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            Write-Host "✓ TimescaleDB is ready!" -ForegroundColor Green
        } else {
            Write-Host "  Attempt $retries/$MaxRetries - waiting..." -ForegroundColor Gray
            Start-Sleep -Seconds 2
        }
    } catch {
        Write-Host "  Attempt $retries/$MaxRetries - waiting..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Host "ERROR: TimescaleDB did not become ready after $MaxRetries attempts" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Function to execute SQL file
function Invoke-SqlFile {
    param(
        [string]$SqlFile,
        [string]$Description
    )

    Write-Host "Executing: $Description" -ForegroundColor Cyan
    Write-Host "  File: $SqlFile" -ForegroundColor Gray

    if (-not (Test-Path $SqlFile)) {
        Write-Host "  ERROR: SQL file not found: $SqlFile" -ForegroundColor Red
        return $false
    }

    try {
        $result = Get-Content $SqlFile | docker exec -i $ContainerName psql -U postgres -d $Database 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Success" -ForegroundColor Green
            return $true
        } else {
            Write-Host "  ✗ Failed: $result" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "  ✗ Error: $_" -ForegroundColor Red
        return $false
    }
}

# Create database and enable TimescaleDB extension
Write-Host "Setting up database..." -ForegroundColor Cyan
docker exec $ContainerName psql -U postgres -c "CREATE DATABASE $Database;" 2>&1 | Out-Null
docker exec $ContainerName psql -U postgres -d $Database -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Database and extension ready" -ForegroundColor Green
} else {
    Write-Host "  Note: Database or extension may already exist (this is normal)" -ForegroundColor Yellow
}

Write-Host ""

# Execute SQL files in order
$sqlFiles = @(
    @{
        File = Join-Path $SqlDir "create_grid_data_table.sql"
        Description = "Creating grid_data hypertable"
    },
    @{
        File = Join-Path $SqlDir "create_grid_entities_table.sql"
        Description = "Creating grid_entities table and adding FK to grid_data"
    },
    @{
        File = Join-Path $SqlDir "create_grid_data_indexes.sql"
        Description = "Creating indexes on grid_data"
    },
    @{
        File = Join-Path $SqlDir "create_grid_entity_connections_table.sql"
        Description = "Creating grid_entity_connections table"
    },
    @{
        File = Join-Path $SqlDir "create_grid_events_table.sql"
        Description = "Creating grid_events hypertable"
    },
    @{
        File = Join-Path $SqlDir "create_load_forecasts_table.sql"
        Description = "Creating load_forecasts hypertable"
    }
)

$allSuccess = $true
foreach ($sqlFile in $sqlFiles) {
    $success = Invoke-SqlFile -SqlFile $sqlFile.File -Description $sqlFile.Description
    if (-not $success) {
        $allSuccess = $false
    }
    Write-Host ""
}

# Summary
Write-Host "======================================" -ForegroundColor Cyan
if ($allSuccess) {
    Write-Host "✓ TimescaleDB setup completed successfully!" -ForegroundColor Green
} else {
    Write-Host "⚠ TimescaleDB setup completed with some errors" -ForegroundColor Yellow
}
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Connection string: postgresql://postgres:$PostgresPassword@localhost:5432/$Database" -ForegroundColor Gray
Write-Host ""

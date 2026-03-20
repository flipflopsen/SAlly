<#
.SYNOPSIS
    Stops the TT-Stack (Telemetry-Timescale-Stack) observability and data storage stack.

.PARAMETER RemoveVolumes
    Also remove Docker volumes (deletes all stored data).

.EXAMPLE
    .\Stop-TTStack.ps1
    Stops the TT-Stack, keeping volumes.

.EXAMPLE
    .\Stop-TTStack.ps1 -RemoveVolumes
    Stops the TT-Stack and removes all data.
#>

[CmdletBinding()]
param(
    [switch]$RemoveVolumes
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptDir

try {
    Write-Host "Stopping TT-Stack..." -ForegroundColor Yellow

    if ($RemoveVolumes) {
        Write-Host "Removing volumes (all data will be deleted)..." -ForegroundColor Red
        docker-compose down -v
    } else {
        docker-compose down
    }

    Write-Host "TT-Stack stopped." -ForegroundColor Green

} finally {
    Pop-Location
}

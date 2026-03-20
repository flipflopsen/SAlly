Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Starting SCADA (HDF5 simulation + orchestrator + GUI)" -ForegroundColor Cyan
Start-Process -FilePath "uv" -ArgumentList "run", ".\sally\main_scada_full.py" -WorkingDirectory $repoRoot

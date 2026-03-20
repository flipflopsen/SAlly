# PowerShell script to run both Django backend and Vite frontend in separate terminals

$ErrorActionPreference = "Stop"

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "🌟 SAlly Simbuilder Development Server Launcher" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host ""

# Get the script directory (sally/simbuilder)
$SimbuilderDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $SimbuilderDir "frontend"

# Check if we're in a virtual environment
if (-not $env:VIRTUAL_ENV) {
    Write-Host "⚠️  Warning: No virtual environment detected" -ForegroundColor Yellow
    Write-Host "   Consider activating your venv first:" -ForegroundColor Yellow
    Write-Host "   .venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host ""
}

# Check if pnpm is installed
try {
    $null = Get-Command pnpm -ErrorAction Stop
} catch {
    Write-Host "❌ Error: pnpm is not installed" -ForegroundColor Red
    Write-Host "   Install it with: npm install -g pnpm" -ForegroundColor Yellow
    exit 1
}

# Check if frontend dependencies are installed
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    pnpm install
    Pop-Location
    Write-Host "✅ Frontend dependencies installed" -ForegroundColor Green
    Write-Host ""
}

Write-Host "🚀 Starting Django backend server..." -ForegroundColor Cyan
Write-Host "   URL: http://0.0.0.0:8000" -ForegroundColor Gray
Write-Host ""

# Start Django backend in a new terminal
$BackendCommand = "cd '$SimbuilderDir'; python manage.py runserver 0.0.0.0:8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $BackendCommand

# Wait a moment for backend to start
Start-Sleep -Seconds 2

Write-Host "🎨 Starting Vite frontend server..." -ForegroundColor Cyan
Write-Host "   URL: http://localhost:5173" -ForegroundColor Gray
Write-Host ""

# Start Vite frontend in a new terminal
$FrontendCommand = "cd '$FrontendDir'; pnpm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $FrontendCommand

Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "✅ Both servers started in separate terminals" -ForegroundColor Green
Write-Host ""
Write-Host "Backend:  http://0.0.0.0:8000" -ForegroundColor White
Write-Host "Frontend: http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Close the terminal windows to stop the servers" -ForegroundColor Yellow
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan


# SAlly Installation Guide

This guide explains how to install SAlly with different dependency configurations using `uv`.

## Prerequisites

- Python 3.11.14
- [uv](https://github.com/astral-sh/uv) package manager

Install uv if you haven't already:
```bash
# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installation Options

SAlly is organized into modular dependency groups. Install only what you need:

### 1. Core Installation (Minimal)

For basic HDF5 simulation and async services:

```bash
uv pip install -e .
```

This installs:
- Core async/event handling (asyncio, aiohttp, asyncpg)
- Data handling (h5py, numpy, pandas, polars)
- Configuration & DI (pyyaml, dependency-injector)
- Logging (loguru, structlog)
- Utilities (pydantic, attrs, click)

### 2. GUI Applications

For the ttkbootstrap-based rule manager GUI:

```bash
uv pip install -e ".[gui]"
```

Adds: ttkbootstrap, customtkinter, pillow

### 3. Web Application

For the Django-based simbuilder web interface:

```bash
uv pip install -e ".[web]"
```

Adds: Django, DRF, Channels, Redis, Twisted, etc.

### 4. Mosaik Co-Simulation

For Mosaik framework and power grid simulation:

```bash
uv pip install -e ".[mosaik]"
```

Adds: mosaik, pandapower, MIDAS ecosystem, lightsim2grid, networkx

### 5. Jupyter Notebooks

For Jupyter notebook support and analysis:

```bash
uv pip install -e ".[jupyter]"
```

Adds: jupyter, jupyterlab, ipython, ipykernel, matplotlib

### 6. Visualization & Analysis

For data visualization and machine learning:

```bash
uv pip install -e ".[viz]"
```

Adds: matplotlib, scikit-learn

### 7. Development Tools

For development, testing, and code quality:

```bash
uv pip install -e ".[dev]"
```

Adds: pytest, black, ruff, mypy, reloadium

### 8. Full Installation

Install everything:

```bash
uv pip install -e ".[all]"
```

## Common Installation Scenarios

### Scenario 1: Researcher (HDF5 + Jupyter + Viz)
```bash
uv pip install -e ".[jupyter,viz]"
```

### Scenario 2: Developer (Core + Dev Tools)
```bash
uv pip install -e ".[dev]"
```

### Scenario 3: GUI User (Core + GUI)
```bash
uv pip install -e ".[gui]"
```

### Scenario 4: Web Developer (Core + Web + Dev)
```bash
uv pip install -e ".[web,dev]"
```

### Scenario 5: Mosaik Simulation (Core + Mosaik + Jupyter)
```bash
uv pip install -e ".[mosaik,jupyter]"
```

## Entry Points

After installation, the following commands are available:

### `sally` - Main CLI
```bash
# HDF5 simulation
sally hdf5 --file simulation/simdata/demo.hdf5 --steps 100

# Async services mode
sally async --db-url postgresql://localhost/smartgrid

# Interactive builder mode
sally builder --example basic
```

### `sally-gui` - Rule Manager GUI
```bash
sally-gui
```

### `sally-web` - Django Web Server
```bash
# Run development server
sally-web runserver

# Run migrations
sally-web migrate

# Create superuser
sally-web createsuperuser
```

## Environment Variables

Configure SAlly using environment variables:

```bash
# Environment (dev/test/prod)
export SALLY_ENV=dev

# Database configuration
export SALLY_DB_HOST=localhost
export SALLY_DB_PORT=5432
export SALLY_DB_NAME=smartgrid
export SALLY_DB_USER=postgres
export SALLY_DB_PASSWORD=yourpassword

# Event bus
export SALLY_EVENT_QUEUE_SIZE=10000

# Logging
export SALLY_LOG_LEVEL=INFO
```

## Verification

Test your installation:

```bash
# Check version
sally --version

# Run a simple test
python -c "from sally.core import get_logger; print('SAlly imported successfully!')"
```

## Troubleshooting

### Issue: Python version mismatch
**Solution**: Ensure you're using Python 3.9.13:
```bash
python --version
```

### Issue: Missing dependencies
**Solution**: Reinstall with the appropriate extras:
```bash
uv pip install -e ".[all]" --force-reinstall
```

### Issue: Import errors
**Solution**: Make sure you're in the project root and have activated the virtual environment.

## Next Steps

- Read the [README](sally/README.md) for usage examples
- Check [ARCHITECTURE_INVENTORY](sally/docs/ARCHITECTURE_INVENTORY.md) for system overview
- Explore [examples](sally/examples/) directory

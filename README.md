# SAlly — Smart Grid Ally

**SAlly (Smart Grid Ally)** is a smart-grid simulation and operator-training platform developed as part of a bachelor’s thesis. It provides graphical interfaces for configuring, monitoring, and interacting with electrical grids of different sizes. Users can inspect component behavior, apply setpoints, define simulation rules, and analyze the resulting grid response through occurred alerts defined by the simulation rules.

SAlly is designed primarily for training power-grid operators in an isolated and reproducible environment using realistic metering data. It can operate as a standalone system or be integrated into a SCADA-oriented environment.

## Example Use Case

A typical training scenario consists of the following workflow:

1. Load an HDF5 (`.hdf5`) dataset containing grid entities, such as nodes, mapped to time-series metering data.
2. Define behavioral rules and simulation events through the `RuleManagerGUI`, for example by a trainer.
3. Allow the trainee to monitor the simulated grid state and component behavior.
4. Apply setpoints with different values to selected nodes.
5. Observe and respond to normal operating conditions, anomalies, or predefined grid events.

The principal objective is to improve operators’ situational awareness before they begin working in a network control center, where the volume, velocity, and complexity of operational information can be substantial.

SAlly can also connect to a time-series database, as commonly used in SCADA-based control-center infrastructures. This provides a potential integration path for environments that already maintain operational or historical metering data.

## Simulation Model

SAlly attempts to reconstruct a grid model from entity and time-series data. This process is most straightforward when using the `.hdf5` input mode, where entity relationships and associated measurements can be represented within a single structured dataset. Reconstruction is theoretically also possible in `timeseries` mode, although it requires sufficient metadata to infer the underlying grid topology.

## Important Notes and Limitations

The core system is functional; however, its implementation was constrained by the scope and duration of a bachelor’s thesis. Consequently, some components should be considered experimental or incomplete.

- The `SCADA-GUI` currently represents a significant performance bottleneck and requires further optimization.
- The backend, data-processing pipeline, and simulation-construction components follow a modular architecture.
- Inter-component communication is implemented through a custom event bus designed to support high-throughput data processing.
- Performance and scalability claims should be validated against the requirements and workloads of the intended deployment environment.
- No ML/DL or Anomaly Detection were used, since the scope constraint of the thesis. Nevertheless, the modular architecture allows for such components to be added without major code changes.

### `simbuilder`

The `simbuilder` is an experimental web application for constructing small simulation grids through a graphical drag-and-drop interface. It allows users to place, connect, and configure grid nodes.

Because the `simbuilder` was outside the primary scope of the thesis, it is only partially implemented and contains known defects. It should therefore be treated as a prototype rather than a production-ready component.

## Further Information

SAlly supports additional features and use cases beyond those summarized here. For a detailed discussion of the system architecture, design decisions, implementation, limitations, and potential real-world applications, refer to the accompanying thesis.

## Installation

### 1. Install with UV (Recommended)

```bash
# Install core dependencies only
uv pip install -e .

# Or install with web support (Django + frontend)
uv pip install -e ".[web,dev]"

# Or install everything
uv pip install -e ".[all]"
```

### 2. Install Frontend Dependencies (for simbuilder)

```bash
cd sally/simbuilder/frontend
pnpm install
```

## Running SAlly

### Main CLI

```bash
sally --help
sally --version
```

### GUI Application

```bash
sally-gui
```

### Web Simbuilder (Node-Based Editor)

The simbuilder requires both Django backend and Vite frontend running simultaneously.

#### Quick Start (Recommended)

**Windows (PowerShell):**
```powershell
cd sally/simbuilder
.\Start-DevServers.ps1
```

**Linux/Mac:**
```bash
cd sally/simbuilder
chmod +x start-dev.sh
./start-dev.sh
```

**Using UV entry point:**
```bash
sally-dev
```

This will start:
- Django backend on http://0.0.0.0:8000
- Vite frontend on http://localhost:5173

Open http://localhost:5173 in your browser.

#### Manual Start (Two Terminals)

**Terminal 1 - Backend:**
```bash
cd sally/simbuilder
python manage.py runserver 127.0.0.1:8000
```

**Terminal 2 - Frontend:**
```bash
cd sally/simbuilder/frontend
pnpm run dev
```

## First Time Setup (Simbuilder)

1. **Run migrations:**
   ```bash
   cd sally/simbuilder
   python manage.py migrate
   ```

2. **Create superuser (optional):**
   ```bash
   python manage.py createsuperuser
   ```

3. **Populate node types:**
   ```bash
   python manage.py populate_global_types
   ```

## Available Commands

### Entry Points

- `sally` - Main CLI application
- `sally-gui` - GUI rule manager
- `sally-web` - Django backend only
- `sally-dev` - Both backend and frontend (development)

### Django Management

```bash
cd sally/simbuilder

# Run server
python manage.py runserver 0.0.0.0:8000

# Database operations
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser

# Populate node types
python manage.py populate_global_types

# Collect static files (production)
python manage.py collectstatic
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'backend'"

This happens when running Django from the wrong directory. Use one of these solutions:

1. Use the `sally-web` command (automatically sets up paths)
2. Run from `sally/simbuilder/` directory: `python manage.py runserver`
3. Use the PowerShell script: `.\Start-DevServers.ps1`

### Port Already in Use

**Backend (port 8000):**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

**Frontend (port 5173):**
```bash
# Windows
netstat -ano | findstr :5173
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:5173 | xargs kill -9
```

### Frontend Dependencies Issues

```bash
cd sally/simbuilder/frontend
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

## Documentation

- **Full Installation Guide**: [doc/INSTALLATION.md](doc/INSTALLATION.md)
- **Simbuilder Documentation**: [sally/simbuilder/README.md](sally/simbuilder/README.md)
- **Dependency Cleanup**: [DEPENDENCY_CLEANUP.md](DEPENDENCY_CLEANUP.md)
- **Git Workflow**: [GIT_WORKFLOW.md](GIT_WORKFLOW.md)

## Project Structure

```
thesis-sally-repo/
├── sally/                  # Main package
│   ├── main.py            # CLI entry point
│   ├── core/              # Core functionality
│   ├── simulation/        # Simulation modules
│   ├── gui/               # GUI applications
│   └── simbuilder/        # Web-based node editor
│       ├── backend/       # Django backend
│       ├── frontend/      # React + Vite frontend
│       └── manage.py      # Django management
├── tests/                 # Test suite
├── pyproject.toml         # Project configuration
└── README.md              # Project overview
```

## Next Steps

1. **Explore the CLI**: `sally --help`
2. **Try the GUI**: `sally-gui`
3. **Build simulations**: Open http://localhost:5173 after running `sally-dev`
4. **Read the docs**: Check [sally/simbuilder/README.md](sally/simbuilder/README.md)

## Support

For issues and questions, see the project repository or documentation.

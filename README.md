# SAlly - Smart Grid Ally


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

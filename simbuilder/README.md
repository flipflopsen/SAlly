# SAlly Simbuilder - Node-Based Simulation Builder

A visual node-based editor for building smart grid simulations using Django + React + Vite.

## Architecture

- **Backend**: Django 4.2+ with Django REST Framework and Channels (WebSocket support)
- **Frontend**: React with Vite for hot module replacement
- **Database**: SQLite (development) / PostgreSQL (production)

## Quick Start

### Prerequisites

- Python 3.9.13+
- Node.js 16+ and pnpm
- UV package manager (recommended)

### Installation

1. **Install Python dependencies** (from project root):
   ```bash
   # Using UV (recommended)
   uv pip install -e ".[web,dev]"
   
   # Or using pip
   pip install -e ".[web,dev]"
   ```

2. **Install frontend dependencies**:
   ```bash
   cd sally/simbuilder/frontend
   pnpm install
   ```

3. **Set up environment variables**:
   
   Create or verify `sally/simbuilder/.env`:
   ```env
   # Django
   DEBUG=True
   SECRET_KEY="your-secret-key-here"
   
   # Django-vite
   DJANGO_VITE_DEV_MODE=true
   DJANGO_VITE_DEV_SERVER_PORT=5173
   ```

4. **Run database migrations**:
   ```bash
   cd sally/simbuilder
   python manage.py migrate
   ```

## Running the Development Server

### Option 1: Using PowerShell Script (Windows - Recommended)

```powershell
cd sally/simbuilder
.\Start-DevServers.ps1
```

This will open two terminal windows:
- Django backend on http://0.0.0.0:8000
- Vite frontend on http://localhost:5173

### Option 2: Using UV Entry Point

```bash
# From project root
sally-dev
```

This runs both servers in a single terminal with proper process management.

### Option 3: Manual (Two Separate Terminals)

**Terminal 1 - Django Backend:**
```bash
cd sally/simbuilder
python manage.py runserver 0.0.0.0:8000
```

**Terminal 2 - Vite Frontend:**
```bash
cd sally/simbuilder/frontend
pnpm run dev
```

### Option 4: Using Bash Script (Linux/Mac)

```bash
cd sally/simbuilder
chmod +x start-dev.sh
./start-dev.sh
```

## Available Commands

### Django Management Commands

```bash
# Run backend only
sally-web runserver 0.0.0.0:8000

# Or from simbuilder directory
python manage.py runserver 0.0.0.0:8000

# Create superuser
python manage.py createsuperuser

# Run migrations
python manage.py migrate

# Create migrations
python manage.py makemigrations

# Populate node type definitions
python manage.py populate_global_types

# Collect static files (production)
python manage.py collectstatic
```

### Frontend Commands

```bash
cd sally/simbuilder/frontend

# Development server
pnpm run dev

# Build for production
pnpm run build

# Preview production build
pnpm run preview
```

## URLs

- **Frontend (Development)**: http://localhost:5173
- **Backend API**: http://0.0.0.0:8000/api/
- **Django Admin**: http://0.0.0.0:8000/admin/
- **Node Editor**: http://localhost:5173/editor/
- **WebSocket**: ws://0.0.0.0:8000/ws/graph/<project_id>/

## Project Structure

```
sally/simbuilder/
├── backend/                 # Django backend
│   ├── config/             # Django settings
│   ├── node_editor/        # Main app
│   ├── plugins/            # Node and connection plugins
│   │   ├── nodes/          # Node type plugins
│   │   └── connections/    # Connection type plugins
│   └── templates/          # Django templates
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API and WebSocket services
│   │   └── store/          # State management
│   └── vite.config.js      # Vite configuration
├── manage.py               # Django management script
├── django_runner.py        # UV entry point wrapper
├── run_dev.py              # Development server runner
└── Start-DevServers.ps1    # PowerShell launcher
```

## Troubleshooting

### Backend Issues

**ModuleNotFoundError: No module named 'backend'**
- Make sure you're running from the correct directory
- The `sally-web` command automatically sets up the Python path

**Database errors**
```bash
python manage.py migrate
```

### Frontend Issues

**Port 5173 already in use**
```bash
# Kill the process using port 5173
# Windows:
netstat -ano | findstr :5173
taskkill /PID <PID> /F

# Linux/Mac:
lsof -ti:5173 | xargs kill -9
```

**Dependencies not found**
```bash
cd sally/simbuilder/frontend
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

## Development Workflow

1. Start both servers using one of the methods above
2. Open http://localhost:5173 in your browser
3. Make changes to frontend code - Vite will hot-reload
4. Make changes to backend code - Django will auto-reload
5. API changes are immediately available via WebSocket

## Production Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for production deployment instructions.

## Contributing

See the main project [CONTRIBUTING.md](../../CONTRIBUTING.md) for contribution guidelines.


# SAlly - Smart Grid Ally for Simulation, Monitoring, and Analysis

**Version**: 0.7.3
**Status**: Active Development

A comprehensive Python framework for smart grid simulation, monitoring, and analysis with support for HDF5 data replay, real-time monitoring, and Mosaik co-simulation.

## Features

- 🔄 **Multiple Simulation Modes**: HDF5 replay, async services, Mosaik co-simulation
- 📊 **Real-time Monitoring**: Event-driven architecture with TimescaleDB persistence
- 📏 **Rule Management**: Flexible rule engine for grid condition monitoring
- 🎨 **Visualization**: Single-line diagram generator with multiple color schemes
- 🔌 **Extensible**: Plugin architecture for custom simulators and services
- 🏗️ **Clean Architecture**: Layered design (core, domain, infrastructure, application, presentation)

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/bena1680/sally
cd thesis-sally-repo

# Install with uv (recommended) - core only
uv pip install -e .

# Or install with specific features
uv pip install -e ".[gui]"        # GUI applications
uv pip install -e ".[web]"        # Web interface
uv pip install -e ".[mosaik]"     # Mosaik co-simulation
uv pip install -e ".[jupyter]"    # Jupyter notebooks
uv pip install -e ".[all]"        # Everything

# For development
uv pip install -e ".[dev]"
```

📖 **See [INSTALLATION.md](../INSTALLATION.md) for detailed installation options and scenarios.**

### Running Simulations

```bash
# HDF5-based simulation
sally hdf5 --file simulation/simdata/demo.hdf5 --steps 100

# Async services mode (requires TimescaleDB)
sally async --db-url postgresql://localhost/smartgrid

# Interactive builder mode
sally builder --example basic

# Launch GUI
sally-gui

# Start web server
sally-web runserver
```

### Python API

```python
from sally.application import SimulationBuilder
from sally.core import get_logger

logger = get_logger(__name__)

# Build and run simulation
simulation = (SimulationBuilder()
    .with_hdf5_file('simulation/simdata/demo.hdf5')
    .with_config('config/default.yml')
    .build())

await simulation.run_steps(10)
simulation.close()
```

## Architecture

SAlly follows a clean layered architecture:

```
sally/
├── core/              # Framework foundations (event bus, logging, utilities)
├── domain/            # Domain models (grid entities, events)
├── infrastructure/    # External dependencies (data management, services)
├── application/       # Business logic (simulation, rule management)
├── presentation/      # User interfaces (GUI tools, visualizations)
├── config/            # Configuration files (default, dev, test, prod)
├── examples/          # Example scripts and demonstrations
```

### Key Components

- **Event Bus**: Async event-driven architecture for service communication
- **Simulation Engine**: HDF5 replay, Mosaik integration, data providers
- **Rule Manager**: Flexible rule evaluation engine
- **Services**: Grid data generation, load forecasting, stability monitoring
- **SDL Generator**: Single-line diagram visualization
- **Config Manager**: Environment-specific configuration management

## Simulation Modes

### 1. HDF5 Mode
Replay pre-recorded simulation data from HDF5 files for rule testing and analysis.

**Use Cases**: Testing rule logic, debugging, GUI-based rule creation
**Entry Point**: `main.py hdf5` or `main_hdf5_simulation.py`

### 2. Async Services Mode
Event-driven real-time monitoring with async services and TimescaleDB persistence.

**Use Cases**: Real-time monitoring, service integration testing, production deployment
**Entry Point**: `main.py async` or `main_async_services.py`

### 3. Builder Mode
Flexible simulation construction with dependency injection for various scenarios.

**Use Cases**: Testing, research experiments, custom scenarios
**Entry Point**: `main.py builder` or `SimulationBuilder` API

See `docs/SIMULATION_MODES.md` for detailed comparison.

## Configuration

Configuration is managed through YAML files with environment-specific overlays:

```yaml
# config/default.yml
database:
  host: localhost
  port: 5432
  database: smartgrid

event_bus:
  max_queue_size: 10000

simulation:
  default_hdf5_path: simulation/simdata/demo.hdf5
  default_steps: 44640
```

Environment-specific configs:
- `config/dev.yml` - Development settings
- `config/test.yml` - Test settings
- `config/prod.yml` - Production settings

Set environment via `SALLY_ENV` variable:
```bash
export SALLY_ENV=prod
python main.py hdf5
```

## Examples

The `examples/` directory contains demonstration scripts:

- `example_observer_pattern.py` - Observer pattern with DI
- `example_mosaik_integration.py` - Full Mosaik co-simulation
- `example_simulation_builder.py` - 7 SimulationBuilder scenarios

Run examples:
```bash
python -m sally.examples.example_observer_pattern
python -m sally.examples.example_simulation_builder
```

See `examples/README.md` for detailed documentation.

## Development

### Project Structure

```
sally/
├── core/                    # Core framework
│   ├── event_bus.py        # Event-driven architecture
│   ├── logger.py           # Logging utilities
│   ├── observer.py         # Observer pattern
│   ├── config.py           # Configuration management
│   └── hdf5_builder.py     # HDF5 test data builder
├── domain/                  # Domain layer
│   ├── grid_entities.py    # Grid entity models
│   └── events.py           # Domain events
├── infrastructure/          # Infrastructure layer
│   ├── data_management/    # Data adapters
│   └── services/           # External services
├── application/             # Application layer
│   ├── simulation/         # Simulation orchestration
│   └── rule_management/    # Rule engine
└── presentation/            # Presentation layer
    └── gui/                # GUI components
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test suite
pytest tests/framework/test_builder.py

# Run with coverage
pytest --cov=sally tests/
```

### Code Style

The project follows PEP 8 with these conventions:
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`

Format code:
```bash
black sally/
ruff check sally/
```

## Documentation

- `docs/ARCHITECTURE_INVENTORY.md` - Complete module documentation
- `docs/SIMULATION_MODES.md` - Simulation approaches comparison
- `docs/EXAMPLES_STATUS.md` - Example functionality status
- `docs/TODO.md` - Planned features and known issues
- `examples/README.md` - Example scripts documentation
- `presentation/gui/sdl/README.md` - SDL generator documentation

## Dependencies

### Core
- `dependency-injector` - Dependency injection
- `structlog` - Structured logging
- `h5py` - HDF5 file handling
- `pandas`, `numpy` - Data processing
- `pyyaml` - Configuration

### Optional
- `mosaik`, `mosaik-api` - Co-simulation (for Mosaik mode)
- `asyncpg` - PostgreSQL async driver (for async services mode)
- `ttkbootstrap` - GUI toolkit (for visualization)
- `matplotlib` - Plotting (for analysis)

### Database
- PostgreSQL with TimescaleDB extension (for production deployments)

## Relationship with SimBuilder

SAlly is the simulation and monitoring framework, while SimBuilder (in `simbuilder/` directory) is a Django-based web application for visual simulation design. They work together:

- **SimBuilder**: Visual node-based editor for designing simulations
- **SAlly**: Execution engine for running simulations

See `simbuilder/README.md` for SimBuilder documentation.

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.md` for guidelines.

### Development Workflow

1. Create feature branch
2. Make changes following code style guidelines
3. Add tests for new functionality
4. Update documentation
5. Submit pull request

## License

[License information]

## Contact

[Contact information]

## Acknowledgments

[Acknowledgments]

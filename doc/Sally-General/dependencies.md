# Sally Dependencies

## Core Dependencies

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| Async runtime | `asyncio` | Python standard async library, used in all async services | - |
| Alternative async runtime | `trio` | Structured concurrency with better error handling | `curio` |
| Async-Trio bridge | `trio-asyncio` | Enables mixing asyncio and trio code | - |
| Lightweight threading | `greenlet` | Lightweight pseudo-concurrent programming for gevent | `threading` |
| Async networking | `gevent` | Greenlet-based networking library | `asyncio` |

## Data Handling

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| HDF5 file I/O | `h5py` | Read/write HDF5 simulation data files | `pytables` |
| Numerical computing | `numpy` | Array operations, used throughout simulation | `cupy` |
| Data manipulation | `pandas` | DataFrame operations for time-series data | `polars` |
| Fast DataFrames | `polars` | High-performance alternative for large datasets | `pandas` |
| HDF5 tables | `tables` (PyTables) | Advanced HDF5 table operations | `h5py` |

## Database & Persistence

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| Async PostgreSQL driver | `asyncpg` | Fast async PostgreSQL/TimescaleDB driver | `psycopg2` (sync) |
| Async HTTP client/server | `aiohttp` | Mature async HTTP for API and WebSocket | `httpx` |

## Co-Simulation (Mosaik Ecosystem)

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| Co-simulation framework | `mosaik` | Smart grid co-simulation orchestration | - |
| Mosaik simulator API | `mosaik-api` | Build custom mosaik simulators | - |
| Power flow simulation | `pandapower` | Power system modeling and analysis | `GridLAB-D` |
| Network graphs | `networkx` | Grid topology representation | `igraph` |
| Discrete event simulation | `simpy` | Event-driven simulation support | - |

## MIDAS Integration

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| MIDAS core | `midas-mosaik` | MIDAS mosaik integration | - |
| Power grid scenarios | `midas-powergrid` | Power grid scenario generation | - |
| MIDAS utilities | `midas-util` | Common MIDAS utilities | - |

## Configuration & DI

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| YAML parsing | `pyyaml` | Configuration file parsing | `toml` |
| Dependency injection | `dependency-injector` | IoC container for service wiring | `injector` |
| Environment config | `python-decouple` | Environment variable management | `python-dotenv` |
| Data validation | `pydantic` | Runtime data validation and settings | `attrs` |
| Data classes | `attrs` | Lightweight dataclass alternative | `dataclasses` |

## Logging & Observability

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| Structured logging | `loguru` | Modern logging with rotation | `logging` |
| Log formatting | `structlog` | Structured log output | `python-json-logger` |
| Telemetry SDK | `opentelemetry-sdk` | Distributed tracing and metrics | - |
| OTLP export | `opentelemetry-exporter-otlp` | Export to OTEL Collector | - |

## GUI (Desktop)

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| Modern Tkinter themes | `ttkbootstrap` | Bootstrap-styled Tkinter widgets | `customtkinter` |
| Custom widgets | `customtkinter` | Modern-looking Tkinter widgets | `ttkbootstrap` |
| Image handling | `pillow` | Image loading for GUI icons | - |

## Web Frontend

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| Web framework | `django` | Web application framework | `fastapi` |
| REST API | `djangorestframework` | REST API endpoints | - |
| WebSocket support | `channels` | Django WebSocket support | - |
| ASGI server | `daphne` | ASGI server for channels | `uvicorn` |

## SCADA Web Bridge

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| MQTT client | `paho-mqtt` | MQTT messaging for IoT/SCADA | `aiomqtt` |
| WebSocket server | `python-socketio` | Socket.IO for real-time web | `websockets` |

## CLI

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| CLI framework | `click` | Command-line interface creation | `argparse`, `typer` |

## Development

| Use-case | Dependency | Reasoning | Alternatives |
| --- | --- | --- | --- |
| Testing | `pytest` | Test framework | `unittest` |
| Async testing | `pytest-asyncio` | Async test support | - |
| Formatting | `black` | Code formatter | `autopep8` |
| Linting | `ruff` | Fast Python linter | `flake8` |
| Type checking | `mypy` | Static type checking | `pyright` |

## Notes on Dependencies

- **h5py vs PyTables**: h5py is used for direct HDF5 access; PyTables (`tables`) provides higher-level table abstractions
- **pandas vs polars**: pandas is used for compatibility; polars is available for performance-critical paths
- **asyncio vs trio**: Sally primarily uses asyncio but supports trio via trio-asyncio for structured concurrency
- **ttkbootstrap**: Provides modern Bootstrap-styled themes for Tkinter without requiring a web stack

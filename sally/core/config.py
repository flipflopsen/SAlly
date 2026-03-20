"""Configuration management for sally.

Provides centralized configuration loading with environment-specific overlays
and validation. All configuration sections from default.yml are parsed into
strongly-typed dataclasses for IDE support and validation.

Usage:
    from sally.core.config import config, get_config

    # Direct attribute access (preferred)
    db_host = config.database.host
    otel_enabled = config.otel.enabled
    rules_path = config.paths.rules_dir

    # Dot-notation access
    db_host = config.get('database.host')

    # Get resolved Path objects
    rules_path = config.get_path('rules_dir')
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from dataclasses import dataclass, field, fields
from logging import getLogger


logger = getLogger(__name__)


# =============================================================================
# Path Resolution Helpers
# =============================================================================

def _get_package_root() -> Path:
    """Get the sally package root directory."""
    return Path(__file__).resolve().parent.parent


def _get_project_root() -> Path:
    """Get the project root directory (thesis-sally-repo)."""
    return _get_package_root().parent


# =============================================================================
# Configuration Dataclasses
# =============================================================================

@dataclass
class PathsConfig:
    """Paths configuration - resolved relative to PROJECT_ROOT."""
    # Data directories
    data_dir: str = 'data'
    rules_dir: str = 'data/rules'
    csv_dir: str = 'data/csv'
    hdf5_dir: str = 'data/hdf5'
    midas_dir: str = 'data/midas'

    # Logs directory
    logs_dir: str = 'logs'

    # Simulation paths
    sim_app_dir: str = 'sally/application/simulation'
    simdata_dir: str = 'sally/application/simulation/simdata'

    # Default file artifacts
    default_rules_file: str = 'data/rules/chainrule_pv_household.json'
    default_hdf5_file: str = 'sally/application/simulation/simdata/demo.hdf5'

    # Config directory
    config_dir: str = 'sally/config'

    def resolve(self, path_attr: str) -> Path:
        """Resolve a path attribute to an absolute Path.

        Args:
            path_attr: Name of the path attribute (e.g., 'rules_dir')

        Returns:
            Resolved absolute Path
        """
        path_str = getattr(self, path_attr, None)
        if path_str is None:
            raise ValueError(f"Unknown path attribute: {path_attr}")

        path = Path(path_str)
        if path.is_absolute():
            return path
        return _get_project_root() / path

    @property
    def project_root(self) -> Path:
        """Get the project root directory."""
        return _get_project_root()

    @property
    def package_root(self) -> Path:
        """Get the sally package root directory."""
        return _get_package_root()


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = 'localhost'
    port: int = 5432
    database: str = 'smartgrid'
    user: str = 'postgres'
    password: str = ''
    pool_size: int = 10
    max_pool_size: int = 20
    timescale_specific: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': True,
        'hypertable_chunk_time_interval': '15 minutes'
    })

    @property
    def dsn(self) -> str:
        """Get database connection string."""
        if self.password:
            return f'postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}'
        return f'postgresql://{self.user}@{self.host}:{self.port}/{self.database}'


@dataclass
class EventBusConfig:
    """Event bus configuration for high-performance event processing."""
    buffer_size: int = 65536
    batch_size: int = 1024
    worker_count: int = 4
    max_queue_size: int = 10000  # Legacy parameter


@dataclass
class OTelConfig:
    """OpenTelemetry configuration."""
    enabled: bool = True
    endpoint: str = 'http://localhost:4317'
    traces_endpoint: Optional[str] = None
    metrics_endpoint: Optional[str] = None
    logs_endpoint: Optional[str] = None

    service_name: str = 'sally'
    service_version: str = '0.7.3'

    # Export settings
    metrics_interval_ms: int = 100
    traces_batch_size: int = 512
    sample_rate: float = 1.0

    # Feature flags
    trace_event_bus: bool = True
    trace_simulation: bool = True
    trace_rules: bool = True
    trace_gui: bool = False


@dataclass
class SimulationConfig:
    """Simulation configuration."""
    simulation_mode: Literal["hdf5", "midas", "timescale"] = "hdf5"
    default_hdf5_path: str = '../simulation/simdata/demo.hdf5'
    default_rules_path: str = '../../../data/rules/chainrule_pv_household.json'
    default_steps: int = 44640
    step_size: int = 1
    step_timeout_seconds: float = 0.1
    start_time: str = '2014-01-01 00:00:00'
    publish_scada_events: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = 'INFO'
    format: str = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'

    # File logging
    file_enabled: bool = True
    file_max_bytes: int = 5000000
    file_backup_count: int = 5

    # Console logging
    console_enabled: bool = True
    console_colored: bool = True

    # OTEL log export
    otel_export: bool = True


@dataclass
class ServiceConfig:
    """Individual service configuration."""
    enabled: bool = True
    update_interval_ms: int = 1000


@dataclass
class GridDataServiceConfig(ServiceConfig):
    """Grid data service configuration."""
    pass


@dataclass
class LoadForecastingServiceConfig(ServiceConfig):
    """Load forecasting service configuration."""
    enabled: bool = False
    forecast_horizon_minutes: int = 60
    update_interval_ms: int = 5000


@dataclass
class StabilityMonitoringServiceConfig(ServiceConfig):
    """Stability monitoring service configuration."""
    enabled: bool = False
    check_interval_ms: int = 1000
    voltage_low_pu: float = 0.92
    voltage_high_pu: float = 1.08
    freq_low_hz: float = 49.5
    freq_high_hz: float = 50.5


@dataclass
class ServicesConfig:
    """Services configuration container."""
    grid_data: GridDataServiceConfig = field(default_factory=GridDataServiceConfig)
    load_forecasting: LoadForecastingServiceConfig = field(default_factory=LoadForecastingServiceConfig)
    stability_monitoring: StabilityMonitoringServiceConfig = field(default_factory=StabilityMonitoringServiceConfig)


from dataclasses import dataclass, field
from typing import List, Literal

@dataclass
class ScadaOrchestrationConfig:
    """Orchestration configuration for SCADA system."""
    update_interval_ms: int = 10
    max_triggered_rules_history: int = 50
    event_buffer_size: int = 100000
    default_step_interval_s: float = 1.0


@dataclass
class ScadaGuiConfig:
    """GUI configuration for SCADA system."""
    window_size: List[int] = field(default_factory=lambda: [1920, 1080])
    sidebar_width: int = 350
    theme: str = "darkly"
    refresh_rate_ms: int = 100


@dataclass
class ScadaSldConfig:
    """Single Line Diagram (SLD) configuration."""
    auto_layout: bool = True
    component_spacing: int = 100
    show_labels: bool = True
    animation_enabled: bool = True
    blink_interval_ms: int = 500


@dataclass
class ScadaSimulationConfig:
    """Simulation configuration for SCADA system."""
    default_step_interval_s: float = 1.0
    scada_poll_interval_minutes: int = 15
    enable_setpoints: bool = True


@dataclass
class ScadaMqttConfig:
    """MQTT configuration for SCADA web bridge."""
    host: str = "localhost"
    port: int = 1883
    client_id: str = "sally-scada-bridge"
    keepalive: int = 60
    qos: int = 1
    retain_topology: bool = True


@dataclass
class ScadaWebSocketConfig:
    """WebSocket configuration for SCADA web bridge."""
    host: str = "0.0.0.0"
    port: int = 3001
    cors_allowed_origins: str = "*"


@dataclass
class ScadaBackendConfig:
    """Backend configuration for SCADA web interface."""
    host: str = "localhost"
    port: int = 3000


@dataclass
class ScadaFrontendConfig:
    """Frontend configuration for SCADA web interface."""
    host: str = "localhost"
    port: int = 4200


@dataclass
class ScadaWebConfig:
    """Web interface configuration (Guardian-compatible)."""
    enabled: bool = True
    bridge_mode: Literal["mqtt", "websocket"] = "mqtt"
    mqtt: ScadaMqttConfig = field(default_factory=ScadaMqttConfig)
    websocket: ScadaWebSocketConfig = field(default_factory=ScadaWebSocketConfig)
    backend: ScadaBackendConfig = field(default_factory=ScadaBackendConfig)
    frontend: ScadaFrontendConfig = field(default_factory=ScadaFrontendConfig)


@dataclass
class ScadaConfig:
    """SCADA configuration."""
    orchestration: ScadaOrchestrationConfig = field(default_factory=ScadaOrchestrationConfig)
    gui: ScadaGuiConfig = field(default_factory=ScadaGuiConfig)
    sld: ScadaSldConfig = field(default_factory=ScadaSldConfig)
    simulation: ScadaSimulationConfig = field(default_factory=ScadaSimulationConfig)
    web: ScadaWebConfig = field(default_factory=ScadaWebConfig)


@dataclass
class MosaikConfig:
    """Mosaik configuration."""
    config_file: str = 'simulation/mosaik_simulators/simulation_config.yml'
    duration: int = 100
    step_size: int = 1


@dataclass
class GuiConfig:
    """GUI configuration (legacy)."""
    theme: str = 'default'
    window_width: int = 1200
    window_height: int = 800


@dataclass
class EnvConfig:
    """Environment variables configuration."""
    # Environment
    SALLY_ENV: str = 'development'

    # OpenTelemetry
    SALLY_OTEL_ENABLED: bool = True
    SALLY_OTEL_ENDPOINT: str = 'http://localhost:4317'
    SALLY_OTEL_MODE: str = 'otlp_grpc'
    SALLY_OTEL_TRACES_ENDPOINT: Optional[str] = None
    SALLY_OTEL_METRICS_ENDPOINT: Optional[str] = None
    SALLY_OTEL_LOGS_ENDPOINT: Optional[str] = None
    SALLY_OTEL_SERVICE_NAME: str = 'sally'
    SALLY_OTEL_SERVICE_VERSION: str = '0.7.3'
    SALLY_OTEL_METRICS_INTERVAL_MS: int = 10000
    SALLY_OTEL_TRACES_BATCH_SIZE: int = 512
    SALLY_OTEL_SAMPLE_RATE: float = 1.0
    SALLY_OTEL_TRACE_EVENT_BUS: bool = True
    SALLY_OTEL_TRACE_SIMULATION: bool = True
    SALLY_OTEL_TRACE_RULES: bool = True
    SALLY_OTEL_TRACE_GUI: bool = False
    SALLY_DEPLOYMENT_ENV: str = 'development'

    # Logging
    SALLY_LOG_LEVEL: str = 'DEBUG'
    SALLY_LOG_FILE_ENABLED: bool = True
    SALLY_LOG_CONSOLE_ENABLED: bool = True
    SALLY_LOG_COLORED: bool = True
    SALLY_LOG_OTEL_EXPORT: bool = True

    # Event Bus
    SALLY_EVENTBUS_BUFFER_SIZE: int = 65536
    SALLY_EVENTBUS_BATCH_SIZE: int = 1024
    SALLY_EVENTBUS_WORKER_COUNT: int = 4
    SALLY_EVENTBUS_MAX_QUEUE_SIZE: int = 10000
    SALLY_EVENT_QUEUE_SIZE: Optional[int] = None

    # Simulation
    SALLY_SIM_STEPS: int = 44640
    SALLY_SIM_STEP_SIZE: int = 1
    SALLY_SIM_STEP_TIMEOUT: float = 0.5
    SALLY_SIM_PUBLISH_SCADA: bool = True

    # Database
    SALLY_DB_HOST: str = 'localhost'
    SALLY_DB_PORT: int = 5432
    SALLY_DB_NAME: str = 'smartgrid'
    SALLY_DB_USER: str = 'postgres'
    SALLY_DB_PASSWORD: str = ''
    SALLY_DB_POOL_SIZE: int = 10
    SALLY_DB_MAX_POOL_SIZE: int = 20

    # SCADA
    SALLY_SCADA_UPDATE_INTERVAL_MS: int = 10
    SALLY_SCADA_STEP_INTERVAL: float = 1.0
    SALLY_SCADA_THEME: str = 'default'

    # Docker Network Configuration
    OTEL_HTTP_PORT: int = 4318
    PROMETHEUS_PORT: int = 9090
    GRAFANA_PORT: int = 3000
    TEMPO_PORT: int = 3200
    LOKI_PORT: int = 3100


@dataclass
class SallyConfig:
    """Main configuration container with all sections."""
    # Core sections
    paths: PathsConfig = field(default_factory=PathsConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    event_bus: EventBusConfig = field(default_factory=EventBusConfig)
    otel: OTelConfig = field(default_factory=OTelConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Service sections
    services: ServicesConfig = field(default_factory=ServicesConfig)
    scada: ScadaConfig = field(default_factory=ScadaConfig)
    mosaik: MosaikConfig = field(default_factory=MosaikConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)

    # Environment variables
    env: EnvConfig = field(default_factory=EnvConfig)

    # Additional custom config (for sections not explicitly defined)
    custom: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Configuration Manager
# =============================================================================

def _update_dataclass(instance: Any, data: Dict[str, Any]) -> None:
    """Update a dataclass instance from a dictionary.

    Args:
        instance: Dataclass instance to update
        data: Dictionary with values to set
    """
    if not data:
        return

    for key, value in data.items():
        if hasattr(instance, key):
            current = getattr(instance, key)
            # Handle nested dataclasses
            if hasattr(current, '__dataclass_fields__') and isinstance(value, dict):
                _update_dataclass(current, value)
            else:
                try:
                    setattr(instance, key, value)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Could not set {key}={value}: {e}")


class ConfigManager:
    """Manages application configuration with environment-specific overlays.

    Configuration loading order (later overrides earlier):
    1. Default values (from dataclass defaults)
    2. config/default.yml
    3. config/{environment}.yml (e.g., config/dev.yml)
    4. Environment variables (SALLY_*)
    5. Explicit overrides via set() method

    Example:
        config = ConfigManager(environment='dev')

        # Direct access
        db_host = config.database.host
        otel_enabled = config.otel.enabled

        # Dot notation
        db_host = config.get('database.host')

        # Get resolved paths
        rules_path = config.get_path('rules_dir')
    """

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        environment: Optional[str] = None
    ):
        """Initialize configuration manager.

        Args:
            config_dir: Directory containing config files (default: sally/config)
            environment: Environment name (dev/test/prod). If None, uses SALLY_ENV
        """
        self.config_dir = config_dir or _get_package_root() / 'config'
        self.environment = environment or os.getenv('SALLY_ENV', 'default')
        self._config = SallyConfig()
        self._overrides: Dict[str, Any] = {}
        self._raw_yaml: Dict[str, Any] = {}

        self._load_config()
        self._apply_env_config()

    def _load_config(self) -> None:
        """Load configuration from files and environment."""
        # Load default config
        default_config_path = self.config_dir / 'default.yml'
        if default_config_path.exists():
            self._load_yaml_file(default_config_path)
        else:
            logger.warning(f"Default config not found: {default_config_path}")

        # Load environment-specific config
        env_config_path = self.config_dir / f'{self.environment}.yml'
        if env_config_path.exists():
            self._load_yaml_file(env_config_path)
            logger.info(f"Loaded {self.environment} environment config")

        # Load legacy config for backward compatibility
        legacy_config_path = self.config_dir / 'default.yml'
        if legacy_config_path.exists() and legacy_config_path != default_config_path:
            logger.warning(
                f"Loading legacy config from {legacy_config_path}. "
                "Consider migrating to default.yml"
            )
            self._load_yaml_file(legacy_config_path)

        # Load environment variables
        self._load_env_vars()

    def _load_yaml_file(self, path: Path) -> None:
        """Load configuration from YAML file.

        Args:
            path: Path to the YAML configuration file
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # Store raw YAML for debugging
            self._raw_yaml.update(data)

            # Update all known config sections
            section_mapping = {
                'paths': self._config.paths,
                'database': self._config.database,
                'db': self._config.database,  # Legacy alias
                'event_bus': self._config.event_bus,
                'otel': self._config.otel,
                'simulation': self._config.simulation,
                'logging': self._config.logging,
                'scada': self._config.scada,
                'mosaik': self._config.mosaik,
                'gui': self._config.gui,
                'env': self._config.env,
            }

            for key, config_obj in section_mapping.items():
                if key in data:
                    _update_dataclass(config_obj, data[key])

            # Handle nested services config specially
            if 'services' in data:
                services_data = data['services']
                if 'grid_data' in services_data:
                    _update_dataclass(self._config.services.grid_data, services_data['grid_data'])
                if 'load_forecasting' in services_data:
                    _update_dataclass(self._config.services.load_forecasting, services_data['load_forecasting'])
                if 'stability_monitoring' in services_data:
                    _update_dataclass(self._config.services.stability_monitoring, services_data['stability_monitoring'])

            # Store any additional custom config not in known sections
            known_sections = set(section_mapping.keys()) | {'services'}
            for key, value in data.items():
                if key not in known_sections:
                    self._config.custom[key] = value

            logger.debug(f"Loaded config from {path}")

        except Exception as e:
            logger.error(f"Error loading config from {path}: {e}")

    def _load_env_vars(self) -> None:
        """Load configuration from environment variables and update env config."""
        import os

        # Load all environment variables into the env config section
        env_cfg = self._config.env
        for field_info in fields(env_cfg):
            key = field_info.name
            current_value = getattr(env_cfg, key)
            env_value = os.getenv(key)

            if env_value is not None:
                # Convert to appropriate type
                field_type = field_info.type
                if field_type == bool or field_type == 'bool':
                    setattr(env_cfg, key, env_value.lower() in ('true', '1', 'yes'))
                elif field_type == int or field_type == 'int':
                    setattr(env_cfg, key, int(env_value))
                elif field_type == float or field_type == 'float':
                    setattr(env_cfg, key, float(env_value))
                elif 'Optional' in str(field_type):
                    # Handle Optional types
                    if 'int' in str(field_type):
                        setattr(env_cfg, key, int(env_value) if env_value else None)
                    elif 'float' in str(field_type):
                        setattr(env_cfg, key, float(env_value) if env_value else None)
                    else:
                        setattr(env_cfg, key, env_value if env_value else None)
                else:
                    setattr(env_cfg, key, env_value)

        # Also update legacy config sections for backward compatibility
        # Database config
        if host := os.getenv('SALLY_DB_HOST'):
            self._config.database.host = host
        if port := os.getenv('SALLY_DB_PORT'):
            self._config.database.port = int(port)
        if database := os.getenv('SALLY_DB_NAME'):
            self._config.database.database = database
        if user := os.getenv('SALLY_DB_USER'):
            self._config.database.user = user
        if password := os.getenv('SALLY_DB_PASSWORD'):
            self._config.database.password = password

        # Event bus config
        if queue_size := os.getenv('SALLY_EVENT_QUEUE_SIZE'):
            self._config.event_bus.max_queue_size = int(queue_size)

        # Logging config
        if log_level := os.getenv('SALLY_LOG_LEVEL'):
            self._config.logging.level = log_level

        # OTEL config
        if otel_enabled := os.getenv('SALLY_OTEL_ENABLED'):
            self._config.otel.enabled = otel_enabled.lower() in ('true', '1', 'yes')
        if otel_endpoint := os.getenv('SALLY_OTEL_ENDPOINT'):
            self._config.otel.endpoint = otel_endpoint

    def _apply_env_config(self) -> None:
        """Apply environment variables from the env config section."""
        env_cfg = self._config.env
        for field_info in fields(env_cfg):
            key = field_info.name
            value = getattr(env_cfg, key)
            # Only set if not already set in environment
            if os.getenv(key) is None:
                os.environ[key] = str(value)

    # =========================================================================
    # Property Accessors for Direct Access
    # =========================================================================

    @property
    def paths(self) -> PathsConfig:
        """Get paths configuration."""
        return self._config.paths

    @property
    def database(self) -> DatabaseConfig:
        """Get database configuration."""
        return self._config.database

    @property
    def event_bus(self) -> EventBusConfig:
        """Get event bus configuration."""
        return self._config.event_bus

    @property
    def otel(self) -> OTelConfig:
        """Get OpenTelemetry configuration."""
        return self._config.otel

    @property
    def simulation(self) -> SimulationConfig:
        """Get simulation configuration."""
        return self._config.simulation

    @property
    def logging(self) -> LoggingConfig:
        """Get logging configuration."""
        return self._config.logging

    @property
    def services(self) -> ServicesConfig:
        """Get services configuration."""
        return self._config.services

    @property
    def scada(self) -> ScadaConfig:
        """Get SCADA configuration."""
        return self._config.scada

    @property
    def mosaik(self) -> MosaikConfig:
        """Get Mosaik configuration."""
        return self._config.mosaik

    @property
    def gui(self) -> GuiConfig:
        """Get GUI configuration."""
        return self._config.gui

    @property
    def env(self) -> EnvConfig:
        """Get environment variables configuration."""
        return self._config.env

    @property
    def custom(self) -> Dict[str, Any]:
        """Get custom configuration values."""
        return self._config.custom

    # =========================================================================
    # Dynamic Access Methods
    # =========================================================================

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key.

        Args:
            key: Configuration key in dot notation (e.g., 'database.host')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            host = config.get('database.host')
            port = config.get('database.port', 5432)
        """
        # Check overrides first
        if key in self._overrides:
            return self._overrides[key]

        # Navigate through config structure
        parts = key.split('.')
        value: Any = self._config

        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value (runtime override).

        Args:
            key: Configuration key in dot notation
            value: Value to set

        Example:
            config.set('database.port', 5433)
        """
        self._overrides[key] = value
        logger.debug(f"Config override: {key} = {value}")

    def get_path(self, path_attr: str) -> Path:
        """Get a resolved path from the paths configuration.

        Args:
            path_attr: Name of the path attribute (e.g., 'rules_dir', 'logs_dir')

        Returns:
            Resolved absolute Path

        Example:
            rules_path = config.get_path('rules_dir')
            logs_path = config.get_path('logs_dir')
        """
        return self._config.paths.resolve(path_attr)

    # =========================================================================
    # Legacy Accessors (for backward compatibility)
    # =========================================================================

    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration."""
        return self._config.database

    def get_event_bus_config(self) -> EventBusConfig:
        """Get event bus configuration."""
        return self._config.event_bus

    def get_simulation_config(self) -> SimulationConfig:
        """Get simulation configuration."""
        return self._config.simulation

    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration."""
        return self._config.logging

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            'paths': {
                'data_dir': self._config.paths.data_dir,
                'rules_dir': self._config.paths.rules_dir,
                'csv_dir': self._config.paths.csv_dir,
                'hdf5_dir': self._config.paths.hdf5_dir,
                'logs_dir': self._config.paths.logs_dir,
                'simdata_dir': self._config.paths.simdata_dir,
                'default_rules_file': self._config.paths.default_rules_file,
                'default_hdf5_file': self._config.paths.default_hdf5_file,
            },
            'database': {
                'host': self._config.database.host,
                'port': self._config.database.port,
                'database': self._config.database.database,
                'user': self._config.database.user,
                'pool_size': self._config.database.pool_size,
                'max_pool_size': self._config.database.max_pool_size,
            },
            'event_bus': {
                'buffer_size': self._config.event_bus.buffer_size,
                'batch_size': self._config.event_bus.batch_size,
                'worker_count': self._config.event_bus.worker_count,
                'max_queue_size': self._config.event_bus.max_queue_size,
            },
            'otel': {
                'enabled': self._config.otel.enabled,
                'endpoint': self._config.otel.endpoint,
                'service_name': self._config.otel.service_name,
                'service_version': self._config.otel.service_version,
            },
            'simulation': {
                'default_hdf5_path': self._config.simulation.default_hdf5_path,
                'default_rules_path': self._config.simulation.default_rules_path,
                'default_steps': self._config.simulation.default_steps,
            },
            'logging': {
                'level': self._config.logging.level,
                'format': self._config.logging.format,
            },
            'custom': self._config.custom,
            'overrides': self._overrides,
        }

    def reload(self) -> None:
        """Reload configuration from files."""
        self._config = SallyConfig()
        self._overrides.clear()
        self._raw_yaml.clear()
        self._load_config()
        self._apply_env_config()
        logger.info("Configuration reloaded")


# =============================================================================
# Global Configuration Instance
# =============================================================================

_config_instance: Optional[ConfigManager] = None


def get_config(environment: Optional[str] = None) -> ConfigManager:
    """Get global configuration instance.

    Args:
        environment: Environment name (only used on first call)

    Returns:
        ConfigManager instance

    Example:
        from sally.core.config import get_config

        config = get_config()
        db_host = config.database.host
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager(environment=environment)
    return _config_instance


def reset_config() -> None:
    """Reset the global configuration instance.

    Useful for testing or when configuration needs to be reloaded.
    """
    global _config_instance
    _config_instance = None


# Lazy-loaded global config proxy
class _ConfigProxy:
    """Lazy proxy to the global config instance.

    Allows importing `config` directly without calling get_config().
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(get_config(), name)

    def __repr__(self) -> str:
        return repr(get_config())


# Global config instance for direct import
config: ConfigManager = _ConfigProxy()  # type: ignore

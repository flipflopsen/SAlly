"""
sally/core/settings.py

Centralized configuration management for Sally.
All paths, endpoints, and feature flags in one place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
import logging


class LogLevel(Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(Enum):
    """Application environment."""
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


@dataclass
class PathConfig:
    """Centralized path configuration."""
    # Base paths
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    package_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)

    # Data directories
    data_dir: Path = field(init=False)
    hdf5_dir: Path = field(init=False)
    csv_dir: Path = field(init=False)
    rules_dir: Path = field(init=False)
    midas_dir: Path = field(init=False)

    # Test data
    test_data_dir: Path = field(init=False)
    test_hdf5_dir: Path = field(init=False)

    # Output directories
    logs_dir: Path = field(init=False)
    output_dir: Path = field(init=False)

    # Config directory
    config_dir: Path = field(init=False)

    # Default files
    default_hdf5_file: Path = field(init=False)
    default_rules_file: Path = field(init=False)

    def __post_init__(self):
        # Initialize derived paths from ConfigManager
        try:
            from sally.core.config import get_config
            cfg = get_config()

            self.project_root = cfg.paths.project_root
            self.package_root = cfg.paths.package_root

            self.data_dir = cfg.get_path("data_dir")
            self.hdf5_dir = cfg.get_path("hdf5_dir")
            self.csv_dir = cfg.get_path("csv_dir")
            self.rules_dir = cfg.get_path("rules_dir")
            self.midas_dir = cfg.get_path("midas_dir")

            self.logs_dir = cfg.get_path("logs_dir")
            self.config_dir = cfg.get_path("config_dir")

            self.default_hdf5_file = cfg.get_path("default_hdf5_file")
            self.default_rules_file = cfg.get_path("default_rules_file")
        except Exception:
            # Fallback to filesystem-derived paths if ConfigManager is unavailable
            self.data_dir = self.project_root / "data"
            self.hdf5_dir = self.data_dir / "hdf5"
            self.csv_dir = self.data_dir / "csv"
            self.rules_dir = self.data_dir / "rules"
            self.midas_dir = self.data_dir / "midas"

            self.logs_dir = self.project_root / "logs"
            self.config_dir = self.package_root / "config"

            sim_data_dir = self.package_root / "application" / "simulation" / "simdata"
            self.default_hdf5_file = sim_data_dir / "demo.hdf5"
            self.default_rules_file = self.rules_dir / "chainrule_pv_household.json"

        # Test and output paths derived from project root
        self.test_data_dir = self.project_root / "tests" / "test_data"
        self.test_hdf5_dir = self.test_data_dir / "hdf5"
        self.output_dir = self.project_root / "output"

        # Ensure critical directories exist
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        for dir_path in [self.logs_dir, self.output_dir, self.rules_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_hdf5_path(self, filename: str) -> Path:
        """Get full path to an HDF5 file."""
        path = self.hdf5_dir / filename
        if not path.exists():
            # Check in test data
            test_path = self.test_hdf5_dir / filename
            if test_path.exists():
                return test_path
            # Check in simdata
            sim_path = self.package_root / "application" / "simulation" / "simdata" / filename
            if sim_path.exists():
                return sim_path
        return path

    def get_rules_path(self, filename: str) -> Path:
        """Get full path to a rules file."""
        return self.rules_dir / filename


@dataclass
class OTELConfig:
    """OpenTelemetry configuration."""
    enabled: bool = False
    endpoint: str = "http://localhost:4317"
    traces_endpoint: Optional[str] = None
    metrics_endpoint: Optional[str] = None
    logs_endpoint: Optional[str] = None

    service_name: str = "sally"
    service_version: str = "0.7.3"

    # Export settings
    metrics_interval_ms: int = 10000
    traces_batch_size: int = 512
    sample_rate: float = 1.0

    # Feature flags for instrumenting specific components
    trace_event_bus: bool = True
    trace_simulation: bool = True
    trace_rules: bool = True
    trace_gui: bool = False  # GUI tracing can be noisy

    @classmethod
    def from_env(cls) -> "OTELConfig":
        """Load OTEL config from environment variables."""
        from sally.core.config import get_config
        cfg = get_config()

        return cls(
            enabled=cfg.env.SALLY_OTEL_ENABLED,
            endpoint=cfg.env.SALLY_OTEL_ENDPOINT,
            traces_endpoint=cfg.env.SALLY_OTEL_TRACES_ENDPOINT,
            metrics_endpoint=cfg.env.SALLY_OTEL_METRICS_ENDPOINT,
            logs_endpoint=cfg.env.SALLY_OTEL_LOGS_ENDPOINT,
            service_name=cfg.env.SALLY_OTEL_SERVICE_NAME,
            service_version=cfg.env.SALLY_OTEL_SERVICE_VERSION,
            metrics_interval_ms=cfg.env.SALLY_OTEL_METRICS_INTERVAL_MS,
            traces_batch_size=cfg.env.SALLY_OTEL_TRACES_BATCH_SIZE,
            sample_rate=cfg.env.SALLY_OTEL_SAMPLE_RATE,
            trace_event_bus=cfg.env.SALLY_OTEL_TRACE_EVENT_BUS,
            trace_simulation=cfg.env.SALLY_OTEL_TRACE_SIMULATION,
            trace_rules=cfg.env.SALLY_OTEL_TRACE_RULES,
            trace_gui=cfg.env.SALLY_OTEL_TRACE_GUI,
        )


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    format: str = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

    # File logging
    file_enabled: bool = True
    file_path: Optional[Path] = None
    file_max_bytes: int = 5_000_000  # 5MB
    file_backup_count: int = 5

    # Console logging
    console_enabled: bool = True
    console_colored: bool = True

    # OTEL log export (automatically enabled when OTEL is enabled)
    otel_export: bool = False

    # Per-module log levels
    module_levels: Dict[str, LogLevel] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Load logging config from environment variables."""
        from sally.core.config import get_config
        cfg = get_config()

        level_str = cfg.env.SALLY_LOG_LEVEL.upper()
        try:
            level = LogLevel[level_str]
        except KeyError:
            level = LogLevel.INFO

        return cls(
            level=level,
            file_enabled=cfg.env.SALLY_LOG_FILE_ENABLED,
            console_enabled=cfg.env.SALLY_LOG_CONSOLE_ENABLED,
            console_colored=cfg.env.SALLY_LOG_COLORED,
            otel_export=cfg.env.SALLY_LOG_OTEL_EXPORT,
        )


@dataclass
class EventBusConfig:
    """Event bus performance configuration."""
    buffer_size: int = 65536
    batch_size: int = 1024
    worker_count: int = 4
    max_queue_size: int = 10000

    # Performance tuning
    use_ring_buffer: bool = True
    enable_metrics: bool = True
    metrics_interval_ms: int = 5000

    @classmethod
    def from_env(cls) -> "EventBusConfig":
        """Load event bus config from environment variables."""
        from sally.core.config import get_config
        cfg = get_config()

        return cls(
            buffer_size=cfg.env.SALLY_EVENTBUS_BUFFER_SIZE,
            batch_size=cfg.env.SALLY_EVENTBUS_BATCH_SIZE,
            worker_count=cfg.env.SALLY_EVENTBUS_WORKER_COUNT,
            max_queue_size=cfg.env.SALLY_EVENTBUS_MAX_QUEUE_SIZE,
        )


@dataclass
class SimulationConfig:
    """Simulation configuration."""
    default_hdf5_path: str = ""  # Set from PathConfig
    default_rules_path: str = ""  # Set from PathConfig
    default_steps: int = 44640
    step_size: int = 1
    start_time: str = "2014-01-01 00:00:00"

    # Performance
    step_timeout_seconds: float = 0.5
    publish_scada_events: bool = True
    batch_events: bool = True

    @classmethod
    def from_env(cls) -> "SimulationConfig":
        """Load simulation config from environment variables."""
        from sally.core.config import get_config
        cfg = get_config()

        return cls(
            default_steps=cfg.env.SALLY_SIM_STEPS,
            step_size=cfg.env.SALLY_SIM_STEP_SIZE,
            step_timeout_seconds=cfg.env.SALLY_SIM_STEP_TIMEOUT,
            publish_scada_events=cfg.env.SALLY_SIM_PUBLISH_SCADA,
        )


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "smartgrid"
    user: str = "postgres"
    password: str = ""
    pool_size: int = 10
    max_pool_size: int = 20

    @property
    def dsn(self) -> str:
        """Get database connection string."""
        if self.password:
            return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"postgresql://{self.user}@{self.host}:{self.port}/{self.database}"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load database config from environment variables."""
        from sally.core.config import get_config
        cfg = get_config()

        return cls(
            host=cfg.env.SALLY_DB_HOST,
            port=cfg.env.SALLY_DB_PORT,
            database=cfg.env.SALLY_DB_NAME,
            user=cfg.env.SALLY_DB_USER,
            password=cfg.env.SALLY_DB_PASSWORD,
            pool_size=cfg.env.SALLY_DB_POOL_SIZE,
            max_pool_size=cfg.env.SALLY_DB_MAX_POOL_SIZE,
        )


@dataclass
class SCADAConfig:
    """SCADA GUI and orchestration configuration."""
    update_interval_ms: int = 100
    max_triggered_rules_history: int = 50
    event_buffer_size: int = 1000
    default_step_interval_s: float = 1.0

    # UI settings
    theme: str = "darkly"
    window_width: int = 1600
    window_height: int = 900

    @classmethod
    def from_env(cls) -> "SCADAConfig":
        """Load SCADA config from environment variables."""
        from sally.core.config import get_config
        cfg = get_config()

        return cls(
            update_interval_ms=cfg.env.SALLY_SCADA_UPDATE_INTERVAL_MS,
            default_step_interval_s=cfg.env.SALLY_SCADA_STEP_INTERVAL,
            theme=cfg.env.SALLY_SCADA_THEME,
        )


@dataclass
class Settings:
    """
    Master settings container for Sally.

    Usage:
        from sally.core.settings import get_settings

        settings = get_settings()
        hdf5_path = settings.paths.default_hdf5_file

        if settings.otel.enabled:
            # Initialize telemetry
            ...
    """
    environment: Environment = Environment.DEV

    paths: PathConfig = field(default_factory=PathConfig)
    otel: OTELConfig = field(default_factory=OTELConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    event_bus: EventBusConfig = field(default_factory=EventBusConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    scada: SCADAConfig = field(default_factory=SCADAConfig)

    # Additional custom configuration
    custom: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Update simulation paths from PathConfig
        if not self.simulation.default_hdf5_path:
            self.simulation.default_hdf5_path = str(self.paths.default_hdf5_file)
        if not self.simulation.default_rules_path:
            self.simulation.default_rules_path = str(self.paths.default_rules_file)

        # Set log file path from paths
        if self.logging.file_enabled and not self.logging.file_path:
            self.logging.file_path = self.paths.logs_dir / "sally.log"

        # Enable OTEL log export if OTEL is enabled
        if self.otel.enabled:
            self.logging.otel_export = True

    @classmethod
    def from_env(cls) -> "Settings":
        """Load all settings from environment variables."""
        try:
            from sally.core.config import get_config
            cfg = get_config()

            try:
                environment = Environment(cfg.environment)
            except ValueError:
                environment = Environment.DEV

            # Map ConfigManager values into Settings
            log_level = LogLevel.INFO
            if isinstance(cfg.logging.level, str) and cfg.logging.level.upper() in LogLevel.__members__:
                log_level = LogLevel[cfg.logging.level.upper()]

            return cls(
                environment=environment,
                paths=PathConfig(),
                otel=OTELConfig(
                    enabled=cfg.otel.enabled,
                    endpoint=cfg.otel.endpoint,
                    traces_endpoint=cfg.otel.traces_endpoint,
                    metrics_endpoint=cfg.otel.metrics_endpoint,
                    logs_endpoint=cfg.otel.logs_endpoint,
                    service_name=cfg.otel.service_name,
                    service_version=cfg.otel.service_version,
                    metrics_interval_ms=cfg.otel.metrics_interval_ms,
                    traces_batch_size=cfg.otel.traces_batch_size,
                    sample_rate=cfg.otel.sample_rate,
                    trace_event_bus=cfg.otel.trace_event_bus,
                    trace_simulation=cfg.otel.trace_simulation,
                    trace_rules=cfg.otel.trace_rules,
                    trace_gui=cfg.otel.trace_gui,
                ),
                logging=LoggingConfig(
                    level=log_level,
                    format=cfg.logging.format,
                    file_enabled=cfg.logging.file_enabled,
                    file_max_bytes=cfg.logging.file_max_bytes,
                    file_backup_count=cfg.logging.file_backup_count,
                    console_enabled=cfg.logging.console_enabled,
                    console_colored=cfg.logging.console_colored,
                    otel_export=cfg.logging.otel_export,
                ),
                event_bus=EventBusConfig(
                    buffer_size=cfg.event_bus.buffer_size,
                    batch_size=cfg.event_bus.batch_size,
                    worker_count=cfg.event_bus.worker_count,
                    max_queue_size=cfg.event_bus.max_queue_size,
                ),
                simulation=SimulationConfig(
                    default_hdf5_path=cfg.simulation.default_hdf5_path or str(cfg.get_path("default_hdf5_file")),
                    default_rules_path=cfg.simulation.default_rules_path or str(cfg.get_path("default_rules_file")),
                    default_steps=cfg.simulation.default_steps,
                    step_size=cfg.simulation.step_size,
                    start_time=cfg.simulation.start_time,
                    step_timeout_seconds=cfg.simulation.step_timeout_seconds,
                    publish_scada_events=cfg.simulation.publish_scada_events,
                ),
                database=DatabaseConfig(
                    host=cfg.database.host,
                    port=cfg.database.port,
                    database=cfg.database.database,
                    user=cfg.database.user,
                    password=cfg.database.password,
                    pool_size=cfg.database.pool_size,
                    max_pool_size=cfg.database.max_pool_size,
                ),
                scada=SCADAConfig(
                    update_interval_ms=cfg.scada.orchestration.update_interval_ms,
                    max_triggered_rules_history=cfg.scada.orchestration.max_triggered_rules_history,
                    event_buffer_size=cfg.scada.orchestration.event_buffer_size,
                    default_step_interval_s=cfg.scada.orchestration.default_step_interval_s,
                    theme=cfg.scada.theme,
                    window_width=cfg.scada.window_width,
                    window_height=cfg.scada.window_height,
                ),
            )
        except Exception:
            from sally.core.config import get_config
            cfg = get_config()
            env_str = cfg.env.SALLY_ENV.lower()
            try:
                environment = Environment(env_str)
            except ValueError:
                environment = Environment.DEV

            return cls(
                environment=environment,
                paths=PathConfig(),
                otel=OTELConfig.from_env(),
                logging=LoggingConfig.from_env(),
                event_bus=EventBusConfig.from_env(),
                simulation=SimulationConfig.from_env(),
                database=DatabaseConfig.from_env(),
                scada=SCADAConfig.from_env(),
            )

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Settings":
        """Load settings from a YAML configuration file."""
        import yaml

        settings = cls.from_env()  # Start with env defaults

        if not yaml_path.exists():
            return settings

        with yaml_path.open("r") as f:
            data = yaml.safe_load(f) or {}

        # Update OTEL config
        if "otel" in data:
            otel_data = data["otel"]
            for key, value in otel_data.items():
                if hasattr(settings.otel, key):
                    setattr(settings.otel, key, value)

        # Update logging config
        if "logging" in data:
            log_data = data["logging"]
            if "level" in log_data:
                try:
                    settings.logging.level = LogLevel[log_data["level"].upper()]
                except KeyError:
                    pass
            for key in ["file_enabled", "console_enabled", "console_colored"]:
                if key in log_data:
                    setattr(settings.logging, key, log_data[key])

        # Update event bus config
        if "event_bus" in data:
            for key, value in data["event_bus"].items():
                if hasattr(settings.event_bus, key):
                    setattr(settings.event_bus, key, value)

        # Update simulation config
        if "simulation" in data:
            for key, value in data["simulation"].items():
                if hasattr(settings.simulation, key):
                    setattr(settings.simulation, key, value)

        # Update database config
        if "database" in data or "db" in data:
            db_data = data.get("database", data.get("db", {}))
            for key, value in db_data.items():
                if hasattr(settings.database, key):
                    setattr(settings.database, key, value)

        # Update SCADA config
        if "scada" in data:
            scada_data = data["scada"]
            if "orchestration" in scada_data:
                for key, value in scada_data["orchestration"].items():
                    if hasattr(settings.scada, key):
                        setattr(settings.scada, key, value)
            for key, value in scada_data.items():
                if key != "orchestration" and hasattr(settings.scada, key):
                    setattr(settings.scada, key, value)

        # Store any additional custom config
        for key in data:
            if key not in ["otel", "logging", "event_bus", "simulation", "database", "db", "scada"]:
                settings.custom[key] = data[key]

        return settings

    def to_dict(self) -> Dict[str, Any]:
        """Export settings as a dictionary."""
        return {
            "environment": self.environment.value,
            "otel": {
                "enabled": self.otel.enabled,
                "endpoint": self.otel.endpoint,
                "service_name": self.otel.service_name,
            },
            "logging": {
                "level": self.logging.level.value,
                "file_enabled": self.logging.file_enabled,
                "otel_export": self.logging.otel_export,
            },
            "event_bus": {
                "buffer_size": self.event_bus.buffer_size,
                "batch_size": self.event_bus.batch_size,
                "worker_count": self.event_bus.worker_count,
            },
            "simulation": {
                "default_hdf5_path": self.simulation.default_hdf5_path,
                "default_rules_path": self.simulation.default_rules_path,
                "default_steps": self.simulation.default_steps,
            },
            "paths": {
                "project_root": str(self.paths.project_root),
                "logs_dir": str(self.paths.logs_dir),
                "hdf5_dir": str(self.paths.hdf5_dir),
                "rules_dir": str(self.paths.rules_dir),
            },
        }


# Global settings instance
_settings: Optional[Settings] = None


def get_settings(
    reload: bool = False,
    yaml_path: Optional[Path] = None,
) -> Settings:
    """
    Get the global settings instance.

    Args:
        reload: Force reload settings
        yaml_path: Optional path to YAML config file

    Returns:
        Settings instance
    """
    global _settings

    if _settings is None or reload:
        if yaml_path:
            _settings = Settings.from_yaml(yaml_path)
        else:
            # Try to load from default config
            paths = PathConfig()
            default_yaml = paths.config_dir / "default.yml"
            if default_yaml.exists():
                _settings = Settings.from_yaml(default_yaml)
            else:
                _settings = Settings.from_env()

    return _settings


def init_settings(
    environment: Optional[str] = None,
    yaml_path: Optional[Path] = None,
    **overrides,
) -> Settings:
    """
    Initialize settings with explicit configuration.

    Args:
        environment: Environment name (dev/test/prod)
        yaml_path: Path to YAML config
        **overrides: Specific setting overrides

    Returns:
        Configured Settings instance
    """
    global _settings

    if yaml_path:
        _settings = Settings.from_yaml(yaml_path)
    else:
        _settings = Settings.from_env()

    if environment:
        try:
            _settings.environment = Environment(environment)
        except ValueError:
            pass

    # Apply overrides
    for key, value in overrides.items():
        if "." in key:
            parts = key.split(".")
            obj = _settings
            for part in parts[:-1]:
                obj = getattr(obj, part, None)
                if obj is None:
                    break
            if obj is not None:
                setattr(obj, parts[-1], value)

    return _settings

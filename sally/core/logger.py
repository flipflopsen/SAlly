"""
sally/core/logger.py

Centralized logging configuration for Sally with OpenTelemetry integration.
Provides structured logging with console coloring, file rotation, and OTEL export.
Includes correlation ID injection from OTEL trace context for log-trace correlation.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING
from sally.core.config import get_config

if TYPE_CHECKING:
    from sally.core.settings import Settings

# Try to import OTEL trace context for correlation ID injection
try:
    from opentelemetry import trace as otel_trace
    _OTEL_TRACE_AVAILABLE = True
except ImportError:
    _OTEL_TRACE_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """Custom formatter with ANSI color codes for console output."""

    # ANSI escape codes
    COLORS = {
        "grey": "\x1b[38;20m",
        "green": "\x1b[32;20m",
        "yellow": "\x1b[33;20m",
        "red": "\x1b[31;20m",
        "bold_red": "\x1b[31;1m",
        "blue": "\x1b[34;20m",
        "cyan": "\x1b[36;20m",
        "reset": "\x1b[0m",
    }

    LEVEL_COLORS = {
        logging.DEBUG: "cyan",
        logging.INFO: "green",
        logging.WARNING: "yellow",
        logging.ERROR: "red",
        logging.CRITICAL: "bold_red",
    }

    def __init__(self, fmt: str = None, use_colors: bool = True):
        super().__init__(fmt or "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        self.use_colors = use_colors and self._supports_color()
        self._base_fmt = fmt or "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

    @staticmethod
    def _supports_color() -> bool:
        """Check if the terminal supports color."""
        if sys.platform == "win32":
            return True  # Modern Windows terminals support ANSI
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        if not self.use_colors:
            return super().format(record)

        color_name = self.LEVEL_COLORS.get(record.levelno, "grey")
        color = self.COLORS.get(color_name, "")
        reset = self.COLORS["reset"]
        grey = self.COLORS["grey"]

        # Create colored format
        colored_fmt = (
            f"{color}[%(asctime)s] [%(levelname)s] [%(name)s]{grey} %(message)s{reset}"
        )
        formatter = logging.Formatter(colored_fmt)
        return formatter.format(record)


# Legacy alias for backward compatibility
CustomFormatter = ColoredFormatter


import json
from datetime import datetime


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging, optimized for Loki ingestion.

    Produces JSON logs with consistent labels that Loki can parse and index:
    - timestamp: ISO 8601 format
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - logger: Logger name (module path)
    - message: Log message
    - trace_id: OTEL trace ID for correlation
    - span_id: OTEL span ID for correlation
    - service: Service name for filtering
    - extra: Additional context data

    Usage:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredJsonFormatter(service_name="SAlly.MyService"))
    """

    # Fields to extract from log record as extra data
    EXTRA_FIELDS = {
        "entity_id", "entity_type", "rule_id", "event_type",
        "timestep", "operation", "query_type", "duration_ms",
        "count", "batch_size", "error_type", "correlation_id"
    }

    def __init__(
        self,
        service_name: str = "sally",
        include_extra: bool = True,
        pretty: bool = False
    ):
        """
        Initialize the JSON formatter.

        Args:
            service_name: Service name to include in all logs
            include_extra: Whether to include extra fields from log record
            pretty: Whether to pretty-print JSON (for debugging)
        """
        super().__init__()
        self.service_name = service_name
        self.include_extra = include_extra
        self.pretty = pretty

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        # Get trace context (injected by CorrelationIdFilter)
        trace_id = getattr(record, 'trace_id', '00000000000000000000000000000000')
        span_id = getattr(record, 'span_id', '0000000000000000')

        # Build base log entry
        log_entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "trace_id": trace_id,
            "span_id": span_id,
        }

        # Add source location for errors
        if record.levelno >= logging.ERROR:
            log_entry["source"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName
            }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Extract extra fields from record
        if self.include_extra:
            extra = {}
            for key in self.EXTRA_FIELDS:
                if hasattr(record, key):
                    extra[key] = getattr(record, key)

            # Also check for any custom attributes added to the record
            for key, value in record.__dict__.items():
                if (key not in logging.LogRecord.__dict__ and
                    not key.startswith('_') and
                    key not in {'message', 'args', 'exc_info', 'exc_text',
                               'stack_info', 'trace_id', 'span_id', 'correlation_id'}):
                    if isinstance(value, (str, int, float, bool, type(None))):
                        extra[key] = value

            if extra:
                log_entry["extra"] = extra

        # Serialize to JSON
        if self.pretty:
            return json.dumps(log_entry, indent=2, default=str)
        return json.dumps(log_entry, separators=(',', ':'), default=str)


class CorrelationIdFilter(logging.Filter):
    """
    Logging filter that injects correlation ID from OTEL trace context.

    This enables log-trace correlation by adding trace_id and span_id
    to each log record, which can then be used to correlate logs with
    distributed traces in Grafana.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add correlation ID fields to the log record.

        Args:
            record: The log record to process

        Returns:
            Always True (log is never filtered out by this filter)
        """
        # Default values if no trace context
        record.trace_id = "00000000000000000000000000000000"
        record.span_id = "0000000000000000"
        record.correlation_id = ""

        if _OTEL_TRACE_AVAILABLE:
            try:
                span = otel_trace.get_current_span()
                if span is not None:
                    ctx = span.get_span_context()
                    # Check if context is valid (not the INVALID_SPAN_CONTEXT)
                    # Note: Don't check is_recording() - a span can have valid context
                    # even when not recording (e.g., sampled out or parent-based)
                    if ctx is not None and ctx.is_valid:
                        # Format as hex strings (standard OTEL format)
                        record.trace_id = format(ctx.trace_id, '032x')
                        record.span_id = format(ctx.span_id, '016x')
                        # Short correlation ID for human readability
                        record.correlation_id = record.trace_id[:8]
            except Exception:
                # Never fail logging due to correlation ID extraction
                pass

        return True


class LoggerFactory:
    """
    Factory for creating and managing loggers.

    Provides centralized configuration for all Sally loggers with:
    - Console output with optional colors
    - Rotating file logging
    - OTEL log export integration
    - Per-module log level overrides
    """

    _instance: Optional["LoggerFactory"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if LoggerFactory._initialized:
            return

        self._loggers: Dict[str, logging.Logger] = {}
        self._root_logger: Optional[logging.Logger] = None
        self._log_level: int = logging.DEBUG
        self._console_handler: Optional[logging.Handler] = None
        self._file_handler: Optional[logging.Handler] = None
        self._otel_handler: Optional[logging.Handler] = None

        # Configuration
        self._file_enabled: bool = True
        self._console_enabled: bool = True
        self._console_colored: bool = True
        self._otel_enabled: bool = False
        self._log_dir: Optional[Path] = None

        # Module-specific levels
        self._module_levels: Dict[str, int] = {}

        # Initialize with defaults
        self._setup_defaults()
        LoggerFactory._initialized = True

    def _setup_defaults(self) -> None:
        """Set up default logging configuration."""
        cfg = get_config()

        level_name = cfg.env.SALLY_LOG_LEVEL.upper()
        self._log_level = getattr(logging, level_name, logging.DEBUG)

        project_root = Path(__file__).resolve().parents[2]
        self._log_dir = project_root / "logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)

        self._otel_enabled = cfg.env.SALLY_OTEL_ENABLED

        self._root_logger = logging.getLogger("sally")
        self._root_logger.setLevel(self._log_level)
        self._root_logger.propagate = False

        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up logging handlers."""
        if self._root_logger:
            for handler in self._root_logger.handlers[:]:
                self._root_logger.removeHandler(handler)
            # Remove existing filters
            for f in self._root_logger.filters[:]:
                self._root_logger.removeFilter(f)

        # Add correlation ID filter to root logger
        correlation_filter = CorrelationIdFilter()
        self._root_logger.addFilter(correlation_filter)

        # Console handler
        if self._console_enabled:
            self._console_handler = logging.StreamHandler(sys.stdout)
            self._console_handler.setLevel(self._log_level)
            self._console_handler.setFormatter(ColoredFormatter(use_colors=self._console_colored))
            self._root_logger.addHandler(self._console_handler)

        # File handler with correlation ID in format
        if self._file_enabled and self._log_dir:
            log_file = self._log_dir / "sally.log"
            self._file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            self._file_handler.setLevel(self._log_level)
            # Add filter to handler to ensure trace fields are always present
            self._file_handler.addFilter(CorrelationIdFilter())
            # Include trace_id and span_id for log-trace correlation
            self._file_handler.setFormatter(logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] "
                "[trace_id=%(trace_id)s span_id=%(span_id)s] %(message)s"
            ))
            self._root_logger.addHandler(self._file_handler)

        # OTEL handler
        if self._otel_enabled:
            self._setup_otel_handler()

    def _setup_otel_handler(self) -> None:
        """Set up OpenTelemetry log export handler."""
        try:
            from sally.core.telemetry import get_telemetry
            telemetry = get_telemetry()

            if telemetry.log_handler:
                self._otel_handler = telemetry.log_handler
                self._root_logger.addHandler(self._otel_handler)
        except ImportError:
            pass
        except Exception as e:
            print(f"Failed to set up OTEL log handler: {e}", file=sys.stderr)

    def configure(self, settings: "Settings" = None, **kwargs) -> None:
        """Configure logging from settings or keyword arguments."""
        if settings:
            log_config = settings.logging
            self._log_level = getattr(logging, log_config.level.value, logging.DEBUG)
            self._file_enabled = log_config.file_enabled
            self._console_enabled = log_config.console_enabled
            self._console_colored = log_config.console_colored
            self._otel_enabled = log_config.otel_export or settings.otel.enabled

            if log_config.file_path:
                self._log_dir = log_config.file_path.parent
            else:
                self._log_dir = settings.paths.logs_dir

        if "level" in kwargs:
            level = kwargs["level"]
            if isinstance(level, str):
                self._log_level = getattr(logging, level.upper(), logging.DEBUG)
            else:
                self._log_level = level

        if "file_enabled" in kwargs:
            self._file_enabled = kwargs["file_enabled"]
        if "console_enabled" in kwargs:
            self._console_enabled = kwargs["console_enabled"]
        if "console_colored" in kwargs:
            self._console_colored = kwargs["console_colored"]
        if "otel_enabled" in kwargs:
            self._otel_enabled = kwargs["otel_enabled"]
        if "log_dir" in kwargs:
            self._log_dir = Path(kwargs["log_dir"])

        if self._root_logger:
            self._root_logger.setLevel(self._log_level)

        self._setup_handlers()

        for logger in self._loggers.values():
            logger.setLevel(self._log_level)

    def set_module_level(self, module_name: str, level: int) -> None:
        """Set log level for a specific module."""
        self._module_levels[module_name] = level
        if module_name in self._loggers:
            self._loggers[module_name].setLevel(level)

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the specified name."""
        if not name.startswith("sally"):
            full_name = f"sally.{name}" if name else "sally"
        else:
            full_name = name

        if full_name in self._loggers:
            return self._loggers[full_name]

        logger = logging.getLogger(full_name)
        level = self._module_levels.get(full_name, self._log_level)
        logger.setLevel(level)
        logger.propagate = True

        self._loggers[full_name] = logger
        return logger


# Global factory instance
_factory: Optional[LoggerFactory] = None


def _get_factory() -> LoggerFactory:
    """Get the global logger factory."""
    global _factory
    if _factory is None:
        _factory = LoggerFactory()
    return _factory


def get_logger(name: str = None) -> logging.Logger:
    return getLogger(name)

def getLogger(name: str = None) -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        Configured logging.Logger instance

    Example:
        from sally.core.logger import get_logger

        logger = get_logger(__name__)
        logger.info("Starting simulation...")
    """
    return _get_factory().get_logger(name or "sally")


def configure_logging(settings: "Settings" = None, **kwargs) -> None:
    """Configure the logging system."""
    _get_factory().configure(settings, **kwargs)


def set_log_level(level: str | int) -> None:
    """Set the global log level."""
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.DEBUG)
    _get_factory().configure(level=level)


def set_module_log_level(module_name: str, level: str | int) -> None:
    """Set log level for a specific module."""
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.DEBUG)
    _get_factory().set_module_level(module_name, level)


# Legacy compatibility functions
def _get_log_level() -> int:
    """Legacy function for backward compatibility."""
    from sally.core.config import get_config
    cfg = get_config()
    level_name = cfg.env.SALLY_LOG_LEVEL.upper()
    return getattr(logging, level_name, logging.DEBUG)


def _ensure_log_dir() -> Path:
    """Legacy function for backward compatibility."""
    project_root = Path(__file__).resolve().parents[2]
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def Pprint(sim_id, eid, message):
    """Pretty print with simulator ID and entity ID (legacy function)."""
    logger = get_logger("sally.simulation")
    logger.debug("[%s|%s] %s", sim_id, eid, message)

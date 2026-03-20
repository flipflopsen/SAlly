"""
sally/paths.py

Centralized path definitions for the Sally project.
Provides backward compatibility while using the new config-based path system.

Usage:
    from sally.paths import RULES_PATH, LOG_DIR, PROJECT_ROOT

    # Or use the config directly for more flexibility:
    from sally.core.config import config
    rules_path = config.get_path('rules_dir')
"""
from pathlib import Path
from typing import TYPE_CHECKING

# Avoid circular import - use lazy loading
if TYPE_CHECKING:
    from sally.core.config import ConfigManager

# --- Base Anchors ---
# Assumes this file is located at: thesis-sally-repo/sally/paths.py


def _get_config() -> "ConfigManager":
    """Lazy-load the config to avoid circular imports."""
    from sally.core.config import get_config
    return get_config()


_CONFIG = _get_config()
PACKAGE_ROOT = _CONFIG.paths.package_root
PROJECT_ROOT = _CONFIG.paths.project_root


# --- Data Directories (computed from config) ---
@property
def _rule_data_dir() -> Path:
    return _get_config().get_path('rules_dir')


# Static paths for backward compatibility (sourced from config)
RULE_DATA_DIR = _CONFIG.get_path("rules_dir")
CONFIG_DIR = _CONFIG.get_path("config_dir")
LOG_DIR = _CONFIG.get_path("logs_dir")

# --- Simulation Specific ---
SIM_APP_DIR = _CONFIG.get_path("sim_app_dir")
SIMDATA_DIR = _CONFIG.get_path("simdata_dir")

# --- Specific File Artifacts ---
RULES_PATH = _CONFIG.get_path("default_rules_file")
DEFAULT_HDF5 = _CONFIG.get_path("default_hdf5_file")

# --- Configuration Files ---
SALLY_CONFIG = CONFIG_DIR / "default.yml"
DEFAULT_CONFIG = CONFIG_DIR / "default.yml"

# --- Infrastructure ---
# Ensure directories exist (optional, depending on write permissions)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_config_path() -> Path:
    """
    Determines the active configuration path.
    Priority:
    1. SALLY_CONFIG (if exists)
    2. DEFAULT_CONFIG
    """
    if SALLY_CONFIG.exists():
        return SALLY_CONFIG
    return DEFAULT_CONFIG


# =============================================================================
# Config-based Path Accessors (preferred for new code)
# =============================================================================

def get_rules_dir() -> Path:
    """Get the rules directory path from config."""
    return _get_config().get_path('rules_dir')


def get_data_dir() -> Path:
    """Get the data directory path from config."""
    return _get_config().get_path('data_dir')


def get_logs_dir() -> Path:
    """Get the logs directory path from config."""
    return _get_config().get_path('logs_dir')


def get_simdata_dir() -> Path:
    """Get the simulation data directory path from config."""
    return _get_config().get_path('simdata_dir')


def get_default_rules_file() -> Path:
    """Get the default rules file path from config."""
    return _get_config().get_path('default_rules_file')


def get_default_hdf5_file() -> Path:
    """Get the default HDF5 file path from config."""
    return _get_config().get_path('default_hdf5_file')

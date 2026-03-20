"""
Tests for sally.core.config — ConfigManager, dataclass configs, path resolution.

Covers: PathsConfig, DatabaseConfig, EventBusConfig, OTelConfig, SimulationConfig,
        LoggingConfig, ScadaConfig, ConfigManager (load, get, set, get_path, reload),
        global get_config / reset_config.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict
from unittest.mock import patch

import pytest

from tests.diag.metrics import record_metric


# ---------------------------------------------------------------------------
# PathsConfig
# ---------------------------------------------------------------------------


class TestPathsConfig:
    """Tests for the PathsConfig dataclass."""

    def test_defaults_are_relative_strings(self):
        from sally.core.config import PathsConfig

        pc = PathsConfig()
        assert pc.data_dir == "data"
        assert pc.rules_dir == "data/rules"
        assert pc.logs_dir == "logs"
        record_metric("paths_config_defaults", 1, "bool")

    def test_resolve_returns_absolute_path(self):
        from sally.core.config import PathsConfig

        pc = PathsConfig()
        resolved = pc.resolve("rules_dir")
        assert resolved.is_absolute()
        assert "data" in str(resolved) and "rules" in str(resolved)
        record_metric("paths_resolve_absolute", 1, "bool")

    def test_resolve_unknown_attr_raises(self):
        from sally.core.config import PathsConfig

        pc = PathsConfig()
        with pytest.raises(ValueError, match="Unknown path attribute"):
            pc.resolve("nonexistent_attr")
        record_metric("paths_resolve_unknown", 1, "bool")

    def test_resolve_absolute_path_untouched(self):
        from sally.core.config import PathsConfig

        pc = PathsConfig()
        if os.name == "nt":
            pc.data_dir = "C:\\absolute\\data"
        else:
            pc.data_dir = "/absolute/data"
        resolved = pc.resolve("data_dir")
        assert resolved.is_absolute()
        record_metric("paths_resolve_absolute_untouched", 1, "bool")

    def test_project_root_and_package_root(self):
        from sally.core.config import PathsConfig

        pc = PathsConfig()
        assert pc.project_root.is_absolute()
        assert pc.package_root.is_absolute()
        assert pc.package_root.name == "sally"
        record_metric("paths_project_package_root", 1, "bool")


# ---------------------------------------------------------------------------
# DatabaseConfig
# ---------------------------------------------------------------------------


class TestDatabaseConfig:
    """Tests for DatabaseConfig including DSN generation."""

    def test_defaults(self):
        from sally.core.config import DatabaseConfig

        dc = DatabaseConfig()
        assert dc.host == "localhost"
        assert dc.port == 5432
        assert dc.database == "smartgrid"
        record_metric("db_config_defaults", 1, "bool")

    def test_dsn_without_password(self):
        from sally.core.config import DatabaseConfig

        dc = DatabaseConfig(host="db.local", port=5433, database="mydb", user="admin")
        assert "admin@db.local:5433/mydb" in dc.dsn
        assert ":" not in dc.dsn.split("@")[0].split("//")[1]  # no password
        record_metric("db_dsn_no_password", 1, "bool")

    def test_dsn_with_password(self):
        from sally.core.config import DatabaseConfig

        dc = DatabaseConfig(password="secret")
        assert "postgres:secret@" in dc.dsn
        record_metric("db_dsn_with_password", 1, "bool")


# ---------------------------------------------------------------------------
# EventBusConfig
# ---------------------------------------------------------------------------


class TestEventBusConfig:
    def test_defaults(self):
        from sally.core.config import EventBusConfig

        ec = EventBusConfig()
        assert ec.buffer_size == 65536
        assert ec.batch_size == 1024
        assert ec.worker_count == 4
        record_metric("eventbus_config_defaults", 1, "bool")


# ---------------------------------------------------------------------------
# OTelConfig
# ---------------------------------------------------------------------------


class TestOTelConfig:
    def test_defaults(self):
        from sally.core.config import OTelConfig

        oc = OTelConfig()
        assert oc.enabled is True
        assert oc.endpoint == "http://localhost:4317"
        assert oc.service_name == "sally"
        record_metric("otel_config_defaults", 1, "bool")

    def test_feature_flags(self):
        from sally.core.config import OTelConfig

        oc = OTelConfig(trace_gui=True, trace_event_bus=False)
        assert oc.trace_gui is True
        assert oc.trace_event_bus is False
        record_metric("otel_config_flags", 1, "bool")


# ---------------------------------------------------------------------------
# SimulationConfig
# ---------------------------------------------------------------------------


class TestSimulationConfig:
    def test_defaults(self):
        from sally.core.config import SimulationConfig

        sc = SimulationConfig()
        assert sc.simulation_mode == "hdf5"
        assert sc.default_steps == 44640
        assert sc.publish_scada_events is True
        record_metric("sim_config_defaults", 1, "bool")


# ---------------------------------------------------------------------------
# ScadaConfig hierarchy
# ---------------------------------------------------------------------------


class TestScadaConfig:
    def test_nested_defaults(self):
        from sally.core.config import ScadaConfig

        sc = ScadaConfig()
        assert sc.orchestration.update_interval_ms == 10
        assert sc.gui.theme == "darkly"
        assert sc.sld.auto_layout is True
        assert sc.web.bridge_mode == "mqtt"
        assert sc.web.mqtt.port == 1883
        record_metric("scada_config_nested", 1, "bool")


# ---------------------------------------------------------------------------
# EnvConfig
# ---------------------------------------------------------------------------


class TestEnvConfig:
    def test_defaults(self):
        from sally.core.config import EnvConfig

        ec = EnvConfig()
        assert ec.SALLY_ENV == "development"
        assert ec.SALLY_OTEL_ENABLED is True
        assert ec.SALLY_LOG_LEVEL == "DEBUG"
        record_metric("env_config_defaults", 1, "bool")


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------


class TestConfigManager:
    """Tests for the ConfigManager including load, get, set, and path resolution."""

    def test_get_config_singleton(self):
        from sally.core.config import get_config, reset_config

        reset_config()
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2
        record_metric("config_singleton", 1, "bool")

    def test_reset_config(self):
        from sally.core.config import get_config, reset_config

        c1 = get_config()
        reset_config()
        c2 = get_config()
        # After reset, a new instance is created
        assert c1 is not c2
        record_metric("config_reset", 1, "bool")

    def test_dot_notation_get(self):
        from sally.core.config import get_config, reset_config

        reset_config()
        cfg = get_config()
        host = cfg.get("database.host")
        assert host is not None
        assert isinstance(host, str)
        record_metric("config_dot_get", 1, "bool")

    def test_get_default_on_missing(self):
        from sally.core.config import get_config, reset_config

        reset_config()
        cfg = get_config()
        val = cfg.get("nonexistent.deeply.nested", default="fallback")
        assert val == "fallback"
        record_metric("config_get_default", 1, "bool")

    def test_set_override(self):
        from sally.core.config import get_config, reset_config

        reset_config()
        cfg = get_config()
        cfg.set("database.port", 9999)
        assert cfg.get("database.port") == 9999
        record_metric("config_set_override", 1, "bool")

    def test_get_path(self):
        from sally.core.config import get_config, reset_config

        reset_config()
        cfg = get_config()
        rules_path = cfg.get_path("rules_dir")
        assert rules_path.is_absolute()
        assert "rules" in str(rules_path)
        record_metric("config_get_path", 1, "bool")

    def test_reload(self):
        from sally.core.config import get_config, reset_config

        reset_config()
        cfg = get_config()
        cfg.set("database.port", 1234)
        assert cfg.get("database.port") == 1234
        cfg.reload()
        # Override should be gone after reload
        assert cfg.get("database.port") != 1234
        record_metric("config_reload", 1, "bool")

    def test_to_dict(self):
        from sally.core.config import get_config, reset_config

        reset_config()
        cfg = get_config()
        d = cfg.to_dict()
        assert "paths" in d
        assert "database" in d
        assert "otel" in d
        assert isinstance(d["database"]["host"], str)
        record_metric("config_to_dict", 1, "bool")

    def test_property_accessors(self):
        from sally.core.config import get_config, reset_config

        reset_config()
        cfg = get_config()
        assert cfg.database.host is not None
        assert cfg.otel.service_name == "sally"
        assert cfg.simulation.default_steps > 0
        assert cfg.logging.level is not None
        record_metric("config_property_access", 1, "bool")

    def test_legacy_accessors(self):
        from sally.core.config import get_config, reset_config

        reset_config()
        cfg = get_config()
        db = cfg.get_database_config()
        assert db.host is not None
        eb = cfg.get_event_bus_config()
        assert eb.buffer_size > 0
        record_metric("config_legacy_access", 1, "bool")

    def test_config_proxy(self):
        """Test the _ConfigProxy lazy-loading proxy."""
        from sally.core.config import config, reset_config

        reset_config()
        assert config.database.host is not None
        record_metric("config_proxy", 1, "bool")

    def test_load_yaml_file(self, tmp_path):
        """Test loading a custom YAML config file."""
        from sally.core.config import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "default.yml").write_text(
            "database:\n  host: custom_host\n  port: 9999\n",
            encoding="utf-8",
        )
        cm = ConfigManager(config_dir=config_dir)
        assert cm.database.host == "custom_host"
        assert cm.database.port == 9999
        record_metric("config_load_yaml", 1, "bool")

    def test_env_var_override(self, tmp_path, monkeypatch):
        """Test that environment variables override config values."""
        from sally.core.config import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "default.yml").write_text("database:\n  host: from_yaml\n", encoding="utf-8")

        monkeypatch.setenv("SALLY_DB_HOST", "from_env")
        cm = ConfigManager(config_dir=config_dir)
        assert cm.database.host == "from_env"
        record_metric("config_env_override", 1, "bool")

    def test_environment_overlay(self, tmp_path):
        """Test environment-specific config overlay."""
        from sally.core.config import ConfigManager

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "default.yml").write_text("database:\n  host: default\n", encoding="utf-8")
        (config_dir / "test.yml").write_text("database:\n  host: test_host\n", encoding="utf-8")

        cm = ConfigManager(config_dir=config_dir, environment="test")
        assert cm.database.host == "test_host"
        record_metric("config_env_overlay", 1, "bool")


# ---------------------------------------------------------------------------
# _update_dataclass helper
# ---------------------------------------------------------------------------


class TestUpdateDataclass:
    def test_updates_simple_fields(self):
        from sally.core.config import _update_dataclass, DatabaseConfig

        dc = DatabaseConfig()
        _update_dataclass(dc, {"host": "new_host", "port": 1234})
        assert dc.host == "new_host"
        assert dc.port == 1234
        record_metric("update_dc_simple", 1, "bool")

    def test_nested_update(self):
        from sally.core.config import _update_dataclass, ScadaConfig

        sc = ScadaConfig()
        _update_dataclass(sc, {"gui": {"theme": "solar"}})
        assert sc.gui.theme == "solar"
        record_metric("update_dc_nested", 1, "bool")

    def test_ignores_unknown_fields_gracefully(self):
        from sally.core.config import _update_dataclass, DatabaseConfig

        dc = DatabaseConfig()
        # Should not raise
        _update_dataclass(dc, {"unknown_field": "value"})
        assert not hasattr(dc, "unknown_field")
        record_metric("update_dc_unknown", 1, "bool")

    def test_empty_data(self):
        from sally.core.config import _update_dataclass, DatabaseConfig

        dc = DatabaseConfig()
        _update_dataclass(dc, {})
        assert dc.host == "localhost"  # unchanged
        _update_dataclass(dc, None)
        assert dc.host == "localhost"
        record_metric("update_dc_empty", 1, "bool")

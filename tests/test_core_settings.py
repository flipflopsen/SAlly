"""
Tests for sally.core.settings

Covers: LogLevel, Environment, PathConfig, OTELConfig, LoggingConfig,
        EventBusConfig, SimulationConfig, DatabaseConfig, SCADAConfig, Settings.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.diag.metrics import record_metric


class TestLogLevel:
    def test_values(self):
        from sally.core.settings import LogLevel
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.CRITICAL.value == "CRITICAL"
        record_metric("loglevel_values", len(LogLevel), "levels")


class TestEnvironmentEnum:
    def test_values(self):
        from sally.core.settings import Environment
        assert Environment.DEV.value == "dev"
        assert Environment.TEST.value == "test"
        assert Environment.PROD.value == "prod"
        record_metric("env_enum", len(Environment), "envs")


class TestPathConfig:
    def test_creates_directories(self, tmp_path):
        """PathConfig should derive standard paths and create directories."""
        from sally.core.settings import PathConfig
        pc = PathConfig()
        assert pc.project_root.exists()
        assert isinstance(pc.data_dir, Path)
        record_metric("pathcfg_init", 1, "bool")

    def test_get_hdf5_path(self):
        from sally.core.settings import PathConfig
        pc = PathConfig()
        hdf5_path = pc.get_hdf5_path("test.hdf5")
        assert str(hdf5_path).endswith("test.hdf5")
        record_metric("pathcfg_hdf5", 1, "bool")

    def test_get_rules_path(self):
        from sally.core.settings import PathConfig
        pc = PathConfig()
        rp = pc.get_rules_path("rules.json")
        assert str(rp).endswith("rules.json")
        record_metric("pathcfg_rules", 1, "bool")


class TestOTELConfig:
    def test_defaults(self):
        from sally.core.settings import OTELConfig
        cfg = OTELConfig()
        assert cfg.enabled is False
        assert cfg.endpoint == "http://localhost:4317"
        assert cfg.service_name == "sally"
        assert cfg.sample_rate == 1.0
        record_metric("otelcfg_defaults", 1, "bool")

    def test_feature_flags(self):
        from sally.core.settings import OTELConfig
        cfg = OTELConfig()
        assert cfg.trace_event_bus is True
        assert cfg.trace_simulation is True
        assert cfg.trace_gui is False
        record_metric("otelcfg_flags", 1, "bool")


class TestLoggingConfig:
    def test_defaults(self):
        from sally.core.settings import LoggingConfig, LogLevel
        cfg = LoggingConfig()
        assert cfg.level == LogLevel.INFO
        assert cfg.file_enabled is True
        assert cfg.console_colored is True
        assert cfg.otel_export is False
        record_metric("logcfg_defaults", 1, "bool")


class TestEventBusConfig:
    def test_defaults(self):
        from sally.core.settings import EventBusConfig
        cfg = EventBusConfig()
        assert cfg.buffer_size == 65536
        assert cfg.batch_size == 1024
        assert cfg.worker_count == 4
        assert cfg.use_ring_buffer is True
        record_metric("ebcfg_defaults", 1, "bool")


class TestSimulationConfig:
    def test_defaults(self):
        from sally.core.settings import SimulationConfig
        cfg = SimulationConfig()
        assert cfg.default_steps == 44640
        assert cfg.step_size == 1
        assert cfg.step_timeout_seconds == 0.5
        assert cfg.publish_scada_events is True
        record_metric("simcfg_defaults", 1, "bool")


class TestDatabaseConfig:
    def test_dsn_no_password(self):
        from sally.core.settings import DatabaseConfig
        cfg = DatabaseConfig(user="test", password="", host="db", port=5432, database="mydb")
        assert cfg.dsn == "postgresql://test@db:5432/mydb"
        record_metric("dbcfg_dsn_nopass", 1, "bool")

    def test_dsn_with_password(self):
        from sally.core.settings import DatabaseConfig
        cfg = DatabaseConfig(user="test", password="secret", host="db", port=5432, database="mydb")
        assert cfg.dsn == "postgresql://test:secret@db:5432/mydb"
        record_metric("dbcfg_dsn_pass", 1, "bool")


class TestSCADAConfig:
    def test_defaults(self):
        from sally.core.settings import SCADAConfig
        cfg = SCADAConfig()
        assert cfg.update_interval_ms == 100
        assert cfg.theme == "darkly"
        assert cfg.window_width == 1600
        record_metric("scadacfg_defaults", 1, "bool")


class TestSettings:
    def test_defaults(self):
        from sally.core.settings import Settings, Environment
        s = Settings()
        assert s.environment == Environment.DEV
        assert s.otel.enabled is False
        assert isinstance(s.paths, object)
        record_metric("settings_defaults", 1, "bool")

    def test_post_init_sets_sim_paths(self):
        from sally.core.settings import Settings
        s = Settings()
        assert s.simulation.default_hdf5_path != ""
        assert s.simulation.default_rules_path != ""
        record_metric("settings_sim_paths", 1, "bool")

    def test_otel_enables_log_export(self):
        from sally.core.settings import Settings, OTELConfig
        s = Settings(otel=OTELConfig(enabled=True))
        assert s.logging.otel_export is True
        record_metric("settings_otel_log", 1, "bool")

    def test_custom_dict(self):
        from sally.core.settings import Settings
        s = Settings(custom={"foo": "bar"})
        assert s.custom["foo"] == "bar"
        record_metric("settings_custom", 1, "bool")

"""
Tests for sally.core.service_telemetry

Covers: ServiceNames constants, ServiceTelemetryMixin (track_operation_start/end,
        _track_operation context manager, _record_service_span),
        load_telemetry_config_from_yaml, init_service_telemetry.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from tests.diag.metrics import record_metric


class TestServiceNames:
    def test_all_names_start_with_sally(self):
        from sally.core.service_telemetry import ServiceNames

        attrs = [a for a in dir(ServiceNames) if not a.startswith("_")]
        for attr in attrs:
            val = getattr(ServiceNames, attr)
            assert val.startswith("SAlly."), f"{attr}={val} doesn't start with SAlly."
        record_metric("svc_names_count", len(attrs), "names")

    def test_specific_names(self):
        from sally.core.service_telemetry import ServiceNames

        assert ServiceNames.ORCHESTRATOR == "SAlly.Orchestrator"
        assert ServiceNames.GRID_DATA == "SAlly.GridData"
        assert ServiceNames.RULES == "SAlly.Rules"
        assert ServiceNames.SETPOINTS == "SAlly.Setpoints"
        record_metric("svc_names_specific", 1, "bool")


class TestLoadTelemetryConfigFromYaml:
    def test_loads_otel_section(self, tmp_path):
        from sally.core.service_telemetry import load_telemetry_config_from_yaml

        cfg = {"otel": {"enabled": True, "endpoint": "http://localhost:4317"}}
        p = tmp_path / "cfg.yml"
        p.write_text(yaml.dump(cfg))

        result = load_telemetry_config_from_yaml(p)
        assert result["enabled"] is True
        assert result["endpoint"] == "http://localhost:4317"
        record_metric("yaml_otel_load", 1, "bool")

    def test_missing_file_returns_empty(self, tmp_path):
        from sally.core.service_telemetry import load_telemetry_config_from_yaml

        result = load_telemetry_config_from_yaml(tmp_path / "nope.yml")
        assert result == {}
        record_metric("yaml_missing", 1, "bool")

    def test_fallback_telemetry_key(self, tmp_path):
        from sally.core.service_telemetry import load_telemetry_config_from_yaml

        cfg = {"telemetry": {"enabled": False}}
        p = tmp_path / "cfg2.yml"
        p.write_text(yaml.dump(cfg))

        result = load_telemetry_config_from_yaml(p)
        assert result.get("enabled") is False
        record_metric("yaml_fallback", 1, "bool")


class TestServiceTelemetryMixin:
    def _make_mixin(self):
        from sally.core.service_telemetry import ServiceTelemetryMixin

        class TestSvc(ServiceTelemetryMixin):
            pass

        svc = TestSvc()
        mock_tm = MagicMock()
        mock_tm.enabled = True
        svc._init_service_telemetry("SAlly.Test", telemetry=mock_tm)
        return svc, mock_tm

    def test_init_sets_fields(self):
        svc, tm = self._make_mixin()
        assert svc._service_name == "SAlly.Test"
        assert svc._start_time > 0
        assert svc._operations_total == 0
        record_metric("mixin_init", 1, "bool")

    def test_track_operation_start_end(self):
        svc, tm = self._make_mixin()
        start = svc._track_operation_start("test_op")
        assert svc._operations_active == 1
        assert svc._operations_total == 1

        svc._track_operation_end("test_op", start, success=True)
        assert svc._operations_active == 0
        record_metric("mixin_track", 1, "bool")

    def test_track_operation_end_error(self):
        svc, tm = self._make_mixin()
        start = svc._track_operation_start("test_op")
        svc._track_operation_end("test_op", start, success=False, error_type="ValueError")
        assert svc._errors_total == 1
        record_metric("mixin_error", 1, "bool")

    def test_track_operation_context_manager_success(self):
        svc, tm = self._make_mixin()
        with svc._track_operation("op"):
            pass
        assert svc._operations_total == 1
        assert svc._errors_total == 0
        record_metric("mixin_ctx_ok", 1, "bool")

    def test_track_operation_context_manager_exception(self):
        svc, tm = self._make_mixin()
        with pytest.raises(ValueError):
            with svc._track_operation("op"):
                raise ValueError("boom")
        assert svc._errors_total == 1
        record_metric("mixin_ctx_err", 1, "bool")

    def test_record_service_span_disabled(self):
        from sally.core.service_telemetry import ServiceTelemetryMixin

        class TestSvc(ServiceTelemetryMixin):
            pass

        svc = TestSvc()
        svc._telemetry = None
        svc._service_name = "SAlly.Test"

        # Should return a nullcontext and not raise
        with svc._record_service_span("test_span"):
            pass
        record_metric("mixin_span_disabled", 1, "bool")

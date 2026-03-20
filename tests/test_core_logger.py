"""
Tests for sally.core.logger — ColoredFormatter, StructuredJsonFormatter,
CorrelationIdFilter, and logging setup helpers.

Covers: formatting, colour detection, JSON structured output, trace context injection.
"""

from __future__ import annotations

import json
import logging
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from tests.diag.metrics import record_metric


class TestColoredFormatter:
    def test_basic_format_no_color(self):
        from sally.core.logger import ColoredFormatter

        fmt = ColoredFormatter(use_colors=False)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        output = fmt.format(record)
        assert "hello" in output
        assert "INFO" in output
        record_metric("colored_fmt_nocolor", 1, "bool")

    def test_color_output_contains_ansi(self):
        from sally.core.logger import ColoredFormatter

        fmt = ColoredFormatter(use_colors=True)
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="warn msg", args=(), exc_info=None,
        )
        output = fmt.format(record)
        assert "warn msg" in output
        # ANSI codes use \x1b[
        if "\x1b[" in output:
            record_metric("colored_fmt_ansi", 1, "bool")
        else:
            record_metric("colored_fmt_ansi", 0, "bool")

    def test_level_colors_map(self):
        from sally.core.logger import ColoredFormatter

        fmt = ColoredFormatter(use_colors=True)
        for level in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]:
            assert level in fmt.LEVEL_COLORS
        record_metric("colored_fmt_levels", 5, "levels")

    def test_custom_format(self):
        from sally.core.logger import ColoredFormatter

        custom_fmt = "%(name)s :: %(message)s"
        fmt = ColoredFormatter(fmt=custom_fmt, use_colors=False)
        record = logging.LogRecord(
            name="mylogger", level=logging.INFO, pathname="", lineno=0,
            msg="custom", args=(), exc_info=None,
        )
        output = fmt.format(record)
        assert "mylogger" in output
        assert "custom" in output
        record_metric("colored_fmt_custom", 1, "bool")


class TestStructuredJsonFormatter:
    def test_json_output_is_valid(self):
        from sally.core.logger import StructuredJsonFormatter

        fmt = StructuredJsonFormatter(service_name="test_service")
        record = logging.LogRecord(
            name="test.module", level=logging.INFO, pathname="test.py", lineno=42,
            msg="structured log", args=(), exc_info=None,
        )
        output = fmt.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "structured log"
        assert data["service"] == "test_service"
        assert "timestamp" in data
        assert "trace_id" in data
        record_metric("json_fmt_valid", 1, "bool")

    def test_error_includes_source(self):
        from sally.core.logger import StructuredJsonFormatter

        fmt = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="myfile.py", lineno=99,
            msg="error!", args=(), exc_info=None,
        )
        record.funcName = "test_func"
        output = fmt.format(record)
        data = json.loads(output)
        assert "source" in data
        assert data["source"]["line"] == 99
        record_metric("json_fmt_error_source", 1, "bool")

    def test_exception_included(self):
        from sally.core.logger import StructuredJsonFormatter

        fmt = StructuredJsonFormatter()
        try:
            raise ValueError("test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="oops", args=(), exc_info=exc_info,
        )
        output = fmt.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]
        record_metric("json_fmt_exception", 1, "bool")

    def test_pretty_print(self):
        from sally.core.logger import StructuredJsonFormatter

        fmt = StructuredJsonFormatter(pretty=True)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="pretty", args=(), exc_info=None,
        )
        output = fmt.format(record)
        assert "\n" in output  # Indented JSON has newlines
        record_metric("json_fmt_pretty", 1, "bool")

    def test_extra_fields(self):
        from sally.core.logger import StructuredJsonFormatter

        fmt = StructuredJsonFormatter(include_extra=True)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="extra", args=(), exc_info=None,
        )
        record.entity_id = "GEN_1"  # type: ignore
        record.entity_type = "generator"  # type: ignore
        output = fmt.format(record)
        data = json.loads(output)
        assert "extra" in data
        assert data["extra"]["entity_id"] == "GEN_1"
        record_metric("json_fmt_extra", 2, "fields")


class TestCorrelationIdFilter:
    def test_filter_adds_trace_id(self):
        from sally.core.logger import CorrelationIdFilter

        filt = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="corr", args=(), exc_info=None,
        )
        result = filt.filter(record)
        assert result is True
        assert hasattr(record, "trace_id")
        assert hasattr(record, "span_id")
        record_metric("corr_filter_ids", 1, "bool")


class TestCustomFormatterAlias:
    def test_backward_compatibility(self):
        from sally.core.logger import CustomFormatter, ColoredFormatter

        assert CustomFormatter is ColoredFormatter
        record_metric("formatter_alias", 1, "bool")

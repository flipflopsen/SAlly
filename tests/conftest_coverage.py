"""
Shared fixtures for comprehensive coverage tests.

Provides mock objects, test helpers, and fixtures that avoid
importing heavy dependencies (TimescaleDB, OTEL, etc.) directly.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Async test support ──────────────────────────────────────────────────────
@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── TimescaleDB mock ────────────────────────────────────────────────────────
class MockTimescaleDB:
    """Mock TimescaleDBConnection for testing services without a real DB."""

    def __init__(self):
        self.inserted_batches: List[List[Dict]] = []
        self.entity_dicts: List[Dict] = []
        self.connection_dicts: List[Dict] = []
        self.queries: List[tuple] = []
        self._fail_next = False

    async def insert_grid_data_batch(self, batch):
        if self._fail_next:
            self._fail_next = False
            raise RuntimeError("Simulated DB failure")
        self.inserted_batches.append(list(batch))

    async def upsert_grid_entities(self, entity_dicts):
        self.entity_dicts.extend(entity_dicts)

    async def upsert_grid_connections(self, connection_dicts):
        self.connection_dicts.extend(connection_dicts)

    async def execute_query(self, query, *args):
        self.queries.append((query, args))
        return []

    async def stream_recent_grid_data_continuous(self, **kwargs):
        # Yield one empty batch then stop
        yield []

    async def stream_grid_data(self, **kwargs):
        yield []

    def acquire(self):
        return _MockAcquireCtx()

    def set_fail_next(self):
        self._fail_next = True


class _MockAcquireCtx:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_db():
    return MockTimescaleDB()


# ── EventBus mock ───────────────────────────────────────────────────────────
class MockEventBus:
    """Lightweight event bus mock for testing."""

    def __init__(self):
        self.published_events: List[Any] = []
        self.handlers: Dict[str, List[Any]] = {}

    async def publish(self, event):
        self.published_events.append(event)

    def publish_sync(self, event):
        self.published_events.append(event)

    def subscribe(self, handler):
        for et in getattr(handler, "event_types", []):
            self.handlers.setdefault(et, []).append(handler)

    def get_metrics(self):
        return {"published": len(self.published_events)}


@pytest.fixture
def mock_event_bus():
    return MockEventBus()


# ── TelemetryManager mock ──────────────────────────────────────────────────
class MockTelemetryManager:
    """Mock telemetry that stores all operations for assertion."""

    def __init__(self):
        self.enabled = False
        self.counters: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = {}
        self.gauges: Dict[str, Any] = {}
        self.spans: List[Dict] = []

    def counter(self, name, value=1, labels=None):
        self.counters[name] = self.counters.get(name, 0) + value

    def increment_counter(self, name, value=1.0, labels=None):
        self.counters[name] = self.counters.get(name, 0) + value

    def histogram(self, name, value, labels=None):
        self.histograms.setdefault(name, []).append(value)

    def record_histogram(self, name, value, labels=None):
        self.histograms.setdefault(name, []).append(value)

    def gauge(self, name, callback_or_value, description=""):
        self.gauges[name] = callback_or_value

    def set_gauge(self, name, value, labels=None):
        self.gauges[name] = value

    def start_span(self, name, kind="internal", attributes=None):
        span = MagicMock()
        span.end = MagicMock()
        self.spans.append({"name": name, "kind": kind, "attributes": attributes})
        return span

    def span(self, name, attributes=None):
        return MagicMock(__enter__=MagicMock(), __exit__=MagicMock())

    @staticmethod
    def get_instance():
        return MockTelemetryManager()


@pytest.fixture
def mock_telemetry():
    return MockTelemetryManager()


# ── Temporary config directory ──────────────────────────────────────────────
@pytest.fixture
def tmp_config_dir(tmp_path):
    """Create a temporary config directory with a default.yml."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    default_yml = config_dir / "default.yml"
    default_yml.write_text(
        """
paths:
  data_dir: data
  rules_dir: data/rules
  logs_dir: logs

database:
  host: localhost
  port: 5432
  database: test_smartgrid

otel:
  enabled: false
  endpoint: http://localhost:4317

logging:
  level: DEBUG
  console_enabled: true

simulation:
  default_steps: 100
  step_size: 1
""",
        encoding="utf-8",
    )
    return config_dir

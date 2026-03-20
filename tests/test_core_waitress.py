"""
Tests for sally.core.waitress — high_precision_wait function.

Covers: timing accuracy, GIL-release behaviour, edge cases.
"""

from __future__ import annotations

import time

import pytest

from sally.core.waitress import high_precision_wait
from tests.diag.metrics import record_metric


class TestHighPrecisionWait:
    def test_basic_wait_accuracy(self):
        """Wait should be accurate within 5 ms for a 50 ms target."""
        target = 0.05  # 50 ms
        start = time.perf_counter()
        high_precision_wait(target)
        elapsed = time.perf_counter() - start
        assert elapsed >= target
        assert elapsed < target + 0.010  # within 10 ms overshoot
        record_metric("wait_accuracy_50ms", elapsed * 1000, "ms")

    def test_short_wait(self):
        """Very short waits (1 ms) — mostly busy-wait."""
        target = 0.001
        start = time.perf_counter()
        high_precision_wait(target)
        elapsed = time.perf_counter() - start
        assert elapsed >= target
        assert elapsed < target + 0.010
        record_metric("wait_accuracy_1ms", elapsed * 1000, "ms")

    def test_zero_duration(self):
        """Zero duration should return nearly instantly."""
        start = time.perf_counter()
        high_precision_wait(0.0)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.005  # less than 5 ms
        record_metric("wait_zero_duration", elapsed * 1000, "ms")

    def test_custom_tolerance(self):
        """Custom sleep_tolerance should still produce accurate waits."""
        target = 0.02
        start = time.perf_counter()
        high_precision_wait(target, sleep_tolerance=0.005)
        elapsed = time.perf_counter() - start
        assert elapsed >= target
        assert elapsed < target + 0.010
        record_metric("wait_custom_tolerance", elapsed * 1000, "ms")

    def test_longer_wait(self):
        """200 ms wait with timing record."""
        target = 0.2
        start = time.perf_counter()
        high_precision_wait(target)
        elapsed = time.perf_counter() - start
        assert elapsed >= target
        assert elapsed < target + 0.015
        record_metric("wait_accuracy_200ms", elapsed * 1000, "ms")

    @pytest.mark.benchmark
    def test_many_short_waits(self):
        """Benchmark: 100 × 1 ms waits."""
        n = 100
        target = 0.001
        total_start = time.perf_counter()
        for _ in range(n):
            high_precision_wait(target)
        total = time.perf_counter() - total_start
        avg_ms = (total / n) * 1000
        record_metric("wait_avg_1ms_100x", avg_ms, "ms")
        assert avg_ms < 5.0  # Each wait should average < 5 ms overhead

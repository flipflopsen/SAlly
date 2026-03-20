"""
Tests for sally.core.buffers — base ABC and registry.

Covers: BufferScenario, EventBusBuffer ABC, registry (get_buffer_for_scenario).
"""

from __future__ import annotations

from typing import List, Optional

import pytest

from sally.core.buffers.base import BufferScenario, EventBusBuffer
from sally.core.buffers.registry import get_buffer_for_scenario, AVAILABLE_BUFFERS
from sally.core.buffers.ring_buffer import RingBuffer
from sally.core.buffers.mpsc_buffer import MPSCBuffer
from sally.core.buffers.spmc_buffer import SPMCBuffer
from sally.core.buffers.mpmc_buffer import MPMCBuffer
from sally.core.event_bus import Event
from tests.diag.metrics import record_metric


# ---------------------------------------------------------------------------
# BufferScenario
# ---------------------------------------------------------------------------


class TestBufferScenario:
    def test_scenario_values(self):
        assert BufferScenario.SPSC == "spsc"
        assert BufferScenario.SPMC == "spmc"
        assert BufferScenario.MPSC == "mpsc"
        assert BufferScenario.MPMC == "mpmc"
        record_metric("buffer_scenarios", 4, "count")


# ---------------------------------------------------------------------------
# EventBusBuffer ABC
# ---------------------------------------------------------------------------


class TestEventBusBufferABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            EventBusBuffer()  # type: ignore
        record_metric("buffer_abc_guard", 1, "bool")


# ---------------------------------------------------------------------------
# Registry: get_buffer_for_scenario
# ---------------------------------------------------------------------------


class TestBufferRegistry:
    @pytest.mark.parametrize(
        "scenario,expected_type",
        [
            (BufferScenario.SPSC, RingBuffer),
            (BufferScenario.SPMC, SPMCBuffer),
            (BufferScenario.MPSC, MPSCBuffer),
            (BufferScenario.MPMC, MPMCBuffer),
        ],
    )
    def test_correct_buffer_selection(self, scenario, expected_type):
        buf = get_buffer_for_scenario(scenario, capacity=128)
        assert isinstance(buf, expected_type)
        assert buf.capacity == 128
        record_metric(f"registry_{scenario}", 1, "bool")

    def test_fallback_when_preferred_unavailable(self):
        """When preferred buffer is missing, fall back to a safe alternative."""
        limited = [RingBuffer, MPMCBuffer]
        buf = get_buffer_for_scenario(BufferScenario.MPSC, capacity=64, available_buffers=limited)
        assert isinstance(buf, MPMCBuffer)
        record_metric("registry_fallback_mpsc", 1, "bool")

    def test_fallback_consumer_safety(self):
        limited = [RingBuffer, MPMCBuffer]
        buf = get_buffer_for_scenario(BufferScenario.SPMC, capacity=64, available_buffers=limited)
        assert isinstance(buf, MPMCBuffer)
        record_metric("registry_fallback_spmc", 1, "bool")

    def test_all_available_buffers_present(self):
        assert RingBuffer in AVAILABLE_BUFFERS
        assert SPMCBuffer in AVAILABLE_BUFFERS
        assert MPSCBuffer in AVAILABLE_BUFFERS
        assert MPMCBuffer in AVAILABLE_BUFFERS
        record_metric("registry_all_available", 4, "count")

    def test_empty_available_raises(self):
        with pytest.raises(ValueError, match="No buffer types available"):
            get_buffer_for_scenario(BufferScenario.SPSC, capacity=64, available_buffers=[])
        record_metric("registry_empty_raises", 1, "bool")


# ---------------------------------------------------------------------------
# Concrete buffer basic API
# ---------------------------------------------------------------------------


class TestRingBufferAPI:
    def test_push_pop(self):
        buf = RingBuffer(16)
        evt = Event(event_type="test")
        assert buf.push(evt) is True
        assert len(buf) == 1
        assert buf.is_empty is False
        popped = buf.pop()
        assert popped is not None
        assert popped.event_type == "test"
        assert buf.is_empty is True
        record_metric("ring_push_pop", 1, "bool")

    def test_batch_pop(self):
        buf = RingBuffer(32)
        for i in range(10):
            buf.push(Event(event_type=f"e{i}"))
        batch = buf.pop_batch(5)
        assert len(batch) == 5
        assert len(buf) == 5
        record_metric("ring_batch_pop", 5, "events")

    def test_peek(self):
        buf = RingBuffer(16)
        buf.push(Event(event_type="peek_test"))
        peeked = buf.peek()
        assert peeked is not None
        assert peeked.event_type == "peek_test"
        assert len(buf) == 1  # not consumed
        record_metric("ring_peek", 1, "bool")

    def test_peek_batch(self):
        buf = RingBuffer(32)
        for i in range(5):
            buf.push(Event(event_type=f"e{i}"))
        peeked = buf.peek_batch(3)
        assert len(peeked) == 3
        assert len(buf) == 5  # still there
        record_metric("ring_peek_batch", 3, "events")

    def test_full_buffer(self):
        buf = RingBuffer(4)
        for i in range(4):
            assert buf.push(Event(event_type=f"e{i}")) is True
        assert buf.is_full is True
        # Next push should fail or overwrite depending on implementation
        record_metric("ring_full", 4, "events")

    def test_pop_empty(self):
        buf = RingBuffer(8)
        assert buf.pop() is None
        assert buf.pop_batch(5) == []
        record_metric("ring_pop_empty", 1, "bool")


class TestMPSCBufferAPI:
    def test_push_pop(self):
        buf = MPSCBuffer(16)
        evt = Event(event_type="mpsc_test")
        assert buf.push(evt) is True
        popped = buf.pop()
        assert popped is not None and popped.event_type == "mpsc_test"
        record_metric("mpsc_push_pop", 1, "bool")

    def test_scenario(self):
        buf = MPSCBuffer(16)
        assert buf.scenario == BufferScenario.MPSC
        record_metric("mpsc_scenario", 1, "bool")


class TestSPMCBufferAPI:
    def test_push_pop(self):
        buf = SPMCBuffer(16)
        evt = Event(event_type="spmc_test")
        assert buf.push(evt) is True
        popped = buf.pop()
        assert popped is not None and popped.event_type == "spmc_test"
        record_metric("spmc_push_pop", 1, "bool")

    def test_scenario(self):
        buf = SPMCBuffer(16)
        assert buf.scenario == BufferScenario.SPMC
        record_metric("spmc_scenario", 1, "bool")


class TestMPMCBufferAPI:
    def test_push_pop(self):
        buf = MPMCBuffer(16)
        evt = Event(event_type="mpmc_test")
        assert buf.push(evt) is True
        popped = buf.pop()
        assert popped is not None and popped.event_type == "mpmc_test"
        record_metric("mpmc_push_pop", 1, "bool")

    def test_scenario(self):
        buf = MPMCBuffer(16)
        assert buf.scenario == BufferScenario.MPMC
        record_metric("mpmc_scenario", 1, "bool")

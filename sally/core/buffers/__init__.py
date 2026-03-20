"""
EventBus buffer implementations for various producer/consumer scenarios.

This module provides high-performance buffer implementations optimized for
different threading scenarios:

- RingBuffer (SPSC): Lock-free, single producer, single consumer
- SPMCBuffer: Single producer, multiple consumers (lock on pop)
- MPSCBuffer: Multiple producers, single consumer (lock on push)
- MPMCBuffer: Multiple producers, multiple consumers (fully locked)

Usage:
    from sally.core.buffers import RingBuffer, get_buffer_for_scenario, BufferScenario

    # Direct instantiation
    buffer = RingBuffer(capacity=1024)

    # Auto-selection based on scenario
    buffer = get_buffer_for_scenario(BufferScenario.MPMC, capacity=1024)
"""

from .base import BufferScenario, EventBusBuffer
from .ring_buffer import RingBuffer
from .mpsc_buffer import MPSCBuffer
from .spmc_buffer import SPMCBuffer
from .mpmc_buffer import MPMCBuffer
from .registry import AVAILABLE_BUFFERS, get_buffer_for_scenario


__all__ = [
    # Base classes and enums
    "BufferScenario",
    "EventBusBuffer",
    # Buffer implementations
    "RingBuffer",
    "MPSCBuffer",
    "SPMCBuffer",
    "MPMCBuffer",
    # Registry
    "AVAILABLE_BUFFERS",
    "get_buffer_for_scenario",
]

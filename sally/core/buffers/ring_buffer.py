"""
RingBuffer - Lock-free SPSC (Single Producer, Single Consumer) buffer.

This buffer provides the highest performance for single-threaded scenarios
where only one producer and one consumer access the buffer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from .base import BufferScenario, EventBusBuffer

if TYPE_CHECKING:
    from sally.core.event_bus import Event


logger = logging.getLogger(__name__)


class RingBuffer(EventBusBuffer):
    """
    Lock-free ring buffer for high-performance event queuing.

    Optimized for single-producer, single-consumer (SPSC) scenarios.
    Uses power-of-2 sizing for fast modulo operations.

    Thread-safety: NOT thread-safe. Use only with single producer and single consumer.
    """

    __slots__ = ('_buffer', '_capacity', '_mask', '_head', '_tail', '_size')

    def __init__(self, capacity: int = 65536):
        # Round up to next power of 2 for fast modulo
        self._capacity = 1 << (capacity - 1).bit_length()
        self._mask = self._capacity - 1
        self._buffer: List[Optional[Event]] = [None] * self._capacity
        self._head = 0  # Write position
        self._tail = 0  # Read position
        self._size = 0
        logger.debug("RingBuffer (SPSC) initialized with capacity %d", self._capacity)

    @property
    def scenario(self) -> str:
        return BufferScenario.SPSC

    def push(self, event: Event) -> bool:
        """Push event to buffer. Returns False if full."""
        if self._size >= self._capacity:
            return False
        self._buffer[self._head & self._mask] = event
        self._head += 1
        self._size += 1
        return True

    def pop(self) -> Optional[Event]:
        """Pop event from buffer. Returns None if empty."""
        if self._size == 0:
            return None
        event = self._buffer[self._tail & self._mask]
        self._buffer[self._tail & self._mask] = None  # Help GC
        self._tail += 1
        self._size -= 1
        return event

    def pop_batch(self, max_count: int) -> List[Event]:
        """Pop up to max_count events. More efficient than repeated pop()."""
        count = min(max_count, self._size)
        if count == 0:
            return []

        events = []
        for _ in range(count):
            idx = self._tail & self._mask
            events.append(self._buffer[idx])
            self._buffer[idx] = None
            self._tail += 1
        self._size -= count
        return events

    def peek(self) -> Optional[Event]:
        """Peek at next event without removing it."""
        if self._size == 0:
            return None
        return self._buffer[self._tail & self._mask]

    def peek_batch(self, max_count: int) -> List[Event]:
        """Peek at up to max_count events without removing them."""
        count = min(max_count, self._size)
        if count == 0:
            return []

        events = []
        tail = self._tail
        for _ in range(count):
            events.append(self._buffer[tail & self._mask])
            tail += 1
        return events

    def __len__(self) -> int:
        return self._size

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def is_empty(self) -> bool:
        return self._size == 0

    @property
    def is_full(self) -> bool:
        return self._size >= self._capacity

"""
MPMCBuffer - Fully thread-safe Multiple Producer, Multiple Consumer buffer.

This buffer is the safest option when multiple threads both publish
and consume events. Uses full locking for maximum thread-safety.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, List, Optional

from .base import BufferScenario, EventBusBuffer

if TYPE_CHECKING:
    from sally.core.event_bus import Event


logger = logging.getLogger(__name__)


class MPMCBuffer(EventBusBuffer):
    """
    Fully thread-safe buffer for multiple producers and multiple consumers.

    Uses a single lock for all operations. While less performant than
    specialized buffers, it provides maximum flexibility.

    Thread-safety: Fully thread-safe for any number of producers and consumers.
    """

    __slots__ = ('_buffer', '_capacity', '_mask', '_head', '_tail', '_size', '_lock')

    def __init__(self, capacity: int = 65536):
        self._capacity = 1 << (capacity - 1).bit_length()
        self._mask = self._capacity - 1
        self._buffer: List[Optional[Event]] = [None] * self._capacity
        self._head = 0
        self._tail = 0
        self._size = 0
        self._lock = threading.Lock()
        logger.debug("MPMCBuffer initialized with capacity %d", self._capacity)

    @property
    def scenario(self) -> str:
        return BufferScenario.MPMC

    def push(self, event: Event) -> bool:
        """Thread-safe push."""
        with self._lock:
            if self._size >= self._capacity:
                return False
            self._buffer[self._head & self._mask] = event
            self._head += 1
            self._size += 1
            return True

    def pop(self) -> Optional[Event]:
        """Thread-safe pop."""
        with self._lock:
            if self._size == 0:
                return None
            event = self._buffer[self._tail & self._mask]
            self._buffer[self._tail & self._mask] = None
            self._tail += 1
            self._size -= 1
            return event

    def pop_batch(self, max_count: int) -> List[Event]:
        """Thread-safe batch pop."""
        with self._lock:
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
        """Thread-safe peek at next event."""
        with self._lock:
            if self._size == 0:
                return None
            return self._buffer[self._tail & self._mask]

    def peek_batch(self, max_count: int) -> List[Event]:
        """Thread-safe peek at up to max_count events."""
        with self._lock:
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
        with self._lock:
            return self._size

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def is_empty(self) -> bool:
        with self._lock:
            return self._size == 0

    @property
    def is_full(self) -> bool:
        with self._lock:
            return self._size >= self._capacity

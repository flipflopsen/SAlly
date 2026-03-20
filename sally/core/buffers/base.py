"""
Base classes and enums for EventBus buffer implementations.

This module provides the abstract base class and scenario identifiers
for all buffer types used by the EventBus.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from sally.core.event_bus import Event


# =============================================================================
# Buffer Scenario Enum
# =============================================================================

class BufferScenario:
    """Buffer usage scenario identifiers."""
    SPSC = "spsc"  # Single Producer, Single Consumer
    SPMC = "spmc"  # Single Producer, Multiple Consumer
    MPSC = "mpsc"  # Multiple Producer, Single Consumer
    MPMC = "mpmc"  # Multiple Producer, Multiple Consumer


# =============================================================================
# EventBusBuffer - Abstract Base Class for all buffer types
# =============================================================================

class EventBusBuffer(ABC):
    """
    Abstract base class for event bus buffers.

    All buffer implementations must inherit from this class and implement
    the required methods. This allows the EventBus to work with different
    buffer types optimized for various producer/consumer scenarios.
    """

    @property
    @abstractmethod
    def scenario(self) -> str:
        """Return the buffer's optimized scenario (SPSC, SPMC, MPSC, MPMC)."""
        ...

    @abstractmethod
    def push(self, event: Event) -> bool:
        """Push event to buffer. Returns False if full."""
        ...

    @abstractmethod
    def pop(self) -> Optional[Event]:
        """Pop event from buffer. Returns None if empty."""
        ...

    @abstractmethod
    def pop_batch(self, max_count: int) -> List[Event]:
        """Pop up to max_count events."""
        ...

    @abstractmethod
    def peek(self) -> Optional[Event]:
        """Peek at next event without removing it. Returns None if empty."""
        ...

    @abstractmethod
    def peek_batch(self, max_count: int) -> List[Event]:
        """Peek at up to max_count events without removing them."""
        ...

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of events in the buffer."""
        ...

    @property
    @abstractmethod
    def capacity(self) -> int:
        """Return the buffer capacity."""
        ...

    @property
    @abstractmethod
    def is_empty(self) -> bool:
        """Return True if buffer is empty."""
        ...

    @property
    @abstractmethod
    def is_full(self) -> bool:
        """Return True if buffer is full."""
        ...

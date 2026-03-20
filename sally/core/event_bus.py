# core/event_bus.py
"""
High-Performance Event Bus for Smart Grid Simulation

This module provides a high-throughput event bus capable of processing
millions of events per second using:
- Lock-free ring buffers for minimal contention
- Batch processing to reduce per-event overhead
- Memory pooling to avoid allocation costs
- Multiple worker strategies (asyncio, sync)
- OpenTelemetry tracing for every event (configurable)

Performance targets:
- Publish: >5M events/second (fire-and-forget)
- Process: >1M events/second (with simple handlers)
"""

from __future__ import annotations

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Union,
)

from sally.core.logger import get_logger

# Import buffer implementations from dedicated buffers module
from sally.core.buffers import (
    BufferScenario,
    EventBusBuffer,
    RingBuffer,
    MPSCBuffer,
    SPMCBuffer,
    MPMCBuffer,
    AVAILABLE_BUFFERS,
    get_buffer_for_scenario,
)

logger = get_logger(__name__)

# Try to import telemetry - gracefully handle if not available
_TELEMETRY_AVAILABLE = True
try:
    from sally.core.telemetry import get_telemetry, TelemetryManager
    _TELEMETRY_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# Event Classes
# =============================================================================

@dataclass(slots=True)
class Event:
    """
    Base event class optimized for high-throughput scenarios.

    Uses __slots__ via dataclass(slots=True) for memory efficiency.
    Timestamp defaults to current time if not provided.
    """
    event_type: str
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    lifetime_seconds: int = 600  # For TTL-based expiration, 0 = infinite
    delete_event_after_all_subscribers_handled: bool = True  # Hint for memory management


class EventHandler(Protocol):
    """Protocol for event handlers - supports both sync and async handlers."""

    @property
    def event_types(self) -> List[str]:
        """Event types this handler subscribes to."""
        ...

    async def handle(self, event: Event) -> None:
        """Handle an event asynchronously."""
        ...


class SyncEventHandler(Protocol):
    """Protocol for synchronous event handlers (higher throughput)."""

    @property
    def event_types(self) -> List[str]:
        ...

    def handle_sync(self, event: Event) -> None:
        """Handle an event synchronously."""
        ...


# =============================================================================
# Metrics Collector - Low-overhead performance tracking with OTEL
# =============================================================================

@dataclass
class EventBusMetrics:
    """Performance metrics with minimal overhead and OTEL export."""
    events_published: int = 0
    events_processed: int = 0
    events_dropped: int = 0
    batches_processed: int = 0
    total_processing_time_ns: int = 0
    peak_queue_size: int = 0

    # Rolling window for recent latencies (fixed size to avoid allocations)
    _latency_window: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    def record_latency(self, latency_ns: float) -> None:
        """Record a processing latency sample."""
        self._latency_window.append(latency_ns)

    def get_avg_latency_us(self) -> float:
        """Get average latency in microseconds."""
        if not self._latency_window:
            return 0.0
        return sum(self._latency_window) / len(self._latency_window) / 1000

    def get_throughput(self, elapsed_seconds: float) -> float:
        """Calculate events per second."""
        if elapsed_seconds <= 0:
            return 0.0
        return self.events_processed / elapsed_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary."""
        return {
            'events_published': self.events_published,
            'events_processed': self.events_processed,
            'events_dropped': self.events_dropped,
            'batches_processed': self.batches_processed,
            'avg_latency_us': self.get_avg_latency_us(),
            'peak_queue_size': self.peak_queue_size,
        }


# =============================================================================
# High-Performance Event Bus with OTEL Tracing
# =============================================================================

class EventBus:
    """
    High-performance event bus optimized for millions of events per second.

    Features:
    - Multiple buffer types for different producer/consumer scenarios
    - Automatic buffer selection based on detected usage patterns
    - Batch processing to amortize overhead
    - Support for both sync and async handlers
    - Event TTL (lifetime_seconds) support
    - Handler-controlled event retention (delete_event_after_all_subscribers_handled)
    - Configurable worker count
    - Low-overhead metrics collection
    - OpenTelemetry tracing for event processing (configurable)

    Buffer Scenarios:
    - SPSC (Single Producer, Single Consumer): RingBuffer - fastest, no locks
    - SPMC (Single Producer, Multiple Consumer): SPMCBuffer - lock on pop
    - MPSC (Multiple Producer, Single Consumer): MPSCBuffer - lock on push
    - MPMC (Multiple Producer, Multiple Consumer): MPMCBuffer - fully locked

    Usage:
        bus = EventBus(buffer_size=65536, batch_size=256, worker_count=4)
        bus.subscribe(my_handler)
        await bus.start()

        # Publish events (fire-and-forget for max throughput)
        bus.publish_sync(event)  # Non-blocking

        # Or async publish with backpressure
        await bus.publish(event)

        await bus.stop()
    """

    __slots__ = (
        '_handlers', '_sync_handlers', '_buffers', '_running', '_tasks',
        '_metrics', '_buffer_size', '_batch_size', '_worker_count',
        '_start_time', '_lock', '_event_types', '_telemetry', '_trace_events',
        '_otel_metrics_registered', '_last_metrics_export', '_event_type_counters',
        '_available_buffers', '_no_removal_handlers', '_no_removal_sync_handlers',
        '_event_handler_counts', '_producer_count', '_consumer_count'
    )

    def __init__(
        self,
        buffer_size: int = 65536,
        batch_size: int = 256,
        worker_count: int = 4,
        max_queue_size: int = None,  # Legacy parameter, maps to buffer_size
        trace_events: bool = True,   # Enable OTEL tracing per event
        available_buffers: Optional[List[type]] = None,  # Buffer types to use
    ):
        """
        Initialize the event bus.

        Args:
            buffer_size: Size of ring buffer per event type (power of 2 recommended)
            batch_size: Number of events to process per batch
            worker_count: Number of worker tasks per event type
            max_queue_size: Legacy parameter, use buffer_size instead
            trace_events: Enable OpenTelemetry spans for each event (default: True)
            available_buffers: List of buffer classes to use. EventBus will select
                               the most appropriate based on detected scenario.
                               Example: [RingBuffer, MPMCBuffer]
        """
        if max_queue_size is not None:
            buffer_size = max_queue_size

        self._buffer_size = buffer_size
        self._batch_size = batch_size
        self._worker_count = worker_count
        self._trace_events = trace_events
        self._available_buffers = available_buffers or AVAILABLE_BUFFERS

        self._handlers: Dict[str, List[EventHandler]] = {}
        self._sync_handlers: Dict[str, List[SyncEventHandler]] = {}
        self._buffers: Dict[str, EventBusBuffer] = {}
        self._event_types: Set[str] = set()

        # Track handlers subscribed via subscribe_to_all_without_removal
        self._no_removal_handlers: Dict[str, List[EventHandler]] = {}
        self._no_removal_sync_handlers: Dict[str, List[SyncEventHandler]] = {}

        # Track handler counts per event for non-removal events
        # Maps event_id -> set of handler names that have processed it
        self._event_handler_counts: Dict[str, Set[str]] = {}

        # Producer/consumer counts for scenario detection
        self._producer_count: int = 1  # Default: single producer (main thread)
        self._consumer_count: int = worker_count  # Workers are consumers

        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._metrics = EventBusMetrics()
        self._start_time: float = 0
        self._lock = threading.Lock()

        # Per-event-type counters for detailed metrics
        self._event_type_counters: Dict[str, Dict[str, int]] = {}

        # OTEL integration
        self._telemetry: Optional[TelemetryManager] = None
        self._otel_metrics_registered = False
        self._last_metrics_export = 0.0

        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
                self._register_otel_metrics()
            except Exception as e:
                logger.warning("Failed to initialize OTEL telemetry: %s", e)

        # Log buffer configuration
        buffer_names = [b.__name__ for b in self._available_buffers]
        logger.info(
            "EventBus initialized: buffer_size=%d, batch_size=%d, workers=%d, "
            "tracing=%s, available_buffers=%s",
            buffer_size, batch_size, worker_count, trace_events, buffer_names
        )

    def _register_otel_metrics(self) -> None:
        """Register OTEL metrics for the event bus."""
        if not self._telemetry or not self._telemetry.enabled or self._otel_metrics_registered:
            return

        try:
            # Register observable gauges
            self._telemetry.gauge(
                "eventbus.queue_size",
                lambda: sum(len(b) for b in self._buffers.values()),
                "Total events in all queues"
            )
            self._telemetry.gauge(
                "eventbus.handler_count",
                lambda: sum(len(h) for h in self._handlers.values()) +
                        sum(len(h) for h in self._sync_handlers.values()),
                "Total registered handlers"
            )
            # Per-event-type queue depth gauges
            for event_type in self._event_types:
                self._register_event_type_gauge(event_type)

            self._otel_metrics_registered = True
            logger.debug("OTEL metrics registered for EventBus")
        except Exception as e:
            logger.warning("Failed to register OTEL metrics: %s", e)

    def _register_event_type_gauge(self, event_type: str) -> None:
        """Register gauge for a specific event type queue depth."""
        if not self._telemetry or not self._telemetry.enabled:
            return
        try:
            # Create closure for event_type
            et = event_type
            self._telemetry.gauge(
                f"eventbus.queue.{et}.depth",
                lambda et=et: len(self._buffers.get(et, [])),
                f"Queue depth for {et} events"
            )
        except Exception:
            pass  # Ignore registration errors for individual event types

    def _init_event_type_counters(self, event_type: str) -> None:
        """Initialize per-event-type counters."""
        if event_type not in self._event_type_counters:
            self._event_type_counters[event_type] = {
                "published": 0,
                "processed": 0,
                "dropped": 0,
            }

    def subscribe(self, handler: Union[EventHandler, SyncEventHandler]) -> None:
        """
        Subscribe a handler to its declared event types.

        Supports both async EventHandler and sync SyncEventHandler.
        """
        event_types = handler.event_types
        handler_name = handler.__class__.__name__

        for event_type in event_types:
            self._ensure_event_type(event_type)

            # Check if handler has sync method
            if hasattr(handler, 'handle_sync'):
                if event_type not in self._sync_handlers:
                    self._sync_handlers[event_type] = []
                self._sync_handlers[event_type].append(handler)
                logger.debug("Sync handler subscribed: %s -> %s", handler_name, event_type)
            else:
                if event_type not in self._handlers:
                    self._handlers[event_type] = []
                self._handlers[event_type].append(handler)
                logger.debug("Async handler subscribed: %s -> %s", handler_name, event_type)

    def subscribe_to_all_without_removal(self, handler: Union[EventHandler, SyncEventHandler]) -> None:
        """
        Subscribe a handler that receives events without immediate removal.

        Events subscribed through this method will only be removed from the buffer
        after ALL handlers (both regular and no-removal) have processed them.
        This is controlled by the event's delete_event_after_all_subscribers_handled flag.

        Use this for handlers that need to observe events that other handlers
        also need to process (e.g., logging, monitoring, telemetry).

        Args:
            handler: Handler to subscribe (async or sync)
        """
        event_types = handler.event_types
        handler_name = handler.__class__.__name__

        for event_type in event_types:
            self._ensure_event_type(event_type)

            # Check if handler has sync method
            if hasattr(handler, 'handle_sync'):
                if event_type not in self._no_removal_sync_handlers:
                    self._no_removal_sync_handlers[event_type] = []
                self._no_removal_sync_handlers[event_type].append(handler)
                logger.debug(
                    "No-removal sync handler subscribed: %s -> %s",
                    handler_name, event_type
                )
            else:
                if event_type not in self._no_removal_handlers:
                    self._no_removal_handlers[event_type] = []
                self._no_removal_handlers[event_type].append(handler)
                logger.debug(
                    "No-removal async handler subscribed: %s -> %s",
                    handler_name, event_type
                )

    def unsubscribe_no_removal(self, handler: Union[EventHandler, SyncEventHandler]) -> None:
        """Remove a no-removal handler from all its event types."""
        handler_name = handler.__class__.__name__
        for event_type in handler.event_types:
            if hasattr(handler, 'handle_sync'):
                if event_type in self._no_removal_sync_handlers:
                    self._no_removal_sync_handlers[event_type] = [
                        h for h in self._no_removal_sync_handlers[event_type] if h is not handler
                    ]
            else:
                if event_type in self._no_removal_handlers:
                    self._no_removal_handlers[event_type] = [
                        h for h in self._no_removal_handlers[event_type] if h is not handler
                    ]
        logger.debug("No-removal handler unsubscribed: %s", handler_name)

    def get_total_handler_count(self, event_type: str) -> int:
        """Get total number of handlers (regular + no-removal) for an event type."""
        count = 0
        count += len(self._handlers.get(event_type, []))
        count += len(self._sync_handlers.get(event_type, []))
        count += len(self._no_removal_handlers.get(event_type, []))
        count += len(self._no_removal_sync_handlers.get(event_type, []))
        return count


    def unsubscribe(self, handler: Union[EventHandler, SyncEventHandler]) -> None:
        """Remove a handler from all its event types."""
        handler_name = handler.__class__.__name__
        for event_type in handler.event_types:
            if hasattr(handler, 'handle_sync'):
                if event_type in self._sync_handlers:
                    self._sync_handlers[event_type] = [
                        h for h in self._sync_handlers[event_type] if h is not handler
                    ]
            else:
                if event_type in self._handlers:
                    self._handlers[event_type] = [
                        h for h in self._handlers[event_type] if h is not handler
                    ]
        logger.debug("Handler unsubscribed: %s", handler_name)

    def _ensure_event_type(self, event_type: str) -> None:
        """Ensure buffer exists for event type, selecting appropriate buffer type."""
        if event_type not in self._buffers:
            scenario = self._detect_scenario()
            buffer = get_buffer_for_scenario(
                scenario, self._buffer_size, self._available_buffers
            )
            self._buffers[event_type] = buffer
            self._event_types.add(event_type)
            self._init_event_type_counters(event_type)
            # Register gauge for new event type
            if self._otel_metrics_registered:
                self._register_event_type_gauge(event_type)
            logger.debug(
                "Buffer created for event type: %s (scenario=%s, buffer=%s)",
                event_type, scenario, buffer.__class__.__name__
            )

    def _detect_scenario(self) -> str:
        """
        Detect the producer/consumer scenario based on configuration.

        Returns:
            BufferScenario constant (SPSC, SPMC, MPSC, MPMC)
        """
        multiple_producers = self._producer_count > 1
        multiple_consumers = self._consumer_count > 1

        if multiple_producers and multiple_consumers:
            return BufferScenario.MPMC
        elif multiple_producers:
            return BufferScenario.MPSC
        elif multiple_consumers:
            return BufferScenario.SPMC
        else:
            return BufferScenario.SPSC

    def set_producer_count(self, count: int) -> None:
        """
        Set the expected number of producers (threads publishing events).

        Call this before creating buffers if you have multiple producer threads.
        """
        self._producer_count = max(1, count)
        logger.debug("Producer count set to %d", self._producer_count)

    def set_consumer_count(self, count: int) -> None:
        """
        Set the expected number of consumers (worker threads).

        This is typically the worker_count, but can be adjusted if needed.
        """
        self._consumer_count = max(1, count)
        logger.debug("Consumer count set to %d", self._consumer_count)

    def publish_sync(self, event: Event) -> bool:
        """
        Publish event synchronously (non-blocking, fire-and-forget).

        This is the fastest publish method. Returns False if buffer is full.
        """
        buffer = self._buffers.get(event.event_type)
        if buffer is None:
            # Auto-create buffer for unknown event types
            self._ensure_event_type(event.event_type)
            buffer = self._buffers[event.event_type]

        success = buffer.push(event)
        event_type = event.event_type

        if success:
            self._metrics.events_published += 1
            if len(buffer) > self._metrics.peak_queue_size:
                self._metrics.peak_queue_size = len(buffer)

            # Update per-event-type counter
            if event_type in self._event_type_counters:
                self._event_type_counters[event_type]["published"] += 1

            # Record OTEL counter with event type label
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.counter(
                    "eventbus.events.published",
                    1,
                    {"event_type": event_type}
                )
        else:
            self._metrics.events_dropped += 1

            # Update per-event-type dropped counter
            if event_type in self._event_type_counters:
                self._event_type_counters[event_type]["dropped"] += 1

            if self._telemetry and self._telemetry.enabled:
                self._telemetry.counter(
                    "eventbus.events.dropped",
                    1,
                    {"event_type": event_type}
                )
            logger.warning("Event dropped (buffer full): type=%s", event_type)

        return success

    async def publish(self, event: Event) -> bool:
        """
        Publish event asynchronously with backpressure.

        If buffer is full, yields to allow processing before retrying.
        """
        buffer = self._buffers.get(event.event_type)
        if buffer is None:
            # Auto-create buffer for unknown event types
            self._ensure_event_type(event.event_type)
            buffer = self._buffers[event.event_type]

        # Try to push, yield if full
        retry_count = 0
        while not buffer.push(event):
            retry_count += 1
            if retry_count > 100:
                self._metrics.events_dropped += 1
                return False
            await asyncio.sleep(0)  # Yield to allow processing

        self._metrics.events_published += 1
        if len(buffer) > self._metrics.peak_queue_size:
            self._metrics.peak_queue_size = len(buffer)

        return True

    async def start(self) -> None:
        """Start event processing workers."""
        if self._running:
            return

        self._running = True
        self._start_time = time.perf_counter()
        self._tasks.clear()

        # Create workers for each event type
        for event_type in self._event_types:
            for worker_id in range(self._worker_count):
                task = asyncio.create_task(
                    self._worker_loop(event_type, worker_id),
                    name=f"eventbus_worker_{event_type}_{worker_id}"
                )
                self._tasks.append(task)

        logger.info(f"Event bus started: {len(self._tasks)} workers")

    async def stop(self, drain: bool = True) -> None:
        """
        Stop event processing.

        Args:
            drain: If True, process remaining events before stopping
        """
        if not self._running:
            return

        if drain:
            # Wait for buffers to drain (with timeout)
            timeout = 5.0
            start = time.perf_counter()
            while time.perf_counter() - start < timeout:
                all_empty = all(buf.is_empty for buf in self._buffers.values())
                if all_empty:
                    break
                await asyncio.sleep(0.01)

        self._running = False

        # Cancel all worker tasks
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()
        logger.info("Event bus stopped")

    async def _worker_loop(self, event_type: str, worker_id: int) -> None:
        """Worker coroutine that processes events in batches with OTEL tracing."""
        buffer = self._buffers[event_type]
        async_handlers = self._handlers.get(event_type, [])
        sync_handlers = self._sync_handlers.get(event_type, [])
        no_removal_async = self._no_removal_handlers.get(event_type, [])
        no_removal_sync = self._no_removal_sync_handlers.get(event_type, [])

        logger.debug("Worker %d started for event type: %s", worker_id, event_type)

        while self._running:
            try:
                # Get batch of events
                events = buffer.pop_batch(self._batch_size)

                if not events:
                    # No events, yield and retry
                    await asyncio.sleep(0.0001)  # 100μs sleep
                    continue

                # Filter out expired events (TTL check)
                current_time = time.time()
                valid_events = []
                expired_count = 0

                for event in events:
                    if self._is_event_expired(event, current_time):
                        expired_count += 1
                        logger.debug(
                            "Event expired: type=%s, age=%.2fs, ttl=%d",
                            event.event_type,
                            current_time - event.timestamp,
                            event.lifetime_seconds
                        )
                    else:
                        valid_events.append(event)

                if expired_count > 0:
                    self._metrics.events_dropped += expired_count
                    if self._telemetry and self._telemetry.enabled:
                        self._telemetry.counter(
                            "eventbus.events.expired",
                            expired_count,
                            {"event_type": event_type}
                        )

                if not valid_events:
                    continue

                # Process batch with optional OTEL span
                start_ns = time.perf_counter_ns()

                # Create batch span if tracing is enabled
                batch_span = None
                all_handlers_count = (
                    len(sync_handlers) + len(async_handlers) +
                    len(no_removal_sync) + len(no_removal_async)
                )
                if self._trace_events and self._telemetry and self._telemetry.enabled:
                    batch_span = self._telemetry.start_span(
                        f"eventbus.process_batch.{event_type}",
                        kind="consumer",
                        attributes={
                            "event_type": event_type,
                            "batch_size": len(valid_events),
                            "worker_id": worker_id,
                            "sync_handlers": len(sync_handlers) + len(no_removal_sync),
                            "async_handlers": len(async_handlers) + len(no_removal_async),
                        }
                    )

                try:
                    # Process each event
                    for event in valid_events:
                        await self._process_single_event(
                            event, event_type, worker_id,
                            sync_handlers, async_handlers,
                            no_removal_sync, no_removal_async
                        )
                finally:
                    if batch_span:
                        batch_span.end()

                # Update metrics
                elapsed_ns = time.perf_counter_ns() - start_ns
                batch_size = len(valid_events)
                elapsed_ms = elapsed_ns / 1_000_000  # Convert to milliseconds

                self._metrics.events_processed += batch_size
                self._metrics.batches_processed += 1
                self._metrics.total_processing_time_ns += elapsed_ns

                # Update per-event-type counter
                if event_type in self._event_type_counters:
                    self._event_type_counters[event_type]["processed"] += batch_size

                if batch_size > 0:
                    self._metrics.record_latency(elapsed_ns / batch_size)

                    # Export OTEL metrics with per-event-type granularity
                    if self._telemetry and self._telemetry.enabled:
                        self._telemetry.counter(
                            "eventbus.events.processed",
                            batch_size,
                            {"event_type": event_type}
                        )
                        self._telemetry.histogram(
                            "eventbus.batch.latency_ms",
                            elapsed_ms,
                            {"event_type": event_type}
                        )
                        # Per-event latency
                        per_event_latency_ms = elapsed_ms / batch_size
                        self._telemetry.histogram(
                            "eventbus.event.latency_ms",
                            per_event_latency_ms,
                            {"event_type": event_type}
                        )

            except asyncio.CancelledError:
                logger.debug("Worker %d cancelled for event type: %s", worker_id, event_type)
                break
            except Exception as e:
                logger.error("Worker error: worker=%d event_type=%s error=%s", worker_id, event_type, e)
                await asyncio.sleep(0.001)

    def _is_event_expired(self, event: Event, current_time: float) -> bool:
        """Check if an event has expired based on its lifetime_seconds."""
        if event.lifetime_seconds <= 0:
            return False  # 0 or negative = infinite lifetime
        age = current_time - event.timestamp
        return age > event.lifetime_seconds

    async def _process_single_event(
        self,
        event: Event,
        event_type: str,
        worker_id: int,
        sync_handlers: List[SyncEventHandler],
        async_handlers: List[EventHandler],
        no_removal_sync: List[SyncEventHandler],
        no_removal_async: List[EventHandler],
    ) -> None:
        """Process a single event through all handlers."""
        # Create per-event span if tracing
        event_span = None
        if self._trace_events and self._telemetry and self._telemetry.enabled:
            event_span = self._telemetry.start_span(
                f"eventbus.event.{event_type}",
                kind="producer",
                attributes={
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id or "",
                    "timestamp": event.timestamp,
                    "lifetime_seconds": event.lifetime_seconds,
                    "delete_after_handled": event.delete_event_after_all_subscribers_handled,
                },
                service_name="SAlly.EventBus",
            )

        try:
            # Process regular sync handlers
            for handler in sync_handlers:
                handler_name = handler.__class__.__name__
                try:
                    handler.handle_sync(event)
                except Exception as e:
                    logger.error(
                        "Sync handler error: handler=%s event=%s error=%s",
                        handler_name, event_type, e
                    )
                    if event_span:
                        event_span.record_exception(e)

            # Process no-removal sync handlers
            for handler in no_removal_sync:
                handler_name = handler.__class__.__name__
                try:
                    handler.handle_sync(event)
                except Exception as e:
                    logger.error(
                        "No-removal sync handler error: handler=%s event=%s error=%s",
                        handler_name, event_type, e
                    )
                    if event_span:
                        event_span.record_exception(e)

            # Process regular async handlers
            if async_handlers:
                tasks = [h.handle(event) for h in async_handlers]
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            handler_name = async_handlers[i].__class__.__name__
                            logger.error(
                                "Async handler error: handler=%s event=%s error=%s",
                                handler_name, event_type, result
                            )
                            if event_span:
                                event_span.record_exception(result)

            # Process no-removal async handlers
            if no_removal_async:
                tasks = [h.handle(event) for h in no_removal_async]
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            handler_name = no_removal_async[i].__class__.__name__
                            logger.error(
                                "No-removal async handler error: handler=%s event=%s error=%s",
                                handler_name, event_type, result
                            )
                            if event_span:
                                event_span.record_exception(result)

        finally:
            if event_span:
                event_span.end()

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        elapsed = time.perf_counter() - self._start_time if self._start_time else 0

        metrics = self._metrics.to_dict()
        metrics['elapsed_seconds'] = elapsed
        metrics['throughput_eps'] = self._metrics.get_throughput(elapsed)
        metrics['queue_sizes'] = {
            et: len(buf) for et, buf in self._buffers.items()
        }
        metrics['buffer_scenarios'] = {
            et: buf.scenario for et, buf in self._buffers.items()
        }
        metrics['handler_count'] = sum(
            len(h) for h in self._handlers.values()
        ) + sum(
            len(h) for h in self._sync_handlers.values()
        )
        metrics['no_removal_handler_count'] = sum(
            len(h) for h in self._no_removal_handlers.values()
        ) + sum(
            len(h) for h in self._no_removal_sync_handlers.values()
        )
        metrics['total_handler_count'] = metrics['handler_count'] + metrics['no_removal_handler_count']
        metrics['producer_count'] = self._producer_count
        metrics['consumer_count'] = self._consumer_count

        # Export metrics to OTEL if enabled
        if self._telemetry and self._telemetry.enabled:
            now = time.time()
            if now - self._last_metrics_export > 5.0:  # Export every 5 seconds
                self._telemetry.histogram("eventbus.throughput_eps", metrics['throughput_eps'])
                self._telemetry.histogram("eventbus.avg_latency_us", metrics['avg_latency_us'])
                self._last_metrics_export = now

        return metrics

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics = EventBusMetrics()
        self._start_time = time.perf_counter()
        logger.info("EventBus metrics reset")


# =============================================================================
# Legacy Compatibility - Abstract EventHandler base class
# =============================================================================

class AbstractEventHandler(ABC):
    """
    Abstract base class for event handlers.

    Provides backward compatibility with the original EventHandler interface.
    """

    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle an event asynchronously."""
        pass

    @property
    @abstractmethod
    def event_types(self) -> List[str]:
        """Return list of event types this handler subscribes to."""
        pass


# Alias for backward compatibility
BaseEventHandler = AbstractEventHandler

"""
Event Bus Buffer Benchmark Tests

Performance benchmarks for all buffer types to compare their throughput
in different producer/consumer scenarios:
- RingBuffer (SPSC): Lock-free, highest performance
- SPMCBuffer: Lock on pop for consumer thread-safety
- MPSCBuffer: Lock on push for producer thread-safety
- MPMCBuffer: Fully locked for maximum safety

Each benchmark tests:
1. Single-threaded push/pop performance
2. Multi-threaded producer scenarios
3. Multi-threaded consumer scenarios
4. Full MPMC scenarios
5. Visualization Generation (matplotlib)
"""

import threading
import time
import unittest
import os
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Type

import pytest

# Optional imports for plotting
try:
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from tests.diag.metrics import record_metric


pytestmark = pytest.mark.benchmark

from sally.core.event_bus import (
    Event,
    EventBus,
    EventBusBuffer,
    RingBuffer,
    SPMCBuffer,
    MPSCBuffer,
    MPMCBuffer,
    BufferScenario,
)


# =============================================================================
# Buffer Benchmark Utilities
# =============================================================================

def benchmark_single_thread_push(buffer_class: Type[EventBusBuffer], num_ops: int) -> float:
    """Benchmark single-threaded push operations."""
    buffer = buffer_class(capacity=num_ops * 2)
    events = [Event(event_type="bench") for _ in range(num_ops)]

    start = time.perf_counter()
    for event in events:
        buffer.push(event)
    elapsed = time.perf_counter() - start

    return num_ops / elapsed


def benchmark_single_thread_pop(buffer_class: Type[EventBusBuffer], num_ops: int) -> float:
    """Benchmark single-threaded pop operations."""
    buffer = buffer_class(capacity=num_ops * 2)
    for _ in range(num_ops):
        buffer.push(Event(event_type="bench"))

    start = time.perf_counter()
    while not buffer.is_empty:
        buffer.pop()
    elapsed = time.perf_counter() - start

    return num_ops / elapsed


def benchmark_batch_pop(buffer_class: Type[EventBusBuffer], num_ops: int, batch_size: int) -> float:
    """Benchmark batch pop operations."""
    buffer = buffer_class(capacity=num_ops * 2)
    for _ in range(num_ops):
        buffer.push(Event(event_type="bench"))

    start = time.perf_counter()
    while not buffer.is_empty:
        buffer.pop_batch(batch_size)
    elapsed = time.perf_counter() - start

    return num_ops / elapsed


def benchmark_multi_producer(
    buffer_class: Type[EventBusBuffer],
    num_producers: int,
    events_per_producer: int
) -> float:
    """Benchmark multiple producers pushing to a single buffer."""
    buffer = buffer_class(capacity=num_producers * events_per_producer * 2)
    total_events = num_producers * events_per_producer

    def producer():
        for _ in range(events_per_producer):
            while not buffer.push(Event(event_type="bench")):
                pass  # Retry if full

    start = time.perf_counter()
    threads = [threading.Thread(target=producer) for _ in range(num_producers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start

    return total_events / elapsed


def benchmark_multi_consumer(
    buffer_class: Type[EventBusBuffer],
    num_consumers: int,
    total_events: int
) -> float:
    """Benchmark multiple consumers popping from a single buffer."""
    buffer = buffer_class(capacity=total_events * 2)

    # Pre-fill buffer
    for _ in range(total_events):
        buffer.push(Event(event_type="bench"))

    consumed = [0]
    lock = threading.Lock()
    done_event = threading.Event()

    def consumer():
        local_count = 0
        while not done_event.is_set():
            event = buffer.pop()
            if event is not None:
                local_count += 1
            elif buffer.is_empty:
                break
        with lock:
            consumed[0] += local_count

    start = time.perf_counter()
    threads = [threading.Thread(target=consumer) for _ in range(num_consumers)]
    for t in threads:
        t.start()

    # Wait for all events to be consumed
    while consumed[0] < total_events and not buffer.is_empty:
        time.sleep(0.001)
    done_event.set()

    for t in threads:
        t.join(timeout=5)
    elapsed = time.perf_counter() - start

    return consumed[0] / elapsed


def benchmark_mpmc(
    buffer_class: Type[EventBusBuffer],
    num_producers: int,
    num_consumers: int,
    events_per_producer: int
) -> float:
    """Benchmark full MPMC scenario."""
    total_events = num_producers * events_per_producer
    buffer = buffer_class(capacity=total_events * 2)

    consumed = [0]
    consumed_lock = threading.Lock()
    producers_done = threading.Event()

    def producer():
        for _ in range(events_per_producer):
            while not buffer.push(Event(event_type="bench")):
                time.sleep(0.00001)

    def consumer():
        local_count = 0
        while True:
            event = buffer.pop()
            if event is not None:
                local_count += 1
            elif producers_done.is_set() and buffer.is_empty:
                break
            else:
                time.sleep(0.00001)
        with consumed_lock:
            consumed[0] += local_count

    start = time.perf_counter()

    producer_threads = [threading.Thread(target=producer) for _ in range(num_producers)]
    consumer_threads = [threading.Thread(target=consumer) for _ in range(num_consumers)]

    for t in consumer_threads:
        t.start()
    for t in producer_threads:
        t.start()

    for t in producer_threads:
        t.join(timeout=30)
    producers_done.set()

    for t in consumer_threads:
        t.join(timeout=30)

    elapsed = time.perf_counter() - start

    return consumed[0] / elapsed


# =============================================================================
# Benchmark Tests
# =============================================================================

class TestBufferBenchmarks(unittest.TestCase):
    """Performance benchmarks for all buffer types."""

    NUM_OPS = 500_000
    BATCH_SIZE = 256

    def test_single_thread_push_all_buffers(self):
        """Benchmark single-threaded push for all buffer types."""
        print("\n" + "=" * 70)
        print("BENCHMARK: Single-Threaded Push Performance")
        print("=" * 70)

        buffers = [RingBuffer, SPMCBuffer, MPSCBuffer, MPMCBuffer]
        results = {}

        for buf_class in buffers:
            rate = benchmark_single_thread_push(buf_class, self.NUM_OPS)
            results[buf_class.__name__] = rate
            print(f"  {buf_class.__name__:15s}: {rate:>12,.0f} ops/sec")

            record_metric(f"push_ops_per_s_{buf_class.__name__}", rate, "ops/s")

        strict = os.environ.get("SALLY_STRICT_BENCHMARKS", "").strip().lower() in {"1", "true", "yes"}
        if strict:
            # RingBuffer should be fastest (no locks)
            self.assertGreater(results["RingBuffer"], 500_000)
        else:
            self.assertGreater(results["RingBuffer"], 1_000)

        # Print relative performance
        print("\nRelative to RingBuffer:")
        ring_rate = results["RingBuffer"]
        for name, rate in results.items():
            pct = (rate / ring_rate) * 100
            print(f"  {name:15s}: {pct:>6.1f}%")

    def test_single_thread_pop_all_buffers(self):
        """Benchmark single-threaded pop for all buffer types."""
        print("\n" + "=" * 70)
        print("BENCHMARK: Single-Threaded Pop Performance")
        print("=" * 70)

        buffers = [RingBuffer, SPMCBuffer, MPSCBuffer, MPMCBuffer]
        results = {}

        for buf_class in buffers:
            rate = benchmark_single_thread_pop(buf_class, self.NUM_OPS)
            results[buf_class.__name__] = rate
            print(f"  {buf_class.__name__:15s}: {rate:>12,.0f} ops/sec")

            record_metric(f"pop_ops_per_s_{buf_class.__name__}", rate, "ops/s")

        strict = os.environ.get("SALLY_STRICT_BENCHMARKS", "").strip().lower() in {"1", "true", "yes"}
        if strict:
            self.assertGreater(results["RingBuffer"], 500_000)
        else:
            self.assertGreater(results["RingBuffer"], 1_000)

    def test_batch_pop_all_buffers(self):
        """Benchmark batch pop for all buffer types."""
        print("\n" + "=" * 70)
        print(f"BENCHMARK: Batch Pop Performance (batch_size={self.BATCH_SIZE})")
        print("=" * 70)

        buffers = [RingBuffer, SPMCBuffer, MPSCBuffer, MPMCBuffer]
        results = {}

        for buf_class in buffers:
            rate = benchmark_batch_pop(buf_class, self.NUM_OPS, self.BATCH_SIZE)
            results[buf_class.__name__] = rate
            print(f"  {buf_class.__name__:15s}: {rate:>12,.0f} ops/sec")

            record_metric(f"batch_pop_ops_per_s_{buf_class.__name__}", rate, "ops/s")

        # Batch should be faster than individual ops
        individual_rate = benchmark_single_thread_pop(RingBuffer, 100_000)
        batch_rate = benchmark_batch_pop(RingBuffer, 100_000, self.BATCH_SIZE)
        print(f"\nRingBuffer speedup from batching: {batch_rate/individual_rate:.2f}x")


class TestMultiProducerBenchmarks(unittest.TestCase):
    """Benchmarks for multi-producer scenarios."""

    def test_multi_producer_mpsc_vs_mpmc(self):
        """Compare MPSC and MPMC buffers for multi-producer workload."""
        print("\n" + "=" * 70)
        print("BENCHMARK: Multi-Producer Performance (4 producers)")
        print("=" * 70)

        num_producers = 4
        events_per_producer = 50_000

        # MPSC should be faster than MPMC for this scenario
        mpsc_rate = benchmark_multi_producer(MPSCBuffer, num_producers, events_per_producer)
        mpmc_rate = benchmark_multi_producer(MPMCBuffer, num_producers, events_per_producer)

        print(f"  MPSCBuffer: {mpsc_rate:>12,.0f} ops/sec")
        print(f"  MPMCBuffer: {mpmc_rate:>12,.0f} ops/sec")
        print(f"  MPSC advantage: {(mpsc_rate/mpmc_rate - 1)*100:.1f}%")

        record_metric("multi_producer_ops_per_s_mpsc", mpsc_rate, "ops/s")
        record_metric("multi_producer_ops_per_s_mpmc", mpmc_rate, "ops/s")

        strict = os.environ.get("SALLY_STRICT_BENCHMARKS", "").strip().lower() in {"1", "true", "yes"}
        if strict:
            self.assertGreater(mpsc_rate, 10_000)
            self.assertGreater(mpmc_rate, 10_000)
        else:
            self.assertGreater(mpsc_rate, 100)
            self.assertGreater(mpmc_rate, 100)

    def test_multi_producer_scaling(self):
        """Test how multi-producer performance scales with producer count."""
        print("\n" + "=" * 70)
        print("BENCHMARK: Multi-Producer Scaling (MPMCBuffer)")
        print("=" * 70)

        total_events = 200_000
        producer_counts = [1, 2, 4, 8]

        for num_producers in producer_counts:
            events_per = total_events // num_producers
            rate = benchmark_multi_producer(MPMCBuffer, num_producers, events_per)
            print(f"  {num_producers} producers: {rate:>12,.0f} ops/sec")


class TestMultiConsumerBenchmarks(unittest.TestCase):
    """Benchmarks for multi-consumer scenarios."""

    def test_multi_consumer_spmc_vs_mpmc(self):
        """Compare SPMC and MPMC buffers for multi-consumer workload."""
        print("\n" + "=" * 70)
        print("BENCHMARK: Multi-Consumer Performance (4 consumers)")
        print("=" * 70)

        num_consumers = 4
        total_events = 200_000

        spmc_rate = benchmark_multi_consumer(SPMCBuffer, num_consumers, total_events)
        mpmc_rate = benchmark_multi_consumer(MPMCBuffer, num_consumers, total_events)

        print(f"  SPMCBuffer: {spmc_rate:>12,.0f} ops/sec")
        print(f"  MPMCBuffer: {mpmc_rate:>12,.0f} ops/sec")

        record_metric("multi_consumer_ops_per_s_spmc", spmc_rate, "ops/s")
        record_metric("multi_consumer_ops_per_s_mpmc", mpmc_rate, "ops/s")

        strict = os.environ.get("SALLY_STRICT_BENCHMARKS", "").strip().lower() in {"1", "true", "yes"}
        if strict:
            self.assertGreater(spmc_rate, 10_000)
            self.assertGreater(mpmc_rate, 10_000)
        else:
            self.assertGreater(spmc_rate, 100)
            self.assertGreater(mpmc_rate, 100)


class TestMPMCBenchmarks(unittest.TestCase):
    """Benchmarks for full MPMC scenarios."""

    def test_mpmc_scenario(self):
        """Benchmark full MPMC with multiple producers and consumers."""
        print("\n" + "=" * 70)
        print("BENCHMARK: Full MPMC Scenario")
        print("=" * 70)

        configs = [
            (2, 2, 50_000),   # 2P/2C
            (4, 4, 25_000),   # 4P/4C
            (4, 2, 50_000),   # 4P/2C (producer-heavy)
            (2, 4, 50_000),   # 2P/4C (consumer-heavy)
        ]

        for num_producers, num_consumers, events_per in configs:
            rate = benchmark_mpmc(MPMCBuffer, num_producers, num_consumers, events_per)
            print(f"  {num_producers}P/{num_consumers}C: {rate:>12,.0f} ops/sec")

            record_metric("mpmc_ops_per_s", rate, "ops/s")

            strict = os.environ.get("SALLY_STRICT_BENCHMARKS", "").strip().lower() in {"1", "true", "yes"}
            if strict:
                self.assertGreater(rate, 1_000)  # Minimum threshold
            else:
                self.assertGreater(rate, 10)


class TestEventBusBufferSelection(unittest.TestCase):
    """Benchmark EventBus with different buffer configurations."""

    def test_eventbus_with_different_buffers(self):
        """Compare EventBus performance with different buffer types."""
        print("\n" + "=" * 70)
        print("BENCHMARK: EventBus with Different Buffer Configurations")
        print("=" * 70)

        num_events = 100_000
        buffer_configs = [
            ("SPSC (RingBuffer)", [RingBuffer]),
            ("MPMC Only", [MPMCBuffer]),
            ("All Buffers", [RingBuffer, SPMCBuffer, MPSCBuffer, MPMCBuffer]),
        ]

        for name, buffers in buffer_configs:
            bus = EventBus(
                buffer_size=num_events * 2,
                batch_size=256,
                worker_count=1,
                available_buffers=buffers
            )

            # Pre-create buffer
            bus._ensure_event_type("bench")

            events = [Event(event_type="bench") for _ in range(num_events)]

            start = time.perf_counter()
            for event in events:
                bus.publish_sync(event)
            elapsed = time.perf_counter() - start

            rate = num_events / elapsed
            buffer_type = bus._buffers["bench"].__class__.__name__
            print(f"  {name:25s} ({buffer_type:12s}): {rate:>12,.0f} ops/sec")

            record_metric("eventbus_publish_ops_per_s", rate, "ops/s")


class TestBufferOverheadComparison(unittest.TestCase):
    """Compare lock overhead between buffer types."""

    def test_lock_overhead_comparison(self):
        """Measure overhead of locking vs lock-free buffers."""
        print("\n" + "=" * 70)
        print("BENCHMARK: Lock Overhead Analysis")
        print("=" * 70)

        num_ops = 1_000_000

        # RingBuffer (no locks)
        ring_push = benchmark_single_thread_push(RingBuffer, num_ops)
        ring_pop = benchmark_single_thread_pop(RingBuffer, num_ops)

        # MPMCBuffer (full locking)
        mpmc_push = benchmark_single_thread_push(MPMCBuffer, num_ops)
        mpmc_pop = benchmark_single_thread_pop(MPMCBuffer, num_ops)

        print(f"  RingBuffer (lock-free):")
        print(f"    Push: {ring_push:>12,.0f} ops/sec")
        print(f"    Pop:  {ring_pop:>12,.0f} ops/sec")

        print(f"  MPMCBuffer (locked):")
        print(f"    Push: {mpmc_push:>12,.0f} ops/sec")
        print(f"    Pop:  {mpmc_pop:>12,.0f} ops/sec")

        push_overhead = (1 - mpmc_push/ring_push) * 100
        pop_overhead = (1 - mpmc_pop/ring_pop) * 100

        print(f"\n  Lock overhead:")
        print(f"    Push: {push_overhead:.1f}% slower")
        print(f"    Pop:  {pop_overhead:.1f}% slower")

        record_metric("push_ops_per_s_ring", ring_push, "ops/s")
        record_metric("push_ops_per_s_mpmc", mpmc_push, "ops/s")
        record_metric("push_lock_overhead_pct", push_overhead, "%")


# =============================================================================
# Summary Report and Visualizations
# =============================================================================

class TestBenchmarkSummary(unittest.TestCase):
    """Generate a summary report of all benchmarks and plot graphs."""

    def test_generate_summary(self):
        """Generate benchmark summary report."""
        print("\n")
        print("=" * 70)
        print(" BUFFER PERFORMANCE SUMMARY ")
        print("=" * 70)
        print()
        print("Buffer Selection Guidelines:")
        print("-" * 70)
        print("| Scenario | Producers | Consumers | Recommended Buffer |")
        print("|----------|-----------|-----------|-------------------|")
        print("| SPSC     | 1         | 1         | RingBuffer        |")
        print("| SPMC     | 1         | Multiple  | SPMCBuffer        |")
        print("| MPSC     | Multiple  | 1         | MPSCBuffer        |")
        print("| MPMC     | Multiple  | Multiple  | MPMCBuffer        |")
        print("-" * 70)
        print()
        print("Performance Characteristics:")
        print("-" * 70)
        print("| Buffer      | Thread-Safe Push | Thread-Safe Pop | Locks |")
        print("|-------------|------------------|-----------------|-------|")
        print("| RingBuffer  | No               | No              | None  |")
        print("| SPMCBuffer  | No               | Yes             | Pop   |")
        print("| MPSCBuffer  | Yes              | No              | Push  |")
        print("| MPMCBuffer  | Yes              | Yes             | Both  |")
        print("-" * 70)
        print()

        # Quick single-thread benchmark for summary
        num_ops = 100_000
        buffers = [RingBuffer, SPMCBuffer, MPSCBuffer, MPMCBuffer]

        print("Single-Thread Performance (100K ops):")
        print("-" * 70)
        print("| Buffer      |    Push (ops/s) |     Pop (ops/s) |")
        print("|-------------|-----------------|-----------------|")

        for buf_class in buffers:
            push_rate = benchmark_single_thread_push(buf_class, num_ops)
            pop_rate = benchmark_single_thread_pop(buf_class, num_ops)
            print(f"| {buf_class.__name__:11s} | {push_rate:>15,.0f} | {pop_rate:>15,.0f} |")

        print("-" * 70)
        print()

    def test_generate_visualizations(self):
        """Run actual benchmarks and generate matplotlib graphs if installed."""
        if not HAS_MATPLOTLIB:
            print("\nmatplotlib or numpy not installed. Skipping visualization generation.")
            return

        print("\n" + "=" * 70)
        print(" GENERATING PERFORMANCE VISUALIZATIONS ")
        print("=" * 70)

        # Base properties
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()

        buffers = [RingBuffer, SPMCBuffer, MPSCBuffer, MPMCBuffer]
        buffer_names = [b.__name__ for b in buffers]
        num_ops_single = 500_000

        # Run benchmarks to gather real-time data for graphs
        push_rates = [benchmark_single_thread_push(b, num_ops_single) for b in buffers]
        pop_rates = [benchmark_single_thread_pop(b, num_ops_single) for b in buffers]

        # ---------------------------------------------------------------------
        # Plot 1: Single-Thread Push/Pop Comparison
        # ---------------------------------------------------------------------
        x = np.arange(len(buffer_names))
        width = 0.35

        fig1, ax1 = plt.subplots(figsize=(10, 6))
        ax1.bar(x - width/2, push_rates, width, label='Push', color='skyblue', edgecolor='black', alpha=0.85)
        ax1.bar(x + width/2, pop_rates, width, label='Pop', color='lightcoral', edgecolor='black', alpha=0.85)

        ax1.set_xlabel('Buffer Type', fontweight='bold')
        ax1.set_ylabel('Operations per Second', fontweight='bold')
        ax1.set_title(f'Single-Thread Push/Pop Performance ({num_ops_single:,} ops)', fontsize=14, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(buffer_names)
        ax1.legend()
        ax1.grid(True, axis='y', linestyle='--', alpha=0.7)

        # Values on top of bars
        for i in range(len(buffer_names)):
            ax1.text(i - width/2, push_rates[i] + (max(push_rates)*0.01), f'{int(push_rates[i]):,}', ha='center', va='bottom', fontsize=9)
            ax1.text(i + width/2, pop_rates[i] + (max(pop_rates)*0.01), f'{int(pop_rates[i]):,}', ha='center', va='bottom', fontsize=9)

        plt.tight_layout()
        filename1 = os.path.join(out_dir, f'{timestamp}_buffer_push_pop_comparison.png')
        plt.savefig(filename1, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Saved: {filename1}")

        # ---------------------------------------------------------------------
        # Plot 2: Multi-Producer Scaling
        # ---------------------------------------------------------------------
        total_events = 200_000
        producers = [1, 2, 4, 8]
        scaling_rates = [benchmark_multi_producer(MPMCBuffer, p, total_events // p) for p in producers]

        fig2, ax2 = plt.subplots(figsize=(8, 5))
        ax2.plot(producers, scaling_rates, marker='o', linewidth=2.5, markersize=8, color='darkgreen')

        ax2.set_xlabel('Number of Producers', fontweight='bold')
        ax2.set_ylabel('Operations per Second', fontweight='bold')
        ax2.set_title(f'MPMCBuffer Multi-Producer Scaling ({total_events:,} total events)', fontsize=13, fontweight='bold')
        ax2.grid(True, linestyle='--', alpha=0.7)
        ax2.set_xticks(producers)

        for i, rate in enumerate(scaling_rates):
            ax2.annotate(f'{int(rate):,}', (producers[i], rate), textcoords="offset points", xytext=(0,10), ha='center', fontsize=10)

        plt.tight_layout()
        filename2 = os.path.join(out_dir, f'{timestamp}_mpmc_scaling.png')
        plt.savefig(filename2, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Saved: {filename2}")

        # ---------------------------------------------------------------------
        # Plot 3: Lock Overhead Analysis
        # ---------------------------------------------------------------------
        categories = ['Push', 'Pop']
        lock_free = [push_rates[0], pop_rates[0]]  # RingBuffer
        locked = [push_rates[3], pop_rates[3]]     # MPMCBuffer

        x_ov = np.arange(len(categories))
        width_ov = 0.35

        fig3, ax3 = plt.subplots(figsize=(8, 6))
        ax3.bar(x_ov - width_ov/2, lock_free, width_ov, label='Lock-Free (RingBuffer)', color='mediumseagreen', edgecolor='black', alpha=0.85)
        ax3.bar(x_ov + width_ov/2, locked, width_ov, label='Fully Locked (MPMCBuffer)', color='indianred', edgecolor='black', alpha=0.85)

        ax3.set_xlabel('Operation Type', fontweight='bold')
        ax3.set_ylabel('Operations per Second', fontweight='bold')
        ax3.set_title(f'Lock Overhead Analysis ({num_ops_single:,} operations)', fontsize=14, fontweight='bold')
        ax3.set_xticks(x_ov)
        ax3.set_xticklabels(categories)
        ax3.legend()
        ax3.grid(True, axis='y', linestyle='--', alpha=0.7)

        for i in range(len(categories)):
            ax3.text(i - width_ov/2, lock_free[i] + (max(lock_free)*0.01), f'{int(lock_free[i]):,}', ha='center', va='bottom', fontsize=10)
            ax3.text(i + width_ov/2, locked[i] + (max(locked)*0.01), f'{int(locked[i]):,}', ha='center', va='bottom', fontsize=10)

        plt.tight_layout()
        filename3 = os.path.join(out_dir, f'{timestamp}_lock_overhead.png')
        plt.savefig(filename3, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Saved: {filename3}")
        print("\nAll visualizations generated successfully.")


if __name__ == '__main__':
    unittest.main(verbosity=2)

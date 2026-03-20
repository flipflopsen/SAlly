#!/usr/bin/env python
"""
Load test script for Sally OpenTelemetry integration.

This script generates a high volume of events, traces, and metrics
to validate that the observability stack can handle production loads.

Run with: python scripts/load_test_telemetry.py [--events N] [--duration S]
"""

import argparse
import os
import sys
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


@dataclass
class LoadTestConfig:
    """Configuration for load test."""
    events_per_second: int = 1000
    duration_seconds: int = 30
    num_workers: int = 4
    event_types: List[str] = None

    def __post_init__(self):
        if self.event_types is None:
            self.event_types = [
                "GridMeasurementEvent",
                "VoltageReadingEvent",
                "PowerFlowEvent",
                "TransformerStateEvent",
                "RuleTriggeredEvent",
                "SetpointAppliedEvent",
                "SimulationStepEvent",
                "CommandReceivedEvent",
            ]


@dataclass
class LoadTestStats:
    """Statistics for load test."""
    events_generated: int = 0
    spans_created: int = 0
    metrics_recorded: int = 0
    errors: int = 0
    start_time: float = 0
    end_time: float = 0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0

    @property
    def events_per_second(self) -> float:
        return self.events_generated / self.duration if self.duration else 0


class LoadTestRunner:
    """Runner for telemetry load tests."""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.stats = LoadTestStats()
        self._running = False
        self._lock = threading.Lock()
        self._telemetry = None

    def _init_telemetry(self):
        """Initialize telemetry for load testing."""
        from sally.core.service_telemetry import ServiceNames, init_service_telemetry
        from sally.core.telemetry import TelemetryConfig

        config = TelemetryConfig(
            enabled=True,
            service_name="SAlly.LoadTest",
            otlp_endpoint=os.getenv("SALLY_OTEL_ENDPOINT", "http://localhost:4317"),
            export_mode="otlp",
        )

        self._telemetry = init_service_telemetry("SAlly.LoadTest", config)
        return self._telemetry

    def _generate_event_batch(self, batch_id: int, batch_size: int):
        """Generate a batch of events."""
        from sally.core.metrics_helpers import (
            record_event_published,
            record_event_processed,
            record_event_latency,
            record_simulation_step,
        )

        for i in range(batch_size):
            try:
                event_type = random.choice(self.config.event_types)

                # Create span for event processing
                with self._telemetry.span(
                    "loadtest.event",
                    {
                        "event_type": event_type,
                        "batch_id": batch_id,
                        "event_id": i,
                    }
                ):
                    # Record metrics
                    record_event_published(event_type)
                    record_event_processed(event_type)

                    # Simulate some processing time
                    latency = random.uniform(0.1, 5.0)
                    record_event_latency(latency, event_type)

                    # Occasionally record simulation step
                    if random.random() < 0.1:
                        record_simulation_step(
                            timestep=batch_id * batch_size + i,
                            duration_ms=random.uniform(10, 100),
                            success=random.random() > 0.01,
                        )

                with self._lock:
                    self.stats.events_generated += 1
                    self.stats.spans_created += 1
                    self.stats.metrics_recorded += 3

            except Exception as e:
                with self._lock:
                    self.stats.errors += 1

    def _worker(self, worker_id: int):
        """Worker thread for generating events."""
        events_per_worker = self.config.events_per_second // self.config.num_workers
        batch_size = max(1, events_per_worker // 10)  # 10 batches per second
        sleep_time = 0.1  # 100ms between batches

        batch_id = 0
        while self._running:
            start = time.perf_counter()

            self._generate_event_batch(worker_id * 1000000 + batch_id, batch_size)

            # Sleep to maintain rate
            elapsed = time.perf_counter() - start
            if elapsed < sleep_time:
                time.sleep(sleep_time - elapsed)

            batch_id += 1

    def run(self) -> LoadTestStats:
        """Run the load test."""
        print(f"\n{'='*60}")
        print("Sally Telemetry Load Test")
        print(f"{'='*60}")
        print(f"Target rate: {self.config.events_per_second} events/second")
        print(f"Duration: {self.config.duration_seconds} seconds")
        print(f"Workers: {self.config.num_workers}")
        print(f"{'='*60}\n")

        # Initialize telemetry
        print("Initializing telemetry...")
        try:
            self._init_telemetry()
            print("✓ Telemetry initialized\n")
        except Exception as e:
            print(f"✗ Failed to initialize telemetry: {e}")
            return self.stats

        # Start workers
        self._running = True
        self.stats.start_time = time.time()

        print(f"Starting {self.config.num_workers} worker threads...")

        with ThreadPoolExecutor(max_workers=self.config.num_workers) as executor:
            futures = [
                executor.submit(self._worker, i)
                for i in range(self.config.num_workers)
            ]

            # Run for specified duration with progress updates
            start_time = time.time()
            last_count = 0

            while time.time() - start_time < self.config.duration_seconds:
                time.sleep(1.0)

                with self._lock:
                    current_count = self.stats.events_generated
                    current_rate = current_count - last_count
                    last_count = current_count

                elapsed = time.time() - start_time
                print(f"[{elapsed:5.1f}s] Events: {current_count:,} | Rate: {current_rate:,}/s | Errors: {self.stats.errors}")

            # Stop workers
            self._running = False
            print("\nStopping workers...")

        self.stats.end_time = time.time()

        # Print summary
        self._print_summary()

        return self.stats

    def _print_summary(self):
        """Print test summary."""
        print(f"\n{'='*60}")
        print("Load Test Summary")
        print(f"{'='*60}")
        print(f"Duration: {self.stats.duration:.2f} seconds")
        print(f"Events generated: {self.stats.events_generated:,}")
        print(f"Actual rate: {self.stats.events_per_second:,.1f} events/second")
        print(f"Spans created: {self.stats.spans_created:,}")
        print(f"Metrics recorded: {self.stats.metrics_recorded:,}")
        print(f"Errors: {self.stats.errors:,}")

        target_rate = self.config.events_per_second
        actual_rate = self.stats.events_per_second
        achieved_pct = (actual_rate / target_rate) * 100 if target_rate else 0

        print(f"\nTarget rate achievement: {achieved_pct:.1f}%")

        if self.stats.errors > 0:
            error_pct = (self.stats.errors / self.stats.events_generated) * 100
            print(f"Error rate: {error_pct:.2f}%")

        if achieved_pct >= 90:
            print("\n✓ Load test PASSED - achieved target rate")
        else:
            print("\n⚠ Load test WARNING - below target rate")
            print("  Check OTEL collector capacity and network latency")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sally Telemetry Load Test"
    )
    parser.add_argument(
        "--events", "-e",
        type=int,
        default=1000,
        help="Target events per second (default: 1000)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=30,
        help="Test duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=4,
        help="Number of worker threads (default: 4)"
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=None,
        help="OTEL collector endpoint (default: from SALLY_OTEL_ENDPOINT env)"
    )

    args = parser.parse_args()

    # Set environment
    os.environ.setdefault("SALLY_OTEL_ENABLED", "true")
    if args.endpoint:
        os.environ["SALLY_OTEL_ENDPOINT"] = args.endpoint

    config = LoadTestConfig(
        events_per_second=args.events,
        duration_seconds=args.duration,
        num_workers=args.workers,
    )

    runner = LoadTestRunner(config)
    stats = runner.run()

    # Exit with error if too many failures
    if stats.errors > stats.events_generated * 0.01:  # >1% error rate
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

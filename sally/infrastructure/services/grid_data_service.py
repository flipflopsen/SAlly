"""
Grid Data Service

High-frequency grid data collection and processing service with OTEL instrumentation.
Supports PMU data (30-60 Hz), SCADA data (1-10 Hz), and renewable generation monitoring.
"""

import asyncio
import random
import math
import time
from typing import List, Dict, Any, Optional
from sally.core.event_bus import EventHandler, Event, EventBus
from sally.core.service_telemetry import ServiceNames
from sally.infrastructure.data_management.timescale.timescaledb_connection import TimescaleDBConnection
from sally.domain.events import GridDataEvent
from sally.domain.grid_entities import GridMeasurement, EntityType

from sally.core.logger import get_logger

logger = get_logger(__name__)

# Try to import telemetry
_TELEMETRY_AVAILABLE = False
try:
    from sally.core.telemetry import get_telemetry, TelemetryManager
    _TELEMETRY_AVAILABLE = True
except ImportError:
    pass


class GridDataService(EventHandler):
    """
    High-frequency grid data collection and processing service with OTEL instrumentation.

    Service Name: SAlly.GridData
    """

    def __init__(self, db: TimescaleDBConnection, event_bus: EventBus, stream_mode: str = "continuous"):
        self.db = db
        self.stream_mode = stream_mode  # 'continuous', 'batch', or 'generate'
        self.event_bus = event_bus
        self.running = False
        self._batch_buffer: List[Dict[str, Any]] = []
        self._batch_size = 500  # Higher batch size for grid data
        self._last_flush = time.time()
        self._flush_interval = 0.05  # 50ms batch flush for real-time monitoring
        self._service_name = ServiceNames.GRID_DATA

        # Stream configuration
        self._stream_poll_interval = 0.5  # Stream polling interval in seconds
        self._stream_batch_size = 500

        # Grid topology (for generate mode)
        self.grid_entities = self._initialize_grid_topology() if stream_mode == "generate" else {}
        self._entity_states = {}  # Track current state of each entity

        # Metrics tracking
        self._events_processed = 0
        self._batches_flushed = 0
        self._total_records_flushed = 0
        self._flush_errors = 0
        self._data_points_collected = 0

        # OTEL telemetry
        self._telemetry: Optional[TelemetryManager] = None
        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
                self._register_metrics()
            except Exception as e:
                logger.warning("Failed to initialize grid data telemetry: %s", e)

        logger.info(
            "GridDataService initialized: service=%s mode=%s batch_size=%d, flush_interval=%.3fs",
            self._service_name, self.stream_mode, self._batch_size, self._flush_interval
        )

    def _register_metrics(self) -> None:
        """Register OTEL metrics for grid data service."""
        if not self._telemetry or not self._telemetry.enabled:
            return

        try:
            self._telemetry.gauge(
                "grid_data.batch_buffer_size",
                lambda: len(self._batch_buffer),
                "Current batch buffer size"
            )
            self._telemetry.gauge(
                "grid_data.entity_states_count",
                lambda: len(self._entity_states),
                "Number of tracked entity states"
            )
            self._telemetry.gauge(
                "grid_data.entities_monitored",
                lambda: len(self.grid_entities),
                "Total entities being monitored"
            )
            self._telemetry.gauge(
                "grid_data.data_points_collected",
                lambda: self._data_points_collected,
                "Total data points collected"
            )
            logger.debug("Grid data OTEL metrics registered")
        except Exception as e:
            logger.warning("Failed to register grid data metrics: %s", e)

    def _initialize_grid_topology(self) -> Dict[str, EntityType]:
        """Initialize a realistic grid topology with various entity types."""
        entities = {}

        # Power generation entities
        for i in range(5):  # 5 generators
            entities[f"GEN_{i + 1}"] = EntityType.PYPOWER_NODE

        # Transmission nodes
        for i in range(15):  # 15 transmission nodes
            entities[f"NODE_{i + 1:02d}"] = EntityType.PYPOWER_NODE

        # Transmission lines
        for i in range(20):  # 20 transmission lines
            entities[f"LINE_{i + 1:02d}"] = EntityType.PYPOWER_BRANCH

        # Transformers
        for i in range(10):  # 10 transformers
            entities[f"TRANS_{i + 1:02d}"] = EntityType.PYPOWER_TRANSFORMER
            entities[f"TRANS_PRI_{i + 1:02d}"] = EntityType.PYPOWER_TR_PRI
            entities[f"TRANS_SEC_{i + 1:02d}"] = EntityType.PYPOWER_TR_SEC

        # Renewable generation
        for i in range(8):  # 8 PV installations
            entities[f"PV_{i + 1:02d}"] = EntityType.CSV_PV

        for i in range(6):  # 6 wind turbines
            entities[f"WIND_{i + 1:02d}"] = EntityType.WIND_TURBINE

        # Energy storage
        for i in range(4):  # 4 battery systems
            entities[f"BESS_{i + 1:02d}"] = EntityType.BATTERY_ESS

        # Load entities
        for i in range(50):  # 50 households
            entities[f"HOUSE_{i + 1:03d}"] = EntityType.HOUSEHOLD_SIM

        for i in range(20):  # 20 load buses
            entities[f"LOAD_{i + 1:02d}"] = EntityType.LOAD_BUS

        logger.info(
            "Grid topology initialized: total_entities=%d generators=%d nodes=%d branches=%d",
            len(entities), 5, 15, 20
        )
        logger.debug(
            "Grid topology breakdown: transformers=%d, PV=%d, wind=%d, BESS=%d, households=%d, loads=%d",
            10, 8, 6, 4, 50, 20
        )
        return entities

    @property
    def event_types(self) -> List[str]:
        return ["grid_data_update"]

    async def handle(self, event: Event) -> None:
        """Handle grid data events with batching for high-performance storage."""
        if isinstance(event, GridDataEvent):
            self._events_processed += 1
            self._data_points_collected += 1
            measurement = event.measurement

            logger.debug(
                "GridDataEvent received: entity=%s type=%s p=%.2f",
                measurement.entity,
                measurement.entity_type.value if measurement.entity_type else "N/A",
                measurement.p or 0.0
            )

            # Create span for data collection
            span = None
            if self._telemetry and self._telemetry.enabled:
                span = self._telemetry.start_span(
                    "grid_data.collect",
                    kind="consumer",
                    attributes={
                        "entity": measurement.entity,
                        "entity_type": measurement.entity_type.value if measurement.entity_type else "",
                    }
                )

            try:
                # Convert to database format
                grid_data = {
                    'time': measurement.timestamp,
                    'entity': measurement.entity,
                    'entity_type': measurement.entity_type.value,
                    'p': measurement.p,
                    'p_out': measurement.p_out,
                    'p_from': measurement.p_from,
                    'p_to': measurement.p_to,
                    'q': measurement.q,
                    'q_from': measurement.q_from,
                    'va': measurement.va,
                    'vl': measurement.vl,
                    'vm': measurement.vm,
                    'humidity': measurement.humidity
                }

                self._batch_buffer.append(grid_data)

                # Update entity state tracking
                self._entity_states[measurement.entity] = measurement

                # Record data collection metric
                if self._telemetry and self._telemetry.enabled:
                    entity_type = measurement.entity_type.value if measurement.entity_type else "unknown"
                    self._telemetry.counter(
                        "grid_data.collected.total",
                        1,
                        {"entity_type": entity_type}
                    )

                # Flush batch if conditions met
                current_time = time.time()
                if (len(self._batch_buffer) >= self._batch_size or
                        current_time - self._last_flush >= self._flush_interval):
                    await self._flush_batch()
            finally:
                if span:
                    span.end()

    async def _flush_batch(self) -> None:
        """Flush accumulated grid data to TimescaleDB with OTEL tracing."""
        if not self._batch_buffer:
            return

        batch_size = len(self._batch_buffer)
        start_time = time.perf_counter()
        span = None
        if self._telemetry and self._telemetry.enabled:
            span = self._telemetry.start_span(
                "grid_data.flush_batch",
                kind="internal",
                attributes={
                    "batch_size": batch_size,
                }
            )

        try:
            await self.db.insert_grid_data_batch(self._batch_buffer)
            elapsed = (time.perf_counter() - start_time) * 1000

            self._batches_flushed += 1
            self._total_records_flushed += batch_size

            logger.debug(
                "Grid data batch flushed: count=%d elapsed=%.2fms total_batches=%d",
                batch_size, elapsed, self._batches_flushed
            )

            if self._telemetry and self._telemetry.enabled:
                self._telemetry.counter("grid_data.records_flushed", batch_size)
                self._telemetry.histogram(
                    "grid_data.flush_duration_ms",
                    elapsed,
                    {"batch_size": str(batch_size)}
                )
                self._telemetry.histogram("grid_data.collection_latency_ms", elapsed)

            self._batch_buffer.clear()
            self._last_flush = time.time()

        except Exception as e:
            self._flush_errors += 1
            logger.error(
                "Failed to flush grid data batch: error=%s count=%d errors_total=%d",
                str(e), batch_size, self._flush_errors
            )
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.counter("grid_data.flush_errors")
        finally:
            if span:
                span.end()

    async def start_data_acquisition(self) -> None:
        """Start high-frequency grid data streaming or generation."""
        self.running = True
        logger.info(
            "Grid data acquisition starting: mode=%s batch_size=%d",
            self.stream_mode, self._batch_size
        )

        tasks = []

        if self.stream_mode == "continuous":
            # Stream data continuously from TimescaleDB
            tasks.append(asyncio.create_task(self._stream_continuous_data()))
            logger.info("Continuous streaming task started")

        elif self.stream_mode == "batch":
            # Process historical data in batches
            tasks.append(asyncio.create_task(self._stream_batch_data()))
            logger.info("Batch streaming task started")

        elif self.stream_mode == "generate":
            # PMU-like data from transmission nodes (30-60 Hz)
            tasks.append(asyncio.create_task(self._generate_pmu_data()))
            logger.debug("PMU data generation task started")

            # SCADA data from generation and load (1-10 Hz)
            tasks.append(asyncio.create_task(self._generate_scada_data()))
            logger.debug("SCADA data generation task started")

            # Renewable generation data (variable frequency)
            tasks.append(asyncio.create_task(self._generate_renewable_data()))
            logger.debug("Renewable data generation task started")

            # Periodic batch flush
            tasks.append(asyncio.create_task(self._periodic_flush()))
            logger.debug("Periodic flush task started")

        logger.info("All data acquisition tasks started: count=%d", len(tasks))
        await asyncio.gather(*tasks, return_exceptions=True)
    async def _stream_continuous_data(self) -> None:
        """Stream grid data continuously from TimescaleDB and publish to event bus."""
        logger.info("Starting continuous data streaming from TimescaleDB")

        try:
            async for batch in self.db.stream_recent_grid_data_continuous(
                poll_interval=self._stream_poll_interval,
                batch_size=self._stream_batch_size
            ):
                if not self.running:
                    break

                await self._process_and_publish_batch(batch)

        except Exception as e:
            logger.error(f"Error in continuous streaming: {e}", exc_info=True)

    async def _stream_batch_data(self) -> None:
        """Stream historical data in batches and publish to event bus."""
        from datetime import datetime, timezone, timedelta

        logger.info("Starting batch data streaming from TimescaleDB")

        # Stream data from last 1 hour
        start_time = datetime.now(timezone.utc) - timedelta(hours=1)

        try:
            async for batch in self.db.stream_grid_data(
                start_time=start_time,
                batch_size=self._stream_batch_size
            ):
                if not self.running:
                    break

                await self._process_and_publish_batch(batch)

                # Small delay between batches to avoid overwhelming consumers
                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"Error in batch streaming: {e}", exc_info=True)

        logger.info("Batch streaming completed")

    async def _process_and_publish_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Process a batch of records and publish as GridDataEvents."""
        span = None
        if self._telemetry and self._telemetry.enabled:
            span = self._telemetry.start_span(
                "grid_data.process_batch",
                kind="internal",
                attributes={"batch_size": len(batch)}
            )

        try:
            for record in batch:
                # Convert database record to GridMeasurement
                entity_type_str = record.get('entity_type', 'pypower_node')
                try:
                    entity_type = EntityType(entity_type_str)
                except ValueError:
                    logger.warning(f"Unknown entity type: {entity_type_str}, defaulting to PYPOWER_NODE")
                    entity_type = EntityType.PYPOWER_NODE

                # Convert timestamp to float if needed
                timestamp = record['time']
                if hasattr(timestamp, 'timestamp'):
                    timestamp = timestamp.timestamp()

                measurement = GridMeasurement(
                    entity=record['entity'],
                    entity_type=entity_type,
                    timestamp=timestamp,
                    p=record.get('p'),
                    p_out=record.get('p_out'),
                    p_from=record.get('p_from'),
                    p_to=record.get('p_to'),
                    q=record.get('q'),
                    q_from=record.get('q_from'),
                    va=record.get('va'),
                    vl=record.get('vl'),
                    vm=record.get('vm'),
                    humidity=record.get('humidity')
                )

                # Create and publish event
                event = GridDataEvent(
                    measurement=measurement,
                    timestamp=timestamp,
                    correlation_id=f"stream_{record['entity']}_{int(timestamp * 1000000)}"
                )

                await self.event_bus.publish(event)
                self._data_points_collected += 1

            # Record metrics
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.counter("grid_data.streamed.total", len(batch))
                self._telemetry.histogram("grid_data.batch_size", len(batch))

            logger.debug(f"Processed and published batch of {len(batch)} measurements")

        except Exception as e:
            logger.error(f"Error processing batch: {e}", exc_info=True)
        finally:
            if span:
                span.end()
    async def _generate_pmu_data(self) -> None:
        """Generate high-frequency PMU-like data for transmission system monitoring"""
        # PMUs typically sample at 30-60 Hz for real-time stability monitoring
        sampling_rate = 30  # Hz
        interval = 1.0 / sampling_rate

        # Filter entities that have PMU capabilities (nodes, generators)
        pmu_entities = {k: v for k, v in self.grid_entities.items()
                        if v in [EntityType.PYPOWER_NODE, EntityType.PYPOWER_TR_PRI,
                                 EntityType.PYPOWER_TR_SEC]}

        base_frequency = 50.0  # 50 Hz system

        while self.running:
            current_time = time.time()

            for entity, entity_type in pmu_entities.items():
                try:
                    # Simulate realistic power system measurements
                    system_load_factor = 0.7 + 0.3 * math.sin(2 * math.pi * current_time / 3600)  # Hourly variation

                    # Voltage magnitude (typically 0.95-1.05 p.u.)
                    vm = 1.0 + 0.05 * math.sin(2 * math.pi * current_time / 300) + random.gauss(0, 0.01)
                    vm = max(0.9, min(1.1, vm))  # Realistic bounds

                    # Voltage angle (varies with power flow)
                    base_angle = random.uniform(-0.2, 0.2)  # Base angle for this node
                    va = base_angle + 0.1 * math.sin(2 * math.pi * current_time / 600) + random.gauss(0, 0.02)

                    # Active power (MW)
                    if "GEN" in entity:
                        p = 100 + 200 * system_load_factor + random.gauss(0, 5)  # Generation
                    else:
                        p = 50 * system_load_factor + random.gauss(0, 2)  # Load

                    # Reactive power (MVAR) - typically 10-30% of active power
                    q = p * (0.1 + 0.2 * random.random()) + random.gauss(0, 1)

                    # Voltage level (kV) - depends on voltage class
                    vl = 138.0 if "GEN" in entity else 69.0  # Different voltage levels
                    vl *= vm  # Scale by voltage magnitude

                    measurement = GridMeasurement(
                        entity=entity,
                        entity_type=entity_type,
                        timestamp=current_time,
                        p=p,
                        q=q,
                        va=va,
                        vl=vl,
                        vm=vm
                    )

                    event = GridDataEvent(
                        measurement=measurement,
                        timestamp=current_time,
                        correlation_id=f"pmu_{entity}_{int(current_time * 1000000)}"
                    )

                    await self.event_bus.publish(event)

                except Exception as e:
                    logger.error("Error generating PMU data",
                                 entity=entity, error=str(e))

            await asyncio.sleep(interval)

    async def _generate_scada_data(self) -> None:
        """Generate SCADA data for branches, transformers, and other equipment"""
        # SCADA typically samples at 1-10 Hz
        interval = 0.5  # 2 Hz

        scada_entities = {k: v for k, v in self.grid_entities.items()
                          if v in [EntityType.PYPOWER_BRANCH, EntityType.PYPOWER_TRANSFORMER]}

        while self.running:
            current_time = time.time()

            for entity, entity_type in scada_entities.items():
                try:
                    # Simulate power flows through branches and transformers
                    base_flow = 50 + 100 * math.sin(2 * math.pi * current_time / 3600)

                    if entity_type == EntityType.PYPOWER_BRANCH:
                        # Power flow through transmission line
                        p_from = base_flow + random.gauss(0, 5)
                        p_to = p_from * 0.98  # Line losses
                        q_from = p_from * 0.15 + random.gauss(0, 2)

                        measurement = GridMeasurement(
                            entity=entity,
                            entity_type=entity_type,
                            timestamp=current_time,
                            p_from=p_from,
                            p_to=p_to,
                            q_from=q_from
                        )

                    elif entity_type == EntityType.PYPOWER_TRANSFORMER:
                        # Power flow through transformer
                        p_from = base_flow + random.gauss(0, 3)
                        p_to = p_from * 0.995  # Transformer losses
                        q_from = p_from * 0.1 + random.gauss(0, 1.5)

                        measurement = GridMeasurement(
                            entity=entity,
                            entity_type=entity_type,
                            timestamp=current_time,
                            p_from=p_from,
                            p_to=p_to,
                            q_from=q_from
                        )

                    event = GridDataEvent(
                        measurement=measurement,
                        timestamp=current_time,
                        correlation_id=f"scada_{entity}_{int(current_time * 1000000)}"
                    )

                    await self.event_bus.publish(event)

                except Exception as e:
                    logger.error("Error generating SCADA data",
                                 entity=entity, error=str(e))

            await asyncio.sleep(interval)

    async def _generate_renewable_data(self) -> None:
        """Generate renewable generation data (PV, wind) with realistic variability"""
        interval = 1.0  # 1 Hz for renewable monitoring

        renewable_entities = {k: v for k, v in self.grid_entities.items()
                              if v in [EntityType.CSV_PV, EntityType.WIND_TURBINE]}

        while self.running:
            current_time = time.time()
            hour_of_day = (current_time % 86400) / 3600

            for entity, entity_type in renewable_entities.items():
                try:
                    if entity_type == EntityType.CSV_PV:
                        # Solar PV generation pattern
                        if 6 <= hour_of_day <= 18:  # Daylight hours
                            solar_factor = math.sin(math.pi * (hour_of_day - 6) / 12)
                            cloud_factor = 0.7 + 0.3 * random.random()  # Cloud variability
                            p = 25 * solar_factor * cloud_factor + random.gauss(0, 1)
                        else:
                            p = 0  # No solar generation at night

                        p = max(0, p)  # Non-negative generation

                    elif entity_type == EntityType.WIND_TURBINE:
                        # Wind turbine generation with wind speed variation
                        base_wind_speed = 8 + 5 * math.sin(2 * math.pi * current_time / 7200)  # 2-hour cycle
                        wind_speed = base_wind_speed + random.gauss(0, 2)
                        wind_speed = max(3, min(25, wind_speed))  # Cut-in to cut-out

                        if wind_speed < 3:
                            p = 0
                        elif wind_speed > 12:
                            p = 15  # Rated power
                        else:
                            p = 15 * (wind_speed - 3) / 9  # Linear ramp

                        q = p * 0.1 + random.gauss(0, 0.5)  # Small reactive power

                    measurement = GridMeasurement(
                        entity=entity,
                        entity_type=entity_type,
                        timestamp=current_time,
                        p=p,
                        q=q if entity_type == EntityType.WIND_TURBINE else None
                    )

                    event = GridDataEvent(
                        measurement=measurement,
                        timestamp=current_time,
                        correlation_id=f"renewable_{entity}_{int(current_time * 1000000)}"
                    )

                    await self.event_bus.publish(event)

                except Exception as e:
                    logger.error("Error generating renewable data",
                                 entity=entity, error=str(e))

            await asyncio.sleep(interval)

    async def _periodic_flush(self) -> None:
        """Periodically flush batches for real-time database updates"""
        while self.running:
            await asyncio.sleep(self._flush_interval)
            if self._batch_buffer:
                await self._flush_batch()

    async def stop(self) -> None:
        """Stop data acquisition and flush remaining data."""
        logger.info(
            "Stopping grid data acquisition: events_processed=%d batches_flushed=%d total_records=%d",
            self._events_processed, self._batches_flushed, self._total_records_flushed
        )
        self.running = False
        await self._flush_batch()  # Final flush
        logger.info("Grid data acquisition stopped successfully")

    def get_entity_states(self) -> Dict[str, GridMeasurement]:
        """Get current state of all grid entities."""
        logger.debug("Returning entity states: count=%d", len(self._entity_states))
        return dict(self._entity_states)

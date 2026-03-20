import logging
import time

import asyncpg
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Telemetry imports
_TELEMETRY_AVAILABLE = False
try:
    from sally.core.telemetry import TelemetryManager, get_telemetry
    from sally.core.metrics_registry import DATABASE, SPANS, ATTRS
    from sally.core.service_telemetry import ServiceNames
    _TELEMETRY_AVAILABLE = True
except ImportError:
    pass


class TimescaleDBConnection:
    """High-performance TimescaleDB connection manager with connection pooling and telemetry"""

    def __init__(self, dsn: str, pool_size: int = 20, max_size: int = 50):
        self.dsn = dsn
        self.pool_size = pool_size
        self.max_size = max_size
        self.pool: Optional[asyncpg.Pool] = None
        self._metrics = {
            'connections_created': 0,
            'queries_executed': 0,
            'errors': 0,
            'query_times': []
        }

        # Telemetry
        self._telemetry: Optional[TelemetryManager] = None
        self._service_name = ServiceNames.DATABASE if _TELEMETRY_AVAILABLE else "SAlly.Database"

        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
                self._register_gauges()
            except Exception as e:
                logger.warning("Failed to initialize database telemetry: %s", e)

    def _register_gauges(self) -> None:
        """Register observable gauges for pool metrics."""
        if not self._telemetry or not self._telemetry.enabled:
            return

        try:
            self._telemetry.gauge(
                DATABASE.POOL_SIZE,
                lambda: self.pool.get_size() if self.pool else 0,
                "Current database connection pool size"
            )
            self._telemetry.gauge(
                DATABASE.POOL_IDLE,
                lambda: self.pool.get_idle_size() if self.pool else 0,
                "Idle connections in pool"
            )
            self._telemetry.gauge(
                DATABASE.POOL_ACTIVE,
                lambda: (self.pool.get_size() - self.pool.get_idle_size()) if self.pool else 0,
                "Active connections in pool"
            )
            logger.debug("Database telemetry gauges registered")
        except Exception as e:
            logger.warning("Failed to register database gauges: %s", e)

    def _record_query_metrics(
        self,
        duration_ms: float,
        query_type: str = "query",
        table: str = "",
        row_count: int = 0,
        error: Optional[Exception] = None
    ) -> None:
        """Record query execution metrics."""
        self._metrics['queries_executed'] += 1
        self._metrics['query_times'].append(duration_ms)

        # Keep only last 1000 query times
        if len(self._metrics['query_times']) > 1000:
            self._metrics['query_times'] = self._metrics['query_times'][-1000:]

        if error:
            self._metrics['errors'] += 1

        if not self._telemetry or not self._telemetry.enabled:
            return

        labels = {DATABASE.LABEL_QUERY_TYPE: query_type}
        if table:
            labels[DATABASE.LABEL_TABLE] = table

        self._telemetry.counter(DATABASE.QUERIES_TOTAL, 1, labels)
        self._telemetry.histogram(DATABASE.QUERY_DURATION_MS, duration_ms, labels)

        if error:
            error_labels = {
                **labels,
                DATABASE.LABEL_ERROR_TYPE: type(error).__name__
            }
            self._telemetry.counter(DATABASE.ERRORS_TOTAL, 1, error_labels)

    async def initialize(self) -> None:
        """Initialize connection pool"""
        self.pool = await asyncpg.create_pool(
            self.dsn,
            min_size=self.pool_size,
            max_size=self.max_size,
            max_queries=50000,  # Optimize for high query volume
            max_inactive_connection_lifetime=300,
            setup=self._setup_connection,
            command_timeout=5
        )
        logger.info("Database pool initialized",
                    pool_size=self.pool_size,
                    max_size=self.max_size)

    async def _setup_connection(self, conn: asyncpg.Connection) -> None:
        """Optimize connection settings for high-frequency operations"""
        # Set timezone to UTC for consistent timestamps
        await conn.execute("SET timezone = 'UTC'")

        # Optimize for write-heavy workload
        await conn.execute("SET synchronous_commit = off")
        await conn.execute("SET wal_compression = on")

        self._metrics['connections_created'] += 1

    @asynccontextmanager
    async def acquire(self):
        """Acquire connection from pool with automatic release"""
        if not self.pool:
            raise RuntimeError("Database not initialized")

        async with self.pool.acquire() as conn:
            yield conn

    async def execute_query(self, query: str, *args) -> List[asyncpg.Record]:
        """Execute query with performance tracking and telemetry"""
        start_time = time.perf_counter()
        error = None
        result = []

        # Detect query type and table from query
        query_upper = query.strip().upper()
        if query_upper.startswith("SELECT"):
            query_type = "select"
        elif query_upper.startswith("INSERT"):
            query_type = "insert"
        elif query_upper.startswith("UPDATE"):
            query_type = "update"
        elif query_upper.startswith("DELETE"):
            query_type = "delete"
        else:
            query_type = "other"

        # Try to extract table name
        table = ""
        if "FROM" in query_upper:
            parts = query_upper.split("FROM")
            if len(parts) > 1:
                table = parts[1].strip().split()[0].lower()
        elif "INTO" in query_upper:
            parts = query_upper.split("INTO")
            if len(parts) > 1:
                table = parts[1].strip().split()[0].lower()

        try:
            async with self.acquire() as conn:
                result = await conn.fetch(query, *args)
        except Exception as e:
            error = e
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._record_query_metrics(duration_ms, query_type, table, len(result), error)

        return result

    async def execute_batch(self, query: str, data: List[tuple]) -> None:
        """Execute batch insert for high-throughput scenarios with telemetry"""
        start_time = time.perf_counter()
        error = None

        # Extract table name from INSERT query
        query_upper = query.strip().upper()
        table = ""
        if "INTO" in query_upper:
            parts = query_upper.split("INTO")
            if len(parts) > 1:
                table = parts[1].strip().split()[0].lower()

        try:
            async with self.acquire() as conn:
                await conn.executemany(query, data)
        except Exception as e:
            error = e
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._record_query_metrics(duration_ms, "batch_insert", table, len(data), error)

            # Also record batch-specific histogram
            if self._telemetry and self._telemetry.enabled:
                self._telemetry.histogram(
                    DATABASE.BATCH_INSERT_DURATION_MS,
                    duration_ms,
                    {DATABASE.LABEL_TABLE: table, ATTRS.ROW_COUNT: str(len(data))}
                )

        logger.debug("Batch executed",
                     records=len(data),
                     execution_time_ms=duration_ms)

    async def insert_grid_data_batch(self, grid_data: List[Dict[str, Any]]) -> None:
        """Optimized batch insert for grid data"""
        if not grid_data:
            return

        query = """
                INSERT INTO grid_data (time, entity, entity_type, p, p_out, p_from, p_to,
                                       q, q_from, va, vl, vm, humidity)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) \
                """

        # Convert timestamps and prepare data
        data = []
        for item in grid_data:
            timestamp = item['time']
            if isinstance(timestamp, (int, float)):
                from datetime import datetime, timezone
                timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)

            data.append((
                timestamp,
                item['entity'],
                item['entity_type'],
                item.get('p'),
                item.get('p_out'),
                item.get('p_from'),
                item.get('p_to'),
                item.get('q'),
                item.get('q_from'),
                item.get('va'),
                item.get('vl'),
                item.get('vm'),
                item.get('humidity')
            ))

        await self.execute_batch(query, data)

    async def insert_grid_event(self, event_data: Dict[str, Any]) -> None:
        """Insert grid alarm/event"""
        query = """
                INSERT INTO grid_events (time, entity, entity_type, event_type,
                                         severity, message, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7) \
                """

        timestamp = event_data['time']
        if isinstance(timestamp, (int, float)):
            from datetime import datetime, timezone
            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)

        async with self.acquire() as conn:
            await conn.execute(
                query,
                timestamp,
                event_data['entity'],
                event_data['entity_type'],
                event_data['event_type'],
                event_data['severity'],
                event_data['message'],
                event_data.get('metadata', {})
            )

    async def get_recent_measurements(self, entity: str, minutes: int = 5) -> List[Dict]:
        """Get recent measurements for an entity"""
        query = """
        SELECT time, entity, entity_type, p, p_out, p_from, p_to,
               q, q_from, va, vl, vm, humidity
        FROM grid_data
        WHERE entity = $1 AND time >= NOW() - INTERVAL '%s minutes'
        ORDER BY time DESC
        LIMIT 1000
        """ % minutes

        return await self.execute_query(query, entity)

    async def get_voltage_profile(self, entity_type: str = 'pypower node') -> List[Dict]:
        """Get current voltage profile across the grid"""
        query = """
                SELECT DISTINCT \
                ON (entity) entity, time, vm, va, vl
                FROM grid_data
                WHERE entity_type = $1 AND vm IS NOT NULL
                ORDER BY entity, time DESC \
                """

        return await self.execute_query(query, entity_type)

    async def close(self) -> None:
        """Close database pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

    def get_metrics(self) -> Dict[str, Any]:
        """Get database performance metrics"""
        query_times = self._metrics['query_times']
        avg_query_time = sum(query_times) / len(query_times) if query_times else 0

        pool_stats = {}
        if self.pool:
            pool_stats = {
                'size': self.pool.get_size(),
                'idle_size': self.pool.get_idle_size(),
                'max_size': self.pool.get_max_size()
            }

        return {
            'connections_created': self._metrics['connections_created'],
            'queries_executed': self._metrics['queries_executed'],
            'avg_query_time_ms': avg_query_time,
            'pool_stats': pool_stats
        }

    async def stream_grid_data(self,
                                start_time: Optional[Any] = None,
                                entity_filter: Optional[List[str]] = None,
                                batch_size: int = 1000):
        """
        Stream grid data from TimescaleDB in batches for high-performance processing.

        Args:
            start_time: Starting timestamp (datetime or epoch). If None, streams recent data.
            entity_filter: List of entity names to filter. If None, streams all entities.
            batch_size: Number of records per batch

        Yields:
            List of records as dicts
        """
        # Build query with optional filters
        where_conditions = []
        params = []
        param_idx = 1

        if start_time is not None:
            if isinstance(start_time, (int, float)):
                from datetime import datetime, timezone
                start_time = datetime.fromtimestamp(start_time, tz=timezone.utc)
            where_conditions.append(f"time >= ${param_idx}")
            params.append(start_time)
            param_idx += 1
        else:
            # Default to last 5 minutes if no start time
            where_conditions.append("time >= NOW() - INTERVAL '5 minutes'")

        if entity_filter:
            where_conditions.append(f"entity = ANY(${param_idx})")
            params.append(entity_filter)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        query = f"""
        SELECT time, entity_id, entity, entity_type, p, p_out, p_from, p_to,
               q, q_from, va, vl, vm, humidity
        FROM grid_data
        {where_clause}
        ORDER BY time ASC
        """

        async with self.acquire() as conn:
            # Use server-side cursor for memory-efficient streaming
            async with conn.transaction():
                cursor = await conn.cursor(query, *params, prefetch=batch_size)

                batch = []
                async for record in cursor:
                    batch.append(dict(record))

                    if len(batch) >= batch_size:
                        yield batch
                        batch = []

                # Yield remaining records
                if batch:
                    yield batch

    async def stream_recent_grid_data_continuous(self,
                                                   poll_interval: float = 1.0,
                                                   batch_size: int = 500):
        """
        Continuously stream new grid data as it arrives (near real-time).

        Args:
            poll_interval: Seconds between polls for new data
            batch_size: Records per batch

        Yields:
            Batches of new grid data records
        """
        import asyncio
        from datetime import datetime, timezone, timedelta

        last_timestamp = datetime.now(timezone.utc) - timedelta(seconds=10)

        while True:
            query = """
            SELECT time, entity_id, entity, entity_type, p, p_out, p_from, p_to,
                   q, q_from, va, vl, vm, humidity
            FROM grid_data
            WHERE time > $1
            ORDER BY time ASC
            LIMIT $2
            """

            records = await self.execute_query(query, last_timestamp, batch_size)

            if records:
                batch = [dict(record) for record in records]
                last_timestamp = records[-1]['time']
                yield batch

            await asyncio.sleep(poll_interval)

    async def upsert_grid_entities(self, entities: List[Dict[str, Any]]) -> None:
        """Batch upsert grid entities"""
        if not entities:
            return

        query = """
        INSERT INTO grid_entities (
            entity_id, entity_name, entity_type, rated_power, rated_voltage,
            location, manufacturer, model, installation_date, metadata, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
        ON CONFLICT (entity_id) DO UPDATE SET
            entity_name = EXCLUDED.entity_name,
            entity_type = EXCLUDED.entity_type,
            rated_power = EXCLUDED.rated_power,
            rated_voltage = EXCLUDED.rated_voltage,
            location = EXCLUDED.location,
            manufacturer = EXCLUDED.manufacturer,
            model = EXCLUDED.model,
            installation_date = EXCLUDED.installation_date,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        """

        data = []
        for entity in entities:
            installation_date = entity.get('installation_date')
            if isinstance(installation_date, str):
                from datetime import datetime
                try:
                    installation_date = datetime.fromisoformat(installation_date).date()
                except:
                    installation_date = None

            data.append((
                entity['entity_id'],
                entity['entity_name'],
                entity['entity_type'],
                entity.get('rated_power'),
                entity.get('rated_voltage'),
                entity.get('location'),
                entity.get('manufacturer'),
                entity.get('model'),
                installation_date,
                entity.get('metadata', {})
            ))

        await self.execute_batch(query, data)
        logger.info(f"Upserted {len(entities)} grid entities")

    async def upsert_grid_connections(self, connections: List[Dict[str, Any]]) -> None:
        """Batch upsert grid entity connections"""
        if not connections:
            return

        query = """
        INSERT INTO grid_entity_connections (
            from_entity_id, to_entity_id, connection_type, line_length,
            resistance, reactance, capacity, is_active, metadata, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        ON CONFLICT (from_entity_id, to_entity_id) DO UPDATE SET
            connection_type = EXCLUDED.connection_type,
            line_length = EXCLUDED.line_length,
            resistance = EXCLUDED.resistance,
            reactance = EXCLUDED.reactance,
            capacity = EXCLUDED.capacity,
            is_active = EXCLUDED.is_active,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        """

        data = []
        for conn in connections:
            data.append((
                conn['from_entity_id'],
                conn['to_entity_id'],
                conn['connection_type'],
                conn.get('line_length'),
                conn.get('resistance'),
                conn.get('reactance'),
                conn.get('capacity'),
                conn.get('is_active', True),
                conn.get('metadata', {})
            ))

        await self.execute_batch(query, data)
        logger.info(f"Upserted {len(connections)} grid connections")

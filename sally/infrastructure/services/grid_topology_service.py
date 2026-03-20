"""
Grid Topology Service

Handles updates to grid entity and connection topology data in TimescaleDB.
Processes EntityRelationalDataEvent to maintain grid structure metadata.
"""

import asyncio
from typing import List, Dict, Any, Optional
from sally.core.event_bus import EventHandler, Event, EventBus
from sally.core.service_telemetry import ServiceNames
from sally.infrastructure.data_management.timescale.timescaledb_connection import TimescaleDBConnection
from sally.domain.events import EntityRelationalDataEvent, GridEntityData, GridConnectionData
from sally.core.logger import get_logger

logger = get_logger(__name__)

# Try to import telemetry
_TELEMETRY_AVAILABLE = False
try:
    from sally.core.telemetry import get_telemetry, TelemetryManager
    _TELEMETRY_AVAILABLE = True
except ImportError:
    pass


class GridTopologyService(EventHandler):
    """
    Service for managing grid topology metadata (entities and connections).

    Service Name: SAlly.GridTopology
    """

    def __init__(self, db: TimescaleDBConnection, event_bus: EventBus):
        self.db = db
        self.event_bus = event_bus
        self._service_name = ServiceNames.GRID_DATA

        # Metrics
        self._events_processed = 0
        self._entities_upserted = 0
        self._connections_upserted = 0
        self._errors = 0

        # OTEL telemetry
        self._telemetry: Optional[TelemetryManager] = None
        if _TELEMETRY_AVAILABLE:
            try:
                self._telemetry = get_telemetry()
                self._register_metrics()
            except Exception as e:
                logger.warning("Failed to initialize topology service telemetry: %s", e)

        logger.info("GridTopologyService initialized")

    def _register_metrics(self) -> None:
        """Register OTEL metrics for topology service."""
        if not self._telemetry or not self._telemetry.enabled:
            return

        try:
            self._telemetry.gauge(
                "grid_topology.entities_tracked",
                lambda: self._entities_upserted,
                "Total entities tracked in topology"
            )
            self._telemetry.gauge(
                "grid_topology.connections_tracked",
                lambda: self._connections_upserted,
                "Total connections tracked in topology"
            )
            logger.debug("Grid topology OTEL metrics registered")
        except Exception as e:
            logger.warning("Failed to register topology metrics: %s", e)

    @property
    def event_types(self) -> List[str]:
        return ["entity_relational_data"]

    async def handle(self, event: Event) -> None:
        """Handle EntityRelationalDataEvent to update topology data."""
        if isinstance(event, EntityRelationalDataEvent):
            self._events_processed += 1

            logger.info(
                "EntityRelationalDataEvent received: entities=%d connections=%d operation=%s",
                len(event.entities), len(event.connections), event.operation
            )

            span = None
            if self._telemetry and self._telemetry.enabled:
                span = self._telemetry.start_span(
                    "grid_topology.update",
                    kind="consumer",
                    attributes={
                        "entity_count": len(event.entities),
                        "connection_count": len(event.connections),
                        "operation": event.operation
                    }
                )

            try:
                # Process entities
                if event.entities:
                    await self._process_entities(event.entities, event.operation)

                # Process connections
                if event.connections:
                    await self._process_connections(event.connections, event.operation)

                # Record success metrics
                if self._telemetry and self._telemetry.enabled:
                    self._telemetry.counter("grid_topology.events_processed", 1)

            except Exception as e:
                self._errors += 1
                logger.error(
                    "Failed to process topology event: error=%s entities=%d connections=%d",
                    str(e), len(event.entities), len(event.connections),
                    exc_info=True
                )
                if self._telemetry and self._telemetry.enabled:
                    self._telemetry.counter("grid_topology.errors", 1)
            finally:
                if span:
                    span.end()

    async def _process_entities(self, entities: List[GridEntityData], operation: str) -> None:
        """Process entity data based on operation type."""
        if operation in ["insert", "update", "upsert"]:
            # Convert to dicts for database insertion
            entity_dicts = []
            for entity in entities:
                entity_dict = {
                    'entity_id': entity.entity_id,
                    'entity_name': entity.entity_name,
                    'entity_type': entity.entity_type,
                    'rated_power': entity.rated_power,
                    'rated_voltage': entity.rated_voltage,
                    'location': entity.location,
                    'manufacturer': entity.manufacturer,
                    'model': entity.model,
                    'installation_date': entity.installation_date,
                    'metadata': entity.metadata or {}
                }
                entity_dicts.append(entity_dict)

            await self.db.upsert_grid_entities(entity_dicts)
            self._entities_upserted += len(entities)

            logger.debug(f"Upserted {len(entities)} entities to database")

        elif operation == "delete":
            # TODO: Implement delete operation
            logger.warning("Delete operation not yet implemented for entities")

    async def _process_connections(self, connections: List[GridConnectionData], operation: str) -> None:
        """Process connection data based on operation type."""
        if operation in ["insert", "update", "upsert"]:
            # Convert to dicts for database insertion
            connection_dicts = []
            for conn in connections:
                conn_dict = {
                    'from_entity_id': conn.from_entity_id,
                    'to_entity_id': conn.to_entity_id,
                    'connection_type': conn.connection_type,
                    'line_length': conn.line_length,
                    'resistance': conn.resistance,
                    'reactance': conn.reactance,
                    'capacity': conn.capacity,
                    'is_active': conn.is_active,
                    'metadata': conn.metadata or {}
                }
                connection_dicts.append(conn_dict)

            await self.db.upsert_grid_connections(connection_dicts)
            self._connections_upserted += len(connections)

            logger.debug(f"Upserted {len(connections)} connections to database")

        elif operation == "delete":
            # TODO: Implement delete operation
            logger.warning("Delete operation not yet implemented for connections")

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        return {
            'events_processed': self._events_processed,
            'entities_upserted': self._entities_upserted,
            'connections_upserted': self._connections_upserted,
            'errors': self._errors
        }

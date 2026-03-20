"""
Metrics Registry for Sally Observability.

This module defines all metric names used throughout the Sally system.
Using constants ensures consistency and makes it easy to find all metric usages.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class EventBusMetrics:
    """Metrics for the high-performance event bus."""

    # Counters
    EVENTS_PUBLISHED: Final[str] = "eventbus.events.published"
    EVENTS_PROCESSED: Final[str] = "eventbus.events.processed"
    EVENTS_DROPPED: Final[str] = "eventbus.events.dropped"

    # Gauges
    QUEUE_SIZE: Final[str] = "eventbus.queue.size"
    HANDLER_COUNT: Final[str] = "eventbus.handler.count"

    # Histograms
    EVENT_LATENCY_MS: Final[str] = "eventbus.event.latency_ms"
    BATCH_LATENCY_MS: Final[str] = "eventbus.batch.latency_ms"

    # Labels
    LABEL_EVENT_TYPE: Final[str] = "event_type"


@dataclass(frozen=True)
class RulesMetrics:
    """Metrics for the rules engine."""

    # Counters
    EVALUATIONS_TOTAL: Final[str] = "rules.evaluations.total"
    TRIGGERED_TOTAL: Final[str] = "rules.triggered.total"
    CHAINS_TRIGGERED_TOTAL: Final[str] = "rules.chains.triggered.total"
    CHAINS_EVALUATED_TOTAL: Final[str] = "rules.chains.evaluated.total"
    SINGLES_TRIGGERED_TOTAL: Final[str] = "rules.singles.triggered.total"
    EVENTS_TRIGGERED_TOTAL: Final[str] = "rules.events.triggered.total"
    LOADED_TOTAL: Final[str] = "rules.loaded.total"

    # Gauges
    ACTIVE_COUNT: Final[str] = "rules.active.count"
    GROUPS_COUNT: Final[str] = "rules.groups.count"

    # Histograms
    EVALUATION_DURATION_MS: Final[str] = "rules.evaluation.duration_ms"

    # Labels
    LABEL_RULE_ID: Final[str] = "rule_id"
    LABEL_RESULT: Final[str] = "result"
    LABEL_GROUP_ID: Final[str] = "group_id"


@dataclass(frozen=True)
class SetpointsMetrics:
    """Metrics for the setpoint service."""

    # Counters
    APPLIED_TOTAL: Final[str] = "setpoints.applied.total"
    CLEARED_TOTAL: Final[str] = "setpoints.cleared.total"

    # Gauges
    ACTIVE_COUNT: Final[str] = "setpoints.active.count"
    VALUE: Final[str] = "setpoints.value"

    # Histograms
    APPLY_DURATION_MS: Final[str] = "setpoints.apply.duration_ms"

    # Labels
    LABEL_ENTITY_ID: Final[str] = "entity_id"
    LABEL_ATTRIBUTE: Final[str] = "attribute"


@dataclass(frozen=True)
class ScadaMetrics:
    """Metrics for SCADA and simulation orchestration."""

    # Counters
    SIMULATION_STEPS_TOTAL: Final[str] = "scada.simulation.steps.total"
    COMMANDS_TOTAL: Final[str] = "scada.commands.total"

    # Gauges
    SIMULATION_TIMESTEP: Final[str] = "scada.simulation.timestep"

    # Histograms
    STEP_DURATION_MS: Final[str] = "scada.step.duration_ms"
    COMMAND_DURATION_MS: Final[str] = "scada.command.duration_ms"

    # Labels
    LABEL_COMMAND_TYPE: Final[str] = "command_type"
    LABEL_SUCCESS: Final[str] = "success"


@dataclass(frozen=True)
class GridDataMetrics:
    """Metrics for grid data collection."""

    # Counters
    COLLECTED_TOTAL: Final[str] = "grid_data.collected.total"

    # Gauges
    ENTITIES_MONITORED: Final[str] = "grid_data.entities.monitored"
    DATA_POINTS_COLLECTED: Final[str] = "grid_data.data_points.collected"

    # Histograms
    BATCH_DURATION_MS: Final[str] = "grid_data.batch.duration_ms"

    # Labels
    LABEL_ENTITY_TYPE: Final[str] = "entity_type"


@dataclass(frozen=True)
class OtelCollectorMetrics:
    """Metrics for OTEL collector monitoring."""

    # OTEL collector metrics (these are exposed by the collector itself)
    RECEIVER_ACCEPTED_SPANS: Final[str] = "otelcol_receiver_accepted_spans"
    RECEIVER_REFUSED_SPANS: Final[str] = "otelcol_receiver_refused_spans"
    EXPORTER_SENT_SPANS: Final[str] = "otelcol_exporter_sent_spans"
    EXPORTER_FAILED_SPANS: Final[str] = "otelcol_exporter_send_failed_spans"


@dataclass(frozen=True)
class DatabaseMetrics:
    """Metrics for database connections and queries (TimescaleDB/PostgreSQL)."""

    # Counters
    QUERIES_TOTAL: Final[str] = "db.queries.total"
    ERRORS_TOTAL: Final[str] = "db.errors.total"
    CONNECTIONS_CREATED: Final[str] = "db.connections.created"

    # Gauges
    POOL_SIZE: Final[str] = "db.pool.size"
    POOL_ACTIVE: Final[str] = "db.pool.active"
    POOL_IDLE: Final[str] = "db.pool.idle"
    POOL_WAITING: Final[str] = "db.pool.waiting"

    # Histograms
    QUERY_DURATION_MS: Final[str] = "db.query.duration_ms"
    BATCH_INSERT_DURATION_MS: Final[str] = "db.batch_insert.duration_ms"

    # Labels
    LABEL_QUERY_TYPE: Final[str] = "query_type"
    LABEL_TABLE: Final[str] = "table"
    LABEL_ERROR_TYPE: Final[str] = "error_type"


@dataclass(frozen=True)
class ServiceMetrics:
    """General service-level metrics for health and performance monitoring."""

    # Counters
    REQUESTS_TOTAL: Final[str] = "service.requests.total"
    ERRORS_TOTAL: Final[str] = "service.errors.total"
    OPERATIONS_TOTAL: Final[str] = "service.operations.total"

    # Gauges
    UPTIME_SECONDS: Final[str] = "service.uptime.seconds"
    OPERATIONS_ACTIVE: Final[str] = "service.operations.active"
    HEALTH_STATUS: Final[str] = "service.health.status"

    # Histograms
    OPERATION_DURATION_MS: Final[str] = "service.operation.duration_ms"

    # Labels
    LABEL_SERVICE_NAME: Final[str] = "service_name"
    LABEL_OPERATION: Final[str] = "operation"
    LABEL_STATUS: Final[str] = "status"
    LABEL_ERROR_TYPE: Final[str] = "error_type"


@dataclass(frozen=True)
class GridTopologyMetrics:
    """Metrics for grid topology tracking (entities and connections)."""

    # Counters
    UPDATES_TOTAL: Final[str] = "grid_topology.updates.total"
    ENTITIES_UPSERTED: Final[str] = "grid_topology.entities.upserted"
    CONNECTIONS_UPSERTED: Final[str] = "grid_topology.connections.upserted"
    ERRORS_TOTAL: Final[str] = "grid_topology.errors.total"

    # Gauges
    ENTITIES_TRACKED: Final[str] = "grid_topology.entities.tracked"
    CONNECTIONS_TRACKED: Final[str] = "grid_topology.connections.tracked"

    # Histograms
    UPDATE_DURATION_MS: Final[str] = "grid_topology.update.duration_ms"

    # Labels
    LABEL_OPERATION: Final[str] = "operation"
    LABEL_ENTITY_TYPE: Final[str] = "entity_type"


# Singleton instances for easy import
EVENTBUS = EventBusMetrics()
RULES = RulesMetrics()
SETPOINTS = SetpointsMetrics()
SCADA = ScadaMetrics()
GRID_DATA = GridDataMetrics()
OTEL_COLLECTOR = OtelCollectorMetrics()
DATABASE = DatabaseMetrics()
SERVICE = ServiceMetrics()
GRID_TOPOLOGY = GridTopologyMetrics()


# Span names for tracing
@dataclass(frozen=True)
class SpanNames:
    """Standard span names for distributed tracing."""

    # Event Bus
    EVENTBUS_PUBLISH: Final[str] = "eventbus.publish"
    EVENTBUS_WORKER_BATCH: Final[str] = "eventbus.worker.batch"

    # SCADA
    SCADA_RUN_STEP: Final[str] = "scada.run_step"
    SCADA_PROCESS_COMMAND: Final[str] = "scada.process_command"

    # Rules
    RULES_EVALUATE: Final[str] = "rules.evaluate"
    RULES_EVALUATE_CHAIN: Final[str] = "rules.evaluate_chain"
    RULES_EVALUATE_RULES: Final[str] = "rules.evaluate_rules"
    RULES_HANDLE_TRIGGERED: Final[str] = "rules.handle_triggered"

    # Setpoints
    SETPOINT_APPLY: Final[str] = "setpoint.apply"
    SETPOINT_GET: Final[str] = "setpoint.get"
    SETPOINT_CLEAR: Final[str] = "setpoint.clear"

    # Grid Data
    GRID_DATA_COLLECT: Final[str] = "grid_data.collect"
    GRID_DATA_FLUSH_BATCH: Final[str] = "grid_data.flush_batch"

    # Grid Topology
    GRID_TOPOLOGY_UPDATE: Final[str] = "grid_topology.update"
    GRID_TOPOLOGY_UPSERT_ENTITIES: Final[str] = "grid_topology.upsert_entities"
    GRID_TOPOLOGY_UPSERT_CONNECTIONS: Final[str] = "grid_topology.upsert_connections"

    # Database
    DB_QUERY: Final[str] = "db.query"
    DB_BATCH_INSERT: Final[str] = "db.batch_insert"
    DB_CONNECT: Final[str] = "db.connect"
    DB_POOL_ACQUIRE: Final[str] = "db.pool.acquire"

    # Services (general)
    SERVICE_INIT: Final[str] = "service.init"
    SERVICE_SHUTDOWN: Final[str] = "service.shutdown"
    SERVICE_HEALTH_CHECK: Final[str] = "service.health_check"


SPANS = SpanNames()


# Span attribute names
@dataclass(frozen=True)
class SpanAttributes:
    """Standard span attribute names for distributed tracing."""

    # Common
    CORRELATION_ID: Final[str] = "correlation_id"

    # Event Bus
    EVENT_TYPE: Final[str] = "event_type"
    BATCH_SIZE: Final[str] = "batch_size"
    DROPPED: Final[str] = "dropped"

    # SCADA
    TIMESTEP: Final[str] = "timestep"
    COMMAND_TYPE: Final[str] = "command_type"
    PAYLOAD: Final[str] = "payload"
    SUCCESS: Final[str] = "success"

    # Rules
    RULE_ID: Final[str] = "rule_id"
    RULE_TRIGGERED: Final[str] = "rule_triggered"
    CHAIN_LENGTH: Final[str] = "chain_length"
    LOGIC_OPS: Final[str] = "logic_ops"
    GROUP_ID: Final[str] = "group_id"

    # Setpoints
    ENTITY_ID: Final[str] = "entity_id"
    ATTRIBUTE: Final[str] = "attribute"
    VALUE: Final[str] = "value"
    PREVIOUS_VALUE: Final[str] = "previous_value"

    # Grid Data
    ENTITY_TYPE: Final[str] = "entity_type"

    # Grid Topology
    ENTITY_COUNT: Final[str] = "entity_count"
    CONNECTION_COUNT: Final[str] = "connection_count"
    OPERATION: Final[str] = "operation"

    # Database
    QUERY_TYPE: Final[str] = "query_type"
    TABLE_NAME: Final[str] = "table_name"
    ROW_COUNT: Final[str] = "row_count"
    DURATION_MS: Final[str] = "duration_ms"
    POOL_SIZE: Final[str] = "pool_size"
    ERROR_TYPE: Final[str] = "error_type"

    # Services
    SERVICE_NAME: Final[str] = "service.name"
    SERVICE_VERSION: Final[str] = "service.version"
    SERVICE_INSTANCE: Final[str] = "service.instance.id"


ATTRS = SpanAttributes()

-- Create grid_events hypertable for storing grid-related events and alarms
-- This table stores events, alarms, and notifications from the grid monitoring system

CREATE TABLE IF NOT EXISTS grid_events (
    time          TIMESTAMPTZ       NOT NULL,
    event_id      UUID              NOT NULL DEFAULT gen_random_uuid(),
    entity        TEXT              NOT NULL,
    entity_type   TEXT              NOT NULL,
    event_type    TEXT              NOT NULL,
    severity      TEXT              NOT NULL, -- 'INFO', 'WARNING', 'CRITICAL', 'EMERGENCY'
    message       TEXT              NOT NULL,
    acknowledged  BOOLEAN           DEFAULT FALSE,
    metadata      JSONB             NULL
)
WITH (
    timescaledb.hypertable,
    timescaledb.partition_column='time',
    timescaledb.segmentby='event_type'
);

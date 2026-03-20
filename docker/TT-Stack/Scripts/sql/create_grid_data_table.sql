-- Create grid_data hypertable for storing time-series grid measurements
-- This table stores electrical measurements from grid entities (buses, loads, generators, etc.)

CREATE TABLE IF NOT EXISTS grid_data (
  time          TIMESTAMPTZ       NOT NULL,
  entity_id     INTEGER           NULL,  -- Nullable until topology sync
  entity        TEXT              NOT NULL,
  entity_type   TEXT              NOT NULL,
  p             DOUBLE PRECISION  NULL,
  p_out         DOUBLE PRECISION  NULL,
  p_from        DOUBLE PRECISION  NULL,
  p_to          DOUBLE PRECISION  NULL,
  q             DOUBLE PRECISION  NULL,
  q_from        DOUBLE PRECISION  NULL,
  va            DOUBLE PRECISION  NULL,
  vl            DOUBLE PRECISION  NULL,
  vm            DOUBLE PRECISION  NULL,
  humidity      DOUBLE PRECISION  NULL
)
WITH (
  timescaledb.hypertable,
  timescaledb.partition_column='time',
  timescaledb.segmentby='entity'
);

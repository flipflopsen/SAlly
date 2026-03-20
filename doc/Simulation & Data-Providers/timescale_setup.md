# TimescaleDB setup commands

## Installation
```docker run -d --name timescaledb -p 5432:5432 -e POSTGRES_PASSWORD=password timescale/timescaledb-ha:pg17```

```docker exec -it timescaledb psql -d "postgres://postgres:password@localhost/postgres"```

## Tables
```sql
CREATE TABLE grid_data (
  time          TIMESTAMPTZ       NOT NULL,
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
```

```sql
CREATE INDEX idx_grid_data_entity_time ON grid_data (entity, time DESC);
CREATE INDEX idx_grid_data_type_time ON grid_data (entity_type, time DESC);
CREATE INDEX idx_grid_data_power_time ON grid_data (p, time DESC) WHERE p IS NOT NULL;
CREATE INDEX idx_grid_data_voltage_time ON grid_data (vm, time DESC) WHERE vm IS NOT NULL;
```

```sql
CREATE TABLE grid_events (
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
```

```sql
CREATE TABLE load_forecasts (
    time             TIMESTAMPTZ       NOT NULL,
    forecast_time    TIMESTAMPTZ       NOT NULL, -- When forecast was made
    entity           TEXT              NOT NULL,
    horizon_minutes  INTEGER           NOT NULL, -- Forecast horizon
    predicted_load   DOUBLE PRECISION  NOT NULL,
    confidence_lower DOUBLE PRECISION  NULL,
    confidence_upper DOUBLE PRECISION  NULL,
    model_version    TEXT              NOT NULL,
    actual_load      DOUBLE PRECISION  NULL -- Filled in later for accuracy assessment
)
WITH (
    timescaledb.hypertable,
    timescaledb.partition_column='time',
    timescaledb.segmentby='entity'
);
```
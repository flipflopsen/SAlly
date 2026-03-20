CREATE TABLE IF NOT EXISTS load_forecasts (
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

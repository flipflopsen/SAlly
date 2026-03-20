-- Create indexes on grid_data table for efficient querying
-- These indexes optimize common query patterns for time-series analysis

CREATE INDEX IF NOT EXISTS idx_grid_data_entity_time ON grid_data (entity, time DESC);
CREATE INDEX IF NOT EXISTS idx_grid_data_type_time ON grid_data (entity_type, time DESC);
CREATE INDEX IF NOT EXISTS idx_grid_data_power_time ON grid_data (p, time DESC) WHERE p IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_grid_data_voltage_time ON grid_data (vm, time DESC) WHERE vm IS NOT NULL;

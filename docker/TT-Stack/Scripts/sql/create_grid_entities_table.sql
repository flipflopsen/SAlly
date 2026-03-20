-- Create grid_entities table for storing static entity metadata
-- This is a normal table (not a hypertable) storing information about grid components
-- The entity_id is referenced by grid_data.entity_id as a foreign key

CREATE TABLE IF NOT EXISTS grid_entities (
    entity_id       INTEGER         PRIMARY KEY,
    entity_name     TEXT            NOT NULL UNIQUE,
    entity_type     TEXT            NOT NULL, -- 'bus', 'load', 'generator', 'line', 'transformer', etc.
    rated_power     DOUBLE PRECISION NULL,    -- Rated power in kW/MW
    rated_voltage   DOUBLE PRECISION NULL,    -- Rated voltage in kV
    location        TEXT            NULL,     -- Physical location or substation
    manufacturer    TEXT            NULL,     -- Manufacturer name
    model           TEXT            NULL,     -- Model number
    installation_date DATE          NULL,     -- When installed
    metadata        JSONB           NULL,     -- Additional flexible metadata
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_grid_entities_type ON grid_entities (entity_type);
CREATE INDEX IF NOT EXISTS idx_grid_entities_name ON grid_entities (entity_name);

-- Add foreign key constraint to grid_data table (with nullable support)
-- Only enforces constraint when entity_id is not NULL
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'fk_grid_data_entity'
    ) THEN
        ALTER TABLE grid_data
        ADD CONSTRAINT fk_grid_data_entity
        FOREIGN KEY (entity_id)
        REFERENCES grid_entities(entity_id)
        ON DELETE SET NULL;
    END IF;
END $$;

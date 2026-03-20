-- Create grid_entity_connections table for storing the grid topology
-- This is a normal table (not a hypertable) storing connections between grid entities
-- Represents lines, transformers, and other connections in the power grid

CREATE TABLE IF NOT EXISTS grid_entity_connections (
    connection_id   SERIAL          PRIMARY KEY,
    from_entity_id  INTEGER         NOT NULL,
    to_entity_id    INTEGER         NOT NULL,
    connection_type TEXT            NOT NULL, -- 'line', 'transformer', 'switch', 'breaker', etc.
    line_length     DOUBLE PRECISION NULL,    -- Length in km (for lines)
    resistance      DOUBLE PRECISION NULL,    -- Resistance in Ohms
    reactance       DOUBLE PRECISION NULL,    -- Reactance in Ohms
    capacity        DOUBLE PRECISION NULL,    -- Power capacity in MW
    is_active       BOOLEAN         DEFAULT TRUE,
    metadata        JSONB           NULL,     -- Additional flexible metadata
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW(),

    -- Foreign key constraints
    CONSTRAINT fk_from_entity FOREIGN KEY (from_entity_id)
        REFERENCES grid_entities(entity_id) ON DELETE CASCADE,
    CONSTRAINT fk_to_entity FOREIGN KEY (to_entity_id)
        REFERENCES grid_entities(entity_id) ON DELETE CASCADE,

    -- Prevent self-connections
    CONSTRAINT chk_no_self_connection CHECK (from_entity_id != to_entity_id),
    
    -- Unique constraint for upsert operations
    CONSTRAINT uq_connection_pair UNIQUE (from_entity_id, to_entity_id)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_connections_from_entity ON grid_entity_connections (from_entity_id);
CREATE INDEX IF NOT EXISTS idx_connections_to_entity ON grid_entity_connections (to_entity_id);
CREATE INDEX IF NOT EXISTS idx_connections_type ON grid_entity_connections (connection_type);
CREATE INDEX IF NOT EXISTS idx_connections_active ON grid_entity_connections (is_active) WHERE is_active = TRUE;

-- Create index for bidirectional queries (finding connections in either direction)
CREATE INDEX IF NOT EXISTS idx_connections_both_entities ON grid_entity_connections (from_entity_id, to_entity_id);

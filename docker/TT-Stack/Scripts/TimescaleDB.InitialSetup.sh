#!/bin/bash
# ==============================================================================
# TimescaleDB Initial Setup Script (Bash)
# ==============================================================================
#
# SYNOPSIS:
#   Initializes TimescaleDB with required tables and indexes for Sally grid data storage.
#
# DESCRIPTION:
#   This script sets up the TimescaleDB database for the Sally system by:
#   1. Waiting for TimescaleDB to be ready
#   2. Creating the sally_grid database if it doesn't exist
#   3. Enabling the TimescaleDB extension
#   4. Creating required tables (grid_data, grid_events, load_forecasts)
#   5. Creating indexes for optimal query performance
#
# USAGE:
#   ./TimescaleDB.InitialSetup.sh [OPTIONS]
#
# OPTIONS:
#   -c, --container NAME     Container name (default: tt-stack-timescaledb-1)
#   -d, --database NAME      Database name (default: sally_grid)
#   -p, --password PASS      PostgreSQL password (default: password)
#   -r, --retries NUM        Max connection retries (default: 30)
#   -h, --help              Show this help message
#
# EXAMPLES:
#   ./TimescaleDB.InitialSetup.sh
#   ./TimescaleDB.InitialSetup.sh --container timescaledb --database my_grid
#
# ==============================================================================

set -e  # Exit on error

# Default values
CONTAINER_NAME="tt-stack-timescaledb-1"
DATABASE="sally_grid"
POSTGRES_PASSWORD="password"
MAX_RETRIES=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -d|--database)
            DATABASE="$2"
            shift 2
            ;;
        -p|--password)
            POSTGRES_PASSWORD="$2"
            shift 2
            ;;
        -r|--retries)
            MAX_RETRIES="$2"
            shift 2
            ;;
        -h|--help)
            sed -n '/^# =====*, /^# =====$/, p' "$0" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *)
            echo -e "${RED}ERROR: Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SQL_DIR="$SCRIPT_DIR/sql"

echo -e "${CYAN}======================================${NC}"
echo -e "${CYAN}  TimescaleDB Initial Setup          ${NC}"
echo -e "${CYAN}======================================${NC}"
echo ""

# Check if SQL directory exists
if [ ! -d "$SQL_DIR" ]; then
    echo -e "${RED}ERROR: SQL directory not found at: $SQL_DIR${NC}"
    exit 1
fi

# Wait for TimescaleDB to be ready
echo -e "${YELLOW}Waiting for TimescaleDB to be ready...${NC}"
retries=0
ready=false

while [ "$ready" = false ] && [ $retries -lt $MAX_RETRIES ]; do
    retries=$((retries + 1))
    if docker exec "$CONTAINER_NAME" pg_isready -U postgres >/dev/null 2>&1; then
        ready=true
        echo -e "${GREEN}✓ TimescaleDB is ready!${NC}"
    else
        echo -e "${GRAY}  Attempt $retries/$MAX_RETRIES - waiting...${NC}"
        sleep 2
    fi
done

if [ "$ready" = false ]; then
    echo -e "${RED}ERROR: TimescaleDB did not become ready after $MAX_RETRIES attempts${NC}"
    exit 1
fi

echo ""

# Function to execute SQL file
execute_sql_file() {
    local sql_file="$1"
    local description="$2"

    echo -e "${CYAN}Executing: $description${NC}"
    echo -e "${GRAY}  File: $sql_file${NC}"

    if [ ! -f "$sql_file" ]; then
        echo -e "${RED}  ERROR: SQL file not found: $sql_file${NC}"
        return 1
    fi

    if docker exec -i "$CONTAINER_NAME" psql -U postgres -d "$DATABASE" < "$sql_file" >/dev/null 2>&1; then
        echo -e "${GREEN}  ✓ Success${NC}"
        return 0
    else
        echo -e "${RED}  ✗ Failed${NC}"
        return 1
    fi
}

# Create database and enable TimescaleDB extension
echo -e "${CYAN}Setting up database...${NC}"
docker exec "$CONTAINER_NAME" psql -U postgres -c "CREATE DATABASE $DATABASE;" >/dev/null 2>&1 || true
docker exec "$CONTAINER_NAME" psql -U postgres -d "$DATABASE" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" >/dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}  ✓ Database and extension ready${NC}"
else
    echo -e "${YELLOW}  Note: Database or extension may already exist (this is normal)${NC}"
fi

echo ""

# Execute SQL files in order
all_success=true

execute_sql_file "$SQL_DIR/create_grid_data_table.sql" "Creating grid_data hypertable" || all_success=false
echo ""

execute_sql_file "$SQL_DIR/create_grid_entities_table.sql" "Creating grid_entities table and adding FK to grid_data" || all_success=false
echo ""

execute_sql_file "$SQL_DIR/create_grid_data_indexes.sql" "Creating indexes on grid_data" || all_success=false
echo ""

execute_sql_file "$SQL_DIR/create_grid_entity_connections_table.sql" "Creating grid_entity_connections table" || all_success=false
echo ""

execute_sql_file "$SQL_DIR/create_grid_events_table.sql" "Creating grid_events hypertable" || all_success=false
echo ""

execute_sql_file "$SQL_DIR/create_load_forecasts_table.sql" "Creating load_forecasts hypertable" || all_success=false
echo ""

# Summary
echo -e "${CYAN}======================================${NC}"
if [ "$all_success" = true ]; then
    echo -e "${GREEN}✓ TimescaleDB setup completed successfully!${NC}"
else
    echo -e "${YELLOW}⚠ TimescaleDB setup completed with some errors${NC}"
fi
echo -e "${CYAN}======================================${NC}"
echo ""
echo -e "${GRAY}Connection string: postgresql://postgres:$POSTGRES_PASSWORD@localhost:5432/$DATABASE${NC}"
echo ""

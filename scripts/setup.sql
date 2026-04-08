-- =============================================================================
-- S360 Self-Assessment — Infrastructure Setup
-- Run once per target account. Fully idempotent (safe to re-run).
-- Requires ACCOUNTADMIN or equivalent.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Warehouse
CREATE WAREHOUSE IF NOT EXISTS IDENTIFIER(:warehouse)
    WAREHOUSE_SIZE  = 'XSMALL'
    AUTO_SUSPEND    = 120
    AUTO_RESUME     = TRUE
    COMMENT         = 'S360 Self-Assessment';

-- Database + schema
CREATE DATABASE IF NOT EXISTS IDENTIFIER(:database);
CREATE SCHEMA   IF NOT EXISTS IDENTIFIER(:database || '.' || :schema);

-- Required for ACCOUNT_USAGE views (cost, query history, etc.)
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE SYSADMIN;

-- Grant the deploying role access to the objects
GRANT USAGE  ON WAREHOUSE IDENTIFIER(:warehouse)            TO ROLE SYSADMIN;
GRANT USAGE  ON DATABASE  IDENTIFIER(:database)             TO ROLE SYSADMIN;
GRANT ALL    ON SCHEMA    IDENTIFIER(:database || '.' || :schema) TO ROLE SYSADMIN;

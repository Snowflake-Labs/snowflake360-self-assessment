-- =============================================================================
-- S360 Self-Assessment — Infrastructure Setup
-- Run once per target account. Fully idempotent (safe to re-run).
--
-- Variables injected by deploy.sh via: snow sql --variable key=value
--   &database   Target database  (default: DEMOS)
--   &schema     Target schema    (default: S360_SELF_ASSESS)
--   &warehouse  Warehouse name   (default: S360_WH)
--   &role       Deploying role   (default: ACCOUNTADMIN)
-- =============================================================================

USE ROLE &role;

-- ── Warehouse ────────────────────────────────────────────────────────────────
CREATE WAREHOUSE IF NOT EXISTS IDENTIFIER('&warehouse')
    WAREHOUSE_SIZE  = 'XSMALL'
    AUTO_SUSPEND    = 120
    AUTO_RESUME     = TRUE
    COMMENT         = 'S360 Self-Assessment query warehouse';

-- ── Database + Schema ────────────────────────────────────────────────────────
CREATE DATABASE IF NOT EXISTS IDENTIFIER('&database');
CREATE SCHEMA   IF NOT EXISTS IDENTIFIER('&database.&schema');

-- ── ACCOUNT_USAGE access ─────────────────────────────────────────────────────
-- Required for all topic overview queries (50+ ACCOUNT_USAGE views)
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE IDENTIFIER('&role');

-- ── Cortex AI access ─────────────────────────────────────────────────────────
-- Required for all Analyzer tabs (SNOWFLAKE.CORTEX.AI_COMPLETE)
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE IDENTIFIER('&role');

-- ── App object privileges ────────────────────────────────────────────────────
GRANT USAGE         ON WAREHOUSE IDENTIFIER('&warehouse')         TO ROLE IDENTIFIER('&role');
GRANT USAGE         ON DATABASE  IDENTIFIER('&database')          TO ROLE IDENTIFIER('&role');
GRANT ALL           ON SCHEMA    IDENTIFIER('&database.&schema')  TO ROLE IDENTIFIER('&role');
GRANT CREATE STREAMLIT ON SCHEMA IDENTIFIER('&database.&schema')  TO ROLE IDENTIFIER('&role');
GRANT CREATE STAGE     ON SCHEMA IDENTIFIER('&database.&schema')  TO ROLE IDENTIFIER('&role');

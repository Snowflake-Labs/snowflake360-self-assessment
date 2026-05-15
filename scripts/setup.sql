-- Copyright 2026 Snowflake, Inc.
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

-- =============================================================================
-- S360 Self-Assessment — Infrastructure Setup
-- Run once per target account. Fully idempotent (safe to re-run).
--
-- Variables injected by deploy.sh via: snow sql --variable key=value
--   <% database %>   Target database  (default: DEMOS)
--   <% schema %>     Target schema    (default: S360_SELF_ASSESS)
--   <% warehouse %>  Warehouse name   (default: S360_WH)
--   <% role %>       Deploying role   (default: ACCOUNTADMIN)
-- =============================================================================

USE ROLE IDENTIFIER('<% role %>');

-- ── Warehouse ────────────────────────────────────────────────────────────────
CREATE WAREHOUSE IF NOT EXISTS IDENTIFIER('<% warehouse %>')
    WAREHOUSE_SIZE  = 'XSMALL'
    AUTO_SUSPEND    = 120
    AUTO_RESUME     = TRUE
    COMMENT         = 'S360 Self-Assessment query warehouse';

-- ── Database + Schema ────────────────────────────────────────────────────────
CREATE DATABASE IF NOT EXISTS IDENTIFIER('<% database %>');
CREATE SCHEMA   IF NOT EXISTS IDENTIFIER('<% database %>.<% schema %>');

-- ── ACCOUNT_USAGE access ─────────────────────────────────────────────────────
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE IDENTIFIER('<% role %>');

-- ── Cortex AI access ─────────────────────────────────────────────────────────
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE IDENTIFIER('<% role %>');

-- ── Cortex model registry (populates SNOWFLAKE.MODELS for dynamic LLM list) ─
CALL SNOWFLAKE.MODELS.CORTEX_BASE_MODELS_REFRESH();

-- ── (OPTIONAL) Cross-region inference for broader model availability ────────
-- ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';

-- ── App object privileges ────────────────────────────────────────────────────
GRANT USAGE            ON WAREHOUSE IDENTIFIER('<% warehouse %>')              TO ROLE IDENTIFIER('<% role %>');
GRANT USAGE            ON DATABASE  IDENTIFIER('<% database %>')               TO ROLE IDENTIFIER('<% role %>');
GRANT ALL              ON SCHEMA    IDENTIFIER('<% database %>.<% schema %>')  TO ROLE IDENTIFIER('<% role %>');
GRANT CREATE STREAMLIT ON SCHEMA    IDENTIFIER('<% database %>.<% schema %>')  TO ROLE IDENTIFIER('<% role %>');
GRANT CREATE STAGE     ON SCHEMA    IDENTIFIER('<% database %>.<% schema %>')  TO ROLE IDENTIFIER('<% role %>');

-- ── User Preferences table (persists LLM choice and other settings) ────────
CREATE TABLE IF NOT EXISTS IDENTIFIER('<% database %>.<% schema %>.USER_PREFERENCES') (
    USER_NAME      VARCHAR NOT NULL,
    SETTING_KEY    VARCHAR NOT NULL,
    SETTING_VALUE  VARCHAR,
    UPDATED_AT     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (USER_NAME, SETTING_KEY)
);

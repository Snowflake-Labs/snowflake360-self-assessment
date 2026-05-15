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
-- S360 Self-Assessment — Manual Installation Script
-- Copy-paste into a Snowsight worksheet and run as ACCOUNTADMIN
-- (or a role with equivalent privileges — see Step 0 for custom role setup)
--
-- STEP 0  Edit the variables below to customise names
-- STEP 1  Run the full script in Snowsight (Ctrl+Shift+Enter / Cmd+Shift+Enter)
-- STEP 2  Upload the app files (see "Upload App Files" at the bottom)
-- =============================================================================

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │  CONFIGURATION — edit these values before running                      │
-- └─────────────────────────────────────────────────────────────────────────┘
SET v_role      = 'ACCOUNTADMIN';     -- Role that will own and run the app
SET v_warehouse = 'S360_WH';          -- Warehouse to create (XSMALL, auto-suspend 120s)
SET v_database  = 'DEMOS';            -- Database to create / use
SET v_schema    = 'S360_SELF_ASSESS'; -- Schema to create / use
SET v_app_name  = 'S360_SELF_ASSESSMENT'; -- Streamlit app name (do not change)

-- ── Use the target role ───────────────────────────────────────────────────────
USE ROLE IDENTIFIER($v_role);

-- =============================================================================
-- STEP 1 — Warehouse
-- =============================================================================
CREATE WAREHOUSE IF NOT EXISTS IDENTIFIER($v_warehouse)
    WAREHOUSE_SIZE  = 'XSMALL'
    AUTO_SUSPEND    = 120
    AUTO_RESUME     = TRUE
    COMMENT         = 'S360 Self-Assessment query warehouse';

-- =============================================================================
-- STEP 2 — Database and Schema
-- =============================================================================
CREATE DATABASE IF NOT EXISTS IDENTIFIER($v_database);

CREATE SCHEMA IF NOT EXISTS IDENTIFIER($v_database || '.' || $v_schema);

-- =============================================================================
-- STEP 3 — Privileges required by the app
-- =============================================================================

-- 3a. ACCOUNT_USAGE read access (required for all 50+ topic queries)
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE
    TO ROLE IDENTIFIER($v_role);

-- 3b. Cortex AI access (required for all Analyzer / Summary tabs)
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER
    TO ROLE IDENTIFIER($v_role);

-- 3b-ii. Register Cortex models (populates SNOWFLAKE.MODELS for dynamic LLM dropdown)
--        This can take 1-2 minutes. Safe to re-run at any time.
CALL SNOWFLAKE.MODELS.CORTEX_BASE_MODELS_REFRESH();

-- 3c. Warehouse, database, schema access
GRANT USAGE ON WAREHOUSE IDENTIFIER($v_warehouse)
    TO ROLE IDENTIFIER($v_role);

GRANT USAGE ON DATABASE IDENTIFIER($v_database)
    TO ROLE IDENTIFIER($v_role);

GRANT ALL ON SCHEMA IDENTIFIER($v_database || '.' || $v_schema)
    TO ROLE IDENTIFIER($v_role);

-- 3d. Streamlit and Stage creation (needed to host the app)
GRANT CREATE STREAMLIT ON SCHEMA IDENTIFIER($v_database || '.' || $v_schema)
    TO ROLE IDENTIFIER($v_role);

GRANT CREATE STAGE ON SCHEMA IDENTIFIER($v_database || '.' || $v_schema)
    TO ROLE IDENTIFIER($v_role);

-- =============================================================================
-- STEP 4 — Stage for Streamlit app files
-- =============================================================================
CREATE STAGE IF NOT EXISTS IDENTIFIER($v_database || '.' || $v_schema || '.' || $v_app_name)
    DIRECTORY = (ENABLE = TRUE)
    COMMENT   = 'Hosts S360 Self-Assessment Streamlit source files';

-- =============================================================================
-- STEP 4b — User Preferences table (persists LLM choice per user)
-- =============================================================================
CREATE TABLE IF NOT EXISTS IDENTIFIER($v_database || '.' || $v_schema || '.USER_PREFERENCES') (
    USER_NAME      VARCHAR NOT NULL,
    SETTING_KEY    VARCHAR NOT NULL,
    SETTING_VALUE  VARCHAR,
    UPDATED_AT     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (USER_NAME, SETTING_KEY)
);

-- =============================================================================
-- STEP 5 — Streamlit app shell
-- (The app will show a blank page until files are uploaded in Step 6)
-- =============================================================================
CREATE STREAMLIT IF NOT EXISTS IDENTIFIER($v_database || '.' || $v_schema || '.' || $v_app_name)
    ROOT_LOCATION = '@' || $v_database || '.' || $v_schema || '.' || $v_app_name
    MAIN_FILE     = 'app.py'
    QUERY_WAREHOUSE = $v_warehouse
    TITLE         = 'Snowflake 360 Self-Assessment'
    COMMENT       = 'S360 health-check app — see https://snow.gitlab-dedicated.com/snowflakecorp/ps/professional-services/s360_self_assessment';

-- =============================================================================
-- STEP 6 — Verify
-- =============================================================================
SHOW STREAMLITS LIKE 'S360_SELF_ASSESSMENT'
    IN SCHEMA IDENTIFIER($v_database || '.' || $v_schema);

-- =============================================================================
-- UPLOAD APP FILES
-- =============================================================================
--
-- After running the SQL above, upload the app source files to the stage.
-- You need the Snowflake CLI (snow) installed for this step.
--
-- From the repo root directory, run ONE of the following:
--
-- ── Option A: snow CLI (recommended) ─────────────────────────────────────────
--
--   If you used the default database/schema:
--
--     snow streamlit deploy --connection <your_connection_name> --replace
--
--   If you used custom database/schema, first edit snowflake.yml (or use the
--   template):
--
--     sed -e 's/__DATABASE__/MY_DB/g' \
--         -e 's/__SCHEMA__/MY_SCHEMA/g' \
--         -e 's/__WAREHOUSE__/MY_WH/g' \
--         snowflake.yml.template > snowflake.yml
--
--     snow streamlit deploy --connection <your_connection_name> --replace
--
-- ── Option B: Manual upload via Snowsight ────────────────────────────────────
--
--   1. In Snowsight, go to:
--        Data → Databases → <database> → <schema> → Stages → S360_SELF_ASSESSMENT
--   2. Click "+ Files" and upload the following from the repo root:
--        app.py
--        environment.yml
--   3. Create sub-folders and upload:
--        .streamlit/    (config.toml)
--        core/          (all .py files, recursively)
--        components/    (all .py files, recursively)
--        metrics/       (all .py files, recursively)
--
--   Note: Snowsight file upload is manual and error-prone for large trees.
--   The snow CLI option (Option A) is strongly recommended.
--
-- ── Option C: PUT via SnowSQL ────────────────────────────────────────────────
--
--   Run the following from a SnowSQL session (replace paths as needed):
--
--     PUT file:///path/to/repo/app.py
--         @DEMOS.S360_SELF_ASSESS.S360_SELF_ASSESSMENT/
--         AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
--
--     PUT file:///path/to/repo/environment.yml
--         @DEMOS.S360_SELF_ASSESS.S360_SELF_ASSESSMENT/
--         AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
--
--     PUT file:///path/to/repo/.streamlit/config.toml
--         @DEMOS.S360_SELF_ASSESS.S360_SELF_ASSESSMENT/.streamlit/
--         AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
--
--   Repeat for every .py file under core/, components/, and metrics/.
--   (The snow CLI Option A automates all of this in one command.)
--
-- =============================================================================
-- POST-INSTALL
-- =============================================================================
--
-- 1. Open Snowsight → Streamlit Apps → S360_SELF_ASSESSMENT
-- 2. On the Home page, select an LLM and click Test to verify Cortex is working
-- 3. Select topics to analyse and click Run Selected Topics
-- 4. After charts load, use "Export Telemetry for Printing" (top-right) per topic
--
-- =============================================================================

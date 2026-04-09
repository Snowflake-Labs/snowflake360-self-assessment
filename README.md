# Snowflake 360 Self-Assessment

A Streamlit-in-Snowflake (SiS) application that provides a guided health-check of a Snowflake account across 8 operational topic areas. All analysis is performed using `SNOWFLAKE.ACCOUNT_USAGE` views and Snowflake Cortex AI — no external dependencies or data egress.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit in Snowflake                       │
│                                                                 │
│  app.py  ─── navigation, Home page (LLM selector + batch run)  │
│    │                                                            │
│    ├── components/<Topic>/                                      │
│    │     ├── *_overview.py      ← SQL queries → session_state  │
│    │     └── *_analysis.py      ← Cortex AI prompts + render   │
│    │                                                            │
│    ├── core/                                                    │
│    │     ├── data/catalog.json  ← tab/component registry       │
│    │     ├── config/            ← design tokens, app settings  │
│    │     ├── export_collectors.py  ← per-topic HTML export     │
│    │     └── export_telemetry.py   ← Chart.js HTML renderer    │
│    │                                                            │
│    └── metrics/                 ← metric base classes          │
│                                                                 │
│  Data source: SNOWFLAKE.ACCOUNT_USAGE  (read-only)             │
│  AI service:  SNOWFLAKE.CORTEX.AI_COMPLETE()                   │
└─────────────────────────────────────────────────────────────────┘
```

### Topics

| Topic | Component Folder |
|---|---|
| Database Management | `components/Database_Management/` |
| Data Governance | `components/Data_Governance_New/` |
| Virtual Warehouses | `components/Virtual_Warehouses/` |
| Access Control | `components/Access_Control/` |
| Data Ingestion | `components/Data_Ingestion/` |
| Data Transformation | `components/Data_Transformation/` |
| FinOps (lite) | `components/FinOps_Lite/` |
| Data Recovery & DevOps | `components/Data_Recovery_DevOps/` |

### Where Analyzer Prompts Are Stored

Prompts are **inline Python** inside each topic's `*_analysis.py` (or `*_analyzer.py`) file — there are no external prompt tables or stored procedures.

| Topic | Prompt file |
|---|---|
| Virtual Warehouses | `components/Virtual_Warehouses/warehouse_prompt.py` + `warehouse_analysis.py` |
| Database Management | `components/Database_Management/db_management_analysis.py` |
| Data Governance | `components/Data_Governance_New/governance_analyzer.py` |
| Access Control | `components/Access_Control/access_control_analysis.py` |
| Data Ingestion | `components/Data_Ingestion/ingestion_analysis.py` |
| Data Transformation | `components/Data_Transformation/transformation_analysis.py` |
| FinOps (lite) | `components/FinOps_Lite/finops_analysis.py` |
| Data Recovery & DevOps | `components/Data_Recovery_DevOps/recovery_devops_analyzer.py` |

Each `_analysis.py` follows the same pattern:
1. `_gather_data()` — queries `SNOWFLAKE.ACCOUNT_USAGE` and builds a text summary
2. `_call_cortex()` — calls `SNOWFLAKE.CORTEX.AI_COMPLETE(model, prompt)` with the gathered data injected into the prompt
3. `comp_*_analysis()` — Streamlit render function (tabs, markdown, expanders)

---

## Snowflake Objects

### Defaults

| Object | Default name | Configurable |
|---|---|---|
| Database | `DEMOS` | Yes (`--database`) |
| Schema | `S360_SELF_ASSESS` | Yes (`--schema`) |
| Warehouse | `S360_WH` | Yes (`--warehouse`) |
| Streamlit app | `S360_SELF_ASSESSMENT` | No |
| Stage | `<database>.<schema>.S360_SELF_ASSESSMENT` | No |
| Role | `ACCOUNTADMIN` | Yes (`--role`) |

### ACCOUNT_USAGE Views Used

The app reads the following `SNOWFLAKE.ACCOUNT_USAGE` views:

| Category | Views |
|---|---|
| Compute | `WAREHOUSE_METERING_HISTORY`, `WAREHOUSE_LOAD_HISTORY`, `WAREHOUSE_EVENTS_HISTORY`, `WAREHOUSE_PRISM` |
| Queries | `QUERY_HISTORY`, `QUERY_ACCELERATION_ELIGIBLE`, `QUERY_ACCELERATION_HISTORY`, `QUERY_ATTRIBUTION_HISTORY` |
| Storage | `DATABASE_STORAGE_USAGE_HISTORY`, `TABLE_STORAGE_METRICS`, `STORAGE_USAGE` |
| Objects | `DATABASES`, `SCHEMATA`, `TABLES`, `VIEWS`, `COLUMNS`, `FUNCTIONS`, `PROCEDURES`, `FILE_FORMATS` |
| Governance | `TAGS`, `TAG_REFERENCES`, `MASKING_POLICIES`, `ROW_ACCESS_POLICIES`, `POLICY_REFERENCES` |
| Access | `USERS`, `ROLES`, `GRANTS_TO_ROLES`, `GRANTS_TO_USERS`, `LOGIN_HISTORY`, `SESSIONS` |
| Security | `PASSWORD_POLICIES`, `SESSION_POLICIES`, `NETWORK_POLICIES`, `NETWORK_RULES`, `NETWORK_RULE_REFERENCES`, `TRUST_CENTER_FINDINGS` |
| Ingestion | `PIPES`, `PIPE_USAGE_HISTORY`, `COPY_HISTORY` |
| Transformation | `AUTOMATIC_CLUSTERING_HISTORY`, `MATERIALIZED_VIEW_REFRESH_HISTORY`, `DYNAMIC_TABLE_REFRESH_HISTORY`, `SEARCH_OPTIMIZATION_HISTORY`, `OBJECT_DEPENDENCIES`, `CLASS_INSTANCES`, `SEMANTIC_VIEWS` |
| Cost | `METERING_DAILY_HISTORY`, `DATA_TRANSFER_HISTORY`, `SERVERLESS_TASK_HISTORY`, `SNOWPARK_CONTAINER_SERVICES_HISTORY`, `RESOURCE_MONITORS`, `ANOMALIES_DAILY` |
| Tasks | `TASK_HISTORY`, `ACCESS_HISTORY` |

---

## Required Privileges

The role used to run the app needs:

```sql
-- 1. Read ACCOUNT_USAGE views
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <role>;

-- 2. Use Cortex AI (all analyzer tabs)
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE <role>;

-- 3. Warehouse access
GRANT USAGE ON WAREHOUSE <warehouse> TO ROLE <role>;

-- 4. Database and schema access
GRANT USAGE  ON DATABASE <database>          TO ROLE <role>;
GRANT USAGE  ON SCHEMA   <database>.<schema> TO ROLE <role>;

-- 5. Create and run the Streamlit app + stage
GRANT CREATE STREAMLIT ON SCHEMA <database>.<schema> TO ROLE <role>;
GRANT CREATE STAGE     ON SCHEMA <database>.<schema> TO ROLE <role>;
```

> **Simplest approach**: use `ACCOUNTADMIN` — it has all of the above by default.

---

## Installation

Two options are provided. Both produce the same result.

### Option A — Scripted install (Snowflake CLI)

Requires `snow` CLI ≥ 2.x configured with a valid connection.

```bash
# Clone the repo
git clone <repo-url>
cd s360_self_assessment

# First-time install (creates warehouse, database, schema, grants, deploys app)
./scripts/deploy.sh --connection <connection_name>

# Custom targets
./scripts/deploy.sh \
  --connection  <connection_name> \
  --database    MY_DB      \
  --schema      MY_SCHEMA  \
  --warehouse   MY_WH      \
  --role        MY_ROLE

# Re-deploy only (code update, no infra changes)
./scripts/deploy.sh --connection <connection_name> --skip-setup

# Re-deploy and prune stale stage files
./scripts/deploy.sh --connection <connection_name> --skip-setup --prune
```

See [scripts/deploy.sh](scripts/deploy.sh) for full option reference.

### Option B — Manual SQL install (copy & paste)

For accounts where the `snow` CLI is not available or not configured.

1. Open **Snowsight → Worksheets** and run [scripts/install_manual.sql](scripts/install_manual.sql)
2. Edit the variable block at the top of the file to set your desired names
3. Run the full script — it creates all required objects and grants
4. Upload the app files using one of:
   - **snow CLI**: `snow streamlit deploy --connection <conn> --replace` (from repo root)
   - **Snowsight UI**: Navigate to the stage `<database>.<schema>.S360_SELF_ASSESSMENT` and upload all files manually

See [scripts/install_manual.sql](scripts/install_manual.sql) for details.

---

## Post-install

1. Open **Snowsight → Streamlit Apps** and launch `S360_SELF_ASSESSMENT`
2. On the **Home** page, select an LLM from the dropdown and click **Test** to verify Cortex is reachable
3. Select topics to analyse, tick **Run All**, and click **Run Selected Topics**
4. Once charts load for a topic, the **Export Telemetry for Printing** button appears top-right

---

## Repo Layout

```
s360_self_assessment/
├── app.py                        # Main entrypoint
├── snowflake.yml                 # Snowflake CLI deploy definition (generated)
├── snowflake.yml.template        # Template — used by deploy.sh
├── environment.yml               # Conda deps (snowflake channel)
├── components/
│   ├── <Topic>/
│   │   ├── *_overview.py         # Data queries → session_state cache
│   │   └── *_analysis.py         # Cortex AI prompts + render
│   └── ...
├── core/
│   ├── data/catalog.json         # Tab / component registry
│   ├── config/                   # Design tokens, global settings
│   ├── export_collectors.py      # Per-topic HTML export builders
│   └── export_telemetry.py       # Chart.js HTML renderer
├── metrics/                      # Metric base classes
└── scripts/
    ├── deploy.sh                 # Snow CLI install script
    ├── setup.sql                 # Infrastructure SQL (used by deploy.sh)
    └── install_manual.sql        # Copy-paste SQL install (no CLI needed)
```

---

## Notes

- **SiS version**: Streamlit 1.22 — use `st.experimental_rerun()`, no `type` param on `st.download_button`
- **Column names**: All `ACCOUNT_USAGE` queries use unquoted aliases; Snowflake returns them **UPPERCASE**. Component and export code must use uppercase column names.
- **No data stored**: The app never writes to any table. All state lives in `st.session_state` for the duration of the browser session.
- **Cortex models**: Default is `claude-3-7-sonnet`. Selectable on Home page. Availability varies by region — use the **Test** button to verify.

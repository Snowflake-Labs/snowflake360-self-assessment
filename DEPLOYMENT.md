# S360 Self-Assessment — Deployment & Project Reference

> **For AI assistants (Cursor, Cortex Code, etc.):** Read this file first before touching anything in this repo. The deployment method matters and the wrong approach will silently break the app.

---

## First-time deployment (new account)

### Prerequisites
- [Snowflake CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/installation/installation) installed
- A configured connection with ACCOUNTADMIN (or a role with CREATE WAREHOUSE / CREATE DATABASE privileges)

### Steps

```bash
git clone <repo-url>
cd s360_self_assessment

# Deploy with defaults (creates DEMOS db, S360_SELF_ASSESS schema, S360_WH warehouse)
./scripts/deploy.sh --connection <connection_name>

# Or with custom targets:
./scripts/deploy.sh --connection <connection_name> \
    --database  MY_DB     \
    --schema    MY_SCHEMA \
    --warehouse MY_WH
```

The script does three things:
1. **`scripts/setup.sql`** — creates the warehouse, database, schema, and grants `IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE` (required for `ACCOUNT_USAGE` views)
2. **`snowflake.yml`** — generated from `snowflake.yml.template` with your target values
3. **`snow streamlit deploy --replace`** — uploads all app files and creates the Streamlit object

### Re-deploying (code updates only)

```bash
# Skip infra setup — just patch snowflake.yml and redeploy
./scripts/deploy.sh --connection <connection_name> --skip-setup

# Also remove stale stage files after deleting a component:
./scripts/deploy.sh --connection <connection_name> --skip-setup --prune
```

---

## Project structure

```
s360_self_assessment/            ← repo root (this directory)
│
├── app.py                       ← Streamlit entrypoint. import-only, no logic.
│                                  Imports pages/routers from components/.
│
├── environment.yml              ← Conda dependencies for Streamlit in Snowflake.
│                                  Only snowflake-channel packages. Edit with care.
│
├── snowflake.yml                ← Snowflake CLI deployment manifest.
│                                  Single source of truth for WHERE the app lives.
│
├── .streamlit/
│   └── config.toml             ← Theme (brand colours). Applied at runtime.
│
├── core/                        ← Shared internals. No UI code here.
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py          ← Re-exports all tokens/settings. Import from here.
│   │   ├── design_tokens.py     ← Colour palette, chart colours, gauge colours.
│   │   ├── component_settings.py← Markdown templates for UI chrome.
│   │   └── global_settings.py   ← App name, version, copy strings.
│   ├── data/
│   │   └── catalog.json         ← Static topic metadata (labels, descriptions).
│   ├── export_collectors.py     ← Per-topic HTML export data collectors.
│   ├── export_telemetry.py      ← HTML report renderer (self-contained output).
│   ├── handle_catalog.py        ← catalog.json loader.
│   └── utils.py                 ← Shared helpers.
│
├── components/                  ← One subdirectory per app topic/page.
│   ├── __init__.py
│   ├── local.py                 ← CSS injection + layout helpers used app-wide.
│   ├── utils.py                 ← Component-level helpers.
│   ├── Analysis/
│   │   ├── __init__.py
│   │   └── invoke_metrics_comps.py  ← Home page metric summary renderer.
│   ├── Access_Control/
│   ├── Data_Governance_New/
│   ├── Data_Ingestion/
│   ├── Data_Recovery_DevOps/
│   ├── Data_Transformation/
│   ├── Database_Management/
│   ├── FinOps_Lite/
│   └── Virtual_Warehouses/
│       └── (each topic has __init__.py + *_overview.py + *_analysis.py + ...)
│
└── metrics/                     ← Metric calculation helpers (small, reusable).
    ├── __init__.py
    ├── base_metric.py
    ├── analysis_metric.py
    ├── Access_Control/
    └── Virtual_Warehouses/
```

---

## Snowflake deployment target

Defined in `snowflake.yml`:

| Property | Value |
|---|---|
| App name | `S360_SELF_ASSESSMENT` |
| Database | `DEMOS` |
| Schema | `S360_SELF_ASSESS` |
| Stage | `DEMOS.S360_SELF_ASSESS.S360_SELF_ASSESSMENT` |
| Main file | `app.py` |
| Warehouse | `ADMIN_XSMALL` |

The Snowflake CLI uploads every path listed under `artifacts:` and sets `ROOT_LOCATION` automatically. **Do not change `ROOT_LOCATION` by hand.**

---

## How to deploy

**The only supported deployment method is `snow streamlit deploy`.**

```bash
# First time or to replace an existing deployment:
snow streamlit deploy --connection <connection_name> --replace

# Subsequent deploys — only uploads changed files (diff-based):
snow streamlit deploy --connection <connection_name>

# Remove stale files from the stage (e.g. after deleting a component):
snow streamlit deploy --connection <connection_name> --replace --prune
```

The CLI:
1. Bundles files into `output/bundle/streamlit/s360_self_assessment/` (gitignored)
2. Diffs local bundle against the Snowflake stage
3. Uploads only changed/added files
4. Creates or replaces the `STREAMLIT` object pointing to the stage

The app is live at:
```
https://app.snowflake.com/SFPSCOGS/au_demo44/#/streamlit-apps/DEMOS.S360_SELF_ASSESS.S360_SELF_ASSESSMENT
```

---

## NEVER do these things

### Never use manual `PUT` to upload files

```sql
-- DO NOT DO THIS
PUT file://./app.py @DEMOS.S360_SELF_ASSESS.S360_SELF_ASSESSMENT/s360_self_assessment/;
```

Why it breaks: Snowflake's `PUT` appends the local filename to whatever prefix you specify. If you `PUT` into `@stage/some_prefix/`, you get `@stage/some_prefix/app.py`. But if the CLI already deployed into `@stage/s360_self_assessment/S360_SELF_ASSESSMENT/`, you now have *two* copies at different paths. SiS extracts ALL files under `ROOT_LOCATION` alphabetically, and nested duplicates at a shorter prefix will silently overwrite the real files in `/tmp/appRoot/`, leaving the app root incomplete.

### Never manually `CREATE OR REPLACE STREAMLIT` with a custom `ROOT_LOCATION`

```sql
-- DO NOT DO THIS
CREATE OR REPLACE STREAMLIT DEMOS.S360_SELF_ASSESS.S360_SELF_ASSESSMENT
  ROOT_LOCATION = '@DEMOS.S360_SELF_ASSESS.S360_SELF_ASSESSMENT/some_custom_prefix'
  MAIN_FILE = 'app.py'
  QUERY_WAREHOUSE = ADMIN_XSMALL;
```

Why it breaks: The stage path must match exactly what the CLI uploaded. If they diverge, `ModuleNotFoundError` or `TypeError: bad argument type for built-in operation` appear at app startup with no useful traceback.

### Never deploy from a stale local copy

The canonical source is this GitLab repo. Do not deploy from `/Users/.../Downloads/...` or any other local checkout that may be behind.

---

## How Streamlit in Snowflake (SiS) works with stages

Understanding this prevents the class of errors above:

1. `ROOT_LOCATION` points to a stage path prefix, e.g. `@stage/S360_SELF_ASSESSMENT`
2. At startup SiS extracts **every file** under that prefix into `/tmp/appRoot/`
3. The prefix is stripped — `@stage/S360_SELF_ASSESSMENT/core/utils.py` → `/tmp/appRoot/core/utils.py`
4. Python imports resolve relative to `/tmp/appRoot/` — so `from core.utils import ...` works only if `/tmp/appRoot/core/utils.py` exists
5. If any duplicate files exist at a *shorter* prefix (e.g. `@stage/S360_SELF_ASSESSMENT/core/utils.py` AND `@stage/core/utils.py`), the shorter-prefix file is extracted last and wins, potentially overwriting the correct one

`snow streamlit deploy` manages this correctly. Manual `PUT` does not.

---

## Adding a new topic (component)

1. Create `components/YourTopic/` with `__init__.py` — follow the pattern of an existing topic
2. Register the topic in `core/data/catalog.json`
3. Import and route in `app.py`
4. Run `snow streamlit deploy --connection <conn> --replace` — no stage cleanup needed

## Modifying design tokens / colours

Edit `core/config/design_tokens.py`. All colours are imported from there via `core/config/__init__.py`. Do not hardcode hex values elsewhere.

## Runtime Python version

Snowflake SiS runs **Python 3.11**. The `environment.yml` pins `python==3.11.*`. Do not use syntax or stdlib features beyond 3.11.

---

## Local development (optional)

The app can be run locally for layout/UI iteration, but Snowflake-specific queries (`session.sql(...)`) will fail outside SiS.

```bash
pip install streamlit plotly pandas
streamlit run app.py
```

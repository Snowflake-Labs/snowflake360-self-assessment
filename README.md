# Snowflake 360 Self-Assessment (Streamlit in Snowflake)

Snowflake 360 Self-Assessment is a Streamlit app that runs inside Snowflake (Snowsight) and provides a guided health-check of a Snowflake account across operational areas like database management, warehouses, ingestion, governance, access control, transformation, and recovery/devops.

The app includes:
- Topic-driven analysis tabs and interactive visuals
- Telemetry HTML export per topic ("Export Telemetry for Printing")
- Home-page LLM selector used by analyzer tabs (Summary + Individual Analyser)

## Prerequisites

### Snowflake
- A Snowflake account with **Streamlit in Snowflake** enabled
- A role with privileges to:
  - Create/replace a Streamlit app in the target database/schema
  - Read `SNOWFLAKE.ACCOUNT_USAGE` views (many analyses rely on these)
- For AI features (Summary/Analyzer tabs):
  - Grant the **`SNOWFLAKE.CORTEX_USER`** database role to the executing role

### Tooling
- Snowflake CLI (`snow`) configured with a connection (e.g. `au_demo44`)

## Install / Deploy

### First-time deployment (new account)

1. Configure a Snowflake CLI connection with a role that has ACCOUNTADMIN (or CREATE WAREHOUSE / CREATE DATABASE privileges):

```bash
snow connection list   # verify your connection exists
```

2. Clone the repo and run the deploy script:

```bash
git clone <repo-url>
cd s360_self_assessment

./scripts/deploy.sh --connection <connection_name>
```

This creates the warehouse, database, and schema, grants `ACCOUNT_USAGE` access, and deploys the Streamlit app in one step.

**Custom targets** (if you don't want the defaults of `DEMOS` / `S360_SELF_ASSESS` / `S360_WH`):

```bash
./scripts/deploy.sh --connection <connection_name> \
    --database  MY_DB      \
    --schema    MY_SCHEMA  \
    --warehouse MY_WH
```

### Re-deploying (code updates only)

```bash
./scripts/deploy.sh --connection <connection_name> --skip-setup
```

Add `--prune` to also remove stale stage files after deleting a component:

```bash
./scripts/deploy.sh --connection <connection_name> --skip-setup --prune
```

## Running (Snowsight)

After deployment, open **Snowsight → Streamlit Apps** and launch the deployed app.

## Configuration notes

### AI model selection
On the Home page, choose an LLM from the dropdown and click **Test** to verify it can respond. The selected model is stored in `st.session_state.selected_llm` and is used by analyzer tabs.

### Telemetry export
On topic pages, the top-right **Export Telemetry for Printing** button generates a self-contained HTML report and triggers a download.

## Repo layout

- `app.py` — main Streamlit entrypoint
- `components/` — topic pages and analyzers
- `metrics/` — metric definitions
- `core/` — shared utilities, configuration, export logic
- `snowflake.yml` — Snowflake CLI deployment definition
- `environment.yml` — runtime dependencies for Streamlit in Snowflake

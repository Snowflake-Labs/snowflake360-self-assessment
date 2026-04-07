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

This project is deployed to Snowflake using `snow streamlit deploy`.

1) Configure a Snowflake CLI connection:

```bash
snow connection list
```

2) Deploy the app to the Snowflake objects defined in `snowflake.yml`:

```bash
snow streamlit deploy --connection <connection_name> --replace
```

If you want to keep the stage tidy and remove stale artifacts:

```bash
snow streamlit deploy --connection <connection_name> --replace --prune
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

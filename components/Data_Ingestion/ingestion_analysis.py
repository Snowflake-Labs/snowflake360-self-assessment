"""
Data Ingestion Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers data loading and pipe usage metrics from ACCOUNT_USAGE and generates
recommendations via SNOWFLAKE.CORTEX.AI_COMPLETE().
"""

import streamlit as st
import json

AVAILABLE_MODELS = ["claude-3-7-sonnet", "llama3.1-70b", "mistral-large2"]


def _call_cortex(session, model_name, prompt):
    try:
        safe_prompt = prompt.replace("$$", "$$$$").replace("'", "''")
        result = session.sql(f"""
            SELECT SNOWFLAKE.CORTEX.AI_COMPLETE(
                $${model_name}$$,
                $${safe_prompt}$$
            ) AS RESPONSE
        """).collect()
        if result and len(result) > 0:
            return result[0]['RESPONSE']
        return "No response from Cortex"
    except Exception as e:
        return f"Error calling Cortex: {str(e)}"


def _gather_data(session):
    sections = []

    try:
        rows = session.sql("""
            SELECT TABLE_CATALOG_NAME AS DATABASE_NAME,
                   TABLE_SCHEMA_NAME AS SCHEMA_NAME,
                   TABLE_NAME,
                   COUNT(*) AS LOAD_COUNT,
                   SUM(ROW_COUNT) AS TOTAL_ROWS,
                   SUM(FILE_SIZE) / POWER(1024,3) AS TOTAL_GB,
                   SUM(CASE WHEN STATUS = 'Loaded' THEN 1 ELSE 0 END) AS SUCCESSFUL,
                   SUM(CASE WHEN STATUS != 'Loaded' THEN 1 ELSE 0 END) AS FAILED,
                   SUM(ERROR_COUNT) AS TOTAL_ERRORS
            FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
            WHERE LAST_LOAD_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY TABLE_CATALOG_NAME, TABLE_SCHEMA_NAME, TABLE_NAME
            ORDER BY TOTAL_GB DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["COPY HISTORY (last 30 days, top 10 targets by volume):"]
            for r in rows:
                lines.append(f"  {r['DATABASE_NAME']}.{r['SCHEMA_NAME']}.{r['TABLE_NAME']}: "
                             f"loads={r['LOAD_COUNT']}, rows={r['TOTAL_ROWS']}, "
                             f"gb={r['TOTAL_GB']:.2f}, ok={r['SUCCESSFUL']}, failed={r['FAILED']}, "
                             f"errors={r['TOTAL_ERRORS']}")
            sections.append("\n".join(lines))
        else:
            sections.append("COPY HISTORY: No COPY operations in last 30 days")
    except Exception as e:
        sections.append(f"COPY_HISTORY: Error - {e}")

    try:
        rows = session.sql("""
            SELECT PIPE_CATALOG_NAME AS DATABASE_NAME,
                   PIPE_SCHEMA_NAME AS SCHEMA_NAME,
                   PIPE_NAME,
                   SUM(FILES_INSERTED) AS TOTAL_FILES,
                   SUM(BYTES_INSERTED) / POWER(1024,3) AS TOTAL_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY PIPE_CATALOG_NAME, PIPE_SCHEMA_NAME, PIPE_NAME
            ORDER BY TOTAL_GB DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["PIPE USAGE (last 30 days, top 10 by volume):"]
            for r in rows:
                lines.append(f"  {r['DATABASE_NAME']}.{r['SCHEMA_NAME']}.{r['PIPE_NAME']}: "
                             f"files={r['TOTAL_FILES']}, gb={r['TOTAL_GB']:.4f}")
            sections.append("\n".join(lines))
        else:
            sections.append("PIPE USAGE: No pipe activity in last 30 days")
    except Exception as e:
        sections.append(f"PIPE_USAGE_HISTORY: Error - {e}")

    try:
        rows = session.sql("""
            SELECT SERVICE_TYPE,
                   SUM(CREDITS_USED) AS TOTAL_CREDITS
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
              AND SERVICE_TYPE ILIKE '%PIPE%'
            GROUP BY SERVICE_TYPE
            ORDER BY TOTAL_CREDITS DESC
        """).collect()
        if rows:
            lines = ["PIPE METERING (last 30 days):"]
            for r in rows:
                lines.append(f"  {r['SERVICE_TYPE']}: credits={r['TOTAL_CREDITS']:.2f}")
            sections.append("\n".join(lines))
        else:
            sections.append("PIPE METERING: No pipe-related metering found")
    except Exception as e:
        sections.append(f"METERING_DAILY_HISTORY: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_ingestion_analyzer(entry_actions=None):
    st.markdown("### Data Ingestion Analyzer")
    st.markdown("AI-powered analysis of your data loading patterns, pipe usage, and ingestion efficiency.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        model = st.selectbox("Cortex Model", AVAILABLE_MODELS, key="ingestion_model")

    cache_key = "ingestion_analysis_result"

    if st.button("Run Analysis", type="primary", key="ingestion_run_btn"):
        with st.spinner("Gathering ingestion data and running AI analysis..."):
            data_summary = _gather_data(session)
            prompt = (
                "You are a Snowflake expert specializing in data ingestion and loading optimization. "
                "Analyze the following ingestion data from SNOWFLAKE.ACCOUNT_USAGE views. "
                "Provide:\n"
                "1. **Summary Assessment**: Overall ingestion health and efficiency\n"
                "2. **Key Findings**: Load failures, small file issues, cost patterns\n"
                "3. **Recommendations**: Steps to improve loading performance and reduce costs\n"
                "4. **Risk Areas**: High failure rates, inefficient patterns, cost anomalies\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[cache_key] = result

    if cache_key in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state[cache_key])

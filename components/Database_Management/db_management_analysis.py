"""
Database Management Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers storage and database metadata from ACCOUNT_USAGE and generates
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
            SELECT TABLE_CATALOG AS DATABASE_NAME,
                   TABLE_SCHEMA AS SCHEMA_NAME,
                   TABLE_NAME,
                   ACTIVE_BYTES / POWER(1024,3) AS ACTIVE_GB,
                   TIME_TRAVEL_BYTES / POWER(1024,3) AS TIME_TRAVEL_GB,
                   FAILSAFE_BYTES / POWER(1024,3) AS FAILSAFE_GB,
                   (ACTIVE_BYTES + TIME_TRAVEL_BYTES + FAILSAFE_BYTES) / POWER(1024,3) AS TOTAL_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
            WHERE ACTIVE_BYTES > 0
              AND DELETED IS NULL
            ORDER BY TOTAL_GB DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["TOP 10 TABLES BY STORAGE (GB):"]
            for r in rows:
                lines.append(f"  {r['DATABASE_NAME']}.{r['SCHEMA_NAME']}.{r['TABLE_NAME']}: "
                             f"active={r['ACTIVE_GB']:.2f}, tt={r['TIME_TRAVEL_GB']:.2f}, "
                             f"failsafe={r['FAILSAFE_GB']:.2f}, total={r['TOTAL_GB']:.2f}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"TABLE_STORAGE_METRICS: Error - {e}")

    try:
        rows = session.sql("""
            SELECT COUNT(*) AS DB_COUNT,
                   AVG(DATEDIFF('day', CREATED, CURRENT_TIMESTAMP())) AS AVG_AGE_DAYS,
                   MAX(DATEDIFF('day', CREATED, CURRENT_TIMESTAMP())) AS MAX_AGE_DAYS,
                   SUM(CASE WHEN IS_TRANSIENT = 'YES' THEN 1 ELSE 0 END) AS TRANSIENT_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
            WHERE DELETED IS NULL
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"DATABASES: count={r['DB_COUNT']}, avg_age_days={r['AVG_AGE_DAYS']:.0f}, "
                            f"max_age_days={r['MAX_AGE_DAYS']:.0f}, transient={r['TRANSIENT_COUNT']}")
    except Exception as e:
        sections.append(f"DATABASES: Error - {e}")

    try:
        rows = session.sql("""
            SELECT TABLE_NAME,
                   SUM(CREDITS_USED) AS TOTAL_CREDITS,
                   SUM(NUM_BYTES_RECLUSTERED) / POWER(1024,3) AS RECLUSTERED_GB,
                   COUNT(*) AS OPERATIONS
            FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY TABLE_NAME
            ORDER BY TOTAL_CREDITS DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["AUTO-CLUSTERING (last 30 days, top 10 by credits):"]
            for r in rows:
                lines.append(f"  {r['TABLE_NAME']}: credits={r['TOTAL_CREDITS']:.2f}, "
                             f"reclustered_gb={r['RECLUSTERED_GB']:.2f}, ops={r['OPERATIONS']}")
            sections.append("\n".join(lines))
        else:
            sections.append("AUTO-CLUSTERING: No clustering activity in last 30 days")
    except Exception as e:
        sections.append(f"AUTOMATIC_CLUSTERING_HISTORY: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_db_management_analyzer(entry_actions=None):
    st.markdown("### Database Management Analyzer")
    st.markdown("AI-powered analysis of your database storage, table lifecycle, and clustering patterns.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        model = st.selectbox("Cortex Model", AVAILABLE_MODELS, key="db_mgmt_model")

    cache_key = "db_mgmt_analysis_result"

    if st.button("Run Analysis", type="primary", key="db_mgmt_run_btn"):
        with st.spinner("Gathering database data and running AI analysis..."):
            data_summary = _gather_data(session)
            prompt = (
                "You are a Snowflake expert specializing in database management and storage optimization. "
                "Analyze the following database and storage data from SNOWFLAKE.ACCOUNT_USAGE views. "
                "Provide:\n"
                "1. **Summary Assessment**: Overall health of the database estate\n"
                "2. **Key Findings**: Notable patterns, anomalies, or concerns\n"
                "3. **Recommendations**: Specific, actionable optimization steps\n"
                "4. **Risk Areas**: Potential issues that need attention\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[cache_key] = result

    if cache_key in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state[cache_key])

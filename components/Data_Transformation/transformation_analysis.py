"""
Data Transformation Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers query workload and session patterns from ACCOUNT_USAGE and generates
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
            SELECT QUERY_TYPE,
                   COUNT(*) AS QUERY_COUNT,
                   AVG(TOTAL_ELAPSED_TIME) / 1000 AS AVG_ELAPSED_SEC,
                   AVG(EXECUTION_TIME) / 1000 AS AVG_EXEC_SEC,
                   SUM(CASE WHEN EXECUTION_STATUS != 'SUCCESS' THEN 1 ELSE 0 END) AS ERROR_COUNT,
                   SUM(BYTES_SPILLED_TO_LOCAL_STORAGE + BYTES_SPILLED_TO_REMOTE_STORAGE) / POWER(1024,3) AS TOTAL_SPILL_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY QUERY_TYPE
            ORDER BY QUERY_COUNT DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["QUERY WORKLOAD (last 30 days, top 10 types):"]
            for r in rows:
                lines.append(f"  {r['QUERY_TYPE']}: count={r['QUERY_COUNT']}, "
                             f"avg_elapsed={r['AVG_ELAPSED_SEC']:.1f}s, avg_exec={r['AVG_EXEC_SEC']:.1f}s, "
                             f"errors={r['ERROR_COUNT']}, spill_gb={r['TOTAL_SPILL_GB']:.2f}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"QUERY_HISTORY: Error - {e}")

    try:
        rows = session.sql("""
            SELECT EXECUTION_STATUS,
                   COUNT(*) AS QUERY_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY EXECUTION_STATUS
            ORDER BY QUERY_COUNT DESC
        """).collect()
        if rows:
            lines = ["QUERY STATUS DISTRIBUTION (last 30 days):"]
            for r in rows:
                lines.append(f"  {r['EXECUTION_STATUS']}: {r['QUERY_COUNT']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"QUERY STATUS: Error - {e}")

    try:
        rows = session.sql("""
            SELECT CLIENT_APPLICATION_ID,
                   COUNT(DISTINCT SESSION_ID) AS SESSION_COUNT,
                   COUNT(DISTINCT USER_NAME) AS USER_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS
            WHERE CREATED_ON >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY CLIENT_APPLICATION_ID
            ORDER BY SESSION_COUNT DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["CLIENT DISTRIBUTION (last 30 days, top 10):"]
            for r in rows:
                lines.append(f"  {r['CLIENT_APPLICATION_ID']}: sessions={r['SESSION_COUNT']}, "
                             f"users={r['USER_COUNT']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"SESSIONS: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_transformation_analyzer(entry_actions=None):
    st.markdown("### Data Transformation Analyzer")
    st.markdown("AI-powered analysis of your query workload, transformation patterns, and error rates.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        model = st.selectbox("Cortex Model", AVAILABLE_MODELS, key="transformation_model")

    cache_key = "transformation_analysis_result"

    if st.button("Run Analysis", type="primary", key="transformation_run_btn"):
        with st.spinner("Gathering transformation data and running AI analysis..."):
            data_summary = _gather_data(session)
            prompt = (
                "You are a Snowflake expert specializing in data transformation, query optimization, and workload management. "
                "Analyze the following transformation and query workload data from SNOWFLAKE.ACCOUNT_USAGE views. "
                "Provide:\n"
                "1. **Summary Assessment**: Overall transformation health and efficiency\n"
                "2. **Key Findings**: Error-prone query types, spill patterns, client tool usage\n"
                "3. **Recommendations**: Steps to optimize transformation workloads\n"
                "4. **Risk Areas**: High error rates, excessive spilling, inefficient patterns\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[cache_key] = result

    if cache_key in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state[cache_key])

"""
Data Recovery & DevOps Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers task execution, dynamic table health, and CI/CD patterns from ACCOUNT_USAGE
and generates recommendations via SNOWFLAKE.CORTEX.AI_COMPLETE().
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
            SELECT STATE,
                   COUNT(*) AS RUN_COUNT,
                   AVG(TIMESTAMPDIFF('second', QUERY_START_TIME, COMPLETED_TIME)) AS AVG_DURATION_SEC
            FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
            WHERE QUERY_START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY STATE
            ORDER BY RUN_COUNT DESC
        """).collect()
        if rows:
            lines = ["TASK HISTORY (last 30 days by state):"]
            for r in rows:
                dur = f"{r['AVG_DURATION_SEC']:.1f}s" if r['AVG_DURATION_SEC'] else "N/A"
                lines.append(f"  {r['STATE']}: runs={r['RUN_COUNT']}, avg_duration={dur}")
            sections.append("\n".join(lines))
        else:
            sections.append("TASK HISTORY: No task runs in last 30 days")
    except Exception as e:
        sections.append(f"TASK_HISTORY: Error - {e}")

    try:
        rows = session.sql("""
            SELECT DATABASE_NAME,
                   SCHEMA_NAME,
                   NAME AS DT_NAME,
                   COUNT(*) AS REFRESH_COUNT,
                   SUM(CASE WHEN REFRESH_ACTION = 'INCREMENTAL' THEN 1 ELSE 0 END) AS INCREMENTAL,
                   SUM(CASE WHEN REFRESH_ACTION = 'FULL' THEN 1 ELSE 0 END) AS FULL_REFRESH,
                   SUM(CASE WHEN STATE != 'SUCCEEDED' THEN 1 ELSE 0 END) AS FAILURES
            FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
            WHERE DATA_TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY DATABASE_NAME, SCHEMA_NAME, NAME
            ORDER BY REFRESH_COUNT DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["DYNAMIC TABLE REFRESH (last 30 days, top 10):"]
            for r in rows:
                lines.append(f"  {r['DATABASE_NAME']}.{r['SCHEMA_NAME']}.{r['DT_NAME']}: "
                             f"total={r['REFRESH_COUNT']}, incr={r['INCREMENTAL']}, "
                             f"full={r['FULL_REFRESH']}, failures={r['FAILURES']}")
            sections.append("\n".join(lines))
        else:
            sections.append("DYNAMIC TABLE REFRESH: No DT refresh activity in last 30 days")
    except Exception as e:
        sections.append(f"DYNAMIC_TABLE_REFRESH_HISTORY: Error - {e}")

    try:
        rows = session.sql("""
            SELECT QUERY_TYPE,
                   COUNT(*) AS QUERY_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND (QUERY_TYPE IN ('CREATE_TABLE', 'CREATE_TABLE_AS_SELECT', 'ALTER_TABLE_ADD_COLUMN',
                                  'ALTER_TABLE_DROP_COLUMN', 'ALTER_TABLE_MODIFY_COLUMN',
                                  'CREATE_VIEW', 'ALTER_VIEW')
                   OR QUERY_TEXT ILIKE '%git%'
                   OR QUERY_TEXT ILIKE '%EXECUTE IMMEDIATE FROM%')
            GROUP BY QUERY_TYPE
            ORDER BY QUERY_COUNT DESC
        """).collect()
        if rows:
            lines = ["DDL / CI-CD PATTERNS (last 30 days):"]
            for r in rows:
                lines.append(f"  {r['QUERY_TYPE']}: {r['QUERY_COUNT']}")
            sections.append("\n".join(lines))
        else:
            sections.append("DDL / CI-CD: No DDL or CI/CD patterns detected")
    except Exception as e:
        sections.append(f"QUERY_HISTORY DDL: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_recovery_devops_analyzer(entry_actions=None):
    st.markdown("### Data Recovery & DevOps Analyzer")
    st.markdown("AI-powered analysis of task orchestration, dynamic tables, and CI/CD patterns.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        model = st.selectbox("Cortex Model", AVAILABLE_MODELS, key="recovery_devops_model")

    cache_key = "recovery_devops_analysis_result"

    if st.button("Run Analysis", type="primary", key="recovery_devops_run_btn"):
        with st.spinner("Gathering DevOps data and running AI analysis..."):
            data_summary = _gather_data(session)
            prompt = (
                "You are a Snowflake expert specializing in DevOps, task orchestration, dynamic tables, and CI/CD practices. "
                "Analyze the following data from SNOWFLAKE.ACCOUNT_USAGE views. "
                "Provide:\n"
                "1. **Summary Assessment**: Overall operational health and DevOps maturity\n"
                "2. **Key Findings**: Task failures, DT refresh issues, CI/CD adoption level\n"
                "3. **Recommendations**: Steps to improve reliability and DevOps practices\n"
                "4. **Risk Areas**: Failing tasks, full-refresh DTs, missing CI/CD patterns\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[cache_key] = result

    if cache_key in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state[cache_key])

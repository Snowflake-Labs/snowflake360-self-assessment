"""
FinOps Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers credit consumption, warehouse costs, and storage usage from ACCOUNT_USAGE
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
            SELECT USAGE_DATE,
                   SUM(CREDITS_USED) AS TOTAL_CREDITS,
                   SUM(CREDITS_ADJUSTMENT_CLOUD_SERVICES) AS CS_ADJUSTMENT
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
            GROUP BY USAGE_DATE
            ORDER BY USAGE_DATE DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["DAILY METERING (last 10 days):"]
            for r in rows:
                lines.append(f"  {r['USAGE_DATE']}: credits={r['TOTAL_CREDITS']:.2f}, "
                             f"cs_adj={r['CS_ADJUSTMENT']:.2f}")
            sections.append("\n".join(lines))

        totals = session.sql("""
            SELECT SUM(CREDITS_USED) AS TOTAL_CREDITS_30D,
                   AVG(CREDITS_USED) AS AVG_DAILY_CREDITS,
                   MAX(CREDITS_USED) AS PEAK_DAILY_CREDITS
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
        """).collect()
        if totals:
            r = totals[0]
            sections.append(f"METERING TOTALS (30d): total={r['TOTAL_CREDITS_30D']:.2f}, "
                            f"avg_daily={r['AVG_DAILY_CREDITS']:.2f}, peak={r['PEAK_DAILY_CREDITS']:.2f}")
    except Exception as e:
        sections.append(f"METERING_DAILY_HISTORY: Error - {e}")

    try:
        rows = session.sql("""
            SELECT WAREHOUSE_NAME,
                   SUM(CREDITS_USED) AS TOTAL_CREDITS,
                   SUM(CREDITS_USED_COMPUTE) AS COMPUTE_CREDITS,
                   SUM(CREDITS_USED_CLOUD_SERVICES) AS CS_CREDITS
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY WAREHOUSE_NAME
            ORDER BY TOTAL_CREDITS DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["TOP 10 WAREHOUSES BY CREDITS (last 30 days):"]
            for r in rows:
                lines.append(f"  {r['WAREHOUSE_NAME']}: total={r['TOTAL_CREDITS']:.2f}, "
                             f"compute={r['COMPUTE_CREDITS']:.2f}, cs={r['CS_CREDITS']:.2f}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"WAREHOUSE_METERING_HISTORY: Error - {e}")

    try:
        rows = session.sql("""
            SELECT USAGE_DATE,
                   STORAGE_BYTES / POWER(1024,4) AS STORAGE_TB,
                   STAGE_BYTES / POWER(1024,4) AS STAGE_TB,
                   FAILSAFE_BYTES / POWER(1024,4) AS FAILSAFE_TB
            FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
            WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
            ORDER BY USAGE_DATE DESC
            LIMIT 5
        """).collect()
        if rows:
            lines = ["STORAGE USAGE (recent 5 days):"]
            for r in rows:
                lines.append(f"  {r['USAGE_DATE']}: storage={r['STORAGE_TB']:.3f}TB, "
                             f"stage={r['STAGE_TB']:.3f}TB, failsafe={r['FAILSAFE_TB']:.3f}TB")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"STORAGE_USAGE: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_finops_analyzer(entry_actions=None):
    st.markdown("### FinOps Analyzer")
    st.markdown("AI-powered analysis of your Snowflake credit consumption, cost trends, and optimization opportunities.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        model = st.selectbox("Cortex Model", AVAILABLE_MODELS, key="finops_model")

    cache_key = "finops_analysis_result"

    if st.button("Run Analysis", type="primary", key="finops_run_btn"):
        with st.spinner("Gathering FinOps data and running AI analysis..."):
            data_summary = _gather_data(session)
            prompt = (
                "You are a Snowflake FinOps expert specializing in cost optimization and credit management. "
                "Analyze the following cost and usage data from SNOWFLAKE.ACCOUNT_USAGE views. "
                "Provide:\n"
                "1. **Summary Assessment**: Overall cost health and spend trajectory\n"
                "2. **Key Findings**: Top cost drivers, trends, anomalies\n"
                "3. **Recommendations**: Specific cost optimization actions with estimated savings\n"
                "4. **Risk Areas**: Runaway costs, idle resources, unexpected spikes\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[cache_key] = result

    if cache_key in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state[cache_key])

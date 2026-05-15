# Copyright 2026 Snowflake, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
FinOps Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers credit consumption, warehouse costs, and storage usage from ACCOUNT_USAGE
and generates recommendations via SNOWFLAKE.CORTEX.COMPLETE().
"""

import streamlit as st
import json
from core.config.design_tokens import BRAND_PRIMARY, TEXT_HEADING


def _call_cortex(session, model_name, prompt):
    try:
        safe_prompt = prompt.replace("$$", "$$$$").replace("'", "''")
        result = session.sql(f"""
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                $${model_name}$$,
                $${safe_prompt}$$
            ) AS RESPONSE
        """).collect()
        if result and len(result) > 0:
            raw = result[0]['RESPONSE']
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    raw = parsed.get("choices", [{}])[0].get("messages", raw) if "choices" in parsed else parsed.get("message", parsed.get("content", raw))
                    if isinstance(raw, dict):
                        raw = raw.get("content", str(raw))
            except (json.JSONDecodeError, TypeError, KeyError, IndexError):
                pass
            return str(raw)
        return "No response from Cortex"
    except Exception as e:
        err_msg = str(e)
        if "deprecated" in err_msg.lower() or "not available" in err_msg.lower() or "not found" in err_msg.lower():
            return "MODEL_UNAVAILABLE"
        return f"Error calling Cortex: {err_msg}"


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


def _gather_individual_data(session, warehouse_name):
    sections = []

    try:
        rows = session.sql(f"""
            SELECT TO_DATE(START_TIME) AS USAGE_DATE,
                   SUM(CREDITS_USED) AS TOTAL_CREDITS,
                   SUM(CREDITS_USED_COMPUTE) AS COMPUTE_CREDITS,
                   SUM(CREDITS_USED_CLOUD_SERVICES) AS CS_CREDITS
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
            GROUP BY USAGE_DATE
            ORDER BY USAGE_DATE DESC
            LIMIT 15
        """).collect()
        if rows:
            lines = [f"DAILY CREDIT TREND FOR {warehouse_name}:"]
            for r in rows:
                lines.append(f"  {r['USAGE_DATE']}: total={r['TOTAL_CREDITS']:.2f}, "
                             f"compute={r['COMPUTE_CREDITS']:.2f}, cs={r['CS_CREDITS']:.2f}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"DAILY TREND: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT SUM(CREDITS_USED) AS TOTAL_CREDITS,
                   SUM(CREDITS_USED_COMPUTE) AS COMPUTE_CREDITS,
                   SUM(CREDITS_USED_CLOUD_SERVICES) AS CS_CREDITS,
                   AVG(CREDITS_USED) AS AVG_HOURLY,
                   MAX(CREDITS_USED) AS PEAK_HOURLY
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"COST SUMMARY (30d): total={r['TOTAL_CREDITS']:.2f}, "
                            f"compute={r['COMPUTE_CREDITS']:.2f}, cs={r['CS_CREDITS']:.2f}, "
                            f"avg_hourly={r['AVG_HOURLY']:.4f}, peak_hourly={r['PEAK_HOURLY']:.4f}")
    except Exception as e:
        sections.append(f"COST SUMMARY: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT SUM(CREDITS_USED) AS TOTAL_30D
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
        """).collect()
        if rows and rows[0]['TOTAL_30D']:
            projected = float(rows[0]['TOTAL_30D']) * (365.0 / 30.0)
            sections.append(f"ANNUAL PROJECTION: ~{projected:.0f} credits/year (based on 30d trend)")
    except Exception as e:
        sections.append(f"PROJECTION: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_finops_analyzer(entry_actions=None):
    st.markdown("### FinOps Analyzer")
    st.markdown("AI-powered analysis of your Snowflake credit consumption, cost trends, and optimization opportunities.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    model = st.session_state.get("selected_llm", "claude-sonnet-4-6")

    tab_summary, tab_individual = st.tabs(["Summary Analysis", "Individual Cost Analysis"])

    with tab_summary:
        cache_key = f"finops_analysis_result_{model}"

        if cache_key not in st.session_state:
            status_text = st.empty()
            progress_bar = st.empty()
            status_text.text("Gathering data...")
            progress_bar_widget = progress_bar.progress(0)
            progress_bar_widget.progress(0.3)
            data_summary = _gather_data(session)
            status_text.text("Running AI analysis...")
            progress_bar_widget.progress(0.7)
            with st.spinner("Running AI analysis..."):
                prompt = (
                    "You are a Snowflake FinOps expert specializing in cost optimization and credit management. "
                    "Analyze the following cost and usage data from SNOWFLAKE.ACCOUNT_USAGE views. "
                    "Format your response using proper Markdown with ## headers, bullet points (- or *), and bold text (**). "
                    "Provide:\n"
                    "1. **Summary Assessment**: Overall cost health and spend trajectory\n"
                    "2. **Key Findings**: Top cost drivers, trends, anomalies\n"
                    "3. **Recommendations**: Specific cost optimization actions with estimated savings\n"
                    "4. **Risk Areas**: Runaway costs, idle resources, unexpected spikes\n\n"
                    f"DATA:\n{data_summary}"
                )
                result = _call_cortex(session, model, prompt)
                if result == "MODEL_UNAVAILABLE":
                    st.warning(f"The model **{model}** is deprecated or unavailable. Please select a different LLM on the Home page.")
                    return
                st.session_state[cache_key] = result
            progress_bar.empty()
            status_text.empty()

        if cache_key in st.session_state:
            st.markdown("---")
            raw_text = st.session_state[cache_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

    with tab_individual:
        entity_cache = "fin_entity_list"
        if entity_cache not in st.session_state:
            try:
                rows = session.sql("""
                    SELECT DISTINCT WAREHOUSE_NAME
                    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
                    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                    ORDER BY WAREHOUSE_NAME
                """).collect()
                st.session_state[entity_cache] = [r[0] for r in rows] if rows else []
            except Exception:
                st.session_state[entity_cache] = []

        entities = st.session_state[entity_cache]
        if not entities:
            st.info("No warehouses found.")
            return

        selected = st.selectbox("Warehouse Name", entities, key="fin_entity_select")

        if st.button("Analyze", key="fin_indiv_btn", type="primary"):
            indiv_key = f"fin_indiv_{selected}"
            _prog = st.progress(0)
            _stat = st.empty()
            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Gathering data...</p>', unsafe_allow_html=True)
            _prog.progress(30)
            data_summary = _gather_individual_data(session, selected)

            try:
                met_rows = session.sql(f"""
                    SELECT ROUND(SUM(CREDITS_USED), 2) AS TOTAL_CREDITS,
                           ROUND(SUM(CREDITS_USED_COMPUTE), 2) AS COMPUTE_CREDITS,
                           ROUND(SUM(CREDITS_USED_CLOUD_SERVICES), 2) AS CS_CREDITS
                    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
                    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                      AND WAREHOUSE_NAME = '{selected}'
                """).collect()
                total_credits = float(met_rows[0]['TOTAL_CREDITS']) if met_rows else 0.0
                compute_credits = float(met_rows[0]['COMPUTE_CREDITS']) if met_rows else 0.0
                cs_credits = float(met_rows[0]['CS_CREDITS']) if met_rows else 0.0
            except Exception:
                total_credits = 0.0
                compute_credits = 0.0
                cs_credits = 0.0

            st.session_state[f"fin_indiv_metrics_{selected}"] = {
                "total": total_credits, "compute": compute_credits, "cs": cs_credits
            }

            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Analyzing with AI...</p>', unsafe_allow_html=True)
            _prog.progress(70)
            prompt = (
                f"You are a Snowflake FinOps expert. "
                f"Analyze the following cost data for warehouse '{selected}'. "
                f"Format your response using proper Markdown with ## headers, bullet points, and bold text. "
                f"Provide:\n"
                f"1. **Cost Summary**: Total spend and breakdown (compute vs cloud services)\n"
                f"2. **Trend Analysis**: Daily credit consumption patterns and anomalies\n"
                f"3. **Cost Projection**: Projected annual cost based on current trends\n"
                f"4. **Optimization Opportunities**: Specific actions to reduce costs\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[indiv_key] = result
            _prog.progress(100)
            _prog.empty()
            _stat.empty()

        indiv_key = f"fin_indiv_{selected}"
        if indiv_key in st.session_state:
            metrics = st.session_state.get(f"fin_indiv_metrics_{selected}", {})
            if metrics:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Credits (30d)", f"{metrics.get('total', 0):.2f}")
                c2.metric("Compute Credits", f"{metrics.get('compute', 0):.2f}")
                c3.metric("CS Credits", f"{metrics.get('cs', 0):.2f}")

            st.markdown("---")
            raw_text = st.session_state[indiv_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

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
Data Transformation Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers query workload and session patterns from ACCOUNT_USAGE and generates
recommendations via SNOWFLAKE.CORTEX.COMPLETE().
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


def _gather_individual_data(session, warehouse_name):
    sections = []

    try:
        rows = session.sql(f"""
            SELECT QUERY_TYPE, COUNT(*) AS CNT,
                   AVG(TOTAL_ELAPSED_TIME) / 1000 AS AVG_ELAPSED_SEC,
                   SUM(CASE WHEN EXECUTION_STATUS != 'SUCCESS' THEN 1 ELSE 0 END) AS ERRORS,
                   SUM(BYTES_SPILLED_TO_LOCAL_STORAGE + BYTES_SPILLED_TO_REMOTE_STORAGE) / POWER(1024,3) AS SPILL_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
            GROUP BY QUERY_TYPE
            ORDER BY CNT DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = [f"QUERY TYPE MIX FOR {warehouse_name}:"]
            for r in rows:
                lines.append(f"  {r['QUERY_TYPE']}: count={r['CNT']}, avg_sec={r['AVG_ELAPSED_SEC']:.1f}, "
                             f"errors={r['ERRORS']}, spill_gb={r['SPILL_GB']:.2f}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"QUERY TYPE MIX: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT EXECUTION_STATUS, COUNT(*) AS CNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
            GROUP BY EXECUTION_STATUS
            ORDER BY CNT DESC
        """).collect()
        if rows:
            lines = ["ERROR DISTRIBUTION:"]
            for r in rows:
                lines.append(f"  {r['EXECUTION_STATUS']}: {r['CNT']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"ERROR DISTRIBUTION: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT COUNT(*) AS TOTAL_QUERIES,
                   SUM(BYTES_SPILLED_TO_LOCAL_STORAGE) / POWER(1024,3) AS LOCAL_SPILL_GB,
                   SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) / POWER(1024,3) AS REMOTE_SPILL_GB,
                   AVG(TOTAL_ELAPSED_TIME) / 1000 AS AVG_ELAPSED_SEC,
                   MAX(TOTAL_ELAPSED_TIME) / 1000 AS MAX_ELAPSED_SEC,
                   COUNT(CASE WHEN TOTAL_ELAPSED_TIME > 300000 THEN 1 END) AS LONG_RUNNING
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"PERFORMANCE SUMMARY: queries={r['TOTAL_QUERIES']}, "
                            f"avg_sec={r['AVG_ELAPSED_SEC']:.1f}, max_sec={r['MAX_ELAPSED_SEC']:.1f}, "
                            f"local_spill_gb={r['LOCAL_SPILL_GB']:.2f}, remote_spill_gb={r['REMOTE_SPILL_GB']:.2f}, "
                            f"long_running={r['LONG_RUNNING']}")
    except Exception as e:
        sections.append(f"PERFORMANCE SUMMARY: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT USER_NAME, COUNT(*) AS CNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
            GROUP BY USER_NAME
            ORDER BY CNT DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["TOP USERS:"]
            for r in rows:
                lines.append(f"  {r['USER_NAME']}: {r['CNT']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"TOP USERS: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_transformation_analyzer(entry_actions=None):
    st.markdown("### Data Transformation Analyzer")
    st.markdown("AI-powered analysis of your query workload, transformation patterns, and error rates.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    model = st.session_state.get("selected_llm", "claude-sonnet-4-6")

    tab_summary, tab_individual = st.tabs(["Summary Analysis", "Individual Workload Analysis"])

    with tab_summary:
        cache_key = f"transformation_analysis_result_{model}"

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
                    "You are a Snowflake expert specializing in data transformation, query optimization, and workload management. "
                    "Analyze the following transformation and query workload data from SNOWFLAKE.ACCOUNT_USAGE views. "
                    "Format your response using proper Markdown with ## headers, bullet points (- or *), and bold text (**). "
                    "Provide:\n"
                    "1. **Summary Assessment**: Overall transformation health and efficiency\n"
                    "2. **Key Findings**: Error-prone query types, spill patterns, client tool usage\n"
                    "3. **Recommendations**: Steps to optimize transformation workloads\n"
                    "4. **Risk Areas**: High error rates, excessive spilling, inefficient patterns\n\n"
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
        entity_cache = "tx_entity_list"
        if entity_cache not in st.session_state:
            try:
                rows = session.sql("""
                    SELECT DISTINCT WAREHOUSE_NAME
                    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                      AND WAREHOUSE_NAME IS NOT NULL
                    ORDER BY WAREHOUSE_NAME
                    LIMIT 50
                """).collect()
                st.session_state[entity_cache] = [r[0] for r in rows] if rows else []
            except Exception:
                st.session_state[entity_cache] = []

        entities = st.session_state[entity_cache]
        if not entities:
            st.info("No warehouses found.")
            return

        selected = st.selectbox("Warehouse Name", entities, key="tx_entity_select")

        if st.button("Analyze", key="tx_indiv_btn", type="primary"):
            indiv_key = f"tx_indiv_{selected}"
            _prog = st.progress(0)
            _stat = st.empty()
            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Gathering data...</p>', unsafe_allow_html=True)
            _prog.progress(30)
            data_summary = _gather_individual_data(session, selected)

            try:
                q_rows = session.sql(f"""
                    SELECT COUNT(*) AS Q_COUNT,
                           SUM(CASE WHEN EXECUTION_STATUS != 'SUCCESS' THEN 1 ELSE 0 END) AS ERR_COUNT
                    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                      AND WAREHOUSE_NAME = '{selected}'
                """).collect()
                q_count = int(q_rows[0]['Q_COUNT']) if q_rows else 0
                err_count = int(q_rows[0]['ERR_COUNT']) if q_rows else 0
            except Exception:
                q_count = 0
                err_count = 0

            st.session_state[f"tx_indiv_metrics_{selected}"] = {
                "queries": q_count, "errors": err_count
            }

            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Analyzing with AI...</p>', unsafe_allow_html=True)
            _prog.progress(70)
            prompt = (
                f"You are a Snowflake expert specializing in query optimization and workload management. "
                f"Analyze the following workload data for warehouse '{selected}'. "
                f"Format your response using proper Markdown with ## headers, bullet points, and bold text. "
                f"Provide:\n"
                f"1. **Workload Profile**: Query type mix and volume patterns\n"
                f"2. **Error Analysis**: Error rates and problematic query types\n"
                f"3. **Performance Issues**: Spilling, long-running queries, bottlenecks\n"
                f"4. **Recommendations**: Specific optimization actions for this workload\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[indiv_key] = result
            _prog.progress(100)
            _prog.empty()
            _stat.empty()

        indiv_key = f"tx_indiv_{selected}"
        if indiv_key in st.session_state:
            metrics = st.session_state.get(f"tx_indiv_metrics_{selected}", {})
            if metrics:
                c1, c2 = st.columns(2)
                c1.metric("Queries (30d)", metrics.get("queries", 0))
                c2.metric("Errors (30d)", metrics.get("errors", 0))

            st.markdown("---")
            raw_text = st.session_state[indiv_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

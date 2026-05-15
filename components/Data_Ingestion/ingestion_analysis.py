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
Data Ingestion Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers data loading and pipe usage metrics from ACCOUNT_USAGE and generates
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


def _gather_individual_data(session, table_fqn):
    sections = []
    parts = table_fqn.split(".")
    if len(parts) == 3:
        db, schema, table = parts[0], parts[1], parts[2]
    else:
        db, schema, table = "", "", table_fqn

    try:
        rows = session.sql(f"""
            SELECT COUNT(*) AS LOAD_COUNT,
                   SUM(ROW_COUNT) AS TOTAL_ROWS,
                   SUM(FILE_SIZE) / POWER(1024,3) AS TOTAL_GB,
                   SUM(CASE WHEN STATUS = 'Loaded' THEN 1 ELSE 0 END) AS SUCCESSFUL,
                   SUM(CASE WHEN STATUS != 'Loaded' THEN 1 ELSE 0 END) AS FAILED,
                   SUM(ERROR_COUNT) AS TOTAL_ERRORS,
                   MIN(LAST_LOAD_TIME) AS FIRST_LOAD,
                   MAX(LAST_LOAD_TIME) AS LAST_LOAD
            FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
            WHERE LAST_LOAD_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND TABLE_CATALOG_NAME = '{db}'
              AND TABLE_SCHEMA_NAME = '{schema}'
              AND TABLE_NAME = '{table}'
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"LOAD SUMMARY (30d): loads={r['LOAD_COUNT']}, rows={r['TOTAL_ROWS']}, "
                            f"gb={r['TOTAL_GB']:.4f}, ok={r['SUCCESSFUL']}, failed={r['FAILED']}, "
                            f"errors={r['TOTAL_ERRORS']}, first={r['FIRST_LOAD']}, last={r['LAST_LOAD']}")
    except Exception as e:
        sections.append(f"LOAD SUMMARY: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT TO_DATE(LAST_LOAD_TIME) AS LOAD_DATE,
                   COUNT(*) AS LOADS,
                   SUM(ROW_COUNT) AS ROWS_LOADED,
                   SUM(ERROR_COUNT) AS ERRORS
            FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
            WHERE LAST_LOAD_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND TABLE_CATALOG_NAME = '{db}'
              AND TABLE_SCHEMA_NAME = '{schema}'
              AND TABLE_NAME = '{table}'
            GROUP BY LOAD_DATE
            ORDER BY LOAD_DATE DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["DAILY LOAD TREND (last 10 days):"]
            for r in rows:
                lines.append(f"  {r['LOAD_DATE']}: loads={r['LOADS']}, rows={r['ROWS_LOADED']}, errors={r['ERRORS']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"DAILY TREND: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT STATUS, COUNT(*) AS CNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
            WHERE LAST_LOAD_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND TABLE_CATALOG_NAME = '{db}'
              AND TABLE_SCHEMA_NAME = '{schema}'
              AND TABLE_NAME = '{table}'
            GROUP BY STATUS
            ORDER BY CNT DESC
        """).collect()
        if rows:
            lines = ["STATUS BREAKDOWN:"]
            for r in rows:
                lines.append(f"  {r['STATUS']}: {r['CNT']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"STATUS BREAKDOWN: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_ingestion_analyzer(entry_actions=None):
    st.markdown("### Data Ingestion Analyzer")
    st.markdown("AI-powered analysis of your data loading patterns, pipe usage, and ingestion efficiency.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    model = st.session_state.get("selected_llm", "claude-sonnet-4-6")

    tab_summary, tab_individual = st.tabs(["Summary Analysis", "Individual Pipeline Analysis"])

    with tab_summary:
        cache_key = f"ingestion_analysis_result_{model}"

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
                    "You are a Snowflake expert specializing in data ingestion and loading optimization. "
                    "Analyze the following ingestion data from SNOWFLAKE.ACCOUNT_USAGE views. "
                    "Format your response using proper Markdown with ## headers, bullet points (- or *), and bold text (**). "
                    "Provide:\n"
                    "1. **Summary Assessment**: Overall ingestion health and efficiency\n"
                    "2. **Key Findings**: Load failures, small file issues, cost patterns\n"
                    "3. **Recommendations**: Steps to improve loading performance and reduce costs\n"
                    "4. **Risk Areas**: High failure rates, inefficient patterns, cost anomalies\n\n"
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
        entity_cache = "ing_entity_list"
        if entity_cache not in st.session_state:
            try:
                rows = session.sql("""
                    SELECT DISTINCT TABLE_CATALOG_NAME || '.' || TABLE_SCHEMA_NAME || '.' || TABLE_NAME AS TABLE_FQN
                    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
                    WHERE LAST_LOAD_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                    ORDER BY TABLE_FQN
                    LIMIT 50
                """).collect()
                st.session_state[entity_cache] = [r[0] for r in rows] if rows else []
            except Exception:
                st.session_state[entity_cache] = []

        entities = st.session_state[entity_cache]
        if not entities:
            st.info("No target tables found.")
            return

        selected = st.selectbox("Target Table", entities, key="ing_entity_select")

        if st.button("Analyze", key="ing_indiv_btn", type="primary"):
            indiv_key = f"ing_indiv_{selected}"
            _prog = st.progress(0)
            _stat = st.empty()
            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Gathering data...</p>', unsafe_allow_html=True)
            _prog.progress(30)
            data_summary = _gather_individual_data(session, selected)

            parts = selected.split(".")
            db = parts[0] if len(parts) == 3 else ""
            schema = parts[1] if len(parts) == 3 else ""
            table = parts[2] if len(parts) == 3 else selected

            try:
                met_rows = session.sql(f"""
                    SELECT COUNT(*) AS LOAD_COUNT,
                           SUM(ROW_COUNT) AS TOTAL_ROWS,
                           SUM(ERROR_COUNT) AS TOTAL_ERRORS
                    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
                    WHERE LAST_LOAD_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                      AND TABLE_CATALOG_NAME = '{db}'
                      AND TABLE_SCHEMA_NAME = '{schema}'
                      AND TABLE_NAME = '{table}'
                """).collect()
                load_count = int(met_rows[0]['LOAD_COUNT']) if met_rows else 0
                total_rows = int(met_rows[0]['TOTAL_ROWS'] or 0) if met_rows else 0
                total_errors = int(met_rows[0]['TOTAL_ERRORS'] or 0) if met_rows else 0
            except Exception:
                load_count = 0
                total_rows = 0
                total_errors = 0

            st.session_state[f"ing_indiv_metrics_{selected}"] = {
                "loads": load_count, "rows": total_rows, "errors": total_errors
            }

            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Analyzing with AI...</p>', unsafe_allow_html=True)
            _prog.progress(70)
            prompt = (
                f"You are a Snowflake expert specializing in data ingestion. "
                f"Analyze the following load data for table '{selected}'. "
                f"Format your response using proper Markdown with ## headers, bullet points, and bold text. "
                f"Provide:\n"
                f"1. **Pipeline Health**: Overall loading health for this table\n"
                f"2. **Error Analysis**: Error patterns and failure rates\n"
                f"3. **Volume Trends**: Loading volume and frequency patterns\n"
                f"4. **Recommendations**: Specific improvements for this pipeline\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[indiv_key] = result
            _prog.progress(100)
            _prog.empty()
            _stat.empty()

        indiv_key = f"ing_indiv_{selected}"
        if indiv_key in st.session_state:
            metrics = st.session_state.get(f"ing_indiv_metrics_{selected}", {})
            if metrics:
                c1, c2, c3 = st.columns(3)
                c1.metric("Loads (30d)", metrics.get("loads", 0))
                c2.metric("Rows Loaded", metrics.get("rows", 0))
                c3.metric("Errors", metrics.get("errors", 0))

            st.markdown("---")
            raw_text = st.session_state[indiv_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

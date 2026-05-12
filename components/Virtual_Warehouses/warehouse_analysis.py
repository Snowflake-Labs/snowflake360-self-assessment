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
        return f"Error calling Cortex: {str(e)}"


def _gather_data(session, progress_bar=None, status_text=None):
    sections = []
    queries = [
        ("Warehouse Inventory", """
            WITH active_fleet AS (
                SELECT
                    q.WAREHOUSE_NAME,
                    q.WAREHOUSE_SIZE,
                    q.WAREHOUSE_TYPE
                FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
                WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
                  AND q.WAREHOUSE_NAME IS NOT NULL
                QUALIFY ROW_NUMBER() OVER (PARTITION BY q.WAREHOUSE_NAME ORDER BY q.START_TIME DESC) = 1
            )
            SELECT WAREHOUSE_NAME, WAREHOUSE_SIZE, WAREHOUSE_TYPE
            FROM active_fleet
            ORDER BY WAREHOUSE_NAME
            LIMIT 25
        """),
        ("Credit Usage (30 days)", """
            SELECT WAREHOUSE_NAME,
                   ROUND(SUM(CREDITS_USED_COMPUTE), 2) AS COMPUTE_CREDITS,
                   ROUND(SUM(CREDITS_ATTRIBUTED_COMPUTE_QUERIES), 2) AS QUERY_CREDITS,
                   ROUND(SUM(CREDITS_USED_COMPUTE) - SUM(CREDITS_ATTRIBUTED_COMPUTE_QUERIES), 2) AS IDLE_CREDITS,
                   ROUND(DIV0(SUM(CREDITS_USED_COMPUTE) - SUM(CREDITS_ATTRIBUTED_COMPUTE_QUERIES),
                              SUM(CREDITS_USED_COMPUTE)) * 100, 1) AS IDLE_PCT
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND CREDITS_USED_COMPUTE > 0
            GROUP BY WAREHOUSE_NAME
            ORDER BY COMPUTE_CREDITS DESC
            LIMIT 15
        """),
        ("Query Load (30 days)", """
            SELECT WAREHOUSE_NAME,
                   ROUND(AVG(AVG_RUNNING), 2) AS AVG_RUNNING,
                   ROUND(AVG(AVG_QUEUED_LOAD), 2) AS AVG_QUEUED,
                   ROUND(AVG(AVG_BLOCKED), 2) AS AVG_BLOCKED,
                   COUNT(*) AS LOAD_RECORDS
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY WAREHOUSE_NAME
            ORDER BY AVG_RUNNING DESC
            LIMIT 15
        """),
        ("Spilling & Long Queries (30 days)", """
            SELECT WAREHOUSE_NAME,
                   COUNT(*) AS QUERY_COUNT,
                   ROUND(AVG(TOTAL_ELAPSED_TIME) / 1000, 1) AS AVG_DURATION_SEC,
                   SUM(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 ELSE 0 END) AS LOCAL_SPILL_COUNT,
                   SUM(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 ELSE 0 END) AS REMOTE_SPILL_COUNT,
                   COUNT(CASE WHEN TOTAL_ELAPSED_TIME > 300000 THEN 1 END) AS LONG_RUNNING_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IS NOT NULL
              AND EXECUTION_STATUS = 'SUCCESS'
            GROUP BY WAREHOUSE_NAME
            ORDER BY QUERY_COUNT DESC
            LIMIT 15
        """),
    ]
    total = len(queries) + 1
    for i, (label, sql) in enumerate(queries):
        if status_text is not None:
            status_text.text(f"Gathering data... ({i+1}/{total-1}: {label})")
        if progress_bar is not None:
            progress_bar.progress((i + 1) / total)
        try:
            rows = session.sql(sql).collect()
            if rows:
                col_names = [desc.name for desc in rows[0]._fields] if hasattr(rows[0], '_fields') else list(rows[0].asDict().keys())
                lines = [f"{label.upper()}:"]
                for r in rows:
                    d = r.asDict() if hasattr(r, 'asDict') else dict(r)
                    parts = [f"{k}={v}" for k, v in d.items()]
                    lines.append("  " + ", ".join(parts))
                sections.append("\n".join(lines))
            else:
                sections.append(f"{label}: No data")
        except Exception as e:
            sections.append(f"{label}: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def _gather_individual_data(session, warehouse_name):
    sections = []

    try:
        rows = session.sql(f"""
            SELECT ROUND(SUM(CREDITS_USED_COMPUTE), 2) AS COMPUTE_CREDITS,
                   ROUND(SUM(CREDITS_USED_CLOUD_SERVICES), 2) AS CS_CREDITS,
                   ROUND(SUM(CREDITS_USED), 2) AS TOTAL_CREDITS,
                   ROUND(DIV0(SUM(CREDITS_USED_COMPUTE) - SUM(CREDITS_ATTRIBUTED_COMPUTE_QUERIES),
                              SUM(CREDITS_USED_COMPUTE)) * 100, 1) AS IDLE_PCT
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"CREDITS (30d): compute={r['COMPUTE_CREDITS']}, cs={r['CS_CREDITS']}, "
                            f"total={r['TOTAL_CREDITS']}, idle_pct={r['IDLE_PCT']}%")
    except Exception as e:
        sections.append(f"CREDITS: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT ROUND(AVG(AVG_RUNNING), 2) AS AVG_RUNNING,
                   ROUND(AVG(AVG_QUEUED_LOAD), 2) AS AVG_QUEUED,
                   ROUND(AVG(AVG_BLOCKED), 2) AS AVG_BLOCKED
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"LOAD (30d): avg_running={r['AVG_RUNNING']}, avg_queued={r['AVG_QUEUED']}, avg_blocked={r['AVG_BLOCKED']}")
    except Exception as e:
        sections.append(f"LOAD: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT COUNT(*) AS QUERY_COUNT,
                   ROUND(AVG(TOTAL_ELAPSED_TIME) / 1000, 1) AS AVG_DURATION_SEC,
                   SUM(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 ELSE 0 END) AS LOCAL_SPILL,
                   SUM(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 ELSE 0 END) AS REMOTE_SPILL,
                   SUM(BYTES_SPILLED_TO_LOCAL_STORAGE) / POWER(1024,3) AS LOCAL_SPILL_GB,
                   SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) / POWER(1024,3) AS REMOTE_SPILL_GB,
                   COUNT(CASE WHEN TOTAL_ELAPSED_TIME > 300000 THEN 1 END) AS LONG_RUNNING
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
              AND EXECUTION_STATUS = 'SUCCESS'
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"QUERIES (30d): count={r['QUERY_COUNT']}, avg_sec={r['AVG_DURATION_SEC']}, "
                            f"local_spill={r['LOCAL_SPILL']}({r['LOCAL_SPILL_GB']:.2f}GB), "
                            f"remote_spill={r['REMOTE_SPILL']}({r['REMOTE_SPILL_GB']:.2f}GB), "
                            f"long_running={r['LONG_RUNNING']}")
    except Exception as e:
        sections.append(f"QUERIES: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT QUERY_TYPE, COUNT(*) AS CNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME = '{warehouse_name}'
            GROUP BY QUERY_TYPE
            ORDER BY CNT DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["QUERY TYPE MIX:"]
            for r in rows:
                lines.append(f"  {r['QUERY_TYPE']}: {r['CNT']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"QUERY TYPE MIX: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_warehouse_analysis(entry_actions=None):
    st.markdown("### Virtual Warehouse Analyzer")
    st.markdown("AI-powered analysis of warehouse sizing, credit usage, and performance patterns.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    model = st.session_state.get("selected_llm", "claude-3-7-sonnet")

    tab_summary, tab_individual = st.tabs(["Summary Analysis", "Individual Warehouse Analysis"])

    with tab_summary:
        cache_key = "wh_analysis_result"

        if cache_key not in st.session_state:
            status_text = st.empty()
            progress_bar = st.empty()
            status_text.markdown(
                f'<p style="color: {TEXT_HEADING}; font-weight: 600;">Loading Warehouse Analyzer...</p>',
                unsafe_allow_html=True
            )
            progress_bar_widget = progress_bar.progress(0)
            data_summary = _gather_data(session, progress_bar=progress_bar_widget, status_text=status_text)
            status_text.text("Running AI analysis...")
            progress_bar_widget.progress(0.9)
            with st.spinner("Running AI analysis..."):
                prompt = (
                    "You are a Snowflake expert specializing in warehouse management and performance optimization. "
                    "Analyze the following warehouse data from SNOWFLAKE.ACCOUNT_USAGE views. "
                    "Format your response using proper Markdown with headers (##), bullet points (- or *), "
                    "and bold text (**). Structure your analysis as follows:\n\n"
                    "## Summary Assessment\nOverall health of the warehouse estate\n\n"
                    "## Sizing Recommendations\n- Warehouses that may be over- or under-sized (use bullet points)\n\n"
                    "## Idle & Waste Analysis\n- Warehouses with high idle percentages\n\n"
                    "## Performance Concerns\n- Queuing, blocking, spilling, or long-running query patterns\n\n"
                    "## Cost Optimization\n- Specific, actionable steps to reduce credit consumption\n\n"
                    f"DATA:\n{data_summary}"
                )
                result = _call_cortex(session, model, prompt)
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
        entity_cache = "wh_entity_list"
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

        selected = st.selectbox("Warehouse Name", entities, key="wh_entity_select")

        if st.button("Analyze", key="wh_indiv_btn", type="secondary"):
            indiv_key = f"wh_indiv_{selected}"
            _prog = st.progress(0)
            _stat = st.empty()
            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Gathering data...</p>', unsafe_allow_html=True)
            _prog.progress(30)
            data_summary = _gather_individual_data(session, selected)

            try:
                met_rows = session.sql(f"""
                    SELECT ROUND(SUM(CREDITS_USED), 2) AS TOTAL_CREDITS,
                           COUNT(*) AS METERING_RECORDS
                    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
                    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                      AND WAREHOUSE_NAME = '{selected}'
                """).collect()
                total_credits = float(met_rows[0]['TOTAL_CREDITS']) if met_rows else 0.0
            except Exception:
                total_credits = 0.0

            try:
                q_rows = session.sql(f"""
                    SELECT COUNT(*) AS Q_COUNT
                    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                      AND WAREHOUSE_NAME = '{selected}'
                """).collect()
                q_count = int(q_rows[0]['Q_COUNT']) if q_rows else 0
            except Exception:
                q_count = 0

            st.session_state[f"wh_indiv_metrics_{selected}"] = {
                "credits": total_credits, "queries": q_count
            }

            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Analyzing with AI...</p>', unsafe_allow_html=True)
            _prog.progress(70)
            prompt = (
                f"You are a Snowflake expert specializing in warehouse performance optimization. "
                f"Analyze the following data for warehouse '{selected}'. "
                f"Format your response using proper Markdown with ## headers, bullet points, and bold text. "
                f"Provide:\n"
                f"1. **Warehouse Health**: Overall performance assessment\n"
                f"2. **Credit Efficiency**: Idle vs active credit usage\n"
                f"3. **Query Performance**: Spilling, duration, long-running queries\n"
                f"4. **Sizing Assessment**: Whether this warehouse is right-sized\n"
                f"5. **Recommendations**: Specific optimization actions\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[indiv_key] = result
            _prog.progress(100)
            _prog.empty()
            _stat.empty()

        indiv_key = f"wh_indiv_{selected}"
        if indiv_key in st.session_state:
            metrics = st.session_state.get(f"wh_indiv_metrics_{selected}", {})
            if metrics:
                c1, c2 = st.columns(2)
                c1.metric("Credits (30d)", f"{metrics.get('credits', 0):.2f}")
                c2.metric("Queries (30d)", metrics.get("queries", 0))

            st.markdown("---")
            raw_text = st.session_state[indiv_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

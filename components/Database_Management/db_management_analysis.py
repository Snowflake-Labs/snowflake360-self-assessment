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
Database Management Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers storage and database metadata from ACCOUNT_USAGE and generates
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


def _gather_data(session, progress_bar=None, status_text=None):
    sections = []
    queries = [
        ("Storage Metrics", """
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
        """),
        ("Database Summary", """
            SELECT COUNT(*) AS DB_COUNT,
                   AVG(DATEDIFF('day', CREATED, CURRENT_TIMESTAMP())) AS AVG_AGE_DAYS,
                   MAX(DATEDIFF('day', CREATED, CURRENT_TIMESTAMP())) AS MAX_AGE_DAYS,
                   SUM(CASE WHEN IS_TRANSIENT = 'YES' THEN 1 ELSE 0 END) AS TRANSIENT_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
            WHERE DELETED IS NULL
        """),
        ("Clustering History", """
            SELECT TABLE_NAME,
                   SUM(CREDITS_USED) AS TOTAL_CREDITS,
                   SUM(NUM_BYTES_RECLUSTERED) / POWER(1024,3) AS RECLUSTERED_GB,
                   COUNT(*) AS OPERATIONS
            FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY TABLE_NAME
            ORDER BY TOTAL_CREDITS DESC
            LIMIT 10
        """),
    ]
    total = len(queries) + 1
    for i, (label, sql) in enumerate(queries):
        if status_text is not None:
            status_text.text(f"Gathering data... ({i+1}/{total-1} queries: {label})")
        if progress_bar is not None:
            progress_bar.progress((i + 1) / total)
        try:
            rows = session.sql(sql).collect()
            if label == "Storage Metrics" and rows:
                lines = ["TOP 10 TABLES BY STORAGE (GB):"]
                for r in rows:
                    lines.append(f"  {r['DATABASE_NAME']}.{r['SCHEMA_NAME']}.{r['TABLE_NAME']}: "
                                 f"active={r['ACTIVE_GB']:.2f}, tt={r['TIME_TRAVEL_GB']:.2f}, "
                                 f"failsafe={r['FAILSAFE_GB']:.2f}, total={r['TOTAL_GB']:.2f}")
                sections.append("\n".join(lines))
            elif label == "Database Summary" and rows:
                r = rows[0]
                sections.append(f"DATABASES: count={r['DB_COUNT']}, avg_age_days={r['AVG_AGE_DAYS']:.0f}, "
                                f"max_age_days={r['MAX_AGE_DAYS']:.0f}, transient={r['TRANSIENT_COUNT']}")
            elif label == "Clustering History":
                if rows:
                    lines = ["AUTO-CLUSTERING (last 30 days, top 10 by credits):"]
                    for r in rows:
                        lines.append(f"  {r['TABLE_NAME']}: credits={r['TOTAL_CREDITS']:.2f}, "
                                     f"reclustered_gb={r['RECLUSTERED_GB']:.2f}, ops={r['OPERATIONS']}")
                    sections.append("\n".join(lines))
                else:
                    sections.append("AUTO-CLUSTERING: No clustering activity in last 30 days")
        except Exception as e:
            sections.append(f"{label}: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def _gather_individual_data(session, database_name):
    sections = []

    try:
        rows = session.sql(f"""
            SELECT COUNT(*) AS TABLE_COUNT,
                   COUNT(DISTINCT TABLE_SCHEMA) AS SCHEMA_COUNT,
                   SUM(CASE WHEN TABLE_TYPE = 'BASE TABLE' THEN 1 ELSE 0 END) AS BASE_TABLES,
                   SUM(CASE WHEN TABLE_TYPE = 'VIEW' THEN 1 ELSE 0 END) AS VIEWS,
                   SUM(CASE WHEN TABLE_TYPE = 'MATERIALIZED VIEW' THEN 1 ELSE 0 END) AS MAT_VIEWS
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE TABLE_CATALOG = '{database_name}'
              AND DELETED IS NULL
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"TABLE INVENTORY: tables={r['TABLE_COUNT']}, schemas={r['SCHEMA_COUNT']}, "
                            f"base_tables={r['BASE_TABLES']}, views={r['VIEWS']}, mat_views={r['MAT_VIEWS']}")
    except Exception as e:
        sections.append(f"TABLE INVENTORY: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT TABLE_SCHEMA, TABLE_NAME,
                   (ACTIVE_BYTES + TIME_TRAVEL_BYTES + FAILSAFE_BYTES) / POWER(1024,3) AS TOTAL_GB,
                   ACTIVE_BYTES / POWER(1024,3) AS ACTIVE_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
            WHERE TABLE_CATALOG = '{database_name}'
              AND ACTIVE_BYTES > 0
              AND DELETED IS NULL
            ORDER BY TOTAL_GB DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["TOP 10 TABLES BY STORAGE (GB):"]
            for r in rows:
                lines.append(f"  {r['TABLE_SCHEMA']}.{r['TABLE_NAME']}: total={r['TOTAL_GB']:.2f}, active={r['ACTIVE_GB']:.2f}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"STORAGE METRICS: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT SUM(ACTIVE_BYTES) / POWER(1024,3) AS TOTAL_ACTIVE_GB,
                   SUM(TIME_TRAVEL_BYTES) / POWER(1024,3) AS TOTAL_TT_GB,
                   SUM(FAILSAFE_BYTES) / POWER(1024,3) AS TOTAL_FS_GB
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
            WHERE TABLE_CATALOG = '{database_name}'
              AND DELETED IS NULL
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"STORAGE TOTALS: active={r['TOTAL_ACTIVE_GB']:.2f}GB, "
                            f"time_travel={r['TOTAL_TT_GB']:.2f}GB, failsafe={r['TOTAL_FS_GB']:.2f}GB")
    except Exception as e:
        sections.append(f"STORAGE TOTALS: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT TABLE_NAME,
                   SUM(CREDITS_USED) AS TOTAL_CREDITS,
                   SUM(NUM_BYTES_RECLUSTERED) / POWER(1024,3) AS RECLUSTERED_GB,
                   COUNT(*) AS OPERATIONS
            FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND DATABASE_NAME = '{database_name}'
            GROUP BY TABLE_NAME
            ORDER BY TOTAL_CREDITS DESC
            LIMIT 5
        """).collect()
        if rows:
            lines = ["CLUSTERING ACTIVITY (last 30 days):"]
            for r in rows:
                lines.append(f"  {r['TABLE_NAME']}: credits={r['TOTAL_CREDITS']:.2f}, reclustered_gb={r['RECLUSTERED_GB']:.2f}")
            sections.append("\n".join(lines))
        else:
            sections.append("CLUSTERING: No clustering activity in last 30 days for this database")
    except Exception as e:
        sections.append(f"CLUSTERING: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_db_management_analyzer(entry_actions=None):
    st.markdown("### Database Management Analyzer")
    st.markdown("AI-powered analysis of your database storage, table lifecycle, and clustering patterns.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    model = st.session_state.get("selected_llm", "claude-3-7-sonnet")

    tab_summary, tab_individual = st.tabs(["Summary Analysis", "Individual Database Analysis"])

    with tab_summary:
        cache_key = f"db_mgmt_analysis_result_{model}"

        if cache_key not in st.session_state:
            status_text = st.empty()
            progress_bar = st.empty()
            status_text.markdown(
                f'<p style="color: {TEXT_HEADING}; font-weight: 600;">Loading Database Management Analyzer...</p>',
                unsafe_allow_html=True
            )
            progress_bar_widget = progress_bar.progress(0)
            data_summary = _gather_data(session, progress_bar=progress_bar_widget, status_text=status_text)
            status_text.text("Running AI analysis...")
            progress_bar_widget.progress(0.9)
            with st.spinner("Running AI analysis..."):
                prompt = (
                    "You are a Snowflake expert specializing in database management and storage optimization. "
                    "Analyze the following database and storage data from SNOWFLAKE.ACCOUNT_USAGE views. "
                    "Format your response using proper Markdown with headers (##), bullet points (- or *), "
                    "and bold text (**). Structure your analysis as follows:\n\n"
                    "## Summary Assessment\nOverall health of the database estate\n\n"
                    "## Key Findings\n- Notable patterns, anomalies, or concerns (use bullet points)\n\n"
                    "## Recommendations\n- Specific, actionable optimization steps (use numbered list)\n\n"
                    "## Risk Areas\n- Potential issues that need attention (use bullet points)\n\n"
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
        entity_cache = "db_mgmt_entity_list"
        if entity_cache not in st.session_state:
            try:
                rows = session.sql("SELECT DATABASE_NAME FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES WHERE DELETED IS NULL ORDER BY DATABASE_NAME").collect()
                st.session_state[entity_cache] = [r[0] for r in rows] if rows else []
            except Exception:
                st.session_state[entity_cache] = []

        entities = st.session_state[entity_cache]
        if not entities:
            st.info("No databases found.")
            return

        selected = st.selectbox("Database Name", entities, key="db_mgmt_entity_select")

        if st.button("Analyze", key="db_mgmt_indiv_btn", type="secondary"):
            indiv_key = f"db_mgmt_indiv_{selected}"
            _prog = st.progress(0)
            _stat = st.empty()
            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Gathering data...</p>', unsafe_allow_html=True)
            _prog.progress(30)
            data_summary = _gather_individual_data(session, selected)

            try:
                inv_rows = session.sql(f"""
                    SELECT COUNT(*) AS TABLE_COUNT,
                           COUNT(DISTINCT TABLE_SCHEMA) AS SCHEMA_COUNT
                    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
                    WHERE TABLE_CATALOG = '{selected}' AND DELETED IS NULL
                """).collect()
                tbl_count = inv_rows[0]['TABLE_COUNT'] if inv_rows else 0
                sch_count = inv_rows[0]['SCHEMA_COUNT'] if inv_rows else 0
            except Exception:
                tbl_count = 0
                sch_count = 0

            try:
                stor_rows = session.sql(f"""
                    SELECT COALESCE(SUM(ACTIVE_BYTES),0) / POWER(1024,3) AS TOTAL_GB
                    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
                    WHERE TABLE_CATALOG = '{selected}' AND DELETED IS NULL
                """).collect()
                total_gb = float(stor_rows[0]['TOTAL_GB']) if stor_rows else 0.0
            except Exception:
                total_gb = 0.0

            st.session_state[f"db_mgmt_indiv_metrics_{selected}"] = {
                "tables": tbl_count, "schemas": sch_count, "storage_gb": total_gb
            }

            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Analyzing with AI...</p>', unsafe_allow_html=True)
            _prog.progress(70)
            prompt = (
                f"You are a Snowflake expert specializing in database management. "
                f"Analyze the following data for database '{selected}'. "
                f"Format your response using proper Markdown with ## headers, bullet points, and bold text. "
                f"Provide:\n"
                f"1. **Database Health Summary**: Overall health of this specific database\n"
                f"2. **Storage Analysis**: Storage distribution, large tables, optimization opportunities\n"
                f"3. **Schema & Table Organization**: Table type mix, schema design observations\n"
                f"4. **Clustering Assessment**: Clustering costs and effectiveness\n"
                f"5. **Recommendations**: Specific actions to optimize this database\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[indiv_key] = result
            _prog.progress(100)
            _prog.empty()
            _stat.empty()

        indiv_key = f"db_mgmt_indiv_{selected}"
        if indiv_key in st.session_state:
            metrics = st.session_state.get(f"db_mgmt_indiv_metrics_{selected}", {})
            if metrics:
                c1, c2, c3 = st.columns(3)
                c1.metric("Tables", metrics.get("tables", 0))
                c2.metric("Schemas", metrics.get("schemas", 0))
                c3.metric("Storage (GB)", f"{metrics.get('storage_gb', 0):.2f}")

            st.markdown("---")
            raw_text = st.session_state[indiv_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

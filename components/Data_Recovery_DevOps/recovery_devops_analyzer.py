"""
Data Recovery & DevOps Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers task execution, dynamic table health, and CI/CD patterns from ACCOUNT_USAGE
and generates recommendations via SNOWFLAKE.CORTEX.AI_COMPLETE().
"""

import streamlit as st
import json
from core.config.design_tokens import BRAND_PRIMARY, TEXT_HEADING


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


def _gather_individual_data(session, entity_name):
    sections = []

    try:
        rows = session.sql(f"""
            SELECT STATE, COUNT(*) AS RUN_COUNT,
                   AVG(TIMESTAMPDIFF('second', QUERY_START_TIME, COMPLETED_TIME)) AS AVG_DURATION_SEC,
                   MIN(QUERY_START_TIME) AS FIRST_RUN,
                   MAX(QUERY_START_TIME) AS LAST_RUN
            FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
            WHERE NAME = '{entity_name}'
              AND QUERY_START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY STATE
            ORDER BY RUN_COUNT DESC
        """).collect()
        if rows:
            lines = [f"TASK RUNS FOR {entity_name}:"]
            for r in rows:
                dur = f"{r['AVG_DURATION_SEC']:.1f}s" if r['AVG_DURATION_SEC'] else "N/A"
                lines.append(f"  {r['STATE']}: runs={r['RUN_COUNT']}, avg_duration={dur}, "
                             f"first={r['FIRST_RUN']}, last={r['LAST_RUN']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"TASK RUNS: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT COUNT(*) AS REFRESH_COUNT,
                   SUM(CASE WHEN REFRESH_ACTION = 'INCREMENTAL' THEN 1 ELSE 0 END) AS INCREMENTAL,
                   SUM(CASE WHEN REFRESH_ACTION = 'FULL' THEN 1 ELSE 0 END) AS FULL_REFRESH,
                   SUM(CASE WHEN STATE != 'SUCCEEDED' THEN 1 ELSE 0 END) AS FAILURES
            FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
            WHERE NAME = '{entity_name}'
              AND DATA_TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        """).collect()
        if rows and rows[0]['REFRESH_COUNT'] and int(rows[0]['REFRESH_COUNT']) > 0:
            r = rows[0]
            sections.append(f"DT REFRESH: total={r['REFRESH_COUNT']}, incr={r['INCREMENTAL']}, "
                            f"full={r['FULL_REFRESH']}, failures={r['FAILURES']}")
    except Exception as e:
        sections.append(f"DT REFRESH: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT TO_DATE(QUERY_START_TIME) AS RUN_DATE,
                   COUNT(*) AS RUNS,
                   SUM(CASE WHEN STATE = 'SUCCEEDED' THEN 1 ELSE 0 END) AS SUCCESS,
                   SUM(CASE WHEN STATE = 'FAILED' THEN 1 ELSE 0 END) AS FAILED
            FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
            WHERE NAME = '{entity_name}'
              AND QUERY_START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY RUN_DATE
            ORDER BY RUN_DATE DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["DAILY RUN TREND (last 10 days):"]
            for r in rows:
                lines.append(f"  {r['RUN_DATE']}: runs={r['RUNS']}, success={r['SUCCESS']}, failed={r['FAILED']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"DAILY TREND: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_recovery_devops_analyzer(entry_actions=None):
    st.markdown("### Data Recovery & DevOps Analyzer")
    st.markdown("AI-powered analysis of task orchestration, dynamic tables, and CI/CD patterns.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    model = st.session_state.get("selected_llm", "claude-3-7-sonnet")

    tab_summary, tab_individual = st.tabs(["Summary Analysis", "Individual Task Analysis"])

    with tab_summary:
        cache_key = "recovery_devops_analysis_result"

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
                    "You are a Snowflake expert specializing in DevOps, task orchestration, dynamic tables, and CI/CD practices. "
                    "Analyze the following data from SNOWFLAKE.ACCOUNT_USAGE views. "
                    "Format your response using proper Markdown with ## headers, bullet points (- or *), and bold text (**). "
                    "Provide:\n"
                    "1. **Summary Assessment**: Overall operational health and DevOps maturity\n"
                    "2. **Key Findings**: Task failures, DT refresh issues, CI/CD adoption level\n"
                    "3. **Recommendations**: Steps to improve reliability and DevOps practices\n"
                    "4. **Risk Areas**: Failing tasks, full-refresh DTs, missing CI/CD patterns\n\n"
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
        entity_cache = "rd_entity_list"
        if entity_cache not in st.session_state:
            try:
                rows = session.sql("""
                    SELECT DISTINCT NAME AS ENTITY_NAME FROM (
                        SELECT NAME FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
                        WHERE QUERY_START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                        UNION
                        SELECT NAME FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
                        WHERE DATA_TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                    ) ORDER BY ENTITY_NAME LIMIT 50
                """).collect()
                st.session_state[entity_cache] = [r[0] for r in rows] if rows else []
            except Exception:
                st.session_state[entity_cache] = []

        entities = st.session_state[entity_cache]
        if not entities:
            st.info("No tasks or dynamic tables found.")
            return

        selected = st.selectbox("Task / Dynamic Table", entities, key="rd_entity_select")

        if st.button("Analyze", key="rd_indiv_btn"):
            indiv_key = f"rd_indiv_{selected}"
            _prog = st.progress(0)
            _stat = st.empty()
            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Gathering data...</p>', unsafe_allow_html=True)
            _prog.progress(30)
            data_summary = _gather_individual_data(session, selected)

            try:
                t_rows = session.sql(f"""
                    SELECT COUNT(*) AS TOTAL_RUNS,
                           SUM(CASE WHEN STATE = 'SUCCEEDED' THEN 1 ELSE 0 END) AS SUCCESS,
                           SUM(CASE WHEN STATE = 'FAILED' THEN 1 ELSE 0 END) AS FAILED
                    FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
                    WHERE NAME = '{selected}'
                      AND QUERY_START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                """).collect()
                total_runs = int(t_rows[0]['TOTAL_RUNS']) if t_rows else 0
                success = int(t_rows[0]['SUCCESS']) if t_rows else 0
                failed = int(t_rows[0]['FAILED']) if t_rows else 0
            except Exception:
                total_runs = 0
                success = 0
                failed = 0

            st.session_state[f"rd_indiv_metrics_{selected}"] = {
                "total": total_runs, "success": success, "failed": failed
            }

            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Analyzing with AI...</p>', unsafe_allow_html=True)
            _prog.progress(70)
            prompt = (
                f"You are a Snowflake expert specializing in task orchestration and DevOps. "
                f"Analyze the following run data for task/dynamic table '{selected}'. "
                f"Format your response using proper Markdown with ## headers, bullet points, and bold text. "
                f"Provide:\n"
                f"1. **Entity Health**: Overall health and reliability\n"
                f"2. **Run Analysis**: Success/failure rates and duration patterns\n"
                f"3. **Trend Assessment**: Are things improving or degrading?\n"
                f"4. **Recommendations**: Specific improvements for this entity\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[indiv_key] = result
            _prog.progress(100)
            _prog.empty()
            _stat.empty()

        indiv_key = f"rd_indiv_{selected}"
        if indiv_key in st.session_state:
            metrics = st.session_state.get(f"rd_indiv_metrics_{selected}", {})
            if metrics:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Runs (30d)", metrics.get("total", 0))
                c2.metric("Succeeded", metrics.get("success", 0))
                c3.metric("Failed", metrics.get("failed", 0))

            st.markdown("---")
            raw_text = st.session_state[indiv_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

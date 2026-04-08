import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from .dcm_adoption import comp_dcm_adoption
from .git_integration import comp_git_integration
from .cicd_automation import comp_cicd_automation
from .declarative_pipeline import comp_declarative_pipeline


def _cached_sql(cache_key, sql):
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        df = session.sql(sql).to_pandas()
    except Exception:
        df = pd.DataFrame()
    st.session_state[cache_key] = df
    return df


_DCM_ADOPTION_SQL = """
SELECT
    CASE
        WHEN query_text ILIKE '%CREATE OR ALTER%' THEN 'Declarative (DevOps Pattern)'
        WHEN query_text ILIKE '%EXECUTE IMMEDIATE FROM%' THEN 'Deployment from File/Git'
        ELSE 'Imperative (Standard DDL)'
    END AS ddl_pattern,
    COUNT(*) AS execution_count,
    COUNT(DISTINCT user_name) AS distinct_users
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type IN ('CREATE_TABLE', 'ALTER_TABLE', 'EXECUTE_IMMEDIATE')
  AND execution_status = 'SUCCESS'
GROUP BY ALL
ORDER BY 2 DESC
"""

_GIT_INTEGRATION_SQL = """
SELECT
    'Git Operation' AS category,
    CASE
        WHEN query_text ILIKE '%ALTER GIT REPOSITORY%FETCH%' THEN 'Git Fetch (Update)'
        WHEN query_text ILIKE '%FROM @%branches/%' OR query_text ILIKE '%FROM @%tags/%' THEN 'Execution from Git'
        ELSE 'Other'
    END AS operation_type,
    COUNT(*) AS count_ops
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (
      query_text ILIKE '%ALTER GIT REPOSITORY%'
      OR query_text ILIKE '%FROM @%'
  )
GROUP BY ALL
"""

_CICD_AUTOMATION_SQL = """
SELECT
    CASE
        WHEN s.client_application_id ILIKE '%GitHub%' THEN 'GitHub Actions'
        WHEN s.client_application_id ILIKE '%GitLab%' THEN 'GitLab CI'
        WHEN s.client_application_id ILIKE '%Jenkins%' THEN 'Jenkins'
        WHEN s.client_application_id ILIKE '%Terraform%' THEN 'Terraform'
        WHEN s.client_application_id ILIKE '%Schemachange%' THEN 'Schemachange'
        WHEN q.user_name ILIKE '%SVC_%' OR q.user_name ILIKE '%CI_%' THEN 'Service Account (Generic)'
        ELSE 'Human / Other'
    END AS deployment_agent,
    COUNT(DISTINCT s.session_id) AS session_count,
    COUNT(DISTINCT q.query_id) AS ddl_operations_count
FROM SNOWFLAKE.ACCOUNT_USAGE.sessions s
JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
    ON s.session_id = q.session_id
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (
      q.query_type ILIKE 'CREATE%' OR
      q.query_type ILIKE 'ALTER%' OR
      q.query_type ILIKE 'DROP%' OR
      q.query_type ILIKE 'GRANT%'
  )
GROUP BY all
ORDER BY 3 DESC
"""

_DECLARATIVE_PIPELINE_SQL = """
WITH dt_usage AS (
    SELECT 'Dynamic Tables (Declarative)' AS type, COUNT(*) as activity_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.dynamic_table_refresh_history
    WHERE data_timestamp >= DATEADD('day', -7, CURRENT_TIMESTAMP())
),
task_usage AS (
    SELECT 'Tasks (Imperative)' AS type, COUNT(*) as activity_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.task_history
    WHERE scheduled_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
),
aggr AS (
    SELECT * FROM dt_usage
    UNION ALL
    SELECT * FROM task_usage
)
SELECT a.* FROM aggr a
"""

_DEVOPS_GIT_COUNT_SQL = """
SELECT COUNT(DISTINCT user_name) AS git_users
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
  AND (query_text ILIKE '%CREATE GIT REPOSITORY%' OR query_text ILIKE '%ALTER GIT REPOSITORY%'
       OR query_text ILIKE '%EXECUTE IMMEDIATE FROM%')
"""

_DEVOPS_CICD_COUNT_SQL = """
SELECT COUNT(DISTINCT user_name) AS cicd_users
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
  AND (reported_client_type ILIKE '%PYTHON%' OR reported_client_type ILIKE '%JDBC%'
       OR reported_client_type ILIKE '%GO%' OR reported_client_type ILIKE '%ODBC%')
  AND query_type IN ('CREATE_TABLE', 'CREATE_VIEW', 'ALTER_TABLE', 'DROP_TABLE')
"""

_DEVOPS_DT_COUNT_SQL = """
SELECT COUNT(*) AS dt_count
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE table_type = 'DYNAMIC TABLE' AND deleted IS NULL
"""

_DEVOPS_TASK_COUNT_SQL = """
SELECT COUNT(*) AS task_count
FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
WHERE scheduled_time >= DATEADD('day', -30, CURRENT_DATE)
"""

_DEVOPS_COMBINED_SQL = """
SELECT
    'DDL Operations' AS category, COUNT(*) AS activity_count
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
  AND query_type IN ('CREATE_TABLE', 'CREATE_VIEW', 'ALTER_TABLE', 'DROP_TABLE', 'CREATE_SCHEMA', 'DROP_SCHEMA')
UNION ALL
SELECT 'Task Executions', COUNT(*)
FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
WHERE scheduled_time >= DATEADD('day', -30, CURRENT_DATE)
UNION ALL
SELECT 'Dynamic Table Refreshes', COUNT(*)
FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
WHERE refresh_start_time >= DATEADD('day', -30, CURRENT_DATE)
ORDER BY activity_count DESC
"""

_ALL_DEVOPS_QUERIES = {
    "rd_dcm_adoption": _DCM_ADOPTION_SQL,
    "rd_git_integration": _GIT_INTEGRATION_SQL,
    "rd_cicd_automation": _CICD_AUTOMATION_SQL,
    "rd_declarative_pipeline": _DECLARATIVE_PIPELINE_SQL,
    "devops_git_count": _DEVOPS_GIT_COUNT_SQL,
    "devops_cicd_count": _DEVOPS_CICD_COUNT_SQL,
    "devops_dt_count": _DEVOPS_DT_COUNT_SQL,
    "devops_task_count": _DEVOPS_TASK_COUNT_SQL,
    "devops_combined": _DEVOPS_COMBINED_SQL,
}


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_devops_queries(progress_bar=None, status_text=None):
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_DEVOPS_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    total = len(needed)
    completed = 0
    for k, sql in needed.items():
        key, df, err = _run_query_thread(session, k, sql)
        st.session_state[key] = df
        completed += 1
        if progress_bar is not None:
            progress_bar.progress(completed / total)
        if status_text is not None:
            status_text.text(f"Loading data... ({completed}/{total} queries)")


def comp_recovery_devops_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in _ALL_DEVOPS_QUERIES)
        if not all_cached:
            status_ph.markdown(
                '<p style="color: #003D73; font-weight: 600;">Loading Data Recovery & DevOps data...</p>',
                unsafe_allow_html=True)
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_all_devops_queries(progress_bar=progress_bar_widget, status_text=status_ph)
            progress_ph.empty()
            status_ph.empty()
        else:
            _prefetch_all_devops_queries()
        tab_dcm, tab_git, tab_cicd, tab_pipeline, tab_summary = st.tabs([
            "Database Change Management (DCM) Adoption",
            "Git Integration Usage",
            "CI/CD Tool Automation",
            "Declarative Pipeline Adoption (Dynamic Tables)",
            "DevOps Summary"
        ])

        with tab_dcm:
            comp_dcm_adoption()

        with tab_git:
            comp_git_integration()

        with tab_cicd:
            comp_cicd_automation()

        with tab_pipeline:
            comp_declarative_pipeline()

        with tab_summary:
            _render_devops_summary()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_devops_summary():
    st.markdown("### DevOps Maturity Summary")

    with st.expander("DevOps Maturity Score", expanded=True):
        st.markdown(
            '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
            'ℹ️&nbsp;&nbsp;<b>DevOps Maturity:</b> Composite assessment of Git integration, CI/CD automation, '
            'DCM adoption, and declarative pipeline usage.</div>',
            unsafe_allow_html=True)
        try:
            git_df = st.session_state.get("devops_git_count", pd.DataFrame())
            cicd_df = st.session_state.get("devops_cicd_count", pd.DataFrame())
            dt_df = st.session_state.get("devops_dt_count", pd.DataFrame())
            task_df = st.session_state.get("devops_task_count", pd.DataFrame())

            git_users = int(git_df.iloc[0, 0]) if not git_df.empty else 0
            cicd_users = int(cicd_df.iloc[0, 0]) if not cicd_df.empty else 0
            dt_count = int(dt_df.iloc[0, 0]) if not dt_df.empty else 0
            task_runs = int(task_df.iloc[0, 0]) if not task_df.empty else 0

            git_score = min(25, git_users * 5)
            cicd_score = min(25, cicd_users * 5)
            dt_score = min(25, dt_count * 2)
            task_score = min(25, 25 if task_runs > 100 else int(task_runs * 25 / 100))
            total_score = git_score + cicd_score + dt_score + task_score

            level = 'Advanced' if total_score >= 75 else 'Intermediate' if total_score >= 40 else 'Foundational'
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Overall Score", f"{total_score}/100")
            with col2:
                st.metric("Git Integration", f"{git_score}/25")
            with col3:
                st.metric("CI/CD Automation", f"{cicd_score}/25")
            with col4:
                st.metric("Dynamic Tables", f"{dt_score}/25")
            with col5:
                st.metric("Task Orchestration", f"{task_score}/25")

            categories = ['Git Integration', 'CI/CD Automation', 'Dynamic Tables', 'Task Orchestration']
            scores = [git_score, cicd_score, dt_score, task_score]
            colors = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229']
            fig = go.Figure(go.Bar(x=categories, y=scores, marker_color=colors,
                                   text=scores, textposition='outside'))
            fig.add_hline(y=25, line_dash="dash", line_color="#003D73", annotation_text="Max per category")
            fig.update_layout(title=f'DevOps Maturity: {level} ({total_score}/100)',
                              yaxis_title='Score', height=360, margin=dict(t=50, b=60))
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

    with st.expander("Combined DevOps Dashboard", expanded=True):
        st.markdown(
            '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
            'ℹ️&nbsp;&nbsp;<b>Combined Dashboard:</b> Key DevOps activity metrics over the last 30 days.</div>',
            unsafe_allow_html=True)
        try:
            df = st.session_state.get("devops_combined", pd.DataFrame())
            if df.empty:
                st.info("No DevOps activity data available.")
            else:
                df['ACTIVITY_COUNT'] = pd.to_numeric(df['ACTIVITY_COUNT'], errors='coerce').fillna(0)
                colors = ['#29B5E8', '#11567F', '#75C2D8']
                fig = go.Figure(go.Bar(
                    x=df['CATEGORY'], y=df['ACTIVITY_COUNT'],
                    marker_color=colors[:len(df)],
                    text=df['ACTIVITY_COUNT'].astype(int), textposition='outside'
                ))
                fig.update_layout(title='DevOps Activity (Last 30 Days)', yaxis_title='Count',
                                  height=360, margin=dict(t=50, b=80))
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df)
        except Exception as e:
            st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

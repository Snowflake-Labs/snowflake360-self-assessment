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
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
from .dcm_adoption import comp_dcm_adoption, _ALL_DCM_QUERIES
from .git_integration import comp_git_integration, _ALL_GIT_QUERIES
from .cicd_automation import comp_cicd_automation, _ALL_CICD_QUERIES
from .declarative_pipeline import comp_declarative_pipeline, _ALL_ORCH_QUERIES
from .dbt_projects import comp_dbt_projects

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

_SQL_MATURITY_SCORE = """
WITH metrics AS (
    SELECT
        SUM(CASE WHEN query_text ILIKE '%CREATE OR ALTER%' THEN 1 ELSE 0 END) AS declarative_ddl,
        SUM(CASE WHEN query_text ILIKE '%EXECUTE IMMEDIATE FROM%' THEN 1 ELSE 0 END) AS git_deploys,
        SUM(CASE WHEN query_text ILIKE '%snow dbt%' OR query_text ILIKE '%EXECUTE DBT PROJECT%' THEN 1 ELSE 0 END) AS dcm_deploys,
        COUNT(*) AS total_ddl
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND query_type IN ('CREATE_TABLE','ALTER_TABLE','EXECUTE_IMMEDIATE','CREATE_VIEW')
      AND execution_status = 'SUCCESS'
),
dbt_stats AS (
    SELECT COUNT(*) AS dbt_executions
    FROM SNOWFLAKE.ACCOUNT_USAGE.DBT_PROJECT_EXECUTION_HISTORY
    WHERE QUERY_START_TIME >= DATEADD('day', -30, CURRENT_DATE())
),
dt_stats AS (
    SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END AS has_dynamic_tables
    FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
    WHERE DATA_TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
)
SELECT
    m.declarative_ddl,
    m.git_deploys,
    m.dcm_deploys,
    m.total_ddl,
    d.dbt_executions,
    dt.has_dynamic_tables,
    (CASE WHEN m.declarative_ddl > 0 THEN 1 ELSE 0 END)
      + (CASE WHEN m.git_deploys > 0 THEN 1 ELSE 0 END)
      + (CASE WHEN m.dcm_deploys > 0 THEN 1 ELSE 0 END)
      + (CASE WHEN d.dbt_executions > 0 THEN 1 ELSE 0 END)
      + (CASE WHEN dt.has_dynamic_tables > 0 THEN 1 ELSE 0 END)
      + (CASE WHEN m.declarative_ddl * 100.0 / NULLIF(m.total_ddl, 0) > 50 THEN 1 ELSE 0 END)
    AS maturity_points,
    CASE
        WHEN m.declarative_ddl * 100.0 / NULLIF(m.total_ddl, 0) > 50 AND m.git_deploys > 0 THEN 'ADVANCED'
        WHEN m.declarative_ddl * 100.0 / NULLIF(m.total_ddl, 0) > 20 OR m.git_deploys > 0 THEN 'INTERMEDIATE'
        WHEN m.total_ddl > 0 THEN 'BASIC'
        ELSE 'NO_DATA'
    END AS devops_maturity_level,
    CASE
        WHEN m.declarative_ddl * 100.0 / NULLIF(m.total_ddl, 0) < 20
        THEN 'Adopt CREATE OR ALTER for declarative, idempotent deployments'
        WHEN m.git_deploys = 0
        THEN 'Consider Git integration for version-controlled deployments'
        WHEN d.dbt_executions = 0
        THEN 'Consider deploying dbt projects to Snowflake for managed transformations'
        ELSE 'DevOps practices look mature'
    END AS primary_recommendation
FROM metrics m, dbt_stats d, dt_stats dt
"""

_SQL_SUMMARY_METRICS = """
WITH ddl_patterns AS (
    SELECT
        SUM(CASE WHEN query_text ILIKE '%CREATE OR ALTER%' THEN 1 ELSE 0 END) AS declarative_count,
        SUM(CASE WHEN query_text ILIKE '%EXECUTE IMMEDIATE FROM%' THEN 1 ELSE 0 END) AS git_deploy_count,
        SUM(CASE WHEN query_text ILIKE '%CREATE OR REPLACE%' THEN 1 ELSE 0 END) AS idempotent_count,
        COUNT(*) AS total_ddl
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND query_type IN ('CREATE_TABLE','ALTER_TABLE','EXECUTE_IMMEDIATE','CREATE_VIEW','ALTER_VIEW')
      AND execution_status = 'SUCCESS'
),
automation_stats AS (
    SELECT
        COUNT(DISTINCT CASE
            WHEN s.client_application_id ILIKE '%GitHub%'
                 OR s.client_application_id ILIKE '%GitLab%'
                 OR s.client_application_id ILIKE '%Jenkins%'
                 OR s.client_application_id ILIKE '%Terraform%'
                 OR s.client_application_id ILIKE '%dbt%'
            THEN q.query_id
        END) AS automated_ddl_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
    INNER JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
        ON s.session_id = q.session_id
    WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND (q.query_type ILIKE 'CREATE%' OR q.query_type ILIKE 'ALTER%')
),
orchestration_stats AS (
    SELECT
        (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
         WHERE data_timestamp >= DATEADD('day', -7, CURRENT_TIMESTAMP())) AS dt_refreshes,
        (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
         WHERE scheduled_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())) AS task_runs
)
SELECT 'DDL Patterns' AS metric_category, 'Declarative DDL (CREATE OR ALTER)' AS metric_name, dp.declarative_count AS metric_value,
    ROUND(dp.declarative_count * 100.0 / NULLIF(dp.total_ddl, 0), 1) AS pct_of_total
FROM ddl_patterns dp
UNION ALL
SELECT 'DDL Patterns', 'Git-based Deployments', dp.git_deploy_count,
    ROUND(dp.git_deploy_count * 100.0 / NULLIF(dp.total_ddl, 0), 1)
FROM ddl_patterns dp
UNION ALL
SELECT 'DDL Patterns', 'Idempotent DDL (CREATE OR REPLACE)', dp.idempotent_count,
    ROUND(dp.idempotent_count * 100.0 / NULLIF(dp.total_ddl, 0), 1)
FROM ddl_patterns dp
UNION ALL
SELECT 'Automation', 'CI/CD Automated DDL Operations', ast.automated_ddl_count,
    ROUND(ast.automated_ddl_count * 100.0 / NULLIF((SELECT total_ddl FROM ddl_patterns), 0), 1)
FROM automation_stats ast
UNION ALL
SELECT 'Orchestration', 'Dynamic Table Refreshes (7d)', os.dt_refreshes, NULL
FROM orchestration_stats os
UNION ALL
SELECT 'Orchestration', 'Task Runs (7d)', os.task_runs, NULL
FROM orchestration_stats os
ORDER BY metric_category, metric_name
"""

_ALL_SUMMARY_QUERIES = {
    "rd_maturity_score": _SQL_MATURITY_SCORE,
    "rd_summary_metrics": _SQL_SUMMARY_METRICS,
}

_ALL_DEVOPS_QUERIES = {}
_ALL_DEVOPS_QUERIES.update(_ALL_DCM_QUERIES)
_ALL_DEVOPS_QUERIES.update(_ALL_GIT_QUERIES)
_ALL_DEVOPS_QUERIES.update(_ALL_CICD_QUERIES)
_ALL_DEVOPS_QUERIES.update(_ALL_ORCH_QUERIES)
_ALL_DEVOPS_QUERIES.update(_ALL_SUMMARY_QUERIES)


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
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_run_query_thread, session, k, sql): k
            for k, sql in needed.items()
        }
        for future in as_completed(futures):
            key, df, err = future.result()
            st.session_state[key] = df
            completed += 1
            if progress_bar is not None:
                progress_bar.progress(completed / total)
            if status_text is not None:
                status_text.text(f"Loading data... ({completed}/{total} queries)")


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


def comp_recovery_devops_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in _ALL_DEVOPS_QUERIES)
        if not all_cached:
            status_ph.markdown(
                f'<p style="color:{_C2};font-weight:600;">Loading DevOps data...</p>',
                unsafe_allow_html=True)
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_all_devops_queries(progress_bar=progress_bar_widget, status_text=status_ph)
            progress_ph.empty()
            status_ph.empty()

        tab_dcm, tab_git, tab_cicd, tab_orch, tab_dbt, tab_summary = st.tabs([
            "Database Change Management (DCM) Adoption",
            "Git Integration Usage",
            "CI/CD Tool Automation",
            "Orchestration Patterns",
            "dbt Projects",
            "DevOps Maturity Summary"
        ])

        with tab_dcm:
            comp_dcm_adoption()

        with tab_git:
            comp_git_integration()

        with tab_cicd:
            comp_cicd_automation()

        with tab_orch:
            comp_declarative_pipeline()

        with tab_dbt:
            comp_dbt_projects()

        with tab_summary:
            _render_devops_maturity_summary()

    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid {_CA};padding:10px;">'
            f'Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_devops_maturity_summary():
    score_df = _cached_sql("rd_maturity_score", _SQL_MATURITY_SCORE)

    if score_df.empty:
        st.info("No maturity score data available.")
        return

    row = score_df.iloc[0]
    decl = int(row.iloc[0] or 0)
    git_dep = int(row.iloc[1] or 0)
    dcm_dep = int(row.iloc[2] or 0)
    total_ddl = int(row.iloc[3] or 0)
    dbt_exec = int(row.iloc[4] or 0)
    has_dt = int(row.iloc[5] or 0)
    maturity_pts = int(row.iloc[6] or 0)
    level = str(row.iloc[7])
    recommendation = str(row.iloc[8])

    level_map = {'NO_DATA': 0, 'BASIC': 1, 'INTERMEDIATE': 2, 'ADVANCED': 3}
    score_val = level_map.get(level, 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Maturity Level", level)
    c2.metric("Maturity Points", f"{maturity_pts} / 6")
    c3.metric("Total Successful DDL", f"{total_ddl:,}")
    c4.metric("Declarative DDL", f"{decl:,}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Git Deployments", f"{git_dep:,}")
    c6.metric("dbt Executions", f"{dbt_exec:,}")
    c7.metric("Dynamic Tables", "Yes" if has_dt else "No")
    c8.metric("DCM Deploys", f"{dcm_dep:,}")

    st.markdown("#### Primary Recommendation")
    st.info(recommendation)

    maturity_fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score_val,
        number={"suffix": " / 3"},
        gauge={
            "axis": {"range": [0, 3], "tickmode": "array", "tickvals": [0, 1, 2, 3],
                     "ticktext": ["No Data", "Basic", "Intermediate", "Advanced"]},
            "bar": {"color": _C2},
            "steps": [
                {"range": [0, 1], "color": "#F4FAFD"},
                {"range": [1, 2], "color": _C3},
                {"range": [2, 3], "color": _C1},
            ],
            "threshold": {"line": {"color": _CA, "width": 4}, "thickness": 0.75, "value": score_val},
        },
    ))
    maturity_fig.update_layout(
        height=360, margin=dict(t=120, b=20, l=30, r=30),
        annotations=[dict(text="DevOps Maturity Score", x=0.5, y=1.22,
                          xref="paper", yref="paper", showarrow=False,
                          font=dict(size=17, color=_C2))],
    )
    st.plotly_chart(maturity_fig, use_container_width=True, key="maturity_gauge")

    metrics_df = _cached_sql("rd_summary_metrics", _SQL_SUMMARY_METRICS)
    if not metrics_df.empty:
        metrics_df.columns = ['METRIC_CATEGORY', 'METRIC_NAME', 'METRIC_VALUE', 'PCT_OF_TOTAL']

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("**DevOps Summary Metrics**")
            plot_df = metrics_df.sort_values('METRIC_VALUE', ascending=True)
            cat_colors = {'DDL Patterns': _C2, 'Orchestration': _C1, 'Automation': _C3}
            bar_colors = [cat_colors.get(c, _C1) for c in plot_df['METRIC_CATEGORY']]
            fig = go.Figure(go.Bar(
                y=plot_df['METRIC_NAME'], x=plot_df['METRIC_VALUE'],
                orientation='h', marker_color=bar_colors,
                text=[f"{int(v):,}" if pd.notna(v) else '0' for v in plot_df['METRIC_VALUE']],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Value: %{x:,}<extra></extra>'
            ))
            fig.update_layout(height=400, xaxis_title='Metric Value', showlegend=False,
                              margin=dict(t=20, b=50, l=250, r=50))
            st.plotly_chart(fig, use_container_width=True, key="summary_metrics_bar")

        with col_r:
            st.markdown("**Summary Metric Value Mix**")
            cat_agg = metrics_df.groupby('METRIC_CATEGORY')['METRIC_VALUE'].sum().reset_index()
            cat_agg = cat_agg[cat_agg['METRIC_VALUE'] > 0]
            if not cat_agg.empty:
                colors = [cat_colors.get(c, _C1) for c in cat_agg['METRIC_CATEGORY']]
                fig = go.Figure(go.Pie(
                    labels=cat_agg['METRIC_CATEGORY'], values=cat_agg['METRIC_VALUE'],
                    hole=0.45, marker=dict(colors=colors),
                    textinfo='label+percent', textposition='outside',
                    hovertemplate='<b>%{label}</b><br>Value: %{value:,}<br>%{percent}<extra></extra>'
                ))
                fig.update_layout(height=400, showlegend=True,
                                  legend=dict(orientation='h', y=-0.15, x=0.5, xanchor='center'),
                                  margin=dict(t=20, b=60, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True, key="summary_mix_donut")
            else:
                st.info("No metric data for mix chart.")

        st.dataframe(metrics_df, use_container_width=True)

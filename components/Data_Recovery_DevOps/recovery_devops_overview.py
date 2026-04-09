import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from .dcm_adoption import comp_dcm_adoption, _ALL_DCM_QUERIES
from .git_integration import comp_git_integration, _ALL_GIT_QUERIES
from .cicd_automation import comp_cicd_automation, _ALL_CICD_QUERIES
from .declarative_pipeline import comp_declarative_pipeline, _ALL_ORCH_QUERIES

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

_SQL_MATURITY_SCORE = """
WITH metrics AS (
    SELECT
        SUM(CASE WHEN query_text ILIKE '%CREATE OR ALTER%' THEN 1 ELSE 0 END) AS declarative_ddl,
        SUM(CASE WHEN query_text ILIKE '%EXECUTE IMMEDIATE FROM%' THEN 1 ELSE 0 END) AS git_deploys,
        COUNT(*) AS total_ddl
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND query_type IN ('CREATE_TABLE','ALTER_TABLE','EXECUTE_IMMEDIATE','CREATE_VIEW')
      AND execution_status = 'SUCCESS'
)
SELECT
    declarative_ddl,
    git_deploys,
    total_ddl,
    CASE
        WHEN declarative_ddl * 100.0 / NULLIF(total_ddl, 0) > 50 AND git_deploys > 0 THEN 'ADVANCED'
        WHEN declarative_ddl * 100.0 / NULLIF(total_ddl, 0) > 20 OR git_deploys > 0 THEN 'INTERMEDIATE'
        WHEN total_ddl > 0 THEN 'BASIC'
        ELSE 'NO_DATA'
    END AS devops_maturity_level,
    CASE
        WHEN declarative_ddl * 100.0 / NULLIF(total_ddl, 0) < 20
        THEN 'Adopt CREATE OR ALTER for declarative, idempotent deployments'
        WHEN git_deploys = 0
        THEN 'Consider Git integration for version-controlled deployments'
        ELSE 'DevOps practices look mature'
    END AS primary_recommendation
FROM metrics
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

        tab_dcm, tab_git, tab_cicd, tab_orch, tab_summary = st.tabs([
            "Database Change Management (DCM) Adoption",
            "Git Integration Usage",
            "CI/CD Tool Automation",
            "Orchestration Patterns",
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

    score_df.columns = ['DECLARATIVE_DDL', 'GIT_DEPLOYS', 'TOTAL_DDL', 'DEVOPS_MATURITY_LEVEL', 'PRIMARY_RECOMMENDATION']

    decl = int(score_df.iloc[0]['DECLARATIVE_DDL']) if score_df.iloc[0]['DECLARATIVE_DDL'] else 0
    git_dep = int(score_df.iloc[0]['GIT_DEPLOYS']) if score_df.iloc[0]['GIT_DEPLOYS'] else 0
    total_ddl = int(score_df.iloc[0]['TOTAL_DDL']) if score_df.iloc[0]['TOTAL_DDL'] else 0
    level = str(score_df.iloc[0]['DEVOPS_MATURITY_LEVEL'])
    recommendation = str(score_df.iloc[0]['PRIMARY_RECOMMENDATION'])

    level_map = {'NO_DATA': 0, 'BASIC': 1, 'INTERMEDIATE': 2, 'ADVANCED': 3}
    score_val = level_map.get(level, 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Maturity Level", level)
    c2.metric("Declarative DDL", f"{decl:,}")
    c3.metric("Git Deployments", f"{git_dep:,}")
    c4.metric("Total Successful DDL", f"{total_ddl:,}")

    st.markdown("### Primary Recommendation")
    st.markdown(
        f'<div style="background-color:#e8f4f8;border-left:6px solid {_C1};padding:12px;border-radius:4px;">'
        f'{recommendation}</div>',
        unsafe_allow_html=True)

    st.markdown("")

    st.markdown(
        f'<div style="text-align:center;color:{_C1};font-size:18px;font-weight:600;">DevOps Maturity Score</div>',
        unsafe_allow_html=True)

    theta_vals = np.linspace(0, 180, 100)
    r_vals = [1] * 100
    x_bg = [r * np.cos(np.radians(t)) for r, t in zip(r_vals, theta_vals)]
    y_bg = [r * np.sin(np.radians(t)) for r, t in zip(r_vals, theta_vals)]

    sections = [
        (0, 45, _C3, 'No Data'),
        (45, 90, _CA, 'Basic'),
        (90, 135, _C1, 'Intermediate'),
        (135, 180, _C2, 'Advanced'),
    ]

    fig = go.Figure()
    for start_a, end_a, color, label in sections:
        t = np.linspace(start_a, end_a, 30)
        xs = [0] + [0.95 * np.cos(np.radians(a)) for a in t] + [0]
        ys = [0] + [0.95 * np.sin(np.radians(a)) for a in t] + [0]
        fig.add_trace(go.Scatter(x=xs, y=ys, fill='toself', fillcolor=color,
                                 line=dict(color='white', width=1),
                                 hoverinfo='text', text=label, showlegend=False))
        mid_a = (start_a + end_a) / 2
        lx = 1.12 * np.cos(np.radians(mid_a))
        ly = 1.12 * np.sin(np.radians(mid_a))
        fig.add_annotation(x=lx, y=ly, text=label, showarrow=False,
                           font=dict(size=11, color='#333'))

    needle_angle = 45 * score_val + 22.5
    nx = 0.75 * np.cos(np.radians(needle_angle))
    ny = 0.75 * np.sin(np.radians(needle_angle))
    fig.add_trace(go.Scatter(x=[0, nx], y=[0, ny], mode='lines',
                             line=dict(color=_CA, width=4), showlegend=False))
    fig.add_trace(go.Scatter(x=[0], y=[0], mode='markers',
                             marker=dict(size=10, color=_CA), showlegend=False))

    fig.add_annotation(x=0, y=0.35, text=f"<b>{score_val} / 3</b>",
                       showarrow=False, font=dict(size=36, color='#333'))

    fig.update_layout(
        height=350, xaxis=dict(visible=False, range=[-1.3, 1.3]),
        yaxis=dict(visible=False, range=[-0.2, 1.3], scaleanchor='x'),
        margin=dict(t=20, b=20, l=20, r=20), plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig, use_container_width=True, key="maturity_gauge")

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

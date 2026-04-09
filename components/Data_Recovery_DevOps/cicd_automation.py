import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

_SQL_CICD_SUMMARY = """
SELECT
    CASE
        WHEN s.client_application_id ILIKE '%GitHub%' THEN 'GitHub Actions'
        WHEN s.client_application_id ILIKE '%GitLab%' THEN 'GitLab CI'
        WHEN s.client_application_id ILIKE '%Jenkins%' THEN 'Jenkins'
        WHEN s.client_application_id ILIKE '%Terraform%' THEN 'Terraform'
        WHEN s.client_application_id ILIKE '%Schemachange%' THEN 'Schemachange'
        WHEN s.client_application_id ILIKE '%dbt%' THEN 'dbt'
        WHEN s.client_application_id ILIKE '%Airflow%' THEN 'Airflow'
        WHEN q.user_name ILIKE '%SVC_%' OR q.user_name ILIKE '%CI_%' THEN 'Service Account'
        ELSE 'Human / Other'
    END AS deployment_agent,
    COUNT(DISTINCT s.session_id) AS session_count,
    COUNT(DISTINCT q.query_id) AS ddl_operations_count,
    ROUND(COUNT(DISTINCT q.query_id) * 100.0 / NULLIF(SUM(COUNT(DISTINCT q.query_id)) OVER(), 0), 1) AS pct_of_ddl_ops
FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
INNER JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    ON s.session_id = q.session_id
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (q.query_type ILIKE 'CREATE%'
       OR q.query_type ILIKE 'ALTER%'
       OR q.query_type ILIKE 'DROP%'
       OR q.query_type ILIKE 'GRANT%')
GROUP BY deployment_agent
ORDER BY ddl_operations_count DESC
"""

_SQL_CICD_DETAIL = """
SELECT
    CASE
        WHEN s.client_application_id ILIKE '%GitHub%' THEN 'GitHub Actions'
        WHEN s.client_application_id ILIKE '%GitLab%' THEN 'GitLab CI'
        WHEN s.client_application_id ILIKE '%Jenkins%' THEN 'Jenkins'
        WHEN s.client_application_id ILIKE '%Terraform%' THEN 'Terraform'
        WHEN s.client_application_id ILIKE '%Schemachange%' THEN 'Schemachange'
        WHEN s.client_application_id ILIKE '%dbt%' THEN 'dbt'
        WHEN s.client_application_id ILIKE '%Airflow%' THEN 'Airflow'
        WHEN s.client_application_id ILIKE '%Fivetran%' THEN 'Fivetran'
        WHEN s.client_application_id ILIKE '%Matillion%' THEN 'Matillion'
        WHEN q.user_name ILIKE '%SVC_%' OR q.user_name ILIKE '%CI_%' OR q.user_name ILIKE '%SERVICE%' THEN 'Service Account (Generic)'
        ELSE 'Human / Other'
    END AS deployment_agent,
    s.client_application_id,
    COUNT(DISTINCT s.session_id) AS session_count,
    COUNT(DISTINCT q.query_id) AS ddl_operations_count,
    COUNT(DISTINCT q.user_name) AS distinct_users
FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
INNER JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    ON s.session_id = q.session_id
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (q.query_type ILIKE 'CREATE%'
       OR q.query_type ILIKE 'ALTER%'
       OR q.query_type ILIKE 'DROP%'
       OR q.query_type ILIKE 'GRANT%')
GROUP BY deployment_agent, s.client_application_id
ORDER BY ddl_operations_count DESC
"""

_ALL_CICD_QUERIES = {
    "rd_cicd_summary": _SQL_CICD_SUMMARY,
    "rd_cicd_detail": _SQL_CICD_DETAIL,
}


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


def comp_cicd_automation(entry_actions=None):
    try:
        df = _cached_sql("rd_cicd_summary", _SQL_CICD_SUMMARY)

        if df.empty:
            st.markdown(
                '<div style="background-color:#fff3cd;border-left:6px solid #ffc107;padding:10px;">'
                '⚠️&nbsp;&nbsp;No CI/CD tool data found for the last 30 days.</div>',
                unsafe_allow_html=True)
            return

        df.columns = ['DEPLOYMENT_AGENT', 'SESSION_COUNT', 'DDL_OPERATIONS_COUNT', 'PCT_OF_DDL_OPS']

        total_ops = int(df['DDL_OPERATIONS_COUNT'].sum())
        num_agents = len(df)
        human_row = df.loc[df['DEPLOYMENT_AGENT'] == 'Human / Other']
        automated = total_ops - (int(human_row['DDL_OPERATIONS_COUNT'].iloc[0]) if len(human_row) > 0 else 0)
        auto_pct = round(automated * 100.0 / total_ops, 1) if total_ops > 0 else 0.0
        top_agent = df.iloc[0]['DEPLOYMENT_AGENT'] if len(df) > 0 else 'N/A'

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("DDL Ops Attributed (30d)", f"{total_ops:,}")
        c2.metric("Deployment Agents", str(num_agents))
        c3.metric("Automated DDL Share", f"{auto_pct}%")
        c4.metric("Top Agent", top_agent[:20] + '...' if len(str(top_agent)) > 20 else top_agent)

        st.markdown("")

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("**CI/CD Tool Summary (30d)**")
            plot_df = df.sort_values('DDL_OPERATIONS_COUNT', ascending=True)
            fig = go.Figure(go.Bar(
                y=plot_df['DEPLOYMENT_AGENT'], x=plot_df['DDL_OPERATIONS_COUNT'],
                orientation='h', marker_color=_C1,
                text=[f"{v:,}" for v in plot_df['DDL_OPERATIONS_COUNT']],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>DDL Operations: %{x:,}<extra></extra>'
            ))
            fig.update_layout(height=400, xaxis_title='DDL Operations', showlegend=False,
                              margin=dict(t=20, b=50, l=180, r=50))
            st.plotly_chart(fig, use_container_width=True, key="cicd_ops_bar")

        with col_r:
            st.markdown("**DDL Automation Share by Agent**")
            colors = [_C1, _C2, _C3, _CA][:len(df)]
            fig = go.Figure(go.Pie(
                labels=df['DEPLOYMENT_AGENT'], values=df['DDL_OPERATIONS_COUNT'],
                hole=0.45, marker=dict(colors=colors),
                textinfo='label+percent', textposition='outside',
                hovertemplate='<b>%{label}</b><br>Ops: %{value:,}<br>%{percent}<extra></extra>'
            ))
            fig.update_layout(height=400, showlegend=True,
                              legend=dict(orientation='h', y=-0.15, x=0.5, xanchor='center'),
                              margin=dict(t=20, b=60, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True, key="cicd_share_donut")

        st.markdown("**Session Footprint by Deployment Agent**")
        plot_df2 = df.sort_values('SESSION_COUNT', ascending=True)
        fig = go.Figure(go.Bar(
            y=plot_df2['DEPLOYMENT_AGENT'], x=plot_df2['SESSION_COUNT'],
            orientation='h', marker_color=_C3,
            text=[f"{int(v):,}" for v in plot_df2['SESSION_COUNT']],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Distinct Sessions: %{x:,}<extra></extra>'
        ))
        fig.update_layout(height=350, xaxis_title='Distinct Sessions', showlegend=False,
                          margin=dict(t=20, b=50, l=180, r=50))
        st.plotly_chart(fig, use_container_width=True, key="cicd_session_bar")

        st.markdown("**CI/CD Tool Identification Detail**")
        detail_df = _cached_sql("rd_cicd_detail", _SQL_CICD_DETAIL)
        if not detail_df.empty:
            detail_df.columns = ['DEPLOYMENT_AGENT', 'CLIENT_APPLICATION_ID', 'SESSION_COUNT', 'DDL_OPERATIONS_COUNT', 'DISTINCT_USERS']
            st.dataframe(detail_df, use_container_width=True)
        else:
            st.info("No detail data available.")

    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid {_CA};padding:10px;">'
            f'Error: {str(e)}</div>', unsafe_allow_html=True)

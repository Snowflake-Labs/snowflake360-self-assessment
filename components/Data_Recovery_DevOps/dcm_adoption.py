import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

_SQL_DDL_PATTERNS = """
SELECT
    CASE
        WHEN query_text ILIKE '%CREATE OR ALTER%' THEN 'Declarative (DevOps Pattern)'
        WHEN query_text ILIKE '%EXECUTE IMMEDIATE FROM%' THEN 'Deployment from File/Git'
        WHEN query_text ILIKE '%CREATE OR REPLACE%' THEN 'Idempotent DDL'
        ELSE 'Imperative (Standard DDL)'
    END AS ddl_pattern,
    COUNT(*) AS execution_count,
    COUNT(DISTINCT user_name) AS distinct_users,
    COUNT(DISTINCT role_name) AS distinct_roles,
    ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) AS pct_of_total
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type IN ('CREATE_TABLE','ALTER_TABLE','EXECUTE_IMMEDIATE','CREATE_VIEW','ALTER_VIEW')
  AND execution_status = 'SUCCESS'
GROUP BY ddl_pattern
ORDER BY execution_count DESC
"""

_ALL_DCM_QUERIES = {
    "rd_dcm_adoption": _SQL_DDL_PATTERNS,
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


def comp_dcm_adoption(entry_actions=None):
    try:
        df = _cached_sql("rd_dcm_adoption", _SQL_DDL_PATTERNS)

        if df.empty:
            st.markdown(
                '<div style="background-color:#fff3cd;border-left:6px solid #ffc107;padding:10px;">'
                '⚠️&nbsp;&nbsp;No DDL deployment pattern data found for the last 30 days.</div>',
                unsafe_allow_html=True)
            return

        df.columns = ['DDL_PATTERN', 'EXECUTION_COUNT', 'DISTINCT_USERS', 'DISTINCT_ROLES', 'PCT_OF_TOTAL']

        total_ddl = int(df['EXECUTION_COUNT'].sum())
        decl = int(df.loc[df['DDL_PATTERN'].str.contains('Declarative', case=False), 'EXECUTION_COUNT'].sum()) if any(df['DDL_PATTERN'].str.contains('Declarative', case=False)) else 0
        git_dep = int(df.loc[df['DDL_PATTERN'].str.contains('File/Git', case=False), 'EXECUTION_COUNT'].sum()) if any(df['DDL_PATTERN'].str.contains('File/Git', case=False)) else 0
        top_pattern = df.iloc[0]['DDL_PATTERN'] if len(df) > 0 else 'N/A'

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Successful DDL Ops (30d)", f"{total_ddl:,}")
        c2.metric("Declarative DDL", f"{decl:,}")
        c3.metric("Git-Based Deployments", f"{git_dep:,}")
        c4.metric("Top Pattern", top_pattern[:20] + '...' if len(str(top_pattern)) > 20 else top_pattern)

        st.markdown("")

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("**DDL Deployment Pattern Distribution (30d)**")
            colors = [_C1, _C2, _C3, _CA][:len(df)]
            fig = go.Figure(go.Pie(
                labels=df['DDL_PATTERN'], values=df['EXECUTION_COUNT'],
                hole=0.45, marker=dict(colors=colors),
                textinfo='label+percent', textposition='outside',
                hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>'
            ))
            fig.update_layout(height=400, showlegend=True,
                              legend=dict(orientation='h', y=-0.15, x=0.5, xanchor='center'),
                              margin=dict(t=20, b=60, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True, key="dcm_donut")

        with col_r:
            st.markdown("**DDL Pattern Execution Count (30d)**")
            plot_df = df.sort_values('EXECUTION_COUNT', ascending=True)
            colors = [_C2, _C1, _C3, _CA][:len(plot_df)]
            fig = go.Figure(go.Bar(
                y=plot_df['DDL_PATTERN'], x=plot_df['EXECUTION_COUNT'],
                orientation='h', marker_color=colors[::-1],
                text=[f"{v:,}" for v in plot_df['EXECUTION_COUNT']],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Executions: %{x:,}<extra></extra>'
            ))
            fig.update_layout(height=400, xaxis_title='Executions', showlegend=False,
                              margin=dict(t=20, b=50, l=200, r=50))
            st.plotly_chart(fig, use_container_width=True, key="dcm_exec_bar")

        st.markdown("**Pattern Participation Coverage (Users vs Roles)**")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Distinct Users', x=df['DDL_PATTERN'], y=df['DISTINCT_USERS'],
            marker_color=_C1, text=df['DISTINCT_USERS'], textposition='outside'
        ))
        fig.add_trace(go.Bar(
            name='Distinct Roles', x=df['DDL_PATTERN'], y=df['DISTINCT_ROLES'],
            marker_color=_CA, text=df['DISTINCT_ROLES'], textposition='outside'
        ))
        fig.update_layout(barmode='group', height=400, yaxis_title='Count',
                          legend=dict(orientation='h', y=1.1, x=0.5, xanchor='center'),
                          margin=dict(t=40, b=100, l=50, r=50))
        st.plotly_chart(fig, use_container_width=True, key="dcm_participation")

        st.markdown("**Pattern Coverage Detail**")
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid {_CA};padding:10px;">'
            f'Error: {str(e)}</div>', unsafe_allow_html=True)

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

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

_SQL_GIT_ACTIVITY = """
SELECT
    'Git Operation' AS category,
    CASE
        WHEN query_text ILIKE '%ALTER GIT REPOSITORY%FETCH%' THEN 'Git Fetch (Update)'
        WHEN query_text ILIKE '%FROM @%branches/%' OR query_text ILIKE '%FROM @%tags/%' THEN 'Execution from Git Branch/Tag'
        WHEN query_text ILIKE '%CREATE GIT REPOSITORY%' THEN 'Git Repository Creation'
        WHEN query_text ILIKE '%SHOW GIT%' THEN 'Git Metadata Query'
        ELSE 'Other Git Operation'
    END AS operation_type,
    COUNT(*) AS count_ops,
    COUNT(DISTINCT user_name) AS distinct_users
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (query_text ILIKE '%ALTER GIT REPOSITORY%'
       OR query_text ILIKE '%FROM @%'
       OR query_text ILIKE '%CREATE GIT REPOSITORY%'
       OR query_text ILIKE '%SHOW GIT%')
GROUP BY operation_type
HAVING COUNT(*) > 0
ORDER BY count_ops DESC
"""

_ALL_GIT_QUERIES = {
    "rd_git_integration": _SQL_GIT_ACTIVITY,
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


def comp_git_integration(entry_actions=None):
    try:
        df = _cached_sql("rd_git_integration", _SQL_GIT_ACTIVITY)

        if df.empty:
            st.markdown(
                '<div style="background-color:#fff3cd;border-left:6px solid #ffc107;padding:10px;">'
                '⚠️&nbsp;&nbsp;No Git integration activity data found for the last 30 days.</div>',
                unsafe_allow_html=True)
            return

        df.columns = ['CATEGORY', 'OPERATION_TYPE', 'COUNT_OPS', 'DISTINCT_USERS']

        total_ops = int(df['COUNT_OPS'].sum())
        num_categories = len(df)
        top_activity = df.iloc[0]['OPERATION_TYPE'] if len(df) > 0 else 'N/A'
        max_users = int(df['DISTINCT_USERS'].max()) if len(df) > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Git Operations (30d)", f"{total_ops:,}")
        c2.metric("Operation Categories", str(num_categories))
        c3.metric("Top Git Activity", top_activity[:20] + '...' if len(str(top_activity)) > 20 else top_activity)
        c4.metric("Max Users / Operation", str(max_users))

        st.markdown("")

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("**Git Operation Categories (30d)**")
            plot_df = df.sort_values('COUNT_OPS', ascending=True)
            fig = go.Figure(go.Bar(
                y=plot_df['OPERATION_TYPE'], x=plot_df['COUNT_OPS'],
                orientation='h', marker_color=_C1,
                text=[f"{v:,}" for v in plot_df['COUNT_OPS']],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Operations: %{x:,}<extra></extra>'
            ))
            fig.update_layout(height=400, xaxis_title='Operations', showlegend=False,
                              margin=dict(t=20, b=50, l=200, r=50))
            st.plotly_chart(fig, use_container_width=True, key="git_ops_bar")

        with col_r:
            st.markdown("**Git Activity Mix (30d)**")
            colors = [_C1, _C2, _C3, _CA][:len(df)]
            fig = go.Figure(go.Pie(
                labels=df['OPERATION_TYPE'], values=df['COUNT_OPS'],
                hole=0.45, marker=dict(colors=colors),
                textinfo='label+percent', textposition='outside',
                hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>'
            ))
            fig.update_layout(height=400, showlegend=True,
                              legend=dict(orientation='h', y=-0.15, x=0.5, xanchor='center'),
                              margin=dict(t=20, b=60, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True, key="git_mix_donut")

        st.markdown("**Distinct Users by Git Operation**")
        plot_df2 = df.sort_values('DISTINCT_USERS', ascending=True)
        fig = go.Figure(go.Bar(
            y=plot_df2['OPERATION_TYPE'], x=plot_df2['DISTINCT_USERS'],
            orientation='h', marker_color=_C3,
            text=[f"{int(v):,}" for v in plot_df2['DISTINCT_USERS']],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Distinct Users: %{x:,}<extra></extra>'
        ))
        fig.update_layout(height=350, xaxis_title='Distinct Users', showlegend=False,
                          margin=dict(t=20, b=50, l=200, r=50))
        st.plotly_chart(fig, use_container_width=True, key="git_users_bar")

        st.markdown("**Git Integration Detail**")
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid {_CA};padding:10px;">'
            f'Error: {str(e)}</div>', unsafe_allow_html=True)

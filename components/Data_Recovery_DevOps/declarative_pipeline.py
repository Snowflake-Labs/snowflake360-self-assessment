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

_SQL_ORCHESTRATION = """
WITH dt_usage AS (
    SELECT
        'Dynamic Tables (Declarative)' AS orchestration_type,
        COUNT(*) AS activity_count,
        COUNT(DISTINCT name) AS distinct_objects
    FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
    WHERE data_timestamp >= DATEADD('day', -7, CURRENT_TIMESTAMP())
),
task_usage AS (
    SELECT
        'Tasks (Imperative)' AS orchestration_type,
        COUNT(*) AS activity_count,
        COUNT(DISTINCT name) AS distinct_objects
    FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
    WHERE scheduled_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
),
combined AS (
    SELECT * FROM dt_usage
    UNION ALL
    SELECT * FROM task_usage
)
SELECT
    orchestration_type,
    activity_count,
    distinct_objects,
    CASE
        WHEN orchestration_type LIKE '%Dynamic%' AND activity_count > 0 THEN 'Using Modern Declarative Pattern'
        WHEN orchestration_type LIKE '%Task%' AND activity_count > 0 THEN 'Using Traditional Imperative Pattern'
        ELSE 'No Activity'
    END AS pattern_assessment
FROM combined
ORDER BY activity_count DESC
"""

_SQL_DT_INVENTORY = """
SELECT
    COUNT(*) AS dt_count,
    COUNT(DISTINCT table_catalog) AS db_count,
    COUNT(DISTINCT table_schema) AS schema_count
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE table_type = 'DYNAMIC TABLE' AND deleted IS NULL
"""

_SQL_DT_REFRESH_STATS = """
SELECT
    COUNT(*) AS refresh_count,
    AVG(TIMESTAMPDIFF('minute', refresh_start_time, refresh_end_time)) AS avg_lag_min
FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
WHERE data_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
"""

_SQL_DT_DAILY_REFRESH = """
SELECT
    TO_DATE(data_timestamp) AS refresh_date,
    SUM(CASE WHEN state = 'SUCCEEDED' THEN 1 ELSE 0 END) AS success,
    SUM(CASE WHEN state != 'SUCCEEDED' THEN 1 ELSE 0 END) AS failures
FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
WHERE data_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY refresh_date
ORDER BY refresh_date
"""

_ALL_ORCH_QUERIES = {
    "rd_orchestration": _SQL_ORCHESTRATION,
    "rd_dt_inventory": _SQL_DT_INVENTORY,
    "rd_dt_refresh_stats": _SQL_DT_REFRESH_STATS,
    "rd_dt_daily_refresh": _SQL_DT_DAILY_REFRESH,
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


def comp_declarative_pipeline(entry_actions=None):
    try:
        st.markdown("### Declarative vs Imperative Orchestration (7d)")

        df = _cached_sql("rd_orchestration", _SQL_ORCHESTRATION)

        if df.empty:
            st.markdown(
                '<div style="background-color:#fff3cd;border-left:6px solid #ffc107;padding:10px;">'
                '⚠️&nbsp;&nbsp;No orchestration pattern data found for the last 7 days.</div>',
                unsafe_allow_html=True)
        else:
            df.columns = ['ORCHESTRATION_TYPE', 'ACTIVITY_COUNT', 'DISTINCT_OBJECTS', 'PATTERN_ASSESSMENT']

            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown("**Orchestration Activity Count**")
                plot_df = df.sort_values('ACTIVITY_COUNT', ascending=True)
                fig = go.Figure(go.Bar(
                    y=plot_df['ORCHESTRATION_TYPE'], x=plot_df['ACTIVITY_COUNT'],
                    orientation='h', marker_color=_C1,
                    text=[f"{int(v):,}" for v in plot_df['ACTIVITY_COUNT']],
                    textposition='outside',
                    hovertemplate='<b>%{y}</b><br>Activity Count: %{x:,}<extra></extra>'
                ))
                fig.update_layout(height=350, xaxis_title='Activity Count', showlegend=False,
                                  margin=dict(t=20, b=50, l=220, r=50))
                st.plotly_chart(fig, use_container_width=True, key="orch_activity_bar")

            with col_r:
                st.markdown("**Distinct Orchestrated Objects**")
                colors = [_C1, _C2][:len(df)]
                fig = go.Figure(go.Pie(
                    labels=df['ORCHESTRATION_TYPE'], values=df['ACTIVITY_COUNT'],
                    hole=0.45, marker=dict(colors=colors),
                    textinfo='label+percent', textposition='outside',
                    hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>'
                ))
                fig.update_layout(height=350, showlegend=True,
                                  legend=dict(orientation='h', y=-0.15, x=0.5, xanchor='center'),
                                  margin=dict(t=20, b=60, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True, key="orch_objects_donut")

            st.dataframe(df, use_container_width=True)

        st.markdown("---")

        inv_df = _cached_sql("rd_dt_inventory", _SQL_DT_INVENTORY)
        ref_df = _cached_sql("rd_dt_refresh_stats", _SQL_DT_REFRESH_STATS)

        dt_count = int(inv_df.iloc[0, 0]) if not inv_df.empty and inv_df.iloc[0, 0] else 0
        db_count = int(inv_df.iloc[0, 1]) if not inv_df.empty and inv_df.iloc[0, 1] else 0
        schema_count = int(inv_df.iloc[0, 2]) if not inv_df.empty and inv_df.iloc[0, 2] else 0
        refresh_count = int(ref_df.iloc[0, 0]) if not ref_df.empty and ref_df.iloc[0, 0] else 0
        avg_lag = round(float(ref_df.iloc[0, 1]), 1) if not ref_df.empty and ref_df.iloc[0, 1] else 0.0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Dynamic Tables", f"{dt_count:,}")
        c2.metric("Databases", str(db_count))
        c3.metric("Schemas", str(schema_count))
        c4.metric("Refreshes (30d)", f"{refresh_count:,}")
        c5.metric("Avg Lag (min)", str(avg_lag))

        st.markdown("")

        if refresh_count == 0:
            lc, rc = st.columns(2)
            with lc:
                st.markdown(
                    '<div style="background-color:#fff3cd;border-left:6px solid #ffc107;padding:10px;">'
                    '⚠️&nbsp;&nbsp;No refresh history found.</div>',
                    unsafe_allow_html=True)
            with rc:
                st.markdown(
                    '<div style="background-color:#fff3cd;border-left:6px solid #ffc107;padding:10px;">'
                    '⚠️&nbsp;&nbsp;No refresh outcome data.</div>',
                    unsafe_allow_html=True)

        st.markdown("**Daily Refresh Trend (30d)**")
        trend_df = _cached_sql("rd_dt_daily_refresh", _SQL_DT_DAILY_REFRESH)
        if not trend_df.empty:
            trend_df.columns = ['REFRESH_DATE', 'SUCCESS', 'FAILURES']
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Failures', x=trend_df['REFRESH_DATE'], y=trend_df['FAILURES'],
                marker_color=_CA
            ))
            fig.add_trace(go.Bar(
                name='Success', x=trend_df['REFRESH_DATE'], y=trend_df['SUCCESS'],
                marker_color=_C1
            ))
            fig.update_layout(barmode='stack', height=400,
                              legend=dict(orientation='h', y=-0.15, x=0.5, xanchor='center'),
                              margin=dict(t=20, b=60, l=50, r=50))
            st.plotly_chart(fig, use_container_width=True, key="dt_daily_trend")
        else:
            st.info("No daily refresh data available.")

    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid {_CA};padding:10px;">'
            f'Error: {str(e)}</div>', unsafe_allow_html=True)

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
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


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


_CHART_COLORS = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229', '#1A7DA8', '#023E8A', '#48CAE4']
_SEV_COLORS = {'CRITICAL': '#F39C12', 'HIGH': '#E8A229', 'MODERATE': '#75C2D8', 'LOW': '#29B5E8', 'OK': '#29B5E8'}


def comp_scaling_management(entry_actions=None):
    try:
        st.markdown("### Scaling Management")
        with st.expander("Warehouse Oversizing Analysis", expanded=True):
            _render_oversizing()
        with st.expander("Warehouse Idle Time Analysis", expanded=True):
            _render_idle_time()
        with st.expander("Combined Scaling Efficiency Summary", expanded=True):
            _render_scaling_efficiency()
    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
            f'🛑&nbsp;&nbsp;Component Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_oversizing():
    st.markdown("#### Warehouse Oversizing Analysis")
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Oversizing Analysis:</b> Warehouses running queries with fewer data partitions '
        'than available compute nodes waste capacity. A high oversizing percentage suggests a smaller '
        'warehouse would handle the workload more cost-effectively.</div>', unsafe_allow_html=True)
    try:
        session = st.session_state.session
        query = """
        WITH node_mapping AS (
            SELECT 'X-Small' AS size, 1 AS nodes UNION ALL
            SELECT 'Small', 2 UNION ALL SELECT 'Medium', 4 UNION ALL
            SELECT 'Large', 8 UNION ALL SELECT 'X-Large', 16 UNION ALL
            SELECT '2X-Large', 32 UNION ALL SELECT '3X-Large', 64 UNION ALL
            SELECT '4X-Large', 128 UNION ALL SELECT '5X-Large', 256 UNION ALL
            SELECT '6X-Large', 512
        ),
        oversized_queries AS (
            SELECT
                q.WAREHOUSE_NAME,
                q.WAREHOUSE_SIZE,
                n.nodes AS available_nodes,
                q.PARTITIONS_SCANNED,
                q.QUERY_ID,
                CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 'YES' ELSE 'NO' END AS is_oversized
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
            INNER JOIN node_mapping n ON q.WAREHOUSE_SIZE = n.size
            WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
              AND q.WAREHOUSE_SIZE NOT IN ('X-Small', 'Small')
              AND q.PARTITIONS_SCANNED > 0
              AND q.WAREHOUSE_NAME IS NOT NULL
        )
        SELECT
            WAREHOUSE_NAME,
            WAREHOUSE_SIZE,
            COUNT(*) AS total_queries,
            COUNT(CASE WHEN is_oversized = 'YES' THEN 1 END) AS oversized_queries,
            ROUND(COUNT(CASE WHEN is_oversized = 'YES' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS pct_oversized,
            CASE
                WHEN ROUND(COUNT(CASE WHEN is_oversized='YES' THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) >= 80 THEN 'CRITICAL'
                WHEN ROUND(COUNT(CASE WHEN is_oversized='YES' THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) >= 50 THEN 'HIGH'
                WHEN ROUND(COUNT(CASE WHEN is_oversized='YES' THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) >= 25 THEN 'MODERATE'
                ELSE 'LOW'
            END AS severity
        FROM oversized_queries
        GROUP BY 1, 2
        HAVING total_queries > 0
        ORDER BY pct_oversized DESC
        LIMIT 20
        """
        df = _cached_sql("sm_oversizing", query)
        if df.empty:
            st.info("No oversizing data found for the last 7 days.")
            return
        df['PCT_OVERSIZED'] = pd.to_numeric(df['PCT_OVERSIZED'], errors='coerce').fillna(0)
        df['TOTAL_QUERIES'] = pd.to_numeric(df['TOTAL_QUERIES'], errors='coerce').fillna(0)
        col1, col2, col3 = st.columns(3)
        critical = len(df[df['SEVERITY'] == 'CRITICAL'])
        high = len(df[df['SEVERITY'] == 'HIGH'])
        with col1:
            st.metric("Warehouses Analyzed", len(df))
        with col2:
            st.metric("Critical (>80% oversized)", critical)
        with col3:
            st.metric("High (50-80% oversized)", high)
        bar_colors = [_SEV_COLORS.get(s, '#29B5E8') for s in df['SEVERITY']]
        fig = go.Figure(go.Bar(
            x=df['WAREHOUSE_NAME'], y=df['PCT_OVERSIZED'],
            marker_color=bar_colors,
            text=[f"{v:.0f}%" for v in df['PCT_OVERSIZED']],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Oversized: %{y:.1f}%<extra></extra>'
        ))
        fig.update_layout(
            title='Warehouse Oversizing % (Last 7 Days)',
            xaxis_title='Warehouse', yaxis_title='% Queries Oversized',
            yaxis=dict(range=[0, min(110, df['PCT_OVERSIZED'].max() * 1.2)]),
            height=380, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['WAREHOUSE_NAME', 'WAREHOUSE_SIZE', 'TOTAL_QUERIES', 'OVERSIZED_QUERIES', 'PCT_OVERSIZED', 'SEVERITY']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_idle_time():
    st.markdown("#### Warehouse Idle Time Analysis")
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Idle Time Analysis:</b> High idle % means the warehouse is running (and billing) '
        'without executing queries. Reducing the auto-suspend timeout is the primary fix.</div>', unsafe_allow_html=True)
    try:
        session = st.session_state.session
        query = """
        WITH idle_stats AS (
            SELECT
                WAREHOUSE_NAME,
                COUNT(*) AS interval_count,
                SUM(CASE WHEN AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) AS idle_intervals,
                AVG(AVG_RUNNING) AS avg_running_threads,
                AVG(AVG_QUEUED_LOAD) AS avg_queued_load
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
            WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY WAREHOUSE_NAME
        )
        SELECT
            WAREHOUSE_NAME,
            ROUND(interval_count * 5.0 / 60.0, 2) AS est_uptime_hours,
            ROUND(idle_intervals * 5.0 / 60.0, 2) AS est_idle_hours,
            ROUND(idle_intervals * 100.0 / NULLIF(interval_count, 0), 1) AS pct_time_idle,
            ROUND(avg_running_threads, 2) AS avg_running_threads,
            ROUND(avg_queued_load, 2) AS avg_queued_load,
            CASE
                WHEN idle_intervals * 100.0 / NULLIF(interval_count, 0) >= 70 THEN 'CRITICAL'
                WHEN idle_intervals * 100.0 / NULLIF(interval_count, 0) >= 50 THEN 'HIGH'
                WHEN idle_intervals * 100.0 / NULLIF(interval_count, 0) >= 30 THEN 'MODERATE'
                ELSE 'LOW'
            END AS idle_severity
        FROM idle_stats
        WHERE interval_count * 5.0 / 60.0 > 1
        ORDER BY pct_time_idle DESC
        """
        df = _cached_sql("sm_load_analysis", query)
        if df.empty:
            st.info("No warehouse load history found for the last 7 days.")
            return
        df['PCT_TIME_IDLE'] = pd.to_numeric(df['PCT_TIME_IDLE'], errors='coerce').fillna(0)
        df['EST_UPTIME_HOURS'] = pd.to_numeric(df['EST_UPTIME_HOURS'], errors='coerce').fillna(0)
        df['EST_IDLE_HOURS'] = pd.to_numeric(df['EST_IDLE_HOURS'], errors='coerce').fillna(0)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Warehouses with Load Data", len(df))
        with col2:
            high_idle = len(df[df['PCT_TIME_IDLE'] >= 50])
            st.metric("High Idle (>50%)", high_idle)
        with col3:
            avg_idle = df['PCT_TIME_IDLE'].mean()
            st.metric("Avg Idle %", f"{avg_idle:.1f}%")
        bar_colors = [_SEV_COLORS.get(s, '#29B5E8') for s in df['IDLE_SEVERITY']]
        fig = go.Figure(go.Bar(
            x=df['WAREHOUSE_NAME'], y=df['PCT_TIME_IDLE'],
            marker_color=bar_colors,
            text=[f"{v:.0f}%" for v in df['PCT_TIME_IDLE']],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Idle: %{y:.1f}%<br>Uptime: %{customdata[0]:.1f}h<extra></extra>',
            customdata=df[['EST_UPTIME_HOURS']].values
        ))
        fig.update_layout(
            title='Warehouse Idle % (Last 7 Days)',
            xaxis_title='Warehouse', yaxis_title='% Time Idle',
            yaxis=dict(range=[0, 110]),
            height=380, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['WAREHOUSE_NAME', 'EST_UPTIME_HOURS', 'EST_IDLE_HOURS', 'PCT_TIME_IDLE', 'AVG_RUNNING_THREADS', 'IDLE_SEVERITY']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_scaling_efficiency():
    st.markdown("#### Combined Scaling Efficiency Summary")
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Scaling Efficiency:</b> Combines oversizing and idle analysis into a single '
        'recommendation per warehouse, prioritising the most impactful right-sizing actions.</div>', unsafe_allow_html=True)
    try:
        session = st.session_state.session
        query = """
        WITH node_mapping AS (
            SELECT 'X-Small' AS size, 1 AS nodes UNION ALL SELECT 'Small', 2 UNION ALL
            SELECT 'Medium', 4 UNION ALL SELECT 'Large', 8 UNION ALL SELECT 'X-Large', 16 UNION ALL
            SELECT '2X-Large', 32 UNION ALL SELECT '3X-Large', 64 UNION ALL SELECT '4X-Large', 128
        ),
        query_eff AS (
            SELECT
                q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE, n.nodes,
                COUNT(*) AS total_queries,
                SUM(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 ELSE 0 END) AS over_queries,
                AVG(q.PARTITIONS_SCANNED) AS avg_parts
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
            INNER JOIN node_mapping n ON q.WAREHOUSE_SIZE = n.size
            WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
              AND q.PARTITIONS_SCANNED > 0 AND q.WAREHOUSE_NAME IS NOT NULL
            GROUP BY 1, 2, 3
        ),
        idle_eff AS (
            SELECT WAREHOUSE_NAME,
                COUNT(*) AS total_intervals,
                SUM(CASE WHEN AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) AS idle_intervals
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
            WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP()) AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY WAREHOUSE_NAME
        )
        SELECT
            qe.WAREHOUSE_NAME,
            qe.WAREHOUSE_SIZE,
            qe.total_queries,
            ROUND(qe.over_queries * 100.0 / NULLIF(qe.total_queries, 0), 1) AS pct_oversized,
            ROUND(ie.idle_intervals * 100.0 / NULLIF(ie.total_intervals, 0), 1) AS pct_idle,
            CASE
                WHEN qe.over_queries*100.0/NULLIF(qe.total_queries,0) >= 50
                     AND ie.idle_intervals*100.0/NULLIF(ie.total_intervals,0) >= 50 THEN 'CRITICAL - Downsize + Reduce Auto-Suspend'
                WHEN qe.over_queries*100.0/NULLIF(qe.total_queries,0) >= 50 THEN 'HIGH - Downsize Candidate'
                WHEN ie.idle_intervals*100.0/NULLIF(ie.total_intervals,0) >= 50 THEN 'HIGH - Reduce Auto-Suspend'
                WHEN qe.over_queries*100.0/NULLIF(qe.total_queries,0) >= 25
                     OR ie.idle_intervals*100.0/NULLIF(ie.total_intervals,0) >= 25 THEN 'MODERATE - Review Configuration'
                ELSE 'OK - Well Configured'
            END AS recommendation
        FROM query_eff qe
        LEFT JOIN idle_eff ie ON qe.WAREHOUSE_NAME = ie.WAREHOUSE_NAME
        ORDER BY pct_oversized DESC NULLS LAST, pct_idle DESC NULLS LAST
        LIMIT 20
        """
        df = _cached_sql("sm_scaling_efficiency", query)
        if df.empty:
            st.info("No scaling efficiency data found for the last 7 days.")
            return
        df['PCT_OVERSIZED'] = pd.to_numeric(df['PCT_OVERSIZED'], errors='coerce').fillna(0)
        df['PCT_IDLE'] = pd.to_numeric(df['PCT_IDLE'], errors='coerce').fillna(0)
        crit_mask = df['RECOMMENDATION'].str.startswith('CRITICAL')
        high_mask = df['RECOMMENDATION'].str.startswith('HIGH')
        ok_mask = df['RECOMMENDATION'].str.startswith('OK')
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Warehouses", len(df))
        with col2:
            st.metric("Critical/High Issues", int(crit_mask.sum() + high_mask.sum()))
        with col3:
            st.metric("Well Configured", int(ok_mask.sum()))
        fig = go.Figure()
        fig.add_trace(go.Bar(name='% Oversized', x=df['WAREHOUSE_NAME'], y=df['PCT_OVERSIZED'], marker_color='#11567F'))
        fig.add_trace(go.Bar(name='% Idle', x=df['WAREHOUSE_NAME'], y=df['PCT_IDLE'], marker_color='#E8A229'))
        fig.update_layout(
            barmode='group', title='Oversizing vs Idle % per Warehouse (Last 7 Days)',
            xaxis_title='Warehouse', yaxis_title='%',
            height=380, margin=dict(t=50, b=80),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['WAREHOUSE_NAME', 'WAREHOUSE_SIZE', 'TOTAL_QUERIES', 'PCT_OVERSIZED', 'PCT_IDLE', 'RECOMMENDATION']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

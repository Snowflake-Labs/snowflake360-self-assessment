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


_C = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229', '#1A7DA8', '#023E8A', '#48CAE4']


def comp_performance_monitoring(entry_actions=None):
    try:
        st.markdown("### Performance Monitoring")
        with st.expander("Warehouse Fleet Distribution", expanded=True):
            _render_fleet_distribution()
        with st.expander("Top Warehouses by Credit Consumption", expanded=True):
            _render_top_credit_warehouses()
        with st.expander("Hourly Query Activity", expanded=True):
            _render_hourly_activity()
        with st.expander("Resource Constraints (Spills & Timeouts)", expanded=True):
            _render_resource_constraints()
        with st.expander("Configuration Change History", expanded=True):
            _render_config_changes()
        with st.expander("Query Acceleration Service (QAS) Eligibility", expanded=True):
            _render_qas()
    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
            f'🛑&nbsp;&nbsp;Component Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_fleet_distribution():
    st.markdown("#### Warehouse Fleet Distribution")
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Fleet Distribution:</b> Breakdown of active warehouses by type (standard vs '
        'Snowpark-Optimized) and size over the last 7 days.</div>', unsafe_allow_html=True)
    try:
        session = st.session_state.session
        query = """
        WITH active_fleet AS (
            SELECT
                WAREHOUSE_NAME,
                WAREHOUSE_SIZE,
                WAREHOUSE_TYPE,
                CASE WHEN WAREHOUSE_TYPE = 'SNOWPARK-OPTIMIZED' THEN 'Memory Optimized' ELSE 'Standard' END AS resource_constraint
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IS NOT NULL
            QUALIFY ROW_NUMBER() OVER (PARTITION BY WAREHOUSE_NAME ORDER BY START_TIME DESC) = 1
        )
        SELECT WAREHOUSE_TYPE, resource_constraint, WAREHOUSE_SIZE, COUNT(*) AS warehouse_count
        FROM active_fleet
        GROUP BY 1, 2, 3
        ORDER BY WAREHOUSE_TYPE, WAREHOUSE_SIZE
        """
        df = _cached_sql("pm_fleet_dist", query)
        if df.empty:
            st.info("No fleet data found for the last 7 days.")
            return
        df['WAREHOUSE_COUNT'] = pd.to_numeric(df['WAREHOUSE_COUNT'], errors='coerce').fillna(0)
        col1, col2 = st.columns(2)
        with col1:
            fig_bar = go.Figure(go.Bar(
                x=df['WAREHOUSE_SIZE'], y=df['WAREHOUSE_COUNT'],
                marker_color=_C[0],
                text=df['WAREHOUSE_COUNT'], textposition='outside',
                hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
            ))
            fig_bar.update_layout(title='Fleet by Size', xaxis_title='Size', yaxis_title='Count',
                                  height=320, margin=dict(t=40, b=60))
            st.plotly_chart(fig_bar, use_container_width=True)
        with col2:
            type_counts = df.groupby('RESOURCE_CONSTRAINT')['WAREHOUSE_COUNT'].sum().reset_index()
            fig_pie = go.Figure(go.Pie(
                labels=type_counts['RESOURCE_CONSTRAINT'], values=type_counts['WAREHOUSE_COUNT'],
                hole=0.3, marker_colors=_C[:len(type_counts)]
            ))
            fig_pie.update_layout(title='Fleet by Type', height=320, margin=dict(t=40, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_top_credit_warehouses():
    st.markdown("#### Top 15 Warehouses by Credit Consumption (30 Days)")
    try:
        session = st.session_state.session
        query = """
        WITH cost AS (
            SELECT WAREHOUSE_NAME, SUM(CREDITS_USED) AS total_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP()) AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY WAREHOUSE_NAME
        ),
        load_stats AS (
            SELECT WAREHOUSE_NAME,
                AVG(AVG_RUNNING) AS avg_running_threads,
                AVG(AVG_QUEUED_LOAD) AS avg_queued_load
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
            WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP()) AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY WAREHOUSE_NAME
        )
        SELECT
            c.WAREHOUSE_NAME,
            ROUND(c.total_credits, 2) AS credits_30d,
            ROUND(l.avg_running_threads, 2) AS avg_threads,
            ROUND(l.avg_queued_load, 2) AS avg_queue,
            CASE
                WHEN l.avg_queued_load > 0.1 THEN 'OVERUSED'
                WHEN l.avg_running_threads < 0.5 THEN 'UNDERUTILIZED'
                ELSE 'HEALTHY'
            END AS health_status
        FROM cost c
        LEFT JOIN load_stats l ON c.WAREHOUSE_NAME = l.WAREHOUSE_NAME
        ORDER BY c.total_credits DESC
        LIMIT 15
        """
        df = _cached_sql("pm_credit_trend", query)
        if df.empty:
            st.info("No metering data found for the last 30 days.")
            return
        df['CREDITS_30D'] = pd.to_numeric(df['CREDITS_30D'], errors='coerce').fillna(0)
        _h_colors = {'OVERUSED': '#F39C12', 'UNDERUTILIZED': '#E8A229', 'HEALTHY': '#29B5E8'}
        bar_colors = [_h_colors.get(s, '#29B5E8') for s in df['HEALTH_STATUS'].fillna('HEALTHY')]
        fig = go.Figure(go.Bar(
            x=df['WAREHOUSE_NAME'], y=df['CREDITS_30D'],
            marker_color=bar_colors,
            text=[f"{v:.1f}" for v in df['CREDITS_30D']], textposition='outside',
            hovertemplate='<b>%{x}</b><br>Credits: %{y:.2f}<extra></extra>'
        ))
        fig.update_layout(
            title='Top 15 Warehouses by Credits (30 Days)',
            xaxis_title='Warehouse', yaxis_title='Credits Used',
            height=380, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_hourly_activity():
    st.markdown("#### Hourly Query Activity (Last 7 Days)")
    try:
        session = st.session_state.session
        query = """
        WITH hourly_stats AS (
            SELECT
                HOUR(START_TIME) AS hour_of_day,
                COUNT(*) AS query_count,
                AVG(TOTAL_ELAPSED_TIME) / 1000.0 AS avg_duration_sec,
                SUM(BYTES_SCANNED) / POW(1024, 4) AS total_tb_scanned
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY HOUR(START_TIME)
        ),
        max_stats AS (SELECT MAX(query_count) AS max_count FROM hourly_stats)
        SELECT
            h.hour_of_day,
            h.query_count,
            ROUND(h.avg_duration_sec, 2) AS avg_duration_sec,
            ROUND(h.total_tb_scanned, 4) AS total_tb_scanned,
            ROUND(h.query_count * 100.0 / NULLIF(m.max_count, 0), 1) AS pct_of_peak,
            CASE
                WHEN h.query_count >= m.max_count * 0.8 THEN 'PEAK'
                WHEN h.query_count >= m.max_count * 0.5 THEN 'HIGH'
                WHEN h.query_count >= m.max_count * 0.2 THEN 'MODERATE'
                ELSE 'LOW'
            END AS activity_level
        FROM hourly_stats h CROSS JOIN max_stats m
        ORDER BY h.hour_of_day
        """
        df = _cached_sql("pm_query_perf", query)
        if df.empty:
            st.info("No query history found for the last 7 days.")
            return
        df['QUERY_COUNT'] = pd.to_numeric(df['QUERY_COUNT'], errors='coerce').fillna(0)
        df['AVG_DURATION_SEC'] = pd.to_numeric(df['AVG_DURATION_SEC'], errors='coerce').fillna(0)
        bar_colors = ['#11567F' if lvl == 'PEAK' else '#29B5E8' if lvl == 'HIGH' else '#75C2D8' if lvl == 'MODERATE' else '#ADE8F4'
                      for lvl in df['ACTIVITY_LEVEL']]
        fig = go.Figure(go.Bar(
            x=df['HOUR_OF_DAY'], y=df['QUERY_COUNT'],
            marker_color=bar_colors,
            hovertemplate='Hour %{x}:00<br>Queries: %{y}<extra></extra>'
        ))
        fig.update_layout(
            title='Query Count by Hour of Day (Last 7 Days)',
            xaxis_title='Hour of Day (UTC)', yaxis_title='Query Count',
            xaxis=dict(tickmode='linear', tick0=0, dtick=1),
            height=340, margin=dict(t=50, b=60)
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_resource_constraints():
    st.markdown("#### Warehouse Resource Constraints (Spills & Timeouts, Last 7 Days)")
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Remote spills</b> indicate queries that exceeded local disk — upgrade to Snowpark-Optimized '
        'or a larger warehouse. <b>Timeouts</b> suggest overly complex queries or too-short timeout settings.</div>',
        unsafe_allow_html=True)
    try:
        session = st.session_state.session
        query = """
        SELECT
            WAREHOUSE_NAME,
            COUNT(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 END) AS remote_spills,
            COUNT(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 END) AS local_spills,
            ROUND(SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) / POW(1024, 3), 2) AS remote_spill_gb,
            ROUND(SUM(BYTES_SPILLED_TO_LOCAL_STORAGE) / POW(1024, 3), 2) AS local_spill_gb,
            COUNT(CASE WHEN ERROR_CODE = '100188' THEN 1 END) AS statement_timeouts,
            CASE
                WHEN COUNT(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 END) > 0 THEN 'CRITICAL'
                WHEN COUNT(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 END) > 100 THEN 'HIGH'
                WHEN COUNT(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 END) > 0 THEN 'MODERATE'
                ELSE 'OK'
            END AS spill_severity
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
          AND WAREHOUSE_NAME IS NOT NULL
        GROUP BY WAREHOUSE_NAME
        HAVING remote_spills > 0 OR statement_timeouts > 0 OR local_spills > 0
        ORDER BY remote_spills DESC, local_spills DESC
        LIMIT 20
        """
        df = _cached_sql("pm_resource_bottleneck", query)
        if df.empty:
            st.success("No remote spills or statement timeouts detected in the last 7 days.")
            return
        df['REMOTE_SPILLS'] = pd.to_numeric(df['REMOTE_SPILLS'], errors='coerce').fillna(0)
        df['LOCAL_SPILLS'] = pd.to_numeric(df['LOCAL_SPILLS'], errors='coerce').fillna(0)
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Remote Spills (critical)', x=df['WAREHOUSE_NAME'], y=df['REMOTE_SPILLS'], marker_color='#0077B6'))
        fig.add_trace(go.Bar(name='Local Spills', x=df['WAREHOUSE_NAME'], y=df['LOCAL_SPILLS'], marker_color='#E8A229'))
        fig.update_layout(
            barmode='group', title='Memory Spills by Warehouse',
            xaxis_title='Warehouse', yaxis_title='Spill Count',
            height=360, margin=dict(t=50, b=80),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['WAREHOUSE_NAME', 'REMOTE_SPILLS', 'LOCAL_SPILLS', 'REMOTE_SPILL_GB', 'LOCAL_SPILL_GB', 'STATEMENT_TIMEOUTS', 'SPILL_SEVERITY']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_config_changes():
    st.markdown("#### Warehouse Configuration Change History (Last 30 Days)")
    try:
        session = st.session_state.session
        query = """
        WITH change_stats AS (
            SELECT
                WAREHOUSE_NAME,
                COUNT(CASE WHEN EVENT_NAME = 'RESIZE_WAREHOUSE' THEN 1 END) AS resize_events,
                COUNT(CASE WHEN EVENT_NAME = 'CONVERT_WAREHOUSE' THEN 1 END) AS conversion_events,
                MAX(TIMESTAMP) AS last_event_time
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY
            WHERE TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP()) AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY WAREHOUSE_NAME
        )
        SELECT
            WAREHOUSE_NAME, resize_events, conversion_events, last_event_time,
            CASE
                WHEN resize_events > 10 THEN 'FREQUENT_CHANGES'
                WHEN resize_events > 0 THEN 'OCCASIONAL_CHANGES'
                ELSE 'STABLE'
            END AS change_frequency
        FROM change_stats
        WHERE resize_events > 0 OR conversion_events > 0
        ORDER BY resize_events DESC
        """
        df = _cached_sql("pm_config_changes", query)
        if df.empty:
            st.info("No warehouse resize or conversion events in the last 30 days.")
            return
        df['RESIZE_EVENTS'] = pd.to_numeric(df['RESIZE_EVENTS'], errors='coerce').fillna(0)
        _cf_colors = {'FREQUENT_CHANGES': '#E8A229', 'OCCASIONAL_CHANGES': '#75C2D8', 'STABLE': '#29B5E8'}
        fig = go.Figure(go.Bar(
            x=df['WAREHOUSE_NAME'], y=df['RESIZE_EVENTS'],
            marker_color=[_cf_colors.get(c, '#29B5E8') for c in df['CHANGE_FREQUENCY']],
            text=df['RESIZE_EVENTS'], textposition='outside'
        ))
        fig.update_layout(
            title='Warehouse Resize Events (Last 30 Days)',
            xaxis_title='Warehouse', yaxis_title='Resize Count',
            height=340, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['WAREHOUSE_NAME', 'RESIZE_EVENTS', 'CONVERSION_EVENTS', 'LAST_EVENT_TIME', 'CHANGE_FREQUENCY']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_qas():
    st.markdown("#### Query Acceleration Service (QAS)")
    try:
        session = st.session_state.session
        eligible_query = """
        SELECT
            WAREHOUSE_NAME,
            QUERY_ID,
            ROUND(ELIGIBLE_QUERY_ACCELERATION_TIME, 2) AS est_time_saved_sec,
            UPPER_LIMIT_SCALE_FACTOR AS suggested_scale_factor,
            CASE
                WHEN ELIGIBLE_QUERY_ACCELERATION_TIME > 60 THEN 'HIGH_IMPACT'
                WHEN ELIGIBLE_QUERY_ACCELERATION_TIME > 10 THEN 'MODERATE_IMPACT'
                ELSE 'LOW_IMPACT'
            END AS impact_level
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_ELIGIBLE
        WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
          AND WAREHOUSE_NAME IS NOT NULL
        ORDER BY ELIGIBLE_QUERY_ACCELERATION_TIME DESC
        LIMIT 20
        """
        usage_query = """
        SELECT
            WAREHOUSE_NAME,
            ROUND(SUM(CREDITS_USED), 4) AS qas_credits_used,
            COUNT(*) AS acceleration_events,
            ROUND(AVG(CREDITS_USED), 6) AS avg_credits_per_event
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_HISTORY
        WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
          AND WAREHOUSE_NAME IS NOT NULL
        GROUP BY WAREHOUSE_NAME
        ORDER BY qas_credits_used DESC
        """
        df_elig = _cached_sql("pm_qas_eligible", eligible_query)
        df_usage = _cached_sql("pm_qas_usage", usage_query)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("QAS-Eligible Queries (7d)", len(df_elig))
        with col2:
            df_usage['QAS_CREDITS_USED'] = pd.to_numeric(df_usage.get('QAS_CREDITS_USED', pd.Series([0])), errors='coerce').fillna(0)
            total_qas_credits = df_usage['QAS_CREDITS_USED'].sum() if not df_usage.empty else 0
            st.metric("QAS Credits Used (30d)", f"{total_qas_credits:.2f}")
        with col3:
            st.metric("Warehouses Using QAS", len(df_usage))
        if not df_elig.empty:
            df_elig['EST_TIME_SAVED_SEC'] = pd.to_numeric(df_elig['EST_TIME_SAVED_SEC'], errors='coerce').fillna(0)
            st.markdown("**Top QAS-Eligible Queries (Last 7 Days)**")
            st.dataframe(df_elig[['WAREHOUSE_NAME', 'QUERY_ID', 'EST_TIME_SAVED_SEC', 'SUGGESTED_SCALE_FACTOR', 'IMPACT_LEVEL']])
        else:
            st.info("No QAS-eligible queries found for the last 7 days.")
        if not df_usage.empty:
            st.markdown("**QAS Usage by Warehouse (Last 30 Days)**")
            st.dataframe(df_usage)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

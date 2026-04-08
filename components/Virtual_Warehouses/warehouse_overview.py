import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from core.config.design_tokens import (
    BRAND_PRIMARY, BRAND_SECONDARY,
    CHART_SERIES, CHART_EXTENDED,
)
from .scaling_management import comp_scaling_management
from .performance_monitoring import comp_performance_monitoring


_WH_FLEET_SQL = """
WITH active_fleet AS (
    SELECT
        q.WAREHOUSE_NAME,
        q.WAREHOUSE_SIZE,
        q.WAREHOUSE_TYPE,
        CASE
            WHEN q.WAREHOUSE_TYPE = 'SNOWPARK-OPTIMIZED' THEN 'Memory Optimized'
            ELSE 'Standard'
        END AS RESOURCE_CONSTRAINT
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND q.WAREHOUSE_NAME IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY q.WAREHOUSE_NAME ORDER BY q.START_TIME DESC) = 1
)
SELECT WAREHOUSE_NAME, WAREHOUSE_SIZE, WAREHOUSE_TYPE, RESOURCE_CONSTRAINT
FROM active_fleet
ORDER BY WAREHOUSE_NAME
"""

_WH_CREDITS_SQL = """
WITH cost AS (
    SELECT m.WAREHOUSE_NAME, SUM(m.CREDITS_USED) AS TOTAL_CREDITS
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY m
    WHERE m.START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY m.WAREHOUSE_NAME
),
load_stats AS (
    SELECT l.WAREHOUSE_NAME,
           AVG(l.AVG_RUNNING) AS AVG_RUNNING_THREADS,
           AVG(l.AVG_QUEUED_LOAD) AS AVG_QUEUED_LOAD
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY l
    WHERE l.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
    GROUP BY l.WAREHOUSE_NAME
)
SELECT c.WAREHOUSE_NAME,
       ROUND(c.TOTAL_CREDITS, 2) AS CREDITS_30_DAY,
       ROUND(l.AVG_RUNNING_THREADS, 2) AS AVG_THREADS,
       ROUND(l.AVG_QUEUED_LOAD, 2) AS AVG_QUEUE,
       CASE
           WHEN l.AVG_QUEUED_LOAD > 0.1 THEN 'OVERUSED_QUEUING'
           WHEN l.AVG_RUNNING_THREADS < 0.5 THEN 'UNDERUTILIZED'
           ELSE 'HEALTHY'
       END AS HEALTH_STATUS
FROM cost c
INNER JOIN load_stats l ON c.WAREHOUSE_NAME = l.WAREHOUSE_NAME
ORDER BY c.TOTAL_CREDITS DESC
LIMIT 15
"""

_WH_HEATMAP_SQL = """
WITH top_wh AS (
    SELECT WAREHOUSE_NAME, SUM(CREDITS_USED_COMPUTE) AS TOTAL_CREDITS
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY WAREHOUSE_NAME
    HAVING TOTAL_CREDITS >= 1
    ORDER BY TOTAL_CREDITS DESC
    LIMIT 15
),
wh_load AS (
    SELECT
        HOUR(DATE_TRUNC('hour', wlh.START_TIME)) AS HOUR_OF_DAY,
        wlh.WAREHOUSE_NAME,
        ROUND(AVG(wlh.AVG_RUNNING), 4) AS AVG_QUERY_LOAD
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY wlh
    INNER JOIN top_wh tw ON wlh.WAREHOUSE_NAME = tw.WAREHOUSE_NAME
    WHERE wlh.START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY ALL
)
SELECT tw.WAREHOUSE_NAME, tw.TOTAL_CREDITS,
       wl.HOUR_OF_DAY, wl.AVG_QUERY_LOAD
FROM top_wh tw
LEFT JOIN wh_load wl ON tw.WAREHOUSE_NAME = wl.WAREHOUSE_NAME
ORDER BY tw.TOTAL_CREDITS DESC, wl.HOUR_OF_DAY
"""

_WH_CREDIT_TS_SQL = """
WITH top_wh AS (
    SELECT WAREHOUSE_NAME, SUM(CREDITS_USED_COMPUTE) AS TOTAL_CREDITS
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY WAREHOUSE_NAME
    ORDER BY TOTAL_CREDITS DESC
    LIMIT 10
)
SELECT DATE_TRUNC('day', wmh.START_TIME) AS DAY,
       wmh.WAREHOUSE_NAME,
       SUM(wmh.CREDITS_USED_COMPUTE) AS COMPUTE_CREDITS,
       SUM(wmh.CREDITS_USED_COMPUTE - wmh.CREDITS_ATTRIBUTED_COMPUTE_QUERIES) AS IDLE_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY wmh
INNER JOIN top_wh tw ON wmh.WAREHOUSE_NAME = tw.WAREHOUSE_NAME
WHERE wmh.START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND wmh.CREDITS_USED_COMPUTE > 0
GROUP BY ALL
ORDER BY DAY, wmh.WAREHOUSE_NAME
"""

_WH_HOURLY_ACTIVITY_SQL = """
SELECT HOUR(START_TIME) AS HOUR_OF_DAY,
       COUNT(*) AS QUERY_COUNT,
       ROUND(AVG(TOTAL_ELAPSED_TIME) / 1000.0, 2) AS AVG_DURATION_SEC,
       ROUND(SUM(BYTES_SCANNED) / POW(1024, 4), 3) AS TOTAL_TB_SCANNED
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_NAME IS NOT NULL
GROUP BY HOUR(START_TIME)
ORDER BY HOUR_OF_DAY
"""

_WH_CONSTRAINT_SQL = """
SELECT WAREHOUSE_NAME,
       COUNT(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 END) AS REMOTE_SPILLS,
       COUNT(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 END) AS LOCAL_SPILLS,
       ROUND(SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) / POW(1024, 3), 2) AS REMOTE_SPILL_GB,
       ROUND(SUM(BYTES_SPILLED_TO_LOCAL_STORAGE) / POW(1024, 3), 2) AS LOCAL_SPILL_GB
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_NAME IS NOT NULL
GROUP BY WAREHOUSE_NAME
HAVING REMOTE_SPILLS > 0 OR LOCAL_SPILLS > 0
ORDER BY REMOTE_SPILLS DESC, LOCAL_SPILLS DESC
"""

_WH_OVERSIZING_SQL = """
WITH node_mapping AS (
    SELECT 'X-Small' AS size, 1 AS nodes UNION ALL
    SELECT 'Small', 2 UNION ALL SELECT 'Medium', 4 UNION ALL
    SELECT 'Large', 8 UNION ALL SELECT 'X-Large', 16 UNION ALL
    SELECT '2X-Large', 32 UNION ALL SELECT '3X-Large', 64 UNION ALL
    SELECT '4X-Large', 128 UNION ALL SELECT '5X-Large', 256 UNION ALL
    SELECT '6X-Large', 512
)
SELECT q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE,
       COUNT(*) AS TOTAL_QUERIES,
       COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END) AS OVERSIZED_QUERIES,
       ROUND(COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS PCT_OVERSIZED
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
INNER JOIN node_mapping n ON q.WAREHOUSE_SIZE = n.size
WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND q.WAREHOUSE_SIZE NOT IN ('X-Small', 'Small')
  AND q.PARTITIONS_SCANNED > 0
GROUP BY q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE
HAVING TOTAL_QUERIES > 0
ORDER BY PCT_OVERSIZED DESC
"""

_WH_IDLE_SQL = """
SELECT l.WAREHOUSE_NAME,
       COUNT(*) AS INTERVAL_COUNT,
       SUM(CASE WHEN l.AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) AS IDLE_INTERVALS,
       ROUND(SUM(CASE WHEN l.AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS PCT_TIME_IDLE,
       ROUND(AVG(l.AVG_RUNNING), 2) AS AVG_RUNNING_THREADS,
       ROUND(COUNT(*) * 5.0 / 60.0, 2) AS EST_UPTIME_HOURS,
       ROUND(SUM(CASE WHEN l.AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) * 5.0 / 60.0, 2) AS EST_IDLE_HOURS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY l
WHERE l.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY l.WAREHOUSE_NAME
HAVING EST_UPTIME_HOURS > 1
ORDER BY PCT_TIME_IDLE DESC
"""

_WH_WORKLOAD_SQL = """
SELECT WAREHOUSE_NAME, WAREHOUSE_SIZE,
       COUNT(*) AS TOTAL_QUERIES,
       SUM(CASE WHEN BYTES_SCANNED < 104857600 THEN 1 ELSE 0 END) AS TINY_UNDER_100MB,
       SUM(CASE WHEN BYTES_SCANNED >= 104857600 AND BYTES_SCANNED < 1073741824 THEN 1 ELSE 0 END) AS SMALL_100MB_1GB,
       SUM(CASE WHEN BYTES_SCANNED >= 1073741824 AND BYTES_SCANNED < 107374182400 THEN 1 ELSE 0 END) AS LARGE_1GB_100GB,
       SUM(CASE WHEN BYTES_SCANNED >= 107374182400 THEN 1 ELSE 0 END) AS MASSIVE_OVER_100GB,
       ROUND(SUM(CASE WHEN BYTES_SCANNED < 104857600 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS TINY_QUERY_PCT
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_SIZE IS NOT NULL
  AND WAREHOUSE_NAME IS NOT NULL
GROUP BY WAREHOUSE_NAME, WAREHOUSE_SIZE
ORDER BY TOTAL_QUERIES DESC
LIMIT 20
"""

_WH_CONFIG_CHANGES_SQL = """
SELECT WAREHOUSE_NAME,
       COUNT(CASE WHEN EVENT_NAME = 'RESIZE_WAREHOUSE' THEN 1 END) AS RESIZE_EVENTS,
       COUNT(CASE WHEN EVENT_NAME = 'CONVERT_WAREHOUSE' THEN 1 END) AS CONVERSION_EVENTS,
       MAX(TIMESTAMP) AS LAST_EVENT_TIME
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY
WHERE TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY WAREHOUSE_NAME
HAVING RESIZE_EVENTS > 0 OR CONVERSION_EVENTS > 0
ORDER BY RESIZE_EVENTS DESC
"""

_WH_DATA_SKEW_SQL = """
SELECT
    query_id, warehouse_name, user_name,
    ROUND(total_elapsed_time / 1000.0, 1) AS duration_sec,
    ROUND(bytes_scanned / POWER(1024, 3), 2) AS scanned_gb,
    ROUND((bytes_spilled_to_local_storage + bytes_spilled_to_remote_storage) / POWER(1024, 3), 2) AS spilled_gb,
    ROUND((bytes_spilled_to_local_storage + bytes_spilled_to_remote_storage) / NULLIF(bytes_scanned, 0) * 100, 1) AS spill_ratio_pct,
    LEFT(query_text, 120) AS query_preview
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
  AND (bytes_spilled_to_local_storage + bytes_spilled_to_remote_storage) > 0
  AND bytes_scanned > 0
ORDER BY spill_ratio_pct DESC
LIMIT 20
"""

_WH_LOAD_DISTRIBUTION_SQL = """
SELECT
    user_name, role_name, warehouse_name,
    COUNT(*) AS query_count,
    ROUND(SUM(total_elapsed_time) / 3600000.0, 2) AS total_hours,
    ROUND(AVG(bytes_scanned) / POWER(1024, 3), 3) AS avg_scanned_gb,
    ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) AS pct_of_total
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
  AND warehouse_name IS NOT NULL
GROUP BY user_name, role_name, warehouse_name
ORDER BY query_count DESC
LIMIT 20
"""

_WH_POOR_PRUNING_SQL = """
SELECT
    query_id, warehouse_name, user_name,
    partitions_scanned, partitions_total,
    ROUND(partitions_scanned * 100.0 / NULLIF(partitions_total, 0), 1) AS scan_pct,
    ROUND(bytes_scanned / POWER(1024, 3), 2) AS scanned_gb,
    ROUND(total_elapsed_time / 1000.0, 1) AS duration_sec,
    LEFT(query_text, 120) AS query_preview
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
  AND partitions_total > 1000
  AND partitions_scanned > partitions_total * 0.9
ORDER BY partitions_scanned DESC
LIMIT 20
"""


_ALL_WH_QUERIES = {
    "wh_fleet_data": _WH_FLEET_SQL,
    "wh_credits_health": _WH_CREDITS_SQL,
    "wh_heatmap_data": _WH_HEATMAP_SQL,
    "wh_credit_ts_data": _WH_CREDIT_TS_SQL,
    "wh_hourly_activity": _WH_HOURLY_ACTIVITY_SQL,
    "wh_constraint_data": _WH_CONSTRAINT_SQL,
    "wh_oversizing_data": _WH_OVERSIZING_SQL,
    "wh_idle_data": _WH_IDLE_SQL,
    "wh_workload_data": _WH_WORKLOAD_SQL,
    "wh_config_changes": _WH_CONFIG_CHANGES_SQL,
    "wh_data_skew": _WH_DATA_SKEW_SQL,
    "wh_load_distribution": _WH_LOAD_DISTRIBUTION_SQL,
    "wh_poor_pruning": _WH_POOR_PRUNING_SQL,
}


def _run_query(sql):
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        return session.sql(sql).to_pandas()
    except Exception as e:
        st.warning(f"Query error: {e}")
        return pd.DataFrame()


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_wh_queries(progress_bar=None, status_text=None):
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_WH_QUERIES.items() if k not in st.session_state}
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


PALETTE = CHART_SERIES + CHART_EXTENDED


def comp_warehouse_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in _ALL_WH_QUERIES)
        if not all_cached:
            status_ph.markdown(
                '<p style="color: #003D73; font-weight: 600;">Loading Virtual Warehouses data...</p>',
                unsafe_allow_html=True)
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_all_wh_queries(progress_bar=progress_bar_widget, status_text=status_ph)
            progress_ph.empty()
            status_ph.empty()

        sub_tabs = st.tabs(["Overview", "Scaling Management", "Performance Monitoring", "Fleet & Query Analysis"])

        with sub_tabs[0]:
            _render_overview()

        with sub_tabs[1]:
            comp_scaling_management()

        with sub_tabs[2]:
            comp_performance_monitoring()

        with sub_tabs[3]:
            _render_fleet_query()

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
            f'Error loading Warehouses Overview: {e}</div>',
            unsafe_allow_html=True,
        )


def _render_overview():
    ck = "wh_fleet_data"
    df = st.session_state.get(ck, pd.DataFrame())

    ck2 = "wh_credits_health"
    credits_df = st.session_state.get(ck2, pd.DataFrame())

    if df.empty:
        st.info("No warehouse data found.")
        return

    total = len(df)
    size_counts = df["WAREHOUSE_SIZE"].value_counts()
    type_counts = df["WAREHOUSE_TYPE"].value_counts()

    m1, m2, m3 = st.columns(3)
    m1.metric("Active Warehouses", total)
    m2.metric("Warehouse Types", len(type_counts))
    m3.metric("Size Variants", len(size_counts))

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Fleet Distribution by Size")
        sizes = size_counts.index.tolist()
        counts = size_counts.values.tolist()
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(sizes))]
        fig = go.Figure(data=[go.Bar(
            x=sizes, y=counts,
            marker_color=colors,
            text=counts, textposition="outside",
            hovertemplate="<b>%{x}</b><br>Count: %{y}<extra></extra>",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=40, r=20), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Top 15 Warehouses by Credit Consumption")
        if not credits_df.empty:
            top = credits_df.head(15)
            colors = [PALETTE[i % len(PALETTE)] for i in range(len(top))]
            fig = go.Figure(data=[go.Bar(
                y=top["WAREHOUSE_NAME"], x=top["CREDITS_30_DAY"],
                orientation="h", marker_color=colors,
                text=[f"{v:.1f}" for v in top["CREDITS_30_DAY"]],
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Credits: %{x:.2f}<br>Status: %{customdata}<extra></extra>",
                customdata=top["HEALTH_STATUS"],
            )])
            fig.update_layout(
                height=max(300, len(top) * 30),
                margin=dict(t=10, b=40, l=160, r=60),
                xaxis_title="Credits (30 days)", showlegend=False,
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No credit data available.")

    with st.expander("Active Warehouse Fleet Details", expanded=True):
        if not credits_df.empty:
            df_display = df.merge(credits_df[["WAREHOUSE_NAME", "CREDITS_30_DAY", "HEALTH_STATUS"]], on="WAREHOUSE_NAME", how="left").fillna(0)
        else:
            df_display = df.copy()
        st.dataframe(df_display, use_container_width=True)

    with st.expander("Data Skew Detection (High Spill Ratio)", expanded=True):
        _render_data_skew_detection()

    with st.expander("User/Role/Warehouse Load Distribution", expanded=True):
        _render_load_distribution()

    with st.expander("Poor Partition Pruning Detection", expanded=True):
        _render_poor_pruning()


def _render_data_skew_detection():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Data Skew:</b> Queries with the highest spill-to-scan ratio (last 7 days). '
        'High ratios indicate data skew or insufficient warehouse sizing.</div>',
        unsafe_allow_html=True)
    df = st.session_state.get("wh_data_skew", pd.DataFrame())
    if df.empty:
        st.success("No queries with significant data spill detected in the last 7 days.")
        return
    df['SPILL_RATIO_PCT'] = pd.to_numeric(df['SPILL_RATIO_PCT'], errors='coerce').fillna(0)
    fig = go.Figure(go.Bar(
        y=df['QUERY_ID'].astype(str).str[:12], x=df['SPILL_RATIO_PCT'],
        orientation='h', marker_color=CHART_SERIES[3],
        text=[f"{v:.0f}%" for v in df['SPILL_RATIO_PCT']], textposition='outside'
    ))
    fig.update_layout(
        title='Top Queries by Spill-to-Scan Ratio',
        xaxis_title='Spill Ratio %', height=max(300, len(df) * 25 + 80),
        margin=dict(t=50, l=120, r=40, b=60)
    )
    fig.update_yaxes(autorange='reversed')
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df[['QUERY_ID', 'WAREHOUSE_NAME', 'USER_NAME', 'DURATION_SEC', 'SCANNED_GB', 'SPILLED_GB', 'SPILL_RATIO_PCT']])


def _render_load_distribution():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Load Distribution:</b> Top 20 user/role/warehouse combinations by query volume (last 7 days).</div>',
        unsafe_allow_html=True)
    df = st.session_state.get("wh_load_distribution", pd.DataFrame())
    if df.empty:
        st.info("No query activity data available.")
        return
    df['QUERY_COUNT'] = pd.to_numeric(df['QUERY_COUNT'], errors='coerce').fillna(0)
    df['LABEL'] = df['USER_NAME'] + ' / ' + df['WAREHOUSE_NAME']
    fig = go.Figure(go.Bar(
        y=df['LABEL'].head(15), x=df['QUERY_COUNT'].head(15),
        orientation='h', marker_color=BRAND_SECONDARY,
        text=df['QUERY_COUNT'].head(15).astype(int), textposition='outside'
    ))
    fig.update_layout(
        title='Top Query Load Combinations (User/Warehouse)',
        xaxis_title='Query Count', height=max(300, 15 * 30 + 80),
        margin=dict(t=50, l=250, r=40, b=60)
    )
    fig.update_yaxes(autorange='reversed')
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df[['USER_NAME', 'ROLE_NAME', 'WAREHOUSE_NAME', 'QUERY_COUNT', 'TOTAL_HOURS', 'AVG_SCANNED_GB', 'PCT_OF_TOTAL']])


def _render_poor_pruning():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Poor Partition Pruning:</b> Queries scanning >90% of large tables (>1000 partitions). '
        'Consider adding clustering keys or rewriting predicates.</div>',
        unsafe_allow_html=True)
    df = st.session_state.get("wh_poor_pruning", pd.DataFrame())
    if df.empty:
        st.success("No queries with poor partition pruning detected in the last 7 days.")
        return
    df['SCAN_PCT'] = pd.to_numeric(df['SCAN_PCT'], errors='coerce').fillna(0)
    fig = go.Figure(go.Bar(
        y=df['QUERY_ID'].astype(str).str[:12], x=df['SCAN_PCT'],
        orientation='h', marker_color=CHART_SERIES[3],
        text=[f"{v:.0f}%" for v in df['SCAN_PCT']], textposition='outside'
    ))
    fig.update_layout(
        title='Top Queries by Partition Scan %',
        xaxis_title='% Partitions Scanned', height=max(300, len(df) * 25 + 80),
        margin=dict(t=50, l=120, r=40, b=60)
    )
    fig.update_yaxes(autorange='reversed')
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df[['QUERY_ID', 'WAREHOUSE_NAME', 'PARTITIONS_SCANNED', 'PARTITIONS_TOTAL', 'SCAN_PCT', 'SCANNED_GB', 'DURATION_SEC']])


def _render_fleet_query():
    st.markdown("#### Credit Usage by Warehouse (Last 30 Days)")
    df = st.session_state.get("wh_credit_ts_data", pd.DataFrame())

    if df.empty:
        st.info("No credit usage data available.")
    else:
        warehouses = df["WAREHOUSE_NAME"].unique().tolist()
        fig = go.Figure()
        for i, wh in enumerate(warehouses):
            wh_data = df[df["WAREHOUSE_NAME"] == wh].sort_values("DAY")
            fig.add_trace(go.Scatter(
                x=wh_data["DAY"], y=wh_data["COMPUTE_CREDITS"],
                mode="lines", fill="tonexty" if i > 0 else "tozeroy",
                name=wh,
                line=dict(color=PALETTE[i % len(PALETTE)]),
                stackgroup="one",
                hovertemplate="<b>%{fullData.name}</b><br>Date: %{x}<br>Credits: %{y:.2f}<extra></extra>",
            ))
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=40, r=20),
                          xaxis_title="Date", yaxis_title="Compute Credits", showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Warehouse Query Workload Profile (Last 7 Days)")
    wl_df = st.session_state.get("wh_workload_data", pd.DataFrame())

    if wl_df.empty:
        st.info("No workload profile data available.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Tiny (<100MB)", x=wl_df["WAREHOUSE_NAME"], y=wl_df["TINY_UNDER_100MB"], marker_color=CHART_SERIES[0]))
        fig.add_trace(go.Bar(name="Small (100MB-1GB)", x=wl_df["WAREHOUSE_NAME"], y=wl_df["SMALL_100MB_1GB"], marker_color=CHART_SERIES[1]))
        fig.add_trace(go.Bar(name="Large (1-100GB)", x=wl_df["WAREHOUSE_NAME"], y=wl_df["LARGE_1GB_100GB"], marker_color=CHART_SERIES[2]))
        fig.add_trace(go.Bar(name="Massive (>100GB)", x=wl_df["WAREHOUSE_NAME"], y=wl_df["MASSIVE_OVER_100GB"], marker_color=CHART_SERIES[3]))
        fig.update_layout(barmode="stack", height=400, margin=dict(t=10, b=60, l=40, r=20),
                          xaxis_title="Warehouse", yaxis_title="Query Count", showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(wl_df, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Idle Percentage by Warehouse")
    ts_df = st.session_state.get("wh_credit_ts_data", pd.DataFrame())
    if not ts_df.empty:
        idle_df = (
            ts_df.groupby("WAREHOUSE_NAME")
            .agg({"COMPUTE_CREDITS": "sum", "IDLE_CREDITS": "sum"})
            .reset_index()
        )
        idle_df["IDLE_PCT"] = (idle_df["IDLE_CREDITS"] / idle_df["COMPUTE_CREDITS"] * 100).round(1)
        idle_df = idle_df.sort_values("IDLE_PCT", ascending=True)

        fig = go.Figure(data=[go.Bar(
            y=idle_df["WAREHOUSE_NAME"], x=idle_df["IDLE_PCT"],
            orientation="h", marker_color=BRAND_SECONDARY,
            text=[f"{v:.1f}%" for v in idle_df["IDLE_PCT"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Idle: %{x:.1f}%<extra></extra>",
        )])
        fig.update_layout(
            height=max(300, len(idle_df) * 35),
            margin=dict(t=10, b=40, l=160, r=60),
            xaxis_title="Idle %", showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

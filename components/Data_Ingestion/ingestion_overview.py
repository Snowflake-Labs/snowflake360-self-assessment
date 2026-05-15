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
from core.config.design_tokens import CHART_SERIES, CHART_EXTENDED, BRAND_SECONDARY, BRAND_ACCENT, COLOR_LIGHT

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

from .bulk_load_analysis import comp_bulk_load_analysis
from .snowpipe_analysis import comp_snowpipe_analysis

_SNOWPIPE_STREAMING_SQL = """
SELECT
    usage_date::DATE AS usage_date,
    ROUND(SUM(credits_used), 4) AS credits_used
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
WHERE service_type = 'SNOWPIPE_STREAMING'
  AND usage_date >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY 1
ORDER BY 1
"""

_INGESTION_SUMMARY_SQL = """
WITH copy_summary AS (
    SELECT
        'COPY Command' AS method,
        COUNT(*) AS job_count,
        SUM(file_size) / POW(1024, 3) AS gb_loaded,
        SUM(row_count) AS rows_loaded,
        ROUND(AVG(file_size) / POW(1024, 2), 2) AS avg_file_mb,
        0 AS credits_last_30_days
    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
    WHERE status = 'Loaded'
      AND pipe_name IS NULL
      AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
pipe_summary AS (
    SELECT
        'Snowpipe' AS method,
        COUNT(*) AS job_count,
        SUM(ch.file_size) / POW(1024, 3) AS gb_loaded,
        SUM(ch.row_count) AS rows_loaded,
        ROUND(AVG(ch.file_size) / POW(1024, 2), 2) AS avg_file_mb,
        (SELECT COALESCE(SUM(credits_used), 0)
         FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
         WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())) AS credits_last_30_days
    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY ch
    WHERE ch.status = 'Loaded'
      AND ch.pipe_name IS NOT NULL
      AND ch.last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
streaming_summary AS (
    SELECT
        'Snowpipe Streaming' AS method,
        0 AS job_count,
        0 AS gb_loaded,
        0 AS rows_loaded,
        0 AS avg_file_mb,
        COALESCE((SELECT SUM(credits_used)
         FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
         WHERE service_type = 'SNOWPIPE_STREAMING'
           AND usage_date >= DATEADD('day', -30, CURRENT_DATE)), 0) AS credits_last_30_days
)
SELECT
    method AS ingestion_method,
    job_count AS events_or_channels,
    ROUND(COALESCE(gb_loaded, 0), 3) AS gb_loaded_30d,
    COALESCE(rows_loaded, 0) AS rows_loaded_30d,
    COALESCE(avg_file_mb, 0) AS avg_file_mb,
    ROUND(COALESCE(credits_last_30_days, 0), 4) AS credits_last_30_days
FROM copy_summary
UNION ALL
SELECT method, job_count, ROUND(COALESCE(gb_loaded, 0), 3), COALESCE(rows_loaded, 0), COALESCE(avg_file_mb, 0), ROUND(COALESCE(credits_last_30_days, 0), 4)
FROM pipe_summary
UNION ALL
SELECT method, job_count, gb_loaded, rows_loaded, avg_file_mb, ROUND(credits_last_30_days, 4)
FROM streaming_summary
ORDER BY gb_loaded_30d DESC NULLS LAST
"""


def _run_query(sql):
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        return session.sql(sql).to_pandas()
    except Exception:
        return pd.DataFrame()


_STREAMING_BREAKDOWN_SQL = """
SELECT
    entity_id AS service_entity,
    ROUND(SUM(credits_used), 4) AS total_credits,
    COUNT(DISTINCT usage_date) AS active_days,
    MIN(usage_date) AS first_seen,
    MAX(usage_date) AS last_seen
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
WHERE service_type = 'SNOWPIPE_STREAMING'
  AND usage_date >= DATEADD('day', -30, CURRENT_DATE)
GROUP BY entity_id
ORDER BY total_credits DESC
"""

_BULK_LOAD_SQL = """
WITH copy_stats AS (
    SELECT
        table_catalog_name || '.' || table_schema_name || '.' || table_name AS target_table,
        COUNT(*) AS job_count,
        SUM(row_count) AS total_rows_loaded,
        ROUND(SUM(file_size) / POW(1024, 3), 2) AS total_gb,
        ROUND(AVG(file_size) / POW(1024, 2), 2) AS avg_file_mb,
        ROUND(MIN(file_size) / POW(1024, 2), 2) AS min_file_mb,
        ROUND(MAX(file_size) / POW(1024, 2), 2) AS max_file_mb,
        ROUND(STDDEV(file_size) / POW(1024, 2), 2) AS stddev_file_mb,
        CASE
            WHEN MAX(file_size) > (AVG(file_size) * 100) THEN '⚠️ High Variance (Outliers)'
            WHEN AVG(file_size) / POW(1024, 2) < 10 THEN '⚠️ Small Files (<10MB)'
            ELSE '✅ Healthy'
        END AS health_check,
        CASE
            WHEN MAX(file_size) > (AVG(file_size) * 100) THEN 'High file size variance detected'
            WHEN AVG(file_size) / POW(1024, 2) < 10 THEN 'Batch files before ingestion'
            ELSE 'File sizing looks appropriate'
        END AS recommendation
    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
    WHERE status = 'Loaded'
      AND pipe_name IS NULL
      AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY 1
)
SELECT
    target_table,
    job_count,
    total_gb,
    total_rows_loaded,
    avg_file_mb,
    min_file_mb,
    max_file_mb,
    stddev_file_mb,
    health_check,
    recommendation
FROM copy_stats
ORDER BY total_gb DESC
LIMIT 20
"""

_PIPE_EFFICIENCY_SQL = """
WITH pipe_costs AS (
    SELECT
        pipe_name,
        SUM(credits_used) AS credits_30d,
        SUM(bytes_inserted) / POW(1024, 3) AS bytes_gb_30d,
        SUM(files_inserted) AS files_inserted_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY 1
),
pipe_volume AS (
    SELECT
        pipe_name,
        COUNT(*) AS files_loaded,
        SUM(file_size) / POW(1024, 3) AS gb_loaded,
        AVG(file_size) / POW(1024, 2) AS avg_file_mb,
        SUM(row_count) AS rows_loaded
    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
    WHERE pipe_name IS NOT NULL
      AND status = 'Loaded'
      AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY 1
)
SELECT
    COALESCE(v.pipe_name, c.pipe_name) AS pipe_name,
    COALESCE(v.files_loaded, 0) AS files_loaded,
    ROUND(COALESCE(v.gb_loaded, 0), 3) AS gb_ingested,
    COALESCE(v.rows_loaded, 0) AS rows_loaded,
    ROUND(COALESCE(v.avg_file_mb, 0), 2) AS avg_file_mb,
    ROUND(COALESCE(c.credits_30d, 0), 4) AS credits_used,
    ROUND(COALESCE(c.credits_30d, 0) / NULLIF(COALESCE(v.gb_loaded, 0), 0), 4) AS credits_per_gb,
    CASE
        WHEN COALESCE(v.gb_loaded, 0) = 0 AND COALESCE(c.credits_30d, 0) > 0 THEN '🔴 Idle Burning Credits'
        WHEN COALESCE(c.credits_30d, 0) / NULLIF(COALESCE(v.gb_loaded, 0), 0) > 1 THEN '🟡 High Cost per GB'
        WHEN COALESCE(v.avg_file_mb, 0) < 10 THEN '🟡 Small File Overhead'
        ELSE '🟢 Efficient'
    END AS efficiency_status,
    CASE
        WHEN COALESCE(v.gb_loaded, 0) = 0 AND COALESCE(c.credits_30d, 0) > 0
            THEN 'Pipe is active but not loading data - consider suspending'
        WHEN COALESCE(c.credits_30d, 0) / NULLIF(COALESCE(v.gb_loaded, 0), 0) > 1
            THEN 'High cost per GB - review file sizes and batching strategy'
        WHEN COALESCE(v.avg_file_mb, 0) < 10
            THEN 'Batch small files before ingestion'
        ELSE 'Pipe is operating efficiently'
    END AS recommendation
FROM pipe_volume v
FULL OUTER JOIN pipe_costs c ON v.pipe_name = c.pipe_name
ORDER BY COALESCE(c.credits_30d, 0) DESC
"""

_SNOWPIPE_DETAIL_SQL = """
SELECT
    pipe_name,
    ROUND(SUM(credits_used), 4) AS credits_burned,
    SUM(files_inserted) AS files_inserted,
    ROUND(SUM(bytes_inserted) / POW(1024, 3), 3) AS gb_loaded,
    CASE
        WHEN SUM(bytes_inserted) = 0 AND SUM(credits_used) > 0 THEN '🔴 Overhead Only'
        WHEN SUM(bytes_inserted) > 0 AND (SUM(credits_used) / (SUM(bytes_inserted) / POW(1024, 3))) > 1 THEN '🟡 High Overhead'
        ELSE '🟢 Efficient'
    END AS status,
    CASE
        WHEN SUM(bytes_inserted) = 0 AND SUM(credits_used) > 0
            THEN 'Pipe consuming credits without loading data - suspend or investigate'
        WHEN SUM(bytes_inserted) > 0 AND (SUM(credits_used) / (SUM(bytes_inserted) / POW(1024, 3))) > 1
            THEN 'High credit cost per GB - review file sizes and notification frequency'
        ELSE 'Pipe is operating efficiently'
    END AS recommendation
FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY credits_burned DESC
LIMIT 10
"""

_PIPE_COST_PROJECTION_SQL = """
WITH snowpipe_costs AS (
    SELECT
        'Snowpipe (File-based)' AS ingest_method,
        SUM(credits_used) AS total_credits,
        SUM(bytes_inserted) / POW(1024, 3) AS total_gb,
        SUM(files_inserted) AS total_files
    FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
streaming_costs AS (
    SELECT
        'Snowpipe Streaming' AS ingest_method,
        SUM(credits_used_compute + credits_used_cloud_services) AS total_credits,
        NULL AS total_gb,
        NULL AS total_files
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE service_type = 'SNOWPIPE_STREAMING'
      AND usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
combined AS (
    SELECT * FROM snowpipe_costs
    UNION ALL
    SELECT * FROM streaming_costs
)
SELECT
    ingest_method,
    ROUND(COALESCE(total_credits, 0), 4) AS credits_last_30_days,
    ROUND(COALESCE(total_gb, 0), 2) AS gb_ingested_30_days,
    COALESCE(total_files, 0) AS files_processed_30_days,
    ROUND(COALESCE(total_credits, 0) * 3, 0) AS est_credits_3_months,
    ROUND(COALESCE(total_credits, 0) * 6, 0) AS est_credits_6_months,
    ROUND(COALESCE(total_credits, 0) * 12, 0) AS est_credits_12_months,
    CASE
        WHEN COALESCE(total_credits, 0) > 100 THEN 'High Usage'
        WHEN COALESCE(total_credits, 0) > 10 THEN 'Moderate Usage'
        ELSE 'Low Usage'
    END AS usage_tier
FROM combined
WHERE COALESCE(total_credits, 0) > 0
ORDER BY COALESCE(total_credits, 0) DESC
"""

_STREAMING_MIGRATION_SQL = """
SELECT
    DATE_TRUNC('month', sfmh.start_time) AS usage_month,
    sfmh.table_name,
    sfmh.schema_name,
    sfmh.database_name,
    ROUND(SUM(sfmh.credits_used)) AS monthly_credits,
    ROUND(SUM(sfmh.credits_used) * 3.96) AS estimated_monthly_cost,
    SUM(sfmh.num_bytes_migrated) AS total_bytes_migrated,
    SUM(sfmh.num_rows_migrated) AS total_rows_migrated,
    COUNT(*) AS migration_events
FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPIPE_STREAMING_FILE_MIGRATION_HISTORY sfmh
WHERE sfmh.start_time >= DATEADD(month, -6, CURRENT_DATE())
GROUP BY DATE_TRUNC('month', sfmh.start_time), sfmh.table_name, sfmh.schema_name, sfmh.database_name
ORDER BY usage_month DESC, monthly_credits DESC
"""

_STREAMING_MTD_SQL = """
SELECT
    ROUND(SUM(CASE WHEN DATE_TRUNC('month', mdh.usage_date) = DATE_TRUNC('month', CURRENT_DATE()) THEN mdh.credits_billed * 3.96 ELSE 0 END)) AS current_mtd_streaming_cost,
    ROUND(SUM(CASE WHEN DATE_TRUNC('month', mdh.usage_date) = DATE_TRUNC('month', DATEADD('month', -1, CURRENT_DATE())) AND mdh.usage_date <= DATEADD('month', -1, CURRENT_DATE()) THEN mdh.credits_billed * 3.96 ELSE 0 END)) AS previous_mtd_streaming_cost,
    ROUND(SUM(CASE WHEN DATE_TRUNC('month', mdh.usage_date) = DATE_TRUNC('month', CURRENT_DATE()) THEN mdh.credits_billed ELSE 0 END)) AS current_mtd_streaming_credits,
    ROUND(SUM(CASE WHEN DATE_TRUNC('month', mdh.usage_date) = DATE_TRUNC('month', DATEADD('month', -1, CURRENT_DATE())) AND mdh.usage_date <= DATEADD('month', -1, CURRENT_DATE()) THEN mdh.credits_billed ELSE 0 END)) AS previous_mtd_streaming_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY mdh
WHERE mdh.service_type = 'SNOWPIPE_STREAMING'
  AND mdh.usage_date >= DATE_TRUNC('month', DATEADD('month', -1, CURRENT_DATE()))
"""

_ALL_INGESTION_QUERIES = {
    "ingestion_streaming_data": _SNOWPIPE_STREAMING_SQL,
    "ingestion_summary_data": _INGESTION_SUMMARY_SQL,
    "ingestion_streaming_breakdown": _STREAMING_BREAKDOWN_SQL,
    "ig_bulk_load": _BULK_LOAD_SQL,
    "ig_pipe_efficiency": _PIPE_EFFICIENCY_SQL,
    "ig_snowpipe_detail": _SNOWPIPE_DETAIL_SQL,
    "ig_pipe_cost_projection": _PIPE_COST_PROJECTION_SQL,
    "ig_streaming_migration": _STREAMING_MIGRATION_SQL,
    "ig_streaming_mtd": _STREAMING_MTD_SQL,
}


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_ingestion_queries(progress_bar=None, status_text=None):
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_INGESTION_QUERIES.items() if k not in st.session_state}
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


def _render_snowpipe_streaming():
    st.markdown("#### Snowpipe Streaming Credit Usage (Last 30 Days)")
    st.caption("Daily credit consumption from Snowpipe Streaming ingestion.")

    ck = "ingestion_streaming_data"
    if ck not in st.session_state:
        st.session_state[ck] = _run_query(_SNOWPIPE_STREAMING_SQL)
    df = st.session_state[ck]

    if df.empty:
        st.info("No Snowpipe Streaming activity detected in the last 30 days.")
        return

    df["credits_used"] = df["credits_used"].astype(float)

    total_credits = df["credits_used"].sum()
    peak_day = df.loc[df["credits_used"].idxmax(), "usage_date"] if len(df) > 0 else "N/A"
    active_days = len(df)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Credits (30d)", f"{total_credits:.4f}")
    m2.metric("Active Days", active_days)
    m3.metric("Peak Usage Date", str(peak_day))

    fig = go.Figure(data=[go.Bar(
        x=df["usage_date"].astype(str),
        y=df["credits_used"],
        marker_color=_C1,
        text=[f"{v:.4f}" for v in df["credits_used"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Credits: %{y:.4f}<extra></extra>",
    )])
    fig.update_layout(
        height=350,
        xaxis_title="Date",
        yaxis_title="Credits Used",
        showlegend=False,
        margin=dict(t=30, b=60, l=60, r=20)
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Snowpipe Streaming Daily Credit Details", expanded=True):
        st.dataframe(df, use_container_width=True)

    with st.expander("Snowpipe Streaming Service Breakdown", expanded=True):
        _render_streaming_service_breakdown()

    with st.expander("Streaming Channel Health (Table-Level)", expanded=True):
        _render_streaming_channel_health()


def _render_ingestion_summary():
    ck = "ingestion_summary_data"
    if ck not in st.session_state:
        st.session_state[ck] = _run_query(_INGESTION_SUMMARY_SQL)
    df = st.session_state[ck]

    if df.empty:
        st.info("No ingestion activity detected in the last 30 days.")
        return

    for col in ['EVENTS_OR_CHANNELS', 'GB_LOADED_30D', 'ROWS_LOADED_30D', 'AVG_FILE_MB', 'CREDITS_LAST_30_DAYS']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    with st.expander("Ingestion Method Summary Dashboard", expanded=True):
        st.caption("30-day comparison across COPY, Snowpipe, and Snowpipe Streaming using channel history for activity and metering history for streaming credits.")
        st.markdown("### Top-Line Ingestion Summary")
        st.dataframe(df, use_container_width=True)

        methods = df['INGESTION_METHOD'].tolist()
        colors = [_C1, _C2, _C3][:len(df)]

        c1, c2, c3 = st.columns(3)
        with c1:
            fig1 = go.Figure(go.Pie(
                labels=methods, values=df['EVENTS_OR_CHANNELS'].tolist(),
                hole=0.4, marker_colors=colors,
                textinfo='percent', textposition='inside',
                hovertemplate="<b>%{label}</b><br>Events: %{value:,.0f}<br>%{percent}<extra></extra>"))
            fig1.update_layout(title="Events / Channels by Method", height=320, margin=dict(t=40, b=10, l=10, r=10),
                               legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(fig1, use_container_width=True)

        with c2:
            fig2 = go.Figure(go.Pie(
                labels=methods, values=df['GB_LOADED_30D'].tolist(),
                hole=0.4, marker_colors=colors,
                textinfo='percent', textposition='inside',
                hovertemplate="<b>%{label}</b><br>GB: %{value:,.3f}<br>%{percent}<extra></extra>"))
            fig2.update_layout(title="Data Volume (GB) by Method", height=320, margin=dict(t=40, b=10, l=10, r=10),
                               legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(fig2, use_container_width=True)

        credits_col = 'CREDITS_LAST_30_DAYS' if 'CREDITS_LAST_30_DAYS' in df.columns else None
        with c3:
            if credits_col and df[credits_col].sum() > 0:
                credit_methods = df[df[credits_col] > 0]['INGESTION_METHOD'].tolist()
                credit_vals = df[df[credits_col] > 0][credits_col].tolist()
                credit_colors = [colors[i] for i, m in enumerate(methods) if m in credit_methods]
                fig3 = go.Figure(go.Pie(
                    labels=credit_methods, values=credit_vals,
                    hole=0.4, marker_colors=credit_colors,
                    textinfo='percent', textposition='inside',
                    hovertemplate="<b>%{label}</b><br>Credits: %{value:,.4f}<br>%{percent}<extra></extra>"))
                fig3.update_layout(title="Credits Consumed by Method", height=320, margin=dict(t=40, b=10, l=10, r=10),
                                   legend=dict(orientation="h", y=-0.1))
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("No credit data available.")

        st.markdown("#### Side-by-Side Ingestion Comparison")
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(x=methods, y=df['EVENTS_OR_CHANNELS'].tolist(), name='Events / Channels', marker_color=_C1))
        fig4.add_trace(go.Bar(x=methods, y=df['ROWS_LOADED_30D'].tolist(), name='Rows', marker_color=_C2))
        if credits_col:
            fig4.add_trace(go.Bar(x=methods, y=df[credits_col].tolist(), name='Credits', marker_color=_CA))
        fig4.update_layout(barmode='group', height=400, margin=dict(t=30, b=60, l=60, r=30),
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig4, use_container_width=True)

        st.dataframe(df, use_container_width=True)


def comp_ingestion_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in _ALL_INGESTION_QUERIES)
        if not all_cached:
            status_ph.markdown(
                '<p style="color: #003D73; font-weight: 600;">Loading Data Ingestion data...</p>',
                unsafe_allow_html=True)
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_all_ingestion_queries(progress_bar=progress_bar_widget, status_text=status_ph)
            progress_ph.empty()
            status_ph.empty()
        else:
            _prefetch_all_ingestion_queries()
        sub_tabs = st.tabs([
            "Bulk Load (COPY INTO) Analysis",
            "Snowpipe Analysis (Cost vs. Volume)",
            "Snowpipe Streaming",
            "Ingestion Summary Dashboard"
        ])

        with sub_tabs[0]:
            with st.spinner("Loading Bulk Load Analysis..."):
                comp_bulk_load_analysis()

        with sub_tabs[1]:
            with st.spinner("Loading Snowpipe Analysis..."):
                comp_snowpipe_analysis()

        with sub_tabs[2]:
            with st.spinner("Loading Snowpipe Streaming..."):
                _render_snowpipe_streaming()
                st.divider()
                _render_streaming_migration_charts()

        with sub_tabs[3]:
            with st.spinner("Loading Ingestion Summary Dashboard..."):
                _render_ingestion_summary()

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
            f'Error loading Data Ingestion Overview: {str(e)}'
            f'</div>', unsafe_allow_html=True)


def _render_streaming_service_breakdown():
    try:
        ck = "ingestion_streaming_breakdown"
        if ck in st.session_state:
            df = st.session_state[ck]
        else:
            df = _run_query(_STREAMING_BREAKDOWN_SQL)
            st.session_state[ck] = df
        if df.empty:
            st.info("No Snowpipe Streaming service-level detail available.")
            return
        df['TOTAL_CREDITS'] = pd.to_numeric(df['TOTAL_CREDITS'], errors='coerce').fillna(0)
        st.metric("Streaming Services/Entities", len(df))
        colors = [CHART_SERIES[i % len(CHART_SERIES)] for i in range(len(df))]
        fig = go.Figure(go.Bar(
            x=df['SERVICE_ENTITY'].astype(str), y=df['TOTAL_CREDITS'],
            marker_color=colors,
            text=[f"{v:,.4f}" for v in df['TOTAL_CREDITS']], textposition='outside'
        ))
        fig.update_layout(
            title='Snowpipe Streaming Credits by Entity (Last 30 Days)',
            yaxis_title='Credits', height=360, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading streaming breakdown: {e}")


def _render_streaming_channel_health():
    import plotly.graph_objects as go
    _C1 = '#29B5E8'
    _C2 = '#11567F'
    _CA = '#E8A229'
    session = st.session_state.get("session")
    if not session:
        return
    try:
        df = session.sql("""
            SELECT
                TABLE_DATABASE_NAME || '.' || TABLE_SCHEMA_NAME || '.' || TABLE_NAME AS TABLE_FQN,
                COUNT(DISTINCT CHANNEL_ID) AS ACTIVE_CHANNELS,
                SUM(ROWS_INSERTED) AS TOTAL_ROWS_INSERTED,
                SUM(ROW_ERROR_COUNT) AS TOTAL_ERRORS,
                ROUND(AVG(SNOWFLAKE_PROCESSING_LATENCY_MS), 1) AS AVG_LATENCY_MS,
                ROUND(MAX(SNOWFLAKE_PROCESSING_LATENCY_MS), 1) AS MAX_LATENCY_MS,
                ROUND(100.0 * SUM(ROW_ERROR_COUNT) / NULLIF(SUM(ROWS_PARSED), 0), 4) AS ERROR_RATE_PCT
            FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPIPE_STREAMING_CHANNEL_HISTORY
            WHERE CREATED_ON >= DATEADD('day', -30, CURRENT_DATE())
            GROUP BY 1
            ORDER BY TOTAL_ROWS_INSERTED DESC
            LIMIT 20
        """).to_pandas()
    except Exception:
        st.info("No streaming channel data available (`SNOWPIPE_STREAMING_CHANNEL_HISTORY`).")
        return
    if df.empty:
        st.info("No streaming channel activity in the last 30 days.")
        return
    total_channels = int(df["ACTIVE_CHANNELS"].sum())
    total_rows = int(df["TOTAL_ROWS_INSERTED"].sum())
    total_errors = int(df["TOTAL_ERRORS"].sum())
    avg_latency = round(float(df["AVG_LATENCY_MS"].mean()), 1)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Channels", f"{total_channels:,}")
    c2.metric("Rows Inserted (30d)", f"{total_rows:,}")
    c3.metric("Row Errors (30d)", f"{total_errors:,}")
    c4.metric("Avg Latency (ms)", f"{avg_latency:,.1f}")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Rows Inserted by Table (Top 20)")
        fig = go.Figure(data=[go.Bar(
            y=df["TABLE_FQN"].tolist()[::-1], x=df["TOTAL_ROWS_INSERTED"].tolist()[::-1],
            orientation="h", marker_color=_C1)])
        fig.update_layout(height=420, margin=dict(t=10, b=40, l=280, r=20), showlegend=False, xaxis_title="Rows")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Avg Latency by Table (ms)")
        fig = go.Figure(data=[go.Bar(
            y=df["TABLE_FQN"].tolist()[::-1], x=df["AVG_LATENCY_MS"].tolist()[::-1],
            orientation="h", marker_color=[_CA if v > 500 else _C2 for v in df["AVG_LATENCY_MS"].tolist()[::-1]])])
        fig.update_layout(height=420, margin=dict(t=10, b=40, l=280, r=20), showlegend=False, xaxis_title="Latency (ms)")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_streaming_migration_charts():
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Legacy Snowpipe Streaming")
        ck = "ig_streaming_migration"
        if ck not in st.session_state:
            st.session_state[ck] = _run_query(_STREAMING_MIGRATION_SQL)
        df = st.session_state[ck]
        if df.empty:
            st.info("No Snowpipe Streaming file migration data in the last 6 months.")
        else:
            for col in ["MONTHLY_CREDITS", "ESTIMATED_MONTHLY_COST"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            df["USAGE_MONTH"] = df["USAGE_MONTH"].astype(str).str[:7]
            months = sorted(df["USAGE_MONTH"].unique().tolist())
            tables = df["TABLE_NAME"].unique().tolist()[:10]
            bar_colors = [_C1, _CA, _C2, _C3] + list(CHART_SERIES)
            fig = go.Figure()
            for i, tbl in enumerate(tables):
                subset = df[df["TABLE_NAME"] == tbl]
                month_map = dict(zip(subset["USAGE_MONTH"], subset["MONTHLY_CREDITS"]))
                fig.add_trace(go.Bar(
                    name=tbl,
                    x=months,
                    y=[month_map.get(m, 0) for m in months],
                    marker_color=bar_colors[i % len(bar_colors)],
                    hovertemplate="<b>%{x}</b><br>%{fullData.name}<br>Credits: %{y:,.0f}<extra></extra>",
                ))
            fig.update_layout(
                barmode="stack",
                height=380,
                margin=dict(t=10, b=60, l=60, r=20),
                xaxis_title="Month",
                yaxis_title="Credits",
                legend=dict(orientation="h", y=-0.35, font=dict(size=11)),
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown("#### Streaming Trends")
        ck2 = "ig_streaming_mtd"
        if ck2 not in st.session_state:
            st.session_state[ck2] = _run_query(_STREAMING_MTD_SQL)
        df2 = st.session_state[ck2]
        if df2.empty:
            st.info("No streaming trend data available.")
        else:
            row = df2.iloc[0]
            curr_cost = float(row.get("CURRENT_MTD_STREAMING_COST") or 0)
            prev_cost = float(row.get("PREVIOUS_MTD_STREAMING_COST") or 0)
            curr_cred = float(row.get("CURRENT_MTD_STREAMING_CREDITS") or 0)
            prev_cred = float(row.get("PREVIOUS_MTD_STREAMING_CREDITS") or 0)
            if curr_cost + prev_cost > 0:
                fig2 = go.Figure(data=[go.Pie(
                    labels=["Current MTD", "Previous MTD"],
                    values=[curr_cost, prev_cost],
                    hole=0.45,
                    marker=dict(colors=[_CA, _C1]),
                    textinfo="percent+label",
                    textposition="inside",
                    hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>",
                )])
                fig2.update_layout(
                    height=300,
                    margin=dict(t=10, b=10, l=20, r=20),
                    showlegend=True,
                    legend=dict(orientation="h", y=-0.1),
                )
                st.plotly_chart(fig2, use_container_width=True)
                mc1, mc2 = st.columns(2)
                mc1.metric(
                    "Current MTD Credits", f"{curr_cred:,.0f}",
                    delta=f"{curr_cred - prev_cred:+,.0f} vs prev MTD",
                )
                mc2.metric(
                    "Current MTD Cost", f"${curr_cost:,.0f}",
                    delta=f"${curr_cost - prev_cost:+,.0f} vs prev MTD",
                )
            else:
                st.info("No streaming cost data available for this period.")

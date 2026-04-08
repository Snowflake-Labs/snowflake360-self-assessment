import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.config.design_tokens import CHART_SERIES, CHART_EXTENDED, BRAND_PRIMARY, BRAND_SECONDARY
from .bulk_load_analysis import comp_bulk_load_analysis
from .snowpipe_analysis import comp_snowpipe_analysis

PALETTE = CHART_SERIES + CHART_EXTENDED

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
        SUM(row_count) AS rows_loaded
    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
    WHERE status = 'Loaded'
      AND pipe_name IS NULL
      AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
pipe_summary AS (
    SELECT
        'Snowpipe' AS method,
        COUNT(*) AS job_count,
        SUM(file_size) / POW(1024, 3) AS gb_loaded,
        SUM(row_count) AS rows_loaded
    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
    WHERE status = 'Loaded'
      AND pipe_name IS NOT NULL
      AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
SELECT
    method AS ingestion_method,
    job_count AS events_or_channels,
    ROUND(COALESCE(gb_loaded, 0), 2) AS gb_loaded_30d,
    COALESCE(rows_loaded, 0) AS rows_loaded_30d
FROM copy_summary
UNION ALL
SELECT method, job_count, ROUND(COALESCE(gb_loaded, 0), 2), COALESCE(rows_loaded, 0)
FROM pipe_summary
ORDER BY gb_loaded_30d DESC NULLS LAST
"""


def _run_query(sql):
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        return session.sql(sql).to_pandas()
    except Exception as e:
        st.warning(f"Query error: {e}")
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
        table_schema_name || '.' || table_name AS target_table,
        COUNT(*) AS job_count,
        SUM(file_size) / POW(1024, 3) AS total_gb_ingested,
        AVG(file_size) / POW(1024, 2) AS avg_file_size_mb,
        MAX(file_size) / POW(1024, 2) AS max_file_size_mb,
        CASE
            WHEN MAX(file_size) > (AVG(file_size) * 100) THEN '⚠️ High Variance (Outliers)'
            WHEN AVG(file_size) < 10 THEN '⚠️ Small Files (<10MB)'
            ELSE '✅ Healthy'
        END AS health_check
    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
    WHERE status = 'Loaded'
      AND pipe_name IS NULL
      AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY 1
)
SELECT
    target_table,
    job_count AS "Load Events",
    ROUND(total_gb_ingested, 2) AS "Total GB",
    ROUND(avg_file_size_mb, 2) AS "Avg File (MB)",
    ROUND(max_file_size_mb, 2) AS "Max File (MB)",
    health_check
FROM copy_stats
ORDER BY total_gb_ingested DESC
LIMIT 20
"""

_PIPE_EFFICIENCY_SQL = """
WITH pipe_costs AS (
    SELECT pipe_name, SUM(credits_used) AS credits_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY 1
),
pipe_volume AS (
    SELECT pipe_name, COUNT(*) AS files_loaded,
        SUM(file_size) / POW(1024, 3) AS gb_loaded,
        AVG(file_size) / POW(1024, 2) AS avg_file_mb
    FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
    WHERE pipe_name IS NOT NULL
      AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY 1
)
SELECT
    v.pipe_name,
    v.files_loaded AS "Files (30d)",
    ROUND(v.gb_loaded, 2) AS "GB Ingested",
    ROUND(v.avg_file_mb, 2) AS "Avg File (MB)",
    ROUND(c.credits_30d, 2) AS "Credits Used (30d)",
    ROUND(c.credits_30d / NULLIF(v.gb_loaded, 0), 2) AS "Credits per GB"
FROM pipe_volume v
LEFT JOIN pipe_costs c ON v.pipe_name = c.pipe_name
ORDER BY c.credits_30d DESC
"""

_SNOWPIPE_DETAIL_SQL = """
SELECT
    pipe_name,
    SUM(credits_used) AS credits_burned,
    SUM(bytes_inserted) / POW(1024, 3) AS gb_loaded,
    CASE
        WHEN SUM(bytes_inserted) = 0 THEN '🔴 100% Overhead (Spinning)'
        WHEN (SUM(credits_used) / NULLIF(SUM(bytes_inserted),0)) > 0.1 THEN '🟡 High Overhead'
        ELSE '🟢 Efficient'
    END AS status
FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY credits_burned DESC
LIMIT 10
"""

_PIPE_COST_PROJECTION_SQL = """
WITH costs AS (
    SELECT 'Snowpipe (File)' AS type, SUM(credits_used) AS total_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    UNION ALL
    SELECT 'Snowpipe Streaming' AS type, SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES)
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE service_type = 'SNOWPIPE_STREAMING'
      AND usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
)
SELECT
    type AS ingest_method,
    ROUND(total_credits, 1) AS last_30_days,
    ROUND(total_credits * 3, 0) AS est_3_months,
    ROUND(total_credits * 6, 0) AS est_6_months,
    ROUND(total_credits * 12, 0) AS est_12_months
FROM costs
"""

_ALL_INGESTION_QUERIES = {
    "ingestion_streaming_data": _SNOWPIPE_STREAMING_SQL,
    "ingestion_summary_data": _INGESTION_SUMMARY_SQL,
    "ingestion_streaming_breakdown": _STREAMING_BREAKDOWN_SQL,
    "ig_bulk_load": _BULK_LOAD_SQL,
    "ig_pipe_efficiency": _PIPE_EFFICIENCY_SQL,
    "ig_snowpipe_detail": _SNOWPIPE_DETAIL_SQL,
    "ig_pipe_cost_projection": _PIPE_COST_PROJECTION_SQL,
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
    for k, sql in needed.items():
        key, df, err = _run_query_thread(session, k, sql)
        st.session_state[key] = df
        completed += 1
        if progress_bar is not None:
            progress_bar.progress(completed / total)
        if status_text is not None:
            status_text.text(f"Loading data... ({completed}/{total} queries)")


def _render_snowpipe_streaming():
    st.markdown("#### Snowpipe Streaming Credit Usage (Last 30 Days)")
    st.markdown("Daily credit consumption from Snowpipe Streaming ingestion.")

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
        marker_color=BRAND_PRIMARY,
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


def _render_ingestion_summary():
    st.markdown("#### Ingestion Summary Dashboard (Last 30 Days)")
    st.markdown("Comparison of all ingestion methods: COPY Command, Snowpipe, and Snowpipe Streaming.")

    ck = "ingestion_summary_data"
    if ck not in st.session_state:
        st.session_state[ck] = _run_query(_INGESTION_SUMMARY_SQL)
    df = st.session_state[ck]

    if df.empty:
        st.info("No ingestion activity detected in the last 30 days.")
        return

    df["gb_loaded_30d"] = df["gb_loaded_30d"].astype(float)
    df["rows_loaded_30d"] = df["rows_loaded_30d"].astype(float)

    methods = df["ingestion_method"].tolist()
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(df))]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### GB Loaded (30 Days) by Method")
        fig = go.Figure(data=[go.Bar(
            x=methods, y=df["gb_loaded_30d"],
            marker_color=colors,
            text=[f"{v:.2f} GB" for v in df["gb_loaded_30d"]],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>GB: %{y:.2f}<extra></extra>",
        )])
        fig.update_layout(height=350, margin=dict(t=30, b=60, l=40, r=20),
                          yaxis_title="GB Loaded", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### Rows Loaded (30 Days) by Method")
        fig = go.Figure(data=[go.Pie(
            labels=methods,
            values=df["rows_loaded_30d"].tolist(),
            hole=0.35,
            marker_colors=colors,
            hovertemplate="<b>%{label}</b><br>Rows: %{value:,.0f}<extra></extra>",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ingestion Method Summary Table", expanded=True):
        st.dataframe(df, use_container_width=True)


def comp_ingestion_overview(entry_actions=None):
    """
    Data Ingestion Overview Component

    Renders sub-tabs for:
    - Bulk Load (COPY INTO) Analysis
    - Snowpipe Analysis (Cost vs. Volume)
    - Snowpipe Streaming
    - Ingestion Summary Dashboard
    """
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

        with sub_tabs[3]:
            with st.spinner("Loading Ingestion Summary Dashboard..."):
                _render_ingestion_summary()

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
            f'🛑&nbsp;&nbsp;Error loading Data Ingestion Overview: {str(e)}'
            f'</div>', unsafe_allow_html=True)


def _render_streaming_service_breakdown():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Streaming Service Breakdown:</b> Snowpipe Streaming credits broken down by '
        'entity (warehouse/service) name from metering history.</div>',
        unsafe_allow_html=True)
    try:
        query = """
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
        ck = "ingestion_streaming_breakdown"
        if ck in st.session_state:
            df = st.session_state[ck]
        else:
            df = _run_query(query)
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
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

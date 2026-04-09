import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'


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


def comp_snowpipe_analysis(entry_actions=None):
    try:
        with st.expander("Snowpipe Efficiency Analysis", expanded=True):
            st.caption("File volume, data loaded, credit consumption, and cost per GB — last 30 days.")
            efficiency_df = _cached_sql("ig_pipe_efficiency", _EFFICIENCY_SQL)
            if len(efficiency_df) > 0:
                st.dataframe(efficiency_df, use_container_width=True)
                st.markdown("---")
                _render_efficiency_charts(efficiency_df)
            else:
                st.info("No Snowpipe efficiency data available for the last 30 days.")

        with st.expander("Top Credit Consumers & Overhead Analysis", expanded=True):
            st.caption("Top 10 Snowpipe credit consumers — spinning pipes burn credits without loading data.")
            snowpipe_df = _cached_sql("ig_snowpipe_detail", _SNOWPIPE_DETAIL_SQL)
            if len(snowpipe_df) > 0:
                st.dataframe(snowpipe_df, use_container_width=True)
                st.markdown("---")
                _render_snowpipe_charts(snowpipe_df)
            else:
                st.info("No Snowpipe data available for the last 30 days.")

        with st.expander("Ingestion Credit Consumption & Cost Projections", expanded=True):
            st.caption("Credit comparison between Snowpipe (file-based) and Snowpipe Streaming with 3/6/12-month projections.")
            cost_df = _cached_sql("ig_pipe_cost_projection", _COST_PROJECTION_SQL)
            if len(cost_df) > 0:
                st.dataframe(cost_df, use_container_width=True)
                st.markdown("---")
                _render_cost_projection_charts(cost_df)
            else:
                st.info("No ingestion cost data available for the last 30 days.")

    except Exception as e:
        st.error(f"Component Error: {e}")


_EFFICIENCY_SQL = """
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

_COST_PROJECTION_SQL = """
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


def _bar_h(y, x, color, text_fmt=None, height=400):
    texts = []
    for v in x:
        if text_fmt == 'int':
            texts.append(f"{int(v):,}")
        elif text_fmt == 'gb':
            texts.append(f"{v:.2f} GB")
        elif text_fmt == 'credits':
            texts.append(f"{v:.2f}")
        else:
            texts.append(f"{v:,.2f}" if isinstance(v, float) else f"{int(v):,}")
    fig = go.Figure(go.Bar(
        y=y, x=x, orientation='h', marker_color=color,
        text=texts, textposition='outside'))
    fig.update_layout(height=height, showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
    return fig


def _render_efficiency_charts(df):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Credits Used by Pipe (30d)**")
        cdf = df[df['CREDITS_USED'].notna()].head(10).sort_values('CREDITS_USED', ascending=True)
        if len(cdf) > 0:
            fig = _bar_h(cdf['PIPE_NAME'], cdf['CREDITS_USED'], _C1, 'credits')
            fig.update_layout(xaxis_title='Credits')
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("**Files Loaded by Pipe (30d)**")
        cdf = df[df['FILES_LOADED'].notna()].head(10).sort_values('FILES_LOADED', ascending=True)
        if len(cdf) > 0:
            fig = _bar_h(cdf['PIPE_NAME'], cdf['FILES_LOADED'], _C2, 'int')
            fig.update_layout(xaxis_title='Files')
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Credits Used by Pipe**")
    t1 = df[['PIPE_NAME', 'CREDITS_USED', 'GB_INGESTED', 'FILES_LOADED']].head(10)
    st.dataframe(t1, use_container_width=True)

    st.markdown("**Files Loaded by Pipe**")
    t2 = df[['PIPE_NAME', 'FILES_LOADED', 'ROWS_LOADED', 'AVG_FILE_MB']].head(10)
    st.dataframe(t2, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**GB Ingested by Pipe (30d)**")
        cdf = df[df['GB_INGESTED'].notna()].head(10).sort_values('GB_INGESTED', ascending=True)
        if len(cdf) > 0:
            fig = _bar_h(cdf['PIPE_NAME'], cdf['GB_INGESTED'], _C1, 'gb')
            fig.update_layout(xaxis_title='GB')
            st.plotly_chart(fig, use_container_width=True)
    with c4:
        st.markdown("**Cost Efficiency: Credits per GB**")
        cdf = df[df['CREDITS_PER_GB'].notna()].head(10).sort_values('CREDITS_PER_GB', ascending=True)
        if len(cdf) > 0:
            fig = _bar_h(cdf['PIPE_NAME'], cdf['CREDITS_PER_GB'], _C1, 'credits')
            fig.update_layout(xaxis_title='Credits per GB')
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**GB Ingested by Pipe**")
    t3 = df[['PIPE_NAME', 'GB_INGESTED', 'ROWS_LOADED', 'CREDITS_USED']].head(10)
    st.dataframe(t3, use_container_width=True)

    st.markdown("**Cost Efficiency by Pipe**")
    eff_cols = ['PIPE_NAME', 'CREDITS_PER_GB', 'EFFICIENCY_STATUS', 'RECOMMENDATION']
    valid = [c for c in eff_cols if c in df.columns]
    st.dataframe(df[valid].head(10), use_container_width=True)

    st.markdown("**Snowpipe Efficiency Status Distribution**")
    status_counts = df['EFFICIENCY_STATUS'].value_counts().reset_index()
    status_counts.columns = ['STATUS', 'COUNT']
    scolors = [_C1] * len(status_counts)
    fig = go.Figure(go.Bar(
        y=status_counts['STATUS'], x=status_counts['COUNT'], orientation='h',
        marker_color=scolors,
        text=[f"{int(v)}" for v in status_counts['COUNT']], textposition='outside'))
    fig.update_layout(height=250, xaxis_title='Pipes', margin=dict(t=20, b=40, l=200, r=50))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Snowpipe Efficiency Detail**")
    det_cols = ['PIPE_NAME', 'EFFICIENCY_STATUS', 'CREDITS_PER_GB', 'AVG_FILE_MB', 'RECOMMENDATION']
    valid = [c for c in det_cols if c in df.columns]
    st.dataframe(df[valid], use_container_width=True)

    st.markdown("**Efficiency Status & Recommendations**")
    rec_cols = ['PIPE_NAME', 'EFFICIENCY_STATUS', 'RECOMMENDATION']
    valid = [c for c in rec_cols if c in df.columns]
    st.dataframe(df[valid], use_container_width=True)


def _render_snowpipe_charts(df):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Credits Burned by Pipe (30d)**")
        cdf = df[df['CREDITS_BURNED'].notna()].head(10).sort_values('CREDITS_BURNED', ascending=True)
        if len(cdf) > 0:
            fig = _bar_h(cdf['PIPE_NAME'], cdf['CREDITS_BURNED'], _C1, 'credits')
            fig.update_layout(xaxis_title='Credits')
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("**GB Loaded by Pipe (30d)**")
        cdf = df[df['GB_LOADED'].notna()].head(10).sort_values('GB_LOADED', ascending=True)
        if len(cdf) > 0:
            fig = _bar_h(cdf['PIPE_NAME'], cdf['GB_LOADED'], _C2, 'gb')
            fig.update_layout(xaxis_title='GB')
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Credits Burned by Pipe**")
    st.dataframe(df[['PIPE_NAME', 'CREDITS_BURNED', 'GB_LOADED', 'STATUS']].head(10), use_container_width=True)

    st.markdown("**GB Loaded by Pipe**")
    st.dataframe(df[['PIPE_NAME', 'GB_LOADED', 'CREDITS_BURNED', 'FILES_INSERTED']].head(10), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**Credits vs GB Loaded Comparison**")
        cdf = df.head(10).sort_values('CREDITS_BURNED', ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=cdf['PIPE_NAME'], x=cdf['CREDITS_BURNED'], name='Credits Burned',
                             orientation='h', marker_color=_C1))
        fig.add_trace(go.Bar(y=cdf['PIPE_NAME'], x=cdf['GB_LOADED'], name='GB Loaded',
                             orientation='h', marker_color=_C2))
        fig.update_layout(height=400, barmode='group', xaxis_title='Value',
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                          margin=dict(t=40, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Credits vs GB Loaded Comparison**")
    comp_cols = ['PIPE_NAME', 'CREDITS_BURNED', 'GB_LOADED', 'STATUS', 'RECOMMENDATION']
    valid = [c for c in comp_cols if c in df.columns]
    st.dataframe(df[valid].head(10), use_container_width=True)

    st.markdown("**Overhead Status & Recommendations**")
    oh_cols = ['PIPE_NAME', 'STATUS', 'RECOMMENDATION']
    valid = [c for c in oh_cols if c in df.columns]
    st.dataframe(df[valid].head(10), use_container_width=True)


def _render_cost_projection_charts(df):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Credit Consumption — Last 30 Days**")
        cdf = df[df['CREDITS_LAST_30_DAYS'].notna()]
        if len(cdf) > 0:
            bar_colors = [_C2, _C1, _C3, _CA][:len(cdf)]
            fig = go.Figure(go.Bar(
                y=cdf['INGEST_METHOD'], x=cdf['CREDITS_LAST_30_DAYS'], orientation='h',
                marker_color=bar_colors,
                text=[f"{v:.1f}" for v in cdf['CREDITS_LAST_30_DAYS']], textposition='outside'))
            fig.update_layout(height=300, xaxis_title='Credits', showlegend=False,
                              margin=dict(t=20, b=50, l=180, r=50))
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("**Projected Credits by Horizon**")
        methods = df['INGEST_METHOD'].tolist()
        est3 = df['EST_CREDITS_3_MONTHS'].tolist() if 'EST_CREDITS_3_MONTHS' in df.columns else []
        est6 = df['EST_CREDITS_6_MONTHS'].tolist() if 'EST_CREDITS_6_MONTHS' in df.columns else []
        est12 = df['EST_CREDITS_12_MONTHS'].tolist() if 'EST_CREDITS_12_MONTHS' in df.columns else []
        if est3:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=methods, y=est3, name='3 Months', marker_color=_C1,
                                 text=[f"{int(v):,}" for v in est3], textposition='outside'))
            fig.add_trace(go.Bar(x=methods, y=est6, name='6 Months', marker_color=_C2,
                                 text=[f"{int(v):,}" for v in est6], textposition='outside'))
            fig.add_trace(go.Bar(x=methods, y=est12, name='12 Months', marker_color=_CA,
                                 text=[f"{int(v):,}" for v in est12], textposition='outside'))
            fig.update_layout(height=400, barmode='group', yaxis_title='Credits',
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                              margin=dict(t=40, b=60, l=60, r=30))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Cost Profile by Ingestion Method**")
    cp_cols = ['INGEST_METHOD', 'CREDITS_LAST_30_DAYS', 'GB_INGESTED_30_DAYS', 'FILES_PROCESSED_30_DAYS', 'USAGE_TIER']
    valid = [c for c in cp_cols if c in df.columns]
    st.dataframe(df[valid], use_container_width=True)

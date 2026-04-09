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


_BULK_LOAD_QUERY = """
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


def comp_bulk_load_analysis(entry_actions=None):
    try:
        st.markdown("COPY command ingestion analysis — last 30 days, top 20 tables by volume.")

        df = _cached_sql("ig_bulk_load", _BULK_LOAD_QUERY)

        if df.empty:
            st.info("No COPY INTO data found for the last 30 days.")
            return

        df.columns = ['TARGET_TABLE', 'JOB_COUNT', 'TOTAL_GB', 'TOTAL_ROWS_LOADED',
                      'AVG_FILE_MB', 'MIN_FILE_MB', 'MAX_FILE_MB', 'STDDEV_FILE_MB',
                      'HEALTH_CHECK', 'RECOMMENDATION']

        tables_loaded = len(df)
        total_events = int(df['JOB_COUNT'].sum())
        total_gb = float(df['TOTAL_GB'].sum())
        healthy = len(df[df['HEALTH_CHECK'] == '✅ Healthy'])

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Tables Loaded", tables_loaded)
        with c2:
            st.metric("Total Load Events", f"{total_events:,}")
        with c3:
            st.metric("Total GB Ingested", f"{total_gb:,.2f}")
        with c4:
            st.metric("Healthy Tables", f"{healthy} / {tables_loaded}")

        with st.expander("COPY INTO Load Statistics — Top 20 Tables", expanded=True):
            display_cols = ['TARGET_TABLE', 'JOB_COUNT', 'TOTAL_GB', 'TOTAL_ROWS_LOADED',
                            'AVG_FILE_MB', 'MIN_FILE_MB', 'MAX_FILE_MB']
            st.dataframe(df[display_cols], use_container_width=True)

        st.markdown("#### Ingestion Analytics Charts")

        _render_section(df, 'TOTAL_GB', 'Total GB', 'Top Tables by Volume Ingested (GB)',
                        'Total GB', _C1,
                        ['TARGET_TABLE', 'TOTAL_GB', 'JOB_COUNT', 'TOTAL_ROWS_LOADED'],
                        'Top Tables by Volume Ingested')

        _render_section(df, 'JOB_COUNT', 'Load Events', 'Load Events by Table',
                        'Load Events', _C2,
                        ['TARGET_TABLE', 'JOB_COUNT', 'TOTAL_GB', 'HEALTH_CHECK'],
                        'Load Events by Table')

        _render_section(df, 'AVG_FILE_MB', 'Avg File (MB)', 'Average File Size by Table (MB)',
                        'Avg File (MB)', _C3,
                        ['TARGET_TABLE', 'AVG_FILE_MB', 'MIN_FILE_MB', 'MAX_FILE_MB', 'STDDEV_FILE_MB'],
                        'Average File Size by Table')

        _render_section(df, 'TOTAL_ROWS_LOADED', 'Rows Loaded', 'Rows Loaded by Table',
                        'Rows Loaded', _C2,
                        ['TARGET_TABLE', 'TOTAL_ROWS_LOADED', 'JOB_COUNT', 'TOTAL_GB'],
                        'Rows Loaded by Table')

        st.markdown("#### Bulk Load Health Status Distribution")
        health_counts = df['HEALTH_CHECK'].value_counts().reset_index()
        health_counts.columns = ['STATUS', 'COUNT']
        hcolors = []
        for s in health_counts['STATUS']:
            if 'Healthy' in s:
                hcolors.append(_C1)
            else:
                hcolors.append(_CA)
        fig = go.Figure(go.Bar(
            y=health_counts['STATUS'], x=health_counts['COUNT'],
            orientation='h',
            marker_color=hcolors,
            text=health_counts['COUNT'], textposition='outside'
        ))
        fig.update_layout(height=250, margin=dict(t=20, b=40, l=180, r=50), xaxis_title='Tables')
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Bulk Load Health Detail")
        detail_cols = ['TARGET_TABLE', 'HEALTH_CHECK', 'AVG_FILE_MB', 'MAX_FILE_MB', 'RECOMMENDATION']
        st.dataframe(df[detail_cols], use_container_width=True)

        st.markdown("#### Recommendations")
        rec_cols = ['TARGET_TABLE', 'HEALTH_CHECK', 'RECOMMENDATION']
        st.dataframe(df[rec_cols], use_container_width=True)

    except Exception as e:
        st.error(f"Component Error: {e}")


def _render_section(df, value_col, value_label, chart_title, x_label, color, table_cols, table_title):
    plot_df = df.head(10).sort_values(value_col, ascending=True)
    fig = go.Figure(go.Bar(
        y=plot_df['TARGET_TABLE'], x=plot_df[value_col], orientation='h',
        marker_color=color,
        text=[f"{v:,.2f}" if isinstance(v, float) else f"{int(v):,}" for v in plot_df[value_col]],
        textposition='outside'
    ))
    fig.update_layout(
        title=chart_title, xaxis_title=x_label,
        height=400, margin=dict(t=40, b=40, l=120, r=60),
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(f"**{table_title}**")
    valid_cols = [c for c in table_cols if c in df.columns]
    st.dataframe(df[valid_cols], use_container_width=True)

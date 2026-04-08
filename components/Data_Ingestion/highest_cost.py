import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.config.design_tokens import (
    BRAND_PRIMARY, BRAND_SECONDARY,
    CHART_SERIES, CHART_EXTENDED,
)

_COPY_COST_SQL = """
SELECT
    TABLE_CATALOG_NAME AS DATABASE_NAME,
    TABLE_SCHEMA_NAME AS SCHEMA_NAME,
    TABLE_NAME,
    COUNT(*) AS LOAD_COUNT,
    SUM(ROW_COUNT) AS TOTAL_ROWS,
    ROUND(SUM(FILE_SIZE) / POW(1024, 3), 2) AS TOTAL_GB_LOADED,
    ROUND(AVG(ROW_COUNT), 0) AS AVG_ROWS_PER_LOAD,
    MIN(LAST_LOAD_TIME) AS FIRST_LOAD,
    MAX(LAST_LOAD_TIME) AS LAST_LOAD
FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
WHERE LAST_LOAD_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND STATUS = 'Loaded'
GROUP BY 1, 2, 3
ORDER BY TOTAL_GB_LOADED DESC
LIMIT 20
"""

_PIPE_COST_SQL = """
SELECT
    PIPE_NAME,
    ROUND(SUM(CREDITS_USED), 4) AS TOTAL_CREDITS,
    SUM(BYTES_INSERTED) / POW(1024, 3) AS TOTAL_GB_INSERTED,
    SUM(FILES_INSERTED) AS TOTAL_FILES
FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY PIPE_NAME
ORDER BY TOTAL_CREDITS DESC
LIMIT 15
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


_ALL_HIGHEST_COST_QUERIES = {
    "highest_cost_copy_data": _COPY_COST_SQL,
    "highest_cost_pipe_data": _PIPE_COST_SQL,
}


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_highest_cost_queries():
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_HIGHEST_COST_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    for k, sql in needed.items():
        key, df, err = _run_query_thread(session, k, sql)
        st.session_state[key] = df


def comp_highest_cost(entry_actions=None):
    try:
        _prefetch_all_highest_cost_queries()
        st.markdown("### Highest Cost Ingestion")
        st.markdown("Top tables by data volume loaded and Snowpipe credit consumption over the last 30 days.")

        tab1, tab2 = st.tabs(["Bulk Load (COPY)", "Snowpipe Credits"])

        with tab1:
            _render_copy_cost()

        with tab2:
            _render_pipe_cost()

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
            f'Component Error: {str(e)}'
            f'</div>', unsafe_allow_html=True)


def _render_copy_cost():
    cache_key = "highest_cost_copy_data"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_COPY_COST_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.info("No COPY history found in the last 30 days.")
        return

    palette = CHART_SERIES + CHART_EXTENDED
    top = df.head(10)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("#### Top Tables by Data Volume Loaded")
        labels = (top["DATABASE_NAME"] + "." + top["TABLE_NAME"]).tolist()
        vals = top["TOTAL_GB_LOADED"].tolist()
        fig = go.Figure(data=[go.Bar(
            y=labels[::-1], x=vals[::-1],
            orientation="h",
            marker_color=BRAND_SECONDARY,
            text=[f"{v:.2f} GB" for v in vals[::-1]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x:.2f} GB<extra></extra>",
        )])
        fig.update_layout(
            height=max(300, len(top) * 35),
            margin=dict(t=10, b=40, l=200, r=60),
            xaxis_title="GB Loaded (30 days)",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Load Count Distribution")
        fig_pie = go.Figure(data=[go.Pie(
            labels=labels[:8], values=top["LOAD_COUNT"].tolist()[:8],
            marker=dict(colors=palette[:8]),
            textinfo="label+value",
            hole=0.35,
        )])
        fig_pie.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10), showlegend=True)
        st.plotly_chart(fig_pie, use_container_width=True)

    with st.expander("Full COPY Load Details", expanded=True):
        st.dataframe(df, use_container_width=True)


def _render_pipe_cost():
    cache_key = "highest_cost_pipe_data"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_PIPE_COST_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.info("No Snowpipe usage found in the last 30 days.")
        return

    palette = CHART_SERIES + CHART_EXTENDED
    top = df.head(10)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("#### Top Pipes by Credit Consumption")
        pipes = top["PIPE_NAME"].tolist()
        credits = top["TOTAL_CREDITS"].tolist()
        fig = go.Figure(data=[go.Bar(
            y=pipes[::-1], x=credits[::-1],
            orientation="h",
            marker_color=BRAND_PRIMARY,
            text=[f"{v:.4f}" for v in credits[::-1]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Credits: %{x:.4f}<extra></extra>",
        )])
        fig.update_layout(
            height=max(300, len(top) * 35),
            margin=dict(t=10, b=40, l=200, r=60),
            xaxis_title="Credits Used (30 days)",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Files Inserted Distribution")
        fig_pie = go.Figure(data=[go.Pie(
            labels=pipes[:8], values=top["TOTAL_FILES"].tolist()[:8],
            marker=dict(colors=palette[:8]),
            textinfo="label+value",
            hole=0.35,
        )])
        fig_pie.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10), showlegend=True)
        st.plotly_chart(fig_pie, use_container_width=True)

    with st.expander("Full Snowpipe Usage Details", expanded=True):
        st.dataframe(df, use_container_width=True)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
from .bulk_load_analysis import comp_bulk_load_analysis
from .snowpipe_analysis import comp_snowpipe_analysis
from .ingestion_summary import comp_ingestion_summary
from ._all_di_queries import _ALL_DI_QUERIES

_C1 = "#29B5E8"
_C2 = "#11567F"
_C3 = "#75C2D8"
_CA = "#E8A229"

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

_ALL_INGESTION_QUERIES = {**_ALL_DI_QUERIES, "ingestion_streaming_breakdown": _STREAMING_BREAKDOWN_SQL}


def _run_query(sql):
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        return session.sql(sql).to_pandas()
    except Exception:
        return pd.DataFrame()


def _prefetch_all_ingestion_queries(progress_bar=None, status_text=None):
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_INGESTION_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    total = len(needed)
    completed = 0
    def _run(s, k, q):
        try:
            return k, s.sql(q).to_pandas(), None
        except Exception as e:
            return k, pd.DataFrame(), e
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_run, session, k, sql): k for k, sql in needed.items()}
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

    ck = "di_streaming_credits"
    if ck not in st.session_state:
        st.session_state[ck] = _run_query(_ALL_DI_QUERIES["di_streaming_credits"])
    df = st.session_state[ck]

    if df.empty:
        st.info("No Snowpipe Streaming activity detected in the last 30 days.")
        return

    df["CREDITS_USED"] = pd.to_numeric(df["CREDITS_USED"], errors="coerce").fillna(0)

    total_credits = df["CREDITS_USED"].sum()
    peak_day = df.loc[df["CREDITS_USED"].idxmax(), "USAGE_DATE"] if len(df) > 0 else "N/A"
    active_days = len(df)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Credits (30d)", f"{total_credits:.4f}")
    m2.metric("Active Days", active_days)
    m3.metric("Peak Usage Date", str(peak_day))

    fig = go.Figure(data=[go.Bar(
        x=df["USAGE_DATE"].astype(str),
        y=df["CREDITS_USED"],
        marker_color=_C1,
        text=[f"{v:.4f}" for v in df["CREDITS_USED"]],
        textposition="outside",
    )])
    fig.update_layout(height=350, xaxis_title="Date", yaxis_title="Credits Used",
                      showlegend=False, margin=dict(t=30, b=60, l=60, r=20))
    st.plotly_chart(fig, use_container_width=True, key="streaming_daily")

    with st.expander("Snowpipe Streaming Daily Credit Details", expanded=True):
        st.dataframe(df, use_container_width=True)

    with st.expander("Snowpipe Streaming Service Breakdown", expanded=True):
        _render_streaming_service_breakdown()


def _render_streaming_service_breakdown():
    ck = "ingestion_streaming_breakdown"
    if ck in st.session_state:
        df = st.session_state[ck]
    else:
        df = _run_query(_STREAMING_BREAKDOWN_SQL)
        st.session_state[ck] = df
    if df.empty:
        st.info("No Snowpipe Streaming service-level detail available.")
        return
    df["TOTAL_CREDITS"] = pd.to_numeric(df["TOTAL_CREDITS"], errors="coerce").fillna(0)
    st.metric("Streaming Services/Entities", len(df))
    fig = go.Figure(go.Bar(
        x=df["SERVICE_ENTITY"].astype(str), y=df["TOTAL_CREDITS"],
        marker_color=_C1,
        text=[f"{v:,.4f}" for v in df["TOTAL_CREDITS"]], textposition="outside"
    ))
    fig.update_layout(height=360, yaxis_title="Credits",
                      margin=dict(t=30, b=80, l=60, r=20), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, key="streaming_breakdown")
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

        sub_tabs = st.tabs([
            "Bulk Load (COPY INTO) Analysis",
            "Snowpipe Analysis (Cost vs. Volume)",
            "Snowpipe Streaming",
            "Ingestion Summary Dashboard"
        ])

        with sub_tabs[0]:
            comp_bulk_load_analysis()

        with sub_tabs[1]:
            comp_snowpipe_analysis()

        with sub_tabs[2]:
            _render_snowpipe_streaming()

        with sub_tabs[3]:
            comp_ingestion_summary()

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
            f'🛑&nbsp;&nbsp;Error loading Data Ingestion Overview: {str(e)}'
            f'</div>', unsafe_allow_html=True)

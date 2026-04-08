import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = "#29B5E8"
_C2 = "#11567F"
_C3 = "#75C2D8"
_CA = "#E8A229"


def _get(key, sql):
    if key in st.session_state:
        return st.session_state[key]
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        df = session.sql(sql).to_pandas()
    except Exception:
        df = pd.DataFrame()
    st.session_state[key] = df
    return df


def _donut(labels, values, colors, h=300, key=""):
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.45, marker_colors=colors,
        textinfo="percent", textposition="inside",
    ))
    fig.update_layout(height=h, margin=dict(t=20, b=20, l=20, r=20),
                      legend=dict(orientation="v", x=1.02, y=0.5))
    st.plotly_chart(fig, use_container_width=True, key=key)


def comp_ingestion_summary():
    from components.Data_Ingestion._all_di_queries import _ALL_DI_QUERIES
    df = _get("di_ingestion_summary", _ALL_DI_QUERIES["di_ingestion_summary"])

    with st.expander("Ingestion Method Summary Dashboard", expanded=True):
        st.caption("30-day comparison across COPY, Snowpipe, and Snowpipe Streaming using channel history for activity and metering history for streaming credits.")

        if df.empty:
            st.info("No ingestion summary data found for the last 30 days.")
            return

        st.markdown("### Top-Line Ingestion Summary")
        summary_cols = ["INGESTION_METHOD", "EVENTS_OR_CHANNELS", "GB_LOADED_30D", "ROWS_LOADED_30D", "AVG_FILE_MB"]
        avail = [c for c in summary_cols if c in df.columns]
        st.dataframe(df[avail], use_container_width=True)

        methods = df["INGESTION_METHOD"].tolist()
        palette = [_C1, _C2, _C3][:len(methods)]

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Events / Channels by Method**")
            if "EVENTS_OR_CHANNELS" in df.columns:
                _donut(methods, df["EVENTS_OR_CHANNELS"].tolist(), palette, h=300, key="is_evt_donut")
        with c2:
            st.markdown("**Data Volume (GB) by Method**")
            if "GB_LOADED_30D" in df.columns:
                _donut(methods, df["GB_LOADED_30D"].tolist(), palette, h=300, key="is_gb_donut")
        with c3:
            st.markdown("**Credits Consumed by Method**")
            if "CREDITS_LAST_30_DAYS" in df.columns:
                _donut(methods, df["CREDITS_LAST_30_DAYS"].tolist(), palette, h=300, key="is_cred_donut")

        st.markdown("**Side-by-Side Ingestion Comparison**")
        series = []
        if "EVENTS_OR_CHANNELS" in df.columns:
            series.append(("Events / Channels", df["EVENTS_OR_CHANNELS"].tolist(), _C3))
        if "ROWS_LOADED_30D" in df.columns:
            series.append(("Rows", df["ROWS_LOADED_30D"].tolist(), _C2))
        if "CREDITS_LAST_30_DAYS" in df.columns:
            series.append(("Credits", df["CREDITS_LAST_30_DAYS"].tolist(), _CA))
        if series:
            fig = go.Figure()
            for name, values, color in series:
                fig.add_trace(go.Bar(name=name, x=methods, y=values, marker_color=color))
            fig.update_layout(barmode="group", height=400,
                              margin=dict(t=40, b=60, l=50, r=30),
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True, key="is_compare_bar")

        all_cols = [c for c in df.columns]
        st.dataframe(df[all_cols], use_container_width=True)

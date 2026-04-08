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


def _bar(x, y, colors, h=300, xlabel="", ylabel="", key=""):
    fig = go.Figure(go.Bar(
        y=x, x=y, orientation="h",
        marker_color=colors if isinstance(colors, list) else [colors] * len(x),
        text=y, textposition="outside",
    ))
    fig.update_layout(height=h, xaxis_title=xlabel, yaxis_title=ylabel,
                      margin=dict(t=20, b=40, l=180, r=40), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, key=key)


def comp_bulk_load_analysis():
    from components.Data_Ingestion._all_di_queries import _ALL_DI_QUERIES
    sql = _ALL_DI_QUERIES["di_copy_analysis"]
    df = _get("di_copy_analysis", sql)

    st.caption("COPY command ingestion analysis — last 30 days, top 20 tables by volume.")

    if df.empty:
        st.info("No COPY INTO load data found for the last 30 days.")
        return

    total_tables = len(df)
    total_events = int(df["JOB_COUNT"].sum())
    total_gb = round(float(df["TOTAL_GB"].sum()), 2)
    healthy = int((df["HEALTH_CHECK"] == "Healthy").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tables Loaded", f"{total_tables}")
    c2.metric("Total Load Events", f"{total_events:,}")
    c3.metric("Total GB Ingested", f"{total_gb:,.2f}")
    c4.metric("Healthy Tables", f"{healthy} / {total_tables}")

    with st.expander("COPY INTO Load Statistics — Top 20 Tables", expanded=True):
        show_cols = ["TARGET_TABLE", "JOB_COUNT", "TOTAL_GB", "TOTAL_ROWS_LOADED",
                     "AVG_FILE_MB", "MIN_FILE_MB", "MAX_FILE_MB", "STDDEV_FILE_MB"]
        display = df[[c for c in show_cols if c in df.columns]]
        st.dataframe(display, use_container_width=True)

    st.markdown("### Ingestion Analytics Charts")

    st.markdown("**Top Tables by Volume Ingested (GB)**")
    top_vol = df.nlargest(10, "TOTAL_GB")
    _bar(top_vol["TARGET_TABLE"].tolist(), top_vol["TOTAL_GB"].tolist(),
         _C1, h=max(250, len(top_vol) * 30), xlabel="Total GB", key="bl_vol_bar")
    st.markdown("**Top Tables by Volume Ingested**")
    st.dataframe(top_vol[["TARGET_TABLE", "TOTAL_GB", "JOB_COUNT", "TOTAL_ROWS_LOADED"]],
                 use_container_width=True)

    st.markdown("**Load Events by Table**")
    top_events = df.nlargest(10, "JOB_COUNT")
    _bar(top_events["TARGET_TABLE"].tolist(), top_events["JOB_COUNT"].tolist(),
         _C2, h=max(250, len(top_events) * 30), xlabel="Load Events", key="bl_evt_bar")
    st.markdown("**Load Events by Table**")
    st.dataframe(top_events[["TARGET_TABLE", "JOB_COUNT", "TOTAL_GB", "HEALTH_CHECK"]],
                 use_container_width=True)

    st.markdown("**Average File Size by Table (MB)**")
    top_avg = df.nlargest(10, "AVG_FILE_MB")
    _bar(top_avg["TARGET_TABLE"].tolist(), top_avg["AVG_FILE_MB"].tolist(),
         _C1, h=max(250, len(top_avg) * 30), xlabel="Avg File (MB)", key="bl_avg_bar")
    st.markdown("**Average File Size by Table**")
    st.dataframe(top_avg[["TARGET_TABLE", "AVG_FILE_MB", "MIN_FILE_MB", "MAX_FILE_MB", "STDDEV_FILE_MB"]],
                 use_container_width=True)

    if "TOTAL_ROWS_LOADED" in df.columns:
        st.markdown("**Rows Loaded by Table**")
        top_rows = df.nlargest(10, "TOTAL_ROWS_LOADED")
        _bar(top_rows["TARGET_TABLE"].tolist(), top_rows["TOTAL_ROWS_LOADED"].tolist(),
             _C2, h=max(250, len(top_rows) * 30), xlabel="Rows Loaded", key="bl_row_bar")
        st.markdown("**Rows Loaded by Table**")
        st.dataframe(top_rows[["TARGET_TABLE", "TOTAL_ROWS_LOADED", "JOB_COUNT", "TOTAL_GB"]],
                     use_container_width=True)

    st.markdown("**Bulk Load Health Status Distribution**")
    health_agg = df.groupby("HEALTH_CHECK").size().reset_index(name="COUNT")
    hc_map = {"Healthy": _C1, "Small Files (<10MB)": _CA, "Large Files (>250MB)": _C2, "High Variance": _C3}
    hc_colors = [hc_map.get(h, _C1) for h in health_agg["HEALTH_CHECK"]]
    _bar(health_agg["HEALTH_CHECK"].tolist(), health_agg["COUNT"].tolist(),
         hc_colors, h=max(150, len(health_agg) * 50), xlabel="Tables", key="bl_health_bar")

    st.markdown("**Bulk Load Health Detail**")
    st.dataframe(df[["TARGET_TABLE", "HEALTH_CHECK", "AVG_FILE_MB", "MAX_FILE_MB", "RECOMMENDATION"]],
                 use_container_width=True)

    st.markdown("### Recommendations")
    st.dataframe(df[["TARGET_TABLE", "HEALTH_CHECK", "RECOMMENDATION"]],
                 use_container_width=True)

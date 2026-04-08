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


def _grouped_bar(x_labels, series_list, h=350, xlabel="", ylabel="", key=""):
    fig = go.Figure()
    for name, values, color in series_list:
        fig.add_trace(go.Bar(name=name, x=x_labels, y=values, marker_color=color,
                             text=[f"{v:,.2f}" if isinstance(v, float) else f"{v:,}" for v in values],
                             textposition="outside"))
    fig.update_layout(barmode="group", height=h, xaxis_title=xlabel, yaxis_title=ylabel,
                      margin=dict(t=40, b=60, l=50, r=30),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True, key=key)


def comp_snowpipe_analysis():
    from components.Data_Ingestion._all_di_queries import _ALL_DI_QUERIES

    with st.expander("Snowpipe Efficiency Analysis", expanded=True):
        _render_efficiency(
            _get("di_snowpipe_efficiency", _ALL_DI_QUERIES["di_snowpipe_efficiency"]))

    with st.expander("Top Credit Consumers & Overhead Analysis", expanded=True):
        _render_top_consumers(
            _get("di_top_pipe_consumers", _ALL_DI_QUERIES["di_top_pipe_consumers"]))

    with st.expander("Ingestion Credit Consumption & Cost Projections", expanded=True):
        _render_projections(
            _get("di_credit_projection", _ALL_DI_QUERIES["di_credit_projection"]))


def _render_efficiency(df):
    st.caption("File volume, data loaded, credit consumption, and cost per GB — last 30 days.")
    if df.empty:
        st.info("No Snowpipe activity found for the last 30 days.")
        return

    st.dataframe(df, use_container_width=True)

    top = df.nlargest(10, "CREDITS_USED") if "CREDITS_USED" in df.columns else df.head(10)
    bh = max(250, len(top) * 30)

    st.markdown("**Credits Used by Pipe (30d)**")
    _bar(top["PIPE_NAME"].tolist(), top["CREDITS_USED"].tolist(), _C1, h=bh, xlabel="Credits", key="sp_cred_bar")
    st.markdown("**Credits Used by Pipe**")
    st.dataframe(top[["PIPE_NAME", "CREDITS_USED", "GB_INGESTED", "FILES_LOADED"]], use_container_width=True)

    if "FILES_LOADED" in df.columns:
        top_f = df.nlargest(10, "FILES_LOADED")
        st.markdown("**Files Loaded by Pipe (30d)**")
        _bar(top_f["PIPE_NAME"].tolist(), top_f["FILES_LOADED"].tolist(), _C2, h=bh, xlabel="Files", key="sp_files_bar")
        st.markdown("**Files Loaded by Pipe**")
        st.dataframe(top_f[["PIPE_NAME", "FILES_LOADED", "ROWS_LOADED", "AVG_FILE_MB"]], use_container_width=True)

    if "GB_INGESTED" in df.columns:
        top_g = df.nlargest(10, "GB_INGESTED")
        st.markdown("**GB Ingested by Pipe (30d)**")
        _bar(top_g["PIPE_NAME"].tolist(), top_g["GB_INGESTED"].tolist(), _C1, h=bh, xlabel="GB", key="sp_gb_bar")
        st.markdown("**GB Ingested by Pipe**")
        st.dataframe(top_g[["PIPE_NAME", "GB_INGESTED", "ROWS_LOADED", "CREDITS_USED"]], use_container_width=True)

    if "CREDITS_PER_GB" in df.columns:
        valid = df[df["CREDITS_PER_GB"].notna() & (df["CREDITS_PER_GB"] > 0)].nlargest(10, "CREDITS_PER_GB")
        if not valid.empty:
            st.markdown("**Cost Efficiency: Credits per GB**")
            _bar(valid["PIPE_NAME"].tolist(), valid["CREDITS_PER_GB"].tolist(), _C1, h=bh, xlabel="Credits per GB", key="sp_cpg_bar")
            st.markdown("**Cost Efficiency by Pipe**")
            st.dataframe(valid[["PIPE_NAME", "CREDITS_PER_GB", "EFFICIENCY_STATUS", "RECOMMENDATION"]], use_container_width=True)

    if "EFFICIENCY_STATUS" in df.columns:
        st.markdown("**Snowpipe Efficiency Status Distribution**")
        eff_agg = df.groupby("EFFICIENCY_STATUS").size().reset_index(name="COUNT")
        eff_map = {"Efficient": _C1, "Small File Overhead": _CA, "High Cost per GB": _C2, "Idle Burning Credits": _C3}
        eff_colors = [eff_map.get(s, _C1) for s in eff_agg["EFFICIENCY_STATUS"]]
        _bar(eff_agg["EFFICIENCY_STATUS"].tolist(), eff_agg["COUNT"].tolist(),
             eff_colors, h=max(150, len(eff_agg) * 50), xlabel="Pipes", key="sp_eff_dist")

        st.markdown("**Snowpipe Efficiency Detail**")
        st.dataframe(df[["PIPE_NAME", "EFFICIENCY_STATUS", "CREDITS_PER_GB", "AVG_FILE_MB", "RECOMMENDATION"]],
                     use_container_width=True)

    st.markdown("**Efficiency Status & Recommendations**")
    st.dataframe(df[["PIPE_NAME", "EFFICIENCY_STATUS", "RECOMMENDATION"]], use_container_width=True)


def _render_top_consumers(df):
    st.caption("Top 10 Snowpipe credit consumers — spinning pipes burn credits without loading data.")
    if df.empty:
        st.info("No Snowpipe credit consumption data found.")
        return

    st.dataframe(df, use_container_width=True)

    top = df.head(10)
    bh = max(250, len(top) * 30)

    st.markdown("**Credits Burned by Pipe (30d)**")
    _bar(top["PIPE_NAME"].tolist(), top["CREDITS_BURNED"].tolist(), _C1, h=bh, xlabel="Credits", key="tc_cred_bar")
    st.markdown("**Credits Burned by Pipe**")
    st.dataframe(top[["PIPE_NAME", "CREDITS_BURNED", "GB_LOADED", "STATUS"]], use_container_width=True)

    if "GB_LOADED" in df.columns:
        top_gb = df.nlargest(10, "GB_LOADED")
        st.markdown("**GB Loaded by Pipe (30d)**")
        _bar(top_gb["PIPE_NAME"].tolist(), top_gb["GB_LOADED"].tolist(), _C2, h=bh, xlabel="GB", key="tc_gb_bar")
        st.markdown("**GB Loaded by Pipe**")
        st.dataframe(top_gb[["PIPE_NAME", "GB_LOADED", "CREDITS_BURNED", "FILES_INSERTED"]], use_container_width=True)

    st.markdown("**Credits vs GB Loaded Comparison**")
    _grouped_bar(
        top["PIPE_NAME"].tolist(),
        [("Credits Burned", top["CREDITS_BURNED"].tolist(), _C3),
         ("GB Loaded", top["GB_LOADED"].tolist(), _C2)],
        h=max(300, len(top) * 35), xlabel="", ylabel="Value", key="tc_compare")
    st.markdown("**Credits vs GB Loaded Comparison**")
    st.dataframe(top[["PIPE_NAME", "CREDITS_BURNED", "GB_LOADED", "STATUS", "RECOMMENDATION"]],
                 use_container_width=True)

    st.markdown("**Overhead Status & Recommendations**")
    st.dataframe(top[["PIPE_NAME", "STATUS", "RECOMMENDATION"]], use_container_width=True)


def _render_projections(df):
    st.caption("Credit comparison between Snowpipe (file-based) and Snowpipe Streaming with 3/6/12-month projections.")
    if df.empty:
        st.info("No ingestion credit data found for projections.")
        return

    st.dataframe(df, use_container_width=True)

    lc, rc = st.columns(2)
    with lc:
        st.markdown("**Credit Consumption — Last 30 Days**")
        _bar(df["INGEST_METHOD"].tolist(), df["CREDITS_LAST_30_DAYS"].tolist(),
             [_C2, _C1][:len(df)], h=200, xlabel="Credits", key="proj_30d")

    with rc:
        st.markdown("**Projected Credits by Horizon**")
        proj_cols = ["EST_CREDITS_3_MONTHS", "EST_CREDITS_6_MONTHS", "EST_CREDITS_12_MONTHS"]
        avail = [c for c in proj_cols if c in df.columns]
        if avail:
            labels = df["INGEST_METHOD"].tolist()
            series = []
            color_map = {0: _C3, 1: _C2, 2: _CA}
            name_map = {0: "3 Months", 1: "6 Months", 2: "12 Months"}
            for i, col in enumerate(avail):
                series.append((name_map[i], df[col].tolist(), color_map[i]))
            _grouped_bar(labels, series, h=350, ylabel="Credits", key="proj_horizon")

    st.markdown("**Cost Profile by Ingestion Method**")
    profile_cols = ["INGEST_METHOD", "CREDITS_LAST_30_DAYS", "GB_INGESTED_30_DAYS", "FILES_PROCESSED_30_DAYS", "USAGE_TIER"]
    avail_profile = [c for c in profile_cols if c in df.columns]
    st.dataframe(df[avail_profile], use_container_width=True)

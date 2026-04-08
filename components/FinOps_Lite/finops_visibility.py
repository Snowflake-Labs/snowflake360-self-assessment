import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

CREDIT_PRICE = 3.0
STORAGE_PRICE = 23.0


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


def _get_credit_price():
    ci = st.session_state.get("customer_info", {})
    if isinstance(ci, dict):
        p = ci.get("credit_price")
        if p and float(p) > 0:
            return float(p)
    return CREDIT_PRICE


def comp_finops_visibility(entry_actions=None):
    try:
        cp = _get_credit_price()
        _render_top_metrics(cp)
        _render_eac_overview(cp)
        with st.expander("The Executive Forecast (Account Level)", expanded=True):
            _render_executive_forecast(cp)
        with st.expander("Compute Spend by Service & Warehouse", expanded=True):
            _render_compute_breakdown(cp)
        with st.expander("Top 20 Costliest Queries (With User Attribution)", expanded=True):
            _render_costliest_queries(cp)
        with st.expander("Storage Costs (By Database)", expanded=True):
            _render_storage_costs(cp)
        with st.expander("Monthly Warehouse Credit Trend (Last 12 Months)", expanded=True):
            _render_monthly_wh_credits()
        with st.expander("Daily Cost Trend (30 Days) with 7-Day Moving Average", expanded=True):
            _render_daily_cost_trend(cp)
        with st.expander("Query Cost Attribution (By User)", expanded=True):
            _render_user_cost_attribution(cp)
        with st.expander("Data Transfer Volume (30 Days)", expanded=True):
            _render_data_transfer()
        with st.expander("Service Type Cost Breakdown", expanded=True):
            _render_service_type_breakdown(cp)
        _render_wh_eac_heatmap(cp)
        with st.expander("Account-Level Cost Anomalies (Last 60 Days)", expanded=True):
            _render_cost_anomalies(cp)
    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_top_metrics(cp):
    df = _cached_sql("fv_exec_forecast", st.session_state.get("fv_exec_forecast_sql", "SELECT 1 WHERE FALSE"))
    if "fv_exec_forecast" in st.session_state:
        df = st.session_state["fv_exec_forecast"]
    if df.empty:
        return
    compute_cost = 0
    cs_cost = 0
    storage_cost = 0
    for _, row in df.iterrows():
        cat = str(row.get("CATEGORY", ""))
        val = float(row.get("ACTUAL_COST_30D", 0) or 0)
        if "Compute" in cat and "Cloud" not in cat:
            compute_cost = val
        elif "Cloud" in cat:
            cs_cost = val
        elif "Storage" in cat:
            storage_cost = val
    total_cost = compute_cost + cs_cost + storage_cost
    eac = total_cost * 12

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Compute Cost (30d)", f"${compute_cost:,.0f}")
    c2.metric("Cloud Services Cost (30d)", f"${cs_cost:,.0f}")
    c3.metric("Storage Cost (30d)", f"${storage_cost:,.0f}")
    c4.metric("Total Cost (30d)", f"${total_cost:,.0f}")
    c5.metric("EAC (Annual Est.)", f"${eac:,.0f}")


def _render_eac_overview(cp):
    df = st.session_state.get("fv_exec_forecast", pd.DataFrame())
    if df.empty:
        return

    compute_cost = 0
    cs_cost = 0
    storage_cost = 0
    for _, row in df.iterrows():
        cat = str(row.get("CATEGORY", ""))
        val = float(row.get("ACTUAL_COST_30D", 0) or 0)
        if "Compute" in cat and "Cloud" not in cat:
            compute_cost = val
        elif "Cloud" in cat:
            cs_cost = val
        elif "Storage" in cat:
            storage_cost = val
    total_30d = compute_cost + cs_cost + storage_cost
    eac = total_30d * 12

    col_chart, col_table = st.columns(2)
    with col_chart:
        st.markdown("**EAC Overview**")
        cats = ["Compute", "Cloud Services", "Storage", "30-Day Total", "Annual EAC"]
        vals = [compute_cost, cs_cost, storage_cost, total_30d, eac]
        colors = [_C1, _C2, _C3, _C1, _CA]
        fig = go.Figure(data=[go.Bar(
            x=cats, y=vals, marker_color=colors,
            text=[f"${v:,.0f}" for v in vals], textposition="outside",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=50, r=10), yaxis_title="Cost ($)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        st.markdown("**EAC Components**")
        tbl = pd.DataFrame({
            "CATEGORY": ["Compute", "Cloud Services", "Storage", "30-Day Total", "Annual EAC"],
            "VALUE": [f"${compute_cost:,.2f}", f"${cs_cost:,.2f}", f"${storage_cost:,.2f}", f"${total_30d:,.2f}", f"${eac:,.2f}"]
        })
        st.dataframe(tbl, use_container_width=True)


def _render_executive_forecast(cp):
    df = st.session_state.get("fv_exec_forecast", pd.DataFrame())
    if df.empty:
        st.info("No cost data available.")
        return

    st.dataframe(df, use_container_width=True)
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Cost Distribution (Last 30 Days)**")
        cats = df["CATEGORY"].tolist()
        costs = [float(v or 0) for v in df["ACTUAL_COST_30D"].tolist()]
        valid = [(c, v) for c, v in zip(cats, costs) if v > 0]
        if valid:
            labels, values = zip(*valid)
            colors = [_C1, _C2, _C3, _CA][:len(values)]
            fig = go.Figure(data=[go.Pie(
                labels=list(labels), values=list(values), hole=0.45,
                marker=dict(colors=colors),
                textinfo="label+percent",
            )])
            fig.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
                              legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Forecast Comparison by Category**")
        fig2 = go.Figure()
        period_cols = ["ACTUAL_COST_30D", "FORECAST_1M", "FORECAST_3M", "FORECAST_6M", "EAC_ANNUAL"]
        period_labels = ["30d", "1M", "3M", "6M", "EAC"]
        cat_colors = [_C1, _C2, _C3, _CA]
        for i, (_, row) in enumerate(df.iterrows()):
            cat = row["CATEGORY"]
            vals = [float(row.get(c, 0) or 0) for c in period_cols]
            fig2.add_trace(go.Bar(
                name=cat, x=period_labels, y=vals,
                marker_color=cat_colors[i % len(cat_colors)],
            ))
        fig2.update_layout(barmode="group", height=350, margin=dict(t=10, b=40, l=50, r=10),
                           legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", font=dict(size=9)))
        st.plotly_chart(fig2, use_container_width=True)


def _render_compute_breakdown(cp):
    df = st.session_state.get("fv_compute_breakdown", pd.DataFrame())
    if df.empty:
        st.info("No compute breakdown data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Top Compute Resources by Cost (30d)**")
        top = df.head(15).sort_values("COST_LAST_30D", ascending=True)
        fig = go.Figure(data=[go.Bar(
            y=top["RESOURCE_NAME"].tolist(), x=top["COST_LAST_30D"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=200, r=10), xaxis_title="COST_LAST_30D", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Compute Resource Mix**")
        svc = df.groupby("SERVICE_TYPE")["CREDITS_LAST_30D"].sum().reset_index()
        fig2 = go.Figure(data=[go.Pie(
            labels=svc["SERVICE_TYPE"].tolist(), values=svc["CREDITS_LAST_30D"].tolist(),
            hole=0.45, marker=dict(colors=[_C1, _C2, _C3, _CA][:len(svc)]),
            textinfo="label+percent",
        )])
        fig2.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_costliest_queries(cp):
    df = st.session_state.get("fv_costliest_queries", pd.DataFrame())
    if df.empty:
        st.info("No query attribution data available.")
        return

    st.markdown("**Top 20 Queries by Attributed Compute Cost**")
    top = df.head(20).sort_values("QUERY_COST_USD", ascending=True)
    fig = go.Figure(data=[go.Bar(
        y=top["QUERY_ID"].astype(str).tolist(), x=top["QUERY_COST_USD"].tolist(),
        orientation="h", marker_color=_C1,
    )])
    fig.update_layout(height=500, margin=dict(t=10, b=40, l=250, r=10), xaxis_title="QUERY_COST_USD", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_storage_costs(cp):
    df = st.session_state.get("fv_storage_costs", pd.DataFrame())
    if df.empty:
        st.info("No storage cost data available.")
        return

    col1, col2 = st.columns(2)
    top = df.head(15).sort_values("EST_MONTHLY_COST", ascending=True)
    with col1:
        st.markdown("**Estimated Monthly Storage Cost by Database**")
        fig = go.Figure(data=[go.Bar(
            y=top["DATABASE_NAME"].tolist(), x=top["EST_MONTHLY_COST"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=10), xaxis_title="EST_MONTHLY_COST", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    top2 = df.head(15).sort_values("AVG_TB", ascending=True)
    with col2:
        st.markdown("**Average Storage by Database (TB)**")
        fig2 = go.Figure(data=[go.Bar(
            y=top2["DATABASE_NAME"].tolist(), x=top2["AVG_TB"].tolist(),
            orientation="h", marker_color=_CA,
        )])
        fig2.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=10), xaxis_title="AVG_TB", showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_monthly_wh_credits():
    df = st.session_state.get("fv_monthly_wh_credits", pd.DataFrame())
    if df.empty:
        st.info("No monthly warehouse credit data available.")
        return

    st.markdown("**Monthly Warehouse Credits (Last 12 Months)**")
    months = [str(m)[:10] for m in df["MONTH"].tolist()]
    fig = go.Figure(data=[go.Scatter(
        x=months, y=df["MONTHLY_CREDITS"].tolist(),
        mode="lines+markers", line=dict(color=_C1, width=2),
        marker=dict(size=6),
    )])
    fig.update_layout(height=350, margin=dict(t=10, b=60, l=50, r=10),
                      xaxis_title="MONTH", yaxis_title="MONTHLY_CREDITS")
    st.plotly_chart(fig, use_container_width=True)


def _render_daily_cost_trend(cp):
    df = st.session_state.get("fv_daily_cost_trend", pd.DataFrame())
    if df.empty:
        st.info("No daily cost data available.")
        return

    st.markdown("Daily compute + cloud services cost with 7-day rolling average to smooth noise.")
    st.markdown("**Daily Cost with 7-Day Moving Average**")

    dates = [str(d)[:10] for d in df["USAGE_DATE"].tolist()]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=df["TOTAL_COST_USD"].tolist(),
        name="Daily Cost ($)", marker_color=_C3,
    ))
    if "ROLLING_7D_AVG_COST" in df.columns:
        fig.add_trace(go.Scatter(
            x=dates, y=df["ROLLING_7D_AVG_COST"].tolist(),
            name="7-Day MA ($)", mode="lines",
            line=dict(color=_C2, width=2),
        ))
    fig.update_layout(height=400, margin=dict(t=10, b=80, l=50, r=10),
                      xaxis=dict(tickangle=45), yaxis_title="Cost (USD estimate)",
                      legend=dict(orientation="h", y=1.02, x=0, xanchor="left"))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_user_cost_attribution(cp):
    df = st.session_state.get("fv_user_cost_attribution", pd.DataFrame())
    if df.empty:
        st.info("No user cost attribution data available.")
        return

    st.markdown("Attributed compute cost by user over the last 30 days.")

    col1, col2 = st.columns(2)
    top5 = df.head(5).sort_values("TOTAL_COST_USD", ascending=True)
    with col1:
        st.markdown("**Top 10 Users by Attributed Cost**")
        top10 = df.head(10).sort_values("TOTAL_COST_USD", ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=top10["USER_NAME"].tolist(), x=top10["TOTAL_COST_USD"].tolist(),
            orientation="h", marker_color=_C1, name="TOTAL_COST_USD",
            text=[f"${v:,.2f}" for v in top10["TOTAL_COST_USD"].tolist()], textposition="outside",
        ))
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=250, r=80), xaxis_title="Cost (USD)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Top 10 Users by Query Volume**")
        top10q = df.head(10).sort_values("QUERY_COUNT", ascending=True)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            y=top10q["USER_NAME"].tolist(), x=top10q["QUERY_COUNT"].tolist(),
            orientation="h", marker_color=_C2, name="QUERY_COUNT",
            text=[f"{v:,.0f}" for v in top10q["QUERY_COUNT"].tolist()], textposition="outside",
        ))
        fig2.update_layout(height=350, margin=dict(t=10, b=40, l=250, r=80), xaxis_title="Queries", showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_data_transfer():
    df = st.session_state.get("fv_data_transfer", pd.DataFrame())
    if df.empty:
        st.markdown("Egress data transfer by region \u2014 transfers out of Snowflake's cloud region may incur cost.")
        st.info("No data transfer records found.")
        return

    st.dataframe(df, use_container_width=True)


def _render_service_type_breakdown(cp):
    df = st.session_state.get("fv_service_type_breakdown", pd.DataFrame())
    if df.empty:
        st.info("No service type data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Cost by Snowflake Service Type**")
        sdf = df.sort_values("TOTAL_COST_USD", ascending=True)
        fig = go.Figure(data=[go.Bar(
            y=sdf["SERVICE_TYPE"].tolist(), x=sdf["TOTAL_COST_USD"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=200, r=10), xaxis_title="TOTAL_COST_USD", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Service Cost Tier Distribution**")
        if "COST_TIER" in df.columns:
            tier = df.groupby("COST_TIER")["TOTAL_COST_USD"].sum().reset_index()
            fig2 = go.Figure(data=[go.Pie(
                labels=tier["COST_TIER"].tolist(), values=tier["TOTAL_COST_USD"].tolist(),
                hole=0.45, marker=dict(colors=[_C1, _C2, _C3][:len(tier)]),
                textinfo="label+percent",
            )])
            fig2.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_wh_eac_heatmap(cp):
    st.markdown("### Top 30 Warehouse 12-Month EAC Forecast")
    st.markdown(f"Warehouse forecast heatmap using the selected customer's credit price from Customer Info. "
                f"Low projected spend is shaded toward cyan and high projected spend toward orange.")

    df = st.session_state.get("fv_wh_eac_heatmap", pd.DataFrame())
    if df.empty:
        st.info("No warehouse EAC heatmap data available.")
        return

    display_df = df.copy()
    month_cols = [c for c in display_df.columns if c.startswith("M") and c[1:].isdigit()]

    def _fmt_usd(val):
        try:
            return f"${float(val):,.0f}"
        except (ValueError, TypeError):
            return val

    for c in month_cols:
        display_df[c] = display_df[c].apply(_fmt_usd)

    rename = {f"M{i}": str(i) for i in range(1, 13)}
    display_df = display_df.rename(columns=rename)

    num_cols = [str(i) for i in range(1, 13)]

    def _color_cell(val):
        try:
            num = float(str(val).replace("$", "").replace(",", ""))
        except (ValueError, TypeError):
            return ""
        all_vals = []
        for c in month_cols:
            for v in df[c].tolist():
                try:
                    all_vals.append(float(v))
                except (ValueError, TypeError):
                    pass
        if not all_vals:
            return ""
        mn, mx = min(all_vals), max(all_vals)
        if mx == mn:
            return "background-color: rgba(41,181,232,0.3)"
        ratio = (num - mn) / (mx - mn)
        r = int(41 + (232 - 41) * ratio)
        g = int(181 + (162 - 181) * ratio)
        b = int(232 + (41 - 232) * ratio)
        return f"background-color: rgba({r},{g},{b},0.5)"

    styled = display_df.style.applymap(_color_cell, subset=num_cols)
    st.dataframe(styled, use_container_width=True)


def _render_cost_anomalies(cp):
    df = st.session_state.get("fv_cost_anomalies", pd.DataFrame())
    if df.empty:
        st.info("No cost anomalies detected in the last 60 days.")
        return

    severity_colors = {"CRITICAL": "#003D73", "HIGH": _CA, "MODERATE": _C1, "LOW": _C3}

    chart_df = df.sort_values("ANOMALY_DATE", ascending=True).copy()
    dates = [str(d)[:10] for d in chart_df["ANOMALY_DATE"].tolist()]
    colors = [severity_colors.get(s, _C1) for s in chart_df["SEVERITY"].tolist()]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates,
        y=chart_df["ACTUAL_COST_USD"].tolist(),
        name="Actual Cost ($)",
        marker_color=colors,
        text=[f"${v:,.0f}" for v in chart_df["ACTUAL_COST_USD"].tolist()],
        textposition="outside",
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=chart_df["EXPECTED_COST_USD"].tolist(),
        name="Expected Cost ($)",
        mode="lines+markers",
        line=dict(color=_C2, width=2, dash="dash"),
        marker=dict(size=6),
    ))
    fig.update_layout(
        height=400,
        margin=dict(t=30, b=80, l=50, r=10),
        xaxis=dict(tickangle=45, title="Anomaly Date"),
        yaxis_title="Cost (USD)",
        legend=dict(orientation="h", y=1.05, x=0, xanchor="left"),
        barmode="overlay",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        "**Severity Legend:** "
        '<span style="color:#003D73">&#9608; CRITICAL (>100%)</span> · '
        f'<span style="color:{_CA}">&#9608; HIGH (>50%)</span> · '
        f'<span style="color:{_C1}">&#9608; MODERATE (>25%)</span> · '
        f'<span style="color:{_C3}">&#9608; LOW (≤25%)</span>',
        unsafe_allow_html=True,
    )

    st.dataframe(df, use_container_width=True)

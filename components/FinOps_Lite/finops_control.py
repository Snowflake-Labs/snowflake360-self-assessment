import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

CREDIT_PRICE = 3.0


def _get_credit_price():
    ci = st.session_state.get("customer_info", {})
    if isinstance(ci, dict):
        p = ci.get("credit_price")
        if p and float(p) > 0:
            return float(p)
    return CREDIT_PRICE


def comp_finops_control(entry_actions=None):
    try:
        cp = _get_credit_price()
        with st.expander("Resource Monitor Inventory", expanded=True):
            _render_resource_monitors()
        with st.expander("Top Credit Consuming Warehouses (Last 30 Days)", expanded=True):
            _render_top_credit_wh()
        with st.expander("Warehouses with Unusual Activity (Always-On Pattern, 7d)", expanded=True):
            _render_always_on_wh()
        with st.expander("Idle Time Analysis \u2014 Cost Savings Opportunity (10d)", expanded=True):
            _render_idle_time()
        with st.expander("Resource Monitor Coverage Gap Analysis", expanded=True):
            _render_rm_coverage_gap()
        with st.expander("Warehouse Cost Trend \u2014 Week over Week Comparison", expanded=True):
            _render_wow_cost_trend()
        with st.expander("Serverless Compute Costs (Last 30 Days)", expanded=True):
            _render_serverless_costs()
        with st.expander("Spending Summary (30 Days)", expanded=True):
            _render_spending_summary()
        with st.expander("Monthly Spending Trend (Last 12 Months)", expanded=True):
            _render_monthly_trend(cp)
        with st.expander("Storage Costs (Not Budget Controlled)", expanded=True):
            _render_storage_costs()
        with st.expander("Budget MTD Utilization & EOM Projection", expanded=True):
            _render_budget_util()
        with st.expander("Snowpark Container Services (30 Days)", expanded=True):
            _render_spcs()
        with st.expander("Budget Inventory", expanded=True):
            _render_budget_inventory()
        with st.expander("Custom Budgets (Potential Dangling)", expanded=True):
            _render_dangling_budgets()
    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_resource_monitors():
    df = st.session_state.get("fc_resource_monitors", pd.DataFrame())
    if df.empty:
        st.info("No resource monitors configured.")
        return
    st.dataframe(df, use_container_width=True)


def _render_top_credit_wh():
    df = st.session_state.get("fc_top_credit_wh", pd.DataFrame())
    if df.empty:
        st.info("No warehouse credit data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Total Credits by Warehouse (30d)**")
        top = df.head(15).sort_values("TOTAL_CREDITS_30D", ascending=True)
        fig = go.Figure(data=[go.Bar(
            y=top["WAREHOUSE_NAME"].tolist(), x=top["TOTAL_CREDITS_30D"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=10), xaxis_title="TOTAL_CREDITS_30D", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Usage Tier Distribution**")
        if "USAGE_TIER" in df.columns:
            tier = df.groupby("USAGE_TIER")["TOTAL_CREDITS_30D"].sum().reset_index()
            fig2 = go.Figure(data=[go.Pie(
                labels=tier["USAGE_TIER"].tolist(), values=tier["TOTAL_CREDITS_30D"].tolist(),
                hole=0.45, marker=dict(colors=[_C1, _C2, _C3][:len(tier)]),
                textinfo="label+percent",
            )])
            fig2.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_always_on_wh():
    df = st.session_state.get("fc_always_on_wh", pd.DataFrame())
    if df.empty:
        st.info("No warehouses with unusual always-on patterns detected.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Avg Hours/Day Running (last 7d)**")
        top = df.head(15).sort_values("AVG_HOURS_PER_DAY", ascending=True)
        fig = go.Figure(data=[go.Bar(
            y=top["WAREHOUSE_NAME"].tolist(), x=top["AVG_HOURS_PER_DAY"].tolist(),
            orientation="h", marker_color=_CA,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=10), xaxis_title="AVG_HOURS_PER_DAY", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Uptime Status Distribution**")
        if "UPTIME_STATUS" in df.columns:
            tier = df.groupby("UPTIME_STATUS").size().reset_index(name="COUNT")
            fig2 = go.Figure(data=[go.Pie(
                labels=tier["UPTIME_STATUS"].tolist(), values=tier["COUNT"].tolist(),
                hole=0.45, marker=dict(colors=[_C1, _CA, _C3][:len(tier)]),
                textinfo="label+percent",
            )])
            fig2.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_idle_time():
    df = st.session_state.get("fc_idle_time", pd.DataFrame())
    if df.empty:
        st.info("No idle time data available.")
        return

    col1, col2 = st.columns(2)
    top = df.head(15).sort_values("IDLE_CREDITS", ascending=True)
    with col1:
        st.markdown("**Idle Credits by Warehouse (10d)**")
        fig = go.Figure(data=[go.Bar(
            y=top["WAREHOUSE_NAME"].tolist(), x=top["IDLE_CREDITS"].tolist(),
            orientation="h", marker_color=_CA,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=10), xaxis_title="IDLE_CREDITS", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    top2 = df.head(15).sort_values("IDLE_PERCENT", ascending=True)
    with col2:
        st.markdown("**Idle % by Warehouse (10d)**")
        fig2 = go.Figure(data=[go.Bar(
            y=top2["WAREHOUSE_NAME"].tolist(), x=top2["IDLE_PERCENT"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig2.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=10), xaxis_title="IDLE_PERCENT", showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_rm_coverage_gap():
    df = st.session_state.get("fc_rm_coverage_gap", pd.DataFrame())
    if df.empty:
        st.info("No coverage gap data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Coverage Gap \u2014 Item Count**")
        fig = go.Figure(data=[go.Pie(
            labels=df["RISK_CATEGORY"].tolist(), values=df["ITEM_COUNT"].tolist(),
            hole=0.45, marker=dict(colors=[_C1, _C2]),
            textinfo="label+percent",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Coverage Gap \u2014 Credits**")
        fig2 = go.Figure(data=[go.Pie(
            labels=df["RISK_CATEGORY"].tolist(), values=df["CREDITS_OR_QUOTA"].tolist(),
            hole=0.45, marker=dict(colors=[_C1, _C2]),
            textinfo="label+percent",
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_wow_cost_trend():
    df = st.session_state.get("fc_wow_cost_trend", pd.DataFrame())
    if df.empty:
        st.info("No week-over-week data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**WoW Credits Comparison**")
        top = df.head(20)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Previous Week", x=top["WAREHOUSE_NAME"].tolist(), y=top["PREVIOUS_WEEK_CREDITS"].tolist(),
            marker_color=_C3,
        ))
        fig.add_trace(go.Bar(
            name="Current Week", x=top["WAREHOUSE_NAME"].tolist(), y=top["CURRENT_WEEK_CREDITS"].tolist(),
            marker_color=_C2,
        ))
        fig.update_layout(barmode="group", height=400, margin=dict(t=10, b=120, l=50, r=10),
                          xaxis=dict(tickangle=45),
                          legend=dict(orientation="h", y=1.02, x=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Trend Status Distribution**")
        if "TREND_STATUS" in df.columns:
            tier = df.groupby("TREND_STATUS").size().reset_index(name="COUNT")
            fig2 = go.Figure(data=[go.Pie(
                labels=tier["TREND_STATUS"].tolist(), values=tier["COUNT"].tolist(),
                hole=0.45, marker=dict(colors=[_C1, _C2, _CA][:len(tier)]),
                textinfo="label+percent",
            )])
            fig2.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_serverless_costs():
    df = st.session_state.get("fc_serverless_costs", pd.DataFrame())
    if df.empty:
        st.info("No serverless compute costs found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Serverless Credits by Type (30d)**")
        fig = go.Figure(data=[go.Bar(
            y=df["SERVICE_TYPE"].tolist(), x=df["TOTAL_CREDITS"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=300, margin=dict(t=10, b=40, l=200, r=10), xaxis_title="TOTAL_CREDITS", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Serverless Credit Distribution**")
        fig2 = go.Figure(data=[go.Pie(
            labels=df["SERVICE_TYPE"].tolist(), values=df["TOTAL_CREDITS"].tolist(),
            hole=0.45, marker=dict(colors=[_C1, _C2, _C3, _CA][:len(df)]),
            textinfo="label+percent",
        )])
        fig2.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_spending_summary():
    df = st.session_state.get("fc_spending_summary", pd.DataFrame())
    if df.empty:
        st.info("No spending summary data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Credits by Service Type**")
        fig = go.Figure(data=[go.Bar(
            y=df["SERVICE_TYPE"].tolist(), x=df["TOTAL_CREDITS"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=300, margin=dict(t=10, b=40, l=200, r=10), xaxis_title="TOTAL_CREDITS", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Spend Mix**")
        fig2 = go.Figure(data=[go.Pie(
            labels=df["SERVICE_TYPE"].tolist(), values=df["TOTAL_CREDITS"].tolist(),
            hole=0.45, marker=dict(colors=[_C1, _C2][:len(df)]),
            textinfo="label+percent",
        )])
        fig2.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_monthly_trend(cp):
    df = st.session_state.get("fc_monthly_trend", pd.DataFrame())
    if df.empty:
        st.info("No monthly trend data available.")
        return

    st.markdown("Month-by-month warehouse credit spend for year-over-year and trend analysis.")

    sdf = df.sort_values("MONTH", ascending=True)
    months = [str(m)[:10] for m in sdf["MONTH"].tolist()]
    labels = sdf["MONTH_LABEL"].tolist() if "MONTH_LABEL" in sdf.columns else months

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Monthly Credits (Stacked)**")
        fig = go.Figure()
        if "COMPUTE_CREDITS" in sdf.columns and "CS_CREDITS" in sdf.columns:
            fig.add_trace(go.Bar(name="Compute", x=labels, y=sdf["COMPUTE_CREDITS"].tolist(), marker_color=_C1))
            fig.add_trace(go.Bar(name="Cloud Services", x=labels, y=sdf["CS_CREDITS"].tolist(), marker_color=_CA))
        else:
            fig.add_trace(go.Bar(name="Credits", x=labels, y=sdf["TOTAL_CREDITS"].tolist(), marker_color=_C1))
        fig.update_layout(barmode="stack", height=400, margin=dict(t=10, b=80, l=50, r=10), xaxis=dict(tickangle=45),
                          legend=dict(orientation="h", y=1.02, x=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Monthly Estimated Cost USD (Customer Credit Rate)**")
        if "ESTIMATED_COST_USD" in sdf.columns:
            fig2 = go.Figure(data=[go.Scatter(
                x=labels, y=sdf["ESTIMATED_COST_USD"].tolist(),
                mode="lines+markers", line=dict(color=_C2, width=2), marker=dict(size=6),
            )])
            fig2.update_layout(height=400, margin=dict(t=10, b=80, l=50, r=10), xaxis=dict(tickangle=45),
                               yaxis_title="Cost (USD)")
            st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_storage_costs():
    df = st.session_state.get("fc_storage_costs", pd.DataFrame())
    if df.empty:
        st.info("No storage cost data available.")
        return

    st.markdown("**Average Storage TB by Month**")
    sdf = df.sort_values("MONTH", ascending=True)
    months = [str(m)[:10] for m in sdf["MONTH"].tolist()]
    fig = go.Figure(data=[go.Bar(
        x=months, y=sdf["AVG_STORAGE_TB"].tolist(),
        marker_color=_CA,
    )])
    fig.update_layout(height=350, margin=dict(t=10, b=60, l=50, r=10), xaxis_title="MONTH", yaxis_title="AVG_STORAGE_TB")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_budget_util():
    df = st.session_state.get("fc_budget_util", pd.DataFrame())
    if df.empty:
        st.info("No budget utilization data available.")
        return

    st.markdown("Account-level month-to-date budget utilisation and projected month-end status.")

    row = df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Budget Limit", f"{row.get('BUDGET_LIMIT_CREDITS', 0):,.0f} credits")
    c2.metric("Current Spend", f"{row.get('CURRENT_SPEND_CREDITS', 0):,.2f} credits")
    c3.metric("Utilization", f"{row.get('UTILIZATION_PERCENT', 0):,.2f}%")
    c4.metric("Projected Month End", f"{row.get('PROJECTED_MONTH_END_CREDITS', 0):,.2f} cre...")

    st.dataframe(df, use_container_width=True)


def _render_spcs():
    df = st.session_state.get("fc_spcs_credits", pd.DataFrame())
    if df.empty:
        st.info("No SPCS data available.")
        return
    st.dataframe(df, use_container_width=True)


def _render_budget_inventory():
    df = st.session_state.get("fc_budget_inventory", pd.DataFrame())
    if df.empty:
        st.info("No budgets configured.")
        return

    total = len(df)
    root = len(df[df["BUDGET_NAME"] == "ACCOUNT_ROOT_BUDGET"]) if "BUDGET_NAME" in df.columns else 0
    custom = total - root
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Budgets", str(total))
    c2.metric("Root Budgets", str(root))
    c3.metric("Custom Budgets", str(custom))

    st.dataframe(df, use_container_width=True)


def _render_dangling_budgets():
    df = st.session_state.get("fc_dangling_budgets", pd.DataFrame())
    if df.empty:
        st.info("No custom budget data available.")
        return
    st.dataframe(df, use_container_width=True)

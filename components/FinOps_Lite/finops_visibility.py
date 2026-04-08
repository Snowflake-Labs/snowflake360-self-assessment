import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.config.design_tokens import (
    BRAND_PRIMARY, BRAND_SECONDARY,
    CHART_SERIES, CHART_EXTENDED,
)

CREDIT_COST = 3.0
COST_PER_TB = 23.0


def _run_query(sql):
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        return session.sql(sql).to_pandas()
    except Exception as e:
        st.warning(f"Query error: {e}")
        return pd.DataFrame()


_EXEC_FORECAST_SQL = f"""
WITH compute_cost AS (
    SELECT
        'Compute & Services' AS category,
        SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES) AS units,
        SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES) * {CREDIT_COST} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
),
storage_cost AS (
    SELECT
        'Storage' AS category,
        AVG(storage_bytes + stage_bytes + failsafe_bytes) / POW(1024, 4) AS units_tb,
        (AVG(storage_bytes + stage_bytes + failsafe_bytes) / POW(1024, 4)) * {COST_PER_TB} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
    WHERE usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
transfer_cost AS (
    SELECT
        'Data Transfer' AS category,
        SUM(bytes_transferred) / POW(1024, 3) AS units_gb,
        0 AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
unioned AS (
    SELECT * FROM compute_cost
    UNION ALL SELECT * FROM storage_cost
    UNION ALL SELECT * FROM transfer_cost
)
SELECT
    category AS "Category",
    ROUND(cost_last_30d, 2) AS "Actual Cost (Last 30 Days)",
    ROUND(cost_last_30d, 2) AS "Forecast (Next 1 Month)",
    ROUND(cost_last_30d * 3, 2) AS "Forecast (Next 3 Months)",
    ROUND(cost_last_30d * 6, 2) AS "Forecast (Next 6 Months)",
    ROUND(cost_last_30d * 12, 2) AS "EAC (Estimated Annual)"
FROM unioned
"""

_COMPUTE_BREAKDOWN_SQL = f"""
WITH resource_metrics AS (
    SELECT 'WAREHOUSE_METERING' AS service_type, WAREHOUSE_NAME AS resource_name,
           SUM(CREDITS_USED) AS credits_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY 1, 2
    UNION ALL
    SELECT SERVICE_TYPE, SERVICE_TYPE AS resource_name,
           SUM(CREDITS_USED) AS credits_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
      AND SERVICE_TYPE NOT IN ('WAREHOUSE_METERING', 'WAREHOUSE_METERING_READER')
    GROUP BY 1, 2
),
final_calc AS (
    SELECT service_type, resource_name,
           ROUND(credits_last_30d, 1) AS credits_last_30d,
           ROUND(credits_last_30d * {CREDIT_COST}, 2) AS cost_last_30d,
           ROUND((credits_last_30d * {CREDIT_COST}) * 12, 0) AS estimated_annual_cost
    FROM resource_metrics
)
SELECT
    service_type AS "Service Type",
    resource_name AS "Resource Name",
    credits_last_30d AS "Credits (Last 30 Days)",
    cost_last_30d AS "Cost (Last 30 Days)",
    estimated_annual_cost AS "Estimated Annual Cost",
    ROUND(RATIO_TO_REPORT(cost_last_30d) OVER () * 100, 2) AS "% of Total"
FROM final_calc
WHERE cost_last_30d > 0
ORDER BY cost_last_30d DESC
LIMIT 20
"""

_COSTLIEST_QUERIES_SQL = f"""
WITH query_costs AS (
    SELECT query_id, user_name, warehouse_name,
           credits_attributed_compute,
           credits_attributed_compute * {CREDIT_COST} AS query_cost_usd
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
)
SELECT
    ROUND(qc.query_cost_usd, 4) AS "Query Cost ($)",
    qc.user_name AS "User",
    qc.warehouse_name AS "Warehouse",
    qc.query_id AS "Query ID",
    LEFT(qh.query_text, 100) AS "Query Preview"
FROM query_costs qc
JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY qh ON qc.query_id = qh.query_id
ORDER BY qc.query_cost_usd DESC
LIMIT 20
"""

_STORAGE_COSTS_SQL = f"""
SELECT
    usage_date AS "Usage Date",
    database_name AS "Database",
    ROUND(AVG(average_database_bytes) / POW(1024, 3), 2) AS "Avg GB",
    ROUND(AVG(average_database_bytes) / POW(1024, 4), 4) AS "Avg TB",
    ROUND((AVG(average_database_bytes) / POW(1024, 4)) * {COST_PER_TB}, 2) AS "Daily Cost ($)",
    ROUND(((AVG(average_database_bytes) / POW(1024, 4)) * {COST_PER_TB}) * 30, 2) AS "Est Monthly Cost ($)"
FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASE_STORAGE_USAGE_HISTORY
WHERE usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
QUALIFY ROW_NUMBER() OVER (PARTITION BY database_name ORDER BY usage_date DESC) = 1
ORDER BY "Daily Cost ($)" DESC
"""

_DATA_TRANSFER_SQL = """
SELECT
    target_cloud AS "Target Cloud",
    transfer_type AS "Transfer Type",
    ROUND(SUM(bytes_transferred) / POW(1024, 3), 2) AS "GB Transferred"
FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY "GB Transferred" DESC
"""

_DAILY_COST_TREND_SQL = f"""
SELECT
    mdh.usage_date AS "Date",
    ROUND(SUM(mdh.credits_used_compute), 2) AS "Compute Credits",
    ROUND(SUM(mdh.credits_used_cloud_services), 2) AS "Cloud Services Credits",
    ROUND(SUM(mdh.credits_used_compute + mdh.credits_used_cloud_services), 2) AS "Total Credits",
    ROUND(SUM(mdh.credits_used_compute + mdh.credits_used_cloud_services) * {CREDIT_COST}, 2) AS "Total Cost ($)",
    ROUND(AVG(SUM(mdh.credits_used_compute + mdh.credits_used_cloud_services) * {CREDIT_COST}) OVER (
        ORDER BY mdh.usage_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS "7-Day Rolling Avg ($)"
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY mdh
WHERE mdh.usage_date >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY mdh.usage_date
ORDER BY mdh.usage_date ASC
"""

_SERVICE_TYPE_BREAKDOWN_SQL = f"""
SELECT
    mdh.service_type AS "Service Type",
    ROUND(SUM(mdh.credits_used), 2) AS "Total Credits",
    ROUND(SUM(mdh.credits_used) * {CREDIT_COST}, 2) AS "Total Cost ($)",
    ROUND(SUM(mdh.credits_used) * {CREDIT_COST} * 12, 0) AS "Est Annual Cost ($)",
    ROUND(RATIO_TO_REPORT(SUM(mdh.credits_used)) OVER () * 100, 2) AS "% of Total"
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY mdh
WHERE mdh.usage_date >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY mdh.service_type
ORDER BY "Total Cost ($)" DESC
"""

_ANOMALIES_SQL = f"""
SELECT
    date AS "Anomaly Date",
    ROUND(actual_value, 2) AS "Actual Credits",
    ROUND(forecasted_value, 2) AS "Expected Credits",
    ROUND(actual_value * {CREDIT_COST}, 2) AS "Actual Cost ($)",
    ROUND(forecasted_value * {CREDIT_COST}, 2) AS "Expected Cost ($)",
    ROUND((actual_value - forecasted_value) * {CREDIT_COST}, 2) AS "Overspend ($)",
    ROUND(((actual_value - forecasted_value) / NULLIF(forecasted_value, 0)) * 100, 1) AS "Deviation %"
FROM SNOWFLAKE.ACCOUNT_USAGE.ANOMALIES_DAILY
WHERE date >= DATEADD('day', -60, CURRENT_TIMESTAMP())
  AND is_anomaly = TRUE
ORDER BY date DESC
"""

_ALL_VISIBILITY_QUERIES = {
    "finops_exec_forecast": _EXEC_FORECAST_SQL,
    "finops_compute_breakdown": _COMPUTE_BREAKDOWN_SQL,
    "finops_costliest_queries": _COSTLIEST_QUERIES_SQL,
    "finops_storage_costs": _STORAGE_COSTS_SQL,
    "finops_data_transfer": _DATA_TRANSFER_SQL,
    "finops_anomalies": _ANOMALIES_SQL,
    "fv_daily_cost_trend": _DAILY_COST_TREND_SQL,
    "fv_service_type_breakdown": _SERVICE_TYPE_BREAKDOWN_SQL,
}


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_visibility_queries():
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_VISIBILITY_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    for k, sql in needed.items():
        key, df, err = _run_query_thread(session, k, sql)
        st.session_state[key] = df


def comp_finops_visibility(entry_actions=None):
    try:
        _prefetch_all_visibility_queries()
        st.markdown("### Visibility")

        with st.expander("The Executive Forecast (Account Level)", expanded=True):
            _render_executive_forecast()

        with st.expander("Compute Breakdown (By Feature & Warehouse)", expanded=True):
            _render_compute_breakdown()

        with st.expander("Top 20 Costliest Queries (With User Attribution)", expanded=True):
            _render_costliest_queries()

        with st.expander("Storage Costs (By Database)", expanded=True):
            _render_storage_costs_by_database()

        with st.expander("Data Transfer Costs", expanded=True):
            _render_data_transfer_costs()

        with st.expander("Daily Cost Trend (30 Days)", expanded=True):
            _render_daily_cost_trend()

        with st.expander("Cost by Service Type", expanded=True):
            _render_service_type_breakdown()

        with st.expander("Cost Anomalies (Automated Detection)", expanded=True):
            _render_cost_anomalies()

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
            f'Component Error: {str(e)}'
            f'</div>', unsafe_allow_html=True)


def _render_executive_forecast():
    st.markdown("#### The Executive Forecast (Account Level)")
    st.markdown(f"**Cost breakdown and forecast by category** (compute, storage, data transfer) showing last 30 days actual spend and projected costs based on current consumption rates. Using ${CREDIT_COST}/credit, ${COST_PER_TB}/TB/month.")

    cache_key = "finops_exec_forecast"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_EXEC_FORECAST_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.info("No cost data available.")
        return

    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Cost Distribution (Last 30 Days)")
        cats = df["Category"].tolist()
        costs = df["Actual Cost (Last 30 Days)"].tolist()
        palette = ["#29B5E8", "#E8A229", "#0077B6"]
        fig = go.Figure(data=[go.Bar(
            x=cats, y=costs,
            marker_color=palette[:len(cats)],
            text=[f"${v:,.2f}" for v in costs],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=50, r=50), xaxis_title="Category", yaxis_title="Cost ($)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### Forecast Comparison")
        fig2 = go.Figure()
        periods = [
            ("Actual Cost (Last 30 Days)", "#29B5E8"),
            ("Forecast (Next 3 Months)", "#0077B6"),
            ("EAC (Estimated Annual)", "#11567F"),
        ]
        for col_name, color in periods:
            if col_name in df.columns:
                fig2.add_trace(go.Bar(
                    name=col_name.replace("Forecast ", "").replace("(", "").replace(")", ""),
                    x=cats, y=df[col_name].tolist(),
                    marker_color=color,
                    hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
                ))
        fig2.update_layout(barmode="group", height=350, margin=dict(t=10, b=80, l=50, r=50), legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center", font=dict(size=9)))
        st.plotly_chart(fig2, use_container_width=True)


def _render_compute_breakdown():
    st.markdown("#### Compute Breakdown (By Feature & Warehouse)")
    st.markdown(f"**Top 20 resources by cost over last 30 days** at ${CREDIT_COST}/credit.")

    cache_key = "finops_compute_breakdown"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_COMPUTE_BREAKDOWN_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.info("No compute breakdown data available.")
        return

    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Cost by Service Type")
        svc = df.groupby("Service Type")["Cost (Last 30 Days)"].sum().reset_index().sort_values("Cost (Last 30 Days)", ascending=False)
        fig = go.Figure(data=[go.Bar(
            x=svc["Service Type"].tolist(), y=svc["Cost (Last 30 Days)"].tolist(),
            marker_color=BRAND_SECONDARY,
            text=[f"${v:,.2f}" for v in svc["Cost (Last 30 Days)"].tolist()],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=80, l=50, r=50), xaxis=dict(tickangle=45), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### Top 10 Resources by Cost")
        top = df.head(10)
        fig2 = go.Figure(data=[go.Bar(
            y=top["Resource Name"].tolist()[::-1],
            x=top["Cost (Last 30 Days)"].tolist()[::-1],
            orientation="h", marker_color="#E8A229",
            text=[f"${v:,.2f}" for v in top["Cost (Last 30 Days)"].tolist()[::-1]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>",
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=40, l=150, r=50), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)


def _render_costliest_queries():
    st.markdown("#### Top 20 Costliest Queries")
    st.markdown(f"**Most expensive individual queries over last 30 days** at ${CREDIT_COST}/credit.")

    cache_key = "finops_costliest_queries"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_COSTLIEST_QUERIES_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.info("No query attribution data available.")
        return

    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Cost by User (Top 10)")
        user_df = df.groupby("User")["Query Cost ($)"].sum().reset_index().sort_values("Query Cost ($)", ascending=False).head(10)
        fig = go.Figure(data=[go.Bar(
            y=user_df["User"].tolist()[::-1], x=user_df["Query Cost ($)"].tolist()[::-1],
            orientation="h", marker_color="#0077B6",
            text=[f"${v:,.2f}" for v in user_df["Query Cost ($)"].tolist()[::-1]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=120, r=50), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### Cost by Warehouse (Top 10)")
        wh_df = df.groupby("Warehouse")["Query Cost ($)"].sum().reset_index().sort_values("Query Cost ($)", ascending=False).head(10)
        fig2 = go.Figure(data=[go.Bar(
            y=wh_df["Warehouse"].tolist()[::-1], x=wh_df["Query Cost ($)"].tolist()[::-1],
            orientation="h", marker_color="#E8A229",
            text=[f"${v:,.2f}" for v in wh_df["Query Cost ($)"].tolist()[::-1]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>",
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=40, l=120, r=50), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)


def _render_storage_costs_by_database():
    st.markdown("#### Storage Costs (By Database)")
    st.markdown(f"**Latest daily database storage costs** at ${COST_PER_TB}/TB/month.")

    cache_key = "finops_storage_costs"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_STORAGE_COSTS_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.info("No storage cost data available.")
        return

    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Daily Storage Cost (Top 10)")
        top = df.head(10)
        fig = go.Figure(data=[go.Bar(
            y=top["Database"].tolist()[::-1], x=top["Daily Cost ($)"].tolist()[::-1],
            orientation="h", marker_color="#0077B6",
            text=[f"${v:,.2f}" for v in top["Daily Cost ($)"].tolist()[::-1]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=150, r=50), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### Est Monthly Cost (Top 10)")
        top = df.head(10)
        fig2 = go.Figure(data=[go.Bar(
            y=top["Database"].tolist()[::-1], x=top["Est Monthly Cost ($)"].tolist()[::-1],
            orientation="h", marker_color="#00B4D8",
            text=[f"${v:,.2f}" for v in top["Est Monthly Cost ($)"].tolist()[::-1]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>",
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=40, l=150, r=50), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)


def _render_data_transfer_costs():
    st.markdown("#### Data Transfer Costs")
    st.markdown("**Data transfer volume summary** by target cloud and transfer type over last 30 days.")

    cache_key = "finops_data_transfer"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_DATA_TRANSFER_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.info("No data transfer history found in the last 30 days.")
        return

    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### By Target Cloud")
        cloud_df = df.groupby("Target Cloud")["GB Transferred"].sum().reset_index().sort_values("GB Transferred", ascending=False)
        fig = go.Figure(data=[go.Bar(
            x=cloud_df["Target Cloud"].tolist(), y=cloud_df["GB Transferred"].tolist(),
            marker_color=BRAND_SECONDARY,
            text=[f"{v:,.2f} GB" for v in cloud_df["GB Transferred"].tolist()],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y:,.2f} GB<extra></extra>",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=80, l=50, r=50), xaxis=dict(tickangle=45), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### By Transfer Type")
        type_df = df.groupby("Transfer Type")["GB Transferred"].sum().reset_index().sort_values("GB Transferred", ascending=False)
        fig2 = go.Figure(data=[go.Bar(
            x=type_df["Transfer Type"].tolist(), y=type_df["GB Transferred"].tolist(),
            marker_color="#E8A229",
            text=[f"{v:,.2f} GB" for v in type_df["GB Transferred"].tolist()],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y:,.2f} GB<extra></extra>",
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=80, l=50, r=50), xaxis=dict(tickangle=45), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)


def _render_daily_cost_trend():
    st.markdown("#### Daily Cost Trend (30 Days)")
    st.markdown(f"**Daily aggregated credit cost** over last 30 days with rolling 7-day average at ${CREDIT_COST}/credit.")

    cache_key = "fv_daily_cost_trend"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_DAILY_COST_TREND_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.info("No daily cost data available.")
        return

    st.dataframe(df, use_container_width=True)

    dates = [str(d)[:10] for d in df["Date"].tolist()]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=df["Total Cost ($)"].tolist(),
        name="Daily Cost",
        marker_color="#29B5E8",
        hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=df["7-Day Rolling Avg ($)"].tolist(),
        name="7-Day Rolling Avg",
        mode="lines",
        line=dict(color="#E8A229", width=3, dash="dash"),
        hovertemplate="<b>%{x}</b><br>Avg: $%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        height=400,
        margin=dict(t=10, b=80, l=50, r=50),
        xaxis=dict(tickangle=45, title="Date"),
        yaxis=dict(title="Cost ($)"),
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    )
    st.plotly_chart(fig, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    total_cost = df["Total Cost ($)"].sum()
    avg_daily = df["Total Cost ($)"].mean()
    max_day = df.loc[df["Total Cost ($)"].idxmax()]
    with col1:
        st.metric("Total 30-Day Cost", f"${total_cost:,.2f}")
    with col2:
        st.metric("Avg Daily Cost", f"${avg_daily:,.2f}")
    with col3:
        st.metric("Peak Day", f"${max_day['Total Cost ($)']:,.2f}", delta=str(max_day['Date'])[:10])


def _render_service_type_breakdown():
    st.markdown("#### Cost by Service Type")
    st.markdown(f"**Aggregated cost by Snowflake service type** over last 30 days at ${CREDIT_COST}/credit.")

    cache_key = "fv_service_type_breakdown"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_SERVICE_TYPE_BREAKDOWN_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.info("No service type data available.")
        return

    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Cost Distribution by Service Type")
        colors = CHART_EXTENDED[:len(df)] if len(df) <= len(CHART_EXTENDED) else CHART_SERIES[:len(df)]
        fig = go.Figure(data=[go.Pie(
            labels=df["Service Type"].tolist(),
            values=df["Total Cost ($)"].tolist(),
            marker=dict(colors=colors),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
                          legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center", font=dict(size=9)))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### Cost by Service Type (Bar)")
        fig2 = go.Figure(data=[go.Bar(
            y=df["Service Type"].tolist()[::-1],
            x=df["Total Cost ($)"].tolist()[::-1],
            orientation="h", marker_color="#29B5E8",
            text=[f"${v:,.2f}" for v in df["Total Cost ($)"].tolist()[::-1]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>$%{x:,.2f}<extra></extra>",
        )])
        fig2.update_layout(height=400, margin=dict(t=10, b=40, l=200, r=50), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)


def _render_cost_anomalies():
    st.markdown("#### Cost Anomalies (Automated Detection)")
    st.markdown(f"**Daily cost anomalies over last 60 days** showing actual vs expected credits at ${CREDIT_COST}/credit.")

    cache_key = "finops_anomalies"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = _run_query(_ANOMALIES_SQL)

    df = st.session_state[cache_key]
    if df.empty:
        st.markdown(
            '<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
            'No cost anomalies detected in the last 60 days.</div>',
            unsafe_allow_html=True)
        return

    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Overspend by Date (Top 10)")
        top = df.sort_values("Overspend ($)", ascending=False).head(10)
        dates = [str(d)[:10] for d in top["Anomaly Date"].tolist()]
        vals = top["Overspend ($)"].tolist()
        fig = go.Figure(data=[go.Bar(
            x=dates, y=vals,
            marker_color=["#E8A229" if v > 0 else "#29B5E8" for v in vals],
            text=[f"${v:,.2f}" for v in vals],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=80, l=50, r=50), xaxis=dict(tickangle=45), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### Deviation % Distribution")
        dev = df.copy()
        dev["Bucket"] = pd.cut(
            dev["Deviation %"],
            bins=[-float("inf"), 0, 25, 50, 100, float("inf")],
            labels=["< 0%", "0-25%", "25-50%", "50-100%", "> 100%"]
        )
        buckets = dev["Bucket"].value_counts().reset_index()
        buckets.columns = ["Bucket", "Count"]
        colors = ["#29B5E8", "#75C2D8", "#E8A229", "#E8A229", "#11567F"]
        fig2 = go.Figure(data=[go.Bar(
            x=buckets["Bucket"].astype(str).tolist(),
            y=buckets["Count"].tolist(),
            marker_color=colors[:len(buckets)],
            text=buckets["Count"].tolist(),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Count: %{y}<extra></extra>",
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=80, l=50, r=50), xaxis=dict(tickangle=45), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

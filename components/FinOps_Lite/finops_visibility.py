import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'
CREDIT_COST = 3.0
COST_PER_TB = 23.0


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


_SQL_EXEC_FORECAST = f"""
WITH compute_cost AS (
    SELECT 'Compute (Warehouse)' AS category,
           SUM(CREDITS_USED_COMPUTE) * {CREDIT_COST} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
cs_cost AS (
    SELECT 'Cloud Services' AS category,
           SUM(CREDITS_USED_CLOUD_SERVICES) * {CREDIT_COST} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
),
storage_cost AS (
    SELECT 'Storage' AS category,
           (AVG(storage_bytes + stage_bytes + failsafe_bytes) / POW(1024, 4)) * {COST_PER_TB} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
    WHERE usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
transfer_cost AS (
    SELECT 'Data Transfer' AS category, 0 AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    HAVING COUNT(*) >= 0
),
unioned AS (
    SELECT * FROM compute_cost UNION ALL
    SELECT * FROM cs_cost UNION ALL
    SELECT * FROM storage_cost UNION ALL
    SELECT * FROM transfer_cost
)
SELECT
    category AS CATEGORY,
    ROUND(cost_last_30d, 2) AS ACTUAL_COST_30D,
    ROUND(cost_last_30d, 2) AS FORECAST_1M,
    ROUND(cost_last_30d * 3, 2) AS FORECAST_3M,
    ROUND(cost_last_30d * 6, 2) AS FORECAST_6M,
    ROUND(cost_last_30d * 12, 2) AS EAC_ANNUAL
FROM unioned
ORDER BY cost_last_30d DESC
"""

_SQL_COMPUTE_BREAKDOWN = f"""
WITH resource_metrics AS (
    SELECT 'WAREHOUSE' AS service_type, WAREHOUSE_NAME AS resource_name,
           SUM(CREDITS_USED) AS credits_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY WAREHOUSE_NAME
    UNION ALL
    SELECT SERVICE_TYPE, SERVICE_TYPE AS resource_name,
           SUM(CREDITS_USED) AS credits_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
      AND SERVICE_TYPE NOT IN ('WAREHOUSE_METERING', 'WAREHOUSE_METERING_READER')
    GROUP BY SERVICE_TYPE
)
SELECT
    service_type AS SERVICE_TYPE,
    resource_name AS RESOURCE_NAME,
    ROUND(credits_last_30d, 2) AS CREDITS_LAST_30D,
    ROUND(credits_last_30d * {CREDIT_COST}, 2) AS COST_LAST_30D,
    ROUND(credits_last_30d * {CREDIT_COST} * 12, 0) AS ESTIMATED_ANNUAL_COST,
    ROUND(RATIO_TO_REPORT(credits_last_30d * {CREDIT_COST}) OVER () * 100, 2) AS PCT_OF_TOTAL_COMPUTE
FROM resource_metrics
WHERE credits_last_30d > 0
ORDER BY COST_LAST_30D DESC
LIMIT 20
"""

_SQL_COSTLIEST_QUERIES = f"""
WITH query_costs AS (
    SELECT query_id, user_name, warehouse_name,
           ROUND(credits_attributed_compute, 4) AS credits_used,
           ROUND(credits_attributed_compute * {CREDIT_COST}, 4) AS query_cost_usd
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
)
SELECT
    qc.query_cost_usd AS QUERY_COST_USD,
    qc.credits_used AS CREDITS_USED,
    qc.user_name AS USER_NAME,
    qc.warehouse_name AS WAREHOUSE_NAME,
    qc.query_id AS QUERY_ID
FROM query_costs qc
ORDER BY qc.query_cost_usd DESC
LIMIT 20
"""

_SQL_USER_COST_ATTRIBUTION = f"""
SELECT
    user_name AS USER_NAME,
    COUNT(DISTINCT query_id) AS QUERY_COUNT,
    ROUND(SUM(credits_attributed_compute), 2) AS TOTAL_CREDITS,
    ROUND(SUM(credits_attributed_compute) * {CREDIT_COST}, 2) AS TOTAL_COST_USD,
    ROUND(AVG(credits_attributed_compute) * {CREDIT_COST}, 4) AS AVG_COST_PER_QUERY,
    ROUND(RATIO_TO_REPORT(SUM(credits_attributed_compute)) OVER () * 100, 2) AS PCT_OF_TOTAL
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY user_name
ORDER BY TOTAL_COST_USD DESC
LIMIT 20
"""

_SQL_STORAGE_BY_DB = f"""
WITH latest_storage AS (
    SELECT database_name, usage_date, average_database_bytes,
           ROW_NUMBER() OVER (PARTITION BY database_name ORDER BY usage_date DESC) AS rn
    FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASE_STORAGE_USAGE_HISTORY
    WHERE usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
)
SELECT
    database_name AS DATABASE_NAME,
    usage_date AS LATEST_DATE,
    ROUND(average_database_bytes / POW(1024, 3), 2) AS AVG_GB,
    ROUND(average_database_bytes / POW(1024, 4), 4) AS AVG_TB,
    ROUND((average_database_bytes / POW(1024, 4)) * {COST_PER_TB}, 2) AS DAILY_COST_USD,
    ROUND(((average_database_bytes / POW(1024, 4)) * {COST_PER_TB}) * 30, 2) AS EST_MONTHLY_COST,
    ROUND(RATIO_TO_REPORT((average_database_bytes / POW(1024, 4)) * {COST_PER_TB}) OVER () * 100, 2) AS PCT_OF_TOTAL_STORAGE
FROM latest_storage
WHERE rn = 1
ORDER BY DAILY_COST_USD DESC
"""

_SQL_MONTHLY_WH_CREDITS = """
SELECT
    DATE_TRUNC('month', START_TIME) AS MONTH,
    ROUND(SUM(CREDITS_USED), 2) AS MONTHLY_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE START_TIME >= DATEADD('month', -12, CURRENT_TIMESTAMP())
GROUP BY DATE_TRUNC('month', START_TIME)
ORDER BY MONTH
"""

_SQL_DAILY_COST_TREND = f"""
SELECT
    DATE(START_TIME) AS USAGE_DATE,
    ROUND(SUM(CREDITS_USED_COMPUTE), 2) AS COMPUTE_CREDITS,
    ROUND(SUM(CREDITS_USED_CLOUD_SERVICES), 2) AS CLOUD_SERVICES_CREDITS,
    ROUND(SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES), 2) AS TOTAL_CREDITS,
    ROUND(SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES) * {CREDIT_COST}, 2) AS TOTAL_COST_USD,
    ROUND(AVG(SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES) * {CREDIT_COST}) OVER (
        ORDER BY DATE(START_TIME) ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS ROLLING_7D_AVG_COST
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY DATE(START_TIME)
ORDER BY USAGE_DATE
"""

_SQL_DATA_TRANSFER = """
SELECT
    target_cloud AS TARGET_CLOUD,
    transfer_type AS TRANSFER_TYPE,
    ROUND(SUM(bytes_transferred) / POW(1024, 3), 2) AS GB_TRANSFERRED,
    COUNT(*) AS TRANSFER_EVENTS
FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY target_cloud, transfer_type
ORDER BY GB_TRANSFERRED DESC
"""

_SQL_SERVICE_TYPE_COST = f"""
SELECT
    SERVICE_TYPE,
    ROUND(SUM(CREDITS_USED), 2) AS TOTAL_CREDITS,
    ROUND(SUM(CREDITS_USED) * {CREDIT_COST}, 2) AS TOTAL_COST_USD,
    ROUND(SUM(CREDITS_USED) * {CREDIT_COST} * 12, 0) AS EST_ANNUAL_COST,
    ROUND(RATIO_TO_REPORT(SUM(CREDITS_USED)) OVER () * 100, 2) AS PCT_OF_TOTAL,
    CASE
        WHEN SUM(CREDITS_USED) * {CREDIT_COST} > 1000 THEN 'HIGH_COST'
        WHEN SUM(CREDITS_USED) * {CREDIT_COST} > 100 THEN 'MODERATE_COST'
        ELSE 'LOW_COST'
    END AS COST_TIER
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY SERVICE_TYPE
ORDER BY TOTAL_COST_USD DESC
"""

_SQL_WH_EAC_FORECAST = f"""
WITH wh_monthly AS (
    SELECT WAREHOUSE_NAME,
           ROUND(SUM(CREDITS_USED) * {CREDIT_COST}, 0) AS monthly_cost
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY WAREHOUSE_NAME
)
SELECT WAREHOUSE_NAME,
       monthly_cost AS M1,
       monthly_cost * 2 AS M2,
       monthly_cost * 3 AS M3,
       monthly_cost * 4 AS M4,
       monthly_cost * 5 AS M5,
       monthly_cost * 6 AS M6,
       monthly_cost * 7 AS M7,
       monthly_cost * 8 AS M8,
       monthly_cost * 9 AS M9,
       monthly_cost * 10 AS M10,
       monthly_cost * 11 AS M11,
       monthly_cost * 12 AS M12
FROM wh_monthly
ORDER BY monthly_cost DESC
LIMIT 30
"""

_ALL_VIS_QUERIES = {
    "fv_exec_forecast": _SQL_EXEC_FORECAST,
    "fv_compute_breakdown": _SQL_COMPUTE_BREAKDOWN,
    "fv_costliest_queries": _SQL_COSTLIEST_QUERIES,
    "fv_user_cost_attribution": _SQL_USER_COST_ATTRIBUTION,
    "fv_storage_by_db": _SQL_STORAGE_BY_DB,
    "fv_monthly_wh_credits": _SQL_MONTHLY_WH_CREDITS,
    "fv_daily_cost_trend": _SQL_DAILY_COST_TREND,
    "fv_data_transfer": _SQL_DATA_TRANSFER,
    "fv_service_type_cost": _SQL_SERVICE_TYPE_COST,
    "fv_wh_eac_forecast": _SQL_WH_EAC_FORECAST,
}


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch():
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_VIS_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_run_query_thread, session, k, sql): k for k, sql in needed.items()}
        for f in as_completed(futures):
            key, df, _ = f.result()
            st.session_state[key] = df


def comp_finops_visibility(entry_actions=None):
    try:
        _prefetch()

        df_fc = _cached_sql("fv_exec_forecast", _SQL_EXEC_FORECAST)
        _render_kpis(df_fc)

        _render_eac_overview(df_fc)

        with st.expander("The Executive Forecast (Account Level)", expanded=True):
            st.dataframe(df_fc, use_container_width=True)

        _render_cost_distribution(df_fc)

        with st.expander("Compute Spend by Service & Warehouse", expanded=True):
            _render_compute_spend()

        with st.expander("Top 20 Costliest Queries (With User Attribution)", expanded=True):
            _render_costliest_queries()

        with st.expander("Storage Costs (By Database)", expanded=True):
            _render_storage_costs()

        with st.expander("Monthly Warehouse Credit Trend (Last 12 Months)", expanded=True):
            _render_monthly_wh_trend()

        with st.expander("Daily Cost Trend (30 Days) with 7-Day Moving Average", expanded=True):
            st.markdown("Daily compute + cloud services cost with 7-day rolling average to smooth noise.")
            _render_daily_cost_trend()

        with st.expander("Query Cost Attribution (By User)", expanded=True):
            st.markdown("Attributed compute cost by user over the last 30 days.")
            _render_user_cost_attribution()

        with st.expander("Data Transfer Volume (30 Days)", expanded=True):
            st.markdown("Egress data transfer by region — transfers out of Snowflake's cloud region may incur cost.")
            _render_data_transfer()

        with st.expander("Service Type Cost Breakdown", expanded=True):
            _render_service_type_cost()

        st.markdown("#### Top 30 Warehouse 12-Month EAC Forecast")
        st.markdown("Warehouse forecast heatmap using the selected customer's credit price from Customer Info. Low projected spend is shaded toward cyan and high projected spend toward orange.")
        _render_wh_eac_heatmap()

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid {_CA}; padding: 10px;">'
            f'Component Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_kpis(df):
    if df.empty:
        return
    compute_val = 0
    cs_val = 0
    storage_val = 0
    for _, row in df.iterrows():
        cat = str(row.get("CATEGORY", ""))
        cost = float(row.get("ACTUAL_COST_30D", 0) or 0)
        if "Compute" in cat:
            compute_val = cost
        elif "Cloud" in cat:
            cs_val = cost
        elif "Storage" in cat:
            storage_val = cost
    total = compute_val + cs_val + storage_val
    eac = total * 12
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Compute Cost (30d)", f"${compute_val:,.0f}")
    with c2:
        st.metric("Cloud Services Cost (30d)", f"${cs_val:,.0f}")
    with c3:
        st.metric("Storage Cost (30d)", f"${storage_val:,.0f}")
    with c4:
        st.metric("Total Cost (30d)", f"${total:,.0f}")
    with c5:
        st.metric("EAC (Annual Est.)", f"${eac:,.0f}")


def _render_eac_overview(df):
    if df.empty:
        return
    cats = []
    vals = []
    colors = []
    for _, row in df.iterrows():
        cat = str(row.get("CATEGORY", ""))
        cost = float(row.get("ACTUAL_COST_30D", 0) or 0)
        if cost > 0:
            cats.append(cat)
            vals.append(cost)
            colors.append(_C1)
    total = sum(vals)
    eac = total * 12
    cats.append("30-Day Total")
    vals.append(total)
    colors.append(_C2)
    cats.append("Annual EAC")
    vals.append(eac)
    colors.append(_CA)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### EAC Overview")
        fig = go.Figure(data=[go.Bar(
            x=cats, y=vals, marker_color=colors,
            text=[f"${v:,.0f}" for v in vals], textposition="outside",
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=50, r=20),
                          xaxis_title="", yaxis_title="Cost ($)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("#### EAC Components")
        comp_cats = []
        comp_vals = []
        for _, row in df.iterrows():
            cat = str(row.get("CATEGORY", ""))
            cost = float(row.get("ACTUAL_COST_30D", 0) or 0)
            comp_cats.append(cat)
            comp_vals.append(f"${cost:,.2f}")
        comp_cats.append("30-Day Total")
        comp_vals.append(f"${total:,.2f}")
        comp_cats.append("Annual EAC")
        comp_vals.append(f"${eac:,.2f}")
        tbl = pd.DataFrame({"CATEGORY": comp_cats, "VALUE": comp_vals})
        st.dataframe(tbl, use_container_width=True)


def _render_cost_distribution(df):
    if df.empty:
        return
    cats = []
    vals = []
    for _, row in df.iterrows():
        cat = str(row.get("CATEGORY", ""))
        cost = float(row.get("ACTUAL_COST_30D", 0) or 0)
        if cost > 0:
            cats.append(cat)
            vals.append(cost)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Cost Distribution (Last 30 Days)")
        fig = go.Figure(data=[go.Pie(
            labels=cats, values=vals, hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3][:len(cats)]),
            textinfo='percent', textposition='inside',
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("#### Forecast Comparison by Category")
        periods = ["ACTUAL_COST_30D", "FORECAST_1M", "FORECAST_3M", "FORECAST_6M", "EAC_ANNUAL"]
        period_labels = ["30d", "1M", "3M", "6M", "EAC"]
        colors_map = {c: [_C1, _C2, _C3, _CA][:len(cats)] for c in cats}
        fig2 = go.Figure()
        for i, cat in enumerate(cats):
            row = df[df["CATEGORY"] == cat].iloc[0]
            fig2.add_trace(go.Bar(
                name=cat,
                x=period_labels,
                y=[float(row.get(p, 0) or 0) for p in periods],
                marker_color=[_C1, _C2, _C3, _CA][i % 4],
            ))
        fig2.update_layout(barmode="group", height=400,
                           margin=dict(t=10, b=40, l=50, r=20),
                           legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"))
        st.plotly_chart(fig2, use_container_width=True)


def _render_compute_spend():
    df = _cached_sql("fv_compute_breakdown", _SQL_COMPUTE_BREAKDOWN)
    if df.empty:
        st.info("No compute breakdown data available.")
        return
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Top Compute Resources by Cost (30d)")
        top = df.head(15)
        fig = go.Figure(data=[go.Bar(
            y=top["RESOURCE_NAME"].tolist()[::-1],
            x=top["COST_LAST_30D"].tolist()[::-1],
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=450, margin=dict(t=10, b=40, l=200, r=20), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Compute Resource Mix")
        svc = df.groupby("SERVICE_TYPE")["COST_LAST_30D"].sum().reset_index()
        fig2 = go.Figure(data=[go.Pie(
            labels=svc["SERVICE_TYPE"].tolist(),
            values=svc["COST_LAST_30D"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3, _CA][:len(svc)]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=450, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_costliest_queries():
    st.markdown("##### Top 20 Queries by Attributed Compute Cost")
    df = _cached_sql("fv_costliest_queries", _SQL_COSTLIEST_QUERIES)
    if df.empty:
        st.info("No query attribution data available.")
        return
    top = df.head(10)
    fig = go.Figure(data=[go.Bar(
        y=top["QUERY_ID"].tolist()[::-1],
        x=top["QUERY_COST_USD"].tolist()[::-1],
        orientation="h", marker_color=_C1,
    )])
    fig.update_layout(height=400, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                      xaxis_title="QUERY_COST_USD", yaxis_title="QUERY_ID")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_storage_costs():
    df = _cached_sql("fv_storage_by_db", _SQL_STORAGE_BY_DB)
    if df.empty:
        st.info("No storage cost data available.")
        return
    col1, col2 = st.columns(2)
    top = df.head(15)
    with col1:
        st.markdown("##### Estimated Monthly Storage Cost by Database")
        fig = go.Figure(data=[go.Bar(
            y=top["DATABASE_NAME"].tolist()[::-1],
            x=top["EST_MONTHLY_COST"].tolist()[::-1],
            orientation="h", marker_color=_C2,
        )])
        fig.update_layout(height=450, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                          xaxis_title="EST_MONTHLY_COST")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Average Storage by Database (TB)")
        fig2 = go.Figure(data=[go.Bar(
            y=top["DATABASE_NAME"].tolist()[::-1],
            x=top["AVG_TB"].tolist()[::-1],
            orientation="h", marker_color=_CA,
        )])
        fig2.update_layout(height=450, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                           xaxis_title="AVG_TB")
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_monthly_wh_trend():
    st.markdown("##### Monthly Warehouse Credits (Last 12 Months)")
    df = _cached_sql("fv_monthly_wh_credits", _SQL_MONTHLY_WH_CREDITS)
    if df.empty:
        st.info("No monthly credit data available.")
        return
    df = df.sort_values("MONTH")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["MONTH"], y=df["MONTHLY_CREDITS"],
        mode="lines+markers", name="Monthly Credits",
        line=dict(color=_C1, width=2), marker=dict(size=6, color=_C1),
    ))
    fig.update_layout(height=350, margin=dict(t=10, b=40, l=50, r=20),
                      xaxis_title="MONTH", yaxis_title="MONTHLY_CREDITS")
    st.plotly_chart(fig, use_container_width=True)


def _render_daily_cost_trend():
    st.markdown("##### Daily Cost with 7-Day Moving Average")
    df = _cached_sql("fv_daily_cost_trend", _SQL_DAILY_COST_TREND)
    if df.empty:
        st.info("No daily cost data available.")
        return
    df = df.sort_values("USAGE_DATE")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["USAGE_DATE"], y=df["TOTAL_COST_USD"],
        name="Daily Cost ($)", marker_color=_C3,
    ))
    fig.add_trace(go.Scatter(
        x=df["USAGE_DATE"], y=df["ROLLING_7D_AVG_COST"],
        mode="lines", name="7-Day MA ($)",
        line=dict(color=_C2, width=2),
    ))
    fig.update_layout(height=400, margin=dict(t=10, b=40, l=50, r=20),
                      xaxis_title="", yaxis_title="Cost (USD estimate)",
                      legend=dict(orientation="h", y=1.05, x=0, xanchor="left"))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_user_cost_attribution():
    df = _cached_sql("fv_user_cost_attribution", _SQL_USER_COST_ATTRIBUTION)
    if df.empty:
        st.info("No user attribution data available.")
        return
    col1, col2 = st.columns(2)
    top5 = df.head(5)
    with col1:
        st.markdown("##### Top 10 Users by Attributed Cost")
        top10 = df.head(10)
        fig = go.Figure(data=[go.Bar(
            y=top10["USER_NAME"].tolist()[::-1],
            x=top10["TOTAL_COST_USD"].tolist()[::-1],
            orientation="h",
            marker_color=[_C2, _C1][:1] * len(top10),
            text=[f"${v:,.2f}" for v in top10["TOTAL_COST_USD"].tolist()[::-1]],
            textposition="outside",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                          xaxis_title="Cost (USD)")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Top 10 Users by Query Volume")
        top10 = df.head(10)
        fig2 = go.Figure(data=[go.Bar(
            y=top10["USER_NAME"].tolist()[::-1],
            x=top10["QUERY_COUNT"].tolist()[::-1],
            orientation="h",
            marker_color=[_C1, _C2][:1] * len(top10),
            text=[f"{int(v):,}" for v in top10["QUERY_COUNT"].tolist()[::-1]],
            textposition="outside",
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                           xaxis_title="Queries")
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_data_transfer():
    df = _cached_sql("fv_data_transfer", _SQL_DATA_TRANSFER)
    if df.empty:
        st.info("No data transfer records found.")
        return
    st.dataframe(df, use_container_width=True)


def _render_service_type_cost():
    df = _cached_sql("fv_service_type_cost", _SQL_SERVICE_TYPE_COST)
    if df.empty:
        st.info("No service type cost data available.")
        return
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Cost by Snowflake Service Type")
        fig = go.Figure(data=[go.Bar(
            y=df["SERVICE_TYPE"].tolist()[::-1],
            x=df["TOTAL_COST_USD"].tolist()[::-1],
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=180, r=20), showlegend=False,
                          xaxis_title="TOTAL_COST_USD")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Service Cost Tier Distribution")
        tier = df.groupby("COST_TIER")["PCT_OF_TOTAL"].sum().reset_index()
        fig2 = go.Figure(data=[go.Pie(
            labels=tier["COST_TIER"].tolist(),
            values=tier["PCT_OF_TOTAL"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3][:len(tier)]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_wh_eac_heatmap():
    df = _cached_sql("fv_wh_eac_forecast", _SQL_WH_EAC_FORECAST)
    if df.empty:
        st.info("No warehouse EAC forecast data available.")
        return
    months = [str(i) for i in range(1, 13)]
    wh_names = df["WAREHOUSE_NAME"].tolist()
    z_vals = []
    for _, row in df.iterrows():
        z_vals.append([float(row.get(f"M{i}", 0) or 0) for i in range(1, 13)])

    text_vals = [[f"${v:,.0f}" for v in row] for row in z_vals]
    fig = go.Figure(data=go.Heatmap(
        z=z_vals, x=months, y=wh_names,
        text=text_vals, texttemplate="%{text}",
        colorscale=[[0, _C3], [0.5, _CA], [1, _CA]],
        showscale=False,
    ))
    fig.update_layout(
        height=max(400, len(wh_names) * 28),
        margin=dict(t=10, b=40, l=250, r=20),
        xaxis=dict(side="top"),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'


def _get_credit_rate():
    return float(st.session_state.get("rate_credit", 3.0))


def _cached_sql(cache_key, sql):
    credit_rate = _get_credit_rate()
    keyed = f"{cache_key}_{credit_rate}"
    if keyed in st.session_state:
        return st.session_state[keyed]
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        formatted = sql.format(CREDIT_COST=credit_rate)
        df = session.sql(formatted).to_pandas()
    except Exception:
        df = pd.DataFrame()
    st.session_state[keyed] = df
    return df


_SQL_RESOURCE_MONITORS = """
SELECT name AS MONITOR_NAME, credit_quota AS CREDIT_QUOTA,
       notify AS NOTIFY, suspend AS SUSPEND, suspend_immediate AS SUSPEND_IMMEDIATE,
       created AS CREATED, owner AS OWNER, warehouses AS WAREHOUSES
FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS
ORDER BY credit_quota DESC
"""

_SQL_TOP_WH_CREDITS = """
SELECT warehouse_name AS WAREHOUSE_NAME,
       ROUND(SUM(credits_used), 2) AS TOTAL_CREDITS_30D,
       ROUND(AVG(credits_used), 4) AS AVG_CREDITS_PER_HOUR,
       COUNT(*) AS HOURS_ACTIVE,
       ROUND(SUM(credits_used_compute), 2) AS COMPUTE_CREDITS,
       ROUND(SUM(credits_used_cloud_services), 2) AS CLOUD_SERVICES_CREDITS,
       CASE WHEN SUM(credits_used) > 1000 THEN 'HIGH_USAGE'
            WHEN SUM(credits_used) > 500 THEN 'MEDIUM_USAGE'
            ELSE 'LOW_USAGE' END AS USAGE_TIER
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
GROUP BY warehouse_name
ORDER BY TOTAL_CREDITS_30D DESC
"""

_SQL_UNUSUAL_ACTIVITY = """
WITH daily_usage AS (
    SELECT warehouse_name, DATE(start_time) AS usage_date,
           COUNT(DISTINCT HOUR(start_time)) AS hours_running_per_day
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
    GROUP BY warehouse_name, DATE(start_time)
)
SELECT warehouse_name AS WAREHOUSE_NAME,
       ROUND(AVG(hours_running_per_day), 1) AS AVG_HOURS_PER_DAY,
       MAX(hours_running_per_day) AS MAX_HOURS_PER_DAY,
       COUNT(*) AS DAYS_TRACKED,
       CASE WHEN AVG(hours_running_per_day) >= 20 THEN 'ALWAYS_ON'
            WHEN AVG(hours_running_per_day) >= 12 THEN 'HIGH_UPTIME'
            ELSE 'NORMAL' END AS UPTIME_STATUS
FROM daily_usage
GROUP BY warehouse_name
HAVING AVG(hours_running_per_day) >= 12
ORDER BY AVG_HOURS_PER_DAY DESC
"""

_SQL_IDLE_TIME = """
SELECT warehouse_name AS WAREHOUSE_NAME,
       ROUND(SUM(credits_used_compute), 2) AS TOTAL_COMPUTE_CREDITS,
       ROUND(SUM(credits_attributed_compute_queries), 2) AS QUERY_CREDITS,
       ROUND(SUM(credits_used_compute) - SUM(credits_attributed_compute_queries), 2) AS IDLE_CREDITS,
       ROUND((SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
             NULLIF(SUM(credits_used_compute), 0) * 100, 2) AS IDLE_PERCENT,
       CASE WHEN (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
                 NULLIF(SUM(credits_used_compute), 0) > 0.3 THEN 'HIGH_IDLE_OPTIMIZE_AUTO_SUSP'
            WHEN (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
                 NULLIF(SUM(credits_used_compute), 0) > 0.15 THEN 'MODERATE_IDLE'
            ELSE 'LOW_IDLE' END AS IDLE_STATUS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD('day', -10, CURRENT_DATE)
  AND credits_attributed_compute_queries IS NOT NULL
GROUP BY warehouse_name
HAVING SUM(credits_used_compute) - SUM(credits_attributed_compute_queries) > 0
ORDER BY IDLE_CREDITS DESC
"""

_SQL_RM_COVERAGE_GAP = """
WITH warehouse_spend AS (
    SELECT warehouse_name, SUM(credits_used) AS monthly_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY warehouse_name
),
monitor_quotas AS (
    SELECT name AS monitor_name, credit_quota
    FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS
    WHERE deleted IS NULL
),
combined AS (
    SELECT 'Warehouses without Resource Monitors' AS RISK_CATEGORY,
           COUNT(DISTINCT warehouse_name) AS ITEM_COUNT,
           ROUND(SUM(monthly_credits), 2) AS CREDITS_OR_QUOTA,
           LISTAGG(warehouse_name, ', ') WITHIN GROUP (ORDER BY monthly_credits DESC) AS ITEM_LIST
    FROM warehouse_spend WHERE monthly_credits > 100
    UNION ALL
    SELECT 'Resource Monitors Configured', COUNT(*),
           ROUND(SUM(credit_quota), 2),
           LISTAGG(monitor_name, ', ') WITHIN GROUP (ORDER BY credit_quota DESC)
    FROM monitor_quotas
)
SELECT * FROM combined
"""

_SQL_WOW_COST_TREND = """
WITH weekly_data AS (
    SELECT warehouse_name,
           SUM(CASE WHEN start_time >= DATEADD('day', -7, CURRENT_DATE) THEN credits_used ELSE 0 END) AS current_credits,
           SUM(CASE WHEN start_time >= DATEADD('day', -14, CURRENT_DATE) AND start_time < DATEADD('day', -7, CURRENT_DATE)
                    THEN credits_used ELSE 0 END) AS previous_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATEADD('day', -14, CURRENT_DATE)
    GROUP BY warehouse_name
)
SELECT warehouse_name AS WAREHOUSE_NAME,
       ROUND(previous_credits, 2) AS PREVIOUS_WEEK_CREDITS,
       ROUND(current_credits, 2) AS CURRENT_WEEK_CREDITS,
       ROUND(current_credits - previous_credits, 2) AS CREDIT_CHANGE,
       ROUND((current_credits - previous_credits) / NULLIF(previous_credits, 0) * 100, 2) AS PERCENT_CHANGE,
       CASE WHEN (current_credits - previous_credits) / NULLIF(previous_credits, 0) > 0.5 THEN 'COST_SPIKE_GT_50PCT'
            WHEN (current_credits - previous_credits) / NULLIF(previous_credits, 0) > 0.25 THEN 'COST_INCREASE_GT_25PCT'
            ELSE 'STABLE_OR_DECREASING' END AS TREND_STATUS
FROM weekly_data
WHERE current_credits > 10 OR previous_credits > 10
ORDER BY CREDIT_CHANGE DESC
"""

_SQL_SERVERLESS_COSTS = """
SELECT service_type AS SERVICE_TYPE, total_credits AS TOTAL_CREDITS, databases_using AS DATABASES_USING, executions AS EXECUTIONS
FROM (
    SELECT 'AUTO_CLUSTERING' AS service_type, ROUND(SUM(credits_used), 2) AS total_credits,
           COUNT(DISTINCT database_name) AS databases_using, COUNT(*) AS executions
    FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
    UNION ALL
    SELECT 'SERVERLESS_TASK', ROUND(SUM(credits_used), 2),
           COUNT(DISTINCT database_name), COUNT(*)
    FROM SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
    UNION ALL
    SELECT 'MATERIALIZED_VIEWS', ROUND(SUM(credits_used), 2),
           COUNT(DISTINCT database_name), COUNT(*)
    FROM SNOWFLAKE.ACCOUNT_USAGE.MATERIALIZED_VIEW_REFRESH_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
    UNION ALL
    SELECT 'SEARCH_OPTIMIZATION', ROUND(SUM(credits_used), 2),
           COUNT(DISTINCT database_name), COUNT(*)
    FROM SNOWFLAKE.ACCOUNT_USAGE.SEARCH_OPTIMIZATION_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
) s
WHERE total_credits > 0
ORDER BY total_credits DESC
"""

_SQL_SPENDING_SUMMARY = """
SELECT 'WAREHOUSE_METERING' AS SERVICE_TYPE,
       ROUND(SUM(credits_used), 2) AS TOTAL_CREDITS,
       COUNT(DISTINCT DATE(start_time)) AS DAYS_WITH_ACTIVITY,
       ROUND(AVG(credits_used), 4) AS AVG_PER_EVENT,
       ROUND(MIN(credits_used), 4) AS MIN_PER_EVENT,
       ROUND(MAX(credits_used), 4) AS MAX_PER_EVENT
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
UNION ALL
SELECT 'SERVERLESS_TASKS', ROUND(SUM(credits_used), 2),
       COUNT(DISTINCT DATE(start_time)), ROUND(AVG(credits_used), 4),
       ROUND(MIN(credits_used), 4), ROUND(MAX(credits_used), 4)
FROM SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
ORDER BY TOTAL_CREDITS DESC
"""

_SQL_MONTHLY_TREND = """
SELECT DATE_TRUNC('month', start_time) AS MONTH,
       ROUND(SUM(credits_used_compute), 2) AS COMPUTE_CREDITS,
       ROUND(SUM(credits_used_cloud_services), 2) AS CS_CREDITS,
       ROUND(SUM(credits_used), 2) AS TOTAL_CREDITS,
       COUNT(DISTINCT DATE(start_time)) AS DAYS_IN_MONTH,
       ROUND(SUM(credits_used) * {CREDIT_COST}, 2) AS ESTIMATED_COST_USD,
       TO_CHAR(DATE_TRUNC('month', start_time), 'Mon YYYY') AS MONTH_LABEL
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
GROUP BY DATE_TRUNC('month', start_time)
ORDER BY MONTH DESC
LIMIT 12
"""

_SQL_STORAGE_COSTS = """
SELECT DATE_TRUNC('month', usage_date) AS MONTH,
       ROUND(AVG(storage_bytes + stage_bytes + failsafe_bytes) / POWER(1024, 4), 4) AS AVG_STORAGE_TB,
       'Storage NOT covered by compute budgets' AS NOTE
FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
WHERE usage_date >= DATEADD('month', -3, CURRENT_DATE)
GROUP BY DATE_TRUNC('month', usage_date)
ORDER BY MONTH DESC
"""

_SQL_BUDGET_MTD = """
WITH current_month_spend AS (
    SELECT SUM(CREDITS_USED) AS month_to_date_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATE_TRUNC('month', CURRENT_TIMESTAMP())
),
daily_avg AS (
    SELECT AVG(daily_credits) AS avg_daily_spend
    FROM (SELECT DATE(START_TIME) AS d, SUM(CREDITS_USED) AS daily_credits
          FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
          WHERE START_TIME >= DATEADD('day', -30, CURRENT_DATE) GROUP BY d)
)
SELECT 500 AS BUDGET_LIMIT_CREDITS,
       ROUND(s.month_to_date_credits, 2) AS CURRENT_SPEND_CREDITS,
       ROUND((s.month_to_date_credits / 500) * 100, 2) AS UTILIZATION_PERCENT,
       ROUND(500 - s.month_to_date_credits, 2) AS REMAINING_CREDITS,
       CASE WHEN (s.month_to_date_credits / 500) > 0.9 THEN 'WARNING_GT_90PCT'
            WHEN (s.month_to_date_credits / 500) > 0.75 THEN 'CAUTION_GT_75PCT'
            ELSE 'HEALTHY_LT_75PCT' END AS UTILIZATION_STATUS,
       ROUND(d.avg_daily_spend, 2) AS AVG_DAILY_SPEND_30D,
       DAY(LAST_DAY(CURRENT_DATE)) AS DAYS_IN_MONTH,
       DAY(CURRENT_DATE) AS DAYS_ELAPSED,
       ROUND(d.avg_daily_spend * DAY(LAST_DAY(CURRENT_DATE)), 2) AS PROJECTED_MONTH_END_CREDITS
FROM current_month_spend s CROSS JOIN daily_avg d
"""

_SQL_SPCS = """
SELECT 'SPCS Services' AS SERVICE_NAME,
       ROUND(SUM(credits_used), 2) AS TOTAL_CREDITS,
       'Covered by ACCOUNT_ROOT_BUDGET' AS BUDGET_STATUS
FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPARK_CONTAINER_SERVICES_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
"""

_SQL_BUDGET_INVENTORY = """
SELECT name AS BUDGET_NAME,
       DATABASE_NAME || '.' || SCHEMA_NAME AS FULL_PATH,
       CREATED AS CREATED_DATE,
       OWNER_NAME AS OWNER,
       COMMENT
FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
WHERE CLASS_NAME = 'BUDGET' AND DELETED IS NULL
ORDER BY CREATED DESC
"""

_SQL_CUSTOM_BUDGETS = """
WITH all_budgets AS (
    SELECT name AS budget_name
    FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
    WHERE class_name = 'BUDGET' AND deleted IS NULL AND name != 'ACCOUNT_ROOT_BUDGET'
)
SELECT COUNT(*) AS CUSTOM_BUDGET_COUNT,
       LISTAGG(budget_name, ', ') WITHIN GROUP (ORDER BY budget_name) AS BUDGET_NAMES,
       'Note: Use <budget>!GET_LINKED_RESOURCES() to verify attachments' AS RECOMMENDATION
FROM all_budgets
"""

_ALL_CTRL_QUERIES = {
    "fc_resource_monitors": _SQL_RESOURCE_MONITORS,
    "fc_top_wh_credits": _SQL_TOP_WH_CREDITS,
    "fc_unusual_activity": _SQL_UNUSUAL_ACTIVITY,
    "fc_idle_time": _SQL_IDLE_TIME,
    "fc_rm_coverage_gap": _SQL_RM_COVERAGE_GAP,
    "fc_wow_cost_trend": _SQL_WOW_COST_TREND,
    "fc_serverless_costs": _SQL_SERVERLESS_COSTS,
    "fc_spending_summary": _SQL_SPENDING_SUMMARY,
    "fc_monthly_trend": _SQL_MONTHLY_TREND,
    "fc_storage_costs": _SQL_STORAGE_COSTS,
    "fc_budget_mtd": _SQL_BUDGET_MTD,
    "fc_spcs": _SQL_SPCS,
    "fc_budget_inventory": _SQL_BUDGET_INVENTORY,
    "fc_custom_budgets": _SQL_CUSTOM_BUDGETS,
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
    needed = {k: sql for k, sql in _ALL_CTRL_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_run_query_thread, session, k, sql): k for k, sql in needed.items()}
        for f in as_completed(futures):
            key, df, _ = f.result()
            st.session_state[key] = df


def comp_finops_control(entry_actions=None):
    try:
        _prefetch()

        with st.expander("Resource Monitor Inventory", expanded=True):
            df = _cached_sql("fc_resource_monitors", _SQL_RESOURCE_MONITORS)
            if df.empty:
                st.info("No resource monitors configured.")
            else:
                st.dataframe(df, use_container_width=True)

        with st.expander("Top Credit Consuming Warehouses (Last 30 Days)", expanded=True):
            _render_top_wh_credits()

        with st.expander("Warehouses with Unusual Activity (Always-On Pattern, 7d)", expanded=True):
            _render_unusual_activity()

        with st.expander("Idle Time Analysis \u2014 Cost Savings Opportunity (10d)", expanded=True):
            _render_idle_time()

        with st.expander("Resource Monitor Coverage Gap Analysis", expanded=True):
            _render_rm_coverage_gap()

        with st.expander("Warehouse Cost Trend \u2014 Week over Week Comparison", expanded=True):
            _render_wow_trend()

        with st.expander("Serverless Compute Costs (Last 30 Days)", expanded=True):
            _render_serverless_costs()

        with st.expander("Spending Summary (30 Days)", expanded=True):
            _render_spending_summary()

        with st.expander("Monthly Spending Trend (Last 12 Months)", expanded=True):
            st.markdown("Month-by-month warehouse credit spend for year-over-year and trend analysis.")
            _render_monthly_trend()

        with st.expander("Storage Costs (Not Budget Controlled)", expanded=True):
            _render_storage_costs()

        with st.expander("Budget MTD Utilization & EOM Projection", expanded=True):
            st.markdown("Account-level month-to-date budget utilisation and projected month-end status.")
            _render_budget_mtd()

        with st.expander("Snowpark Container Services (30 Days)", expanded=True):
            df = _cached_sql("fc_spcs", _SQL_SPCS)
            st.dataframe(df, use_container_width=True)

        with st.expander("Budget Inventory", expanded=True):
            _render_budget_inventory()

        with st.expander("Custom Budgets (Potential Dangling)", expanded=True):
            df = _cached_sql("fc_custom_budgets", _SQL_CUSTOM_BUDGETS)
            st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid {_CA}; padding: 10px;">'
            f'Component Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_top_wh_credits():
    df = _cached_sql("fc_top_wh_credits", _SQL_TOP_WH_CREDITS)
    if df.empty:
        st.info("No warehouse credit data available.")
        return
    col1, col2 = st.columns(2)
    top = df.head(15)
    with col1:
        st.markdown("##### Total Credits by Warehouse (30d)")
        fig = go.Figure(data=[go.Bar(
            y=top["WAREHOUSE_NAME"].tolist()[::-1],
            x=top["TOTAL_CREDITS_30D"].tolist()[::-1],
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=450, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                          xaxis_title="TOTAL_CREDITS_30D")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Usage Tier Distribution")
        tier = df.groupby("USAGE_TIER").size().reset_index(name="COUNT")
        fig2 = go.Figure(data=[go.Pie(
            labels=tier["USAGE_TIER"].tolist(),
            values=tier["COUNT"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3][:len(tier)]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=450, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_unusual_activity():
    df = _cached_sql("fc_unusual_activity", _SQL_UNUSUAL_ACTIVITY)
    if df.empty:
        st.info("No warehouses detected running \u226512 hours/day on average.")
        return
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Avg Hours/Day Running (last 7d)")
        fig = go.Figure(data=[go.Bar(
            y=df["WAREHOUSE_NAME"].tolist()[::-1],
            x=df["AVG_HOURS_PER_DAY"].tolist()[::-1],
            orientation="h", marker_color=_CA,
        )])
        fig.update_layout(height=450, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                          xaxis_title="AVG_HOURS_PER_DAY")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Uptime Status Distribution")
        tier = df.groupby("UPTIME_STATUS").size().reset_index(name="COUNT")
        fig2 = go.Figure(data=[go.Pie(
            labels=tier["UPTIME_STATUS"].tolist(),
            values=tier["COUNT"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3][:len(tier)]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=450, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_idle_time():
    df = _cached_sql("fc_idle_time", _SQL_IDLE_TIME)
    if df.empty:
        st.info("No significant idle credit waste detected.")
        return
    for c in ['TOTAL_COMPUTE_CREDITS', 'QUERY_CREDITS', 'IDLE_CREDITS', 'IDLE_PERCENT']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Idle Credits by Warehouse (10d)")
        fig = go.Figure(data=[go.Bar(
            y=df["WAREHOUSE_NAME"].tolist()[::-1],
            x=df["IDLE_CREDITS"].tolist()[::-1],
            orientation="h", marker_color=_CA,
        )])
        fig.update_layout(height=450, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                          xaxis_title="IDLE_CREDITS")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Idle % by Warehouse (10d)")
        fig2 = go.Figure(data=[go.Bar(
            y=df["WAREHOUSE_NAME"].tolist()[::-1],
            x=df["IDLE_PERCENT"].tolist()[::-1],
            orientation="h", marker_color=_CA,
        )])
        fig2.update_layout(height=450, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                           xaxis_title="IDLE_PERCENT")
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_rm_coverage_gap():
    df = _cached_sql("fc_rm_coverage_gap", _SQL_RM_COVERAGE_GAP)
    if df.empty:
        st.info("No data available for resource monitor coverage analysis.")
        return
    df['ITEM_COUNT'] = pd.to_numeric(df['ITEM_COUNT'], errors='coerce').fillna(0)
    df['CREDITS_OR_QUOTA'] = pd.to_numeric(df['CREDITS_OR_QUOTA'], errors='coerce').fillna(0)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Coverage Gap \u2014 Item Count")
        fig = go.Figure(data=[go.Pie(
            labels=df["RISK_CATEGORY"].tolist(),
            values=df["ITEM_COUNT"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2]),
            textinfo='percent', textposition='inside',
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Coverage Gap \u2014 Credits")
        fig2 = go.Figure(data=[go.Pie(
            labels=df["RISK_CATEGORY"].tolist(),
            values=df["CREDITS_OR_QUOTA"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_wow_trend():
    df = _cached_sql("fc_wow_cost_trend", _SQL_WOW_COST_TREND)
    if df.empty:
        st.info("Insufficient data for week-over-week trend analysis.")
        return
    for c in ['PREVIOUS_WEEK_CREDITS', 'CURRENT_WEEK_CREDITS']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### WoW Credits Comparison")
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Previous Week', x=df['WAREHOUSE_NAME'], y=df['PREVIOUS_WEEK_CREDITS'], marker_color=_C3))
        fig.add_trace(go.Bar(name='Current Week', x=df['WAREHOUSE_NAME'], y=df['CURRENT_WEEK_CREDITS'], marker_color=_C1))
        fig.update_layout(barmode='group', height=400, margin=dict(t=10, b=80, l=50, r=20),
                          legend=dict(orientation='h', y=1.05, x=0))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Trend Status Distribution")
        tier = df.groupby("TREND_STATUS").size().reset_index(name="COUNT")
        fig2 = go.Figure(data=[go.Pie(
            labels=tier["TREND_STATUS"].tolist(),
            values=tier["COUNT"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3][:len(tier)]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_serverless_costs():
    df = _cached_sql("fc_serverless_costs", _SQL_SERVERLESS_COSTS)
    if df.empty:
        st.info("No serverless compute costs detected in the last 30 days.")
        return
    df['TOTAL_CREDITS'] = pd.to_numeric(df['TOTAL_CREDITS'], errors='coerce').fillna(0)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Serverless Credits by Type (30d)")
        fig = go.Figure(data=[go.Bar(
            y=df["SERVICE_TYPE"].tolist()[::-1],
            x=df["TOTAL_CREDITS"].tolist()[::-1],
            orientation="h", marker_color=_C2,
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=150, r=20), showlegend=False,
                          xaxis_title="TOTAL_CREDITS")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Serverless Credit Distribution")
        fig2 = go.Figure(data=[go.Pie(
            labels=df["SERVICE_TYPE"].tolist(),
            values=df["TOTAL_CREDITS"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3, _CA][:len(df)]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_spending_summary():
    df = _cached_sql("fc_spending_summary", _SQL_SPENDING_SUMMARY)
    if df.empty:
        st.info("No spending data available for the last 30 days.")
        return
    df['TOTAL_CREDITS'] = pd.to_numeric(df['TOTAL_CREDITS'], errors='coerce').fillna(0)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Credits by Service Type")
        fig = go.Figure(data=[go.Bar(
            y=df["SERVICE_TYPE"].tolist()[::-1],
            x=df["TOTAL_CREDITS"].tolist()[::-1],
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=300, margin=dict(t=10, b=40, l=150, r=20), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Spend Mix")
        fig2 = go.Figure(data=[go.Pie(
            labels=df["SERVICE_TYPE"].tolist(),
            values=df["TOTAL_CREDITS"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2][:len(df)]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_monthly_trend():
    df = _cached_sql("fc_monthly_trend", _SQL_MONTHLY_TREND)
    if df.empty:
        st.info("No monthly spending data available.")
        return
    for c in ['COMPUTE_CREDITS', 'CS_CREDITS', 'TOTAL_CREDITS', 'ESTIMATED_COST_USD']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df = df.sort_values('MONTH')
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Monthly Credits (Stacked)")
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Compute', x=df['MONTH'], y=df['COMPUTE_CREDITS'], marker_color=_C1))
        fig.add_trace(go.Bar(name='Cloud Services', x=df['MONTH'], y=df['CS_CREDITS'], marker_color=_CA))
        fig.update_layout(barmode='stack', height=400, margin=dict(t=10, b=80, l=50, r=20),
                          legend=dict(orientation='h', y=1.05, x=0))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Monthly Estimated Cost USD (Customer Credit Rate)")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df['MONTH'], y=df['ESTIMATED_COST_USD'],
            mode='lines+markers', name='Cost (USD)',
            line=dict(color=_C2, width=2), marker=dict(size=6, color=_C2),
        ))
        fig2.update_layout(height=400, margin=dict(t=10, b=80, l=50, r=20),
                           xaxis_title="Month", yaxis_title="Cost (USD)")
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_storage_costs():
    st.markdown("##### Average Storage TB by Month")
    df = _cached_sql("fc_storage_costs", _SQL_STORAGE_COSTS)
    if df.empty:
        st.info("No storage usage data available.")
        return
    df['AVG_STORAGE_TB'] = pd.to_numeric(df['AVG_STORAGE_TB'], errors='coerce').fillna(0)
    df_sorted = df.sort_values('MONTH')
    fig = go.Figure(data=[go.Bar(
        x=df_sorted['MONTH'], y=df_sorted['AVG_STORAGE_TB'],
        marker_color=_CA,
        text=[f"{v:,.4f}" for v in df_sorted['AVG_STORAGE_TB']], textposition='outside'
    )])
    fig.update_layout(height=350, margin=dict(t=10, b=40, l=50, r=20),
                      xaxis_title="", yaxis_title="AVG_STORAGE_TB")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_budget_mtd():
    df = _cached_sql("fc_budget_mtd", _SQL_BUDGET_MTD)
    if df.empty:
        st.info("No budget data available.")
        return
    row = df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Budget Limit", f"{float(row.get('BUDGET_LIMIT_CREDITS', 0)):,.0f} credits")
    with c2:
        st.metric("Current Spend", f"{float(row.get('CURRENT_SPEND_CREDITS', 0)):,.2f} credits")
    with c3:
        st.metric("Utilization", f"{float(row.get('UTILIZATION_PERCENT', 0)):,.2f}%")
    with c4:
        proj = float(row.get('PROJECTED_MONTH_END_CREDITS', 0))
        st.metric("Projected Month End", f"{proj:,.2f} cre...")
    st.dataframe(df, use_container_width=True)


def _render_budget_inventory():
    df = _cached_sql("fc_budget_inventory", _SQL_BUDGET_INVENTORY)
    if df.empty:
        st.info("No budgets configured.")
        return
    total = len(df)
    root = len(df[df['BUDGET_NAME'] == 'ACCOUNT_ROOT_BUDGET'])
    custom = total - root
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Budgets", total)
    with c2:
        st.metric("Root Budgets", root)
    with c3:
        st.metric("Custom Budgets", custom)
    st.dataframe(df, use_container_width=True)

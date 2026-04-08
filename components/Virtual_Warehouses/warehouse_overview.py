import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.config.design_tokens import (
    BRAND_PRIMARY, BRAND_PRIMARY_DARK, BRAND_SECONDARY, BRAND_ACCENT,
    CHART_SERIES, CHART_EXTENDED,
)
from .scaling_management import comp_scaling_management
from .performance_monitoring import comp_performance_monitoring

PALETTE = CHART_SERIES + CHART_EXTENDED

_SIZE_ORDER = [
    'X-Small', 'Small', 'Medium', 'Large', 'X-Large',
    '2X-Large', '3X-Large', '4X-Large', '5X-Large', '6X-Large', 'Adaptive',
]

_WH_SIZE_DIST_SQL = """
SELECT WAREHOUSE_SIZE, COUNT(*) AS WAREHOUSE_COUNT
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES
WHERE DELETED IS NULL
GROUP BY WAREHOUSE_SIZE
ORDER BY WAREHOUSE_COUNT DESC
"""

_WH_CONFIG_DETAILS_SQL = """
SELECT WAREHOUSE_NAME, WAREHOUSE_TYPE, WAREHOUSE_SIZE AS SIZE,
       MIN_CLUSTER_COUNT, MAX_CLUSTER_COUNT, SCALING_POLICY, AUTO_SUSPEND
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES
WHERE DELETED IS NULL
ORDER BY WAREHOUSE_NAME
"""

_WH_HEATMAP_SQL = """
WITH top_wh AS (
    SELECT WAREHOUSE_NAME, SUM(CREDITS_USED_COMPUTE) AS TOTAL_CREDITS
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY WAREHOUSE_NAME
    HAVING TOTAL_CREDITS >= 1
    ORDER BY TOTAL_CREDITS DESC
    LIMIT 20
),
wh_load AS (
    SELECT
        HOUR(DATE_TRUNC('hour', wlh.START_TIME)) AS HOUR_OF_DAY,
        wlh.WAREHOUSE_NAME,
        ROUND(AVG(wlh.AVG_RUNNING), 2) AS AVG_QUERY_LOAD
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY wlh
    INNER JOIN top_wh tw ON wlh.WAREHOUSE_NAME = tw.WAREHOUSE_NAME
    WHERE wlh.START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY ALL
)
SELECT tw.WAREHOUSE_NAME, ROUND(tw.TOTAL_CREDITS, 0) AS TOTAL_CREDITS,
       wl.HOUR_OF_DAY, wl.AVG_QUERY_LOAD
FROM top_wh tw
LEFT JOIN wh_load wl ON tw.WAREHOUSE_NAME = wl.WAREHOUSE_NAME
ORDER BY tw.TOTAL_CREDITS DESC, wl.HOUR_OF_DAY
"""

_WH_CREDIT_TS_SQL = """
WITH top_wh AS (
    SELECT WAREHOUSE_NAME, SUM(CREDITS_USED_COMPUTE) AS TOTAL_CREDITS
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY WAREHOUSE_NAME
    ORDER BY TOTAL_CREDITS DESC
    LIMIT 10
)
SELECT DATE_TRUNC('day', wmh.START_TIME) AS START_TIME,
       wmh.WAREHOUSE_NAME,
       SUM(wmh.CREDITS_USED_COMPUTE) AS COMPUTE_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY wmh
INNER JOIN top_wh tw ON wmh.WAREHOUSE_NAME = tw.WAREHOUSE_NAME
WHERE wmh.START_TIME >= DATEADD('day', -365, CURRENT_TIMESTAMP())
  AND wmh.CREDITS_USED_COMPUTE > 0
GROUP BY ALL
ORDER BY START_TIME, wmh.WAREHOUSE_NAME
"""

_WH_IDLE_SQL = """
SELECT l.WAREHOUSE_NAME,
       COUNT(*) AS INTERVAL_COUNT,
       SUM(CASE WHEN l.AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) AS IDLE_INTERVALS,
       ROUND(SUM(CASE WHEN l.AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS PCT_TIME_IDLE,
       ROUND(AVG(l.AVG_RUNNING), 2) AS AVG_RUNNING_THREADS,
       ROUND(COUNT(*) * 5.0 / 60.0, 2) AS EST_UPTIME_HOURS,
       ROUND(SUM(CASE WHEN l.AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) * 5.0 / 60.0, 2) AS EST_IDLE_HOURS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY l
WHERE l.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND l.WAREHOUSE_NAME IS NOT NULL
GROUP BY l.WAREHOUSE_NAME
HAVING EST_UPTIME_HOURS > 1
ORDER BY PCT_TIME_IDLE DESC
"""

_WH_OVERSIZING_SQL = """
WITH node_mapping AS (
    SELECT 'X-Small' AS size, 1 AS nodes UNION ALL
    SELECT 'Small', 2 UNION ALL SELECT 'Medium', 4 UNION ALL
    SELECT 'Large', 8 UNION ALL SELECT 'X-Large', 16 UNION ALL
    SELECT '2X-Large', 32 UNION ALL SELECT '3X-Large', 64 UNION ALL
    SELECT '4X-Large', 128 UNION ALL SELECT '5X-Large', 256 UNION ALL
    SELECT '6X-Large', 512
)
SELECT q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE,
       COUNT(*) AS TOTAL_QUERIES,
       COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END) AS OVERSIZED_QUERIES,
       ROUND(COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS PCT_OVERSIZED,
       CASE
           WHEN ROUND(COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) >= 80 THEN 'CRITICAL'
           WHEN ROUND(COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) >= 50 THEN 'HIGH'
           WHEN ROUND(COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) >= 25 THEN 'MODERATE'
           ELSE 'LOW'
       END AS SEVERITY
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
INNER JOIN node_mapping n ON q.WAREHOUSE_SIZE = n.size
WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND q.WAREHOUSE_SIZE NOT IN ('X-Small', 'Small')
  AND q.PARTITIONS_SCANNED > 0
  AND q.WAREHOUSE_NAME IS NOT NULL
GROUP BY q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE
HAVING TOTAL_QUERIES > 0
ORDER BY PCT_OVERSIZED DESC
"""

_WH_SCALING_EFFICIENCY_SQL = """
WITH node_mapping AS (
    SELECT 'X-Small' AS size, 1 AS nodes, 1 AS credits_per_hour UNION ALL
    SELECT 'Small', 2, 2 UNION ALL SELECT 'Medium', 4, 4 UNION ALL
    SELECT 'Large', 8, 8 UNION ALL SELECT 'X-Large', 16, 16 UNION ALL
    SELECT '2X-Large', 32, 32 UNION ALL SELECT '3X-Large', 64, 64 UNION ALL
    SELECT '4X-Large', 128, 128 UNION ALL SELECT '5X-Large', 256, 256 UNION ALL
    SELECT '6X-Large', 512, 512
),
query_efficiency AS (
    SELECT q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE, n.nodes, n.credits_per_hour,
        COUNT(*) AS total_queries,
        SUM(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 ELSE 0 END) AS undersized_data_queries,
        AVG(q.PARTITIONS_SCANNED) AS avg_partitions_scanned
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    INNER JOIN node_mapping n ON q.WAREHOUSE_SIZE = n.size
    WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND q.PARTITIONS_SCANNED > 0 AND q.WAREHOUSE_NAME IS NOT NULL
    GROUP BY 1, 2, 3, 4
),
idle_efficiency AS (
    SELECT WAREHOUSE_NAME,
        COUNT(*) AS total_intervals,
        SUM(CASE WHEN AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) AS idle_intervals
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
    WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND WAREHOUSE_NAME IS NOT NULL
    GROUP BY WAREHOUSE_NAME
)
SELECT qe.WAREHOUSE_NAME, qe.WAREHOUSE_SIZE, qe.nodes AS NODE_COUNT, qe.credits_per_hour AS CREDITS_PER_HOUR,
    qe.total_queries AS TOTAL_QUERIES, ROUND(qe.avg_partitions_scanned, 0) AS AVG_PARTITIONS_SCANNED,
    ROUND(qe.undersized_data_queries * 100.0 / NULLIF(qe.total_queries, 0), 1) AS PCT_OVERSIZED_FOR_DATA,
    ROUND(ie.idle_intervals * 100.0 / NULLIF(ie.total_intervals, 0), 1) AS PCT_IDLE_TIME,
    CASE
        WHEN qe.undersized_data_queries*100.0/NULLIF(qe.total_queries,0) >= 50
             AND ie.idle_intervals*100.0/NULLIF(ie.total_intervals,0) >= 50
        THEN 'CRITICAL - Downsize + Reduce Auto-Suspend'
        WHEN qe.undersized_data_queries*100.0/NULLIF(qe.total_queries,0) >= 50
        THEN 'HIGH - Downsize Candidate'
        WHEN ie.idle_intervals*100.0/NULLIF(ie.total_intervals,0) >= 50
        THEN 'HIGH - Reduce Auto-Suspend'
        WHEN qe.undersized_data_queries*100.0/NULLIF(qe.total_queries,0) >= 25
             OR ie.idle_intervals*100.0/NULLIF(ie.total_intervals,0) >= 25
        THEN 'MODERATE - Review Configuration'
        ELSE 'OK - Well Configured'
    END AS OVERALL_RECOMMENDATION
FROM query_efficiency qe
LEFT JOIN idle_efficiency ie ON qe.WAREHOUSE_NAME = ie.WAREHOUSE_NAME
ORDER BY PCT_OVERSIZED_FOR_DATA DESC NULLS LAST, PCT_IDLE_TIME DESC NULLS LAST
"""

_WH_WORKLOAD_SQL = """
SELECT WAREHOUSE_NAME, WAREHOUSE_SIZE,
       COUNT(*) AS TOTAL_QUERIES,
       SUM(CASE WHEN BYTES_SCANNED < 104857600 THEN 1 ELSE 0 END) AS TINY_UNDER_100MB,
       SUM(CASE WHEN BYTES_SCANNED >= 104857600 AND BYTES_SCANNED < 1073741824 THEN 1 ELSE 0 END) AS SMALL_100MB_1GB,
       SUM(CASE WHEN BYTES_SCANNED >= 1073741824 AND BYTES_SCANNED < 107374182400 THEN 1 ELSE 0 END) AS LARGE_1GB_100GB,
       SUM(CASE WHEN BYTES_SCANNED >= 107374182400 THEN 1 ELSE 0 END) AS MASSIVE_OVER_100GB,
       ROUND(SUM(CASE WHEN BYTES_SCANNED < 104857600 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS TINY_QUERY_PCT
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_SIZE IS NOT NULL AND WAREHOUSE_NAME IS NOT NULL
GROUP BY WAREHOUSE_NAME, WAREHOUSE_SIZE
ORDER BY TOTAL_QUERIES DESC
LIMIT 25
"""

_WH_DATA_SKEW_SQL = """
WITH spill_stats AS (
    SELECT WAREHOUSE_NAME,
        COUNT(*) AS QUERY_COUNT,
        ROUND(SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) / POW(1024, 3), 3) AS TOTAL_REMOTE_SPILL_GB,
        ROUND(SUM(BYTES_SPILLED_TO_LOCAL_STORAGE) / POW(1024, 3), 3) AS TOTAL_LOCAL_SPILL_GB,
        ROUND((SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) + SUM(BYTES_SPILLED_TO_LOCAL_STORAGE)) / POW(1024, 3), 3) AS TOTAL_SPILL_GB,
        MAX(CASE
            WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 'CRITICAL'
            WHEN BYTES_SPILLED_TO_LOCAL_STORAGE / NULLIF(BYTES_SCANNED, 0) > 1 THEN 'HIGH'
            ELSE 'MODERATE'
        END) AS WORST_SEVERITY
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND (BYTES_SPILLED_TO_LOCAL_STORAGE > 0 OR BYTES_SPILLED_TO_REMOTE_STORAGE > 0)
      AND WAREHOUSE_NAME IS NOT NULL
    GROUP BY WAREHOUSE_NAME
)
SELECT WAREHOUSE_NAME, QUERY_COUNT, TOTAL_REMOTE_SPILL_GB, TOTAL_LOCAL_SPILL_GB, TOTAL_SPILL_GB, WORST_SEVERITY
FROM spill_stats
ORDER BY TOTAL_SPILL_GB DESC
"""

_WH_LOAD_DISTRIBUTION_SQL = """
SELECT USER_NAME, ROLE_NAME, WAREHOUSE_NAME,
    COUNT(*) AS QUERY_COUNT,
    ROUND(SUM(TOTAL_ELAPSED_TIME) / 3600000.0, 2) AS TOTAL_EXECUTION_HOURS,
    ROUND(AVG(TOTAL_ELAPSED_TIME) / 1000.0, 2) AS AVG_DURATION_SEC,
    ROUND(AVG(BYTES_SCANNED) / POW(1024, 2), 0) AS AVG_MB_SCANNED,
    ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) AS PCT_OF_TOTAL_QUERIES,
    ROUND(SUM(TOTAL_ELAPSED_TIME) * 100.0 / NULLIF(SUM(SUM(TOTAL_ELAPSED_TIME)) OVER(), 0), 1) AS PCT_OF_TOTAL_RUNTIME
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_NAME IS NOT NULL
GROUP BY USER_NAME, ROLE_NAME, WAREHOUSE_NAME
ORDER BY QUERY_COUNT DESC
LIMIT 20
"""

_WH_POOR_PRUNING_SQL = """
SELECT QUERY_ID, USER_NAME, WAREHOUSE_NAME,
    PARTITIONS_SCANNED, PARTITIONS_TOTAL,
    ROUND(PARTITIONS_SCANNED * 100.0 / NULLIF(PARTITIONS_TOTAL, 0), 1) AS PCT_TABLE_SCANNED,
    ROUND(BYTES_SCANNED / POWER(1024, 3), 2) AS SCANNED_GB,
    ROUND(TOTAL_ELAPSED_TIME / 1000.0, 1) AS DURATION_SEC,
    CASE
        WHEN PARTITIONS_SCANNED = PARTITIONS_TOTAL THEN 'FULL_TABLE_SCAN'
        WHEN (PARTITIONS_SCANNED * 1.0 / NULLIF(PARTITIONS_TOTAL, 0)) > 0.95 THEN 'NEAR_FULL_SCAN'
        ELSE 'PARTIAL_SCAN_90+'
    END AS SCAN_TYPE,
    LEFT(QUERY_TEXT, 100) AS QUERY_PREVIEW
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_DATE)
  AND PARTITIONS_TOTAL > 1000
  AND PARTITIONS_SCANNED > PARTITIONS_TOTAL * 0.9
ORDER BY SCANNED_GB DESC
LIMIT 20
"""

_WH_ACTIVITY_SUMMARY_SQL = """
SELECT WAREHOUSE_NAME,
    COUNT(DISTINCT DATE_TRUNC('hour', START_TIME)) AS ACTIVE_HOURS,
    COUNT(*) AS TOTAL_QUERIES,
    ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT DATE_TRUNC('hour', START_TIME)), 0), 1) AS QUERIES_PER_ACTIVE_HOUR,
    ROUND(SUM(TOTAL_ELAPSED_TIME) / 3600000.0, 2) AS TOTAL_EXECUTION_HOURS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_NAME IS NOT NULL
GROUP BY WAREHOUSE_NAME
ORDER BY TOTAL_QUERIES DESC
LIMIT 25
"""

_WH_FLEET_SQL = """
WITH active_fleet AS (
    SELECT
        q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE, q.WAREHOUSE_TYPE,
        CASE WHEN q.WAREHOUSE_TYPE = 'SNOWPARK-OPTIMIZED' THEN 'Memory Optimized' ELSE 'Standard' END AS RESOURCE_CONSTRAINT
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND q.WAREHOUSE_NAME IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY q.WAREHOUSE_NAME ORDER BY q.START_TIME DESC) = 1
)
SELECT WAREHOUSE_TYPE, RESOURCE_CONSTRAINT, WAREHOUSE_SIZE, COUNT(*) AS WAREHOUSE_COUNT
FROM active_fleet
GROUP BY 1, 2, 3
ORDER BY WAREHOUSE_TYPE, WAREHOUSE_SIZE
"""

_WH_CREDITS_SQL = """
WITH cost AS (
    SELECT m.WAREHOUSE_NAME, SUM(m.CREDITS_USED) AS TOTAL_CREDITS
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY m
    WHERE m.START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY m.WAREHOUSE_NAME
),
load_stats AS (
    SELECT l.WAREHOUSE_NAME,
           AVG(l.AVG_RUNNING) AS AVG_RUNNING_THREADS,
           AVG(l.AVG_QUEUED_LOAD) AS AVG_QUEUED_LOAD
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY l
    WHERE l.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
    GROUP BY l.WAREHOUSE_NAME
)
SELECT c.WAREHOUSE_NAME,
       ROUND(c.TOTAL_CREDITS, 2) AS CREDITS_30_DAY,
       ROUND(l.AVG_RUNNING_THREADS, 2) AS AVG_THREADS,
       ROUND(l.AVG_QUEUED_LOAD, 2) AS AVG_QUEUE,
       CASE
           WHEN l.AVG_QUEUED_LOAD > 0.1 THEN 'OVERUSED_QUEUING'
           WHEN l.AVG_RUNNING_THREADS < 0.5 THEN 'UNDERUTILIZED'
           ELSE 'HEALTHY'
       END AS HEALTH_STATUS,
       CASE
           WHEN l.AVG_QUEUED_LOAD > 0.1 THEN 'Consider scaling up or multi-cluster'
           WHEN l.AVG_RUNNING_THREADS < 0.5 THEN 'Consider downsizing or reducing auto-suspend'
           ELSE 'Configuration looks appropriate'
       END AS RECOMMENDATION
FROM cost c
INNER JOIN load_stats l ON c.WAREHOUSE_NAME = l.WAREHOUSE_NAME
ORDER BY c.TOTAL_CREDITS DESC
LIMIT 15
"""

_WH_HOURLY_ACTIVITY_SQL = """
WITH hourly_stats AS (
    SELECT HOUR(START_TIME) AS HOUR_OF_DAY,
        COUNT(*) AS QUERY_COUNT,
        AVG(TOTAL_ELAPSED_TIME) / 1000.0 AS avg_duration_sec,
        SUM(BYTES_SCANNED) / POW(1024, 4) AS total_tb_scanned
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND WAREHOUSE_NAME IS NOT NULL
    GROUP BY HOUR(START_TIME)
),
max_stats AS (SELECT MAX(QUERY_COUNT) AS max_count FROM hourly_stats)
SELECT h.HOUR_OF_DAY,
    h.QUERY_COUNT,
    ROUND(h.avg_duration_sec, 2) AS AVG_DURATION_SEC,
    ROUND(h.total_tb_scanned, 3) AS TOTAL_TB_SCANNED,
    ROUND(h.QUERY_COUNT * 100.0 / NULLIF(m.max_count, 0), 1) AS PCT_OF_PEAK,
    CASE
        WHEN h.QUERY_COUNT >= m.max_count * 0.8 THEN 'PEAK'
        WHEN h.QUERY_COUNT >= m.max_count * 0.5 THEN 'HIGH'
        WHEN h.QUERY_COUNT >= m.max_count * 0.2 THEN 'MODERATE'
        ELSE 'LOW'
    END AS ACTIVITY_LEVEL
FROM hourly_stats h CROSS JOIN max_stats m
ORDER BY h.HOUR_OF_DAY
"""

_WH_CONSTRAINT_SQL = """
WITH constraint_stats AS (
    SELECT WAREHOUSE_NAME,
        COUNT(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 END) AS REMOTE_SPILLS,
        COUNT(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 END) AS LOCAL_SPILLS,
        ROUND(SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) / POW(1024, 3), 2) AS TOTAL_REMOTE_SPILL_GB,
        ROUND(SUM(BYTES_SPILLED_TO_LOCAL_STORAGE) / POW(1024, 3), 2) AS TOTAL_LOCAL_SPILL_GB,
        COUNT(CASE WHEN ERROR_CODE = '100188' THEN 1 END) AS STATEMENT_TIMEOUTS
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND WAREHOUSE_NAME IS NOT NULL
    GROUP BY WAREHOUSE_NAME
)
SELECT WAREHOUSE_NAME, REMOTE_SPILLS, LOCAL_SPILLS,
    TOTAL_REMOTE_SPILL_GB, TOTAL_LOCAL_SPILL_GB, STATEMENT_TIMEOUTS,
    CASE
        WHEN REMOTE_SPILLS > 0 THEN 'CRITICAL'
        WHEN LOCAL_SPILLS > 100 THEN 'HIGH'
        WHEN LOCAL_SPILLS > 0 THEN 'MODERATE'
        ELSE 'OK'
    END AS SPILL_SEVERITY
FROM constraint_stats
WHERE REMOTE_SPILLS > 0 OR LOCAL_SPILLS > 0 OR STATEMENT_TIMEOUTS > 0
ORDER BY REMOTE_SPILLS DESC, LOCAL_SPILLS DESC
"""

_WH_CONFIG_CHANGES_SQL = """
WITH change_stats AS (
    SELECT WAREHOUSE_NAME,
        COUNT(CASE WHEN EVENT_NAME = 'RESIZE_WAREHOUSE' THEN 1 END) AS RESIZE_EVENTS,
        COUNT(CASE WHEN EVENT_NAME = 'CONVERT_WAREHOUSE' THEN 1 END) AS CONVERSION_EVENTS,
        MAX(TIMESTAMP) AS LAST_EVENT_TIME
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY
    WHERE TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND WAREHOUSE_NAME IS NOT NULL
    GROUP BY WAREHOUSE_NAME
)
SELECT WAREHOUSE_NAME, RESIZE_EVENTS, CONVERSION_EVENTS, LAST_EVENT_TIME,
    CASE
        WHEN RESIZE_EVENTS > 10 THEN 'FREQUENT_CHANGES'
        WHEN RESIZE_EVENTS > 0 THEN 'OCCASIONAL_CHANGES'
        ELSE 'STABLE'
    END AS CHANGE_FREQUENCY
FROM change_stats
WHERE RESIZE_EVENTS > 0 OR CONVERSION_EVENTS > 0
ORDER BY RESIZE_EVENTS DESC
"""

_WH_QAS_ELIGIBLE_SQL = """
SELECT WAREHOUSE_NAME, QUERY_ID,
    ROUND(ELIGIBLE_QUERY_ACCELERATION_TIME, 2) AS EST_QAS_TIME_SAVED_SEC,
    UPPER_LIMIT_SCALE_FACTOR AS SUGGESTED_SCALE_FACTOR,
    CASE
        WHEN ELIGIBLE_QUERY_ACCELERATION_TIME > 60 THEN 'HIGH_IMPACT'
        WHEN ELIGIBLE_QUERY_ACCELERATION_TIME > 10 THEN 'MODERATE_IMPACT'
        ELSE 'LOW_IMPACT'
    END AS IMPACT_LEVEL
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_ELIGIBLE
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_NAME IS NOT NULL
ORDER BY ELIGIBLE_QUERY_ACCELERATION_TIME DESC
LIMIT 10
"""

_WH_QAS_USAGE_SQL = """
SELECT WAREHOUSE_NAME,
    ROUND(SUM(CREDITS_USED), 4) AS QAS_CREDITS_USED,
    SUM(DATEDIFF('second', START_TIME, END_TIME)) AS TOTAL_ACCELERATION_SEC,
    COUNT(*) AS ACCELERATION_EVENTS,
    ROUND(AVG(CREDITS_USED), 6) AS AVG_CREDITS_PER_EVENT,
    CASE
        WHEN SUM(CREDITS_USED) > 10 THEN 'HIGH_QAS_USAGE'
        WHEN SUM(CREDITS_USED) > 1 THEN 'MODERATE_QAS_USAGE'
        ELSE 'LOW_QAS_USAGE'
    END AS USAGE_TIER
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_HISTORY
WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND WAREHOUSE_NAME IS NOT NULL
GROUP BY WAREHOUSE_NAME
ORDER BY QAS_CREDITS_USED DESC
"""

_ALL_WH_QUERIES = {
    "wh_size_dist_data": _WH_SIZE_DIST_SQL,
    "wh_config_details": _WH_CONFIG_DETAILS_SQL,
    "wh_heatmap_data": _WH_HEATMAP_SQL,
    "wh_credit_ts_data": _WH_CREDIT_TS_SQL,
    "wh_idle_data": _WH_IDLE_SQL,
    "wh_oversizing_data": _WH_OVERSIZING_SQL,
    "wh_scaling_efficiency": _WH_SCALING_EFFICIENCY_SQL,
    "wh_workload_data": _WH_WORKLOAD_SQL,
    "wh_data_skew": _WH_DATA_SKEW_SQL,
    "wh_load_distribution": _WH_LOAD_DISTRIBUTION_SQL,
    "wh_poor_pruning": _WH_POOR_PRUNING_SQL,
    "wh_activity_summary": _WH_ACTIVITY_SUMMARY_SQL,
    "wh_fleet_data": _WH_FLEET_SQL,
    "wh_credits_health": _WH_CREDITS_SQL,
    "wh_hourly_activity": _WH_HOURLY_ACTIVITY_SQL,
    "wh_constraint_data": _WH_CONSTRAINT_SQL,
    "wh_config_changes": _WH_CONFIG_CHANGES_SQL,
    "wh_qas_eligible": _WH_QAS_ELIGIBLE_SQL,
    "wh_qas_usage": _WH_QAS_USAGE_SQL,
}


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_wh_queries(progress_bar=None, status_text=None):
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_WH_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    total = len(needed)
    completed = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_run_query_thread, session, k, sql): k for k, sql in needed.items()}
        for future in as_completed(futures):
            key, df, err = future.result()
            st.session_state[key] = df
            completed += 1
            if progress_bar is not None:
                progress_bar.progress(completed / total)
            if status_text is not None:
                status_text.text(f"Loading data... ({completed}/{total} queries)")


def comp_warehouse_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in _ALL_WH_QUERIES)
        if not all_cached:
            status_ph.markdown(
                '<p style="color:#003D73;font-weight:600;">Loading Virtual Warehouses data...</p>',
                unsafe_allow_html=True)
            pb = progress_ph.progress(0)
            _prefetch_all_wh_queries(progress_bar=pb, status_text=status_ph)
            progress_ph.empty()
            status_ph.empty()

        sub_tabs = st.tabs(["Overview", "Scaling Management", "Performance Monitoring", "Fleet & Query Analysis"])

        with sub_tabs[0]:
            _render_overview()
        with sub_tabs[1]:
            comp_scaling_management()
        with sub_tabs[2]:
            comp_performance_monitoring()
        with sub_tabs[3]:
            _render_fleet_query()

    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
            f'Error loading Warehouses Overview: {e}</div>',
            unsafe_allow_html=True)


def _render_overview():
    size_df = st.session_state.get("wh_size_dist_data", pd.DataFrame())

    total_wh = 0
    size_map = {}
    if not size_df.empty:
        size_df.columns = [c.upper() for c in size_df.columns]
        if 'WAREHOUSE_COUNT' in size_df.columns:
            size_df['WAREHOUSE_COUNT'] = pd.to_numeric(size_df['WAREHOUSE_COUNT'], errors='coerce').fillna(0)
            total_wh = int(size_df['WAREHOUSE_COUNT'].sum())
            size_map = dict(zip(size_df['WAREHOUSE_SIZE'], size_df['WAREHOUSE_COUNT'].astype(int)))

    col_left, col_right = st.columns([1, 1])

    with col_left:
        size_grid_rows = [
            ['X-Small', 'Small', 'Medium'],
            ['Large', 'X-Large', '2X-Large'],
            ['3X-Large', '4X-Large', '5X-Large'],
            ['6X-Large', 'Adaptive', ''],
        ]
        grid_html = ""
        for row in size_grid_rows:
            grid_html += '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:8px;">'
            for sz in row:
                if not sz:
                    grid_html += '<div></div>'
                    continue
                cnt = size_map.get(sz, 0)
                color = BRAND_SECONDARY if cnt > 0 else BRAND_PRIMARY
                label = sz.upper().replace('-', 'X-').replace('X-LARGE', 'X-LARGE')
                label_map = {
                    'X-SMALL': 'XSMALL', 'SMALL': 'SMALL', 'MEDIUM': 'MEDIUM',
                    'LARGE': 'LARGE', 'X-LARGE': 'X-LARGE', '2X-LARGE': '2X-LARGE',
                    '3X-LARGE': '3X-LARGE', '4X-LARGE': '4X-LARGE', '5X-LARGE': '5X-LARGE',
                    '6X-LARGE': '6X-LARGE', 'ADAPTIVE': 'ADAPTIVE',
                }
                disp = sz.upper().replace('-', 'X-')
                lbl = label_map.get(sz.upper(), sz.upper())
                grid_html += (
                    f'<div style="text-align:center;">'
                    f'<div style="font-size:11px;color:#666;font-weight:600;">{sz.upper()}</div>'
                    f'<div style="font-size:28px;font-weight:700;color:{color};">{cnt}</div>'
                    f'</div>'
                )
            grid_html += '</div>'

        st.markdown(
            f'<div style="border:1px solid #e0e0e0;border-radius:8px;padding:20px;background:#fff;'
            f'box-shadow:0 2px 6px rgba(22,63,89,0.08);">'
            f'<div style="font-size:22px;font-weight:700;color:#003D73;margin-bottom:16px;">'
            f'Total Virtual Warehouses: {total_wh}</div>'
            f'{grid_html}'
            f'</div>',
            unsafe_allow_html=True)

    with col_right:
        st.markdown("**Warehouse Distribution by Size**")
        if not size_df.empty:
            sizes = [s for s in _SIZE_ORDER if s in size_map]
            counts = [size_map.get(s, 0) for s in _SIZE_ORDER]
            colors = [PALETTE[i % len(PALETTE)] for i in range(len(_SIZE_ORDER))]
            fig = go.Figure(go.Bar(
                x=[s.upper() for s in _SIZE_ORDER],
                y=counts,
                marker_color=colors,
                text=counts,
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>',
            ))
            fig.update_layout(
                height=340,
                margin=dict(t=10, b=60, l=40, r=20),
                yaxis_title='Number of Warehouses',
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No warehouse size data available.")

    with st.expander("Warehouse Configuration Details", expanded=True):
        cfg_df = st.session_state.get("wh_config_details", pd.DataFrame())
        if cfg_df.empty:
            st.info("No warehouse configuration data available.")
        else:
            cfg_df.columns = [c.upper() for c in cfg_df.columns]
            st.dataframe(cfg_df, use_container_width=True)

    with st.expander("Warehouse Load Heatmap", expanded=True):
        _render_load_heatmap()

    with st.expander("Credit Usage Analysis", expanded=True):
        _render_credit_usage_analysis()


def _render_load_heatmap():
    df = st.session_state.get("wh_heatmap_data", pd.DataFrame())
    if df.empty:
        st.info("No heatmap data available for the last 30 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['AVG_QUERY_LOAD'] = pd.to_numeric(df['AVG_QUERY_LOAD'], errors='coerce')
    df['HOUR_OF_DAY'] = pd.to_numeric(df['HOUR_OF_DAY'], errors='coerce')
    df['TOTAL_CREDITS'] = pd.to_numeric(df['TOTAL_CREDITS'], errors='coerce').fillna(0)

    credits_per_wh = df.drop_duplicates('WAREHOUSE_NAME')[['WAREHOUSE_NAME', 'TOTAL_CREDITS']].set_index('WAREHOUSE_NAME')['TOTAL_CREDITS'].to_dict()

    pivot = df.pivot_table(index='WAREHOUSE_NAME', columns='HOUR_OF_DAY', values='AVG_QUERY_LOAD', aggfunc='mean')
    pivot = pivot.reindex(columns=range(24))
    pivot = pivot.reindex([w for w in sorted(credits_per_wh, key=lambda x: -credits_per_wh[x]) if w in pivot.index])

    credits_col = pd.Series({w: credits_per_wh.get(w, 0) for w in pivot.index}, name='CREDITS')
    display_df = pd.concat([credits_col, pivot], axis=1)

    max_val = float(pivot.max().max()) if not pivot.empty else 1.0
    if max_val == 0:
        max_val = 1.0

    def color_cell(val):
        if pd.isna(val) or val == 0:
            return 'background-color: #f8f9fa; color: #888;'
        ratio = min(val / max_val, 1.0)
        if ratio > 0.6:
            r, g, b = 232, 162, 41
        elif ratio > 0.2:
            r, g, b = 41, 181, 232
        else:
            r, g, b = 117, 194, 216
        alpha = 0.3 + ratio * 0.7
        return f'background-color: rgba({r},{g},{b},{alpha:.2f}); color: #262730;'

    def format_val(val):
        if pd.isna(val):
            return 'None'
        return f'{val:.2f}'

    hour_cols = [c for c in display_df.columns if isinstance(c, (int, float))]
    styled = display_df.style
    styled = styled.format(lambda v: format_val(v) if isinstance(v, float) and not pd.isna(v) else ('None' if pd.isna(v) else str(int(v) if isinstance(v, float) and v == int(v) else v)), subset=hour_cols)
    styled = styled.format(lambda v: f'{int(v):,}' if not pd.isna(v) else '0', subset=['CREDITS'])
    styled = styled.map(color_cell, subset=hour_cols)

    st.dataframe(styled, use_container_width=True)


def _render_credit_usage_analysis():
    st.markdown("**Credit Usage by Warehouse Over Time**")
    ts_df = st.session_state.get("wh_credit_ts_data", pd.DataFrame())
    if ts_df.empty:
        st.info("No credit usage data available.")
    else:
        ts_df.columns = [c.upper() for c in ts_df.columns]
        ts_df['COMPUTE_CREDITS'] = pd.to_numeric(ts_df['COMPUTE_CREDITS'], errors='coerce').fillna(0)
        warehouses = ts_df['WAREHOUSE_NAME'].unique().tolist()
        fig = go.Figure()
        for i, wh in enumerate(warehouses):
            wh_data = ts_df[ts_df['WAREHOUSE_NAME'] == wh].sort_values('START_TIME')
            fig.add_trace(go.Scatter(
                x=wh_data['START_TIME'], y=wh_data['COMPUTE_CREDITS'],
                mode='lines', name=wh,
                line=dict(color=PALETTE[i % len(PALETTE)], width=1),
                stackgroup='one',
                hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Credits: %{y:.2f}<extra></extra>',
            ))
        fig.update_layout(
            height=380,
            margin=dict(t=10, b=40, l=50, r=20),
            xaxis_title='START_TIME',
            yaxis_title='COMPUTE_CREDITS',
            legend=dict(orientation='v', yanchor='top', y=1, xanchor='left', x=1.02, font=dict(size=10)),
            showlegend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Average Idle % by Warehouse**")
    idle_df = st.session_state.get("wh_idle_data", pd.DataFrame())
    if idle_df.empty:
        st.info("No idle data available.")
    else:
        idle_df.columns = [c.upper() for c in idle_df.columns]
        idle_df['PCT_TIME_IDLE'] = pd.to_numeric(idle_df['PCT_TIME_IDLE'], errors='coerce').fillna(0)
        idle_df = idle_df.sort_values('PCT_TIME_IDLE', ascending=False)
        fig = go.Figure(go.Bar(
            y=idle_df['WAREHOUSE_NAME'],
            x=idle_df['PCT_TIME_IDLE'],
            orientation='h',
            marker_color=BRAND_SECONDARY,
            text=[f'{v:.1f}' for v in idle_df['PCT_TIME_IDLE']],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Idle: %{x:.1f}%<extra></extra>',
        ))
        fig.update_layout(
            height=max(300, len(idle_df) * 28),
            margin=dict(t=10, b=40, l=200, r=80),
            xaxis_title='% Time Idle',
            showlegend=False,
        )
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)


def _render_fleet_query():
    with st.expander("Active Warehouse Fleet Distribution", expanded=True):
        st.markdown("Warehouse breakdown by type, resource constraint, and size over the last 7 days.")
        _render_fleet_distribution()

    with st.expander("Top 15 Warehouses by Credit Consumption & Health", expanded=True):
        st.markdown("Credits consumed with health diagnosis based on avg running threads and queue depth.")
        _render_top_credits_health()

    with st.expander("Hourly Query Activity Distribution (Peak Hours)", expanded=True):
        st.markdown("Query volume and average duration by hour of day to identify peak usage windows.")
        _render_hourly_activity()

    with st.expander("Resource Constraint Analysis (Spills & Timeouts)", expanded=True):
        st.markdown("Warehouses experiencing memory spills (local/remote) or statement timeouts.")
        _render_resource_constraints()

    with st.expander("Warehouse Configuration Change History", expanded=True):
        st.markdown("Resize and type conversion events — frequent changes may indicate auto-scaling should be enabled.")
        _render_config_changes()

    with st.expander("Query Acceleration Service (QAS) — Eligible Candidates", expanded=True):
        st.markdown("Top queries eligible for QAS acceleration with estimated time savings.")
        _render_qas_eligible()

    with st.expander("Query Acceleration Service (QAS) — Usage Summary", expanded=True):
        st.markdown("Credits consumed and acceleration duration by warehouse via QAS.")
        _render_qas_usage()


def _render_fleet_distribution():
    df = st.session_state.get("wh_fleet_data", pd.DataFrame())
    if df.empty:
        st.info("No fleet data found for the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['WAREHOUSE_COUNT'] = pd.to_numeric(df['WAREHOUSE_COUNT'], errors='coerce').fillna(0)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Fleet by Warehouse Type**")
        type_counts = df.groupby('WAREHOUSE_TYPE')['WAREHOUSE_COUNT'].sum().reset_index()
        fig_pie = go.Figure(go.Pie(
            labels=type_counts['WAREHOUSE_TYPE'],
            values=type_counts['WAREHOUSE_COUNT'],
            hole=0.0,
            marker_colors=[PALETTE[i % len(PALETTE)] for i in range(len(type_counts))],
            textinfo='percent',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<extra></extra>',
        ))
        fig_pie.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
                              legend=dict(orientation='v', x=1, y=0.5))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown("**Fleet by Resource Constraint**")
        rc_counts = df.groupby('RESOURCE_CONSTRAINT')['WAREHOUSE_COUNT'].sum().reset_index()
        fig_rc = go.Figure(go.Bar(
            y=rc_counts['RESOURCE_CONSTRAINT'],
            x=rc_counts['WAREHOUSE_COUNT'],
            orientation='h',
            marker_color=BRAND_SECONDARY,
            text=rc_counts['WAREHOUSE_COUNT'].astype(int),
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>',
        ))
        fig_rc.update_layout(
            height=280, margin=dict(t=10, b=10, l=120, r=60),
            xaxis_title='WAREHOUSE_COUNT', yaxis_title='RESOURCE_CONSTRAINT',
            showlegend=False,
        )
        st.plotly_chart(fig_rc, use_container_width=True)

    with col3:
        st.markdown("**Fleet by Warehouse Size**")
        sz_counts = df.groupby('WAREHOUSE_SIZE')['WAREHOUSE_COUNT'].sum().reset_index()
        sz_counts = sz_counts[sz_counts['WAREHOUSE_COUNT'] > 0]
        fig_sz = go.Figure(go.Bar(
            y=sz_counts['WAREHOUSE_SIZE'],
            x=sz_counts['WAREHOUSE_COUNT'],
            orientation='h',
            marker_color=BRAND_SECONDARY,
            text=sz_counts['WAREHOUSE_COUNT'].astype(int),
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>',
        ))
        fig_sz.update_layout(
            height=280, margin=dict(t=10, b=10, l=80, r=60),
            xaxis_title='WAREHOUSE_COUNT', yaxis_title='WAREHOUSE_SIZE',
            showlegend=False,
        )
        st.plotly_chart(fig_sz, use_container_width=True)

    st.dataframe(df[['WAREHOUSE_TYPE', 'RESOURCE_CONSTRAINT', 'WAREHOUSE_SIZE', 'WAREHOUSE_COUNT']],
                 use_container_width=True)


def _render_top_credits_health():
    df = st.session_state.get("wh_credits_health", pd.DataFrame())
    if df.empty:
        st.info("No credit consumption data found for the last 30 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['CREDITS_30_DAY'] = pd.to_numeric(df['CREDITS_30_DAY'], errors='coerce').fillna(0)

    _health_colors = {'HEALTHY': BRAND_SECONDARY, 'OVERUSED_QUEUING': BRAND_ACCENT, 'UNDERUTILIZED': '#75C2D8'}
    bar_colors = [_health_colors.get(h, BRAND_SECONDARY) for h in df['HEALTH_STATUS'].fillna('HEALTHY')]

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("**Credits by Warehouse (health colour-coded)**")
        fig = go.Figure(go.Bar(
            y=df['WAREHOUSE_NAME'],
            x=df['CREDITS_30_DAY'],
            orientation='h',
            marker_color=bar_colors,
            text=[f'{v:.1f}' for v in df['CREDITS_30_DAY']],
            textposition='outside',
            customdata=df['HEALTH_STATUS'],
            hovertemplate='<b>%{y}</b><br>Credits: %{x:.2f}<br>Health: %{customdata}<extra></extra>',
        ))
        fig.update_layout(
            height=max(320, len(df) * 32),
            margin=dict(t=10, b=40, l=200, r=80),
            xaxis_title='Credits',
            showlegend=False,
        )
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Health Distribution**")
        health_counts = df['HEALTH_STATUS'].value_counts().reset_index()
        health_counts.columns = ['HEALTH_STATUS', 'COUNT']
        pie_colors = [_health_colors.get(h, BRAND_SECONDARY) for h in health_counts['HEALTH_STATUS']]
        fig_pie = go.Figure(go.Pie(
            labels=health_counts['HEALTH_STATUS'],
            values=health_counts['COUNT'],
            marker_colors=pie_colors,
            textinfo='percent',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<extra></extra>',
        ))
        fig_pie.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    cols_show = [c for c in ['WAREHOUSE_NAME', 'CREDITS_30_DAY', 'AVG_THREADS', 'AVG_QUEUE', 'HEALTH_STATUS', 'RECOMMENDATION'] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True)


def _render_hourly_activity():
    df = st.session_state.get("wh_hourly_activity", pd.DataFrame())
    if df.empty:
        st.info("No hourly activity data found.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['QUERY_COUNT'] = pd.to_numeric(df['QUERY_COUNT'], errors='coerce').fillna(0)
    df['AVG_DURATION_SEC'] = pd.to_numeric(df['AVG_DURATION_SEC'], errors='coerce').fillna(0)
    df['TOTAL_TB_SCANNED'] = pd.to_numeric(df['TOTAL_TB_SCANNED'], errors='coerce').fillna(0)

    _act_colors = {'PEAK': '#11567F', 'HIGH': '#75C2D8', 'MODERATE': '#ADE8F4', 'LOW': '#CAF0F8'}
    bar_colors = [_act_colors.get(lvl, '#29B5E8') for lvl in df.get('ACTIVITY_LEVEL', pd.Series([''] * len(df)))]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Query Count by Hour of Day**")
        fig1 = go.Figure(go.Bar(
            x=df['HOUR_OF_DAY'], y=df['QUERY_COUNT'],
            marker_color=bar_colors,
            customdata=df.get('ACTIVITY_LEVEL', pd.Series([''] * len(df))),
            hovertemplate='Hour %{x}<br>Queries: %{y}<br>Level: %{customdata}<extra></extra>',
        ))
        fig1.update_layout(
            height=320, margin=dict(t=10, b=40, l=50, r=10),
            xaxis_title='Hour', yaxis_title='Queries',
            xaxis=dict(tickmode='linear', tick0=0, dtick=5),
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.markdown("**Avg Query Duration by Hour (seconds)**")
        fig2 = go.Figure(go.Scatter(
            x=df['HOUR_OF_DAY'], y=df['AVG_DURATION_SEC'],
            mode='lines+markers',
            line=dict(color=BRAND_ACCENT, width=2),
            marker=dict(color=BRAND_ACCENT, size=6),
            hovertemplate='Hour %{x}<br>Avg Duration: %{y:.2f}s<extra></extra>',
        ))
        fig2.update_layout(
            height=320, margin=dict(t=10, b=40, l=50, r=10),
            xaxis_title='Hour', yaxis_title='Avg Duration (s)',
            xaxis=dict(tickmode='linear', tick0=0, dtick=5),
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col3:
        st.markdown("**TB Scanned by Hour**")
        fig3 = go.Figure(go.Bar(
            x=df['HOUR_OF_DAY'], y=df['TOTAL_TB_SCANNED'],
            marker_color=BRAND_SECONDARY,
            hovertemplate='Hour %{x}<br>TB Scanned: %{y:.3f}<extra></extra>',
        ))
        fig3.update_layout(
            height=320, margin=dict(t=10, b=40, l=50, r=10),
            xaxis_title='Hour', yaxis_title='TB Scanned',
            xaxis=dict(tickmode='linear', tick0=0, dtick=5),
        )
        st.plotly_chart(fig3, use_container_width=True)

    cols_show = [c for c in ['HOUR_OF_DAY', 'QUERY_COUNT', 'AVG_DURATION_SEC', 'TOTAL_TB_SCANNED', 'PCT_OF_PEAK', 'ACTIVITY_LEVEL'] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True)


def _render_resource_constraints():
    df = st.session_state.get("wh_constraint_data", pd.DataFrame())
    if df.empty:
        st.success("No memory spills or statement timeouts detected in the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['REMOTE_SPILLS'] = pd.to_numeric(df['REMOTE_SPILLS'], errors='coerce').fillna(0)
    df['LOCAL_SPILLS'] = pd.to_numeric(df['LOCAL_SPILLS'], errors='coerce').fillna(0)

    _sev_colors = {'CRITICAL': '#11567F', 'HIGH': BRAND_ACCENT, 'MODERATE': '#75C2D8', 'OK': '#ADE8F4'}
    r_colors = [_sev_colors.get(s, '#75C2D8') for s in df.get('SPILL_SEVERITY', pd.Series(['MODERATE'] * len(df)))]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Remote Spills by Warehouse**")
        fig_r = go.Figure(go.Bar(
            y=df['WAREHOUSE_NAME'], x=df['REMOTE_SPILLS'],
            orientation='h',
            marker_color=r_colors,
            text=df['REMOTE_SPILLS'].astype(int),
            textposition='outside',
            customdata=df.get('SPILL_SEVERITY', pd.Series([''] * len(df))),
            hovertemplate='<b>%{y}</b><br>Remote Spills: %{x}<br>Severity: %{customdata}<extra></extra>',
        ))
        fig_r.update_layout(
            height=max(300, len(df) * 24),
            margin=dict(t=10, b=20, l=200, r=60),
            xaxis_title='Remote Spills',
            showlegend=False,
        )
        fig_r.update_yaxes(autorange='reversed')
        st.plotly_chart(fig_r, use_container_width=True)

    with col2:
        st.markdown("**Local Spills by Warehouse**")
        df_sorted = df.sort_values('LOCAL_SPILLS', ascending=True)
        fig_l = go.Figure(go.Bar(
            y=df_sorted['WAREHOUSE_NAME'], x=df_sorted['LOCAL_SPILLS'],
            orientation='h',
            marker_color=BRAND_SECONDARY,
            text=df_sorted['LOCAL_SPILLS'].astype(int),
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Local Spills: %{x}<extra></extra>',
        ))
        fig_l.update_layout(
            height=max(300, len(df_sorted) * 24),
            margin=dict(t=10, b=20, l=200, r=60),
            xaxis_title='Local Spills',
            showlegend=False,
        )
        fig_l.update_yaxes(autorange='reversed')
        st.plotly_chart(fig_l, use_container_width=True)

    cols_show = [c for c in ['WAREHOUSE_NAME', 'REMOTE_SPILLS', 'LOCAL_SPILLS', 'TOTAL_REMOTE_SPILL_GB', 'TOTAL_LOCAL_SPILL_GB', 'STATEMENT_TIMEOUTS'] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True)


def _render_config_changes():
    df = st.session_state.get("wh_config_changes", pd.DataFrame())
    if df.empty:
        st.success("✅ No warehouse configuration changes found.")
        return
    df.columns = [c.upper() for c in df.columns]
    cols_show = [c for c in ['WAREHOUSE_NAME', 'RESIZE_EVENTS', 'CONVERSION_EVENTS', 'LAST_EVENT_TIME', 'CHANGE_FREQUENCY'] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True)


def _render_qas_eligible():
    df = st.session_state.get("wh_qas_eligible", pd.DataFrame())
    if df.empty:
        st.info("No QAS-eligible queries found for the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['EST_QAS_TIME_SAVED_SEC'] = pd.to_numeric(df['EST_QAS_TIME_SAVED_SEC'], errors='coerce').fillna(0)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("**Estimated QAS Time Savings (sec)**")
        df_chart = df.copy()
        df_chart['LABEL'] = df_chart['QUERY_ID'].astype(str).str[:8] + ' @ ' + df_chart['WAREHOUSE_NAME']
        fig = go.Figure(go.Bar(
            y=df_chart['LABEL'],
            x=df_chart['EST_QAS_TIME_SAVED_SEC'],
            orientation='h',
            marker_color=BRAND_PRIMARY_DARK,
            text=[f'{v:.1f}' for v in df_chart['EST_QAS_TIME_SAVED_SEC']],
            textposition='outside',
            customdata=df_chart.get('IMPACT_LEVEL', pd.Series([''] * len(df_chart))),
            hovertemplate='<b>%{y}</b><br>Saved: %{x:.1f}s<br>Impact: %{customdata}<extra></extra>',
        ))
        fig.update_layout(
            height=max(280, len(df_chart) * 36),
            margin=dict(t=10, b=20, l=220, r=80),
            xaxis_title='Saved (sec)',
            showlegend=False,
        )
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        cols_show = [c for c in ['WAREHOUSE_NAME', 'QUERY_ID', 'EST_QAS_TIME_SAVED_SEC', 'SUGGESTED_SCALE_FACTOR', 'IMPACT_LEVEL'] if c in df.columns]
        st.dataframe(df[cols_show], use_container_width=True)


def _render_qas_usage():
    df = st.session_state.get("wh_qas_usage", pd.DataFrame())
    if df.empty:
        st.info("No QAS usage data found for the last 30 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['QAS_CREDITS_USED'] = pd.to_numeric(df['QAS_CREDITS_USED'], errors='coerce').fillna(0)
    df['ACCELERATION_EVENTS'] = pd.to_numeric(df['ACCELERATION_EVENTS'], errors='coerce').fillna(0)

    _usage_colors = {'HIGH_QAS_USAGE': BRAND_PRIMARY_DARK, 'MODERATE_QAS_USAGE': BRAND_SECONDARY, 'LOW_QAS_USAGE': '#75C2D8'}
    bar_colors = [_usage_colors.get(u, BRAND_PRIMARY_DARK) for u in df.get('USAGE_TIER', pd.Series(['HIGH_QAS_USAGE'] * len(df)))]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**QAS Credits by Warehouse**")
        fig1 = go.Figure(go.Bar(
            y=df['WAREHOUSE_NAME'],
            x=df['QAS_CREDITS_USED'],
            orientation='h',
            marker_color=bar_colors,
            text=[f'{v:.4f}' for v in df['QAS_CREDITS_USED']],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Credits: %{x:.4f}<extra></extra>',
        ))
        fig1.update_layout(
            height=max(280, len(df) * 36),
            margin=dict(t=10, b=20, l=200, r=80),
            xaxis_title='QAS Credits',
            showlegend=False,
        )
        fig1.update_yaxes(autorange='reversed')
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.markdown("**QAS Acceleration Events by Warehouse**")
        fig2 = go.Figure(go.Bar(
            y=df['WAREHOUSE_NAME'],
            x=df['ACCELERATION_EVENTS'],
            orientation='h',
            marker_color=bar_colors,
            text=df['ACCELERATION_EVENTS'].astype(int),
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Events: %{x}<extra></extra>',
        ))
        fig2.update_layout(
            height=max(280, len(df) * 36),
            margin=dict(t=10, b=20, l=200, r=80),
            xaxis_title='Acceleration Events',
            showlegend=False,
        )
        fig2.update_yaxes(autorange='reversed')
        st.plotly_chart(fig2, use_container_width=True)

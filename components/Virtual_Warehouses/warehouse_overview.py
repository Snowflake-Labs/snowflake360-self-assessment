# Copyright 2026 Snowflake, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.config.design_tokens import (
    BRAND_PRIMARY, BRAND_SECONDARY, BRAND_ACCENT, BRAND_PRIMARY_DARK,
    CHART_SERIES, CHART_EXTENDED,
)
from .scaling_management import comp_scaling_management
from .performance_monitoring import comp_performance_monitoring


_WH_FLEET_SQL = """
WITH active_fleet AS (
    SELECT
        q.WAREHOUSE_NAME,
        q.WAREHOUSE_SIZE,
        q.WAREHOUSE_TYPE,
        CASE
            WHEN q.WAREHOUSE_TYPE = 'SNOWPARK-OPTIMIZED' THEN 'Memory Optimized'
            ELSE 'Standard'
        END AS RESOURCE_CONSTRAINT
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND q.WAREHOUSE_NAME IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY q.WAREHOUSE_NAME ORDER BY q.START_TIME DESC) = 1
)
SELECT WAREHOUSE_NAME, WAREHOUSE_SIZE, WAREHOUSE_TYPE, RESOURCE_CONSTRAINT
FROM active_fleet
ORDER BY WAREHOUSE_NAME
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
       END AS HEALTH_STATUS
FROM cost c
INNER JOIN load_stats l ON c.WAREHOUSE_NAME = l.WAREHOUSE_NAME
ORDER BY c.TOTAL_CREDITS DESC
LIMIT 15
"""

_WH_HEATMAP_SQL = """
WITH top_wh AS (
    SELECT WAREHOUSE_NAME, SUM(CREDITS_USED_COMPUTE) AS TOTAL_CREDITS
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY WAREHOUSE_NAME
    HAVING TOTAL_CREDITS >= 1
    ORDER BY TOTAL_CREDITS DESC
    LIMIT 15
),
wh_load AS (
    SELECT
        HOUR(DATE_TRUNC('hour', wlh.START_TIME)) AS HOUR_OF_DAY,
        wlh.WAREHOUSE_NAME,
        ROUND(AVG(wlh.AVG_RUNNING), 4) AS AVG_QUERY_LOAD
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY wlh
    INNER JOIN top_wh tw ON wlh.WAREHOUSE_NAME = tw.WAREHOUSE_NAME
    WHERE wlh.START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY ALL
)
SELECT tw.WAREHOUSE_NAME, tw.TOTAL_CREDITS,
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
SELECT DATE_TRUNC('day', wmh.START_TIME) AS DAY,
       wmh.WAREHOUSE_NAME,
       SUM(wmh.CREDITS_USED_COMPUTE) AS COMPUTE_CREDITS,
       SUM(wmh.CREDITS_USED_COMPUTE - wmh.CREDITS_ATTRIBUTED_COMPUTE_QUERIES) AS IDLE_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY wmh
INNER JOIN top_wh tw ON wmh.WAREHOUSE_NAME = tw.WAREHOUSE_NAME
WHERE wmh.START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND wmh.CREDITS_USED_COMPUTE > 0
GROUP BY ALL
ORDER BY DAY, wmh.WAREHOUSE_NAME
"""

_WH_HOURLY_ACTIVITY_SQL = """
SELECT HOUR(START_TIME) AS HOUR_OF_DAY,
       COUNT(*) AS QUERY_COUNT,
       ROUND(AVG(TOTAL_ELAPSED_TIME) / 1000.0, 2) AS AVG_DURATION_SEC,
       ROUND(SUM(BYTES_SCANNED) / POW(1024, 4), 3) AS TOTAL_TB_SCANNED
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_NAME IS NOT NULL
GROUP BY HOUR(START_TIME)
ORDER BY HOUR_OF_DAY
"""

_WH_CONSTRAINT_SQL = """
SELECT WAREHOUSE_NAME,
       COUNT(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 END) AS REMOTE_SPILLS,
       COUNT(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 END) AS LOCAL_SPILLS,
       ROUND(SUM(BYTES_SPILLED_TO_REMOTE_STORAGE) / POW(1024, 3), 2) AS TOTAL_REMOTE_SPILL_GB,
       ROUND(SUM(BYTES_SPILLED_TO_LOCAL_STORAGE) / POW(1024, 3), 2) AS TOTAL_LOCAL_SPILL_GB,
       COUNT(CASE WHEN ERROR_CODE = '100188' THEN 1 END) AS STATEMENT_TIMEOUTS,
       CASE
           WHEN COUNT(CASE WHEN BYTES_SPILLED_TO_REMOTE_STORAGE > 0 THEN 1 END) > 0 THEN 'CRITICAL'
           WHEN COUNT(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 END) > 100 THEN 'HIGH'
           WHEN COUNT(CASE WHEN BYTES_SPILLED_TO_LOCAL_STORAGE > 0 THEN 1 END) > 0 THEN 'MODERATE'
           ELSE 'OK'
       END AS SPILL_SEVERITY
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND WAREHOUSE_NAME IS NOT NULL
GROUP BY WAREHOUSE_NAME
HAVING REMOTE_SPILLS > 0 OR LOCAL_SPILLS > 0
ORDER BY REMOTE_SPILLS DESC, LOCAL_SPILLS DESC
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
           WHEN ROUND(COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) >= 50 THEN 'HIGH'
           WHEN ROUND(COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) >= 20 THEN 'MODERATE'
           ELSE 'LOW'
       END AS SEVERITY
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
INNER JOIN node_mapping n ON q.WAREHOUSE_SIZE = n.size
WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND q.WAREHOUSE_SIZE NOT IN ('X-Small', 'Small')
  AND q.PARTITIONS_SCANNED > 0
GROUP BY q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE
HAVING TOTAL_QUERIES > 0
ORDER BY PCT_OVERSIZED DESC
"""

_WH_SCALING_EFFICIENCY_SQL = """
WITH node_mapping AS (
    SELECT 'X-Small' AS size, 1 AS nodes, 1 AS cph UNION ALL
    SELECT 'Small', 2, 2 UNION ALL SELECT 'Medium', 4, 4 UNION ALL
    SELECT 'Large', 8, 8 UNION ALL SELECT 'X-Large', 16, 16 UNION ALL
    SELECT '2X-Large', 32, 32 UNION ALL SELECT '3X-Large', 64, 64 UNION ALL
    SELECT '4X-Large', 128, 128 UNION ALL SELECT '5X-Large', 256, 256 UNION ALL
    SELECT '6X-Large', 512, 512
),
oversizing AS (
    SELECT q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE,
           COUNT(*) AS TOTAL_QUERIES,
           ROUND(COUNT(CASE WHEN q.PARTITIONS_SCANNED < n.nodes THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS PCT_OVERSIZED_FOR_DATA,
           n.nodes AS NODE_COUNT, n.cph AS CREDITS_PER_HOUR
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    INNER JOIN node_mapping n ON q.WAREHOUSE_SIZE = n.size
    WHERE q.START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND q.PARTITIONS_SCANNED > 0
    GROUP BY q.WAREHOUSE_NAME, q.WAREHOUSE_SIZE, n.nodes, n.cph
    HAVING TOTAL_QUERIES >= 10
),
idle AS (
    SELECT WAREHOUSE_NAME,
           ROUND(SUM(CASE WHEN AVG_RUNNING < 0.1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS PCT_IDLE_TIME
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
    WHERE START_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
    GROUP BY WAREHOUSE_NAME
)
SELECT
    COALESCE(o.WAREHOUSE_NAME, i.WAREHOUSE_NAME) AS WAREHOUSE_NAME,
    COALESCE(o.WAREHOUSE_SIZE, 'Unknown') AS WAREHOUSE_SIZE,
    COALESCE(o.NODE_COUNT, 0) AS NODE_COUNT,
    COALESCE(o.CREDITS_PER_HOUR, 0) AS CREDITS_PER_HOUR,
    COALESCE(o.TOTAL_QUERIES, 0) AS TOTAL_QUERIES,
    COALESCE(o.PCT_OVERSIZED_FOR_DATA, 0) AS PCT_OVERSIZED_FOR_DATA,
    COALESCE(i.PCT_IDLE_TIME, 0) AS PCT_IDLE_TIME,
    CASE
        WHEN COALESCE(o.PCT_OVERSIZED_FOR_DATA, 0) > 50 AND COALESCE(i.PCT_IDLE_TIME, 0) > 50 THEN 'CRITICAL - Downsize + Reduce Auto-Suspend'
        WHEN COALESCE(o.PCT_OVERSIZED_FOR_DATA, 0) > 50 THEN 'HIGH - Downsize Candidate'
        WHEN COALESCE(i.PCT_IDLE_TIME, 0) > 50 THEN 'HIGH - Reduce Auto-Suspend'
        WHEN COALESCE(o.PCT_OVERSIZED_FOR_DATA, 0) > 20 OR COALESCE(i.PCT_IDLE_TIME, 0) > 30 THEN 'MODERATE - Review Configuration'
        ELSE 'OK - Well Configured'
    END AS OVERALL_RECOMMENDATION
FROM oversizing o
FULL OUTER JOIN idle i ON o.WAREHOUSE_NAME = i.WAREHOUSE_NAME
ORDER BY PCT_OVERSIZED_FOR_DATA DESC, PCT_IDLE_TIME DESC
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
GROUP BY l.WAREHOUSE_NAME
HAVING EST_UPTIME_HOURS > 1
ORDER BY PCT_TIME_IDLE DESC
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
  AND WAREHOUSE_SIZE IS NOT NULL
  AND WAREHOUSE_NAME IS NOT NULL
GROUP BY WAREHOUSE_NAME, WAREHOUSE_SIZE
ORDER BY TOTAL_QUERIES DESC
LIMIT 20
"""

_WH_CONFIG_CHANGES_SQL = """
SELECT WAREHOUSE_NAME,
       COUNT(CASE WHEN EVENT_NAME = 'RESIZE_WAREHOUSE' THEN 1 END) AS RESIZE_EVENTS,
       COUNT(CASE WHEN EVENT_NAME = 'CONVERT_WAREHOUSE' THEN 1 END) AS CONVERSION_EVENTS,
       MAX(TIMESTAMP) AS LAST_EVENT_TIME
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY
WHERE TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY WAREHOUSE_NAME
HAVING RESIZE_EVENTS > 0 OR CONVERSION_EVENTS > 0
ORDER BY RESIZE_EVENTS DESC
"""

_WH_DATA_SKEW_SQL = """
SELECT
    warehouse_name AS WAREHOUSE_NAME,
    COUNT(*) AS QUERY_COUNT,
    ROUND(SUM(bytes_spilled_to_remote_storage) / POWER(1024, 3), 3) AS TOTAL_REMOTE_SPILL_GB,
    ROUND(SUM(bytes_spilled_to_local_storage) / POWER(1024, 3), 3) AS TOTAL_LOCAL_SPILL_GB,
    ROUND(SUM(bytes_spilled_to_local_storage + bytes_spilled_to_remote_storage) / POWER(1024, 3), 3) AS TOTAL_SPILL_GB,
    CASE
        WHEN SUM(bytes_spilled_to_remote_storage) > 1073741824 THEN 'CRITICAL'
        WHEN SUM(bytes_spilled_to_remote_storage) > 0 THEN 'HIGH'
        WHEN SUM(bytes_spilled_to_local_storage) > 10737418240 THEN 'HIGH'
        ELSE 'MODERATE'
    END AS WORST_SEVERITY
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
  AND (bytes_spilled_to_local_storage + bytes_spilled_to_remote_storage) > 0
  AND warehouse_name IS NOT NULL
GROUP BY warehouse_name
HAVING TOTAL_SPILL_GB > 0
ORDER BY TOTAL_SPILL_GB DESC
LIMIT 20
"""

_WH_LOAD_DISTRIBUTION_SQL = """
SELECT
    user_name AS USER_NAME, role_name AS ROLE_NAME, warehouse_name AS WAREHOUSE_NAME,
    COUNT(*) AS QUERY_COUNT,
    ROUND(SUM(total_elapsed_time) / 3600000.0, 2) AS TOTAL_EXECUTION_HOURS,
    ROUND(AVG(bytes_scanned) / POWER(1024, 3), 3) AS AVG_SCANNED_GB,
    ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) AS PCT_OF_TOTAL_QUERIES,
    ROUND(SUM(total_elapsed_time) * 100.0 / NULLIF(SUM(SUM(total_elapsed_time)) OVER(), 0), 1) AS PCT_OF_TOTAL_RUNTIME
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
  AND warehouse_name IS NOT NULL
GROUP BY user_name, role_name, warehouse_name
ORDER BY query_count DESC
LIMIT 20
"""

_WH_POOR_PRUNING_SQL = """
SELECT
    query_id AS QUERY_ID, warehouse_name AS WAREHOUSE_NAME, user_name AS USER_NAME,
    partitions_scanned AS PARTITIONS_SCANNED, partitions_total AS PARTITIONS_TOTAL,
    ROUND(partitions_scanned * 100.0 / NULLIF(partitions_total, 0), 1) AS PCT_TABLE_SCANNED,
    ROUND(bytes_scanned / POWER(1024, 3), 2) AS SCANNED_GB,
    ROUND(total_elapsed_time / 1000.0, 1) AS DURATION_SEC,
    LEFT(query_text, 120) AS QUERY_PREVIEW,
    CASE
        WHEN ROUND(partitions_scanned * 100.0 / NULLIF(partitions_total, 0), 1) >= 100 THEN 'FULL_TABLE_SCAN'
        WHEN ROUND(partitions_scanned * 100.0 / NULLIF(partitions_total, 0), 1) >= 95 THEN 'NEAR_FULL_SCAN'
        ELSE 'PARTIAL_SCAN_90+'
    END AS SCAN_TYPE
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
  AND partitions_total > 1000
  AND partitions_scanned > partitions_total * 0.9
ORDER BY partitions_scanned DESC
LIMIT 20
"""


_WH_CONFIG_DETAILS_SQL = """
SELECT
    NAME AS WAREHOUSE_NAME,
    WAREHOUSE_TYPE,
    SIZE,
    MIN_CLUSTER_COUNT,
    MAX_CLUSTER_COUNT,
    SCALING_POLICY,
    AUTO_SUSPEND,
    AUTO_RESUME
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES
WHERE DELETED IS NULL
ORDER BY NAME
"""

_WH_ACTIVITY_SUMMARY_SQL = """
SELECT
    warehouse_name AS WAREHOUSE_NAME,
    COUNT(DISTINCT DATE_TRUNC('hour', start_time)) AS ACTIVE_HOURS,
    COUNT(*) AS TOTAL_QUERIES,
    ROUND(SUM(total_elapsed_time) / 3600000.0, 2) AS TOTAL_EXECUTION_HOURS,
    ROUND(COUNT(*) / NULLIF(COUNT(DISTINCT DATE_TRUNC('hour', start_time)), 0), 0) AS QUERIES_PER_ACTIVE_HOUR
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
  AND warehouse_name IS NOT NULL
GROUP BY warehouse_name
ORDER BY TOTAL_QUERIES DESC
LIMIT 30
"""

_WH_QAS_ELIGIBLE_SQL = """
SELECT
    WAREHOUSE_NAME,
    QUERY_ID,
    ROUND(ELIGIBLE_QUERY_ACCELERATION_TIME, 2) AS EST_QAS_TIME_SAVED_SEC,
    UPPER_LIMIT_SCALE_FACTOR AS SUGGESTED_MAX_SCALE_FACTOR,
    CASE
        WHEN ELIGIBLE_QUERY_ACCELERATION_TIME > 60 THEN 'HIGH_IMPACT'
        WHEN ELIGIBLE_QUERY_ACCELERATION_TIME > 10 THEN 'MODERATE_IMPACT'
        ELSE 'LOW_IMPACT'
    END AS IMPACT_LEVEL
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_ELIGIBLE
WHERE START_TIME >= DATEADD('day', -7, CURRENT_DATE)
ORDER BY ELIGIBLE_QUERY_ACCELERATION_TIME DESC
LIMIT 10
"""

_WH_QAS_USAGE_SQL = """
SELECT
    warehouse_name AS WAREHOUSE_NAME,
    ROUND(SUM(credits_used_query_acceleration), 2) AS QAS_CREDITS,
    COUNT(*) AS ACCELERATION_EVENTS,
    CASE
        WHEN SUM(credits_used_query_acceleration) > 100 THEN 'HIGH_QAS_USAGE'
        WHEN SUM(credits_used_query_acceleration) > 10 THEN 'MODERATE_QAS_USAGE'
        ELSE 'LOW_QAS_USAGE'
    END AS USAGE_TIER
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
GROUP BY warehouse_name
HAVING QAS_CREDITS > 0
ORDER BY QAS_CREDITS DESC
LIMIT 15
"""

_ALL_WH_QUERIES = {
    "wh_fleet_data": _WH_FLEET_SQL,
    "wh_credits_health": _WH_CREDITS_SQL,
    "wh_heatmap_data": _WH_HEATMAP_SQL,
    "wh_credit_ts_data": _WH_CREDIT_TS_SQL,
    "wh_hourly_activity": _WH_HOURLY_ACTIVITY_SQL,
    "wh_constraint_data": _WH_CONSTRAINT_SQL,
    "wh_oversizing_data": _WH_OVERSIZING_SQL,
    "wh_idle_data": _WH_IDLE_SQL,
    "wh_workload_data": _WH_WORKLOAD_SQL,
    "wh_config_changes": _WH_CONFIG_CHANGES_SQL,
    "wh_data_skew": _WH_DATA_SKEW_SQL,
    "wh_load_distribution": _WH_LOAD_DISTRIBUTION_SQL,
    "wh_poor_pruning": _WH_POOR_PRUNING_SQL,
    "wh_config_details": _WH_CONFIG_DETAILS_SQL,
    "wh_activity_summary": _WH_ACTIVITY_SUMMARY_SQL,
    "wh_qas_eligible": _WH_QAS_ELIGIBLE_SQL,
    "wh_qas_usage": _WH_QAS_USAGE_SQL,
    "wh_scaling_efficiency": _WH_SCALING_EFFICIENCY_SQL,
}


def _run_query(sql):
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        return session.sql(sql).to_pandas()
    except Exception as e:
        st.warning(f"Query error: {e}")
        return pd.DataFrame()


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
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_run_query_thread, session, k, sql): k
            for k, sql in needed.items()
        }
        for future in as_completed(futures):
            key, df, err = future.result()
            st.session_state[key] = df
            completed += 1
            if progress_bar is not None:
                progress_bar.progress(completed / total)
            if status_text is not None:
                status_text.text(f"Loading data... ({completed}/{total} queries)")


PALETTE = CHART_SERIES + CHART_EXTENDED


def comp_warehouse_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in _ALL_WH_QUERIES)
        if not all_cached:
            status_ph.markdown(
                '<p style="color: #003D73; font-weight: 600;">Loading Virtual Warehouses data...</p>',
                unsafe_allow_html=True)
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_all_wh_queries(progress_bar=progress_bar_widget, status_text=status_ph)
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
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
            f'Error loading Warehouses Overview: {e}</div>',
            unsafe_allow_html=True,
        )


def _render_overview():
    fleet_df = st.session_state.get("wh_fleet_data", pd.DataFrame())

    if fleet_df.empty:
        st.info("No warehouse data found.")
        return

    fleet_df.columns = [c.upper() for c in fleet_df.columns]
    size_order = ["X-Small", "Small", "Medium", "Large", "X-Large", "2X-Large", "3X-Large",
                  "4X-Large", "5X-Large", "6X-Large", "Adaptive"]
    size_col = next((c for c in fleet_df.columns if "SIZE" in c), None)
    if size_col:
        all_sizes_df = pd.DataFrame({"SIZE": size_order})
        size_counts = fleet_df[size_col].value_counts().rename_axis("SIZE").reset_index(name="COUNT")
        size_counts = all_sizes_df.merge(size_counts, on="SIZE", how="left").fillna(0)
        size_counts["COUNT"] = size_counts["COUNT"].astype(int)
    else:
        size_counts = pd.DataFrame({"SIZE": [], "COUNT": []})

    total = len(fleet_df)

    col_count, col_bar = st.columns([1, 2])

    with col_count:
        st.markdown(f"**Total Virtual Warehouses: {total}**")
        cols_per_row = 3
        rows = [size_counts.iloc[i:i+cols_per_row] for i in range(0, len(size_counts), cols_per_row)]
        for row in rows:
            cs = st.columns(cols_per_row)
            for j, (_, sz_row) in enumerate(row.iterrows()):
                cnt = int(sz_row["COUNT"])
                color = PALETTE[j % len(PALETTE)] if cnt > 0 else "#888888"
                cs[j].markdown(
                    f'<div style="text-align:center">'
                    f'<div style="font-size:11px;color:#666">{sz_row["SIZE"]}</div>'
                    f'<div style="font-size:24px;font-weight:bold;color:{color}">{cnt}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with col_bar:
        st.markdown("**Warehouse Distribution by Size**")
        fig = go.Figure(data=[go.Bar(
            x=size_counts["SIZE"],
            y=size_counts["COUNT"],
            marker_color=[PALETTE[i % len(PALETTE)] for i in range(len(size_counts))],
            text=size_counts["COUNT"].tolist(),
            textposition="outside",
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=60, l=30, r=20),
                          xaxis=dict(tickangle=-30), showlegend=False,
                          yaxis_title="Number of Warehouses")
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Warehouse Configuration Details", expanded=True):
        config_df = st.session_state.get("wh_config_details", pd.DataFrame())
        if config_df.empty:
            st.info("No warehouse configuration data available.")
        else:
            config_df.columns = [c.upper() for c in config_df.columns]
            st.dataframe(config_df, use_container_width=True)

    with st.expander("Warehouse Load Heatmap", expanded=True):
        heatmap_df = st.session_state.get("wh_heatmap_data", pd.DataFrame())
        if heatmap_df.empty:
            st.info("No heatmap data available.")
        else:
            heatmap_df.columns = [c.upper() for c in heatmap_df.columns]
            pivot = heatmap_df.pivot_table(index="WAREHOUSE_NAME", columns="HOUR_OF_DAY",
                                           values="AVG_QUERY_LOAD", aggfunc="mean").round(2)
            credit_series = heatmap_df.groupby("WAREHOUSE_NAME")["TOTAL_CREDITS"].first().round(0).astype(int)
            pivot.insert(0, "CREDITS", credit_series)
            pivot = pivot.sort_values("CREDITS", ascending=False)

            hour_cols = [c for c in pivot.columns if c != "CREDITS"]
            max_val = pivot[hour_cols].max().max() or 1
            threshold = max_val * 0.35

            def _heatmap_style(val):
                if pd.isna(val) or not isinstance(val, (int, float)):
                    return "background-color: #f5f5f5; color: #999; text-align: center;"
                intensity = min(val / max_val, 1.0)
                if val >= threshold:
                    r = int(232 + (180 - 232) * intensity)
                    g = int(162 + (100 - 162) * intensity)
                    b = int(41 + (20 - 41) * intensity)
                else:
                    r = int(200 + (41 - 200) * (intensity / 0.35 if threshold > 0 else 0))
                    g = int(230 + (181 - 230) * (intensity / 0.35 if threshold > 0 else 0))
                    b = int(250 + (232 - 250) * (intensity / 0.35 if threshold > 0 else 0))
                fg = "white" if intensity > 0.5 else "#333"
                return f"background-color: rgba({r},{g},{b},0.85); color: {fg}; text-align: center; font-size:11px;"

            def _format_val(val):
                if pd.isna(val) or not isinstance(val, (int, float)):
                    return "None"
                return f"{val:.2f}"

            styled = (pivot.style
                      .map(_heatmap_style, subset=hour_cols)
                      .format(_format_val, subset=hour_cols)
                      .format("{:,}", subset=["CREDITS"]))
            st.dataframe(styled, use_container_width=True)

    with st.expander("Credit Usage Analysis", expanded=True):
        ts_df = st.session_state.get("wh_credit_ts_data", pd.DataFrame())
        if ts_df.empty:
            st.info("No credit usage data available.")
        else:
            ts_df.columns = [c.upper() for c in ts_df.columns]
            st.markdown("**Credit Usage by Warehouse Over Time**")
            warehouses = ts_df["WAREHOUSE_NAME"].unique().tolist()
            fig = go.Figure()
            for i, wh in enumerate(warehouses):
                wh_data = ts_df[ts_df["WAREHOUSE_NAME"] == wh].sort_values("DAY")
                fig.add_trace(go.Scatter(
                    x=wh_data["DAY"], y=wh_data["COMPUTE_CREDITS"],
                    mode="lines", fill="tonexty" if i > 0 else "tozeroy",
                    name=wh,
                    line=dict(color=PALETTE[i % len(PALETTE)]),
                    stackgroup="one",
                    hovertemplate="<b>%{fullData.name}</b><br>Date: %{x}<br>Credits: %{y:.2f}<extra></extra>",
                ))
            fig.update_layout(height=380, margin=dict(t=10, b=40, l=40, r=20),
                              xaxis_title="START_TIME", yaxis_title="COMPUTE_CREDITS", showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

            if "IDLE_CREDITS" in ts_df.columns and "COMPUTE_CREDITS" in ts_df.columns:
                st.markdown("**Average Idle % by Warehouse**")
                idle_df = (
                    ts_df.groupby("WAREHOUSE_NAME")
                    .agg({"COMPUTE_CREDITS": "sum", "IDLE_CREDITS": "sum"})
                    .reset_index()
                )
                idle_df["IDLE_PCT"] = (idle_df["IDLE_CREDITS"] / idle_df["COMPUTE_CREDITS"].replace(0, 1) * 100).round(1)
                idle_df = idle_df.sort_values("IDLE_PCT", ascending=False)
                fig2 = go.Figure(data=[go.Bar(
                    y=idle_df["WAREHOUSE_NAME"], x=idle_df["IDLE_PCT"],
                    orientation="h", marker_color=BRAND_SECONDARY,
                    text=[f"{v:.1f}%" for v in idle_df["IDLE_PCT"]],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Idle: %{x:.1f}%<extra></extra>",
                )])
                fig2.update_layout(
                    height=max(300, len(idle_df) * 28),
                    margin=dict(t=10, b=40, l=200, r=80),
                    xaxis_title="Idle %", showlegend=False,
                )
                st.plotly_chart(fig2, use_container_width=True)


def _render_fleet_query():
    with st.expander("Active Warehouse Fleet Distribution", expanded=True):
        st.markdown("Warehouse breakdown by type, resource constraint, and size over the last 7 days.")
        fleet_df = st.session_state.get("wh_fleet_data", pd.DataFrame())
        if fleet_df.empty:
            st.info("No fleet data available.")
        else:
            fleet_df.columns = [c.upper() for c in fleet_df.columns]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Fleet by Warehouse Type**")
                tc = fleet_df["WAREHOUSE_TYPE"].value_counts() if "WAREHOUSE_TYPE" in fleet_df.columns else pd.Series()
                fig = go.Figure(go.Pie(labels=tc.index.tolist(), values=tc.values.tolist(),
                                       marker_colors=[PALETTE[i % len(PALETTE)] for i in range(len(tc))],
                                       texttemplate="%{percent:.0%}", hole=0.3))
                fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10), showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.markdown("**Fleet by Resource Constraint**")
                rc = fleet_df["RESOURCE_CONSTRAINT"].value_counts() if "RESOURCE_CONSTRAINT" in fleet_df.columns else pd.Series()
                fig = go.Figure(go.Bar(y=rc.index.tolist(), x=rc.values.tolist(), orientation="h",
                                        marker_color=PALETTE[0], text=rc.values.tolist(), textposition="outside"))
                fig.update_layout(height=280, margin=dict(t=10, b=10, l=120, r=60),
                                  xaxis_title="WAREHOUSE_COUNT", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            with col3:
                st.markdown("**Fleet by Warehouse Size**")
                sc = fleet_df["WAREHOUSE_SIZE"].value_counts() if "WAREHOUSE_SIZE" in fleet_df.columns else pd.Series()
                sc = sc[sc.index != "None"] if "None" in sc.index else sc
                fig = go.Figure(go.Bar(y=sc.index.tolist(), x=sc.values.tolist(), orientation="h",
                                        marker_color=PALETTE[1], text=sc.values.tolist(), textposition="outside"))
                fig.update_layout(height=280, margin=dict(t=10, b=10, l=100, r=60),
                                  xaxis_title="WAREHOUSE_COUNT", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            show_cols = [c for c in ["WAREHOUSE_TYPE", "RESOURCE_CONSTRAINT", "WAREHOUSE_SIZE"] if c in fleet_df.columns]
            if show_cols:
                tbl = fleet_df.groupby(show_cols).size().reset_index(name="WAREHOUSE_COUNT")
                st.dataframe(tbl, use_container_width=True)

    with st.expander("Top 15 Warehouses by Credit Consumption & Health", expanded=True):
        st.markdown("Credits consumed with health diagnosis based on avg running threads and queue depth.")
        credits_df = st.session_state.get("wh_credits_health", pd.DataFrame())
        if credits_df.empty:
            st.info("No credit health data available.")
        else:
            credits_df.columns = [c.upper() for c in credits_df.columns]
            col_bar, col_pie = st.columns(2)
            with col_bar:
                st.markdown("**Credits by Warehouse (health colour-coded)**")
                health_colors = {"HEALTHY": BRAND_SECONDARY, "OVERUSED_QUEUING": BRAND_ACCENT,
                                 "UNDERUTILIZED": "#75C2D8"}
                top = credits_df.sort_values("CREDITS_30_DAY", ascending=True).tail(15)
                bar_colors = [health_colors.get(s, PALETTE[0]) for s in top.get("HEALTH_STATUS", pd.Series(["HEALTHY"] * len(top)))]
                fig = go.Figure(go.Bar(
                    y=top["WAREHOUSE_NAME"], x=top["CREDITS_30_DAY"],
                    orientation="h",
                    marker_color=bar_colors,
                    text=[f"{v:.1f}" for v in top["CREDITS_30_DAY"]],
                    textposition="outside",
                    customdata=top.get("HEALTH_STATUS", pd.Series([""] * len(top))),
                    hovertemplate="<b>%{y}</b><br>Credits: %{x:.2f}<br>Status: %{customdata}<extra></extra>",
                ))
                fig.update_layout(height=max(300, len(top) * 28), margin=dict(t=10, b=20, l=180, r=80),
                                  xaxis_title="Credits", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            with col_pie:
                st.markdown("**Health Distribution**")
                if "HEALTH_STATUS" in credits_df.columns:
                    hc = credits_df["HEALTH_STATUS"].value_counts()
                    pie_colors = [health_colors.get(s, PALETTE[0]) for s in hc.index.tolist()]
                    fig = go.Figure(go.Pie(labels=hc.index.tolist(), values=hc.values.tolist(),
                                           marker_colors=pie_colors,
                                           texttemplate="%{percent:.1%}", hole=0.3))
                    fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10))
                    st.plotly_chart(fig, use_container_width=True)
            st.dataframe(credits_df, use_container_width=True)

    with st.expander("Hourly Query Activity Distribution (Peak Hours)", expanded=True):
        st.markdown("Query volume and average duration by hour of day to identify peak usage windows.")
        hourly_df = st.session_state.get("wh_hourly_activity", pd.DataFrame())
        if hourly_df.empty:
            st.info("No hourly activity data available.")
        else:
            hourly_df.columns = [c.upper() for c in hourly_df.columns]
            for col in ["QUERY_COUNT", "AVG_DURATION_SEC", "TOTAL_TB_SCANNED"]:
                if col in hourly_df.columns:
                    hourly_df[col] = pd.to_numeric(hourly_df[col], errors="coerce").fillna(0)
            max_q = hourly_df["QUERY_COUNT"].max() or 1
            hourly_df["PCT_OF_PEAK"] = (hourly_df["QUERY_COUNT"] / max_q * 100).round(1)
            hourly_df["ACTIVITY_LEVEL"] = hourly_df["QUERY_COUNT"].apply(
                lambda x: "PEAK" if x >= max_q * 0.85 else ("HIGH" if x >= max_q * 0.6 else "MODERATE"))
            level_colors = {"PEAK": BRAND_PRIMARY_DARK, "HIGH": BRAND_SECONDARY, "MODERATE": "#75C2D8"}
            bar_colors = [level_colors.get(l, BRAND_SECONDARY) for l in hourly_df["ACTIVITY_LEVEL"]]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Query Count by Hour of Day**")
                fig = go.Figure(go.Bar(x=hourly_df["HOUR_OF_DAY"], y=hourly_df["QUERY_COUNT"],
                                        marker_color=bar_colors,
                                        hovertemplate="Hour %{x}: %{y:,.0f} queries<extra></extra>"))
                fig.update_layout(height=280, margin=dict(t=10, b=40, l=40, r=10),
                                  xaxis_title="Hour", yaxis_title="Queries", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.markdown("**Avg Query Duration by Hour (seconds)**")
                fig = go.Figure(go.Scatter(x=hourly_df["HOUR_OF_DAY"], y=hourly_df["AVG_DURATION_SEC"],
                                           mode="lines+markers", line=dict(color=BRAND_ACCENT, width=2),
                                           marker=dict(color=BRAND_ACCENT, size=5),
                                           hovertemplate="Hour %{x}: %{y:.2f}s<extra></extra>"))
                fig.update_layout(height=280, margin=dict(t=10, b=40, l=50, r=10),
                                  xaxis_title="Hour", yaxis_title="Avg Duration (s)")
                st.plotly_chart(fig, use_container_width=True)
            with col3:
                st.markdown("**TB Scanned by Hour**")
                fig = go.Figure(go.Bar(x=hourly_df["HOUR_OF_DAY"], y=hourly_df["TOTAL_TB_SCANNED"],
                                        marker_color=BRAND_SECONDARY,
                                        hovertemplate="Hour %{x}: %{y:.3f} TB<extra></extra>"))
                fig.update_layout(height=280, margin=dict(t=10, b=40, l=50, r=10),
                                  xaxis_title="Hour", yaxis_title="TB Scanned", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(hourly_df, use_container_width=True)

    with st.expander("Resource Constraint Analysis (Spills & Timeouts)", expanded=True):
        st.markdown("Warehouses experiencing memory spills (local/remote) or statement timeouts.")
        constraint_df = st.session_state.get("wh_constraint_data", pd.DataFrame())
        if constraint_df.empty:
            st.success("No resource constraint issues detected in the last 7 days.")
        else:
            constraint_df.columns = [c.upper() for c in constraint_df.columns]
            for col in ["REMOTE_SPILLS", "LOCAL_SPILLS", "TOTAL_REMOTE_SPILL_GB", "TOTAL_LOCAL_SPILL_GB", "STATEMENT_TIMEOUTS"]:
                if col in constraint_df.columns:
                    constraint_df[col] = pd.to_numeric(constraint_df[col], errors="coerce").fillna(0)
            _sev_colors = {"CRITICAL": BRAND_PRIMARY_DARK, "HIGH": BRAND_ACCENT, "MODERATE": '#75C2D8'}
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Remote Spills by Warehouse**")
                df_r = constraint_df[constraint_df["REMOTE_SPILLS"] > 0].sort_values("REMOTE_SPILLS", ascending=True)
                if not df_r.empty:
                    bar_colors = [_sev_colors.get(s, BRAND_SECONDARY) for s in df_r.get("SPILL_SEVERITY", pd.Series(["MODERATE"] * len(df_r)))]
                    fig = go.Figure(go.Bar(y=df_r["WAREHOUSE_NAME"], x=df_r["REMOTE_SPILLS"],
                                           orientation="h", marker_color=bar_colors,
                                           text=df_r["REMOTE_SPILLS"].tolist(), textposition="outside"))
                    for sev, color in _sev_colors.items():
                        if sev in df_r.get("SPILL_SEVERITY", pd.Series([])).values:
                            fig.add_trace(go.Bar(y=[None], x=[None], name=sev, marker_color=color, showlegend=True))
                    fig.update_layout(height=max(250, len(df_r)*28), margin=dict(t=10, b=20, l=200, r=60),
                                      xaxis_title="Remote Spills", barmode="overlay",
                                      legend=dict(title="SPILL_SEVERITY", orientation="v", x=1.02, y=1))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.success("No remote spills detected.")
            with col2:
                st.markdown("**Local Spills by Warehouse**")
                df_l = constraint_df.sort_values("LOCAL_SPILLS", ascending=True)
                fig = go.Figure(go.Bar(y=df_l["WAREHOUSE_NAME"], x=df_l["LOCAL_SPILLS"],
                                       orientation="h", marker_color=BRAND_SECONDARY,
                                       text=df_l["LOCAL_SPILLS"].tolist(), textposition="outside"))
                fig.update_layout(height=max(250, len(df_l)*28), margin=dict(t=10, b=20, l=200, r=60),
                                  xaxis_title="Local Spills", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(constraint_df, use_container_width=True)

    with st.expander("Warehouse Configuration Change History", expanded=True):
        st.markdown("Resize and type conversion events — frequent changes may indicate auto-scaling should be enabled.")
        config_change_df = st.session_state.get("wh_config_changes", pd.DataFrame())
        if config_change_df.empty:
            st.success("No warehouse configuration changes found.")
        else:
            config_change_df.columns = [c.upper() for c in config_change_df.columns]
            st.dataframe(config_change_df, use_container_width=True)

    with st.expander("Query Acceleration Service (QAS) — Eligible Candidates", expanded=True):
        st.markdown("Top queries eligible for QAS acceleration with estimated time savings.")
        qas_df = st.session_state.get("wh_qas_eligible", pd.DataFrame())
        if qas_df.empty:
            st.info("No QAS-eligible queries found in the last 7 days.")
        else:
            qas_df.columns = [c.upper() for c in qas_df.columns]
            col_bar, col_table = st.columns(2)
            with col_bar:
                st.markdown("**Estimated QAS Time Savings (sec)**")
                savings_col = "EST_QAS_TIME_SAVED_SEC" if "EST_QAS_TIME_SAVED_SEC" in qas_df.columns else "EST_SAVINGS_TB"
                qas_df[savings_col] = pd.to_numeric(qas_df[savings_col], errors="coerce").fillna(0)
                top_qas = qas_df.head(10).sort_values(savings_col, ascending=True)
                labels = (top_qas["QUERY_ID"].str[:8] + " @ " + top_qas["WAREHOUSE_NAME"]).tolist()
                impact_colors = {"HIGH_IMPACT": BRAND_PRIMARY_DARK, "MODERATE_IMPACT": BRAND_SECONDARY, "LOW_IMPACT": "#75C2D8"}
                bar_colors = [impact_colors.get(l, BRAND_SECONDARY) for l in top_qas.get("IMPACT_LEVEL", pd.Series(["HIGH_IMPACT"]*len(top_qas)))]
                fig = go.Figure(go.Bar(y=labels, x=top_qas[savings_col],
                                       orientation="h", marker_color=bar_colors,
                                       text=[f"{v:.1f}" for v in top_qas[savings_col]],
                                       textposition="outside",
                                       customdata=top_qas.get("IMPACT_LEVEL", pd.Series([""] * len(top_qas))),
                                       hovertemplate="<b>%{y}</b><br>Savings: %{x:.1f}s<extra></extra>"))
                for imp, color in impact_colors.items():
                    if imp in top_qas.get("IMPACT_LEVEL", pd.Series([])).values:
                        fig.add_trace(go.Bar(y=[None], x=[None], name=imp, marker_color=color, showlegend=True))
                fig.update_layout(height=max(280, len(top_qas)*30), margin=dict(t=10, b=20, l=260, r=80),
                                  xaxis_title="Saved (sec)", barmode="overlay",
                                  legend=dict(title="IMPACT_LEVEL", orientation="v", x=1.02, y=1))
                st.plotly_chart(fig, use_container_width=True)
            with col_table:
                show_cols = [c for c in ["WAREHOUSE_NAME", "QUERY_ID", "EST_QAS_TIME_SAVED_SEC", "EST_SAVINGS_TB"] if c in qas_df.columns]
                st.dataframe(qas_df[show_cols], use_container_width=True)

    with st.expander("Query Acceleration Service (QAS) — Usage Summary", expanded=True):
        st.markdown("Credits consumed and acceleration duration by warehouse via QAS.")
        qas_usage_df = st.session_state.get("wh_qas_usage", pd.DataFrame())
        if qas_usage_df.empty:
            st.info("No QAS usage data found for the last 30 days.")
        else:
            qas_usage_df.columns = [c.upper() for c in qas_usage_df.columns]
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**QAS Credits by Warehouse**")
                df_sorted = qas_usage_df.sort_values("QAS_CREDITS", ascending=True)
                tier_colors = {"HIGH_QAS_USAGE": BRAND_PRIMARY_DARK, "MODERATE_QAS_USAGE": BRAND_SECONDARY,
                               "LOW_QAS_USAGE": "#75C2D8"}
                bar_colors = [tier_colors.get(t, BRAND_SECONDARY) for t in df_sorted.get("USAGE_TIER", pd.Series(["LOW_QAS_USAGE"]*len(df_sorted)))]
                fig = go.Figure(go.Bar(y=df_sorted["WAREHOUSE_NAME"], x=df_sorted["QAS_CREDITS"],
                                       orientation="h", marker_color=bar_colors,
                                       text=[f"{v:.2f}" for v in df_sorted["QAS_CREDITS"]],
                                       textposition="outside",
                                       customdata=df_sorted.get("USAGE_TIER", pd.Series([""] * len(df_sorted))),
                                       hovertemplate="<b>%{y}</b><br>Credits: %{x:.2f}<br>Tier: %{customdata}<extra></extra>"))
                fig.update_layout(height=max(250, len(df_sorted)*28), margin=dict(t=10, b=20, l=200, r=80),
                                  xaxis_title="QAS Credits", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.markdown("**QAS Acceleration Events by Warehouse**")
                df_sorted2 = qas_usage_df.sort_values("ACCELERATION_EVENTS", ascending=True)
                bar_colors2 = [tier_colors.get(t, BRAND_SECONDARY) for t in df_sorted2.get("USAGE_TIER", pd.Series(["LOW_QAS_USAGE"]*len(df_sorted2)))]
                fig = go.Figure(go.Bar(y=df_sorted2["WAREHOUSE_NAME"], x=df_sorted2["ACCELERATION_EVENTS"],
                                       orientation="h", marker_color=bar_colors2,
                                       text=df_sorted2["ACCELERATION_EVENTS"].tolist(),
                                       textposition="outside",
                                       hovertemplate="<b>%{y}</b><br>Events: %{x}<extra></extra>"))
                fig.update_layout(height=max(250, len(df_sorted2)*28), margin=dict(t=10, b=20, l=200, r=80),
                                  xaxis_title="Acceleration Events", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

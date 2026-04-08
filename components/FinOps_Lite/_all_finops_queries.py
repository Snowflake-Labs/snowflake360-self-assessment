_ALL_FINOPS_QUERIES = {

    # ========================
    # finops_visibility.py
    # ========================

    "fv_exec_forecast": """
WITH compute_cost AS (
    SELECT 'Compute (Warehouse)' AS CATEGORY,
           SUM(CREDITS_USED_COMPUTE) AS units,
           SUM(CREDITS_USED_COMPUTE) * {credit_price} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
),
cs_cost AS (
    SELECT 'Cloud Services' AS CATEGORY,
           SUM(CREDITS_USED_CLOUD_SERVICES) AS units,
           SUM(CREDITS_USED_CLOUD_SERVICES) * {credit_price} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
),
storage_cost AS (
    SELECT 'Storage' AS CATEGORY,
           AVG(storage_bytes + stage_bytes + failsafe_bytes) / POW(1024, 4) AS units_tb,
           (AVG(storage_bytes + stage_bytes + failsafe_bytes) / POW(1024, 4)) * {storage_price} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
    WHERE usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
transfer_cost AS (
    SELECT 'Data Transfer' AS CATEGORY,
           COALESCE(SUM(bytes_transferred) / POW(1024, 3), 0) AS units_gb,
           0 AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
unioned AS (
    SELECT CATEGORY, cost_last_30d FROM compute_cost
    UNION ALL SELECT CATEGORY, cost_last_30d FROM cs_cost
    UNION ALL SELECT CATEGORY, cost_last_30d FROM storage_cost
    UNION ALL SELECT CATEGORY, cost_last_30d FROM transfer_cost
)
SELECT
    CATEGORY,
    ROUND(cost_last_30d, 2) AS ACTUAL_COST_30D,
    ROUND(cost_last_30d, 2) AS FORECAST_1M,
    ROUND(cost_last_30d * 3, 2) AS FORECAST_3M,
    ROUND(cost_last_30d * 6, 2) AS FORECAST_6M,
    ROUND(cost_last_30d * 12, 2) AS EAC_ANNUAL
FROM unioned
ORDER BY cost_last_30d DESC
""",

    "fv_compute_breakdown": """
WITH resource_metrics AS (
    SELECT 'WAREHOUSE' AS SERVICE_TYPE, WAREHOUSE_NAME AS RESOURCE_NAME,
           SUM(CREDITS_USED) AS credits_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY WAREHOUSE_NAME
    UNION ALL
    SELECT SERVICE_TYPE, SERVICE_TYPE AS RESOURCE_NAME,
           SUM(CREDITS_USED) AS credits_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
      AND SERVICE_TYPE NOT IN ('WAREHOUSE_METERING', 'WAREHOUSE_METERING_READER')
    GROUP BY SERVICE_TYPE
)
SELECT
    SERVICE_TYPE,
    RESOURCE_NAME,
    ROUND(credits_last_30d, 2) AS CREDITS_LAST_30D,
    ROUND(credits_last_30d * {credit_price}, 2) AS COST_LAST_30D,
    ROUND((credits_last_30d * {credit_price}) * 12, 0) AS ESTIMATED_ANNUAL_COST,
    ROUND(RATIO_TO_REPORT(credits_last_30d * {credit_price}) OVER () * 100, 2) AS PCT_OF_TOTAL_COMPUTE
FROM resource_metrics
WHERE credits_last_30d > 0
ORDER BY COST_LAST_30D DESC
LIMIT 20
""",

    "fv_costliest_queries": """
WITH query_costs AS (
    SELECT query_id, user_name, warehouse_name,
           credits_attributed_compute,
           credits_attributed_compute * {credit_price} AS query_cost_usd
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
)
SELECT
    ROUND(qc.query_cost_usd, 4) AS QUERY_COST_USD,
    ROUND(qc.credits_attributed_compute, 4) AS CREDITS_USED,
    qc.user_name AS USER_NAME,
    qc.warehouse_name AS WAREHOUSE_NAME,
    qc.query_id AS QUERY_ID
FROM query_costs qc
ORDER BY qc.query_cost_usd DESC
LIMIT 20
""",

    "fv_user_cost_attribution": """
SELECT
    qah.user_name AS USER_NAME,
    COUNT(DISTINCT qah.query_id) AS QUERY_COUNT,
    ROUND(SUM(qah.credits_attributed_compute), 2) AS TOTAL_CREDITS,
    ROUND(SUM(qah.credits_attributed_compute) * {credit_price}, 2) AS TOTAL_COST_USD,
    ROUND(AVG(qah.credits_attributed_compute) * {credit_price}, 4) AS AVG_COST_PER_QUERY,
    ROUND(RATIO_TO_REPORT(SUM(qah.credits_attributed_compute)) OVER () * 100, 2) AS PCT_OF_TOTAL
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY qah
WHERE qah.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY qah.user_name
ORDER BY TOTAL_COST_USD DESC
LIMIT 20
""",

    "fv_storage_costs": """
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
    ROUND((average_database_bytes / POW(1024, 4)) * {storage_price}, 2) AS DAILY_COST_USD,
    ROUND(((average_database_bytes / POW(1024, 4)) * {storage_price}) * 30, 2) AS EST_MONTHLY_COST,
    ROUND(RATIO_TO_REPORT((average_database_bytes / POW(1024, 4)) * {storage_price}) OVER () * 100, 2) AS PCT_OF_TOTAL_STORAGE
FROM latest_storage
WHERE rn = 1
ORDER BY DAILY_COST_USD DESC
""",

    "fv_data_transfer": """
SELECT
    target_cloud AS TARGET_CLOUD,
    transfer_type AS TRANSFER_TYPE,
    ROUND(SUM(bytes_transferred) / POW(1024, 3), 2) AS GB_TRANSFERRED
FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY GB_TRANSFERRED DESC
""",

    "fv_daily_cost_trend": """
SELECT
    mdh.usage_date AS USAGE_DATE,
    ROUND(SUM(mdh.credits_used_compute), 2) AS COMPUTE_CREDITS,
    ROUND(SUM(mdh.credits_used_cloud_services), 2) AS CLOUD_SERVICES_CREDITS,
    ROUND(SUM(mdh.credits_used_compute + mdh.credits_used_cloud_services), 2) AS TOTAL_CREDITS,
    ROUND(SUM(mdh.credits_used_compute + mdh.credits_used_cloud_services) * {credit_price}, 2) AS TOTAL_COST_USD,
    ROUND(AVG(SUM(mdh.credits_used_compute + mdh.credits_used_cloud_services) * {credit_price}) OVER (
        ORDER BY mdh.usage_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS ROLLING_7D_AVG_COST
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY mdh
WHERE mdh.usage_date >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY mdh.usage_date
ORDER BY mdh.usage_date ASC
""",

    "fv_service_type_breakdown": """
SELECT
    mdh.service_type AS SERVICE_TYPE,
    ROUND(SUM(mdh.credits_used), 2) AS TOTAL_CREDITS,
    ROUND(SUM(mdh.credits_used) * {credit_price}, 2) AS TOTAL_COST_USD,
    ROUND(SUM(mdh.credits_used) * {credit_price} * 12, 0) AS EST_ANNUAL_COST,
    ROUND(RATIO_TO_REPORT(SUM(mdh.credits_used)) OVER () * 100, 2) AS PCT_OF_TOTAL,
    CASE
        WHEN SUM(mdh.credits_used) * {credit_price} > 1000 THEN 'HIGH_COST'
        WHEN SUM(mdh.credits_used) * {credit_price} > 100 THEN 'MODERATE_COST'
        ELSE 'LOW_COST'
    END AS COST_TIER
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY mdh
WHERE mdh.usage_date >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY mdh.service_type
ORDER BY TOTAL_COST_USD DESC
""",

    "fv_monthly_wh_credits": """
SELECT
    DATE_TRUNC('month', start_time) AS MONTH,
    ROUND(SUM(credits_used), 2) AS MONTHLY_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
GROUP BY DATE_TRUNC('month', start_time)
ORDER BY MONTH ASC
LIMIT 12
""",

    "fv_wh_eac_heatmap": """
WITH monthly_credits AS (
    SELECT
        warehouse_name,
        ROUND(SUM(credits_used), 2) AS total_credits_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY warehouse_name
    ORDER BY total_credits_30d DESC
    LIMIT 30
)
SELECT
    warehouse_name AS WAREHOUSE_NAME,
    ROUND(total_credits_30d * {credit_price} * 1, 0) AS M1,
    ROUND(total_credits_30d * {credit_price} * 2, 0) AS M2,
    ROUND(total_credits_30d * {credit_price} * 3, 0) AS M3,
    ROUND(total_credits_30d * {credit_price} * 4, 0) AS M4,
    ROUND(total_credits_30d * {credit_price} * 5, 0) AS M5,
    ROUND(total_credits_30d * {credit_price} * 6, 0) AS M6,
    ROUND(total_credits_30d * {credit_price} * 7, 0) AS M7,
    ROUND(total_credits_30d * {credit_price} * 8, 0) AS M8,
    ROUND(total_credits_30d * {credit_price} * 9, 0) AS M9,
    ROUND(total_credits_30d * {credit_price} * 10, 0) AS M10,
    ROUND(total_credits_30d * {credit_price} * 11, 0) AS M11,
    ROUND(total_credits_30d * {credit_price} * 12, 0) AS M12
FROM monthly_credits
ORDER BY total_credits_30d DESC
""",

    # ========================
    # finops_control.py
    # ========================

    "fc_resource_monitors": """
SELECT
    name AS MONITOR_NAME,
    credit_quota AS CREDIT_QUOTA,
    notify AS NOTIFY_PCT,
    suspend AS SUSPEND_PCT,
    suspend_immediate AS SUSPEND_IMMEDIATE_PCT,
    created AS CREATED,
    owner AS OWNER,
    warehouses AS WAREHOUSES
FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS
ORDER BY credit_quota DESC
""",

    "fc_top_credit_wh": """
SELECT
    warehouse_name AS WAREHOUSE_NAME,
    ROUND(SUM(credits_used), 2) AS TOTAL_CREDITS_30D,
    ROUND(AVG(credits_used), 4) AS AVG_CREDITS_PER_HOUR,
    COUNT(*) AS HOURS_ACTIVE,
    ROUND(SUM(credits_used_compute), 2) AS COMPUTE_CREDITS,
    ROUND(SUM(credits_used_cloud_services), 2) AS CLOUD_SERVICES_CREDITS,
    CASE
        WHEN SUM(credits_used) > 1000 THEN 'HIGH_USAGE'
        WHEN SUM(credits_used) > 500 THEN 'MEDIUM_USAGE'
        ELSE 'LOW_USAGE'
    END AS USAGE_TIER
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
GROUP BY warehouse_name
ORDER BY TOTAL_CREDITS_30D DESC
""",

    "fc_always_on_wh": """
WITH daily_usage AS (
    SELECT warehouse_name, DATE(start_time) AS usage_date,
           COUNT(DISTINCT HOUR(start_time)) AS hours_running_per_day
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
    GROUP BY warehouse_name, DATE(start_time)
)
SELECT
    warehouse_name AS WAREHOUSE_NAME,
    ROUND(AVG(hours_running_per_day), 1) AS AVG_HOURS_PER_DAY,
    MAX(hours_running_per_day) AS MAX_HOURS_PER_DAY,
    COUNT(*) AS DAYS_TRACKED,
    CASE
        WHEN AVG(hours_running_per_day) >= 20 THEN 'ALWAYS_ON'
        WHEN AVG(hours_running_per_day) >= 12 THEN 'HIGH_UPTIME'
        ELSE 'NORMAL'
    END AS UPTIME_STATUS
FROM daily_usage
GROUP BY warehouse_name
HAVING AVG(hours_running_per_day) >= 12
ORDER BY AVG_HOURS_PER_DAY DESC
""",

    "fc_idle_time": """
SELECT
    warehouse_name AS WAREHOUSE_NAME,
    ROUND(SUM(credits_used_compute), 2) AS TOTAL_COMPUTE_CREDITS,
    ROUND(SUM(credits_attributed_compute_queries), 2) AS QUERY_CREDITS,
    ROUND(SUM(credits_used_compute) - SUM(credits_attributed_compute_queries), 2) AS IDLE_CREDITS,
    ROUND(
        (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
        NULLIF(SUM(credits_used_compute), 0) * 100, 2
    ) AS IDLE_PERCENT,
    CASE
        WHEN (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
             NULLIF(SUM(credits_used_compute), 0) > 0.3 THEN 'HIGH_IDLE_OPTIMIZE_AUTO_SUSP'
        WHEN (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
             NULLIF(SUM(credits_used_compute), 0) > 0.15 THEN 'MODERATE_IDLE'
        ELSE 'LOW_IDLE'
    END AS IDLE_STATUS
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD('day', -10, CURRENT_DATE)
  AND credits_attributed_compute_queries IS NOT NULL
GROUP BY warehouse_name
HAVING SUM(credits_used_compute) - SUM(credits_attributed_compute_queries) > 0
ORDER BY IDLE_CREDITS DESC
""",

    "fc_rm_coverage_gap": """
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
)
SELECT
    'Warehouses without Resource Monitors' AS RISK_CATEGORY,
    COUNT(DISTINCT warehouse_name) AS ITEM_COUNT,
    ROUND(SUM(monthly_credits), 2) AS CREDITS_OR_QUOTA
FROM warehouse_spend WHERE monthly_credits > 100
UNION ALL
SELECT
    'Resource Monitors Configured' AS RISK_CATEGORY,
    COUNT(*) AS ITEM_COUNT,
    ROUND(COALESCE(SUM(credit_quota), 0), 2) AS CREDITS_OR_QUOTA
FROM monitor_quotas
""",

    "fc_wow_cost_trend": """
WITH weekly_data AS (
    SELECT warehouse_name,
           SUM(CASE WHEN start_time >= DATEADD('day', -7, CURRENT_DATE) THEN credits_used ELSE 0 END) AS current_credits,
           SUM(CASE WHEN start_time >= DATEADD('day', -14, CURRENT_DATE) AND start_time < DATEADD('day', -7, CURRENT_DATE)
                    THEN credits_used ELSE 0 END) AS previous_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATEADD('day', -14, CURRENT_DATE)
    GROUP BY warehouse_name
)
SELECT
    warehouse_name AS WAREHOUSE_NAME,
    ROUND(previous_credits, 2) AS PREVIOUS_WEEK_CREDITS,
    ROUND(current_credits, 2) AS CURRENT_WEEK_CREDITS,
    ROUND(current_credits - previous_credits, 2) AS CREDIT_CHANGE,
    ROUND((current_credits - previous_credits) / NULLIF(previous_credits, 0) * 100, 2) AS PERCENT_CHANGE,
    CASE
        WHEN (current_credits - previous_credits) / NULLIF(previous_credits, 0) > 0.5 THEN 'COST_SPIKE_GT_50PCT'
        WHEN (current_credits - previous_credits) / NULLIF(previous_credits, 0) > 0.25 THEN 'COST_INCREASE_GT_25PCT'
        ELSE 'STABLE_OR_DECREASING'
    END AS TREND_STATUS
FROM weekly_data
WHERE current_credits > 10 OR previous_credits > 10
ORDER BY CREDIT_CHANGE DESC
""",

    "fc_serverless_costs": """
SELECT service_type AS SERVICE_TYPE, total_credits AS TOTAL_CREDITS
FROM (
    SELECT 'AUTO_CLUSTERING' AS service_type, ROUND(SUM(credits_used), 2) AS total_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
    UNION ALL
    SELECT 'SERVERLESS_TASK', ROUND(SUM(credits_used), 2)
    FROM SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
    UNION ALL
    SELECT 'MATERIALIZED_VIEWS', ROUND(SUM(credits_used), 2)
    FROM SNOWFLAKE.ACCOUNT_USAGE.MATERIALIZED_VIEW_REFRESH_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
    UNION ALL
    SELECT 'SEARCH_OPTIMIZATION', ROUND(SUM(credits_used), 2)
    FROM SNOWFLAKE.ACCOUNT_USAGE.SEARCH_OPTIMIZATION_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
) x
WHERE total_credits > 0
ORDER BY total_credits DESC
""",

    "fc_spending_summary": """
SELECT
    'WAREHOUSE_METERING' AS SERVICE_TYPE,
    ROUND(SUM(credits_used), 2) AS TOTAL_CREDITS,
    COUNT(DISTINCT DATE(start_time)) AS DAYS_WITH_ACTIVITY,
    ROUND(AVG(credits_used), 4) AS AVG_PER_EVENT,
    ROUND(MIN(credits_used), 4) AS MIN_PER_EVENT,
    ROUND(MAX(credits_used), 4) AS MAX_PER_EVENT
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
UNION ALL
SELECT
    'SERVERLESS_TASKS' AS SERVICE_TYPE,
    ROUND(SUM(credits_used), 2) AS TOTAL_CREDITS,
    COUNT(DISTINCT DATE(start_time)) AS DAYS_WITH_ACTIVITY,
    ROUND(AVG(credits_used), 4) AS AVG_PER_EVENT,
    ROUND(MIN(credits_used), 4) AS MIN_PER_EVENT,
    ROUND(MAX(credits_used), 4) AS MAX_PER_EVENT
FROM SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
ORDER BY TOTAL_CREDITS DESC
""",

    "fc_monthly_trend": """
SELECT
    DATE_TRUNC('month', start_time) AS MONTH,
    ROUND(SUM(credits_used_compute), 2) AS COMPUTE_CREDITS,
    ROUND(SUM(credits_used_cloud_services), 2) AS CS_CREDITS,
    ROUND(SUM(credits_used), 2) AS TOTAL_CREDITS,
    COUNT(DISTINCT DATE(start_time)) AS DAYS_IN_MONTH,
    ROUND(SUM(credits_used) * {credit_price}, 2) AS ESTIMATED_COST_USD,
    TO_CHAR(DATE_TRUNC('month', start_time), 'Mon YYYY') AS MONTH_LABEL
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
GROUP BY DATE_TRUNC('month', start_time)
ORDER BY MONTH DESC
LIMIT 12
""",

    "fc_storage_costs": """
SELECT
    DATE_TRUNC('month', usage_date) AS MONTH,
    ROUND(AVG(storage_bytes + stage_bytes + failsafe_bytes) / POWER(1024, 4), 4) AS AVG_STORAGE_TB,
    'Storage NOT covered by compute budgets' AS NOTE
FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
WHERE usage_date >= DATEADD('month', -3, CURRENT_DATE)
GROUP BY DATE_TRUNC('month', usage_date)
ORDER BY MONTH DESC
""",

    "fc_budget_util": """
WITH current_month_spend AS (
    SELECT COALESCE(SUM(CREDITS_USED), 0) AS month_to_date_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATE_TRUNC('month', CURRENT_TIMESTAMP())
),
daily_avg AS (
    SELECT AVG(daily_credits) AS avg_daily_spend
    FROM (
        SELECT DATE(START_TIME) AS d, SUM(CREDITS_USED) AS daily_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE START_TIME >= DATEADD('day', -30, CURRENT_DATE)
        GROUP BY DATE(START_TIME)
    )
)
SELECT
    500 AS BUDGET_LIMIT_CREDITS,
    ROUND(s.month_to_date_credits, 2) AS CURRENT_SPEND_CREDITS,
    ROUND((s.month_to_date_credits / 500) * 100, 2) AS UTILIZATION_PERCENT,
    ROUND(500 - s.month_to_date_credits, 2) AS REMAINING_CREDITS,
    CASE
        WHEN (s.month_to_date_credits / 500) > 0.9 THEN 'WARNING_GT_90PCT'
        WHEN (s.month_to_date_credits / 500) > 0.75 THEN 'CAUTION_GT_75PCT'
        ELSE 'HEALTHY_LT_75PCT'
    END AS UTILIZATION_STATUS,
    ROUND(d.avg_daily_spend, 2) AS AVG_DAILY_SPEND_30D,
    DAY(LAST_DAY(CURRENT_DATE)) AS DAYS_IN_MONTH,
    DAY(CURRENT_DATE) AS DAYS_ELAPSED,
    ROUND(d.avg_daily_spend * DAY(LAST_DAY(CURRENT_DATE)), 2) AS PROJECTED_MONTH_END_CREDITS
FROM current_month_spend s
CROSS JOIN daily_avg d
""",

    "fc_spcs_credits": """
SELECT
    'SPCS Services' AS SERVICE_NAME,
    ROUND(COALESCE(SUM(credits_used), 0), 2) AS TOTAL_CREDITS,
    'Covered by ACCOUNT_ROOT_BUDGET' AS BUDGET_STATUS
FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPARK_CONTAINER_SERVICES_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
""",

    "fc_budget_inventory": """
SELECT
    NAME AS BUDGET_NAME,
    DATABASE_NAME || '.' || SCHEMA_NAME AS FULL_PATH,
    CREATED AS CREATED_DATE,
    OWNER_NAME AS OWNER,
    COMMENT
FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
WHERE CLASS_NAME = 'BUDGET'
  AND DELETED IS NULL
ORDER BY CREATED DESC
""",

    "fc_dangling_budgets": """
WITH all_budgets AS (
    SELECT name AS budget_name
    FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
    WHERE class_name = 'BUDGET'
      AND deleted IS NULL
      AND name != 'ACCOUNT_ROOT_BUDGET'
)
SELECT
    COUNT(*) AS CUSTOM_BUDGET_COUNT,
    COALESCE(LISTAGG(budget_name, ', ') WITHIN GROUP (ORDER BY budget_name), '') AS BUDGET_NAMES,
    'Note: Use <budget>!GET_LINKED_RESOURCES() to verify attachments' AS RECOMMENDATION
FROM all_budgets
""",

    # ========================
    # finops_optimization.py
    # ========================

    "fo_cloud_svcs_overhead": """
WITH pattern_summary AS (
    SELECT 'SHOW Commands' AS pattern, SUM(credits_used_cloud_services) AS credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP()) AND query_type = 'SHOW'
    UNION ALL
    SELECT 'Short Queries (<100ms)', SUM(credits_used_cloud_services)
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP()) AND total_elapsed_time < 100
    UNION ALL
    SELECT 'Metadata Scans', SUM(credits_used_cloud_services)
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND (schema_name = 'INFORMATION_SCHEMA' OR query_text ILIKE '%INFORMATION_SCHEMA%')
    UNION ALL
    SELECT 'Single-Row Inserts', SUM(credits_used_cloud_services)
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND query_type = 'INSERT' AND rows_produced = 1
)
SELECT
    pattern AS PATTERN,
    ROUND(credits, 4) AS CLOUD_SERVICES_CREDITS_30D,
    ROUND(credits * {credit_price}, 2) AS ESTIMATED_COST_USD,
    ROUND(RATIO_TO_REPORT(credits) OVER () * 100, 1) AS PCT_OF_OVERHEAD
FROM pattern_summary
WHERE credits > 0
ORDER BY credits DESC
""",

    "fo_copy_summary": """
WITH copy_q AS (
    SELECT QUERY_PARAMETERIZED_HASH, MIN(QUERY_TEXT) AS sample_text,
           COUNT(*) AS executions, SUM(CREDITS_USED_CLOUD_SERVICES) AS cs_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE START_TIME > DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND REGEXP_LIKE(QUERY_TEXT, '^\\\\s*COPY\\\\s+INTO\\\\b', 'i')
    GROUP BY QUERY_PARAMETERIZED_HASH
)
SELECT
    COALESCE(SUM(executions), 0) AS TOTAL_COPY_COMMANDS_30D,
    COALESCE(COUNT(*), 0) AS DISTINCT_COPY_PATTERNS,
    ROUND(COALESCE(SUM(cs_credits), 0), 4) AS TOTAL_CLOUD_SERVICES_CREDITS
FROM copy_q
""",

    "fo_copy_patterns": """
SELECT
    SUBSTR(QUERY_TEXT, 1, 120) AS PATTERN_SHORT,
    COUNT(*) AS EXECUTION_COUNT,
    SUM(ROWS_PRODUCED) AS TOTAL_ROWS_LOADED,
    ROUND(AVG(COMPILATION_TIME), 0) AS AVG_COMPILE_MS,
    ROUND(SUM(CREDITS_USED_CLOUD_SERVICES), 4) AS CLOUD_SERVICES_CREDITS,
    CASE
        WHEN AVG(COMPILATION_TIME) > 5000 THEN 'HIGH_FILE_LISTING_OVERHEAD'
        WHEN COUNT(*) > 100 AND SUM(ROWS_PRODUCED) < 1000 THEN 'REDUNDANT_PATTERN'
        ELSE 'INVESTIGATE'
    END AS ISSUE_TYPE
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND QUERY_TYPE = 'COPY'
  AND EXECUTION_TIME > 1000
  AND ROWS_PRODUCED < 100
GROUP BY SUBSTR(QUERY_TEXT, 1, 120)
ORDER BY EXECUTION_COUNT DESC
LIMIT 10
""",

    "fo_short_queries": """
SELECT
    'Short Queries (<100ms)' AS PATTERN_TYPE,
    REGEXP_REPLACE(q.query_text, '\\\\b\\\\d+\\\\b', '?') AS QUERY_TEMPLATE_SHORT,
    q.user_name AS USER_NAME,
    s.client_application_id AS CLIENT_TOOL,
    COUNT(*) AS EXECUTION_COUNT,
    ROUND(SUM(q.credits_used_cloud_services), 4) AS CLOUD_SERVICES_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
JOIN SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND q.total_elapsed_time < 100
  AND q.query_type = 'SELECT'
GROUP BY ALL
HAVING COUNT(*) > 1000
ORDER BY EXECUTION_COUNT DESC
LIMIT 10
""",

    "fo_info_schema": """
SELECT
    q.user_name AS USER_NAME,
    s.client_application_id AS CLIENT_TOOL,
    SUBSTR(q.query_text, 1, 80) AS QUERY_PREVIEW_SHORT,
    COUNT(*) AS EXECUTION_COUNT,
    ROUND(AVG(q.compilation_time), 0) AS AVG_COMPILE_MS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
JOIN SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (q.schema_name = 'INFORMATION_SCHEMA' OR q.query_text ILIKE '%INFORMATION_SCHEMA%')
GROUP BY ALL
ORDER BY EXECUTION_COUNT DESC
LIMIT 10
""",

    "fo_show_commands": """
SELECT
    q.query_type AS QUERY_TYPE,
    SUBSTR(q.query_text, 1, 60) AS COMMAND_TYPE,
    q.user_name AS USER_NAME,
    s.client_application_id AS CLIENT_TOOL,
    COUNT(*) AS EXECUTION_COUNT
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
JOIN SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND q.query_type = 'SHOW'
GROUP BY ALL
ORDER BY EXECUTION_COUNT DESC
LIMIT 10
""",

    "fo_single_row_inserts": """
SELECT
    REGEXP_SUBSTR(query_text, 'INSERT INTO ([a-zA-Z0-9_.]+)', 1, 1, 'i', 1) AS TARGET_TABLE,
    user_name AS USER_NAME,
    COUNT(*) AS INSERT_COUNT,
    SUM(rows_produced) AS TOTAL_ROWS_LOADED,
    CASE
        WHEN COUNT(*) > 1000 THEN 'CRITICAL_BATCH_IMMEDIATELY'
        WHEN COUNT(*) > 100 THEN 'HIGH_CONSIDER_BATCHING'
        ELSE 'MODERATE'
    END AS SEVERITY
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type = 'INSERT'
  AND rows_produced = 1
GROUP BY ALL
ORDER BY INSERT_COUNT DESC
LIMIT 10
""",

    "fo_complex_queries": """
SELECT
    query_id AS QUERY_ID,
    query_type AS QUERY_TYPE,
    user_name AS USER_NAME,
    warehouse_name AS WAREHOUSE_NAME,
    LENGTH(query_text) AS SQL_CHARACTER_LENGTH,
    compilation_time AS COMPILE_MS,
    CASE
        WHEN compilation_time > 30000 THEN 'CRITICAL_SIMPLIFY_QUERY'
        WHEN compilation_time > 10000 THEN 'HIGH_REVIEW_COMPLEXITY'
        ELSE 'MODERATE'
    END AS SEVERITY
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND compilation_time > 5000
ORDER BY compilation_time DESC
LIMIT 10
""",

    "fo_ddl_clone": """
SELECT
    query_type AS QUERY_TYPE,
    REGEXP_SUBSTR(query_text, ' (TABLE|VIEW|SCHEMA|DATABASE) [IF EXISTS ]*([a-zA-Z0-9_.]+)', 1, 1, 'i', 2) AS OBJECT_NAME,
    user_name AS USER_NAME,
    COUNT(*) AS OPERATION_COUNT
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type IN ('CREATE_TABLE', 'DROP_TABLE', 'CREATE_VIEW', 'ALTER_TABLE', 'RESTORE', 'CREATE_TABLE_AS_SELECT')
  AND query_text ILIKE '%CLONE%'
GROUP BY ALL
ORDER BY OPERATION_COUNT DESC
LIMIT 10
""",

    "fo_ddl_summary": """
WITH ddl_q AS (
    SELECT query_parameterized_hash, COUNT(*) AS executions, SUM(credits_used_cloud_services) AS cs_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
      AND REGEXP_LIKE(query_text, '^\\\\s*(CREATE|ALTER|DROP)\\\\b', 'i')
    GROUP BY query_parameterized_hash
)
SELECT
    COALESCE(SUM(executions), 0) AS TOTAL_DDL_30D,
    COALESCE(COUNT(*), 0) AS DISTINCT_DDL_PATTERNS,
    ROUND(COALESCE(SUM(cs_credits), 0), 4) AS TOTAL_CS_CREDITS
FROM ddl_q
""",

    "fo_clone_summary": """
WITH clone_q AS (
    SELECT query_parameterized_hash, COUNT(*) AS executions, SUM(credits_used_cloud_services) AS cs_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
      AND REGEXP_LIKE(query_text, '\\\\bCLONE\\\\b', 'i')
    GROUP BY query_parameterized_hash
)
SELECT
    COALESCE(SUM(executions), 0) AS TOTAL_CLONE_30D,
    COALESCE(COUNT(*), 0) AS DISTINCT_CLONE_PATTERNS,
    ROUND(COALESCE(SUM(cs_credits), 0), 4) AS TOTAL_CS_CREDITS
FROM clone_q
""",

}

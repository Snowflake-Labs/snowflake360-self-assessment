_ALL_FINOPS_QUERIES = {

    # ========================
    # finops_visibility.py
    # ========================

    "finops_exec_forecast": """
WITH compute_cost AS (
    SELECT
        'Compute & Services' AS category,
        SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES) AS units,
        SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES) * 3.0 AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
),
storage_cost AS (
    SELECT
        'Storage' AS category,
        AVG(storage_bytes + stage_bytes + failsafe_bytes) / POW(1024, 4) AS units_tb,
        (AVG(storage_bytes + stage_bytes + failsafe_bytes) / POW(1024, 4)) * 23.0 AS cost_last_30d
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
""",

    "finops_compute_breakdown": """
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
           ROUND(credits_last_30d * 3.0, 2) AS cost_last_30d,
           ROUND((credits_last_30d * 3.0) * 12, 0) AS estimated_annual_cost
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
""",

    "finops_costliest_queries": """
WITH query_costs AS (
    SELECT query_id, user_name, warehouse_name,
           credits_attributed_compute,
           credits_attributed_compute * 3.0 AS query_cost_usd
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
""",

    "finops_storage_costs": """
SELECT
    usage_date AS "Usage Date",
    database_name AS "Database",
    ROUND(AVG(average_database_bytes) / POW(1024, 3), 2) AS "Avg GB",
    ROUND(AVG(average_database_bytes) / POW(1024, 4), 4) AS "Avg TB",
    ROUND((AVG(average_database_bytes) / POW(1024, 4)) * 23.0, 2) AS "Daily Cost ($)",
    ROUND(((AVG(average_database_bytes) / POW(1024, 4)) * 23.0) * 30, 2) AS "Est Monthly Cost ($)"
FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASE_STORAGE_USAGE_HISTORY
WHERE usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
QUALIFY ROW_NUMBER() OVER (PARTITION BY database_name ORDER BY usage_date DESC) = 1
ORDER BY "Daily Cost ($)" DESC
""",

    "finops_data_transfer": """
SELECT
    target_cloud AS "Target Cloud",
    transfer_type AS "Transfer Type",
    ROUND(SUM(bytes_transferred) / POW(1024, 3), 2) AS "GB Transferred"
FROM SNOWFLAKE.ACCOUNT_USAGE.DATA_TRANSFER_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY "GB Transferred" DESC
""",

    "fv_daily_cost_trend": """
SELECT
    mdh.usage_date AS "Date",
    ROUND(SUM(mdh.credits_used_compute), 2) AS "Compute Credits",
    ROUND(SUM(mdh.credits_used_cloud_services), 2) AS "Cloud Services Credits",
    ROUND(SUM(mdh.credits_used_compute + mdh.credits_used_cloud_services), 2) AS "Total Credits",
    ROUND(SUM(mdh.credits_used_compute + mdh.credits_used_cloud_services) * 3.0, 2) AS "Total Cost ($)",
    ROUND(AVG(SUM(mdh.credits_used_compute + mdh.credits_used_cloud_services) * 3.0) OVER (
        ORDER BY mdh.usage_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS "7-Day Rolling Avg ($)"
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY mdh
WHERE mdh.usage_date >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY mdh.usage_date
ORDER BY mdh.usage_date ASC
""",

    "fv_service_type_breakdown": """
SELECT
    mdh.service_type AS "Service Type",
    ROUND(SUM(mdh.credits_used), 2) AS "Total Credits",
    ROUND(SUM(mdh.credits_used) * 3.0, 2) AS "Total Cost ($)",
    ROUND(SUM(mdh.credits_used) * 3.0 * 12, 0) AS "Est Annual Cost ($)",
    ROUND(RATIO_TO_REPORT(SUM(mdh.credits_used)) OVER () * 100, 2) AS "% of Total"
FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY mdh
WHERE mdh.usage_date >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY mdh.service_type
ORDER BY "Total Cost ($)" DESC
""",

    "finops_anomalies": """
SELECT
    date AS "Anomaly Date",
    ROUND(actual_value, 2) AS "Actual Credits",
    ROUND(forecasted_value, 2) AS "Expected Credits",
    ROUND(actual_value * 3.0, 2) AS "Actual Cost ($)",
    ROUND(forecasted_value * 3.0, 2) AS "Expected Cost ($)",
    ROUND((actual_value - forecasted_value) * 3.0, 2) AS "Overspend ($)",
    ROUND(((actual_value - forecasted_value) / NULLIF(forecasted_value, 0)) * 100, 1) AS "Deviation %"
FROM SNOWFLAKE.ACCOUNT_USAGE.ANOMALIES_DAILY
WHERE date >= DATEADD('day', -60, CURRENT_TIMESTAMP())
  AND is_anomaly = TRUE
ORDER BY date DESC
""",

    # ========================
    # finops_control.py
    # ========================

    "fc_resource_monitors": """
SELECT
    name AS monitor_name,
    credit_quota,
    notify,
    suspend,
    suspend_immediate,
    created,
    owner,
    warehouses
FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS
ORDER BY credit_quota DESC
""",

    "fc_risk_analysis": """
WITH warehouse_spend AS (
    SELECT
        warehouse_name,
        NVL(SUM(credits_used), 0) AS monthly_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY warehouse_name
),
monitor_quotas AS (
    SELECT
        name AS monitor_name,
        credit_quota
    FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS
    ),
warehouses_without_monitors AS (
    SELECT
        ws.warehouse_name,
        ws.monthly_credits
    FROM warehouse_spend ws
    WHERE ws.monthly_credits > 100
)
SELECT
    '⚠️ Warehouses without Resource Monitors (>100 credits MTD)' AS risk_category,
    NVL(COUNT(DISTINCT warehouse_name), 0) AS item_count,
    ROUND(NVL(SUM(monthly_credits), 0), 2) AS credits_or_quota,
    LISTAGG(warehouse_name, ', ') WITHIN GROUP (ORDER BY monthly_credits DESC) AS item_list
FROM warehouses_without_monitors
UNION ALL
SELECT
    '📊 Resource Monitors Configured' AS risk_category,
    NVL(COUNT(*), 0) AS item_count,
    ROUND(NVL(SUM(credit_quota), 0), 2) AS credits_or_quota,
    LISTAGG(monitor_name, ', ') WITHIN GROUP (ORDER BY credit_quota DESC) AS item_list
FROM monitor_quotas
""",

    "fc_budgets": """
SELECT
    'Total Budgets Configured' AS metric,
    NVL(COUNT(*), 0) AS count
FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
WHERE CLASS_NAME = 'BUDGET'
  AND DELETED IS NULL
""",

    "fc_budget_inventory": """
SELECT
    'Budget Details' AS section,
    NAME AS budget_name,
    DATABASE_NAME || '.' || SCHEMA_NAME AS full_path,
    CREATED AS created_date,
    OWNER_NAME AS owner,
    COMMENT
FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
WHERE CLASS_NAME = 'BUDGET'
  AND DELETED IS NULL
ORDER BY CREATED DESC
""",

    "fc_budget_stats": """
WITH budget_analysis AS (
    SELECT
        NVL(COUNT(*), 0) AS total_budgets,
        NVL(COUNT(CASE WHEN NAME = 'ACCOUNT_ROOT_BUDGET' THEN 1 END), 0) AS account_budgets,
        NVL(COUNT(CASE WHEN NAME != 'ACCOUNT_ROOT_BUDGET' THEN 1 END), 0) AS custom_budgets
    FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
    WHERE CLASS_NAME = 'BUDGET'
      AND DELETED IS NULL
)
SELECT
    'Budget Statistics' AS section,
    total_budgets,
    account_budgets,
    custom_budgets
FROM budget_analysis
""",

    "fc_budget_util": """
WITH current_month_spend AS (
    SELECT NVL(SUM(CREDITS_USED), 0) AS month_to_date_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATE_TRUNC('month', CURRENT_TIMESTAMP())
)
SELECT
    'Budget Utilization (Month-to-Date)' AS section,
    500 AS budget_limit_credits,
    s.month_to_date_credits AS current_spend_credits,
    ROUND((s.month_to_date_credits / 500) * 100, 2) AS utilization_percent,
    500 - s.month_to_date_credits AS remaining_credits,
    CASE
        WHEN (s.month_to_date_credits / 500) > 0.9 THEN 'WARNING: >90% utilized'
        WHEN (s.month_to_date_credits / 500) > 0.75 THEN 'CAUTION: >75% utilized'
        ELSE 'HEALTHY: <75% utilized'
    END AS status
FROM current_month_spend s
""",

    "fc_projection": """
WITH daily_avg AS (
    SELECT
        AVG(daily_credits) AS avg_daily_spend
    FROM (
        SELECT
            DATE(START_TIME) AS credit_date,
            NVL(SUM(CREDITS_USED), 0) AS daily_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE START_TIME >= DATEADD('day', -30, CURRENT_DATE)
        GROUP BY DATE(START_TIME)
    )
)
SELECT
    'End-of-Month Projection' AS section,
    500 AS budget_limit_credits,
    d.avg_daily_spend AS avg_daily_spend_30d,
    DAY(LAST_DAY(CURRENT_DATE)) AS days_in_month,
    DAY(CURRENT_DATE) AS days_elapsed,
    ROUND(d.avg_daily_spend * DAY(LAST_DAY(CURRENT_DATE)), 2) AS projected_month_end_credits,
    CASE
        WHEN (d.avg_daily_spend * DAY(LAST_DAY(CURRENT_DATE))) > 500
        THEN 'PROJECTED TO EXCEED BUDGET'
        WHEN (d.avg_daily_spend * DAY(LAST_DAY(CURRENT_DATE))) > 450
        THEN 'PROJECTED NEAR BUDGET LIMIT'
        ELSE 'PROJECTED WITHIN BUDGET'
    END AS projection_status
FROM daily_avg d
""",

    "fc_wh_without_controls": """
        WITH warehouse_spend AS (
            SELECT
                WAREHOUSE_NAME,
                ROUND(SUM(CREDITS_USED), 2) AS mtd_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATE_TRUNC('month', CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY WAREHOUSE_NAME
        ),
        monitored AS (
            SELECT DISTINCT OBJECT_NAME AS WAREHOUSE_NAME
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE POLICY_KIND = 'RESOURCE_MONITOR'
            UNION
            SELECT DISTINCT WAREHOUSE_NAME
            FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS rm
            WHERE rm.DELETED IS NULL
        )
        SELECT
            ws.WAREHOUSE_NAME,
            ws.mtd_credits,
            CASE WHEN m.WAREHOUSE_NAME IS NOT NULL THEN 'Monitored' ELSE 'UNMONITORED' END AS control_status
        FROM warehouse_spend ws
        LEFT JOIN monitored m ON ws.WAREHOUSE_NAME = m.WAREHOUSE_NAME
        WHERE ws.mtd_credits > 10
        ORDER BY control_status, ws.mtd_credits DESC
""",

    "fc_monitors_limits": """
        WITH monitor_spend AS (
            SELECT
                WAREHOUSE_NAME,
                SUM(CREDITS_USED) AS mtd_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATE_TRUNC('month', CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY WAREHOUSE_NAME
        )
        SELECT
            rm.NAME AS monitor_name,
            rm.CREDIT_QUOTA,
            rm.FREQUENCY,
            rm.SUSPEND_AT,
            rm.SUSPEND_IMMEDIATELY_AT,
            COALESCE(SUM(ms.mtd_credits), 0) AS mtd_credits_used,
            ROUND(COALESCE(SUM(ms.mtd_credits), 0) / NULLIF(rm.CREDIT_QUOTA, 0) * 100, 1) AS pct_quota_used,
            CASE
                WHEN COALESCE(SUM(ms.mtd_credits), 0) / NULLIF(rm.CREDIT_QUOTA, 0) >= 0.9 THEN 'CRITICAL (>90%)'
                WHEN COALESCE(SUM(ms.mtd_credits), 0) / NULLIF(rm.CREDIT_QUOTA, 0) >= 0.75 THEN 'HIGH (>75%)'
                WHEN COALESCE(SUM(ms.mtd_credits), 0) / NULLIF(rm.CREDIT_QUOTA, 0) >= 0.5 THEN 'MODERATE (>50%)'
                ELSE 'LOW (<50%)'
            END AS usage_status
        FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS rm
        LEFT JOIN monitor_spend ms ON ms.WAREHOUSE_NAME = rm.NAME
        WHERE rm.DELETED IS NULL
          AND rm.CREDIT_QUOTA > 0
        GROUP BY rm.NAME, rm.CREDIT_QUOTA, rm.FREQUENCY, rm.SUSPEND_AT, rm.SUSPEND_IMMEDIATELY_AT
        ORDER BY pct_quota_used DESC NULLS LAST
""",

    "fc_statement_timeouts": """
        SELECT
            WAREHOUSE_NAME,
            USER_NAME,
            COUNT(*) AS timeout_count,
            ROUND(AVG(TOTAL_ELAPSED_TIME) / 1000.0, 1) AS avg_elapsed_sec,
            ROUND(MAX(TOTAL_ELAPSED_TIME) / 1000.0, 1) AS max_elapsed_sec,
            DATE_TRUNC('day', MIN(START_TIME)) AS first_seen,
            DATE_TRUNC('day', MAX(START_TIME)) AS last_seen
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE ERROR_CODE = '100188'
          AND START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
          AND WAREHOUSE_NAME IS NOT NULL
        GROUP BY WAREHOUSE_NAME, USER_NAME
        ORDER BY timeout_count DESC
        LIMIT 30
""",

    "fc_always_on_wh": """
        WITH daily_usage AS (
            SELECT
                warehouse_name,
                DATE(start_time) AS usage_date,
                COUNT(DISTINCT HOUR(start_time)) AS hours_running_per_day
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
            GROUP BY warehouse_name, DATE(start_time)
        )
        SELECT
            warehouse_name,
            ROUND(AVG(hours_running_per_day), 1) AS avg_hours_per_day,
            MAX(hours_running_per_day) AS max_hours_per_day,
            COUNT(*) AS days_tracked,
            CASE
                WHEN AVG(hours_running_per_day) >= 20 THEN 'ALWAYS_ON'
                WHEN AVG(hours_running_per_day) >= 12 THEN 'HIGH_UPTIME'
                ELSE 'NORMAL'
            END AS uptime_status
        FROM daily_usage
        GROUP BY warehouse_name
        HAVING AVG(hours_running_per_day) >= 12
        ORDER BY avg_hours_per_day DESC
""",

    "fc_idle_time": """
        SELECT
            warehouse_name,
            ROUND(SUM(credits_used_compute), 2) AS total_compute_credits,
            ROUND(SUM(credits_attributed_compute_queries), 2) AS query_credits,
            ROUND(SUM(credits_used_compute) - SUM(credits_attributed_compute_queries), 2) AS idle_credits,
            ROUND(
                (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
                NULLIF(SUM(credits_used_compute), 0) * 100, 2
            ) AS idle_percent,
            CASE
                WHEN (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
                     NULLIF(SUM(credits_used_compute), 0) > 0.3 THEN 'HIGH_IDLE'
                WHEN (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
                     NULLIF(SUM(credits_used_compute), 0) > 0.15 THEN 'MODERATE_IDLE'
                ELSE 'LOW_IDLE'
            END AS idle_status
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE start_time >= DATEADD('day', -10, CURRENT_DATE)
          AND credits_attributed_compute_queries IS NOT NULL
        GROUP BY warehouse_name
        HAVING SUM(credits_used_compute) - SUM(credits_attributed_compute_queries) > 0
        ORDER BY idle_credits DESC
""",

    "fc_rm_coverage_gap": """
        WITH warehouse_spend AS (
            SELECT warehouse_name, SUM(credits_used) AS monthly_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE start_time >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY warehouse_name
        ),
        monitor_quotas AS (
            SELECT rm.name AS monitor_name, rm.credit_quota
            FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS rm
            WHERE rm.deleted IS NULL
        ),
        combined AS (
            SELECT
                'Warehouses without Resource Monitors' AS risk_category,
                COUNT(DISTINCT warehouse_name) AS item_count,
                ROUND(SUM(monthly_credits), 2) AS credits_or_quota
            FROM warehouse_spend
            WHERE monthly_credits > 100
            UNION ALL
            SELECT
                'Resource Monitors Configured' AS risk_category,
                COUNT(*) AS item_count,
                ROUND(SUM(credit_quota), 2) AS credits_or_quota
            FROM monitor_quotas
        )
        SELECT risk_category, item_count, credits_or_quota
        FROM combined
""",

    "fc_wow_cost_trend": """
        WITH weekly_data AS (
            SELECT
                warehouse_name,
                SUM(CASE WHEN start_time >= DATEADD('day', -7, CURRENT_DATE) THEN credits_used ELSE 0 END) AS current_credits,
                SUM(CASE WHEN start_time >= DATEADD('day', -14, CURRENT_DATE) AND start_time < DATEADD('day', -7, CURRENT_DATE)
                         THEN credits_used ELSE 0 END) AS previous_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE start_time >= DATEADD('day', -14, CURRENT_DATE)
            GROUP BY warehouse_name
        )
        SELECT
            warehouse_name,
            ROUND(previous_credits, 2) AS previous_week_credits,
            ROUND(current_credits, 2) AS current_week_credits,
            ROUND(current_credits - previous_credits, 2) AS credit_change,
            ROUND((current_credits - previous_credits) / NULLIF(previous_credits, 0) * 100, 2) AS percent_change,
            CASE
                WHEN (current_credits - previous_credits) / NULLIF(previous_credits, 0) > 0.5 THEN 'COST_SPIKE_GT_50PCT'
                WHEN (current_credits - previous_credits) / NULLIF(previous_credits, 0) > 0.25 THEN 'COST_INCREASE_GT_25PCT'
                ELSE 'STABLE_OR_DECREASING'
            END AS trend_status
        FROM weekly_data
        WHERE current_credits > 10 OR previous_credits > 10
        ORDER BY credit_change DESC
""",

    "fc_spending_summary": """
        SELECT
            'WAREHOUSE_METERING' AS service_type,
            ROUND(SUM(credits_used), 2) AS total_credits,
            COUNT(DISTINCT DATE(start_time)) AS days_with_activity,
            ROUND(AVG(credits_used), 4) AS avg_per_event,
            ROUND(MIN(credits_used), 4) AS min_per_event,
            ROUND(MAX(credits_used), 4) AS max_per_event
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
        UNION ALL
        SELECT
            'SERVERLESS_TASKS' AS service_type,
            ROUND(SUM(credits_used), 2) AS total_credits,
            COUNT(DISTINCT DATE(start_time)) AS days_with_activity,
            ROUND(AVG(credits_used), 4) AS avg_per_event,
            ROUND(MIN(credits_used), 4) AS min_per_event,
            ROUND(MAX(credits_used), 4) AS max_per_event
        FROM SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY
        WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
        ORDER BY total_credits DESC
""",

    "fc_monthly_trend": """
        SELECT
            DATE_TRUNC('month', start_time) AS month,
            ROUND(SUM(credits_used), 2) AS monthly_credits,
            COUNT(DISTINCT DATE(start_time)) AS days_in_month
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        GROUP BY DATE_TRUNC('month', start_time)
        ORDER BY month DESC
        LIMIT 12
""",

    "fc_serverless_costs": """
        SELECT service_type, total_credits, databases_using, executions
        FROM (
            SELECT 'SERVERLESS_TASK' AS service_type,
                   ROUND(SUM(credits_used), 2) AS total_credits,
                   COUNT(DISTINCT database_name) AS databases_using,
                   COUNT(*) AS executions
            FROM SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
            UNION ALL
            SELECT 'MATERIALIZED_VIEWS', ROUND(SUM(credits_used), 2),
                   COUNT(DISTINCT database_name), COUNT(*)
            FROM SNOWFLAKE.ACCOUNT_USAGE.MATERIALIZED_VIEW_REFRESH_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
            UNION ALL
            SELECT 'AUTO_CLUSTERING', ROUND(SUM(credits_used), 2),
                   COUNT(DISTINCT database_name), COUNT(*)
            FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
            UNION ALL
            SELECT 'SEARCH_OPTIMIZATION', ROUND(SUM(credits_used), 2),
                   COUNT(DISTINCT database_name), COUNT(*)
            FROM SNOWFLAKE.ACCOUNT_USAGE.SEARCH_OPTIMIZATION_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
        ) serverless_costs
        WHERE total_credits > 0
        ORDER BY total_credits DESC
""",

    "fc_storage_costs": """
        SELECT
            DATE_TRUNC('month', usage_date) AS month,
            ROUND(AVG(storage_bytes + stage_bytes + failsafe_bytes) / POWER(1024, 4), 4) AS avg_storage_tb
        FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
        WHERE usage_date >= DATEADD('month', -3, CURRENT_DATE)
        GROUP BY DATE_TRUNC('month', usage_date)
        ORDER BY month DESC
""",

    "fc_spcs_credits": """
        SELECT
            'SPCS Services' AS service_name,
            ROUND(SUM(credits_used), 2) AS total_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPARK_CONTAINER_SERVICES_HISTORY
        WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
""",

    "fc_dangling_budgets": """
        WITH all_budgets AS (
            SELECT
                name AS budget_name,
                database_name,
                schema_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
            WHERE class_name = 'BUDGET'
              AND deleted IS NULL
              AND name != 'ACCOUNT_ROOT_BUDGET'
        )
        SELECT
            COUNT(*) AS custom_budget_count,
            LISTAGG(budget_name, ', ') WITHIN GROUP (ORDER BY budget_name) AS budget_names
        FROM all_budgets
""",

    # ========================
    # finops_optimization.py
    # ========================

    "fo_ddl": """
WITH ddl_q AS (
  SELECT
    query_parameterized_hash,
    MIN(query_text) AS sample_text,
    NVL(COUNT(*), 0) AS executions,
    NVL(SUM(credits_used_cloud_services), 0) AS cs_credits
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND REGEXP_LIKE(query_text, '^\\\\s*(CREATE|ALTER|DROP)\\\\b', 'i')
  GROUP BY query_parameterized_hash
)
SELECT
    NVL(SUM(executions), 0) AS total_ddl_30d,
    NVL(COUNT(*), 0) AS distinct_ddl_patterns_30d
FROM ddl_q
""",

    "fo_top_ddl": """
WITH ddl_q AS (
  SELECT
    query_parameterized_hash,
    MIN(query_text) AS sample_text,
    NVL(COUNT(*), 0) AS executions,
    NVL(SUM(credits_used_cloud_services), 0) AS cs_credits
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND REGEXP_LIKE(query_text, '^\\\\s*(CREATE|ALTER|DROP)\\\\b', 'i')
  GROUP BY query_parameterized_hash
)
SELECT
    query_parameterized_hash,
    executions,
    cs_credits,
    sample_text
FROM ddl_q
ORDER BY executions DESC
LIMIT 10
""",

    "fo_cloning": """
SELECT
    query_type,
    REGEXP_SUBSTR(query_text, ' (TABLE|VIEW|SCHEMA|DATABASE) [IF EXISTS ]*([a-zA-Z0-9_.]+)', 1, 1, 'i', 2) AS object_name,
    user_name,
    NVL(COUNT(*), 0) AS operation_count,
    NVL(SUM(credits_used_cloud_services), 0) AS cloud_services_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type IN ('CREATE_TABLE', 'DROP_TABLE', 'CREATE_VIEW', 'ALTER_TABLE', 'RESTORE', 'CREATE_TABLE_AS_SELECT')
  AND query_text ILIKE '%CLONE%'
GROUP BY ALL
ORDER BY operation_count DESC
LIMIT 10
""",

    "fo_clone_summary": """
WITH clone_q AS (
  SELECT
    query_parameterized_hash,
    MIN(query_text) AS sample_text,
    NVL(COUNT(*), 0) AS executions,
    NVL(SUM(credits_used_cloud_services), 0) AS cs_credits
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND REGEXP_LIKE(query_text, '\\\\bCLONE\\\\b', 'i')
  GROUP BY query_parameterized_hash
)
SELECT
    NVL(SUM(executions), 0) AS total_clone_30d,
    NVL(COUNT(*), 0) AS distinct_clone_patterns_30d
FROM clone_q
""",

    "fo_top_clone": """
WITH clone_q AS (
  SELECT
    query_parameterized_hash,
    MIN(query_text) AS sample_text,
    NVL(COUNT(*), 0) AS executions,
    NVL(SUM(credits_used_cloud_services), 0) AS cs_credits
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND REGEXP_LIKE(query_text, '\\\\bCLONE\\\\b', 'i')
  GROUP BY query_parameterized_hash
)
SELECT
    query_parameterized_hash,
    executions,
    cs_credits,
    sample_text
FROM clone_q
ORDER BY executions DESC
LIMIT 10
""",

    "fo_simple_queries": """
SELECT
    'Short Queries (<100ms)' AS pattern_type,
    REGEXP_REPLACE(q.query_text, '\\\\b\\\\d+\\\\b', '?') AS query_template,
    q.user_name,
    s.client_application_id AS client_tool,
    NVL(COUNT(*), 0) AS execution_count,
    NVL(SUM(q.credits_used_cloud_services), 0) AS cloud_services_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history q
JOIN SNOWFLAKE.ACCOUNT_USAGE.sessions s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND q.total_elapsed_time < 100
  AND q.query_type = 'SELECT'
GROUP BY ALL
HAVING NVL(COUNT(*), 0) > 1000
ORDER BY execution_count DESC
LIMIT 10
""",

    "fo_info_schema": """
SELECT
    'Metadata Scan' AS pattern_type,
    q.user_name,
    s.client_application_id AS client_tool,
    SUBSTR(q.query_text, 1, 80) AS query_preview,
    NVL(COUNT(*), 0) AS execution_count,
    NVL(AVG(q.compilation_time), 0) AS avg_compile_ms
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history q
JOIN SNOWFLAKE.ACCOUNT_USAGE.sessions s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (q.schema_name = 'INFORMATION_SCHEMA' OR q.query_text ILIKE '%INFORMATION_SCHEMA%')
GROUP BY ALL
ORDER BY execution_count DESC
LIMIT 10
""",

    "fo_show_commands": """
SELECT
    q.query_type,
    SUBSTR(q.query_text, 1, 50) AS command_type,
    q.user_name,
    s.client_application_id AS client_tool,
    NVL(COUNT(*), 0) AS execution_count
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history q
JOIN SNOWFLAKE.ACCOUNT_USAGE.sessions s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND q.query_type = 'SHOW'
GROUP BY ALL
ORDER BY execution_count DESC
LIMIT 10
""",

    "fo_single_row_inserts": """
SELECT
    'Single Row Insert' AS pattern_type,
    REGEXP_SUBSTR(query_text, 'INSERT INTO ([a-zA-Z0-9_.]+)', 1, 1, 'i', 1) AS target_table,
    user_name,
    NVL(COUNT(*), 0) AS insert_count,
    NVL(SUM(rows_produced), 0) AS total_rows_loaded
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type = 'INSERT'
  AND rows_produced = 1
GROUP BY ALL
ORDER BY insert_count DESC
LIMIT 10
""",

    "fo_complex_queries": """
SELECT
    'Complex Compilation' AS pattern_type,
    query_id,
    user_name,
    LENGTH(query_text) AS sql_character_length,
    compilation_time AS compile_ms,
    execution_time AS exec_ms,
    ROUND(NVL(compilation_time, 0) / (NVL(total_elapsed_time, 0) * 100), 1) AS pct_time_compiling
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND compilation_time > 5000
ORDER BY compilation_time DESC
LIMIT 10
""",

    "fo_summary": """
        WITH copy_q AS (
            SELECT
                QUERY_PARAMETERIZED_HASH,
                MIN(QUERY_TEXT) AS sample_text,
                COUNT(*) AS executions,
                SUM(CREDITS_USED_CLOUD_SERVICES) AS cs_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME > DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND REGEXP_LIKE(QUERY_TEXT, '^\\s*COPY\\s+INTO\\b', 'i')
            GROUP BY QUERY_PARAMETERIZED_HASH
        )
        SELECT
            SUM(executions) AS total_copy_commands_30d,
            COUNT(*) AS distinct_copy_patterns,
            ROUND(SUM(cs_credits), 4) AS total_cloud_services_credits
        FROM copy_q
""",

    "fo_patterns": """
        SELECT
            SUBSTR(QUERY_TEXT, 1, 120) AS query_pattern,
            COUNT(*) AS execution_count,
            SUM(ROWS_PRODUCED) AS total_rows_loaded,
            ROUND(AVG(COMPILATION_TIME), 0) AS avg_compile_ms,
            ROUND(AVG(EXECUTION_TIME), 0) AS avg_execution_ms,
            ROUND(SUM(CREDITS_USED_CLOUD_SERVICES), 4) AS cloud_services_credits,
            CASE
                WHEN AVG(COMPILATION_TIME) > 5000 THEN 'HIGH_FILE_LISTING_OVERHEAD'
                WHEN COUNT(*) > 100 AND SUM(ROWS_PRODUCED) < 1000 THEN 'REDUNDANT_PATTERN'
                ELSE 'INVESTIGATE'
            END AS issue_type
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
          AND QUERY_TYPE = 'COPY'
          AND EXECUTION_TIME > 1000
          AND ROWS_PRODUCED < 100
        GROUP BY SUBSTR(QUERY_TEXT, 1, 120)
        ORDER BY execution_count DESC
        LIMIT 10
""",

    "fo_cloud_svcs_overhead": """
        WITH pattern_summary AS (
            SELECT 'SHOW Commands' AS pattern, SUM(credits_used_cloud_services) AS credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND query_type = 'SHOW'
            UNION ALL
            SELECT 'Short Queries (<100ms)', SUM(credits_used_cloud_services)
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND total_elapsed_time < 100
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
            pattern,
            ROUND(credits, 4) AS cloud_services_credits_30d,
            ROUND(credits * 3.00, 2) AS estimated_cost_usd,
            ROUND(RATIO_TO_REPORT(credits) OVER () * 100, 1) AS pct_of_overhead
        FROM pattern_summary
        WHERE credits > 0
        ORDER BY credits DESC
""",

}

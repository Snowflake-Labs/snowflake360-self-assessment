_ALL_TF_QUERIES = {
    "tf_overview": """
WITH
-- 1. Clustered vs unclustered base tables
clustered_tables AS (
  SELECT
    SUM(CASE WHEN clustering_key IS NOT NULL THEN 1 ELSE 0 END) AS clustered_tables,
    SUM(CASE WHEN clustering_key IS NULL  THEN 1 ELSE 0 END)    AS unclustered_tables
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE table_type = 'BASE TABLE'
    AND deleted IS NULL
),

-- 2. Materialized views (defined)
materialized_views AS (
  SELECT COUNT(*) AS num_materialized_views
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE table_type = 'MATERIALIZED VIEW'
    AND deleted IS NULL
),

-- 3. Tables with semi-structured columns (VARIANT/OBJECT/ARRAY)
semi_structured_tables AS (
  SELECT
    COUNT(DISTINCT c.table_catalog || '.' || c.table_schema || '.' || c.table_name)
      AS num_tables_with_semi_structured
  FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS c
  JOIN SNOWFLAKE.ACCOUNT_USAGE.TABLES  t
    ON c.table_id = t.table_id
  WHERE t.table_type = 'BASE TABLE'
    AND t.deleted IS NULL
    AND c.deleted IS NULL
    AND c.data_type IN ('VARIANT','OBJECT','ARRAY')
),

-- 4. Dynamic tables
dynamic_tables AS (
  SELECT COUNT(*) AS num_dynamic_tables
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE is_dynamic = 'YES'
    AND deleted IS NULL
),

-- 5. Hybrid tables
hybrid_tables AS (
  SELECT COUNT(*) AS num_hybrid_tables
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE (is_hybrid = 'YES')
    AND deleted IS NULL
),

-- 6. Event tables
event_tables AS (
  SELECT COUNT(*) AS num_event_tables
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE table_type = 'EVENT TABLE'
    AND deleted IS NULL
),

-- 7. Semantic views
semantic_views AS (
  SELECT COUNT(*) AS num_semantic_views
  FROM SNOWFLAKE.ACCOUNT_USAGE.SEMANTIC_VIEWS
  WHERE deleted IS NULL
),

-- 8. Warehouses with spilling or high queueing in last 30 days
spill_or_queue_wh AS (
  SELECT
    COUNT(DISTINCT warehouse_name) AS num_warehouses_spill_or_queue_last_30d
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND warehouse_name IS NOT NULL
    AND (
         bytes_spilled_to_remote_storage > 0
      OR bytes_spilled_to_local_storage  > 0
      OR queued_overload_time            > 0
    )
),

-- 9. Short UPSERTs (MERGE with few rows affected) in last 30 days
short_upserts AS (
  SELECT
    COUNT(*) AS num_short_upserts_last_30d
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND query_type = 'MERGE'
    AND (rows_inserted + rows_updated) BETWEEN 1 AND 1000
),

-- 10. Snowpark queries in last 30 days (by client_application_id)
snowpark_queries AS (
  SELECT
    COUNT(DISTINCT q.query_id) AS num_snowpark_queries_last_30d
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
  JOIN SNOWFLAKE.ACCOUNT_USAGE.SESSIONS     s
    ON q.session_id = s.session_id
  WHERE q.start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND s.client_application_id ILIKE 'SNOWPARK%'
),

-- 11. Data clustering: tables with clustering keys and auto clustering ON
clustered_data AS (
  SELECT
    COUNT(*) AS num_clustered_tables_with_key,
    SUM(CASE WHEN auto_clustering_on = 'ON' THEN 1 ELSE 0 END)
      AS num_tables_with_auto_clustering
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE table_type = 'BASE TABLE'
    AND deleted IS NULL
    AND clustering_key IS NOT NULL
),

-- 12. High cloud services usage days in last 30 days
high_cloud_services AS (
  SELECT
    COUNT(*) AS num_wh_days_high_cloud_services_last_30d
  FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND credits_used_cloud_services > 10
)

SELECT
  -- Clustered vs unclustered tables
  ct.clustered_tables,
  ct.unclustered_tables,

  -- Materialized views
  mv.num_materialized_views,

  -- Semi-structured tables
  ss.num_tables_with_semi_structured,

  -- Dynamic, hybrid, event tables
  dt.num_dynamic_tables,
  ht.num_hybrid_tables,
  et.num_event_tables,

  -- Semantic views
  sv.num_semantic_views,

  -- Spill / high queue
  w.num_warehouses_spill_or_queue_last_30d,

  -- Short upserts
  su.num_short_upserts_last_30d,

  -- Snowpark
  sp.num_snowpark_queries_last_30d,

  -- Data clustering
  cd.num_clustered_tables_with_key,
  cd.num_tables_with_auto_clustering,

  -- High cloud services usage
  hc.num_wh_days_high_cloud_services_last_30d

FROM clustered_tables     ct
CROSS JOIN materialized_views mv
CROSS JOIN semi_structured_tables ss
CROSS JOIN dynamic_tables   dt
CROSS JOIN hybrid_tables    ht
CROSS JOIN event_tables     et
CROSS JOIN semantic_views   sv
CROSS JOIN spill_or_queue_wh w
CROSS JOIN short_upserts    su
CROSS JOIN snowpark_queries sp
CROSS JOIN clustered_data   cd
CROSS JOIN high_cloud_services hc
        """,
    "dt_object_lifecycle": """
        SELECT
            CASE
                WHEN DATEDIFF('day', created, CURRENT_TIMESTAMP()) <= 30 THEN '0-30 days'
                WHEN DATEDIFF('day', created, CURRENT_TIMESTAMP()) <= 90 THEN '31-90 days'
                WHEN DATEDIFF('day', created, CURRENT_TIMESTAMP()) <= 365 THEN '91-365 days'
                ELSE '365+ days'
            END AS age_bucket,
            table_type,
            COUNT(*) AS object_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
        WHERE deleted IS NULL
          AND table_catalog != 'SNOWFLAKE'
          AND table_schema != 'INFORMATION_SCHEMA'
        GROUP BY age_bucket, table_type
        ORDER BY age_bucket, object_count DESC
        """,
    "dt_micro_tx": """
        SELECT
            warehouse_name,
            database_name,
            COUNT(*) AS short_upsert_count,
            ROUND(AVG(total_elapsed_time), 1) AS avg_elapsed_ms,
            ROUND(SUM(credits_used_cloud_services), 4) AS cloud_services_credits,
            COUNT(DISTINCT user_name) AS distinct_users
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
          AND query_type IN ('MERGE', 'UPDATE', 'INSERT')
          AND total_elapsed_time < 500
          AND rows_produced <= 10
        GROUP BY warehouse_name, database_name
        HAVING COUNT(*) > 50
        ORDER BY short_upsert_count DESC
        LIMIT 20
        """,
    "tf_problematic_queries": """
SELECT
    i.insight_type_id AS insight_code,
    -- Categorize for readability
    CASE
        WHEN i.insight_type_id ILIKE '%SPILL%' THEN '\u26a0\ufe0f Memory Pressure'
        WHEN i.insight_type_id ILIKE '%EXPLODING%' THEN '\U0001f525 Cardinality Explosion'
        WHEN i.insight_type_id ILIKE '%FILTER%' OR i.insight_type_id ILIKE '%SCAN%' THEN '\U0001f50d Pruning/Scanning Issues'
        WHEN i.insight_type_id ILIKE '%JOIN%' THEN '\U0001f517 Join Logic Issues'
        WHEN i.insight_type_id ILIKE '%UNION%' OR i.insight_type_id ILIKE '%AGGREGATE%' THEN '\U0001f9ee Logic Inefficiency'
        WHEN i.insight_type_id ILIKE '%SEARCH_OPTIMIZATION%' THEN '\u26a1 Search Opt Opportunity'
        ELSE 'Other'
    END AS category,
    COUNT(*) AS occurrence_count,
    COUNT(DISTINCT i.query_id) AS distinct_queries,
    MAX(q.query_text) AS example_query
FROM SNOWFLAKE.ACCOUNT_USAGE.query_insights i
JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
    ON i.query_id = q.query_id
WHERE i.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY 3 DESC
        """,
    "tf_category_summary": """
SELECT
    -- 1. Define the Categories
    CASE
        WHEN insight_type_id ILIKE '%SPILL%' THEN '\u26a0\ufe0f Memory Pressure'
        WHEN insight_type_id ILIKE '%EXPLODING%' THEN '\U0001f525 Cardinality Explosion'
        WHEN insight_type_id ILIKE '%FILTER%' OR insight_type_id ILIKE '%SCAN%' THEN '\U0001f50d Pruning/Scanning Issues'
        WHEN insight_type_id ILIKE '%JOIN%' THEN '\U0001f517 Join Logic Issues'
        WHEN insight_type_id ILIKE '%UNION%' OR insight_type_id ILIKE '%AGGREGATE%' THEN '\U0001f9ee Logic Inefficiency'
        WHEN insight_type_id ILIKE '%SEARCH_OPTIMIZATION%' THEN '\u26a1 Search Opt Opportunity'
        ELSE 'Other'
    END AS problem_category,

    -- 2. Aggregate the Counts
    COUNT(*) AS total_occurrences,
    COUNT(DISTINCT query_id) AS distinct_queries_affected,

    -- 3. List the specific codes caught in this bucket (for reference)
    ARRAY_AGG(DISTINCT insight_type_id) WITHIN GROUP (ORDER BY insight_type_id) AS specific_insight_codes

FROM SNOWFLAKE.ACCOUNT_USAGE.query_insights
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY 2 DESC
        """,
    "tf_syntax_hunter": """
SELECT
    query_id,
    SUBSTR(query_text, 1, 200) AS query_preview,

    -- 1. ASOF JOIN
    CASE
        WHEN query_text ILIKE '%ASOF JOIN%' THEN '\u2705 Yes'
        ELSE 'No'
    END AS uses_asof_join,

    -- 2. COLLATION
    CASE
        WHEN query_text ILIKE '%COLLATE%' THEN '\u2705 Yes'
        ELSE 'No'
    END AS uses_collation,

    -- 3. DIRECTED JOINS (Look for "JOIN +")
    CASE
        WHEN REGEXP_LIKE(query_text, '.*JOIN\\\\s*\\\\+.*', 'i') THEN '\u2705 Yes'
        ELSE 'No'
    END AS uses_directed_join,

    -- 4. ORDER BY in CTE (Heuristic: WITH ... ORDER BY ... SELECT)
    CASE
        WHEN REGEXP_LIKE(query_text, '.*WITH.*ORDER BY.*SELECT.*', 'is') THEN '\u2705 Yes'
        ELSE 'No'
    END AS order_by_in_cte,

    -- 5. ORDER BY with GROUP BY
    CASE
        WHEN query_text ILIKE '%GROUP BY%' AND query_text ILIKE '%ORDER BY%' THEN '\u2705 Yes'
        ELSE 'No'
    END AS sort_and_agg,

    -- 6. DISTINCT vs APPROX CANDIDATE
    CASE
        WHEN query_text ILIKE '%DISTINCT%' AND bytes_scanned > 1024*1024*1024
        THEN '\u26a0\ufe0f Consider APPROX'
        ELSE '-'
    END AS distinct_optimization_check

FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND (
      query_text ILIKE '%ASOF JOIN%' OR
      query_text ILIKE '%COLLATE%' OR
      query_text ILIKE '%DISTINCT%' OR
      query_text ILIKE '%+%' OR
      query_text ILIKE '%ORDER BY%'
  )
LIMIT 100
        """,
    "tf_syntax_frequency": """
WITH feature_flags AS (
    SELECT
        -- 1. ASOF JOIN
        CASE
            WHEN query_text ILIKE '%ASOF JOIN%' THEN 1
            ELSE 0
        END AS uses_asof_join,

        -- 2. COLLATION
        CASE
            WHEN query_text ILIKE '%COLLATE%' THEN 1
            ELSE 0
        END AS uses_collation,

        -- 3. DIRECTED JOINS ("JOIN +")
        CASE
            WHEN REGEXP_LIKE(query_text, '.*JOIN\\\\s*\\\\+.*', 'i') THEN 1
            ELSE 0
        END AS uses_directed_join,

        -- 4. ORDER BY IN CTE (Inefficiency)
        CASE
            WHEN REGEXP_LIKE(query_text, '.*WITH.*ORDER BY.*SELECT.*', 'is') THEN 1
            ELSE 0
        END AS order_by_in_cte,

        -- 5. ORDER BY + GROUP BY (Heavy Compute)
        CASE
            WHEN query_text ILIKE '%GROUP BY%' AND query_text ILIKE '%ORDER BY%' THEN 1
            ELSE 0
        END AS sort_and_agg,

        -- 6. HEAVY DISTINCT (>1GB Scanned)
        CASE
            WHEN query_text ILIKE '%DISTINCT%' AND bytes_scanned > 1024*1024*1024 THEN 1
            ELSE 0
        END AS heavy_distinct

    FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
    WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND (
          query_text ILIKE '%ASOF JOIN%' OR
          query_text ILIKE '%COLLATE%' OR
          query_text ILIKE '%DISTINCT%' OR
          query_text ILIKE '%+%' OR
          query_text ILIKE '%ORDER BY%'
      )
)
, aggr as (
SELECT 'Sort + Aggregate (Heavy Compute)' AS detection_type, SUM(sort_and_agg) AS occurrence_count FROM feature_flags
UNION ALL
SELECT 'Order By inside CTE (Likely Redundant)', SUM(order_by_in_cte) FROM feature_flags
UNION ALL
SELECT 'Heavy Distinct (>1GB Scanned)', SUM(heavy_distinct) FROM feature_flags
UNION ALL
SELECT 'Directed Join Hints ("+")', SUM(uses_directed_join) FROM feature_flags
UNION ALL
SELECT 'ASOF Join Used', SUM(uses_asof_join) FROM feature_flags
UNION ALL
SELECT 'Collation Used', SUM(uses_collation) FROM feature_flags
)
SELECT a.*
FROM aggr a
ORDER BY occurrence_count DESC
        """,
    "tf_view_dependency": """
WITH RECURSIVE view_lineage AS (
    -- Anchor: Base Views
    SELECT
        referencing_database || '.' || referencing_schema || '.' || referencing_object_name AS parent_view,
        referenced_database || '.' || referenced_schema || '.' || referenced_object_name AS child_object,
        1 AS depth
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies
    WHERE referencing_object_domain = 'VIEW'

    UNION ALL

    -- Recursive Step: Find views that reference the previous level
    SELECT
        od.referencing_database || '.' || od.referencing_schema || '.' || od.referencing_object_name,
        vl.child_object,
        vl.depth + 1
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies od
    JOIN view_lineage vl
        ON od.referenced_database || '.' || od.referenced_schema || '.' || od.referenced_object_name = vl.parent_view
    WHERE vl.depth < 10 -- Safety limit
)
SELECT
    parent_view AS root_view,
    MAX(depth) AS max_depth
FROM view_lineage
GROUP BY parent_view
HAVING MAX(depth) > 2 -- Show only "Deep" stacks
ORDER BY max_depth DESC
        """,
    "tf_lifecycle": """
WITH lifecycle_data AS (
    SELECT
        table_name AS object_name,
        table_type,
        'NO' AS is_secure,
        CASE
            WHEN table_type = 'TEMPORARY' THEN '\u2705 Temp Table'
            WHEN deleted IS NOT NULL AND DATEDIFF('minute', created, deleted) < 60 THEN '\u26a0\ufe0f Short-Lived (Non-Temp)'
            ELSE 'Standard'
        END AS lifespan_check
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE (deleted IS NOT NULL OR table_type = 'TEMPORARY')

    UNION ALL

    SELECT
        table_name AS object_name,
        'VIEW' AS table_type,
        is_secure,
        'Standard' AS lifespan_check
    FROM SNOWFLAKE.ACCOUNT_USAGE.views
    WHERE is_secure = 'YES'
)
SELECT * FROM lifecycle_data
ORDER BY lifespan_check, table_type, object_name
LIMIT 5000
        """,
    "tf_summary": """
WITH RECURSIVE view_lineage AS (
    -- 1. STACKED VIEW DETECTION
    -- Anchor: Base Views
    SELECT
        referencing_database || '.' || referencing_schema || '.' || referencing_object_name AS parent_view,
        referenced_database || '.' || referenced_schema || '.' || referenced_object_name AS child_object,
        1 AS depth
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies
    WHERE referencing_object_domain = 'VIEW'

    UNION ALL

    -- Recursive Step
    SELECT
        od.referencing_database || '.' || od.referencing_schema || '.' || od.referencing_object_name,
        vl.child_object,
        vl.depth + 1
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies od
    JOIN view_lineage vl
        ON od.referenced_database || '.' || od.referenced_schema || '.' || od.referenced_object_name = vl.parent_view
    WHERE vl.depth < 10
),
view_depth_stats AS (
    SELECT
        parent_view,
        MAX(depth) AS max_depth
    FROM view_lineage
    GROUP BY 1
),
lifecycle_stats AS (
    -- 2. OBJECT LIFECYCLE (Temp, Short-Lived, Secure)
    SELECT
        CASE
            WHEN table_type = 'TEMPORARY' THEN 'Temporary Tables (Session Scope)'
            WHEN deleted IS NOT NULL AND DATEDIFF('minute', created, deleted) < 60 THEN 'Short-Lived Tables (<1hr)'
            ELSE NULL
        END AS category
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE (deleted IS NOT NULL OR table_type = 'TEMPORARY')

    UNION ALL

    SELECT
        'Secure Views' AS category
    FROM SNOWFLAKE.ACCOUNT_USAGE.views
    WHERE is_secure = 'YES'
)

-- 3. FINAL AGGREGATION
SELECT
    'Stacked Views (Depth 3-5)' AS metric_name,
    COUNT(*) AS count_objects
FROM view_depth_stats
WHERE max_depth BETWEEN 3 AND 5

UNION ALL

SELECT
    'Stacked Views (Depth > 5)',
    COUNT(*)
FROM view_depth_stats
WHERE max_depth > 5

UNION ALL

SELECT
    category,
    COUNT(*)
FROM lifecycle_stats
WHERE category IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
        """,
    "tf_workload_shape": """
SELECT
    -- Normalize query to group repeated UPDATE statements
    REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?') AS query_pattern,
    COUNT(*) AS execution_count,
    AVG(execution_time) AS avg_duration_ms,
    CASE
        WHEN AVG(execution_time) < 500 AND COUNT(*) > 100 THEN '\u26a0\ufe0f Micro-Updates (Batch these!)'
        ELSE 'OK'
    END AS recommendation
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE query_type IN ('UPDATE', 'INSERT', 'DELETE')
  AND start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY ALL
HAVING count(*) > 50
ORDER BY 2 DESC
""",
    "tf_rap_query": """
SELECT
    pr.policy_name,
    pr.ref_entity_name AS protected_table,
    COUNT(DISTINCT q.query_id) AS slow_query_count,
    AVG(q.execution_time) AS avg_execution_ms
FROM SNOWFLAKE.ACCOUNT_USAGE.policy_references pr
JOIN SNOWFLAKE.ACCOUNT_USAGE.access_history ah
    ON ah.query_start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
    ON ah.query_id = q.query_id
    AND q.execution_time > 5000 -- Queries taking > 5 seconds
WHERE pr.policy_kind = 'ROW_ACCESS_POLICY'
GROUP BY 1, 2
ORDER BY 3 DESC
""",
    "tf_mv_refresh_cost": """
SELECT
    table_name AS mv_name,
    COUNT(*) AS refresh_count,
    SUM(credits_used) AS refresh_cost_credits,
    AVG(credits_used) AS avg_cost_per_refresh
FROM SNOWFLAKE.ACCOUNT_USAGE.materialized_view_refresh_history
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY 3 DESC
""",
    "tf_perf_insights": """
WITH micro_updates AS (
    -- A. AGGREGATE MICRO-UPDATES
    SELECT
        COUNT(*) AS total_executions,
        COUNT(DISTINCT REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?')) AS unique_patterns
    FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
    WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND query_type IN ('UPDATE', 'INSERT', 'DELETE')
      AND execution_time < 500 -- < 500ms
),
rap_impact AS (
    -- B. AGGREGATE RAP PERFORMANCE (Fixed Join Logic)
    -- Counts queries > 5s that touched a table protected by a Row Access Policy
    SELECT
        COUNT(DISTINCT q.query_id) AS slow_protected_queries,
        AVG(q.execution_time) / 1000 AS avg_duration_sec
    FROM SNOWFLAKE.ACCOUNT_USAGE.access_history ah
    JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
        ON ah.query_id = q.query_id
    -- Flatten accessed objects to match them against Policy References
    , LATERAL FLATTEN(ah.direct_objects_accessed) f
    JOIN SNOWFLAKE.ACCOUNT_USAGE.policy_references pr
        ON f.value:objectName::STRING = pr.ref_entity_name
    WHERE ah.query_start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND q.execution_time > 5000 -- Only slow queries
      AND pr.policy_kind = 'ROW_ACCESS_POLICY'
),
mv_churn AS (
    -- C. AGGREGATE MATERIALIZED VIEW COSTS
    SELECT
        COUNT(DISTINCT table_name) AS active_mvs,
        SUM(credits_used) AS total_maintenance_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.materialized_view_refresh_history
    WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
)

-- FINAL DASHBOARD OUTPUT
, AGGR AS (
SELECT
    'Micro-Updates (Short Modifies)' AS metric_category,
    'Total Executions (<500ms)' AS metric_name,
    total_executions::STRING AS value
FROM micro_updates

UNION ALL

SELECT
    'Micro-Updates (Short Modifies)',
    'Distinct Patterns Detected',
    unique_patterns::STRING
FROM micro_updates

UNION ALL

SELECT
    'Row Access Policies (Security)',
    'Slow Queries on Protected Tables (>5s)',
    slow_protected_queries::STRING
FROM rap_impact

UNION ALL

SELECT
    'Materialized Views',
    'Total Refresh Cost (Credits)',
    ROUND(total_maintenance_credits, 2)::STRING
FROM mv_churn

UNION ALL

SELECT
    'Materialized Views',
    'Active MVs Refreshed',
    active_mvs::STRING
FROM mv_churn)

SELECT
     A.*
     FROM AGGR A
""",
    "tf_view_dependency_v2": """
WITH RECURSIVE view_lineage AS (
    SELECT
        referencing_database || '.' || referencing_schema || '.' || referencing_object_name AS parent_view,
        referenced_database || '.' || referenced_schema || '.' || referenced_object_name AS child_object,
        1 AS depth
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies
    WHERE referencing_object_domain = 'VIEW'
    UNION ALL
    SELECT
        od.referencing_database || '.' || od.referencing_schema || '.' || od.referencing_object_name,
        vl.child_object,
        vl.depth + 1
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies od
    JOIN view_lineage vl
        ON od.referenced_database || '.' || od.referenced_schema || '.' || od.referenced_object_name = vl.parent_view
    WHERE vl.depth < 10
),
view_depths AS (
    SELECT parent_view AS root_view, MAX(depth) AS max_depth
    FROM view_lineage
    GROUP BY parent_view
)
SELECT
    root_view,
    max_depth,
    CASE
        WHEN max_depth > 5 THEN 'CRITICAL_DEPTH'
        WHEN max_depth > 3 THEN 'HIGH_DEPTH'
        ELSE 'MODERATE_DEPTH'
    END AS depth_severity,
    CASE
        WHEN max_depth > 5 THEN 'Refactor to reduce view nesting - consider materialized views'
        WHEN max_depth > 3 THEN 'Review if intermediate views can be consolidated'
        ELSE 'Acceptable depth'
    END AS recommendation
FROM view_depths
WHERE max_depth > 2
ORDER BY max_depth DESC
        """,
    "tf_workload_shape_v2": """
SELECT
    REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?') AS query_pattern,
    query_type,
    COUNT(*) AS execution_count,
    ROUND(AVG(execution_time), 2) AS avg_duration_ms,
    SUM(rows_inserted + rows_updated + rows_deleted) AS total_rows_affected,
    CASE
        WHEN AVG(execution_time) < 500 AND COUNT(*) > 100 THEN '\u26a0\ufe0f Micro-Updates (Batch these!)'
        WHEN COUNT(*) > 50 THEN '\u2705 Frequent Pattern'
        ELSE 'OK'
    END AS recommendation
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE query_type IN ('UPDATE', 'INSERT', 'DELETE')
  AND start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?'), query_type
HAVING COUNT(*) > 50
ORDER BY execution_count DESC
LIMIT 20
        """,
    "tf_mv_inventory": """
SELECT
    table_catalog || '.' || table_schema || '.' || table_name AS mv_name,
    ROUND(COALESCE(bytes, 0) / POW(1024, 3), 4) AS size_gb,
    COALESCE(row_count, 0) AS row_count,
    created::DATE AS created_date
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE table_type = 'MATERIALIZED VIEW'
  AND deleted IS NULL
ORDER BY bytes DESC NULLS LAST
LIMIT 100
        """,
    "tf_lifecycle_agg": """
WITH short_lived AS (
    SELECT 'SHORT_LIVED' AS lifespan_category, COUNT(*) AS object_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
    WHERE deleted IS NOT NULL
      AND DATEDIFF('minute', created, deleted) < 60
      AND table_type != 'TEMPORARY'
),
secure_views AS (
    SELECT 'SECURE_VIEW' AS lifespan_category, COUNT(*) AS object_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.VIEWS
    WHERE is_secure = 'YES' AND deleted IS NULL
),
temp_tables AS (
    SELECT 'TEMP_TABLE' AS lifespan_category, COUNT(*) AS object_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
    WHERE table_type = 'TEMPORARY' AND deleted IS NULL
)
SELECT * FROM short_lived
UNION ALL SELECT * FROM secure_views
UNION ALL SELECT * FROM temp_tables
ORDER BY object_count DESC
        """,
}

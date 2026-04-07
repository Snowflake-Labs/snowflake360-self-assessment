# Auto-generated: SQL queries for Database Overview parallel prefetch
ALL_DB_OVERVIEW_QUERIES = {
    "db_overview_1_total_storage_query": """
        SELECT
            ROUND(SUM(active_bytes) / POWER(2, 40), 6) AS active_storage_tb,
            ROUND(SUM(time_travel_bytes) / POWER(2, 40), 6) AS time_travel_storage_tb,
            ROUND(SUM(failsafe_bytes) / POWER(2, 40), 6) AS failsafe_storage_tb,
            ROUND(SUM(retained_for_clone_bytes) / POWER(2, 40), 6) AS retained_for_clone_storage_tb
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
        WHERE deleted = FALSE
""",

    "db_overview_2_storage_summary_query": """
            SELECT
                ROUND(SUM(active_bytes) / POWER(2, 40), 6) AS active_storage_tb,
                ROUND(SUM(time_travel_bytes) / POWER(2, 40), 6) AS time_travel_storage_tb,
                ROUND(SUM(failsafe_bytes) / POWER(2, 40), 6) AS failsafe_storage_tb,
                ROUND(SUM(retained_for_clone_bytes) / POWER(2, 40), 6) AS clone_storage_tb,
                COUNT(DISTINCT table_catalog) as database_count,
                COUNT(*) as table_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
            WHERE deleted = FALSE
""",

    "db_overview_3_db_storage_query": """
            SELECT
                table_catalog AS database_name,
                ROUND(SUM(active_bytes) / POWER(2, 40), 6) AS active_storage_tb,
                ROUND(SUM(time_travel_bytes) / POWER(2, 40), 6) AS time_travel_tb,
                ROUND(SUM(failsafe_bytes) / POWER(2, 40), 6) AS failsafe_tb,
                ROUND(SUM(retained_for_clone_bytes) / POWER(2, 40), 6) AS clone_tb,
                active_storage_tb + time_travel_tb + failsafe_tb + clone_tb AS total_storage_tb,
                COUNT(*) as table_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
            WHERE deleted = FALSE
GROUP BY 1
            HAVING total_storage_tb > 0
            ORDER BY total_storage_tb DESC
            """,

    "db_overview_4_top_tables_query": """
            SELECT
                table_catalog || '.' || table_schema || '.' || table_name AS full_table_name,
                table_catalog AS database_name,
                table_schema AS schema_name,
                table_name,
                ROUND(active_bytes / POWER(2, 30), 4) AS active_storage_gb,
                ROUND(time_travel_bytes / POWER(2, 30), 4) AS time_travel_gb,
                ROUND(failsafe_bytes / POWER(2, 30), 4) AS failsafe_gb,
                ROUND((active_bytes + time_travel_bytes + failsafe_bytes) / POWER(2, 30), 4) AS total_gb
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
            WHERE deleted = FALSE
ORDER BY total_gb DESC
            LIMIT 50
            """,

    "db_overview_5_clustering_overview_query": """
            SELECT
                COUNT(*) as total_tables,
                COUNT(CASE WHEN clustering_key IS NOT NULL THEN 1 END) as clustered_tables,
                COUNT(CASE WHEN clustering_key IS NULL THEN 1 END) as unclustered_tables,
                ROUND(COUNT(CASE WHEN clustering_key IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) as cluster_percentage
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE deleted IS NULL
            AND table_schema != 'INFORMATION_SCHEMA'
            AND table_type = 'BASE TABLE'
            """,

    "db_overview_6_clustered_tables_query": """
            SELECT
                table_catalog || '.' || table_schema || '.' || table_name AS full_table_name,
                table_catalog AS database_name,
                clustering_key,
                row_count,
                ROUND(bytes / POWER(1024, 3), 2) AS size_gb,
                auto_clustering_on,
                created
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE deleted IS NULL
            AND clustering_key IS NOT NULL
            ORDER BY size_gb DESC
            LIMIT 100
            """,

    "db_overview_7_credit_history_query": """
            SELECT
                DATE_TRUNC('day', start_time) AS cluster_date,
                ROUND(SUM(credits_used), 2) AS daily_credits,
                COUNT(DISTINCT table_id) AS tables_clustered
            FROM SNOWFLAKE.ACCOUNT_USAGE.automatic_clustering_history
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
            ORDER BY 1
            """,

    "db_overview_8_summary_query": """
            SELECT
                COUNT(*) as total_short_lived,
                COUNT(CASE WHEN is_transient = 'NO' THEN 1 END) as permanent_short_lived,
                COUNT(CASE WHEN is_transient = 'YES' THEN 1 END) as transient_short_lived,
                AVG(TIMEDIFF('minute', created, deleted)) as avg_lifespan_minutes,
                ROUND(SUM(bytes) / POWER(1024, 3), 2) as total_churned_storage_gb
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE deleted IS NOT NULL
            AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            AND TIMEDIFF('hour', created, deleted) < 24
""",

    "db_overview_9_detail_query": """
            SELECT
                table_catalog || '.' || table_schema || '.' || table_name AS full_table_name,
                table_owner,
                CASE
                    WHEN is_transient = 'NO' THEN 'Permanent (Action Required)'
                    ELSE 'Transient (OK)'
                END AS table_type,
                created,
                deleted,
                TIMEDIFF('minute', created, deleted) AS lifespan_minutes,
                ROUND(bytes / POWER(1024, 2), 2) AS size_mb,
                TO_CHAR(created, 'Day') AS day_of_week
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE deleted IS NOT NULL
            AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            AND TIMEDIFF('hour', created, deleted) < 24
ORDER BY lifespan_minutes ASC
            LIMIT 100
            """,

    "db_overview_10_pattern_query": """
            SELECT
                table_owner AS owner,
                COUNT(*) as short_lived_count,
                AVG(TIMEDIFF('minute', created, deleted)) as avg_lifespan,
                COUNT(CASE WHEN is_transient = 'NO' THEN 1 END) as permanent_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE deleted IS NOT NULL
            AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            AND TIMEDIFF('hour', created, deleted) < 24
GROUP BY 1
            HAVING permanent_count > 0
            ORDER BY permanent_count DESC
            LIMIT 20
            """,

    "db_overview_11_summary_query": """
            WITH churn_data AS (
                SELECT
                    sm.id,
                    sm.active_bytes,
                    sm.time_travel_bytes,
                    sm.failsafe_bytes,
                    (sm.time_travel_bytes + sm.failsafe_bytes) as churn_bytes,
                    DIV0((sm.time_travel_bytes + sm.failsafe_bytes), NULLIF(sm.active_bytes, 0)) as churn_ratio,
                    t.is_transient
                FROM SNOWFLAKE.ACCOUNT_USAGE.table_storage_metrics sm
                JOIN SNOWFLAKE.ACCOUNT_USAGE.tables t ON sm.id = t.table_id
                WHERE sm.deleted = FALSE
AND (sm.time_travel_bytes + sm.failsafe_bytes) > 0
            )
            SELECT
                COUNT(*) as tables_with_churn,
                COUNT(CASE WHEN churn_ratio > 1 THEN 1 END) as high_churn_tables,
                COUNT(CASE WHEN is_transient = 'NO' THEN 1 END) as permanent_with_churn,
                ROUND(SUM(churn_bytes) / POWER(1024, 4), 4) as total_churn_tb,
                ROUND(AVG(churn_ratio), 2) as avg_churn_ratio
            FROM churn_data
            """,

    "db_overview_12_detail_query": """
            WITH storage_metrics AS (
                SELECT
                    t.table_catalog,
                    t.table_schema,
                    t.table_name,
                    t.table_catalog || '.' || t.table_schema || '.' || t.table_name AS full_name,
                    t.is_transient,
                    t.row_count,
                    (sm.active_bytes / POW(1024, 3)) AS active_gb,
                    (sm.time_travel_bytes / POW(1024, 3)) AS time_travel_gb,
                    (sm.failsafe_bytes / POW(1024, 3)) AS failsafe_gb,
                    ((sm.time_travel_bytes + sm.failsafe_bytes) / POW(1024, 3)) AS total_churn_gb,
                    DIV0((sm.time_travel_bytes + sm.failsafe_bytes), NULLIF(sm.active_bytes, 0)) AS churn_ratio
                FROM SNOWFLAKE.ACCOUNT_USAGE.table_storage_metrics sm
                JOIN SNOWFLAKE.ACCOUNT_USAGE.tables t ON sm.id = t.table_id
                WHERE sm.deleted = FALSE
AND (sm.time_travel_bytes + sm.failsafe_bytes) > 0
            )
            SELECT
                full_name AS table_name,
                CASE WHEN is_transient = 'YES' THEN 'Transient' ELSE 'Permanent' END AS table_type,
                row_count,
                ROUND(active_gb, 2) AS active_data_gb,
                ROUND(time_travel_gb, 2) AS time_travel_gb,
                ROUND(failsafe_gb, 2) AS failsafe_gb,
                ROUND(total_churn_gb, 2) AS total_churn_gb,
                ROUND(churn_ratio, 2) AS churn_ratio
            FROM storage_metrics
            ORDER BY total_churn_gb DESC
            LIMIT 100
            """,

    "db_overview_13_db_churn_query": """
            SELECT
                t.table_catalog AS database_name,
                COUNT(*) as table_count,
                ROUND(SUM(sm.time_travel_bytes + sm.failsafe_bytes) / POW(1024, 4), 4) AS total_churn_tb,
                ROUND(AVG(DIV0((sm.time_travel_bytes + sm.failsafe_bytes), NULLIF(sm.active_bytes, 0))), 2) AS avg_churn_ratio
            FROM SNOWFLAKE.ACCOUNT_USAGE.table_storage_metrics sm
            JOIN SNOWFLAKE.ACCOUNT_USAGE.tables t ON sm.id = t.table_id
            WHERE sm.deleted = FALSE
AND (sm.time_travel_bytes + sm.failsafe_bytes) > 0
            GROUP BY 1
            ORDER BY total_churn_tb DESC
            """,

    "db_overview_14_object_count_query": """
    SELECT OBJECT_TYPE, OBJECT_COUNT
    FROM   (SELECT 'DATABASES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'SCHEMAS' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.SCHEMATA WHERE (DELETED IS NULL)
            UNION ALL
            SELECT TABLE_TYPE OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES WHERE (DELETED IS NULL) GROUP BY TABLE_TYPE
            UNION ALL
            SELECT 'ROW_ACCESS_POLICIES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.ROW_ACCESS_POLICIES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'PIPES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.PIPES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'ROLES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES WHERE (DELETED_ON IS NULL)
            UNION ALL
            SELECT 'NETWORK_RULES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'NETWORK_POLICIES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'MASKING_POLICIES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.MASKING_POLICIES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'USERS' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.USERS WHERE (DELETED_ON IS NULL)
            UNION ALL
            SELECT 'FILE_FORMATS' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.FILE_FORMATS WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'FUNCTIONS' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.FUNCTIONS WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'PROCEDURES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.PROCEDURES WHERE (DELETED IS NULL))
    ORDER BY OBJECT_TYPE ASC
    """,

    "db_overview_15_db_storage_query": """
    SELECT table_catalog,
        ROUND(SUM(active_bytes) / POWER(2, 40), 6) AS active_storage,
        ROUND(SUM(time_travel_bytes) / POWER(2, 40), 6) AS time_travel_storage,
        ROUND(SUM(failsafe_bytes) / POWER(2, 40), 6) AS failsafe_storage,
        ROUND(SUM(retained_for_clone_bytes) / POWER(2, 40), 6) AS retained_for_clone_storage,
        active_storage + time_travel_storage + failsafe_storage + retained_for_clone_storage AS total_storage
    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
    WHERE deleted = FALSE
GROUP BY 1
    HAVING total_storage > 0
    ORDER BY total_storage DESC
    LIMIT 10
    """,

    "db_overview_16_credit_query": """
    WITH table_types AS (
        SELECT
            table_id,
            CASE
                WHEN is_iceberg = 'YES' THEN 'Iceberg Table'
                WHEN is_dynamic = 'YES' THEN 'Dynamic Table'
                WHEN table_type = 'MATERIALIZED VIEW' THEN 'Materialized View'
                WHEN table_type = 'EVENT TABLE' THEN 'Event Table'
                ELSE 'Standard Table'
            END AS object_type
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
        WHERE deleted IS NULL
)
    SELECT
        COALESCE(t.object_type, 'Dropped/Unknown Table') AS "Table Type",
        ROUND(SUM(h.credits_used), 2) AS "Clustering Credits (30 Days)",
        COUNT(DISTINCT h.table_id) AS "Distinct Tables Clustered"
    FROM SNOWFLAKE.ACCOUNT_USAGE.automatic_clustering_history h
    LEFT JOIN table_types t
        ON h.table_id = t.table_id
    WHERE h.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
    ORDER BY 2 DESC
    """,

    "db_overview_17_clustering_query": """
    SELECT
        CASE
            WHEN is_iceberg = 'YES' THEN 'Iceberg Table'
            WHEN is_dynamic = 'YES' THEN 'Dynamic Table'
            WHEN table_type = 'MATERIALIZED VIEW' THEN 'Materialized View'
            ELSE 'Standard Table'
        END AS "Table Type",
        COUNT(CASE WHEN clustering_key IS NOT NULL THEN 1 END) AS "Clustered Count",
        COUNT(CASE WHEN clustering_key IS NULL THEN 1 END) AS "Unclustered Count",
        ROUND(
            COUNT(CASE WHEN clustering_key IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0),
            1
        ) AS "% Clustered"
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE deleted IS NULL
      AND table_schema != 'INFORMATION_SCHEMA'
      AND table_type != 'EXTERNAL TABLE'
GROUP BY 1
    ORDER BY 2 DESC
    """,

    "db_overview_18_lifespan_query": """
    SELECT
        table_catalog AS "Database",
        table_schema AS "Schema",
        table_name AS "Table Name",
        table_owner AS "Owner",
        created AS "Created Time",
        deleted AS "Dropped Time",
        TIMEDIFF('minute', created, deleted) AS "Lifespan (Minutes)",
        CASE
            WHEN is_transient = 'NO' AND table_type = 'BASE TABLE' THEN 'Permanent (High Cost)'
            WHEN is_transient = 'YES' THEN 'Transient (Good)'
            ELSE table_type
        END AS "Table Type",
        TO_CHAR(created, 'Day') AS "Day of Week",
        TO_CHAR(created, 'HH24') || ':00' AS "Hour of Day"
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE
        deleted IS NOT NULL
        AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        AND TIMEDIFF('hour', created, deleted) < 24
        AND ((table_name NOT LIKE '%tmp%') OR (table_name NOT LIKE '%temp%'))
ORDER BY "Lifespan (Minutes)" ASC
    """,

    "db_overview_19_aggregates_query": """
    SELECT
        CASE
            WHEN is_transient = 'NO' THEN 'Permanent (Action Required)'
            ELSE 'Transient (Acceptable)'
        END AS "Table Category",
        COUNT(*) AS "Count of Short-Lived Tables",
        AVG(TIMEDIFF('minute', created, deleted)) AS "Avg Lifespan (Minutes)",
        SUM(bytes) / POW(1024, 3) AS "Est. Churned Storage (GB)"
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE deleted IS NOT NULL
      AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND TIMEDIFF('hour', created, deleted) < 24
      AND table_type = 'BASE TABLE'
GROUP BY 1
    """,

    "db_overview_20_churn_query": """
    WITH storage_metrics AS (
        SELECT
            t.table_catalog,
            t.table_schema,
            t.table_name,
            t.is_transient,
            (sm.active_bytes / POW(1024, 3)) AS active_gb,
            (sm.time_travel_bytes / POW(1024, 3)) AS time_travel_gb,
            (sm.failsafe_bytes / POW(1024, 3)) AS failsafe_gb,
            ((sm.time_travel_bytes + sm.failsafe_bytes) / POW(1024, 3)) AS total_churn_gb,
            DIV0((sm.time_travel_bytes + sm.failsafe_bytes), NULLIF(sm.active_bytes, 0)) AS churn_ratio
        FROM SNOWFLAKE.ACCOUNT_USAGE.table_storage_metrics sm
        JOIN SNOWFLAKE.ACCOUNT_USAGE.tables t
            ON sm.id = t.table_id
        WHERE sm.deleted = FALSE
AND (sm.time_travel_bytes + sm.failsafe_bytes) > 0
    )
    SELECT
        table_schema || '.' || table_name AS "Table",
        CASE
            WHEN is_transient = 'YES' THEN 'Transient'
            ELSE 'Permanent (High Risk)'
        END AS "Type",
        ROUND(active_gb, 2) AS "Active Data (GB)",
        ROUND(total_churn_gb, 2) AS "Churn History (GB)",
        ROUND(churn_ratio, 1) AS "Churn Ratio (x)"
    FROM storage_metrics
    ORDER BY total_churn_gb DESC
    LIMIT 20
    """,

    "db_overview_21_access_query": """
    WITH access_log AS (
        SELECT
            f.value:objectDomain::STRING AS object_type,
            f.value:objectName::STRING AS object_name,
            f.value:objectId::INT AS object_id,
            query_start_time,
            user_name
        FROM SNOWFLAKE.ACCOUNT_USAGE.access_history,
        LATERAL FLATTEN(direct_objects_accessed) f
        WHERE query_start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        AND f.value:objectDomain::STRING NOT IN ('STAGE', 'UDF')
)
    SELECT
        object_type AS "Object Type",
        object_name AS "Object Name",
        COUNT(*) AS "Total Access Events",
        COUNT(DISTINCT user_name) AS "Distinct Users",
        MAX(query_start_time) AS "Last Accessed"
    FROM access_log
    GROUP BY 1, 2
    ORDER BY 3 DESC
    LIMIT 200
    """,

    "db_overview_22_potential_savings_query": """
        SELECT
            t.TABLE_CATALOG AS database_name,
            COUNT(*) AS table_count,
            ROUND(SUM(ts.ACTIVE_BYTES) / POWER(1024, 4), 4) AS active_tb,
            ROUND(SUM(ts.TIME_TRAVEL_BYTES) / POWER(1024, 4), 4) AS time_travel_tb,
            ROUND(SUM(ts.FAILSAFE_BYTES) / POWER(1024, 4), 4) AS failsafe_tb,
            ROUND(SUM(ts.RETAINED_FOR_CLONE_BYTES) / POWER(1024, 4), 4) AS clone_retained_tb,
            ROUND((SUM(ts.TIME_TRAVEL_BYTES) + SUM(ts.FAILSAFE_BYTES) + SUM(ts.RETAINED_FOR_CLONE_BYTES)) / POWER(1024, 4), 4) AS potential_savings_tb
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS ts
        JOIN SNOWFLAKE.ACCOUNT_USAGE.TABLES t
            ON ts.ID = t.TABLE_ID AND t.DELETED IS NULL
        WHERE ts.ACTIVE_BYTES > 0
          AND t.TABLE_CATALOG != 'SNOWFLAKE'
          AND t.TABLE_SCHEMA != 'INFORMATION_SCHEMA'
        GROUP BY t.TABLE_CATALOG
        HAVING SUM(ts.TIME_TRAVEL_BYTES) + SUM(ts.FAILSAFE_BYTES) + SUM(ts.RETAINED_FOR_CLONE_BYTES) > 0
        ORDER BY potential_savings_tb DESC
        LIMIT 15
    """,

}

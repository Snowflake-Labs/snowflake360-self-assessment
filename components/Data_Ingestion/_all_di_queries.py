_ALL_DI_QUERIES = {
    "di_copy_analysis": """
        WITH copy_stats AS (
            SELECT
                table_catalog_name || '.' || table_schema_name || '.' || table_name AS target_table,
                COUNT(*) AS job_count,
                SUM(file_size) / POW(1024, 3) AS total_gb_ingested,
                AVG(file_size) / POW(1024, 2) AS avg_file_size_mb,
                MIN(file_size) / POW(1024, 2) AS min_file_size_mb,
                MAX(file_size) / POW(1024, 2) AS max_file_size_mb,
                STDDEV(file_size) / POW(1024, 2) AS stddev_file_size_mb,
                SUM(row_count) AS total_rows_loaded
            FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
            WHERE status = 'Loaded'
              AND pipe_name IS NULL
              AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY table_catalog_name, table_schema_name, table_name
        )
        SELECT
            target_table,
            job_count,
            ROUND(total_gb_ingested, 2) AS total_gb,
            total_rows_loaded,
            ROUND(avg_file_size_mb, 2) AS avg_file_mb,
            ROUND(min_file_size_mb, 2) AS min_file_mb,
            ROUND(max_file_size_mb, 2) AS max_file_mb,
            ROUND(COALESCE(stddev_file_size_mb, 0), 2) AS stddev_file_mb,
            CASE
                WHEN max_file_size_mb > (avg_file_size_mb * 100) AND avg_file_size_mb > 0 THEN 'High Variance'
                WHEN avg_file_size_mb < 10 THEN 'Small Files (<10MB)'
                WHEN avg_file_size_mb > 250 THEN 'Large Files (>250MB)'
                ELSE 'Healthy'
            END AS health_check,
            CASE
                WHEN max_file_size_mb > (avg_file_size_mb * 100) AND avg_file_size_mb > 0
                    THEN 'High file size variance detected - investigate outliers'
                WHEN avg_file_size_mb < 10
                    THEN 'Batch files before ingestion'
                WHEN avg_file_size_mb > 250
                    THEN 'Consider splitting large files for parallelism'
                ELSE 'File sizing looks appropriate'
            END AS recommendation
        FROM copy_stats
        ORDER BY total_gb_ingested DESC
        LIMIT 20
    """,
    "di_snowpipe_efficiency": """
        WITH pipe_costs AS (
            SELECT
                pipe_name,
                SUM(credits_used) AS credits_30d,
                SUM(bytes_inserted) / POW(1024, 3) AS bytes_gb_30d,
                SUM(files_inserted) AS files_inserted_30d
            FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY pipe_name
        ),
        pipe_volume AS (
            SELECT
                pipe_name,
                COUNT(*) AS files_loaded,
                SUM(file_size) / POW(1024, 3) AS gb_loaded,
                AVG(file_size) / POW(1024, 2) AS avg_file_mb,
                SUM(row_count) AS rows_loaded
            FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
            WHERE pipe_name IS NOT NULL
              AND status = 'Loaded'
              AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY pipe_name
        )
        SELECT
            COALESCE(v.pipe_name, c.pipe_name) AS pipe_name,
            COALESCE(v.files_loaded, 0) AS files_loaded,
            ROUND(COALESCE(v.gb_loaded, 0), 3) AS gb_ingested,
            COALESCE(v.rows_loaded, 0) AS rows_loaded,
            ROUND(COALESCE(v.avg_file_mb, 0), 2) AS avg_file_mb,
            ROUND(COALESCE(c.credits_30d, 0), 4) AS credits_used,
            ROUND(COALESCE(c.credits_30d, 0) / NULLIF(COALESCE(v.gb_loaded, 0), 0), 4) AS credits_per_gb,
            CASE
                WHEN COALESCE(v.gb_loaded, 0) = 0 AND COALESCE(c.credits_30d, 0) > 0 THEN 'Idle Burning Credits'
                WHEN COALESCE(c.credits_30d, 0) / NULLIF(COALESCE(v.gb_loaded, 0), 0) > 1 THEN 'High Cost per GB'
                WHEN COALESCE(v.avg_file_mb, 0) < 10 THEN 'Small File Overhead'
                ELSE 'Efficient'
            END AS efficiency_status,
            CASE
                WHEN COALESCE(v.gb_loaded, 0) = 0 AND COALESCE(c.credits_30d, 0) > 0
                    THEN 'Pipe is active but not loading data - consider suspending'
                WHEN COALESCE(c.credits_30d, 0) / NULLIF(COALESCE(v.gb_loaded, 0), 0) > 1
                    THEN 'High cost per GB - review file sizes and batching strategy'
                WHEN COALESCE(v.avg_file_mb, 0) < 10
                    THEN 'Batch small files before ingestion'
                ELSE 'Pipe is operating efficiently'
            END AS recommendation
        FROM pipe_volume v
        FULL OUTER JOIN pipe_costs c ON v.pipe_name = c.pipe_name
        ORDER BY COALESCE(c.credits_30d, 0) DESC
    """,
    "di_top_pipe_consumers": """
        SELECT
            pipe_name,
            ROUND(SUM(credits_used), 4) AS credits_burned,
            SUM(files_inserted) AS files_inserted,
            ROUND(SUM(bytes_inserted) / POW(1024, 3), 3) AS gb_loaded,
            CASE
                WHEN SUM(bytes_inserted) = 0 AND SUM(credits_used) > 0 THEN 'Overhead Only'
                WHEN SUM(bytes_inserted) > 0
                     AND (SUM(credits_used) / (SUM(bytes_inserted) / POW(1024, 3))) > 1 THEN 'High Overhead'
                ELSE 'Efficient'
            END AS status,
            CASE
                WHEN SUM(bytes_inserted) = 0 AND SUM(credits_used) > 0
                    THEN 'Pipe consuming credits without loading data - suspend or investigate'
                WHEN SUM(bytes_inserted) > 0
                     AND (SUM(credits_used) / (SUM(bytes_inserted) / POW(1024, 3))) > 1
                    THEN 'High credit cost per GB - review file sizes and notification frequency'
                ELSE 'Pipe is operating efficiently'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
        WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        GROUP BY pipe_name
        ORDER BY credits_burned DESC
        LIMIT 10
    """,
    "di_credit_projection": """
        WITH snowpipe_costs AS (
            SELECT
                'Snowpipe (File-based)' AS ingest_method,
                SUM(credits_used) AS total_credits,
                SUM(bytes_inserted) / POW(1024, 3) AS total_gb,
                SUM(files_inserted) AS total_files
            FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        ),
        streaming_costs AS (
            SELECT
                'Snowpipe Streaming' AS ingest_method,
                SUM(credits_used_compute + credits_used_cloud_services) AS total_credits,
                NULL AS total_gb,
                NULL AS total_files
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE service_type = 'SNOWPIPE_STREAMING'
              AND usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        ),
        combined AS (
            SELECT * FROM snowpipe_costs
            UNION ALL
            SELECT * FROM streaming_costs
        )
        SELECT
            ingest_method,
            ROUND(COALESCE(total_credits, 0), 2) AS credits_last_30_days,
            ROUND(COALESCE(total_gb, 0), 2) AS gb_ingested_30_days,
            COALESCE(total_files, 0) AS files_processed_30_days,
            ROUND(COALESCE(total_credits, 0) * 3, 0) AS est_credits_3_months,
            ROUND(COALESCE(total_credits, 0) * 6, 0) AS est_credits_6_months,
            ROUND(COALESCE(total_credits, 0) * 12, 0) AS est_credits_12_months,
            CASE
                WHEN COALESCE(total_credits, 0) > 100 THEN 'High Usage'
                WHEN COALESCE(total_credits, 0) > 10 THEN 'Moderate Usage'
                ELSE 'Low Usage'
            END AS usage_tier
        FROM combined
        WHERE COALESCE(total_credits, 0) > 0
        ORDER BY COALESCE(total_credits, 0) DESC
    """,
    "di_ingestion_summary": """
        WITH copy_summary AS (
            SELECT
                'COPY Command' AS ingestion_method,
                COUNT(*) AS events_or_channels,
                SUM(file_size) / POW(1024, 3) AS gb_loaded,
                SUM(row_count) AS rows_loaded,
                AVG(file_size) / POW(1024, 2) AS avg_file_mb,
                NULL AS credits_last_30_days
            FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
            WHERE status = 'Loaded'
              AND pipe_name IS NULL
              AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        ),
        pipe_summary AS (
            SELECT
                'Snowpipe' AS ingestion_method,
                COUNT(*) AS events_or_channels,
                SUM(file_size) / POW(1024, 3) AS gb_loaded,
                SUM(row_count) AS rows_loaded,
                AVG(file_size) / POW(1024, 2) AS avg_file_mb,
                NULL AS credits_last_30_days
            FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
            WHERE status = 'Loaded'
              AND pipe_name IS NOT NULL
              AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        ),
        streaming_summary AS (
            SELECT
                'Snowpipe Streaming' AS ingestion_method,
                COUNT(DISTINCT channel_name) AS events_or_channels,
                NULL AS gb_loaded,
                SUM(rows_inserted) AS rows_loaded,
                NULL AS avg_file_mb,
                NULL AS credits_last_30_days
            FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPIPE_STREAMING_CLIENT_HISTORY
            WHERE event_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        ),
        pipe_credits AS (
            SELECT ROUND(SUM(credits_used), 4) AS c
            FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        ),
        streaming_credits AS (
            SELECT ROUND(SUM(credits_used_compute + credits_used_cloud_services), 4) AS c
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE service_type = 'SNOWPIPE_STREAMING'
              AND usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        )
        SELECT
            ingestion_method,
            COALESCE(events_or_channels, 0) AS events_or_channels,
            ROUND(COALESCE(gb_loaded, 0), 3) AS gb_loaded_30d,
            COALESCE(rows_loaded, 0) AS rows_loaded_30d,
            ROUND(COALESCE(avg_file_mb, 0), 2) AS avg_file_mb,
            CASE
                WHEN ingestion_method = 'Snowpipe' THEN (SELECT c FROM pipe_credits)
                WHEN ingestion_method = 'Snowpipe Streaming' THEN (SELECT c FROM streaming_credits)
                ELSE 0
            END AS credits_last_30_days
        FROM copy_summary
        UNION ALL
        SELECT ingestion_method, COALESCE(events_or_channels, 0),
               ROUND(COALESCE(gb_loaded, 0), 3), COALESCE(rows_loaded, 0),
               ROUND(COALESCE(avg_file_mb, 0), 2),
               (SELECT c FROM pipe_credits)
        FROM pipe_summary
        UNION ALL
        SELECT ingestion_method, COALESCE(events_or_channels, 0),
               ROUND(COALESCE(gb_loaded, 0), 3), COALESCE(rows_loaded, 0),
               ROUND(COALESCE(avg_file_mb, 0), 2),
               (SELECT c FROM streaming_credits)
        FROM streaming_summary
        ORDER BY gb_loaded_30d DESC NULLS LAST
    """,
    "di_streaming_credits": """
        SELECT
            usage_date::DATE AS usage_date,
            ROUND(SUM(credits_used), 4) AS credits_used
        FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
        WHERE service_type = 'SNOWPIPE_STREAMING'
          AND usage_date >= DATEADD('day', -30, CURRENT_DATE())
        GROUP BY 1
        ORDER BY 1
    """,
}

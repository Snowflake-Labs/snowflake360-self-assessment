_ALL_DEVOPS_QUERIES = {

    "rd_dcm_adoption": """
SELECT
    CASE
        WHEN query_text ILIKE '%CREATE OR ALTER%' THEN 'Declarative (DevOps Pattern)'
        WHEN query_text ILIKE '%EXECUTE IMMEDIATE FROM%' THEN 'Deployment from File/Git'
        WHEN query_text ILIKE '%CREATE OR REPLACE%' THEN 'Idempotent DDL'
        ELSE 'Imperative (Standard DDL)'
    END AS DDL_PATTERN,
    COUNT(*) AS EXECUTION_COUNT,
    COUNT(DISTINCT user_name) AS DISTINCT_USERS,
    COUNT(DISTINCT role_name) AS DISTINCT_ROLES,
    ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) AS PCT_OF_TOTAL
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type IN ('CREATE_TABLE', 'ALTER_TABLE', 'EXECUTE_IMMEDIATE', 'CREATE_VIEW', 'ALTER_VIEW')
  AND execution_status = 'SUCCESS'
GROUP BY DDL_PATTERN
ORDER BY EXECUTION_COUNT DESC
""",

    "rd_git_integration": """
SELECT
    'Git Operation' AS CATEGORY,
    CASE
        WHEN query_text ILIKE '%ALTER GIT REPOSITORY%FETCH%' THEN 'Git Fetch (Update)'
        WHEN query_text ILIKE '%FROM @%branches/%' OR query_text ILIKE '%FROM @%tags/%' THEN 'Execution from Git Branch/Tag'
        WHEN query_text ILIKE '%CREATE GIT REPOSITORY%' THEN 'Git Repository Creation'
        WHEN query_text ILIKE '%SHOW GIT%' THEN 'Git Metadata Query'
        ELSE 'Other Git Operation'
    END AS OPERATION_TYPE,
    COUNT(*) AS COUNT_OPS,
    COUNT(DISTINCT user_name) AS DISTINCT_USERS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (query_text ILIKE '%ALTER GIT REPOSITORY%'
       OR query_text ILIKE '%FROM @%'
       OR query_text ILIKE '%CREATE GIT REPOSITORY%'
       OR query_text ILIKE '%SHOW GIT%')
GROUP BY OPERATION_TYPE
HAVING COUNT(*) > 0
ORDER BY COUNT_OPS DESC
""",

    "rd_cicd_detail": """
SELECT
    CASE
        WHEN s.client_application_id ILIKE '%GitHub%' THEN 'GitHub Actions'
        WHEN s.client_application_id ILIKE '%GitLab%' THEN 'GitLab CI'
        WHEN s.client_application_id ILIKE '%Jenkins%' THEN 'Jenkins'
        WHEN s.client_application_id ILIKE '%Terraform%' THEN 'Terraform'
        WHEN s.client_application_id ILIKE '%Schemachange%' THEN 'Schemachange'
        WHEN s.client_application_id ILIKE '%dbt%' THEN 'dbt'
        WHEN s.client_application_id ILIKE '%Airflow%' THEN 'Airflow'
        WHEN s.client_application_id ILIKE '%Fivetran%' THEN 'Fivetran'
        WHEN s.client_application_id ILIKE '%Matillion%' THEN 'Matillion'
        WHEN q.user_name ILIKE '%SVC_%' OR q.user_name ILIKE '%CI_%' OR q.user_name ILIKE '%SERVICE%' THEN 'Service Account (Generic)'
        ELSE 'Human / Other'
    END AS DEPLOYMENT_AGENT,
    s.client_application_id AS CLIENT_APPLICATION_ID,
    COUNT(DISTINCT s.session_id) AS SESSION_COUNT,
    COUNT(DISTINCT q.query_id) AS DDL_OPERATIONS_COUNT,
    COUNT(DISTINCT q.user_name) AS DISTINCT_USERS
FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    ON s.session_id = q.session_id
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (q.query_type ILIKE 'CREATE%'
       OR q.query_type ILIKE 'ALTER%'
       OR q.query_type ILIKE 'DROP%'
       OR q.query_type ILIKE 'GRANT%')
GROUP BY DEPLOYMENT_AGENT, s.client_application_id
ORDER BY DDL_OPERATIONS_COUNT DESC
""",

    "rd_cicd_summary": """
SELECT
    CASE
        WHEN s.client_application_id ILIKE '%GitHub%' THEN 'GitHub Actions'
        WHEN s.client_application_id ILIKE '%GitLab%' THEN 'GitLab CI'
        WHEN s.client_application_id ILIKE '%Jenkins%' THEN 'Jenkins'
        WHEN s.client_application_id ILIKE '%Terraform%' THEN 'Terraform'
        WHEN s.client_application_id ILIKE '%Schemachange%' THEN 'Schemachange'
        WHEN s.client_application_id ILIKE '%dbt%' THEN 'dbt'
        WHEN s.client_application_id ILIKE '%Airflow%' THEN 'Airflow'
        WHEN q.user_name ILIKE '%SVC_%' OR q.user_name ILIKE '%CI_%' THEN 'Service Account'
        ELSE 'Human / Other'
    END AS DEPLOYMENT_AGENT,
    COUNT(DISTINCT s.session_id) AS SESSION_COUNT,
    COUNT(DISTINCT q.query_id) AS DDL_OPERATIONS_COUNT,
    ROUND(COUNT(DISTINCT q.query_id) * 100.0 / NULLIF(SUM(COUNT(DISTINCT q.query_id)) OVER(), 0), 1) AS PCT_OF_DDL_OPS
FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
    ON s.session_id = q.session_id
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (q.query_type ILIKE 'CREATE%'
       OR q.query_type ILIKE 'ALTER%'
       OR q.query_type ILIKE 'DROP%'
       OR q.query_type ILIKE 'GRANT%')
GROUP BY DEPLOYMENT_AGENT
ORDER BY DDL_OPERATIONS_COUNT DESC
""",

    "rd_orchestration": """
WITH dt_usage AS (
    SELECT
        'Dynamic Tables (Declarative)' AS ORCHESTRATION_TYPE,
        COUNT(*) AS ACTIVITY_COUNT,
        COUNT(DISTINCT name) AS DISTINCT_OBJECTS
    FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
    WHERE data_timestamp >= DATEADD('day', -7, CURRENT_TIMESTAMP())
),
task_usage AS (
    SELECT
        'Tasks (Imperative)' AS ORCHESTRATION_TYPE,
        COUNT(*) AS ACTIVITY_COUNT,
        COUNT(DISTINCT name) AS DISTINCT_OBJECTS
    FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
    WHERE scheduled_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
),
combined AS (
    SELECT * FROM dt_usage
    UNION ALL
    SELECT * FROM task_usage
)
SELECT
    ORCHESTRATION_TYPE,
    ACTIVITY_COUNT,
    DISTINCT_OBJECTS,
    CASE
        WHEN ORCHESTRATION_TYPE LIKE '%Dynamic%' AND ACTIVITY_COUNT > 0 THEN 'Using Modern Declarative Pattern'
        WHEN ORCHESTRATION_TYPE LIKE '%Task%' AND ACTIVITY_COUNT > 0 THEN 'Using Traditional Imperative Pattern'
        ELSE 'No Activity'
    END AS PATTERN_ASSESSMENT
FROM combined
ORDER BY ACTIVITY_COUNT DESC
""",

    "rd_dt_inventory": """
SELECT
    COUNT(*) AS DT_COUNT,
    COUNT(DISTINCT table_catalog) AS DB_COUNT,
    COUNT(DISTINCT table_schema) AS SCHEMA_COUNT
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE table_type = 'DYNAMIC TABLE' AND deleted IS NULL
""",

    "rd_dt_refresh_stats": """
SELECT
    COUNT(*) AS TOTAL_REFRESHES,
    ROUND(AVG(TIMESTAMPDIFF('minute', refresh_start_time, refresh_end_time)), 1) AS AVG_LAG_MIN
FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
WHERE data_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
""",

    "rd_dt_daily_refresh": """
SELECT
    TO_DATE(refresh_start_time) AS REFRESH_DATE,
    SUM(CASE WHEN state = 'SUCCEEDED' THEN 1 ELSE 0 END) AS SUCCESS,
    SUM(CASE WHEN state != 'SUCCEEDED' THEN 1 ELSE 0 END) AS FAILURES
FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
WHERE data_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY REFRESH_DATE
ORDER BY REFRESH_DATE ASC
""",

    "rd_maturity_summary": """
WITH ddl_patterns AS (
    SELECT
        SUM(CASE WHEN query_text ILIKE '%CREATE OR ALTER%' THEN 1 ELSE 0 END) AS declarative_count,
        SUM(CASE WHEN query_text ILIKE '%EXECUTE IMMEDIATE FROM%' THEN 1 ELSE 0 END) AS git_deploy_count,
        SUM(CASE WHEN query_text ILIKE '%CREATE OR REPLACE%' THEN 1 ELSE 0 END) AS idempotent_count,
        COUNT(*) AS total_ddl
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND query_type IN ('CREATE_TABLE', 'ALTER_TABLE', 'EXECUTE_IMMEDIATE', 'CREATE_VIEW', 'ALTER_VIEW')
      AND execution_status = 'SUCCESS'
),
automation_stats AS (
    SELECT
        COUNT(DISTINCT CASE
            WHEN s.client_application_id ILIKE '%GitHub%'
                 OR s.client_application_id ILIKE '%GitLab%'
                 OR s.client_application_id ILIKE '%Jenkins%'
                 OR s.client_application_id ILIKE '%Terraform%'
                 OR s.client_application_id ILIKE '%dbt%'
            THEN q.query_id
        END) AS automated_ddl_count,
        COUNT(DISTINCT q.query_id) AS total_ddl_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
    JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
        ON s.session_id = q.session_id
    WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND (q.query_type ILIKE 'CREATE%' OR q.query_type ILIKE 'ALTER%')
),
orchestration_stats AS (
    SELECT
        (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.DYNAMIC_TABLE_REFRESH_HISTORY
         WHERE data_timestamp >= DATEADD('day', -7, CURRENT_TIMESTAMP())) AS dt_refreshes,
        (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
         WHERE scheduled_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())) AS task_runs
)
SELECT 'DDL Patterns' AS METRIC_CATEGORY, 'Declarative DDL (CREATE OR ALTER)' AS METRIC_NAME,
       dp.declarative_count AS METRIC_VALUE,
       ROUND(dp.declarative_count * 100.0 / NULLIF(dp.total_ddl, 0), 1) AS PCT_OF_TOTAL
FROM ddl_patterns dp
UNION ALL
SELECT 'DDL Patterns', 'Git-based Deployments', dp.git_deploy_count,
       ROUND(dp.git_deploy_count * 100.0 / NULLIF(dp.total_ddl, 0), 1)
FROM ddl_patterns dp
UNION ALL
SELECT 'DDL Patterns', 'Idempotent DDL (CREATE OR REPLACE)', dp.idempotent_count,
       ROUND(dp.idempotent_count * 100.0 / NULLIF(dp.total_ddl, 0), 1)
FROM ddl_patterns dp
UNION ALL
SELECT 'Automation', 'CI/CD Automated DDL Operations', ast.automated_ddl_count,
       ROUND(ast.automated_ddl_count * 100.0 / NULLIF(ast.total_ddl_count, 0), 1)
FROM automation_stats ast
UNION ALL
SELECT 'Orchestration', 'Dynamic Table Refreshes (7d)', os.dt_refreshes, NULL
FROM orchestration_stats os
UNION ALL
SELECT 'Orchestration', 'Task Runs (7d)', os.task_runs, NULL
FROM orchestration_stats os
ORDER BY METRIC_CATEGORY, METRIC_NAME
""",

    "rd_maturity_score": """
WITH metrics AS (
    SELECT
        SUM(CASE WHEN query_text ILIKE '%CREATE OR ALTER%' THEN 1 ELSE 0 END) AS declarative_ddl,
        SUM(CASE WHEN query_text ILIKE '%EXECUTE IMMEDIATE FROM%' THEN 1 ELSE 0 END) AS git_deploys,
        COUNT(*) AS total_ddl
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND query_type IN ('CREATE_TABLE', 'ALTER_TABLE', 'EXECUTE_IMMEDIATE', 'CREATE_VIEW')
      AND execution_status = 'SUCCESS'
)
SELECT
    m.declarative_ddl AS DECLARATIVE_DDL,
    m.git_deploys AS GIT_DEPLOYS,
    m.total_ddl AS TOTAL_DDL,
    CASE
        WHEN m.declarative_ddl * 100.0 / NULLIF(m.total_ddl, 0) > 50 AND m.git_deploys > 0 THEN 'ADVANCED'
        WHEN m.declarative_ddl * 100.0 / NULLIF(m.total_ddl, 0) > 20 OR m.git_deploys > 0 THEN 'INTERMEDIATE'
        WHEN m.total_ddl > 0 THEN 'BASIC'
        ELSE 'NO_DATA'
    END AS DEVOPS_MATURITY_LEVEL,
    CASE
        WHEN m.declarative_ddl * 100.0 / NULLIF(m.total_ddl, 0) < 20
        THEN 'Adopt CREATE OR ALTER for declarative, idempotent deployments'
        WHEN m.git_deploys = 0
        THEN 'Consider Git integration for version-controlled deployments'
        ELSE 'DevOps practices look mature'
    END AS PRIMARY_RECOMMENDATION
FROM metrics m
""",

}

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

"""Cortex operations for Warehouse Analysis"""

import streamlit as st
import pandas as pd
import json
import uuid
import time
from typing import Dict, Any, Optional, List


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


def call_cortex_llm(session, model_name: str, prompt: str, operation_name: str = "cortex_analysis") -> str:
    """
    Call Snowflake Cortex LLM with the provided prompt.

    Args:
        session: Snowflake session
        model_name: Name of the Cortex model (claude-3-7-sonnet or claude-4-sonnet)
        prompt: Prompt text for the LLM
        operation_name: Name of the operation for logging

    Returns:
        String response from the LLM
    """
    try:
        sql_safe_prompt = prompt.replace("$$", "$$$$").replace("'", "''")

        cortex_sql = f"""
        SELECT SNOWFLAKE.CORTEX.AI_COMPLETE(
            $${model_name}$$,
            $${sql_safe_prompt}$$
        ) AS CORTEX_RESPONSE
        """

        result = session.sql(cortex_sql).collect()

        if result and len(result) > 0:
            response = result[0]['CORTEX_RESPONSE']
            return response if response else f"Cortex {operation_name} returned null response"
        else:
            return f"Cortex {operation_name} returned no results"

    except Exception as e:
        error_msg = str(e)
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error in Cortex {operation_name} with {model_name}: {error_msg}'
                    f'</div>', unsafe_allow_html=True)

        if "unavailable" in error_msg.lower() or "not found" in error_msg.lower():
            st.markdown('<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '🛑&nbsp;&nbsp;<strong>Model Unavailable</strong>: The selected Cortex model is not available in your environment.'
                        '</div>', unsafe_allow_html=True)
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;<strong>Available models to try:</strong>'
                        '</div>', unsafe_allow_html=True)
            from .config import AVAILABLE_CORTEX_MODELS
            for model in AVAILABLE_CORTEX_MODELS:
                st.markdown(f'<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'ℹ️&nbsp;&nbsp;• {model}'
                        f'</div>', unsafe_allow_html=True)
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;Please select a different model from the dropdown and try again.'
                        '</div>', unsafe_allow_html=True)

        return f"Error: {error_msg}"


def fetch_warehouse_data_for_analysis(session, lookback_days: int = 15,
                                    top_n_warehouses: int = 10) -> pd.DataFrame:
    """
    Fetch warehouse data with time series information for Cortex analysis and charts.
    Queries the underlying ACCOUNT_USAGE tables to build detailed time series data.

    Args:
        session: Snowflake session
        lookback_days: Number of days to look back for analysis
        top_n_warehouses: Number of top warehouses to analyze by credit consumption

    Returns:
        DataFrame with warehouse data including WAREHOUSE_DETAILS_JSON with hourly_info
    """
    try:
        import pandas as pd
        ts_end_dt = pd.Timestamp.now(tz='UTC')
        ts_start_dt = ts_end_dt - pd.Timedelta(days=int(lookback_days))
        ts_start_str = ts_start_dt.strftime('%Y-%m-%d %H:%M:%S')
        ts_end_str = ts_end_dt.strftime('%Y-%m-%d %H:%M:%S')

        top_wh_query = f"""
        SELECT WAREHOUSE_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE START_TIME >= '{ts_start_str}'::TIMESTAMP_NTZ
          AND START_TIME < '{ts_end_str}'::TIMESTAMP_NTZ
          AND WAREHOUSE_NAME NOT LIKE 'SYSTEM$%'
          AND WAREHOUSE_NAME NOT LIKE 'CLOUD_SERVICES_ONLY'
        GROUP BY 1
        ORDER BY SUM(CREDITS_USED) DESC
        LIMIT {top_n_warehouses}
        """

        top_warehouses_df = _cached_sql("wc_top_warehouses", top_wh_query)
        if top_warehouses_df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                '⚠️&nbsp;&nbsp;No warehouses found with credit usage in the specified period.'
                                '</div>', unsafe_allow_html=True)
            return pd.DataFrame()

        warehouse_names = top_warehouses_df['WAREHOUSE_NAME'].tolist()
        warehouse_filter = "'" + "','".join(warehouse_names) + "'"

        query = f"""
        WITH
        warehouse_config_raw AS (
            SELECT
                WAREHOUSE_NAME,
                WAREHOUSE_TYPE,
                WAREHOUSE_TSHIRT_SIZE_CONFIG,
                MIN_CLUSTER_COUNT,
                MAX_CLUSTER_COUNT,
                AUTO_SUSPEND_SECONDS,
                AUTO_RESUME_ENABLED,
                QAS_ENABLED,
                QAS_MAX_SCALE_FACTOR,
                SCALING_POLICY
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_PRISM
            WHERE WAREHOUSE_NAME IN ({warehouse_filter})
        ),
        hourly_query_history AS (
            SELECT
                WAREHOUSE_NAME,
                DATE_TRUNC('HOUR', START_TIME) AS usage_hour_utc,
                COUNT(*) AS total_queries,
                AVG(TOTAL_ELAPSED_TIME / 1000) AS avg_total_elapsed_time_sec,
                MEDIAN(TOTAL_ELAPSED_TIME / 1000) AS median_total_elapsed_time_sec,
                APPROX_PERCENTILE(TOTAL_ELAPSED_TIME / 1000, 0.95) AS p95_total_elapsed_time_sec,
                AVG(EXECUTION_TIME / 1000) AS avg_execution_time_sec,
                MEDIAN(EXECUTION_TIME / 1000) AS median_execution_time_sec,
                SUM(COALESCE(BYTES_SPILLED_TO_LOCAL_STORAGE, 0) / POWER(1024,3)) AS total_bytes_spilled_local_gb,
                SUM(COALESCE(BYTES_SPILLED_TO_REMOTE_STORAGE, 0) / POWER(1024,3)) AS total_bytes_spilled_remote_gb,
                ANY_VALUE(WAREHOUSE_SIZE) as warehouse_tshirt_size_query
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME >= '{ts_start_str}'::TIMESTAMP_NTZ
              AND START_TIME < '{ts_end_str}'::TIMESTAMP_NTZ
              AND WAREHOUSE_SIZE IS NOT NULL
              AND WAREHOUSE_NAME IN ({warehouse_filter})
            GROUP BY 1, 2
        ),
        hourly_metering_history AS (
            SELECT
                WAREHOUSE_NAME,
                DATE_TRUNC('HOUR', START_TIME) AS usage_hour_utc,
                SUM(CREDITS_USED_COMPUTE) AS compute_credits,
                SUM(CREDITS_USED_CLOUD_SERVICES) AS cloud_service_credits,
                SUM(CREDITS_USED) AS total_credits_used
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= '{ts_start_str}'::TIMESTAMP_NTZ
              AND START_TIME < '{ts_end_str}'::TIMESTAMP_NTZ
              AND WAREHOUSE_NAME IN ({warehouse_filter})
            GROUP BY 1, 2
        ),
        hourly_load_history AS (
            SELECT
                WAREHOUSE_NAME,
                DATE_TRUNC('HOUR', START_TIME) AS usage_hour_utc,
                AVG(AVG_RUNNING) AS avg_concurrent_running_queries,
                MAX(AVG_RUNNING) AS max_concurrent_running_queries,
                AVG(AVG_QUEUED_LOAD) AS avg_queued_load,
                MAX(AVG_QUEUED_LOAD) AS max_queued_load
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
            WHERE START_TIME >= '{ts_start_str}'::TIMESTAMP_NTZ
              AND START_TIME < '{ts_end_str}'::TIMESTAMP_NTZ
              AND WAREHOUSE_NAME IN ({warehouse_filter})
            GROUP BY 1, 2
        ),
        all_warehouse_hours_scaffold AS (
            SELECT DISTINCT wcr.WAREHOUSE_NAME, h.usage_hour_utc
            FROM warehouse_config_raw wcr
            LEFT JOIN (
                SELECT WAREHOUSE_NAME, usage_hour_utc FROM hourly_query_history
                UNION ALL SELECT WAREHOUSE_NAME, usage_hour_utc FROM hourly_metering_history
                UNION ALL SELECT WAREHOUSE_NAME, usage_hour_utc FROM hourly_load_history
            ) h ON wcr.WAREHOUSE_NAME = h.WAREHOUSE_NAME
        ),
        joined_hourly_data AS (
            SELECT
                awhs.usage_hour_utc,
                wcr.WAREHOUSE_NAME,
                wcr.WAREHOUSE_TYPE,
                wcr.WAREHOUSE_TSHIRT_SIZE_CONFIG,
                wcr.MIN_CLUSTER_COUNT,
                wcr.MAX_CLUSTER_COUNT,
                wcr.SCALING_POLICY,
                wcr.AUTO_SUSPEND_SECONDS,
                wcr.AUTO_RESUME_ENABLED,
                wcr.QAS_ENABLED,
                wcr.QAS_MAX_SCALE_FACTOR,
                COALESCE(hqh.total_queries, 0) AS total_queries,
                hqh.avg_total_elapsed_time_sec,
                hqh.median_total_elapsed_time_sec,
                hqh.p95_total_elapsed_time_sec,
                hqh.avg_execution_time_sec,
                hqh.median_execution_time_sec,
                COALESCE(hqh.total_bytes_spilled_local_gb, 0) AS total_bytes_spilled_local_gb,
                COALESCE(hqh.total_bytes_spilled_remote_gb, 0) AS total_bytes_spilled_remote_gb,
                COALESCE(hmh.compute_credits, 0) AS compute_credits,
                COALESCE(hmh.cloud_service_credits, 0) AS cloud_service_credits,
                COALESCE(hmh.total_credits_used, 0) AS total_credits_used,
                COALESCE(hlh.avg_concurrent_running_queries, 0) AS avg_concurrent_running_queries,
                COALESCE(hlh.max_concurrent_running_queries, 0) AS max_concurrent_running_queries,
                COALESCE(hlh.avg_queued_load, 0) AS avg_queued_load,
                COALESCE(hlh.max_queued_load, 0) AS max_queued_load
            FROM warehouse_config_raw wcr
            LEFT JOIN all_warehouse_hours_scaffold awhs ON wcr.WAREHOUSE_NAME = awhs.WAREHOUSE_NAME
            LEFT JOIN hourly_query_history hqh ON wcr.WAREHOUSE_NAME = hqh.WAREHOUSE_NAME AND awhs.usage_hour_utc = hqh.usage_hour_utc
            LEFT JOIN hourly_metering_history hmh ON wcr.WAREHOUSE_NAME = hmh.WAREHOUSE_NAME AND awhs.usage_hour_utc = hmh.usage_hour_utc
            LEFT JOIN hourly_load_history hlh ON wcr.WAREHOUSE_NAME = hlh.WAREHOUSE_NAME AND awhs.usage_hour_utc = hlh.usage_hour_utc
        )
        SELECT
            jhd.WAREHOUSE_NAME,
            ANY_VALUE(jhd.WAREHOUSE_TYPE) as WAREHOUSE_TYPE,
            ANY_VALUE(jhd.WAREHOUSE_TSHIRT_SIZE_CONFIG) as WAREHOUSE_TSHIRT_SIZE_CONFIG,
            ANY_VALUE(jhd.MIN_CLUSTER_COUNT) as MIN_CLUSTER_COUNT,
            ANY_VALUE(jhd.MAX_CLUSTER_COUNT) as MAX_CLUSTER_COUNT,
            ANY_VALUE(jhd.SCALING_POLICY) as SCALING_POLICY,
            ANY_VALUE(jhd.AUTO_SUSPEND_SECONDS) as AUTO_SUSPEND_SECONDS,
            ANY_VALUE(jhd.AUTO_RESUME_ENABLED) as AUTO_RESUME_ENABLED,
            ANY_VALUE(jhd.QAS_ENABLED) as QAS_ENABLED,
            ANY_VALUE(jhd.QAS_MAX_SCALE_FACTOR) as QAS_MAX_SCALE_FACTOR,
            SUM(jhd.total_credits_used) AS PERIOD_TOTAL_CREDITS_CALCULATED,
            OBJECT_CONSTRUCT(
                'properties', OBJECT_CONSTRUCT(
                    'WAREHOUSE_TYPE', ANY_VALUE(jhd.WAREHOUSE_TYPE),
                    'WAREHOUSE_TSHIRT_SIZE_CONFIG', ANY_VALUE(jhd.WAREHOUSE_TSHIRT_SIZE_CONFIG),
                    'MIN_CLUSTER_COUNT', ANY_VALUE(jhd.MIN_CLUSTER_COUNT),
                    'MAX_CLUSTER_COUNT', ANY_VALUE(jhd.MAX_CLUSTER_COUNT),
                    'SCALING_POLICY', ANY_VALUE(jhd.SCALING_POLICY),
                    'AUTO_SUSPEND_SECONDS', ANY_VALUE(jhd.AUTO_SUSPEND_SECONDS),
                    'AUTO_RESUME_ENABLED', ANY_VALUE(jhd.AUTO_RESUME_ENABLED),
                    'QAS_ENABLED', ANY_VALUE(jhd.QAS_ENABLED),
                    'QAS_MAX_SCALE_FACTOR', ANY_VALUE(jhd.QAS_MAX_SCALE_FACTOR),
                    'HOURLY_DATA_COLUMN_HEADERS', ARRAY_CONSTRUCT(
                        'USAGE_HOUR_UTC', 'TOTAL_QUERIES',
                        'AVG_TOTAL_ELAPSED_TIME_SEC', 'MEDIAN_TOTAL_ELAPSED_TIME_SEC', 'P95_TOTAL_ELAPSED_TIME_SEC',
                        'AVG_EXECUTION_TIME_SEC', 'MEDIAN_EXECUTION_TIME_SEC',
                        'TOTAL_BYTES_SPILLED_LOCAL_GB', 'TOTAL_BYTES_SPILLED_REMOTE_GB',
                        'COMPUTE_CREDITS', 'CLOUD_SERVICE_CREDITS', 'TOTAL_CREDITS_USED',
                        'AVG_CONCURRENT_RUNNING_QUERIES', 'MAX_CONCURRENT_RUNNING_QUERIES',
                        'AVG_QUEUED_LOAD', 'MAX_QUEUED_LOAD'
                    )
                ),
                'hourly_info', COALESCE(ARRAY_AGG(
                    CASE
                        WHEN jhd.usage_hour_utc IS NOT NULL THEN
                            ARRAY_CONSTRUCT(
                                TO_CHAR(jhd.usage_hour_utc, 'YYYY-MM-DD HH24:MI:SS'),
                                COALESCE(jhd.total_queries, 0),
                                COALESCE(jhd.avg_total_elapsed_time_sec, 0.0),
                                COALESCE(jhd.median_total_elapsed_time_sec, 0.0),
                                COALESCE(jhd.p95_total_elapsed_time_sec, 0.0),
                                COALESCE(jhd.avg_execution_time_sec, 0.0),
                                COALESCE(jhd.median_execution_time_sec, 0.0),
                                COALESCE(jhd.total_bytes_spilled_local_gb, 0.0),
                                COALESCE(jhd.total_bytes_spilled_remote_gb, 0.0),
                                COALESCE(jhd.compute_credits, 0.0),
                                COALESCE(jhd.cloud_service_credits, 0.0),
                                COALESCE(jhd.total_credits_used, 0.0),
                                COALESCE(jhd.avg_concurrent_running_queries, 0.0),
                                COALESCE(jhd.max_concurrent_running_queries, 0.0),
                                COALESCE(jhd.avg_queued_load, 0.0),
                                COALESCE(jhd.max_queued_load, 0.0)
                            )
                        ELSE NULL
                    END
                ) WITHIN GROUP (ORDER BY jhd.usage_hour_utc ASC), ARRAY_CONSTRUCT())
            ) AS WAREHOUSE_DETAILS_JSON
        FROM joined_hourly_data jhd
        GROUP BY jhd.WAREHOUSE_NAME
        ORDER BY SUM(jhd.total_credits_used) DESC
        """

        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Fetching warehouse time series data...'
                    '</div>', unsafe_allow_html=True)
        result = _cached_sql("wc_timeseries", query)

        if result.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                '⚠️&nbsp;&nbsp;No data returned from warehouse analysis query.'
                                '</div>', unsafe_allow_html=True)
            return pd.DataFrame()

        st.success(f"Fetched data for {len(result)} warehouses with time series information")
        return result

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error fetching warehouse data for analysis: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Please check Snowflake permissions and ensure access to SNOWFLAKE.ACCOUNT_USAGE tables.'
                    '</div>', unsafe_allow_html=True)

        error_msg = str(e)
        if "not exist or not authorized" in error_msg:
            st.markdown('<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '🛑&nbsp;&nbsp;<strong>Access Issue</strong>: The ACCOUNT_USAGE tables are not accessible.'
                        '</div>', unsafe_allow_html=True)
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;<strong>Possible Solutions:</strong>'
                        '</div>', unsafe_allow_html=True)
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;• Verify you have SELECT permissions on SNOWFLAKE.ACCOUNT_USAGE.* tables'
                        '</div>', unsafe_allow_html=True)
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;• Check if the tables exist in the specified schema'
                        '</div>', unsafe_allow_html=True)
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;• Ensure your role has access to the SNOWFLAKE database'
                        '</div>', unsafe_allow_html=True)

        if 'account_info' not in st.session_state:
            st.markdown('<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '🛑&nbsp;&nbsp;<strong>Session Context Issue</strong>: Account information not initialized.'
                        '</div>', unsafe_allow_html=True)
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;Please ensure the application session context is properly set up.'
                        '</div>', unsafe_allow_html=True)

        return pd.DataFrame(columns=['WAREHOUSE_NAME', 'WAREHOUSE_TYPE', 'WAREHOUSE_TSHIRT_SIZE_CONFIG',
                                   'MIN_CLUSTER_COUNT', 'MAX_CLUSTER_COUNT', 'SCALING_POLICY',
                                   'AUTO_SUSPEND_SECONDS', 'AUTO_RESUME_ENABLED', 'QAS_ENABLED',
                                   'QAS_MAX_SCALE_FACTOR', 'PERIOD_TOTAL_CREDITS_CALCULATED',
                                   'WAREHOUSE_DETAILS_JSON'])


def create_warehouse_analysis_prompt(row: pd.Series, base_prompt: str, lookback_days: int) -> str:
    """
    Create a complete analysis prompt for a specific warehouse.

    Args:
        row: DataFrame row containing warehouse data
        base_prompt: Base prompt template
        lookback_days: Number of lookback days

    Returns:
        Complete prompt string for the warehouse
    """
    prompt = base_prompt.replace("{lookback_days_actual_value}", str(lookback_days))

    warehouse_data = f"""
Here is the data for warehouse '{row['WAREHOUSE_NAME']}':

WAREHOUSE_TYPE: {row['WAREHOUSE_TYPE']}
WAREHOUSE_TSHIRT_SIZE_CONFIG: {row['WAREHOUSE_TSHIRT_SIZE_CONFIG']}
MIN_CLUSTER_COUNT: {row['MIN_CLUSTER_COUNT']}
MAX_CLUSTER_COUNT: {row['MAX_CLUSTER_COUNT']}
SCALING_POLICY: {row['SCALING_POLICY']}
AUTO_SUSPEND_SECONDS: {row['AUTO_SUSPEND_SECONDS']}
AUTO_RESUME_ENABLED: {row['AUTO_RESUME_ENABLED']}
QAS_ENABLED: {row['QAS_ENABLED']}
QAS_MAX_SCALE_FACTOR: {row['QAS_MAX_SCALE_FACTOR']}
PERIOD_TOTAL_CREDITS_CALCULATED: {row['PERIOD_TOTAL_CREDITS_CALCULATED']}

WAREHOUSE_DETAILS_JSON:
{row['WAREHOUSE_DETAILS_JSON']}
"""

    final_prompt = prompt.replace("{{DATA_INJECTION_BLOCK}}", warehouse_data)

    return final_prompt


def run_warehouse_analysis(session, model_name: str, warehouses_df: pd.DataFrame,
                          base_prompt: str, lookback_days: int) -> Dict[str, str]:
    """
    Run Cortex analysis for multiple warehouses.

    Args:
        session: Snowflake session
        model_name: Cortex model name
        warehouses_df: DataFrame with warehouse data
        base_prompt: Base prompt template
        lookback_days: Lookback period in days

    Returns:
        Dictionary mapping warehouse names to analysis results
    """
    results = {}
    total_warehouses = len(warehouses_df)

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        for idx, (_, row) in enumerate(warehouses_df.iterrows()):
            warehouse_name = row['WAREHOUSE_NAME']

            progress = (idx + 1) / total_warehouses
            progress_bar.progress(progress)
            status_text.text(f"Analyzing warehouse {idx + 1}/{total_warehouses}: {warehouse_name}")

            warehouse_prompt = create_warehouse_analysis_prompt(row, base_prompt, lookback_days)

            analysis_result = call_cortex_llm(
                session,
                model_name,
                warehouse_prompt,
                f"warehouse_analysis_{warehouse_name}"
            )

            results[warehouse_name] = analysis_result

            time.sleep(0.1)

        progress_bar.empty()
        status_text.empty()

        return results

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error during warehouse analysis: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        return results


def prepare_portfolio_data(raw_df: pd.DataFrame, cortex_results_dict: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Prepare portfolio data for consolidation analysis.

    Args:
        raw_df: Raw warehouse data DataFrame
        cortex_results_dict: Dictionary of analysis results

    Returns:
        List of warehouse summaries for portfolio analysis
    """
    portfolio_summaries = []

    for _, row in raw_df.iterrows():
        warehouse_name = row['WAREHOUSE_NAME']
        analysis_text = cortex_results_dict.get(warehouse_name, "")

        avg_utilization = 1.0
        peak_running = 5.0
        peak_queued = 0.0

        inferred_env = "PROD"
        if any(substring in warehouse_name.upper() for substring in ["DEV", "TEST", "QA", "STAGE"]):
            inferred_env = "NON-PROD"

        inferred_workload = "MIXED"
        if "ETL" in warehouse_name.upper():
            inferred_workload = "ETL"
        elif any(substring in warehouse_name.upper() for substring in ["BI", "RPT", "DASH", "TABLEAU"]):
            inferred_workload = "BI"
        elif any(substring in warehouse_name.upper() for substring in ["DS", "ML", "ANALYTICS"]):
            inferred_workload = "ANALYTICS"

        recommendations = extract_key_recommendations(analysis_text)
        usage_pattern = extract_usage_pattern_summary(analysis_text)

        summary = {
            "WAREHOUSE_NAME": str(warehouse_name),
            "WAREHOUSE_TSHIRT_SIZE_CONFIG": str(row.get('WAREHOUSE_TSHIRT_SIZE_CONFIG', 'N/A')),
            "MIN_CLUSTER_COUNT": int(row.get('MIN_CLUSTER_COUNT', 0)),
            "MAX_CLUSTER_COUNT": int(row.get('MAX_CLUSTER_COUNT', 0)),
            "SCALING_POLICY": str(row.get('SCALING_POLICY', 'N/A')),
            "PERIOD_TOTAL_CREDITS_CALCULATED": float(row.get('PERIOD_TOTAL_CREDITS_CALCULATED', 0.0)),
            "PERIOD_AVG_UTILIZATION_FACTOR": float(avg_utilization),
            "PERIOD_PEAK_RUNNING_QUERIES": float(peak_running),
            "PERIOD_PEAK_QUEUED_LOAD": float(peak_queued),
            "INFERRED_ENVIRONMENT": str(inferred_env),
            "INFERRED_WORKLOAD_TYPE": str(inferred_workload),
            "USAGE_PATTERN_SUMMARY": usage_pattern,
            "INDIVIDUAL_RECOMMENDATIONS": recommendations
        }

        portfolio_summaries.append(summary)

    portfolio_summaries.sort(key=lambda x: x['PERIOD_TOTAL_CREDITS_CALCULATED'], reverse=True)

    return portfolio_summaries


def extract_key_recommendations(analysis_text: str) -> List[str]:
    """Extract key recommendations from analysis text."""
    if not isinstance(analysis_text, str):
        return ["Could not parse recommendations from analysis."]

    recommendations = []

    if "## SUMMARY AND ACTION ITEMS" in analysis_text:
        summary_section = analysis_text.split("## SUMMARY AND ACTION ITEMS")[1]

        if "## DETAILED ANALYSIS" in summary_section:
            summary_section = summary_section.split("## DETAILED ANALYSIS")[0]

        lines = summary_section.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith(('- ', '* ', '• ')) or line.startswith(tuple(f"{i}." for i in range(1, 10))):
                rec_text = line.lstrip('- * • ').lstrip('0123456789. ').strip()
                if rec_text:
                    recommendations.append(rec_text)

    return recommendations[:3] if recommendations else ["No specific recommendations identified."]


def extract_usage_pattern_summary(analysis_text: str) -> str:
    """Extract usage pattern summary from analysis text."""
    if not isinstance(analysis_text, str):
        return "Usage pattern could not be determined."

    if "business hours" in analysis_text.lower():
        return "Active during business hours"
    elif "24/7" in analysis_text.lower() or "continuous" in analysis_text.lower():
        return "Continuous 24/7 usage pattern"
    elif "batch" in analysis_text.lower() or "scheduled" in analysis_text.lower():
        return "Batch/scheduled workload pattern"
    elif "sporadic" in analysis_text.lower() or "ad-hoc" in analysis_text.lower():
        return "Sporadic ad-hoc usage pattern"
    else:
        return "Standard business usage pattern"


def run_portfolio_analysis(session, raw_df: pd.DataFrame, cortex_results_dict: Dict[str, str],
                          model_name: str, lookback_days: int) -> str:
    """
    Run portfolio-level consolidation analysis.

    Args:
        session: Snowflake session
        raw_df: Raw warehouse data
        cortex_results_dict: Individual analysis results
        model_name: Cortex model name
        lookback_days: Analysis period

    Returns:
        Portfolio analysis result string
    """
    try:
        from .warehouse_prompt import CONSOLIDATION_PROMPT_TEMPLATE

        portfolio_data = prepare_portfolio_data(raw_df, cortex_results_dict)

        if not portfolio_data:
            return "Error: Could not prepare portfolio data for analysis."

        portfolio_json = json.dumps(portfolio_data, indent=2)

        consolidation_prompt = CONSOLIDATION_PROMPT_TEMPLATE.replace(
            "{lookback_days_actual_value}", str(lookback_days)
        )
        consolidation_prompt = consolidation_prompt.replace(
            "{{MULTI_WAREHOUSE_SUMMARIES_JSON_BLOCK}}", portfolio_json
        )

        portfolio_result = call_cortex_llm(
            session,
            model_name,
            consolidation_prompt,
            "portfolio_consolidation_analysis"
        )

        return portfolio_result

    except Exception as e:
        return f"Error in portfolio analysis: {str(e)}"

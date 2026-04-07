# warehouse_charts.py
"""Chart visualization functions for warehouse analysis"""

import streamlit as st
import pandas as pd
import json
from typing import Dict, Any, Optional

def safe_to_numeric(series, errors='coerce'):
    """Converts a pandas Series to numeric, coercing errors."""
    return pd.to_numeric(series, errors=errors)

def plot_credits_over_time(df_period_data, time_col_name, granularity_label, chart_type="Line Chart"):
    """Plots total credits used over time."""
    credits_col = 'TOTAL_CREDITS_USED'
    if time_col_name not in df_period_data.columns or credits_col not in df_period_data.columns:
        # st.warning(f"Required columns ('{time_col_name}', '{credits_col}') not found for credit chart.")
        st.markdown(f'<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'⚠️&nbsp;&nbsp;Required columns ("{time_col_name}", "{credits_col}") not found for credit chart.'
                            '</div>', unsafe_allow_html=True)
        return

    chart_df = df_period_data.copy()
    chart_df[credits_col] = safe_to_numeric(chart_df[credits_col])
    chart_df = chart_df.set_index(time_col_name)

    st.subheader("Credits Consumption Over Time")
    if chart_type == "Line Chart":
        st.line_chart(chart_df[credits_col], use_container_width=True)
    elif chart_type == "Bar Chart":
        st.bar_chart(chart_df[credits_col], use_container_width=True)
    else:
        st.line_chart(chart_df[credits_col], use_container_width=True)
    st.caption(f"{credits_col} (per {granularity_label})")

def plot_load_and_queuing(df_period_data, time_col_name, granularity_label, chart_type="Line Chart"):
    """Plots average running queries and max queued load over time."""
    running_col = 'AVG_CONCURRENT_RUNNING_QUERIES'
    queued_col = 'MAX_QUEUED_LOAD'

    if not all(col in df_period_data.columns for col in [time_col_name, running_col, queued_col]):
        # st.warning(f"Required columns not found for load & queuing chart.")
        st.markdown(f'<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'⚠️&nbsp;&nbsp;Required columns not found for load & queuing chart.'
                            '</div>', unsafe_allow_html=True)
        return

    chart_df = df_period_data.copy()
    chart_df[running_col] = safe_to_numeric(chart_df[running_col])
    chart_df[queued_col] = safe_to_numeric(chart_df[queued_col])
    chart_df = chart_df.set_index(time_col_name)

    st.subheader("Query Load and Queuing")
    st.line_chart(chart_df[[running_col, queued_col]], use_container_width=True)
    st.caption(f"{running_col} vs. {queued_col} (per {granularity_label})")

def plot_p95_elapsed_time(df_period_data, time_col_name, granularity_label, chart_type="Line Chart"):
    """Plots P95 total elapsed time over time."""
    p95_col = 'P95_TOTAL_ELAPSED_TIME_SEC'
    if time_col_name not in df_period_data.columns or p95_col not in df_period_data.columns:
        # st.warning(f"Required columns not found for P95 elapsed time chart.")
        st.markdown(f'<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'⚠️&nbsp;&nbsp;Required columns not found for P95 elapsed time chart.'
                            '</div>', unsafe_allow_html=True)
        return

    chart_df = df_period_data.copy()
    chart_df[p95_col] = safe_to_numeric(chart_df[p95_col])
    chart_df = chart_df.set_index(time_col_name)

    st.subheader("P95 Query Elapsed Time")
    st.line_chart(chart_df[p95_col], use_container_width=True)
    st.caption(f"{p95_col} in seconds (per {granularity_label})")

def plot_spilling_gb_over_time(df_period_data, time_col_name, granularity_label, chart_type="Bar Chart"):
    """Plots total spilling (local + remote) in GB over time."""
    local_spill_col = 'TOTAL_BYTES_SPILLED_LOCAL_GB'
    remote_spill_col = 'TOTAL_BYTES_SPILLED_REMOTE_GB'

    if not all(col in df_period_data.columns for col in [time_col_name, local_spill_col, remote_spill_col]):
        # st.warning(f"Required columns not found for spilling chart.")
        st.markdown(f'<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'⚠️&nbsp;&nbsp;Required columns not found for spilling chart.'
                            '</div>', unsafe_allow_html=True)
        return

    chart_df = df_period_data.copy()
    chart_df['TOTAL_SPILL_GB'] = (safe_to_numeric(chart_df[local_spill_col]).fillna(0) +
                                  safe_to_numeric(chart_df[remote_spill_col]).fillna(0))
    chart_df = chart_df.set_index(time_col_name)

    st.subheader("Total Disk Spilling (Local + Remote)")
    if chart_type == "Bar Chart":
        st.bar_chart(chart_df['TOTAL_SPILL_GB'], use_container_width=True)
    elif chart_type == "Line Chart":
        st.line_chart(chart_df['TOTAL_SPILL_GB'], use_container_width=True)
    else:
        st.bar_chart(chart_df['TOTAL_SPILL_GB'], use_container_width=True)
    st.caption(f"Total Spilling in GB (per {granularity_label})")

def plot_total_queries(df_period_data, time_col_name, granularity_label, chart_type="Bar Chart"):
    """Plots total queries over time."""
    queries_col = 'TOTAL_QUERIES'
    if time_col_name not in df_period_data.columns or queries_col not in df_period_data.columns:
        # st.warning(f"Required columns not found for total queries chart.")
        st.markdown(f'<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'⚠️&nbsp;&nbsp;Required columns not found for total queries chart.'
                            '</div>', unsafe_allow_html=True)
        return

    chart_df = df_period_data.copy()
    chart_df[queries_col] = safe_to_numeric(chart_df[queries_col])
    chart_df = chart_df.set_index(time_col_name)

    st.subheader("Total Queries")
    if chart_type == "Bar Chart":
        st.bar_chart(chart_df[queries_col], use_container_width=True)
    elif chart_type == "Line Chart":
        st.line_chart(chart_df[queries_col], use_container_width=True)
    else:
        st.bar_chart(chart_df[queries_col], use_container_width=True)
    st.caption(f"{queries_col} (per {granularity_label})")

def plot_avg_time_components(df_period_data, time_col_name, granularity_label, chart_type="Line Chart"):
    """Plots Average Total Elapsed Time vs. Average Execution Time."""
    elapsed_col = 'AVG_TOTAL_ELAPSED_TIME_SEC'
    execution_col = 'AVG_EXECUTION_TIME_SEC'

    if not all(col in df_period_data.columns for col in [time_col_name, elapsed_col, execution_col]):
        # st.warning(f"Required columns not found for average time components chart.")
        st.markdown(f'<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'⚠️&nbsp;&nbsp;Required columns not found for average time components chart.'
                            '</div>', unsafe_allow_html=True)
        return

    chart_df = df_period_data.copy()
    chart_df[elapsed_col] = safe_to_numeric(chart_df[elapsed_col])
    chart_df[execution_col] = safe_to_numeric(chart_df[execution_col])
    chart_df = chart_df.set_index(time_col_name)

    st.subheader("Avg. Query Time Components")
    st.line_chart(chart_df[[elapsed_col, execution_col]], use_container_width=True)
    st.caption(f"{elapsed_col} vs. {execution_col} (per {granularity_label})")

def display_warehouse_summary_metrics(properties: dict, metrics: dict, warehouse_name: str):
    """Display warehouse configuration and summary metrics when no time series data is available."""
    st.markdown("#### 📊 Warehouse Configuration & Metrics Summary")

    # Configuration section
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🏗️ Configuration:**")
        config_data = {
            "Size": properties.get('size', 'Unknown'),
            "Auto Suspend": f"{properties.get('auto_suspend', 'Unknown')} seconds",
            "Auto Resume": str(properties.get('auto_resume', 'Unknown')),
            "QAS Enabled": str(properties.get('qas_enabled', 'Unknown')),
            "Scaling Policy": properties.get('scaling_policy', 'Unknown')
        }

        for key, value in config_data.items():
            st.metric(label=key, value=value)

    with col2:
        st.markdown("**📈 Metrics:**")

        # Display total credits with visual indicator
        total_credits = metrics.get('total_credits', 0)
        analysis_days = metrics.get('analysis_period_days', 0)

        st.metric(
            label="Total Credits Used",
            value=f"{total_credits:.2f}",
            help=f"Credits consumed over {analysis_days} days analysis period"
        )

        # Calculate daily average
        if analysis_days > 0:
            daily_avg = total_credits / analysis_days
            st.metric(
                label="Daily Average Credits",
                value=f"{daily_avg:.2f}",
                help="Average credits per day"
            )

        # Display cluster configuration
        min_clusters = properties.get('min_cluster_count', 0)
        max_clusters = properties.get('max_cluster_count', 0)

        if min_clusters and max_clusters:
            cluster_range = f"{min_clusters} - {max_clusters}" if min_clusters != max_clusters else str(min_clusters)
            st.metric(label="Cluster Range", value=cluster_range)

    # Credits visualization
    st.markdown("---")
    st.markdown("**💰 Credits Analysis:**")

    if total_credits > 0:
        # Simple visualization using Streamlit metrics and bars
        col1, col2, col3 = st.columns(3)

        with col1:
            cost_estimate = total_credits * 2  # Rough estimate, adjust as needed
            st.metric(
                label="Estimated Cost (USD)",
                value=f"${cost_estimate:.2f}",
                help="Estimated cost based on $2/credit (approximate)"
            )

        with col2:
            if analysis_days > 0:
                efficiency_score = min(100, (total_credits / (analysis_days * 24)) * 100)  # Simple efficiency metric
                st.metric(
                    label="Efficiency Score",
                    value=f"{efficiency_score:.0f}%",
                    help="Utilization efficiency based on continuous usage"
                )

        with col3:
            warehouse_size = properties.get('size', 'Unknown')
            size_multiplier = {
                'X-Small': 1, 'Small': 2, 'Medium': 4, 'Large': 8,
                'X-Large': 16, '2X-Large': 32, '3X-Large': 64, '4X-Large': 128
            }.get(warehouse_size, 1)

            if size_multiplier > 1:
                credits_per_size_unit = total_credits / size_multiplier if size_multiplier else total_credits
                st.metric(
                    label="Credits per Size Unit",
                    value=f"{credits_per_size_unit:.2f}",
                    help=f"Credits normalized by warehouse size ({warehouse_size})"
                )

    # Create a simple bar chart showing relative usage if multiple warehouses
    if total_credits > 0:
        st.markdown("---")
        st.markdown("**📊 Usage Visualization:**")

        # Create a simple progress bar showing relative usage
        max_possible_usage = analysis_days * 24  # 24 credits per day as baseline
        if max_possible_usage > 0:
            usage_percentage = min(100, (total_credits / max_possible_usage) * 100)
            st.progress(usage_percentage / 100)
            st.caption(f"Usage: {usage_percentage:.1f}% of theoretical maximum continuous usage")


def display_warehouse_charts(warehouse_details_json_str: str, warehouse_name: str):
    """Display warehouse performance charts from time series data exactly like the reference project."""
    if not warehouse_details_json_str or warehouse_details_json_str == '{}':
        st.markdown(f'<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'ℹ️&nbsp;&nbsp;No detailed data available for {warehouse_name} charts.'
                    f'</div>', unsafe_allow_html=True)
        return

    try:
        full_wh_data = json.loads(warehouse_details_json_str)
        properties = full_wh_data.get('properties', {})
        time_series_data_list = []
        column_headers = []
        granularity_label = "hour"
        time_col_for_charts = "USAGE_HOUR_UTC"

        # Check for hourly data first (primary data source)
        if 'HOURLY_DATA_COLUMN_HEADERS' in properties and 'hourly_info' in full_wh_data:
            column_headers = properties['HOURLY_DATA_COLUMN_HEADERS']
            time_series_data_list = full_wh_data['hourly_info']
            time_col_for_charts = column_headers[0] if column_headers else "USAGE_HOUR_UTC"
        # Check for daily data if no hourly data
        elif 'DAILY_DATA_COLUMN_HEADERS' in properties and 'daily_info' in full_wh_data:
            column_headers = properties['DAILY_DATA_COLUMN_HEADERS']
            time_series_data_list = full_wh_data['daily_info']
            granularity_label = "day"
            time_col_for_charts = column_headers[0] if column_headers else "USAGE_DAY_UTC"

        # Display charts only if we have proper time series data
        if time_series_data_list and column_headers and len(time_series_data_list) > 0:
            df_period_data = pd.DataFrame(time_series_data_list, columns=column_headers)

            # Ensure we have the time column
            if time_col_for_charts in df_period_data.columns and len(df_period_data) > 0:
                # Convert timestamp to datetime
                df_period_data[time_col_for_charts] = pd.to_datetime(df_period_data[time_col_for_charts])
                df_period_data = df_period_data.sort_values(by=time_col_for_charts)
                df_period_data.attrs['granularity'] = granularity_label

                # Display the 6 performance charts exactly like the reference project
                st.markdown("### Performance Charts")

                col1, col2 = st.columns(2)
                with col1:
                    # Chart 1: Credits Consumption Over Time
                    with st.container():
                        plot_credits_over_time(df_period_data, time_col_name=time_col_for_charts, granularity_label=granularity_label, chart_type="Line Chart")

                    # Chart 2: Query Load and Queuing
                    with st.container():
                        plot_load_and_queuing(df_period_data, time_col_name=time_col_for_charts, granularity_label=granularity_label)

                    # Chart 3: Total Disk Spilling (Local + Remote)
                    with st.container():
                        plot_spilling_gb_over_time(df_period_data, time_col_name=time_col_for_charts, granularity_label=granularity_label, chart_type="Bar Chart")

                with col2:
                    # Chart 4: Total Queries
                    with st.container():
                        plot_total_queries(df_period_data, time_col_name=time_col_for_charts, granularity_label=granularity_label, chart_type="Line Chart")

                    # Chart 5: P95 Query Elapsed Time
                    with st.container():
                        plot_p95_elapsed_time(df_period_data, time_col_name=time_col_for_charts, granularity_label=granularity_label)

                    # Chart 6: Avg. Query Time Components
                    with st.container():
                        plot_avg_time_components(df_period_data, time_col_name=time_col_for_charts, granularity_label=granularity_label)
            else:
                # st.warning(f"Time series data structure error for {warehouse_name} - missing time column '{time_col_for_charts}'")
                st.markdown(f'<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                    f'⚠️&nbsp;&nbsp;Time series data structure error for {warehouse_name} - missing time column "{time_col_for_charts}"'
                                    '</div>', unsafe_allow_html=True)
        else:
            # st.warning(f"No time series data found for {warehouse_name}. Charts require hourly or daily usage data.")
            st.markdown(f'<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                f'⚠️&nbsp;&nbsp;No time series data found for {warehouse_name}. Charts require hourly or daily usage data.'
                                '</div>', unsafe_allow_html=True)

    except Exception as e:
        # st.error(f"Error displaying charts for {warehouse_name}: {str(e)}")
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error displaying charts for {warehouse_name}: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        # Show debug info if needed
        if st.checkbox("Show debug info", key=f"debug_error_{warehouse_name}"):
            st.code(f"JSON structure: {warehouse_details_json_str[:1000]}...")
            import traceback
            st.code(traceback.format_exc())

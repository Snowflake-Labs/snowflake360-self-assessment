import streamlit as st
import pandas as pd
import plotly.graph_objects as go
try:
    from streamlit_echarts import st_echarts
except ImportError:
    def st_echarts(**kwargs):
        import streamlit as st
        st.info("Chart unavailable (echarts not supported in SiS)")


def comp_finops_visibility(entry_actions=None):
    """
    FinOPS Visibility Component

    Provides visibility into costs, forecasting, and cost breakdowns.

    Expanders:
    1. FinOPS Visibility Overview
    2. FinOPS Visibility Analyzer
    3. The Executive Forecast (Account Level)
    4. Compute Breakdown (By Feature & Warehouse)
    5. Top 20 Costliest Queries (With User Attribution)
    6. Storage Costs (By Database)
    7. Data Transfer Costs
    8. Cost Anomalies (Automated Detection)
    """
    try:
        st.markdown("### Visibility")

        # Expander 3: The Executive Forecast (Account Level)
        with st.expander("The Executive Forecast (Account Level)", expanded=True):
            _render_executive_forecast()

        # Expander 4: Compute Breakdown (By Feature & Warehouse)
        with st.expander("Compute Breakdown (By Feature & Warehouse)", expanded=True):
            _render_compute_breakdown()

        # Expander 5: Top 20 Costliest Queries (With User Attribution)
        with st.expander("Top 20 Costliest Queries (With User Attribution)", expanded=True):
            _render_costliest_queries()

        # Expander 6: Storage Costs (By Database)
        with st.expander("Storage Costs (By Database)", expanded=True):
            _render_storage_costs_by_database()

        # Expander 7: Data Transfer Costs
        with st.expander("Data Transfer Costs", expanded=True):
            _render_data_transfer_costs()

        # Expander 8: Cost Anomalies (Automated Detection)
        with st.expander("Cost Anomalies (Automated Detection)", expanded=True):
            _render_cost_anomalies()

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_executive_forecast():
    """Render The Executive Forecast (Account Level) expander content."""

    st.markdown("#### The Executive Forecast (Account Level)")

    # Introduction text
    st.markdown("""
    **Cost breakdown and forecast by category** (compute, storage, data transfer) showing last 30 days
    actual spend and projected costs for 1/3/6/12 months based on current consumption rates.
    """)

    try:
        # Get session context values for filtering
        execution_id = st.session_state.account_info.get('current_id', 0)
        account_id = st.session_state.account_info.get('account_id', 0)

        # Get cost rates from session
        credit_cost = st.session_state.account_info.get('credit_cost', 3.0)
        cost_per_tb = st.session_state.account_info.get('cost_per_tb', 23.0)
        xfer_per_tb = st.session_state.account_info.get('xfer_per_tb', 0.0)

        if execution_id == 0 or account_id == 0:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No execution context available. Please select an account first.'
                        '</div>', unsafe_allow_html=True)
            return

        # Executive Forecast Query
        forecast_query = f"""
WITH compute_cost AS (
    SELECT
        'Compute & Services' AS category,
        SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES) AS units,
        SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES) * {credit_cost} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
),
storage_cost AS (
    SELECT
        'Storage' AS category,
        AVG(storage_bytes + stage_bytes + failsafe_bytes) / POW(1024, 4) AS units_tb,
        (AVG(storage_bytes + stage_bytes + failsafe_bytes) / POW(1024, 4)) * {cost_per_tb} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.storage_usage
    WHERE usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
transfer_cost AS (
    SELECT
        'Data Transfer' AS category,
        SUM(bytes_transferred) / POW(1024, 3) AS units_gb,
        (SUM(bytes_transferred) / POW(1024, 3)) * {xfer_per_tb} AS cost_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.data_transfer_history
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
),
unioned_costs AS (
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
    ROUND(cost_last_30d * 12, 2) AS "EAC (Estimated Annual Consumption)"
FROM unioned_costs
"""

        # Display the query in terminal
        print("=" * 100)
        print("=" * 100)
        print(f"🏢 ACCOUNT_ID: {account_id}")
        print(f"💾 COST_PER_TB: ${cost_per_tb}")
        print("-" * 50)
        print(forecast_query)
        print("-" * 50)
        print("=" * 100)

        # Execute the query
        forecast_df = st.session_state.session.sql(forecast_query).to_pandas()

        if not forecast_df.empty:
            # Create Report Category and Metric for executive forecast
            finops_category = ReportCategory('finops_lite', 'FinOps (Lite)')
            forecast_metric = ReportMetric('executive_forecast', 'finops_lite', 'Executive Forecast (Account Level)')

            # Create a proper metric object for the dialogs
            class ForecastMetric:
                def __init__(self, data):
                    self.display_data = data
                    self.display_data_copy = data.copy()
                    self.has_custom_columns = False

            # Initialize forecast metric with data - this will persist across reruns
            if 'forecast_metric_obj' not in st.session_state:
                st.session_state.forecast_metric_obj = ForecastMetric(forecast_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.forecast_metric_obj.has_custom_columns:
                    st.session_state.forecast_metric_obj.display_data_copy = forecast_df.copy()
                    st.session_state.forecast_metric_obj.display_data = forecast_df

            # Format numeric columns for display
            numeric_cols = ["Actual Cost (Last 30 Days)", "Forecast (Next 1 Month)",
                           "Forecast (Next 3 Months)", "Forecast (Next 6 Months)",
                           "EAC (Estimated Annual Consumption)"]
            format_dict = {col: '${:,.2f}' for col in numeric_cols if col in forecast_df.columns}

            # Set dataframes for the report metric
            forecast_metric.dataframes = [st.session_state.forecast_metric_obj.display_data.style.format(format_dict)]

            # Create layout with buttons on top-right and table below
            button_row_empty, button_row_col = st.columns([0.75, 0.25])

            with button_row_col:
                # Create buttons side by side
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    # Gear icon button for "Set table" functionality
                    gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="forecast_config_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if gear_clicked:
                        _show_dialog(st.session_state.forecast_metric_obj, 'display_data', forecast_metric, None, None, None)

                with btn_col2:
                    # Report icon button for "Add to report" functionality
                    metric_exists = ReportManager().metric_exists(forecast_metric.key)
                    report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="forecast_config_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if report_clicked:
                        show_metric_dialog(finops_category, forecast_metric, metric_exists, False)

            # Display the table with formatting
            st.dataframe(
                st.session_state.forecast_metric_obj.display_data.style.format(format_dict),
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Cost Analysis Charts")

            # Row 1: Cost Distribution and Forecast Comparison
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container(border=True):
                st.markdown("##### Cost Distribution by Category (Last 30 Days)")
                _render_cost_distribution_chart(forecast_df)

            with chart_col2.container(border=True):
                st.markdown("##### Forecast Comparison by Category")
                _render_forecast_comparison_chart(forecast_df)

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No cost data available for the selected account.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading executive forecast: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure cost data is available.'
                    '</div>', unsafe_allow_html=True)


def _render_cost_distribution_chart(forecast_df):
    """Render cost distribution pie chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="cost_distribution_chart_type"
    )

    # Get actual cost data
    if "Actual Cost (Last 30 Days)" not in forecast_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No cost data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_cost_distribution_bar_chart(forecast_df)
    elif chart_type == "Pie Chart":
        _render_cost_distribution_pie_chart(forecast_df)
    elif chart_type == "Pie - Donut":
        _render_cost_distribution_donut_chart(forecast_df)
    else:  # Pie - Rose Chart
        _render_cost_distribution_rose_chart(forecast_df)


def _render_cost_distribution_bar_chart(forecast_df):
    """Render cost distribution bar chart using Plotly."""

    categories = forecast_df['Category'].tolist()
    costs = forecast_df['Actual Cost (Last 30 Days)'].tolist()
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=categories,
            y=costs,
            marker_color=colors[:len(categories)],
            text=[f"${val:,.2f}" for val in costs],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Cost: $%{y:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Category',
        yaxis_title='Cost ($)',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=50)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="cost_dist_bar_chart")


def _render_cost_distribution_pie_chart(forecast_df):
    """Render cost distribution standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Actual Cost (Last 30 Days)']), "name": f"{row['Category']} (${row['Actual Cost (Last 30 Days)']:,.2f})"}
        for _, row in forecast_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c"],
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["0%", "60%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="cost_dist_pie_chart")


def _render_cost_distribution_donut_chart(forecast_df):
    """Render cost distribution donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Actual Cost (Last 30 Days)']), "name": f"{row['Category']} (${row['Actual Cost (Last 30 Days)']:,.2f})"}
        for _, row in forecast_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c"],
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["30%", "60%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="cost_dist_donut_chart")


def _render_cost_distribution_rose_chart(forecast_df):
    """Render cost distribution rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Actual Cost (Last 30 Days)']), "name": f"{row['Category']} (${row['Actual Cost (Last 30 Days)']:,.2f})"}
        for _, row in forecast_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c"],
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": [20, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="cost_dist_rose_chart")


def _render_forecast_comparison_chart(forecast_df):
    """Render forecast comparison chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="forecast_comparison_chart_type"
    )

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_forecast_comparison_bar_chart(forecast_df)
    elif chart_type == "Pie Chart":
        _render_forecast_comparison_pie_chart(forecast_df)
    elif chart_type == "Pie - Donut":
        _render_forecast_comparison_donut_chart(forecast_df)
    else:  # Pie - Rose Chart
        _render_forecast_comparison_rose_chart(forecast_df)


def _render_forecast_comparison_bar_chart(forecast_df):
    """Render forecast comparison grouped bar chart using Plotly."""

    categories = forecast_df['Category'].tolist()

    fig = go.Figure()

    # Add bars for each forecast period
    forecast_periods = [
        ("Actual Cost (Last 30 Days)", "#1f77b4"),
        ("Forecast (Next 1 Month)", "#ff7f0e"),
        ("Forecast (Next 3 Months)", "#2ca02c"),
        ("Forecast (Next 6 Months)", "#d62728"),
        ("EAC (Estimated Annual Consumption)", "#9467bd")
    ]

    for period_name, color in forecast_periods:
        if period_name in forecast_df.columns:
            values = forecast_df[period_name].tolist()
            fig.add_trace(go.Bar(
                name=period_name.replace("Forecast ", "").replace("(", "").replace(")", ""),
                x=categories,
                y=values,
                marker_color=color,
                text=[f"${val:,.0f}" for val in values],
                textposition='outside',
                textfont=dict(size=8),
                hovertemplate='<b>%{x}</b><br>' + period_name + ': $%{y:,.2f}<extra></extra>'
            ))

    fig.update_layout(
        barmode='group',
        height=350,
        xaxis_title='Category',
        yaxis_title='Cost ($)',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.45,
            xanchor="center",
            x=0.5,
            font=dict(size=9)
        ),
        margin=dict(t=20, b=120, l=50, r=50)
    )

    st.plotly_chart(fig, use_container_width=True, key="forecast_comp_bar_chart")


def _render_forecast_comparison_pie_chart(forecast_df):
    """Render forecast comparison - EAC distribution pie chart using ECharts."""

    # For pie chart, show EAC distribution by category
    chart_data = [
        {"value": float(row['EAC (Estimated Annual Consumption)']), "name": f"{row['Category']} (${row['EAC (Estimated Annual Consumption)']:,.0f})"}
        for _, row in forecast_df.iterrows()
        if 'EAC (Estimated Annual Consumption)' in forecast_df.columns
    ]

    option = {
        "title": {
            "text": "Annual Consumption (EAC)",
            "left": "center",
            "top": "0",
            "textStyle": {"fontSize": 12}
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c"],
        "series": [
            {
                "name": "EAC",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "50%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="forecast_comp_pie_chart")


def _render_forecast_comparison_donut_chart(forecast_df):
    """Render forecast comparison - EAC distribution donut chart using ECharts."""

    chart_data = [
        {"value": float(row['EAC (Estimated Annual Consumption)']), "name": f"{row['Category']} (${row['EAC (Estimated Annual Consumption)']:,.0f})"}
        for _, row in forecast_df.iterrows()
        if 'EAC (Estimated Annual Consumption)' in forecast_df.columns
    ]

    option = {
        "title": {
            "text": "Annual Consumption (EAC)",
            "left": "center",
            "top": "0",
            "textStyle": {"fontSize": 12}
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c"],
        "series": [
            {
                "name": "EAC",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "50%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="forecast_comp_donut_chart")


def _render_forecast_comparison_rose_chart(forecast_df):
    """Render forecast comparison - EAC distribution rose chart using ECharts."""

    chart_data = [
        {"value": float(row['EAC (Estimated Annual Consumption)']), "name": f"{row['Category']} (${row['EAC (Estimated Annual Consumption)']:,.0f})"}
        for _, row in forecast_df.iterrows()
        if 'EAC (Estimated Annual Consumption)' in forecast_df.columns
    ]

    option = {
        "title": {
            "text": "Annual Consumption (EAC)",
            "left": "center",
            "top": "0",
            "textStyle": {"fontSize": 12}
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c"],
        "series": [
            {
                "name": "EAC",
                "type": "pie",
                "radius": [20, 95],
                "center": ["50%", "50%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="forecast_comp_rose_chart")


def _render_compute_breakdown():
    """Render Compute Breakdown (By Feature & Warehouse) expander content."""

    st.markdown("#### Compute Breakdown (By Feature & Warehouse)")

    # Introduction text
    st.markdown("""
    **Top 20 resources by cost over last 30 days** showing service type, credits/cost, estimated annual cost,
    and percentage of total compute spend.
    """)

    try:
        # Get session context values for filtering
        execution_id = st.session_state.account_info.get('current_id', 0)
        account_id = st.session_state.account_info.get('account_id', 0)

        # Get cost rates from session
        credit_cost = st.session_state.account_info.get('credit_cost', 3.0)

        if execution_id == 0 or account_id == 0:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No execution context available. Please select an account first.'
                        '</div>', unsafe_allow_html=True)
            return

        # Compute Breakdown Query
        compute_breakdown_query = f"""
WITH resource_metrics AS (
    -- 1. Get detailed Warehouse-level spend
    SELECT
        'WAREHOUSE_METERING' AS service_type,
        WAREHOUSE_NAME AS resource_name,
        SUM(CREDITS_USED) AS credits_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    GROUP BY 1, 2

    UNION ALL

    -- 2. Get other Service Types (AI, Pipes, etc.) from Daily History
    -- We filter out 'WAREHOUSE_METERING' here to avoid double-counting
    SELECT
        SERVICE_TYPE,
        SERVICE_TYPE AS resource_name,
        SUM(CREDITS_USED) AS credits_last_30d
    FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
    WHERE USAGE_DATE >= DATEADD('day', -30, CURRENT_DATE())
      AND SERVICE_TYPE NOT IN ('WAREHOUSE_METERING', 'WAREHOUSE_METERING_READER')
    GROUP BY 1, 2
),
final_calculation AS (
    SELECT
        service_type,
        resource_name,
        ROUND(credits_last_30d, 1) AS credits_last_30d,
        ROUND(credits_last_30d * {credit_cost}, 2) AS cost_last_30d,
        ROUND((credits_last_30d * {credit_cost}) * 12, 0) AS estimated_annual_cost
    FROM resource_metrics
)
SELECT
    service_type AS "Service Type",
    resource_name AS "Resource Name",
    credits_last_30d AS "Credits (Last 30 Days)",
    cost_last_30d AS "Cost (Last 30 Days)",
    estimated_annual_cost AS "Estimated Annual Cost",
    ROUND(RATIO_TO_REPORT(cost_last_30d) OVER () * 100, 2) AS "% of Total Compute"
FROM final_calculation
WHERE cost_last_30d > 0
ORDER BY cost_last_30d DESC
LIMIT 20
"""

        # Display the query in terminal
        print("=" * 100)
        print("=" * 100)
        print(f"🏢 ACCOUNT_ID: {account_id}")
        print("-" * 50)
        print(compute_breakdown_query)
        print("-" * 50)
        print("=" * 100)

        # Execute the query
        compute_df = st.session_state.session.sql(compute_breakdown_query).to_pandas()

        if not compute_df.empty:
            # Create Report Category and Metric for compute breakdown
            finops_category = ReportCategory('finops_lite', 'FinOps (Lite)')
            compute_metric = ReportMetric('compute_breakdown', 'finops_lite', 'Compute Breakdown (By Feature & Warehouse)')

            # Create a proper metric object for the dialogs
            class ComputeMetric:
                def __init__(self, data):
                    self.display_data = data
                    self.display_data_copy = data.copy()
                    self.has_custom_columns = False

            # Initialize compute metric with data - this will persist across reruns
            if 'compute_breakdown_metric_obj' not in st.session_state:
                st.session_state.compute_breakdown_metric_obj = ComputeMetric(compute_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.compute_breakdown_metric_obj.has_custom_columns:
                    st.session_state.compute_breakdown_metric_obj.display_data_copy = compute_df.copy()
                    st.session_state.compute_breakdown_metric_obj.display_data = compute_df

            # Format numeric columns for display
            format_dict = {
                "Credits (Last 30 Days)": '{:,.1f}',
                "Cost (Last 30 Days)": '${:,.2f}',
                "Estimated Annual Cost": '${:,.0f}',
                "% of Total Compute": '{:.2f}%'
            }
            # Filter to only columns that exist
            format_dict = {k: v for k, v in format_dict.items() if k in compute_df.columns}

            # Set dataframes for the report metric
            compute_metric.dataframes = [st.session_state.compute_breakdown_metric_obj.display_data.style.format(format_dict)]

            # Create layout with buttons on top-right and table below
            button_row_empty, button_row_col = st.columns([0.75, 0.25])

            with button_row_col:
                # Create buttons side by side
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    # Gear icon button for "Set table" functionality
                    gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="compute_breakdown_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if gear_clicked:
                        _show_dialog(st.session_state.compute_breakdown_metric_obj, 'display_data', compute_metric, None, None, None)

                with btn_col2:
                    # Report icon button for "Add to report" functionality
                    metric_exists = ReportManager().metric_exists(compute_metric.key)
                    report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="compute_breakdown_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if report_clicked:
                        show_metric_dialog(finops_category, compute_metric, metric_exists, False)

            # Display the table with formatting
            st.dataframe(
                st.session_state.compute_breakdown_metric_obj.display_data.style.format(format_dict),
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Compute Cost Analysis Charts")

            # Row 1: Cost by Service Type and Top Resources
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container(border=True):
                st.markdown("##### Cost by Service Type (Last 30 Days)")
                _render_cost_by_service_type_chart(compute_df)

            with chart_col2.container(border=True):
                st.markdown("##### Top 10 Resources by Cost")
                _render_top_resources_chart(compute_df)

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No compute breakdown data available for the selected account.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading compute breakdown: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure metering data is available.'
                    '</div>', unsafe_allow_html=True)


def _render_cost_by_service_type_chart(compute_df):
    """Render cost by service type chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="cost_by_service_type_chart_type"
    )

    # Aggregate by service type
    if "Service Type" not in compute_df.columns or "Cost (Last 30 Days)" not in compute_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No service type data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    # Group by service type
    service_type_df = compute_df.groupby("Service Type")["Cost (Last 30 Days)"].sum().reset_index()
    service_type_df = service_type_df.sort_values("Cost (Last 30 Days)", ascending=False)

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_service_type_bar_chart(service_type_df)
    elif chart_type == "Pie Chart":
        _render_service_type_pie_chart(service_type_df)
    elif chart_type == "Pie - Donut":
        _render_service_type_donut_chart(service_type_df)
    else:  # Pie - Rose Chart
        _render_service_type_rose_chart(service_type_df)


def _render_service_type_bar_chart(service_type_df):
    """Render service type bar chart using Plotly."""

    categories = service_type_df['Service Type'].tolist()
    costs = service_type_df['Cost (Last 30 Days)'].tolist()

    fig_bar = go.Figure(data=[
        go.Bar(
            x=categories,
            y=costs,
            marker_color='#1f77b4',
            text=[f"${val:,.2f}" for val in costs],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Cost: $%{y:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Service Type',
        yaxis_title='Cost ($)',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=50),
        xaxis=dict(tickangle=45)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="service_type_bar_chart")


def _render_service_type_pie_chart(service_type_df):
    """Render service type standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Cost (Last 30 Days)']), "name": f"{row['Service Type']} (${row['Cost (Last 30 Days)']:,.2f})"}
        for _, row in service_type_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="service_type_pie_chart")


def _render_service_type_donut_chart(service_type_df):
    """Render service type donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Cost (Last 30 Days)']), "name": f"{row['Service Type']} (${row['Cost (Last 30 Days)']:,.2f})"}
        for _, row in service_type_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="service_type_donut_chart")


def _render_service_type_rose_chart(service_type_df):
    """Render service type rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Cost (Last 30 Days)']), "name": f"{row['Service Type']} (${row['Cost (Last 30 Days)']:,.2f})"}
        for _, row in service_type_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": [20, 95],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="service_type_rose_chart")


def _render_top_resources_chart(compute_df):
    """Render top resources chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="top_resources_chart_type"
    )

    # Get top 10 resources
    if "Resource Name" not in compute_df.columns or "Cost (Last 30 Days)" not in compute_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No resource data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    top_resources_df = compute_df.head(10).copy()

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_top_resources_bar_chart(top_resources_df)
    elif chart_type == "Pie Chart":
        _render_top_resources_pie_chart(top_resources_df)
    elif chart_type == "Pie - Donut":
        _render_top_resources_donut_chart(top_resources_df)
    else:  # Pie - Rose Chart
        _render_top_resources_rose_chart(top_resources_df)


def _render_top_resources_bar_chart(top_resources_df):
    """Render top resources bar chart using Plotly."""

    resources = top_resources_df['Resource Name'].tolist()
    costs = top_resources_df['Cost (Last 30 Days)'].tolist()

    # Use horizontal bar for better label visibility
    fig_bar = go.Figure(data=[
        go.Bar(
            y=resources[::-1],  # Reverse for descending order from top
            x=costs[::-1],
            orientation='h',
            marker_color='#ff7f0e',
            text=[f"${val:,.2f}" for val in costs[::-1]],
            textposition='outside',
            textfont=dict(size=9),
            hovertemplate='<b>%{y}</b><br>Cost: $%{x:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Cost ($)',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="top_resources_bar_chart")


def _render_top_resources_pie_chart(top_resources_df):
    """Render top resources standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Cost (Last 30 Days)']), "name": f"{row['Resource Name'][:20]}... (${row['Cost (Last 30 Days)']:,.0f})" if len(str(row['Resource Name'])) > 20 else f"{row['Resource Name']} (${row['Cost (Last 30 Days)']:,.0f})"}
        for _, row in top_resources_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="top_resources_pie_chart")


def _render_top_resources_donut_chart(top_resources_df):
    """Render top resources donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Cost (Last 30 Days)']), "name": f"{row['Resource Name'][:20]}... (${row['Cost (Last 30 Days)']:,.0f})" if len(str(row['Resource Name'])) > 20 else f"{row['Resource Name']} (${row['Cost (Last 30 Days)']:,.0f})"}
        for _, row in top_resources_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="top_resources_donut_chart")


def _render_top_resources_rose_chart(top_resources_df):
    """Render top resources rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Cost (Last 30 Days)']), "name": f"{row['Resource Name'][:20]}... (${row['Cost (Last 30 Days)']:,.0f})" if len(str(row['Resource Name'])) > 20 else f"{row['Resource Name']} (${row['Cost (Last 30 Days)']:,.0f})"}
        for _, row in top_resources_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": [15, 85],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="top_resources_rose_chart")


def _render_costliest_queries():
    """Render Top 20 Costliest Queries (With User Attribution) expander content."""

    st.markdown("#### Top 20 Costliest Queries (With User Attribution)")

    # Introduction text
    st.markdown("""
    **Top 20 most expensive individual queries over last 30 days** showing cost, user, warehouse,
    query ID, and query text preview based on attributed compute credits.
    """)

    try:
        # Get session context values for filtering
        execution_id = st.session_state.account_info.get('current_id', 0)
        account_id = st.session_state.account_info.get('account_id', 0)

        # Get cost rates from session
        credit_cost = st.session_state.account_info.get('credit_cost', 3.0)

        if execution_id == 0 or account_id == 0:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No execution context available. Please select an account first.'
                        '</div>', unsafe_allow_html=True)
            return

        # Costliest Queries Query
        costliest_queries_query = f"""
WITH query_costs AS (
    SELECT
        query_id,
        user_name,
        warehouse_name,
        credits_attributed_compute,
        credits_attributed_compute * {credit_cost} AS query_cost_usd
    FROM SNOWFLAKE.ACCOUNT_USAGE.query_attribution_history
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
)
SELECT
    qc.query_cost_usd AS "Query Cost ($)",
    qc.user_name AS "User Name",
    qc.warehouse_name AS "Warehouse Name",
    qc.query_id AS "Query ID",
    LEFT(qh.query_text, 100) AS "Query Text Preview"
FROM query_costs qc
JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history qh
    ON qc.query_id = qh.query_id
ORDER BY qc.query_cost_usd DESC
LIMIT 20
"""

        # Display the query in terminal
        print("=" * 100)
        print("=" * 100)
        print(f"🏢 ACCOUNT_ID: {account_id}")
        print("-" * 50)
        print(costliest_queries_query)
        print("-" * 50)
        print("=" * 100)

        # Execute the query
        queries_df = st.session_state.session.sql(costliest_queries_query).to_pandas()

        if not queries_df.empty:
            # Create Report Category and Metric for costliest queries
            finops_category = ReportCategory('finops_lite', 'FinOps (Lite)')
            queries_metric = ReportMetric('costliest_queries', 'finops_lite', 'Top 20 Costliest Queries')

            # Create a proper metric object for the dialogs
            class QueriesMetric:
                def __init__(self, data):
                    self.display_data = data
                    self.display_data_copy = data.copy()
                    self.has_custom_columns = False

            # Initialize queries metric with data - this will persist across reruns
            if 'costliest_queries_metric_obj' not in st.session_state:
                st.session_state.costliest_queries_metric_obj = QueriesMetric(queries_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.costliest_queries_metric_obj.has_custom_columns:
                    st.session_state.costliest_queries_metric_obj.display_data_copy = queries_df.copy()
                    st.session_state.costliest_queries_metric_obj.display_data = queries_df

            # Format numeric columns for display
            format_dict = {
                "Query Cost ($)": '${:,.4f}'
            }
            # Filter to only columns that exist
            format_dict = {k: v for k, v in format_dict.items() if k in queries_df.columns}

            # Set dataframes for the report metric
            queries_metric.dataframes = [st.session_state.costliest_queries_metric_obj.display_data.style.format(format_dict)]

            # Create layout with buttons on top-right and table below
            button_row_empty, button_row_col = st.columns([0.75, 0.25])

            with button_row_col:
                # Create buttons side by side
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    # Gear icon button for "Set table" functionality
                    gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="costliest_queries_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if gear_clicked:
                        _show_dialog(st.session_state.costliest_queries_metric_obj, 'display_data', queries_metric, None, None, None)

                with btn_col2:
                    # Report icon button for "Add to report" functionality
                    metric_exists = ReportManager().metric_exists(queries_metric.key)
                    report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="costliest_queries_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if report_clicked:
                        show_metric_dialog(finops_category, queries_metric, metric_exists, False)

            # Display the table with formatting
            st.dataframe(
                st.session_state.costliest_queries_metric_obj.display_data.style.format(format_dict),
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Query Cost Analysis Charts")

            # Row 1: Cost by User and Cost by Warehouse
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container(border=True):
                st.markdown("##### Query Cost by User (Top 10)")
                _render_cost_by_user_chart(queries_df)

            with chart_col2.container(border=True):
                st.markdown("##### Query Cost by Warehouse (Top 10)")
                _render_cost_by_warehouse_chart(queries_df)

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No costliest queries data available for the selected account.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading costliest queries: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure query attribution history data is available.'
                    '</div>', unsafe_allow_html=True)


def _render_cost_by_user_chart(queries_df):
    """Render cost by user chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="cost_by_user_chart_type"
    )

    # Aggregate by user
    if "User Name" not in queries_df.columns or "Query Cost ($)" not in queries_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No user data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    # Group by user and get top 10
    user_df = queries_df.groupby("User Name")["Query Cost ($)"].sum().reset_index()
    user_df = user_df.sort_values("Query Cost ($)", ascending=False).head(10)

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_user_cost_bar_chart(user_df)
    elif chart_type == "Pie Chart":
        _render_user_cost_pie_chart(user_df)
    elif chart_type == "Pie - Donut":
        _render_user_cost_donut_chart(user_df)
    else:  # Pie - Rose Chart
        _render_user_cost_rose_chart(user_df)


def _render_user_cost_bar_chart(user_df):
    """Render user cost bar chart using Plotly."""

    users = user_df['User Name'].tolist()
    costs = user_df['Query Cost ($)'].tolist()

    # Use horizontal bar for better label visibility
    fig_bar = go.Figure(data=[
        go.Bar(
            y=users[::-1],  # Reverse for descending order from top
            x=costs[::-1],
            orientation='h',
            marker_color='#2ca02c',
            text=[f"${val:,.2f}" for val in costs[::-1]],
            textposition='outside',
            textfont=dict(size=9),
            hovertemplate='<b>%{y}</b><br>Cost: $%{x:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Total Query Cost ($)',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="user_cost_bar_chart")


def _render_user_cost_pie_chart(user_df):
    """Render user cost standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Query Cost ($)']), "name": f"{row['User Name']} (${row['Query Cost ($)']:,.2f})"}
        for _, row in user_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="user_cost_pie_chart")


def _render_user_cost_donut_chart(user_df):
    """Render user cost donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Query Cost ($)']), "name": f"{row['User Name']} (${row['Query Cost ($)']:,.2f})"}
        for _, row in user_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="user_cost_donut_chart")


def _render_user_cost_rose_chart(user_df):
    """Render user cost rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Query Cost ($)']), "name": f"{row['User Name']} (${row['Query Cost ($)']:,.2f})"}
        for _, row in user_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": [15, 85],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="user_cost_rose_chart")


def _render_cost_by_warehouse_chart(queries_df):
    """Render cost by warehouse chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="cost_by_warehouse_chart_type"
    )

    # Aggregate by warehouse
    if "Warehouse Name" not in queries_df.columns or "Query Cost ($)" not in queries_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No warehouse data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    # Group by warehouse and get top 10
    warehouse_df = queries_df.groupby("Warehouse Name")["Query Cost ($)"].sum().reset_index()
    warehouse_df = warehouse_df.sort_values("Query Cost ($)", ascending=False).head(10)

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_warehouse_cost_bar_chart(warehouse_df)
    elif chart_type == "Pie Chart":
        _render_warehouse_cost_pie_chart(warehouse_df)
    elif chart_type == "Pie - Donut":
        _render_warehouse_cost_donut_chart(warehouse_df)
    else:  # Pie - Rose Chart
        _render_warehouse_cost_rose_chart(warehouse_df)


def _render_warehouse_cost_bar_chart(warehouse_df):
    """Render warehouse cost bar chart using Plotly."""

    warehouses = warehouse_df['Warehouse Name'].tolist()
    costs = warehouse_df['Query Cost ($)'].tolist()

    # Use horizontal bar for better label visibility
    fig_bar = go.Figure(data=[
        go.Bar(
            y=warehouses[::-1],  # Reverse for descending order from top
            x=costs[::-1],
            orientation='h',
            marker_color='#d62728',
            text=[f"${val:,.2f}" for val in costs[::-1]],
            textposition='outside',
            textfont=dict(size=9),
            hovertemplate='<b>%{y}</b><br>Cost: $%{x:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Total Query Cost ($)',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="warehouse_cost_bar_chart")


def _render_warehouse_cost_pie_chart(warehouse_df):
    """Render warehouse cost standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Query Cost ($)']), "name": f"{row['Warehouse Name']} (${row['Query Cost ($)']:,.2f})"}
        for _, row in warehouse_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="warehouse_cost_pie_chart")


def _render_warehouse_cost_donut_chart(warehouse_df):
    """Render warehouse cost donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Query Cost ($)']), "name": f"{row['Warehouse Name']} (${row['Query Cost ($)']:,.2f})"}
        for _, row in warehouse_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="warehouse_cost_donut_chart")


def _render_warehouse_cost_rose_chart(warehouse_df):
    """Render warehouse cost rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Query Cost ($)']), "name": f"{row['Warehouse Name']} (${row['Query Cost ($)']:,.2f})"}
        for _, row in warehouse_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Cost",
                "type": "pie",
                "radius": [15, 85],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="warehouse_cost_rose_chart")


def _render_storage_costs_by_database():
    """Render Storage Costs (By Database) expander content."""

    st.markdown("#### Storage Costs (By Database)")

    # Get cost_per_tb for dynamic introduction
    cost_per_tb = st.session_state.account_info.get('cost_per_tb', 23.0)

    # Introduction text with dynamic cost_per_tb
    st.markdown(f"""
    **Latest daily database storage costs** showing average GB/TB, daily cost (${cost_per_tb}/TB),
    and projected monthly cost per database, ordered by highest daily cost.
    """)

    try:
        # Get session context values for filtering
        execution_id = st.session_state.account_info.get('current_id', 0)
        account_id = st.session_state.account_info.get('account_id', 0)

        if execution_id == 0 or account_id == 0:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No execution context available. Please select an account first.'
                        '</div>', unsafe_allow_html=True)
            return

        # Storage Costs Query
        storage_costs_query = f"""
SELECT
    usage_date AS "Usage Date",
    database_name AS "Database Name",

    -- Volume
    ROUND(AVG(average_database_bytes) / POW(1024, 3), 2) AS "Avg GB",
    ROUND(AVG(average_database_bytes) / POW(1024, 4), 4) AS "Avg TB",

    -- Cost
    ROUND((AVG(average_database_bytes) / POW(1024, 4)) * {cost_per_tb}, 2) AS "Daily Cost ($)",

    -- Monthly Projection (Daily * 30)
    ROUND(((AVG(average_database_bytes) / POW(1024, 4)) * {cost_per_tb}) * 30, 2) AS "Est Monthly Cost ($)"

FROM SNOWFLAKE.ACCOUNT_USAGE.database_storage_usage_history
WHERE usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
QUALIFY ROW_NUMBER() OVER (PARTITION BY database_name ORDER BY usage_date DESC) = 1
ORDER BY "Daily Cost ($)" DESC
"""

        # Display the query in terminal
        print("=" * 100)
        print("=" * 100)
        print(f"🏢 ACCOUNT_ID: {account_id}")
        print(f"💾 COST_PER_TB: ${cost_per_tb}")
        print("-" * 50)
        print(storage_costs_query)
        print("-" * 50)
        print("=" * 100)

        # Execute the query
        storage_df = st.session_state.session.sql(storage_costs_query).to_pandas()

        if not storage_df.empty:
            # Create Report Category and Metric for storage costs
            finops_category = ReportCategory('finops_lite', 'FinOps (Lite)')
            storage_metric = ReportMetric('storage_costs_by_database', 'finops_lite', 'Storage Costs (By Database)')

            # Create a proper metric object for the dialogs
            class StorageMetric:
                def __init__(self, data):
                    self.display_data = data
                    self.display_data_copy = data.copy()
                    self.has_custom_columns = False

            # Initialize storage metric with data - this will persist across reruns
            if 'storage_costs_metric_obj' not in st.session_state:
                st.session_state.storage_costs_metric_obj = StorageMetric(storage_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.storage_costs_metric_obj.has_custom_columns:
                    st.session_state.storage_costs_metric_obj.display_data_copy = storage_df.copy()
                    st.session_state.storage_costs_metric_obj.display_data = storage_df

            # Format numeric columns for display
            format_dict = {
                "Avg GB": '{:,.2f}',
                "Avg TB": '{:,.4f}',
                "Daily Cost ($)": '${:,.2f}',
                "Est Monthly Cost ($)": '${:,.2f}'
            }
            # Filter to only columns that exist
            format_dict = {k: v for k, v in format_dict.items() if k in storage_df.columns}

            # Set dataframes for the report metric
            storage_metric.dataframes = [st.session_state.storage_costs_metric_obj.display_data.style.format(format_dict)]

            # Create layout with buttons on top-right and table below
            button_row_empty, button_row_col = st.columns([0.75, 0.25])

            with button_row_col:
                # Create buttons side by side
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    # Gear icon button for "Set table" functionality
                    gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="storage_costs_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if gear_clicked:
                        _show_dialog(st.session_state.storage_costs_metric_obj, 'display_data', storage_metric, None, None, None)

                with btn_col2:
                    # Report icon button for "Add to report" functionality
                    metric_exists = ReportManager().metric_exists(storage_metric.key)
                    report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="storage_costs_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if report_clicked:
                        show_metric_dialog(finops_category, storage_metric, metric_exists, False)

            # Display the table with formatting
            st.dataframe(
                st.session_state.storage_costs_metric_obj.display_data.style.format(format_dict),
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Storage Cost Analysis Charts")

            # Row 1: Daily Cost Distribution and Monthly Cost Projection
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container(border=True):
                st.markdown("##### Daily Storage Cost by Database (Top 10)")
                _render_daily_storage_cost_chart(storage_df)

            with chart_col2.container(border=True):
                st.markdown("##### Estimated Monthly Cost by Database (Top 10)")
                _render_monthly_storage_cost_chart(storage_df)

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No storage cost data available for the selected account.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading storage costs: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure database storage usage history data is available.'
                    '</div>', unsafe_allow_html=True)


def _render_daily_storage_cost_chart(storage_df):
    """Render daily storage cost chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="daily_storage_cost_chart_type"
    )

    # Get top 10 databases by daily cost
    if "Database Name" not in storage_df.columns or "Daily Cost ($)" not in storage_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No database data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    top_storage_df = storage_df.head(10).copy()

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_daily_storage_bar_chart(top_storage_df)
    elif chart_type == "Pie Chart":
        _render_daily_storage_pie_chart(top_storage_df)
    elif chart_type == "Pie - Donut":
        _render_daily_storage_donut_chart(top_storage_df)
    else:  # Pie - Rose Chart
        _render_daily_storage_rose_chart(top_storage_df)


def _render_daily_storage_bar_chart(top_storage_df):
    """Render daily storage cost bar chart using Plotly."""

    databases = top_storage_df['Database Name'].tolist()
    costs = top_storage_df['Daily Cost ($)'].tolist()

    # Use horizontal bar for better label visibility
    fig_bar = go.Figure(data=[
        go.Bar(
            y=databases[::-1],  # Reverse for descending order from top
            x=costs[::-1],
            orientation='h',
            marker_color='#9467bd',
            text=[f"${val:,.2f}" for val in costs[::-1]],
            textposition='outside',
            textfont=dict(size=9),
            hovertemplate='<b>%{y}</b><br>Daily Cost: $%{x:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Daily Cost ($)',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="daily_storage_bar_chart")


def _render_daily_storage_pie_chart(top_storage_df):
    """Render daily storage cost standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Daily Cost ($)']), "name": f"{row['Database Name'][:15]}... (${row['Daily Cost ($)']:,.2f})" if len(str(row['Database Name'])) > 15 else f"{row['Database Name']} (${row['Daily Cost ($)']:,.2f})"}
        for _, row in top_storage_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Daily Cost",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="daily_storage_pie_chart")


def _render_daily_storage_donut_chart(top_storage_df):
    """Render daily storage cost donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Daily Cost ($)']), "name": f"{row['Database Name'][:15]}... (${row['Daily Cost ($)']:,.2f})" if len(str(row['Database Name'])) > 15 else f"{row['Database Name']} (${row['Daily Cost ($)']:,.2f})"}
        for _, row in top_storage_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Daily Cost",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="daily_storage_donut_chart")


def _render_daily_storage_rose_chart(top_storage_df):
    """Render daily storage cost rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Daily Cost ($)']), "name": f"{row['Database Name'][:15]}... (${row['Daily Cost ($)']:,.2f})" if len(str(row['Database Name'])) > 15 else f"{row['Database Name']} (${row['Daily Cost ($)']:,.2f})"}
        for _, row in top_storage_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Daily Cost",
                "type": "pie",
                "radius": [15, 85],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="daily_storage_rose_chart")


def _render_monthly_storage_cost_chart(storage_df):
    """Render monthly storage cost chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="monthly_storage_cost_chart_type"
    )

    # Get top 10 databases by monthly cost
    if "Database Name" not in storage_df.columns or "Est Monthly Cost ($)" not in storage_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No database data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    top_storage_df = storage_df.head(10).copy()

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_monthly_storage_bar_chart(top_storage_df)
    elif chart_type == "Pie Chart":
        _render_monthly_storage_pie_chart(top_storage_df)
    elif chart_type == "Pie - Donut":
        _render_monthly_storage_donut_chart(top_storage_df)
    else:  # Pie - Rose Chart
        _render_monthly_storage_rose_chart(top_storage_df)


def _render_monthly_storage_bar_chart(top_storage_df):
    """Render monthly storage cost bar chart using Plotly."""

    databases = top_storage_df['Database Name'].tolist()
    costs = top_storage_df['Est Monthly Cost ($)'].tolist()

    # Use horizontal bar for better label visibility
    fig_bar = go.Figure(data=[
        go.Bar(
            y=databases[::-1],  # Reverse for descending order from top
            x=costs[::-1],
            orientation='h',
            marker_color='#17becf',
            text=[f"${val:,.2f}" for val in costs[::-1]],
            textposition='outside',
            textfont=dict(size=9),
            hovertemplate='<b>%{y}</b><br>Est Monthly Cost: $%{x:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Est Monthly Cost ($)',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="monthly_storage_bar_chart")


def _render_monthly_storage_pie_chart(top_storage_df):
    """Render monthly storage cost standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Est Monthly Cost ($)']), "name": f"{row['Database Name'][:15]}... (${row['Est Monthly Cost ($)']:,.0f})" if len(str(row['Database Name'])) > 15 else f"{row['Database Name']} (${row['Est Monthly Cost ($)']:,.0f})"}
        for _, row in top_storage_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Monthly Cost",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="monthly_storage_pie_chart")


def _render_monthly_storage_donut_chart(top_storage_df):
    """Render monthly storage cost donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Est Monthly Cost ($)']), "name": f"{row['Database Name'][:15]}... (${row['Est Monthly Cost ($)']:,.0f})" if len(str(row['Database Name'])) > 15 else f"{row['Database Name']} (${row['Est Monthly Cost ($)']:,.0f})"}
        for _, row in top_storage_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Monthly Cost",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="monthly_storage_donut_chart")


def _render_monthly_storage_rose_chart(top_storage_df):
    """Render monthly storage cost rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Est Monthly Cost ($)']), "name": f"{row['Database Name'][:15]}... (${row['Est Monthly Cost ($)']:,.0f})" if len(str(row['Database Name'])) > 15 else f"{row['Database Name']} (${row['Est Monthly Cost ($)']:,.0f})"}
        for _, row in top_storage_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Monthly Cost",
                "type": "pie",
                "radius": [15, 85],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="monthly_storage_rose_chart")


def _render_data_transfer_costs():
    """Render Data Transfer Costs expander content."""

    st.markdown("#### Data Transfer Costs")

    # Introduction text
    st.markdown("""
    **Data transfer volume summary** by target cloud and transfer type showing GB transferred over last 30 days
    with variable cost notation (actual rates depend on region/provider).
    """)

    try:
        # Get session context values for filtering
        execution_id = st.session_state.account_info.get('current_id', 0)
        account_id = st.session_state.account_info.get('account_id', 0)
        org_name = st.session_state.account_info.get('org_name', '')
        account_alias = st.session_state.account_info.get('account_alias', '')
        account_shk = st.session_state.account_info.get('account_shk', 0)

        # Get cost rates from session
        xfer_per_tb = st.session_state.account_info.get('xfer_per_tb', 0.0)

        if execution_id == 0 or account_id == 0:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No execution context available. Please select an account first.'
                        '</div>', unsafe_allow_html=True)
            return

        # Data Transfer Costs Query
        data_transfer_query = f"""
SELECT
    {execution_id} AS "Execution ID",
    '{org_name}' AS "Org Name",
    '{account_alias}' AS "Account Alias",
    {account_shk} AS "Account SHK",
    {account_id} AS "Account ID",
    target_cloud AS "Target Cloud",
    transfer_type AS "Transfer Type",
    ROUND(SUM(bytes_transferred) / POW(1024, 3), 2) AS "GB Transferred",

    -- Estimate Cost based on session rate
    ROUND((SUM(bytes_transferred) / POW(1024, 3)) * {xfer_per_tb}, 2) AS "Estimated Cost ($)"

FROM SNOWFLAKE.ACCOUNT_USAGE.data_transfer_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY "GB Transferred" DESC
"""

        # Display the query in terminal
        print("=" * 100)
        print("=" * 100)
        print(f"🏢 ACCOUNT_ID: {account_id}")
        print("-" * 50)
        print(data_transfer_query)
        print("-" * 50)
        print("=" * 100)

        # Execute the query
        transfer_df = st.session_state.session.sql(data_transfer_query).to_pandas()

        if not transfer_df.empty:
            # Create Report Category and Metric for data transfer costs
            finops_category = ReportCategory('finops_lite', 'FinOps (Lite)')
            transfer_metric = ReportMetric('data_transfer_costs', 'finops_lite', 'Data Transfer Costs')

            # Create a proper metric object for the dialogs
            class TransferMetric:
                def __init__(self, data):
                    self.display_data = data
                    self.display_data_copy = data.copy()
                    self.has_custom_columns = False

            # Initialize transfer metric with data - this will persist across reruns
            if 'data_transfer_metric_obj' not in st.session_state:
                st.session_state.data_transfer_metric_obj = TransferMetric(transfer_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.data_transfer_metric_obj.has_custom_columns:
                    st.session_state.data_transfer_metric_obj.display_data_copy = transfer_df.copy()
                    st.session_state.data_transfer_metric_obj.display_data = transfer_df

            # Format numeric columns for display
            format_dict = {
                "GB Transferred": '{:,.2f}',
                "Estimated Cost ($)": '${:,.2f}'
            }
            # Filter to only columns that exist
            format_dict = {k: v for k, v in format_dict.items() if k in transfer_df.columns}

            # Set dataframes for the report metric
            transfer_metric.dataframes = [st.session_state.data_transfer_metric_obj.display_data.style.format(format_dict)]

            # Create layout with buttons on top-right and table below
            button_row_empty, button_row_col = st.columns([0.75, 0.25])

            with button_row_col:
                # Create buttons side by side
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    # Gear icon button for "Set table" functionality
                    gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="data_transfer_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if gear_clicked:
                        _show_dialog(st.session_state.data_transfer_metric_obj, 'display_data', transfer_metric, None, None, None)

                with btn_col2:
                    # Report icon button for "Add to report" functionality
                    metric_exists = ReportManager().metric_exists(transfer_metric.key)
                    report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="data_transfer_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if report_clicked:
                        show_metric_dialog(finops_category, transfer_metric, metric_exists, False)

            # Display the table with formatting
            st.dataframe(
                st.session_state.data_transfer_metric_obj.display_data.style.format(format_dict),
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Data Transfer Analysis Charts")

            # Row 1: Transfer by Target Cloud and Transfer by Type
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container(border=True):
                st.markdown("##### Data Transfer by Target Cloud")
                _render_transfer_by_cloud_chart(transfer_df)

            with chart_col2.container(border=True):
                st.markdown("##### Data Transfer by Transfer Type")
                _render_transfer_by_type_chart(transfer_df)

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No data transfer data available for the selected account.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading data transfer costs: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure data transfer history data is available.'
                    '</div>', unsafe_allow_html=True)


def _render_transfer_by_cloud_chart(transfer_df):
    """Render data transfer by target cloud chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="transfer_by_cloud_chart_type"
    )

    # Aggregate by target cloud
    if "Target Cloud" not in transfer_df.columns or "GB Transferred" not in transfer_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No target cloud data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    # Group by target cloud
    cloud_df = transfer_df.groupby("Target Cloud")["GB Transferred"].sum().reset_index()
    cloud_df = cloud_df.sort_values("GB Transferred", ascending=False)

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_cloud_transfer_bar_chart(cloud_df)
    elif chart_type == "Pie Chart":
        _render_cloud_transfer_pie_chart(cloud_df)
    elif chart_type == "Pie - Donut":
        _render_cloud_transfer_donut_chart(cloud_df)
    else:  # Pie - Rose Chart
        _render_cloud_transfer_rose_chart(cloud_df)


def _render_cloud_transfer_bar_chart(cloud_df):
    """Render target cloud transfer bar chart using Plotly."""

    clouds = cloud_df['Target Cloud'].tolist()
    gb_transferred = cloud_df['GB Transferred'].tolist()

    fig_bar = go.Figure(data=[
        go.Bar(
            x=clouds,
            y=gb_transferred,
            marker_color='#1f77b4',
            text=[f"{val:,.2f} GB" for val in gb_transferred],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Transferred: %{y:,.2f} GB<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Target Cloud',
        yaxis_title='GB Transferred',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=50),
        xaxis=dict(tickangle=45)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="cloud_transfer_bar_chart")


def _render_cloud_transfer_pie_chart(cloud_df):
    """Render target cloud transfer standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['GB Transferred']), "name": f"{row['Target Cloud']} ({row['GB Transferred']:,.2f} GB)"}
        for _, row in cloud_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} GB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Transfer",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="cloud_transfer_pie_chart")


def _render_cloud_transfer_donut_chart(cloud_df):
    """Render target cloud transfer donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['GB Transferred']), "name": f"{row['Target Cloud']} ({row['GB Transferred']:,.2f} GB)"}
        for _, row in cloud_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} GB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Transfer",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="cloud_transfer_donut_chart")


def _render_cloud_transfer_rose_chart(cloud_df):
    """Render target cloud transfer rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['GB Transferred']), "name": f"{row['Target Cloud']} ({row['GB Transferred']:,.2f} GB)"}
        for _, row in cloud_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} GB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Transfer",
                "type": "pie",
                "radius": [20, 95],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="cloud_transfer_rose_chart")


def _render_transfer_by_type_chart(transfer_df):
    """Render data transfer by transfer type chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="transfer_by_type_chart_type"
    )

    # Aggregate by transfer type
    if "Transfer Type" not in transfer_df.columns or "GB Transferred" not in transfer_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No transfer type data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    # Group by transfer type
    type_df = transfer_df.groupby("Transfer Type")["GB Transferred"].sum().reset_index()
    type_df = type_df.sort_values("GB Transferred", ascending=False)

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_type_transfer_bar_chart(type_df)
    elif chart_type == "Pie Chart":
        _render_type_transfer_pie_chart(type_df)
    elif chart_type == "Pie - Donut":
        _render_type_transfer_donut_chart(type_df)
    else:  # Pie - Rose Chart
        _render_type_transfer_rose_chart(type_df)


def _render_type_transfer_bar_chart(type_df):
    """Render transfer type bar chart using Plotly."""

    types = type_df['Transfer Type'].tolist()
    gb_transferred = type_df['GB Transferred'].tolist()

    fig_bar = go.Figure(data=[
        go.Bar(
            x=types,
            y=gb_transferred,
            marker_color='#ff7f0e',
            text=[f"{val:,.2f} GB" for val in gb_transferred],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Transferred: %{y:,.2f} GB<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Transfer Type',
        yaxis_title='GB Transferred',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=50),
        xaxis=dict(tickangle=45)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="type_transfer_bar_chart")


def _render_type_transfer_pie_chart(type_df):
    """Render transfer type standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['GB Transferred']), "name": f"{row['Transfer Type']} ({row['GB Transferred']:,.2f} GB)"}
        for _, row in type_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} GB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Transfer",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="type_transfer_pie_chart")


def _render_type_transfer_donut_chart(type_df):
    """Render transfer type donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['GB Transferred']), "name": f"{row['Transfer Type']} ({row['GB Transferred']:,.2f} GB)"}
        for _, row in type_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} GB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Transfer",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="type_transfer_donut_chart")


def _render_type_transfer_rose_chart(type_df):
    """Render transfer type rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['GB Transferred']), "name": f"{row['Transfer Type']} ({row['GB Transferred']:,.2f} GB)"}
        for _, row in type_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} GB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Transfer",
                "type": "pie",
                "radius": [20, 95],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="type_transfer_rose_chart")


def _render_cost_anomalies():
    """Render Cost Anomalies (Automated Detection) expander content."""

    st.markdown("#### Cost Anomalies (Automated Detection)")

    # Introduction text
    st.markdown("""
    **Daily cost anomalies over last 60 days** showing actual vs expected credits/costs,
    estimated overspend amount, and deviation percentage from forecast.
    """)

    try:
        # Get session context values for filtering
        execution_id = st.session_state.account_info.get('current_id', 0)
        account_id = st.session_state.account_info.get('account_id', 0)
        org_name = st.session_state.account_info.get('org_name', '')
        account_alias = st.session_state.account_info.get('account_alias', '')
        account_shk = st.session_state.account_info.get('account_shk', 0)

        # Get cost rates from session
        credit_cost = st.session_state.account_info.get('credit_cost', 3.0)

        if execution_id == 0 or account_id == 0:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No execution context available. Please select an account first.'
                        '</div>', unsafe_allow_html=True)
            return

        # Cost Anomalies Query
        anomalies_query = f"""
SELECT
    {execution_id} AS "Execution ID",
    '{org_name}' AS "Org Name",
    '{account_alias}' AS "Account Alias",
    {account_shk} AS "Account SHK",
    {account_id} AS "Account ID",
    date AS "Anomaly Date",
    anomaly_id AS "Anomaly ID",

    -- Consumption Details (Credits)
    ROUND(actual_value, 2) AS "Actual Credits",
    ROUND(forecasted_value, 2) AS "Expected Credits",

    -- Dollar Impact
    ROUND(actual_value * {credit_cost}, 2) AS "Actual Cost ($)",
    ROUND(forecasted_value * {credit_cost}, 2) AS "Expected Cost ($)",

    -- "Waste" or Overspend
    ROUND((actual_value - forecasted_value) * {credit_cost}, 2) AS "Estimated Overspend ($)",

    -- Severity (Percentage exceeding forecast)
    ROUND(((actual_value - forecasted_value) / NULLIF(forecasted_value, 0)) * 100, 1) AS "Deviation %"

FROM SNOWFLAKE.ACCOUNT_USAGE.anomalies_daily
WHERE date >= DATEADD('day', -60, CURRENT_TIMESTAMP())
  AND is_anomaly = TRUE
ORDER BY date DESC
"""

        # Display the query in terminal
        print("=" * 100)
        print("=" * 100)
        print(f"🏢 ACCOUNT_ID: {account_id}")
        print("-" * 50)
        print(anomalies_query)
        print("-" * 50)
        print("=" * 100)

        # Execute the query
        anomalies_df = st.session_state.session.sql(anomalies_query).to_pandas()

        if not anomalies_df.empty:
            # Create Report Category and Metric for cost anomalies
            finops_category = ReportCategory('finops_lite', 'FinOps (Lite)')
            anomalies_metric = ReportMetric('cost_anomalies', 'finops_lite', 'Cost Anomalies (Automated Detection)')

            # Create a proper metric object for the dialogs
            class AnomaliesMetric:
                def __init__(self, data):
                    self.display_data = data
                    self.display_data_copy = data.copy()
                    self.has_custom_columns = False

            # Initialize anomalies metric with data - this will persist across reruns
            if 'cost_anomalies_metric_obj' not in st.session_state:
                st.session_state.cost_anomalies_metric_obj = AnomaliesMetric(anomalies_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.cost_anomalies_metric_obj.has_custom_columns:
                    st.session_state.cost_anomalies_metric_obj.display_data_copy = anomalies_df.copy()
                    st.session_state.cost_anomalies_metric_obj.display_data = anomalies_df

            # Format numeric columns for display
            format_dict = {
                "Actual Credits": '{:,.2f}',
                "Expected Credits": '{:,.2f}',
                "Actual Cost ($)": '${:,.2f}',
                "Expected Cost ($)": '${:,.2f}',
                "Estimated Overspend ($)": '${:,.2f}',
                "Deviation %": '{:,.1f}%'
            }
            # Filter to only columns that exist
            format_dict = {k: v for k, v in format_dict.items() if k in anomalies_df.columns}

            # Set dataframes for the report metric
            anomalies_metric.dataframes = [st.session_state.cost_anomalies_metric_obj.display_data.style.format(format_dict)]

            # Create layout with buttons on top-right and table below
            button_row_empty, button_row_col = st.columns([0.75, 0.25])

            with button_row_col:
                # Create buttons side by side
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    # Gear icon button for "Set table" functionality
                    gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="cost_anomalies_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if gear_clicked:
                        _show_dialog(st.session_state.cost_anomalies_metric_obj, 'display_data', anomalies_metric, None, None, None)

                with btn_col2:
                    # Report icon button for "Add to report" functionality
                    metric_exists = ReportManager().metric_exists(anomalies_metric.key)
                    report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="cost_anomalies_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if report_clicked:
                        show_metric_dialog(finops_category, anomalies_metric, metric_exists, False)

            # Display the table with formatting
            st.dataframe(
                st.session_state.cost_anomalies_metric_obj.display_data.style.format(format_dict),
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Anomaly Analysis Charts")

            # Row 1: Overspend Distribution and Deviation Distribution
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container(border=True):
                st.markdown("##### Estimated Overspend by Date")
                _render_overspend_by_date_chart(anomalies_df)

            with chart_col2.container(border=True):
                st.markdown("##### Deviation % Distribution")
                _render_deviation_distribution_chart(anomalies_df)

        else:
            st.markdown('<div style="background-color: #d4edda; border-left: 6px solid #28a745; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '✅&nbsp;&nbsp;No cost anomalies detected in the last 60 days. Your spending is within expected forecasts.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading cost anomalies: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure anomalies_daily data is available.'
                    '</div>', unsafe_allow_html=True)


def _render_overspend_by_date_chart(anomalies_df):
    """Render overspend by date chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="overspend_by_date_chart_type"
    )

    # Check for required columns
    if "Anomaly Date" not in anomalies_df.columns or "Estimated Overspend ($)" not in anomalies_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No overspend data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    # Get top 10 by overspend
    overspend_df = anomalies_df.copy()
    overspend_df = overspend_df.sort_values("Estimated Overspend ($)", ascending=False).head(10)

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_overspend_bar_chart(overspend_df)
    elif chart_type == "Pie Chart":
        _render_overspend_pie_chart(overspend_df)
    elif chart_type == "Pie - Donut":
        _render_overspend_donut_chart(overspend_df)
    else:  # Pie - Rose Chart
        _render_overspend_rose_chart(overspend_df)


def _render_overspend_bar_chart(overspend_df):
    """Render overspend bar chart using Plotly."""

    # Convert date to string for display
    dates = [str(d)[:10] for d in overspend_df['Anomaly Date'].tolist()]
    overspends = overspend_df['Estimated Overspend ($)'].tolist()

    fig_bar = go.Figure(data=[
        go.Bar(
            x=dates,
            y=overspends,
            marker_color=['#d62728' if v > 0 else '#2ca02c' for v in overspends],
            text=[f"${val:,.2f}" for val in overspends],
            textposition='outside',
            textfont=dict(size=9),
            hovertemplate='<b>%{x}</b><br>Overspend: $%{y:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Anomaly Date',
        yaxis_title='Estimated Overspend ($)',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=50),
        xaxis=dict(tickangle=45)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="overspend_bar_chart")


def _render_overspend_pie_chart(overspend_df):
    """Render overspend standard pie chart using ECharts."""

    # Filter to only positive overspends for pie chart
    positive_df = overspend_df[overspend_df['Estimated Overspend ($)'] > 0]

    if positive_df.empty:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No positive overspend data for pie chart.'
                    '</div>', unsafe_allow_html=True)
        return

    chart_data = [
        {"value": float(row['Estimated Overspend ($)']), "name": f"{str(row['Anomaly Date'])[:10]} (${row['Estimated Overspend ($)']:,.2f})"}
        for _, row in positive_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Overspend",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="overspend_pie_chart")


def _render_overspend_donut_chart(overspend_df):
    """Render overspend donut pie chart using ECharts."""

    # Filter to only positive overspends for pie chart
    positive_df = overspend_df[overspend_df['Estimated Overspend ($)'] > 0]

    if positive_df.empty:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No positive overspend data for donut chart.'
                    '</div>', unsafe_allow_html=True)
        return

    chart_data = [
        {"value": float(row['Estimated Overspend ($)']), "name": f"{str(row['Anomaly Date'])[:10]} (${row['Estimated Overspend ($)']:,.2f})"}
        for _, row in positive_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Overspend",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="overspend_donut_chart")


def _render_overspend_rose_chart(overspend_df):
    """Render overspend rose-type pie chart using ECharts."""

    # Filter to only positive overspends for pie chart
    positive_df = overspend_df[overspend_df['Estimated Overspend ($)'] > 0]

    if positive_df.empty:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No positive overspend data for rose chart.'
                    '</div>', unsafe_allow_html=True)
        return

    chart_data = [
        {"value": float(row['Estimated Overspend ($)']), "name": f"{str(row['Anomaly Date'])[:10]} (${row['Estimated Overspend ($)']:,.2f})"}
        for _, row in positive_df.iterrows()
    ]

    option = {
        "legend": {
            "type": "scroll",
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: ${c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Overspend",
                "type": "pie",
                "radius": [15, 85],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="overspend_rose_chart")


def _render_deviation_distribution_chart(anomalies_df):
    """Render deviation distribution chart with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key="deviation_distribution_chart_type"
    )

    # Check for required columns
    if "Deviation %" not in anomalies_df.columns:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No deviation data available for chart.'
                    '</div>', unsafe_allow_html=True)
        return

    # Create deviation buckets
    deviation_df = anomalies_df.copy()
    deviation_df['Deviation Bucket'] = pd.cut(
        deviation_df['Deviation %'],
        bins=[-float('inf'), 0, 25, 50, 100, float('inf')],
        labels=['< 0% (Under)', '0-25%', '25-50%', '50-100%', '> 100%']
    )

    bucket_counts = deviation_df['Deviation Bucket'].value_counts().reset_index()
    bucket_counts.columns = ['Bucket', 'Count']
    bucket_counts = bucket_counts.sort_values('Bucket')

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_deviation_bar_chart(bucket_counts)
    elif chart_type == "Pie Chart":
        _render_deviation_pie_chart(bucket_counts)
    elif chart_type == "Pie - Donut":
        _render_deviation_donut_chart(bucket_counts)
    else:  # Pie - Rose Chart
        _render_deviation_rose_chart(bucket_counts)


def _render_deviation_bar_chart(bucket_counts):
    """Render deviation distribution bar chart using Plotly."""

    buckets = bucket_counts['Bucket'].astype(str).tolist()
    counts = bucket_counts['Count'].tolist()

    # Color code by severity
    colors = ['#2ca02c', '#ffc107', '#ff7f0e', '#d62728', '#8b0000']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=buckets,
            y=counts,
            marker_color=colors[:len(buckets)],
            text=counts,
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Deviation Range',
        yaxis_title='Number of Anomalies',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=50),
        xaxis=dict(tickangle=45)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key="deviation_bar_chart")


def _render_deviation_pie_chart(bucket_counts):
    """Render deviation distribution standard pie chart using ECharts."""

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Bucket']} ({row['Count']})"}
        for _, row in bucket_counts.iterrows()
        if row['Count'] > 0
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} anomalies ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#ffc107", "#ff7f0e", "#d62728", "#8b0000"],
        "series": [
            {
                "name": "Deviation",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="deviation_pie_chart")


def _render_deviation_donut_chart(bucket_counts):
    """Render deviation distribution donut pie chart using ECharts."""

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Bucket']} ({row['Count']})"}
        for _, row in bucket_counts.iterrows()
        if row['Count'] > 0
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} anomalies ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#ffc107", "#ff7f0e", "#d62728", "#8b0000"],
        "series": [
            {
                "name": "Deviation",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="deviation_donut_chart")


def _render_deviation_rose_chart(bucket_counts):
    """Render deviation distribution rose-type pie chart using ECharts."""

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Bucket']} ({row['Count']})"}
        for _, row in bucket_counts.iterrows()
        if row['Count'] > 0
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} anomalies ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#ffc107", "#ff7f0e", "#d62728", "#8b0000"],
        "series": [
            {
                "name": "Deviation",
                "type": "pie",
                "radius": [20, 95],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key="deviation_rose_chart")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_echarts import st_echarts


def comp_finops_control(entry_actions=None):
    """
    FinOPS Control Component

    Provides control capabilities for resource monitors and warehouse management.

    Expanders:
    1. FinOPS Control Overview
    2. FinOPS Control Analyzer
    3. Resource Monitors (Inventory & Orphans)
    4. Warehouses Without Controls (Exposure Risk)
    5. Resource Monitors: Approaching Limits (Usage vs. Quota)
    6. Statement Timeouts (Parameters)
    7. Snowflake Budgets
    """
    try:
        st.markdown("### Control")

        # Expander 3: Resource Monitors (Inventory & Orphans)
        with st.expander("Resource Monitors (Inventory & Orphans)", expanded=True):
            _render_resource_monitors_inventory()

        # Expander 4: Warehouses Without Controls (Exposure Risk)
        with st.expander("Warehouses Without Controls (Exposure Risk)", expanded=False):
            st.markdown("#### Warehouses Without Controls (Exposure Risk)")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;Content for Warehouses Without Controls (Exposure Risk) will be implemented here.'
                        '</div>', unsafe_allow_html=True)

        # Expander 5: Resource Monitors: Approaching Limits (Usage vs. Quota)
        with st.expander("Resource Monitors: Approaching Limits (Usage vs. Quota)", expanded=False):
            st.markdown("#### Resource Monitors: Approaching Limits (Usage vs. Quota)")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;Content for Resource Monitors: Approaching Limits (Usage vs. Quota) will be implemented here.'
                        '</div>', unsafe_allow_html=True)

        # Expander 6: Statement Timeouts (Parameters)
        with st.expander("Statement Timeouts (Parameters)", expanded=False):
            st.markdown("#### Statement Timeouts (Parameters)")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;Content for Statement Timeouts (Parameters) will be implemented here.'
                        '</div>', unsafe_allow_html=True)

        # Expander 7: Snowflake Budgets
        with st.expander("Snowflake Budgets", expanded=False):
            _render_snowflake_budgets()

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_resource_monitors_inventory():
    """Render Resource Monitors Inventory & Orphans expander content."""

    st.markdown("#### Resource Monitors (Inventory & Orphans)")

    # Introduction text
    st.markdown("""
    **Resource monitor inventory** showing credit quotas, notification/suspension thresholds, schedules,
    and ownership ordered by quota size. This view helps identify monitors that may be under-utilized
    or orphaned (no warehouses assigned).
    """)

    try:

        # Resource Monitors Query
        resource_monitors_query = f"""
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
"""


        # Execute the query
        resource_monitors_df = st.session_state.session.sql(resource_monitors_query).to_pandas()

        if not resource_monitors_df.empty:
            # Create Report Category and Metric for resource monitors

            # Create a proper metric object for the dialogs
            # Initialize resource monitors metric with data - this will persist across reruns
            if 'resource_monitors_metric_obj' not in st.session_state:
                st.session_state.resource_monitors_metric_obj = ResourceMonitorsMetric(resource_monitors_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.resource_monitors_metric_obj.has_custom_columns:
                    df_copy = resource_monitors_df.copy()
                    df = resource_monitors_df

            # Set dataframes for the report metric

            # Create layout with buttons on top-right and table below

                # Create buttons side by side
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    # Gear icon button for "Set table" functionality
                    gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="resource_monitors_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if gear_clicked:
                        _show_dialog(st.session_state.resource_monitors_metric_obj, 'display_data', resource_monitors_metric, None, None, None)

                with btn_col2:
                    # Report icon button for "Add to report" functionality
                    metric_exists = ReportManager().metric_exists(resource_monitors_metric.key)
                    report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="resource_monitors_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if report_clicked:
                        show_metric_dialog(finops_category, resource_monitors_metric, metric_exists, False)

            # Display the metric's display_data (this will be modified by the dialog)
            st.dataframe(
                df,
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Resource Monitor Analysis")

            # Row 1: Credit Quota Distribution & Threshold Analysis
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container(border=True):
                st.markdown("##### Credit Quota by Monitor")
                _render_credit_quota_chart_content(resource_monitors_df, key_prefix="rm_quota_")

            with chart_col2.container(border=True):
                st.markdown("##### Threshold Comparison (Notify vs Suspend)")
                _render_threshold_chart_content(resource_monitors_df, key_prefix="rm_threshold_")

            # Row 2: Ownership Distribution & Warehouse Assignment
            chart_col3, chart_col4 = st.columns(2)

            with chart_col3.container(border=True):
                st.markdown("##### Resource Monitors by Owner")
                _render_owner_distribution_chart_content(resource_monitors_df, key_prefix="rm_owner_")

            with chart_col4.container(border=True):
                st.markdown("##### Warehouse Assignment Status")
                _render_warehouse_assignment_chart_content(resource_monitors_df, key_prefix="rm_wh_")

            # ========== NEW SECTION: Resource Monitor Risk Analysis ==========
            _render_resource_monitor_risk_analysis()

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No resource monitors data available for the current execution context.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading resource monitors: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Credit Quota Chart Functions ==========

def _render_credit_quota_chart_content(df, key_prefix=""):
    """Render credit quota chart content with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key=f"{key_prefix}chart_type"
    )

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_credit_quota_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_credit_quota_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_credit_quota_donut_pie_chart(df, key_prefix)
    else:  # Pie - Rose Chart
        _render_credit_quota_rose_pie_chart(df, key_prefix)


def _render_credit_quota_bar_chart(df, key_prefix=""):
    """Render credit quota bar chart using Plotly."""

    fig_bar = go.Figure(data=[
        go.Bar(
            x=df['MONITOR_NAME'],
            y=df['CREDIT_QUOTA'],
            marker_color='#1f77b4',
            text=[f"{val:,.0f}" for val in df['CREDIT_QUOTA']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Quota: %{y:,.0f} credits<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Resource Monitor',
        yaxis_title='Credit Quota',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_credit_quota_standard_pie_chart(df, key_prefix=""):
    """Render credit quota standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDIT_QUOTA']), "name": f"{row['MONITOR_NAME']} ({row['CREDIT_QUOTA']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
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
                "name": "Credit Quota",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_credit_quota_donut_pie_chart(df, key_prefix=""):
    """Render credit quota donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDIT_QUOTA']), "name": f"{row['MONITOR_NAME']} ({row['CREDIT_QUOTA']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
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
                "name": "Credit Quota",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_credit_quota_rose_pie_chart(df, key_prefix=""):
    """Render credit quota rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDIT_QUOTA']), "name": f"{row['MONITOR_NAME']} ({row['CREDIT_QUOTA']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
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
                "name": "Credit Quota",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Threshold Chart Functions ==========

def _render_threshold_chart_content(df, key_prefix=""):
    """Render threshold comparison chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_threshold_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_threshold_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_threshold_donut_pie_chart(df, key_prefix)
    else:
        _render_threshold_rose_pie_chart(df, key_prefix)


def _render_threshold_bar_chart(df, key_prefix=""):
    """Render threshold comparison bar chart using Plotly."""

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Notify %',
        x=df['MONITOR_NAME'],
        y=df['NOTIFY'],
        marker_color='#ff7f0e',
        text=[f"{val}%" if pd.notna(val) else "N/A" for val in df['NOTIFY']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.add_trace(go.Bar(
        name='Suspend %',
        x=df['MONITOR_NAME'],
        y=df['SUSPEND'],
        marker_color='#d62728',
        text=[f"{val}%" if pd.notna(val) else "N/A" for val in df['SUSPEND']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.add_trace(go.Bar(
        name='Suspend Immediate %',
        x=df['MONITOR_NAME'],
        y=df['SUSPEND_IMMEDIATE'],
        marker_color='#9467bd',
        text=[f"{val}%" if pd.notna(val) else "N/A" for val in df['SUSPEND_IMMEDIATE']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.update_layout(
        height=350,
        barmode='group',
        xaxis_title='Resource Monitor',
        yaxis_title='Threshold (%)',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(t=40, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_threshold_standard_pie_chart(df, key_prefix=""):
    """Render threshold distribution pie chart - shows average thresholds."""

    avg_notify = df['NOTIFY'].mean() if df['NOTIFY'].notna().any() else 0
    avg_suspend = df['SUSPEND'].mean() if df['SUSPEND'].notna().any() else 0
    avg_suspend_imm = df['SUSPEND_IMMEDIATE'].mean() if df['SUSPEND_IMMEDIATE'].notna().any() else 0

    chart_data = [
        {"value": float(avg_notify), "name": f"Avg Notify ({avg_notify:.1f}%)"},
        {"value": float(avg_suspend), "name": f"Avg Suspend ({avg_suspend:.1f}%)"},
        {"value": float(avg_suspend_imm), "name": f"Avg Suspend Imm. ({avg_suspend_imm:.1f}%)"}
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c}%"
        },
        "color": ["#ff7f0e", "#d62728", "#9467bd"],
        "series": [
            {
                "name": "Threshold Averages",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_threshold_donut_pie_chart(df, key_prefix=""):
    """Render threshold distribution donut chart."""

    avg_notify = df['NOTIFY'].mean() if df['NOTIFY'].notna().any() else 0
    avg_suspend = df['SUSPEND'].mean() if df['SUSPEND'].notna().any() else 0
    avg_suspend_imm = df['SUSPEND_IMMEDIATE'].mean() if df['SUSPEND_IMMEDIATE'].notna().any() else 0

    chart_data = [
        {"value": float(avg_notify), "name": f"Avg Notify ({avg_notify:.1f}%)"},
        {"value": float(avg_suspend), "name": f"Avg Suspend ({avg_suspend:.1f}%)"},
        {"value": float(avg_suspend_imm), "name": f"Avg Suspend Imm. ({avg_suspend_imm:.1f}%)"}
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c}%"
        },
        "color": ["#ff7f0e", "#d62728", "#9467bd"],
        "series": [
            {
                "name": "Threshold Averages",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_threshold_rose_pie_chart(df, key_prefix=""):
    """Render threshold distribution rose chart."""

    avg_notify = df['NOTIFY'].mean() if df['NOTIFY'].notna().any() else 0
    avg_suspend = df['SUSPEND'].mean() if df['SUSPEND'].notna().any() else 0
    avg_suspend_imm = df['SUSPEND_IMMEDIATE'].mean() if df['SUSPEND_IMMEDIATE'].notna().any() else 0

    chart_data = [
        {"value": float(avg_notify), "name": f"Avg Notify ({avg_notify:.1f}%)"},
        {"value": float(avg_suspend), "name": f"Avg Suspend ({avg_suspend:.1f}%)"},
        {"value": float(avg_suspend_imm), "name": f"Avg Suspend Imm. ({avg_suspend_imm:.1f}%)"}
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c}%"
        },
        "color": ["#ff7f0e", "#d62728", "#9467bd"],
        "series": [
            {
                "name": "Threshold Averages",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Owner Distribution Chart Functions ==========

def _render_owner_distribution_chart_content(df, key_prefix=""):
    """Render owner distribution chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_owner_distribution_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_owner_distribution_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_owner_distribution_donut_pie_chart(df, key_prefix)
    else:
        _render_owner_distribution_rose_pie_chart(df, key_prefix)


def _render_owner_distribution_bar_chart(df, key_prefix=""):
    """Render owner distribution bar chart using Plotly."""

    owner_counts = df['OWNER'].value_counts().reset_index()
    owner_counts.columns = ['OWNER', 'COUNT']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=owner_counts['OWNER'],
            y=owner_counts['COUNT'],
            marker_color='#2ca02c',
            text=owner_counts['COUNT'],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Owner',
        yaxis_title='Number of Monitors',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_owner_distribution_standard_pie_chart(df, key_prefix=""):
    """Render owner distribution standard pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "series": [
            {
                "name": "Owner Distribution",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_owner_distribution_donut_pie_chart(df, key_prefix=""):
    """Render owner distribution donut pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "series": [
            {
                "name": "Owner Distribution",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_owner_distribution_rose_pie_chart(df, key_prefix=""):
    """Render owner distribution rose pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "series": [
            {
                "name": "Owner Distribution",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Warehouse Assignment Chart Functions ==========

def _render_warehouse_assignment_chart_content(df, key_prefix=""):
    """Render warehouse assignment chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_warehouse_assignment_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_warehouse_assignment_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_warehouse_assignment_donut_pie_chart(df, key_prefix)
    else:
        _render_warehouse_assignment_rose_pie_chart(df, key_prefix)


def _render_warehouse_assignment_bar_chart(df, key_prefix=""):
    """Render warehouse assignment bar chart using Plotly."""

    # Count warehouses assigned to each monitor
    def count_warehouses(warehouses):
        if pd.isna(warehouses) or warehouses == '' or warehouses == '[]':
            return 0
        if isinstance(warehouses, str):
            # Parse the array string
            warehouses = warehouses.strip('[]')
            if not warehouses:
                return 0
            return len([w.strip() for w in warehouses.split(',') if w.strip()])
        return 0

    df_copy = df.copy()
    df_copy['WH_COUNT'] = df_copy['WAREHOUSES'].apply(count_warehouses)

    fig_bar = go.Figure(data=[
        go.Bar(
            x=df_copy['MONITOR_NAME'],
            y=df_copy['WH_COUNT'],
            marker_color=['#d62728' if x == 0 else '#2ca02c' for x in df_copy['WH_COUNT']],
            text=df_copy['WH_COUNT'],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Warehouses: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Resource Monitor',
        yaxis_title='Number of Warehouses',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_warehouse_assignment_standard_pie_chart(df, key_prefix=""):
    """Render warehouse assignment status pie chart (Assigned vs Orphaned)."""

    def has_warehouses(warehouses):
        if pd.isna(warehouses) or warehouses == '' or warehouses == '[]':
            return False
        if isinstance(warehouses, str):
            warehouses = warehouses.strip('[]')
            return bool(warehouses.strip())
        return False

    df_copy = df.copy()
    df_copy['HAS_WH'] = df_copy['WAREHOUSES'].apply(has_warehouses)

    assigned_count = df_copy['HAS_WH'].sum()
    orphaned_count = len(df_copy) - assigned_count

    chart_data = [
        {"value": int(assigned_count), "name": f"With Warehouses ({assigned_count})"},
        {"value": int(orphaned_count), "name": f"Orphaned ({orphaned_count})"}
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "color": ["#2ca02c", "#d62728"],
        "series": [
            {
                "name": "Warehouse Assignment",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_warehouse_assignment_donut_pie_chart(df, key_prefix=""):
    """Render warehouse assignment status donut chart."""

    def has_warehouses(warehouses):
        if pd.isna(warehouses) or warehouses == '' or warehouses == '[]':
            return False
        if isinstance(warehouses, str):
            warehouses = warehouses.strip('[]')
            return bool(warehouses.strip())
        return False

    df_copy = df.copy()
    df_copy['HAS_WH'] = df_copy['WAREHOUSES'].apply(has_warehouses)

    assigned_count = df_copy['HAS_WH'].sum()
    orphaned_count = len(df_copy) - assigned_count

    chart_data = [
        {"value": int(assigned_count), "name": f"With Warehouses ({assigned_count})"},
        {"value": int(orphaned_count), "name": f"Orphaned ({orphaned_count})"}
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "color": ["#2ca02c", "#d62728"],
        "series": [
            {
                "name": "Warehouse Assignment",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_warehouse_assignment_rose_pie_chart(df, key_prefix=""):
    """Render warehouse assignment status rose chart."""

    def has_warehouses(warehouses):
        if pd.isna(warehouses) or warehouses == '' or warehouses == '[]':
            return False
        if isinstance(warehouses, str):
            warehouses = warehouses.strip('[]')
            return bool(warehouses.strip())
        return False

    df_copy = df.copy()
    df_copy['HAS_WH'] = df_copy['WAREHOUSES'].apply(has_warehouses)

    assigned_count = df_copy['HAS_WH'].sum()
    orphaned_count = len(df_copy) - assigned_count

    chart_data = [
        {"value": int(assigned_count), "name": f"With Warehouses ({assigned_count})"},
        {"value": int(orphaned_count), "name": f"Orphaned ({orphaned_count})"}
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "color": ["#2ca02c", "#d62728"],
        "series": [
            {
                "name": "Warehouse Assignment",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Resource Monitor Risk Analysis Section ==========

def _render_resource_monitor_risk_analysis():
    """Render Resource Monitor Risk Analysis section with warehouse spend analysis."""


    st.markdown("---")
    st.markdown("#### Resource Monitor Risk Analysis")

    # Introduction text
    st.markdown("""
    **Resource monitor risk analysis** identifying warehouses without resource monitors and their credit consumption,
    along with configured resource monitors and their total quotas. This helps identify cost exposure risks from
    unmonitored warehouse spending.
    """)

    try:

        # Resource Monitor Risk Analysis Query
        risk_analysis_query = f"""
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
    LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSES w
        ON ws.warehouse_name = w.name
    WHERE (w.resource_monitor IS NULL OR w.resource_monitor = '')
    AND ws.monthly_credits > 100
)
SELECT
    '⚠️ Warehouses without Resource Monitors' AS risk_category,
    NVL(COUNT(DISTINCT warehouse_name), 0) AS item_count,
    ROUND(NVL(SUM(monthly_credits), 0), 2) AS credits_or_quota,
    LISTAGG(warehouse_name, ', ') WITHIN GROUP (ORDER BY monthly_credits DESC) AS item_list
FROM warehouses_without_monitors
HAVING NVL(COUNT(DISTINCT warehouse_name), 0) > 0
UNION ALL
SELECT
    '📊 Resource Monitors Configured' AS risk_category,
    NVL(COUNT(*), 0) AS item_count,
    ROUND(NVL(SUM(credit_quota), 0), 2) AS credits_or_quota,
    LISTAGG(monitor_name, ', ') WITHIN GROUP (ORDER BY credit_quota DESC) AS item_list
FROM monitor_quotas
"""


        # Also display query in UI expander for visibility
        with st.expander("📝 View Risk Analysis Query", expanded=False):
            st.code(risk_analysis_query, language="sql")

        # Execute the query
        risk_analysis_df = st.session_state.session.sql(risk_analysis_query).to_pandas()

        if not risk_analysis_df.empty:
            # Create Report Category and Metric for risk analysis

            # Create a proper metric object for the dialogs
            # Initialize risk analysis metric with data - this will persist across reruns
            if 'risk_analysis_metric_obj' not in st.session_state:
                st.session_state.risk_analysis_metric_obj = RiskAnalysisMetric(risk_analysis_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.risk_analysis_metric_obj.has_custom_columns:
                    df_copy = risk_analysis_df.copy()
                    df = risk_analysis_df

            # Set dataframes for the report metric

            # Create layout with buttons on top-right and table below

                # Create buttons side by side
                risk_btn_col1, risk_btn_col2 = st.columns(2)

                with risk_btn_col1:
                    # Gear icon button for "Set table" functionality
                    risk_gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="risk_analysis_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if risk_gear_clicked:
                        _show_dialog(st.session_state.risk_analysis_metric_obj, 'display_data', risk_analysis_metric, None, None, None)

                with risk_btn_col2:
                    # Report icon button for "Add to report" functionality
                    risk_metric_exists = ReportManager().metric_exists(risk_analysis_metric.key)
                    risk_report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="risk_analysis_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if risk_report_clicked:
                        show_metric_dialog(finops_category, risk_analysis_metric, risk_metric_exists, False)

            # Display the metric's display_data (this will be modified by the dialog)
            st.dataframe(
                df,
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Risk Analysis Charts")

            # Row 1: Risk Category Distribution & Credits/Quota Comparison
            risk_chart_col1, risk_chart_col2 = st.columns(2)

            with risk_chart_col1.container(border=True):
                st.markdown("##### Risk Category: Item Count")
                _render_risk_category_count_chart_content(risk_analysis_df, key_prefix="risk_count_")

            with risk_chart_col2.container(border=True):
                st.markdown("##### Risk Category: Credits/Quota")
                _render_risk_category_credits_chart_content(risk_analysis_df, key_prefix="risk_credits_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No risk analysis data available. This may indicate all warehouses have resource monitors configured.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading risk analysis: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Risk Category Count Chart Functions ==========

def _render_risk_category_count_chart_content(df, key_prefix=""):
    """Render risk category count chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_risk_category_count_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_risk_category_count_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_risk_category_count_donut_pie_chart(df, key_prefix)
    else:
        _render_risk_category_count_rose_pie_chart(df, key_prefix)


def _render_risk_category_count_bar_chart(df, key_prefix=""):
    """Render risk category count bar chart using Plotly."""

    fig_bar = go.Figure(data=[
        go.Bar(
            x=df['RISK_CATEGORY'],
            y=df['ITEM_COUNT'],
            marker_color=['#d62728' if '⚠️' in cat else '#2ca02c' for cat in df['RISK_CATEGORY']],
            text=[f"{val:,.0f}" for val in df['ITEM_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y:,.0f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Risk Category',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=100, l=50, r=20),
        xaxis_tickangle=-25
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_risk_category_count_standard_pie_chart(df, key_prefix=""):
    """Render risk category count standard pie chart using ECharts."""

    chart_data = [
        {"value": int(row['ITEM_COUNT']), "name": f"{row['RISK_CATEGORY']} ({row['ITEM_COUNT']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} items ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#d62728", "#2ca02c"],
        "series": [
            {
                "name": "Item Count",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_risk_category_count_donut_pie_chart(df, key_prefix=""):
    """Render risk category count donut pie chart using ECharts."""

    chart_data = [
        {"value": int(row['ITEM_COUNT']), "name": f"{row['RISK_CATEGORY']} ({row['ITEM_COUNT']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} items ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#d62728", "#2ca02c"],
        "series": [
            {
                "name": "Item Count",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_risk_category_count_rose_pie_chart(df, key_prefix=""):
    """Render risk category count rose pie chart using ECharts."""

    chart_data = [
        {"value": int(row['ITEM_COUNT']), "name": f"{row['RISK_CATEGORY']} ({row['ITEM_COUNT']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} items ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#d62728", "#2ca02c"],
        "series": [
            {
                "name": "Item Count",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Risk Category Credits Chart Functions ==========

def _render_risk_category_credits_chart_content(df, key_prefix=""):
    """Render risk category credits/quota chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_risk_category_credits_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_risk_category_credits_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_risk_category_credits_donut_pie_chart(df, key_prefix)
    else:
        _render_risk_category_credits_rose_pie_chart(df, key_prefix)


def _render_risk_category_credits_bar_chart(df, key_prefix=""):
    """Render risk category credits/quota bar chart using Plotly."""

    fig_bar = go.Figure(data=[
        go.Bar(
            x=df['RISK_CATEGORY'],
            y=df['CREDITS_OR_QUOTA'],
            marker_color=['#d62728' if '⚠️' in cat else '#2ca02c' for cat in df['RISK_CATEGORY']],
            text=[f"{val:,.2f}" for val in df['CREDITS_OR_QUOTA']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Credits/Quota: %{y:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Risk Category',
        yaxis_title='Credits / Quota',
        showlegend=False,
        margin=dict(t=20, b=100, l=50, r=20),
        xaxis_tickangle=-25
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_risk_category_credits_standard_pie_chart(df, key_prefix=""):
    """Render risk category credits/quota standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDITS_OR_QUOTA']), "name": f"{row['RISK_CATEGORY']} ({row['CREDITS_OR_QUOTA']:,.2f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#d62728", "#2ca02c"],
        "series": [
            {
                "name": "Credits/Quota",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_risk_category_credits_donut_pie_chart(df, key_prefix=""):
    """Render risk category credits/quota donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDITS_OR_QUOTA']), "name": f"{row['RISK_CATEGORY']} ({row['CREDITS_OR_QUOTA']:,.2f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#d62728", "#2ca02c"],
        "series": [
            {
                "name": "Credits/Quota",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_risk_category_credits_rose_pie_chart(df, key_prefix=""):
    """Render risk category credits/quota rose pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDITS_OR_QUOTA']), "name": f"{row['RISK_CATEGORY']} ({row['CREDITS_OR_QUOTA']:,.2f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#d62728", "#2ca02c"],
        "series": [
            {
                "name": "Credits/Quota",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Snowflake Budgets Section ==========

def _render_snowflake_budgets():
    """Render Snowflake Budgets expander content."""

    st.markdown("#### Snowflake Budgets")

    # Introduction text
    st.markdown("""
    **Budget configuration count** showing total number of active budgets defined in the account.
    Snowflake Budgets help you monitor and control spending by setting spending limits and alerts.
    """)

    try:

        # Snowflake Budgets Query
        budgets_query = f"""
SELECT
    'Total Budgets Configured' AS metric,
    NVL(COUNT(*), 0) AS count
FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
WHERE CLASS_NAME = 'BUDGET'
  AND DELETED IS NULL
"""


        # Execute the query
        budgets_df = st.session_state.session.sql(budgets_query).to_pandas()

        if not budgets_df.empty:
            # Create Report Category and Metric for budgets

            # Create a proper metric object for the dialogs
            # Initialize budgets metric with data - this will persist across reruns
            if 'budgets_metric_obj' not in st.session_state:
                st.session_state.budgets_metric_obj = BudgetsMetric(budgets_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.budgets_metric_obj.has_custom_columns:
                    df_copy = budgets_df.copy()
                    df = budgets_df

            # Set dataframes for the report metric

            # Create layout with buttons on top-right and table below

                # Create buttons side by side
                budget_btn_col1, budget_btn_col2 = st.columns(2)

                with budget_btn_col1:
                    # Gear icon button for "Set table" functionality
                    budget_gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="budgets_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if budget_gear_clicked:
                        _show_dialog(st.session_state.budgets_metric_obj, 'display_data', budgets_metric, None, None, None)

                with budget_btn_col2:
                    # Report icon button for "Add to report" functionality
                    budget_metric_exists = ReportManager().metric_exists(budgets_metric.key)
                    budget_report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="budgets_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if budget_report_clicked:
                        show_metric_dialog(finops_category, budgets_metric, budget_metric_exists, False)

            # Display the metric's display_data (this will be modified by the dialog)
            st.dataframe(
                df,
                use_container_width=True
            )

            # Get the budget count for charts
            budget_count = int(budgets_df['COUNT'].iloc[0]) if 'COUNT' in budgets_df.columns else 0

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Budget Analysis Charts")

            # Row 1: Budget Count Visualization & Budget Status
            budget_chart_col1, budget_chart_col2 = st.columns(2)

            with budget_chart_col1.container(border=True):
                st.markdown(f"##### Budget Count: {budget_count}")
                _render_budget_count_chart_content(budget_count, key_prefix="budget_count_")

            with budget_chart_col2.container(border=True):
                st.markdown("##### Budget Configuration Status")
                _render_budget_status_chart_content(budget_count, key_prefix="budget_status_")

            # ========== NEW SECTION: Budget Inventory Details ==========
            _render_budget_inventory()

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No budget data available for the current execution context.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading budgets: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Budget Count Chart Functions ==========

def _render_budget_count_chart_content(budget_count, key_prefix=""):
    """Render budget count chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_count_bar_chart(budget_count, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_count_standard_pie_chart(budget_count, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_count_donut_pie_chart(budget_count, key_prefix)
    else:
        _render_budget_count_rose_pie_chart(budget_count, key_prefix)


def _render_budget_count_bar_chart(budget_count, key_prefix=""):
    """Render budget count bar chart using Plotly."""

    fig_bar = go.Figure(data=[
        go.Bar(
            x=['Total Budgets'],
            y=[budget_count],
            marker_color='#1f77b4',
            text=[f"{budget_count}"],
            textposition='outside',
            textfont=dict(size=14),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budget_count_standard_pie_chart(budget_count, key_prefix=""):
    """Render budget count standard pie chart using ECharts."""

    chart_data = [
        {"value": budget_count, "name": f"Configured ({budget_count})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets"
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
                "name": "Budget Count",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_count_donut_pie_chart(budget_count, key_prefix=""):
    """Render budget count donut pie chart using ECharts."""

    chart_data = [
        {"value": budget_count, "name": f"Configured ({budget_count})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets"
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
                "name": "Budget Count",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_count_rose_pie_chart(budget_count, key_prefix=""):
    """Render budget count rose pie chart using ECharts."""

    chart_data = [
        {"value": budget_count, "name": f"Configured ({budget_count})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets"
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
                "name": "Budget Count",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Budget Status Chart Functions ==========

def _render_budget_status_chart_content(budget_count, key_prefix=""):
    """Render budget status chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_status_bar_chart(budget_count, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_status_standard_pie_chart(budget_count, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_status_donut_pie_chart(budget_count, key_prefix)
    else:
        _render_budget_status_rose_pie_chart(budget_count, key_prefix)


def _render_budget_status_bar_chart(budget_count, key_prefix=""):
    """Render budget status bar chart using Plotly."""

    has_budgets = budget_count > 0
    status_labels = ['Budgets Configured', 'Budget Adoption']
    status_values = [budget_count, 100 if has_budgets else 0]
    colors = ['#2ca02c' if has_budgets else '#d62728', '#1f77b4']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=status_labels,
            y=status_values,
            marker_color=colors,
            text=[f"{budget_count}", f"{'Active' if has_budgets else 'Not Configured'}"],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Value: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budget_status_standard_pie_chart(budget_count, key_prefix=""):
    """Render budget status standard pie chart using ECharts."""

    has_budgets = budget_count > 0

    chart_data = [
        {"value": budget_count if has_budgets else 1, "name": f"Configured ({budget_count})" if has_budgets else "Not Configured"},
    ]

    if not has_budgets:
        chart_data = [{"value": 1, "name": "No Budgets Configured"}]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}"
        },
        "color": ["#2ca02c" if has_budgets else "#d62728"],
        "series": [
            {
                "name": "Budget Status",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_status_donut_pie_chart(budget_count, key_prefix=""):
    """Render budget status donut pie chart using ECharts."""

    has_budgets = budget_count > 0

    chart_data = [
        {"value": budget_count if has_budgets else 1, "name": f"Configured ({budget_count})" if has_budgets else "Not Configured"},
    ]

    if not has_budgets:
        chart_data = [{"value": 1, "name": "No Budgets Configured"}]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}"
        },
        "color": ["#2ca02c" if has_budgets else "#d62728"],
        "series": [
            {
                "name": "Budget Status",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_status_rose_pie_chart(budget_count, key_prefix=""):
    """Render budget status rose pie chart using ECharts."""

    has_budgets = budget_count > 0

    chart_data = [
        {"value": budget_count if has_budgets else 1, "name": f"Configured ({budget_count})" if has_budgets else "Not Configured"},
    ]

    if not has_budgets:
        chart_data = [{"value": 1, "name": "No Budgets Configured"}]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}"
        },
        "color": ["#2ca02c" if has_budgets else "#d62728"],
        "series": [
            {
                "name": "Budget Status",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Budget Inventory Section ==========

def _render_budget_inventory():
    """Render Budget Inventory section with budget details."""

    st.markdown("---")
    st.markdown("#### Budget Inventory")

    # Introduction text
    st.markdown("""
    **Budget inventory** listing all active budgets with their names, schema locations, creation dates,
    owners, and descriptions ordered by most recent. This provides visibility into all configured budgets
    across the account.
    """)

    try:
        # Budget Inventory Query
        budget_inventory_query = f"""
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
"""


        # Execute the query
        budget_inventory_df = st.session_state.session.sql(budget_inventory_query).to_pandas()

        if not budget_inventory_df.empty:
            # Create Report Category and Metric for budget inventory

            # Create a proper metric object for the dialogs
            # Initialize budget inventory metric with data - this will persist across reruns
            if 'budget_inventory_metric_obj' not in st.session_state:
                st.session_state.budget_inventory_metric_obj = BudgetInventoryMetric(budget_inventory_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.budget_inventory_metric_obj.has_custom_columns:
                    df_copy = budget_inventory_df.copy()
                    df = budget_inventory_df

            # Set dataframes for the report metric

            # Create layout with buttons on top-right and table below

                # Create buttons side by side
                inv_btn_col1, inv_btn_col2 = st.columns(2)

                with inv_btn_col1:
                    # Gear icon button for "Set table" functionality
                    inv_gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="budget_inventory_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if inv_gear_clicked:
                        _show_dialog(st.session_state.budget_inventory_metric_obj, 'display_data', budget_inventory_metric, None, None, None)

                with inv_btn_col2:
                    # Report icon button for "Add to report" functionality
                    inv_metric_exists = ReportManager().metric_exists(budget_inventory_metric.key)
                    inv_report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="budget_inventory_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if inv_report_clicked:
                        show_metric_dialog(finops_category, budget_inventory_metric, inv_metric_exists, False)

            # Display the metric's display_data (this will be modified by the dialog)
            st.dataframe(
                df,
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Budget Inventory Charts")

            # Row 1: Budgets by Owner & Budgets by Schema/Database
            inv_chart_col1, inv_chart_col2 = st.columns(2)

            with inv_chart_col1.container(border=True):
                st.markdown("##### Budgets by Owner")
                _render_budgets_by_owner_chart_content(budget_inventory_df, key_prefix="budget_owner_")

            with inv_chart_col2.container(border=True):
                st.markdown("##### Budgets by Database/Schema")
                _render_budgets_by_path_chart_content(budget_inventory_df, key_prefix="budget_path_")

            # ========== Budget Statistics Section ==========
            _render_budget_statistics()

            # ========== Budget Utilization Section ==========
            _render_budget_utilization()

            # ========== End-of-Month Projection Section ==========
            _render_budget_projection()

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No budget inventory data available. No budgets are configured in this account.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading budget inventory: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Budgets by Owner Chart Functions ==========

def _render_budgets_by_owner_chart_content(df, key_prefix=""):
    """Render budgets by owner chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budgets_by_owner_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budgets_by_owner_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budgets_by_owner_donut_pie_chart(df, key_prefix)
    else:
        _render_budgets_by_owner_rose_pie_chart(df, key_prefix)


def _render_budgets_by_owner_bar_chart(df, key_prefix=""):
    """Render budgets by owner bar chart using Plotly."""

    owner_counts = df['OWNER'].value_counts().reset_index()
    owner_counts.columns = ['OWNER', 'COUNT']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=owner_counts['OWNER'],
            y=owner_counts['COUNT'],
            marker_color='#1f77b4',
            text=owner_counts['COUNT'],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Budgets: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Owner',
        yaxis_title='Number of Budgets',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budgets_by_owner_standard_pie_chart(df, key_prefix=""):
    """Render budgets by owner standard pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Owner",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budgets_by_owner_donut_pie_chart(df, key_prefix=""):
    """Render budgets by owner donut pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Owner",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budgets_by_owner_rose_pie_chart(df, key_prefix=""):
    """Render budgets by owner rose pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Owner",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Budgets by Path Chart Functions ==========

def _render_budgets_by_path_chart_content(df, key_prefix=""):
    """Render budgets by database/schema path chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budgets_by_path_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budgets_by_path_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budgets_by_path_donut_pie_chart(df, key_prefix)
    else:
        _render_budgets_by_path_rose_pie_chart(df, key_prefix)


def _render_budgets_by_path_bar_chart(df, key_prefix=""):
    """Render budgets by path bar chart using Plotly."""

    path_counts = df['FULL_PATH'].value_counts().reset_index()
    path_counts.columns = ['FULL_PATH', 'COUNT']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=path_counts['FULL_PATH'],
            y=path_counts['COUNT'],
            marker_color='#2ca02c',
            text=path_counts['COUNT'],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Budgets: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Database.Schema',
        yaxis_title='Number of Budgets',
        showlegend=False,
        margin=dict(t=20, b=100, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budgets_by_path_standard_pie_chart(df, key_prefix=""):
    """Render budgets by path standard pie chart using ECharts."""

    path_counts = df['FULL_PATH'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{path} ({count})"}
        for path, count in path_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Path",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budgets_by_path_donut_pie_chart(df, key_prefix=""):
    """Render budgets by path donut pie chart using ECharts."""

    path_counts = df['FULL_PATH'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{path} ({count})"}
        for path, count in path_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Path",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budgets_by_path_rose_pie_chart(df, key_prefix=""):
    """Render budgets by path rose pie chart using ECharts."""

    path_counts = df['FULL_PATH'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{path} ({count})"}
        for path, count in path_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Path",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Budget Statistics Section ==========

def _render_budget_statistics():
    """Render Budget Statistics section with breakdown of account vs custom budgets."""

    st.markdown("---")
    st.markdown("#### Budget Statistics")

    # Introduction text
    st.markdown("""
    **Budget statistics summary** showing total count broken down into account-level root budgets
    vs custom budgets. This helps understand the budget hierarchy and adoption across the account.
    """)

    try:
        # Budget Statistics Query
        budget_stats_query = f"""
WITH budget_analysis AS (
    SELECT
        NVL(COUNT(*), 0) AS total_budgets,
        NVL(COUNT(CASE WHEN NAME = 'ACCOUNT_ROOT_BUDGET' THEN 1 END), 0) AS account_budgets,
        NVL(COUNT(CASE WHEN NAME != 'ACCOUNT_ROOT_BUDGET' THEN 1 END), 0) AS custom_budgets,
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
"""


        # Execute the query
        budget_stats_df = st.session_state.session.sql(budget_stats_query).to_pandas()

        if not budget_stats_df.empty:
            # Create Report Category and Metric for budget statistics

            # Create a proper metric object for the dialogs
            # Initialize budget stats metric with data - this will persist across reruns
            if 'budget_stats_metric_obj' not in st.session_state:
                st.session_state.budget_stats_metric_obj = BudgetStatsMetric(budget_stats_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.budget_stats_metric_obj.has_custom_columns:
                    df_copy = budget_stats_df.copy()
                    df = budget_stats_df

            # Set dataframes for the report metric

            # Create layout with buttons on top-right and table below

                # Create buttons side by side
                stats_btn_col1, stats_btn_col2 = st.columns(2)

                with stats_btn_col1:
                    # Gear icon button for "Set table" functionality
                    stats_gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="budget_stats_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if stats_gear_clicked:
                        _show_dialog(st.session_state.budget_stats_metric_obj, 'display_data', budget_stats_metric, None, None, None)

                with stats_btn_col2:
                    # Report icon button for "Add to report" functionality
                    stats_metric_exists = ReportManager().metric_exists(budget_stats_metric.key)
                    stats_report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="budget_stats_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if stats_report_clicked:
                        show_metric_dialog(finops_category, budget_stats_metric, stats_metric_exists, False)

            # Display the metric's display_data (this will be modified by the dialog)
            st.dataframe(
                df,
                use_container_width=True
            )

            # Get values for charts
            total_budgets = int(budget_stats_df['TOTAL_BUDGETS'].iloc[0]) if 'TOTAL_BUDGETS' in budget_stats_df.columns else 0
            account_budgets = int(budget_stats_df['ACCOUNT_BUDGETS'].iloc[0]) if 'ACCOUNT_BUDGETS' in budget_stats_df.columns else 0
            custom_budgets = int(budget_stats_df['CUSTOM_BUDGETS'].iloc[0]) if 'CUSTOM_BUDGETS' in budget_stats_df.columns else 0

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Budget Statistics Charts")

            # Row 1: Budget Type Distribution & Total Budget Count
            stats_chart_col1, stats_chart_col2 = st.columns(2)

            with stats_chart_col1.container(border=True):
                st.markdown(f"##### Budget Type Distribution: {total_budgets} Total")
                _render_budget_type_dist_chart_content(account_budgets, custom_budgets, key_prefix="budget_type_dist_")

            with stats_chart_col2.container(border=True):
                st.markdown(f"##### Budget Breakdown")
                _render_budget_breakdown_chart_content(total_budgets, account_budgets, custom_budgets, key_prefix="budget_breakdown_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No budget statistics data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading budget statistics: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Budget Type Distribution Chart Functions ==========

def _render_budget_type_dist_chart_content(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_type_dist_bar_chart(account_budgets, custom_budgets, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_type_dist_standard_pie_chart(account_budgets, custom_budgets, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_type_dist_donut_pie_chart(account_budgets, custom_budgets, key_prefix)
    else:
        _render_budget_type_dist_rose_pie_chart(account_budgets, custom_budgets, key_prefix)


def _render_budget_type_dist_bar_chart(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution bar chart using Plotly."""

    labels = ['Account Root Budget', 'Custom Budgets']
    values = [account_budgets, custom_budgets]
    colors = ['#2ca02c', '#ff7f0e']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=values,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Budget Type',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budget_type_dist_standard_pie_chart(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution standard pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root Budget ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom Budgets ({custom_budgets})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#ff7f0e"],
        "series": [
            {
                "name": "Budget Type",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_type_dist_donut_pie_chart(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution donut pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root Budget ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom Budgets ({custom_budgets})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#ff7f0e"],
        "series": [
            {
                "name": "Budget Type",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_type_dist_rose_pie_chart(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution rose pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root Budget ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom Budgets ({custom_budgets})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#ff7f0e"],
        "series": [
            {
                "name": "Budget Type",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Budget Breakdown Chart Functions ==========

def _render_budget_breakdown_chart_content(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_breakdown_bar_chart(total_budgets, account_budgets, custom_budgets, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_breakdown_standard_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_breakdown_donut_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix)
    else:
        _render_budget_breakdown_rose_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix)


def _render_budget_breakdown_bar_chart(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown bar chart using Plotly."""

    labels = ['Total Budgets', 'Account Root', 'Custom']
    values = [total_budgets, account_budgets, custom_budgets]
    colors = ['#1f77b4', '#2ca02c', '#ff7f0e']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=values,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Category',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budget_breakdown_standard_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown standard pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom ({custom_budgets})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#ff7f0e"],
        "series": [
            {
                "name": "Budget Breakdown",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_breakdown_donut_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown donut pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom ({custom_budgets})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#ff7f0e"],
        "series": [
            {
                "name": "Budget Breakdown",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_breakdown_rose_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown rose pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom ({custom_budgets})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#ff7f0e"],
        "series": [
            {
                "name": "Budget Breakdown",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Budget Utilization Section ==========

def _render_budget_utilization():
    """Render Budget Utilization section with month-to-date spend tracking."""

    st.markdown("---")
    st.markdown("#### Budget Utilization (Month-to-Date)")

    # Introduction text
    st.markdown("""
    **Month-to-date budget utilization** tracking against 500 credit limit showing current spend,
    utilization percentage, remaining credits, and health status (warning at >90%, caution at >75%).
    """)

    try:
        # Budget Utilization Query
        budget_util_query = f"""
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
"""


        # Execute the query
        budget_util_df = st.session_state.session.sql(budget_util_query).to_pandas()

        if not budget_util_df.empty:
            # Create Report Category and Metric for budget utilization

            # Create a proper metric object for the dialogs
            # Initialize budget utilization metric with data - this will persist across reruns
            if 'budget_util_metric_obj' not in st.session_state:
                st.session_state.budget_util_metric_obj = BudgetUtilMetric(budget_util_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.budget_util_metric_obj.has_custom_columns:
                    df_copy = budget_util_df.copy()
                    df = budget_util_df

            # Set dataframes for the report metric

            # Create layout with buttons on top-right and table below

                # Create buttons side by side
                util_btn_col1, util_btn_col2 = st.columns(2)

                with util_btn_col1:
                    # Gear icon button for "Set table" functionality
                    util_gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="budget_util_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if util_gear_clicked:
                        _show_dialog(st.session_state.budget_util_metric_obj, 'display_data', budget_util_metric, None, None, None)

                with util_btn_col2:
                    # Report icon button for "Add to report" functionality
                    util_metric_exists = ReportManager().metric_exists(budget_util_metric.key)
                    util_report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="budget_util_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if util_report_clicked:
                        show_metric_dialog(finops_category, budget_util_metric, util_metric_exists, False)

            # Display the metric's display_data (this will be modified by the dialog)
            st.dataframe(
                df,
                use_container_width=True
            )

            # Get values for charts
            budget_limit = float(budget_util_df['BUDGET_LIMIT_CREDITS'].iloc[0]) if 'BUDGET_LIMIT_CREDITS' in budget_util_df.columns else 500
            current_spend = float(budget_util_df['CURRENT_SPEND_CREDITS'].iloc[0]) if 'CURRENT_SPEND_CREDITS' in budget_util_df.columns else 0
            utilization_pct = float(budget_util_df['UTILIZATION_PERCENT'].iloc[0]) if 'UTILIZATION_PERCENT' in budget_util_df.columns else 0
            remaining = float(budget_util_df['REMAINING_CREDITS'].iloc[0]) if 'REMAINING_CREDITS' in budget_util_df.columns else 500
            status = str(budget_util_df['STATUS'].iloc[0]) if 'STATUS' in budget_util_df.columns else 'HEALTHY'

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Budget Utilization Charts")

            # Row 1: Utilization Gauge & Spend vs Remaining
            util_chart_col1, util_chart_col2 = st.columns(2)

            with util_chart_col1.container(border=True):
                st.markdown(f"##### Budget Utilization: {utilization_pct:.1f}%")
                _render_budget_utilization_chart_content(current_spend, remaining, budget_limit, key_prefix="budget_util_gauge_")

            with util_chart_col2.container(border=True):
                st.markdown(f"##### Spend vs Remaining: {budget_limit:.0f} Credits")
                _render_spend_remaining_chart_content(current_spend, remaining, key_prefix="spend_remaining_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No budget utilization data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading budget utilization: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Budget Utilization Chart Functions ==========

def _render_budget_utilization_chart_content(current_spend, remaining, budget_limit, key_prefix=""):
    """Render budget utilization chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_utilization_bar_chart(current_spend, remaining, budget_limit, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_utilization_standard_pie_chart(current_spend, remaining, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_utilization_donut_pie_chart(current_spend, remaining, key_prefix)
    else:
        _render_budget_utilization_rose_pie_chart(current_spend, remaining, key_prefix)


def _render_budget_utilization_bar_chart(current_spend, remaining, budget_limit, key_prefix=""):
    """Render budget utilization bar chart using Plotly."""

    # Determine color based on utilization
    utilization_pct = (current_spend / budget_limit) * 100 if budget_limit > 0 else 0
    if utilization_pct > 90:
        spend_color = '#d62728'  # Red - Warning
    elif utilization_pct > 75:
        spend_color = '#ff7f0e'  # Orange - Caution
    else:
        spend_color = '#2ca02c'  # Green - Healthy

    labels = ['Current Spend', 'Remaining', 'Budget Limit']
    values = [current_spend, remaining, budget_limit]
    colors = [spend_color, '#1f77b4', '#7f7f7f']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:.1f}" for v in values],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Credits: %{y:.1f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Category',
        yaxis_title='Credits',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budget_utilization_standard_pie_chart(current_spend, remaining, key_prefix=""):
    """Render budget utilization standard pie chart using ECharts."""

    # Determine color based on utilization
    total = current_spend + remaining
    utilization_pct = (current_spend / total) * 100 if total > 0 else 0
    if utilization_pct > 90:
        spend_color = '#d62728'  # Red - Warning
    elif utilization_pct > 75:
        spend_color = '#ff7f0e'  # Orange - Caution
    else:
        spend_color = '#2ca02c'  # Green - Healthy

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Current Spend ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [spend_color, "#1f77b4"],
        "series": [
            {
                "name": "Budget Utilization",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_utilization_donut_pie_chart(current_spend, remaining, key_prefix=""):
    """Render budget utilization donut pie chart using ECharts."""

    # Determine color based on utilization
    total = current_spend + remaining
    utilization_pct = (current_spend / total) * 100 if total > 0 else 0
    if utilization_pct > 90:
        spend_color = '#d62728'  # Red - Warning
    elif utilization_pct > 75:
        spend_color = '#ff7f0e'  # Orange - Caution
    else:
        spend_color = '#2ca02c'  # Green - Healthy

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Current Spend ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [spend_color, "#1f77b4"],
        "series": [
            {
                "name": "Budget Utilization",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_utilization_rose_pie_chart(current_spend, remaining, key_prefix=""):
    """Render budget utilization rose pie chart using ECharts."""

    # Determine color based on utilization
    total = current_spend + remaining
    utilization_pct = (current_spend / total) * 100 if total > 0 else 0
    if utilization_pct > 90:
        spend_color = '#d62728'  # Red - Warning
    elif utilization_pct > 75:
        spend_color = '#ff7f0e'  # Orange - Caution
    else:
        spend_color = '#2ca02c'  # Green - Healthy

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Current Spend ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [spend_color, "#1f77b4"],
        "series": [
            {
                "name": "Budget Utilization",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Spend vs Remaining Chart Functions ==========

def _render_spend_remaining_chart_content(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_spend_remaining_bar_chart(current_spend, remaining, key_prefix)
    elif chart_type == "Pie Chart":
        _render_spend_remaining_standard_pie_chart(current_spend, remaining, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_spend_remaining_donut_pie_chart(current_spend, remaining, key_prefix)
    else:
        _render_spend_remaining_rose_pie_chart(current_spend, remaining, key_prefix)


def _render_spend_remaining_bar_chart(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining bar chart using Plotly."""

    # Stacked bar chart showing spend vs remaining
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Current Spend',
        x=['Budget'],
        y=[current_spend],
        marker_color='#ff7f0e',
        text=[f"{current_spend:.1f}"],
        textposition='inside',
        textfont=dict(size=12, color='white')
    ))

    fig.add_trace(go.Bar(
        name='Remaining',
        x=['Budget'],
        y=[remaining],
        marker_color='#1f77b4',
        text=[f"{remaining:.1f}"],
        textposition='inside',
        textfont=dict(size=12, color='white')
    ))

    fig.update_layout(
        height=350,
        barmode='stack',
        xaxis_title='',
        yaxis_title='Credits',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        margin=dict(t=40, b=40, l=50, r=20)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_spend_remaining_standard_pie_chart(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining standard pie chart using ECharts."""

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Spent ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#ff7f0e", "#1f77b4"],
        "series": [
            {
                "name": "Spend vs Remaining",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_spend_remaining_donut_pie_chart(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining donut pie chart using ECharts."""

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Spent ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#ff7f0e", "#1f77b4"],
        "series": [
            {
                "name": "Spend vs Remaining",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_spend_remaining_rose_pie_chart(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining rose pie chart using ECharts."""

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Spent ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#ff7f0e", "#1f77b4"],
        "series": [
            {
                "name": "Spend vs Remaining",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== End-of-Month Projection Section ==========

def _render_budget_projection():
    """Render End-of-Month Projection section with spend forecast."""

    st.markdown("---")
    st.markdown("#### End-of-Month Projection")

    # Introduction text
    st.markdown("""
    **End-of-month credit spend forecast** using 30-day average daily spend to project month-end total
    against 500 credit budget limit with status alerts for exceeding or nearing budget.
    """)

    try:
        # End-of-Month Projection Query
        projection_query = f"""
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
"""


        # Execute the query
        projection_df = st.session_state.session.sql(projection_query).to_pandas()

        if not projection_df.empty:
            # Create Report Category and Metric for projection

            # Create a proper metric object for the dialogs
            # Initialize projection metric with data - this will persist across reruns
            if 'projection_metric_obj' not in st.session_state:
                st.session_state.projection_metric_obj = ProjectionMetric(projection_df)
            else:
                # Update the data if it's changed, but preserve any column customizations
                if not st.session_state.projection_metric_obj.has_custom_columns:
                    df_copy = projection_df.copy()
                    df = projection_df

            # Set dataframes for the report metric

            # Create layout with buttons on top-right and table below

                # Create buttons side by side
                proj_btn_col1, proj_btn_col2 = st.columns(2)

                with proj_btn_col1:
                    # Gear icon button for "Set table" functionality
                    proj_gear_clicked = st.button(
                        "Set Table", icon=":material/settings:",
                        key="budget_projection_gear_btn",
                        help="Customize table columns and rows",
                        type="secondary",
                        use_container_width=True
                    )
                    if proj_gear_clicked:
                        _show_dialog(st.session_state.projection_metric_obj, 'display_data', projection_metric, None, None, None)

                with proj_btn_col2:
                    # Report icon button for "Add to report" functionality
                    proj_metric_exists = ReportManager().metric_exists(projection_metric.key)
                    proj_report_clicked = st.button(
                        "Add to Report", icon=":material/add_circle:",
                        key="budget_projection_report_btn",
                        help="Add to report",
                        type="secondary",
                        use_container_width=True
                    )
                    if proj_report_clicked:
                        show_metric_dialog(finops_category, projection_metric, proj_metric_exists, False)

            # Display the metric's display_data (this will be modified by the dialog)
            st.dataframe(
                df,
                use_container_width=True
            )

            # Get values for charts
            budget_limit = float(projection_df['BUDGET_LIMIT_CREDITS'].iloc[0]) if 'BUDGET_LIMIT_CREDITS' in projection_df.columns else 500
            avg_daily = float(projection_df['AVG_DAILY_SPEND_30D'].iloc[0]) if 'AVG_DAILY_SPEND_30D' in projection_df.columns else 0
            days_in_month = int(projection_df['DAYS_IN_MONTH'].iloc[0]) if 'DAYS_IN_MONTH' in projection_df.columns else 30
            days_elapsed = int(projection_df['DAYS_ELAPSED'].iloc[0]) if 'DAYS_ELAPSED' in projection_df.columns else 0
            projected_credits = float(projection_df['PROJECTED_MONTH_END_CREDITS'].iloc[0]) if 'PROJECTED_MONTH_END_CREDITS' in projection_df.columns else 0
            status = str(projection_df['PROJECTION_STATUS'].iloc[0]) if 'PROJECTION_STATUS' in projection_df.columns else 'UNKNOWN'

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### End-of-Month Projection Charts")

            # Row 1: Projected vs Budget & Daily Progress
            proj_chart_col1, proj_chart_col2 = st.columns(2)

            with proj_chart_col1.container(border=True):
                st.markdown(f"##### Projected vs Budget: {projected_credits:.1f} / {budget_limit:.0f}")
                _render_projection_vs_budget_chart_content(projected_credits, budget_limit, key_prefix="proj_vs_budget_")

            with proj_chart_col2.container(border=True):
                st.markdown(f"##### Month Progress: Day {days_elapsed} of {days_in_month}")
                _render_month_progress_chart_content(days_elapsed, days_in_month, avg_daily, key_prefix="month_progress_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No projection data available. Insufficient spending history for forecast.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading projection: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Projection vs Budget Chart Functions ==========

def _render_projection_vs_budget_chart_content(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_projection_vs_budget_bar_chart(projected_credits, budget_limit, key_prefix)
    elif chart_type == "Pie Chart":
        _render_projection_vs_budget_standard_pie_chart(projected_credits, budget_limit, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_projection_vs_budget_donut_pie_chart(projected_credits, budget_limit, key_prefix)
    else:
        _render_projection_vs_budget_rose_pie_chart(projected_credits, budget_limit, key_prefix)


def _render_projection_vs_budget_bar_chart(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget bar chart using Plotly."""

    # Determine color based on projection status
    if projected_credits > budget_limit:
        proj_color = '#d62728'  # Red - Exceeds
    elif projected_credits > budget_limit * 0.9:
        proj_color = '#ff7f0e'  # Orange - Near limit
    else:
        proj_color = '#2ca02c'  # Green - Within budget

    labels = ['Projected Spend', 'Budget Limit']
    values = [projected_credits, budget_limit]
    colors = [proj_color, '#1f77b4']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:.1f}" for v in values],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Credits: %{y:.1f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='Credits',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_projection_vs_budget_standard_pie_chart(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget standard pie chart using ECharts."""

    # Determine color based on projection status
    if projected_credits > budget_limit:
        proj_color = '#d62728'  # Red - Exceeds
    elif projected_credits > budget_limit * 0.9:
        proj_color = '#ff7f0e'  # Orange - Near limit
    else:
        proj_color = '#2ca02c'  # Green - Within budget

    # Show projected as portion of budget
    remaining_in_budget = max(0, budget_limit - projected_credits)

    chart_data = [
        {"value": round(projected_credits, 1), "name": f"Projected ({projected_credits:.1f})"},
        {"value": round(remaining_in_budget, 1), "name": f"Buffer ({remaining_in_budget:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [proj_color, "#1f77b4"],
        "series": [
            {
                "name": "Projection vs Budget",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_projection_vs_budget_donut_pie_chart(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget donut pie chart using ECharts."""

    # Determine color based on projection status
    if projected_credits > budget_limit:
        proj_color = '#d62728'  # Red - Exceeds
    elif projected_credits > budget_limit * 0.9:
        proj_color = '#ff7f0e'  # Orange - Near limit
    else:
        proj_color = '#2ca02c'  # Green - Within budget

    remaining_in_budget = max(0, budget_limit - projected_credits)

    chart_data = [
        {"value": round(projected_credits, 1), "name": f"Projected ({projected_credits:.1f})"},
        {"value": round(remaining_in_budget, 1), "name": f"Buffer ({remaining_in_budget:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [proj_color, "#1f77b4"],
        "series": [
            {
                "name": "Projection vs Budget",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_projection_vs_budget_rose_pie_chart(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget rose pie chart using ECharts."""

    # Determine color based on projection status
    if projected_credits > budget_limit:
        proj_color = '#d62728'  # Red - Exceeds
    elif projected_credits > budget_limit * 0.9:
        proj_color = '#ff7f0e'  # Orange - Near limit
    else:
        proj_color = '#2ca02c'  # Green - Within budget

    remaining_in_budget = max(0, budget_limit - projected_credits)

    chart_data = [
        {"value": round(projected_credits, 1), "name": f"Projected ({projected_credits:.1f})"},
        {"value": round(remaining_in_budget, 1), "name": f"Buffer ({remaining_in_budget:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [proj_color, "#1f77b4"],
        "series": [
            {
                "name": "Projection vs Budget",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Month Progress Chart Functions ==========

def _render_month_progress_chart_content(days_elapsed, days_in_month, avg_daily, key_prefix=""):
    """Render month progress chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_month_progress_bar_chart(days_elapsed, days_in_month, avg_daily, key_prefix)
    elif chart_type == "Pie Chart":
        _render_month_progress_standard_pie_chart(days_elapsed, days_in_month, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_month_progress_donut_pie_chart(days_elapsed, days_in_month, key_prefix)
    else:
        _render_month_progress_rose_pie_chart(days_elapsed, days_in_month, key_prefix)


def _render_month_progress_bar_chart(days_elapsed, days_in_month, avg_daily, key_prefix=""):
    """Render month progress bar chart using Plotly."""

    days_remaining = days_in_month - days_elapsed

    labels = ['Days Elapsed', 'Days Remaining', f'Avg Daily Spend']
    values = [days_elapsed, days_remaining, avg_daily]
    colors = ['#2ca02c', '#1f77b4', '#ff7f0e']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{days_elapsed}", f"{days_remaining}", f"{avg_daily:.2f}"],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Value: %{y:.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='Days / Credits',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_month_progress_standard_pie_chart(days_elapsed, days_in_month, key_prefix=""):
    """Render month progress standard pie chart using ECharts."""

    days_remaining = days_in_month - days_elapsed

    chart_data = [
        {"value": days_elapsed, "name": f"Days Elapsed ({days_elapsed})"},
        {"value": days_remaining, "name": f"Days Remaining ({days_remaining})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} days ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#1f77b4"],
        "series": [
            {
                "name": "Month Progress",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_month_progress_donut_pie_chart(days_elapsed, days_in_month, key_prefix=""):
    """Render month progress donut pie chart using ECharts."""

    days_remaining = days_in_month - days_elapsed

    chart_data = [
        {"value": days_elapsed, "name": f"Days Elapsed ({days_elapsed})"},
        {"value": days_remaining, "name": f"Days Remaining ({days_remaining})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} days ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#1f77b4"],
        "series": [
            {
                "name": "Month Progress",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_month_progress_rose_pie_chart(days_elapsed, days_in_month, key_prefix=""):
    """Render month progress rose pie chart using ECharts."""

    days_remaining = days_in_month - days_elapsed

    chart_data = [
        {"value": days_elapsed, "name": f"Days Elapsed ({days_elapsed})"},
        {"value": days_remaining, "name": f"Days Remaining ({days_remaining})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} days ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#1f77b4"],
        "series": [
            {
                "name": "Month Progress",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")

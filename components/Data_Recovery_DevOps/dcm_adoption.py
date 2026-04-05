import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_echarts import st_echarts




def comp_dcm_adoption(entry_actions=None):
    """Database Change Management (DCM) Adoption Component

    Analyzes DDL deployment patterns and categorizes them as declarative DevOps,
    file/Git-based, or imperative standard DDL.

    Args:
        entry_actions: Optional entry actions for the component
    """
    try:
        st.markdown("### Database Change Management (DCM) Adoption")

        # DDL Deployment Pattern Analysis Expander
        with st.expander("DDL Deployment Pattern Analysis", expanded=True):
            st.markdown("DDL deployment pattern analysis categorizing successful CREATE/ALTER operations as declarative DevOps, file/Git-based, or imperative standard DDL by execution count and user distribution over last 30 days.")

            # Query for DDL deployment pattern analysis
            ddl_query = f"""
            SELECT
                CASE
                    WHEN query_text ILIKE '%CREATE OR ALTER%' THEN 'Declarative (DevOps Pattern)'
                    WHEN query_text ILIKE '%EXECUTE IMMEDIATE FROM%' THEN 'Deployment from File/Git'
                    ELSE 'Imperative (Standard DDL)'
                END AS ddl_pattern,
                COUNT(*) AS execution_count,
                COUNT(DISTINCT user_name) AS distinct_users
            FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND query_type IN ('CREATE_TABLE', 'ALTER_TABLE', 'EXECUTE_IMMEDIATE')
              AND execution_status = 'SUCCESS'
            GROUP BY ALL
            ORDER BY 2 DESC
            """

            # Display the query in terminal
            print("=" * 100)
            print("🔧 DDL DEPLOYMENT PATTERN ANALYSIS QUERY")
            print("=" * 100)
            print(f"🏢 ACCOUNT_ID: {account_id}")
            print("=" * 100)
            print(ddl_query)
            print("=" * 100)

            try:
                df = st.session_state.session.sql(ddl_query).to_pandas()
            except Exception as e:
                # st.error(f"Error executing query: {str(e)}")
                st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                            f'</div>', unsafe_allow_html=True)
                return

            if df.empty:
                st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;No DDL deployment pattern data found for the last 30 days.'
                            '</div>', unsafe_allow_html=True)
                return

            # Rename columns for display
            df.columns = ['DDL_PATTERN', 'EXECUTION_COUNT', 'DISTINCT_USERS']

            # Render the table with Set Table and Add to Report buttons
            _render_ddl_table(df)

            # Render charts (2 per row)
            st.markdown("---")
            _render_ddl_charts(df)

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ============================
# Table with Set Table & Add to Report
# ============================

def _render_ddl_table(df):
    """Render DDL Pattern data table with Set Table and Add to Report buttons."""

    # Create Report Category and Metric for DDL pattern analysis
    ddl_category = ReportCategory('data_recovery_devops', 'Data Recovery & DevOps')
    ddl_metric = ReportMetric('ddl_deployment_patterns', 'data_recovery_devops', 'DDL Deployment Pattern Analysis')

    # Create a proper metric object for the dialogs
    class DDLMetric:
        def __init__(self, data):
            self.display_data = data
            self.display_data_copy = data.copy()
            self.has_custom_columns = False

    # Initialize DDL metric with data - this will persist across reruns
    if 'ddl_metric_obj' not in st.session_state:
        st.session_state.ddl_metric_obj = DDLMetric(df)
    else:
        # Update the data if it's changed, but preserve any column customizations
        if not st.session_state.ddl_metric_obj.has_custom_columns:
            st.session_state.ddl_metric_obj.display_data_copy = df.copy()
            st.session_state.ddl_metric_obj.display_data = df

    # Set dataframes for the report metric
    ddl_metric.dataframes = [st.session_state.ddl_metric_obj.display_data]

    # Create layout with buttons on top-right and table below
    button_row_empty, button_row_col = st.columns([0.75, 0.25])

    with button_row_col:
        # Create buttons side by side
        btn_col1, btn_col2 = st.columns(2)

        with btn_col1:
            # Gear icon button for "Set table" functionality
            gear_clicked = st.button(
                "Set Table", icon=":material/settings:",
                key="ddl_config_gear_btn",
                help="Customize table columns and rows",
                type="secondary",
                use_container_width=True
            )
            if gear_clicked:
                _show_dialog(st.session_state.ddl_metric_obj, 'display_data', ddl_metric, None, None, None)

        with btn_col2:
            # Report icon button for "Add to report" functionality
            metric_exists = ReportManager().metric_exists(ddl_metric.key)
            report_clicked = st.button(
                "Add to Report", icon=":material/add_circle:",
                key="ddl_config_report_btn",
                help="Add to report",
                type="secondary",
                use_container_width=True
            )
            if report_clicked:
                show_metric_dialog(ddl_category, ddl_metric, metric_exists, False)

    # Display the metric's display_data (this will be modified by the dialog)
    st.dataframe(
        st.session_state.ddl_metric_obj.display_data,
        use_container_width=True
    )


# ============================
# Chart Rendering (2 per row)
# ============================

def _render_ddl_charts(df):
    """Render DDL Pattern charts - 2 charts per row with chart type selectors."""

    col1, col2 = st.columns(2)

    with col1.container(border=True):
        st.markdown("##### Execution Count by DDL Pattern")
        _render_execution_count_chart(df, key_prefix="exec_count_")

    with col2.container(border=True):
        st.markdown("##### Distinct Users by DDL Pattern")
        _render_distinct_users_chart(df, key_prefix="distinct_users_")


# ============================
# Execution Count Chart
# ============================

def _render_execution_count_chart(df, key_prefix=""):
    """Render execution count chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_execution_count_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_execution_count_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_execution_count_donut_chart(df, key_prefix)
    else:
        _render_execution_count_rose_chart(df, key_prefix)


def _render_execution_count_bar_chart(df, key_prefix=""):
    """Render execution count bar chart using Plotly."""
    # Sort ascending for horizontal bar layout
    plot_df = df.sort_values('EXECUTION_COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DDL_PATTERN'],
            x=plot_df['EXECUTION_COUNT'],
            orientation='h',
            marker_color='#1f77b4',
            text=[f"{val:,}" for val in plot_df['EXECUTION_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Execution Count: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Execution Count',
        yaxis_title='DDL Pattern',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_execution_count_pie_chart(df, key_prefix=""):
    """Render execution count pie chart using ECharts."""
    chart_data = [
        {"value": int(row['EXECUTION_COUNT']), "name": f"{row['DDL_PATTERN']} ({row['EXECUTION_COUNT']:,})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Execution Count",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_execution_count_donut_chart(df, key_prefix=""):
    """Render execution count donut chart using ECharts."""
    chart_data = [
        {"value": int(row['EXECUTION_COUNT']), "name": f"{row['DDL_PATTERN']} ({row['EXECUTION_COUNT']:,})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Execution Count",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_execution_count_rose_chart(df, key_prefix=""):
    """Render execution count rose chart using ECharts."""
    chart_data = [
        {"value": int(row['EXECUTION_COUNT']), "name": row['DDL_PATTERN']}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Execution Count",
            "type": "pie",
            "radius": ["10%", "60%"],
            "center": ["50%", "45%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


# ============================
# Distinct Users Chart
# ============================

def _render_distinct_users_chart(df, key_prefix=""):
    """Render distinct users chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_distinct_users_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_distinct_users_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_distinct_users_donut_chart(df, key_prefix)
    else:
        _render_distinct_users_rose_chart(df, key_prefix)


def _render_distinct_users_bar_chart(df, key_prefix=""):
    """Render distinct users bar chart using Plotly."""
    # Sort ascending for horizontal bar layout
    plot_df = df.sort_values('DISTINCT_USERS', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DDL_PATTERN'],
            x=plot_df['DISTINCT_USERS'],
            orientation='h',
            marker_color='#2ca02c',
            text=[f"{val:,}" for val in plot_df['DISTINCT_USERS']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Distinct Users: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Distinct Users',
        yaxis_title='DDL Pattern',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_distinct_users_pie_chart(df, key_prefix=""):
    """Render distinct users pie chart using ECharts."""
    chart_data = [
        {"value": int(row['DISTINCT_USERS']), "name": f"{row['DDL_PATTERN']} ({row['DISTINCT_USERS']:,})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Distinct Users",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_distinct_users_donut_chart(df, key_prefix=""):
    """Render distinct users donut chart using ECharts."""
    chart_data = [
        {"value": int(row['DISTINCT_USERS']), "name": f"{row['DDL_PATTERN']} ({row['DISTINCT_USERS']:,})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Distinct Users",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_distinct_users_rose_chart(df, key_prefix=""):
    """Render distinct users rose chart using ECharts."""
    chart_data = [
        {"value": int(row['DISTINCT_USERS']), "name": row['DDL_PATTERN']}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Distinct Users",
            "type": "pie",
            "radius": ["10%", "60%"],
            "center": ["50%", "45%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")

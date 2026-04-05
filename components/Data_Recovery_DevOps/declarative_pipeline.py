import streamlit as st
import pandas as pd
import plotly.graph_objects as go
try:
    from streamlit_echarts import st_echarts
except ImportError:
    def st_echarts(**kwargs):
        import streamlit as st
        st.info("Chart unavailable (echarts not supported in SiS)")


def comp_declarative_pipeline(entry_actions=None):
    """Declarative Pipeline Adoption (Dynamic Tables) Component

    Analyzes orchestration pattern comparison showing activity counts for
    declarative Dynamic Tables vs imperative Tasks over last 7 days.

    Args:
        entry_actions: Optional entry actions for the component
    """
    try:
        # Get session and context
        try:
            from snowflake.snowpark.context import get_active_session
            session = get_active_session()
        except Exception as e:
            st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Unable to get Snowflake session: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if not session:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;Snowflake session not available.'
                        '</div>', unsafe_allow_html=True)
            return

        # Orchestration Pattern Comparison expander
        with st.expander("Orchestration Pattern Comparison", expanded=True):
            # Introduction text (no CSS styling)
            st.markdown("Orchestration pattern comparison showing activity counts for declarative Dynamic Tables vs imperative Tasks over last 7 days.")
            st.markdown("<br>", unsafe_allow_html=True)

            # Build and execute the query
            query = f"""
            WITH dt_usage AS (
                SELECT 'Dynamic Tables (Declarative)' AS type, COUNT(*) as activity_count
                FROM SNOWFLAKE.ACCOUNT_USAGE.dynamic_table_refresh_history
                WHERE data_timestamp >= DATEADD('day', -7, CURRENT_TIMESTAMP())
            ),
            task_usage AS (
                SELECT 'Tasks (Imperative)' AS type, COUNT(*) as activity_count
                FROM SNOWFLAKE.ACCOUNT_USAGE.task_history
                WHERE scheduled_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
            ),
            aggr AS (
                SELECT * FROM dt_usage
                UNION ALL
                SELECT * FROM task_usage
            )
            SELECT
                a.*
            FROM aggr a
            """


            # Execute query
            try:
                df = session.sql(query).to_pandas()
            except Exception as e:
                st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                            f'</div>', unsafe_allow_html=True)
                return

            if df.empty:
                st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;No orchestration pattern data found for the last 7 days.'
                            '</div>', unsafe_allow_html=True)
                return

            # Rename columns for display
            df.columns = ['ORCHESTRATION_TYPE', 'ACTIVITY_COUNT']


            # Create metric object for dialogs
            # Initialize or update metric object in session state


            # Display the dataframe
            st.dataframe(
                df,
                hide_index=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Orchestration Analytics Charts")

            # Row 1: Two charts
            col1, col2 = st.columns(2)

            with col1.container(border=True):
                st.markdown("##### Activity Count by Orchestration Type")
                _render_activity_count_chart(df, key_prefix="activity_")

            with col2.container(border=True):
                st.markdown("##### Declarative vs Imperative Distribution")
                _render_distribution_chart(df, key_prefix="dist_")

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ============================
# Chart Type Selector & Charts for Activity Count
# ============================

def _render_activity_count_chart(df, key_prefix=""):
    """Render activity count by orchestration type chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_activity_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_activity_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_activity_donut_chart(df, key_prefix)
    else:
        _render_activity_rose_chart(df, key_prefix)


def _render_activity_bar_chart(df, key_prefix=""):
    """Render activity count bar chart using Plotly."""
    # Sort ascending for horizontal bar layout
    plot_df = df.sort_values('ACTIVITY_COUNT', ascending=True)

    # Define colors for declarative vs imperative
    colors = ['#2ca02c' if 'Declarative' in t else '#1f77b4' for t in plot_df['ORCHESTRATION_TYPE']]

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['ORCHESTRATION_TYPE'],
            x=plot_df['ACTIVITY_COUNT'],
            orientation='h',
            marker_color=colors,
            text=[f"{int(val):,}" for val in plot_df['ACTIVITY_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Activity Count: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Activity Count',
        yaxis_title='Orchestration Type',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_activity_pie_chart(df, key_prefix=""):
    """Render activity count pie chart using ECharts."""
    chart_data = [
        {"value": int(row['ACTIVITY_COUNT']), "name": f"{row['ORCHESTRATION_TYPE']} ({int(row['ACTIVITY_COUNT']):,})"}
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
        "color": ["#2ca02c", "#1f77b4"],
        "series": [{
            "name": "Activity Count",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_activity_donut_chart(df, key_prefix=""):
    """Render activity count donut chart using ECharts."""
    chart_data = [
        {"value": int(row['ACTIVITY_COUNT']), "name": f"{row['ORCHESTRATION_TYPE']} ({int(row['ACTIVITY_COUNT']):,})"}
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
        "color": ["#2ca02c", "#1f77b4"],
        "series": [{
            "name": "Activity Count",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_activity_rose_chart(df, key_prefix=""):
    """Render activity count rose chart using ECharts."""
    chart_data = [
        {"value": int(row['ACTIVITY_COUNT']), "name": row['ORCHESTRATION_TYPE']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} activities ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#2ca02c", "#1f77b4"],
        "series": [{
            "name": "Activity Count",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


# ============================
# Chart Type Selector & Charts for Distribution
# ============================

def _render_distribution_chart(df, key_prefix=""):
    """Render distribution chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_dist_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_dist_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_dist_donut_chart(df, key_prefix)
    else:
        _render_dist_rose_chart(df, key_prefix)


def _render_dist_bar_chart(df, key_prefix=""):
    """Render distribution bar chart using Plotly."""
    # Calculate percentages
    total = df['ACTIVITY_COUNT'].sum()
    plot_df = df.copy()
    plot_df['PERCENTAGE'] = (plot_df['ACTIVITY_COUNT'] / total * 100).round(1)
    plot_df = plot_df.sort_values('PERCENTAGE', ascending=True)

    # Define colors for declarative vs imperative
    colors = ['#2ca02c' if 'Declarative' in t else '#1f77b4' for t in plot_df['ORCHESTRATION_TYPE']]

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['ORCHESTRATION_TYPE'],
            x=plot_df['PERCENTAGE'],
            orientation='h',
            marker_color=colors,
            text=[f"{val:.1f}%" for val in plot_df['PERCENTAGE']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Percentage: %{x:.1f}%<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Percentage (%)',
        yaxis_title='Orchestration Type',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_dist_pie_chart(df, key_prefix=""):
    """Render distribution pie chart using ECharts."""
    total = df['ACTIVITY_COUNT'].sum()
    chart_data = [
        {"value": int(row['ACTIVITY_COUNT']), "name": f"{row['ORCHESTRATION_TYPE']} ({row['ACTIVITY_COUNT']/total*100:.1f}%)"}
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
        "color": ["#2ca02c", "#1f77b4"],
        "series": [{
            "name": "Distribution",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "label": {"formatter": "{d}%"},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_dist_donut_chart(df, key_prefix=""):
    """Render distribution donut chart using ECharts."""
    total = df['ACTIVITY_COUNT'].sum()
    chart_data = [
        {"value": int(row['ACTIVITY_COUNT']), "name": f"{row['ORCHESTRATION_TYPE']} ({row['ACTIVITY_COUNT']/total*100:.1f}%)"}
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
        "color": ["#2ca02c", "#1f77b4"],
        "series": [{
            "name": "Distribution",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "label": {"formatter": "{d}%"},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_dist_rose_chart(df, key_prefix=""):
    """Render distribution rose chart using ECharts."""
    chart_data = [
        {"value": int(row['ACTIVITY_COUNT']), "name": row['ORCHESTRATION_TYPE']}
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
        "color": ["#2ca02c", "#1f77b4"],
        "series": [{
            "name": "Distribution",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")

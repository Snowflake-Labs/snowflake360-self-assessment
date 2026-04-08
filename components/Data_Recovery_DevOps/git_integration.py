import streamlit as st
import pandas as pd
import plotly.graph_objects as go
try:
    from streamlit_echarts import st_echarts
except ImportError:
    def st_echarts(**kwargs):
        import streamlit as st
        st.info("Chart unavailable (echarts not supported in SiS)")


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




def comp_git_integration(entry_actions=None):
    """Git Integration Usage Component

    Analyzes Git integration activity including repository fetches/updates
    and executions from Git branches/tags.

    Args:
        entry_actions: Optional entry actions for the component
    """
    try:
        st.markdown("### Git Integration Usage")

        # Git Integration Activity Analysis Expander
        with st.expander("Git Integration Activity Analysis", expanded=True):
            st.markdown("Git integration activity analysis categorizing operations as repository fetches/updates or executions from Git branches/tags over last 30 days.")

            # Query for Git integration activity analysis
            git_query = f"""
            SELECT
                'Git Operation' AS category,
                CASE
                    WHEN query_text ILIKE '%ALTER GIT REPOSITORY%FETCH%' THEN 'Git Fetch (Update)'
                    WHEN query_text ILIKE '%FROM @%branches/%' OR query_text ILIKE '%FROM @%tags/%' THEN 'Execution from Git'
                    ELSE 'Other'
                END AS operation_type,
                COUNT(*) AS count_ops
            FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND (
                  query_text ILIKE '%ALTER GIT REPOSITORY%'
                  OR query_text ILIKE '%FROM @%'
              )
            GROUP BY ALL
            """



            try:
                df = _cached_sql("rd_git_integration", git_query)
            except Exception as e:
                # st.error(f"Error executing query: {str(e)}")
                st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                            f'</div>', unsafe_allow_html=True)
                return

            if df.empty:
                st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;No Git integration activity data found for the last 30 days.'
                            '</div>', unsafe_allow_html=True)
                return

            # Rename columns for display
            df.columns = ['CATEGORY', 'OPERATION_TYPE', 'COUNT_OPS']

            # Render the table with Set Table and Add to Report buttons
            _render_git_table(df)

            # Render charts (2 per row)
            st.markdown("---")
            _render_git_charts(df)

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ============================
# Table with Set Table & Add to Report
# ============================

def _render_git_table(df):
    """Render Git Integration data table."""
    st.dataframe(df, use_container_width=True)


# ============================
# Chart Rendering (2 per row)
# ============================

def _render_git_charts(df):
    """Render Git Integration charts - 2 charts per row with chart type selectors."""

    col1, col2 = st.columns(2)

    with col1.container():
        st.markdown("##### Operation Count by Type")
        _render_operation_count_chart(df, key_prefix="op_count_")

    with col2.container():
        st.markdown("##### Git Operations Distribution")
        _render_operations_distribution_chart(df, key_prefix="op_dist_")


# ============================
# Operation Count Chart
# ============================

def _render_operation_count_chart(df, key_prefix=""):
    """Render operation count chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_operation_count_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_operation_count_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_operation_count_donut_chart(df, key_prefix)
    else:
        _render_operation_count_rose_chart(df, key_prefix)


def _render_operation_count_bar_chart(df, key_prefix=""):
    """Render operation count bar chart using Plotly."""
    # Sort ascending for horizontal bar layout
    plot_df = df.sort_values('COUNT_OPS', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['OPERATION_TYPE'],
            x=plot_df['COUNT_OPS'],
            orientation='h',
            marker_color='#29B5E8',
            text=[f"{val:,}" for val in plot_df['COUNT_OPS']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Operation Count',
        yaxis_title='Operation Type',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_operation_count_pie_chart(df, key_prefix=""):
    """Render operation count pie chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OPS']), "name": f"{row['OPERATION_TYPE']} ({row['COUNT_OPS']:,})"}
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
            "name": "Operation Count",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_operation_count_donut_chart(df, key_prefix=""):
    """Render operation count donut chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OPS']), "name": f"{row['OPERATION_TYPE']} ({row['COUNT_OPS']:,})"}
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
            "name": "Operation Count",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_operation_count_rose_chart(df, key_prefix=""):
    """Render operation count rose chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OPS']), "name": row['OPERATION_TYPE']}
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
            "name": "Operation Count",
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
# Operations Distribution Chart
# ============================

def _render_operations_distribution_chart(df, key_prefix=""):
    """Render operations distribution chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_distribution_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_distribution_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_distribution_donut_chart(df, key_prefix)
    else:
        _render_distribution_rose_chart(df, key_prefix)


def _render_distribution_bar_chart(df, key_prefix=""):
    """Render distribution bar chart using Plotly."""
    # Calculate percentage for each operation type
    total = df['COUNT_OPS'].sum()
    plot_df = df.copy()
    plot_df['PERCENTAGE'] = (plot_df['COUNT_OPS'] / total * 100).round(1)
    plot_df = plot_df.sort_values('PERCENTAGE', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['OPERATION_TYPE'],
            x=plot_df['PERCENTAGE'],
            orientation='h',
            marker_color='#0077B6',
            text=[f"{val:.1f}%" for val in plot_df['PERCENTAGE']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Percentage: %{x:.1f}%<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Percentage (%)',
        yaxis_title='Operation Type',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_distribution_pie_chart(df, key_prefix=""):
    """Render distribution pie chart using ECharts."""
    total = df['COUNT_OPS'].sum()
    chart_data = [
        {"value": int(row['COUNT_OPS']), "name": f"{row['OPERATION_TYPE']} ({row['COUNT_OPS']/total*100:.1f}%)"}
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
            "name": "Distribution",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_distribution_donut_chart(df, key_prefix=""):
    """Render distribution donut chart using ECharts."""
    total = df['COUNT_OPS'].sum()
    chart_data = [
        {"value": int(row['COUNT_OPS']), "name": f"{row['OPERATION_TYPE']} ({row['COUNT_OPS']/total*100:.1f}%)"}
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
            "name": "Distribution",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_distribution_rose_chart(df, key_prefix=""):
    """Render distribution rose chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OPS']), "name": row['OPERATION_TYPE']}
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
            "name": "Distribution",
            "type": "pie",
            "radius": ["10%", "60%"],
            "center": ["50%", "45%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")

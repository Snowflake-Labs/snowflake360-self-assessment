import streamlit as st
import pandas as pd
import plotly.graph_objects as go
try:
    from streamlit_echarts import st_echarts
except ImportError:
    def st_echarts(**kwargs):
        import streamlit as st
        st.info("Chart unavailable (echarts not supported in SiS)")


def comp_bulk_load_analysis(entry_actions=None):
    """
    Bulk Load (COPY INTO) Analysis Component

    Analyzes bulk load operations using COPY INTO commands for last 30 days.
    Shows top 20 tables by volume with file size metrics and health checks.
    """
    try:
        st.markdown("COPY command ingestion analysis for last 30 days showing top 20 tables by volume, "
                    "file size metrics, and health checks for outliers and small files.<br><br>", unsafe_allow_html=True)

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

        query = """
        WITH copy_stats AS (
            SELECT
                table_schema_name || '.' || table_name AS target_table,
                COUNT(*) AS job_count,
                SUM(file_size) / POW(1024, 3) AS total_gb_ingested,
                AVG(file_size) / POW(1024, 2) AS avg_file_size_mb,
                MAX(file_size) / POW(1024, 2) AS max_file_size_mb,

                CASE
                    WHEN MAX(file_size) > (AVG(file_size) * 100) THEN '⚠️ High Variance (Outliers)'
                    WHEN AVG(file_size) < 10 THEN '⚠️ Small Files (<10MB)'
                    ELSE '✅ Healthy'
                END AS health_check

            FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
            WHERE status = 'Loaded'
              AND pipe_name IS NULL
              AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY 1
        )
        SELECT
            target_table,
            job_count AS "Load Events",
            ROUND(total_gb_ingested, 2) AS "Total GB",
            ROUND(avg_file_size_mb, 2) AS "Avg File (MB)",
            ROUND(max_file_size_mb, 2) AS "Max File (MB)",
            health_check
        FROM copy_stats
        ORDER BY total_gb_ingested DESC
        LIMIT 20
        """

        try:
            df = session.sql(query).to_pandas()
        except Exception as e:
            st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No COPY INTO data found for the last 30 days.'
                        '</div>', unsafe_allow_html=True)
            return

        df.columns = ['TARGET_TABLE', 'LOAD_EVENTS', 'TOTAL_GB', 'AVG_FILE_MB', 'MAX_FILE_MB', 'HEALTH_CHECK']

        with st.expander("COPY INTO Load Statistics (Top 20 Tables)", expanded=True):
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")
            st.markdown("#### Ingestion Analytics Charts")

            col1, col2 = st.columns(2)

            with col1.container(border=True):
                st.markdown("##### Top Tables by Total Volume Ingested (GB)")
                _render_volume_chart(df, key_prefix="vol_")

            with col2.container(border=True):
                st.markdown("##### Load Events Distribution")
                _render_load_events_chart(df, key_prefix="events_")

            col3, col4 = st.columns(2)

            with col3.container(border=True):
                st.markdown("##### Average File Size by Table (MB)")
                _render_avg_file_size_chart(df, key_prefix="avgfile_")

            with col4.container(border=True):
                st.markdown("##### Health Check Summary")
                _render_health_check_chart(df, key_prefix="health_")

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_volume_chart(df, key_prefix=""):
    """Render top tables by volume chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_volume_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_volume_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_volume_donut_chart(df, key_prefix)
    else:
        _render_volume_rose_chart(df, key_prefix)


def _render_volume_bar_chart(df, key_prefix=""):
    """Render volume bar chart using Plotly."""
    plot_df = df.head(10).sort_values('TOTAL_GB', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['TARGET_TABLE'],
            x=plot_df['TOTAL_GB'],
            orientation='h',
            marker_color='#1f77b4',
            text=[f"{val:.2f} GB" for val in plot_df['TOTAL_GB']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Volume: %{x:.2f} GB<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Total GB Ingested',
        yaxis_title='Target Table',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_volume_pie_chart(df, key_prefix=""):
    """Render volume pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['TOTAL_GB']), "name": f"{row['TARGET_TABLE']} ({row['TOTAL_GB']:.2f} GB)"}
        for _, row in plot_df.iterrows()
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
            "name": "Volume",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_volume_donut_chart(df, key_prefix=""):
    """Render volume donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['TOTAL_GB']), "name": f"{row['TARGET_TABLE']} ({row['TOTAL_GB']:.2f} GB)"}
        for _, row in plot_df.iterrows()
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
            "name": "Volume",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_volume_rose_chart(df, key_prefix=""):
    """Render volume rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['TOTAL_GB']), "name": row['TARGET_TABLE']}
        for _, row in plot_df.iterrows()
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} GB ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Volume",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_load_events_chart(df, key_prefix=""):
    """Render load events chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_events_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_events_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_events_donut_chart(df, key_prefix)
    else:
        _render_events_rose_chart(df, key_prefix)


def _render_events_bar_chart(df, key_prefix=""):
    """Render load events bar chart using Plotly."""
    plot_df = df.head(10).sort_values('LOAD_EVENTS', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['TARGET_TABLE'],
            x=plot_df['LOAD_EVENTS'],
            orientation='h',
            marker_color='#ff7f0e',
            text=[f"{int(val)}" for val in plot_df['LOAD_EVENTS']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Load Events: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Load Events',
        yaxis_title='Target Table',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_events_pie_chart(df, key_prefix=""):
    """Render load events pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['LOAD_EVENTS']), "name": f"{row['TARGET_TABLE']} ({int(row['LOAD_EVENTS'])} events)"}
        for _, row in plot_df.iterrows()
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
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#1f77b4"],
        "series": [{
            "name": "Events",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_events_donut_chart(df, key_prefix=""):
    """Render load events donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['LOAD_EVENTS']), "name": f"{row['TARGET_TABLE']} ({int(row['LOAD_EVENTS'])} events)"}
        for _, row in plot_df.iterrows()
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
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#1f77b4"],
        "series": [{
            "name": "Events",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_events_rose_chart(df, key_prefix=""):
    """Render load events rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['LOAD_EVENTS']), "name": row['TARGET_TABLE']}
        for _, row in plot_df.iterrows()
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} events ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#1f77b4"],
        "series": [{
            "name": "Events",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_avg_file_size_chart(df, key_prefix=""):
    """Render average file size chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_avg_file_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_avg_file_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_avg_file_donut_chart(df, key_prefix)
    else:
        _render_avg_file_rose_chart(df, key_prefix)


def _render_avg_file_bar_chart(df, key_prefix=""):
    """Render average file size bar chart using Plotly."""
    plot_df = df.head(10).sort_values('AVG_FILE_MB', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['TARGET_TABLE'],
            x=plot_df['AVG_FILE_MB'],
            orientation='h',
            marker_color='#2ca02c',
            text=[f"{val:.1f} MB" for val in plot_df['AVG_FILE_MB']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Avg File Size: %{x:.2f} MB<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Average File Size (MB)',
        yaxis_title='Target Table',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_avg_file_pie_chart(df, key_prefix=""):
    """Render average file size pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_FILE_MB']), "name": f"{row['TARGET_TABLE']} ({row['AVG_FILE_MB']:.1f} MB)"}
        for _, row in plot_df.iterrows()
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
        "color": ["#2ca02c", "#98df8a", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#d62728", "#ff9896", "#9467bd", "#c5b0d5"],
        "series": [{
            "name": "Avg File Size",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_avg_file_donut_chart(df, key_prefix=""):
    """Render average file size donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_FILE_MB']), "name": f"{row['TARGET_TABLE']} ({row['AVG_FILE_MB']:.1f} MB)"}
        for _, row in plot_df.iterrows()
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
        "color": ["#2ca02c", "#98df8a", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#d62728", "#ff9896", "#9467bd", "#c5b0d5"],
        "series": [{
            "name": "Avg File Size",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_avg_file_rose_chart(df, key_prefix=""):
    """Render average file size rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_FILE_MB']), "name": row['TARGET_TABLE']}
        for _, row in plot_df.iterrows()
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} MB ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#2ca02c", "#98df8a", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#d62728", "#ff9896", "#9467bd", "#c5b0d5"],
        "series": [{
            "name": "Avg File Size",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_health_check_chart(df, key_prefix=""):
    """Render health check summary chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_health_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_health_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_health_donut_chart(df, key_prefix)
    else:
        _render_health_rose_chart(df, key_prefix)


def _render_health_bar_chart(df, key_prefix=""):
    """Render health check bar chart using Plotly."""
    health_counts = df['HEALTH_CHECK'].value_counts().reset_index()
    health_counts.columns = ['STATUS', 'COUNT']

    health_counts = health_counts.sort_values('COUNT', ascending=True)

    colors = []
    for status in health_counts['STATUS']:
        if '✅' in status:
            colors.append('#2ca02c')
        else:
            colors.append('#d62728')

    fig = go.Figure(data=[
        go.Bar(
            y=health_counts['STATUS'],
            x=health_counts['COUNT'],
            orientation='h',
            marker_color=colors,
            text=[f"{int(val)}" for val in health_counts['COUNT']],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Number of Tables',
        yaxis_title='Health Status',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_health_pie_chart(df, key_prefix=""):
    """Render health check pie chart using ECharts."""
    health_counts = df['HEALTH_CHECK'].value_counts()
    chart_data = [
        {"value": int(count), "name": f"{status} ({count})"}
        for status, count in health_counts.items()
    ]

    colors = []
    for status in health_counts.index:
        if '✅' in status:
            colors.append('#2ca02c')
        elif 'High Variance' in status:
            colors.append('#d62728')
        else:
            colors.append('#ff7f0e')

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 12,
            "textStyle": {"fontSize": 10}
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
        "color": colors,
        "series": [{
            "name": "Health",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_health_donut_chart(df, key_prefix=""):
    """Render health check donut chart using ECharts."""
    health_counts = df['HEALTH_CHECK'].value_counts()
    chart_data = [
        {"value": int(count), "name": f"{status} ({count})"}
        for status, count in health_counts.items()
    ]

    colors = []
    for status in health_counts.index:
        if '✅' in status:
            colors.append('#2ca02c')
        elif 'High Variance' in status:
            colors.append('#d62728')
        else:
            colors.append('#ff7f0e')

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 12,
            "textStyle": {"fontSize": 10}
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
        "color": colors,
        "series": [{
            "name": "Health",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_health_rose_chart(df, key_prefix=""):
    """Render health check rose chart using ECharts."""
    health_counts = df['HEALTH_CHECK'].value_counts()
    chart_data = [
        {"value": int(count), "name": status}
        for status, count in health_counts.items()
    ]

    colors = []
    for status in health_counts.index:
        if '✅' in status:
            colors.append('#2ca02c')
        elif 'High Variance' in status:
            colors.append('#d62728')
        else:
            colors.append('#ff7f0e')

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 12,
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} tables ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": colors,
        "series": [{
            "name": "Health",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")

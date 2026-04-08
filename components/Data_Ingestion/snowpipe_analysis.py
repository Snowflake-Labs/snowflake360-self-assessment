import streamlit as st
import pandas as pd
import plotly.express as px
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


def comp_snowpipe_analysis(entry_actions=None):
    """
    Snowpipe Analysis (Cost vs. Volume) Component

    Analyzes Snowpipe usage with cost vs. volume comparison and overhead analysis.
    """
    if not hasattr(st.session_state, 'session') or st.session_state.session is None:
        st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;No active Snowflake session. Please connect to view Snowpipe metrics.'
                            '</div>', unsafe_allow_html=True)
        return

    try:
        st.markdown("### Snowpipe Analysis (Cost vs. Volume)")

        with st.expander("Snowpipe Efficiency Analysis", expanded=True):
            st.markdown("Snowpipe efficiency analysis showing file volume, data loaded, credit consumption, and cost per GB to identify inefficient pipes with high overhead.")

            efficiency_query = """
            WITH pipe_costs AS (
                SELECT
                    pipe_name,
                    SUM(credits_used) AS credits_30d
                FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
                WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                GROUP BY 1
            ),
            pipe_volume AS (
                SELECT
                    pipe_name,
                    COUNT(*) AS files_loaded,
                    SUM(file_size) / POW(1024, 3) AS gb_loaded,
                    AVG(file_size) / POW(1024, 2) AS avg_file_mb
                FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
                WHERE pipe_name IS NOT NULL
                  AND last_load_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
                GROUP BY 1
            )
            SELECT
                v.pipe_name,
                v.files_loaded AS "Files (30d)",
                ROUND(v.gb_loaded, 2) AS "GB Ingested",
                ROUND(v.avg_file_mb, 2) AS "Avg File (MB)",
                ROUND(c.credits_30d, 2) AS "Credits Used (30d)",
                ROUND(c.credits_30d / NULLIF(v.gb_loaded, 0), 2) AS "Credits per GB"

            FROM pipe_volume v
            LEFT JOIN pipe_costs c ON v.pipe_name = c.pipe_name
            ORDER BY c.credits_30d DESC
            """

            try:
                efficiency_df = _cached_sql("ig_pipe_efficiency", efficiency_query)

                if len(efficiency_df) > 0:
                    st.dataframe(
                        efficiency_df,
                        use_container_width=True
                    )

                    st.markdown("---")
                    _render_efficiency_charts(efficiency_df)
                else:
                    st.info("No Snowpipe efficiency data available for the last 30 days.")

            except Exception as query_error:
                st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing Snowpipe efficiency query: {str(query_error)}'
                            f'</div>', unsafe_allow_html=True)

        with st.expander("Top Credit Consumers & Overhead Analysis", expanded=True):
            st.markdown("Top 10 Snowpipe credit consumers with overhead analysis flagging pipes burning credits without loading data (spinning) or with high listing costs.")

            snowpipe_query = """
            SELECT
                pipe_name,
                SUM(credits_used) AS credits_burned,
                SUM(bytes_inserted) / POW(1024, 3) AS gb_loaded,

                CASE
                    WHEN SUM(bytes_inserted) = 0 THEN '🔴 100% Overhead (Spinning)'
                    WHEN (SUM(credits_used) / NULLIF(SUM(bytes_inserted),0)) > 0.1 THEN '🟡 High Overhead'
                    ELSE '🟢 Efficient'
                END AS status

            FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY ALL
            ORDER BY credits_burned DESC
            LIMIT 10
            """

            try:
                snowpipe_df = _cached_sql("ig_snowpipe_detail", snowpipe_query)

                if len(snowpipe_df) > 0:
                    st.dataframe(
                        snowpipe_df,
                        use_container_width=True
                    )

                    st.markdown("---")
                    _render_snowpipe_charts(snowpipe_df)
                else:
                    st.info("No Snowpipe data available for the last 30 days.")

            except Exception as query_error:
                st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing Snowpipe query: {str(query_error)}'
                            f'</div>', unsafe_allow_html=True)

        with st.expander("Ingestion Credit Consumption & Cost Projections", expanded=True):
            st.markdown("Data ingestion credit consumption comparison between Snowpipe (file-based) and Snowpipe Streaming with projected costs for 3, 6, and 12 months based on last 30 days.")

            cost_projection_query = """
            WITH costs AS (
                SELECT 'Snowpipe (File)' AS type, SUM(credits_used) AS total_credits
                FROM SNOWFLAKE.ACCOUNT_USAGE.PIPE_USAGE_HISTORY
                WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())

                UNION ALL

                SELECT 'Snowpipe Streaming' AS type, SUM(CREDITS_USED_COMPUTE + CREDITS_USED_CLOUD_SERVICES)
                FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
                WHERE service_type = 'SNOWPIPE_STREAMING'
                  AND usage_date >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            )
            SELECT
                type AS ingest_method,
                ROUND(total_credits, 1) AS last_30_days,
                ROUND(total_credits * 3, 0) AS est_3_months,
                ROUND(total_credits * 6, 0) AS est_6_months,
                ROUND(total_credits * 12, 0) AS est_12_months
            FROM costs
            """

            try:
                cost_df = _cached_sql("ig_pipe_cost_projection", cost_projection_query)

                if len(cost_df) > 0:
                    st.dataframe(
                        cost_df,
                        use_container_width=True
                    )

                    st.markdown("---")
                    _render_cost_projection_charts(cost_df)
                else:
                    st.info("No ingestion cost data available for the last 30 days.")

            except Exception as query_error:
                st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing cost projection query: {str(query_error)}'
                            f'</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_efficiency_charts(efficiency_df):
    """Render 4 charts for Snowpipe efficiency analysis (2 per row)."""

    chart_col1, chart_col2 = st.columns([1, 1])

    with chart_col1.container():
        st.markdown("##### Credits Used by Pipe (30d)")
        _render_eff_credits_chart(efficiency_df, key_prefix="eff_credits_")

    with chart_col2.container():
        st.markdown("##### Files Loaded by Pipe (30d)")
        _render_eff_files_chart(efficiency_df, key_prefix="eff_files_")

    chart_col3, chart_col4 = st.columns([1, 1])

    with chart_col3.container():
        st.markdown("##### GB Ingested by Pipe (30d)")
        _render_eff_gb_chart(efficiency_df, key_prefix="eff_gb_")

    with chart_col4.container():
        st.markdown("##### Cost Efficiency: Credits per GB")
        _render_eff_cost_chart(efficiency_df, key_prefix="eff_cost_")


def _render_eff_credits_chart(df, key_prefix=""):
    """Render Credits Used chart with chart type selector."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    chart_df = df[df['Credits Used (30d)'].notna()].head(10).copy()

    if len(chart_df) == 0:
        st.info("No credit data available for visualization.")
        return

    if chart_type == "Bar Chart":
        plot_df = chart_df.sort_values('Credits Used (30d)', ascending=True)
        fig = go.Figure(data=[
            go.Bar(
                y=plot_df['PIPE_NAME'],
                x=plot_df['Credits Used (30d)'],
                orientation='h',
                marker_color='#29B5E8',
                text=[f"{val:.2f}" for val in plot_df['Credits Used (30d)']],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{y}</b><br>Credits: %{x:.2f}<extra></extra>'
            )
        ])
        fig.update_layout(height=400, xaxis_title='Credits Used (30d)', yaxis_title='Pipe Name', showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": float(row['Credits Used (30d)']), "name": f"{row['PIPE_NAME'][:25]} ({row['Credits Used (30d)']:.2f})"} for _, row in chart_df.iterrows() if pd.notna(row['Credits Used (30d)'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Credits", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": float(row['Credits Used (30d)']), "name": f"{row['PIPE_NAME'][:25]} ({row['Credits Used (30d)']:.2f})"} for _, row in chart_df.iterrows() if pd.notna(row['Credits Used (30d)'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Credits", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": float(row['Credits Used (30d)']), "name": f"{row['PIPE_NAME'][:25]} ({row['Credits Used (30d)']:.2f})"} for _, row in chart_df.iterrows() if pd.notna(row['Credits Used (30d)'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Credits", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_eff_files_chart(df, key_prefix=""):
    """Render Files Loaded chart with chart type selector."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    chart_df = df[df['Files (30d)'].notna()].head(10).copy()

    if len(chart_df) == 0:
        st.info("No files data available for visualization.")
        return

    if chart_type == "Bar Chart":
        plot_df = chart_df.sort_values('Files (30d)', ascending=True)
        fig = go.Figure(data=[
            go.Bar(
                y=plot_df['PIPE_NAME'],
                x=plot_df['Files (30d)'],
                orientation='h',
                marker_color='#0077B6',
                text=[f"{int(val):,}" for val in plot_df['Files (30d)']],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{y}</b><br>Files: %{x:,}<extra></extra>'
            )
        ])
        fig.update_layout(height=400, xaxis_title='Files Loaded (30d)', yaxis_title='Pipe Name', showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": int(row['Files (30d)']), "name": f"{row['PIPE_NAME'][:25]} ({int(row['Files (30d)']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['Files (30d)'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Files", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": int(row['Files (30d)']), "name": f"{row['PIPE_NAME'][:25]} ({int(row['Files (30d)']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['Files (30d)'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Files", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": int(row['Files (30d)']), "name": f"{row['PIPE_NAME'][:25]} ({int(row['Files (30d)']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['Files (30d)'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Files", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_eff_gb_chart(df, key_prefix=""):
    """Render GB Ingested chart with chart type selector."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    chart_df = df[df['GB Ingested'].notna()].head(10).copy()

    if len(chart_df) == 0:
        st.info("No GB ingested data available for visualization.")
        return

    if chart_type == "Bar Chart":
        plot_df = chart_df.sort_values('GB Ingested', ascending=True)
        fig = go.Figure(data=[
            go.Bar(
                y=plot_df['PIPE_NAME'],
                x=plot_df['GB Ingested'],
                orientation='h',
                marker_color='#E8A229',
                text=[f"{val:.2f} GB" for val in plot_df['GB Ingested']],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{y}</b><br>GB Ingested: %{x:.2f}<extra></extra>'
            )
        ])
        fig.update_layout(height=400, xaxis_title='GB Ingested (30d)', yaxis_title='Pipe Name', showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": float(row['GB Ingested']), "name": f"{row['PIPE_NAME'][:25]} ({row['GB Ingested']:.2f} GB)"} for _, row in chart_df.iterrows() if pd.notna(row['GB Ingested']) and row['GB Ingested'] > 0]
        if not chart_data:
            st.info("No positive GB ingested data for pie chart.")
            return
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "GB Ingested", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": float(row['GB Ingested']), "name": f"{row['PIPE_NAME'][:25]} ({row['GB Ingested']:.2f} GB)"} for _, row in chart_df.iterrows() if pd.notna(row['GB Ingested']) and row['GB Ingested'] > 0]
        if not chart_data:
            st.info("No positive GB ingested data for donut chart.")
            return
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "GB Ingested", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": float(row['GB Ingested']), "name": f"{row['PIPE_NAME'][:25]} ({row['GB Ingested']:.2f} GB)"} for _, row in chart_df.iterrows() if pd.notna(row['GB Ingested']) and row['GB Ingested'] > 0]
        if not chart_data:
            st.info("No positive GB ingested data for rose chart.")
            return
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "GB Ingested", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_eff_cost_chart(df, key_prefix=""):
    """Render Credits per GB (Cost Efficiency) chart with chart type selector."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    chart_df = df[df['Credits per GB'].notna()].head(10).copy()

    if len(chart_df) == 0:
        st.info("No cost efficiency data available for visualization.")
        return

    if chart_type == "Bar Chart":
        plot_df = chart_df.sort_values('Credits per GB', ascending=True)
        colors = []
        for val in plot_df['Credits per GB']:
            if val > 1:
                colors.append('#E74C3C')
            elif val > 0.5:
                colors.append('#E8A229')
            else:
                colors.append('#0077B6')
        fig = go.Figure(data=[
            go.Bar(
                y=plot_df['PIPE_NAME'],
                x=plot_df['Credits per GB'],
                orientation='h',
                marker_color=colors,
                text=[f"{val:.2f}" for val in plot_df['Credits per GB']],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{y}</b><br>Credits/GB: %{x:.2f}<extra></extra>'
            )
        ])
        fig.update_layout(height=400, xaxis_title='Credits per GB', yaxis_title='Pipe Name', showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
        st.markdown('<div style="font-size: 11px; color: #666666;"><span style="color: #0077B6;">●</span> Efficient (&lt;0.5) | <span style="color: #E8A229;">●</span> Medium (0.5-1) | <span style="color: #E74C3C;">●</span> Inefficient (&gt;1)</div>', unsafe_allow_html=True)
    elif chart_type == "Pie Chart":
        chart_data = [{"value": float(row['Credits per GB']), "name": f"{row['PIPE_NAME'][:25]} ({row['Credits per GB']:.2f})"} for _, row in chart_df.iterrows() if pd.notna(row['Credits per GB'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Credits/GB", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": float(row['Credits per GB']), "name": f"{row['PIPE_NAME'][:25]} ({row['Credits per GB']:.2f})"} for _, row in chart_df.iterrows() if pd.notna(row['Credits per GB'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Credits/GB", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": float(row['Credits per GB']), "name": f"{row['PIPE_NAME'][:25]} ({row['Credits per GB']:.2f})"} for _, row in chart_df.iterrows() if pd.notna(row['Credits per GB'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Credits/GB", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_snowpipe_charts(snowpipe_df):
    """Render 4 charts for Snowpipe overhead analysis (2 per row)."""

    chart_col1, chart_col2 = st.columns([1, 1])

    with chart_col1.container():
        st.markdown("##### Credits Burned by Pipe (30d)")
        _render_credits_chart(snowpipe_df, key_prefix="credits_")

    with chart_col2.container():
        st.markdown("##### GB Loaded by Pipe (30d)")
        _render_gb_loaded_chart(snowpipe_df, key_prefix="gb_")

    chart_col3, chart_col4 = st.columns([1, 1])

    with chart_col3.container():
        st.markdown("##### Overhead Status Distribution")
        _render_status_chart(snowpipe_df, key_prefix="status_")

    with chart_col4.container():
        st.markdown("##### Credits vs GB Loaded Comparison")
        _render_comparison_chart(snowpipe_df, key_prefix="compare_")


def _render_credits_chart(df, key_prefix=""):
    """Render Credits Burned chart with chart type selector."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    chart_df = df[df['CREDITS_BURNED'].notna()].copy()

    if len(chart_df) == 0:
        st.info("No credit data available for visualization.")
        return

    if chart_type == "Bar Chart":
        plot_df = chart_df.head(10).sort_values('CREDITS_BURNED', ascending=True)
        fig = go.Figure(data=[
            go.Bar(
                y=plot_df['PIPE_NAME'],
                x=plot_df['CREDITS_BURNED'],
                orientation='h',
                marker_color='#29B5E8',
                text=[f"{val:.2f}" for val in plot_df['CREDITS_BURNED']],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{y}</b><br>Credits: %{x:.2f}<extra></extra>'
            )
        ])
        fig.update_layout(height=400, xaxis_title='Credits Burned (30d)', yaxis_title='Pipe Name', showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": float(row['CREDITS_BURNED']), "name": f"{row['PIPE_NAME'][:25]} ({row['CREDITS_BURNED']:.2f})"} for _, row in chart_df.iterrows() if pd.notna(row['CREDITS_BURNED'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Credits", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": float(row['CREDITS_BURNED']), "name": f"{row['PIPE_NAME'][:25]} ({row['CREDITS_BURNED']:.2f})"} for _, row in chart_df.iterrows() if pd.notna(row['CREDITS_BURNED'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Credits", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": float(row['CREDITS_BURNED']), "name": f"{row['PIPE_NAME'][:25]} ({row['CREDITS_BURNED']:.2f})"} for _, row in chart_df.iterrows() if pd.notna(row['CREDITS_BURNED'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Credits", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_gb_loaded_chart(df, key_prefix=""):
    """Render GB Loaded chart with chart type selector."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    chart_df = df[df['GB_LOADED'].notna()].copy()

    if len(chart_df) == 0:
        st.info("No GB loaded data available for visualization.")
        return

    if chart_type == "Bar Chart":
        plot_df = chart_df.head(10).sort_values('GB_LOADED', ascending=True)
        fig = go.Figure(data=[
            go.Bar(
                y=plot_df['PIPE_NAME'],
                x=plot_df['GB_LOADED'],
                orientation='h',
                marker_color='#0077B6',
                text=[f"{val:.2f} GB" for val in plot_df['GB_LOADED']],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{y}</b><br>GB Loaded: %{x:.2f}<extra></extra>'
            )
        ])
        fig.update_layout(height=400, xaxis_title='GB Loaded (30d)', yaxis_title='Pipe Name', showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": float(row['GB_LOADED']), "name": f"{row['PIPE_NAME'][:25]} ({row['GB_LOADED']:.2f} GB)"} for _, row in chart_df.iterrows() if pd.notna(row['GB_LOADED']) and row['GB_LOADED'] > 0]
        if not chart_data:
            st.info("No positive GB loaded data for pie chart.")
            return
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "GB Loaded", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": float(row['GB_LOADED']), "name": f"{row['PIPE_NAME'][:25]} ({row['GB_LOADED']:.2f} GB)"} for _, row in chart_df.iterrows() if pd.notna(row['GB_LOADED']) and row['GB_LOADED'] > 0]
        if not chart_data:
            st.info("No positive GB loaded data for donut chart.")
            return
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "GB Loaded", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": float(row['GB_LOADED']), "name": f"{row['PIPE_NAME'][:25]} ({row['GB_LOADED']:.2f} GB)"} for _, row in chart_df.iterrows() if pd.notna(row['GB_LOADED']) and row['GB_LOADED'] > 0]
        if not chart_data:
            st.info("No positive GB loaded data for rose chart.")
            return
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "GB Loaded", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_status_chart(df, key_prefix=""):
    """Render Overhead Status Distribution chart with chart type selector."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    status_counts = df['STATUS'].value_counts().reset_index()
    status_counts.columns = ['STATUS', 'COUNT']

    if len(status_counts) == 0:
        st.info("No status data available for visualization.")
        return

    if chart_type == "Bar Chart":
        plot_df = status_counts.sort_values('COUNT', ascending=True)
        colors = []
        for status in plot_df['STATUS']:
            if '🔴' in status:
                colors.append('#E74C3C')
            elif '🟡' in status:
                colors.append('#E8A229')
            else:
                colors.append('#0077B6')
        fig = go.Figure(data=[
            go.Bar(
                y=plot_df['STATUS'],
                x=plot_df['COUNT'],
                orientation='h',
                marker_color=colors,
                text=[f"{int(val)}" for val in plot_df['COUNT']],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>'
            )
        ])
        fig.update_layout(height=400, xaxis_title='Number of Pipes', yaxis_title='Status', showlegend=False, margin=dict(t=20, b=50, l=200, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": int(row['COUNT']), "name": row['STATUS']} for _, row in status_counts.iterrows()]
        colors = []
        for _, row in status_counts.iterrows():
            if '🔴' in row['STATUS']:
                colors.append('#E74C3C')
            elif '🟡' in row['STATUS']:
                colors.append('#E8A229')
            else:
                colors.append('#0077B6')
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": colors, "series": [{"name": "Status", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": int(row['COUNT']), "name": row['STATUS']} for _, row in status_counts.iterrows()]
        colors = []
        for _, row in status_counts.iterrows():
            if '🔴' in row['STATUS']:
                colors.append('#E74C3C')
            elif '🟡' in row['STATUS']:
                colors.append('#E8A229')
            else:
                colors.append('#0077B6')
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": colors, "series": [{"name": "Status", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": int(row['COUNT']), "name": row['STATUS']} for _, row in status_counts.iterrows()]
        colors = []
        for _, row in status_counts.iterrows():
            if '🔴' in row['STATUS']:
                colors.append('#E74C3C')
            elif '🟡' in row['STATUS']:
                colors.append('#E8A229')
            else:
                colors.append('#0077B6')
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 9}}, "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": colors, "series": [{"name": "Status", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_comparison_chart(df, key_prefix=""):
    """Render Credits vs GB Loaded Comparison chart with chart type selector."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    chart_df = df.copy()

    if len(chart_df) == 0:
        st.info("No data available for comparison visualization.")
        return

    if chart_type == "Bar Chart":
        plot_df = chart_df.head(10).sort_values('CREDITS_BURNED', ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=plot_df['PIPE_NAME'], x=plot_df['CREDITS_BURNED'], name='Credits Burned', orientation='h', marker_color='#29B5E8', text=[f"{val:.2f}" for val in plot_df['CREDITS_BURNED']], textposition='outside', textfont=dict(size=9)))
        fig.add_trace(go.Bar(y=plot_df['PIPE_NAME'], x=plot_df['GB_LOADED'], name='GB Loaded', orientation='h', marker_color='#0077B6', text=[f"{val:.2f}" for val in plot_df['GB_LOADED']], textposition='outside', textfont=dict(size=9)))
        fig.update_layout(height=400, barmode='group', xaxis_title='Value', yaxis_title='Pipe Name', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(t=40, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        plot_df = chart_df.head(10).copy()
        plot_df['EFFICIENCY_RATIO'] = plot_df['CREDITS_BURNED'] / plot_df['GB_LOADED'].replace(0, float('nan'))
        plot_df = plot_df.dropna(subset=['EFFICIENCY_RATIO']).sort_values('EFFICIENCY_RATIO', ascending=True)
        if len(plot_df) == 0:
            st.info("No efficiency ratio data available.")
            return
        colors = []
        for ratio in plot_df['EFFICIENCY_RATIO']:
            if ratio > 1:
                colors.append('#E74C3C')
            elif ratio > 0.5:
                colors.append('#E8A229')
            else:
                colors.append('#0077B6')
        fig = go.Figure(data=[go.Bar(y=plot_df['PIPE_NAME'], x=plot_df['EFFICIENCY_RATIO'], orientation='h', marker_color=colors, text=[f"{val:.2f}" for val in plot_df['EFFICIENCY_RATIO']], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{y}</b><br>Credits/GB: %{x:.2f}<extra></extra>')])
        fig.update_layout(height=400, xaxis_title='Credits per GB (Efficiency Ratio)', yaxis_title='Pipe Name', showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}efficiency")
    elif chart_type == "Pie - Donut":
        plot_df = chart_df.head(10).sort_values('CREDITS_BURNED', ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=plot_df['PIPE_NAME'], x=plot_df['CREDITS_BURNED'], name='Credits Burned', orientation='h', marker_color='#29B5E8'))
        fig.add_trace(go.Bar(y=plot_df['PIPE_NAME'], x=plot_df['GB_LOADED'], name='GB Loaded', orientation='h', marker_color='#0077B6'))
        fig.update_layout(height=400, barmode='stack', xaxis_title='Combined Value', yaxis_title='Pipe Name', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(t=40, b=50, l=120, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}stacked")
    else:
        plot_df = chart_df.copy()
        colors = []
        for status in plot_df['STATUS']:
            if '🔴' in status:
                colors.append('#E74C3C')
            elif '🟡' in status:
                colors.append('#E8A229')
            else:
                colors.append('#0077B6')
        fig = go.Figure(data=[go.Scatter(x=plot_df['GB_LOADED'], y=plot_df['CREDITS_BURNED'], mode='markers+text', marker=dict(size=15, color=colors, line=dict(width=1, color='#11567F')), text=plot_df['PIPE_NAME'].apply(lambda x: x[:15] + '...' if len(str(x)) > 15 else x), textposition='top center', textfont=dict(size=8), hovertemplate='<b>%{text}</b><br>GB Loaded: %{x:.2f}<br>Credits: %{y:.2f}<extra></extra>')])
        fig.update_layout(height=400, xaxis_title='GB Loaded (30d)', yaxis_title='Credits Burned (30d)', showlegend=False, margin=dict(t=20, b=50, l=50, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}scatter")


def _render_cost_projection_charts(cost_df):
    """Render 4 charts for cost projections (2 per row)."""

    chart_col1, chart_col2 = st.columns([1, 1])

    with chart_col1.container():
        st.markdown("##### Credit Consumption: Last 30 Days")
        _render_cost_30days_chart(cost_df, key_prefix="cost_30d_")

    with chart_col2.container():
        st.markdown("##### Projected Credits: 3 Months")
        _render_cost_3month_chart(cost_df, key_prefix="cost_3m_")

    chart_col3, chart_col4 = st.columns([1, 1])

    with chart_col3.container():
        st.markdown("##### Projected Credits: 6 Months")
        _render_cost_6month_chart(cost_df, key_prefix="cost_6m_")

    with chart_col4.container():
        st.markdown("##### Projected Credits: 12 Months")
        _render_cost_12month_chart(cost_df, key_prefix="cost_12m_")


def _render_cost_30days_chart(df, key_prefix=""):
    """Render Last 30 Days chart with chart type selector."""
    chart_type = st.selectbox("Change Chart Type", ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"], index=0, key=f"{key_prefix}chart_type")
    chart_df = df[df['LAST_30_DAYS'].notna()].copy()
    if len(chart_df) == 0:
        st.info("No cost data available for visualization.")
        return
    if chart_type == "Bar Chart":
        plot_df = chart_df.sort_values('LAST_30_DAYS', ascending=True)
        colors = ['#29B5E8', '#E8A229'][:len(plot_df)]
        fig = go.Figure(data=[go.Bar(y=plot_df['INGEST_METHOD'], x=plot_df['LAST_30_DAYS'], orientation='h', marker_color=colors, text=[f"{val:.1f}" for val in plot_df['LAST_30_DAYS']], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{y}</b><br>Credits: %{x:.1f}<extra></extra>')])
        fig.update_layout(height=400, xaxis_title='Credits (Last 30 Days)', yaxis_title='Ingestion Method', showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": float(row['LAST_30_DAYS']), "name": f"{row['INGEST_METHOD']} ({row['LAST_30_DAYS']:.1f})"} for _, row in chart_df.iterrows() if pd.notna(row['LAST_30_DAYS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#29B5E8", "#E8A229"], "series": [{"name": "Credits", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": float(row['LAST_30_DAYS']), "name": f"{row['INGEST_METHOD']} ({row['LAST_30_DAYS']:.1f})"} for _, row in chart_df.iterrows() if pd.notna(row['LAST_30_DAYS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#29B5E8", "#E8A229"], "series": [{"name": "Credits", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": float(row['LAST_30_DAYS']), "name": f"{row['INGEST_METHOD']} ({row['LAST_30_DAYS']:.1f})"} for _, row in chart_df.iterrows() if pd.notna(row['LAST_30_DAYS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#29B5E8", "#E8A229"], "series": [{"name": "Credits", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_cost_3month_chart(df, key_prefix=""):
    """Render 3-Month projection chart with chart type selector."""
    chart_type = st.selectbox("Change Chart Type", ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"], index=0, key=f"{key_prefix}chart_type")
    chart_df = df[df['EST_3_MONTHS'].notna()].copy()
    if len(chart_df) == 0:
        st.info("No projection data available.")
        return
    if chart_type == "Bar Chart":
        plot_df = chart_df.sort_values('EST_3_MONTHS', ascending=True)
        colors = ['#0077B6', '#E74C3C'][:len(plot_df)]
        fig = go.Figure(data=[go.Bar(y=plot_df['INGEST_METHOD'], x=plot_df['EST_3_MONTHS'], orientation='h', marker_color=colors, text=[f"{int(val):,}" for val in plot_df['EST_3_MONTHS']], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{y}</b><br>Projected Credits: %{x:,.0f}<extra></extra>')])
        fig.update_layout(height=400, xaxis_title='Projected Credits (3 Months)', yaxis_title='Ingestion Method', showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": float(row['EST_3_MONTHS']), "name": f"{row['INGEST_METHOD']} ({int(row['EST_3_MONTHS']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['EST_3_MONTHS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#0077B6", "#E74C3C"], "series": [{"name": "Credits", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": float(row['EST_3_MONTHS']), "name": f"{row['INGEST_METHOD']} ({int(row['EST_3_MONTHS']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['EST_3_MONTHS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#0077B6", "#E74C3C"], "series": [{"name": "Credits", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": float(row['EST_3_MONTHS']), "name": f"{row['INGEST_METHOD']} ({int(row['EST_3_MONTHS']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['EST_3_MONTHS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#0077B6", "#E74C3C"], "series": [{"name": "Credits", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_cost_6month_chart(df, key_prefix=""):
    """Render 6-Month projection chart with chart type selector."""
    chart_type = st.selectbox("Change Chart Type", ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"], index=0, key=f"{key_prefix}chart_type")
    chart_df = df[df['EST_6_MONTHS'].notna()].copy()
    if len(chart_df) == 0:
        st.info("No projection data available.")
        return
    if chart_type == "Bar Chart":
        plot_df = chart_df.sort_values('EST_6_MONTHS', ascending=True)
        colors = ['#0077B6', '#11567F'][:len(plot_df)]
        fig = go.Figure(data=[go.Bar(y=plot_df['INGEST_METHOD'], x=plot_df['EST_6_MONTHS'], orientation='h', marker_color=colors, text=[f"{int(val):,}" for val in plot_df['EST_6_MONTHS']], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{y}</b><br>Projected Credits: %{x:,.0f}<extra></extra>')])
        fig.update_layout(height=400, xaxis_title='Projected Credits (6 Months)', yaxis_title='Ingestion Method', showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": float(row['EST_6_MONTHS']), "name": f"{row['INGEST_METHOD']} ({int(row['EST_6_MONTHS']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['EST_6_MONTHS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#0077B6", "#11567F"], "series": [{"name": "Credits", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": float(row['EST_6_MONTHS']), "name": f"{row['INGEST_METHOD']} ({int(row['EST_6_MONTHS']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['EST_6_MONTHS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#0077B6", "#11567F"], "series": [{"name": "Credits", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": float(row['EST_6_MONTHS']), "name": f"{row['INGEST_METHOD']} ({int(row['EST_6_MONTHS']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['EST_6_MONTHS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#0077B6", "#11567F"], "series": [{"name": "Credits", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_cost_12month_chart(df, key_prefix=""):
    """Render 12-Month projection chart with chart type selector."""
    chart_type = st.selectbox("Change Chart Type", ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"], index=0, key=f"{key_prefix}chart_type")
    chart_df = df[df['EST_12_MONTHS'].notna()].copy()
    if len(chart_df) == 0:
        st.info("No projection data available.")
        return
    if chart_type == "Bar Chart":
        plot_df = chart_df.sort_values('EST_12_MONTHS', ascending=True)
        colors = ['#75C2D8', '#48CAE4'][:len(plot_df)]
        fig = go.Figure(data=[go.Bar(y=plot_df['INGEST_METHOD'], x=plot_df['EST_12_MONTHS'], orientation='h', marker_color=colors, text=[f"{int(val):,}" for val in plot_df['EST_12_MONTHS']], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{y}</b><br>Projected Credits: %{x:,.0f}<extra></extra>')])
        fig.update_layout(height=400, xaxis_title='Projected Credits (12 Months)', yaxis_title='Ingestion Method', showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
    elif chart_type == "Pie Chart":
        chart_data = [{"value": float(row['EST_12_MONTHS']), "name": f"{row['INGEST_METHOD']} ({int(row['EST_12_MONTHS']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['EST_12_MONTHS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#75C2D8", "#48CAE4"], "series": [{"name": "Credits", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}pie")
    elif chart_type == "Pie - Donut":
        chart_data = [{"value": float(row['EST_12_MONTHS']), "name": f"{row['INGEST_METHOD']} ({int(row['EST_12_MONTHS']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['EST_12_MONTHS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#75C2D8", "#48CAE4"], "series": [{"name": "Credits", "type": "pie", "radius": ["40%", "65%"], "center": ["50%", "40%"], "data": chart_data, "itemStyle": {"borderRadius": 8}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}donut")
    else:
        chart_data = [{"value": float(row['EST_12_MONTHS']), "name": f"{row['INGEST_METHOD']} ({int(row['EST_12_MONTHS']):,})"} for _, row in chart_df.iterrows() if pd.notna(row['EST_12_MONTHS'])]
        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 5, "textStyle": {"fontSize": 10}}, "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "color": ["#75C2D8", "#48CAE4"], "series": [{"name": "Credits", "type": "pie", "radius": ["20%", "65%"], "center": ["50%", "40%"], "roseType": "area", "data": chart_data, "itemStyle": {"borderRadius": 5}}]}
        st_echarts(options=option, height="400px", key=f"{key_prefix}rose")

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


def comp_workload_shape(entry_actions=None):
    """
    Workload Shape (Updates, MVs, RAPs) Component

    Analyzes DML workload patterns including UPDATE, INSERT, and DELETE queries
    with micro-update detection for batching optimization.
    """
    try:
        # Get session and context
        try:
            from snowflake.snowpark.context import get_active_session
            session = get_active_session()
        except Exception as e:
            # st.error(f"Unable to get Snowflake session: {str(e)}")
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Unable to get Snowflake session: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if not session:
            # st.warning("⚠️ Snowflake session not available.")
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;Snowflake session not available.'
                            '</div>', unsafe_allow_html=True)
            return

        # DML Pattern Analysis Expander
        with st.expander("DML Pattern Analysis (UPDATE/INSERT/DELETE)", expanded=True):
            # Introduction text (no CSS styling as requested)
            st.write("DML pattern analysis identifying frequently executed UPDATE/INSERT/DELETE queries (>50 occurrences) with micro-update detection flagging fast queries executed over 100 times for batching optimization.")

            # Build and execute the query
            query = f"""
SELECT
    -- Normalize query to group repeated UPDATE statements
    REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?') AS query_pattern,
    COUNT(*) AS execution_count,
    AVG(execution_time) AS avg_duration_ms,
    CASE
        WHEN AVG(execution_time) < 500 AND COUNT(*) > 100 THEN '⚠️ Micro-Updates (Batch these!)'
        ELSE 'OK'
    END AS recommendation
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE query_type IN ('UPDATE', 'INSERT', 'DELETE')
  AND start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY ALL
HAVING count(*) > 50
ORDER BY 2 DESC
"""


            # Execute query
            try:
                df = _cached_sql("tf_workload_shape", query)
            except Exception as e:
                # st.error(f"Error executing query: {str(e)}")
                st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                            f'</div>', unsafe_allow_html=True)
                df = pd.DataFrame()

            if df.empty:
                st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;No DML pattern data found for the last 7 days with more than 50 executions.'
                            '</div>', unsafe_allow_html=True)
            else:
                # Rename columns for display
                df.columns = ['QUERY_PATTERN', 'EXECUTION_COUNT', 'AVG_DURATION_MS', 'RECOMMENDATION']

                # Round the average duration
                df['AVG_DURATION_MS'] = df['AVG_DURATION_MS'].round(2)


                # Create metric object for dialogs
                # Initialize or update metric object in session state


                # Display the dataframe
                st.dataframe(
                    df,
                )

                # Charts Section - 2 charts per row
                st.markdown("---")
                st.markdown("#### DML Pattern Analytics Charts")

                # Row 1: Two charts
                col1, col2 = st.columns(2)

                with col1.container():
                    st.markdown("##### Top Queries by Execution Count")
                    _render_execution_count_chart(df, key_prefix="exec_count_")

                with col2.container():
                    st.markdown("##### Average Duration by Query Pattern (ms)")
                    _render_avg_duration_chart(df, key_prefix="avg_dur_")

                # Row 2: Two charts
                col3, col4 = st.columns(2)

                with col3.container():
                    st.markdown("##### Recommendation Distribution")
                    _render_recommendation_chart(df, key_prefix="rec_dist_")

                with col4.container():
                    st.markdown("##### Execution Count vs Duration Comparison")
                    _render_count_vs_duration_chart(df, key_prefix="count_dur_")

        # RAP Slow Query Analysis Expander
        with st.expander("RAP Slow Query Analysis (Memoizable Candidates)", expanded=True):
            # Introduction text (no CSS styling as requested)
            st.write("Finds queries on tables with RAPs that are slow (Candidates for Memoizable).")

            # Build and execute the RAP query
            rap_query = f"""
SELECT
    pr.policy_name,
    pr.ref_entity_name AS protected_table,
    COUNT(DISTINCT q.query_id) AS slow_query_count,
    AVG(q.execution_time) AS avg_execution_ms
FROM SNOWFLAKE.ACCOUNT_USAGE.policy_references pr
JOIN SNOWFLAKE.ACCOUNT_USAGE.access_history ah
    ON ah.query_start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
    ON ah.query_id = q.query_id
    AND q.execution_time > 5000 -- Queries taking > 5 seconds
WHERE pr.policy_kind = 'ROW_ACCESS_POLICY'
GROUP BY 1, 2
ORDER BY 3 DESC
"""


            # Execute query
            try:
                rap_df = _cached_sql("tf_rap_query", rap_query)
            except Exception as e:
                st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing RAP query: {str(e)}'
                            f'</div>', unsafe_allow_html=True)
                rap_df = pd.DataFrame()

            if rap_df.empty:
                st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;No slow queries found on tables with Row Access Policies in the last 7 days.'
                            '</div>', unsafe_allow_html=True)
            else:
                # Rename columns for display
                rap_df.columns = ['POLICY_NAME', 'PROTECTED_TABLE', 'SLOW_QUERY_COUNT', 'AVG_EXECUTION_MS']

                # Round the average execution time
                rap_df['AVG_EXECUTION_MS'] = rap_df['AVG_EXECUTION_MS'].round(2)


                # Create metric object for dialogs
                # Initialize or update metric object in session state


                # Display the dataframe
                st.dataframe(
                    df,
                )

                # Charts Section - 2 charts per row
                st.markdown("---")
                st.markdown("#### RAP Slow Query Analytics Charts")

                # Row 1: Two charts
                rap_col1, rap_col2 = st.columns(2)

                with rap_col1.container():
                    st.markdown("##### Slow Query Count by Policy")
                    _render_rap_slow_query_count_chart(rap_df, key_prefix="rap_count_")

                with rap_col2.container():
                    st.markdown("##### Average Execution Time by Table (ms)")
                    _render_rap_avg_execution_chart(rap_df, key_prefix="rap_avg_")

                # Row 2: Two charts
                rap_col3, rap_col4 = st.columns(2)

                with rap_col3.container():
                    st.markdown("##### Slow Queries by Protected Table")
                    _render_rap_table_distribution_chart(rap_df, key_prefix="rap_table_")

                with rap_col4.container():
                    st.markdown("##### Total Slow Query Time by Policy (ms)")
                    _render_rap_total_time_chart(rap_df, key_prefix="rap_time_")

        # Materialized View Refresh Cost Analysis Expander
        with st.expander("Materialized View Refresh Cost Analysis", expanded=True):
            # Introduction text (no CSS styling as requested)
            st.write("Materialized view refresh cost analysis showing total and average credit consumption per view over last 7 days, ordered by total refresh cost.")

            # Build the MV refresh cost query
            mv_query = f"""
SELECT
    table_name AS mv_name,
    COUNT(*) AS refresh_count,
    SUM(credits_used) AS refresh_cost_credits,
    AVG(credits_used) AS avg_cost_per_refresh
FROM SNOWFLAKE.ACCOUNT_USAGE.materialized_view_refresh_history
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY 3 DESC
"""


            # Execute query
            try:
                mv_df = _cached_sql("tf_mv_refresh_cost", mv_query)
            except Exception as e:
                # st.error(f"Error executing MV refresh cost query: {str(e)}")
                st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing MV refresh cost query: {str(e)}'
                            f'</div>', unsafe_allow_html=True)
                mv_df = pd.DataFrame()

            if mv_df.empty:
                st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;No materialized view refresh data found for the last 7 days.'
                            '</div>', unsafe_allow_html=True)
            else:
                # Rename columns for display
                mv_df.columns = ['MV_NAME', 'REFRESH_COUNT', 'REFRESH_COST_CREDITS', 'AVG_COST_PER_REFRESH']

                # Round the decimal columns
                mv_df['REFRESH_COST_CREDITS'] = mv_df['REFRESH_COST_CREDITS'].round(4)
                mv_df['AVG_COST_PER_REFRESH'] = mv_df['AVG_COST_PER_REFRESH'].round(6)


                # Create metric object for dialogs
                # Initialize or update metric object in session state


                # Display the dataframe
                st.dataframe(
                    df,
                )

                # Charts Section - 2 charts per row
                st.markdown("---")
                st.markdown("#### MV Refresh Cost Analytics Charts")

                # Row 1: Two charts
                mv_col1, mv_col2 = st.columns(2)

                with mv_col1.container():
                    st.markdown("##### Total Refresh Cost by MV (Credits)")
                    _render_mv_total_cost_chart(mv_df, key_prefix="mv_cost_")

                with mv_col2.container():
                    st.markdown("##### Refresh Count by MV")
                    _render_mv_refresh_count_chart(mv_df, key_prefix="mv_count_")

                # Row 2: Two charts
                mv_col3, mv_col4 = st.columns(2)

                with mv_col3.container():
                    st.markdown("##### Average Cost Per Refresh (Credits)")
                    _render_mv_avg_cost_chart(mv_df, key_prefix="mv_avg_")

                with mv_col4.container():
                    st.markdown("##### Cost vs Refresh Frequency")
                    _render_mv_cost_vs_frequency_chart(mv_df, key_prefix="mv_freq_")

        # Performance Dashboard Expander
        with st.expander("Workload Performance Dashboard", expanded=True):
            # Introduction text (no CSS styling as requested)
            st.write("Performance dashboard aggregating micro-update counts, row access policy impact on slow queries, and materialized view refresh costs over last 7 days.")

            # Build the performance dashboard query
            perf_query = f"""
WITH micro_updates AS (
    -- A. AGGREGATE MICRO-UPDATES
    SELECT
        COUNT(*) AS total_executions,
        COUNT(DISTINCT REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?')) AS unique_patterns
    FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
    WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND query_type IN ('UPDATE', 'INSERT', 'DELETE')
      AND execution_time < 500 -- < 500ms
),
rap_impact AS (
    -- B. AGGREGATE RAP PERFORMANCE (Fixed Join Logic)
    -- Counts queries > 5s that touched a table protected by a Row Access Policy
    SELECT
        COUNT(DISTINCT q.query_id) AS slow_protected_queries,
        AVG(q.execution_time) / 1000 AS avg_duration_sec
    FROM SNOWFLAKE.ACCOUNT_USAGE.access_history ah
    JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
        ON ah.query_id = q.query_id
    -- Flatten accessed objects to match them against Policy References
    , LATERAL FLATTEN(ah.direct_objects_accessed) f
    JOIN SNOWFLAKE.ACCOUNT_USAGE.policy_references pr
        ON f.value:objectName::STRING = pr.ref_entity_name
    WHERE ah.query_start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND q.execution_time > 5000 -- Only slow queries
      AND pr.policy_kind = 'ROW_ACCESS_POLICY'
),
mv_churn AS (
    -- C. AGGREGATE MATERIALIZED VIEW COSTS
    SELECT
        COUNT(DISTINCT table_name) AS active_mvs,
        SUM(credits_used) AS total_maintenance_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.materialized_view_refresh_history
    WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
)

-- FINAL DASHBOARD OUTPUT
, AGGR AS (
SELECT
    'Micro-Updates (Short Modifies)' AS metric_category,
    'Total Executions (<500ms)' AS metric_name,
    total_executions::STRING AS value
FROM micro_updates

UNION ALL

SELECT
    'Micro-Updates (Short Modifies)',
    'Distinct Patterns Detected',
    unique_patterns::STRING
FROM micro_updates

UNION ALL

SELECT
    'Row Access Policies (Security)',
    'Slow Queries on Protected Tables (>5s)',
    slow_protected_queries::STRING
FROM rap_impact

UNION ALL

SELECT
    'Materialized Views',
    'Total Refresh Cost (Credits)',
    ROUND(total_maintenance_credits, 2)::STRING
FROM mv_churn

UNION ALL

SELECT
    'Materialized Views',
    'Active MVs Refreshed',
    active_mvs::STRING
FROM mv_churn)

SELECT
     A.*
     FROM AGGR A
"""


            # Execute query
            try:
                perf_df = _cached_sql("tf_perf_insights", perf_query)
            except Exception as e:
                st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing performance dashboard query: {str(e)}'
                            f'</div>', unsafe_allow_html=True)
                perf_df = pd.DataFrame()

            if perf_df.empty:
                st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;No performance dashboard data found for the last 7 days.'
                            '</div>', unsafe_allow_html=True)
            else:
                # Rename columns for display
                perf_df.columns = ['METRIC_CATEGORY', 'METRIC_NAME', 'VALUE']


                # Create metric object for dialogs
                # Initialize or update metric object in session state


                # Display the dataframe
                st.dataframe(
                    df,
                )

                # Charts Section - 2 charts per row
                st.markdown("---")
                st.markdown("#### Workload Performance Analytics Charts")

                # Row 1: Two charts
                perf_col1, perf_col2 = st.columns(2)

                with perf_col1.container():
                    st.markdown("##### Metrics by Category")
                    _render_perf_category_chart(perf_df, key_prefix="perf_cat_")

                with perf_col2.container():
                    st.markdown("##### Metric Values Distribution")
                    _render_perf_values_chart(perf_df, key_prefix="perf_val_")

                # Row 2: Two charts
                perf_col3, perf_col4 = st.columns(2)

                with perf_col3.container():
                    st.markdown("##### Category Breakdown")
                    _render_perf_breakdown_chart(perf_df, key_prefix="perf_break_")

                with perf_col4.container():
                    st.markdown("##### Metrics Summary")
                    _render_perf_summary_chart(perf_df, key_prefix="perf_sum_")

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ============================
# Chart Type Selector & Charts
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
    # Use top 10 for better visualization, sorted ascending for horizontal bar layout
    plot_df = df.head(10).sort_values('EXECUTION_COUNT', ascending=True)

    # Truncate query pattern for display (first 50 chars)
    plot_df = plot_df.copy()
    plot_df['DISPLAY_PATTERN'] = plot_df['QUERY_PATTERN'].apply(lambda x: x[:50] + '...' if len(str(x)) > 50 else x)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DISPLAY_PATTERN'],
            x=plot_df['EXECUTION_COUNT'],
            orientation='h',
            marker_color='#29B5E8',
            text=[f"{int(val):,}" for val in plot_df['EXECUTION_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Executions: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Execution Count',
        yaxis_title='Query Pattern',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_execution_count_pie_chart(df, key_prefix=""):
    """Render execution count pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['EXECUTION_COUNT']), "name": f"{str(row['QUERY_PATTERN'])[:30]}... ({int(row['EXECUTION_COUNT']):,})"}
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
            "name": "Executions",
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
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['EXECUTION_COUNT']), "name": f"{str(row['QUERY_PATTERN'])[:30]}... ({int(row['EXECUTION_COUNT']):,})"}
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
            "name": "Executions",
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
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['EXECUTION_COUNT']), "name": f"{str(row['QUERY_PATTERN'])[:30]}..."}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} executions ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Executions",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_avg_duration_chart(df, key_prefix=""):
    """Render average duration chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_avg_duration_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_avg_duration_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_avg_duration_donut_chart(df, key_prefix)
    else:
        _render_avg_duration_rose_chart(df, key_prefix)


def _render_avg_duration_bar_chart(df, key_prefix=""):
    """Render average duration bar chart using Plotly."""
    # Sort by avg duration ascending for horizontal bar layout
    plot_df = df.head(10).sort_values('AVG_DURATION_MS', ascending=True)

    # Truncate query pattern for display
    plot_df = plot_df.copy()
    plot_df['DISPLAY_PATTERN'] = plot_df['QUERY_PATTERN'].apply(lambda x: x[:50] + '...' if len(str(x)) > 50 else x)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DISPLAY_PATTERN'],
            x=plot_df['AVG_DURATION_MS'],
            orientation='h',
            marker_color='#E8A229',
            text=[f"{val:.1f} ms" for val in plot_df['AVG_DURATION_MS']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Avg Duration: %{x:.2f} ms<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Average Duration (ms)',
        yaxis_title='Query Pattern',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_avg_duration_pie_chart(df, key_prefix=""):
    """Render average duration pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_DURATION_MS']), "name": f"{str(row['QUERY_PATTERN'])[:30]}... ({row['AVG_DURATION_MS']:.1f} ms)"}
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
        "color": ["#E8A229", "#0077B6", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8", "#29B5E8"],
        "series": [{
            "name": "Duration",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_avg_duration_donut_chart(df, key_prefix=""):
    """Render average duration donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_DURATION_MS']), "name": f"{str(row['QUERY_PATTERN'])[:30]}... ({row['AVG_DURATION_MS']:.1f} ms)"}
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
        "color": ["#E8A229", "#0077B6", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8", "#29B5E8"],
        "series": [{
            "name": "Duration",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_avg_duration_rose_chart(df, key_prefix=""):
    """Render average duration rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_DURATION_MS']), "name": f"{str(row['QUERY_PATTERN'])[:30]}..."}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ms ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#E8A229", "#0077B6", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8", "#29B5E8"],
        "series": [{
            "name": "Duration",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_recommendation_chart(df, key_prefix=""):
    """Render recommendation distribution chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_recommendation_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_recommendation_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_recommendation_donut_chart(df, key_prefix)
    else:
        _render_recommendation_rose_chart(df, key_prefix)


def _render_recommendation_bar_chart(df, key_prefix=""):
    """Render recommendation bar chart using Plotly."""
    # Aggregate by recommendation
    rec_counts = df['RECOMMENDATION'].value_counts().reset_index()
    rec_counts.columns = ['RECOMMENDATION', 'COUNT']

    # Sort ascending for horizontal bar layout
    rec_counts = rec_counts.sort_values('COUNT', ascending=True)

    # Define colors based on recommendation
    colors = []
    for rec in rec_counts['RECOMMENDATION']:
        if '⚠️' in rec:
            colors.append('#E74C3C')  # Red for warnings
        else:
            colors.append('#0077B6')  # Green for OK

    fig = go.Figure(data=[
        go.Bar(
            y=rec_counts['RECOMMENDATION'],
            x=rec_counts['COUNT'],
            orientation='h',
            marker_color=colors,
            text=[f"{int(val)}" for val in rec_counts['COUNT']],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Number of Queries',
        yaxis_title='Recommendation',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_recommendation_pie_chart(df, key_prefix=""):
    """Render recommendation pie chart using ECharts."""
    rec_counts = df['RECOMMENDATION'].value_counts()
    chart_data = [
        {"value": int(count), "name": f"{rec} ({count})"}
        for rec, count in rec_counts.items()
    ]

    # Colors: green for OK, red for warnings
    colors = []
    for rec in rec_counts.index:
        if '⚠️' in rec:
            colors.append('#E74C3C')
        else:
            colors.append('#0077B6')

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
            "name": "Recommendation",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_recommendation_donut_chart(df, key_prefix=""):
    """Render recommendation donut chart using ECharts."""
    rec_counts = df['RECOMMENDATION'].value_counts()
    chart_data = [
        {"value": int(count), "name": f"{rec} ({count})"}
        for rec, count in rec_counts.items()
    ]

    colors = []
    for rec in rec_counts.index:
        if '⚠️' in rec:
            colors.append('#E74C3C')
        else:
            colors.append('#0077B6')

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
            "name": "Recommendation",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_recommendation_rose_chart(df, key_prefix=""):
    """Render recommendation rose chart using ECharts."""
    rec_counts = df['RECOMMENDATION'].value_counts()
    chart_data = [
        {"value": int(count), "name": rec}
        for rec, count in rec_counts.items()
    ]

    colors = []
    for rec in rec_counts.index:
        if '⚠️' in rec:
            colors.append('#E74C3C')
        else:
            colors.append('#0077B6')

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 12,
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} queries ({d}%)"},
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
            "name": "Recommendation",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_count_vs_duration_chart(df, key_prefix=""):
    """Render execution count vs duration comparison chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_count_vs_duration_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_count_vs_duration_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_count_vs_duration_donut_chart(df, key_prefix)
    else:
        _render_count_vs_duration_rose_chart(df, key_prefix)


def _render_count_vs_duration_bar_chart(df, key_prefix=""):
    """Render execution count vs duration grouped bar chart using Plotly."""
    # Use top 8 for better visualization
    plot_df = df.head(8).copy()

    # Truncate query pattern for display
    plot_df['DISPLAY_PATTERN'] = plot_df['QUERY_PATTERN'].apply(lambda x: x[:25] + '...' if len(str(x)) > 25 else x)

    # Create figure with secondary y-axis
    fig = go.Figure()

    # Add execution count bars
    fig.add_trace(go.Bar(
        name='Execution Count',
        x=plot_df['DISPLAY_PATTERN'],
        y=plot_df['EXECUTION_COUNT'],
        marker_color='#29B5E8',
        text=[f"{int(val):,}" for val in plot_df['EXECUTION_COUNT']],
        textposition='outside',
        textfont=dict(size=9),
        yaxis='y'
    ))

    # Add average duration bars
    fig.add_trace(go.Bar(
        name='Avg Duration (ms)',
        x=plot_df['DISPLAY_PATTERN'],
        y=plot_df['AVG_DURATION_MS'],
        marker_color='#E8A229',
        text=[f"{val:.0f}" for val in plot_df['AVG_DURATION_MS']],
        textposition='outside',
        textfont=dict(size=9),
        yaxis='y2'
    ))

    fig.update_layout(
        height=400,
        xaxis=dict(
            title='Query Pattern',
            tickangle=45
        ),
        yaxis=dict(
            title='Execution Count',
            side='left'
        ),
        yaxis2=dict(
            title='Avg Duration (ms)',
            side='right',
            overlaying='y'
        ),
        barmode='group',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        margin=dict(t=50, b=120, l=80, r=80)
    )


def _render_count_vs_duration_pie_chart(df, key_prefix=""):
    """Render total execution time distribution pie chart using ECharts."""
    plot_df = df.head(10).copy()
    # Calculate total execution time (count * avg duration)
    plot_df['TOTAL_TIME'] = plot_df['EXECUTION_COUNT'] * plot_df['AVG_DURATION_MS']

    chart_data = [
        {"value": float(row['TOTAL_TIME']), "name": f"{str(row['QUERY_PATTERN'])[:25]}... ({row['TOTAL_TIME']/1000:.1f}s)"}
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
        "color": ["#0077B6", "#29B5E8", "#0077B6", "#E74C3C", "#E8A229", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8"],
        "series": [{
            "name": "Total Time",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_count_vs_duration_donut_chart(df, key_prefix=""):
    """Render total execution time distribution donut chart using ECharts."""
    plot_df = df.head(10).copy()
    plot_df['TOTAL_TIME'] = plot_df['EXECUTION_COUNT'] * plot_df['AVG_DURATION_MS']

    chart_data = [
        {"value": float(row['TOTAL_TIME']), "name": f"{str(row['QUERY_PATTERN'])[:25]}... ({row['TOTAL_TIME']/1000:.1f}s)"}
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
        "color": ["#0077B6", "#29B5E8", "#0077B6", "#E74C3C", "#E8A229", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8"],
        "series": [{
            "name": "Total Time",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_count_vs_duration_rose_chart(df, key_prefix=""):
    """Render total execution time distribution rose chart using ECharts."""
    plot_df = df.head(10).copy()
    plot_df['TOTAL_TIME'] = plot_df['EXECUTION_COUNT'] * plot_df['AVG_DURATION_MS']

    chart_data = [
        {"value": float(row['TOTAL_TIME']), "name": f"{str(row['QUERY_PATTERN'])[:25]}..."}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ms total ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#0077B6", "#29B5E8", "#0077B6", "#E74C3C", "#E8A229", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8"],
        "series": [{
            "name": "Total Time",
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
# RAP Slow Query Charts
# ============================

def _render_rap_slow_query_count_chart(df, key_prefix=""):
    """Render slow query count by policy chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_rap_count_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_rap_count_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_rap_count_donut_chart(df, key_prefix)
    else:
        _render_rap_count_rose_chart(df, key_prefix)


def _render_rap_count_bar_chart(df, key_prefix=""):
    """Render slow query count bar chart using Plotly."""
    # Aggregate by policy name
    agg_df = df.groupby('POLICY_NAME').agg({'SLOW_QUERY_COUNT': 'sum'}).reset_index()
    plot_df = agg_df.sort_values('SLOW_QUERY_COUNT', ascending=True).head(10)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['POLICY_NAME'],
            x=plot_df['SLOW_QUERY_COUNT'],
            orientation='h',
            marker_color='#29B5E8',
            text=[f"{int(val):,}" for val in plot_df['SLOW_QUERY_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Slow Queries: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Slow Query Count',
        yaxis_title='Policy Name',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_rap_count_pie_chart(df, key_prefix=""):
    """Render slow query count pie chart using ECharts."""
    agg_df = df.groupby('POLICY_NAME').agg({'SLOW_QUERY_COUNT': 'sum'}).reset_index()
    chart_data = [
        {"value": int(row['SLOW_QUERY_COUNT']), "name": f"{row['POLICY_NAME']} ({int(row['SLOW_QUERY_COUNT']):,})"}
        for _, row in agg_df.iterrows()
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
            "name": "Slow Queries",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_rap_count_donut_chart(df, key_prefix=""):
    """Render slow query count donut chart using ECharts."""
    agg_df = df.groupby('POLICY_NAME').agg({'SLOW_QUERY_COUNT': 'sum'}).reset_index()
    chart_data = [
        {"value": int(row['SLOW_QUERY_COUNT']), "name": f"{row['POLICY_NAME']} ({int(row['SLOW_QUERY_COUNT']):,})"}
        for _, row in agg_df.iterrows()
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
            "name": "Slow Queries",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_rap_count_rose_chart(df, key_prefix=""):
    """Render slow query count rose chart using ECharts."""
    agg_df = df.groupby('POLICY_NAME').agg({'SLOW_QUERY_COUNT': 'sum'}).reset_index()
    chart_data = [
        {"value": int(row['SLOW_QUERY_COUNT']), "name": row['POLICY_NAME']}
        for _, row in agg_df.iterrows()
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} slow queries ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Slow Queries",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_rap_avg_execution_chart(df, key_prefix=""):
    """Render average execution time chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_rap_avg_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_rap_avg_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_rap_avg_donut_chart(df, key_prefix)
    else:
        _render_rap_avg_rose_chart(df, key_prefix)


def _render_rap_avg_bar_chart(df, key_prefix=""):
    """Render average execution time bar chart using Plotly."""
    plot_df = df.sort_values('AVG_EXECUTION_MS', ascending=True).head(10)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['PROTECTED_TABLE'],
            x=plot_df['AVG_EXECUTION_MS'],
            orientation='h',
            marker_color='#E8A229',
            text=[f"{val:.0f} ms" for val in plot_df['AVG_EXECUTION_MS']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Avg Execution: %{x:.2f} ms<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Average Execution Time (ms)',
        yaxis_title='Protected Table',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_rap_avg_pie_chart(df, key_prefix=""):
    """Render average execution time pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_EXECUTION_MS']), "name": f"{row['PROTECTED_TABLE']} ({row['AVG_EXECUTION_MS']:.0f} ms)"}
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
        "color": ["#E8A229", "#0077B6", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8", "#29B5E8"],
        "series": [{
            "name": "Avg Execution",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_rap_avg_donut_chart(df, key_prefix=""):
    """Render average execution time donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_EXECUTION_MS']), "name": f"{row['PROTECTED_TABLE']} ({row['AVG_EXECUTION_MS']:.0f} ms)"}
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
        "color": ["#E8A229", "#0077B6", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8", "#29B5E8"],
        "series": [{
            "name": "Avg Execution",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_rap_avg_rose_chart(df, key_prefix=""):
    """Render average execution time rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_EXECUTION_MS']), "name": row['PROTECTED_TABLE']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ms ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#E8A229", "#0077B6", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8", "#29B5E8"],
        "series": [{
            "name": "Avg Execution",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_rap_table_distribution_chart(df, key_prefix=""):
    """Render slow queries by protected table chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_rap_table_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_rap_table_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_rap_table_donut_chart(df, key_prefix)
    else:
        _render_rap_table_rose_chart(df, key_prefix)


def _render_rap_table_bar_chart(df, key_prefix=""):
    """Render slow queries by table bar chart using Plotly."""
    plot_df = df.sort_values('SLOW_QUERY_COUNT', ascending=True).head(10)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['PROTECTED_TABLE'],
            x=plot_df['SLOW_QUERY_COUNT'],
            orientation='h',
            marker_color='#0077B6',
            text=[f"{int(val):,}" for val in plot_df['SLOW_QUERY_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Slow Queries: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Slow Query Count',
        yaxis_title='Protected Table',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_rap_table_pie_chart(df, key_prefix=""):
    """Render slow queries by table pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['SLOW_QUERY_COUNT']), "name": f"{row['PROTECTED_TABLE']} ({int(row['SLOW_QUERY_COUNT']):,})"}
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
        "color": ["#0077B6", "#0077B6", "#29B5E8", "#75C2D8", "#E8A229", "#E8A229", "#E74C3C", "#E74C3C", "#0077B6", "#0077B6"],
        "series": [{
            "name": "Slow Queries",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_rap_table_donut_chart(df, key_prefix=""):
    """Render slow queries by table donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['SLOW_QUERY_COUNT']), "name": f"{row['PROTECTED_TABLE']} ({int(row['SLOW_QUERY_COUNT']):,})"}
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
        "color": ["#0077B6", "#0077B6", "#29B5E8", "#75C2D8", "#E8A229", "#E8A229", "#E74C3C", "#E74C3C", "#0077B6", "#0077B6"],
        "series": [{
            "name": "Slow Queries",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_rap_table_rose_chart(df, key_prefix=""):
    """Render slow queries by table rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['SLOW_QUERY_COUNT']), "name": row['PROTECTED_TABLE']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} slow queries ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#0077B6", "#0077B6", "#29B5E8", "#75C2D8", "#E8A229", "#E8A229", "#E74C3C", "#E74C3C", "#0077B6", "#0077B6"],
        "series": [{
            "name": "Slow Queries",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_rap_total_time_chart(df, key_prefix=""):
    """Render total slow query time by policy chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_rap_total_time_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_rap_total_time_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_rap_total_time_donut_chart(df, key_prefix)
    else:
        _render_rap_total_time_rose_chart(df, key_prefix)


def _render_rap_total_time_bar_chart(df, key_prefix=""):
    """Render total slow query time bar chart using Plotly."""
    # Calculate total time (count * avg)
    plot_df = df.copy()
    plot_df['TOTAL_TIME_MS'] = plot_df['SLOW_QUERY_COUNT'] * plot_df['AVG_EXECUTION_MS']
    agg_df = plot_df.groupby('POLICY_NAME').agg({'TOTAL_TIME_MS': 'sum'}).reset_index()
    agg_df = agg_df.sort_values('TOTAL_TIME_MS', ascending=True).head(10)

    fig = go.Figure(data=[
        go.Bar(
            y=agg_df['POLICY_NAME'],
            x=agg_df['TOTAL_TIME_MS'],
            orientation='h',
            marker_color='#0077B6',
            text=[f"{val/1000:.1f}s" for val in agg_df['TOTAL_TIME_MS']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Total Time: %{x:.0f} ms<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Total Slow Query Time (ms)',
        yaxis_title='Policy Name',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_rap_total_time_pie_chart(df, key_prefix=""):
    """Render total slow query time pie chart using ECharts."""
    plot_df = df.copy()
    plot_df['TOTAL_TIME_MS'] = plot_df['SLOW_QUERY_COUNT'] * plot_df['AVG_EXECUTION_MS']
    agg_df = plot_df.groupby('POLICY_NAME').agg({'TOTAL_TIME_MS': 'sum'}).reset_index()

    chart_data = [
        {"value": float(row['TOTAL_TIME_MS']), "name": f"{row['POLICY_NAME']} ({row['TOTAL_TIME_MS']/1000:.1f}s)"}
        for _, row in agg_df.iterrows()
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
        "color": ["#0077B6", "#0077B6", "#29B5E8", "#75C2D8", "#E8A229", "#E8A229", "#0077B6", "#0077B6", "#E74C3C", "#E74C3C"],
        "series": [{
            "name": "Total Time",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_rap_total_time_donut_chart(df, key_prefix=""):
    """Render total slow query time donut chart using ECharts."""
    plot_df = df.copy()
    plot_df['TOTAL_TIME_MS'] = plot_df['SLOW_QUERY_COUNT'] * plot_df['AVG_EXECUTION_MS']
    agg_df = plot_df.groupby('POLICY_NAME').agg({'TOTAL_TIME_MS': 'sum'}).reset_index()

    chart_data = [
        {"value": float(row['TOTAL_TIME_MS']), "name": f"{row['POLICY_NAME']} ({row['TOTAL_TIME_MS']/1000:.1f}s)"}
        for _, row in agg_df.iterrows()
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
        "color": ["#0077B6", "#0077B6", "#29B5E8", "#75C2D8", "#E8A229", "#E8A229", "#0077B6", "#0077B6", "#E74C3C", "#E74C3C"],
        "series": [{
            "name": "Total Time",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_rap_total_time_rose_chart(df, key_prefix=""):
    """Render total slow query time rose chart using ECharts."""
    plot_df = df.copy()
    plot_df['TOTAL_TIME_MS'] = plot_df['SLOW_QUERY_COUNT'] * plot_df['AVG_EXECUTION_MS']
    agg_df = plot_df.groupby('POLICY_NAME').agg({'TOTAL_TIME_MS': 'sum'}).reset_index()

    chart_data = [
        {"value": float(row['TOTAL_TIME_MS']), "name": row['POLICY_NAME']}
        for _, row in agg_df.iterrows()
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ms ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#0077B6", "#0077B6", "#29B5E8", "#75C2D8", "#E8A229", "#E8A229", "#0077B6", "#0077B6", "#E74C3C", "#E74C3C"],
        "series": [{
            "name": "Total Time",
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
# MV Refresh Cost Charts
# ============================

def _render_mv_total_cost_chart(df, key_prefix=""):
    """Render total refresh cost chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_mv_total_cost_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_mv_total_cost_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_mv_total_cost_donut_chart(df, key_prefix)
    else:
        _render_mv_total_cost_rose_chart(df, key_prefix)


def _render_mv_total_cost_bar_chart(df, key_prefix=""):
    """Render total refresh cost bar chart using Plotly."""
    plot_df = df.head(10).sort_values('REFRESH_COST_CREDITS', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['MV_NAME'],
            x=plot_df['REFRESH_COST_CREDITS'],
            orientation='h',
            marker_color='#29B5E8',
            text=[f"{val:.4f}" for val in plot_df['REFRESH_COST_CREDITS']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Credits: %{x:.4f}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Total Refresh Cost (Credits)',
        yaxis_title='Materialized View',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )


def _render_mv_total_cost_pie_chart(df, key_prefix=""):
    """Render total refresh cost pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['REFRESH_COST_CREDITS']), "name": f"{row['MV_NAME']} ({row['REFRESH_COST_CREDITS']:.4f})"}
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
            "name": "Credits",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_mv_total_cost_donut_chart(df, key_prefix=""):
    """Render total refresh cost donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['REFRESH_COST_CREDITS']), "name": f"{row['MV_NAME']} ({row['REFRESH_COST_CREDITS']:.4f})"}
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
            "name": "Credits",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_mv_total_cost_rose_chart(df, key_prefix=""):
    """Render total refresh cost rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['REFRESH_COST_CREDITS']), "name": row['MV_NAME']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} credits ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Credits",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_mv_refresh_count_chart(df, key_prefix=""):
    """Render refresh count chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_mv_refresh_count_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_mv_refresh_count_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_mv_refresh_count_donut_chart(df, key_prefix)
    else:
        _render_mv_refresh_count_rose_chart(df, key_prefix)


def _render_mv_refresh_count_bar_chart(df, key_prefix=""):
    """Render refresh count bar chart using Plotly."""
    plot_df = df.head(10).sort_values('REFRESH_COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['MV_NAME'],
            x=plot_df['REFRESH_COUNT'],
            orientation='h',
            marker_color='#E8A229',
            text=[f"{int(val)}" for val in plot_df['REFRESH_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Refreshes: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Refresh Count',
        yaxis_title='Materialized View',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )


def _render_mv_refresh_count_pie_chart(df, key_prefix=""):
    """Render refresh count pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['REFRESH_COUNT']), "name": f"{row['MV_NAME']} ({int(row['REFRESH_COUNT'])})"}
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
            "name": "Refreshes",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_mv_refresh_count_donut_chart(df, key_prefix=""):
    """Render refresh count donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['REFRESH_COUNT']), "name": f"{row['MV_NAME']} ({int(row['REFRESH_COUNT'])})"}
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
            "name": "Refreshes",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_mv_refresh_count_rose_chart(df, key_prefix=""):
    """Render refresh count rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": int(row['REFRESH_COUNT']), "name": row['MV_NAME']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} refreshes ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Refreshes",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_mv_avg_cost_chart(df, key_prefix=""):
    """Render average cost per refresh chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_mv_avg_cost_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_mv_avg_cost_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_mv_avg_cost_donut_chart(df, key_prefix)
    else:
        _render_mv_avg_cost_rose_chart(df, key_prefix)


def _render_mv_avg_cost_bar_chart(df, key_prefix=""):
    """Render average cost bar chart using Plotly."""
    plot_df = df.head(10).sort_values('AVG_COST_PER_REFRESH', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['MV_NAME'],
            x=plot_df['AVG_COST_PER_REFRESH'],
            orientation='h',
            marker_color='#0077B6',
            text=[f"{val:.6f}" for val in plot_df['AVG_COST_PER_REFRESH']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Avg Cost: %{x:.6f}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Average Cost Per Refresh (Credits)',
        yaxis_title='Materialized View',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )


def _render_mv_avg_cost_pie_chart(df, key_prefix=""):
    """Render average cost pie chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_COST_PER_REFRESH']), "name": f"{row['MV_NAME']} ({row['AVG_COST_PER_REFRESH']:.6f})"}
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
            "name": "Avg Cost",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_mv_avg_cost_donut_chart(df, key_prefix=""):
    """Render average cost donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_COST_PER_REFRESH']), "name": f"{row['MV_NAME']} ({row['AVG_COST_PER_REFRESH']:.6f})"}
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
            "name": "Avg Cost",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_mv_avg_cost_rose_chart(df, key_prefix=""):
    """Render average cost rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['AVG_COST_PER_REFRESH']), "name": row['MV_NAME']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} credits ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Avg Cost",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_mv_cost_vs_frequency_chart(df, key_prefix=""):
    """Render cost vs frequency chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_mv_cost_vs_frequency_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_mv_cost_vs_frequency_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_mv_cost_vs_frequency_donut_chart(df, key_prefix)
    else:
        _render_mv_cost_vs_frequency_rose_chart(df, key_prefix)


def _render_mv_cost_vs_frequency_bar_chart(df, key_prefix=""):
    """Render cost vs frequency bar chart using Plotly (grouped bar)."""
    plot_df = df.head(10).sort_values('REFRESH_COST_CREDITS', ascending=True)

    # Normalize values for comparison (scale to 0-100)
    max_cost = plot_df['REFRESH_COST_CREDITS'].max() if plot_df['REFRESH_COST_CREDITS'].max() > 0 else 1
    max_count = plot_df['REFRESH_COUNT'].max() if plot_df['REFRESH_COUNT'].max() > 0 else 1

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=plot_df['MV_NAME'],
        x=(plot_df['REFRESH_COST_CREDITS'] / max_cost * 100),
        orientation='h',
        name='Cost (normalized)',
        marker_color='#29B5E8',
        hovertemplate='<b>%{y}</b><br>Cost: %{customdata:.4f} credits<extra></extra>',
        customdata=plot_df['REFRESH_COST_CREDITS']
    ))

    fig.add_trace(go.Bar(
        y=plot_df['MV_NAME'],
        x=(plot_df['REFRESH_COUNT'] / max_count * 100),
        orientation='h',
        name='Frequency (normalized)',
        marker_color='#E8A229',
        hovertemplate='<b>%{y}</b><br>Refreshes: %{customdata:,}<extra></extra>',
        customdata=plot_df['REFRESH_COUNT']
    ))

    fig.update_layout(
        height=400,
        xaxis_title='Normalized Value (%)',
        yaxis_title='Materialized View',
        barmode='group',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=40, b=50, l=120, r=50)
    )


def _render_mv_cost_vs_frequency_pie_chart(df, key_prefix=""):
    """Render cost efficiency pie chart using ECharts."""
    plot_df = df.head(10)
    # Show cost efficiency (cost per refresh)
    chart_data = [
        {"value": float(row['REFRESH_COST_CREDITS']), "name": f"{row['MV_NAME']} ({row['REFRESH_COUNT']} refreshes)"}
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
            "name": "Cost Share",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_mv_cost_vs_frequency_donut_chart(df, key_prefix=""):
    """Render cost efficiency donut chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['REFRESH_COST_CREDITS']), "name": f"{row['MV_NAME']} ({row['REFRESH_COUNT']} refreshes)"}
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
            "name": "Cost Share",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_mv_cost_vs_frequency_rose_chart(df, key_prefix=""):
    """Render cost efficiency rose chart using ECharts."""
    plot_df = df.head(10)
    chart_data = [
        {"value": float(row['REFRESH_COST_CREDITS']), "name": row['MV_NAME']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} credits ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Cost Share",
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
# Performance Dashboard Charts
# ============================

def _render_perf_category_chart(df, key_prefix=""):
    """Render metrics by category chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_perf_category_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_perf_category_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_perf_category_donut_chart(df, key_prefix)
    else:
        _render_perf_category_rose_chart(df, key_prefix)


def _render_perf_category_bar_chart(df, key_prefix=""):
    """Render metrics by category bar chart using Plotly."""
    # Count metrics per category
    cat_counts = df.groupby('METRIC_CATEGORY').size().reset_index(name='COUNT')
    cat_counts = cat_counts.sort_values('COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=cat_counts['METRIC_CATEGORY'],
            x=cat_counts['COUNT'],
            orientation='h',
            marker_color='#29B5E8',
            text=[f"{int(val)}" for val in cat_counts['COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Metrics: %{x}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Number of Metrics',
        yaxis_title='Category',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_perf_category_pie_chart(df, key_prefix=""):
    """Render metrics by category pie chart using ECharts."""
    cat_counts = df.groupby('METRIC_CATEGORY').size().reset_index(name='COUNT')
    chart_data = [
        {"value": int(row['COUNT']), "name": f"{row['METRIC_CATEGORY']} ({int(row['COUNT'])})"}
        for _, row in cat_counts.iterrows()
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
            "name": "Categories",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_perf_category_donut_chart(df, key_prefix=""):
    """Render metrics by category donut chart using ECharts."""
    cat_counts = df.groupby('METRIC_CATEGORY').size().reset_index(name='COUNT')
    chart_data = [
        {"value": int(row['COUNT']), "name": f"{row['METRIC_CATEGORY']} ({int(row['COUNT'])})"}
        for _, row in cat_counts.iterrows()
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
            "name": "Categories",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_perf_category_rose_chart(df, key_prefix=""):
    """Render metrics by category rose chart using ECharts."""
    cat_counts = df.groupby('METRIC_CATEGORY').size().reset_index(name='COUNT')
    chart_data = [
        {"value": int(row['COUNT']), "name": row['METRIC_CATEGORY']}
        for _, row in cat_counts.iterrows()
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} metrics ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Categories",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_perf_values_chart(df, key_prefix=""):
    """Render metric values distribution chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_perf_values_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_perf_values_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_perf_values_donut_chart(df, key_prefix)
    else:
        _render_perf_values_rose_chart(df, key_prefix)


def _render_perf_values_bar_chart(df, key_prefix=""):
    """Render metric values bar chart using Plotly."""
    # Convert VALUE to numeric, handling non-numeric gracefully
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)
    plot_df = plot_df.sort_values('NUMERIC_VALUE', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['METRIC_NAME'],
            x=plot_df['NUMERIC_VALUE'],
            orientation='h',
            marker_color='#E8A229',
            text=[f"{val}" for val in plot_df['VALUE']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Value: %{text}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Value',
        yaxis_title='Metric',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_perf_values_pie_chart(df, key_prefix=""):
    """Render metric values pie chart using ECharts."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)
    chart_data = [
        {"value": float(row['NUMERIC_VALUE']), "name": f"{row['METRIC_NAME']} ({row['VALUE']})"}
        for _, row in plot_df.iterrows() if row['NUMERIC_VALUE'] > 0
    ]

    if not chart_data:
        chart_data = [{"value": 1, "name": "No numeric data"}]

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
            "name": "Values",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_perf_values_donut_chart(df, key_prefix=""):
    """Render metric values donut chart using ECharts."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)
    chart_data = [
        {"value": float(row['NUMERIC_VALUE']), "name": f"{row['METRIC_NAME']} ({row['VALUE']})"}
        for _, row in plot_df.iterrows() if row['NUMERIC_VALUE'] > 0
    ]

    if not chart_data:
        chart_data = [{"value": 1, "name": "No numeric data"}]

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
            "name": "Values",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_perf_values_rose_chart(df, key_prefix=""):
    """Render metric values rose chart using ECharts."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)
    chart_data = [
        {"value": float(row['NUMERIC_VALUE']), "name": row['METRIC_NAME']}
        for _, row in plot_df.iterrows() if row['NUMERIC_VALUE'] > 0
    ]

    if not chart_data:
        chart_data = [{"value": 1, "name": "No numeric data"}]

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
            "name": "Values",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_perf_breakdown_chart(df, key_prefix=""):
    """Render category breakdown chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_perf_breakdown_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_perf_breakdown_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_perf_breakdown_donut_chart(df, key_prefix)
    else:
        _render_perf_breakdown_rose_chart(df, key_prefix)


def _render_perf_breakdown_bar_chart(df, key_prefix=""):
    """Render category breakdown bar chart using Plotly."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)

    # Aggregate by category
    cat_agg = plot_df.groupby('METRIC_CATEGORY').agg({'NUMERIC_VALUE': 'sum'}).reset_index()
    cat_agg = cat_agg.sort_values('NUMERIC_VALUE', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=cat_agg['METRIC_CATEGORY'],
            x=cat_agg['NUMERIC_VALUE'],
            orientation='h',
            marker_color='#0077B6',
            text=[f"{val:,.2f}" for val in cat_agg['NUMERIC_VALUE']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Total: %{x:,.2f}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Total Value',
        yaxis_title='Category',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_perf_breakdown_pie_chart(df, key_prefix=""):
    """Render category breakdown pie chart using ECharts."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)
    cat_agg = plot_df.groupby('METRIC_CATEGORY').agg({'NUMERIC_VALUE': 'sum'}).reset_index()

    chart_data = [
        {"value": float(row['NUMERIC_VALUE']), "name": f"{row['METRIC_CATEGORY']} ({row['NUMERIC_VALUE']:,.2f})"}
        for _, row in cat_agg.iterrows() if row['NUMERIC_VALUE'] > 0
    ]

    if not chart_data:
        chart_data = [{"value": 1, "name": "No data"}]

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
            "name": "Breakdown",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_perf_breakdown_donut_chart(df, key_prefix=""):
    """Render category breakdown donut chart using ECharts."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)
    cat_agg = plot_df.groupby('METRIC_CATEGORY').agg({'NUMERIC_VALUE': 'sum'}).reset_index()

    chart_data = [
        {"value": float(row['NUMERIC_VALUE']), "name": f"{row['METRIC_CATEGORY']} ({row['NUMERIC_VALUE']:,.2f})"}
        for _, row in cat_agg.iterrows() if row['NUMERIC_VALUE'] > 0
    ]

    if not chart_data:
        chart_data = [{"value": 1, "name": "No data"}]

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
            "name": "Breakdown",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_perf_breakdown_rose_chart(df, key_prefix=""):
    """Render category breakdown rose chart using ECharts."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)
    cat_agg = plot_df.groupby('METRIC_CATEGORY').agg({'NUMERIC_VALUE': 'sum'}).reset_index()

    chart_data = [
        {"value": float(row['NUMERIC_VALUE']), "name": row['METRIC_CATEGORY']}
        for _, row in cat_agg.iterrows() if row['NUMERIC_VALUE'] > 0
    ]

    if not chart_data:
        chart_data = [{"value": 1, "name": "No data"}]

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
            "name": "Breakdown",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_perf_summary_chart(df, key_prefix=""):
    """Render metrics summary chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_perf_summary_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_perf_summary_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_perf_summary_donut_chart(df, key_prefix)
    else:
        _render_perf_summary_rose_chart(df, key_prefix)


def _render_perf_summary_bar_chart(df, key_prefix=""):
    """Render metrics summary bar chart using Plotly (grouped by category and metric)."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)
    plot_df['LABEL'] = plot_df['METRIC_CATEGORY'] + ': ' + plot_df['METRIC_NAME']
    plot_df = plot_df.sort_values('NUMERIC_VALUE', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['LABEL'],
            x=plot_df['NUMERIC_VALUE'],
            orientation='h',
            marker_color='#0077B6',
            text=[f"{val}" for val in plot_df['VALUE']],
            textposition='outside',
            textfont=dict(size=9),
            hovertemplate='<b>%{y}</b><br>Value: %{text}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Value',
        yaxis_title='Metric',
        showlegend=False,
        margin=dict(t=20, b=50, l=250, r=50)
    )


def _render_perf_summary_pie_chart(df, key_prefix=""):
    """Render metrics summary pie chart using ECharts."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)

    chart_data = [
        {"value": float(row['NUMERIC_VALUE']), "name": f"{row['METRIC_NAME']} ({row['VALUE']})"}
        for _, row in plot_df.iterrows() if row['NUMERIC_VALUE'] > 0
    ]

    if not chart_data:
        chart_data = [{"value": 1, "name": "No numeric data"}]

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
            "name": "Summary",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_perf_summary_donut_chart(df, key_prefix=""):
    """Render metrics summary donut chart using ECharts."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)

    chart_data = [
        {"value": float(row['NUMERIC_VALUE']), "name": f"{row['METRIC_NAME']} ({row['VALUE']})"}
        for _, row in plot_df.iterrows() if row['NUMERIC_VALUE'] > 0
    ]

    if not chart_data:
        chart_data = [{"value": 1, "name": "No numeric data"}]

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
            "name": "Summary",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_perf_summary_rose_chart(df, key_prefix=""):
    """Render metrics summary rose chart using ECharts."""
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)

    chart_data = [
        {"value": float(row['NUMERIC_VALUE']), "name": row['METRIC_NAME']}
        for _, row in plot_df.iterrows() if row['NUMERIC_VALUE'] > 0
    ]

    if not chart_data:
        chart_data = [{"value": 1, "name": "No numeric data"}]

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
            "name": "Summary",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")

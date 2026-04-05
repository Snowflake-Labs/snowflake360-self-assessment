import streamlit as st
import pandas as pd
import plotly.graph_objects as go
try:
    from streamlit_echarts import st_echarts
except ImportError:
    def st_echarts(**kwargs):
        import streamlit as st
        st.info("Chart unavailable (echarts not supported in SiS)")


def comp_syntax_hunter(entry_actions=None):
    """
    Syntax Hunter (Regex & Heuristics) Component

    Uses regex and heuristics to detect query patterns and potential issues.
    """
    try:
        # Get session and context
        try:
            from snowflake.snowpark.context import get_active_session
            session = get_active_session()
        except Exception as e:
            # st.error(f"Unable to get Snowflake session: {str(e)}")
            st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Unable to get Snowflake session: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if not session:
            # st.warning("⚠️ Snowflake session not available.")
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;Snowflake session not available.'
                            '</div>', unsafe_allow_html=True)
            return

        # Build and execute the query
        query = f"""
SELECT
    query_id,
    query_text,

    -- 1. ASOF JOIN
    CASE
        WHEN query_text ILIKE '%ASOF JOIN%' THEN '✅ Yes'
        ELSE 'No'
    END AS uses_asof_join,

    -- 2. COLLATION
    CASE
        WHEN query_text ILIKE '%COLLATE%' THEN '✅ Yes'
        ELSE 'No'
    END AS uses_collation,

    -- 3. DIRECTED JOINS (Look for "JOIN +")
    CASE
        WHEN REGEXP_LIKE(query_text, '.*JOIN\\\\s*\\\\+.*', 'i') THEN '✅ Yes'
        ELSE 'No'
    END AS uses_directed_join,

    -- 4. ORDER BY in CTE (Heuristic: WITH ... ORDER BY ... SELECT)
    CASE
        WHEN REGEXP_LIKE(query_text, '.*WITH.*ORDER BY.*SELECT.*', 'is') THEN '✅ Yes'
        ELSE 'No'
    END AS order_by_in_cte,

    -- 5. ORDER BY with GROUP BY
    CASE
        WHEN query_text ILIKE '%GROUP BY%' AND query_text ILIKE '%ORDER BY%' THEN '✅ Yes'
        ELSE 'No'
    END AS sort_and_agg,

    -- 6. DISTINCT vs APPROX CANDIDATE
    CASE
        WHEN query_text ILIKE '%DISTINCT%' AND bytes_scanned > 1024*1024*1024
        THEN '⚠️ Consider APPROX'
        ELSE '-'
    END AS distinct_optimization_check

FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND (
      query_text ILIKE '%ASOF JOIN%' OR
      query_text ILIKE '%COLLATE%' OR
      query_text ILIKE '%DISTINCT%' OR
      query_text ILIKE '%+%' OR
      query_text ILIKE '%ORDER BY%'
  )
LIMIT 100
        """


        # Execute query
        try:
            df = session.sql(query).to_pandas()
        except Exception as e:
            # st.error(f"Error executing query: {str(e)}")
            st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No SQL pattern data found for the last 7 days.'
                        '</div>', unsafe_allow_html=True)
            return

        # Create expander with introduction text
        with st.expander("Advanced SQL Pattern Detection", expanded=True):
            # Introduction text without CSS styling
            st.markdown("Advanced SQL pattern detection identifying ASOF joins, collation, directed joins, CTE ordering, "
                       "sort/aggregate combinations, and DISTINCT optimization opportunities from last 7 days.")


            # Create metric object for dialogs
            # Initialize or update metric object in session state


            # Display the dataframe
            st.dataframe(
                df,
                hide_index=True
            )

            # Charts Section
            st.markdown("---")
            st.markdown("#### SQL Pattern Analysis Charts")

            # Prepare summary data for charts
            pattern_summary = _prepare_pattern_summary(df)

            # Row 1: Two charts
            col1, col2 = st.columns(2)

            with col1.container(border=True):
                st.markdown("##### Pattern Usage Distribution")
                _render_pattern_usage_chart(pattern_summary, key_prefix="pattern_usage_")

            with col2.container(border=True):
                st.markdown("##### Queries by Pattern Type")
                _render_pattern_queries_chart(pattern_summary, key_prefix="pattern_queries_")

            # Row 2: Two charts
            col3, col4 = st.columns(2)

            with col3.container(border=True):
                st.markdown("##### DISTINCT Optimization Candidates")
                _render_distinct_optimization_chart(df, key_prefix="distinct_opt_")

            with col4.container(border=True):
                st.markdown("##### Pattern Detection Summary")
                _render_pattern_summary_chart(pattern_summary, key_prefix="pattern_summary_")

        # ============================================================
        # Second Expander: SQL Pattern Frequency Summary
        # ============================================================

        # Build and execute the frequency summary query
        frequency_query = f"""
WITH feature_flags AS (
    SELECT
        -- 1. ASOF JOIN
        CASE
            WHEN query_text ILIKE '%ASOF JOIN%' THEN 1
            ELSE 0
        END AS uses_asof_join,

        -- 2. COLLATION
        CASE
            WHEN query_text ILIKE '%COLLATE%' THEN 1
            ELSE 0
        END AS uses_collation,

        -- 3. DIRECTED JOINS ("JOIN +")
        CASE
            WHEN REGEXP_LIKE(query_text, '.*JOIN\\\\s*\\\\+.*', 'i') THEN 1
            ELSE 0
        END AS uses_directed_join,

        -- 4. ORDER BY IN CTE (Inefficiency)
        CASE
            WHEN REGEXP_LIKE(query_text, '.*WITH.*ORDER BY.*SELECT.*', 'is') THEN 1
            ELSE 0
        END AS order_by_in_cte,

        -- 5. ORDER BY + GROUP BY (Heavy Compute)
        CASE
            WHEN query_text ILIKE '%GROUP BY%' AND query_text ILIKE '%ORDER BY%' THEN 1
            ELSE 0
        END AS sort_and_agg,

        -- 6. HEAVY DISTINCT (>1GB Scanned)
        CASE
            WHEN query_text ILIKE '%DISTINCT%' AND bytes_scanned > 1024*1024*1024 THEN 1
            ELSE 0
        END AS heavy_distinct

    FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
    WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND (
          query_text ILIKE '%ASOF JOIN%' OR
          query_text ILIKE '%COLLATE%' OR
          query_text ILIKE '%DISTINCT%' OR
          query_text ILIKE '%+%' OR
          query_text ILIKE '%ORDER BY%'
      )
)
, aggr as (
SELECT 'Sort + Aggregate (Heavy Compute)' AS detection_type, SUM(sort_and_agg) AS occurrence_count FROM feature_flags
UNION ALL
SELECT 'Order By inside CTE (Likely Redundant)', SUM(order_by_in_cte) FROM feature_flags
UNION ALL
SELECT 'Heavy Distinct (>1GB Scanned)', SUM(heavy_distinct) FROM feature_flags
UNION ALL
SELECT 'Directed Join Hints ("+")', SUM(uses_directed_join) FROM feature_flags
UNION ALL
SELECT 'ASOF Join Used', SUM(uses_asof_join) FROM feature_flags
UNION ALL
SELECT 'Collation Used', SUM(uses_collation) FROM feature_flags
)
SELECT a.*
FROM aggr a
ORDER BY occurrence_count DESC
        """


        # Execute frequency query
        try:
            freq_df = session.sql(frequency_query).to_pandas()
        except Exception as e:
            # st.error(f"Error executing frequency query: {str(e)}")
            st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing frequency query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            freq_df = pd.DataFrame()

        if not freq_df.empty:
            # Create second expander with introduction text
            with st.expander("SQL Pattern Frequency Summary", expanded=True):
                # Introduction text without CSS styling
                st.markdown("SQL pattern frequency summary aggregating occurrences of advanced features and potential "
                           "inefficiencies (ASOF joins, collation, directed joins, CTE ordering, sort/aggregate, "
                           "heavy DISTINCT) from last 7 days.")


                # Create metric object for dialogs
                # Initialize or update metric object in session state


                # Display the dataframe
                st.dataframe(
                    df,
                    hide_index=True
                )

                # Charts Section
                st.markdown("---")
                st.markdown("#### Pattern Frequency Charts")

                # Row 1: Two charts
                freq_col1, freq_col2 = st.columns(2)

                with freq_col1.container(border=True):
                    st.markdown("##### Detection Type Occurrences")
                    _render_freq_occurrences_chart(freq_df, key_prefix="freq_occ_")

                with freq_col2.container(border=True):
                    st.markdown("##### Pattern Distribution")
                    _render_freq_distribution_chart(freq_df, key_prefix="freq_dist_")

                # Row 2: Two charts
                freq_col3, freq_col4 = st.columns(2)

                with freq_col3.container(border=True):
                    st.markdown("##### Inefficiency vs Feature Usage")
                    _render_freq_category_chart(freq_df, key_prefix="freq_cat_")

                with freq_col4.container(border=True):
                    st.markdown("##### Top Patterns by Frequency")
                    _render_freq_top_patterns_chart(freq_df, key_prefix="freq_top_")

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _prepare_pattern_summary(df):
    """Prepare summary data for pattern analysis charts."""
    summary = {
        'Pattern': ['ASOF Join', 'Collation', 'Directed Join', 'ORDER BY in CTE', 'Sort + Aggregate', 'DISTINCT Optimization'],
        'Count': [
            (df['USES_ASOF_JOIN'] == '✅ Yes').sum(),
            (df['USES_COLLATION'] == '✅ Yes').sum(),
            (df['USES_DIRECTED_JOIN'] == '✅ Yes').sum(),
            (df['ORDER_BY_IN_CTE'] == '✅ Yes').sum(),
            (df['SORT_AND_AGG'] == '✅ Yes').sum(),
            (df['DISTINCT_OPTIMIZATION_CHECK'] == '⚠️ Consider APPROX').sum()
        ]
    }
    return pd.DataFrame(summary)


# ============================
# Chart Type Selector & Charts
# ============================

def _render_pattern_usage_chart(df, key_prefix=""):
    """Render pattern usage chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_pattern_usage_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_pattern_usage_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_pattern_usage_donut_chart(df, key_prefix)
    else:
        _render_pattern_usage_rose_chart(df, key_prefix)


def _render_pattern_usage_bar_chart(df, key_prefix=""):
    """Render pattern usage bar chart using Plotly."""
    plot_df = df[df['Count'] > 0].sort_values('Count', ascending=True)

    if plot_df.empty:
        st.info("No patterns detected in the analyzed queries.")
        return

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['Pattern'],
            x=plot_df['Count'],
            orientation='h',
            marker_color='#1f77b4',
            text=[f"{int(val)}" for val in plot_df['Count']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Queries: %{x}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Number of Queries',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )


def _render_pattern_usage_pie_chart(df, key_prefix=""):
    """Render pattern usage pie chart using ECharts."""
    plot_df = df[df['Count'] > 0]

    if plot_df.empty:
        st.info("No patterns detected in the analyzed queries.")
        return

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Pattern']} ({int(row['Count'])})"}
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
            "name": "Pattern Usage",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_pattern_usage_donut_chart(df, key_prefix=""):
    """Render pattern usage donut chart using ECharts."""
    plot_df = df[df['Count'] > 0]

    if plot_df.empty:
        st.info("No patterns detected in the analyzed queries.")
        return

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Pattern']} ({int(row['Count'])})"}
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
            "name": "Pattern Usage",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_pattern_usage_rose_chart(df, key_prefix=""):
    """Render pattern usage rose chart using ECharts."""
    plot_df = df[df['Count'] > 0]

    if plot_df.empty:
        st.info("No patterns detected in the analyzed queries.")
        return

    chart_data = [
        {"value": int(row['Count']), "name": row['Pattern']}
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
            "name": "Pattern Usage",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_pattern_queries_chart(df, key_prefix=""):
    """Render pattern queries chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_pattern_queries_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_pattern_queries_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_pattern_queries_donut_chart(df, key_prefix)
    else:
        _render_pattern_queries_rose_chart(df, key_prefix)


def _render_pattern_queries_bar_chart(df, key_prefix=""):
    """Render pattern queries bar chart using Plotly."""
    # Show all patterns (including zeros)
    plot_df = df.sort_values('Count', ascending=True)

    colors = ['#2ca02c' if val > 0 else '#d3d3d3' for val in plot_df['Count']]

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['Pattern'],
            x=plot_df['Count'],
            orientation='h',
            marker_color=colors,
            text=[f"{int(val)}" for val in plot_df['Count']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Queries: %{x}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Number of Queries',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )


def _render_pattern_queries_pie_chart(df, key_prefix=""):
    """Render pattern queries pie chart using ECharts."""
    plot_df = df[df['Count'] > 0]

    if plot_df.empty:
        st.info("No patterns detected in the analyzed queries.")
        return

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Pattern']} ({int(row['Count'])})"}
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
        "color": ["#2ca02c", "#98df8a", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78"],
        "series": [{
            "name": "Pattern Queries",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_pattern_queries_donut_chart(df, key_prefix=""):
    """Render pattern queries donut chart using ECharts."""
    plot_df = df[df['Count'] > 0]

    if plot_df.empty:
        st.info("No patterns detected in the analyzed queries.")
        return

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Pattern']} ({int(row['Count'])})"}
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
        "color": ["#2ca02c", "#98df8a", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78"],
        "series": [{
            "name": "Pattern Queries",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_pattern_queries_rose_chart(df, key_prefix=""):
    """Render pattern queries rose chart using ECharts."""
    plot_df = df[df['Count'] > 0]

    if plot_df.empty:
        st.info("No patterns detected in the analyzed queries.")
        return

    chart_data = [
        {"value": int(row['Count']), "name": row['Pattern']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#2ca02c", "#98df8a", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78"],
        "series": [{
            "name": "Pattern Queries",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_distinct_optimization_chart(df, key_prefix=""):
    """Render DISTINCT optimization candidates chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_distinct_opt_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_distinct_opt_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_distinct_opt_donut_chart(df, key_prefix)
    else:
        _render_distinct_opt_rose_chart(df, key_prefix)


def _render_distinct_opt_bar_chart(df, key_prefix=""):
    """Render DISTINCT optimization bar chart using Plotly."""
    # Count candidates vs non-candidates
    candidates = (df['DISTINCT_OPTIMIZATION_CHECK'] == '⚠️ Consider APPROX').sum()
    non_candidates = len(df) - candidates

    categories = ['APPROX Candidates', 'No Optimization Needed']
    values = [candidates, non_candidates]
    colors = ['#ff7f0e', '#2ca02c']

    fig = go.Figure(data=[
        go.Bar(
            y=categories,
            x=values,
            orientation='h',
            marker_color=colors,
            text=[f"{int(val)}" for val in values],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Queries: %{x}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Number of Queries',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_distinct_opt_pie_chart(df, key_prefix=""):
    """Render DISTINCT optimization pie chart using ECharts."""
    candidates = (df['DISTINCT_OPTIMIZATION_CHECK'] == '⚠️ Consider APPROX').sum()
    non_candidates = len(df) - candidates

    chart_data = [
        {"value": int(candidates), "name": f"⚠️ APPROX Candidates ({candidates})"},
        {"value": int(non_candidates), "name": f"✅ No Optimization ({non_candidates})"}
    ]

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
        "color": ["#ff7f0e", "#2ca02c"],
        "series": [{
            "name": "DISTINCT Optimization",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_distinct_opt_donut_chart(df, key_prefix=""):
    """Render DISTINCT optimization donut chart using ECharts."""
    candidates = (df['DISTINCT_OPTIMIZATION_CHECK'] == '⚠️ Consider APPROX').sum()
    non_candidates = len(df) - candidates

    chart_data = [
        {"value": int(candidates), "name": f"⚠️ APPROX Candidates ({candidates})"},
        {"value": int(non_candidates), "name": f"✅ No Optimization ({non_candidates})"}
    ]

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
        "color": ["#ff7f0e", "#2ca02c"],
        "series": [{
            "name": "DISTINCT Optimization",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_distinct_opt_rose_chart(df, key_prefix=""):
    """Render DISTINCT optimization rose chart using ECharts."""
    candidates = (df['DISTINCT_OPTIMIZATION_CHECK'] == '⚠️ Consider APPROX').sum()
    non_candidates = len(df) - candidates

    chart_data = [
        {"value": int(candidates), "name": "APPROX Candidates"},
        {"value": int(non_candidates), "name": "No Optimization"}
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 12,
            "textStyle": {"fontSize": 10}
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
        "color": ["#ff7f0e", "#2ca02c"],
        "series": [{
            "name": "DISTINCT Optimization",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_pattern_summary_chart(df, key_prefix=""):
    """Render pattern summary chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_pattern_sum_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_pattern_sum_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_pattern_sum_donut_chart(df, key_prefix)
    else:
        _render_pattern_sum_rose_chart(df, key_prefix)


def _render_pattern_sum_bar_chart(df, key_prefix=""):
    """Render pattern summary bar chart using Plotly."""
    # Categorize patterns
    detected = df[df['Count'] > 0]['Count'].sum()
    not_detected = df[df['Count'] == 0].shape[0]

    categories = ['Patterns Detected', 'Patterns Not Found']
    values = [detected, not_detected]
    colors = ['#9467bd', '#d3d3d3']

    fig = go.Figure(data=[
        go.Bar(
            y=categories,
            x=values,
            orientation='h',
            marker_color=colors,
            text=[f"{int(val)}" for val in values],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Count',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )


def _render_pattern_sum_pie_chart(df, key_prefix=""):
    """Render pattern summary pie chart using ECharts."""
    detected = df[df['Count'] > 0]['Count'].sum()
    not_detected = df[df['Count'] == 0].shape[0]

    chart_data = [
        {"value": int(detected), "name": f"Patterns Detected ({detected})"},
        {"value": int(not_detected), "name": f"Patterns Not Found ({not_detected})"}
    ]

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
        "color": ["#9467bd", "#d3d3d3"],
        "series": [{
            "name": "Pattern Summary",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_pattern_sum_donut_chart(df, key_prefix=""):
    """Render pattern summary donut chart using ECharts."""
    detected = df[df['Count'] > 0]['Count'].sum()
    not_detected = df[df['Count'] == 0].shape[0]

    chart_data = [
        {"value": int(detected), "name": f"Patterns Detected ({detected})"},
        {"value": int(not_detected), "name": f"Patterns Not Found ({not_detected})"}
    ]

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
        "color": ["#9467bd", "#d3d3d3"],
        "series": [{
            "name": "Pattern Summary",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_pattern_sum_rose_chart(df, key_prefix=""):
    """Render pattern summary rose chart using ECharts."""
    detected = df[df['Count'] > 0]['Count'].sum()
    not_detected = df[df['Count'] == 0].shape[0]

    chart_data = [
        {"value": int(detected), "name": "Patterns Detected"},
        {"value": int(not_detected), "name": "Patterns Not Found"}
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 12,
            "textStyle": {"fontSize": 10}
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
        "color": ["#9467bd", "#d3d3d3"],
        "series": [{
            "name": "Pattern Summary",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


# ============================================================
# Charts for Second Expander: SQL Pattern Frequency Summary
# ============================================================

def _render_freq_occurrences_chart(df, key_prefix=""):
    """Render frequency occurrences chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_freq_occ_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_freq_occ_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_freq_occ_donut_chart(df, key_prefix)
    else:
        _render_freq_occ_rose_chart(df, key_prefix)


def _render_freq_occ_bar_chart(df, key_prefix=""):
    """Render frequency occurrences bar chart using Plotly."""
    plot_df = df.sort_values('OCCURRENCE_COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DETECTION_TYPE'],
            x=plot_df['OCCURRENCE_COUNT'],
            orientation='h',
            marker_color='#1f77b4',
            text=[f"{int(val):,}" for val in plot_df['OCCURRENCE_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Occurrences: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Occurrence Count',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=220, r=50)
    )


def _render_freq_occ_pie_chart(df, key_prefix=""):
    """Render frequency occurrences pie chart using ECharts."""
    plot_df = df[df['OCCURRENCE_COUNT'] > 0]

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": f"{row['DETECTION_TYPE']} ({int(row['OCCURRENCE_COUNT']):,})"}
        for _, row in plot_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
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
            "name": "Occurrences",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_freq_occ_donut_chart(df, key_prefix=""):
    """Render frequency occurrences donut chart using ECharts."""
    plot_df = df[df['OCCURRENCE_COUNT'] > 0]

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": f"{row['DETECTION_TYPE']} ({int(row['OCCURRENCE_COUNT']):,})"}
        for _, row in plot_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
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
            "name": "Occurrences",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_freq_occ_rose_chart(df, key_prefix=""):
    """Render frequency occurrences rose chart using ECharts."""
    plot_df = df[df['OCCURRENCE_COUNT'] > 0]

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": row['DETECTION_TYPE']}
        for _, row in plot_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "Occurrences",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}freq_occ_rose")


def _render_freq_distribution_chart(df, key_prefix=""):
    """Render frequency distribution chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_freq_dist_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_freq_dist_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_freq_dist_donut_chart(df, key_prefix)
    else:
        _render_freq_dist_rose_chart(df, key_prefix)


def _render_freq_dist_bar_chart(df, key_prefix=""):
    """Render frequency distribution bar chart using Plotly."""
    total = df['OCCURRENCE_COUNT'].sum()
    if total == 0:
        st.info("No patterns detected.")
        return

    plot_df = df.copy()
    plot_df['PERCENTAGE'] = ((plot_df['OCCURRENCE_COUNT'] / total) * 100).round(1)
    plot_df = plot_df.sort_values('PERCENTAGE', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DETECTION_TYPE'],
            x=plot_df['PERCENTAGE'],
            orientation='h',
            marker_color='#ff7f0e',
            text=[f"{val:.1f}%" for val in plot_df['PERCENTAGE']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Percentage: %{x:.1f}%<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Percentage of Total',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=220, r=50)
    )


def _render_freq_dist_pie_chart(df, key_prefix=""):
    """Render frequency distribution pie chart using ECharts."""
    plot_df = df[df['OCCURRENCE_COUNT'] > 0]

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": row['DETECTION_TYPE']}
        for _, row in plot_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"],
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


def _render_freq_dist_donut_chart(df, key_prefix=""):
    """Render frequency distribution donut chart using ECharts."""
    plot_df = df[df['OCCURRENCE_COUNT'] > 0]

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": row['DETECTION_TYPE']}
        for _, row in plot_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"],
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


def _render_freq_dist_rose_chart(df, key_prefix=""):
    """Render frequency distribution rose chart using ECharts."""
    plot_df = df[df['OCCURRENCE_COUNT'] > 0]

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": row['DETECTION_TYPE']}
        for _, row in plot_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"],
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

    st_echarts(options=option, height="400px", key=f"{key_prefix}freq_dist_rose")


def _render_freq_category_chart(df, key_prefix=""):
    """Render inefficiency vs feature usage chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_freq_cat_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_freq_cat_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_freq_cat_donut_chart(df, key_prefix)
    else:
        _render_freq_cat_rose_chart(df, key_prefix)


def _render_freq_cat_bar_chart(df, key_prefix=""):
    """Render category bar chart using Plotly."""
    # Categorize patterns into inefficiencies vs features
    inefficiency_patterns = ['Sort + Aggregate (Heavy Compute)', 'Order By inside CTE (Likely Redundant)', 'Heavy Distinct (>1GB Scanned)']
    feature_patterns = ['Directed Join Hints ("+")', 'ASOF Join Used', 'Collation Used']

    inefficiency_count = df[df['DETECTION_TYPE'].isin(inefficiency_patterns)]['OCCURRENCE_COUNT'].sum()
    feature_count = df[df['DETECTION_TYPE'].isin(feature_patterns)]['OCCURRENCE_COUNT'].sum()

    categories = ['⚠️ Potential Inefficiencies', '✅ Advanced Features']
    values = [inefficiency_count, feature_count]
    colors = ['#d62728', '#2ca02c']

    fig = go.Figure(data=[
        go.Bar(
            y=categories,
            x=values,
            orientation='h',
            marker_color=colors,
            text=[f"{int(val):,}" for val in values],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Occurrence Count',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_freq_cat_pie_chart(df, key_prefix=""):
    """Render category pie chart using ECharts."""
    inefficiency_patterns = ['Sort + Aggregate (Heavy Compute)', 'Order By inside CTE (Likely Redundant)', 'Heavy Distinct (>1GB Scanned)']
    feature_patterns = ['Directed Join Hints ("+")', 'ASOF Join Used', 'Collation Used']

    inefficiency_count = df[df['DETECTION_TYPE'].isin(inefficiency_patterns)]['OCCURRENCE_COUNT'].sum()
    feature_count = df[df['DETECTION_TYPE'].isin(feature_patterns)]['OCCURRENCE_COUNT'].sum()

    chart_data = [
        {"value": int(inefficiency_count), "name": f"⚠️ Potential Inefficiencies ({int(inefficiency_count):,})"},
        {"value": int(feature_count), "name": f"✅ Advanced Features ({int(feature_count):,})"}
    ]

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
        "color": ["#d62728", "#2ca02c"],
        "series": [{
            "name": "Category",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_freq_cat_donut_chart(df, key_prefix=""):
    """Render category donut chart using ECharts."""
    inefficiency_patterns = ['Sort + Aggregate (Heavy Compute)', 'Order By inside CTE (Likely Redundant)', 'Heavy Distinct (>1GB Scanned)']
    feature_patterns = ['Directed Join Hints ("+")', 'ASOF Join Used', 'Collation Used']

    inefficiency_count = df[df['DETECTION_TYPE'].isin(inefficiency_patterns)]['OCCURRENCE_COUNT'].sum()
    feature_count = df[df['DETECTION_TYPE'].isin(feature_patterns)]['OCCURRENCE_COUNT'].sum()

    chart_data = [
        {"value": int(inefficiency_count), "name": f"⚠️ Potential Inefficiencies ({int(inefficiency_count):,})"},
        {"value": int(feature_count), "name": f"✅ Advanced Features ({int(feature_count):,})"}
    ]

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
        "color": ["#d62728", "#2ca02c"],
        "series": [{
            "name": "Category",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_freq_cat_rose_chart(df, key_prefix=""):
    """Render category rose chart using ECharts."""
    inefficiency_patterns = ['Sort + Aggregate (Heavy Compute)', 'Order By inside CTE (Likely Redundant)', 'Heavy Distinct (>1GB Scanned)']
    feature_patterns = ['Directed Join Hints ("+")', 'ASOF Join Used', 'Collation Used']

    inefficiency_count = df[df['DETECTION_TYPE'].isin(inefficiency_patterns)]['OCCURRENCE_COUNT'].sum()
    feature_count = df[df['DETECTION_TYPE'].isin(feature_patterns)]['OCCURRENCE_COUNT'].sum()

    chart_data = [
        {"value": int(inefficiency_count), "name": "Potential Inefficiencies"},
        {"value": int(feature_count), "name": "Advanced Features"}
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 12,
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#d62728", "#2ca02c"],
        "series": [{
            "name": "Category",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}freq_cat_rose")


def _render_freq_top_patterns_chart(df, key_prefix=""):
    """Render top patterns chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_freq_top_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_freq_top_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_freq_top_donut_chart(df, key_prefix)
    else:
        _render_freq_top_rose_chart(df, key_prefix)


def _render_freq_top_bar_chart(df, key_prefix=""):
    """Render top patterns bar chart using Plotly."""
    # Top patterns by occurrence (already sorted by query)
    plot_df = df[df['OCCURRENCE_COUNT'] > 0].head(5).sort_values('OCCURRENCE_COUNT', ascending=True)

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DETECTION_TYPE'],
            x=plot_df['OCCURRENCE_COUNT'],
            orientation='h',
            marker_color='#9467bd',
            text=[f"{int(val):,}" for val in plot_df['OCCURRENCE_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Occurrences: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Occurrence Count',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=220, r=50)
    )


def _render_freq_top_pie_chart(df, key_prefix=""):
    """Render top patterns pie chart using ECharts."""
    plot_df = df[df['OCCURRENCE_COUNT'] > 0].head(5)

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": f"{row['DETECTION_TYPE']} ({int(row['OCCURRENCE_COUNT']):,})"}
        for _, row in plot_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
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
        "color": ["#9467bd", "#c5b0d5", "#1f77b4", "#aec7e8", "#ff7f0e"],
        "series": [{
            "name": "Top Patterns",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_freq_top_donut_chart(df, key_prefix=""):
    """Render top patterns donut chart using ECharts."""
    plot_df = df[df['OCCURRENCE_COUNT'] > 0].head(5)

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": f"{row['DETECTION_TYPE']} ({int(row['OCCURRENCE_COUNT']):,})"}
        for _, row in plot_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
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
        "color": ["#9467bd", "#c5b0d5", "#1f77b4", "#aec7e8", "#ff7f0e"],
        "series": [{
            "name": "Top Patterns",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_freq_top_rose_chart(df, key_prefix=""):
    """Render top patterns rose chart using ECharts."""
    plot_df = df[df['OCCURRENCE_COUNT'] > 0].head(5)

    if plot_df.empty:
        st.info("No patterns detected.")
        return

    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": row['DETECTION_TYPE']}
        for _, row in plot_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 8}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#9467bd", "#c5b0d5", "#1f77b4", "#aec7e8", "#ff7f0e"],
        "series": [{
            "name": "Top Patterns",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}freq_top_rose")

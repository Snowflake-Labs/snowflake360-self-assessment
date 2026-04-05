import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_echarts import st_echarts


def comp_problematic_query_report(entry_actions=None):
    """
    Problematic Query - Report (Native Insights) Component

    Provides query performance insights categorized by issue type.
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
    i.insight_type_id AS insight_code,
    -- Categorize for readability
    CASE
        WHEN i.insight_type_id ILIKE '%SPILL%' THEN '⚠️ Memory Pressure'
        WHEN i.insight_type_id ILIKE '%EXPLODING%' THEN '🔥 Cardinality Explosion'
        WHEN i.insight_type_id ILIKE '%FILTER%' OR i.insight_type_id ILIKE '%SCAN%' THEN '🔍 Pruning/Scanning Issues'
        WHEN i.insight_type_id ILIKE '%JOIN%' THEN '🔗 Join Logic Issues'
        WHEN i.insight_type_id ILIKE '%UNION%' OR i.insight_type_id ILIKE '%AGGREGATE%' THEN '🧮 Logic Inefficiency'
        WHEN i.insight_type_id ILIKE '%SEARCH_OPTIMIZATION%' THEN '⚡ Search Opt Opportunity'
        ELSE 'Other'
    END AS category,
    COUNT(*) AS occurrence_count,
    COUNT(DISTINCT i.query_id) AS distinct_queries,
    MAX(q.query_text) AS example_query
FROM SNOWFLAKE.ACCOUNT_USAGE.query_insights i
JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
    ON i.query_id = q.query_id
WHERE i.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY 3 DESC
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
                        '⚠️&nbsp;&nbsp;No query insights data found for the last 30 days.'
                        '</div>', unsafe_allow_html=True)
            return

        # Create expander with introduction text
        with st.expander("Query Performance Insights Analysis", expanded=True):
            # Introduction text without CSS styling
            st.markdown("Query performance insights categorized by issue type (memory pressure, cardinality explosions, "
                       "pruning, joins, etc.) with occurrence counts and example queries from last 30 days.")


            # Create metric object for dialogs
            # Initialize or update metric object in session state


            # Display the dataframe
            st.dataframe(
                df,
                hide_index=True
            )

            # Charts Section
            st.markdown("---")
            st.markdown("#### Query Insights Charts")

            # Row 1: Two charts
            col1, col2 = st.columns(2)

            with col1.container(border=True):
                st.markdown("##### Issue Occurrences by Category")
                _render_category_occurrences_chart(df, key_prefix="cat_occ_")

            with col2.container(border=True):
                st.markdown("##### Distinct Queries by Category")
                _render_distinct_queries_chart(df, key_prefix="dist_queries_")

            # Row 2: Two charts
            col3, col4 = st.columns(2)

            with col3.container(border=True):
                st.markdown("##### Top Insight Codes by Occurrence")
                _render_insight_codes_chart(df, key_prefix="insight_codes_")

            with col4.container(border=True):
                st.markdown("##### Category Distribution")
                _render_category_distribution_chart(df, key_prefix="cat_dist_")

        # ============================================================
        # Second Expander: Category Summary with Insight Codes
        # ============================================================

        # Build and execute the category summary query
        category_summary_query = f"""
SELECT
    -- 1. Define the Categories
    CASE
        WHEN insight_type_id ILIKE '%SPILL%' THEN '⚠️ Memory Pressure'
        WHEN insight_type_id ILIKE '%EXPLODING%' THEN '🔥 Cardinality Explosion'
        WHEN insight_type_id ILIKE '%FILTER%' OR insight_type_id ILIKE '%SCAN%' THEN '🔍 Pruning/Scanning Issues'
        WHEN insight_type_id ILIKE '%JOIN%' THEN '🔗 Join Logic Issues'
        WHEN insight_type_id ILIKE '%UNION%' OR insight_type_id ILIKE '%AGGREGATE%' THEN '🧮 Logic Inefficiency'
        WHEN insight_type_id ILIKE '%SEARCH_OPTIMIZATION%' THEN '⚡ Search Opt Opportunity'
        ELSE 'Other'
    END AS problem_category,

    -- 2. Aggregate the Counts
    COUNT(*) AS total_occurrences,
    COUNT(DISTINCT query_id) AS distinct_queries_affected,

    -- 3. List the specific codes caught in this bucket (for reference)
    ARRAY_AGG(DISTINCT insight_type_id) WITHIN GROUP (ORDER BY insight_type_id) AS specific_insight_codes

FROM SNOWFLAKE.ACCOUNT_USAGE.query_insights
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY 2 DESC
        """


        # Execute category summary query
        try:
            category_df = session.sql(category_summary_query).to_pandas()
        except Exception as e:
            # st.error(f"Error executing category summary query: {str(e)}")
            st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing category summary query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            category_df = pd.DataFrame()

        if not category_df.empty:
            # Create second expander with introduction text
            with st.expander("Category Summary with Insight Codes", expanded=True):
                # Introduction text without CSS styling
                st.markdown("Query insights aggregated by problem category with total occurrences, distinct affected queries, "
                           "and list of specific insight codes per category from last 30 days.")


                # Create metric object for dialogs
                # Initialize or update metric object in session state


                # Display the dataframe
                st.dataframe(
                    df,
                    hide_index=True
                )

                # Charts Section
                st.markdown("---")
                st.markdown("#### Category Summary Charts")

                # Row 1: Two charts
                cat_col1, cat_col2 = st.columns(2)

                with cat_col1.container(border=True):
                    st.markdown("##### Total Occurrences by Category")
                    _render_cat_summary_occurrences_chart(category_df, key_prefix="cat_sum_occ_")

                with cat_col2.container(border=True):
                    st.markdown("##### Distinct Queries Affected by Category")
                    _render_cat_summary_distinct_chart(category_df, key_prefix="cat_sum_dist_")

                # Row 2: Two charts
                cat_col3, cat_col4 = st.columns(2)

                with cat_col3.container(border=True):
                    st.markdown("##### Occurrences vs Distinct Queries")
                    _render_cat_summary_comparison_chart(category_df, key_prefix="cat_sum_comp_")

                with cat_col4.container(border=True):
                    st.markdown("##### Category Proportion")
                    _render_cat_summary_proportion_chart(category_df, key_prefix="cat_sum_prop_")

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ============================
# Chart Type Selector & Charts
# ============================

def _render_category_occurrences_chart(df, key_prefix=""):
    """Render category occurrences chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_category_occ_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_category_occ_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_category_occ_donut_chart(df, key_prefix)
    else:
        _render_category_occ_rose_chart(df, key_prefix)


def _render_category_occ_bar_chart(df, key_prefix=""):
    """Render category occurrences bar chart using Plotly."""
    # Aggregate by category
    agg_df = df.groupby('CATEGORY').agg({'OCCURRENCE_COUNT': 'sum'}).reset_index()
    agg_df = agg_df.sort_values('OCCURRENCE_COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=agg_df['CATEGORY'],
            x=agg_df['OCCURRENCE_COUNT'],
            orientation='h',
            marker_color='#1f77b4',
            text=[f"{int(val):,}" for val in agg_df['OCCURRENCE_COUNT']],
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
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_category_occ_pie_chart(df, key_prefix=""):
    """Render category occurrences pie chart using ECharts."""
    agg_df = df.groupby('CATEGORY').agg({'OCCURRENCE_COUNT': 'sum'}).reset_index()
    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": f"{row['CATEGORY']} ({int(row['OCCURRENCE_COUNT']):,})"}
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
            "name": "Occurrences",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_category_occ_donut_chart(df, key_prefix=""):
    """Render category occurrences donut chart using ECharts."""
    agg_df = df.groupby('CATEGORY').agg({'OCCURRENCE_COUNT': 'sum'}).reset_index()
    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": f"{row['CATEGORY']} ({int(row['OCCURRENCE_COUNT']):,})"}
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
            "name": "Occurrences",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_category_occ_rose_chart(df, key_prefix=""):
    """Render category occurrences rose chart using ECharts."""
    agg_df = df.groupby('CATEGORY').agg({'OCCURRENCE_COUNT': 'sum'}).reset_index()
    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": row['CATEGORY']}
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

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_distinct_queries_chart(df, key_prefix=""):
    """Render distinct queries by category chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_distinct_queries_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_distinct_queries_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_distinct_queries_donut_chart(df, key_prefix)
    else:
        _render_distinct_queries_rose_chart(df, key_prefix)


def _render_distinct_queries_bar_chart(df, key_prefix=""):
    """Render distinct queries bar chart using Plotly."""
    agg_df = df.groupby('CATEGORY').agg({'DISTINCT_QUERIES': 'sum'}).reset_index()
    agg_df = agg_df.sort_values('DISTINCT_QUERIES', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=agg_df['CATEGORY'],
            x=agg_df['DISTINCT_QUERIES'],
            orientation='h',
            marker_color='#ff7f0e',
            text=[f"{int(val):,}" for val in agg_df['DISTINCT_QUERIES']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Distinct Queries: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Distinct Query Count',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_distinct_queries_pie_chart(df, key_prefix=""):
    """Render distinct queries pie chart using ECharts."""
    agg_df = df.groupby('CATEGORY').agg({'DISTINCT_QUERIES': 'sum'}).reset_index()
    chart_data = [
        {"value": int(row['DISTINCT_QUERIES']), "name": f"{row['CATEGORY']} ({int(row['DISTINCT_QUERIES']):,})"}
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
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"],
        "series": [{
            "name": "Distinct Queries",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_distinct_queries_donut_chart(df, key_prefix=""):
    """Render distinct queries donut chart using ECharts."""
    agg_df = df.groupby('CATEGORY').agg({'DISTINCT_QUERIES': 'sum'}).reset_index()
    chart_data = [
        {"value": int(row['DISTINCT_QUERIES']), "name": f"{row['CATEGORY']} ({int(row['DISTINCT_QUERIES']):,})"}
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
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"],
        "series": [{
            "name": "Distinct Queries",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_distinct_queries_rose_chart(df, key_prefix=""):
    """Render distinct queries rose chart using ECharts."""
    agg_df = df.groupby('CATEGORY').agg({'DISTINCT_QUERIES': 'sum'}).reset_index()
    chart_data = [
        {"value": int(row['DISTINCT_QUERIES']), "name": row['CATEGORY']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"],
        "series": [{
            "name": "Distinct Queries",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_insight_codes_chart(df, key_prefix=""):
    """Render top insight codes chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_insight_codes_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_insight_codes_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_insight_codes_donut_chart(df, key_prefix)
    else:
        _render_insight_codes_rose_chart(df, key_prefix)


def _render_insight_codes_bar_chart(df, key_prefix=""):
    """Render insight codes bar chart using Plotly."""
    # Take top 10 insight codes
    plot_df = df.nlargest(10, 'OCCURRENCE_COUNT').sort_values('OCCURRENCE_COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['INSIGHT_CODE'],
            x=plot_df['OCCURRENCE_COUNT'],
            orientation='h',
            marker_color='#2ca02c',
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
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_insight_codes_pie_chart(df, key_prefix=""):
    """Render insight codes pie chart using ECharts."""
    plot_df = df.nlargest(10, 'OCCURRENCE_COUNT')
    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": f"{row['INSIGHT_CODE']} ({int(row['OCCURRENCE_COUNT']):,})"}
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
        "color": ["#2ca02c", "#98df8a", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#d62728", "#ff9896", "#9467bd", "#c5b0d5"],
        "series": [{
            "name": "Insight Codes",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_insight_codes_donut_chart(df, key_prefix=""):
    """Render insight codes donut chart using ECharts."""
    plot_df = df.nlargest(10, 'OCCURRENCE_COUNT')
    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": f"{row['INSIGHT_CODE']} ({int(row['OCCURRENCE_COUNT']):,})"}
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
        "color": ["#2ca02c", "#98df8a", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#d62728", "#ff9896", "#9467bd", "#c5b0d5"],
        "series": [{
            "name": "Insight Codes",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_insight_codes_rose_chart(df, key_prefix=""):
    """Render insight codes rose chart using ECharts."""
    plot_df = df.nlargest(10, 'OCCURRENCE_COUNT')
    chart_data = [
        {"value": int(row['OCCURRENCE_COUNT']), "name": row['INSIGHT_CODE']}
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
        "color": ["#2ca02c", "#98df8a", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#d62728", "#ff9896", "#9467bd", "#c5b0d5"],
        "series": [{
            "name": "Insight Codes",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_category_distribution_chart(df, key_prefix=""):
    """Render category distribution chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_category_dist_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_category_dist_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_category_dist_donut_chart(df, key_prefix)
    else:
        _render_category_dist_rose_chart(df, key_prefix)


def _render_category_dist_bar_chart(df, key_prefix=""):
    """Render category distribution bar chart using Plotly."""
    # Count unique insight codes per category
    agg_df = df.groupby('CATEGORY').agg({'INSIGHT_CODE': 'count'}).reset_index()
    agg_df.columns = ['CATEGORY', 'INSIGHT_CODE_COUNT']
    agg_df = agg_df.sort_values('INSIGHT_CODE_COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=agg_df['CATEGORY'],
            x=agg_df['INSIGHT_CODE_COUNT'],
            orientation='h',
            marker_color='#9467bd',
            text=[f"{int(val)}" for val in agg_df['INSIGHT_CODE_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Insight Types: %{x}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Number of Insight Types',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_category_dist_pie_chart(df, key_prefix=""):
    """Render category distribution pie chart using ECharts."""
    agg_df = df.groupby('CATEGORY').agg({'INSIGHT_CODE': 'count'}).reset_index()
    agg_df.columns = ['CATEGORY', 'INSIGHT_CODE_COUNT']

    chart_data = [
        {"value": int(row['INSIGHT_CODE_COUNT']), "name": f"{row['CATEGORY']} ({int(row['INSIGHT_CODE_COUNT'])})"}
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
        "color": ["#9467bd", "#c5b0d5", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c"],
        "series": [{
            "name": "Category Distribution",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_category_dist_donut_chart(df, key_prefix=""):
    """Render category distribution donut chart using ECharts."""
    agg_df = df.groupby('CATEGORY').agg({'INSIGHT_CODE': 'count'}).reset_index()
    agg_df.columns = ['CATEGORY', 'INSIGHT_CODE_COUNT']

    chart_data = [
        {"value": int(row['INSIGHT_CODE_COUNT']), "name": f"{row['CATEGORY']} ({int(row['INSIGHT_CODE_COUNT'])})"}
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
        "color": ["#9467bd", "#c5b0d5", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c"],
        "series": [{
            "name": "Category Distribution",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_category_dist_rose_chart(df, key_prefix=""):
    """Render category distribution rose chart using ECharts."""
    agg_df = df.groupby('CATEGORY').agg({'INSIGHT_CODE': 'count'}).reset_index()
    agg_df.columns = ['CATEGORY', 'INSIGHT_CODE_COUNT']

    chart_data = [
        {"value": int(row['INSIGHT_CODE_COUNT']), "name": row['CATEGORY']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} types ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#9467bd", "#c5b0d5", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c"],
        "series": [{
            "name": "Category Distribution",
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
# Charts for Second Expander: Category Summary with Insight Codes
# ============================================================

def _render_cat_summary_occurrences_chart(df, key_prefix=""):
    """Render category summary occurrences chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_cat_sum_occ_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_cat_sum_occ_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_cat_sum_occ_donut_chart(df, key_prefix)
    else:
        _render_cat_sum_occ_rose_chart(df, key_prefix)


def _render_cat_sum_occ_bar_chart(df, key_prefix=""):
    """Render category summary occurrences bar chart using Plotly."""
    plot_df = df.sort_values('TOTAL_OCCURRENCES', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['PROBLEM_CATEGORY'],
            x=plot_df['TOTAL_OCCURRENCES'],
            orientation='h',
            marker_color='#1f77b4',
            text=[f"{int(val):,}" for val in plot_df['TOTAL_OCCURRENCES']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Total Occurrences: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Total Occurrences',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_cat_sum_occ_pie_chart(df, key_prefix=""):
    """Render category summary occurrences pie chart using ECharts."""
    chart_data = [
        {"value": int(row['TOTAL_OCCURRENCES']), "name": f"{row['PROBLEM_CATEGORY']} ({int(row['TOTAL_OCCURRENCES']):,})"}
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
            "name": "Total Occurrences",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_cat_sum_occ_donut_chart(df, key_prefix=""):
    """Render category summary occurrences donut chart using ECharts."""
    chart_data = [
        {"value": int(row['TOTAL_OCCURRENCES']), "name": f"{row['PROBLEM_CATEGORY']} ({int(row['TOTAL_OCCURRENCES']):,})"}
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
            "name": "Total Occurrences",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_cat_sum_occ_rose_chart(df, key_prefix=""):
    """Render category summary occurrences rose chart using ECharts."""
    chart_data = [
        {"value": int(row['TOTAL_OCCURRENCES']), "name": row['PROBLEM_CATEGORY']}
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
            "name": "Total Occurrences",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_cat_summary_distinct_chart(df, key_prefix=""):
    """Render category summary distinct queries chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_cat_sum_dist_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_cat_sum_dist_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_cat_sum_dist_donut_chart(df, key_prefix)
    else:
        _render_cat_sum_dist_rose_chart(df, key_prefix)


def _render_cat_sum_dist_bar_chart(df, key_prefix=""):
    """Render category summary distinct queries bar chart using Plotly."""
    plot_df = df.sort_values('DISTINCT_QUERIES_AFFECTED', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['PROBLEM_CATEGORY'],
            x=plot_df['DISTINCT_QUERIES_AFFECTED'],
            orientation='h',
            marker_color='#ff7f0e',
            text=[f"{int(val):,}" for val in plot_df['DISTINCT_QUERIES_AFFECTED']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Distinct Queries: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Distinct Queries Affected',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_cat_sum_dist_pie_chart(df, key_prefix=""):
    """Render category summary distinct queries pie chart using ECharts."""
    chart_data = [
        {"value": int(row['DISTINCT_QUERIES_AFFECTED']), "name": f"{row['PROBLEM_CATEGORY']} ({int(row['DISTINCT_QUERIES_AFFECTED']):,})"}
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
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"],
        "series": [{
            "name": "Distinct Queries",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_cat_sum_dist_donut_chart(df, key_prefix=""):
    """Render category summary distinct queries donut chart using ECharts."""
    chart_data = [
        {"value": int(row['DISTINCT_QUERIES_AFFECTED']), "name": f"{row['PROBLEM_CATEGORY']} ({int(row['DISTINCT_QUERIES_AFFECTED']):,})"}
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
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"],
        "series": [{
            "name": "Distinct Queries",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_cat_sum_dist_rose_chart(df, key_prefix=""):
    """Render category summary distinct queries rose chart using ECharts."""
    chart_data = [
        {"value": int(row['DISTINCT_QUERIES_AFFECTED']), "name": row['PROBLEM_CATEGORY']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"],
        "series": [{
            "name": "Distinct Queries",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_cat_summary_comparison_chart(df, key_prefix=""):
    """Render category summary comparison chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_cat_sum_comp_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_cat_sum_comp_grouped_bar_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_cat_sum_comp_stacked_bar_chart(df, key_prefix)
    else:
        _render_cat_sum_comp_ratio_chart(df, key_prefix)


def _render_cat_sum_comp_bar_chart(df, key_prefix=""):
    """Render comparison grouped bar chart using Plotly."""
    plot_df = df.sort_values('TOTAL_OCCURRENCES', ascending=True)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=plot_df['PROBLEM_CATEGORY'],
        x=plot_df['TOTAL_OCCURRENCES'],
        orientation='h',
        name='Total Occurrences',
        marker_color='#1f77b4',
        text=[f"{int(val):,}" for val in plot_df['TOTAL_OCCURRENCES']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.add_trace(go.Bar(
        y=plot_df['PROBLEM_CATEGORY'],
        x=plot_df['DISTINCT_QUERIES_AFFECTED'],
        orientation='h',
        name='Distinct Queries',
        marker_color='#ff7f0e',
        text=[f"{int(val):,}" for val in plot_df['DISTINCT_QUERIES_AFFECTED']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.update_layout(
        height=400,
        xaxis_title='Count',
        yaxis_title='',
        barmode='group',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        margin=dict(t=40, b=50, l=180, r=50)
    )


def _render_cat_sum_comp_grouped_bar_chart(df, key_prefix=""):
    """Render comparison using vertical grouped bar chart."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df['PROBLEM_CATEGORY'],
        y=df['TOTAL_OCCURRENCES'],
        name='Total Occurrences',
        marker_color='#1f77b4',
        text=[f"{int(val):,}" for val in df['TOTAL_OCCURRENCES']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.add_trace(go.Bar(
        x=df['PROBLEM_CATEGORY'],
        y=df['DISTINCT_QUERIES_AFFECTED'],
        name='Distinct Queries',
        marker_color='#ff7f0e',
        text=[f"{int(val):,}" for val in df['DISTINCT_QUERIES_AFFECTED']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.update_layout(
        height=400,
        yaxis_title='Count',
        xaxis_title='',
        barmode='group',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        margin=dict(t=40, b=100, l=50, r=50),
        xaxis=dict(tickangle=45)
    )


def _render_cat_sum_comp_stacked_bar_chart(df, key_prefix=""):
    """Render comparison using stacked bar chart."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df['PROBLEM_CATEGORY'],
        y=df['DISTINCT_QUERIES_AFFECTED'],
        name='Distinct Queries',
        marker_color='#ff7f0e'
    ))

    fig.add_trace(go.Bar(
        x=df['PROBLEM_CATEGORY'],
        y=df['TOTAL_OCCURRENCES'] - df['DISTINCT_QUERIES_AFFECTED'],
        name='Repeat Occurrences',
        marker_color='#1f77b4'
    ))

    fig.update_layout(
        height=400,
        yaxis_title='Count',
        xaxis_title='',
        barmode='stack',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        margin=dict(t=40, b=100, l=50, r=50),
        xaxis=dict(tickangle=45)
    )


def _render_cat_sum_comp_ratio_chart(df, key_prefix=""):
    """Render occurrences per query ratio chart."""
    plot_df = df.copy()
    plot_df['RATIO'] = (plot_df['TOTAL_OCCURRENCES'] / plot_df['DISTINCT_QUERIES_AFFECTED']).round(2)
    plot_df = plot_df.sort_values('RATIO', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['PROBLEM_CATEGORY'],
            x=plot_df['RATIO'],
            orientation='h',
            marker_color='#2ca02c',
            text=[f"{val:.1f}x" for val in plot_df['RATIO']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Avg Occurrences per Query: %{x:.2f}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Avg Occurrences per Query',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_cat_summary_proportion_chart(df, key_prefix=""):
    """Render category proportion chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_cat_sum_prop_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_cat_sum_prop_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_cat_sum_prop_donut_chart(df, key_prefix)
    else:
        _render_cat_sum_prop_rose_chart(df, key_prefix)


def _render_cat_sum_prop_bar_chart(df, key_prefix=""):
    """Render category proportion bar chart using Plotly."""
    total = df['TOTAL_OCCURRENCES'].sum()
    plot_df = df.copy()
    plot_df['PERCENTAGE'] = ((plot_df['TOTAL_OCCURRENCES'] / total) * 100).round(1)
    plot_df = plot_df.sort_values('PERCENTAGE', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['PROBLEM_CATEGORY'],
            x=plot_df['PERCENTAGE'],
            orientation='h',
            marker_color='#9467bd',
            text=[f"{val:.1f}%" for val in plot_df['PERCENTAGE']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Proportion: %{x:.1f}%<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Percentage of Total',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_cat_sum_prop_pie_chart(df, key_prefix=""):
    """Render category proportion pie chart using ECharts."""
    chart_data = [
        {"value": int(row['TOTAL_OCCURRENCES']), "name": row['PROBLEM_CATEGORY']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#9467bd", "#c5b0d5", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c"],
        "series": [{
            "name": "Category Proportion",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "label": {"formatter": "{b}: {d}%"},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_cat_sum_prop_donut_chart(df, key_prefix=""):
    """Render category proportion donut chart using ECharts."""
    chart_data = [
        {"value": int(row['TOTAL_OCCURRENCES']), "name": row['PROBLEM_CATEGORY']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#9467bd", "#c5b0d5", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c"],
        "series": [{
            "name": "Category Proportion",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "label": {"formatter": "{b}: {d}%"},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_cat_sum_prop_rose_chart(df, key_prefix=""):
    """Render category proportion rose chart using ECharts."""
    chart_data = [
        {"value": int(row['TOTAL_OCCURRENCES']), "name": row['PROBLEM_CATEGORY']}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#9467bd", "#c5b0d5", "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c"],
        "series": [{
            "name": "Category Proportion",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")

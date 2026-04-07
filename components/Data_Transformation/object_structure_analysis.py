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


def comp_object_structure_analysis(entry_actions=None):
    """
    Object Structure Analysis (Stacked Views & Security) Component

    Analyzes object structures including stacked views and security configurations.
    Identifies deeply nested view stacks by tracing parent-child relationships.
    """
    try:
        st.markdown("### Object Structure Analysis (Stacked Views & Security)")

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

        # Build the recursive view dependency query
        view_dependency_query = f"""
WITH RECURSIVE view_lineage AS (
    -- Anchor: Base Views
    SELECT
        referencing_database || '.' || referencing_schema || '.' || referencing_object_name AS parent_view,
        referenced_database || '.' || referenced_schema || '.' || referenced_object_name AS child_object,
        1 AS depth
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies
    WHERE referencing_object_domain = 'VIEW'

    UNION ALL

    -- Recursive Step: Find views that reference the previous level
    SELECT
        od.referencing_database || '.' || od.referencing_schema || '.' || od.referencing_object_name,
        vl.child_object,
        vl.depth + 1
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies od
    JOIN view_lineage vl
        ON od.referenced_database || '.' || od.referenced_schema || '.' || od.referenced_object_name = vl.parent_view
    WHERE vl.depth < 10 -- Safety limit
)
SELECT
    parent_view AS root_view,
    MAX(depth) AS max_depth
FROM view_lineage
GROUP BY parent_view
HAVING MAX(depth) > 2 -- Show only "Deep" stacks
ORDER BY max_depth DESC
        """


        # Execute the query
        try:
            df = _cached_sql("tf_view_dependency", view_dependency_query)
        except Exception as e:
            # st.error(f"Error executing query: {str(e)}")
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            df = pd.DataFrame()

        # Create expander with introduction text
        with st.expander("View Dependency Analysis", expanded=True):
            # Introduction text without CSS styling
            st.markdown("Recursive view dependency analysis identifying deeply nested view stacks (depth > 2) "
                       "by tracing parent-child relationships up to 10 levels.")

            if df.empty:
                # st.info("No deeply nested view stacks (depth > 2) found in the current account.")
                st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No deeply nested view stacks (depth > 2) found in the current account.'
                    '</div>', unsafe_allow_html=True)

            else:

                # Create metric object for dialogs
                # Initialize or update metric object in session state


                # Display the dataframe
                st.dataframe(
                    df,
                )

                # Charts Section
                st.markdown("---")
                st.markdown("#### View Dependency Charts")

                # Prepare data for charts
                chart_df = df[['ROOT_VIEW', 'MAX_DEPTH']].copy()

                # Row 1: Two charts
                col1, col2 = st.columns(2)

                with col1.container():
                    st.markdown("##### Top Views by Nesting Depth")
                    _render_depth_chart(chart_df, key_prefix="depth_")

                with col2.container():
                    st.markdown("##### Depth Distribution")
                    _render_depth_distribution_chart(chart_df, key_prefix="depth_dist_")

                # Row 2: Two charts
                col3, col4 = st.columns(2)

                with col3.container():
                    st.markdown("##### Views by Depth Category")
                    _render_depth_category_chart(chart_df, key_prefix="depth_cat_")

                with col4.container():
                    st.markdown("##### Complexity Summary")
                    _render_complexity_summary_chart(chart_df, key_prefix="complexity_")

        # ============================================================
        # Second Expander: Object Lifecycle & Security Analysis
        # ============================================================

        # Build the object lifecycle query (with LIMIT to prevent MessageSizeError)
        lifecycle_query = f"""
WITH lifecycle_data AS (
    SELECT
        table_name AS object_name,
        table_type,
        'NO' AS is_secure,
        CASE
            WHEN table_type = 'TEMPORARY' THEN '✅ Temp Table'
            WHEN deleted IS NOT NULL AND DATEDIFF('minute', created, deleted) < 60 THEN '⚠️ Short-Lived (Non-Temp)'
            ELSE 'Standard'
        END AS lifespan_check
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE (deleted IS NOT NULL OR table_type = 'TEMPORARY')

    UNION ALL

    SELECT
        table_name AS object_name,
        'VIEW' AS table_type,
        is_secure,
        'Standard' AS lifespan_check
    FROM SNOWFLAKE.ACCOUNT_USAGE.views
    WHERE is_secure = 'YES'
)
SELECT * FROM lifecycle_data
ORDER BY lifespan_check, table_type, object_name
LIMIT 5000
        """


        # Execute the query
        try:
            lifecycle_df = _cached_sql("tf_lifecycle", lifecycle_query)
        except Exception as e:
            # st.error(f"Error executing lifecycle query: {str(e)}")
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing lifecycle query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            lifecycle_df = pd.DataFrame()

        # Create second expander with introduction text
        with st.expander("Object Lifecycle & Security Analysis", expanded=True):
            # Introduction text without CSS styling
            st.markdown("Object lifecycle and security analysis identifying temporary tables, short-lived "
                       "non-temp tables (< 60 min lifespan), and secure views.")

            if lifecycle_df.empty:
                st.info("No temporary tables, short-lived tables, or secure views found in the current account.")
            else:
                # Show row count and limit notice if applicable
                row_count = len(lifecycle_df)
                if row_count >= 5000:
                    st.caption(f"📊 Showing top 5,000 records (data limited to prevent browser memory issues)")
                else:
                    st.caption(f"📊 Total records: {row_count:,}")

                # Create metric object for dialogs
                # Initialize or update metric object in session state


                # Display the dataframe
                st.dataframe(
                    df,
                )

                # Charts Section
                st.markdown("---")
                st.markdown("#### Object Lifecycle & Security Charts")

                # Row 1: Two charts
                lc_col1, lc_col2 = st.columns(2)

                with lc_col1.container():
                    st.markdown("##### Object Type Distribution")
                    _render_lifecycle_type_chart(lifecycle_df, key_prefix="lc_type_")

                with lc_col2.container():
                    st.markdown("##### Lifespan Analysis")
                    _render_lifecycle_lifespan_chart(lifecycle_df, key_prefix="lc_lifespan_")

                # Row 2: Two charts
                lc_col3, lc_col4 = st.columns(2)

                with lc_col3.container():
                    st.markdown("##### Secure vs Non-Secure Objects")
                    _render_lifecycle_security_chart(lifecycle_df, key_prefix="lc_security_")

                with lc_col4.container():
                    st.markdown("##### Object Summary")
                    _render_lifecycle_summary_chart(lifecycle_df, key_prefix="lc_summary_")

        # ============================================================
        # Third Expander: Object Structure Summary
        # ============================================================

        # Build the combined analysis query
        summary_query = f"""
WITH RECURSIVE view_lineage AS (
    -- 1. STACKED VIEW DETECTION
    -- Anchor: Base Views
    SELECT
        referencing_database || '.' || referencing_schema || '.' || referencing_object_name AS parent_view,
        referenced_database || '.' || referenced_schema || '.' || referenced_object_name AS child_object,
        1 AS depth
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies
    WHERE referencing_object_domain = 'VIEW'

    UNION ALL

    -- Recursive Step
    SELECT
        od.referencing_database || '.' || od.referencing_schema || '.' || od.referencing_object_name,
        vl.child_object,
        vl.depth + 1
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies od
    JOIN view_lineage vl
        ON od.referenced_database || '.' || od.referenced_schema || '.' || od.referenced_object_name = vl.parent_view
    WHERE vl.depth < 10
),
view_depth_stats AS (
    SELECT
        parent_view,
        MAX(depth) AS max_depth
    FROM view_lineage
    GROUP BY 1
),
lifecycle_stats AS (
    -- 2. OBJECT LIFECYCLE (Temp, Short-Lived, Secure)
    SELECT
        CASE
            WHEN table_type = 'TEMPORARY' THEN 'Temporary Tables (Session Scope)'
            WHEN deleted IS NOT NULL AND DATEDIFF('minute', created, deleted) < 60 THEN 'Short-Lived Tables (<1hr)'
            ELSE NULL
        END AS category
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE (deleted IS NOT NULL OR table_type = 'TEMPORARY')

    UNION ALL

    SELECT
        'Secure Views' AS category
    FROM SNOWFLAKE.ACCOUNT_USAGE.views
    WHERE is_secure = 'YES'
)

-- 3. FINAL AGGREGATION
SELECT
    'Stacked Views (Depth 3-5)' AS metric_name,
    COUNT(*) AS count_objects
FROM view_depth_stats
WHERE max_depth BETWEEN 3 AND 5

UNION ALL

SELECT
    'Stacked Views (Depth > 5)',
    COUNT(*)
FROM view_depth_stats
WHERE max_depth > 5

UNION ALL

SELECT
    category,
    COUNT(*)
FROM lifecycle_stats
WHERE category IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
        """


        # Execute the query
        try:
            summary_df = _cached_sql("tf_summary", summary_query)
        except Exception as e:
            # st.error(f"Error executing summary query: {str(e)}")
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing summary query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            summary_df = pd.DataFrame()

        # Create third expander with introduction text
        with st.expander("Object Structure Summary", expanded=True):
            # Introduction text without CSS styling
            st.markdown("Consolidated object structure metrics combining stacked view depth analysis "
                       "(3-5 levels vs >5 levels), temporary tables, short-lived tables (<1hr lifespan), "
                       "and secure views into a single summary view.")

            if summary_df.empty:
                st.info("No object structure metrics found in the current account.")
            else:

                # Create metric object for dialogs
                # Initialize or update metric object in session state


                # Display the dataframe
                st.dataframe(
                    df,
                )

                # Charts Section
                st.markdown("---")
                st.markdown("#### Object Structure Summary Charts")

                # Row 1: Two charts
                sum_col1, sum_col2 = st.columns(2)

                with sum_col1.container():
                    st.markdown("##### Metrics by Count")
                    _render_obj_summary_count_chart(summary_df, key_prefix="obj_sum_count_")

                with sum_col2.container():
                    st.markdown("##### Metrics Distribution")
                    _render_obj_summary_distribution_chart(summary_df, key_prefix="obj_sum_dist_")

                # Row 2: Two charts
                sum_col3, sum_col4 = st.columns(2)

                with sum_col3.container():
                    st.markdown("##### View Depth vs Lifecycle Objects")
                    _render_obj_summary_category_chart(summary_df, key_prefix="obj_sum_cat_")

                with sum_col4.container():
                    st.markdown("##### Top Metrics")
                    _render_obj_summary_top_chart(summary_df, key_prefix="obj_sum_top_")

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ============================================================
# Chart Rendering Functions
# ============================================================

def _render_depth_chart(df, key_prefix=""):
    """Render top views by nesting depth chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_depth_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_depth_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_depth_donut_chart(df, key_prefix)
    else:
        _render_depth_rose_chart(df, key_prefix)


def _render_depth_bar_chart(df, key_prefix=""):
    """Render depth bar chart using Plotly."""
    # Get top 10 views by depth
    plot_df = df.nlargest(10, 'MAX_DEPTH').sort_values('MAX_DEPTH', ascending=True)

    # Truncate view names for display
    plot_df['DISPLAY_NAME'] = plot_df['ROOT_VIEW'].apply(lambda x: x[-50:] if len(x) > 50 else x)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DISPLAY_NAME'],
            x=plot_df['MAX_DEPTH'],
            orientation='h',
            marker_color='#29B5E8',
            text=[f"{int(val)}" for val in plot_df['MAX_DEPTH']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{customdata}</b><br>Depth: %{x}<extra></extra>',
            customdata=plot_df['ROOT_VIEW']
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Nesting Depth',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_depth_pie_chart(df, key_prefix=""):
    """Render depth pie chart using ECharts."""
    # Get top 10 views
    plot_df = df.nlargest(10, 'MAX_DEPTH')

    chart_data = [
        {"value": int(row['MAX_DEPTH']), "name": f"{row['ROOT_VIEW'].split('.')[-1]} (Depth: {int(row['MAX_DEPTH'])})"}
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
            "name": "View Depth",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_depth_donut_chart(df, key_prefix=""):
    """Render depth donut chart using ECharts."""
    plot_df = df.nlargest(10, 'MAX_DEPTH')

    chart_data = [
        {"value": int(row['MAX_DEPTH']), "name": f"{row['ROOT_VIEW'].split('.')[-1]} (Depth: {int(row['MAX_DEPTH'])})"}
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
            "name": "View Depth",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_depth_rose_chart(df, key_prefix=""):
    """Render depth rose chart using ECharts."""
    plot_df = df.nlargest(10, 'MAX_DEPTH')

    chart_data = [
        {"value": int(row['MAX_DEPTH']), "name": row['ROOT_VIEW'].split('.')[-1]}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} levels ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "View Depth",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


def _render_depth_distribution_chart(df, key_prefix=""):
    """Render depth distribution chart with selectable chart types."""
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
    # Group by depth level
    depth_counts = df.groupby('MAX_DEPTH').size().reset_index(name='COUNT')
    depth_counts = depth_counts.sort_values('MAX_DEPTH')
    depth_counts['DEPTH_LABEL'] = depth_counts['MAX_DEPTH'].apply(lambda x: f"Depth {int(x)}")

    fig = go.Figure(data=[
        go.Bar(
            x=depth_counts['DEPTH_LABEL'],
            y=depth_counts['COUNT'],
            marker_color='#E8A229',
            text=[f"{int(val)}" for val in depth_counts['COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Views: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Nesting Depth Level',
        yaxis_title='Number of Views',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=50)
    )


def _render_dist_pie_chart(df, key_prefix=""):
    """Render distribution pie chart using ECharts."""
    depth_counts = df.groupby('MAX_DEPTH').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": f"Depth {int(row['MAX_DEPTH'])} ({int(row['COUNT'])} views)"}
        for _, row in depth_counts.iterrows()
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
        "color": ["#E8A229", "#27AE60", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#666666", "#E8A229"],
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


def _render_dist_donut_chart(df, key_prefix=""):
    """Render distribution donut chart using ECharts."""
    depth_counts = df.groupby('MAX_DEPTH').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": f"Depth {int(row['MAX_DEPTH'])} ({int(row['COUNT'])} views)"}
        for _, row in depth_counts.iterrows()
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
        "color": ["#E8A229", "#27AE60", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#666666", "#E8A229"],
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


def _render_dist_rose_chart(df, key_prefix=""):
    """Render distribution rose chart using ECharts."""
    depth_counts = df.groupby('MAX_DEPTH').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": f"Depth {int(row['MAX_DEPTH'])}"}
        for _, row in depth_counts.iterrows()
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} views ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#E8A229", "#27AE60", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#666666", "#E8A229"],
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

    st_echarts(options=option, height="400px", key=f"{key_prefix}dist_rose")


def _render_depth_category_chart(df, key_prefix=""):
    """Render depth category chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_cat_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_cat_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_cat_donut_chart(df, key_prefix)
    else:
        _render_cat_rose_chart(df, key_prefix)


def _render_cat_bar_chart(df, key_prefix=""):
    """Render category bar chart using Plotly."""
    # Categorize by depth ranges
    def categorize_depth(depth):
        if depth <= 3:
            return "🟢 Moderate (3)"
        elif depth <= 5:
            return "🟡 Deep (4-5)"
        elif depth <= 7:
            return "🟠 Very Deep (6-7)"
        else:
            return "🔴 Critical (8+)"

    df_cat = df.copy()
    df_cat['CATEGORY'] = df_cat['MAX_DEPTH'].apply(categorize_depth)
    category_counts = df_cat.groupby('CATEGORY').size().reset_index(name='COUNT')

    # Sort by severity
    category_order = ["🟢 Moderate (3)", "🟡 Deep (4-5)", "🟠 Very Deep (6-7)", "🔴 Critical (8+)"]
    category_counts['SORT_ORDER'] = category_counts['CATEGORY'].apply(lambda x: category_order.index(x) if x in category_order else 99)
    category_counts = category_counts.sort_values('SORT_ORDER')

    colors = ['#27AE60', '#E8A229', '#E8A229', '#E74C3C']
    color_map = {cat: colors[i] for i, cat in enumerate(category_order)}
    bar_colors = [color_map.get(cat, '#29B5E8') for cat in category_counts['CATEGORY']]

    fig = go.Figure(data=[
        go.Bar(
            x=category_counts['CATEGORY'],
            y=category_counts['COUNT'],
            marker_color=bar_colors,
            text=[f"{int(val)}" for val in category_counts['COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Views: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Depth Category',
        yaxis_title='Number of Views',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=50)
    )


def _render_cat_pie_chart(df, key_prefix=""):
    """Render category pie chart using ECharts."""
    def categorize_depth(depth):
        if depth <= 3:
            return "🟢 Moderate (3)"
        elif depth <= 5:
            return "🟡 Deep (4-5)"
        elif depth <= 7:
            return "🟠 Very Deep (6-7)"
        else:
            return "🔴 Critical (8+)"

    df_cat = df.copy()
    df_cat['CATEGORY'] = df_cat['MAX_DEPTH'].apply(categorize_depth)
    category_counts = df_cat.groupby('CATEGORY').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": f"{row['CATEGORY']} ({int(row['COUNT'])} views)"}
        for _, row in category_counts.iterrows()
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
        "color": ["#27AE60", "#E8A229", "#E8A229", "#E74C3C"],
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


def _render_cat_donut_chart(df, key_prefix=""):
    """Render category donut chart using ECharts."""
    def categorize_depth(depth):
        if depth <= 3:
            return "🟢 Moderate (3)"
        elif depth <= 5:
            return "🟡 Deep (4-5)"
        elif depth <= 7:
            return "🟠 Very Deep (6-7)"
        else:
            return "🔴 Critical (8+)"

    df_cat = df.copy()
    df_cat['CATEGORY'] = df_cat['MAX_DEPTH'].apply(categorize_depth)
    category_counts = df_cat.groupby('CATEGORY').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": f"{row['CATEGORY']} ({int(row['COUNT'])} views)"}
        for _, row in category_counts.iterrows()
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
        "color": ["#27AE60", "#E8A229", "#E8A229", "#E74C3C"],
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


def _render_cat_rose_chart(df, key_prefix=""):
    """Render category rose chart using ECharts."""
    def categorize_depth(depth):
        if depth <= 3:
            return "Moderate (3)"
        elif depth <= 5:
            return "Deep (4-5)"
        elif depth <= 7:
            return "Very Deep (6-7)"
        else:
            return "Critical (8+)"

    df_cat = df.copy()
    df_cat['CATEGORY'] = df_cat['MAX_DEPTH'].apply(categorize_depth)
    category_counts = df_cat.groupby('CATEGORY').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": row['CATEGORY']}
        for _, row in category_counts.iterrows()
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} views ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#27AE60", "#E8A229", "#E8A229", "#E74C3C"],
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

    st_echarts(options=option, height="400px", key=f"{key_prefix}cat_rose")


def _render_complexity_summary_chart(df, key_prefix=""):
    """Render complexity summary chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_summary_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_summary_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_summary_donut_chart(df, key_prefix)
    else:
        _render_summary_rose_chart(df, key_prefix)


def _render_summary_bar_chart(df, key_prefix=""):
    """Render summary bar chart using Plotly."""
    # Calculate summary metrics
    total_views = len(df)
    max_depth = df['MAX_DEPTH'].max()
    avg_depth = df['MAX_DEPTH'].mean()
    critical_views = (df['MAX_DEPTH'] >= 8).sum()

    metrics = ['Total Deep Views', 'Max Depth', 'Avg Depth', 'Critical (8+)']
    values = [total_views, max_depth, round(avg_depth, 1), critical_views]
    colors = ['#29B5E8', '#E8A229', '#27AE60', '#E74C3C']

    fig = go.Figure(data=[
        go.Bar(
            x=metrics,
            y=values,
            marker_color=colors,
            text=[f"{val}" for val in values],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Value: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Metric',
        yaxis_title='Value',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=50)
    )


def _render_summary_pie_chart(df, key_prefix=""):
    """Render summary pie chart using ECharts."""
    # Group into complexity levels
    low = (df['MAX_DEPTH'] <= 4).sum()
    medium = ((df['MAX_DEPTH'] > 4) & (df['MAX_DEPTH'] <= 6)).sum()
    high = (df['MAX_DEPTH'] > 6).sum()

    chart_data = [
        {"value": int(low), "name": f"Low Complexity ({low})"},
        {"value": int(medium), "name": f"Medium Complexity ({medium})"},
        {"value": int(high), "name": f"High Complexity ({high})"}
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
        "color": ["#27AE60", "#E8A229", "#E74C3C"],
        "series": [{
            "name": "Complexity",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_summary_donut_chart(df, key_prefix=""):
    """Render summary donut chart using ECharts."""
    low = (df['MAX_DEPTH'] <= 4).sum()
    medium = ((df['MAX_DEPTH'] > 4) & (df['MAX_DEPTH'] <= 6)).sum()
    high = (df['MAX_DEPTH'] > 6).sum()

    chart_data = [
        {"value": int(low), "name": f"Low Complexity ({low})"},
        {"value": int(medium), "name": f"Medium Complexity ({medium})"},
        {"value": int(high), "name": f"High Complexity ({high})"}
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
        "color": ["#27AE60", "#E8A229", "#E74C3C"],
        "series": [{
            "name": "Complexity",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_summary_rose_chart(df, key_prefix=""):
    """Render summary rose chart using ECharts."""
    low = (df['MAX_DEPTH'] <= 4).sum()
    medium = ((df['MAX_DEPTH'] > 4) & (df['MAX_DEPTH'] <= 6)).sum()
    high = (df['MAX_DEPTH'] > 6).sum()

    chart_data = [
        {"value": int(low), "name": "Low Complexity"},
        {"value": int(medium), "name": "Medium Complexity"},
        {"value": int(high), "name": "High Complexity"}
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
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} views ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#27AE60", "#E8A229", "#E74C3C"],
        "series": [{
            "name": "Complexity",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}summary_rose")


# ============================================================
# Charts for Second Expander: Object Lifecycle & Security Analysis
# ============================================================

def _render_lifecycle_type_chart(df, key_prefix=""):
    """Render object type distribution chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_lc_type_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_lc_type_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_lc_type_donut_chart(df, key_prefix)
    else:
        _render_lc_type_rose_chart(df, key_prefix)


def _render_lc_type_bar_chart(df, key_prefix=""):
    """Render object type bar chart using Plotly."""
    type_counts = df.groupby('TABLE_TYPE').size().reset_index(name='COUNT')
    type_counts = type_counts.sort_values('COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=type_counts['TABLE_TYPE'],
            x=type_counts['COUNT'],
            orientation='h',
            marker_color='#29B5E8',
            text=[f"{int(val)}" for val in type_counts['COUNT']],
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
        margin=dict(t=20, b=50, l=120, r=50)
    )


def _render_lc_type_pie_chart(df, key_prefix=""):
    """Render object type pie chart using ECharts."""
    type_counts = df.groupby('TABLE_TYPE').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": f"{row['TABLE_TYPE']} ({int(row['COUNT'])})"}
        for _, row in type_counts.iterrows()
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
        "color": ["#29B5E8", "#E8A229", "#27AE60", "#E74C3C", "#0077B6"],
        "series": [{
            "name": "Object Type",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_lc_type_donut_chart(df, key_prefix=""):
    """Render object type donut chart using ECharts."""
    type_counts = df.groupby('TABLE_TYPE').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": f"{row['TABLE_TYPE']} ({int(row['COUNT'])})"}
        for _, row in type_counts.iterrows()
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
        "color": ["#29B5E8", "#E8A229", "#27AE60", "#E74C3C", "#0077B6"],
        "series": [{
            "name": "Object Type",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_lc_type_rose_chart(df, key_prefix=""):
    """Render object type rose chart using ECharts."""
    type_counts = df.groupby('TABLE_TYPE').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": row['TABLE_TYPE']}
        for _, row in type_counts.iterrows()
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
        "color": ["#29B5E8", "#E8A229", "#27AE60", "#E74C3C", "#0077B6"],
        "series": [{
            "name": "Object Type",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}lc_type_rose")


def _render_lifecycle_lifespan_chart(df, key_prefix=""):
    """Render lifespan analysis chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_lc_lifespan_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_lc_lifespan_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_lc_lifespan_donut_chart(df, key_prefix)
    else:
        _render_lc_lifespan_rose_chart(df, key_prefix)


def _render_lc_lifespan_bar_chart(df, key_prefix=""):
    """Render lifespan bar chart using Plotly."""
    lifespan_counts = df.groupby('LIFESPAN_CHECK').size().reset_index(name='COUNT')
    lifespan_counts = lifespan_counts.sort_values('COUNT', ascending=True)

    # Color mapping
    color_map = {
        '✅ Temp Table': '#27AE60',
        '⚠️ Short-Lived (Non-Temp)': '#E8A229',
        'Standard': '#29B5E8'
    }
    colors = [color_map.get(val, '#29B5E8') for val in lifespan_counts['LIFESPAN_CHECK']]

    fig = go.Figure(data=[
        go.Bar(
            y=lifespan_counts['LIFESPAN_CHECK'],
            x=lifespan_counts['COUNT'],
            orientation='h',
            marker_color=colors,
            text=[f"{int(val)}" for val in lifespan_counts['COUNT']],
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
        margin=dict(t=20, b=50, l=180, r=50)
    )


def _render_lc_lifespan_pie_chart(df, key_prefix=""):
    """Render lifespan pie chart using ECharts."""
    lifespan_counts = df.groupby('LIFESPAN_CHECK').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": f"{row['LIFESPAN_CHECK']} ({int(row['COUNT'])})"}
        for _, row in lifespan_counts.iterrows()
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
        "color": ["#27AE60", "#E8A229", "#29B5E8"],
        "series": [{
            "name": "Lifespan",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_lc_lifespan_donut_chart(df, key_prefix=""):
    """Render lifespan donut chart using ECharts."""
    lifespan_counts = df.groupby('LIFESPAN_CHECK').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": f"{row['LIFESPAN_CHECK']} ({int(row['COUNT'])})"}
        for _, row in lifespan_counts.iterrows()
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
        "color": ["#27AE60", "#E8A229", "#29B5E8"],
        "series": [{
            "name": "Lifespan",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_lc_lifespan_rose_chart(df, key_prefix=""):
    """Render lifespan rose chart using ECharts."""
    lifespan_counts = df.groupby('LIFESPAN_CHECK').size().reset_index(name='COUNT')

    chart_data = [
        {"value": int(row['COUNT']), "name": row['LIFESPAN_CHECK']}
        for _, row in lifespan_counts.iterrows()
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
        "color": ["#27AE60", "#E8A229", "#29B5E8"],
        "series": [{
            "name": "Lifespan",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}lc_lifespan_rose")


def _render_lifecycle_security_chart(df, key_prefix=""):
    """Render secure vs non-secure chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_lc_security_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_lc_security_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_lc_security_donut_chart(df, key_prefix)
    else:
        _render_lc_security_rose_chart(df, key_prefix)


def _render_lc_security_bar_chart(df, key_prefix=""):
    """Render security bar chart using Plotly."""
    secure_count = (df['IS_SECURE'] == 'YES').sum()
    non_secure_count = (df['IS_SECURE'] == 'NO').sum()

    categories = ['🔒 Secure', '🔓 Non-Secure']
    values = [secure_count, non_secure_count]
    colors = ['#27AE60', '#E74C3C']

    fig = go.Figure(data=[
        go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f"{int(val)}" for val in values],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Security Status',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=50)
    )


def _render_lc_security_pie_chart(df, key_prefix=""):
    """Render security pie chart using ECharts."""
    secure_count = (df['IS_SECURE'] == 'YES').sum()
    non_secure_count = (df['IS_SECURE'] == 'NO').sum()

    chart_data = [
        {"value": int(secure_count), "name": f"🔒 Secure ({int(secure_count)})"},
        {"value": int(non_secure_count), "name": f"🔓 Non-Secure ({int(non_secure_count)})"}
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
        "color": ["#27AE60", "#E74C3C"],
        "series": [{
            "name": "Security",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_lc_security_donut_chart(df, key_prefix=""):
    """Render security donut chart using ECharts."""
    secure_count = (df['IS_SECURE'] == 'YES').sum()
    non_secure_count = (df['IS_SECURE'] == 'NO').sum()

    chart_data = [
        {"value": int(secure_count), "name": f"🔒 Secure ({int(secure_count)})"},
        {"value": int(non_secure_count), "name": f"🔓 Non-Secure ({int(non_secure_count)})"}
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
        "color": ["#27AE60", "#E74C3C"],
        "series": [{
            "name": "Security",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_lc_security_rose_chart(df, key_prefix=""):
    """Render security rose chart using ECharts."""
    secure_count = (df['IS_SECURE'] == 'YES').sum()
    non_secure_count = (df['IS_SECURE'] == 'NO').sum()

    chart_data = [
        {"value": int(secure_count), "name": "Secure"},
        {"value": int(non_secure_count), "name": "Non-Secure"}
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
        "color": ["#27AE60", "#E74C3C"],
        "series": [{
            "name": "Security",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}lc_security_rose")


def _render_lifecycle_summary_chart(df, key_prefix=""):
    """Render object summary chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_lc_summary_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_lc_summary_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_lc_summary_donut_chart(df, key_prefix)
    else:
        _render_lc_summary_rose_chart(df, key_prefix)


def _render_lc_summary_bar_chart(df, key_prefix=""):
    """Render summary bar chart using Plotly."""
    # Calculate summary metrics
    total_objects = len(df)
    temp_tables = (df['LIFESPAN_CHECK'] == '✅ Temp Table').sum()
    short_lived = (df['LIFESPAN_CHECK'] == '⚠️ Short-Lived (Non-Temp)').sum()
    secure_views = (df['IS_SECURE'] == 'YES').sum()

    metrics = ['Total Objects', 'Temp Tables', 'Short-Lived', 'Secure Views']
    values = [total_objects, temp_tables, short_lived, secure_views]
    colors = ['#29B5E8', '#27AE60', '#E8A229', '#0077B6']

    fig = go.Figure(data=[
        go.Bar(
            x=metrics,
            y=values,
            marker_color=colors,
            text=[f"{int(val)}" for val in values],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Metric',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=50)
    )


def _render_lc_summary_pie_chart(df, key_prefix=""):
    """Render summary pie chart using ECharts."""
    temp_tables = (df['LIFESPAN_CHECK'] == '✅ Temp Table').sum()
    short_lived = (df['LIFESPAN_CHECK'] == '⚠️ Short-Lived (Non-Temp)').sum()
    secure_views = ((df['IS_SECURE'] == 'YES') & (df['TABLE_TYPE'] == 'VIEW')).sum()
    standard = len(df) - temp_tables - short_lived - secure_views

    chart_data = [
        {"value": int(temp_tables), "name": f"Temp Tables ({int(temp_tables)})"},
        {"value": int(short_lived), "name": f"Short-Lived ({int(short_lived)})"},
        {"value": int(secure_views), "name": f"Secure Views ({int(secure_views)})"},
        {"value": int(standard), "name": f"Standard ({int(standard)})"}
    ]

    # Filter out zero values
    chart_data = [item for item in chart_data if item['value'] > 0]

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
        "color": ["#27AE60", "#E8A229", "#0077B6", "#29B5E8"],
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


def _render_lc_summary_donut_chart(df, key_prefix=""):
    """Render summary donut chart using ECharts."""
    temp_tables = (df['LIFESPAN_CHECK'] == '✅ Temp Table').sum()
    short_lived = (df['LIFESPAN_CHECK'] == '⚠️ Short-Lived (Non-Temp)').sum()
    secure_views = ((df['IS_SECURE'] == 'YES') & (df['TABLE_TYPE'] == 'VIEW')).sum()
    standard = len(df) - temp_tables - short_lived - secure_views

    chart_data = [
        {"value": int(temp_tables), "name": f"Temp Tables ({int(temp_tables)})"},
        {"value": int(short_lived), "name": f"Short-Lived ({int(short_lived)})"},
        {"value": int(secure_views), "name": f"Secure Views ({int(secure_views)})"},
        {"value": int(standard), "name": f"Standard ({int(standard)})"}
    ]

    # Filter out zero values
    chart_data = [item for item in chart_data if item['value'] > 0]

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
        "color": ["#27AE60", "#E8A229", "#0077B6", "#29B5E8"],
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


def _render_lc_summary_rose_chart(df, key_prefix=""):
    """Render summary rose chart using ECharts."""
    temp_tables = (df['LIFESPAN_CHECK'] == '✅ Temp Table').sum()
    short_lived = (df['LIFESPAN_CHECK'] == '⚠️ Short-Lived (Non-Temp)').sum()
    secure_views = ((df['IS_SECURE'] == 'YES') & (df['TABLE_TYPE'] == 'VIEW')).sum()
    standard = len(df) - temp_tables - short_lived - secure_views

    chart_data = [
        {"value": int(temp_tables), "name": "Temp Tables"},
        {"value": int(short_lived), "name": "Short-Lived"},
        {"value": int(secure_views), "name": "Secure Views"},
        {"value": int(standard), "name": "Standard"}
    ]

    # Filter out zero values
    chart_data = [item for item in chart_data if item['value'] > 0]

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
        "color": ["#27AE60", "#E8A229", "#0077B6", "#29B5E8"],
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

    st_echarts(options=option, height="400px", key=f"{key_prefix}lc_summary_rose")


# ============================================================
# Charts for Third Expander: Object Structure Summary
# ============================================================

def _render_obj_summary_count_chart(df, key_prefix=""):
    """Render metrics count chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_obj_sum_count_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_obj_sum_count_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_obj_sum_count_donut_chart(df, key_prefix)
    else:
        _render_obj_sum_count_rose_chart(df, key_prefix)


def _render_obj_sum_count_bar_chart(df, key_prefix=""):
    """Render count bar chart using Plotly."""
    plot_df = df.sort_values('COUNT_OBJECTS', ascending=True)

    # Color mapping based on metric type
    def get_color(metric):
        if 'Stacked' in metric:
            return '#29B5E8'
        elif 'Temporary' in metric:
            return '#27AE60'
        elif 'Short-Lived' in metric:
            return '#E8A229'
        elif 'Secure' in metric:
            return '#0077B6'
        return '#29B5E8'

    colors = [get_color(m) for m in plot_df['METRIC_NAME']]

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['METRIC_NAME'],
            x=plot_df['COUNT_OBJECTS'],
            orientation='h',
            marker_color=colors,
            text=[f"{int(val):,}" for val in plot_df['COUNT_OBJECTS']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Count',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_obj_sum_count_pie_chart(df, key_prefix=""):
    """Render count pie chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OBJECTS']), "name": f"{row['METRIC_NAME']} ({int(row['COUNT_OBJECTS']):,})"}
        for _, row in df.iterrows() if row['COUNT_OBJECTS'] > 0
    ]

    if not chart_data:
        st.info("No data available for chart.")
        return

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
        "color": ["#29B5E8", "#E8A229", "#27AE60", "#E74C3C", "#0077B6"],
        "series": [{
            "name": "Metrics",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_obj_sum_count_donut_chart(df, key_prefix=""):
    """Render count donut chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OBJECTS']), "name": f"{row['METRIC_NAME']} ({int(row['COUNT_OBJECTS']):,})"}
        for _, row in df.iterrows() if row['COUNT_OBJECTS'] > 0
    ]

    if not chart_data:
        st.info("No data available for chart.")
        return

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
        "color": ["#29B5E8", "#E8A229", "#27AE60", "#E74C3C", "#0077B6"],
        "series": [{
            "name": "Metrics",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_obj_sum_count_rose_chart(df, key_prefix=""):
    """Render count rose chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OBJECTS']), "name": row['METRIC_NAME']}
        for _, row in df.iterrows() if row['COUNT_OBJECTS'] > 0
    ]

    if not chart_data:
        st.info("No data available for chart.")
        return

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
        "color": ["#29B5E8", "#E8A229", "#27AE60", "#E74C3C", "#0077B6"],
        "series": [{
            "name": "Metrics",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}obj_sum_count_rose")


def _render_obj_summary_distribution_chart(df, key_prefix=""):
    """Render distribution chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_obj_sum_dist_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_obj_sum_dist_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_obj_sum_dist_donut_chart(df, key_prefix)
    else:
        _render_obj_sum_dist_rose_chart(df, key_prefix)


def _render_obj_sum_dist_bar_chart(df, key_prefix=""):
    """Render distribution bar chart using Plotly."""
    total = df['COUNT_OBJECTS'].sum()
    if total == 0:
        st.info("No data available for chart.")
        return

    plot_df = df.copy()
    plot_df['PERCENTAGE'] = ((plot_df['COUNT_OBJECTS'] / total) * 100).round(1)
    plot_df = plot_df.sort_values('PERCENTAGE', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['METRIC_NAME'],
            x=plot_df['PERCENTAGE'],
            orientation='h',
            marker_color='#E8A229',
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
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_obj_sum_dist_pie_chart(df, key_prefix=""):
    """Render distribution pie chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OBJECTS']), "name": row['METRIC_NAME']}
        for _, row in df.iterrows() if row['COUNT_OBJECTS'] > 0
    ]

    if not chart_data:
        st.info("No data available for chart.")
        return

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
        "color": ["#E8A229", "#27AE60", "#E74C3C", "#0077B6", "#11567F"],
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


def _render_obj_sum_dist_donut_chart(df, key_prefix=""):
    """Render distribution donut chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OBJECTS']), "name": row['METRIC_NAME']}
        for _, row in df.iterrows() if row['COUNT_OBJECTS'] > 0
    ]

    if not chart_data:
        st.info("No data available for chart.")
        return

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
        "color": ["#E8A229", "#27AE60", "#E74C3C", "#0077B6", "#11567F"],
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


def _render_obj_sum_dist_rose_chart(df, key_prefix=""):
    """Render distribution rose chart using ECharts."""
    chart_data = [
        {"value": int(row['COUNT_OBJECTS']), "name": row['METRIC_NAME']}
        for _, row in df.iterrows() if row['COUNT_OBJECTS'] > 0
    ]

    if not chart_data:
        st.info("No data available for chart.")
        return

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
        "color": ["#E8A229", "#27AE60", "#E74C3C", "#0077B6", "#11567F"],
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

    st_echarts(options=option, height="400px", key=f"{key_prefix}obj_sum_dist_rose")


def _render_obj_summary_category_chart(df, key_prefix=""):
    """Render category comparison chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_obj_sum_cat_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_obj_sum_cat_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_obj_sum_cat_donut_chart(df, key_prefix)
    else:
        _render_obj_sum_cat_rose_chart(df, key_prefix)


def _render_obj_sum_cat_bar_chart(df, key_prefix=""):
    """Render category bar chart using Plotly."""
    # Categorize into View Depth vs Lifecycle
    view_depth_count = df[df['METRIC_NAME'].str.contains('Stacked', case=False, na=False)]['COUNT_OBJECTS'].sum()
    lifecycle_count = df[~df['METRIC_NAME'].str.contains('Stacked', case=False, na=False)]['COUNT_OBJECTS'].sum()

    categories = ['📊 View Depth Analysis', '🔄 Lifecycle Objects']
    values = [view_depth_count, lifecycle_count]
    colors = ['#29B5E8', '#27AE60']

    fig = go.Figure(data=[
        go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f"{int(val):,}" for val in values],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Category',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=50)
    )


def _render_obj_sum_cat_pie_chart(df, key_prefix=""):
    """Render category pie chart using ECharts."""
    view_depth_count = df[df['METRIC_NAME'].str.contains('Stacked', case=False, na=False)]['COUNT_OBJECTS'].sum()
    lifecycle_count = df[~df['METRIC_NAME'].str.contains('Stacked', case=False, na=False)]['COUNT_OBJECTS'].sum()

    chart_data = [
        {"value": int(view_depth_count), "name": f"📊 View Depth Analysis ({int(view_depth_count):,})"},
        {"value": int(lifecycle_count), "name": f"🔄 Lifecycle Objects ({int(lifecycle_count):,})"}
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
        "color": ["#29B5E8", "#27AE60"],
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


def _render_obj_sum_cat_donut_chart(df, key_prefix=""):
    """Render category donut chart using ECharts."""
    view_depth_count = df[df['METRIC_NAME'].str.contains('Stacked', case=False, na=False)]['COUNT_OBJECTS'].sum()
    lifecycle_count = df[~df['METRIC_NAME'].str.contains('Stacked', case=False, na=False)]['COUNT_OBJECTS'].sum()

    chart_data = [
        {"value": int(view_depth_count), "name": f"📊 View Depth Analysis ({int(view_depth_count):,})"},
        {"value": int(lifecycle_count), "name": f"🔄 Lifecycle Objects ({int(lifecycle_count):,})"}
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
        "color": ["#29B5E8", "#27AE60"],
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


def _render_obj_sum_cat_rose_chart(df, key_prefix=""):
    """Render category rose chart using ECharts."""
    view_depth_count = df[df['METRIC_NAME'].str.contains('Stacked', case=False, na=False)]['COUNT_OBJECTS'].sum()
    lifecycle_count = df[~df['METRIC_NAME'].str.contains('Stacked', case=False, na=False)]['COUNT_OBJECTS'].sum()

    chart_data = [
        {"value": int(view_depth_count), "name": "View Depth Analysis"},
        {"value": int(lifecycle_count), "name": "Lifecycle Objects"}
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
        "color": ["#29B5E8", "#27AE60"],
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

    st_echarts(options=option, height="400px", key=f"{key_prefix}obj_sum_cat_rose")


def _render_obj_summary_top_chart(df, key_prefix=""):
    """Render top metrics chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_obj_sum_top_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_obj_sum_top_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_obj_sum_top_donut_chart(df, key_prefix)
    else:
        _render_obj_sum_top_rose_chart(df, key_prefix)


def _render_obj_sum_top_bar_chart(df, key_prefix=""):
    """Render top metrics bar chart using Plotly."""
    # Get top metrics by count
    plot_df = df[df['COUNT_OBJECTS'] > 0].nlargest(5, 'COUNT_OBJECTS').sort_values('COUNT_OBJECTS', ascending=True)

    if plot_df.empty:
        st.info("No data available for chart.")
        return

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['METRIC_NAME'],
            x=plot_df['COUNT_OBJECTS'],
            orientation='h',
            marker_color='#0077B6',
            text=[f"{int(val):,}" for val in plot_df['COUNT_OBJECTS']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Count',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=200, r=50)
    )


def _render_obj_sum_top_pie_chart(df, key_prefix=""):
    """Render top metrics pie chart using ECharts."""
    plot_df = df[df['COUNT_OBJECTS'] > 0].nlargest(5, 'COUNT_OBJECTS')

    if plot_df.empty:
        st.info("No data available for chart.")
        return

    chart_data = [
        {"value": int(row['COUNT_OBJECTS']), "name": f"{row['METRIC_NAME']} ({int(row['COUNT_OBJECTS']):,})"}
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
        "color": ["#0077B6", "#0077B6", "#29B5E8", "#75C2D8", "#E8A229"],
        "series": [{
            "name": "Top Metrics",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_obj_sum_top_donut_chart(df, key_prefix=""):
    """Render top metrics donut chart using ECharts."""
    plot_df = df[df['COUNT_OBJECTS'] > 0].nlargest(5, 'COUNT_OBJECTS')

    if plot_df.empty:
        st.info("No data available for chart.")
        return

    chart_data = [
        {"value": int(row['COUNT_OBJECTS']), "name": f"{row['METRIC_NAME']} ({int(row['COUNT_OBJECTS']):,})"}
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
        "color": ["#0077B6", "#0077B6", "#29B5E8", "#75C2D8", "#E8A229"],
        "series": [{
            "name": "Top Metrics",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_obj_sum_top_rose_chart(df, key_prefix=""):
    """Render top metrics rose chart using ECharts."""
    plot_df = df[df['COUNT_OBJECTS'] > 0].nlargest(5, 'COUNT_OBJECTS')

    if plot_df.empty:
        st.info("No data available for chart.")
        return

    chart_data = [
        {"value": int(row['COUNT_OBJECTS']), "name": row['METRIC_NAME']}
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
        "color": ["#0077B6", "#0077B6", "#29B5E8", "#75C2D8", "#E8A229"],
        "series": [{
            "name": "Top Metrics",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}obj_sum_top_rose")

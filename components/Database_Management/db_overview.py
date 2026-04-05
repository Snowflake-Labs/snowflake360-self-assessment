import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_echarts import st_echarts




def comp_db_overview(entry_actions=None):
    """
    Database Overview Component with sub-tabs for Overview, Database Storage,
    Clustering, Low Lifespan Tables, and High Churn Tables.
    """
    try:
        sub_tab_names = [
            "Overview",
            "Database Storage",
            "Clustering",
            "Low Lifespan Tables",
            "High Churn Tables"
        ]
        sub_tabs = st.tabs(sub_tab_names)

        with sub_tabs[0]:
            _render_db_overview_subtab()

        with sub_tabs[1]:
            comp_db_storage()

        with sub_tabs[2]:
            comp_db_clustering()

        with sub_tabs[3]:
            comp_db_low_lifespan()

        with sub_tabs[4]:
            comp_db_high_churn()

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Database Overview: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_db_overview_subtab():
    """Render the core Database Overview content (storage analytics)."""
    _render_database_overview_tab()


def comp_db_storage(entry_actions=None):
    """Database Storage - Detailed storage analysis"""
    _render_database_storage_tab()


def comp_db_clustering(entry_actions=None):
    """Clustering - Clustering analysis and recommendations"""
    _render_clustering_tab()


def comp_db_low_lifespan(entry_actions=None):
    """Low Lifespan Tables - Analysis of short-lived tables"""
    _render_low_lifespan_tab()


def comp_db_high_churn(entry_actions=None):
    """High Churn Tables - Analysis of tables with high data churn"""
    _render_high_churn_tab()


def _render_database_overview_tab():
    """TAB1: Database Overview - Storage Analytics Overview"""
    try:
        total_storage_query = """
        SELECT
            ROUND(SUM(active_bytes) / POWER(2, 40), 6) AS active_storage_tb,
            ROUND(SUM(time_travel_bytes) / POWER(2, 40), 6) AS time_travel_storage_tb,
            ROUND(SUM(failsafe_bytes) / POWER(2, 40), 6) AS failsafe_storage_tb,
            ROUND(SUM(retained_for_clone_bytes) / POWER(2, 40), 6) AS retained_for_clone_storage_tb
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
"""

        total_storage_df = st.session_state.session.sql(total_storage_query).to_pandas()

        if len(total_storage_df) > 0:
            row = total_storage_df.iloc[0]

            try:
                active_storage = row['ACTIVE_STORAGE_TB']
                time_travel_storage = row['TIME_TRAVEL_STORAGE_TB']
                failsafe_storage = row['FAILSAFE_STORAGE_TB']
                retained_for_clone_storage = row['RETAINED_FOR_CLONE_STORAGE_TB']
            except KeyError as e:
                st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Column not found: {e}'
                            f'</div>', unsafe_allow_html=True)
                st.write("Available columns:", list(total_storage_df.columns))
                st.dataframe(total_storage_df)
                return
            total_storage = active_storage + time_travel_storage + failsafe_storage + retained_for_clone_storage

            with st.expander("Current Database Storage Overview", expanded=True):
                col1, col2 = st.columns([1, 1])
                with col1.container(border=True):
                    st.markdown(f"#### Storage Distribution by Type: {total_storage:.3f} TB")
                    _render_storage_chart_content(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix="tab1_")

                with col2.container(border=True):
                    _render_object_count_content()

                st.markdown("#### Database-Level Storage Breakdown (Top 10)")
                _render_database_breakdown_content()

            # Database Credit Consumption Overview expander
            with st.expander("Database Credit Consumption Overview", expanded=True):
                credit_col1, credit_col2 = st.columns([1, 1])

                with credit_col1.container(border=True):
                    _render_credit_counts_by_table_type(key_prefix="tab1_")

                with credit_col2.container(border=True):
                    _render_clustering_counts(key_prefix="tab1_")

                lifespan_col1, lifespan_col2 = st.columns([1, 1])

                with lifespan_col1.container(border=True):
                    _render_low_lifespan_tables(key_prefix="tab1_")

                with lifespan_col2.container(border=True):
                    _render_lifespan_aggregates(key_prefix="tab1_")

                churn_col1, churn_col2 = st.columns([1, 1])

                with churn_col1.container(border=True):
                    _render_high_churn_tables(key_prefix="tab1_")

                with churn_col2.container(border=True):
                    _render_access_aggregates(key_prefix="tab1_")

        else:
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No storage data available for the current execution context.'
                        '</div>', unsafe_allow_html=True)

    except Exception as query_error:
        # st.error(f"Error executing storage queries: {str(query_error)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error executing storage queries: {str(query_error)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;This might be due to insufficient permissions or missing data in account_usage views.'
                    '</div>', unsafe_allow_html=True)


def _render_database_storage_tab():
    """TAB3: Database Storage - Detailed storage analysis by database, schema, and table"""
    st.markdown("### Database Storage Analysis")
    st.markdown("Detailed breakdown of storage consumption across databases, schemas, and tables.")

    try:
        # Overall Storage Summary
        with st.expander("Overall Storage Summary", expanded=True):
            storage_summary_query = """
            SELECT
                ROUND(SUM(active_bytes) / POWER(2, 40), 6) AS active_storage_tb,
                ROUND(SUM(time_travel_bytes) / POWER(2, 40), 6) AS time_travel_storage_tb,
                ROUND(SUM(failsafe_bytes) / POWER(2, 40), 6) AS failsafe_storage_tb,
                ROUND(SUM(retained_for_clone_bytes) / POWER(2, 40), 6) AS clone_storage_tb,
                COUNT(DISTINCT table_catalog) as database_count,
                COUNT(*) as table_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
"""

            summary_df = st.session_state.session.sql(storage_summary_query).to_pandas()

            if len(summary_df) > 0:
                row = summary_df.iloc[0]
                total_storage = (row['ACTIVE_STORAGE_TB'] + row['TIME_TRAVEL_STORAGE_TB'] +
                               row['FAILSAFE_STORAGE_TB'] + row['CLONE_STORAGE_TB'])

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Storage", f"{total_storage:.3f} TB")
                with col2:
                    st.metric("Active Storage", f"{row['ACTIVE_STORAGE_TB']:.3f} TB")
                with col3:
                    st.metric("Time Travel", f"{row['TIME_TRAVEL_STORAGE_TB']:.3f} TB")
                with col4:
                    st.metric("Failsafe", f"{row['FAILSAFE_STORAGE_TB']:.3f} TB")

                # Storage type breakdown chart
                col1, col2 = st.columns([1, 1])

                with col1.container(border=True):
                    st.markdown("##### Storage Type Distribution")
                    _render_storage_chart_content(
                        row['ACTIVE_STORAGE_TB'],
                        row['TIME_TRAVEL_STORAGE_TB'],
                        row['FAILSAFE_STORAGE_TB'],
                        row['CLONE_STORAGE_TB'],
                        key_prefix="tab3_"
                    )

                with col2.container(border=True):
                    st.markdown("##### Storage Metrics Summary")
                    metrics_data = {
                        'Storage Type': ['Active', 'Time Travel', 'Failsafe', 'Clone'],
                        'Size (TB)': [row['ACTIVE_STORAGE_TB'], row['TIME_TRAVEL_STORAGE_TB'],
                                     row['FAILSAFE_STORAGE_TB'], row['CLONE_STORAGE_TB']],
                        'Percentage': [
                            f"{(row['ACTIVE_STORAGE_TB']/total_storage*100):.1f}%" if total_storage > 0 else "0%",
                            f"{(row['TIME_TRAVEL_STORAGE_TB']/total_storage*100):.1f}%" if total_storage > 0 else "0%",
                            f"{(row['FAILSAFE_STORAGE_TB']/total_storage*100):.1f}%" if total_storage > 0 else "0%",
                            f"{(row['CLONE_STORAGE_TB']/total_storage*100):.1f}%" if total_storage > 0 else "0%"
                        ]
                    }
                    st.dataframe(pd.DataFrame(metrics_data), use_container_width=True, height=200)

        # Database-Level Storage
        with st.expander("Storage by Database", expanded=True):
            db_storage_query = """
            SELECT
                table_catalog AS database_name,
                ROUND(SUM(active_bytes) / POWER(2, 40), 6) AS active_storage_tb,
                ROUND(SUM(time_travel_bytes) / POWER(2, 40), 6) AS time_travel_tb,
                ROUND(SUM(failsafe_bytes) / POWER(2, 40), 6) AS failsafe_tb,
                ROUND(SUM(retained_for_clone_bytes) / POWER(2, 40), 6) AS clone_tb,
                active_storage_tb + time_travel_tb + failsafe_tb + clone_tb AS total_storage_tb,
                COUNT(*) as table_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
GROUP BY 1
            HAVING total_storage_tb > 0
            ORDER BY total_storage_tb DESC
            """

            db_storage_df = st.session_state.session.sql(db_storage_query).to_pandas()

            if len(db_storage_df) > 0:
                col1, col2 = st.columns([1, 1])

                with col1.container(border=True):
                    st.markdown("##### Top Databases by Storage")
                    df_sorted = db_storage_df.head(10).sort_values('TOTAL_STORAGE_TB', ascending=True)

                    option = {
                        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                        "legend": {"bottom": "10", "left": "center"},
                        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "3%", "containLabel": True},
                        "xAxis": {"type": "value", "name": "Storage (TB)"},
                        "yAxis": {"type": "category", "data": df_sorted['DATABASE_NAME'].tolist(), "axisLabel": {"fontSize": 9}},
                        "color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
                        "series": [
                            {"name": "Active", "type": "bar", "stack": "total", "data": df_sorted['ACTIVE_STORAGE_TB'].tolist()},
                            {"name": "Time Travel", "type": "bar", "stack": "total", "data": df_sorted['TIME_TRAVEL_TB'].tolist()},
                            {"name": "Failsafe", "type": "bar", "stack": "total", "data": df_sorted['FAILSAFE_TB'].tolist()},
                            {"name": "Clone", "type": "bar", "stack": "total", "data": df_sorted['CLONE_TB'].tolist()}
                        ]
                    }
                    st_echarts(options=option, height="400px", key="db_storage_stacked_tab3")

                with col2.container(border=True):
                    st.markdown("##### Database Storage Details")
                    display_df = db_storage_df.copy()
                    display_df.columns = ['Database', 'Active (TB)', 'Time Travel (TB)', 'Failsafe (TB)', 'Clone (TB)', 'Total (TB)', 'Tables']
                    for col in ['Active (TB)', 'Time Travel (TB)', 'Failsafe (TB)', 'Clone (TB)', 'Total (TB)']:
                        display_df[col] = display_df[col].round(4)
                    st.dataframe(display_df, use_container_width=True, height=400)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No database storage data available.'
                            '</div>', unsafe_allow_html=True)

        # Top Tables by Storage
        with st.expander("Top Tables by Storage", expanded=False):
            top_tables_query = """
            SELECT
                table_catalog || '.' || table_schema || '.' || table_name AS full_table_name,
                table_catalog AS database_name,
                table_schema AS schema_name,
                table_name,
                ROUND(active_bytes / POWER(2, 30), 4) AS active_storage_gb,
                ROUND(time_travel_bytes / POWER(2, 30), 4) AS time_travel_gb,
                ROUND(failsafe_bytes / POWER(2, 30), 4) AS failsafe_gb,
                ROUND((active_bytes + time_travel_bytes + failsafe_bytes) / POWER(2, 30), 4) AS total_gb
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
ORDER BY total_gb DESC
            LIMIT 50
            """

            top_tables_df = st.session_state.session.sql(top_tables_query).to_pandas()

            if len(top_tables_df) > 0:
                display_df = top_tables_df[['FULL_TABLE_NAME', 'ACTIVE_STORAGE_GB', 'TIME_TRAVEL_GB', 'FAILSAFE_GB', 'TOTAL_GB']].copy()
                display_df.columns = ['Table', 'Active (GB)', 'Time Travel (GB)', 'Failsafe (GB)', 'Total (GB)']
                st.dataframe(display_df, use_container_width=True, height=400)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No table storage data available.'
                            '</div>', unsafe_allow_html=True)

    except Exception as e:
        # st.error(f"Error loading storage analysis: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading storage analysis: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_clustering_tab():
    """TAB4: Clustering - Clustering analysis and recommendations"""
    st.markdown("### Clustering Analysis")
    st.markdown("Analysis of table clustering configurations, costs, and optimization opportunities.")

    try:
        # Clustering Overview
        with st.expander("Clustering Overview", expanded=True):
            clustering_overview_query = """
            SELECT
                COUNT(*) as total_tables,
                COUNT(CASE WHEN clustering_key IS NOT NULL THEN 1 END) as clustered_tables,
                COUNT(CASE WHEN clustering_key IS NULL THEN 1 END) as unclustered_tables,
                ROUND(COUNT(CASE WHEN clustering_key IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) as cluster_percentage
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
AND deleted IS NULL
            AND table_schema != 'INFORMATION_SCHEMA'
            AND table_type = 'BASE TABLE'
            """

            overview_df = st.session_state.session.sql(clustering_overview_query).to_pandas()

            if len(overview_df) > 0:
                row = overview_df.iloc[0]

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Tables", f"{int(row['TOTAL_TABLES']):,}")
                with col2:
                    st.metric("Clustered Tables", f"{int(row['CLUSTERED_TABLES']):,}")
                with col3:
                    st.metric("Unclustered Tables", f"{int(row['UNCLUSTERED_TABLES']):,}")
                with col4:
                    st.metric("Cluster %", f"{row['CLUSTER_PERCENTAGE']:.1f}%")

        # Clustering by Table Type
        with st.expander("Clustering by Table Type", expanded=True):
            col1, col2 = st.columns([1, 1])

            with col1.container(border=True):
                _render_clustering_counts(key_prefix="tab4_")

            with col2.container(border=True):
                _render_credit_counts_by_table_type(key_prefix="tab4_")

        # Clustered Tables Details
        with st.expander("Clustered Tables Details", expanded=True):
            clustered_tables_query = """
            SELECT
                table_catalog || '.' || table_schema || '.' || table_name AS full_table_name,
                table_catalog AS database_name,
                clustering_key,
                row_count,
                ROUND(bytes / POWER(1024, 3), 2) AS size_gb,
                auto_clustering_on,
                created
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
AND deleted IS NULL
            AND clustering_key IS NOT NULL
            ORDER BY size_gb DESC
            LIMIT 100
            """

            clustered_df = st.session_state.session.sql(clustered_tables_query).to_pandas()

            if len(clustered_df) > 0:
                display_df = clustered_df.copy()
                display_df.columns = ['Table', 'Database', 'Clustering Key', 'Row Count', 'Size (GB)', 'Auto Clustering', 'Created']
                st.dataframe(display_df, use_container_width=True, height=400)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No clustered tables found.'
                            '</div>', unsafe_allow_html=True)

        # Clustering Credit History
        with st.expander("Clustering Credit Consumption (Last 30 Days)", expanded=False):
            credit_history_query = """
            SELECT
                DATE_TRUNC('day', start_time) AS cluster_date,
                ROUND(SUM(credits_used), 2) AS daily_credits,
                COUNT(DISTINCT table_id) AS tables_clustered
            FROM SNOWFLAKE.ACCOUNT_USAGE.automatic_clustering_history
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
            ORDER BY 1
            """

            credit_hist_df = st.session_state.session.sql(credit_history_query).to_pandas()

            if len(credit_hist_df) > 0:
                dates = [str(d)[:10] for d in credit_hist_df['CLUSTER_DATE'].tolist()]
                credits = credit_hist_df['DAILY_CREDITS'].tolist()

                option = {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": dates, "axisLabel": {"rotate": 45, "fontSize": 9}},
                    "yAxis": {"type": "value", "name": "Credits"},
                    "series": [{"name": "Credits Used", "type": "line", "data": credits, "smooth": True, "areaStyle": {}}]
                }
                st_echarts(options=option, height="300px", key="clustering_credit_trend")

                total_credits = sum(credits)
                st.markdown(f'<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'ℹ️&nbsp;&nbsp;<strong>Total Clustering Credits (30 days):</strong> {total_credits:.2f} credits'
                            f'</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No clustering credit history available.'
                            '</div>', unsafe_allow_html=True)

        # Recommendations
        with st.expander("Clustering Recommendations", expanded=False):
            st.markdown("""
            **Clustering Best Practices:**

            1. **Cluster Large Tables**: Focus clustering on tables > 1TB that are frequently queried with filter predicates
            2. **Choose Right Keys**: Select clustering keys based on common filter columns in WHERE clauses
            3. **Monitor Credit Usage**: Keep track of automatic clustering credits to control costs
            4. **Avoid Over-Clustering**: Don't cluster small tables or tables with random access patterns
            5. **Review Auto-Clustering**: Ensure auto-clustering is enabled only for tables that benefit from it
            """)

    except Exception as e:
        # st.error(f"Error loading clustering analysis: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading clustering analysis: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_low_lifespan_tab():
    """TAB5: Low Lifespan Tables - Analysis of short-lived tables"""
    st.markdown("### Low Lifespan Tables Analysis")
    st.markdown("Identify tables with short lifespans that may indicate inefficient ETL patterns or unnecessary permanent table creation.")

    try:
        # Summary Metrics
        with st.expander("Low Lifespan Summary", expanded=True):
            summary_query = """
            SELECT
                COUNT(*) as total_short_lived,
                COUNT(CASE WHEN is_transient = 'NO' THEN 1 END) as permanent_short_lived,
                COUNT(CASE WHEN is_transient = 'YES' THEN 1 END) as transient_short_lived,
                AVG(TIMEDIFF('minute', created, deleted)) as avg_lifespan_minutes,
                ROUND(SUM(bytes) / POWER(1024, 3), 2) as total_churned_storage_gb
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE deleted IS NOT NULL
            AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            AND TIMEDIFF('hour', created, deleted) < 24
"""

            summary_df = st.session_state.session.sql(summary_query).to_pandas()

            if len(summary_df) > 0:
                row = summary_df.iloc[0]

                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Short-Lived", f"{int(row['TOTAL_SHORT_LIVED'] or 0):,}")
                with col2:
                    st.metric("Permanent (Issue)", f"{int(row['PERMANENT_SHORT_LIVED'] or 0):,}")
                with col3:
                    st.metric("Transient (OK)", f"{int(row['TRANSIENT_SHORT_LIVED'] or 0):,}")
                with col4:
                    avg_min = row['AVG_LIFESPAN_MINUTES'] or 0
                    st.metric("Avg Lifespan", f"{avg_min:.0f} min")
                with col5:
                    st.metric("Churned Storage", f"{row['TOTAL_CHURNED_STORAGE_GB'] or 0:.2f} GB")

        # Low Lifespan Charts
        with st.expander("Low Lifespan Analysis", expanded=True):
            col1, col2 = st.columns([1, 1])

            with col1.container(border=True):
                _render_low_lifespan_tables(key_prefix="tab5_")

            with col2.container(border=True):
                _render_lifespan_aggregates(key_prefix="tab5_")

        # Detailed Low Lifespan Tables
        with st.expander("Low Lifespan Tables Details", expanded=True):
            detail_query = """
            SELECT
                table_catalog || '.' || table_schema || '.' || table_name AS full_table_name,
                table_owner,
                CASE
                    WHEN is_transient = 'NO' THEN 'Permanent (Action Required)'
                    ELSE 'Transient (OK)'
                END AS table_type,
                created,
                deleted,
                TIMEDIFF('minute', created, deleted) AS lifespan_minutes,
                ROUND(bytes / POWER(1024, 2), 2) AS size_mb,
                TO_CHAR(created, 'Day') AS day_of_week
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE deleted IS NOT NULL
            AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            AND TIMEDIFF('hour', created, deleted) < 24
ORDER BY lifespan_minutes ASC
            LIMIT 100
            """

            detail_df = st.session_state.session.sql(detail_query).to_pandas()

            if len(detail_df) > 0:
                display_df = detail_df.copy()
                display_df.columns = ['Table', 'Owner', 'Type', 'Created', 'Deleted', 'Lifespan (Min)', 'Size (MB)', 'Day']
                st.dataframe(display_df, use_container_width=True, height=400)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No low lifespan tables found in the last 30 days.'
                            '</div>', unsafe_allow_html=True)

        # Pattern Analysis
        with st.expander("Pattern Analysis", expanded=False):
            pattern_query = """
            SELECT
                table_owner AS owner,
                COUNT(*) as short_lived_count,
                AVG(TIMEDIFF('minute', created, deleted)) as avg_lifespan,
                COUNT(CASE WHEN is_transient = 'NO' THEN 1 END) as permanent_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE deleted IS NOT NULL
            AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            AND TIMEDIFF('hour', created, deleted) < 24
GROUP BY 1
            HAVING permanent_count > 0
            ORDER BY permanent_count DESC
            LIMIT 20
            """

            pattern_df = st.session_state.session.sql(pattern_query).to_pandas()

            if len(pattern_df) > 0:
                st.markdown("##### Users Creating Permanent Short-Lived Tables")
                display_df = pattern_df.copy()
                display_df.columns = ['Owner', 'Short-Lived Count', 'Avg Lifespan (Min)', 'Permanent Tables']
                st.dataframe(display_df, use_container_width=True, height=300)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No pattern data available.'
                            '</div>', unsafe_allow_html=True)

        # Recommendations
        with st.expander("Recommendations", expanded=False):
            st.markdown("""
            **Low Lifespan Table Best Practices:**

            1. **Use Transient Tables**: For staging/temporary data, use transient tables to avoid Time Travel/Failsafe costs
            2. **Review ETL Patterns**: Short-lived permanent tables often indicate suboptimal ETL design
            3. **Consider Temporary Tables**: For session-scoped data, use temporary tables instead
            4. **Optimize Pipelines**: Identify users/processes creating many short-lived tables and optimize their workflows
            5. **Cost Impact**: Each permanent table incurs 7+ days of Time Travel and Failsafe storage costs
            """)

    except Exception as e:
        # st.error(f"Error loading low lifespan analysis: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading low lifespan analysis: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_high_churn_tab():
    """TAB6: High Churn Tables - Analysis of tables with high data churn"""
    st.markdown("### High Churn Tables Analysis")
    st.markdown("Identify tables with high Time Travel and Failsafe storage relative to active data, indicating frequent updates/deletes.")

    try:
        # Summary Metrics
        with st.expander("High Churn Summary", expanded=True):
            summary_query = """
            WITH churn_data AS (
                SELECT
                    sm.id,
                    sm.active_bytes,
                    sm.time_travel_bytes,
                    sm.failsafe_bytes,
                    (sm.time_travel_bytes + sm.failsafe_bytes) as churn_bytes,
                    DIV0((sm.time_travel_bytes + sm.failsafe_bytes), NULLIF(sm.active_bytes, 0)) as churn_ratio,
                    t.is_transient
                FROM SNOWFLAKE.ACCOUNT_USAGE.table_storage_metrics sm
                JOIN SNOWFLAKE.ACCOUNT_USAGE.tables t ON sm.id = t.table_id
                WHERE sm.deleted = FALSE
AND (sm.time_travel_bytes + sm.failsafe_bytes) > 0
            )
            SELECT
                COUNT(*) as tables_with_churn,
                COUNT(CASE WHEN churn_ratio > 1 THEN 1 END) as high_churn_tables,
                COUNT(CASE WHEN is_transient = 'NO' THEN 1 END) as permanent_with_churn,
                ROUND(SUM(churn_bytes) / POWER(1024, 4), 4) as total_churn_tb,
                ROUND(AVG(churn_ratio), 2) as avg_churn_ratio
            FROM churn_data
            """

            summary_df = st.session_state.session.sql(summary_query).to_pandas()

            if len(summary_df) > 0:
                row = summary_df.iloc[0]

                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Tables with Churn", f"{int(row['TABLES_WITH_CHURN'] or 0):,}")
                with col2:
                    st.metric("High Churn (>1x)", f"{int(row['HIGH_CHURN_TABLES'] or 0):,}")
                with col3:
                    st.metric("Permanent Tables", f"{int(row['PERMANENT_WITH_CHURN'] or 0):,}")
                with col4:
                    st.metric("Total Churn Storage", f"{row['TOTAL_CHURN_TB'] or 0:.4f} TB")
                with col5:
                    st.metric("Avg Churn Ratio", f"{row['AVG_CHURN_RATIO'] or 0:.2f}x")

        # High Churn Charts
        with st.expander("High Churn Analysis", expanded=True):
            col1, col2 = st.columns([1, 1])

            with col1.container(border=True):
                _render_high_churn_tables(key_prefix="tab6_")

            with col2.container(border=True):
                _render_access_aggregates(key_prefix="tab6_")

        # High Churn Tables Details
        with st.expander("High Churn Tables Details", expanded=True):
            detail_query = """
            WITH storage_metrics AS (
                SELECT
                    t.table_catalog,
                    t.table_schema,
                    t.table_name,
                    t.table_catalog || '.' || t.table_schema || '.' || t.table_name AS full_name,
                    t.is_transient,
                    t.row_count,
                    (sm.active_bytes / POW(1024, 3)) AS active_gb,
                    (sm.time_travel_bytes / POW(1024, 3)) AS time_travel_gb,
                    (sm.failsafe_bytes / POW(1024, 3)) AS failsafe_gb,
                    ((sm.time_travel_bytes + sm.failsafe_bytes) / POW(1024, 3)) AS total_churn_gb,
                    DIV0((sm.time_travel_bytes + sm.failsafe_bytes), NULLIF(sm.active_bytes, 0)) AS churn_ratio
                FROM SNOWFLAKE.ACCOUNT_USAGE.table_storage_metrics sm
                JOIN SNOWFLAKE.ACCOUNT_USAGE.tables t ON sm.id = t.table_id
                WHERE sm.deleted = FALSE
AND (sm.time_travel_bytes + sm.failsafe_bytes) > 0
            )
            SELECT
                full_name AS table_name,
                CASE WHEN is_transient = 'YES' THEN 'Transient' ELSE 'Permanent' END AS table_type,
                row_count,
                ROUND(active_gb, 2) AS active_data_gb,
                ROUND(time_travel_gb, 2) AS time_travel_gb,
                ROUND(failsafe_gb, 2) AS failsafe_gb,
                ROUND(total_churn_gb, 2) AS total_churn_gb,
                ROUND(churn_ratio, 2) AS churn_ratio
            FROM storage_metrics
            ORDER BY total_churn_gb DESC
            LIMIT 100
            """

            detail_df = st.session_state.session.sql(detail_query).to_pandas()

            if len(detail_df) > 0:
                display_df = detail_df.copy()
                display_df.columns = ['Table', 'Type', 'Row Count', 'Active (GB)', 'Time Travel (GB)', 'Failsafe (GB)', 'Total Churn (GB)', 'Churn Ratio']
                st.dataframe(display_df, use_container_width=True, height=400)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No high churn tables found.'
                            '</div>', unsafe_allow_html=True)

        # Churn by Database
        with st.expander("Churn by Database", expanded=False):
            db_churn_query = """
            SELECT
                t.table_catalog AS database_name,
                COUNT(*) as table_count,
                ROUND(SUM(sm.time_travel_bytes + sm.failsafe_bytes) / POW(1024, 4), 4) AS total_churn_tb,
                ROUND(AVG(DIV0((sm.time_travel_bytes + sm.failsafe_bytes), NULLIF(sm.active_bytes, 0))), 2) AS avg_churn_ratio
            FROM SNOWFLAKE.ACCOUNT_USAGE.table_storage_metrics sm
            JOIN SNOWFLAKE.ACCOUNT_USAGE.tables t ON sm.id = t.table_id
            WHERE sm.deleted = FALSE
AND (sm.time_travel_bytes + sm.failsafe_bytes) > 0
            GROUP BY 1
            ORDER BY total_churn_tb DESC
            """

            db_churn_df = st.session_state.session.sql(db_churn_query).to_pandas()

            if len(db_churn_df) > 0:
                col1, col2 = st.columns([1, 1])

                with col1.container(border=True):
                    st.markdown("##### Churn by Database")
                    df_sorted = db_churn_df.head(10).sort_values('TOTAL_CHURN_TB', ascending=True)

                    option = {
                        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "top": "3%", "containLabel": True},
                        "xAxis": {"type": "value", "name": "Churn Storage (TB)"},
                        "yAxis": {"type": "category", "data": df_sorted['DATABASE_NAME'].tolist(), "axisLabel": {"fontSize": 9}},
                        "series": [{"name": "Churn (TB)", "type": "bar", "data": df_sorted['TOTAL_CHURN_TB'].tolist(), "itemStyle": {"color": "#d62728"}}]
                    }
                    st_echarts(options=option, height="350px", key="db_churn_bar")

                with col2.container(border=True):
                    st.markdown("##### Database Churn Details")
                    display_df = db_churn_df.copy()
                    display_df.columns = ['Database', 'Tables', 'Total Churn (TB)', 'Avg Churn Ratio']
                    st.dataframe(display_df, use_container_width=True, height=350)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No database churn data available.'
                            '</div>', unsafe_allow_html=True)

        # Recommendations
        with st.expander("Recommendations", expanded=False):
            st.markdown("""
            **High Churn Table Best Practices:**

            1. **Review Update Patterns**: Tables with high churn may benefit from append-only patterns or merge optimizations
            2. **Consider Transient Tables**: For frequently updated staging tables, use transient tables
            3. **Optimize Time Travel**: Reduce Time Travel retention for high-churn tables that don't need extended history
            4. **Batch Updates**: Combine multiple small updates into fewer larger transactions
            5. **Use Streams**: For CDC patterns, use Snowflake Streams instead of frequent full table scans
            6. **Monitor Cost Impact**: High churn significantly increases storage costs through Time Travel and Failsafe
            """)

    except Exception as e:
        # st.error(f"Error loading high churn analysis: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading high churn analysis: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_storage_metrics_content(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage):
    """Render the storage metrics content in 2x2 grid format (similar to warehouse metrics)."""

    # Define storage types and their values in order
    storage_types = [
        ('Active Storage', active_storage, '#1f77b4'),
        ('Time Travel Storage', time_travel_storage, '#ff7f0e'),
        ('Failsafe Storage', failsafe_storage, '#2ca02c'),
        ('Clone Storage', retained_for_clone_storage, '#d62728')
    ]

    # Display storage metrics in 2x2 grid format
    # Row 1 - Active Storage and Time Travel Storage
    st.markdown('<div style="margin-bottom: 30px;">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    cols_row1 = [col1, col2]
    for i, (storage_type, value, color) in enumerate(storage_types[:2]):
        with cols_row1[i]:
            # Custom styled metric similar to warehouse metrics
            st.markdown(f'''
            <div style="text-align: center;">
                <div style="color: {color}; font-size: 14px; font-weight: bold; margin: 0; line-height: 1.2;">{storage_type}</div>
                <div style="color: {color}; font-size: 32px; font-weight: bold; margin: 0; line-height: 0.8; margin-top: 5px;">{value:.3f} TB</div>
            </div>
            ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Row 2 - Failsafe Storage and Clone Storage
    st.markdown('<div style="margin-bottom: 20px;">', unsafe_allow_html=True)
    col3, col4 = st.columns(2)
    cols_row2 = [col3, col4]
    for i, (storage_type, value, color) in enumerate(storage_types[2:]):
        with cols_row2[i]:
            # Custom styled metric similar to warehouse metrics
            st.markdown(f'''
            <div style="text-align: center;">
                <div style="color: {color}; font-size: 14px; font-weight: bold; margin: 0; line-height: 1.2;">{storage_type}</div>
                <div style="color: {color}; font-size: 32px; font-weight: bold; margin: 0; line-height: 0.8; margin-top: 5px;">{value:.3f} TB</div>
            </div>
            ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def _render_storage_chart_content(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix=""):
    """Render storage distribution chart content with selectable chart types (similar to warehouse charts)."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key=f"{key_prefix}storage_chart_type"
    )

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_storage_bar_chart(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix)
    elif chart_type == "Pie Chart":
        _render_storage_standard_pie_chart(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_storage_donut_pie_chart(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix)
    else:  # Pie - Rose Chart
        _render_storage_rose_pie_chart(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix)


def _render_object_count_content():
    """Render object count by object type chart content with selectable chart types."""

    # Query for object counts by type
    object_count_query = """
    SELECT OBJECT_TYPE, OBJECT_COUNT
    FROM   (SELECT 'DATABASES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'SCHEMAS' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.SCHEMATA WHERE (DELETED IS NULL)
            UNION ALL
            SELECT TABLE_TYPE OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES WHERE (DELETED IS NULL) GROUP BY TABLE_TYPE
            UNION ALL
            SELECT 'ROW_ACCESS_POLICIES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.ROW_ACCESS_POLICIES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'PIPES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.PIPES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'ROLES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES WHERE (DELETED_ON IS NULL)
            UNION ALL
            SELECT 'NETWORK_RULES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'NETWORK_POLICIES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'MASKING_POLICIES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.MASKING_POLICIES WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'USERS' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.USERS WHERE (DELETED_ON IS NULL)
            UNION ALL
            SELECT 'FILE_FORMATS' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.FILE_FORMATS WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'FUNCTIONS' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.FUNCTIONS WHERE (DELETED IS NULL)
            UNION ALL
            SELECT 'PROCEDURES' OBJECT_TYPE, COUNT(*) OBJECT_COUNT FROM SNOWFLAKE.ACCOUNT_USAGE.PROCEDURES WHERE (DELETED IS NULL))
    ORDER BY OBJECT_TYPE ASC
    """

    try:
        object_count_df = st.session_state.session.sql(object_count_query).to_pandas()

        if len(object_count_df) > 0:
            # Calculate total object count for header
            total_objects = object_count_df['OBJECT_COUNT'].sum()
            st.markdown(f"#### Object Count by Object Type: {total_objects:,}")

            # Add chart type selector
            chart_type = st.selectbox(
                "Change Chart Type",
                ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                index=0,  # Default to Bar Chart
                key="object_count_chart_type"
            )

            # Render selected chart type
            if chart_type == "Bar Chart":
                _render_object_count_bar_chart(object_count_df)
            elif chart_type == "Pie Chart":
                _render_object_count_standard_pie_chart(object_count_df)
            elif chart_type == "Pie - Donut":
                _render_object_count_donut_pie_chart(object_count_df)
            else:  # Pie - Rose Chart
                _render_object_count_rose_pie_chart(object_count_df)
        else:
            st.markdown("#### Object Count by Object Type")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No object count data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown("#### Object Count by Object Type")
        # st.error(f"Error loading object count data: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading object count data: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_object_count_bar_chart(object_count_df):
    """Render object count bar chart using Plotly."""

    # Sort by object count descending for better visualization
    df_sorted = object_count_df.sort_values('OBJECT_COUNT', ascending=True)

    fig_bar = go.Figure(data=[
        go.Bar(
            y=df_sorted['OBJECT_TYPE'],
            x=df_sorted['OBJECT_COUNT'],
            orientation='h',
            marker_color='#1f77b4',
            text=df_sorted['OBJECT_COUNT'],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=400,
        xaxis_title='Count',
        yaxis_title='Object Type',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )

    st.plotly_chart(fig_bar, use_container_width=True)


def _render_object_count_standard_pie_chart(object_count_df):
    """Render object count standard pie chart using ECharts."""

    # Prepare data for ECharts standard pie chart
    chart_data = [
        {"value": int(row['OBJECT_COUNT']), "name": f"{row['OBJECT_TYPE']} ({row['OBJECT_COUNT']:,})"}
        for _, row in object_count_df.iterrows()
    ]

    # ECharts standard pie chart configuration
    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {
                "fontSize": 10
            },
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Object Count",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(
        options=option,
        height="400px",
        key="object_count_pie_chart"
    )


def _render_object_count_donut_pie_chart(object_count_df):
    """Render object count donut pie chart using ECharts."""

    # Prepare data for ECharts donut pie chart
    chart_data = [
        {"value": int(row['OBJECT_COUNT']), "name": f"{row['OBJECT_TYPE']} ({row['OBJECT_COUNT']:,})"}
        for _, row in object_count_df.iterrows()
    ]

    # ECharts donut pie chart configuration
    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {
                "fontSize": 10
            },
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Object Count",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(
        options=option,
        height="400px",
        key="object_count_donut_chart"
    )


def _render_object_count_rose_pie_chart(object_count_df):
    """Render object count rose-type pie chart using ECharts."""

    # Prepare data for ECharts rose-type pie chart
    chart_data = [
        {"value": int(row['OBJECT_COUNT']), "name": f"{row['OBJECT_TYPE']} ({row['OBJECT_COUNT']:,})"}
        for _, row in object_count_df.iterrows()
    ]

    # ECharts rose-type pie chart configuration
    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {
                "fontSize": 10
            },
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Object Count",
                "type": "pie",
                "radius": [15, 90],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(
        options=option,
        height="400px",
        key="object_count_rose_chart"
    )


def _render_database_breakdown_content():
    """Render database-level storage breakdown content."""

    # Query for database-level storage metrics (Top 10 databases)
    db_storage_query = """
    SELECT table_catalog,
        ROUND(SUM(active_bytes) / POWER(2, 40), 6) AS active_storage,
        ROUND(SUM(time_travel_bytes) / POWER(2, 40), 6) AS time_travel_storage,
        ROUND(SUM(failsafe_bytes) / POWER(2, 40), 6) AS failsafe_storage,
        ROUND(SUM(retained_for_clone_bytes) / POWER(2, 40), 6) AS retained_for_clone_storage,
        active_storage + time_travel_storage + failsafe_storage + retained_for_clone_storage AS total_storage
    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
GROUP BY 1
    HAVING total_storage > 0
    ORDER BY total_storage DESC
    LIMIT 10
    """

    try:
        db_storage_df = st.session_state.session.sql(db_storage_query).to_pandas()

        if len(db_storage_df) > 0:
            # Debug: Check if we have the expected columns
            expected_cols = ['TABLE_CATALOG', 'ACTIVE_STORAGE', 'TIME_TRAVEL_STORAGE',
                           'FAILSAFE_STORAGE', 'RETAINED_FOR_CLONE_STORAGE', 'TOTAL_STORAGE']

            if not all(col in db_storage_df.columns for col in expected_cols):
                # st.error("Expected columns not found in database storage data")
                st.markdown('<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '🛑&nbsp;&nbsp;Expected columns not found in database storage data'
                            '</div>', unsafe_allow_html=True)
                st.write("Available columns:", list(db_storage_df.columns))
                st.dataframe(db_storage_df)
                return

            table_col, chart_col = st.columns([1, 1])

            # Storage Metrics by Database - with border container
            with table_col.container(border=True):
                # Format the dataframe for display
                display_df = db_storage_df.copy()
                display_df.columns = ['Database', 'Active (TB)', 'Time Travel (TB)', 'Failsafe (TB)', 'Clone (TB)', 'Total (TB)']

                # Format numbers to 3 decimal places
                numeric_cols = ['Active (TB)', 'Time Travel (TB)', 'Failsafe (TB)', 'Clone (TB)', 'Total (TB)']
                for col in numeric_cols:
                    display_df[col] = display_df[col].round(3)

                st.markdown("##### Storage Metrics by Database")
                st.dataframe(display_df, use_container_width=True, height=422)

            # Stacked Storage by Database - with border container
            with chart_col.container(border=True):
                st.markdown("##### Stacked Storage by Database")

                # Add chart type selector
                chart_type = st.selectbox(
                    "Change Chart Type",
                    ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                    index=0,  # Default to Bar Chart
                    key="db_storage_chart_type"
                )

                # Render selected chart type
                if chart_type == "Bar Chart":
                    _render_db_storage_bar_chart(db_storage_df)
                elif chart_type == "Pie Chart":
                    _render_db_storage_standard_pie_chart(db_storage_df)
                elif chart_type == "Pie - Donut":
                    _render_db_storage_donut_pie_chart(db_storage_df)
                else:  # Pie - Rose Chart
                    _render_db_storage_rose_pie_chart(db_storage_df)
        else:
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No database-level storage data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        # st.error(f"Error loading database breakdown: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading database breakdown: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_credit_counts_by_table_type(key_prefix=""):
    """Render Credit Counts By Tables Type chart with selectable chart types."""

    # Query for credit counts by table type
    credit_query = """
    WITH table_types AS (
        SELECT
            table_id,
            CASE
                WHEN is_iceberg = 'YES' THEN 'Iceberg Table'
                WHEN is_dynamic = 'YES' THEN 'Dynamic Table'
                WHEN table_type = 'MATERIALIZED VIEW' THEN 'Materialized View'
                WHEN table_type = 'EVENT TABLE' THEN 'Event Table'
                ELSE 'Standard Table'
            END AS object_type
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
)
    SELECT
        COALESCE(t.object_type, 'Dropped/Unknown Table') AS "Table Type",
        ROUND(SUM(h.credits_used), 2) AS "Clustering Credits (30 Days)",
        COUNT(DISTINCT h.table_id) AS "Distinct Tables Clustered"
    FROM SNOWFLAKE.ACCOUNT_USAGE.automatic_clustering_history h
    LEFT JOIN table_types t
        ON h.table_id = t.table_id
    WHERE h.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
    ORDER BY 2 DESC
    """

    try:
        credit_df = st.session_state.session.sql(credit_query).to_pandas()

        if len(credit_df) > 0:
            st.markdown("##### Credit Counts By Tables Type")

            # Add chart type selector
            chart_type = st.selectbox(
                "Change Chart Type",
                ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                index=0,
                key=f"{key_prefix}credit_counts_chart_type"
            )

            # Render selected chart type
            if chart_type == "Bar Chart":
                _render_credit_counts_bar_chart(credit_df, key_prefix)
            elif chart_type == "Pie Chart":
                _render_credit_counts_pie_chart(credit_df, key_prefix)
            elif chart_type == "Pie - Donut":
                _render_credit_counts_donut_chart(credit_df, key_prefix)
            else:
                _render_credit_counts_rose_chart(credit_df, key_prefix)
        else:
            st.markdown("##### Credit Counts By Tables Type")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No credit consumption data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown("##### Credit Counts By Tables Type")
        # st.error(f"Error loading credit counts: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading credit counts: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_credit_counts_bar_chart(credit_df, key_prefix=""):
    """Render credit counts bar chart using ECharts."""

    # Sort by credits descending
    df_sorted = credit_df.sort_values('Clustering Credits (30 Days)', ascending=True)

    table_types = df_sorted['Table Type'].tolist()
    credits_data = df_sorted['Clustering Credits (30 Days)'].tolist()
    tables_data = df_sorted['Distinct Tables Clustered'].tolist()

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 15,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "top": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "name": "Credits / Count",
            "nameLocation": "middle",
            "nameGap": 25
        },
        "yAxis": {
            "type": "category",
            "data": table_types,
            "axisLabel": {"fontSize": 10}
        },
        "color": ["#1f77b4", "#ff7f0e"],
        "series": [
            {
                "name": "Clustering Credits",
                "type": "bar",
                "data": credits_data
            },
            {
                "name": "Tables Clustered",
                "type": "bar",
                "data": tables_data
            }
        ]
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}credit_counts_bar_chart")


def _render_credit_counts_pie_chart(credit_df, key_prefix=""):
    """Render credit counts pie chart using ECharts."""

    chart_data = [
        {"value": float(row['Clustering Credits (30 Days)']), "name": f"{row['Table Type']} ({row['Clustering Credits (30 Days)']} credits)"}
        for _, row in credit_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Clustering Credits",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}credit_counts_pie_chart")


def _render_credit_counts_donut_chart(credit_df, key_prefix=""):
    """Render credit counts donut chart using ECharts."""

    chart_data = [
        {"value": float(row['Clustering Credits (30 Days)']), "name": f"{row['Table Type']} ({row['Clustering Credits (30 Days)']} credits)"}
        for _, row in credit_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Clustering Credits",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}credit_counts_donut_chart")


def _render_credit_counts_rose_chart(credit_df, key_prefix=""):
    """Render credit counts rose chart using ECharts."""

    chart_data = [
        {"value": float(row['Clustering Credits (30 Days)']), "name": f"{row['Table Type']} ({row['Clustering Credits (30 Days)']} credits)"}
        for _, row in credit_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Clustering Credits",
                "type": "pie",
                "radius": [15, 90],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}credit_counts_rose_chart")


def _render_clustering_counts(key_prefix=""):
    """Render Clustering Counts chart with selectable chart types."""

    # Query for clustering counts
    clustering_query = """
    SELECT
        CASE
            WHEN is_iceberg = 'YES' THEN 'Iceberg Table'
            WHEN is_dynamic = 'YES' THEN 'Dynamic Table'
            WHEN table_type = 'MATERIALIZED VIEW' THEN 'Materialized View'
            ELSE 'Standard Table'
        END AS "Table Type",
        COUNT(CASE WHEN clustering_key IS NOT NULL THEN 1 END) AS "Clustered Count",
        COUNT(CASE WHEN clustering_key IS NULL THEN 1 END) AS "Unclustered Count",
        ROUND(
            COUNT(CASE WHEN clustering_key IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0),
            1
        ) AS "% Clustered"
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE deleted IS NULL
      AND table_schema != 'INFORMATION_SCHEMA'
      AND table_type != 'EXTERNAL TABLE'
GROUP BY 1
    ORDER BY 2 DESC
    """

    try:
        clustering_df = st.session_state.session.sql(clustering_query).to_pandas()

        if len(clustering_df) > 0:
            st.markdown("##### Clustering Counts")

            # Add chart type selector
            chart_type = st.selectbox(
                "Change Chart Type",
                ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                index=0,
                key=f"{key_prefix}clustering_counts_chart_type"
            )

            # Render selected chart type
            if chart_type == "Bar Chart":
                _render_clustering_counts_bar_chart(clustering_df, key_prefix)
            elif chart_type == "Pie Chart":
                _render_clustering_counts_pie_chart(clustering_df, key_prefix)
            elif chart_type == "Pie - Donut":
                _render_clustering_counts_donut_chart(clustering_df, key_prefix)
            else:
                _render_clustering_counts_rose_chart(clustering_df, key_prefix)
        else:
            st.markdown("##### Clustering Counts")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No clustering data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown("##### Clustering Counts")
        # st.error(f"Error loading clustering counts: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading clustering counts: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_clustering_counts_bar_chart(clustering_df, key_prefix=""):
    """Render clustering counts bar chart using ECharts."""

    # Sort by clustered count descending
    df_sorted = clustering_df.sort_values('Clustered Count', ascending=True)

    table_types = df_sorted['Table Type'].tolist()
    clustered_data = df_sorted['Clustered Count'].tolist()
    unclustered_data = df_sorted['Unclustered Count'].tolist()

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 15,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "top": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "name": "Count",
            "nameLocation": "middle",
            "nameGap": 25
        },
        "yAxis": {
            "type": "category",
            "data": table_types,
            "axisLabel": {"fontSize": 10}
        },
        "color": ["#2ca02c", "#d62728"],
        "series": [
            {
                "name": "Clustered",
                "type": "bar",
                "data": clustered_data
            },
            {
                "name": "Unclustered",
                "type": "bar",
                "data": unclustered_data
            }
        ]
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}clustering_counts_bar_chart")


def _render_clustering_counts_pie_chart(clustering_df, key_prefix=""):
    """Render clustering counts pie chart using ECharts - shows clustered counts by table type."""

    chart_data = [
        {"value": int(row['Clustered Count']), "name": f"{row['Table Type']} ({row['Clustered Count']} clustered)"}
        for _, row in clustering_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Clustered Tables",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}clustering_counts_pie_chart")


def _render_clustering_counts_donut_chart(clustering_df, key_prefix=""):
    """Render clustering counts donut chart using ECharts."""

    chart_data = [
        {"value": int(row['Clustered Count']), "name": f"{row['Table Type']} ({row['Clustered Count']} clustered)"}
        for _, row in clustering_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Clustered Tables",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}clustering_counts_donut_chart")


def _render_clustering_counts_rose_chart(clustering_df, key_prefix=""):
    """Render clustering counts rose chart using ECharts."""

    chart_data = [
        {"value": int(row['Clustered Count']), "name": f"{row['Table Type']} ({row['Clustered Count']} clustered)"}
        for _, row in clustering_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Clustered Tables",
                "type": "pie",
                "radius": [15, 90],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}clustering_counts_rose_chart")


def _render_low_lifespan_tables(key_prefix=""):
    """Render Low-lifespan Tables chart with selectable chart types."""

    # Query for low-lifespan tables
    lifespan_query = """
    SELECT
        table_catalog AS "Database",
        table_schema AS "Schema",
        table_name AS "Table Name",
        table_owner AS "Owner",
        created AS "Created Time",
        deleted AS "Dropped Time",
        TIMEDIFF('minute', created, deleted) AS "Lifespan (Minutes)",
        CASE
            WHEN is_transient = 'NO' AND table_type = 'BASE TABLE' THEN 'Permanent (High Cost)'
            WHEN is_transient = 'YES' THEN 'Transient (Good)'
            ELSE table_type
        END AS "Table Type",
        TO_CHAR(created, 'Day') AS "Day of Week",
        TO_CHAR(created, 'HH24') || ':00' AS "Hour of Day"
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE
        deleted IS NOT NULL
        AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        AND TIMEDIFF('hour', created, deleted) < 24
        AND ((table_name NOT LIKE '%tmp%') OR (table_name NOT LIKE '%temp%'))
ORDER BY "Lifespan (Minutes)" ASC
    """

    try:
        lifespan_df = st.session_state.session.sql(lifespan_query).to_pandas()

        if len(lifespan_df) > 0:
            st.markdown("##### Low-lifespan Tables")

            # Add chart type selector
            chart_type = st.selectbox(
                "Change Chart Type",
                ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                index=0,
                key=f"{key_prefix}low_lifespan_chart_type"
            )

            # Aggregate by Table Type for charting
            agg_df = lifespan_df.groupby('Table Type').agg({
                'Table Name': 'count',
                'Lifespan (Minutes)': 'mean'
            }).reset_index()
            agg_df.columns = ['Table Type', 'Count', 'Avg Lifespan (Minutes)']

            # Render selected chart type
            if chart_type == "Bar Chart":
                _render_low_lifespan_bar_chart(agg_df, key_prefix)
            elif chart_type == "Pie Chart":
                _render_low_lifespan_pie_chart(agg_df, key_prefix)
            elif chart_type == "Pie - Donut":
                _render_low_lifespan_donut_chart(agg_df, key_prefix)
            else:
                _render_low_lifespan_rose_chart(agg_df, key_prefix)
        else:
            st.markdown("##### Low-lifespan Tables")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No low-lifespan tables found in the last 30 days.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown("##### Low-lifespan Tables")
        # st.error(f"Error loading low-lifespan tables: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading low-lifespan tables: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_low_lifespan_bar_chart(agg_df, key_prefix=""):
    """Render low-lifespan tables bar chart using ECharts."""

    df_sorted = agg_df.sort_values('Count', ascending=True)

    table_types = df_sorted['Table Type'].tolist()
    count_data = df_sorted['Count'].tolist()
    avg_lifespan_data = [round(x, 1) for x in df_sorted['Avg Lifespan (Minutes)'].tolist()]

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 15,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "top": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "name": "Count / Minutes",
            "nameLocation": "middle",
            "nameGap": 25
        },
        "yAxis": {
            "type": "category",
            "data": table_types,
            "axisLabel": {"fontSize": 10}
        },
        "color": ["#1f77b4", "#ff7f0e"],
        "series": [
            {
                "name": "Table Count",
                "type": "bar",
                "data": count_data
            },
            {
                "name": "Avg Lifespan (Min)",
                "type": "bar",
                "data": avg_lifespan_data
            }
        ]
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}low_lifespan_bar_chart")


def _render_low_lifespan_pie_chart(agg_df, key_prefix=""):
    """Render low-lifespan tables pie chart using ECharts."""

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Table Type']} ({row['Count']} tables)"}
        for _, row in agg_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Low-lifespan Tables",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}low_lifespan_pie_chart")


def _render_low_lifespan_donut_chart(agg_df, key_prefix=""):
    """Render low-lifespan tables donut chart using ECharts."""

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Table Type']} ({row['Count']} tables)"}
        for _, row in agg_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Low-lifespan Tables",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}low_lifespan_donut_chart")


def _render_low_lifespan_rose_chart(agg_df, key_prefix=""):
    """Render low-lifespan tables rose chart using ECharts."""

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Table Type']} ({row['Count']} tables)"}
        for _, row in agg_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Low-lifespan Tables",
                "type": "pie",
                "radius": [15, 90],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}low_lifespan_rose_chart")


def _render_lifespan_aggregates(key_prefix=""):
    """Render Aggregates chart with selectable chart types."""

    # Query for lifespan aggregates
    aggregates_query = """
    SELECT
        CASE
            WHEN is_transient = 'NO' THEN 'Permanent (Action Required)'
            ELSE 'Transient (Acceptable)'
        END AS "Table Category",
        COUNT(*) AS "Count of Short-Lived Tables",
        AVG(TIMEDIFF('minute', created, deleted)) AS "Avg Lifespan (Minutes)",
        SUM(bytes) / POW(1024, 3) AS "Est. Churned Storage (GB)"
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE deleted IS NOT NULL
      AND created >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND TIMEDIFF('hour', created, deleted) < 24
      AND table_type = 'BASE TABLE'
GROUP BY 1
    """

    try:
        aggregates_df = st.session_state.session.sql(aggregates_query).to_pandas()

        if len(aggregates_df) > 0:
            st.markdown("##### Aggregates")

            # Add chart type selector
            chart_type = st.selectbox(
                "Change Chart Type",
                ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                index=0,
                key=f"{key_prefix}aggregates_chart_type"
            )

            # Render selected chart type
            if chart_type == "Bar Chart":
                _render_aggregates_bar_chart(aggregates_df, key_prefix)
            elif chart_type == "Pie Chart":
                _render_aggregates_pie_chart(aggregates_df, key_prefix)
            elif chart_type == "Pie - Donut":
                _render_aggregates_donut_chart(aggregates_df, key_prefix)
            else:
                _render_aggregates_rose_chart(aggregates_df, key_prefix)
        else:
            st.markdown("##### Aggregates")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No aggregate data available for short-lived tables.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown("##### Aggregates")
        # st.error(f"Error loading aggregates: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading aggregates: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_aggregates_bar_chart(aggregates_df, key_prefix=""):
    """Render aggregates bar chart using ECharts."""

    df_sorted = aggregates_df.sort_values('Count of Short-Lived Tables', ascending=True)

    categories = df_sorted['Table Category'].tolist()
    count_data = df_sorted['Count of Short-Lived Tables'].tolist()
    avg_lifespan_data = [round(x, 1) if x is not None else 0 for x in df_sorted['Avg Lifespan (Minutes)'].tolist()]
    storage_data = [round(x, 2) if x is not None else 0 for x in df_sorted['Est. Churned Storage (GB)'].tolist()]

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 15,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "top": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "name": "Count / Minutes / GB",
            "nameLocation": "middle",
            "nameGap": 25
        },
        "yAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {"fontSize": 10}
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c"],
        "series": [
            {
                "name": "Table Count",
                "type": "bar",
                "data": count_data
            },
            {
                "name": "Avg Lifespan (Min)",
                "type": "bar",
                "data": avg_lifespan_data
            },
            {
                "name": "Storage (GB)",
                "type": "bar",
                "data": storage_data
            }
        ]
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}aggregates_bar_chart")


def _render_aggregates_pie_chart(aggregates_df, key_prefix=""):
    """Render aggregates pie chart using ECharts."""

    chart_data = [
        {"value": int(row['Count of Short-Lived Tables']), "name": f"{row['Table Category']} ({row['Count of Short-Lived Tables']} tables)"}
        for _, row in aggregates_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Short-Lived Tables",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}aggregates_pie_chart")


def _render_aggregates_donut_chart(aggregates_df, key_prefix=""):
    """Render aggregates donut chart using ECharts."""

    chart_data = [
        {"value": int(row['Count of Short-Lived Tables']), "name": f"{row['Table Category']} ({row['Count of Short-Lived Tables']} tables)"}
        for _, row in aggregates_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Short-Lived Tables",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}aggregates_donut_chart")


def _render_aggregates_rose_chart(aggregates_df, key_prefix=""):
    """Render aggregates rose chart using ECharts."""

    chart_data = [
        {"value": int(row['Count of Short-Lived Tables']), "name": f"{row['Table Category']} ({row['Count of Short-Lived Tables']} tables)"}
        for _, row in aggregates_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Short-Lived Tables",
                "type": "pie",
                "radius": [15, 90],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}aggregates_rose_chart")


def _render_high_churn_tables(key_prefix=""):
    """Render Top 20 High-Churn Tables chart with selectable chart types."""

    # Query for high-churn tables
    churn_query = """
    WITH storage_metrics AS (
        SELECT
            t.table_catalog,
            t.table_schema,
            t.table_name,
            t.is_transient,
            (sm.active_bytes / POW(1024, 3)) AS active_gb,
            (sm.time_travel_bytes / POW(1024, 3)) AS time_travel_gb,
            (sm.failsafe_bytes / POW(1024, 3)) AS failsafe_gb,
            ((sm.time_travel_bytes + sm.failsafe_bytes) / POW(1024, 3)) AS total_churn_gb,
            DIV0((sm.time_travel_bytes + sm.failsafe_bytes), NULLIF(sm.active_bytes, 0)) AS churn_ratio
        FROM SNOWFLAKE.ACCOUNT_USAGE.table_storage_metrics sm
        JOIN SNOWFLAKE.ACCOUNT_USAGE.tables t
            ON sm.id = t.table_id
        WHERE sm.deleted = FALSE
AND (sm.time_travel_bytes + sm.failsafe_bytes) > 0
    )
    SELECT
        table_schema || '.' || table_name AS "Table",
        CASE
            WHEN is_transient = 'YES' THEN 'Transient'
            ELSE 'Permanent (High Risk)'
        END AS "Type",
        ROUND(active_gb, 2) AS "Active Data (GB)",
        ROUND(total_churn_gb, 2) AS "Churn History (GB)",
        ROUND(churn_ratio, 1) AS "Churn Ratio (x)"
    FROM storage_metrics
    ORDER BY total_churn_gb DESC
    LIMIT 20
    """

    try:
        churn_df = st.session_state.session.sql(churn_query).to_pandas()

        if len(churn_df) > 0:
            st.markdown("##### Top 20 High-Churn Tables")

            # Add chart type selector
            chart_type = st.selectbox(
                "Change Chart Type",
                ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                index=0,
                key=f"{key_prefix}high_churn_chart_type"
            )

            # Render selected chart type
            if chart_type == "Bar Chart":
                _render_high_churn_bar_chart(churn_df, key_prefix)
            elif chart_type == "Pie Chart":
                _render_high_churn_pie_chart(churn_df, key_prefix)
            elif chart_type == "Pie - Donut":
                _render_high_churn_donut_chart(churn_df, key_prefix)
            else:
                _render_high_churn_rose_chart(churn_df, key_prefix)
        else:
            st.markdown("##### Top 20 High-Churn Tables")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No high-churn tables found.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown("##### Top 20 High-Churn Tables")
        # st.error(f"Error loading high-churn tables: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading high-churn tables: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_high_churn_bar_chart(churn_df, key_prefix=""):
    """Render high-churn tables bar chart using ECharts."""

    # Take top 10 for better visualization, sort ascending for horizontal bar
    df_sorted = churn_df.head(10).sort_values('Churn History (GB)', ascending=True)

    tables = df_sorted['Table'].tolist()
    active_data = df_sorted['Active Data (GB)'].tolist()
    churn_data = df_sorted['Churn History (GB)'].tolist()

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 15,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "top": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "name": "Storage (GB)",
            "nameLocation": "middle",
            "nameGap": 25
        },
        "yAxis": {
            "type": "category",
            "data": tables,
            "axisLabel": {"fontSize": 9, "width": 150, "overflow": "truncate"}
        },
        "color": ["#1f77b4", "#d62728"],
        "series": [
            {
                "name": "Active Data (GB)",
                "type": "bar",
                "data": active_data
            },
            {
                "name": "Churn History (GB)",
                "type": "bar",
                "data": churn_data
            }
        ]
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}high_churn_bar_chart")


def _render_high_churn_pie_chart(churn_df, key_prefix=""):
    """Render high-churn tables pie chart using ECharts - aggregated by Type."""

    # Aggregate by Type for pie chart
    agg_df = churn_df.groupby('Type').agg({
        'Churn History (GB)': 'sum'
    }).reset_index()

    chart_data = [
        {"value": round(row['Churn History (GB)'], 2), "name": f"{row['Type']} ({row['Churn History (GB)']:.2f} GB)"}
        for _, row in agg_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} GB ({d}%)"
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
                "name": "Churn by Type",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}high_churn_pie_chart")


def _render_high_churn_donut_chart(churn_df, key_prefix=""):
    """Render high-churn tables donut chart using ECharts."""

    agg_df = churn_df.groupby('Type').agg({
        'Churn History (GB)': 'sum'
    }).reset_index()

    chart_data = [
        {"value": round(row['Churn History (GB)'], 2), "name": f"{row['Type']} ({row['Churn History (GB)']:.2f} GB)"}
        for _, row in agg_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} GB ({d}%)"
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
                "name": "Churn by Type",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}high_churn_donut_chart")


def _render_high_churn_rose_chart(churn_df, key_prefix=""):
    """Render high-churn tables rose chart using ECharts."""

    agg_df = churn_df.groupby('Type').agg({
        'Churn History (GB)': 'sum'
    }).reset_index()

    chart_data = [
        {"value": round(row['Churn History (GB)'], 2), "name": f"{row['Type']} ({row['Churn History (GB)']:.2f} GB)"}
        for _, row in agg_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} GB ({d}%)"
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
                "name": "Churn by Type",
                "type": "pie",
                "radius": [15, 90],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}high_churn_rose_chart")


def _render_access_aggregates(key_prefix=""):
    """Render Access Aggregates chart with selectable chart types."""

    # Query for access aggregates
    access_query = """
    WITH access_log AS (
        SELECT
            f.value:objectDomain::STRING AS object_type,
            f.value:objectName::STRING AS object_name,
            f.value:objectId::INT AS object_id,
            query_start_time,
            user_name
        FROM SNOWFLAKE.ACCOUNT_USAGE.access_history,
        LATERAL FLATTEN(direct_objects_accessed) f
        WHERE query_start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        AND f.value:objectDomain::STRING NOT IN ('STAGE', 'UDF')
)
    SELECT
        object_type AS "Object Type",
        object_name AS "Object Name",
        COUNT(*) AS "Total Access Events",
        COUNT(DISTINCT user_name) AS "Distinct Users",
        MAX(query_start_time) AS "Last Accessed"
    FROM access_log
    GROUP BY 1, 2
    ORDER BY 3 DESC
    """

    try:
        access_df = st.session_state.session.sql(access_query).to_pandas()

        if len(access_df) > 0:
            st.markdown("##### Aggregates")

            # Add chart type selector
            chart_type = st.selectbox(
                "Change Chart Type",
                ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                index=0,
                key=f"{key_prefix}access_aggregates_chart_type"
            )

            # Aggregate by Object Type for charting
            agg_df = access_df.groupby('Object Type').agg({
                'Total Access Events': 'sum',
                'Distinct Users': 'sum'
            }).reset_index()

            # Render selected chart type
            if chart_type == "Bar Chart":
                _render_access_aggregates_bar_chart(agg_df, key_prefix)
            elif chart_type == "Pie Chart":
                _render_access_aggregates_pie_chart(agg_df, key_prefix)
            elif chart_type == "Pie - Donut":
                _render_access_aggregates_donut_chart(agg_df, key_prefix)
            else:
                _render_access_aggregates_rose_chart(agg_df, key_prefix)
        else:
            st.markdown("##### Aggregates")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No access history data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown("##### Aggregates")
        # st.error(f"Error loading access aggregates: {str(e)}")
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading access aggregates: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_access_aggregates_bar_chart(agg_df, key_prefix=""):
    """Render access aggregates bar chart using ECharts."""

    df_sorted = agg_df.sort_values('Total Access Events', ascending=True)

    object_types = df_sorted['Object Type'].tolist()
    access_data = df_sorted['Total Access Events'].tolist()
    users_data = df_sorted['Distinct Users'].tolist()

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 15,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "top": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "name": "Count",
            "nameLocation": "middle",
            "nameGap": 25
        },
        "yAxis": {
            "type": "category",
            "data": object_types,
            "axisLabel": {"fontSize": 10}
        },
        "color": ["#1f77b4", "#ff7f0e"],
        "series": [
            {
                "name": "Access Events",
                "type": "bar",
                "data": access_data
            },
            {
                "name": "Distinct Users",
                "type": "bar",
                "data": users_data
            }
        ]
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}access_aggregates_bar_chart")


def _render_access_aggregates_pie_chart(agg_df, key_prefix=""):
    """Render access aggregates pie chart using ECharts."""

    chart_data = [
        {"value": int(row['Total Access Events']), "name": f"{row['Object Type']} ({row['Total Access Events']:,} events)"}
        for _, row in agg_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Access Events",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}access_aggregates_pie_chart")


def _render_access_aggregates_donut_chart(agg_df, key_prefix=""):
    """Render access aggregates donut chart using ECharts."""

    chart_data = [
        {"value": int(row['Total Access Events']), "name": f"{row['Object Type']} ({row['Total Access Events']:,} events)"}
        for _, row in agg_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Access Events",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}access_aggregates_donut_chart")


def _render_access_aggregates_rose_chart(agg_df, key_prefix=""):
    """Render access aggregates rose chart using ECharts."""

    chart_data = [
        {"value": int(row['Total Access Events']), "name": f"{row['Object Type']} ({row['Total Access Events']:,} events)"}
        for _, row in agg_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
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
        "series": [
            {
                "name": "Access Events",
                "type": "pie",
                "radius": [15, 90],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}access_aggregates_rose_chart")


def _render_db_storage_bar_chart(db_storage_df):
    """Render database storage stacked bar chart using ECharts."""

    # Sort dataframe by total_storage ascending so largest values appear at top of horizontal bar chart
    db_storage_df_sorted = db_storage_df.sort_values('TOTAL_STORAGE', ascending=True)

    # Prepare data for ECharts horizontal stacked bar chart
    databases = db_storage_df_sorted['TABLE_CATALOG'].tolist()
    active_data = db_storage_df_sorted['ACTIVE_STORAGE'].tolist()
    time_travel_data = db_storage_df_sorted['TIME_TRAVEL_STORAGE'].tolist()
    failsafe_data = db_storage_df_sorted['FAILSAFE_STORAGE'].tolist()
    clone_data = db_storage_df_sorted['RETAINED_FOR_CLONE_STORAGE'].tolist()

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "formatter": "{b}<br/>{a0}: {c0} TB<br/>{a1}: {c1} TB<br/>{a2}: {c2} TB<br/>{a3}: {c3} TB"
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 15,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "top": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "name": "Storage (TB)",
            "nameLocation": "middle",
            "nameGap": 25
        },
        "yAxis": {
            "type": "category",
            "data": databases,
            "axisLabel": {"fontSize": 10}
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
        "series": [
            {
                "name": "Active Storage",
                "type": "bar",
                "stack": "total",
                "data": active_data
            },
            {
                "name": "Time Travel Storage",
                "type": "bar",
                "stack": "total",
                "data": time_travel_data
            },
            {
                "name": "Failsafe Storage",
                "type": "bar",
                "stack": "total",
                "data": failsafe_data
            },
            {
                "name": "Clone Storage",
                "type": "bar",
                "stack": "total",
                "data": clone_data
            }
        ]
    }

    st_echarts(options=option, height="400px", key="stacked_storage_chart")


def _render_db_storage_standard_pie_chart(db_storage_df):
    """Render database storage standard pie chart using ECharts."""

    # Prepare data for ECharts standard pie chart - show total storage per database
    chart_data = [
        {"value": float(row['TOTAL_STORAGE']), "name": f"{row['TABLE_CATALOG']} ({row['TOTAL_STORAGE']:.3f} TB)"}
        for _, row in db_storage_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} TB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Storage Size",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="400px", key="db_storage_pie_chart")


def _render_db_storage_donut_pie_chart(db_storage_df):
    """Render database storage donut pie chart using ECharts."""

    # Prepare data for ECharts donut pie chart - show total storage per database
    chart_data = [
        {"value": float(row['TOTAL_STORAGE']), "name": f"{row['TABLE_CATALOG']} ({row['TOTAL_STORAGE']:.3f} TB)"}
        for _, row in db_storage_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} TB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Storage Size",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="400px", key="db_storage_donut_chart")


def _render_db_storage_rose_pie_chart(db_storage_df):
    """Render database storage rose-type pie chart using ECharts."""

    # Prepare data for ECharts rose-type pie chart - show total storage per database
    chart_data = [
        {"value": float(row['TOTAL_STORAGE']), "name": f"{row['TABLE_CATALOG']} ({row['TOTAL_STORAGE']:.3f} TB)"}
        for _, row in db_storage_df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} TB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Storage Size",
                "type": "pie",
                "radius": [15, 90],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="400px", key="db_storage_rose_chart")


def _render_storage_bar_chart(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix=""):
    """Render storage distribution bar chart using Plotly."""

    storage_data = {
        'Storage Type': ['Active Storage', 'Time Travel Storage', 'Failsafe Storage', 'Clone Storage'],
        'Size (TB)': [active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage],
        'Colors': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    }

    fig_bar = go.Figure(data=[
        go.Bar(
            x=storage_data['Storage Type'],
            y=storage_data['Size (TB)'],
            marker_color=storage_data['Colors'],
            text=[f"{val:.3f} TB" for val in storage_data['Size (TB)']],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Size: %{y:.3f} TB<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=400,
        xaxis_title='Storage Type',
        yaxis_title='Size (TB)',
        showlegend=False,
        margin=dict(t=40, b=50, l=50, r=50)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}storage_bar_plotly")


def _render_storage_standard_pie_chart(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix=""):
    """Render storage distribution standard pie chart using ECharts."""

    # Prepare data for ECharts standard pie chart
    chart_data = [
        {"value": float(active_storage), "name": f"Active Storage ({active_storage:.3f} TB)"},
        {"value": float(time_travel_storage), "name": f"Time Travel Storage ({time_travel_storage:.3f} TB)"},
        {"value": float(failsafe_storage), "name": f"Failsafe Storage ({failsafe_storage:.3f} TB)"},
        {"value": float(retained_for_clone_storage), "name": f"Clone Storage ({retained_for_clone_storage:.3f} TB)"}
    ]

    # ECharts standard pie chart configuration
    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {
                "fontSize": 11
            }
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} TB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
        "series": [
            {
                "name": "Storage Size",
                "type": "pie",
                "radius": ["0%", "60%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    # Display the ECharts standard pie chart
    st_echarts(
        options=option,
        height="400px",
        key=f"{key_prefix}storage_pie_chart"
    )


def _render_storage_donut_pie_chart(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix=""):
    """Render storage distribution donut pie chart using ECharts."""

    # Prepare data for ECharts donut pie chart
    chart_data = [
        {"value": float(active_storage), "name": f"Active Storage ({active_storage:.3f} TB)"},
        {"value": float(time_travel_storage), "name": f"Time Travel Storage ({time_travel_storage:.3f} TB)"},
        {"value": float(failsafe_storage), "name": f"Failsafe Storage ({failsafe_storage:.3f} TB)"},
        {"value": float(retained_for_clone_storage), "name": f"Clone Storage ({retained_for_clone_storage:.3f} TB)"}
    ]

    # ECharts donut pie chart configuration
    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {
                "fontSize": 11
            }
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} TB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
        "series": [
            {
                "name": "Storage Size",
                "type": "pie",
                "radius": ["30%", "60%"],  # Donut chart (inner and outer radius)
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    # Display the ECharts donut pie chart
    st_echarts(
        options=option,
        height="400px",
        key=f"{key_prefix}storage_donut_chart"
    )


def _render_storage_rose_pie_chart(active_storage, time_travel_storage, failsafe_storage, retained_for_clone_storage, key_prefix=""):
    """Render storage distribution rose-type pie chart using ECharts."""

    # Prepare data for ECharts rose-type pie chart
    chart_data = [
        {"value": float(active_storage), "name": f"Active Storage ({active_storage:.3f} TB)"},
        {"value": float(time_travel_storage), "name": f"Time Travel Storage ({time_travel_storage:.3f} TB)"},
        {"value": float(failsafe_storage), "name": f"Failsafe Storage ({failsafe_storage:.3f} TB)"},
        {"value": float(retained_for_clone_storage), "name": f"Clone Storage ({retained_for_clone_storage:.3f} TB)"}
    ]

    # ECharts rose-type pie chart configuration
    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {
                "fontSize": 11
            }
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} TB ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
        "series": [
            {
                "name": "Storage Size",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    # Display the ECharts rose-type pie chart
    st_echarts(
        options=option,
        height="400px",
        key=f"{key_prefix}storage_rose_chart"
    )

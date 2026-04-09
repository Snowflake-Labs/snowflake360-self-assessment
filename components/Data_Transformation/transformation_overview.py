import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
from .problematic_query_report import comp_problematic_query_report
from .syntax_hunter import comp_syntax_hunter
from .object_structure_analysis import comp_object_structure_analysis
from .workload_shape import comp_workload_shape
from ._all_tf_queries import _ALL_TF_QUERIES


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_tf_queries(progress_bar=None, status_text=None):
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_TF_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    total = len(needed)
    completed = 0
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_run_query_thread, session, k, sql): k
            for k, sql in needed.items()
        }
        for future in as_completed(futures):
            key, df, err = future.result()
            st.session_state[key] = df
            completed += 1
            if progress_bar is not None:
                progress_bar.progress(completed / total)
            if status_text is not None:
                status_text.text(f"Loading data... ({completed}/{total} queries)")


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


def comp_transformation_overview(entry_actions=None):
    """
    Data Transformation Overview Component

    Renders sub-tabs for:
    - Overview: Comprehensive data transformation landscape assessment
    - Problematic Query - Report (Native Insights)
    - Syntax Hunter (Regex & Heuristics)
    - Object Structure Analysis (Stacked Views & Security)
    - Workload Shape (Updates, MVs, RAPs)

    Args:
        entry_actions: Optional callback actions on component entry
    """
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in _ALL_TF_QUERIES)
        if not all_cached:
            status_ph.markdown(
                '<p style="color: #003D73; font-weight: 600;">Loading Data Transformation data...</p>',
                unsafe_allow_html=True)
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_all_tf_queries(progress_bar=progress_bar_widget, status_text=status_ph)
            progress_ph.empty()
            status_ph.empty()
        else:
            _prefetch_all_tf_queries()
        sub_tabs = st.tabs([
            "Overview",
            "Problematic Query - Report (Native Insights)",
            "Syntax Hunter (Regex & Heuristics)",
            "Object Structure Analysis (Stacked Views & Security)",
            "Workload Shape (Updates, MVs, RAPs)"
        ])

        with sub_tabs[0]:
            _render_overview_content()

        with sub_tabs[1]:
            comp_problematic_query_report()

        with sub_tabs[2]:
            comp_syntax_hunter()

        with sub_tabs[3]:
            comp_object_structure_analysis()

        with sub_tabs[4]:
            comp_workload_shape()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Data Transformation Overview: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_overview_content():
    """Render the core data transformation overview content (landscape assessment, charts)."""
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

        # Build and execute the query
        query = f"""
WITH
-- 1. Clustered vs unclustered base tables
clustered_tables AS (
  SELECT
    SUM(CASE WHEN clustering_key IS NOT NULL THEN 1 ELSE 0 END) AS clustered_tables,
    SUM(CASE WHEN clustering_key IS NULL  THEN 1 ELSE 0 END)    AS unclustered_tables
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE table_type = 'BASE TABLE'
    AND deleted IS NULL
),

-- 2. Materialized views (defined)
materialized_views AS (
  SELECT COUNT(*) AS num_materialized_views
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE table_type = 'MATERIALIZED VIEW'
    AND deleted IS NULL
),

-- 3. Tables with semi-structured columns (VARIANT/OBJECT/ARRAY)
semi_structured_tables AS (
  SELECT
    COUNT(DISTINCT c.table_catalog || '.' || c.table_schema || '.' || c.table_name)
      AS num_tables_with_semi_structured
  FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS c
  JOIN SNOWFLAKE.ACCOUNT_USAGE.TABLES  t
    ON c.table_id = t.table_id
  WHERE t.table_type = 'BASE TABLE'
    AND t.deleted IS NULL
    AND c.deleted IS NULL
    AND c.data_type IN ('VARIANT','OBJECT','ARRAY')
),

-- 4. Dynamic tables
dynamic_tables AS (
  SELECT COUNT(*) AS num_dynamic_tables
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE is_dynamic = 'YES'
    AND deleted IS NULL
),

-- 5. Hybrid tables
hybrid_tables AS (
  SELECT COUNT(*) AS num_hybrid_tables
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE (is_hybrid = 'YES')
    AND deleted IS NULL
),

-- 6. Event tables
event_tables AS (
  SELECT COUNT(*) AS num_event_tables
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE table_type = 'EVENT TABLE'
    AND deleted IS NULL
),

-- 7. Semantic views
semantic_views AS (
  SELECT COUNT(*) AS num_semantic_views
  FROM SNOWFLAKE.ACCOUNT_USAGE.SEMANTIC_VIEWS
  WHERE deleted IS NULL
),

-- 8. Warehouses with spilling or high queueing in last 30 days
spill_or_queue_wh AS (
  SELECT
    COUNT(DISTINCT warehouse_name) AS num_warehouses_spill_or_queue_last_30d
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND warehouse_name IS NOT NULL
    AND (
         bytes_spilled_to_remote_storage > 0
      OR bytes_spilled_to_local_storage  > 0
      OR queued_overload_time            > 0
    )
),

-- 9. Short UPSERTs (MERGE with few rows affected) in last 30 days
short_upserts AS (
  SELECT
    COUNT(*) AS num_short_upserts_last_30d
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND query_type = 'MERGE'
    AND (rows_inserted + rows_updated) BETWEEN 1 AND 1000
),

-- 10. Snowpark queries in last 30 days (by client_application_id)
snowpark_queries AS (
  SELECT
    COUNT(DISTINCT q.query_id) AS num_snowpark_queries_last_30d
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
  JOIN SNOWFLAKE.ACCOUNT_USAGE.SESSIONS     s
    ON q.session_id = s.session_id
  WHERE q.start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND s.client_application_id ILIKE 'SNOWPARK%'
),

-- 11. Data clustering: tables with clustering keys and auto clustering ON
clustered_data AS (
  SELECT
    COUNT(*) AS num_clustered_tables_with_key,
    SUM(CASE WHEN auto_clustering_on = 'ON' THEN 1 ELSE 0 END)
      AS num_tables_with_auto_clustering
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE table_type = 'BASE TABLE'
    AND deleted IS NULL
    AND clustering_key IS NOT NULL
),

-- 12. High cloud services usage days in last 30 days
high_cloud_services AS (
  SELECT
    COUNT(*) AS num_wh_days_high_cloud_services_last_30d
  FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND credits_used_cloud_services > 10
)

SELECT
  -- Clustered vs unclustered tables
  ct.clustered_tables,
  ct.unclustered_tables,

  -- Materialized views
  mv.num_materialized_views,

  -- Semi-structured tables
  ss.num_tables_with_semi_structured,

  -- Dynamic, hybrid, event tables
  dt.num_dynamic_tables,
  ht.num_hybrid_tables,
  et.num_event_tables,

  -- Semantic views
  sv.num_semantic_views,

  -- Spill / high queue
  w.num_warehouses_spill_or_queue_last_30d,

  -- Short upserts
  su.num_short_upserts_last_30d,

  -- Snowpark
  sp.num_snowpark_queries_last_30d,

  -- Data clustering
  cd.num_clustered_tables_with_key,
  cd.num_tables_with_auto_clustering,

  -- High cloud services usage
  hc.num_wh_days_high_cloud_services_last_30d

FROM clustered_tables     ct
CROSS JOIN materialized_views mv
CROSS JOIN semi_structured_tables ss
CROSS JOIN dynamic_tables   dt
CROSS JOIN hybrid_tables    ht
CROSS JOIN event_tables     et
CROSS JOIN semantic_views   sv
CROSS JOIN spill_or_queue_wh w
CROSS JOIN short_upserts    su
CROSS JOIN snowpark_queries sp
CROSS JOIN clustered_data   cd
CROSS JOIN high_cloud_services hc
        """


        # Execute query
        try:
            df = _cached_sql("tf_overview", query)
        except Exception as e:
            # st.error(f"Error executing query: {str(e)}")
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No data transformation landscape data found.'
                        '</div>', unsafe_allow_html=True)
            return

        # Create expander with introduction text
        with st.expander("Data Transformation Landscape Assessment", expanded=True):
            # Introduction text without CSS styling
            st.markdown("Comprehensive data transformation landscape assessment covering table types, clustering status, "
                       "materialized views, semi-structured data, dynamic/hybrid/event tables, semantic views, "
                       "warehouse performance issues, and Snowpark usage.")

            # st.markdown("---")


            # Transpose the data for better display
            display_df = df.T.reset_index()
            display_df.columns = ['METRIC', 'VALUE']

            # Make the metric names more readable
            metric_names = {
                'CLUSTERED_TABLES': 'Clustered Tables',
                'UNCLUSTERED_TABLES': 'Unclustered Tables',
                'NUM_MATERIALIZED_VIEWS': 'Materialized Views',
                'NUM_TABLES_WITH_SEMI_STRUCTURED': 'Tables with Semi-Structured Data',
                'NUM_DYNAMIC_TABLES': 'Dynamic Tables',
                'NUM_HYBRID_TABLES': 'Hybrid Tables',
                'NUM_EVENT_TABLES': 'Event Tables',
                'NUM_SEMANTIC_VIEWS': 'Semantic Views',
                'NUM_WAREHOUSES_SPILL_OR_QUEUE_LAST_30D': 'Warehouses with Spill/Queue (30d)',
                'NUM_SHORT_UPSERTS_LAST_30D': 'Short UPSERTs (30d)',
                'NUM_SNOWPARK_QUERIES_LAST_30D': 'Snowpark Queries (30d)',
                'NUM_CLUSTERED_TABLES_WITH_KEY': 'Tables with Clustering Key',
                'NUM_TABLES_WITH_AUTO_CLUSTERING': 'Tables with Auto Clustering',
                'NUM_WH_DAYS_HIGH_CLOUD_SERVICES_LAST_30D': 'High Cloud Services Days (30d)'
            }
            display_df['METRIC'] = display_df['METRIC'].apply(lambda x: metric_names.get(x, x))

            try:
                clustered = int(df.iloc[0]['CLUSTERED_TABLES'])
                unclustered = int(df.iloc[0]['UNCLUSTERED_TABLES'])
                total_row = pd.DataFrame({'METRIC': ['Total Base Tables'], 'VALUE': [clustered + unclustered]})
                display_df = pd.concat([total_row, display_df], ignore_index=True)
            except Exception:
                pass

            st.dataframe(display_df, use_container_width=True)

            # Charts Section
            # st.markdown("---")
            st.markdown("#### Transformation Landscape Charts")

            # Prepare data for charts from the original dataframe
            row = df.iloc[0]

            # Row 1: Two charts
            col1, col2 = st.columns(2)

            with col1.container():
                st.markdown("##### Table Clustering Distribution")
                _render_clustering_chart(row, key_prefix="clustering_")

            with col2.container():
                st.markdown("##### Table Types Distribution")
                _render_table_types_chart(row, key_prefix="table_types_")

            # Row 2: Two charts
            col3, col4 = st.columns(2)

            with col3.container():
                st.markdown("##### Warehouse Performance Issues (30 Days)")
                _render_warehouse_issues_chart(row, key_prefix="wh_issues_")

            with col4.container():
                st.markdown("##### Query & Usage Patterns (30 Days)")
                _render_query_patterns_chart(row, key_prefix="query_patterns_")

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ============================
# Chart Type Selector & Charts
# ============================

def _render_clustering_chart(row, key_prefix=""):
    """Render table clustering distribution chart with selectable chart types."""


    _render_clustering_bar_chart(row, key_prefix)


def _render_clustering_bar_chart(row, key_prefix=""):
    """Render clustering bar chart using Plotly."""
    categories = ['Clustered Tables', 'Unclustered Tables', 'Auto Clustering ON']
    values = [
        int(row['CLUSTERED_TABLES']),
        int(row['UNCLUSTERED_TABLES']),
        int(row['NUM_TABLES_WITH_AUTO_CLUSTERING'])
    ]

    # Sort for horizontal bar layout
    sorted_data = sorted(zip(values, categories), reverse=False)
    values_sorted = [v for v, c in sorted_data]
    categories_sorted = [c for v, c in sorted_data]

    fig = go.Figure(data=[
        go.Bar(
            y=categories_sorted,
            x=values_sorted,
            orientation='h',
            marker_color='#29B5E8',
            text=[f"{int(val)}" for val in values_sorted],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Number of Tables',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=120, r=50)
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_object_lifecycle():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Object Lifecycle:</b> Tables grouped by age (since creation) and type. '
        'Helps identify stale or legacy objects that may need review.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            CASE
                WHEN DATEDIFF('day', created, CURRENT_TIMESTAMP()) <= 30 THEN '0-30 days'
                WHEN DATEDIFF('day', created, CURRENT_TIMESTAMP()) <= 90 THEN '31-90 days'
                WHEN DATEDIFF('day', created, CURRENT_TIMESTAMP()) <= 365 THEN '91-365 days'
                ELSE '365+ days'
            END AS age_bucket,
            table_type,
            COUNT(*) AS object_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
        WHERE deleted IS NULL
          AND table_catalog != 'SNOWFLAKE'
          AND table_schema != 'INFORMATION_SCHEMA'
        GROUP BY age_bucket, table_type
        ORDER BY age_bucket, object_count DESC
        """
        df = _cached_sql("dt_object_lifecycle", query)
        if df.empty:
            st.info("No table lifecycle data available.")
            return
        df['OBJECT_COUNT'] = pd.to_numeric(df['OBJECT_COUNT'], errors='coerce').fillna(0)
        pivot = df.pivot_table(index='AGE_BUCKET', columns='TABLE_TYPE', values='OBJECT_COUNT', aggfunc='sum', fill_value=0)
        bucket_order = ['0-30 days', '31-90 days', '91-365 days', '365+ days']
        pivot = pivot.reindex([b for b in bucket_order if b in pivot.index])
        colors = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229', '#1A7DA8', '#023E8A']
        fig = go.Figure()
        for i, col in enumerate(pivot.columns):
            fig.add_trace(go.Bar(name=col, x=pivot.index, y=pivot[col], marker_color=colors[i % len(colors)]))
        fig.update_layout(
            barmode='stack', title='Object Count by Age and Type',
            xaxis_title='Age Bucket', yaxis_title='Object Count',
            height=380, margin=dict(t=50, b=60),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_micro_transaction_pattern():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Micro-Transaction Pattern:</b> Short UPSERT/MERGE operations (execution <500ms) '
        'that may indicate row-level transactional workloads better suited for batching or hybrid tables.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            warehouse_name,
            database_name,
            COUNT(*) AS short_upsert_count,
            ROUND(AVG(total_elapsed_time), 1) AS avg_elapsed_ms,
            ROUND(SUM(credits_used_cloud_services), 4) AS cloud_services_credits,
            COUNT(DISTINCT user_name) AS distinct_users
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
          AND query_type IN ('MERGE', 'UPDATE', 'INSERT')
          AND total_elapsed_time < 500
          AND rows_produced <= 10
        GROUP BY warehouse_name, database_name
        HAVING COUNT(*) > 50
        ORDER BY short_upsert_count DESC
        LIMIT 20
        """
        df = _cached_sql("dt_micro_tx", query)
        if df.empty:
            st.success("No significant micro-transaction patterns detected.")
            return
        df['SHORT_UPSERT_COUNT'] = pd.to_numeric(df['SHORT_UPSERT_COUNT'], errors='coerce').fillna(0)
        st.metric("Total Micro-Transaction Operations (30d)", int(df['SHORT_UPSERT_COUNT'].sum()))
        df['LABEL'] = df['DATABASE_NAME'] + ' / ' + df['WAREHOUSE_NAME']
        fig = go.Figure(go.Bar(
            y=df['LABEL'].head(15), x=df['SHORT_UPSERT_COUNT'].head(15),
            orientation='h', marker_color='#E8A229',
            text=df['SHORT_UPSERT_COUNT'].head(15).astype(int), textposition='outside'
        ))
        fig.update_layout(
            title='Top Micro-Transaction Sources',
            xaxis_title='Operation Count', height=max(300, 15 * 30 + 80),
            margin=dict(t=50, l=250, r=40, b=60)
        )
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_table_types_chart(row, key_prefix=""):
    """Render table types distribution chart with selectable chart types."""


    _render_table_types_bar_chart(row, key_prefix)


def _render_table_types_bar_chart(row, key_prefix=""):
    """Render table types bar chart using Plotly."""
    categories = ['Materialized Views', 'Semi-Structured Tables', 'Dynamic Tables', 'Hybrid Tables', 'Event Tables', 'Semantic Views']
    values = [
        int(row['NUM_MATERIALIZED_VIEWS']),
        int(row['NUM_TABLES_WITH_SEMI_STRUCTURED']),
        int(row['NUM_DYNAMIC_TABLES']),
        int(row['NUM_HYBRID_TABLES']),
        int(row['NUM_EVENT_TABLES']),
        int(row['NUM_SEMANTIC_VIEWS'])
    ]

    # Sort for horizontal bar layout
    sorted_data = sorted(zip(values, categories), reverse=False)
    values_sorted = [v for v, c in sorted_data]
    categories_sorted = [c for v, c in sorted_data]

    fig = go.Figure(data=[
        go.Bar(
            y=categories_sorted,
            x=values_sorted,
            orientation='h',
            marker_color='#11567F',
            text=[f"{int(val)}" for val in values_sorted],
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
        margin=dict(t=20, b=50, l=150, r=50)
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_warehouse_issues_chart(row, key_prefix=""):
    """Render warehouse performance issues chart with selectable chart types."""


    _render_warehouse_issues_bar_chart(row, key_prefix)


def _render_warehouse_issues_bar_chart(row, key_prefix=""):
    """Render warehouse issues bar chart using Plotly."""
    categories = ['WH with Spill/Queue', 'High Cloud Services Days']
    values = [
        int(row['NUM_WAREHOUSES_SPILL_OR_QUEUE_LAST_30D']),
        int(row['NUM_WH_DAYS_HIGH_CLOUD_SERVICES_LAST_30D'])
    ]

    # Sort for horizontal bar layout
    sorted_data = sorted(zip(values, categories), reverse=False)
    values_sorted = [v for v, c in sorted_data]
    categories_sorted = [c for v, c in sorted_data]

    fig = go.Figure(data=[
        go.Bar(
            y=categories_sorted,
            x=values_sorted,
            orientation='h',
            marker_color='#E8A229',
            text=[f"{int(val)}" for val in values_sorted],
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
        margin=dict(t=20, b=50, l=160, r=50)
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_query_patterns_chart(row, key_prefix=""):
    """Render query and usage patterns chart with selectable chart types."""


    _render_query_patterns_bar_chart(row, key_prefix)


def _render_query_patterns_bar_chart(row, key_prefix=""):
    """Render query patterns bar chart using Plotly."""
    categories = ['Short UPSERTs', 'Snowpark Queries']
    values = [
        int(row['NUM_SHORT_UPSERTS_LAST_30D']),
        int(row['NUM_SNOWPARK_QUERIES_LAST_30D'])
    ]

    # Sort for horizontal bar layout
    sorted_data = sorted(zip(values, categories), reverse=False)
    values_sorted = [v for v, c in sorted_data]
    categories_sorted = [c for v, c in sorted_data]

    fig = go.Figure(data=[
        go.Bar(
            y=categories_sorted,
            x=values_sorted,
            orientation='h',
            marker_color='#75C2D8',
            text=[f"{int(val):,}" for val in values_sorted],
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
        margin=dict(t=20, b=50, l=120, r=50)
    )
    st.plotly_chart(fig, use_container_width=True)




import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

_DML_SQL = """
SELECT
    REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?') AS query_pattern,
    query_type,
    COUNT(*) AS execution_count,
    ROUND(AVG(execution_time), 2) AS avg_duration_ms,
    SUM(rows_inserted + rows_updated + rows_deleted) AS total_rows_affected,
    CASE
        WHEN AVG(execution_time) < 500 AND COUNT(*) > 100 THEN '⚠️ Micro-Updates (Batch these!)'
        WHEN COUNT(*) > 50 THEN '✅ Frequent Pattern'
        ELSE 'OK'
    END AS recommendation
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE query_type IN ('UPDATE', 'INSERT', 'DELETE')
  AND start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?'), query_type
HAVING COUNT(*) > 50
ORDER BY execution_count DESC
LIMIT 20
"""

_MV_INVENTORY_SQL = """
SELECT
    table_catalog || '.' || table_schema || '.' || table_name AS mv_name,
    ROUND(COALESCE(bytes, 0) / POW(1024, 3), 4) AS size_gb,
    COALESCE(row_count, 0) AS row_count,
    created::DATE AS created_date
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE table_type = 'MATERIALIZED VIEW'
  AND deleted IS NULL
ORDER BY bytes DESC NULLS LAST
LIMIT 100
"""

_LIFECYCLE_AGG_SQL = """
WITH short_lived AS (
    SELECT 'SHORT_LIVED' AS lifespan_category, COUNT(*) AS object_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
    WHERE deleted IS NOT NULL
      AND DATEDIFF('minute', created, deleted) < 60
      AND table_type != 'TEMPORARY'
),
secure_views AS (
    SELECT 'SECURE_VIEW' AS lifespan_category, COUNT(*) AS object_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.VIEWS
    WHERE is_secure = 'YES' AND deleted IS NULL
),
temp_tables AS (
    SELECT 'TEMP_TABLE' AS lifespan_category, COUNT(*) AS object_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
    WHERE table_type = 'TEMPORARY' AND deleted IS NULL
)
SELECT * FROM short_lived
UNION ALL SELECT * FROM secure_views
UNION ALL SELECT * FROM temp_tables
ORDER BY object_count DESC
"""

_MV_COST_SQL = """
SELECT
    table_name AS mv_name,
    COUNT(*) AS refresh_count,
    ROUND(SUM(credits_used), 4) AS refresh_cost_credits,
    ROUND(AVG(credits_used), 6) AS avg_cost_per_refresh
FROM SNOWFLAKE.ACCOUNT_USAGE.materialized_view_refresh_history
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY 3 DESC
"""

_PERF_SQL = """
WITH micro_updates AS (
    SELECT
        COUNT(*) AS total_executions,
        COUNT(DISTINCT REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?')) AS unique_patterns
    FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
    WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND query_type IN ('UPDATE', 'INSERT', 'DELETE')
      AND execution_time < 500
),
rap_impact AS (
    SELECT
        COUNT(DISTINCT q.query_id) AS slow_protected_queries,
        AVG(q.execution_time) / 1000 AS avg_duration_sec
    FROM SNOWFLAKE.ACCOUNT_USAGE.access_history ah
    JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
        ON ah.query_id = q.query_id
    , LATERAL FLATTEN(ah.direct_objects_accessed) f
    JOIN SNOWFLAKE.ACCOUNT_USAGE.policy_references pr
        ON f.value:objectName::STRING = pr.ref_entity_name
    WHERE ah.query_start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND q.execution_time > 5000
      AND pr.policy_kind = 'ROW_ACCESS_POLICY'
),
mv_churn AS (
    SELECT
        COUNT(DISTINCT table_name) AS active_mvs,
        SUM(credits_used) AS total_maintenance_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.materialized_view_refresh_history
    WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
)
, AGGR AS (
SELECT 'Micro-Updates (Short Modifies)' AS metric_category, 'Total Executions (<500ms)' AS metric_name, total_executions::STRING AS value FROM micro_updates
UNION ALL SELECT 'Micro-Updates (Short Modifies)', 'Distinct Patterns Detected', unique_patterns::STRING FROM micro_updates
UNION ALL SELECT 'Row Access Policies (Security)', 'Slow Queries on Protected Tables (>5s)', slow_protected_queries::STRING FROM rap_impact
UNION ALL SELECT 'Materialized Views', 'Total Refresh Cost (Credits)', ROUND(total_maintenance_credits, 2)::STRING FROM mv_churn
UNION ALL SELECT 'Materialized Views', 'Active MVs Refreshed', active_mvs::STRING FROM mv_churn)
SELECT A.* FROM AGGR A
"""


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


def _warn(msg):
    st.markdown(
        f'<div style="background-color:#fff3cd;border-left:6px solid #ffc107;padding:10px;">'
        f'⚠️&nbsp;&nbsp;{msg}</div>', unsafe_allow_html=True)


def _err(msg):
    st.markdown(
        f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
        f'🛑&nbsp;&nbsp;{msg}</div>', unsafe_allow_html=True)


def comp_workload_shape(entry_actions=None):
    try:
        try:
            from snowflake.snowpark.context import get_active_session
            session = get_active_session()
        except Exception as e:
            _err(f"Unable to get Snowflake session: {e}")
            return

        if not session:
            _warn("Snowflake session not available.")
            return

        # =====================================================================
        # Expander 1: DML Pattern Analysis
        # =====================================================================
        with st.expander("DML Pattern Analysis (UPDATE/INSERT/DELETE)", expanded=True):
            st.write("DML patterns from the last 7 days with >50 executions in the selected metric run. "
                     "Micro-updates (<500 ms, >100 executions) are flagged for batching.")
            try:
                dml_df = _cached_sql("tf_workload_shape_v2", _DML_SQL)
            except Exception as e:
                _err(f"Error executing DML query: {e}")
                dml_df = pd.DataFrame()

            if dml_df.empty:
                _warn("No DML pattern data found for the last 7 days with more than 50 executions.")
            else:
                dml_df.columns = [
                    'QUERY_PATTERN', 'QUERY_TYPE', 'EXECUTION_COUNT',
                    'AVG_DURATION_MS', 'TOTAL_ROWS_AFFECTED', 'RECOMMENDATION'
                ]
                dml_df['EXECUTION_COUNT'] = pd.to_numeric(dml_df['EXECUTION_COUNT'], errors='coerce').fillna(0)
                dml_df['AVG_DURATION_MS'] = pd.to_numeric(dml_df['AVG_DURATION_MS'], errors='coerce').fillna(0)
                dml_df['TOTAL_ROWS_AFFECTED'] = pd.to_numeric(dml_df['TOTAL_ROWS_AFFECTED'], errors='coerce').fillna(0)
                st.dataframe(dml_df, use_container_width=True)

                st.markdown("**DML Charts**")

                _render_top20_exec_chart(dml_df)

                ch1, ch2 = st.columns(2)
                with ch1:
                    st.markdown("**Recommendation Distribution**")
                    _render_recommendation_donut(dml_df)
                with ch2:
                    st.markdown("**Executions by DML Type**")
                    _render_dml_type_chart(dml_df)

                _render_rows_affected_chart(dml_df)

        # =====================================================================
        # Expander 2: Materialized Views Inventory
        # =====================================================================
        with st.expander("Materialized Views Inventory", expanded=True):
            st.write("Top 100 materialized views by size.")
            try:
                mv_inv_df = _cached_sql("tf_mv_inventory", _MV_INVENTORY_SQL)
            except Exception as e:
                _err(f"Error: {e}")
                mv_inv_df = pd.DataFrame()

            if mv_inv_df.empty:
                _warn("No materialized views found.")
            else:
                st.dataframe(mv_inv_df, use_container_width=True)

        # =====================================================================
        # Expander 3: Object Lifecycle Analysis
        # =====================================================================
        with st.expander("Object Lifecycle Analysis", expanded=True):
            st.write("Categorises objects by lifecycle: temporary tables, short-lived tables "
                     "(deleted within 60 min), and secure views.")
            try:
                lc_df = _cached_sql("tf_lifecycle_agg", _LIFECYCLE_AGG_SQL)
            except Exception as e:
                _err(f"Error: {e}")
                lc_df = pd.DataFrame()

            if lc_df.empty:
                _warn("No lifecycle data found.")
            else:
                lc_df.columns = ['LIFESPAN_CATEGORY', 'OBJECT_COUNT']
                lc_df['OBJECT_COUNT'] = pd.to_numeric(lc_df['OBJECT_COUNT'], errors='coerce').fillna(0)
                lc_df = lc_df[lc_df['OBJECT_COUNT'] > 0].reset_index(drop=True)

                lc_col1, lc_col2 = st.columns(2)
                with lc_col1:
                    st.markdown("**Object Count by Lifecycle Category**")
                    _render_lifecycle_bar(lc_df)
                with lc_col2:
                    st.markdown("**Lifecycle Distribution**")
                    _render_lifecycle_donut(lc_df)

        # =====================================================================
        # Expander 4: Materialized View Refresh Costs
        # =====================================================================
        with st.expander("Materialized View Refresh Costs", expanded=True):
            st.write("Credit cost per MV refresh over the last 7 days. High-frequency, "
                     "high-cost refresh patterns are candidates for reviewing base table update patterns.")
            try:
                mv_cost_df = _cached_sql("tf_mv_refresh_cost", _MV_COST_SQL)
            except Exception as e:
                _err(f"Error: {e}")
                mv_cost_df = pd.DataFrame()

            if mv_cost_df.empty:
                _warn("No MV refresh cost data found.")
            else:
                mv_cost_df.columns = ['MV_NAME', 'REFRESH_COUNT', 'REFRESH_COST_CREDITS', 'AVG_COST_PER_REFRESH']
                st.dataframe(mv_cost_df, use_container_width=True)

        # =====================================================================
        # Expander 5: RAP Impact Dashboard
        # =====================================================================
        with st.expander("RAP Impact Dashboard (Row Access Policies & MV Costs)", expanded=True):
            st.write("Performance dashboard aggregating micro-update counts, row access policy impact "
                     "on slow queries, and materialized view refresh costs over last 7 days.")
            try:
                perf_df = _cached_sql("tf_perf_insights", _PERF_SQL)
            except Exception as e:
                _err(f"Error: {e}")
                perf_df = pd.DataFrame()

            if perf_df.empty:
                _warn("No performance dashboard data found for the last 7 days.")
            else:
                perf_df.columns = ['METRIC_CATEGORY', 'METRIC_NAME', 'VALUE']
                st.dataframe(perf_df, use_container_width=True)

                rap_col1, rap_col2 = st.columns(2)
                with rap_col1:
                    st.markdown("**Workload Metrics by Category**")
                    _render_rap_metrics_bar(perf_df)
                with rap_col2:
                    st.markdown("**Category Distribution**")
                    _render_rap_category_donut(perf_df)

    except Exception as e:
        _err(f"Component Error: {e}")


# ============================
# DML Charts
# ============================

def _render_top20_exec_chart(df):
    st.markdown("**Top 20 Patterns by Execution Count**")
    plot_df = df.sort_values('EXECUTION_COUNT', ascending=True).copy()
    plot_df['DISPLAY'] = plot_df['QUERY_PATTERN'].apply(
        lambda x: str(x)[:60] + '...' if len(str(x)) > 60 else str(x))
    fig = go.Figure(go.Bar(
        y=plot_df['DISPLAY'], x=plot_df['EXECUTION_COUNT'],
        orientation='h', marker_color=_C1,
        text=[f"{int(v):,}" for v in plot_df['EXECUTION_COUNT']],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Executions: %{x:,}<extra></extra>'
    ))
    fig.update_layout(
        height=max(400, len(plot_df) * 28 + 80),
        xaxis_title='Executions', yaxis_title='',
        showlegend=False, margin=dict(t=20, b=50, l=300, r=80))
    st.plotly_chart(fig, use_container_width=True)


def _render_recommendation_donut(df):
    rec_counts = df['RECOMMENDATION'].value_counts().reset_index()
    rec_counts.columns = ['RECOMMENDATION', 'COUNT']
    colors = [_CA if '⚠️' in str(r) else _C1 for r in rec_counts['RECOMMENDATION']]
    fig = go.Figure(go.Pie(
        labels=rec_counts['RECOMMENDATION'], values=rec_counts['COUNT'],
        hole=0.45, marker_colors=colors,
        textinfo='label+percent', textposition='outside'
    ))
    fig.update_layout(
        height=350, showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.35),
        margin=dict(t=20, b=100, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)


def _render_dml_type_chart(df):
    type_counts = df.groupby('QUERY_TYPE')['EXECUTION_COUNT'].sum().reset_index()
    type_counts = type_counts.sort_values('EXECUTION_COUNT', ascending=True)
    fig = go.Figure(go.Bar(
        y=type_counts['QUERY_TYPE'], x=type_counts['EXECUTION_COUNT'],
        orientation='h', marker_color=_C2,
        text=[f"{int(v):,}" for v in type_counts['EXECUTION_COUNT']],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Executions: %{x:,}<extra></extra>'
    ))
    fig.update_layout(
        height=350, xaxis_title='Executions', yaxis_title='',
        showlegend=False, margin=dict(t=20, b=50, l=80, r=80))
    st.plotly_chart(fig, use_container_width=True)


def _render_rows_affected_chart(df):
    st.markdown("**Rows Affected by Pattern**")
    plot_df = df.copy()
    plot_df['TOTAL_ROWS_AFFECTED'] = pd.to_numeric(plot_df['TOTAL_ROWS_AFFECTED'], errors='coerce').fillna(0)
    plot_df = plot_df[plot_df['TOTAL_ROWS_AFFECTED'] > 0].sort_values('TOTAL_ROWS_AFFECTED', ascending=True)
    if plot_df.empty:
        _warn("No row affected data available.")
        return
    plot_df['DISPLAY'] = plot_df['QUERY_PATTERN'].apply(
        lambda x: str(x)[:60] + '...' if len(str(x)) > 60 else str(x))
    fig = go.Figure(go.Bar(
        y=plot_df['DISPLAY'], x=plot_df['TOTAL_ROWS_AFFECTED'],
        orientation='h', marker_color=_C3,
        text=[f"{int(v):,}" for v in plot_df['TOTAL_ROWS_AFFECTED']],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Rows Affected: %{x:,}<extra></extra>'
    ))
    fig.update_layout(
        height=max(400, len(plot_df) * 28 + 80),
        xaxis_title='Rows Affected', yaxis_title='',
        showlegend=False, margin=dict(t=20, b=50, l=300, r=80))
    st.plotly_chart(fig, use_container_width=True)


# ============================
# Lifecycle Charts
# ============================

def _render_lifecycle_bar(df):
    plot_df = df.sort_values('OBJECT_COUNT', ascending=True)
    colors = [_C1, _C2, _C3, _CA][:len(plot_df)]
    fig = go.Figure(go.Bar(
        y=plot_df['LIFESPAN_CATEGORY'], x=plot_df['OBJECT_COUNT'],
        orientation='h', marker_color=colors,
        text=[f"{int(v):,}" for v in plot_df['OBJECT_COUNT']],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
    ))
    fig.update_layout(
        height=350, xaxis_title='Object Count', yaxis_title='',
        showlegend=False, margin=dict(t=20, b=50, l=120, r=80))
    st.plotly_chart(fig, use_container_width=True)


def _render_lifecycle_donut(df):
    colors = [_C1, _C2, _C3, _CA][:len(df)]
    fig = go.Figure(go.Pie(
        labels=df['LIFESPAN_CATEGORY'], values=df['OBJECT_COUNT'],
        hole=0.45, marker_colors=colors,
        textinfo='label+percent', textposition='outside'
    ))
    fig.update_layout(
        height=350, showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.35),
        margin=dict(t=20, b=100, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)


# ============================
# RAP Dashboard Charts
# ============================

def _render_rap_metrics_bar(df):
    plot_df = df.copy()
    plot_df['NUMERIC_VALUE'] = pd.to_numeric(plot_df['VALUE'], errors='coerce').fillna(0)
    plot_df = plot_df.sort_values('NUMERIC_VALUE', ascending=True)
    fig = go.Figure(go.Bar(
        y=plot_df['METRIC_NAME'], x=plot_df['NUMERIC_VALUE'],
        orientation='h', marker_color=_C1,
        text=[str(v) for v in plot_df['VALUE']],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Value: %{text}<extra></extra>'
    ))
    fig.update_layout(
        height=350, xaxis_title='Value', yaxis_title='',
        showlegend=False, margin=dict(t=20, b=50, l=240, r=80))
    st.plotly_chart(fig, use_container_width=True)


def _render_rap_category_donut(df):
    cat_totals = df.copy()
    cat_totals['NUMERIC_VALUE'] = pd.to_numeric(cat_totals['VALUE'], errors='coerce').fillna(0)
    cat_df = cat_totals.groupby('METRIC_CATEGORY')['NUMERIC_VALUE'].sum().reset_index()
    colors = [_C1, _C2, _C3][:len(cat_df)]
    fig = go.Figure(go.Pie(
        labels=cat_df['METRIC_CATEGORY'], values=cat_df['NUMERIC_VALUE'],
        hole=0.45, marker_colors=colors,
        textinfo='label+percent', textposition='outside'
    ))
    fig.update_layout(
        height=350, showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.35),
        margin=dict(t=20, b=100, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)

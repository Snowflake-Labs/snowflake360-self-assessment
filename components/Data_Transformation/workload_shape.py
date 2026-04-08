import streamlit as st
import pandas as pd
import plotly.graph_objects as go


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


_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'


def comp_workload_shape(entry_actions=None):
    try:
        try:
            from snowflake.snowpark.context import get_active_session
            session = get_active_session()
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Unable to get Snowflake session: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if not session:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;Snowflake session not available.'
                            '</div>', unsafe_allow_html=True)
            return

        _render_dml_pattern_analysis()
        _render_mv_inventory()
        _render_mv_refresh_costs()
        _render_rap_impact_dashboard()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_dml_pattern_analysis():
    with st.expander("DML Pattern Analysis (UPDATE/INSERT/DELETE)", expanded=True):
        st.markdown("DML patterns from the last 7 days with >50 executions in the selected metric run. "
                   "Micro-updates (<500 ms, >100 executions) are flagged for batching.")

        query = """
SELECT
    REGEXP_REPLACE(query_text, '\\\\b\\\\d+\\\\b', '?') AS query_pattern,
    query_type,
    COUNT(*) AS execution_count,
    ROUND(AVG(execution_time), 2) AS avg_duration_ms,
    SUM(rows_inserted + rows_updated + rows_deleted) AS total_rows_affected,
    CASE
        WHEN AVG(execution_time) < 500 AND COUNT(*) > 100 THEN 'MICRO_UPDATES_BATCH_RECOMMENDED'
        WHEN COUNT(*) > 50 THEN 'FREQUENT_PATTERN'
        ELSE 'OK'
    END AS recommendation
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE query_type IN ('UPDATE', 'INSERT', 'DELETE')
  AND start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY ALL
HAVING count(*) > 50
ORDER BY 3 DESC
LIMIT 20
"""

        try:
            dml_df = _cached_sql("tf_workload_shape_v2", query)
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                        f'🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)
            return

        if dml_df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px;">'
                        '⚠️&nbsp;&nbsp;No DML pattern data found for the last 7 days with more than 50 executions.'
                        '</div>', unsafe_allow_html=True)
            return

        st.dataframe(dml_df)

        st.markdown("#### DML Charts")

        top20 = dml_df.head(20).copy()
        top20['DISPLAY'] = top20['QUERY_PATTERN'].apply(lambda x: str(x)[:60] + '...' if len(str(x)) > 60 else str(x))
        plot_top = top20.sort_values('EXECUTION_COUNT', ascending=True)

        fig = go.Figure(data=[go.Bar(
            y=plot_top['DISPLAY'], x=plot_top['EXECUTION_COUNT'], orientation='h',
            marker_color=_C1, text=[f"{int(v):,}" for v in plot_top['EXECUTION_COUNT']],
            textposition='outside', textfont=dict(size=9)
        )])
        fig.update_layout(height=max(400, len(plot_top) * 25 + 100),
                          title='Top 20 Patterns by Execution Count',
                          xaxis_title='Executions', yaxis_title='',
                          showlegend=False, margin=dict(t=40, b=50, l=350, r=50))
        st.plotly_chart(fig, use_container_width=True)

        if 'TOTAL_ROWS_AFFECTED' in dml_df.columns:
            rows_top = dml_df.nlargest(20, 'TOTAL_ROWS_AFFECTED').sort_values('TOTAL_ROWS_AFFECTED', ascending=True).copy()
            rows_top['DISPLAY'] = rows_top['QUERY_PATTERN'].apply(lambda x: str(x)[:60] + '...' if len(str(x)) > 60 else str(x))
            fig = go.Figure(data=[go.Bar(
                y=rows_top['DISPLAY'], x=rows_top['TOTAL_ROWS_AFFECTED'], orientation='h',
                marker_color=_C1, text=[f"{int(v):,}" for v in rows_top['TOTAL_ROWS_AFFECTED']],
                textposition='outside', textfont=dict(size=9)
            )])
            fig.update_layout(height=max(400, len(rows_top) * 25 + 100),
                              title='Rows Affected by Pattern',
                              xaxis_title='Rows Affected', yaxis_title='',
                              showlegend=False, margin=dict(t=40, b=50, l=350, r=50))
            st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1.container():
            st.markdown("##### Recommendation Distribution")
            rec_counts = dml_df['RECOMMENDATION'].value_counts().reset_index()
            rec_counts.columns = ['RECOMMENDATION', 'COUNT']
            rec_labels = []
            for r in rec_counts['RECOMMENDATION']:
                if 'MICRO' in str(r):
                    rec_labels.append('\u26a0\ufe0f Micro-Updates (Batch these!)')
                elif 'FREQUENT' in str(r):
                    rec_labels.append('Frequent Pattern')
                else:
                    rec_labels.append(str(r))
            fig = go.Figure(data=[go.Pie(
                labels=rec_labels, values=rec_counts['COUNT'],
                hole=0.45, marker_colors=[_CA, _C2, _C1],
                textinfo='label+percent', textposition='outside', textfont=dict(size=9)
            )])
            fig.update_layout(height=400, showlegend=True, margin=dict(t=20, b=50, l=20, r=20),
                              legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5, font=dict(size=8)))
            st.plotly_chart(fig, use_container_width=True)

        with col2.container():
            st.markdown("##### Executions by DML Type")
            if 'QUERY_TYPE' in dml_df.columns:
                type_agg = dml_df.groupby('QUERY_TYPE').agg({'EXECUTION_COUNT': 'sum'}).reset_index()
                type_agg = type_agg.sort_values('EXECUTION_COUNT', ascending=True)
                fig = go.Figure(data=[go.Bar(
                    y=type_agg['QUERY_TYPE'], x=type_agg['EXECUTION_COUNT'], orientation='h',
                    marker_color=_C2, text=[f"{int(v):,}" for v in type_agg['EXECUTION_COUNT']],
                    textposition='outside', textfont=dict(size=10)
                )])
                fig.update_layout(height=400, xaxis_title='Executions', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=80, r=50))
                st.plotly_chart(fig, use_container_width=True)


def _render_mv_inventory():
    with st.expander("Materialized Views Inventory", expanded=True):
        st.markdown("Top 100 materialized views by size.")

        mv_inv_query = """
SELECT
    table_catalog AS database_name,
    table_schema AS schema_name,
    table_name AS mv_name,
    row_count,
    bytes AS size_bytes,
    ROUND(bytes / (1024*1024), 2) AS size_mb,
    created,
    last_altered
FROM SNOWFLAKE.ACCOUNT_USAGE.tables
WHERE table_type = 'MATERIALIZED VIEW'
  AND deleted IS NULL
ORDER BY bytes DESC NULLS LAST
LIMIT 100
"""
        try:
            mv_inv_df = _cached_sql("tf_mv_inventory", mv_inv_query)
        except Exception:
            mv_inv_df = pd.DataFrame()

        if mv_inv_df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px;">'
                        '⚠️&nbsp;&nbsp;No materialized views found.'
                        '</div>', unsafe_allow_html=True)
        else:
            st.dataframe(mv_inv_df)


def _render_mv_refresh_costs():
    with st.expander("Materialized View Refresh Costs", expanded=True):
        st.markdown("Credit cost per MV refresh over the last 7 days. High-frequency, high-cost refresh patterns are candidates for reviewing base table update patterns.")

        mv_query = """
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

        try:
            mv_df = _cached_sql("tf_mv_refresh_cost", mv_query)
        except Exception:
            mv_df = pd.DataFrame()

        if mv_df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px;">'
                        '⚠️&nbsp;&nbsp;No MV refresh cost data found.'
                        '</div>', unsafe_allow_html=True)
        else:
            st.dataframe(mv_df)

            col1, col2 = st.columns(2)
            with col1.container():
                st.markdown("##### Refresh Cost by MV (Credits)")
                plot_mv = mv_df.head(10).sort_values('REFRESH_COST_CREDITS', ascending=True)
                fig = go.Figure(data=[go.Bar(
                    y=plot_mv['MV_NAME'], x=plot_mv['REFRESH_COST_CREDITS'], orientation='h',
                    marker_color=_C1, text=[f"{v:.4f}" for v in plot_mv['REFRESH_COST_CREDITS']],
                    textposition='outside', textfont=dict(size=10)
                )])
                fig.update_layout(height=400, xaxis_title='Credits', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
                st.plotly_chart(fig, use_container_width=True)

            with col2.container():
                st.markdown("##### Refresh Count by MV")
                fig = go.Figure(data=[go.Bar(
                    y=plot_mv['MV_NAME'], x=plot_mv['REFRESH_COUNT'], orientation='h',
                    marker_color=_C2, text=[f"{int(v):,}" for v in plot_mv['REFRESH_COUNT']],
                    textposition='outside', textfont=dict(size=10)
                )])
                fig.update_layout(height=400, xaxis_title='Refresh Count', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
                st.plotly_chart(fig, use_container_width=True)


def _render_rap_impact_dashboard():
    with st.expander("RAP Impact Dashboard (Row Access Policies & MV Costs)", expanded=True):
        st.markdown("Performance dashboard aggregating micro-update counts, row access policy impact on slow queries, "
                   "and materialized view refresh costs over the last 7 days.")

        perf_query = """
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
SELECT 'Materialized Views' AS metric_category, 'Active MVs Refreshed' AS metric_name, active_mvs::STRING AS value FROM mv_churn
UNION ALL
SELECT 'Materialized Views', 'Total Refresh Cost (Credits)', ROUND(total_maintenance_credits, 2)::STRING FROM mv_churn
UNION ALL
SELECT 'Micro-Updates (Short Modifies)', 'Distinct Patterns Detected', unique_patterns::STRING FROM micro_updates
UNION ALL
SELECT 'Micro-Updates (Short Modifies)', 'Total Executions (<500ms)', total_executions::STRING FROM micro_updates
UNION ALL
SELECT 'Row Access Policies (Security)', 'Slow Queries on Protected Tables (>5s)', slow_protected_queries::STRING FROM rap_impact
)
SELECT A.* FROM AGGR A
"""

        try:
            perf_df = _cached_sql("tf_perf_insights", perf_query)
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                        f'🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)
            return

        if perf_df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px;">'
                        '⚠️&nbsp;&nbsp;No performance dashboard data found.'
                        '</div>', unsafe_allow_html=True)
            return

        perf_df.columns = ['METRIC_CATEGORY', 'METRIC_NAME', 'VALUE']
        st.dataframe(perf_df)

        col1, col2 = st.columns(2)
        with col1.container():
            st.markdown("##### Workload Metrics by Category")
            plot_perf = perf_df.copy()
            plot_perf['NUM_VALUE'] = pd.to_numeric(plot_perf['VALUE'], errors='coerce').fillna(0)
            plot_perf = plot_perf.sort_values('NUM_VALUE', ascending=True)
            fig = go.Figure(data=[go.Bar(
                y=plot_perf['METRIC_NAME'], x=plot_perf['NUM_VALUE'], orientation='h',
                marker_color=_C1, text=[f"{v:,.1f}" for v in plot_perf['NUM_VALUE']],
                textposition='outside', textfont=dict(size=10)
            )])
            fig.update_layout(height=400, xaxis_title='Value', yaxis_title='',
                              showlegend=False, margin=dict(t=20, b=50, l=220, r=50))
            st.plotly_chart(fig, use_container_width=True)

        with col2.container():
            st.markdown("##### Category Distribution")
            cat_agg = perf_df.copy()
            cat_agg['NUM_VALUE'] = pd.to_numeric(cat_agg['VALUE'], errors='coerce').fillna(0)
            cat_totals = cat_agg.groupby('METRIC_CATEGORY')['NUM_VALUE'].sum().reset_index()
            cat_totals = cat_totals[cat_totals['NUM_VALUE'] > 0]
            if not cat_totals.empty:
                fig = go.Figure(data=[go.Pie(
                    labels=cat_totals['METRIC_CATEGORY'], values=cat_totals['NUM_VALUE'],
                    hole=0.45, marker_colors=[_C1, _C2, _C3, _CA],
                    textinfo='label+percent', textposition='outside', textfont=dict(size=9)
                )])
                fig.update_layout(height=400, showlegend=True, margin=dict(t=20, b=50, l=20, r=20),
                                  legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5, font=dict(size=8)))
                st.plotly_chart(fig, use_container_width=True)

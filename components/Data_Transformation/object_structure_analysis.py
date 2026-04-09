import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

_VIEW_DEPENDENCY_SQL = """
WITH RECURSIVE view_lineage AS (
    SELECT
        referencing_database || '.' || referencing_schema || '.' || referencing_object_name AS parent_view,
        referenced_database || '.' || referenced_schema || '.' || referenced_object_name AS child_object,
        1 AS depth
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies
    WHERE referencing_object_domain = 'VIEW'
    UNION ALL
    SELECT
        od.referencing_database || '.' || od.referencing_schema || '.' || od.referencing_object_name,
        vl.child_object,
        vl.depth + 1
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies od
    JOIN view_lineage vl
        ON od.referenced_database || '.' || od.referenced_schema || '.' || od.referenced_object_name = vl.parent_view
    WHERE vl.depth < 10
),
view_depths AS (
    SELECT parent_view AS root_view, MAX(depth) AS max_depth
    FROM view_lineage
    GROUP BY parent_view
)
SELECT
    root_view,
    max_depth,
    CASE
        WHEN max_depth > 5 THEN 'CRITICAL_DEPTH'
        WHEN max_depth > 3 THEN 'HIGH_DEPTH'
        ELSE 'MODERATE_DEPTH'
    END AS depth_severity,
    CASE
        WHEN max_depth > 5 THEN 'Refactor to reduce view nesting - consider materialized views'
        WHEN max_depth > 3 THEN 'Review if intermediate views can be consolidated'
        ELSE 'Acceptable depth'
    END AS recommendation
FROM view_depths
WHERE max_depth > 2
ORDER BY max_depth DESC
"""

_LIFECYCLE_SQL = """
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

_SUMMARY_SQL = """
WITH RECURSIVE view_lineage AS (
    SELECT
        referencing_database || '.' || referencing_schema || '.' || referencing_object_name AS parent_view,
        referenced_database || '.' || referenced_schema || '.' || referenced_object_name AS child_object,
        1 AS depth
    FROM SNOWFLAKE.ACCOUNT_USAGE.object_dependencies
    WHERE referencing_object_domain = 'VIEW'
    UNION ALL
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
    SELECT parent_view, MAX(depth) AS max_depth
    FROM view_lineage
    GROUP BY 1
),
lifecycle_stats AS (
    SELECT
        CASE
            WHEN table_type = 'TEMPORARY' THEN 'Temporary Tables (Session Scope)'
            WHEN deleted IS NOT NULL AND DATEDIFF('minute', created, deleted) < 60 THEN 'Short-Lived Tables (<1hr)'
            ELSE NULL
        END AS category
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE (deleted IS NOT NULL OR table_type = 'TEMPORARY')
    UNION ALL
    SELECT 'Secure Views' AS category
    FROM SNOWFLAKE.ACCOUNT_USAGE.views
    WHERE is_secure = 'YES'
)
SELECT 'Stacked Views (Depth 3-5)' AS metric_name, COUNT(*) AS count_objects
FROM view_depth_stats WHERE max_depth BETWEEN 3 AND 5
UNION ALL
SELECT 'Stacked Views (Depth > 5)', COUNT(*)
FROM view_depth_stats WHERE max_depth > 5
UNION ALL
SELECT category, COUNT(*)
FROM lifecycle_stats WHERE category IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
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


def _err(msg):
    st.markdown(
        f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
        f'🛑&nbsp;&nbsp;{msg}</div>', unsafe_allow_html=True)


def _info(msg):
    st.markdown(
        f'<div style="background-color:#f0f7fb;border-left:6px solid {_C1};padding:10px;">'
        f'ℹ️&nbsp;&nbsp;{msg}</div>', unsafe_allow_html=True)


def comp_object_structure_analysis(entry_actions=None):
    try:
        try:
            from snowflake.snowpark.context import get_active_session
            session = get_active_session()
        except Exception as e:
            _err(f"Unable to get Snowflake session: {e}")
            return

        if not session:
            st.markdown(
                '<div style="background-color:#fff3cd;border-left:6px solid #ffc107;padding:10px;">'
                '⚠️&nbsp;&nbsp;Snowflake session not available.</div>', unsafe_allow_html=True)
            return

        # =====================================================================
        # Expander 1: View Dependency Analysis
        # =====================================================================
        try:
            dep_df = _cached_sql("tf_view_dependency_v2", _VIEW_DEPENDENCY_SQL)
        except Exception as e:
            _err(f"Error executing view dependency query: {e}")
            dep_df = pd.DataFrame()

        with st.expander("View Dependency Analysis (Depth > 2)", expanded=True):
            st.markdown("Recursive view dependency analysis identifying deeply nested view stacks (depth > 2) "
                        "by tracing parent-child relationships up to 10 levels.")

            if dep_df.empty:
                _info("No deeply nested view stacks (depth > 2) found in the current account.")
            else:
                dep_df.columns = ['ROOT_VIEW', 'MAX_DEPTH', 'DEPTH_SEVERITY', 'RECOMMENDATION']
                dep_df['MAX_DEPTH'] = pd.to_numeric(dep_df['MAX_DEPTH'], errors='coerce').fillna(0)
                st.dataframe(dep_df, use_container_width=True)

                st.markdown("**View Depth Charts**")

                st.markdown("**Top 20 Views by Nesting Depth**")
                _render_top20_depth_chart(dep_df)

                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    st.markdown("**Views per Depth Level**")
                    _render_depth_level_chart(dep_df)
                with dl_col2:
                    st.markdown("**Depth Severity Distribution**")
                    _render_severity_donut(dep_df)

        # =====================================================================
        # Expander 2: Object Lifecycle & Security Analysis
        # =====================================================================
        try:
            lifecycle_df = _cached_sql("tf_lifecycle", _LIFECYCLE_SQL)
        except Exception as e:
            _err(f"Error executing lifecycle query: {e}")
            lifecycle_df = pd.DataFrame()

        with st.expander("Object Lifecycle & Security Analysis", expanded=True):
            st.markdown("Object lifecycle and security analysis identifying temporary tables, short-lived "
                        "non-temp tables (< 60 min lifespan), and secure views.")

            if lifecycle_df.empty:
                _info("No temporary tables, short-lived tables, or secure views found in the current account.")
            else:
                row_count = len(lifecycle_df)
                if row_count >= 5000:
                    st.caption("📊 Showing top 5,000 records (data limited to prevent browser memory issues)")
                else:
                    st.caption(f"📊 Total records: {row_count:,}")

                st.dataframe(lifecycle_df, use_container_width=True)

                st.markdown("---")
                st.markdown("#### Object Lifecycle & Security Charts")

                lc_col1, lc_col2 = st.columns(2)
                with lc_col1:
                    st.markdown("##### Object Type Distribution")
                    _render_lifecycle_type_chart(lifecycle_df)
                with lc_col2:
                    st.markdown("##### Lifespan Analysis")
                    _render_lifecycle_lifespan_chart(lifecycle_df)

                lc_col3, lc_col4 = st.columns(2)
                with lc_col3:
                    st.markdown("##### Secure vs Non-Secure Objects")
                    _render_lifecycle_security_chart(lifecycle_df)
                with lc_col4:
                    st.markdown("##### Object Summary")
                    _render_lifecycle_summary_chart(lifecycle_df)

        # =====================================================================
        # Expander 3: Object Structure Summary
        # =====================================================================
        try:
            summary_df = _cached_sql("tf_summary", _SUMMARY_SQL)
        except Exception as e:
            _err(f"Error executing summary query: {e}")
            summary_df = pd.DataFrame()

        with st.expander("Object Structure Summary", expanded=True):
            st.markdown("Consolidated object structure metrics combining stacked view depth analysis "
                        "(3-5 levels vs >5 levels), temporary tables, short-lived tables (<1hr lifespan), "
                        "and secure views into a single summary view.")

            if summary_df.empty:
                _info("No object structure metrics found in the current account.")
            else:
                st.dataframe(summary_df, use_container_width=True)

                st.markdown("---")
                st.markdown("#### Object Structure Summary Charts")

                sum_col1, sum_col2 = st.columns(2)
                with sum_col1:
                    st.markdown("##### Metrics by Count")
                    _render_obj_summary_count_chart(summary_df)
                with sum_col2:
                    st.markdown("##### Metrics Distribution")
                    _render_obj_summary_distribution_chart(summary_df)

                sum_col3, sum_col4 = st.columns(2)
                with sum_col3:
                    st.markdown("##### View Depth vs Lifecycle Objects")
                    _render_obj_summary_category_chart(summary_df)
                with sum_col4:
                    st.markdown("##### Top Metrics")
                    _render_obj_summary_top_chart(summary_df)

    except Exception as e:
        _err(f"Component Error: {e}")


# ============================================================
# View Depth Charts
# ============================================================

def _render_top20_depth_chart(df):
    plot_df = df.nlargest(20, 'MAX_DEPTH').sort_values('MAX_DEPTH', ascending=True).copy()
    fig = go.Figure(go.Bar(
        y=plot_df['ROOT_VIEW'],
        x=plot_df['MAX_DEPTH'],
        orientation='h',
        marker_color=_C1,
        text=[f"{int(v)}" for v in plot_df['MAX_DEPTH']],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Depth: %{x}<extra></extra>'
    ))
    fig.update_layout(
        height=max(450, len(plot_df) * 28 + 80),
        xaxis_title='Nesting Depth',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=50, l=300, r=60)
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_depth_level_chart(df):
    depth_counts = df.groupby('MAX_DEPTH').size().reset_index(name='COUNT')
    depth_counts = depth_counts.sort_values('MAX_DEPTH')
    fig = go.Figure(go.Bar(
        x=depth_counts['MAX_DEPTH'],
        y=depth_counts['COUNT'],
        marker_color=_C2,
        text=[f"{int(v)}" for v in depth_counts['COUNT']],
        textposition='outside',
        hovertemplate='<b>Depth %{x}</b><br>Views: %{y}<extra></extra>'
    ))
    fig.update_layout(
        height=350,
        xaxis=dict(title='Depth Level', dtick=1),
        yaxis_title='Number of Views',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=50)
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_severity_donut(df):
    sev_counts = df.groupby('DEPTH_SEVERITY').size().reset_index(name='COUNT')
    color_map = {'MODERATE_DEPTH': _C1, 'HIGH_DEPTH': _C3, 'CRITICAL_DEPTH': _C2}
    colors = [color_map.get(s, _C1) for s in sev_counts['DEPTH_SEVERITY']]
    fig = go.Figure(go.Pie(
        labels=sev_counts['DEPTH_SEVERITY'],
        values=sev_counts['COUNT'],
        hole=0.45,
        marker_colors=colors,
        textinfo='label+percent', textposition='outside'
    ))
    fig.update_layout(
        height=350, showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.35),
        margin=dict(t=20, b=100, l=20, r=20)
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Lifecycle Charts
# ============================================================

def _render_lifecycle_type_chart(df):
    col_name = next((c for c in df.columns if 'TYPE' in c.upper()), df.columns[1] if len(df.columns) > 1 else df.columns[0])
    type_counts = df.groupby(col_name).size().reset_index(name='COUNT')
    type_counts = type_counts.sort_values('COUNT', ascending=True)
    fig = go.Figure(go.Bar(
        y=type_counts[col_name], x=type_counts['COUNT'],
        orientation='h', marker_color=_C1,
        text=[f"{int(v)}" for v in type_counts['COUNT']], textposition='outside',
        hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>'
    ))
    fig.update_layout(height=350, xaxis_title='Count', yaxis_title='',
                      showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
    st.plotly_chart(fig, use_container_width=True)


def _render_lifecycle_lifespan_chart(df):
    col_name = next((c for c in df.columns if 'LIFESPAN' in c.upper() or 'CHECK' in c.upper()), df.columns[-1])
    lifespan_counts = df.groupby(col_name).size().reset_index(name='COUNT')
    lifespan_counts = lifespan_counts.sort_values('COUNT', ascending=True)
    color_map = {
        '✅ Temp Table': _C1,
        '⚠️ Short-Lived (Non-Temp)': _CA,
        'Standard': _C2
    }
    colors = [color_map.get(str(v), _C3) for v in lifespan_counts[col_name]]
    fig = go.Figure(go.Bar(
        y=lifespan_counts[col_name], x=lifespan_counts['COUNT'],
        orientation='h', marker_color=colors,
        text=[f"{int(v)}" for v in lifespan_counts['COUNT']], textposition='outside',
        hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>'
    ))
    fig.update_layout(height=350, xaxis_title='Count', yaxis_title='',
                      showlegend=False, margin=dict(t=20, b=50, l=200, r=50))
    st.plotly_chart(fig, use_container_width=True)


def _render_lifecycle_security_chart(df):
    col_name = next((c for c in df.columns if 'SECURE' in c.upper()), None)
    if col_name is None:
        return
    secure_count = (df[col_name] == 'YES').sum()
    non_secure_count = (df[col_name] == 'NO').sum()
    fig = go.Figure(go.Bar(
        x=['🔒 Secure', '🔓 Non-Secure'],
        y=[secure_count, non_secure_count],
        marker_color=[_C1, _C2],
        text=[f"{int(v)}" for v in [secure_count, non_secure_count]],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
    ))
    fig.update_layout(height=350, xaxis_title='Security Status', yaxis_title='Count',
                      showlegend=False, margin=dict(t=20, b=50, l=50, r=50))
    st.plotly_chart(fig, use_container_width=True)


def _render_lifecycle_summary_chart(df):
    lifespan_col = next((c for c in df.columns if 'LIFESPAN' in c.upper() or 'CHECK' in c.upper()), None)
    secure_col = next((c for c in df.columns if 'SECURE' in c.upper()), None)
    total_objects = len(df)
    temp_tables = (df[lifespan_col] == '✅ Temp Table').sum() if lifespan_col else 0
    short_lived = (df[lifespan_col] == '⚠️ Short-Lived (Non-Temp)').sum() if lifespan_col else 0
    secure_views = (df[secure_col] == 'YES').sum() if secure_col else 0
    metrics = ['Total Objects', 'Temp Tables', 'Short-Lived', 'Secure Views']
    values = [total_objects, temp_tables, short_lived, secure_views]
    colors = [_C1, _C2, _CA, _C3]
    fig = go.Figure(go.Bar(
        x=metrics, y=values, marker_color=colors,
        text=[f"{int(v)}" for v in values], textposition='outside',
        hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
    ))
    fig.update_layout(height=350, xaxis_title='Metric', yaxis_title='Count',
                      showlegend=False, margin=dict(t=20, b=50, l=50, r=50))
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Object Structure Summary Charts
# ============================================================

def _render_obj_summary_count_chart(df):
    col_n = next((c for c in df.columns if 'COUNT' in c.upper() or 'OBJECT' in c.upper()), df.columns[-1])
    col_m = next((c for c in df.columns if 'METRIC' in c.upper() or 'NAME' in c.upper()), df.columns[0])
    df2 = df.copy()
    df2[col_n] = pd.to_numeric(df2[col_n], errors='coerce').fillna(0)
    plot_df = df2.sort_values(col_n, ascending=True)
    colors = [_C1 if 'Stacked' in str(m) else _C2 if 'Short' in str(m) else _CA if 'Secure' in str(m) else _C3
              for m in plot_df[col_m]]
    fig = go.Figure(go.Bar(
        y=plot_df[col_m], x=plot_df[col_n], orientation='h',
        marker_color=colors,
        text=[f"{int(v):,}" for v in plot_df[col_n]], textposition='outside',
        hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
    ))
    fig.update_layout(height=350, xaxis_title='Count', yaxis_title='',
                      showlegend=False, margin=dict(t=20, b=50, l=200, r=50))
    st.plotly_chart(fig, use_container_width=True)


def _render_obj_summary_distribution_chart(df):
    col_n = next((c for c in df.columns if 'COUNT' in c.upper() or 'OBJECT' in c.upper()), df.columns[-1])
    col_m = next((c for c in df.columns if 'METRIC' in c.upper() or 'NAME' in c.upper()), df.columns[0])
    df2 = df.copy()
    df2[col_n] = pd.to_numeric(df2[col_n], errors='coerce').fillna(0)
    total = df2[col_n].sum()
    if total == 0:
        _info("No data available for chart.")
        return
    df2['PCT'] = ((df2[col_n] / total) * 100).round(1)
    plot_df = df2.sort_values('PCT', ascending=True)
    fig = go.Figure(go.Bar(
        y=plot_df[col_m], x=plot_df['PCT'], orientation='h',
        marker_color=_CA,
        text=[f"{v:.1f}%" for v in plot_df['PCT']], textposition='outside',
        hovertemplate='<b>%{y}</b><br>Percentage: %{x:.1f}%<extra></extra>'
    ))
    fig.update_layout(height=350, xaxis_title='Percentage of Total', yaxis_title='',
                      showlegend=False, margin=dict(t=20, b=50, l=200, r=50))
    st.plotly_chart(fig, use_container_width=True)


def _render_obj_summary_category_chart(df):
    col_n = next((c for c in df.columns if 'COUNT' in c.upper() or 'OBJECT' in c.upper()), df.columns[-1])
    col_m = next((c for c in df.columns if 'METRIC' in c.upper() or 'NAME' in c.upper()), df.columns[0])
    df2 = df.copy()
    df2[col_n] = pd.to_numeric(df2[col_n], errors='coerce').fillna(0)
    view_depth_count = df2[df2[col_m].str.contains('Stacked', case=False, na=False)][col_n].sum()
    lifecycle_count = df2[~df2[col_m].str.contains('Stacked', case=False, na=False)][col_n].sum()
    fig = go.Figure(go.Bar(
        x=['📊 View Depth Analysis', '🔄 Lifecycle Objects'],
        y=[view_depth_count, lifecycle_count],
        marker_color=[_C1, _C2],
        text=[f"{int(v):,}" for v in [view_depth_count, lifecycle_count]],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Count: %{y:,}<extra></extra>'
    ))
    fig.update_layout(height=350, xaxis_title='Category', yaxis_title='Count',
                      showlegend=False, margin=dict(t=20, b=50, l=50, r=50))
    st.plotly_chart(fig, use_container_width=True)


def _render_obj_summary_top_chart(df):
    col_n = next((c for c in df.columns if 'COUNT' in c.upper() or 'OBJECT' in c.upper()), df.columns[-1])
    col_m = next((c for c in df.columns if 'METRIC' in c.upper() or 'NAME' in c.upper()), df.columns[0])
    df2 = df.copy()
    df2[col_n] = pd.to_numeric(df2[col_n], errors='coerce').fillna(0)
    plot_df = df2[df2[col_n] > 0].nlargest(5, col_n).sort_values(col_n, ascending=True)
    if plot_df.empty:
        _info("No data available for chart.")
        return
    fig = go.Figure(go.Bar(
        y=plot_df[col_m], x=plot_df[col_n], orientation='h',
        marker_color=_C2,
        text=[f"{int(v):,}" for v in plot_df[col_n]], textposition='outside',
        hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
    ))
    fig.update_layout(height=350, xaxis_title='Count', yaxis_title='',
                      showlegend=False, margin=dict(t=20, b=50, l=200, r=50))
    st.plotly_chart(fig, use_container_width=True)

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


def comp_object_structure_analysis(entry_actions=None):
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

        view_dependency_query = """
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
    HAVING MAX(depth) > 2
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
ORDER BY max_depth DESC
        """

        try:
            vd_df = _cached_sql("tf_view_dependency_v2", view_dependency_query)
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            vd_df = pd.DataFrame()

        with st.expander("View Dependency Analysis (Depth > 2)", expanded=True):
            st.markdown("Recursive view dependency analysis identifying deeply nested view stacks (depth > 2) "
                       "by tracing parent-child relationships up to 10 levels.")

            if vd_df.empty:
                st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No deeply nested view stacks (depth > 2) found in the current account.'
                    '</div>', unsafe_allow_html=True)
            else:
                st.dataframe(vd_df)

                st.markdown("#### View Depth Charts")

                top_views = vd_df.nlargest(20, 'MAX_DEPTH').sort_values('MAX_DEPTH', ascending=True)
                top_views['DISPLAY_NAME'] = top_views['ROOT_VIEW'].apply(lambda x: x[-60:] if len(str(x)) > 60 else x)

                fig = go.Figure(data=[go.Bar(
                    y=top_views['DISPLAY_NAME'], x=top_views['MAX_DEPTH'], orientation='h',
                    marker_color=_C1, text=[f"{int(v)}" for v in top_views['MAX_DEPTH']],
                    textposition='outside', textfont=dict(size=9)
                )])
                fig.update_layout(height=max(400, len(top_views) * 25 + 100),
                                  title='Top 20 Views by Nesting Depth',
                                  xaxis_title='Max Depth', yaxis_title='',
                                  showlegend=False, margin=dict(t=40, b=50, l=400, r=50))
                st.plotly_chart(fig, use_container_width=True)

                col1, col2 = st.columns(2)
                with col1.container():
                    st.markdown("##### Views per Depth Level")
                    depth_counts = vd_df.groupby('MAX_DEPTH').size().reset_index(name='COUNT')
                    depth_counts = depth_counts.sort_values('MAX_DEPTH', ascending=True)
                    depth_counts['LABEL'] = depth_counts['MAX_DEPTH'].astype(int).astype(str)
                    fig = go.Figure(data=[go.Bar(
                        y=depth_counts['LABEL'], x=depth_counts['COUNT'],
                        orientation='h', marker_color=_C2,
                        text=[f"{int(v)}" for v in depth_counts['COUNT']],
                        textposition='outside', textfont=dict(size=10)
                    )])
                    fig.update_layout(height=400, xaxis_title='Number of Views', yaxis_title='Depth Level',
                                      showlegend=False, margin=dict(t=20, b=50, l=60, r=50))
                    st.plotly_chart(fig, use_container_width=True)

                with col2.container():
                    st.markdown("##### Depth Severity Distribution")
                    severity_counts = vd_df.groupby('DEPTH_SEVERITY').size().reset_index(name='COUNT')
                    sev_colors = {'CRITICAL_DEPTH': '#E74C3C', 'HIGH_DEPTH': _CA, 'MODERATE_DEPTH': _C1}
                    fig = go.Figure(data=[go.Pie(
                        labels=severity_counts['DEPTH_SEVERITY'], values=severity_counts['COUNT'],
                        hole=0.45,
                        marker_colors=[sev_colors.get(s, _C3) for s in severity_counts['DEPTH_SEVERITY']],
                        textinfo='label+percent', textposition='outside', textfont=dict(size=9)
                    )])
                    fig.update_layout(height=400, showlegend=True, margin=dict(t=20, b=50, l=20, r=20),
                                      legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5, font=dict(size=8)))
                    st.plotly_chart(fig, use_container_width=True)

        lifecycle_query = """
WITH lifecycle_agg AS (
    SELECT 'TEMP_TABLE' AS lifespan_category, COUNT(*) AS object_count
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE table_type = 'TEMPORARY'

    UNION ALL

    SELECT 'SHORT_LIVED', COUNT(*)
    FROM SNOWFLAKE.ACCOUNT_USAGE.tables
    WHERE deleted IS NOT NULL AND DATEDIFF('minute', created, deleted) < 60
      AND table_type != 'TEMPORARY'

    UNION ALL

    SELECT 'SECURE_VIEW', COUNT(*)
    FROM SNOWFLAKE.ACCOUNT_USAGE.views
    WHERE is_secure = 'YES'
)
SELECT * FROM lifecycle_agg
WHERE object_count > 0
ORDER BY object_count DESC
        """

        try:
            lc_df = _cached_sql("tf_lifecycle_agg", lifecycle_query)
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing lifecycle query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            lc_df = pd.DataFrame()

        with st.expander("Object Lifecycle Analysis", expanded=True):
            st.markdown("Categorises objects by lifecycle: temporary tables, short-lived tables (deleted within 60 min), and secure views.")

            if lc_df.empty:
                st.info("No lifecycle data found.")
            else:
                col1, col2 = st.columns(2)
                with col1.container():
                    st.markdown("##### Object Count by Lifecycle Category")
                    plot_lc = lc_df.sort_values('OBJECT_COUNT', ascending=True)
                    fig = go.Figure(data=[go.Bar(
                        y=plot_lc['LIFESPAN_CATEGORY'], x=plot_lc['OBJECT_COUNT'], orientation='h',
                        marker_color=_C1, text=[f"{int(v):,}" for v in plot_lc['OBJECT_COUNT']],
                        textposition='outside', textfont=dict(size=10)
                    )])
                    fig.update_layout(height=400, xaxis_title='Object Count', yaxis_title='',
                                      showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
                    st.plotly_chart(fig, use_container_width=True)

                with col2.container():
                    st.markdown("##### Lifecycle Distribution")
                    fig = go.Figure(data=[go.Pie(
                        labels=lc_df['LIFESPAN_CATEGORY'], values=lc_df['OBJECT_COUNT'],
                        hole=0.45, marker_colors=[_C1, _C2, _C3, _CA],
                        textinfo='label+percent', textposition='outside', textfont=dict(size=9)
                    )])
                    fig.update_layout(height=400, showlegend=True, margin=dict(t=20, b=50, l=20, r=20),
                                      legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5, font=dict(size=8)))
                    st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
    for k, sql in needed.items():
        key, df, err = _run_query_thread(session, k, sql)
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

        try:
            df = _cached_sql("tf_overview", _ALL_TF_QUERIES.get("tf_overview", ""))
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No data transformation landscape data found.'
                        '</div>', unsafe_allow_html=True)
            return

        with st.expander("Data Transformation Landscape Assessment", expanded=True):
            st.markdown("Comprehensive landscape covering table types, clustering status, "
                       "materialized views, semi-structured data, dynamic/hybrid/event tables, semantic views, "
                       "warehouse performance issues, and Snowpark usage.")

            row = df.iloc[0]
            clustered = int(row.get('CLUSTERED_TABLES', 0))
            unclustered = int(row.get('UNCLUSTERED_TABLES', 0))
            total_base = clustered + unclustered

            metrics_data = {
                'Metric': [
                    'Total Base Tables',
                    'Clustered Tables',
                    'Unclustered Tables',
                    'Tables with Auto Clustering ON',
                    'Materialized Views',
                    'Tables with Semi-Structured Data',
                    'Dynamic Tables',
                    'Hybrid Tables',
                    'Event Tables',
                    'Semantic Views',
                    'Warehouses with Spill/Queue (30d)',
                    'Short UPSERTs (30d)',
                    'Snowpark Queries (30d)',
                    'High Cloud Services Days (30d)'
                ],
                'Value': [
                    f"{total_base:,}",
                    f"{clustered:,}",
                    f"{unclustered:,}",
                    f"{int(row.get('NUM_TABLES_WITH_AUTO_CLUSTERING', 0)):,}",
                    f"{int(row.get('NUM_MATERIALIZED_VIEWS', 0)):,}",
                    f"{int(row.get('NUM_TABLES_WITH_SEMI_STRUCTURED', 0)):,}",
                    f"{int(row.get('NUM_DYNAMIC_TABLES', 0)):,}",
                    f"{int(row.get('NUM_HYBRID_TABLES', 0)):,}",
                    f"{int(row.get('NUM_EVENT_TABLES', 0)):,}",
                    f"{int(row.get('NUM_SEMANTIC_VIEWS', 0)):,}",
                    f"{int(row.get('NUM_WAREHOUSES_SPILL_OR_QUEUE_LAST_30D', 0)):,}",
                    f"{int(row.get('NUM_SHORT_UPSERTS_LAST_30D', 0)):,}",
                    f"{int(row.get('NUM_SNOWPARK_QUERIES_LAST_30D', 0)):,}",
                    f"{int(row.get('NUM_WH_DAYS_HIGH_CLOUD_SERVICES_LAST_30D', 0)):,}"
                ]
            }
            display_df = pd.DataFrame(metrics_data)
            st.dataframe(display_df)

            st.markdown("#### Transformation Landscape Charts")

            col1, col2 = st.columns(2)

            with col1.container():
                st.markdown("##### Table Clustering Distribution")
                categories = ['Unclustered Tables', 'Clustered Tables', 'Auto Clustering ON']
                values = [
                    unclustered,
                    clustered,
                    int(row.get('NUM_TABLES_WITH_AUTO_CLUSTERING', 0))
                ]
                sorted_data = sorted(zip(values, categories), reverse=False)
                vals = [v for v, c in sorted_data]
                cats = [c for v, c in sorted_data]
                fig = go.Figure(data=[go.Bar(
                    y=cats, x=vals, orientation='h', marker_color='#29B5E8',
                    text=[f"{int(v):,}" for v in vals], textposition='outside', textfont=dict(size=10),
                    hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
                )])
                fig.update_layout(height=400, xaxis_title='Number of Tables', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
                st.plotly_chart(fig, use_container_width=True)

            with col2.container():
                st.markdown("##### Table Types Distribution")
                categories = ['Semi-Structured', 'Dynamic Tables', 'Event Tables', 'Semantic Views', 'Materialized Views', 'Hybrid Tables']
                values = [
                    int(row.get('NUM_TABLES_WITH_SEMI_STRUCTURED', 0)),
                    int(row.get('NUM_DYNAMIC_TABLES', 0)),
                    int(row.get('NUM_EVENT_TABLES', 0)),
                    int(row.get('NUM_SEMANTIC_VIEWS', 0)),
                    int(row.get('NUM_MATERIALIZED_VIEWS', 0)),
                    int(row.get('NUM_HYBRID_TABLES', 0))
                ]
                sorted_data = sorted(zip(values, categories), reverse=False)
                vals = [v for v, c in sorted_data]
                cats = [c for v, c in sorted_data]
                fig = go.Figure(data=[go.Bar(
                    y=cats, x=vals, orientation='h', marker_color='#11567F',
                    text=[f"{int(v):,}" for v in vals], textposition='outside', textfont=dict(size=10),
                    hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
                )])
                fig.update_layout(height=400, xaxis_title='Count', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
                st.plotly_chart(fig, use_container_width=True)

            col3, col4 = st.columns(2)

            with col3.container():
                st.markdown("##### Warehouse Performance Issues (30 Days)")
                categories = ['WH with Spill/Queue', 'High Cloud Services Days']
                values = [
                    int(row.get('NUM_WAREHOUSES_SPILL_OR_QUEUE_LAST_30D', 0)),
                    int(row.get('NUM_WH_DAYS_HIGH_CLOUD_SERVICES_LAST_30D', 0))
                ]
                sorted_data = sorted(zip(values, categories), reverse=False)
                vals = [v for v, c in sorted_data]
                cats = [c for v, c in sorted_data]
                fig = go.Figure(data=[go.Bar(
                    y=cats, x=vals, orientation='h', marker_color='#E8A229',
                    text=[f"{int(v):,}" for v in vals], textposition='outside', textfont=dict(size=10),
                    hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
                )])
                fig.update_layout(height=400, xaxis_title='Count', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=160, r=50))
                st.plotly_chart(fig, use_container_width=True)

            with col4.container():
                st.markdown("##### Query & Usage Patterns (30 Days)")
                categories = ['Short UPSERTs', 'Snowpark Queries']
                values = [
                    int(row.get('NUM_SHORT_UPSERTS_LAST_30D', 0)),
                    int(row.get('NUM_SNOWPARK_QUERIES_LAST_30D', 0))
                ]
                sorted_data = sorted(zip(values, categories), reverse=False)
                vals = [v for v, c in sorted_data]
                cats = [c for v, c in sorted_data]
                fig = go.Figure(data=[go.Bar(
                    y=cats, x=vals, orientation='h', marker_color='#11567F',
                    text=[f"{int(v):,}" for v in vals], textposition='outside', textfont=dict(size=10),
                    hovertemplate='<b>%{y}</b><br>Count: %{x:,}<extra></extra>'
                )])
                fig.update_layout(height=400, xaxis_title='Count', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=120, r=50))
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

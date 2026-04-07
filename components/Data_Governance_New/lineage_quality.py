import streamlit as st
import plotly.graph_objects as go
import pandas as pd


def _get_cached(cache_key):
    return st.session_state.get(cache_key, pd.DataFrame())


_C = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229', '#1A7DA8', '#023E8A', '#48CAE4']


def comp_lineage_quality(entry_actions=None):
    try:
        st.markdown("### Data Lineage & Quality (Lite)")
        with st.expander("Sensitive Data Access by User", expanded=True):
            _render_sensitive_access()
        with st.expander("Object Dependencies (Sensitive Data Lineage)", expanded=True):
            _render_object_dependencies()
    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
            f'🛑&nbsp;&nbsp;Error loading Data Lineage & Quality: {str(e)}</div>', unsafe_allow_html=True)


def _render_sensitive_access():
    st.markdown("#### Sensitive Data Access by User (Last 30 Days)")
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;Identifies users who accessed objects tagged with PII/PHI/GDPR/sensitive classification '
        'tags in the last 30 days. Uses ACCESS_HISTORY joined to TAG_REFERENCES to surface downstream impact.</div>',
        unsafe_allow_html=True)
    try:
        df = _get_cached("dg_sensitive_access")
        if df.empty:
            st.info("No sensitive data access found — either no sensitive tags are defined, or no users accessed tagged objects in the last 30 days.")
            return
        df['SENSITIVE_ACCESS_COUNT'] = pd.to_numeric(df['SENSITIVE_ACCESS_COUNT'], errors='coerce').fillna(0)
        df['DISTINCT_OBJECTS_ACCESSED'] = pd.to_numeric(df['DISTINCT_OBJECTS_ACCESSED'], errors='coerce').fillna(0)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Users Accessing Sensitive Data", len(df))
        with col2:
            st.metric("Total Sensitive Queries", int(df['SENSITIVE_ACCESS_COUNT'].sum()))
        with col3:
            st.metric("Distinct Objects Touched", int(df['DISTINCT_OBJECTS_ACCESSED'].sum()))
        top_n = min(20, len(df))
        fig = go.Figure(go.Bar(
            x=df.head(top_n)['USER_NAME'],
            y=df.head(top_n)['SENSITIVE_ACCESS_COUNT'],
            marker_color=_C[0],
            text=df.head(top_n)['SENSITIVE_ACCESS_COUNT'],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Queries: %{y}<extra></extra>'
        ))
        fig.update_layout(
            title=f'Top {top_n} Users by Sensitive Data Access (Last 30 Days)',
            xaxis_title='User', yaxis_title='Sensitive Query Count',
            height=380, margin=dict(t=50, b=100),
            xaxis=dict(tickangle=-35)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_object_dependencies():
    st.markdown("#### Object Dependencies — Sensitive Data Lineage")
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;Traces which downstream objects (views, pipes, tasks) reference sensitive base tables/views. '
        'Useful for understanding blast radius if a sensitive object is modified or access is revoked.</div>',
        unsafe_allow_html=True)
    try:
        df = _get_cached("dg_downstream_deps")
        if df.empty:
            st.info("No downstream dependencies found for sensitive objects — either no sensitive tags are defined or no object dependencies exist.")
            return
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Sensitive Source Objects", df[['REFERENCED_DATABASE', 'REFERENCED_SCHEMA', 'REFERENCED_OBJECT_NAME']].drop_duplicates().shape[0])
        with col2:
            st.metric("Downstream Dependent Objects", df[['REFERENCING_DATABASE', 'REFERENCING_SCHEMA', 'REFERENCING_OBJECT_NAME']].drop_duplicates().shape[0])
        dep_counts = (df.groupby('REFERENCED_OBJECT_NAME').size().reset_index(name='downstream_count')
                      .sort_values('downstream_count', ascending=False).head(20))
        fig = go.Figure(go.Bar(
            x=dep_counts['REFERENCED_OBJECT_NAME'],
            y=dep_counts['downstream_count'],
            marker_color=_C[1],
            text=dep_counts['downstream_count'],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Downstream: %{y}<extra></extra>'
        ))
        fig.update_layout(
            title='Sensitive Objects with Most Downstream Dependents',
            xaxis_title='Sensitive Object', yaxis_title='# Downstream Objects',
            height=380, margin=dict(t=50, b=100),
            xaxis=dict(tickangle=-35)
        )
        st.plotly_chart(fig, use_container_width=True)
        type_counts = df.groupby('REFERENCING_OBJECT_DOMAIN').size().reset_index(name='count')
        fig_pie = go.Figure(go.Pie(
            labels=type_counts['REFERENCING_OBJECT_DOMAIN'],
            values=type_counts['count'],
            hole=0.3,
            marker_colors=_C[:len(type_counts)]
        ))
        fig_pie.update_layout(title='Referencing Object Types', height=300, margin=dict(t=40, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

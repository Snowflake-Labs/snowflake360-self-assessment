import streamlit as st
import pandas as pd
import plotly.graph_objects as go

PALETTE = ["#29B5E8", "#11567F", "#75C2D8", "#E8A229", "#1A7DA8", "#023E8A", "#48CAE4", "#0077B6"]


def _get_cached(cache_key):
    return st.session_state.get(cache_key, pd.DataFrame())


def _plotly_bar(df, cat_col, val_col, color, title=""):
    fig = go.Figure(data=[go.Bar(
        y=df[cat_col], x=df[val_col],
        orientation="h",
        marker_color=color,
        text=df[val_col], textposition="outside",
        hovertemplate="<b>%{y}</b><br>Count: %{x}<extra></extra>",
    )])
    fig.update_layout(
        height=max(250, len(df) * 30),
        margin=dict(t=10, b=30, l=140, r=40),
        yaxis=dict(autorange="reversed"), showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _plotly_pie(df, cat_col, val_col, colors):
    fig = go.Figure(data=[go.Pie(
        labels=df[cat_col], values=df[val_col],
        marker_colors=colors[:len(df)],
        hole=0.4,
        hovertemplate="<b>%{label}</b><br>Count: %{value}<extra></extra>",
    )])
    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
                      legend=dict(orientation="h", yanchor="top", y=-0.1))
    st.plotly_chart(fig, use_container_width=True)


def _render_tagging_coverage_audit_content():
    try:
        audit_df = _get_cached("dg_tagging_audit_data")

        if len(audit_df) > 0:
            row1_col1, row1_col2 = st.columns(2)

            with row1_col1:
                st.markdown("##### Top 10 Tagged Databases")
                db_counts = audit_df.groupby('DATABASE_NAME').size().reset_index(name='COUNT')
                db_counts = db_counts.sort_values('COUNT', ascending=False).head(10)
                _plotly_bar(db_counts, 'DATABASE_NAME', 'COUNT', PALETTE[0])

            with row1_col2:
                st.markdown("##### Top 10 Tagged Schemas")
                tagged_df = audit_df[audit_df['TAG_STATUS'] != 'Untagged']
                if len(tagged_df) > 0:
                    schema_counts = tagged_df.groupby('SCHEMA_NAME').size().reset_index(name='COUNT')
                    schema_counts = schema_counts.sort_values('COUNT', ascending=False).head(10)
                    _plotly_bar(schema_counts, 'SCHEMA_NAME', 'COUNT', PALETTE[4])
                else:
                    st.info("No tagged schemas found.")

            row2_col1, row2_col2 = st.columns(2)

            with row2_col1:
                st.markdown("##### Table Type Distribution")
                type_counts = audit_df.groupby('TABLE_TYPE').size().reset_index(name='COUNT')
                _plotly_pie(type_counts, 'TABLE_TYPE', 'COUNT', PALETTE)

            with row2_col2:
                st.markdown("##### Tag Value Breakdown")
                tagged_vals = audit_df[audit_df['TAG_VALUE'].notna() & (audit_df['TAG_VALUE'] != '')]
                if len(tagged_vals) > 0:
                    value_counts = tagged_vals.groupby('TAG_VALUE').size().reset_index(name='COUNT')
                    value_counts = value_counts.sort_values('COUNT', ascending=False).head(10)
                    _plotly_bar(value_counts, 'TAG_VALUE', 'COUNT', PALETTE[3])
                else:
                    st.info("No tag values found.")
        else:
            st.info("No tagging coverage audit data available.")

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                    f'Error loading tagging coverage audit: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_classification_insights():
    import plotly.graph_objects as go
    import pandas as pd
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;Columns tagged with PII, PHI, GDPR, or other sensitivity classification tags. '
        'Use this to audit which columns carry sensitive labels and validate tagging completeness.</div>',
        unsafe_allow_html=True)
    try:
        df = _get_cached("dg_sensitive_tagged")
        if df.empty:
            st.info("No sensitive-tagged columns found. Ensure PII/PHI/GDPR classification tags have been applied to columns.")
            return
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tagged Sensitive Columns", len(df))
        with col2:
            st.metric("Distinct Tables", df['TABLE_NAME'].nunique())
        with col3:
            st.metric("Distinct Tag Names", df['TAG_NAME'].nunique())
        tag_counts = df.groupby('TAG_NAME').size().reset_index(name='count').sort_values('count', ascending=False).head(15)
        fig = go.Figure(go.Bar(
            x=tag_counts['TAG_NAME'], y=tag_counts['count'],
            marker_color='#11567F',
            text=tag_counts['count'], textposition='outside'
        ))
        fig.update_layout(
            title='Top Classification Tags Applied to Columns',
            xaxis_title='Tag Name', yaxis_title='Column Assignments',
            height=360, margin=dict(t=50, b=100), xaxis=dict(tickangle=-35)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_stale_tagged_objects():
    import plotly.graph_objects as go
    import pandas as pd
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;Tagged tables that have not been modified in over 90 days. '
        'Stale tagged objects may indicate data that is no longer actively maintained but still carries '
        'sensitive classification — a potential governance risk.</div>', unsafe_allow_html=True)
    try:
        df = _get_cached("dg_stale_tagged")
        if df.empty:
            st.info("No stale tagged objects found (all tagged tables have been modified within the last 90 days).")
            return
        df['DAYS_SINCE_MODIFIED'] = pd.to_numeric(df['DAYS_SINCE_MODIFIED'], errors='coerce').fillna(0)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Stale Tagged Tables", df['TABLE_NAME'].nunique())
        with col2:
            over_180 = len(df[df['DAYS_SINCE_MODIFIED'] >= 180])
            st.metric("Not Modified in 180+ Days", over_180)
        with col3:
            st.metric("Avg Days Stale", f"{df['DAYS_SINCE_MODIFIED'].mean():.0f}")
        age_bins = pd.cut(df['DAYS_SINCE_MODIFIED'], bins=[90, 180, 365, 730, float('inf')],
                          labels=['90-180d', '180-365d', '1-2yr', '2yr+'])
        age_counts = age_bins.value_counts().sort_index()
        fig = go.Figure(go.Bar(
            x=list(age_counts.index.astype(str)), y=list(age_counts.values),
            marker_color=['#75C2D8', '#E8A229', '#0077B6', '#03045E'],
            text=list(age_counts.values), textposition='outside'
        ))
        fig.update_layout(
            title='Stale Tagged Objects by Age Bracket',
            xaxis_title='Age Since Last Modified', yaxis_title='Count',
            height=340, margin=dict(t=50, b=60)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['DATABASE_NAME', 'SCHEMA_NAME', 'TABLE_NAME', 'TAG_NAME', 'TAG_VALUE', 'LAST_ALTERED', 'DAYS_SINCE_MODIFIED']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_dangling_tags():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Dangling Tags:</b> Tag references where the tagged object has been deleted. '
        'These should be cleaned up to maintain governance hygiene.</div>',
        unsafe_allow_html=True)
    try:
        df = _get_cached("dg_dangling_tags")
        if df.empty:
            st.success("No dangling tags found — all tagged objects are active.")
            return
        st.metric("Dangling Tag References", len(df))
        domain_counts = df.groupby('DOMAIN').size().reset_index(name='COUNT').sort_values('COUNT', ascending=False)
        colors = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229']
        fig = go.Figure(go.Bar(
            x=domain_counts['DOMAIN'], y=domain_counts['COUNT'],
            marker_color=colors[:len(domain_counts)],
            text=domain_counts['COUNT'], textposition='outside'
        ))
        fig.update_layout(title='Dangling Tags by Object Domain', yaxis_title='Count', height=340, margin=dict(t=50, b=60))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_heavy_column_tagging():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Heavy Column Tagging:</b> Tables with the most column-level tags. '
        'High tag density may indicate over-classification or redundant tagging.</div>',
        unsafe_allow_html=True)
    try:
        df = _get_cached("dg_heavy_column_tagging")
        if df.empty:
            st.info("No column-level tags found.")
            return
        for c in ['COLUMN_TAG_COUNT', 'DISTINCT_COLUMNS_TAGGED', 'DISTINCT_TAG_TYPES']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Most Tagged Table", f"{int(df['COLUMN_TAG_COUNT'].iloc[0])} tags")
        with col2:
            st.metric("Tables with Column Tags", len(df))
        fig = go.Figure(go.Bar(
            y=df['TABLE_NAME'].head(15), x=df['COLUMN_TAG_COUNT'].head(15),
            orientation='h', marker_color='#29B5E8',
            text=df['COLUMN_TAG_COUNT'].head(15).astype(int), textposition='outside'
        ))
        fig.update_layout(
            title='Top 15 Tables by Column Tag Count',
            xaxis_title='Tag Count', yaxis_title='Table',
            height=max(300, len(df.head(15)) * 30 + 80), margin=dict(t=50, l=200, r=20, b=60)
        )
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_tags_without_allowed_values():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Tag Design Issues:</b> Tags that have high cardinality of unique values '
        '(>10 distinct values), which may indicate missing ALLOWED_VALUES constraints.</div>',
        unsafe_allow_html=True)
    try:
        df = _get_cached("dg_tags_no_allowed_values")
        if df.empty:
            st.success("All tags have reasonable value cardinality (≤10 distinct values).")
            return
        df['DISTINCT_VALUES'] = pd.to_numeric(df['DISTINCT_VALUES'], errors='coerce').fillna(0)
        st.metric("Tags with High Value Cardinality", len(df))
        fig = go.Figure(go.Bar(
            x=df['TAG_NAME'], y=df['DISTINCT_VALUES'],
            marker_color='#E8A229',
            text=df['DISTINCT_VALUES'].astype(int), textposition='outside'
        ))
        fig.update_layout(
            title='Tags with >10 Distinct Values (Consider ALLOWED_VALUES)',
            yaxis_title='Distinct Values', height=380, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def comp_object_tagging_classification(entry_actions=None):
    try:
        st.markdown("### Data Object Tagging & Classification")

        with st.expander("Tagging Coverage Audit", expanded=True):
            st.markdown("#### Tagging Coverage Audit")
            _render_tagging_coverage_audit_content()

        with st.expander("Classification Insights", expanded=True):
            st.markdown("#### Classification Insights (PII/Sensitive Columns)")
            _render_classification_insights()

        with st.expander("Stale Tagged Objects (>90 days)", expanded=True):
            st.markdown("#### Stale Tagged Objects (Last Modified >90 Days Ago)")
            _render_stale_tagged_objects()

        with st.expander("Dangling Tags (Tags on Deleted Objects)", expanded=True):
            _render_dangling_tags()

        with st.expander("Heavy Column Tagging (Columns with Many Tags)", expanded=True):
            _render_heavy_column_tagging()

        with st.expander("Tag Design: Tags Without Allowed Values", expanded=True):
            _render_tags_without_allowed_values()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                    f'Error loading Data Object Tagging & Classification: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

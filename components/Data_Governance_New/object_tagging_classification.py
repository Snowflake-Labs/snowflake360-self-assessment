"""
Data Object Tagging & Classification Component

Provides functionality for object tagging and data classification analysis.
"""

import streamlit as st
import altair as alt
import pandas as pd


def _altair_bar(df, cat_col, val_col, color, key_prefix):
    """Render a horizontal bar chart using Altair."""
    chart = alt.Chart(df).mark_bar(color=color).encode(
        x=alt.X(f'{val_col}:Q', title='Count'),
        y=alt.Y(f'{cat_col}:N', sort='-x', title=None),
        tooltip=[alt.Tooltip(f'{cat_col}:N', title='Name'),
                 alt.Tooltip(f'{val_col}:Q', title='Count')]
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True, key=f"{key_prefix}_alt_bar")


def _altair_pie(df, cat_col, val_col, inner_radius, key_prefix):
    """Render a pie or donut chart using Altair."""
    chart = alt.Chart(df).mark_arc(innerRadius=inner_radius).encode(
        theta=alt.Theta(f'{val_col}:Q', stack=True),
        color=alt.Color(f'{cat_col}:N', legend=alt.Legend(
            title=None, orient='bottom', columns=2, labelLimit=120
        )),
        tooltip=[alt.Tooltip(f'{cat_col}:N', title='Name'),
                 alt.Tooltip(f'{val_col}:Q', title='Count')]
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True, key=f"{key_prefix}_alt_pie")


def _altair_rose(df, cat_col, val_col, key_prefix):
    """Render a rose (nightingale) chart using Altair."""
    chart = alt.Chart(df).mark_arc(innerRadius=20, stroke='#fff').encode(
        theta=alt.Theta(f'{cat_col}:N', stack=True),
        radius=alt.Radius(f'{val_col}:Q', scale=alt.Scale(type='sqrt', zero=True, rangeMin=20)),
        color=alt.Color(f'{cat_col}:N', legend=alt.Legend(
            title=None, orient='bottom', columns=2, labelLimit=120
        )),
        tooltip=[alt.Tooltip(f'{cat_col}:N', title='Name'),
                 alt.Tooltip(f'{val_col}:Q', title='Count')]
    ).properties(height=300)
    st.altair_chart(chart, use_container_width=True, key=f"{key_prefix}_alt_rose")


def _render_multi_chart(df, cat_col, val_col, color, key_prefix):
    """Render a chart with a chart type selector (Bar, Pie, Donut, Rose)."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}_chart_type"
    )

    if chart_type == "Bar Chart":
        _altair_bar(df, cat_col, val_col, color, key_prefix)
    elif chart_type == "Pie Chart":
        _altair_pie(df, cat_col, val_col, 0, key_prefix)
    elif chart_type == "Pie - Donut":
        _altair_pie(df, cat_col, val_col, 50, key_prefix)
    else:
        _altair_rose(df, cat_col, val_col, key_prefix)


def _render_tagged_tables_per_database_chart(df):
    """Chart-1: Top 10 tagged databases with chart type selector."""
    db_counts = df.groupby('DATABASE_NAME').size().reset_index(name='COUNT')
    db_counts = db_counts.sort_values('COUNT', ascending=False).head(10)

    _render_multi_chart(db_counts, 'DATABASE_NAME', 'COUNT', '#1f77b4', 'top10_db')


def _render_top_tagged_schemas_chart(df):
    """Chart: Top 10 tagged schemas with chart type selector."""
    tagged_df = df[df['TAG_STATUS'] != 'Untagged']
    if len(tagged_df) == 0:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No tagged schemas found.'
                    '</div>', unsafe_allow_html=True)
        return

    schema_counts = tagged_df.groupby('SCHEMA_NAME').size().reset_index(name='COUNT')
    schema_counts = schema_counts.sort_values('COUNT', ascending=False).head(10)

    _render_multi_chart(schema_counts, 'SCHEMA_NAME', 'COUNT', '#9467bd', 'top10_schema')


def _render_table_type_distribution_chart(df):
    """Chart-2: Table type distribution with chart type selector."""
    type_counts = df.groupby('TABLE_TYPE').size().reset_index(name='COUNT')

    _render_multi_chart(type_counts, 'TABLE_TYPE', 'COUNT', '#2ca02c', 'table_type')


def _render_tag_value_breakdown_chart(df):
    """Chart-3: Tag value breakdown with chart type selector."""
    tagged_df = df[df['TAG_VALUE'].notna() & (df['TAG_VALUE'] != '')]
    if len(tagged_df) == 0:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No tag values found.'
                    '</div>', unsafe_allow_html=True)
        return

    value_counts = tagged_df.groupby('TAG_VALUE').size().reset_index(name='COUNT')

    _render_multi_chart(value_counts, 'TAG_VALUE', 'COUNT', '#ff7f0e', 'tag_value')




def _render_tagging_coverage_audit_content():
    """Render tagging coverage audit with 4 dashboard charts."""

    tagging_audit_query = """
    SELECT
        t.TABLE_CATALOG AS database_name,
        t.TABLE_SCHEMA AS schema_name,
        t.TABLE_NAME,
        t.TABLE_TYPE,
        CASE
            WHEN tr.TAG_NAME IS NULL THEN 'Untagged'
            ELSE 'Tagged: ' || tr.TAG_NAME
        END AS tag_status,
        tr.TAG_VALUE,
        tr.APPLY_METHOD
    FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES t
    LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES tr
        ON t.TABLE_ID = tr.OBJECT_ID
        AND tr.DOMAIN IN ('TABLE', 'COLUMN', 'DATABASE', 'SCHEMA', 'SHARE')
        AND tr.OBJECT_DELETED IS NULL
WHERE t.DELETED IS NULL
        AND t.TABLE_CATALOG != 'SNOWFLAKE'
        AND t.TABLE_SCHEMA != 'INFORMATION_SCHEMA'
AND tag_value IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY t.TABLE_ID ORDER BY tr.TAG_NAME NULLS LAST) = 1
    ORDER BY tag_status ASC
    """

    try:
        audit_df = st.session_state.session.sql(tagging_audit_query).to_pandas()

        if len(audit_df) > 0:
            row1_col1, row1_col2 = st.columns([1, 1])

            with row1_col1.container(border=True, height=500):
                st.markdown("##### Top 10 Tagged Databases")
                _render_tagged_tables_per_database_chart(audit_df)

            with row1_col2.container(border=True, height=500):
                st.markdown("##### Top 10 Tagged Schemas")
                _render_top_tagged_schemas_chart(audit_df)

            row2_col1, row2_col2 = st.columns([1, 1])

            with row2_col1.container(border=True, height=500):
                st.markdown("##### Table Type Distribution")
                _render_table_type_distribution_chart(audit_df)

            with row2_col2.container(border=True, height=500):
                st.markdown("##### Tag Value Breakdown")
                _render_tag_value_breakdown_chart(audit_df)
        else:
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No tagging coverage audit data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading tagging coverage audit: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def comp_object_tagging_classification(entry_actions=None):
    """
    Data Object Tagging & Classification Component

    Provides expanders for:
    - Tagging Coverage Audit
    - Classification Insights
    - Stale Tagged Objects

    Args:
        entry_actions: Optional callback actions on component entry
    """
    try:
        st.markdown("### Data Object Tagging & Classification")

        with st.expander("Tagging Coverage Audit", expanded=True):
            st.markdown("#### Tagging Coverage Audit")
            _render_tagging_coverage_audit_content()

        with st.expander("Classification Insights", expanded=False):
            st.markdown("#### Classification Insights")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;Content for Classification Insights will be implemented here.'
                        '</div>', unsafe_allow_html=True)

        with st.expander("Stale Tagged Objects", expanded=False):
            st.markdown("#### Stale Tagged Objects")
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;Content for Stale Tagged Objects will be implemented here.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Data Object Tagging & Classification: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

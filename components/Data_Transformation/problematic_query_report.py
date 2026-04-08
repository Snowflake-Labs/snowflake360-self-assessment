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


def comp_problematic_query_report(entry_actions=None):
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

        query = """
SELECT
    i.insight_type_id AS insight_code,
    CASE
        WHEN i.insight_type_id ILIKE '%SPILL%' THEN '\u26a0\ufe0f Memory Pressure'
        WHEN i.insight_type_id ILIKE '%EXPLODING%' THEN '\U0001f525 Cardinality Explosion'
        WHEN i.insight_type_id ILIKE '%FILTER%' OR i.insight_type_id ILIKE '%SCAN%' THEN '\U0001f50d Pruning/Scanning Issues'
        WHEN i.insight_type_id ILIKE '%JOIN%' THEN '\U0001f517 Join Logic Issues'
        WHEN i.insight_type_id ILIKE '%UNION%' OR i.insight_type_id ILIKE '%AGGREGATE%' THEN '\U0001f9ee Logic Inefficiency'
        WHEN i.insight_type_id ILIKE '%SEARCH_OPTIMIZATION%' THEN '\u26a1 Search Opt Opportunity'
        ELSE 'Other'
    END AS category,
    COUNT(*) AS occurrence_count,
    COUNT(DISTINCT i.query_id) AS distinct_queries,
    MAX(q.query_text) AS example_query
FROM SNOWFLAKE.ACCOUNT_USAGE.query_insights i
JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
    ON i.query_id = q.query_id
WHERE i.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY 3 DESC
        """

        try:
            df = _cached_sql("tf_problematic_queries", query)
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No query insights data found for the last 30 days.'
                        '</div>', unsafe_allow_html=True)
            return

        with st.expander("Query Performance Insights Analysis", expanded=True):
            st.markdown("Query performance insights categorised by issue type (memory pressure, cardinality explosions, "
                       "pruning, joins, etc.) with occurrence counts and example queries from the last 30 days.")

            st.dataframe(df)

            st.markdown("#### Query Insights Charts")

            agg_cat = df.groupby('CATEGORY').agg({'OCCURRENCE_COUNT': 'sum', 'DISTINCT_QUERIES': 'sum'}).reset_index()
            agg_cat = agg_cat.sort_values('OCCURRENCE_COUNT', ascending=True)

            col1, col2 = st.columns(2)
            with col1.container():
                st.markdown("##### Issue Occurrences by Category")
                fig = go.Figure(data=[go.Bar(
                    y=agg_cat['CATEGORY'], x=agg_cat['OCCURRENCE_COUNT'], orientation='h',
                    marker_color=_C1, text=[f"{int(v):,}" for v in agg_cat['OCCURRENCE_COUNT']],
                    textposition='outside', textfont=dict(size=10)
                )])
                fig.update_layout(height=400, xaxis_title='Occurrence Count', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=180, r=50))
                st.plotly_chart(fig, use_container_width=True)

            with col2.container():
                st.markdown("##### Distinct Queries by Category")
                fig = go.Figure(data=[go.Bar(
                    y=agg_cat['CATEGORY'], x=agg_cat['DISTINCT_QUERIES'], orientation='h',
                    marker_color=_C2, text=[f"{int(v):,}" for v in agg_cat['DISTINCT_QUERIES']],
                    textposition='outside', textfont=dict(size=10)
                )])
                fig.update_layout(height=400, xaxis_title='Distinct Queries', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=180, r=50))
                st.plotly_chart(fig, use_container_width=True)

            col3, col4 = st.columns(2)
            with col3.container():
                st.markdown("##### Top Insight Codes by Occurrence")
                top_codes = df.nlargest(10, 'OCCURRENCE_COUNT').sort_values('OCCURRENCE_COUNT', ascending=True)
                fig = go.Figure(data=[go.Bar(
                    y=top_codes['INSIGHT_CODE'], x=top_codes['OCCURRENCE_COUNT'], orientation='h',
                    marker_color=_C1, text=[f"{int(v):,}" for v in top_codes['OCCURRENCE_COUNT']],
                    textposition='outside', textfont=dict(size=10)
                )])
                fig.update_layout(height=400, xaxis_title='Occurrence Count', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=280, r=50))
                st.plotly_chart(fig, use_container_width=True)

            with col4.container():
                st.markdown("##### Category Distribution")
                colors_list = [_C1, _C2, _C3, _CA, '#75C2D8', '#003D73', '#666666']
                fig = go.Figure(data=[go.Pie(
                    labels=agg_cat['CATEGORY'], values=agg_cat['OCCURRENCE_COUNT'],
                    hole=0.45, marker_colors=colors_list[:len(agg_cat)],
                    textinfo='label+percent', textposition='outside',
                    textfont=dict(size=9)
                )])
                fig.update_layout(height=400, showlegend=True, margin=dict(t=20, b=50, l=20, r=20),
                                  legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5, font=dict(size=8)))
                st.plotly_chart(fig, use_container_width=True)

        category_summary_query = """
SELECT
    CASE
        WHEN insight_type_id ILIKE '%SPILL%' THEN '\u26a0\ufe0f Memory Pressure'
        WHEN insight_type_id ILIKE '%EXPLODING%' THEN '\U0001f525 Cardinality Explosion'
        WHEN insight_type_id ILIKE '%FILTER%' OR insight_type_id ILIKE '%SCAN%' THEN '\U0001f50d Pruning/Scanning Issues'
        WHEN insight_type_id ILIKE '%JOIN%' THEN '\U0001f517 Join Logic Issues'
        WHEN insight_type_id ILIKE '%UNION%' OR insight_type_id ILIKE '%AGGREGATE%' THEN '\U0001f9ee Logic Inefficiency'
        WHEN insight_type_id ILIKE '%SEARCH_OPTIMIZATION%' THEN '\u26a1 Search Opt Opportunity'
        ELSE 'Other'
    END AS problem_category,
    COUNT(*) AS total_occurrences,
    COUNT(DISTINCT query_id) AS distinct_queries_affected,
    ARRAY_AGG(DISTINCT insight_type_id) WITHIN GROUP (ORDER BY insight_type_id) AS specific_insight_codes
FROM SNOWFLAKE.ACCOUNT_USAGE.query_insights
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY 2 DESC
        """

        try:
            category_df = _cached_sql("tf_category_summary", category_summary_query)
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing category summary query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            category_df = pd.DataFrame()

        if not category_df.empty:
            with st.expander("Category Summary with Insight Codes", expanded=True):
                st.markdown("Query insights aggregated by problem category with total occurrences, distinct affected queries, "
                           "and specific insight codes from the last 30 days.")

                st.dataframe(category_df)

                st.markdown("#### Category Summary Charts")

                cat_sorted = category_df.sort_values('TOTAL_OCCURRENCES', ascending=True)

                cat_col1, cat_col2 = st.columns(2)
                with cat_col1.container():
                    st.markdown("##### Total Occurrences by Category")
                    fig = go.Figure(data=[go.Bar(
                        y=cat_sorted['PROBLEM_CATEGORY'], x=cat_sorted['TOTAL_OCCURRENCES'], orientation='h',
                        marker_color=_C1, text=[f"{int(v):,}" for v in cat_sorted['TOTAL_OCCURRENCES']],
                        textposition='outside', textfont=dict(size=10)
                    )])
                    fig.update_layout(height=400, xaxis_title='Total Occurrences', yaxis_title='',
                                      showlegend=False, margin=dict(t=20, b=50, l=180, r=50))
                    st.plotly_chart(fig, use_container_width=True)

                with cat_col2.container():
                    st.markdown("##### Distinct Queries Affected")
                    fig = go.Figure(data=[go.Bar(
                        y=cat_sorted['PROBLEM_CATEGORY'], x=cat_sorted['DISTINCT_QUERIES_AFFECTED'], orientation='h',
                        marker_color=_C2, text=[f"{int(v):,}" for v in cat_sorted['DISTINCT_QUERIES_AFFECTED']],
                        textposition='outside', textfont=dict(size=10)
                    )])
                    fig.update_layout(height=400, xaxis_title='Distinct Queries', yaxis_title='',
                                      showlegend=False, margin=dict(t=20, b=50, l=180, r=50))
                    st.plotly_chart(fig, use_container_width=True)

                cat_col3, cat_col4 = st.columns(2)
                with cat_col3.container():
                    st.markdown("##### Occurrences vs Distinct Queries")
                    plot_cat = category_df.sort_values('TOTAL_OCCURRENCES', ascending=True)
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        y=plot_cat['PROBLEM_CATEGORY'], x=plot_cat['TOTAL_OCCURRENCES'], orientation='h',
                        name='Total Occurrences', marker_color=_C1
                    ))
                    fig.add_trace(go.Bar(
                        y=plot_cat['PROBLEM_CATEGORY'], x=plot_cat['DISTINCT_QUERIES_AFFECTED'], orientation='h',
                        name='Distinct Queries', marker_color=_CA
                    ))
                    fig.update_layout(height=400, barmode='group', xaxis_title='Count', yaxis_title='',
                                      legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
                                      margin=dict(t=40, b=50, l=180, r=50))
                    st.plotly_chart(fig, use_container_width=True)

                with cat_col4.container():
                    st.markdown("##### Category Proportion")
                    colors_list = [_C1, _C2, _C3, _CA, '#75C2D8', '#003D73', '#666666']
                    fig = go.Figure(data=[go.Pie(
                        labels=category_df['PROBLEM_CATEGORY'], values=category_df['TOTAL_OCCURRENCES'],
                        hole=0.45, marker_colors=colors_list[:len(category_df)],
                        textinfo='label+percent', textposition='outside',
                        textfont=dict(size=9)
                    )])
                    fig.update_layout(height=400, showlegend=True, margin=dict(t=20, b=50, l=20, r=20),
                                      legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5, font=dict(size=8)))
                    st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

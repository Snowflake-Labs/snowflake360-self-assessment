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


def comp_syntax_hunter(entry_actions=None):
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
    query_id,
    SUBSTR(query_text, 1, 200) AS query_preview,
    CASE WHEN query_text ILIKE '%ASOF JOIN%' THEN 'Yes' ELSE 'No' END AS uses_asof_join,
    CASE WHEN query_text ILIKE '%COLLATE%' THEN 'Yes' ELSE 'No' END AS uses_collation,
    CASE WHEN REGEXP_LIKE(query_text, '.*JOIN\\\\s*\\\\+.*', 'i') THEN 'Yes' ELSE 'No' END AS uses_directed_join,
    CASE WHEN REGEXP_LIKE(query_text, '.*WITH.*ORDER BY.*SELECT.*', 'is') THEN 'Yes' ELSE 'No' END AS order_by_in_cte,
    CASE WHEN query_text ILIKE '%GROUP BY%' AND query_text ILIKE '%ORDER BY%' THEN 'Yes' ELSE 'No' END AS sort_and_agg,
    CASE
        WHEN query_text ILIKE '%DISTINCT%' AND bytes_scanned > 1024*1024*1024
        THEN 'Consider APPROX'
        ELSE 'No'
    END AS distinct_optimization_check
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
  AND (
      query_text ILIKE '%ASOF JOIN%' OR
      query_text ILIKE '%COLLATE%' OR
      query_text ILIKE '%DISTINCT%' OR
      query_text ILIKE '%+%' OR
      query_text ILIKE '%ORDER BY%'
  )
LIMIT 100
        """

        try:
            df = _cached_sql("tf_syntax_hunter", query)
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if df.empty:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No SQL pattern data found for the last 7 days.'
                        '</div>', unsafe_allow_html=True)
            return

        with st.expander("Advanced SQL Pattern Detection", expanded=True):
            st.markdown("Identifies ASOF joins, collation, directed joins, CTE ordering, "
                       "sort/aggregate combinations, and DISTINCT optimisation opportunities from the last 7 days of "
                       "the selected metric run.")

            st.dataframe(df)

            st.markdown("#### SQL Pattern Analysis Charts")

            pattern_summary = pd.DataFrame({
                'Pattern': ['ORDER BY in CTE', 'Sort + Aggregate', 'DISTINCT Optimisation', 'Directed Join', 'Collation', 'ASOF Join'],
                'Count': [
                    df['ORDER_BY_IN_CTE'].str.contains('Yes', case=False, na=False).sum(),
                    df['SORT_AND_AGG'].str.contains('Yes', case=False, na=False).sum(),
                    df['DISTINCT_OPTIMIZATION_CHECK'].str.contains('APPROX', case=False, na=False).sum(),
                    df['USES_DIRECTED_JOIN'].str.contains('Yes', case=False, na=False).sum(),
                    df['USES_COLLATION'].str.contains('Yes', case=False, na=False).sum(),
                    df['USES_ASOF_JOIN'].str.contains('Yes', case=False, na=False).sum()
                ]
            })

            col1, col2 = st.columns(2)
            with col1.container():
                st.markdown("##### Pattern Usage Distribution")
                plot_ps = pattern_summary[pattern_summary['Count'] > 0].sort_values('Count', ascending=True)
                if plot_ps.empty:
                    st.info("No patterns detected in the analyzed queries.")
                else:
                    fig = go.Figure(data=[go.Bar(
                        y=plot_ps['Pattern'], x=plot_ps['Count'], orientation='h',
                        marker_color=_C1, text=[f"{int(v)}" for v in plot_ps['Count']],
                        textposition='outside', textfont=dict(size=10)
                    )])
                    fig.update_layout(height=400, xaxis_title='Queries', yaxis_title='',
                                      showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
                    st.plotly_chart(fig, use_container_width=True)

            with col2.container():
                st.markdown("##### All Patterns (incl. zero)")
                plot_all = pattern_summary.sort_values('Count', ascending=True)
                colors = [_C2 if v > 0 else _C1 for v in plot_all['Count']]
                fig = go.Figure(data=[go.Bar(
                    y=plot_all['Pattern'], x=plot_all['Count'], orientation='h',
                    marker_color=colors, text=[f"{int(v)}" for v in plot_all['Count']],
                    textposition='outside', textfont=dict(size=10)
                )])
                fig.update_layout(height=400, xaxis_title='Queries', yaxis_title='',
                                  showlegend=False, margin=dict(t=20, b=50, l=150, r=50))
                st.plotly_chart(fig, use_container_width=True)

            col3, col4 = st.columns(2)
            with col3.container():
                st.markdown("##### DISTINCT Optimisation Candidates")
                candidates = df['DISTINCT_OPTIMIZATION_CHECK'].str.contains('APPROX', case=False, na=False).sum()
                non_candidates = len(df) - candidates
                fig = go.Figure(data=[go.Pie(
                    labels=['\u26a0\ufe0f APPROX Candidates', '\u2705 No Optimisation'],
                    values=[candidates, non_candidates], hole=0.45,
                    marker_colors=[_CA, _C1],
                    textinfo='label+percent', textposition='outside', textfont=dict(size=9)
                )])
                fig.update_layout(height=400, showlegend=True, margin=dict(t=20, b=50, l=20, r=20),
                                  legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5, font=dict(size=8)))
                st.plotly_chart(fig, use_container_width=True)

            with col4.container():
                st.markdown("##### Pattern Detection Summary")
                detected = pattern_summary[pattern_summary['Count'] > 0]['Count'].sum()
                not_found = pattern_summary[pattern_summary['Count'] == 0].shape[0]
                fig = go.Figure(data=[go.Pie(
                    labels=['Patterns Detected', 'Patterns Not Found'],
                    values=[detected, not_found], hole=0.45,
                    marker_colors=[_C2, _C3],
                    textinfo='label+percent', textposition='outside', textfont=dict(size=9)
                )])
                fig.update_layout(height=400, showlegend=True, margin=dict(t=20, b=50, l=20, r=20),
                                  legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5, font=dict(size=8)))
                st.plotly_chart(fig, use_container_width=True)

        frequency_query = """
WITH feature_flags AS (
    SELECT
        CASE WHEN query_text ILIKE '%ASOF JOIN%' THEN 1 ELSE 0 END AS uses_asof_join,
        CASE WHEN query_text ILIKE '%COLLATE%' THEN 1 ELSE 0 END AS uses_collation,
        CASE WHEN REGEXP_LIKE(query_text, '.*JOIN\\\\s*\\\\+.*', 'i') THEN 1 ELSE 0 END AS uses_directed_join,
        CASE WHEN REGEXP_LIKE(query_text, '.*WITH.*ORDER BY.*SELECT.*', 'is') THEN 1 ELSE 0 END AS order_by_in_cte,
        CASE WHEN query_text ILIKE '%GROUP BY%' AND query_text ILIKE '%ORDER BY%' THEN 1 ELSE 0 END AS sort_and_agg,
        CASE WHEN query_text ILIKE '%DISTINCT%' AND bytes_scanned > 1024*1024*1024 THEN 1 ELSE 0 END AS heavy_distinct
    FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
    WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
      AND (
          query_text ILIKE '%ASOF JOIN%' OR
          query_text ILIKE '%COLLATE%' OR
          query_text ILIKE '%DISTINCT%' OR
          query_text ILIKE '%+%' OR
          query_text ILIKE '%ORDER BY%'
      )
)
, aggr as (
SELECT 'Sort + Aggregate (Heavy Compute)' AS detection_type, SUM(sort_and_agg) AS occurrence_count FROM feature_flags
UNION ALL
SELECT 'Order By inside CTE (Likely Redundant)', SUM(order_by_in_cte) FROM feature_flags
UNION ALL
SELECT 'Heavy Distinct (>1GB Scanned)', SUM(heavy_distinct) FROM feature_flags
UNION ALL
SELECT 'Directed Join Hints ("+")', SUM(uses_directed_join) FROM feature_flags
UNION ALL
SELECT 'ASOF Join Used', SUM(uses_asof_join) FROM feature_flags
UNION ALL
SELECT 'Collation Used', SUM(uses_collation) FROM feature_flags
)
SELECT a.*
FROM aggr a
ORDER BY occurrence_count DESC
        """

        try:
            freq_df = _cached_sql("tf_syntax_frequency", frequency_query)
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error executing frequency query: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            freq_df = pd.DataFrame()

        if not freq_df.empty:
            with st.expander("SQL Pattern Frequency Summary", expanded=True):
                st.markdown("Aggregated occurrence counts of advanced SQL features and potential "
                           "inefficiencies detected in the selected metric run.")

                st.dataframe(freq_df)

                st.markdown("#### Pattern Frequency Charts")

                freq_col1, freq_col2 = st.columns(2)
                with freq_col1.container():
                    st.markdown("##### Detection Type Occurrences")
                    plot_freq = freq_df.sort_values('OCCURRENCE_COUNT', ascending=True)
                    fig = go.Figure(data=[go.Bar(
                        y=plot_freq['DETECTION_TYPE'], x=plot_freq['OCCURRENCE_COUNT'], orientation='h',
                        marker_color=_C1, text=[f"{int(v):,}" for v in plot_freq['OCCURRENCE_COUNT']],
                        textposition='outside', textfont=dict(size=10)
                    )])
                    fig.update_layout(height=400, xaxis_title='Occurrence Count', yaxis_title='',
                                      showlegend=False, margin=dict(t=20, b=50, l=220, r=50))
                    st.plotly_chart(fig, use_container_width=True)

                with freq_col2.container():
                    st.markdown("##### Inefficiency vs Feature Usage")
                    inefficiency_patterns = ['Sort + Aggregate (Heavy Compute)', 'Order By inside CTE (Likely Redundant)', 'Heavy Distinct (>1GB Scanned)']
                    feature_patterns = ['Directed Join Hints ("+")', 'ASOF Join Used', 'Collation Used']
                    ineff_count = freq_df[freq_df['DETECTION_TYPE'].isin(inefficiency_patterns)]['OCCURRENCE_COUNT'].sum()
                    feat_count = freq_df[freq_df['DETECTION_TYPE'].isin(feature_patterns)]['OCCURRENCE_COUNT'].sum()
                    fig = go.Figure(data=[go.Pie(
                        labels=['\u26a0\ufe0f Potential Inefficiencies', '\u2705 Advanced Features'],
                        values=[int(ineff_count), int(feat_count)], hole=0.45,
                        marker_colors=[_C1, _C2],
                        textinfo='label+percent', textposition='outside', textfont=dict(size=9)
                    )])
                    fig.update_layout(height=400, showlegend=True, margin=dict(t=20, b=50, l=20, r=20),
                                      legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5, font=dict(size=8)))
                    st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

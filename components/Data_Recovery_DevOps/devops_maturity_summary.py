import streamlit as st
import pandas as pd
import plotly.graph_objects as go
_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'


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


def _render_gauge(score_val, max_val=3):
    level_map = {'NO_DATA': 0, 'BASIC': 1, 'INTERMEDIATE': 2, 'ADVANCED': 3}
    if isinstance(score_val, str):
        numeric = level_map.get(score_val.upper(), 0)
    else:
        numeric = int(score_val) if score_val else 0

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=numeric,
        number=dict(suffix=f" / {max_val}", font=dict(size=48)),
        title=dict(text="DevOps Maturity Score", font=dict(size=20, color=_C1)),
        gauge=dict(
            axis=dict(range=[0, max_val], tickvals=[0, 1, 2, 3],
                      ticktext=['No Data', 'Basic', 'Intermediate', 'Advanced']),
            bar=dict(color=_CA, thickness=0.3),
            bgcolor='white',
            steps=[
                dict(range=[0, 1], color='#E8E8E8'),
                dict(range=[1, 2], color=_C3),
                dict(range=[2, 3], color=_C1),
            ],
            threshold=dict(line=dict(color=_CA, width=4), thickness=0.75, value=numeric)
        )
    ))
    fig.update_layout(height=350, margin=dict(t=60, b=30, l=40, r=40))
    return fig


def comp_devops_maturity_summary(entry_actions=None):
    try:
        df_score = _cached_sql("rd_maturity_score", "SELECT 1 WHERE FALSE")
        if "rd_maturity_score" in st.session_state:
            df_score = st.session_state["rd_maturity_score"]

        df_summary = _cached_sql("rd_maturity_summary", "SELECT 1 WHERE FALSE")
        if "rd_maturity_summary" in st.session_state:
            df_summary = st.session_state["rd_maturity_summary"]

        maturity_level = 'N/A'
        declarative_ddl = 0
        git_deploys = 0
        total_ddl = 0
        recommendation = ''

        if not df_score.empty:
            row = df_score.iloc[0]
            maturity_level = str(row.get('DEVOPS_MATURITY_LEVEL', 'N/A'))
            declarative_ddl = int(row.get('DECLARATIVE_DDL', 0) or 0)
            git_deploys = int(row.get('GIT_DEPLOYS', 0) or 0)
            total_ddl = int(row.get('TOTAL_DDL', 0) or 0)
            recommendation = str(row.get('PRIMARY_RECOMMENDATION', ''))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Maturity Level", maturity_level)
        c2.metric("Declarative DDL", f"{declarative_ddl:,}")
        c3.metric("Git Deployments", f"{git_deploys:,}")
        c4.metric("Total Successful DDL", f"{total_ddl:,}")

        if recommendation:
            st.markdown("**Primary Recommendation**")
            st.markdown(
                f'<div style="background-color:#f0f7fb;border-left:6px solid {_C1};padding:10px;border-radius:4px;">'
                f'{recommendation}</div>',
                unsafe_allow_html=True)
            st.markdown("")

        fig_gauge = _render_gauge(maturity_level)
        st.plotly_chart(fig_gauge, use_container_width=True)

        if not df_summary.empty:
            col_l, col_r = st.columns(2)

            with col_l:
                st.markdown("**DevOps Summary Metrics**")
                plot_df = df_summary.sort_values('METRIC_VALUE', ascending=True)
                fig = go.Figure(go.Bar(
                    y=plot_df['METRIC_NAME'],
                    x=plot_df['METRIC_VALUE'],
                    orientation='h',
                    marker_color=_C1,
                    text=[f"{int(v):,}" for v in plot_df['METRIC_VALUE']],
                    textposition='outside'
                ))
                fig.update_layout(height=380, xaxis_title='Metric Value', showlegend=False,
                                  margin=dict(t=30, b=50, l=10, r=60))
                st.plotly_chart(fig, use_container_width=True)

            with col_r:
                st.markdown("**Summary Metric Value Mix**")
                cat_df = df_summary.groupby('METRIC_CATEGORY', as_index=False)['METRIC_VALUE'].sum()
                cat_df = cat_df[cat_df['METRIC_VALUE'] > 0]
                if not cat_df.empty:
                    fig = go.Figure(go.Pie(
                        labels=cat_df['METRIC_CATEGORY'],
                        values=cat_df['METRIC_VALUE'],
                        hole=0.45,
                        marker=dict(colors=[_C2, _C1, _C3][:len(cat_df)]),
                        textinfo='label+percent',
                        textposition='outside',
                        hovertemplate='<b>%{label}</b><br>Value: %{value:,}<br>%{percent}<extra></extra>'
                    ))
                    fig.update_layout(height=380, margin=dict(t=30, b=30, l=10, r=10), showlegend=True,
                                      legend=dict(orientation='h', yanchor='top', y=-0.05, xanchor='center', x=0.5))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No metric data with non-zero values.")

            st.dataframe(df_summary, use_container_width=True)
        else:
            st.info("No DevOps maturity summary data available.")

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                    f'Component Error: {str(e)}</div>', unsafe_allow_html=True)

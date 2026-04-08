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


def comp_git_integration(entry_actions=None):
    try:
        df = _cached_sql("rd_git_integration", "SELECT 1 WHERE FALSE")
        if "rd_git_integration" in st.session_state:
            df = st.session_state["rd_git_integration"]

        if df.empty:
            st.info("No Git integration activity data found for the last 30 days.")
            return

        total_ops = int(df['COUNT_OPS'].sum())
        op_categories = len(df)
        top_activity = str(df.iloc[0]['OPERATION_TYPE']) if not df.empty else 'N/A'
        max_users = int(df['DISTINCT_USERS'].max()) if 'DISTINCT_USERS' in df.columns else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Git Operations (30d)", f"{total_ops:,}")
        c2.metric("Operation Categories", f"{op_categories}")
        c3.metric("Top Git Activity", top_activity[:20] + "..." if len(top_activity) > 20 else top_activity)
        c4.metric("Max Users / Operation", f"{max_users}")

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("**Git Operation Categories (30d)**")
            plot_df = df.sort_values('COUNT_OPS', ascending=True)
            fig = go.Figure(go.Bar(
                y=plot_df['OPERATION_TYPE'],
                x=plot_df['COUNT_OPS'],
                orientation='h',
                marker_color=_C1,
                text=[f"{int(v):,}" for v in plot_df['COUNT_OPS']],
                textposition='outside'
            ))
            fig.update_layout(height=380, xaxis_title='Operations', showlegend=False,
                              margin=dict(t=30, b=50, l=10, r=60))
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("**Git Activity Mix (30d)**")
            fig = go.Figure(go.Pie(
                labels=df['OPERATION_TYPE'],
                values=df['COUNT_OPS'],
                hole=0.45,
                marker=dict(colors=[_C1, _C2, _C3, _CA][:len(df)]),
                textinfo='label+percent',
                textposition='outside',
                hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>'
            ))
            fig.update_layout(height=380, margin=dict(t=30, b=30, l=10, r=10), showlegend=True,
                              legend=dict(orientation='h', yanchor='top', y=-0.05, xanchor='center', x=0.5))
            st.plotly_chart(fig, use_container_width=True)

        if 'DISTINCT_USERS' in df.columns:
            st.markdown("**Distinct Users by Git Operation**")
            plot_df = df.sort_values('DISTINCT_USERS', ascending=True)
            fig = go.Figure(go.Bar(
                y=plot_df['OPERATION_TYPE'],
                x=plot_df['DISTINCT_USERS'],
                orientation='h',
                marker_color=_C3,
                text=[f"{int(v):,}" for v in plot_df['DISTINCT_USERS']],
                textposition='outside'
            ))
            fig.update_layout(height=380, xaxis_title='Distinct Users', showlegend=False,
                              margin=dict(t=30, b=50, l=10, r=60))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Git Integration Detail**")
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                    f'Component Error: {str(e)}</div>', unsafe_allow_html=True)

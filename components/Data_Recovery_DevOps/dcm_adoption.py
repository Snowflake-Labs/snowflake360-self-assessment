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


def comp_dcm_adoption(entry_actions=None):
    try:
        df = _cached_sql("rd_dcm_adoption", "SELECT 1 WHERE FALSE")
        if "rd_dcm_adoption" in st.session_state:
            df = st.session_state["rd_dcm_adoption"]

        if df.empty:
            st.info("No DDL deployment pattern data found for the last 30 days.")
            return

        total_ddl = int(df['EXECUTION_COUNT'].sum()) if 'EXECUTION_COUNT' in df.columns else 0
        declarative = int(df.loc[df['DDL_PATTERN'].str.contains('Declarative', case=False, na=False), 'EXECUTION_COUNT'].sum()) if not df.empty else 0
        git_based = int(df.loc[df['DDL_PATTERN'].str.contains('File/Git', case=False, na=False), 'EXECUTION_COUNT'].sum()) if not df.empty else 0
        top_pattern = str(df.iloc[0]['DDL_PATTERN']) if not df.empty else 'N/A'

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Successful DDL Ops (30d)", f"{total_ddl:,}")
        c2.metric("Declarative DDL", f"{declarative:,}")
        c3.metric("Git-Based Deployments", f"{git_based:,}")
        c4.metric("Top Pattern", top_pattern[:20] + "..." if len(top_pattern) > 20 else top_pattern)

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("**DDL Deployment Pattern Distribution (30d)**")
            fig = go.Figure(go.Pie(
                labels=df['DDL_PATTERN'],
                values=df['EXECUTION_COUNT'],
                hole=0.45,
                marker=dict(colors=[_C1, _C2, _C3, _CA][:len(df)]),
                textinfo='label+percent',
                textposition='outside',
                hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>'
            ))
            fig.update_layout(height=380, margin=dict(t=30, b=30, l=10, r=10), showlegend=True,
                              legend=dict(orientation='h', yanchor='top', y=-0.05, xanchor='center', x=0.5))
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("**DDL Pattern Execution Count (30d)**")
            plot_df = df.sort_values('EXECUTION_COUNT', ascending=True)
            fig = go.Figure(go.Bar(
                y=plot_df['DDL_PATTERN'],
                x=plot_df['EXECUTION_COUNT'],
                orientation='h',
                marker_color=_C2,
                text=[f"{int(v):,}" for v in plot_df['EXECUTION_COUNT']],
                textposition='outside'
            ))
            fig.update_layout(height=380, xaxis_title='Executions', showlegend=False,
                              margin=dict(t=30, b=50, l=10, r=60))
            st.plotly_chart(fig, use_container_width=True)

        if 'DISTINCT_USERS' in df.columns and 'DISTINCT_ROLES' in df.columns:
            st.markdown("**Pattern Participation Coverage (Users vs Roles)**")
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Distinct Users', x=df['DDL_PATTERN'], y=df['DISTINCT_USERS'],
                                 marker_color=_C1, text=df['DISTINCT_USERS'], textposition='outside'))
            fig.add_trace(go.Bar(name='Distinct Roles', x=df['DDL_PATTERN'], y=df['DISTINCT_ROLES'],
                                 marker_color=_CA, text=df['DISTINCT_ROLES'], textposition='outside'))
            fig.update_layout(barmode='group', height=380, yaxis_title='Count',
                              legend=dict(orientation='h', yanchor='top', y=1.12, xanchor='center', x=0.5),
                              margin=dict(t=50, b=80, l=50, r=30))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Pattern Coverage Detail**")
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                    f'Component Error: {str(e)}</div>', unsafe_allow_html=True)

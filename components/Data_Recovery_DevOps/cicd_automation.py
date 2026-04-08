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


def comp_cicd_automation(entry_actions=None):
    try:
        df_summary = _cached_sql("rd_cicd_summary", "SELECT 1 WHERE FALSE")
        if "rd_cicd_summary" in st.session_state:
            df_summary = st.session_state["rd_cicd_summary"]

        df_detail = _cached_sql("rd_cicd_detail", "SELECT 1 WHERE FALSE")
        if "rd_cicd_detail" in st.session_state:
            df_detail = st.session_state["rd_cicd_detail"]

        if df_summary.empty and df_detail.empty:
            st.info("No CI/CD tool data found for the last 30 days.")
            return

        df = df_summary if not df_summary.empty else df_detail

        total_ddl = int(df['DDL_OPERATIONS_COUNT'].sum()) if 'DDL_OPERATIONS_COUNT' in df.columns else 0
        agents = len(df)
        automated = df.loc[~df['DEPLOYMENT_AGENT'].str.contains('Human', case=False, na=False), 'DDL_OPERATIONS_COUNT'].sum() if 'DDL_OPERATIONS_COUNT' in df.columns else 0
        auto_share = round(automated / total_ddl * 100, 1) if total_ddl > 0 else 0.0
        top_agent = str(df.iloc[0]['DEPLOYMENT_AGENT']) if not df.empty else 'N/A'

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("DDL Ops Attributed (30d)", f"{total_ddl:,}")
        c2.metric("Deployment Agents", f"{agents}")
        c3.metric("Automated DDL Share", f"{auto_share}%")
        c4.metric("Top Agent", top_agent)

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("**CI/CD Tool Summary (30d)**")
            plot_df = df.sort_values('DDL_OPERATIONS_COUNT', ascending=True)
            fig = go.Figure(go.Bar(
                y=plot_df['DEPLOYMENT_AGENT'],
                x=plot_df['DDL_OPERATIONS_COUNT'],
                orientation='h',
                marker_color=_C1,
                text=[f"{int(v):,}" for v in plot_df['DDL_OPERATIONS_COUNT']],
                textposition='outside'
            ))
            fig.update_layout(height=380, xaxis_title='DDL Operations', showlegend=False,
                              margin=dict(t=30, b=50, l=10, r=60))
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("**DDL Automation Share by Agent**")
            fig = go.Figure(go.Pie(
                labels=df['DEPLOYMENT_AGENT'],
                values=df['DDL_OPERATIONS_COUNT'],
                hole=0.45,
                marker=dict(colors=[_C1, _C2, _C3, _CA][:len(df)]),
                textinfo='label+percent',
                textposition='outside',
                hovertemplate='<b>%{label}</b><br>DDL Ops: %{value:,}<br>%{percent}<extra></extra>'
            ))
            fig.update_layout(height=380, margin=dict(t=30, b=30, l=10, r=10), showlegend=True,
                              legend=dict(orientation='h', yanchor='top', y=-0.05, xanchor='center', x=0.5))
            st.plotly_chart(fig, use_container_width=True)

        if 'SESSION_COUNT' in df.columns:
            st.markdown("**Session Footprint by Deployment Agent**")
            plot_df = df.sort_values('SESSION_COUNT', ascending=True)
            fig = go.Figure(go.Bar(
                y=plot_df['DEPLOYMENT_AGENT'],
                x=plot_df['SESSION_COUNT'],
                orientation='h',
                marker_color=_C3,
                text=[f"{int(v):,}" for v in plot_df['SESSION_COUNT']],
                textposition='outside'
            ))
            fig.update_layout(height=380, xaxis_title='Distinct Sessions', showlegend=False,
                              margin=dict(t=30, b=50, l=10, r=60))
            st.plotly_chart(fig, use_container_width=True)

        if not df_detail.empty:
            st.markdown("**CI/CD Tool Identification Detail**")
            st.dataframe(df_detail, use_container_width=True)
        elif not df_summary.empty:
            st.dataframe(df_summary, use_container_width=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                    f'Component Error: {str(e)}</div>', unsafe_allow_html=True)

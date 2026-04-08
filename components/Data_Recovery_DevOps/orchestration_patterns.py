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


def comp_orchestration_patterns(entry_actions=None):
    try:
        df_orch = _cached_sql("rd_orchestration", "SELECT 1 WHERE FALSE")
        if "rd_orchestration" in st.session_state:
            df_orch = st.session_state["rd_orchestration"]

        if not df_orch.empty:
            st.markdown("### Declarative vs Imperative Orchestration (7d)")

            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown("**Orchestration Activity Count**")
                plot_df = df_orch.sort_values('ACTIVITY_COUNT', ascending=True)
                fig = go.Figure(go.Bar(
                    y=plot_df['ORCHESTRATION_TYPE'],
                    x=plot_df['ACTIVITY_COUNT'],
                    orientation='h',
                    marker_color=_C1,
                    text=[f"{int(v):,}" for v in plot_df['ACTIVITY_COUNT']],
                    textposition='outside'
                ))
                fig.update_layout(height=350, xaxis_title='Activity Count', showlegend=False,
                                  margin=dict(t=30, b=50, l=10, r=60))
                st.plotly_chart(fig, use_container_width=True)

            with col_r:
                st.markdown("**Distinct Orchestrated Objects**")
                fig = go.Figure(go.Pie(
                    labels=df_orch['ORCHESTRATION_TYPE'],
                    values=df_orch['DISTINCT_OBJECTS'],
                    hole=0.45,
                    marker=dict(colors=[_C1, _C2]),
                    textinfo='label+percent',
                    textposition='outside',
                    hovertemplate='<b>%{label}</b><br>Objects: %{value:,}<br>%{percent}<extra></extra>'
                ))
                fig.update_layout(height=350, margin=dict(t=30, b=30, l=10, r=10), showlegend=True,
                                  legend=dict(orientation='h', yanchor='top', y=-0.05, xanchor='center', x=0.5))
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df_orch, use_container_width=True)
        else:
            st.info("No orchestration pattern data found for the last 7 days.")

        st.markdown("---")

        df_inv = _cached_sql("rd_dt_inventory", "SELECT 1 WHERE FALSE")
        if "rd_dt_inventory" in st.session_state:
            df_inv = st.session_state["rd_dt_inventory"]
        df_stats = _cached_sql("rd_dt_refresh_stats", "SELECT 1 WHERE FALSE")
        if "rd_dt_refresh_stats" in st.session_state:
            df_stats = st.session_state["rd_dt_refresh_stats"]

        dt_count = int(df_inv.iloc[0]['DT_COUNT']) if not df_inv.empty else 0
        db_count = int(df_inv.iloc[0]['DB_COUNT']) if not df_inv.empty else 0
        schema_count = int(df_inv.iloc[0]['SCHEMA_COUNT']) if not df_inv.empty else 0
        refreshes = int(df_stats.iloc[0]['TOTAL_REFRESHES']) if not df_stats.empty else 0
        avg_lag = float(df_stats.iloc[0]['AVG_LAG_MIN']) if not df_stats.empty and df_stats.iloc[0]['AVG_LAG_MIN'] is not None else 0.0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Dynamic Tables", f"{dt_count:,}")
        c2.metric("Databases", f"{db_count}")
        c3.metric("Schemas", f"{schema_count}")
        c4.metric("Refreshes (30d)", f"{refreshes:,}")
        c5.metric("Avg Lag (min)", f"{avg_lag:.1f}")

        df_daily = _cached_sql("rd_dt_daily_refresh", "SELECT 1 WHERE FALSE")
        if "rd_dt_daily_refresh" in st.session_state:
            df_daily = st.session_state["rd_dt_daily_refresh"]

        if df_daily.empty or (df_daily['SUCCESS'].sum() == 0 and df_daily['FAILURES'].sum() == 0):
            wl, wr = st.columns(2)
            with wl:
                st.markdown(
                    '<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px;">'
                    '&#9888;&#65039; No refresh history found.</div>',
                    unsafe_allow_html=True)
            with wr:
                st.markdown(
                    '<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px;">'
                    '&#9888;&#65039; No refresh outcome data.</div>',
                    unsafe_allow_html=True)

        st.markdown("**Daily Refresh Trend (30d)**")
        if not df_daily.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Failures', x=df_daily['REFRESH_DATE'], y=df_daily['FAILURES'],
                                 marker_color=_CA))
            fig.add_trace(go.Bar(name='Success', x=df_daily['REFRESH_DATE'], y=df_daily['SUCCESS'],
                                 marker_color=_C1))
            fig.update_layout(barmode='stack', height=380, yaxis_title='Refresh Count',
                              legend=dict(orientation='h', yanchor='top', y=-0.15, xanchor='center', x=0.5),
                              margin=dict(t=30, b=60, l=50, r=30))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No daily refresh data available.")

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                    f'Component Error: {str(e)}</div>', unsafe_allow_html=True)

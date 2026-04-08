import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from core.config.design_tokens import BRAND_SECONDARY, BRAND_ACCENT, BRAND_PRIMARY_DARK

_SEV_COLORS = {
    'CRITICAL': '#F39C12',
    'HIGH': BRAND_SECONDARY,
    'MODERATE': '#75C2D8',
    'LOW': BRAND_ACCENT,
    'OK': '#ADE8F4',
}

_REC_COLORS = {
    'CRITICAL - Downsize + Reduce Auto-Suspend': BRAND_ACCENT,
    'HIGH - Downsize Candidate': '#F39C12',
    'HIGH - Reduce Auto-Suspend': BRAND_SECONDARY,
    'MODERATE - Review Configuration': '#75C2D8',
    'OK - Well Configured': '#ADE8F4',
}


def comp_scaling_management(entry_actions=None):
    try:
        with st.expander("Warehouse Oversizing Analysis", expanded=True):
            st.markdown("Warehouses where queries use fewer partitions than available nodes — candidates for downsizing.")
            _render_oversizing()
        with st.expander("Warehouse Idle Time Analysis", expanded=True):
            st.markdown("Estimated idle hours vs active hours — high idle % suggests shorter auto-suspend timeout.")
            _render_idle_time()
        with st.expander("Combined Scaling Efficiency", expanded=True):
            st.markdown("Warehouse efficiency quadrant: top-right = oversized AND idle (highest priority to fix).")
            _render_scaling_efficiency()
    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
            f'🛑&nbsp;&nbsp;Component Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_oversizing():
    df = st.session_state.get("wh_oversizing_data", pd.DataFrame())
    if df.empty:
        st.info("No oversizing data found for the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['PCT_OVERSIZED'] = pd.to_numeric(df['PCT_OVERSIZED'], errors='coerce').fillna(0)
    df = df.sort_values('PCT_OVERSIZED', ascending=False)

    bar_colors = [_SEV_COLORS.get(s, BRAND_SECONDARY) for s in df.get('SEVERITY', pd.Series(['LOW'] * len(df)))]

    st.markdown("**% Queries Where Warehouse is Oversized for Data**")
    col1, col2 = st.columns([3, 2])

    with col1:
        fig = go.Figure(go.Bar(
            y=df['WAREHOUSE_NAME'],
            x=df['PCT_OVERSIZED'],
            orientation='h',
            marker_color=bar_colors,
            text=[f'{v:.1f}' for v in df['PCT_OVERSIZED']],
            textposition='outside',
            customdata=df.get('SEVERITY', pd.Series([''] * len(df))),
            hovertemplate='<b>%{y}</b><br>Oversized: %{x:.1f}%<br>Severity: %{customdata}<extra></extra>',
        ))
        _sev_vals = list(_SEV_COLORS.keys())
        for sev, color in _SEV_COLORS.items():
            if sev in df.get('SEVERITY', pd.Series([])).values:
                fig.add_trace(go.Bar(
                    y=[None], x=[None], name=sev,
                    marker_color=color, showlegend=True,
                ))
        fig.update_layout(
            height=max(300, len(df) * 28),
            margin=dict(t=10, b=20, l=230, r=80),
            xaxis_title='% Oversized',
            yaxis_title='Warehouse',
            barmode='overlay',
            showlegend=True,
            legend=dict(title='SEVERITY', orientation='v', x=1.02, y=1),
        )
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        cols_show = [c for c in ['WAREHOUSE_NAME', 'WAREHOUSE_SIZE', 'TOTAL_QUERIES', 'OVERSIZED_QUERIES', 'PCT_OVERSIZED', 'SEVERITY'] if c in df.columns]
        st.dataframe(df[cols_show], use_container_width=True)


def _render_idle_time():
    df = st.session_state.get("wh_idle_data", pd.DataFrame())
    if df.empty:
        st.info("No warehouse load history found for the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['EST_UPTIME_HOURS'] = pd.to_numeric(df['EST_UPTIME_HOURS'], errors='coerce').fillna(0)
    df['EST_IDLE_HOURS'] = pd.to_numeric(df['EST_IDLE_HOURS'], errors='coerce').fillna(0)
    df['ACTIVE_HOURS'] = (df['EST_UPTIME_HOURS'] - df['EST_IDLE_HOURS']).clip(lower=0)
    df = df.sort_values('EST_UPTIME_HOURS', ascending=True)

    st.markdown("**Estimated Uptime vs Idle Hours (last 7 days)**")
    col1, col2 = st.columns([3, 2])

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Active',
            y=df['WAREHOUSE_NAME'],
            x=df['ACTIVE_HOURS'],
            orientation='h',
            marker_color=BRAND_SECONDARY,
            hovertemplate='<b>%{y}</b><br>Active: %{x:.2f}h<extra></extra>',
        ))
        fig.add_trace(go.Bar(
            name='Idle',
            y=df['WAREHOUSE_NAME'],
            x=df['EST_IDLE_HOURS'],
            orientation='h',
            marker_color=BRAND_ACCENT,
            hovertemplate='<b>%{y}</b><br>Idle: %{x:.2f}h<extra></extra>',
        ))
        fig.update_layout(
            barmode='stack',
            height=max(300, len(df) * 28),
            margin=dict(t=10, b=20, l=230, r=20),
            xaxis_title='Hours',
            yaxis_title='Warehouse',
            legend=dict(title='State', orientation='v', x=1.02, y=1),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        cols_show = [c for c in ['WAREHOUSE_NAME', 'EST_UPTIME_HOURS', 'EST_IDLE_HOURS', 'PCT_TIME_IDLE'] if c in df.columns]
        st.dataframe(df[cols_show].sort_values('PCT_TIME_IDLE', ascending=False) if 'PCT_TIME_IDLE' in df.columns else df[cols_show],
                     use_container_width=True)


def _render_scaling_efficiency():
    df = st.session_state.get("wh_scaling_efficiency", pd.DataFrame())
    if df.empty:
        st.info("No scaling efficiency data found for the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['PCT_OVERSIZED_FOR_DATA'] = pd.to_numeric(df['PCT_OVERSIZED_FOR_DATA'], errors='coerce').fillna(0)
    df['PCT_IDLE_TIME'] = pd.to_numeric(df['PCT_IDLE_TIME'], errors='coerce').fillna(0)
    df['TOTAL_QUERIES'] = pd.to_numeric(df['TOTAL_QUERIES'], errors='coerce').fillna(1)

    st.markdown("**Warehouse Efficiency: Oversized % vs Idle Time %**")

    rec_col = 'OVERALL_RECOMMENDATION' if 'OVERALL_RECOMMENDATION' in df.columns else None
    if rec_col:
        recs = df[rec_col].fillna('OK - Well Configured')
    else:
        recs = pd.Series(['OK - Well Configured'] * len(df))

    fig = go.Figure()
    for rec_val, color in _REC_COLORS.items():
        mask = recs == rec_val
        sub = df[mask]
        if sub.empty:
            continue
        bubble_sizes = (sub['TOTAL_QUERIES'] / sub['TOTAL_QUERIES'].max() * 40).clip(lower=6)
        fig.add_trace(go.Scatter(
            x=sub['PCT_OVERSIZED_FOR_DATA'],
            y=sub['PCT_IDLE_TIME'],
            mode='markers',
            name=rec_val,
            marker=dict(
                color=color,
                size=bubble_sizes,
                opacity=0.85,
                line=dict(width=1, color='white'),
            ),
            text=sub['WAREHOUSE_NAME'],
            hovertemplate='<b>%{text}</b><br>Oversized: %{x:.1f}%<br>Idle: %{y:.1f}%<br>' + rec_val + '<extra></extra>',
        ))

    max_x = max(df['PCT_OVERSIZED_FOR_DATA'].max() * 1.1, 55)
    max_y = max(df['PCT_IDLE_TIME'].max() * 1.1, 55)

    fig.update_layout(
        height=480,
        margin=dict(t=10, b=60, l=60, r=20),
        xaxis_title='% Queries Oversized for Data',
        yaxis_title='% Time Idle',
        xaxis=dict(range=[0, max_x]),
        yaxis=dict(range=[0, max_y]),
        legend=dict(title='OVERALL_RECOMMENDATION', orientation='v', x=1.02, y=1, font=dict(size=10)),
        shapes=[
            dict(type='line', x0=50, x1=50, y0=0, y1=max_y,
                 line=dict(dash='dash', color='grey', width=1)),
            dict(type='line', x0=0, x1=max_x, y0=50, y1=50,
                 line=dict(dash='dash', color='grey', width=1)),
        ],
    )
    st.plotly_chart(fig, use_container_width=True)

    cols_show = [c for c in ['WAREHOUSE_NAME', 'WAREHOUSE_SIZE', 'NODE_COUNT', 'CREDITS_PER_HOUR', 'TOTAL_QUERIES', 'PCT_OVERSIZED_FOR_DATA', 'PCT_IDLE_TIME', 'OVERALL_RECOMMENDATION'] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True)

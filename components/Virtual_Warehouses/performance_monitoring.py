import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from core.config.design_tokens import BRAND_SECONDARY, BRAND_ACCENT, BRAND_PRIMARY_DARK, CHART_SERIES


_SCAN_TYPE_COLORS = {
    'FULL_TABLE_SCAN': BRAND_PRIMARY_DARK,
    'NEAR_FULL_SCAN': BRAND_SECONDARY,
    'PARTIAL_SCAN_90+': '#75C2D8',
}

_SPILL_SEV_COLORS = {
    'CRITICAL': BRAND_PRIMARY_DARK,
    'HIGH': BRAND_ACCENT,
    'MODERATE': '#75C2D8',
    'OK': '#ADE8F4',
}


def comp_performance_monitoring(entry_actions=None):
    try:
        with st.expander("Query Workload Profile by Data Volume", expanded=True):
            st.markdown("Query distribution by bytes scanned — warehouses with >90% tiny queries are downsize candidates.")
            _render_workload_profile()

        with st.expander("Data Skew Detection (High Spill Ratio)", expanded=True):
            st.markdown("Warehouses with queries spilling to local/remote storage — high spill indicates data skew or undersized warehouse.")
            _render_data_skew()

        with st.expander("User / Role / Warehouse Load Distribution", expanded=True):
            st.markdown("Top 20 user × role × warehouse combinations by query count and % of total execution time.")
            _render_load_distribution()

        with st.expander("Poor Partition Pruning Detection", expanded=True):
            st.markdown("Queries scanning >90% of large tables (>1000 partitions) — optimization candidates.")
            _render_poor_pruning()

        with st.expander("Warehouse Activity Summary", expanded=True):
            st.markdown("Active hours, total queries and execution hours per warehouse — last 7 days.")
            _render_activity_summary()

    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
            f'🛑&nbsp;&nbsp;Component Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_workload_profile():
    df = st.session_state.get("wh_workload_data", pd.DataFrame())
    if df.empty:
        st.info("No workload profile data found for the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    for col in ['TINY_UNDER_100MB', 'SMALL_100MB_1GB', 'LARGE_1GB_100GB', 'MASSIVE_OVER_100GB']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df = df.sort_values('TOTAL_QUERIES', ascending=True)

    st.markdown("**Query Workload Profile by Data Volume Scanned (last 7 days)**")
    fig = go.Figure()
    _bucket_colors = [BRAND_SECONDARY, '#75C2D8', BRAND_ACCENT, BRAND_PRIMARY_DARK]
    _buckets = [
        ('TINY_UNDER_100MB', 'Tiny (<100MB)'),
        ('SMALL_100MB_1GB', 'Small (100MB-1GB)'),
        ('LARGE_1GB_100GB', 'Large (1-100GB)'),
        ('MASSIVE_OVER_100GB', 'Massive (>100GB)'),
    ]
    for i, (col, label) in enumerate(_buckets):
        if col in df.columns:
            fig.add_trace(go.Bar(
                name=label,
                y=df['WAREHOUSE_NAME'],
                x=df[col],
                orientation='h',
                marker_color=_bucket_colors[i],
                hovertemplate=f'<b>%{{y}}</b><br>{label}: %{{x}}<extra></extra>',
            ))
    fig.update_layout(
        barmode='stack',
        height=max(320, len(df) * 22),
        margin=dict(t=10, b=20, l=240, r=20),
        xaxis_title='Query Count',
        yaxis_title='',
        legend=dict(title='Bucket', orientation='v', x=1.02, y=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_data_skew():
    df = st.session_state.get("wh_data_skew", pd.DataFrame())
    if df.empty:
        st.success("No queries with significant data spill detected in the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['TOTAL_SPILL_GB'] = pd.to_numeric(df['TOTAL_SPILL_GB'], errors='coerce').fillna(0)
    df['QUERY_COUNT'] = pd.to_numeric(df['QUERY_COUNT'], errors='coerce').fillna(0)
    df = df.sort_values('TOTAL_SPILL_GB', ascending=False)

    _sev_colors = {'CRITICAL': BRAND_PRIMARY_DARK, 'HIGH': BRAND_ACCENT, 'MODERATE': BRAND_SECONDARY}
    bar_colors = [_sev_colors.get(s, BRAND_SECONDARY) for s in df.get('WORST_SEVERITY', pd.Series(['MODERATE'] * len(df)))]

    st.markdown("**Total Memory Spill by Warehouse (GB, last 7 days)**")
    fig = go.Figure(go.Bar(
        y=df['WAREHOUSE_NAME'],
        x=df['TOTAL_SPILL_GB'],
        orientation='h',
        marker_color=bar_colors,
        text=[f'{int(r)} quer{"y" if int(r)==1 else "ies"}' for r in df['QUERY_COUNT']],
        textposition='outside',
        customdata=df.get('WORST_SEVERITY', pd.Series([''] * len(df))),
        hovertemplate='<b>%{y}</b><br>Total Spill: %{x:.3f} GB<br>Severity: %{customdata}<extra></extra>',
    ))
    fig.update_layout(
        height=max(280, len(df) * 36),
        margin=dict(t=10, b=20, l=230, r=120),
        xaxis_title='Total Spill (GB)',
        showlegend=False,
    )
    fig.update_yaxes(autorange='reversed')
    st.plotly_chart(fig, use_container_width=True)

    cols_show = [c for c in ['WAREHOUSE_NAME', 'QUERY_COUNT', 'TOTAL_REMOTE_SPILL_GB', 'TOTAL_LOCAL_SPILL_GB', 'TOTAL_SPILL_GB', 'WORST_SEVERITY'] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True)


def _render_load_distribution():
    df = st.session_state.get("wh_load_distribution", pd.DataFrame())
    if df.empty:
        st.info("No query activity data available for the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['QUERY_COUNT'] = pd.to_numeric(df['QUERY_COUNT'], errors='coerce').fillna(0)
    df['PCT_OF_TOTAL_RUNTIME'] = pd.to_numeric(df.get('PCT_OF_TOTAL_RUNTIME', pd.Series([0]*len(df))), errors='coerce').fillna(0)

    df['LABEL'] = df['USER_NAME'] + ' @ ' + df['WAREHOUSE_NAME']

    st.markdown("**Top Users by Query Count and % of Total Runtime**")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Query Count',
        y=df['LABEL'].head(20),
        x=df['QUERY_COUNT'].head(20),
        orientation='h',
        marker_color=BRAND_SECONDARY,
        hovertemplate='<b>%{y}</b><br>Query Count: %{x}<extra></extra>',
    ))
    if 'PCT_OF_TOTAL_RUNTIME' in df.columns:
        fig.add_trace(go.Bar(
            name='% of Total Runtime',
            y=df['LABEL'].head(20),
            x=df['PCT_OF_TOTAL_RUNTIME'].head(20),
            orientation='h',
            marker_color=BRAND_ACCENT,
            xaxis='x2',
            hovertemplate='<b>%{y}</b><br>Runtime %: %{x:.1f}%<extra></extra>',
        ))
    fig.update_layout(
        barmode='overlay',
        height=max(320, min(len(df), 20) * 28),
        margin=dict(t=10, b=20, l=280, r=80),
        xaxis_title='Query Count',
        xaxis2=dict(title='% of Total Runtime', overlaying='x', side='top', showgrid=False),
        legend=dict(orientation='h', y=1.05, x=0),
    )
    fig.update_yaxes(autorange='reversed')
    st.plotly_chart(fig, use_container_width=True)

    cols_show = [c for c in ['WAREHOUSE_NAME', 'ROLE_NAME', 'USER_NAME', 'QUERY_COUNT', 'TOTAL_EXECUTION_HOURS', 'PCT_OF_TOTAL_QUERIES', 'PCT_OF_TOTAL_RUNTIME'] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True)


def _render_poor_pruning():
    df = st.session_state.get("wh_poor_pruning", pd.DataFrame())
    if df.empty:
        st.success("No queries with poor partition pruning detected in the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['PCT_TABLE_SCANNED'] = pd.to_numeric(df['PCT_TABLE_SCANNED'], errors='coerce').fillna(0)
    df['SCANNED_GB'] = pd.to_numeric(df['SCANNED_GB'], errors='coerce').fillna(0)
    df['DURATION_SEC'] = pd.to_numeric(df['DURATION_SEC'], errors='coerce').fillna(0)

    cols_show = [c for c in ['WAREHOUSE_NAME', 'USER_NAME', 'PCT_TABLE_SCANNED', 'SCANNED_GB', 'SCAN_TYPE', 'QUERY_PREVIEW'] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True)

    st.markdown("**Partition Pruning Quality (size = query duration)**")
    scan_col = 'SCAN_TYPE' if 'SCAN_TYPE' in df.columns else None
    fig = go.Figure()
    if scan_col:
        for stype, color in _SCAN_TYPE_COLORS.items():
            mask = df[scan_col] == stype
            sub = df[mask]
            if sub.empty:
                continue
            bubble_sz = (sub['DURATION_SEC'] / max(df['DURATION_SEC'].max(), 1) * 30).clip(lower=4)
            fig.add_trace(go.Scatter(
                x=sub['SCANNED_GB'],
                y=sub['PCT_TABLE_SCANNED'],
                mode='markers',
                name=stype,
                marker=dict(color=color, size=bubble_sz, opacity=0.8,
                            line=dict(width=1, color='white')),
                text=sub['WAREHOUSE_NAME'],
                hovertemplate='<b>%{text}</b><br>Scanned: %{x:.2f} GB<br>Table %: %{y:.1f}%<extra></extra>',
            ))
    else:
        fig.add_trace(go.Scatter(
            x=df['SCANNED_GB'], y=df['PCT_TABLE_SCANNED'],
            mode='markers',
            marker=dict(color=BRAND_SECONDARY, size=8),
        ))
    fig.update_layout(
        height=380,
        margin=dict(t=10, b=60, l=60, r=20),
        xaxis_title='Scanned GB',
        yaxis_title='% Table Scanned',
        legend=dict(title='SCAN_TYPE', orientation='v', x=1.02, y=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_activity_summary():
    df = st.session_state.get("wh_activity_summary", pd.DataFrame())
    if df.empty:
        st.info("No warehouse activity data found for the last 7 days.")
        return
    df.columns = [c.upper() for c in df.columns]
    df['TOTAL_QUERIES'] = pd.to_numeric(df['TOTAL_QUERIES'], errors='coerce').fillna(0)
    df['TOTAL_EXECUTION_HOURS'] = pd.to_numeric(df['TOTAL_EXECUTION_HOURS'], errors='coerce').fillna(0)
    df = df.sort_values('TOTAL_QUERIES', ascending=False)

    st.markdown("**Warehouse Activity: Queries vs Execution Hours**")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Total Queries',
        x=df['WAREHOUSE_NAME'],
        y=df['TOTAL_QUERIES'],
        marker_color=BRAND_SECONDARY,
        yaxis='y',
        hovertemplate='<b>%{x}</b><br>Queries: %{y:,.0f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        name='Total Execution Hours',
        x=df['WAREHOUSE_NAME'],
        y=df['TOTAL_EXECUTION_HOURS'],
        mode='lines+markers',
        line=dict(color=BRAND_ACCENT, width=2),
        marker=dict(color=BRAND_ACCENT, size=6),
        yaxis='y2',
        hovertemplate='<b>%{x}</b><br>Exec Hours: %{y:.2f}<extra></extra>',
    ))
    fig.update_layout(
        height=380,
        margin=dict(t=10, b=100, l=60, r=60),
        xaxis=dict(tickangle=-45),
        yaxis=dict(title='Total Queries', side='left'),
        yaxis2=dict(title='Execution Hours', side='right', overlaying='y', showgrid=False),
        legend=dict(orientation='h', y=1.05, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    cols_show = [c for c in ['WAREHOUSE_NAME', 'ACTIVE_HOURS', 'TOTAL_QUERIES', 'QUERIES_PER_ACTIVE_HOUR', 'TOTAL_EXECUTION_HOURS'] if c in df.columns]
    st.dataframe(df[cols_show], use_container_width=True)

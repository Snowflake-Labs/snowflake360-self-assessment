import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.config.design_tokens import (
    BRAND_PRIMARY, BRAND_PRIMARY_DARK, BRAND_SECONDARY, BRAND_ACCENT,
    CHART_SERIES, CHART_EXTENDED,
)
from .object_tagging_classification import comp_object_tagging_classification
from .data_privacy_protection import comp_data_privacy_protection
from .lineage_quality import comp_lineage_quality
from ._dg_queries import ALL_DG_QUERIES


def _run_query(sql):
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        return session.sql(sql).to_pandas()
    except Exception as e:
        st.warning(f"Query error: {e}")
        return pd.DataFrame()


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_governance_queries(progress_bar=None, status_text=None):
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in ALL_DG_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    total = len(needed)
    completed = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_run_query_thread, session, k, sql): k for k, sql in needed.items()}
        for future in as_completed(futures):
            key, df, err = future.result()
            st.session_state[key] = df
            completed += 1
            if progress_bar is not None:
                progress_bar.progress(completed / total)
            if status_text is not None:
                status_text.text(f"Loading data... ({completed}/{total} queries)")
    if progress_bar is not None:
        progress_bar.empty()
    if status_text is not None:
        status_text.empty()


def _render_kpi_tiles(total_tables, tagged_tables, active_policies):
    pct = round(tagged_tables / total_tables * 100, 1) if total_tables > 0 else 0.0
    pct_color = "#0077B6" if pct >= 70 else "#E8A229" if pct >= 40 else "#E74C3C"
    low_coverage_html = ""
    if pct < 40:
        low_coverage_html = '<div style="font-size: 12px; color: #E8A229; font-weight: 600; margin-top: 4px;">⚠ Low coverage</div>'
    st.markdown(f"""
    <div style="display: flex; gap: 16px; padding: 10px 0;">
        <div style="flex: 1; text-align: left; padding: 18px; background: #f0f7fb; border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Total Tables</div>
            <div style="font-size: 36px; font-weight: 700; color: #29B5E8; line-height: 1;">{total_tables:,}</div>
        </div>
        <div style="flex: 1; text-align: left; padding: 18px; background: #EAF8F0; border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Tagged Tables</div>
            <div style="font-size: 36px; font-weight: 700; color: #11567F; line-height: 1;">{tagged_tables:,}</div>
        </div>
        <div style="flex: 1; text-align: left; padding: 18px; background: #fff3cd; border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Tag Coverage</div>
            <div style="font-size: 36px; font-weight: 700; color: {pct_color}; line-height: 1;">{pct:.1f}%</div>
            {low_coverage_html}
        </div>
        <div style="flex: 1; text-align: left; padding: 18px; background: #f0f7fb; border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Active Policies</div>
            <div style="font-size: 36px; font-weight: 700; color: #003D73; line-height: 1;">{active_policies:,}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_governance_health_score():
    df = st.session_state.get("dg_health_score_data", pd.DataFrame())
    tag_df = st.session_state.get("dg_classification_data", pd.DataFrame())

    if df.empty:
        st.info("No governance health data available.")
        return

    total = int(df["TOTAL_TABLES"].sum())
    tagged = int(df["TAGGED_TABLES"].sum())

    col1, col2 = st.columns(2)
    palette = CHART_SERIES + CHART_EXTENDED

    with col1:
        st.markdown("##### Tag Coverage by Database")
        display = df[["DATABASE_NAME", "TOTAL_TABLES", "TAGGED_TABLES", "UNTAGGED_TABLES", "COVERAGE_PCT"]].copy()
        display.columns = ["Database", "Total Tables", "Tagged", "Untagged", "Coverage %"]
        st.dataframe(display, use_container_width=True)

    with col2:
        st.markdown("##### Classification Source Breakdown")
        if not tag_df.empty:
            filtered = tag_df[tag_df["TOTAL_TAGS"] > 0]
            if not filtered.empty:
                colors = [palette[i % len(palette)] for i in range(len(filtered))]
                fig = go.Figure(data=[go.Bar(
                    x=filtered["APPLY_METHOD"].tolist(),
                    y=filtered["TOTAL_TAGS"].astype(int).tolist(),
                    marker_color=colors,
                    text=filtered["TOTAL_TAGS"].astype(int).tolist(),
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Tags: %{y:,}<extra></extra>",
                )])
                fig.update_layout(
                    height=350, margin=dict(t=10, b=40, l=40, r=20),
                    xaxis_title="Apply Method", yaxis_title="Tag Count",
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No classification data available.")
        else:
            st.info("No classification data available.")


def _render_policy_inventory():
    df = st.session_state.get("dg_policy_inventory_data", pd.DataFrame())

    if df.empty:
        st.info("No policy inventory data available.")
        return

    col1, col2 = st.columns(2)
    palette = CHART_SERIES + CHART_EXTENDED

    with col1:
        st.markdown("##### Policy Inventory")
        display = df.copy()
        display.columns = ["Policy Kind", "Active Count"]
        st.dataframe(display, use_container_width=True)

    with col2:
        st.markdown("##### Policy Inventory by Kind")
        active = df[df["ACTIVE_COUNT"] > 0]
        if not active.empty:
            colors = [palette[i % len(palette)] for i in range(len(active))]
            fig = go.Figure(data=[go.Pie(
                labels=active["POLICY_KIND"].tolist(),
                values=active["ACTIVE_COUNT"].astype(int).tolist(),
                marker=dict(colors=colors),
                textinfo="label+value",
                hole=0.35,
            )])
            fig.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10), showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No active policies found.")


def _render_sensitivity_heatmap():
    df = st.session_state.get("dg_sensitivity_heatmap", pd.DataFrame())
    if df.empty:
        st.info("No sensitivity tags found. Consider running Snowflake's automatic classification or applying sensitivity tags manually.")
        return
    df['OBJECT_COUNT'] = pd.to_numeric(df['OBJECT_COUNT'], errors='coerce').fillna(0)
    palette = CHART_SERIES + CHART_EXTENDED
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Sensitivity-Tagged Objects", int(df['OBJECT_COUNT'].sum()))
        colors = [palette[i % len(palette)] for i in range(len(df))]
        fig = go.Figure(go.Bar(
            x=df['SENSITIVITY_LEVEL'], y=df['OBJECT_COUNT'],
            marker_color=colors,
            text=df['OBJECT_COUNT'].astype(int).tolist(), textposition='outside'
        ))
        fig.update_layout(
            title='Objects by Sensitivity Level',
            xaxis_title='Sensitivity Level', yaxis_title='Object Count',
            height=380, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig2 = go.Figure(go.Pie(
            labels=df['SENSITIVITY_LEVEL'], values=df['OBJECT_COUNT'],
            hole=0.3, marker=dict(colors=colors),
            textinfo='label+percent'
        ))
        fig2.update_layout(title='Sensitivity Distribution', height=380, margin=dict(t=50, b=20))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df)


def _render_overview_content():
    health_df = st.session_state.get("dg_health_score_data", pd.DataFrame())
    tag_df = st.session_state.get("dg_classification_data", pd.DataFrame())
    policy_df = st.session_state.get("dg_policy_inventory_data", pd.DataFrame())

    total_tables = int(health_df["TOTAL_TABLES"].sum()) if not health_df.empty else 0
    tagged_tables = int(health_df["TAGGED_TABLES"].sum()) if not health_df.empty else 0
    active_policies = int(policy_df["ACTIVE_COUNT"].sum()) if not policy_df.empty else 0

    _render_kpi_tiles(total_tables, tagged_tables, active_policies)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Classification Source Breakdown")
        if not tag_df.empty:
            tag_df = tag_df.copy()
            tag_df["DISPLAY_METHOD"] = tag_df["APPLY_METHOD"].apply(
                lambda m: "UNKNOWN" if str(m).upper() in ("NULL", "NONE", "") else str(m).upper()
            )
            grouped = tag_df.groupby("DISPLAY_METHOD", as_index=False)["TOTAL_TAGS"].sum()
            grouped = grouped[grouped["TOTAL_TAGS"] > 0]
            if not grouped.empty:
                colors = [BRAND_SECONDARY, BRAND_ACCENT]
                fig = go.Figure(data=[go.Pie(
                    labels=grouped["DISPLAY_METHOD"].tolist(),
                    values=grouped["TOTAL_TAGS"].astype(int).tolist(),
                    hole=0.45,
                    marker=dict(colors=[colors[i % len(colors)] for i in range(len(grouped))]),
                    textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>Tags: %{value:,}<br>%{percent}<extra></extra>",
                )])
                fig.update_layout(
                    title="Tag Application Method",
                    height=380,
                    margin=dict(t=50, b=20, l=20, r=20),
                    showlegend=True,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No classification data available.")
        else:
            st.info("No classification data available.")

    with col2:
        st.subheader("Active Policy Inventory")
        if not policy_df.empty:
            active = policy_df[policy_df["ACTIVE_COUNT"] > 0].copy()
            if not active.empty:
                colors = [BRAND_SECONDARY, BRAND_PRIMARY_DARK]
                fig = go.Figure(data=[go.Bar(
                    x=active["POLICY_KIND"].tolist(),
                    y=active["ACTIVE_COUNT"].astype(int).tolist(),
                    marker_color=[colors[i % len(colors)] for i in range(len(active))],
                    text=active["ACTIVE_COUNT"].astype(int).tolist(),
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Count: %{y:,}<extra></extra>",
                )])
                fig.update_layout(
                    title="Active Policies by Kind",
                    yaxis_title="Count",
                    height=380,
                    margin=dict(t=50, b=80, l=40, r=20),
                    showlegend=False,
                    xaxis_tickangle=-15,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No active policies found.")
        else:
            st.info("No policy inventory data available.")


def comp_governance_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in ALL_DG_QUERIES)
        if not all_cached:
            status_ph.markdown(
                '<p style="color: #003D73; font-weight: 600;">Loading Data Governance data...</p>',
                unsafe_allow_html=True
            )
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_all_governance_queries(
                progress_bar=progress_bar_widget,
                status_text=status_ph
            )
            progress_ph.empty()
            status_ph.empty()

        sub_tab_names = [
            "Overview",
            "Object Tagging & Classification",
            "Data Privacy & Protection",
            "Data Lineage & Quality (Lite)"
        ]
        sub_tabs = st.tabs(sub_tab_names)

        with sub_tabs[0]:
            _render_overview_content()

        with sub_tabs[1]:
            comp_object_tagging_classification()

        with sub_tabs[2]:
            comp_data_privacy_protection()

        with sub_tabs[3]:
            comp_lineage_quality()

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
            f'Error loading Data Governance Overview: {e}</div>',
            unsafe_allow_html=True,
        )

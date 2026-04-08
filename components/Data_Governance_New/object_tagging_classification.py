import streamlit as st
import pandas as pd
import plotly.graph_objects as go

PALETTE = ["#29B5E8", "#11567F", "#75C2D8", "#E8A229", "#1A7DA8", "#023E8A", "#48CAE4", "#0077B6"]


def _get_cached(cache_key):
    return st.session_state.get(cache_key, pd.DataFrame())


def _render_tagging_overview():
    health_df = _get_cached("dg_health_score_data")
    sensitive_df = _get_cached("dg_sensitive_tagged")
    stale_df = _get_cached("dg_stale_tagged")
    domain_df = _get_cached("dg_tag_assignments_by_domain")

    total_tables = int(health_df["TOTAL_TABLES"].sum()) if not health_df.empty else 0
    tagged_tables = int(health_df["TAGGED_TABLES"].sum()) if not health_df.empty else 0
    untagged_tables = total_tables - tagged_tables
    coverage_pct = round(tagged_tables / total_tables * 100, 1) if total_tables > 0 else 0.0
    sensitive_count = len(sensitive_df) if not sensitive_df.empty else 0
    stale_count = stale_df["TABLE_NAME"].nunique() if not stale_df.empty and "TABLE_NAME" in stale_df.columns else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tagged Tables", f"{tagged_tables:,}")
    c2.metric("Untagged Tables", f"{untagged_tables:,}")
    c3.metric("Coverage", f"{coverage_pct}%")
    c4.metric("Sensitive Tagged Columns", f"{sensitive_count:,}")
    c5.metric("Stale Tagged Objects", f"{stale_count:,}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Tagged vs Untagged Tables")
        st.caption("Table Tagging Status")
        fig = go.Figure(data=[go.Pie(
            labels=["Untagged", "Tagged"],
            values=[untagged_tables, tagged_tables],
            hole=0.45,
            marker=dict(colors=[PALETTE[0], PALETTE[1]]),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>",
        )])
        fig.update_layout(
            height=420,
            margin=dict(t=10, b=40, l=20, r=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.05),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Tag Assignments by Object Domain")
        st.caption("Tag Assignments by Domain")
        if not domain_df.empty:
            domain_df = domain_df.copy()
            domain_df["ASSIGNMENT_COUNT"] = pd.to_numeric(domain_df["ASSIGNMENT_COUNT"], errors="coerce").fillna(0)
            display = domain_df.sort_values("ASSIGNMENT_COUNT", ascending=True)
            fig = go.Figure(data=[go.Bar(
                y=display["DOMAIN"].tolist(),
                x=display["ASSIGNMENT_COUNT"].astype(int).tolist(),
                orientation="h",
                marker_color=PALETTE[0],
                text=display["ASSIGNMENT_COUNT"].astype(int).tolist(),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Assignments: %{x:,}<extra></extra>",
            )])
            fig.update_layout(
                height=max(280, len(display) * 60),
                margin=dict(t=10, b=40, l=100, r=40),
                xaxis_title="Assignments",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No tag assignment data available.")


def _render_top_tag_names():
    st.subheader("Top 20 Tag Names by Usage")
    df = _get_cached("dg_top_tag_names")
    if df.empty:
        st.info("No tag name data available.")
        return
    df = df.copy()
    df["ASSIGNMENT_COUNT"] = pd.to_numeric(df["ASSIGNMENT_COUNT"], errors="coerce").fillna(0)
    display = df.sort_values("ASSIGNMENT_COUNT", ascending=True)
    st.caption("Top Tag Names")
    fig = go.Figure(data=[go.Bar(
        y=display["TAG_NAME"].tolist(),
        x=display["ASSIGNMENT_COUNT"].astype(int).tolist(),
        orientation="h",
        marker_color=PALETTE[1],
        text=display["ASSIGNMENT_COUNT"].astype(int).tolist(),
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Assignments: %{x:,}<extra></extra>",
    )])
    fig.update_layout(
        height=max(300, len(display) * 32),
        margin=dict(t=10, b=30, l=240, r=60),
        xaxis_title="Assignments",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_classification_insights_pii():
    st.subheader("Classification Insights (PII / Sensitive)")
    df = _get_cached("dg_sensitive_tagged")
    if df.empty:
        st.info("No sensitive-tagged columns found.")
        return
    df = df.copy()
    col_map = {
        "database_name": "Database", "schema_name": "Schema", "table_name": "Table",
        "COLUMN_NAME": "Column", "TAG_NAME": "Tag Name", "TAG_VALUE": "Tag Value",
        "APPLY_METHOD": "Apply Method",
    }
    df.columns = [str(c).upper() for c in df.columns]
    upper_map = {k.upper(): v for k, v in col_map.items()}

    tag_col = "TAG_NAME"
    if tag_col not in df.columns:
        st.info("No tag name column found in sensitive data.")
        return

    tag_counts = df.groupby(tag_col).size().reset_index(name="count").sort_values("count", ascending=True)
    st.caption("Sensitive Columns by Tag")
    fig = go.Figure(data=[go.Bar(
        y=tag_counts[tag_col].tolist(),
        x=tag_counts["count"].tolist(),
        orientation="h",
        marker_color=PALETTE[0],
        text=tag_counts["count"].tolist(),
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Tagged Columns: %{x:,}<extra></extra>",
    )])
    fig.update_layout(
        height=max(200, len(tag_counts) * 45),
        margin=dict(t=10, b=30, l=180, r=60),
        xaxis_title="Tagged Columns",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    display_df = df.rename(columns=upper_map)
    n = len(display_df)
    with st.expander(f"Classification Insights Detail ({n} rows)", expanded=True):
        cols_to_show = [v for v in ["Database", "Schema", "Table", "Column", "Tag Name", "Tag Value", "Apply Method"] if v in display_df.columns]
        st.dataframe(display_df[cols_to_show], use_container_width=True)


def _render_tagging_coverage_table():
    df = _get_cached("dg_tagging_audit_data")
    if df.empty:
        st.info("No tagging audit data available.")
        return
    df = df.copy()
    df.columns = [str(c).upper() for c in df.columns]
    col_map = {
        "DATABASE_NAME": "Database", "SCHEMA_NAME": "Schema",
        "TABLE_NAME": "Table", "TABLE_TYPE": "Type", "TAG_STATUS": "Tag Status",
    }
    tagged_df = df[df.get("TAG_STATUS", pd.Series(dtype=str)).str.startswith("Tagged", na=False)] if "TAG_STATUS" in df.columns else df
    display_df = tagged_df.rename(columns=col_map)
    cols = [v for v in ["Database", "Schema", "Table", "Type", "Tag Status"] if v in display_df.columns]
    st.dataframe(display_df[cols] if cols else display_df, use_container_width=True)


def comp_object_tagging_classification(entry_actions=None):
    try:
        _render_tagging_overview()

        _render_top_tag_names()

        _render_classification_insights_pii()

        audit_df = _get_cached("dg_tagging_audit_data")
        tagged_count = 0
        if not audit_df.empty:
            tmp = audit_df.copy()
            tmp.columns = [str(c).upper() for c in tmp.columns]
            if "TAG_STATUS" in tmp.columns:
                tagged_count = int(tmp["TAG_STATUS"].str.startswith("Tagged", na=False).sum())
        with st.expander(f"Tagging Coverage Audit (Tagged Objects)", expanded=True):
            _render_tagging_coverage_table()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                    f'Error loading Data Object Tagging & Classification: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

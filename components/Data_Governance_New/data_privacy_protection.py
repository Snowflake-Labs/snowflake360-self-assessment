import streamlit as st
import pandas as pd
import plotly.graph_objects as go

PRIMARY = "#29B5E8"
SECONDARY = "#11567F"
ALERT = "#E8A229"
_C = [PRIMARY, SECONDARY, "#75C2D8", ALERT, "#1A7DA8", "#023E8A", "#48CAE4", "#0077B6"]


def _get_cached(cache_key):
    return st.session_state.get(cache_key, pd.DataFrame())


def _safe_int(val):
    try:
        if pd.isna(val):
            return 0
        return int(val)
    except (ValueError, TypeError):
        return 0


def comp_data_privacy_protection(entry_actions=None):
    try:
        summary_df = _get_cached("dg_sensitive_masking_summary")
        dangling_df = _get_cached("dg_dangling_policies_by_kind")

        tagged_count = _safe_int(summary_df.iloc[0]["TAGGED_COUNT"]) if not summary_df.empty else 0
        masked_count = _safe_int(summary_df.iloc[0]["MASKED_COUNT"]) if not summary_df.empty else 0
        unprotected = tagged_count - masked_count
        dangling_total = _safe_int(dangling_df["DANGLING_COUNT"].sum()) if not dangling_df.empty else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sensitive Columns Identified", f"{tagged_count:,}")
        c2.metric("Masked / Protected", f"{masked_count:,}")
        c3.metric("Unprotected", f"{unprotected:,}",
                  delta="⚠ Risk" if unprotected > 0 else None,
                  delta_color="off" if unprotected > 0 else "normal")
        c4.metric("Dangling Policies", f"{dangling_total:,}",
                  delta="⚠ Review needed" if dangling_total > 0 else None,
                  delta_color="off" if dangling_total > 0 else "normal")

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("### Sensitive Column Protection Status")
            st.markdown("**Masking Coverage**")
            protected_count = masked_count
            unprotected_count = unprotected
            if tagged_count > 0:
                fig = go.Figure(go.Pie(
                    labels=["Unprotected", "Protected (Masked)"],
                    values=[unprotected_count, protected_count],
                    hole=0.4,
                    marker_colors=[PRIMARY, SECONDARY],
                    textinfo="label+percent",
                    textposition="inside",
                ))
                fig.update_layout(
                    height=380, margin=dict(t=10, b=40, l=10, r=10),
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="top", y=-0.05),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No sensitive columns identified.")

        with col_right:
            st.markdown("### Masking Policy Pattern Distribution")
            pattern_df = _get_cached("dg_masking_pattern_summary")
            if not pattern_df.empty:
                st.markdown("**Policy Design Patterns**")
                colors = [PRIMARY, SECONDARY, "#75C2D8", ALERT, "#1A7DA8", "#023E8A"]
                fig = go.Figure(go.Pie(
                    labels=pattern_df["MASKING_PATTERN"].tolist(),
                    values=pattern_df["PATTERN_COUNT"].astype(int).tolist(),
                    hole=0.4,
                    marker_colors=colors[:len(pattern_df)],
                    textinfo="label+percent",
                    textposition="inside",
                ))
                fig.update_layout(
                    height=380, margin=dict(t=10, b=40, l=10, r=10),
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="top", y=-0.05),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No masking policies found.")

        _masking_cov_df = _get_cached("dg_detailed_masking_coverage")
        with st.expander(f"Detailed Masking Coverage Audit ({len(_masking_cov_df)} columns)", expanded=True):
            _render_detailed_masking_coverage(_masking_cov_df)

        _masking_cls_df = _get_cached("dg_masking_policy_patterns")
        with st.expander(f"Masking Policy Classification Detail ({len(_masking_cls_df)} policies)", expanded=True):
            _render_masking_classification_detail(_masking_cls_df)

        _render_dangling_policies()

        _rap_df = _get_cached("dg_rap")
        with st.expander(f"Row Access Policy Audit ({len(_rap_df)} active attachments)", expanded=True):
            _render_rap_audit(_rap_df)

    except Exception as e:
        st.error(f"Error loading Data Privacy & Protection: {e}")


def _render_detailed_masking_coverage(df=None):
    if df is None:
        df = _get_cached("dg_detailed_masking_coverage")
    if df.empty:
        st.info("No sensitive or masked columns found.")
        return
    st.markdown(f"Sensitive or policy-protected columns with their masking coverage status.")
    rename_map = {
        "DATABASE_NAME": "Database", "SCHEMA_NAME": "Schema",
        "TABLE_NAME": "Table", "COLUMN_NAME": "Column",
        "TAG_NAME": "Tag Name", "TAG_VALUE": "Tag Value",
        "POLICY_NAME": "Policy Name", "PROTECTION_STATUS": "Protection Status",
    }
    cols_available = [c for c in rename_map if c in df.columns]
    st.dataframe(df[cols_available].rename(columns=rename_map), use_container_width=True)


def _render_masking_classification_detail(df=None):
    if df is None:
        df = _get_cached("dg_masking_policy_patterns")
    if df.empty:
        st.info("No masking policies found.")
        return
    st.markdown(f"Detailed masking policy design classification including signature and body.")
    rename_map = {
        "POLICY_DB": "Policy DB", "POLICY_SCHEMA": "Policy Schema",
        "POLICY_NAME": "Policy Name", "MASKING_PATTERN": "Masking Pattern",
        "POLICY_SIGNATURE": "Policy Signature",
    }
    cols_available = [c for c in rename_map if c in df.columns]
    st.dataframe(df[cols_available].rename(columns=rename_map), use_container_width=True)


def _render_dangling_policies():
    st.markdown("### Dangling Policies (Defined but Not Applied)")
    st.markdown("These policies exist but are not attached to any object. Review and remove or apply them.")
    df = _get_cached("dg_dangling_policies_by_kind")
    if df.empty:
        st.success("No dangling policies found.")
        return
    st.markdown("**Dangling Policies by Kind**")
    chart_df = df.sort_values("DANGLING_COUNT", ascending=True)
    colors = [PRIMARY if i % 2 == 0 else ALERT for i in range(len(chart_df))]
    fig = go.Figure(go.Bar(
        x=chart_df["DANGLING_COUNT"].tolist(),
        y=chart_df["POLICY_KIND"].tolist(),
        orientation="h",
        marker_color=colors,
        text=[f"{v:,}" for v in chart_df["DANGLING_COUNT"].tolist()],
        textposition="outside",
    ))
    fig.update_layout(
        height=max(200, len(chart_df) * 80),
        margin=dict(t=10, b=40, l=200, r=60),
        xaxis_title="Count", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_rap_audit(df=None):
    if df is None:
        df = _get_cached("dg_rap")
    if df.empty:
        st.info("No active Row Access Policies found.")
        return
    rename_map = {
        "POLICY_DB": "Policy DB", "POLICY_SCHEMA": "Policy Schema",
        "POLICY_NAME": "Policy Name",
        "PROTECTED_DB": "Protected DB", "PROTECTED_SCHEMA": "Protected Schema",
        "PROTECTED_TABLE": "Protected Table", "OBJECT_TYPE": "Object Type",
    }
    cols_available = [c for c in rename_map if c in df.columns]
    st.dataframe(df[cols_available].rename(columns=rename_map), use_container_width=True)

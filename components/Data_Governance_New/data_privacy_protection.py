import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C = ["#29B5E8", "#11567F", "#75C2D8", "#E8A229", "#1A7DA8", "#023E8A", "#48CAE4", "#0077B6"]


def _get_cached(cache_key):
    return st.session_state.get(cache_key, pd.DataFrame())


def _render_dpp_kpi_tiles(sens_count, masked_count, unprotected_count, dangling_count):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sensitive Columns Identified", f"{sens_count:,}")
    c2.metric("Masked / Protected", f"{masked_count:,}")
    c3.metric(
        "Unprotected", f"{unprotected_count:,}",
        delta="⚠ Risk" if unprotected_count > 0 else None,
        delta_color="off",
    )
    c4.metric(
        "Dangling Policies", f"{dangling_count:,}",
        delta="⚠ Review needed" if dangling_count > 0 else None,
        delta_color="off",
    )


def comp_data_privacy_protection(entry_actions=None):
    try:
        detail_df = _get_cached("dg_masking_coverage_detail")
        patterns_df = _get_cached("dg_masking_policy_patterns")
        dangling_df = _get_cached("dg_dangling_policies")
        rap_df = _get_cached("dg_rap")

        detail_df = detail_df.copy() if not detail_df.empty else pd.DataFrame()
        if not detail_df.empty:
            detail_df.columns = [str(c).upper() for c in detail_df.columns]

        sens_count = len(detail_df)
        if not detail_df.empty and "PROTECTION_STATUS" in detail_df.columns:
            masked_count = int((detail_df["PROTECTION_STATUS"] == "PROTECTED").sum())
            unprotected_count = int((detail_df["PROTECTION_STATUS"] == "UNPROTECTED").sum())
        else:
            masked_count = 0
            unprotected_count = 0

        dangling_count = 0
        if not dangling_df.empty:
            dangling_df = dangling_df.copy()
            dangling_df.columns = [str(c).upper() for c in dangling_df.columns]
            if "POLICY_NAME" in dangling_df.columns:
                dangling_count = int(dangling_df["POLICY_NAME"].nunique())

        _render_dpp_kpi_tiles(sens_count, masked_count, unprotected_count, dangling_count)

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Sensitive Column Protection Status")
            st.caption("Masking Coverage")
            if not detail_df.empty and "PROTECTION_STATUS" in detail_df.columns:
                status_counts = detail_df["PROTECTION_STATUS"].value_counts().reset_index()
                status_counts.columns = ["STATUS", "COUNT"]
                color_map = {"PROTECTED": _C[1], "UNPROTECTED": _C[0]}
                colors = [color_map.get(s, _C[2]) for s in status_counts["STATUS"]]
                fig = go.Figure(data=[go.Pie(
                    labels=["Unprotected", "Protected (Masked)"],
                    values=[unprotected_count, masked_count],
                    hole=0.45,
                    marker=dict(colors=[_C[0], _C[1]]),
                    textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>",
                )])
                fig.update_layout(
                    height=380,
                    margin=dict(t=10, b=40, l=20, r=20),
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="top", y=-0.05),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No masking coverage data available.")

        with col2:
            st.subheader("Masking Policy Pattern Distribution")
            st.caption("Policy Design Patterns")
            if not patterns_df.empty:
                patterns_df2 = patterns_df.copy()
                patterns_df2.columns = [str(c).upper() for c in patterns_df2.columns]
                if "MASKING_PATTERN" in patterns_df2.columns:
                    pat_counts = patterns_df2.groupby("MASKING_PATTERN").size().reset_index(name="COUNT")
                    pattern_colors = {
                        "NULLIFY": _C[0],
                        "OTHER": _C[1],
                        "BANDING / BUCKETING": _C[2],
                        "HASHING": _C[3],
                    }
                    colors = [pattern_colors.get(p, _C[4]) for p in pat_counts["MASKING_PATTERN"]]
                    fig2 = go.Figure(data=[go.Pie(
                        labels=pat_counts["MASKING_PATTERN"].tolist(),
                        values=pat_counts["COUNT"].tolist(),
                        hole=0.45,
                        marker=dict(colors=colors),
                        textinfo="label+percent",
                        hovertemplate="<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>",
                    )])
                    fig2.update_layout(
                        height=380,
                        margin=dict(t=10, b=40, l=20, r=20),
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="top", y=-0.05),
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("No masking policy pattern data available.")
            else:
                st.info("No masking policy pattern data available.")

        n_detail = len(detail_df)
        with st.expander(f"Detailed Masking Coverage Audit ({n_detail} columns)", expanded=True):
            st.caption("Sensitive or policy-protected columns with their masking coverage status.")
            if not detail_df.empty:
                col_map = {
                    "DATABASE_NAME": "Database", "SCHEMA_NAME": "Schema", "TABLE_NAME": "Table",
                    "COLUMN_NAME": "Column", "TAG_NAME": "Tag Name", "TAG_VALUE": "Tag Value",
                    "POLICY_NAME": "Policy Name", "PROTECTION_STATUS": "Protection Status",
                }
                disp = detail_df.rename(columns=col_map)
                cols = [v for v in ["Database", "Schema", "Table", "Column", "Tag Name", "Tag Value", "Policy Name", "Protection Status"] if v in disp.columns]
                st.dataframe(disp[cols] if cols else disp, use_container_width=True)
            else:
                st.info("No masking coverage detail data available.")

        n_policies = 0
        if not patterns_df.empty:
            tmp = patterns_df.copy()
            tmp.columns = [str(c).upper() for c in tmp.columns]
            n_policies = len(tmp)
        with st.expander(f"Masking Policy Classification Detail ({n_policies} policies)", expanded=True):
            st.caption("Detailed masking policy design classification including signature and body.")
            if not patterns_df.empty:
                tmp = patterns_df.copy()
                tmp.columns = [str(c).upper() for c in tmp.columns]
                col_map2 = {
                    "POLICY_DB": "Policy DB", "POLICY_SCHEMA": "Policy Schema",
                    "POLICY_NAME": "Policy Name", "MASKING_PATTERN": "Masking Pattern",
                    "POLICY_SIGNATURE": "Policy Signature",
                }
                disp2 = tmp.rename(columns=col_map2)
                cols2 = [v for v in ["Policy DB", "Policy Schema", "Policy Name", "Masking Pattern", "Policy Signature"] if v in disp2.columns]
                st.dataframe(disp2[cols2] if cols2 else disp2, use_container_width=True)
            else:
                st.info("No masking policy data available.")

        st.subheader("Dangling Policies (Defined but Not Applied)")
        st.markdown("These policies exist but are not attached to any object. Review and remove or apply them.")
        if not dangling_df.empty and "POLICY_KIND" in dangling_df.columns:
            kind_counts = dangling_df.groupby("POLICY_KIND").size().reset_index(name="COUNT").sort_values("COUNT", ascending=True)
            st.caption("Dangling Policies by Kind")
            fig3 = go.Figure(data=[go.Bar(
                y=kind_counts["POLICY_KIND"].tolist(),
                x=kind_counts["COUNT"].tolist(),
                orientation="h",
                marker_color=_C[3],
                text=kind_counts["COUNT"].tolist(),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Count: %{x:,}<extra></extra>",
            )])
            fig3.update_layout(
                height=max(200, len(kind_counts) * 60),
                margin=dict(t=10, b=40, l=160, r=60),
                xaxis_title="Count",
                showlegend=False,
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No dangling policies detected.")

        n_rap = 0
        if not rap_df.empty:
            tmp_rap = rap_df.copy()
            tmp_rap.columns = [str(c).upper() for c in tmp_rap.columns]
            n_rap = len(tmp_rap)
        with st.expander(f"Row Access Policy Audit ({n_rap} active attachments)", expanded=True):
            if not rap_df.empty:
                tmp_rap = rap_df.copy()
                tmp_rap.columns = [str(c).upper() for c in tmp_rap.columns]
                col_map3 = {
                    "POLICY_DB": "Policy DB", "POLICY_SCHEMA": "Policy Schema",
                    "POLICY_NAME": "Policy Name", "PROTECTED_DB": "Protected DB",
                    "PROTECTED_SCHEMA": "Protected Schema", "PROTECTED_TABLE": "Protected Table",
                    "OBJECT_TYPE": "Object Type",
                }
                disp3 = tmp_rap.rename(columns=col_map3)
                cols3 = [v for v in ["Policy DB", "Policy Schema", "Policy Name", "Protected DB", "Protected Schema", "Protected Table"] if v in disp3.columns]
                st.dataframe(disp3[cols3] if cols3 else disp3, use_container_width=True)
            else:
                st.info("No active Row Access Policies found.")

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
            f'Error loading Data Privacy & Protection: {str(e)}</div>',
            unsafe_allow_html=True,
        )

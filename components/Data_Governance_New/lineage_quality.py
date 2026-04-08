import streamlit as st
import plotly.graph_objects as go
import pandas as pd

_C = ["#29B5E8", "#11567F", "#75C2D8", "#E8A229", "#1A7DA8", "#023E8A", "#48CAE4"]


def _get_cached(cache_key):
    return st.session_state.get(cache_key, pd.DataFrame())


def _norm(df):
    if df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).upper() for c in df.columns]
    return df


def _render_lq_kpi_tiles(sensitive_accesses, lineage_gaps, dangling_tags, heuristic_hits):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sensitive Object Accesses (all users)", f"{sensitive_accesses:,}")
    c2.metric("Downstream Lineage Gaps", f"{lineage_gaps:,}")
    c3.metric(
        "Dangling Governance Tags", f"{dangling_tags:,}",
        delta="⚠ Cleanup recommended" if dangling_tags > 0 else None,
        delta_color="off",
    )
    c4.metric(
        "Governance Heuristic Hits", f"{heuristic_hits:,}",
        delta="⚠ Review needed" if heuristic_hits > 0 else None,
        delta_color="off",
    )


def comp_lineage_quality(entry_actions=None):
    try:
        access_df = _norm(_get_cached("dg_sensitive_access"))
        deps_df = _norm(_get_cached("dg_downstream_deps"))
        dgt_df = _norm(_get_cached("dg_dangling_gov_tags_by_db"))
        bool_cols_df = _norm(_get_cached("dg_boolean_like_tags_columns"))
        bool_tags_df = _norm(_get_cached("dg_boolean_governance_tags"))
        av_df = _norm(_get_cached("dg_tag_allowed_values_audit"))
        gov_in_use_df = _norm(_get_cached("dg_gov_tags_in_use"))

        sensitive_accesses = int(access_df["SENSITIVE_ACCESS_COUNT"].sum()) if not access_df.empty and "SENSITIVE_ACCESS_COUNT" in access_df.columns else 0
        lineage_gaps = len(deps_df) if not deps_df.empty else 0
        dangling_tags = int(dgt_df["DANGLING_TAGS"].sum()) if not dgt_df.empty and "DANGLING_TAGS" in dgt_df.columns else 0
        heuristic_hits = len(bool_cols_df) + len(bool_tags_df)

        _render_lq_kpi_tiles(sensitive_accesses, lineage_gaps, dangling_tags, heuristic_hits)

        st.divider()

        st.subheader("Sensitive Data Access by User (Top 30)")
        if access_df.empty or sensitive_accesses == 0:
            st.warning("⚠ No sensitive data access data found. This may mean ACCESS_HISTORY data is not available or no objects are tagged as sensitive.")
        else:
            top30 = access_df.head(30)
            if "USER_NAME" in top30.columns and "SENSITIVE_ACCESS_COUNT" in top30.columns:
                fig = go.Figure(go.Bar(
                    x=top30["USER_NAME"],
                    y=top30["SENSITIVE_ACCESS_COUNT"],
                    marker_color=_C[0],
                    text=top30["SENSITIVE_ACCESS_COUNT"],
                    textposition="outside",
                ))
                fig.update_layout(
                    height=380, margin=dict(t=20, b=100),
                    xaxis=dict(tickangle=-35),
                    xaxis_title="User", yaxis_title="Sensitive Access Count",
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

        if lineage_gaps == 0:
            st.info("ℹ No downstream lineage governance gaps detected.")

        n_dgt = int(dgt_df["DANGLING_TAGS"].sum()) if not dgt_df.empty and "DANGLING_TAGS" in dgt_df.columns else 0
        with st.expander("Dangling Governance Tags by Database", expanded=True):
            st.caption("Governance tags defined but with no live object assignments.")
            if not dgt_df.empty:
                col_map = {"DATABASE_NAME": "Database", "DANGLING_TAGS": "Dangling Tags"}
                disp = dgt_df.rename(columns=col_map)
                cols = [v for v in ["Database", "Dangling Tags"] if v in disp.columns]
                st.dataframe(disp[cols] if cols else disp, use_container_width=True)
            else:
                st.success("No dangling governance tags found.")

        n_bool_cols = len(bool_cols_df)
        with st.expander(f"Heuristic: Multiple Boolean-Like Tags on Columns ({n_bool_cols} columns)", expanded=True):
            st.caption("Columns with multiple governance tags that appear to be used as boolean flags.")
            if not bool_cols_df.empty:
                col_map2 = {
                    "OBJECT_DATABASE": "Database", "OBJECT_SCHEMA": "Schema",
                    "OBJECT_NAME": "Object", "COLUMN_NAME": "Column",
                    "TAG_COUNT": "Tag Count", "BOOLEAN_LIKE_TAG_COUNT": "Boolean-Like Tag Count",
                }
                disp2 = bool_cols_df.rename(columns=col_map2)
                cols2 = [v for v in ["Database", "Schema", "Object", "Column", "Tag Count", "Boolean-Like Tag Count"] if v in disp2.columns]
                st.dataframe(disp2[cols2] if cols2 else disp2, use_container_width=True)
            else:
                st.success("No boolean-like tag misuse detected on columns.")

        n_bool_tags = len(bool_tags_df)
        with st.expander(f"Heuristic: Governance Tags Used as Booleans ({n_bool_tags} tags)", expanded=True):
            st.caption("Governance tags whose values behave like boolean flags rather than controlled classifications.")
            if not bool_tags_df.empty:
                col_map3 = {
                    "TAG_NAME": "Tag Name", "ASSIGNMENTS": "Assignments",
                    "DISTINCT_VALUES": "Distinct Values", "COLUMNS_TAGGED": "Columns Tagged",
                    "BOOLEAN_ASSIGNMENTS": "Boolean Assignments",
                }
                disp3 = bool_tags_df.rename(columns=col_map3)
                cols3 = [v for v in ["Tag Name", "Assignments", "Distinct Values", "Columns Tagged", "Boolean Assignments"] if v in disp3.columns]
                st.dataframe(disp3[cols3] if cols3 else disp3, use_container_width=True)
            else:
                st.success("No governance tags identified as boolean-like.")

        n_av = len(av_df)
        with st.expander(f"Governance Tag Allowed Values Audit ({n_av} tags)", expanded=True):
            st.caption("Governance tag definitions and whether they constrain allowed values.")
            if not av_df.empty:
                col_map4 = {
                    "TAG_DATABASE": "Tag Database", "TAG_SCHEMA": "Tag Schema",
                    "TAG_NAME": "Tag Name", "ALLOWED_VALUES": "Allowed Values",
                }
                disp4 = av_df.rename(columns=col_map4)
                cols4 = [v for v in ["Tag Database", "Tag Schema", "Tag Name", "Allowed Values"] if v in disp4.columns]
                st.dataframe(disp4[cols4] if cols4 else disp4, use_container_width=True)
            else:
                st.info("No governance tag allowed values data available.")

        with st.expander("Governance Tags with Allowed Values in Active Use", expanded=True):
            st.caption("Assignment counts for governance tags that define explicit allowed values.")
            if not gov_in_use_df.empty:
                col_map5 = {"TAG_NAME": "Tag Name", "ASSIGNMENTS": "Assignments"}
                disp5 = gov_in_use_df.rename(columns=col_map5)
                cols5 = [v for v in ["Tag Name", "Assignments"] if v in disp5.columns]
                st.dataframe(disp5[cols5] if cols5 else disp5, use_container_width=True)
            else:
                st.info("No governance tags in active use found.")

    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
            f'Error loading Data Lineage & Quality: {str(e)}</div>', unsafe_allow_html=True)

# Copyright 2026 Snowflake, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

PRIMARY = "#29B5E8"
SECONDARY = "#11567F"
ALERT = "#E8A229"
_C = [PRIMARY, SECONDARY, "#75C2D8", ALERT, "#1A7DA8", "#023E8A", "#48CAE4"]


def _get_cached(cache_key):
    return st.session_state.get(cache_key, pd.DataFrame())


def _safe_int(val):
    try:
        if pd.isna(val):
            return 0
        return int(val)
    except (ValueError, TypeError):
        return 0


def comp_lineage_quality(entry_actions=None):
    try:
        access_df = _get_cached("dg_sensitive_access")
        gaps_df = _get_cached("dg_downstream_lineage_gaps")
        dangling_tags_df = _get_cached("dg_dangling_gov_tags")
        boolean_cols_df = _get_cached("dg_boolean_tags_on_columns")
        boolean_tags_df = _get_cached("dg_boolean_tag_heuristic")

        access_count = _safe_int(access_df["SENSITIVE_ACCESS_COUNT"].sum()) if not access_df.empty and "SENSITIVE_ACCESS_COUNT" in access_df.columns else 0
        gap_count = len(gaps_df) if not gaps_df.empty else 0
        dangling_tag_count = _safe_int(dangling_tags_df["DANGLING_TAGS"].sum()) if not dangling_tags_df.empty and "DANGLING_TAGS" in dangling_tags_df.columns else 0
        heuristic_hits = len(boolean_cols_df) + (_safe_int(boolean_tags_df["BOOLEAN_ASSIGNMENTS"].sum()) if not boolean_tags_df.empty and "BOOLEAN_ASSIGNMENTS" in boolean_tags_df.columns else 0)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sensitive Object Accesses (all users)", f"{access_count:,}")
        c2.metric("Downstream Lineage Gaps", f"{gap_count:,}")
        c3.metric("Dangling Governance Tags", f"{dangling_tag_count:,}",
                  delta="⚠ Cleanup recommended" if dangling_tag_count > 0 else None,
                  delta_color="off" if dangling_tag_count > 0 else "normal")
        c4.metric("Governance Heuristic Hits", f"{heuristic_hits:,}",
                  delta="⚠ Review needed" if heuristic_hits > 0 else None,
                  delta_color="off" if heuristic_hits > 0 else "normal")

        st.divider()

        _render_sensitive_access(access_df)

        _render_downstream_gaps(gaps_df)

        with st.expander("Dangling Governance Tags by Database", expanded=True):
            _render_dangling_gov_tags(dangling_tags_df)

        with st.expander(f"Heuristic: Multiple Boolean-Like Tags on Columns ({len(boolean_cols_df)} columns)", expanded=True):
            _render_boolean_columns(boolean_cols_df)

        with st.expander(f"Heuristic: Governance Tags Used as Booleans ({len(boolean_tags_df)} tags)", expanded=True):
            _render_boolean_tags(boolean_tags_df)

        _av_df = _get_cached("dg_gov_tag_allowed_values")
        with st.expander(f"Governance Tag Allowed Values Audit ({len(_av_df)} tags)", expanded=True):
            _render_tag_allowed_values(_av_df)

        with st.expander("Governance Tags with Allowed Values in Active Use", expanded=True):
            _render_tags_in_active_use()

    except Exception as e:
        st.error(f"Error loading Data Lineage & Quality: {e}")


def _render_sensitive_access(df):
    st.markdown("### Sensitive Data Access by User (Top 30)")
    if df.empty:
        st.warning("⚠ No sensitive data access data found. This may mean ACCESS_HISTORY data is not available or no objects are tagged as sensitive.")
        return
    df["SENSITIVE_ACCESS_COUNT"] = pd.to_numeric(df["SENSITIVE_ACCESS_COUNT"], errors="coerce").fillna(0)
    top_n = min(30, len(df))
    chart_df = df.head(top_n)
    fig = go.Figure(go.Bar(
        x=chart_df["USER_NAME"].tolist(),
        y=chart_df["SENSITIVE_ACCESS_COUNT"].tolist(),
        marker_color=PRIMARY,
        text=chart_df["SENSITIVE_ACCESS_COUNT"].astype(int).tolist(),
        textposition="outside",
    ))
    fig.update_layout(
        height=380, margin=dict(t=10, b=100, l=40, r=20),
        xaxis_title="User", yaxis_title="Sensitive Query Count",
        xaxis=dict(tickangle=-35), showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_downstream_gaps(df):
    if df.empty:
        st.info("ℹ No downstream lineage governance gaps detected.")
        return
    st.markdown("### Downstream Lineage Governance Gaps")
    st.warning(f"⚠ {len(df)} downstream objects reference sensitive data but lack policies or tags.")
    rename_map = {
        "BASE_DB": "Base DB", "BASE_SCHEMA": "Base Schema", "BASE_OBJECT": "Base Object",
        "DOWNSTREAM_DB": "Downstream DB", "DOWNSTREAM_SCHEMA": "Downstream Schema",
        "DOWNSTREAM_OBJECT": "Downstream Object",
        "DOWNSTREAM_POLICY_FLAG": "Policy Status", "DOWNSTREAM_TAG_FLAG": "Tag Status",
    }
    cols = [c for c in rename_map if c in df.columns]
    st.dataframe(df[cols].rename(columns=rename_map), use_container_width=True)


def _render_dangling_gov_tags(df):
    st.markdown("Governance tags defined but with no live object assignments.")
    if df.empty:
        st.success("No dangling governance tags found.")
        return
    rename_map = {"DATABASE_NAME": "Database", "DANGLING_TAGS": "Dangling Tags"}
    cols = [c for c in rename_map if c in df.columns]
    st.dataframe(df[cols].rename(columns=rename_map), use_container_width=True)


def _render_boolean_columns(df):
    st.markdown("Columns with multiple governance tags that appear to be used as boolean flags.")
    if df.empty:
        st.success("No boolean-like tag patterns found on columns.")
        return
    rename_map = {
        "DATABASE_NAME": "Database", "SCHEMA_NAME": "Schema",
        "OBJECT_NAME": "Object", "COLUMN_NAME": "Column",
        "TAG_COUNT": "Tag Count", "BOOLEAN_TAG_COUNT": "Boolean-Like Tag Count",
    }
    cols = [c for c in rename_map if c in df.columns]
    st.dataframe(df[cols].rename(columns=rename_map), use_container_width=True)


def _render_boolean_tags(df):
    st.markdown("Governance tags whose values behave like boolean flags rather than controlled classifications.")
    if df.empty:
        st.success("No boolean-pattern governance tags found.")
        return
    rename_map = {
        "TAG_NAME": "Tag Name", "ASSIGNMENTS": "Assignments",
        "DISTINCT_VALUES": "Distinct Values", "COLUMNS_TAGGED": "Columns Tagged",
        "BOOLEAN_ASSIGNMENTS": "Boolean Assignments",
    }
    cols = [c for c in rename_map if c in df.columns]
    st.dataframe(df[cols].rename(columns=rename_map), use_container_width=True)


def _render_tag_allowed_values(df=None):
    st.markdown("Governance tag definitions and whether they constrain allowed values.")
    if df is None:
        df = _get_cached("dg_gov_tag_allowed_values")
    if df.empty:
        st.info("No governance tags with allowed value definitions found.")
        return
    rename_map = {
        "TAG_DATABASE": "Tag Database", "TAG_SCHEMA": "Tag Schema",
        "TAG_NAME": "Tag Name", "ALLOWED_VALUES": "Allowed Values",
    }
    cols = [c for c in rename_map if c in df.columns]
    st.dataframe(df[cols].rename(columns=rename_map), use_container_width=True)


def _render_tags_in_active_use():
    st.markdown("Assignment counts for governance tags that define explicit allowed values.")
    df = _get_cached("dg_gov_tags_with_allowed_values_in_use")
    if df.empty:
        st.info("No governance tags with allowed values in active use.")
        return
    rename_map = {"TAG_NAME": "Tag Name", "ASSIGNMENTS": "Assignments"}
    cols = [c for c in rename_map if c in df.columns]
    st.dataframe(df[cols].rename(columns=rename_map), use_container_width=True)

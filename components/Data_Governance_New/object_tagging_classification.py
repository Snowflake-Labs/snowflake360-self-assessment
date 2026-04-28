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


def comp_object_tagging_classification(entry_actions=None):
    try:
        health_df = _get_cached("dg_health_score_data")
        sensitive_df = _get_cached("dg_sensitive_tagged")
        stale_df = _get_cached("dg_stale_tagged")

        total_tables = _safe_int(health_df["TOTAL_TABLES"].sum()) if not health_df.empty else 0
        tagged_tables = _safe_int(health_df["TAGGED_TABLES"].sum()) if not health_df.empty else 0
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

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("### Tagged vs Untagged Tables")
            st.markdown("**Table Tagging Status**")
            fig = go.Figure(go.Pie(
                labels=["Untagged", "Tagged"],
                values=[untagged_tables, tagged_tables],
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

        with col_right:
            st.markdown("### Tag Assignments by Object Domain")
            domain_df = _get_cached("dg_tag_assignments_by_domain")
            if not domain_df.empty:
                st.markdown("**Tag Assignments by Domain**")
                chart_df = domain_df.sort_values("ASSIGNMENT_COUNT", ascending=True)
                fig = go.Figure(go.Bar(
                    x=chart_df["ASSIGNMENT_COUNT"].tolist(),
                    y=chart_df["DOMAIN"].tolist(),
                    orientation="h",
                    marker_color=PRIMARY,
                    text=[f"{v:,}" for v in chart_df["ASSIGNMENT_COUNT"].tolist()],
                    textposition="outside",
                ))
                fig.update_layout(
                    height=380, margin=dict(t=10, b=40, l=120, r=40),
                    xaxis_title="Assignments", showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No tag assignments found.")

        _render_top_tag_names()

        _render_classification_insights()

        with st.expander("Tagging Coverage Audit (Tagged Objects)", expanded=True):
            _render_tagging_audit_table()

    except Exception as e:
        st.error(f"Error loading Data Object Tagging & Classification: {e}")


def _render_top_tag_names():
    st.markdown("### Top 20 Tag Names by Usage")
    df = _get_cached("dg_top_tag_names")
    if df.empty:
        st.info("No tag names found.")
        return
    st.markdown("**Top Tag Names**")
    chart_df = df.sort_values("USAGE_COUNT", ascending=True)
    fig = go.Figure(go.Bar(
        x=chart_df["USAGE_COUNT"].tolist(),
        y=chart_df["TAG_NAME"].tolist(),
        orientation="h",
        marker_color=SECONDARY,
        text=[f"{v:,}" for v in chart_df["USAGE_COUNT"].tolist()],
        textposition="outside",
    ))
    fig.update_layout(
        height=max(400, len(chart_df) * 28),
        margin=dict(t=10, b=40, l=260, r=60),
        xaxis_title="Tagged Columns", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_classification_insights():
    st.markdown("### Classification Insights (PII / Sensitive)")
    df = _get_cached("dg_sensitive_tagged")
    if df.empty:
        st.info("No sensitive-tagged columns found.")
        return

    st.markdown("**Sensitive Columns by Tag**")
    tag_counts = df.groupby("TAG_NAME").size().reset_index(name="COUNT").sort_values("COUNT", ascending=True)
    top = tag_counts.tail(15)
    fig = go.Figure(go.Bar(
        x=top["COUNT"].tolist(),
        y=top["TAG_NAME"].tolist(),
        orientation="h",
        marker_color=PRIMARY,
        text=[f"{v:,}" for v in top["COUNT"].tolist()],
        textposition="outside",
    ))
    fig.update_layout(
        height=max(250, len(top) * 40),
        margin=dict(t=10, b=40, l=200, r=60),
        xaxis_title="Tagged Columns", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander(f"Classification Insights Detail ({len(df)} rows)", expanded=True):
        rename_map = {
            "DATABASE_NAME": "Database", "SCHEMA_NAME": "Schema",
            "TABLE_NAME": "Table", "COLUMN_NAME": "Column",
            "TAG_NAME": "Tag Name", "TAG_VALUE": "Tag Value",
            "APPLY_METHOD": "Apply Method",
        }
        cols_available = [c for c in rename_map if c in df.columns]
        st.dataframe(df[cols_available].rename(columns=rename_map), use_container_width=True)


def _render_tagging_audit_table():
    audit_df = _get_cached("dg_tagging_audit_data")
    if audit_df.empty:
        st.info("No tagging audit data available.")
        return
    rename_map = {
        "DATABASE_NAME": "Database", "SCHEMA_NAME": "Schema",
        "TABLE_NAME": "Table", "TABLE_TYPE": "Type",
        "TAG_STATUS": "Tag Status",
    }
    cols_available = [c for c in rename_map if c in audit_df.columns]
    st.dataframe(audit_df[cols_available].rename(columns=rename_map), use_container_width=True)

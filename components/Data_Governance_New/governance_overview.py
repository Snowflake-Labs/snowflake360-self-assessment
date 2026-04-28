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
from concurrent.futures import ThreadPoolExecutor, as_completed
from .object_tagging_classification import comp_object_tagging_classification
from .data_privacy_protection import comp_data_privacy_protection
from .lineage_quality import comp_lineage_quality
from ._dg_queries import ALL_DG_QUERIES

PRIMARY = "#29B5E8"
SECONDARY = "#11567F"
ALERT = "#E8A229"
_C = [PRIMARY, SECONDARY, "#75C2D8", ALERT, "#1A7DA8", "#023E8A", "#48CAE4", "#0077B6"]


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
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_run_query_thread, session, k, sql): k
            for k, sql in needed.items()
        }
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


def _get_cached(cache_key):
    return st.session_state.get(cache_key, pd.DataFrame())


def _safe_int(val):
    try:
        if pd.isna(val):
            return 0
        return int(val)
    except (ValueError, TypeError):
        return 0


def _render_overview_content():
    try:
        health_df = _get_cached("dg_health_score_data")
        class_df = _get_cached("dg_classification_data")
        policy_df = _get_cached("dg_policy_inventory_data")

        total_tables = _safe_int(health_df["TOTAL_TABLES"].sum()) if not health_df.empty else 0
        tagged_tables = _safe_int(health_df["TAGGED_TABLES"].sum()) if not health_df.empty else 0
        coverage_pct = round(tagged_tables / total_tables * 100, 1) if total_tables > 0 else 0.0
        active_policies = _safe_int(policy_df["ACTIVE_COUNT"].sum()) if not policy_df.empty else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Tables", f"{total_tables:,}")
        c2.metric("Tagged Tables", f"{tagged_tables:,}")
        coverage_delta = "⚠ Low coverage" if coverage_pct < 50 else None
        c3.metric("Tag Coverage", f"{coverage_pct}%", delta=coverage_delta, delta_color="normal" if coverage_pct >= 50 else "off")
        c4.metric("Active Policies", f"{active_policies:,}")

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("### Classification Source Breakdown")
            if not class_df.empty:
                filtered = class_df[class_df["TOTAL_TAGS"] > 0].copy()
                if not filtered.empty:
                    st.markdown("**Tag Application Method**")
                    fig = go.Figure(go.Pie(
                        labels=filtered["APPLY_METHOD"].tolist(),
                        values=filtered["TOTAL_TAGS"].astype(int).tolist(),
                        hole=0.4,
                        marker_colors=_C[:len(filtered)],
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
                    st.info("No classification data available.")
            else:
                st.info("No classification data available.")

        with col_right:
            st.markdown("### Active Policy Inventory")
            if not policy_df.empty:
                active = policy_df[policy_df["ACTIVE_COUNT"] > 0].copy()
                if not active.empty:
                    st.markdown("**Active Policies by Kind**")
                    fig = go.Figure(go.Bar(
                        x=active["POLICY_KIND"].tolist(),
                        y=active["ACTIVE_COUNT"].astype(int).tolist(),
                        marker_color=SECONDARY,
                        text=active["ACTIVE_COUNT"].astype(int).tolist(),
                        textposition="outside",
                    ))
                    fig.update_layout(
                        height=380, margin=dict(t=10, b=80, l=40, r=20),
                        xaxis_title="", yaxis_title="Active Count",
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No active policies found.")
            else:
                st.info("No policy data available.")

    except Exception as e:
        st.error(f"Error loading Overview: {e}")


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
            "Data Object Tagging & Classification",
            "Data Privacy & Protection",
            "Data Lineage & Quality (Lite)",
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
        st.error(f"Error loading Data Governance Overview: {e}")

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


def _cached_sql(cache_key, sql):
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        df = session.sql(sql).to_pandas()
    except Exception:
        df = pd.DataFrame()
    st.session_state[cache_key] = df
    return df


BRAND_PRIMARY = '#29B5E8'
BRAND_SECONDARY = '#11567F'
BRAND_ACCENT = '#E8A229'
BRAND_PRIMARY_DARK = '#0077B6'
COLOR_LIGHT = '#75C2D8'


def comp_network_policies(entry_actions=None):
    try:
        st.markdown("### Network Rules & Policies")

        with st.expander("Network Security Summary", expanded=True):
            _render_network_policy_summary()

        with st.expander("Network Policies Audit (Enforced vs. Dangling)", expanded=True):
            _render_network_policies_audit()

        with st.expander("Network Rules Audit (Attached vs. Unused)", expanded=True):
            _render_network_rules_audit()

        with st.expander("Dangling Policies Detail", expanded=True):
            _render_dangling_network_policies()

        with st.expander("User Network Policy Coverage", expanded=True):
            _render_user_network_policy_coverage()

    except Exception as e:
        st.error(f"Error loading Network Rules & Policies: {e}")


def _render_network_policy_summary():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'High-level overview of network security posture including policy enforcement levels and rule configuration.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        WITH policy_stats AS (
            SELECT COUNT(*) AS total_policies,
                   COUNT(CASE WHEN deleted IS NULL THEN 1 END) AS active_policies
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES
        ),
        enforcement_stats AS (
            SELECT
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'ACCOUNT' THEN policy_name END) AS account_level_policies,
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'USER' THEN policy_name END) AS user_level_policies,
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'INTEGRATION' THEN policy_name END) AS integration_policies,
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'USER' THEN ref_entity_name END) AS users_with_policies
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE policy_kind = 'NETWORK_POLICY'
        )
        SELECT
            ps.total_policies, ps.active_policies,
            es.account_level_policies, es.user_level_policies,
            es.integration_policies, es.users_with_policies,
            CASE
                WHEN es.account_level_policies > 0 THEN 'PROTECTED'
                WHEN es.user_level_policies > 0 THEN 'PARTIALLY_PROTECTED'
                ELSE 'UNPROTECTED'
            END AS account_protection_status
        FROM policy_stats ps CROSS JOIN enforcement_stats es
        """
        df = _cached_sql("ac_net_policy_summary", query)

        rules_df = st.session_state.get("ac_net_rules_summary", pd.DataFrame())

        if df.empty:
            st.info("No network policy data available.")
            return

        row = df.iloc[0]
        total_policies = int(row.get('TOTAL_POLICIES', 0))
        active_policies = int(row.get('ACTIVE_POLICIES', 0))
        acct_level = int(row.get('ACCOUNT_LEVEL_POLICIES', 0))
        user_level = int(row.get('USER_LEVEL_POLICIES', 0))
        integration = int(row.get('INTEGRATION_POLICIES', 0))
        users_covered = int(row.get('USERS_WITH_POLICIES', 0))
        status = str(row.get('ACCOUNT_PROTECTION_STATUS', 'UNKNOWN'))

        total_rules = 0
        active_rules = 0
        if not rules_df.empty:
            total_rules = int(rules_df.get('TOTAL_RULES', pd.Series([0])).iloc[0]) if 'TOTAL_RULES' in rules_df.columns else len(rules_df)
            active_rules = int(rules_df.get('ACTIVE_RULES', pd.Series([0])).iloc[0]) if 'ACTIVE_RULES' in rules_df.columns else 0
        else:
            nr_df = st.session_state.get("net_rules_data", pd.DataFrame())
            if not nr_df.empty:
                total_rules = len(nr_df)
                if 'USAGE_STATUS' in nr_df.columns:
                    active_rules = len(nr_df[nr_df['USAGE_STATUS'].str.contains('Attached', case=False, na=False)])

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Policies", total_policies)
        with c2:
            st.metric("Active Policies", active_policies)
        with c3:
            st.metric("Total Rules", total_rules)
        with c4:
            st.metric("Active Rules", active_rules)

        c5, c6, c7, c8 = st.columns(4)
        with c5:
            st.metric("Account-Level", acct_level)
        with c6:
            st.metric("User-Level", user_level)
        with c7:
            st.metric("Integration", integration)
        with c8:
            st.metric("Users Covered", users_covered)

        status_color = '#27AE60' if status == 'PROTECTED' else '#F39C12' if 'PARTIAL' in status else '#E74C3C'
        bg_color = '#EAF8F0' if status == 'PROTECTED' else '#fff3cd' if 'PARTIAL' in status else '#FDEDEC'
        st.markdown(
            f'<div style="background-color:{bg_color};border-left:6px solid {status_color};padding:10px;">'
            f'<b>Account Protection Status:</b> {status}</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Policies by Enforcement Level**")
            categories = ['Account-Level', 'User-Level', 'Integration']
            values = [acct_level, user_level, integration]
            fig = go.Figure(go.Bar(x=categories, y=values,
                                   marker_color=[BRAND_PRIMARY, BRAND_SECONDARY, BRAND_PRIMARY_DARK],
                                   text=values, textposition='outside'))
            fig.update_layout(height=320, margin=dict(t=30, b=60), yaxis_title='Policies')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**Network Rules by Direction**")
            nr_df = st.session_state.get("net_rules_data", pd.DataFrame())
            if not nr_df.empty:
                mode_col = 'RULE_MODE' if 'RULE_MODE' in nr_df.columns else 'Mode (Ingress/Egress)' if 'Mode (Ingress/Egress)' in nr_df.columns else None
                if mode_col:
                    mode_counts = nr_df.groupby(mode_col).size().reset_index(name='COUNT')
                    colors = [BRAND_PRIMARY if 'INGRESS' in str(m).upper() else BRAND_ACCENT for m in mode_counts[mode_col]]
                    fig = go.Figure(go.Bar(x=mode_counts[mode_col], y=mode_counts['COUNT'],
                                           marker_color=colors, text=mode_counts['COUNT'], textposition='outside'))
                    fig.update_layout(height=320, margin=dict(t=30, b=60), yaxis_title='Rules')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No rule direction data available.")
            else:
                st.info("No network rules data available.")
    except Exception as e:
        st.error(f"Error: {e}")


def _render_network_policies_audit():
    st.markdown("#### Network Policies Audit (Enforced vs. Dangling)")
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'Network policy inventory showing enforcement status, user attachments, and creation dates. '
        'Policies not attached to any account, user, or integration are marked as Dangling.</div>',
        unsafe_allow_html=True)
    try:
        df = st.session_state.get("ac_net_policy_audit", pd.DataFrame())
        if df.empty:
            network_policies_query = """
            SELECT
                np.name AS policy_name,
                np.owner,
                CASE
                    WHEN pu.applied_to_account > 0 THEN 'ENFORCED_ACCOUNT'
                    WHEN pu.applied_to_users > 0 THEN 'ENFORCED_USER'
                    WHEN pu.applied_to_integrations > 0 THEN 'ENFORCED_INTEGRATION'
                    ELSE 'DANGLING_NOT_ENFORCED'
                END AS enforcement_status,
                COALESCE(pu.applied_to_account, 0) AS account_attachments,
                COALESCE(pu.applied_to_users, 0) AS user_attachments,
                np.created AS created_date
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES np
            LEFT JOIN (
                SELECT policy_name,
                    COUNT(CASE WHEN ref_entity_domain = 'ACCOUNT' THEN 1 END) AS applied_to_account,
                    COUNT(CASE WHEN ref_entity_domain = 'USER' THEN 1 END) AS applied_to_users,
                    COUNT(CASE WHEN ref_entity_domain = 'INTEGRATION' THEN 1 END) AS applied_to_integrations
                FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
                WHERE policy_kind = 'NETWORK_POLICY'
                GROUP BY 1
            ) pu ON np.name = pu.policy_name
            WHERE np.deleted IS NULL
            ORDER BY enforcement_status
            """
            df = _cached_sql("ac_net_policy_audit", network_policies_query)

        if df.empty:
            st.warning("No network policies data found.")
            return

        status_col = 'ENFORCEMENT_STATUS' if 'ENFORCEMENT_STATUS' in df.columns else 'Status' if 'Status' in df.columns else None
        total = len(df)
        enforced = 0
        dangling = 0
        if status_col:
            enforced = len(df[~df[status_col].str.contains('DANGLING|Dangling', case=False, na=False)])
            dangling = total - enforced

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Policies", total)
        with c2:
            st.metric("Enforced Policies", enforced)
        with c3:
            delta = "Review" if dangling > 0 else None
            st.metric("Dangling Policies", dangling, delta=delta, delta_color="inverse" if dangling > 0 else "off")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Policy Enforcement Status**")
            if status_col:
                status_counts = df.groupby(status_col).size().reset_index(name='COUNT')
                colors = [BRAND_PRIMARY if 'ENFORCED' in str(s).upper() and 'NOT' not in str(s).upper() else BRAND_ACCENT
                          for s in status_counts[status_col]]
                fig = go.Figure(go.Pie(labels=status_counts[status_col], values=status_counts['COUNT'],
                                       hole=0.35, marker=dict(colors=colors)))
                fig.update_layout(height=320, margin=dict(t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**User Attachments per Policy**")
            attach_col = 'USER_ATTACHMENTS' if 'USER_ATTACHMENTS' in df.columns else 'User Attachments' if 'User Attachments' in df.columns else None
            name_col = 'POLICY_NAME' if 'POLICY_NAME' in df.columns else 'Policy Name' if 'Policy Name' in df.columns else None
            if attach_col and name_col:
                attach_df = df[[name_col, attach_col]].sort_values(attach_col, ascending=True)
                attach_df = attach_df[attach_df[attach_col] > 0] if not attach_df.empty else attach_df
                if not attach_df.empty:
                    fig = go.Figure(go.Bar(y=attach_df[name_col], x=attach_df[attach_col], orientation='h',
                                           marker_color=BRAND_PRIMARY,
                                           text=attach_df[attach_col], textposition='outside'))
                    fig.update_layout(height=320, margin=dict(t=30, l=180, r=40, b=40), xaxis_title='Users')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No policies with user attachments.")

        display_cols = [c for c in ['POLICY_NAME', 'OWNER', 'ENFORCEMENT_STATUS', 'ACCOUNT_ATTACHMENTS',
                                     'USER_ATTACHMENTS', 'CREATED_DATE'] if c in df.columns]
        if not display_cols:
            display_cols = [c for c in ['Policy Name', 'Status', 'Comment', 'User Attachments', 'Created Date'] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading Network Policies Audit: {e}")


def _render_network_rules_audit():
    st.markdown("#### Network Rules Audit (Attached vs. Unused)")
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'Network rules inventory showing mode, type, usage status, and reference count. '
        'Rules not attached to any policy are marked as Orphaned.</div>',
        unsafe_allow_html=True)
    try:
        df = st.session_state.get("net_rules_data", pd.DataFrame())
        if df.empty:
            network_rules_query = """
            WITH rule_usage AS (
                SELECT network_rule_name, COUNT(*) AS distinct_policies_using_rule
                FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULE_REFERENCES
                GROUP BY 1
            )
            SELECT
                nr.name AS rule_name,
                nr.database_name AS database,
                nr.schema_name AS schema,
                nr.mode AS rule_mode,
                nr.type AS rule_type,
                CASE WHEN ru.distinct_policies_using_rule > 0 THEN 'ATTACHED' ELSE 'ORPHANED' END AS usage_status,
                COALESCE(ru.distinct_policies_using_rule, 0) AS reference_count,
                nr.owner AS owned_by
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES nr
            LEFT JOIN rule_usage ru ON nr.name = ru.network_rule_name
            WHERE nr.deleted IS NULL
            ORDER BY usage_status ASC
            """
            df = _cached_sql("net_rules_data", network_rules_query)

        if df.empty:
            st.warning("No network rules data found.")
            return

        status_col = 'USAGE_STATUS' if 'USAGE_STATUS' in df.columns else 'Usage Status' if 'Usage Status' in df.columns else None
        total = len(df)
        attached = 0
        orphaned = 0
        if status_col:
            attached = len(df[df[status_col].str.contains('ATTACHED|Attached', case=False, na=False)])
            orphaned = total - attached

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Rules", total)
        with c2:
            st.metric("Attached Rules", attached)
        with c3:
            delta = "Review" if orphaned > 0 else None
            st.metric("Orphaned Rules", orphaned, delta=delta, delta_color="inverse" if orphaned > 0 else "off")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Rule Attachment Status**")
            if status_col:
                status_counts = df.groupby(status_col).size().reset_index(name='COUNT')
                colors = [BRAND_PRIMARY if 'ATTACHED' in str(s).upper() and 'ORPHAN' not in str(s).upper() else BRAND_ACCENT
                          for s in status_counts[status_col]]
                fig = go.Figure(go.Pie(labels=status_counts[status_col], values=status_counts['COUNT'],
                                       hole=0.35, marker=dict(colors=colors)))
                fig.update_layout(height=300, margin=dict(t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**Rules by Direction**")
            mode_col = 'RULE_MODE' if 'RULE_MODE' in df.columns else 'Mode (Ingress/Egress)' if 'Mode (Ingress/Egress)' in df.columns else None
            if mode_col:
                mode_counts = df.groupby(mode_col).size().reset_index(name='COUNT')
                colors = [BRAND_PRIMARY if 'INGRESS' in str(m).upper() else BRAND_ACCENT for m in mode_counts[mode_col]]
                fig = go.Figure(go.Bar(x=mode_counts[mode_col], y=mode_counts['COUNT'],
                                       marker_color=colors, text=mode_counts['COUNT'], textposition='outside'))
                fig.update_layout(height=300, margin=dict(t=30, b=60), yaxis_title='Rules')
                st.plotly_chart(fig, use_container_width=True)

        with col3:
            st.markdown("**Rules by Type**")
            type_col = 'RULE_TYPE' if 'RULE_TYPE' in df.columns else 'Type (IPV4/Host/Link)' if 'Type (IPV4/Host/Link)' in df.columns else None
            if type_col:
                type_counts = df.groupby(type_col).size().reset_index(name='COUNT').sort_values('COUNT', ascending=True)
                fig = go.Figure(go.Bar(y=type_counts[type_col], x=type_counts['COUNT'], orientation='h',
                                       marker_color=BRAND_SECONDARY,
                                       text=type_counts['COUNT'], textposition='outside'))
                fig.update_layout(height=300, margin=dict(t=30, l=120, r=40, b=40), xaxis_title='Count')
                st.plotly_chart(fig, use_container_width=True)

        display_cols = [c for c in ['RULE_NAME', 'DATABASE', 'SCHEMA', 'RULE_MODE', 'RULE_TYPE',
                                     'USAGE_STATUS', 'REFERENCE_COUNT', 'OWNED_BY'] if c in df.columns]
        if not display_cols:
            display_cols = [c for c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading Network Rules Audit: {e}")


def _render_dangling_network_policies():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'Policies that exist but are not attached to anything \u2014 stale if older than 30 days.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        WITH policy_usage AS (
            SELECT DISTINCT policy_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE policy_kind = 'NETWORK_POLICY'
        )
        SELECT
            np.name AS policy_name, np.owner, np.created AS created_date, np.comment,
            DATEDIFF('day', np.created, CURRENT_TIMESTAMP()) AS days_since_created,
            CASE WHEN DATEDIFF('day', np.created, CURRENT_TIMESTAMP()) > 30 THEN 'STALE_UNUSED' ELSE 'RECENTLY_CREATED' END AS age_status
        FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES np
        LEFT JOIN policy_usage pu ON np.name = pu.policy_name
        WHERE np.deleted IS NULL AND pu.policy_name IS NULL
        ORDER BY np.created DESC
        """
        df = _cached_sql("ac_dangling_net_policies", query)
        if df.empty:
            st.success("No dangling network policies found — all policies are attached.")
            return

        stale_count = 0
        recent_count = 0
        if 'AGE_STATUS' in df.columns:
            stale_count = len(df[df['AGE_STATUS'] == 'STALE_UNUSED'])
            recent_count = len(df[df['AGE_STATUS'] == 'RECENTLY_CREATED'])

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Stale Unused Policies", stale_count)
        with c2:
            st.metric("Recently Created (unused)", recent_count)
        display_cols = [c for c in ['POLICY_NAME', 'OWNER', 'CREATED_DATE', 'COMMENT'] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")


def _render_user_network_policy_coverage():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'Users that have specific network policies applied at the user level.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            pr.ref_entity_name AS user_name, pr.policy_name,
            np.comment AS policy_description
        FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES pr
        INNER JOIN SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES np
            ON pr.policy_name = np.name AND np.deleted IS NULL
        WHERE pr.policy_kind = 'NETWORK_POLICY' AND pr.ref_entity_domain = 'USER'
        ORDER BY pr.ref_entity_name
        """
        df = _cached_sql("ac_user_net_coverage", query)
        if df.empty:
            st.info("No user-level network policy assignments found.")
            return

        st.metric("Users with Network Policies", len(df))
        policy_counts = df.groupby('POLICY_NAME').size().reset_index(name='USER_COUNT').sort_values('USER_COUNT', ascending=False)
        colors = [BRAND_PRIMARY, BRAND_SECONDARY, COLOR_LIGHT, BRAND_ACCENT]
        fig = go.Figure(go.Bar(
            x=policy_counts['POLICY_NAME'], y=policy_counts['USER_COUNT'],
            marker_color=colors[:len(policy_counts)],
            text=policy_counts['USER_COUNT'], textposition='outside'))
        fig.update_layout(title='Users per Network Policy', yaxis_title='User Count',
                          height=340, margin=dict(t=50, b=80))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")

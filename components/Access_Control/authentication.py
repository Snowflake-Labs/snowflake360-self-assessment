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
SEV_COLORS = {'CRITICAL': '#F39C12', 'HIGH': '#E8A229', 'MODERATE': '#75C2D8', 'LOW': '#29B5E8', 'CLEAR': '#29B5E8'}


def comp_authentication(entry_actions=None):
    try:
        st.markdown("### Authentication")

        with st.expander("Authentication Activity & Failures", expanded=True):
            st.markdown("#### Authentication Activity & Failures")
            st.markdown(
                "Authentication activity analysis across client types, methods, and success/failure status "
                "for the last 30 days, including unique users and percentage of total logins.")
            _render_auth_activity_content()

        with st.expander("Authentication Failure Analysis", expanded=True):
            st.markdown("#### Authentication Failure Analysis")
            st.markdown(
                "Repeated failed login attempts with error detail, client type, and source IP — last 30 days.")
            _render_auth_failure_analysis()

        with st.expander("Credential Hygiene (MFA & Stale Keys)", expanded=True):
            st.markdown("#### Credential Hygiene (MFA & Stale Keys)")
            st.markdown(
                "Analysis of user authentication profiles focusing on MFA adoption, password-only accounts, "
                "and identification of stale keypair credentials.")
            _render_credential_hygiene_content()

        with st.expander("Policy Audit (Password & Session)", expanded=True):
            st.markdown("#### Policy Audit (Password & Session)")
            st.markdown(
                "Comprehensive audit of password and session security policies configured in the account.")
            _render_policy_audit_content()

        with st.expander("Provisioning Method (SCIM vs Manual)", expanded=True):
            st.markdown("#### Provisioning Method (SCIM vs Manual)")
            st.markdown(
                "Role provisioning analysis categorizing roles by owner and method.")
            _render_provisioning_method_content()

        with st.expander("Trust Center (Scanner Status)", expanded=True):
            st.markdown("#### Trust Center (Scanner Status)")
            _render_trust_center_scanner()

        with st.expander("Programmatic Access Token (PAT) Users", expanded=True):
            _render_pat_users()

    except Exception as e:
        st.error(f"Error loading Authentication: {e}")


def _render_auth_activity_content():
    try:
        df = st.session_state.get("authn_auth_activity", pd.DataFrame())
        if df.empty:
            st.info("No authentication activity data available for the last 30 days.")
            return

        total_attempts = int(df['LOGIN_ATTEMPTS'].sum()) if 'LOGIN_ATTEMPTS' in df.columns else 0
        unique_users = int(df['UNIQUE_USERS'].sum()) if 'UNIQUE_USERS' in df.columns else 0
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Login Attempts", f"{total_attempts:,}")
        with col2:
            st.metric("Unique Users", unique_users)
        with col3:
            failed = int(df[df['STATUS'] == 'Failed']['LOGIN_ATTEMPTS'].sum()) if 'STATUS' in df.columns else 0
            st.metric("Failed Attempts", f"{failed:,}")

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("**Login Attempts by Auth Method**")
            method_df = df.groupby('AUTH_METHOD')['LOGIN_ATTEMPTS'].sum().reset_index().sort_values('LOGIN_ATTEMPTS', ascending=False)
            fig = go.Figure(go.Bar(x=method_df['AUTH_METHOD'], y=method_df['LOGIN_ATTEMPTS'],
                                   marker_color=BRAND_PRIMARY, text=method_df['LOGIN_ATTEMPTS'], textposition='outside'))
            fig.update_layout(height=320, margin=dict(t=30, b=60), yaxis_title='Attempts')
            st.plotly_chart(fig, use_container_width=True)
        with chart_col2:
            st.markdown("**Login Attempts by Status**")
            status_df = df.groupby('STATUS')['LOGIN_ATTEMPTS'].sum().reset_index()
            fig = go.Figure(go.Pie(labels=status_df['STATUS'], values=status_df['LOGIN_ATTEMPTS'],
                                   hole=0.35, marker=dict(colors=[BRAND_PRIMARY, BRAND_ACCENT])))
            fig.update_layout(height=320, margin=dict(t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

        chart_col3, chart_col4 = st.columns(2)
        with chart_col3:
            st.markdown("**Top Client Types**")
            client_df = df.groupby('CLIENT_TYPE')['LOGIN_ATTEMPTS'].sum().reset_index().sort_values('LOGIN_ATTEMPTS', ascending=True).tail(10)
            fig = go.Figure(go.Bar(y=client_df['CLIENT_TYPE'], x=client_df['LOGIN_ATTEMPTS'], orientation='h',
                                   marker_color=BRAND_SECONDARY, text=client_df['LOGIN_ATTEMPTS'], textposition='outside'))
            fig.update_layout(height=320, margin=dict(t=30, l=160, r=40, b=40), xaxis_title='Attempts')
            st.plotly_chart(fig, use_container_width=True)
        with chart_col4:
            st.markdown("**Unique IPs by Auth Method**")
            ip_df = df.groupby('AUTH_METHOD')['UNIQUE_IPS'].sum().reset_index().sort_values('UNIQUE_IPS', ascending=False)
            fig = go.Figure(go.Bar(x=ip_df['AUTH_METHOD'], y=ip_df['UNIQUE_IPS'],
                                   marker_color=BRAND_PRIMARY_DARK, text=ip_df['UNIQUE_IPS'], textposition='outside'))
            fig.update_layout(height=320, margin=dict(t=30, b=60), yaxis_title='Unique IPs')
            st.plotly_chart(fig, use_container_width=True)

        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading authentication activity: {e}")


def _render_auth_failure_analysis():
    try:
        df = st.session_state.get("authn_failure_analysis", pd.DataFrame())
        if df.empty:
            st.success("No repeated authentication failures detected in the last 30 days.")
            return

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Repeated Failure Rows", len(df))
        with col2:
            distinct_users = df['USER_NAME'].nunique() if 'USER_NAME' in df.columns else 0
            st.metric("Distinct Users", distinct_users)
        with col3:
            crit_high = 0
            if 'SEVERITY' in df.columns:
                crit_high = len(df[df['SEVERITY'].isin(['CRITICAL', 'HIGH'])])
            st.metric("Critical/High", crit_high)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("**Failure Volume by Severity**")
            if 'SEVERITY' in df.columns:
                sev_df = df.groupby('SEVERITY').size().reset_index(name='COUNT')
                colors = [SEV_COLORS.get(s, BRAND_PRIMARY) for s in sev_df['SEVERITY']]
                fig = go.Figure(go.Bar(x=sev_df['SEVERITY'], y=sev_df['COUNT'],
                                       marker_color=colors, text=sev_df['COUNT'], textposition='outside'))
                fig.update_layout(height=320, margin=dict(t=30, b=60), yaxis_title='Count')
                st.plotly_chart(fig, use_container_width=True)
        with chart_col2:
            st.markdown("**Top Users by Repeated Failures**")
            if 'USER_NAME' in df.columns and 'FAILURE_COUNT' in df.columns:
                user_df = df.groupby('USER_NAME')['FAILURE_COUNT'].sum().reset_index().sort_values('FAILURE_COUNT', ascending=True).tail(10)
                fig = go.Figure(go.Bar(y=user_df['USER_NAME'], x=user_df['FAILURE_COUNT'], orientation='h',
                                       marker_color=BRAND_ACCENT, text=user_df['FAILURE_COUNT'], textposition='outside'))
                fig.update_layout(height=320, margin=dict(t=30, l=160, r=40, b=40), xaxis_title='Failure Count')
                st.plotly_chart(fig, use_container_width=True)

        display_cols = [c for c in ['USER_NAME', 'ERROR_CODE', 'ERROR_MESSAGE', 'CLIENT_TYPE', 'CLIENT_IP',
                                     'FAILURE_COUNT', 'FIRST_FAILURE', 'LAST_FAILURE'] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading failure analysis: {e}")


def _render_credential_hygiene_content():
    try:
        df = st.session_state.get("authn_credential_hygiene", pd.DataFrame())
        if df.empty:
            st.info("No credential hygiene data available.")
            return

        total_users = int(df['USER_COUNT'].sum()) if 'USER_COUNT' in df.columns else 0
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Users", total_users)
        with col2:
            inactive_kp = int(df['INACTIVE_KEYPAIR_USERS'].sum()) if 'INACTIVE_KEYPAIR_USERS' in df.columns else 0
            st.metric("Inactive Keypair Users", inactive_kp)
        with col3:
            pwd_only = int(df[df['AUTH_PROFILE'].str.contains('Password Only', case=False, na=False)]['USER_COUNT'].sum()) if 'AUTH_PROFILE' in df.columns else 0
            st.metric("Password Only Users", pwd_only)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("**User Distribution by Auth Profile**")
            fig = go.Figure(go.Pie(labels=df['AUTH_PROFILE'], values=df['USER_COUNT'],
                                   hole=0.35, marker=dict(colors=[BRAND_PRIMARY, BRAND_ACCENT, BRAND_PRIMARY_DARK, COLOR_LIGHT])))
            fig.update_layout(height=320, margin=dict(t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)
        with chart_col2:
            st.markdown("**Inactive Keypair Users by Auth Profile**")
            inactive_df = df[df['INACTIVE_KEYPAIR_USERS'] > 0] if 'INACTIVE_KEYPAIR_USERS' in df.columns else pd.DataFrame()
            if not inactive_df.empty:
                inactive_df = inactive_df.sort_values('INACTIVE_KEYPAIR_USERS', ascending=True)
                fig = go.Figure(go.Bar(y=inactive_df['AUTH_PROFILE'], x=inactive_df['INACTIVE_KEYPAIR_USERS'],
                                       orientation='h', marker_color=BRAND_ACCENT,
                                       text=inactive_df['INACTIVE_KEYPAIR_USERS'], textposition='outside'))
                fig.update_layout(height=320, margin=dict(t=30, l=160, r=40, b=40), xaxis_title='Inactive Users')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("No inactive keypair users detected.")

        display_cols = [c for c in ['AUTH_PROFILE', 'USER_COUNT', 'INACTIVE_KEYPAIR_USERS', 'PCT_OF_USERS',
                                     'RISK_LEVEL', 'RECOMMENDATION'] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading credential hygiene data: {e}")


def _render_policy_audit_content():
    try:
        pwd_df = st.session_state.get("authn_password_policies", pd.DataFrame())
        sess_df = st.session_state.get("authn_session_policies", pd.DataFrame())

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Password Policies", len(pwd_df))
        with col2:
            st.metric("Session Policies", len(sess_df))

        if not pwd_df.empty:
            st.markdown("**Password Policies**")
            pwd_cols = [c for c in ['POLICY_NAME', 'DATABASE', 'SCHEMA', 'PASSWORD_MAX_AGE_DAYS',
                                     'PASSWORD_MIN_LENGTH', 'PASSWORD_MAX_RETRIES', 'PASSWORD_LOCKOUT_TIME_MINS',
                                     'PASSWORD_HISTORY', 'COMMENT', 'PASSWORD_AGE_RATING'] if c in pwd_df.columns]
            st.dataframe(pwd_df[pwd_cols] if pwd_cols else pwd_df, use_container_width=True)
        else:
            st.info("No password policies configured.")

        if not sess_df.empty:
            st.markdown("**Session Policies**")
            sess_cols = [c for c in ['POLICY_NAME', 'DATABASE', 'SCHEMA', 'SESSION_IDLE_TIMEOUT_MINS',
                                      'SESSION_UI_IDLE_TIMEOUT_MINS', 'COMMENT', 'TIMEOUT_RATING',
                                      'RECOMMENDATION'] if c in sess_df.columns]
            st.dataframe(sess_df[sess_cols] if sess_cols else sess_df, use_container_width=True)
        else:
            st.info("No session policies configured.")
    except Exception as e:
        st.error(f"Error loading policy audit data: {e}")


def _render_provisioning_method_content():
    try:
        df = st.session_state.get("authn_provisioning_method", pd.DataFrame())
        if df.empty:
            st.info("No role provisioning data available.")
            return

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("**Role Provisioning Method**")
            if 'PROVISIONING_METHOD' in df.columns and 'ROLE_COUNT' in df.columns:
                method_df = df.groupby('PROVISIONING_METHOD')['ROLE_COUNT'].sum().reset_index()
                fig = go.Figure(go.Pie(labels=method_df['PROVISIONING_METHOD'], values=method_df['ROLE_COUNT'],
                                       hole=0.35, marker=dict(colors=[BRAND_PRIMARY, BRAND_ACCENT, BRAND_PRIMARY_DARK])))
                fig.update_layout(height=320, margin=dict(t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            st.markdown("**Role Count by Owner**")
            if 'PROVISIONED_BY_ROLE' in df.columns and 'ROLE_COUNT' in df.columns:
                total = df['ROLE_COUNT'].sum()
                display_df = df[['PROVISIONED_BY_ROLE', 'PROVISIONING_METHOD', 'ROLE_COUNT']].copy()
                display_df['PCT'] = (display_df['ROLE_COUNT'] / total * 100).round(1).astype(str) + '%'
                display_df.columns = ['Owner Role', 'Method', 'Roles', '%']
                st.dataframe(display_df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading provisioning method data: {e}")


def _render_trust_center_scanner():
    try:
        df = st.session_state.get("authn_findings", pd.DataFrame())
        if df.empty:
            st.success("No Trust Center findings data available.")
            return

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Scanner Packages", len(df))
        with col2:
            open_f = int(df['OPEN_FINDINGS'].sum()) if 'OPEN_FINDINGS' in df.columns else 0
            st.metric("Open Findings", open_f)
        with col3:
            resolved_f = int(df['RESOLVED_FINDINGS'].sum()) if 'RESOLVED_FINDINGS' in df.columns else 0
            st.metric("Resolved Findings", resolved_f)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("**Open Findings by Scanner Package**")
            if 'SCANNER_PACKAGE' in df.columns and 'OPEN_FINDINGS' in df.columns:
                pkg_df = df[['SCANNER_PACKAGE', 'OPEN_FINDINGS']].sort_values('OPEN_FINDINGS', ascending=True)
                fig = go.Figure(go.Bar(y=pkg_df['SCANNER_PACKAGE'], x=pkg_df['OPEN_FINDINGS'], orientation='h',
                                       marker_color=BRAND_SECONDARY, text=pkg_df['OPEN_FINDINGS'], textposition='outside'))
                fig.update_layout(height=320, margin=dict(t=30, l=200, r=40, b=40), xaxis_title='Open Findings')
                st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            st.markdown("**Scanner Package Severity Distribution**")
            if 'FINDINGS_SEVERITY' in df.columns:
                sev_counts = df['FINDINGS_SEVERITY'].value_counts().reset_index()
                sev_counts.columns = ['SEVERITY', 'COUNT']
                colors = [SEV_COLORS.get(s, BRAND_PRIMARY) for s in sev_counts['SEVERITY']]
                fig = go.Figure(go.Pie(labels=sev_counts['SEVERITY'], values=sev_counts['COUNT'],
                                       hole=0.35, marker=dict(colors=colors)))
                fig.update_layout(height=320, margin=dict(t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)
            elif 'SCAN_FRESHNESS' in df.columns:
                fresh_counts = df['SCAN_FRESHNESS'].value_counts().reset_index()
                fresh_counts.columns = ['STATUS', 'COUNT']
                fig = go.Figure(go.Pie(labels=fresh_counts['STATUS'], values=fresh_counts['COUNT'],
                                       hole=0.35, marker=dict(colors=[BRAND_PRIMARY, BRAND_ACCENT])))
                fig.update_layout(height=320, margin=dict(t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)

        display_cols = [c for c in ['SCANNER_PACKAGE', 'LAST_SCAN_RUN', 'HOURS_SINCE_LAST_SCAN', 'TOTAL_FINDINGS',
                                     'OPEN_FINDINGS', 'RESOLVED_FINDINGS', 'SUPPRESSED_FINDINGS', 'PCT_OPEN',
                                     'FINDINGS_SEVERITY', 'SCAN_FRESHNESS'] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading Trust Center data: {e}")


def _render_pat_users():
    try:
        df = st.session_state.get("ac_pat_users", pd.DataFrame())
        if df.empty:
            st.info("No users with Programmatic Access Tokens found.")
            return

        active = len(df[df['ACTIVITY_STATUS'] == 'ACTIVE']) if 'ACTIVITY_STATUS' in df.columns else 0
        inactive = len(df[df['ACTIVITY_STATUS'] == 'INACTIVE']) if 'ACTIVITY_STATUS' in df.columns else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("PAT Users", len(df))
        with col2:
            st.metric("Active PAT Users (90d)", active)
        with col3:
            st.metric("Inactive PAT Users", inactive)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("**PAT User Activity Status**")
            if 'ACTIVITY_STATUS' in df.columns:
                status_counts = df.groupby('ACTIVITY_STATUS').size().reset_index(name='COUNT')
                fig = go.Figure(go.Pie(labels=status_counts['ACTIVITY_STATUS'], values=status_counts['COUNT'],
                                       hole=0.3, marker=dict(colors=[BRAND_PRIMARY, BRAND_ACCENT]),
                                       textinfo='label+value'))
                fig.update_layout(height=320, margin=dict(t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            st.markdown("**PAT Users by User Type**")
            if 'USER_TYPE' in df.columns:
                type_counts = df.groupby('USER_TYPE').size().reset_index(name='COUNT').sort_values('COUNT', ascending=False)
                colors = [BRAND_PRIMARY, BRAND_ACCENT, BRAND_PRIMARY_DARK, COLOR_LIGHT]
                fig = go.Figure(go.Bar(x=type_counts['USER_TYPE'], y=type_counts['COUNT'],
                                       marker_color=colors[:len(type_counts)],
                                       text=type_counts['COUNT'], textposition='outside'))
                fig.update_layout(height=320, margin=dict(t=30, b=60), yaxis_title='Count')
                st.plotly_chart(fig, use_container_width=True)

        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading PAT users: {e}")

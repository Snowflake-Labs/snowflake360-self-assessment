"""
Authentication Component

Provides authentication analysis including authentication activity,
credential hygiene, policy audit, and provisioning methods.
"""

import streamlit as st
import pandas as pd
try:
    from streamlit_echarts import st_echarts
except ImportError:
    def st_echarts(**kwargs):
        import streamlit as st
        st.info("Chart unavailable (echarts not supported in SiS)")


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
import plotly.graph_objects as go


def comp_authentication(entry_actions=None):
    """
    Authentication Component

    Provides expanders for:
    - Authentication Overview
    - Authentication Analyzer
    - Authentication Activity & Failures
    - Credential Hygiene (MFA & Stale Keys)
    - Policy Audit (Password & Session)
    - Provisioning Method (SCIM vs Manual)
    - Trust Center (Scanner Status)

    Args:
        entry_actions: Optional callback actions on component entry
    """
    try:
        st.markdown("### Authentication")

        with st.expander("Authentication Activity & Failures", expanded=True):
            st.markdown("#### Authentication Activity & Failures")

            st.markdown("""
            Authentication activity analysis across client types, methods, and success/failure status
            for the last 30 days, aggregated by login volume and unique IP addresses.
            """)

            _render_auth_activity_content()

        with st.expander("Credential Hygiene (MFA & Stale Keys)", expanded=True):
            st.markdown("#### Credential Hygiene (MFA & Stale Keys)")

            st.markdown("""
            Analysis of user authentication profiles focusing on MFA adoption, password-only accounts,
            and identification of stale keypair credentials. Users with keypairs who haven't logged in
            for 180+ days are flagged as potentially abandoned credentials requiring review.
            """)

            _render_credential_hygiene_content()

        with st.expander("Policy Audit (Password & Session)", expanded=True):
            st.markdown("#### Policy Audit (Password & Session)")

            st.markdown("""
            Comprehensive audit of password and session security policies configured in the account.
            Password policies define credential complexity, expiration, and lockout rules. Session policies
            control idle timeout durations for both API and UI sessions to minimize unauthorized access risks.
            """)

            _render_policy_audit_content()

        with st.expander("Provisioning Method (SCIM vs Manual)", expanded=True):
            st.markdown("#### Provisioning Method (SCIM vs Manual)")

            st.markdown("""
            Role provisioning analysis categorizing roles by owner and method (automated SCIM vs manual admin vs custom),
            with counts ordered by provisioning method.
            """)

            _render_provisioning_method_content()

        with st.expander("Trust Center (Scanner Status)", expanded=True):
            st.markdown("#### Trust Center (Scanner Status)")
            _render_trust_center_scanner()

        with st.expander("Programmatic Access Token (PAT) Users", expanded=True):
            _render_pat_users()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Authentication: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_auth_activity_content():
    """Render Authentication Activity & Failures content with table and charts."""
    try:
        auth_activity_query = """
SELECT
    first_authentication_factor AS auth_method,
    CASE WHEN is_success = 'YES' THEN 'Success' ELSE 'Failed' END AS status,
    reported_client_type AS client_type,
    COUNT(*) AS login_attempts,
    COUNT(DISTINCT client_ip) AS unique_ips,
    MIN(event_timestamp) AS first_seen,
    MAX(event_timestamp) AS last_seen
FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
WHERE event_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY ALL
ORDER BY login_attempts DESC
"""

        auth_activity_df = _cached_sql("authn_auth_activity", auth_activity_query)

        if not auth_activity_df.empty:
            st.dataframe(
                auth_activity_df,
                use_container_width=True
            )

            st.markdown("---")
            st.markdown("##### Authentication Activity Visualizations")

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container():
                st.markdown("**Login Attempts by Auth Method**")
                _render_auth_method_chart(auth_activity_df, key_prefix="auth_method_")

            with chart_col2.container():
                st.markdown("**Login Attempts by Status**")
                _render_status_chart(auth_activity_df, key_prefix="status_")

            chart_col3, chart_col4 = st.columns(2)

            with chart_col3.container():
                st.markdown("**Login Attempts by Client Type**")
                _render_client_type_chart(auth_activity_df, key_prefix="client_type_")

            with chart_col4.container():
                st.markdown("**Unique IPs by Auth Method**")
                _render_unique_ips_chart(auth_activity_df, key_prefix="unique_ips_")

        else:
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No authentication activity data available for the last 30 days.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading authentication activity: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_credential_hygiene_content():
    """Render Credential Hygiene (MFA & Stale Keys) content with table and charts."""
    try:
        credential_hygiene_query = """
SELECT
    CASE
        WHEN has_password = 'YES' AND ext_authn_duo = 'TRUE' THEN 'Password + MFA (Secure)'
        WHEN has_password = 'YES' AND ext_authn_duo = 'FALSE' THEN 'Password Only (Risky)'
        WHEN has_rsa_public_key = 'YES' THEN 'Keypair User'
        ELSE 'SSO/Federated'
    END AS auth_profile,
    COUNT(*) AS user_count,
    COUNT(CASE
        WHEN has_rsa_public_key = 'YES'
             AND (last_success_login < DATEADD('day', -180, CURRENT_TIMESTAMP()) OR last_success_login IS NULL)
        THEN 1
    END) AS inactive_keypair_users
FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
WHERE deleted_on IS NULL
GROUP BY ALL
"""

        credential_hygiene_df = _cached_sql("authn_credential_hygiene", credential_hygiene_query)

        if not credential_hygiene_df.empty:
            st.dataframe(
                credential_hygiene_df,
                use_container_width=True
            )

            st.markdown("---")
            st.markdown("##### Credential Hygiene Visualizations")

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container():
                st.markdown("**User Distribution by Auth Profile**")
                _render_auth_profile_chart(credential_hygiene_df, key_prefix="auth_profile_")

            with chart_col2.container():
                st.markdown("**Inactive Keypair Users by Auth Profile**")
                _render_inactive_keypair_chart(credential_hygiene_df, key_prefix="inactive_keypair_")

        else:
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No credential hygiene data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading credential hygiene data: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_policy_audit_content():
    """Render Policy Audit (Password & Session) content with table and charts."""
    try:
        policy_audit_query = """
SELECT
    'Password Policy' AS policy_type,
    name AS policy_name,
    password_max_age_days AS max_age,
    password_min_length AS min_length,
    password_max_retries AS max_retries,
    comment
FROM SNOWFLAKE.ACCOUNT_USAGE.PASSWORD_POLICIES
WHERE deleted IS NULL

UNION ALL

SELECT
    'Session Policy',
    name,
    session_idle_timeout_mins,
    session_ui_idle_timeout_mins,
    NULL,
    comment
FROM SNOWFLAKE.ACCOUNT_USAGE.SESSION_POLICIES
WHERE deleted IS NULL
"""

        policy_audit_df = _cached_sql("authn_policy_audit", policy_audit_query)

        if not policy_audit_df.empty:
            st.dataframe(
                policy_audit_df,
                use_container_width=True
            )

            st.markdown("---")
            st.markdown("##### Policy Configuration Visualizations")

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container():
                st.markdown("**Policy Count by Type**")
                _render_policy_type_chart(policy_audit_df, key_prefix="policy_type_")

            with chart_col2.container():
                st.markdown("**Password Policy Settings Comparison**")
                _render_password_policy_settings_chart(policy_audit_df, key_prefix="pwd_policy_settings_")

        else:
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No password or session policies configured in this account.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading policy audit data: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_provisioning_method_content():
    """Render Provisioning Method (SCIM vs Manual) content with table and charts."""
    try:
        provisioning_method_query = """
SELECT
    owner AS provisioned_by_role,
    CASE
        WHEN owner LIKE '%SCIM%' OR owner LIKE '%PROVISION%' THEN 'Automated (SCIM)'
        WHEN owner IN ('USERADMIN', 'SECURITYADMIN', 'ACCOUNTADMIN') THEN 'Manual (Admin)'
        ELSE 'Custom/Other'
    END AS provisioning_method,
    COUNT(*) AS role_count
FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES
WHERE deleted_on IS NULL
GROUP BY ALL
ORDER BY role_count DESC
"""

        provisioning_method_df = _cached_sql("authn_provisioning_method", provisioning_method_query)

        if not provisioning_method_df.empty:
            st.dataframe(
                provisioning_method_df,
                use_container_width=True
            )

            st.markdown("---")
            st.markdown("##### Provisioning Method Visualizations")

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container():
                st.markdown("**Role Distribution by Provisioning Method**")
                _render_provisioning_method_chart(provisioning_method_df, key_prefix="prov_method_")

            with chart_col2.container():
                st.markdown("**Role Count by Owner Role (Top 10)**")
                _render_owner_role_chart(provisioning_method_df, key_prefix="owner_role_")

        else:
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No role provisioning data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading provisioning method data: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ============================================================================
# Chart Rendering Functions for Authentication Activity
# ============================================================================

def _render_auth_method_chart(df, key_prefix=""):
    """Render Login Attempts by Auth Method chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    auth_method_df = df.groupby('AUTH_METHOD').agg({
        'LOGIN_ATTEMPTS': 'sum'
    }).reset_index().sort_values('LOGIN_ATTEMPTS', ascending=False)

    if auth_method_df.empty:
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_generic_bar_chart(auth_method_df, 'AUTH_METHOD', 'LOGIN_ATTEMPTS', 'Login Attempts', key_prefix)
    elif chart_type == "Pie Chart":
        _render_generic_pie_chart(auth_method_df, 'AUTH_METHOD', 'LOGIN_ATTEMPTS', 'login attempts', key_prefix, donut=False)
    elif chart_type == "Pie - Donut":
        _render_generic_pie_chart(auth_method_df, 'AUTH_METHOD', 'LOGIN_ATTEMPTS', 'login attempts', key_prefix, donut=True)
    else:
        _render_generic_rose_chart(auth_method_df, 'AUTH_METHOD', 'LOGIN_ATTEMPTS', 'login attempts', key_prefix)


def _render_status_chart(df, key_prefix=""):
    """Render Login Attempts by Status chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    status_df = df.groupby('STATUS').agg({
        'LOGIN_ATTEMPTS': 'sum'
    }).reset_index().sort_values('LOGIN_ATTEMPTS', ascending=False)

    if status_df.empty:
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_generic_bar_chart(status_df, 'STATUS', 'LOGIN_ATTEMPTS', 'Login Attempts', key_prefix)
    elif chart_type == "Pie Chart":
        _render_generic_pie_chart(status_df, 'STATUS', 'LOGIN_ATTEMPTS', 'login attempts', key_prefix, donut=False)
    elif chart_type == "Pie - Donut":
        _render_generic_pie_chart(status_df, 'STATUS', 'LOGIN_ATTEMPTS', 'login attempts', key_prefix, donut=True)
    else:
        _render_generic_rose_chart(status_df, 'STATUS', 'LOGIN_ATTEMPTS', 'login attempts', key_prefix)


def _render_client_type_chart(df, key_prefix=""):
    """Render Login Attempts by Client Type chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    client_type_df = df.groupby('CLIENT_TYPE').agg({
        'LOGIN_ATTEMPTS': 'sum'
    }).reset_index().sort_values('LOGIN_ATTEMPTS', ascending=False)

    if client_type_df.empty:
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_generic_bar_chart(client_type_df, 'CLIENT_TYPE', 'LOGIN_ATTEMPTS', 'Login Attempts', key_prefix)
    elif chart_type == "Pie Chart":
        _render_generic_pie_chart(client_type_df, 'CLIENT_TYPE', 'LOGIN_ATTEMPTS', 'login attempts', key_prefix, donut=False)
    elif chart_type == "Pie - Donut":
        _render_generic_pie_chart(client_type_df, 'CLIENT_TYPE', 'LOGIN_ATTEMPTS', 'login attempts', key_prefix, donut=True)
    else:
        _render_generic_rose_chart(client_type_df, 'CLIENT_TYPE', 'LOGIN_ATTEMPTS', 'login attempts', key_prefix)


def _render_unique_ips_chart(df, key_prefix=""):
    """Render Unique IPs by Auth Method chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    unique_ips_df = df.groupby('AUTH_METHOD').agg({
        'UNIQUE_IPS': 'sum'
    }).reset_index().sort_values('UNIQUE_IPS', ascending=False)

    if unique_ips_df.empty:
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_generic_bar_chart(unique_ips_df, 'AUTH_METHOD', 'UNIQUE_IPS', 'Unique IPs', key_prefix)
    elif chart_type == "Pie Chart":
        _render_generic_pie_chart(unique_ips_df, 'AUTH_METHOD', 'UNIQUE_IPS', 'unique IPs', key_prefix, donut=False)
    elif chart_type == "Pie - Donut":
        _render_generic_pie_chart(unique_ips_df, 'AUTH_METHOD', 'UNIQUE_IPS', 'unique IPs', key_prefix, donut=True)
    else:
        _render_generic_rose_chart(unique_ips_df, 'AUTH_METHOD', 'UNIQUE_IPS', 'unique IPs', key_prefix)


# ============================================================================
# Chart Rendering Functions for Credential Hygiene
# ============================================================================

def _render_auth_profile_chart(df, key_prefix=""):
    """Render User Distribution by Auth Profile chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    auth_profile_df = df[['AUTH_PROFILE', 'USER_COUNT']].copy()
    auth_profile_df = auth_profile_df.sort_values('USER_COUNT', ascending=False)

    if auth_profile_df.empty:
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_generic_bar_chart(auth_profile_df, 'AUTH_PROFILE', 'USER_COUNT', 'User Count', key_prefix)
    elif chart_type == "Pie Chart":
        _render_generic_pie_chart(auth_profile_df, 'AUTH_PROFILE', 'USER_COUNT', 'users', key_prefix, donut=False)
    elif chart_type == "Pie - Donut":
        _render_generic_pie_chart(auth_profile_df, 'AUTH_PROFILE', 'USER_COUNT', 'users', key_prefix, donut=True)
    else:
        _render_generic_rose_chart(auth_profile_df, 'AUTH_PROFILE', 'USER_COUNT', 'users', key_prefix)


def _render_inactive_keypair_chart(df, key_prefix=""):
    """Render Inactive Keypair Users by Auth Profile chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    inactive_df = df[df['INACTIVE_KEYPAIR_USERS'] > 0][['AUTH_PROFILE', 'INACTIVE_KEYPAIR_USERS']].copy()
    inactive_df = inactive_df.sort_values('INACTIVE_KEYPAIR_USERS', ascending=False)

    if inactive_df.empty:
        st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    '✅&nbsp;&nbsp;No inactive keypair users detected - all keypair credentials are active.'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_generic_bar_chart(inactive_df, 'AUTH_PROFILE', 'INACTIVE_KEYPAIR_USERS', 'Inactive Users', key_prefix)
    elif chart_type == "Pie Chart":
        _render_generic_pie_chart(inactive_df, 'AUTH_PROFILE', 'INACTIVE_KEYPAIR_USERS', 'inactive users', key_prefix, donut=False)
    elif chart_type == "Pie - Donut":
        _render_generic_pie_chart(inactive_df, 'AUTH_PROFILE', 'INACTIVE_KEYPAIR_USERS', 'inactive users', key_prefix, donut=True)
    else:
        _render_generic_rose_chart(inactive_df, 'AUTH_PROFILE', 'INACTIVE_KEYPAIR_USERS', 'inactive users', key_prefix)


# ============================================================================
# Chart Rendering Functions for Policy Audit
# ============================================================================

def _render_policy_type_chart(df, key_prefix=""):
    """Render Policy Count by Type chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    policy_type_df = df.groupby('POLICY_TYPE').size().reset_index(name='POLICY_COUNT')
    policy_type_df = policy_type_df.sort_values('POLICY_COUNT', ascending=False)

    if policy_type_df.empty:
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_generic_bar_chart(policy_type_df, 'POLICY_TYPE', 'POLICY_COUNT', 'Policy Count', key_prefix)
    elif chart_type == "Pie Chart":
        _render_generic_pie_chart(policy_type_df, 'POLICY_TYPE', 'POLICY_COUNT', 'policies', key_prefix, donut=False)
    elif chart_type == "Pie - Donut":
        _render_generic_pie_chart(policy_type_df, 'POLICY_TYPE', 'POLICY_COUNT', 'policies', key_prefix, donut=True)
    else:
        _render_generic_rose_chart(policy_type_df, 'POLICY_TYPE', 'POLICY_COUNT', 'policies', key_prefix)


def _render_password_policy_settings_chart(df, key_prefix=""):
    """Render Password Policy Settings Comparison chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    password_policies_df = df[df['POLICY_TYPE'] == 'Password Policy'].copy()

    if password_policies_df.empty:
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No password policies configured - only session policies exist.'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        chart_df = password_policies_df[['POLICY_NAME', 'MAX_AGE']].copy()
        chart_df['MAX_AGE'] = chart_df['MAX_AGE'].fillna(0).astype(int)
        chart_df = chart_df.sort_values('MAX_AGE', ascending=False)
        _render_generic_bar_chart(chart_df, 'POLICY_NAME', 'MAX_AGE', 'Max Age (Days)', key_prefix)
    else:
        chart_df = password_policies_df[['POLICY_NAME', 'MIN_LENGTH']].copy()
        chart_df['MIN_LENGTH'] = chart_df['MIN_LENGTH'].fillna(0).astype(int)
        chart_df = chart_df.sort_values('MIN_LENGTH', ascending=False)

        if chart_type == "Pie Chart":
            _render_generic_pie_chart(chart_df, 'POLICY_NAME', 'MIN_LENGTH', 'min length', key_prefix, donut=False)
        elif chart_type == "Pie - Donut":
            _render_generic_pie_chart(chart_df, 'POLICY_NAME', 'MIN_LENGTH', 'min length', key_prefix, donut=True)
        else:
            _render_generic_rose_chart(chart_df, 'POLICY_NAME', 'MIN_LENGTH', 'min length', key_prefix)


# ============================================================================
# Chart Rendering Functions for Provisioning Method
# ============================================================================

def _render_provisioning_method_chart(df, key_prefix=""):
    """Render Role Distribution by Provisioning Method chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    prov_method_df = df.groupby('PROVISIONING_METHOD').agg({
        'ROLE_COUNT': 'sum'
    }).reset_index().sort_values('ROLE_COUNT', ascending=False)

    if prov_method_df.empty:
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_generic_bar_chart(prov_method_df, 'PROVISIONING_METHOD', 'ROLE_COUNT', 'Role Count', key_prefix)
    elif chart_type == "Pie Chart":
        _render_generic_pie_chart(prov_method_df, 'PROVISIONING_METHOD', 'ROLE_COUNT', 'roles', key_prefix, donut=False)
    elif chart_type == "Pie - Donut":
        _render_generic_pie_chart(prov_method_df, 'PROVISIONING_METHOD', 'ROLE_COUNT', 'roles', key_prefix, donut=True)
    else:
        _render_generic_rose_chart(prov_method_df, 'PROVISIONING_METHOD', 'ROLE_COUNT', 'roles', key_prefix)


def _render_owner_role_chart(df, key_prefix=""):
    """Render Role Count by Owner Role chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    owner_role_df = df[['PROVISIONED_BY_ROLE', 'ROLE_COUNT']].copy()
    owner_role_df = owner_role_df.sort_values('ROLE_COUNT', ascending=False).head(10)

    if owner_role_df.empty:
        st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_generic_bar_chart(owner_role_df, 'PROVISIONED_BY_ROLE', 'ROLE_COUNT', 'Role Count', key_prefix)
    elif chart_type == "Pie Chart":
        _render_generic_pie_chart(owner_role_df, 'PROVISIONED_BY_ROLE', 'ROLE_COUNT', 'roles', key_prefix, donut=False)
    elif chart_type == "Pie - Donut":
        _render_generic_pie_chart(owner_role_df, 'PROVISIONED_BY_ROLE', 'ROLE_COUNT', 'roles', key_prefix, donut=True)
    else:
        _render_generic_rose_chart(owner_role_df, 'PROVISIONED_BY_ROLE', 'ROLE_COUNT', 'roles', key_prefix)


# ============================================================================
# Generic Chart Rendering Helper Functions
# ============================================================================

def _render_generic_bar_chart(df, category_col, value_col, value_label, key_prefix=""):
    """Render a generic bar chart using ECharts."""
    categories = df[category_col].tolist()
    values = [int(v) for v in df[value_col].tolist()]

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "formatter": "{b}: {c}"
        },
        "xAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {
                "rotate": 30,
                "fontSize": 10,
                "interval": 0
            }
        },
        "yAxis": {
            "type": "value",
            "name": value_label,
            "nameTextStyle": {"fontSize": 11}
        },
        "series": [
            {
                "name": value_label,
                "type": "bar",
                "data": values,
                "itemStyle": {"color": "#29B5E8"},
                "label": {
                    "show": True,
                    "position": "top",
                    "fontSize": 10
                }
            }
        ],
        "grid": {
            "left": "10%",
            "right": "10%",
            "bottom": "20%",
            "top": "15%"
        }
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}bar_chart")


def _render_generic_pie_chart(df, category_col, value_col, value_unit, key_prefix="", donut=False):
    """Render a generic pie or donut chart using ECharts."""
    chart_data = []
    for _, row in df.iterrows():
        chart_data.append({
            "value": int(row[value_col]),
            "name": f"{row[category_col]} ({int(row[value_col]):,})"
        })

    radius = ["30%", "70%"] if donut else ["0%", "70%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "type": "scroll",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": f"{{b}}: {{c}} {value_unit} ({{d}}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": value_unit.title(),
                "type": "pie",
                "radius": radius,
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    chart_key = f"{key_prefix}donut_chart" if donut else f"{key_prefix}pie_chart"
    st_echarts(options=option, height="350px", key=chart_key)


def _render_generic_rose_chart(df, category_col, value_col, value_unit, key_prefix=""):
    """Render a generic rose-type pie chart using ECharts."""
    chart_data = []
    for _, row in df.iterrows():
        chart_data.append({
            "value": int(row[value_col]),
            "name": f"{row[category_col]} ({int(row[value_col]):,})"
        })

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "type": "scroll",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": f"{{b}}: {{c}} {value_unit} ({{d}}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": value_unit.title(),
                "type": "pie",
                "radius": [20, 120],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


def _render_trust_center_scanner():
    import plotly.graph_objects as go
    import pandas as pd
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Snowflake Trust Center</b> continuously scans your account for security risks. '
        'This view shows the distribution of open findings by severity and scanner type, helping you '
        'prioritise remediation efforts.</div>', unsafe_allow_html=True)
    try:
        session = st.session_state.session
        findings_query = """
        SELECT
            SCANNER_NAME,
            FINDING_TYPE,
            SEVERITY,
            STATUS,
            COUNT(*) AS finding_count,
            MAX(DETECTED_AT) AS last_detected
        FROM SNOWFLAKE.ACCOUNT_USAGE.TRUST_CENTER_FINDINGS
        WHERE STATUS != 'RESOLVED'
        GROUP BY SCANNER_NAME, FINDING_TYPE, SEVERITY, STATUS
        ORDER BY
            CASE SEVERITY WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END,
            finding_count DESC
        """
        df = _cached_sql("authn_findings", findings_query)
        if df.empty:
            st.success("No open Trust Center findings — your account is clean!")
            return
        df['FINDING_COUNT'] = pd.to_numeric(df['FINDING_COUNT'], errors='coerce').fillna(0)
        sev_counts = df.groupby('SEVERITY')['FINDING_COUNT'].sum().reset_index()
        col1, col2, col3, col4 = st.columns(4)
        _sev_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        sev_counts = sev_counts.sort_values('SEVERITY', key=lambda x: x.map(_sev_order).fillna(99))
        _sev_colors = {'CRITICAL': '#E74C3C', 'HIGH': '#E8A229', 'MEDIUM': '#75C2D8', 'LOW': '#29B5E8'}
        with col1:
            critical = int(sev_counts[sev_counts['SEVERITY'] == 'CRITICAL']['FINDING_COUNT'].sum())
            st.metric("Critical", critical)
        with col2:
            high = int(sev_counts[sev_counts['SEVERITY'] == 'HIGH']['FINDING_COUNT'].sum())
            st.metric("High", high)
        with col3:
            medium = int(sev_counts[sev_counts['SEVERITY'] == 'MEDIUM']['FINDING_COUNT'].sum())
            st.metric("Medium", medium)
        with col4:
            low = int(sev_counts[sev_counts['SEVERITY'] == 'LOW']['FINDING_COUNT'].sum())
            st.metric("Low", low)
        col_a, col_b = st.columns(2)
        with col_a:
            fig_sev = go.Figure(go.Pie(
                labels=sev_counts['SEVERITY'],
                values=sev_counts['FINDING_COUNT'],
                hole=0.35,
                marker_colors=[_sev_colors.get(s, '#ADE8F4') for s in sev_counts['SEVERITY']]
            ))
            fig_sev.update_layout(title='Findings by Severity', height=320, margin=dict(t=50, b=20))
            st.plotly_chart(fig_sev, use_container_width=True)
        with col_b:
            scanner_counts = df.groupby('SCANNER_NAME')['FINDING_COUNT'].sum().reset_index().sort_values('FINDING_COUNT', ascending=True)
            fig_scanner = go.Figure(go.Bar(
                y=scanner_counts['SCANNER_NAME'], x=scanner_counts['FINDING_COUNT'],
                orientation='h', marker_color='#11567F',
                text=scanner_counts['FINDING_COUNT'], textposition='outside'
            ))
            fig_scanner.update_layout(
                title='Findings by Scanner', xaxis_title='Count',
                height=320, margin=dict(t=50, l=180, r=40, b=40)
            )
            st.plotly_chart(fig_scanner, use_container_width=True)
        st.markdown("**Open Trust Center Findings**")
        st.dataframe(df[['SCANNER_NAME', 'FINDING_TYPE', 'SEVERITY', 'STATUS', 'FINDING_COUNT', 'LAST_DETECTED']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_pat_users():
    import plotly.graph_objects as go
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>PAT Users:</b> Users with Programmatic Access Tokens enabled for API authentication.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            name AS user_name, type AS user_type, default_role, last_success_login,
            DATEDIFF('day', last_success_login, CURRENT_TIMESTAMP()) AS days_since_login,
            CASE
                WHEN last_success_login < DATEADD('day', -90, CURRENT_TIMESTAMP()) OR last_success_login IS NULL THEN 'INACTIVE'
                ELSE 'ACTIVE'
            END AS activity_status
        FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
        WHERE deleted_on IS NULL AND has_pat = 'true'
        ORDER BY last_success_login DESC NULLS LAST
        """
        df = _cached_sql("ac_pat_users", query)
        if df.empty:
            st.info("No users with Programmatic Access Tokens found.")
            return
        col1, col2 = st.columns(2)
        with col1:
            st.metric("PAT Users", len(df))
        with col2:
            active = len(df[df['ACTIVITY_STATUS'] == 'ACTIVE'])
            st.metric("Active PAT Users (90d)", active)
        status_counts = df.groupby('ACTIVITY_STATUS').size().reset_index(name='COUNT')
        fig = go.Figure(go.Pie(
            labels=status_counts['ACTIVITY_STATUS'], values=status_counts['COUNT'],
            hole=0.3, marker=dict(colors=['#29B5E8', '#E8A229']),
            textinfo='label+value'
        ))
        fig.update_layout(title='PAT Users Activity Status', height=320, margin=dict(t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

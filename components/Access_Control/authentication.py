import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = "#29B5E8"
_C2 = "#11567F"
_C3 = "#75C2D8"
_CA = "#E8A229"


def _get(key, sql):
    if key in st.session_state:
        return st.session_state[key]
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        df = session.sql(sql).to_pandas()
    except Exception:
        df = pd.DataFrame()
    st.session_state[key] = df
    return df


def _bar(x, y, colors, h=300, xlabel="", ylabel="Count", horizontal=False, key=""):
    if horizontal:
        fig = go.Figure(go.Bar(
            y=x, x=y, orientation="h",
            marker_color=colors if isinstance(colors, list) else [colors] * len(x),
            text=y, textposition="outside",
        ))
        fig.update_layout(height=h, xaxis_title=ylabel, yaxis_title=xlabel,
                          margin=dict(t=20, b=40, l=200, r=50), showlegend=False)
    else:
        fig = go.Figure(go.Bar(
            x=x, y=y,
            marker_color=colors if isinstance(colors, list) else [colors] * len(x),
            text=y, textposition="outside",
        ))
        fig.update_layout(height=h, xaxis_title=xlabel, yaxis_title=ylabel,
                          margin=dict(t=20, b=60, l=50, r=30), showlegend=False)
    if key:
        st.plotly_chart(fig, use_container_width=True, key=key)
    else:
        st.plotly_chart(fig, use_container_width=True)


def _donut(labels, values, colors, h=320, key=""):
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.45, marker_colors=colors,
        textinfo="percent", textposition="inside",
    ))
    fig.update_layout(height=h, margin=dict(t=20, b=20, l=20, r=20),
                      legend=dict(orientation="v", x=1.02, y=0.5))
    if key:
        st.plotly_chart(fig, use_container_width=True, key=key)
    else:
        st.plotly_chart(fig, use_container_width=True)


def comp_authentication(entry_actions=None):
    try:
        with st.expander("Authentication Activity & Failures", expanded=True):
            _render_auth_activity()

        with st.expander("Authentication Failure Analysis", expanded=True):
            _render_auth_failures()

        with st.expander("Credential Hygiene (MFA & Stale Keys)", expanded=True):
            _render_credential_hygiene()

        with st.expander("Policy Audit (Password & Session)", expanded=True):
            _render_policy_audit()

        with st.expander("Programmatic Access Tokens (PAT)", expanded=True):
            _render_pat_users()

        with st.expander("Provisioning Method (SCIM vs Manual)", expanded=True):
            _render_provisioning_method()

        with st.expander("Trust Center Security Findings", expanded=True):
            _render_trust_center()

    except Exception as e:
        st.error(f"Error loading Authentication: {e}")


def _render_auth_activity():
    st.caption("Login attempts by auth method, status, and client type — last 30 days.")
    sql = """
        SELECT
            first_authentication_factor AS auth_method,
            CASE WHEN is_success = 'YES' THEN 'Success' ELSE 'Failed' END AS status,
            reported_client_type AS client_type,
            COUNT(*) AS login_attempts,
            COUNT(DISTINCT client_ip) AS unique_ips,
            COUNT(DISTINCT user_name) AS unique_users,
            MIN(event_timestamp) AS first_seen,
            MAX(event_timestamp) AS last_seen,
            ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) AS pct_of_total
        FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
        WHERE event_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        GROUP BY 1, 2, 3
        ORDER BY login_attempts DESC
    """
    df = _get("authn_auth_activity", sql)
    if df.empty:
        st.info("No authentication activity data available.")
        return

    method_agg = df.groupby("AUTH_METHOD")["LOGIN_ATTEMPTS"].sum().reset_index()
    method_agg = method_agg.sort_values("LOGIN_ATTEMPTS", ascending=True)

    status_agg = df.groupby("STATUS")["LOGIN_ATTEMPTS"].sum().reset_index()

    client_agg = df.groupby("CLIENT_TYPE")["LOGIN_ATTEMPTS"].sum().reset_index()
    client_agg = client_agg.sort_values("LOGIN_ATTEMPTS", ascending=True).tail(10)

    ip_agg = df.groupby("AUTH_METHOD")["UNIQUE_IPS"].sum().reset_index()
    ip_agg = ip_agg.sort_values("UNIQUE_IPS", ascending=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Login Attempts by Auth Method**")
        _bar(method_agg["AUTH_METHOD"].tolist(),
             method_agg["LOGIN_ATTEMPTS"].tolist(),
             _C1, ylabel="Attempts", xlabel="Method",
             horizontal=False, key="aa_method")
    with col2:
        st.markdown("**Login Attempts by Status**")
        status_colors = {"Success": _C2, "Failed": _C3}
        colors = [status_colors.get(s, _C1) for s in status_agg["STATUS"]]
        _donut(status_agg["STATUS"].tolist(),
               status_agg["LOGIN_ATTEMPTS"].tolist(),
               colors, key="aa_status")

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**Top Client Types**")
        _bar(client_agg["CLIENT_TYPE"].tolist(),
             client_agg["LOGIN_ATTEMPTS"].tolist(),
             _C2, ylabel="Attempts", xlabel="Client Type",
             horizontal=True, h=320, key="aa_client")
    with col4:
        st.markdown("**Unique IPs by Auth Method**")
        _bar(ip_agg["AUTH_METHOD"].tolist(),
             ip_agg["UNIQUE_IPS"].tolist(),
             _C1, ylabel="Unique IPs", xlabel="Method",
             horizontal=False, key="aa_ips")

    display_cols = ["AUTH_METHOD", "STATUS", "CLIENT_TYPE", "LOGIN_ATTEMPTS",
                    "UNIQUE_IPS", "UNIQUE_USERS", "FIRST_SEEN", "LAST_SEEN", "PCT_OF_TOTAL"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "AUTH_METHOD": "Auth Method", "STATUS": "Status", "CLIENT_TYPE": "Client Type",
        "LOGIN_ATTEMPTS": "Attempts", "UNIQUE_IPS": "Unique IPs",
        "UNIQUE_USERS": "Unique Users", "FIRST_SEEN": "First Seen",
        "LAST_SEEN": "Last Seen", "PCT_OF_TOTAL": "% of Total"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)


def _render_auth_failures():
    st.caption("Repeated failed login attempts with error detail, client type, and source IP — last 30 days.")
    sql = """
        SELECT
            user_name,
            error_code,
            error_message,
            reported_client_type AS client_type,
            client_ip,
            COUNT(*) AS failure_count,
            MIN(event_timestamp) AS first_failure,
            MAX(event_timestamp) AS last_failure,
            CASE
                WHEN COUNT(*) > 50 THEN 'CRITICAL'
                WHEN COUNT(*) > 10 THEN 'HIGH'
                WHEN COUNT(*) > 5 THEN 'MODERATE'
                ELSE 'LOW'
            END AS severity
        FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
        WHERE event_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
          AND is_success = 'NO'
        GROUP BY user_name, error_code, error_message, reported_client_type, client_ip
        HAVING COUNT(*) > 1
        ORDER BY failure_count DESC
        LIMIT 20
    """
    df = _get("authn_auth_failures", sql)
    if df.empty:
        st.info("No repeated authentication failures found in the last 30 days.")
        return

    total_rows = len(df)
    distinct_users = df["USER_NAME"].nunique() if "USER_NAME" in df.columns else 0
    high_crit = len(df[df["SEVERITY"].isin(["CRITICAL", "HIGH"])]) if "SEVERITY" in df.columns else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Repeated Failure Rows", f"{total_rows:,}")
    with c2:
        st.metric("Distinct Users", f"{distinct_users:,}")
    with c3:
        st.metric("Critical / High", f"{high_crit:,}",
                  delta="⚠ Review" if high_crit > 0 else None,
                  delta_color="inverse")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Failure Volume by Severity**")
        sev_agg = df.groupby("SEVERITY")["FAILURE_COUNT"].sum().reset_index() if "SEVERITY" in df.columns else pd.DataFrame()
        if not sev_agg.empty:
            sev_color = {"CRITICAL": _CA, "HIGH": _C2, "MODERATE": _C1, "LOW": _C3}
            colors = [sev_color.get(s, _C1) for s in sev_agg["SEVERITY"]]
            _bar(sev_agg["SEVERITY"].tolist(), sev_agg["FAILURE_COUNT"].tolist(),
                 colors, xlabel="Severity", ylabel="Failures", key="af_sev")

    with col2:
        st.markdown("**Top Users by Repeated Failures**")
        user_agg = df.groupby("USER_NAME")["FAILURE_COUNT"].sum().reset_index() if "USER_NAME" in df.columns else pd.DataFrame()
        if not user_agg.empty:
            user_agg = user_agg.sort_values("FAILURE_COUNT", ascending=True).tail(10)
            _bar(user_agg["USER_NAME"].tolist(), user_agg["FAILURE_COUNT"].tolist(),
                 _CA, ylabel="Failures", horizontal=True, h=320, key="af_users")

    display_cols = ["USER_NAME", "ERROR_CODE", "ERROR_MESSAGE", "CLIENT_TYPE",
                    "CLIENT_IP", "FAILURE_COUNT", "FIRST_FAILURE", "LAST_FAILURE"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "USER_NAME": "User", "ERROR_CODE": "Error Code", "ERROR_MESSAGE": "Error Message",
        "CLIENT_TYPE": "Client Type", "CLIENT_IP": "Client IP",
        "FAILURE_COUNT": "Failure Count", "FIRST_FAILURE": "First Failure",
        "LAST_FAILURE": "Last Failure"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)


def _render_credential_hygiene():
    st.caption("MFA adoption, password-only accounts, and stale keypair credentials.")
    sql = """
        WITH auth_profiles AS (
            SELECT
                CASE
                    WHEN has_password = 'YES' AND ext_authn_duo = 'TRUE' THEN 'Password + MFA'
                    WHEN has_password = 'YES' AND ext_authn_duo = 'FALSE' THEN 'Password Only'
                    WHEN has_rsa_public_key = 'YES' THEN 'Keypair'
                    ELSE 'SSO/Federated'
                END AS auth_profile,
                CASE
                    WHEN has_rsa_public_key = 'YES'
                         AND (last_success_login < DATEADD('day', -180, CURRENT_TIMESTAMP())
                              OR last_success_login IS NULL)
                    THEN 1 ELSE 0
                END AS is_inactive_keypair
            FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
            WHERE deleted_on IS NULL
        )
        SELECT
            auth_profile,
            COUNT(*) AS user_count,
            SUM(is_inactive_keypair) AS inactive_keypair_users,
            ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) AS pct_of_users,
            CASE
                WHEN auth_profile = 'Password Only' THEN 'HIGH_RISK'
                WHEN auth_profile = 'Keypair' AND SUM(is_inactive_keypair) > 0 THEN 'MODERATE_RISK'
                ELSE 'LOW_RISK'
            END AS risk_level,
            CASE
                WHEN auth_profile = 'Password Only' THEN 'Enable MFA for these users'
                WHEN SUM(is_inactive_keypair) > 0 THEN 'Review inactive keypair credentials'
                ELSE 'Acceptable'
            END AS recommendation
        FROM auth_profiles
        GROUP BY auth_profile
        ORDER BY user_count DESC
    """
    df = _get("authn_credential_hygiene", sql)
    if df.empty:
        st.info("No credential hygiene data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**User Distribution by Auth Profile**")
        profile_colors = {
            "SSO/Federated": _C1, "Password Only": _C2,
            "Keypair": _C3, "Password + MFA": _CA
        }
        colors = [profile_colors.get(p, _C1) for p in df["AUTH_PROFILE"]]
        _donut(df["AUTH_PROFILE"].tolist(), df["USER_COUNT"].tolist(), colors, key="ch_dist")

    with col2:
        st.markdown("**Inactive Keypair Users by Auth Profile**")
        if "INACTIVE_KEYPAIR_USERS" in df.columns:
            inactive_df = df[["AUTH_PROFILE", "INACTIVE_KEYPAIR_USERS"]].copy()
            inactive_df["INACTIVE_KEYPAIR_USERS"] = pd.to_numeric(
                inactive_df["INACTIVE_KEYPAIR_USERS"], errors="coerce").fillna(0).astype(int)
            inactive_df = inactive_df.sort_values("INACTIVE_KEYPAIR_USERS", ascending=True)
            ik_colors = [profile_colors.get(p, _CA) for p in inactive_df["AUTH_PROFILE"]]
            _bar(inactive_df["AUTH_PROFILE"].tolist(),
                 inactive_df["INACTIVE_KEYPAIR_USERS"].tolist(),
                 ik_colors, ylabel="Inactive Users", horizontal=True, h=280, key="ch_inactive")

    display_cols = ["AUTH_PROFILE", "USER_COUNT", "INACTIVE_KEYPAIR_USERS",
                    "PCT_OF_USERS", "RISK_LEVEL", "RECOMMENDATION"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "AUTH_PROFILE": "Auth Profile", "USER_COUNT": "Users",
        "INACTIVE_KEYPAIR_USERS": "Inactive Keypair", "PCT_OF_USERS": "% of Users",
        "RISK_LEVEL": "Risk", "RECOMMENDATION": "Recommendation"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)


def _render_policy_audit():
    st.caption("Password and session security policies configured in the account.")

    pwd_sql = """
        SELECT
            name AS policy_name, database_name AS db, schema_name AS schema,
            password_max_age_days, password_min_length, password_max_retries,
            password_lockout_time_mins, password_history, comment,
            CASE WHEN password_max_age_days > 90 OR password_max_age_days IS NULL THEN 'WEAK'
                 WHEN password_max_age_days > 60 THEN 'MODERATE'
                 ELSE 'STRONG' END AS age_rating
        FROM SNOWFLAKE.ACCOUNT_USAGE.PASSWORD_POLICIES
        WHERE deleted IS NULL
    """
    sess_sql = """
        SELECT
            name AS policy_name, database_name AS db, schema_name AS schema,
            session_idle_timeout_mins, session_ui_idle_timeout_mins, comment,
            CASE WHEN session_idle_timeout_mins > 60 THEN 'LONG_TIMEOUT'
                 WHEN session_idle_timeout_mins > 30 THEN 'MODERATE_TIMEOUT'
                 ELSE 'SHORT_TIMEOUT' END AS timeout_rating,
            CASE WHEN session_idle_timeout_mins > 60 THEN 'Consider reducing idle timeout'
                 ELSE 'Acceptable' END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.SESSION_POLICIES
        WHERE deleted IS NULL
    """
    pwd_df = _get("authn_pwd_policies", pwd_sql)
    sess_df = _get("authn_session_policies", sess_sql)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Password Policies", len(pwd_df))
    with c2:
        st.metric("Session Policies", len(sess_df))

    if not pwd_df.empty:
        st.markdown("**Password Policies**")
        rename_pwd = {
            "POLICY_NAME": "Policy", "DB": "DB", "SCHEMA": "Schema",
            "PASSWORD_MAX_AGE_DAYS": "Max Age (days)", "PASSWORD_MIN_LENGTH": "Min Length",
            "PASSWORD_MAX_RETRIES": "Max Retries", "PASSWORD_LOCKOUT_TIME_MINS": "Lockout (mins)",
            "PASSWORD_HISTORY": "History", "COMMENT": "Comment", "AGE_RATING": "Age Rating"
        }
        show_cols = [c for c in rename_pwd if c in pwd_df.columns]
        st.dataframe(pwd_df[show_cols].rename(columns=rename_pwd), use_container_width=True)
    else:
        st.info("No password policies found.")

    if not sess_df.empty:
        st.markdown("**Session Policies**")
        rename_sess = {
            "POLICY_NAME": "Policy", "DB": "DB", "SCHEMA": "Schema",
            "SESSION_IDLE_TIMEOUT_MINS": "Idle Timeout (mins)",
            "SESSION_UI_IDLE_TIMEOUT_MINS": "UI Idle Timeout (mins)",
            "COMMENT": "Comment", "TIMEOUT_RATING": "Timeout Rating",
            "RECOMMENDATION": "Recommendation"
        }
        show_cols = [c for c in rename_sess if c in sess_df.columns]
        st.dataframe(sess_df[show_cols].rename(columns=rename_sess), use_container_width=True)
    else:
        st.info("No session policies found.")


def _render_pat_users():
    st.caption("Users with PATs enabled, their recent activity, and active vs inactive token usage.")
    sql = """
        SELECT
            name AS user_name, type AS user_type, default_role, last_success_login,
            DATEDIFF('day', last_success_login, CURRENT_TIMESTAMP()) AS days_since_login,
            CASE
                WHEN last_success_login < DATEADD('day', -90, CURRENT_TIMESTAMP())
                     OR last_success_login IS NULL THEN 'INACTIVE'
                ELSE 'ACTIVE'
            END AS activity_status
        FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
        WHERE deleted_on IS NULL AND has_pat = 'true'
        ORDER BY last_success_login DESC NULLS LAST
    """
    df = _get("ac_pat_users", sql)

    total_pat = len(df) if not df.empty else 0
    active_pat = len(df[df["ACTIVITY_STATUS"] == "ACTIVE"]) if not df.empty and "ACTIVITY_STATUS" in df.columns else 0
    inactive_pat = total_pat - active_pat

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("PAT Users", f"{total_pat:,}")
    with c2:
        st.metric("Active PAT Users", f"{active_pat:,}")
    with c3:
        st.metric("Inactive PAT Users", f"{inactive_pat:,}",
                  delta="⚠ Review" if inactive_pat > 0 else None,
                  delta_color="inverse")

    if df.empty:
        st.info("No users with Programmatic Access Tokens found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**PAT User Activity Status**")
        _donut(["ACTIVE", "INACTIVE"], [active_pat, inactive_pat], [_C1, _CA], key="pat_act")

    with col2:
        st.markdown("**PAT Users by User Type**")
        if "USER_TYPE" in df.columns:
            type_agg = df.groupby("USER_TYPE").size().reset_index(name="COUNT")
            type_agg = type_agg.sort_values("COUNT")
            _bar(type_agg["USER_TYPE"].tolist(), type_agg["COUNT"].tolist(),
                 _C2, xlabel="User Type", ylabel="Users", key="pat_type")


def _render_provisioning_method():
    st.caption("Role provisioning categorised by owner — SCIM (automated) vs manual admin vs custom.")
    sql = """
        SELECT
            owner AS provisioned_by_role,
            CASE
                WHEN owner LIKE '%SCIM%' OR owner LIKE '%PROVISION%' THEN 'Automated (SCIM)'
                WHEN owner IN ('USERADMIN', 'SECURITYADMIN', 'ACCOUNTADMIN') THEN 'Manual (Admin)'
                ELSE 'Custom/Other'
            END AS provisioning_method,
            COUNT(*) AS role_count,
            ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) AS pct_of_total
        FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES
        WHERE deleted_on IS NULL
        GROUP BY 1, 2
        ORDER BY role_count DESC
    """
    df = _get("authn_provisioning_method", sql)
    if df.empty:
        st.info("No provisioning method data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Role Provisioning Method**")
        method_agg = df.groupby("PROVISIONING_METHOD")["ROLE_COUNT"].sum().reset_index()
        method_colors = {"Automated (SCIM)": _C3, "Manual (Admin)": _C1, "Custom/Other": _C2}
        colors = [method_colors.get(m, _C1) for m in method_agg["PROVISIONING_METHOD"]]
        _donut(method_agg["PROVISIONING_METHOD"].tolist(),
               method_agg["ROLE_COUNT"].tolist(), colors, key="pm_donut")

    with col2:
        display_cols = ["PROVISIONED_BY_ROLE", "PROVISIONING_METHOD", "ROLE_COUNT", "PCT_OF_TOTAL"]
        display_cols = [c for c in display_cols if c in df.columns]
        rename_map = {
            "PROVISIONED_BY_ROLE": "Owner Role", "PROVISIONING_METHOD": "Method",
            "ROLE_COUNT": "Roles", "PCT_OF_TOTAL": "%"
        }
        st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)


def _render_trust_center():
    st.caption("Trust Center findings by scanner package, including open findings and scan freshness.")
    sql = """
        SELECT
            scanner_name AS scanner_package,
            MAX(detected_at) AS last_scan_run,
            DATEDIFF('hour', MAX(detected_at), CURRENT_TIMESTAMP()) AS hours_since_last_scan,
            COUNT(*) AS total_findings,
            COUNT(CASE WHEN status = 'OPEN' THEN 1 END) AS open_findings,
            COUNT(CASE WHEN status = 'RESOLVED' THEN 1 END) AS resolved_findings,
            COUNT(CASE WHEN status = 'SUPPRESSED' THEN 1 END) AS suppressed_findings,
            ROUND(COUNT(CASE WHEN status = 'OPEN' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS pct_open,
            CASE
                WHEN COUNT(CASE WHEN status = 'OPEN' THEN 1 END) > 50 THEN 'CRITICAL'
                WHEN COUNT(CASE WHEN status = 'OPEN' THEN 1 END) > 20 THEN 'HIGH'
                WHEN COUNT(CASE WHEN status = 'OPEN' THEN 1 END) > 5 THEN 'MODERATE'
                WHEN COUNT(CASE WHEN status = 'OPEN' THEN 1 END) > 0 THEN 'LOW'
                ELSE 'CLEAR'
            END AS findings_severity
        FROM SNOWFLAKE.ACCOUNT_USAGE.TRUST_CENTER_FINDINGS
        GROUP BY scanner_name
        ORDER BY open_findings DESC
    """
    df = _get("authn_tc_scanner_data", sql)

    scanner_count = len(df) if not df.empty else 0
    open_total = int(df["OPEN_FINDINGS"].sum()) if not df.empty and "OPEN_FINDINGS" in df.columns else 0
    resolved_total = int(df["RESOLVED_FINDINGS"].sum()) if not df.empty and "RESOLVED_FINDINGS" in df.columns else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Scanner Packages", f"{scanner_count:,}")
    with c2:
        st.metric("Open Findings", f"{open_total:,}",
                  delta="⚠ Review" if open_total > 0 else None,
                  delta_color="inverse")
    with c3:
        st.metric("Resolved Findings", f"{resolved_total:,}")

    if df.empty:
        st.info("No Trust Center findings data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Open Findings by Scanner Package**")
        open_df = df[["SCANNER_PACKAGE", "OPEN_FINDINGS"]].copy()
        open_df = open_df.sort_values("OPEN_FINDINGS", ascending=True)
        _bar(open_df["SCANNER_PACKAGE"].tolist(),
             open_df["OPEN_FINDINGS"].tolist(),
             _C2, ylabel="Open Findings", horizontal=True, h=280, key="tc_open")

    with col2:
        st.markdown("**Scanner Package Severity Distribution**")
        sev_agg = df.groupby("FINDINGS_SEVERITY").size().reset_index(name="COUNT")
        sev_colors_map = {
            "CRITICAL": _CA, "HIGH": _CA, "MODERATE": _C1,
            "LOW": _C3, "CLEAR": _C1
        }
        colors = [sev_colors_map.get(s, _C1) for s in sev_agg["FINDINGS_SEVERITY"]]
        _donut(sev_agg["FINDINGS_SEVERITY"].tolist(),
               sev_agg["COUNT"].tolist(), colors, key="tc_sev")

    display_cols = ["SCANNER_PACKAGE", "LAST_SCAN_RUN", "HOURS_SINCE_LAST_SCAN",
                    "TOTAL_FINDINGS", "OPEN_FINDINGS", "RESOLVED_FINDINGS",
                    "SUPPRESSED_FINDINGS", "PCT_OPEN", "FINDINGS_SEVERITY"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "SCANNER_PACKAGE": "Scanner Package", "LAST_SCAN_RUN": "Last Scan Run",
        "HOURS_SINCE_LAST_SCAN": "Hours Since Last Scan",
        "TOTAL_FINDINGS": "Total Findings", "OPEN_FINDINGS": "Open Findings",
        "RESOLVED_FINDINGS": "Resolved Findings", "SUPPRESSED_FINDINGS": "Suppressed Findings",
        "PCT_OPEN": "% Open", "FINDINGS_SEVERITY": "Severity"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)

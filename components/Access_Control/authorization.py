import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = "#29B5E8"
_C2 = "#11567F"
_C3 = "#75C2D8"
_CA = "#E8A229"
_CNP = "#003D73"


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


def _bar(x, y, colors, title="", h=300, xlabel="", ylabel="Count", horizontal=False, key=""):
    if horizontal:
        fig = go.Figure(go.Bar(
            y=x, x=y, orientation="h",
            marker_color=colors if isinstance(colors, list) else [colors] * len(x),
            text=y, textposition="outside",
        ))
        fig.update_layout(height=h, xaxis_title=ylabel, yaxis_title=xlabel,
                          margin=dict(t=20, b=40, l=180, r=40), showlegend=False)
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


def _donut(labels, values, colors, title="", h=320, key=""):
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


def comp_authorization(entry_actions=None):
    try:
        with st.expander("Role Hygiene & Hierarchy", expanded=True):
            _render_role_hygiene()

        with st.expander("User Inventory & Averages", expanded=True):
            _render_user_inventory()

        with st.expander("Security Hygiene Assessment", expanded=True):
            _render_security_hygiene()

        with st.expander("Object Ownership Distribution (Admin Hoarding)", expanded=True):
            _render_object_ownership()

        with st.expander("Privileged Access Summary", expanded=True):
            _render_privileged_access()

        with st.expander("Role Grant Distribution (Excessive Privileges)", expanded=True):
            _render_role_grant_distribution()

    except Exception as e:
        st.error(f"Error loading Authorization: {e}")


def _render_role_hygiene():
    st.caption("Custom roles, orphaned (no parent), hermit (isolated), and activity status within the selected metric run.")
    sql = """
        WITH system_roles AS (
            SELECT 'ACCOUNTADMIN' AS name UNION ALL SELECT 'SYSADMIN' UNION ALL
            SELECT 'SECURITYADMIN' UNION ALL SELECT 'USERADMIN' UNION ALL
            SELECT 'PUBLIC' UNION ALL SELECT 'ORGADMIN'
        ),
        role_hierarchy AS (
            SELECT name AS child_role, grantee_name AS parent_role
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE deleted_on IS NULL AND privilege = 'USAGE' AND granted_on = 'ROLE'
        ),
        role_activity AS (
            SELECT DISTINCT role_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE start_time >= DATEADD('day', -60, CURRENT_TIMESTAMP())
        )
        SELECT
            COUNT(DISTINCT r.name) AS total_roles,
            COUNT(DISTINCT CASE WHEN sr.name IS NULL THEN r.name END) AS custom_roles,
            COUNT(DISTINCT CASE WHEN sr.name IS NOT NULL THEN r.name END) AS system_roles,
            COUNT(DISTINCT CASE
                WHEN rh_parent.parent_role IS NULL AND r.name NOT IN ('ACCOUNTADMIN') THEN r.name
            END) AS orphan_roles,
            COUNT(DISTINCT CASE
                WHEN rh_parent.parent_role IS NULL AND rh_child.child_role IS NULL
                     AND r.name NOT IN ('ACCOUNTADMIN', 'PUBLIC') THEN r.name
            END) AS hermit_roles,
            COUNT(DISTINCT a.role_name) AS active_roles_60d,
            COUNT(DISTINCT r.name) - COUNT(DISTINCT a.role_name) AS inactive_roles
        FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES r
        LEFT JOIN system_roles sr ON r.name = sr.name
        LEFT JOIN role_hierarchy rh_parent ON r.name = rh_parent.child_role
        LEFT JOIN role_hierarchy rh_child ON r.name = rh_child.parent_role
        LEFT JOIN role_activity a ON r.name = a.role_name
        WHERE r.deleted_on IS NULL
    """
    df = _get("auth_role_hygiene", sql)
    if df.empty:
        st.info("No role hygiene data available.")
        return
    row = df.iloc[0]
    total = int(row.get("TOTAL_ROLES", 0))
    custom = int(row.get("CUSTOM_ROLES", 0))
    system = int(row.get("SYSTEM_ROLES", total - custom))
    orphan = int(row.get("ORPHAN_ROLES", 0))
    hermit = int(row.get("HERMIT_ROLES", 0))
    active = int(row.get("ACTIVE_ROLES_60D", 0))
    inactive = int(row.get("INACTIVE_ROLES", 0))
    pct_orphan = round(orphan / total * 100, 1) if total else 0
    pct_hermit = round(hermit / total * 100, 1) if total else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("Total Roles", f"{total:,}")
    with c2:
        st.metric("Custom Roles", f"{custom:,}")
    with c3:
        st.metric("System Roles", f"{system:,}")
    with c4:
        st.metric("Orphan Roles", f"{orphan:,}",
                  delta=f"+{pct_orphan}%" if orphan > 0 else None,
                  delta_color="inverse")
    with c5:
        st.metric("Hermit Roles", f"{hermit:,}",
                  delta=f"+{pct_hermit}%" if hermit > 0 else None,
                  delta_color="inverse")
    with c6:
        st.metric("Active (run)", f"{active:,}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Role Type Distribution**")
        _bar(["Custom", "System"], [custom, system], [_C1, _C1], key="rh_type")
    with col2:
        st.markdown("**Role Activity (run snapshot)**")
        _bar(["Active", "Inactive"], [active, inactive], [_C1, _C1], key="rh_act")
    with col3:
        healthy = max(0, total - orphan)
        orphan_only = max(0, orphan - hermit)
        st.markdown("**Role Hierarchy Health**")
        _bar(["Healthy", "Orphan Only", "Hermit"],
             [healthy, orphan_only, hermit],
             [_C1, _C1, _C1], key="rh_hier")


def _render_user_inventory():
    st.caption("Person users, activity over 60 days, admin role counts, and role assignment averages.")
    sql = """
        WITH user_grants AS (
            SELECT grantee_name AS user_name, COUNT(*) AS role_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
            WHERE deleted_on IS NULL GROUP BY 1
        ),
        role_grants AS (
            SELECT role AS role_name, COUNT(*) AS user_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
            WHERE deleted_on IS NULL GROUP BY 1
        )
        SELECT
            COUNT(*) AS total_users,
            COUNT(CASE WHEN type = 'PERSON' OR type IS NULL THEN 1 END) AS person_users,
            COUNT(CASE WHEN type = 'SERVICE' THEN 1 END) AS service_users,
            COUNT(CASE WHEN type = 'LEGACY_SERVICE' THEN 1 END) AS legacy_service_users,
            COUNT(CASE WHEN last_success_login > DATEADD('day', -60, CURRENT_TIMESTAMP()) THEN 1 END) AS active_users_60d,
            COUNT(CASE WHEN last_success_login <= DATEADD('day', -60, CURRENT_TIMESTAMP()) OR last_success_login IS NULL THEN 1 END) AS inactive_users,
            ROUND(AVG(COALESCE(ug.role_count, 0)), 1) AS avg_roles_per_user,
            (SELECT ROUND(AVG(user_count), 1) FROM role_grants) AS avg_users_per_role,
            MAX(ug.role_count) AS max_roles_single_user,
            MIN(COALESCE(ug.role_count, 0)) AS min_roles_single_user
        FROM SNOWFLAKE.ACCOUNT_USAGE.USERS u
        LEFT JOIN user_grants ug ON u.name = ug.user_name
        WHERE u.deleted_on IS NULL
    """
    df = _get("auth_user_inventory", sql)
    if df.empty:
        st.info("No user inventory data available.")
        return
    row = df.iloc[0]
    total = int(row.get("TOTAL_USERS", 0))
    person = int(row.get("PERSON_USERS", 0))
    service = int(row.get("SERVICE_USERS", 0))
    legacy = int(row.get("LEGACY_SERVICE_USERS", 0))
    active = int(row.get("ACTIVE_USERS_60D", 0))
    inactive = int(row.get("INACTIVE_USERS", 0))
    avg_rpu = float(row.get("AVG_ROLES_PER_USER") or 0)
    avg_upr = float(row.get("AVG_USERS_PER_ROLE") or 0)
    max_r = int(row.get("MAX_ROLES_SINGLE_USER") or 0)
    min_r = int(row.get("MIN_ROLES_SINGLE_USER") or 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Users", f"{total:,}")
    with c2:
        st.metric("Person Users", f"{person:,}")
    with c3:
        st.metric("Service Users", f"{service:,}")
    with c4:
        st.metric("Legacy Service", f"{legacy:,}")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.metric("Active (60d)", f"{active:,}")
    with c6:
        st.metric("Avg Roles/User", f"{avg_rpu}")
    with c7:
        st.metric("Avg Users/Role", f"{avg_upr}")
    with c8:
        st.metric("Max Roles/User", f"{max_r:,}")

    st.caption(f"Role spread per user: min {min_r}, max {max_r}.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**User Activity Status**")
        _bar(["Active (60d)", "Inactive"], [active, inactive], [_C1, _C1], key="ui_act")
    with col2:
        st.markdown("**User Type Distribution**")
        other = max(0, total - person - service - legacy)
        labels = ["Person", "Legacy Service", "Service"]
        values = [person, legacy, service]
        colors = [_C1, _C2, _C3]
        if other > 0:
            labels.append("Other")
            values.append(other)
            colors.append(_CA)
        _donut(labels, values, colors, key="ui_type")


def _render_security_hygiene():
    st.caption("Authentication methods, unhealthy configurations (password without MFA, keypair users, ACCOUNTADMIN default roles), and privileged role assignments.")
    sql = """
        SELECT
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'PASSWORD' THEN user_name END) AS users_using_password,
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'OAUTH_ACCESS_TOKEN' THEN user_name END) AS users_using_oauth,
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'RSA_KEYPAIR' THEN user_name END) AS users_using_keypair,
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'SAML2' THEN user_name END) AS users_using_saml,
            (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE has_password = 'YES' AND ext_authn_duo = 'FALSE' AND deleted_on IS NULL) AS unhealthy_password_no_mfa,
            (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE has_rsa_public_key = 'YES' AND deleted_on IS NULL) AS keypair_users_count,
            (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE default_role = 'ACCOUNTADMIN' AND deleted_on IS NULL) AS default_role_accountadmin,
            (SELECT COUNT(DISTINCT grantee_name) FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
             WHERE role IN ('ACCOUNTADMIN', 'SECURITYADMIN') AND deleted_on IS NULL) AS admin_role_holders_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
        WHERE event_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    """
    df = _get("auth_security_hygiene", sql)
    if df.empty:
        st.info("No security hygiene data available.")
        return
    row = df.iloc[0]
    no_mfa = int(row.get("UNHEALTHY_PASSWORD_NO_MFA", 0))
    default_admin = int(row.get("DEFAULT_ROLE_ACCOUNTADMIN", 0))
    admin_holders = int(row.get("ADMIN_ROLE_HOLDERS_COUNT", 0))
    keypair = int(row.get("KEYPAIR_USERS_COUNT", 0))
    pwd_users = int(row.get("USERS_USING_PASSWORD", 0))
    oauth_users = int(row.get("USERS_USING_OAUTH", 0))
    kp_users = int(row.get("USERS_USING_KEYPAIR", 0))
    saml_users = int(row.get("USERS_USING_SAML", 0))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Password w/o MFA", f"{no_mfa:,}",
                  delta="⚠ Risk" if no_mfa > 0 else None,
                  delta_color="inverse")
    with c2:
        st.metric("Default ACCOUNTADMIN", f"{default_admin:,}",
                  delta="⚠ Risk" if default_admin > 0 else None,
                  delta_color="inverse")
    with c3:
        st.metric("Admin Role Holders", f"{admin_holders:,}")
    with c4:
        st.metric("Keypair Users", f"{keypair:,}")

    if no_mfa > 0:
        st.markdown(
            '<div style="background-color:#FFFBE6;border:1px solid #E8A229;border-radius:4px;padding:10px;margin:8px 0;">'
            f'<b>WARNING: Password users without MFA</b>'
            '</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Auth Methods (last 30d)**")
        _bar(["Password", "OAuth", "Keypair", "SAML"],
             [pwd_users, oauth_users, kp_users, saml_users],
             [_C1, _C1, _C1, _C1], ylabel="Distinct Users", key="sg_auth")
    with col2:
        st.markdown("**Security Risk Indicators**")
        _bar(["Password w/o MFA", "Default ACCOUNTADMIN", "Admin Role Holders", "Keypair Users"],
             [no_mfa, default_admin, admin_holders, keypair],
             [_CA, _C1, _C3, _C1], key="sg_risk")


def _render_object_ownership():
    st.caption("Objects owned by admin roles (ACCOUNTADMIN, SYSADMIN, SECURITYADMIN) by object type.")
    sql = """
        SELECT
            grantee_name AS role_owner,
            granted_on AS object_type,
            COUNT(*) AS object_count,
            CASE WHEN COUNT(*) > 100 THEN 'HIGH_CONCENTRATION'
                 WHEN COUNT(*) > 25 THEN 'MODERATE_CONCENTRATION'
                 ELSE 'LOW'
            END AS ownership_status,
            CASE WHEN grantee_name = 'ACCOUNTADMIN' AND COUNT(*) > 10
                    THEN 'Transfer ownership to appropriate functional roles'
                 WHEN grantee_name = 'SYSADMIN' AND COUNT(*) > 50
                    THEN 'Consider delegating to database-specific roles'
                 ELSE 'Acceptable'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE deleted_on IS NULL AND privilege = 'OWNERSHIP'
          AND grantee_name IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN')
          AND granted_on NOT IN ('USER', 'ROLE')
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
    """
    df = _get("auth_object_ownership", sql)
    if df.empty:
        st.info("No object ownership data available.")
        return

    role_totals = df.groupby("ROLE_OWNER")["OBJECT_COUNT"].sum().reset_index()
    role_totals = role_totals.sort_values("OBJECT_COUNT")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Objects Owned by Admin Roles**")
        role_colors = {
            "ACCOUNTADMIN": _C1,
            "SECURITYADMIN": _C3,
            "SYSADMIN": _CA,
        }
        colors = [role_colors.get(r, _C1) for r in role_totals["ROLE_OWNER"]]
        fig = go.Figure(go.Bar(
            x=role_totals["ROLE_OWNER"],
            y=role_totals["OBJECT_COUNT"],
            marker_color=colors,
            text=role_totals["OBJECT_COUNT"],
            textposition="outside",
        ))
        fig.update_layout(height=320, xaxis_title="Role", yaxis_title="Objects Owned",
                          margin=dict(t=20, b=60, l=60, r=30), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key="oo_by_role")

    with col2:
        st.markdown("**Admin-Owned Objects by Type**")
        type_totals = df.groupby("OBJECT_TYPE")["OBJECT_COUNT"].sum().reset_index()
        type_totals = type_totals.sort_values("OBJECT_COUNT", ascending=True).tail(10)
        fig2 = go.Figure(go.Bar(
            y=type_totals["OBJECT_TYPE"],
            x=type_totals["OBJECT_COUNT"],
            orientation="h",
            marker_color=_C1,
            text=type_totals["OBJECT_COUNT"],
            textposition="outside",
        ))
        fig2.update_layout(height=320, xaxis_title="Objects Owned", yaxis_title="Object Type",
                           margin=dict(t=20, b=40, l=140, r=40), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True, key="oo_by_type")

    display_cols = ["ROLE_OWNER", "OBJECT_TYPE", "OBJECT_COUNT", "OWNERSHIP_STATUS", "RECOMMENDATION"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "ROLE_OWNER": "Role", "OBJECT_TYPE": "Object Type",
        "OBJECT_COUNT": "Count", "OWNERSHIP_STATUS": "Status",
        "RECOMMENDATION": "Recommendation"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)


def _render_privileged_access():
    st.caption("Users with ACCOUNTADMIN, SECURITYADMIN, SYSADMIN, or USERADMIN roles — auth method and risk level.")
    sql = """
        WITH privileged_users AS (
            SELECT DISTINCT grantee_name AS user_name, role AS privileged_role
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
            WHERE role IN ('ACCOUNTADMIN', 'SECURITYADMIN', 'SYSADMIN', 'USERADMIN')
              AND deleted_on IS NULL
        ),
        user_details AS (
            SELECT name, type, default_role, last_success_login,
                   has_password, ext_authn_duo, has_rsa_public_key
            FROM SNOWFLAKE.ACCOUNT_USAGE.USERS WHERE deleted_on IS NULL
        )
        SELECT
            pu.user_name, pu.privileged_role,
            ud.type AS user_type, ud.default_role, ud.last_success_login,
            DATEDIFF('day', ud.last_success_login, CURRENT_TIMESTAMP()) AS days_since_login,
            CASE
                WHEN ud.has_rsa_public_key = 'YES' THEN 'KEYPAIR'
                WHEN ud.has_password = 'YES' AND COALESCE(ud.ext_authn_duo, 'FALSE') = 'TRUE' THEN 'MFA_ENABLED'
                WHEN ud.has_password = 'YES' AND COALESCE(ud.ext_authn_duo, 'FALSE') = 'FALSE' THEN 'NO_MFA'
                ELSE 'OTHER'
            END AS auth_method,
            CASE
                WHEN ud.default_role = 'ACCOUNTADMIN' THEN 'CRITICAL'
                WHEN ud.has_password = 'YES' AND COALESCE(ud.ext_authn_duo, 'FALSE') = 'FALSE' THEN 'HIGH'
                WHEN DATEDIFF('day', ud.last_success_login, CURRENT_TIMESTAMP()) > 90 THEN 'MODERATE'
                ELSE 'LOW'
            END AS risk_level
        FROM privileged_users pu
        INNER JOIN user_details ud ON pu.user_name = ud.name
        ORDER BY
            CASE pu.privileged_role WHEN 'ACCOUNTADMIN' THEN 1 WHEN 'SECURITYADMIN' THEN 2
                WHEN 'SYSADMIN' THEN 3 ELSE 4 END, risk_level DESC
    """
    df = _get("ac_privileged_access", sql)
    if df.empty:
        st.info("No privileged access data available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Users per Privileged Role**")
        role_counts = df.groupby("PRIVILEGED_ROLE")["USER_NAME"].count().reset_index(name="COUNT")
        role_order = ["ACCOUNTADMIN", "SECURITYADMIN", "SYSADMIN", "USERADMIN"]
        role_counts["_order"] = role_counts["PRIVILEGED_ROLE"].apply(
            lambda r: role_order.index(r) if r in role_order else 99)
        role_counts = role_counts.sort_values("_order")
        _bar(role_counts["PRIVILEGED_ROLE"].tolist(), role_counts["COUNT"].tolist(),
             [_C1] * len(role_counts), xlabel="Role", ylabel="Users", key="pa_roles")

    with col2:
        st.markdown("**Risk Distribution**")
        risk_counts = df["RISK_LEVEL"].value_counts().reset_index()
        risk_counts.columns = ["RISK", "COUNT"]
        risk_color = {"LOW": _C1, "MODERATE": _C2, "HIGH": _CA, "CRITICAL": _CA}
        colors = [risk_color.get(r, _C1) for r in risk_counts["RISK"]]
        _donut(risk_counts["RISK"].tolist(), risk_counts["COUNT"].tolist(), colors, key="pa_risk")

    display_cols = ["USER_NAME", "PRIVILEGED_ROLE", "USER_TYPE", "DEFAULT_ROLE",
                    "LAST_SUCCESS_LOGIN", "DAYS_SINCE_LOGIN", "AUTH_METHOD", "RISK_LEVEL"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "USER_NAME": "User", "PRIVILEGED_ROLE": "Role", "USER_TYPE": "Type",
        "DEFAULT_ROLE": "Default Role", "LAST_SUCCESS_LOGIN": "Last Success Login",
        "DAYS_SINCE_LOGIN": "Days Since Login", "AUTH_METHOD": "Auth Method",
        "RISK_LEVEL": "Risk"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)


def _render_role_grant_distribution():
    st.caption("Top 20 non-system roles with the most grants — high counts may indicate over-privileged roles.")
    sql = """
        SELECT
            grantee_name AS role_name,
            COUNT(*) AS total_grants,
            COUNT(DISTINCT granted_on) AS distinct_object_types,
            COUNT(CASE WHEN privilege = 'OWNERSHIP' THEN 1 END) AS ownership_grants,
            COUNT(CASE WHEN privilege IN ('ALL', 'ALL PRIVILEGES') THEN 1 END) AS all_privilege_grants,
            CASE
                WHEN COUNT(*) > 500 THEN 'VERY_HIGH'
                WHEN COUNT(*) > 100 THEN 'HIGH'
                WHEN COUNT(*) > 25 THEN 'MODERATE'
                ELSE 'LOW'
            END AS grant_concentration,
            CASE
                WHEN COUNT(CASE WHEN privilege IN ('ALL', 'ALL PRIVILEGES') THEN 1 END) > 0
                    THEN 'Review ALL PRIVILEGES grants'
                WHEN COUNT(CASE WHEN privilege = 'OWNERSHIP' THEN 1 END) > 50
                    THEN 'Consider splitting role responsibilities'
                WHEN COUNT(*) > 100 THEN 'Consider more granular role structure'
                ELSE 'Acceptable'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE deleted_on IS NULL
          AND grantee_name NOT IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'USERADMIN', 'PUBLIC')
        GROUP BY 1 HAVING COUNT(*) > 10
        ORDER BY total_grants DESC LIMIT 20
    """
    df = _get("ac_role_grant_dist", sql)
    if df.empty:
        st.info("No custom roles with significant grants found.")
        return

    for c in ["TOTAL_GRANTS", "DISTINCT_OBJECT_TYPES", "OWNERSHIP_GRANTS", "ALL_PRIVILEGE_GRANTS"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    conc_colors = {"VERY_HIGH": _CA, "HIGH": _C2, "MODERATE": _C3, "LOW": _C1}
    bar_colors = [conc_colors.get(str(c), _C1) for c in df.get("GRANT_CONCENTRATION", [])]

    st.markdown("**Top Roles by Grant Count**")
    fig = go.Figure(go.Bar(
        x=df["ROLE_NAME"],
        y=df["TOTAL_GRANTS"],
        marker_color=bar_colors,
        text=df["TOTAL_GRANTS"],
        textposition="outside",
    ))
    color_legend = [c for c in conc_colors if c in df["GRANT_CONCENTRATION"].values]
    for conc in color_legend:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(color=conc_colors[conc], size=10, symbol="square"),
            name=conc, showlegend=True
        ))
    fig.update_layout(
        height=350, xaxis_title="Role", yaxis_title="Total Grants",
        margin=dict(t=20, b=120, l=50, r=30),
        xaxis=dict(tickangle=-45),
        legend=dict(orientation="v", x=1.0, y=1.0)
    )
    st.plotly_chart(fig, use_container_width=True, key="rgd_bar")

    display_cols = ["ROLE_NAME", "TOTAL_GRANTS", "DISTINCT_OBJECT_TYPES",
                    "OWNERSHIP_GRANTS", "ALL_PRIVILEGE_GRANTS",
                    "GRANT_CONCENTRATION", "RECOMMENDATION"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "ROLE_NAME": "Role", "TOTAL_GRANTS": "Total Grants",
        "DISTINCT_OBJECT_TYPES": "Obj Types", "OWNERSHIP_GRANTS": "Ownership",
        "ALL_PRIVILEGE_GRANTS": "ALL Privs", "GRANT_CONCENTRATION": "Concentration",
        "RECOMMENDATION": "Recommendation"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)

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
SEV_COLORS = {'CRITICAL': '#F39C12', 'HIGH': '#E8A229', 'MODERATE': '#75C2D8', 'LOW': '#29B5E8'}


def comp_authorization(entry_actions=None):
    try:
        st.markdown("### Authorization")

        with st.expander("Role Hygiene & Hierarchy", expanded=True):
            _render_role_hygiene_hierarchy()

        with st.expander("User Inventory & Averages", expanded=True):
            _render_user_inventory_averages()

        with st.expander("Security Hygiene (\"Unhealthy\" Users)", expanded=True):
            _render_security_hygiene()

        with st.expander("Object Ownership (Admin Hoarding)", expanded=True):
            _render_object_ownership()

        with st.expander("Privileged Access Summary", expanded=True):
            _render_privileged_access()

        with st.expander("Role Grant Distribution", expanded=True):
            _render_role_grant_distribution()

    except Exception as e:
        st.error(f"Error loading Authorization: {e}")


def _render_role_hygiene_hierarchy():
    st.markdown("#### Role Hygiene & Hierarchy")
    st.markdown(
        "Role hygiene analysis identifying custom roles, orphaned roles (no parent), hermit roles (no parent or child), "
        "and active vs inactive roles based on 60-day query history.")
    try:
        role_hygiene_query = """
        WITH system_roles AS (
            SELECT 'ACCOUNTADMIN' AS name UNION ALL SELECT 'SYSADMIN' UNION ALL
            SELECT 'SECURITYADMIN' UNION ALL SELECT 'USERADMIN' UNION ALL SELECT 'PUBLIC' UNION ALL SELECT 'ORGADMIN'
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
            COUNT(DISTINCT CASE WHEN rh_parent.parent_role IS NULL AND r.name NOT IN ('ACCOUNTADMIN') THEN r.name END) AS orphan_roles,
            COUNT(DISTINCT CASE WHEN rh_parent.parent_role IS NULL AND rh_child.child_role IS NULL AND r.name NOT IN ('ACCOUNTADMIN', 'PUBLIC') THEN r.name END) AS hermit_roles,
            COUNT(DISTINCT a.role_name) AS active_roles_60d,
            COUNT(DISTINCT r.name) - COUNT(DISTINCT a.role_name) AS inactive_roles
        FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES r
        LEFT JOIN system_roles sr ON r.name = sr.name
        LEFT JOIN role_hierarchy rh_parent ON r.name = rh_parent.child_role
        LEFT JOIN role_hierarchy rh_child ON r.name = rh_child.parent_role
        LEFT JOIN role_activity a ON r.name = a.role_name
        WHERE r.deleted_on IS NULL
        """
        df = _cached_sql("auth_role_hygiene", role_hygiene_query)
        if df.empty:
            st.info("No role hygiene data available.")
            return

        row = df.iloc[0]
        total_roles = int(row['TOTAL_ROLES'])
        custom_roles = int(row['CUSTOM_ROLES'])
        system_roles = int(row.get('SYSTEM_ROLES', total_roles - custom_roles))
        orphan_roles = int(row['ORPHAN_ROLES'])
        hermit_roles = int(row['HERMIT_ROLES'])
        active_roles = int(row['ACTIVE_ROLES_60D'])
        inactive_roles = int(row['INACTIVE_ROLES'])

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.metric("Total Roles", f"{total_roles:,}")
        with c2:
            st.metric("Custom Roles", f"{custom_roles:,}")
        with c3:
            st.metric("System Roles", system_roles)
        with c4:
            st.metric("Orphan Roles", orphan_roles)
        with c5:
            st.metric("Hermit Roles", hermit_roles)
        with c6:
            st.metric("Active (run)", f"{active_roles:,}")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Role Type Distribution**")
            fig = go.Figure(go.Bar(x=['Custom', 'System'], y=[custom_roles, system_roles],
                                   marker_color=[BRAND_PRIMARY, BRAND_PRIMARY_DARK],
                                   text=[custom_roles, system_roles], textposition='outside'))
            fig.update_layout(height=300, margin=dict(t=20, b=50, l=50, r=30), yaxis_title='Count')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**Role Activity (run snapshot)**")
            fig = go.Figure(go.Bar(x=['Active', 'Inactive'], y=[active_roles, inactive_roles],
                                   marker_color=[COLOR_LIGHT, BRAND_ACCENT],
                                   text=[active_roles, inactive_roles], textposition='outside'))
            fig.update_layout(height=300, margin=dict(t=20, b=50, l=50, r=30), yaxis_title='Count')
            st.plotly_chart(fig, use_container_width=True)
        with col3:
            st.markdown("**Role Hierarchy Health**")
            healthy = total_roles - orphan_roles
            fig = go.Figure(go.Bar(x=['Healthy', 'Orphan', 'Hermit'],
                                   y=[healthy, orphan_roles - hermit_roles, hermit_roles],
                                   marker_color=[BRAND_PRIMARY_DARK, BRAND_ACCENT, BRAND_ACCENT],
                                   text=[healthy, orphan_roles - hermit_roles, hermit_roles], textposition='outside'))
            fig.update_layout(height=300, margin=dict(t=20, b=50, l=50, r=30), yaxis_title='Count')
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading role hygiene data: {e}")


def _render_user_inventory_averages():
    st.markdown("#### User Inventory & Averages")
    st.markdown(
        "User inventory analysis showing total users, person vs service account breakdown, 60-day activity status, "
        "and average roles per user and users per role.")
    try:
        user_inventory_query = """
        WITH user_grants AS (
            SELECT grantee_name AS user_name, COUNT(*) AS role_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
            WHERE deleted_on IS NULL
            GROUP BY 1
        ),
        role_grants AS (
            SELECT role AS role_name, COUNT(*) AS user_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
            WHERE deleted_on IS NULL
            GROUP BY 1
        )
        SELECT
            COUNT(*) AS total_users,
            COUNT(CASE WHEN type = 'PERSON' OR (type IS NULL AND name NOT LIKE '%_SVC_%') THEN 1 END) AS person_users,
            COUNT(CASE WHEN type = 'SERVICE' THEN 1 END) AS service_users,
            COUNT(CASE WHEN type = 'LEGACY_SERVICE' THEN 1 END) AS legacy_service_users,
            COUNT(CASE WHEN last_success_login > DATEADD('day', -60, CURRENT_TIMESTAMP()) THEN 1 END) AS active_users_60d,
            COUNT(CASE WHEN last_success_login <= DATEADD('day', -60, CURRENT_TIMESTAMP()) OR last_success_login IS NULL THEN 1 END) AS inactive_users,
            ROUND(AVG(ug.role_count), 1) AS avg_roles_per_user,
            (SELECT ROUND(AVG(user_count), 1) FROM role_grants) AS avg_users_per_role,
            MAX(ug.role_count) AS max_roles_single_user
        FROM SNOWFLAKE.ACCOUNT_USAGE.USERS u
        LEFT JOIN user_grants ug ON u.name = ug.user_name
        WHERE u.deleted_on IS NULL
        """
        df = _cached_sql("auth_user_inventory", user_inventory_query)
        if df.empty:
            st.info("No user inventory data available.")
            return

        row = df.iloc[0]
        total_users = int(row['TOTAL_USERS'])
        person_users = int(row.get('PERSON_USERS', row.get('TYPE_PERSON_COUNT', 0)))
        service_users = int(row.get('SERVICE_USERS', row.get('TYPE_SERVICE_COUNT', 0)))
        legacy_service = int(row.get('LEGACY_SERVICE_USERS', 0))
        active_60d = int(row['ACTIVE_USERS_60D'])
        inactive = int(row['INACTIVE_USERS'])
        avg_roles = float(row['AVG_ROLES_PER_USER']) if row['AVG_ROLES_PER_USER'] is not None else 0.0
        avg_users = float(row['AVG_USERS_PER_ROLE']) if row['AVG_USERS_PER_ROLE'] is not None else 0.0
        max_roles = int(row.get('MAX_ROLES_SINGLE_USER', 0)) if row.get('MAX_ROLES_SINGLE_USER') is not None else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Users", total_users)
        with c2:
            st.metric("Person Users", person_users)
        with c3:
            st.metric("Service Users", service_users)
        with c4:
            st.metric("Legacy Service", legacy_service)

        c5, c6, c7, c8 = st.columns(4)
        with c5:
            st.metric("Active (60d)", active_60d)
        with c6:
            st.metric("Avg Roles/User", f"{avg_roles:.1f}")
        with c7:
            st.metric("Avg Users/Role", f"{avg_users:.1f}")
        with c8:
            st.metric("Max Roles/User", max_roles)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**User Activity Status**")
            fig = go.Figure(go.Bar(x=['Active (60d)', 'Inactive'], y=[active_60d, inactive],
                                   marker_color=[BRAND_PRIMARY_DARK, BRAND_ACCENT],
                                   text=[active_60d, inactive], textposition='outside'))
            fig.update_layout(height=300, margin=dict(t=20, b=50, l=50, r=30), yaxis_title='Count')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**User Type Distribution**")
            other_users = total_users - person_users - service_users - legacy_service
            if other_users < 0:
                other_users = 0
            labels = ['Person', 'Legacy Service', 'Service', 'Other']
            values = [person_users, legacy_service, service_users, other_users]
            labels_f = [l for l, v in zip(labels, values) if v > 0]
            values_f = [v for v in values if v > 0]
            fig = go.Figure(go.Pie(labels=labels_f, values=values_f, hole=0.35,
                                   marker=dict(colors=[BRAND_PRIMARY, BRAND_ACCENT, BRAND_PRIMARY_DARK, COLOR_LIGHT])))
            fig.update_layout(height=300, margin=dict(t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading user inventory data: {e}")


def _render_security_hygiene():
    st.markdown("#### Security Hygiene (\"Unhealthy\" Users)")
    st.markdown(
        "Authentication security assessment identifying users by auth method, unhealthy configurations "
        "(password without MFA, keypair users, ACCOUNTADMIN default roles), and privileged role assignments.")
    try:
        security_hygiene_query = """
        SELECT
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'PASSWORD' THEN user_name END) AS users_using_password,
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'OAUTH_ACCESS_TOKEN' THEN user_name END) AS users_using_oauth,
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'RSA_KEYPAIR' THEN user_name END) AS users_using_keypair,
            (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE has_password = 'YES' AND ext_authn_duo = 'FALSE' AND deleted_on IS NULL) AS unhealthy_password_no_mfa,
            (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE has_rsa_public_key = 'YES' AND deleted_on IS NULL) AS keypair_users_check_net_policy,
            (SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE default_role = 'ACCOUNTADMIN' AND deleted_on IS NULL) AS default_role_accountadmin,
            (SELECT COUNT(DISTINCT grantee_name) FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
             WHERE role IN ('ACCOUNTADMIN', 'SECURITYADMIN') AND deleted_on IS NULL) AS users_holding_admin_roles
        FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
        WHERE event_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        """
        df = _cached_sql("auth_security_hygiene", security_hygiene_query)
        if df.empty:
            st.info("No security hygiene data available.")
            return

        row = df.iloc[0]
        pwd_users = int(row.get('USERS_USING_PASSWORD', 0) or 0)
        oauth_users = int(row.get('USERS_USING_OAUTH', 0) or 0)
        kp_users = int(row.get('USERS_USING_KEYPAIR', 0) or 0)
        pwd_no_mfa = int(row.get('UNHEALTHY_PASSWORD_NO_MFA', 0) or 0)
        kp_check = int(row.get('KEYPAIR_USERS_CHECK_NET_POLICY', 0) or 0)
        default_admin = int(row.get('DEFAULT_ROLE_ACCOUNTADMIN', 0) or 0)
        admin_holders = int(row.get('USERS_HOLDING_ADMIN_ROLES', 0) or 0)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Password w/o MFA", pwd_no_mfa)
        with c2:
            st.metric("Default ACCOUNTADMIN", default_admin)
        with c3:
            st.metric("Admin Role Holders", admin_holders)
        with c4:
            st.metric("Keypair Users", kp_check)

        if pwd_no_mfa > 0:
            st.warning(f"{pwd_no_mfa} password users without MFA — consider enabling MFA for these accounts.")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Auth Methods (Last 30d)**")
            saml_users = 0
            fig = go.Figure(go.Bar(x=['Password', 'OAuth', 'Keypair', 'SAML'], y=[pwd_users, oauth_users, kp_users, saml_users],
                                   marker_color=[BRAND_PRIMARY, BRAND_PRIMARY_DARK, BRAND_ACCENT, COLOR_LIGHT],
                                   text=[pwd_users, oauth_users, kp_users, saml_users], textposition='outside'))
            fig.update_layout(height=300, margin=dict(t=20, b=50, l=50, r=30), yaxis_title='Distinct Users')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**Security Risk Indicators**")
            risk_types = ['Password w/o MFA', 'Default ACCOUNTADMIN', 'Admin Role Holders', 'Keypair Users']
            risk_vals = [pwd_no_mfa, default_admin, admin_holders, kp_check]
            fig = go.Figure(go.Bar(x=risk_types, y=risk_vals,
                                   marker_color=[BRAND_ACCENT, BRAND_ACCENT, BRAND_PRIMARY_DARK, COLOR_LIGHT],
                                   text=risk_vals, textposition='outside'))
            fig.update_layout(height=300, margin=dict(t=20, b=80, l=50, r=30), yaxis_title='Count')
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading security hygiene data: {e}")


def _render_object_ownership():
    st.markdown("#### Object Ownership (Admin Hoarding)")
    st.markdown(
        "Object ownership distribution across admin roles by object type, excluding user and role objects.")
    try:
        object_ownership_query = """
        SELECT
            grantee_name AS role_owner,
            granted_on AS object_type,
            COUNT(*) AS object_count,
            CASE
                WHEN COUNT(*) > 100 THEN 'HIGH_CONCENTRATION'
                WHEN COUNT(*) > 25 THEN 'MODERATE_CONCENTRATION'
                ELSE 'LOW'
            END AS status,
            CASE
                WHEN grantee_name = 'ACCOUNTADMIN' AND COUNT(*) > 10
                THEN 'Transfer ownership to appropriate functional roles'
                WHEN grantee_name = 'SYSADMIN' AND COUNT(*) > 50
                THEN 'Consider delegating to database-specific roles'
                ELSE 'Acceptable'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE deleted_on IS NULL
          AND privilege = 'OWNERSHIP'
          AND grantee_name IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN')
          AND granted_on NOT IN ('USER', 'ROLE')
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
        """
        df = _cached_sql("auth_object_ownership", object_ownership_query)
        if df.empty:
            st.info("No object ownership data available.")
            return

        role_totals = df.groupby('ROLE_OWNER')['OBJECT_COUNT'].sum().to_dict()
        aa = role_totals.get('ACCOUNTADMIN', 0)
        sa = role_totals.get('SYSADMIN', 0)
        sea = role_totals.get('SECURITYADMIN', 0)
        type_totals = df.groupby('OBJECT_TYPE')['OBJECT_COUNT'].sum().sort_values(ascending=False)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Objects Owned by Admin Roles**")
            fig = go.Figure(go.Bar(x=['ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN'], y=[aa, sa, sea],
                                   marker_color=[BRAND_ACCENT, BRAND_PRIMARY, BRAND_PRIMARY_DARK],
                                   text=[aa, sa, sea], textposition='outside'))
            fig.update_layout(height=300, margin=dict(t=20, b=50, l=50, r=30), yaxis_title='Objects')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**Admin-Owned Objects by Type (Top 10)**")
            top_types = type_totals.head(10)
            fig = go.Figure(go.Bar(y=top_types.index.tolist(), x=top_types.values.tolist(), orientation='h',
                                   marker_color=COLOR_LIGHT,
                                   text=[int(v) for v in top_types.values], textposition='outside'))
            fig.update_layout(height=300, margin=dict(t=20, b=50, l=120, r=50), xaxis_title='Count')
            st.plotly_chart(fig, use_container_width=True)

        display_cols = [c for c in ['ROLE_OWNER', 'OBJECT_TYPE', 'OBJECT_COUNT', 'STATUS', 'RECOMMENDATION'] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading object ownership data: {e}")


def _render_privileged_access():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'Users with elevated roles (ACCOUNTADMIN, SECURITYADMIN, SYSADMIN, USERADMIN) and their risk profile.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        WITH privileged_users AS (
            SELECT DISTINCT
                gu.grantee_name AS user_name, gu.role AS privileged_role
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS gu
            WHERE gu.role IN ('ACCOUNTADMIN', 'SECURITYADMIN', 'SYSADMIN', 'USERADMIN')
              AND gu.deleted_on IS NULL
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
                WHEN ud.has_rsa_public_key = 'true' THEN 'Keypair'
                WHEN ud.ext_authn_duo = 'true' THEN 'Password + MFA'
                WHEN ud.has_password = 'true' THEN 'Password Only'
                ELSE 'SSO/Federated'
            END AS auth_method,
            CASE
                WHEN ud.default_role = 'ACCOUNTADMIN' THEN 'CRITICAL'
                WHEN ud.has_password = 'true' AND COALESCE(ud.ext_authn_duo, 'false') = 'false' THEN 'HIGH'
                WHEN DATEDIFF('day', ud.last_success_login, CURRENT_TIMESTAMP()) > 90 THEN 'MODERATE'
                ELSE 'LOW'
            END AS risk_level
        FROM privileged_users pu
        INNER JOIN user_details ud ON pu.user_name = ud.name
        ORDER BY
            CASE pu.privileged_role WHEN 'ACCOUNTADMIN' THEN 1 WHEN 'SECURITYADMIN' THEN 2 WHEN 'SYSADMIN' THEN 3 ELSE 4 END,
            risk_level DESC
        """
        df = _cached_sql("ac_privileged_access", query)
        if df.empty:
            st.info("No privileged users found.")
            return

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Privileged Users", df['USER_NAME'].nunique())
        with col2:
            st.metric("ACCOUNTADMIN Users", len(df[df['PRIVILEGED_ROLE'] == 'ACCOUNTADMIN']))
        with col3:
            high_risk = len(df[df['RISK_LEVEL'].isin(['CRITICAL', 'HIGH'])])
            st.metric("High/Critical Risk", high_risk)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("**Users per Privileged Role**")
            role_counts = df.groupby('PRIVILEGED_ROLE').size().reset_index(name='COUNT').sort_values('COUNT', ascending=False)
            colors = [BRAND_ACCENT, BRAND_PRIMARY, BRAND_SECONDARY, COLOR_LIGHT]
            fig = go.Figure(go.Bar(x=role_counts['PRIVILEGED_ROLE'], y=role_counts['COUNT'],
                                   marker_color=colors[:len(role_counts)],
                                   text=role_counts['COUNT'], textposition='outside'))
            fig.update_layout(height=340, margin=dict(t=30, b=60), yaxis_title='Users')
            st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            st.markdown("**Risk Distribution**")
            if 'RISK_LEVEL' in df.columns:
                risk_counts = df.groupby('RISK_LEVEL').size().reset_index(name='COUNT')
                risk_colors = [SEV_COLORS.get(r, BRAND_PRIMARY) for r in risk_counts['RISK_LEVEL']]
                fig = go.Figure(go.Pie(labels=risk_counts['RISK_LEVEL'], values=risk_counts['COUNT'],
                                       hole=0.35, marker=dict(colors=risk_colors)))
                fig.update_layout(height=340, margin=dict(t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)

        display_cols = [c for c in ['USER_NAME', 'PRIVILEGED_ROLE', 'USER_TYPE', 'DEFAULT_ROLE',
                                     'LAST_SUCCESS_LOGIN', 'DAYS_SINCE_LOGIN', 'AUTH_METHOD', 'RISK_LEVEL']
                        if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")


def _render_role_grant_distribution():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'Roles with the most privilege grants. Roles with >100 grants may benefit from splitting.</div>',
        unsafe_allow_html=True)
    try:
        query = """
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
                WHEN COUNT(*) > 500 THEN 'Consider splitting into more granular roles'
                WHEN COUNT(*) > 100 THEN 'Review for excessive privileges'
                WHEN COUNT(*) > 25 THEN 'Monitor grant growth'
                ELSE 'Acceptable'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE deleted_on IS NULL
          AND grantee_name NOT IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'USERADMIN', 'PUBLIC')
        GROUP BY grantee_name
        HAVING COUNT(*) > 10
        ORDER BY total_grants DESC
        LIMIT 20
        """
        df = _cached_sql("ac_role_grant_dist", query)
        if df.empty:
            st.info("No custom roles with >10 grants found.")
            return

        for c in ['TOTAL_GRANTS', 'DISTINCT_OBJECT_TYPES', 'OWNERSHIP_GRANTS', 'ALL_PRIVILEGE_GRANTS']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

        conc_colors = {'VERY_HIGH': BRAND_ACCENT, 'HIGH': BRAND_SECONDARY, 'MODERATE': COLOR_LIGHT, 'LOW': BRAND_PRIMARY}
        bar_colors = [conc_colors.get(c, BRAND_PRIMARY) for c in df['GRANT_CONCENTRATION']] if 'GRANT_CONCENTRATION' in df.columns else [BRAND_PRIMARY] * len(df)

        fig = go.Figure(go.Bar(
            y=df['ROLE_NAME'], x=df['TOTAL_GRANTS'], orientation='h',
            marker_color=bar_colors,
            text=df['TOTAL_GRANTS'].astype(int), textposition='outside'))
        fig.update_layout(
            title='Top 20 Roles by Grant Count', xaxis_title='Total Grants',
            height=max(300, len(df) * 30 + 80), margin=dict(t=50, l=200, r=40, b=60))
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)

        display_cols = [c for c in ['ROLE_NAME', 'TOTAL_GRANTS', 'DISTINCT_OBJECT_TYPES', 'OWNERSHIP_GRANTS',
                                     'ALL_PRIVILEGE_GRANTS', 'GRANT_CONCENTRATION', 'RECOMMENDATION'] if c in df.columns]
        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")

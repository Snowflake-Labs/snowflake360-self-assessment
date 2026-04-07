_ALL_AC_QUERIES = {
    "auth_role_hygiene": """
        WITH system_roles AS (
            SELECT 'ACCOUNTADMIN' AS name UNION ALL SELECT 'SYSADMIN' UNION ALL
            SELECT 'SECURITYADMIN' UNION ALL SELECT 'USERADMIN' UNION ALL SELECT 'PUBLIC'
        ),
        role_hierarchy AS (
            SELECT
                name AS child_role,
                grantee_name AS parent_role
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE deleted_on IS NULL
              AND privilege = 'USAGE'
              AND granted_on = 'ROLE'
        ),
        role_activity AS (
            SELECT DISTINCT role_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE start_time >= DATEADD('day', -60, CURRENT_TIMESTAMP())
        )

        SELECT
            COUNT(DISTINCT r.name) AS total_roles,
            COUNT(DISTINCT CASE WHEN sr.name IS NULL THEN r.name END) AS custom_roles,

            COUNT(DISTINCT CASE
                WHEN rh_parent.parent_role IS NULL
                     AND r.name NOT IN ('ACCOUNTADMIN')
                THEN r.name
            END) AS orphan_roles,

            COUNT(DISTINCT CASE
                WHEN rh_parent.parent_role IS NULL
                     AND rh_child.child_role IS NULL
                     AND r.name NOT IN ('ACCOUNTADMIN', 'PUBLIC')
                THEN r.name
            END) AS hermit_roles,

            COUNT(DISTINCT a.role_name) AS active_roles_60d,
            COUNT(DISTINCT r.name) - COUNT(DISTINCT a.role_name) AS inactive_roles

        FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES r
        LEFT JOIN system_roles sr ON r.name = sr.name
        LEFT JOIN role_hierarchy rh_parent ON r.name = rh_parent.child_role
        LEFT JOIN role_hierarchy rh_child ON r.name = rh_child.parent_role
        LEFT JOIN role_activity a ON r.name = a.role_name
        WHERE r.deleted_on IS NULL
        """,
    "ac_privileged_access": """
        WITH privileged_users AS (
            SELECT DISTINCT
                gu.grantee_name AS user_name,
                gu.role AS privileged_role
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS gu
            WHERE gu.role IN ('ACCOUNTADMIN', 'SECURITYADMIN', 'SYSADMIN', 'USERADMIN')
              AND gu.deleted_on IS NULL
        ),
        user_details AS (
            SELECT name, type, default_role, last_success_login,
                   has_password, ext_authn_duo, has_rsa_public_key
            FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
            WHERE deleted_on IS NULL
        )
        SELECT
            pu.user_name, pu.privileged_role,
            ud.type AS user_type, ud.default_role, ud.last_success_login,
            DATEDIFF('day', ud.last_success_login, CURRENT_TIMESTAMP()) AS days_since_login,
            CASE
                WHEN ud.default_role = 'ACCOUNTADMIN' THEN 'CRITICAL'
                WHEN ud.has_password = 'true' AND COALESCE(ud.ext_authn_duo, 'false') = 'false' THEN 'HIGH'
                WHEN DATEDIFF('day', ud.last_success_login, CURRENT_TIMESTAMP()) > 90 THEN 'MODERATE'
                ELSE 'LOW'
            END AS risk_level
        FROM privileged_users pu
        INNER JOIN user_details ud ON pu.user_name = ud.name
        ORDER BY
            CASE pu.privileged_role
                WHEN 'ACCOUNTADMIN' THEN 1 WHEN 'SECURITYADMIN' THEN 2
                WHEN 'SYSADMIN' THEN 3 ELSE 4
            END, risk_level DESC
        """,
    "ac_role_grant_dist": """
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
            END AS grant_concentration
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE deleted_on IS NULL
          AND grantee_name NOT IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'USERADMIN', 'PUBLIC')
        GROUP BY grantee_name
        HAVING COUNT(*) > 10
        ORDER BY total_grants DESC
        LIMIT 20
        """,
    "auth_user_inventory": """
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
            COUNT(CASE WHEN type = 'PERSON' OR type IS NULL THEN 1 END) AS type_person_count,
            COUNT(CASE WHEN type = 'SERVICE' OR type = 'LEGACY_SERVICE' THEN 1 END) AS type_service_count,
            COUNT(CASE WHEN last_success_login > DATEADD('day', -60, CURRENT_TIMESTAMP()) THEN 1 END) AS active_users_60d,
            COUNT(CASE WHEN last_success_login <= DATEADD('day', -60, CURRENT_TIMESTAMP()) OR last_success_login IS NULL THEN 1 END) AS inactive_users,
            ROUND(AVG(ug.role_count), 1) AS avg_roles_per_user,
            (SELECT ROUND(AVG(user_count), 1) FROM role_grants) AS avg_users_per_role
        FROM SNOWFLAKE.ACCOUNT_USAGE.USERS u
        LEFT JOIN user_grants ug ON u.name = ug.user_name
        WHERE u.deleted_on IS NULL
        """,
    "auth_security_hygiene": """
        SELECT
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'PASSWORD' THEN user_name END) AS users_using_password,
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'OAUTH_ACCESS_TOKEN' THEN user_name END) AS users_using_oauth,
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'RSA_KEYPAIR' THEN user_name END) AS users_using_keypair,

            (SELECT COUNT(*)
             FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE has_password = 'YES'
               AND ext_authn_duo = 'FALSE'
               AND deleted_on IS NULL) AS unhealthy_password_no_mfa,

            (SELECT COUNT(*)
             FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE has_rsa_public_key = 'YES'
               AND deleted_on IS NULL) AS keypair_users_check_net_policy,

            (SELECT COUNT(*)
             FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE default_role = 'ACCOUNTADMIN'
               AND deleted_on IS NULL) AS default_role_accountadmin,

            (SELECT COUNT(DISTINCT grantee_name)
             FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
             WHERE role IN ('ACCOUNTADMIN', 'SECURITYADMIN')
               AND deleted_on IS NULL) AS users_holding_admin_roles

        FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
        WHERE event_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        """,
    "auth_object_ownership": """
        SELECT
            grantee_name AS role_owner,
            granted_on AS object_type,
            COUNT(*) AS object_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE deleted_on IS NULL
          AND privilege = 'OWNERSHIP'
          AND grantee_name IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN')
          AND granted_on NOT IN ('USER', 'ROLE')
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
        """,
    "authn_auth_activity": """
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
""",
    "authn_credential_hygiene": """
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
""",
    "authn_policy_audit": """
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
""",
    "authn_provisioning_method": """
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
""",
    "authn_findings": """
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
        """,
    "ac_pat_users": """
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
        """,
    "net_policies_data": """
        SELECT
            np.name AS "Policy Name",
            CASE
                WHEN pu.applied_to_account > 0 THEN '🔒 Enforced (Account Level)'
                WHEN pu.applied_to_users > 0 THEN '👤 Enforced (User Level)'
                WHEN pu.applied_to_integrations > 0 THEN '🔌 Enforced (Integration)'
                ELSE '⚠️ Dangling (Not Enforced)'
            END AS "Status",
            np.comment AS "Comment",
            COALESCE(pu.applied_to_users, 0) AS "User Attachments",
            np.created AS "Created Date"
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
        ORDER BY "Status" DESC
        """,
    "ac_net_policy_summary": """
        WITH policy_stats AS (
            SELECT COUNT(*) AS total_policies,
                   COUNT(CASE WHEN deleted IS NULL THEN 1 END) AS active_policies
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES
        ),
        enforcement_stats AS (
            SELECT
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'ACCOUNT' THEN policy_name END) AS account_level_policies,
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'USER' THEN policy_name END) AS user_level_policies,
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'USER' THEN ref_entity_name END) AS users_with_policies
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE policy_kind = 'NETWORK_POLICY'
        )
        SELECT
            ps.total_policies, ps.active_policies,
            es.account_level_policies, es.user_level_policies, es.users_with_policies,
            CASE
                WHEN es.account_level_policies > 0 THEN 'PROTECTED'
                WHEN es.user_level_policies > 0 THEN 'PARTIALLY_PROTECTED'
                ELSE 'UNPROTECTED'
            END AS account_protection_status
        FROM policy_stats ps CROSS JOIN enforcement_stats es
        """,
    "ac_dangling_net_policies": """
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
        """,
    "ac_user_net_coverage": """
        SELECT
            pr.ref_entity_name AS user_name,
            pr.policy_name,
            np.comment AS policy_description
        FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES pr
        INNER JOIN SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES np
            ON pr.policy_name = np.name AND np.deleted IS NULL
        WHERE pr.policy_kind = 'NETWORK_POLICY'
          AND pr.ref_entity_domain = 'USER'
        ORDER BY pr.ref_entity_name
        """,
    "net_rules_data": """
        WITH rule_usage AS (
            SELECT
                network_rule_name,
                COUNT(*) AS distinct_policies_using_rule
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULE_REFERENCES
            GROUP BY 1
        )
        SELECT
            nr.name AS "Rule Name",
            nr.mode AS "Mode (Ingress/Egress)",
            nr.type AS "Type (IPV4/Host/Link)",

            CASE
                WHEN ru.distinct_policies_using_rule > 0 THEN '✅ Attached'
                ELSE '⚠️ Unused (Orphan)'
            END AS "Usage Status",

            COALESCE(ru.distinct_policies_using_rule, 0) AS "Reference Count",
            nr.owner AS "Owned By",
            nr.comment AS "Comment"

        FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES nr
        LEFT JOIN rule_usage ru ON nr.name = ru.network_rule_name
        WHERE nr.deleted IS NULL
        ORDER BY "Usage Status" ASC
        """,
}

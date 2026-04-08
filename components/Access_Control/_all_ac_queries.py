_ALL_AC_QUERIES = {
    "auth_role_hygiene": """
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
    """,
    "auth_security_hygiene": """
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
    """,
    "auth_object_ownership": """
        SELECT
            grantee_name AS role_owner,
            granted_on AS object_type,
            COUNT(*) AS object_count,
            CASE
                WHEN COUNT(*) > 100 THEN 'HIGH_CONCENTRATION'
                WHEN COUNT(*) > 25 THEN 'MODERATE_CONCENTRATION'
                ELSE 'LOW'
            END AS ownership_status,
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
    """,
    "ac_privileged_access": """
        WITH privileged_users AS (
            SELECT DISTINCT grantee_name AS user_name, role AS privileged_role
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
            WHERE role IN ('ACCOUNTADMIN', 'SECURITYADMIN', 'SYSADMIN', 'USERADMIN')
              AND deleted_on IS NULL
        ),
        user_details AS (
            SELECT name, type, default_role, last_success_login,
                   has_password, ext_authn_duo, has_rsa_public_key
            FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
            WHERE deleted_on IS NULL
        )
        SELECT
            pu.user_name,
            pu.privileged_role,
            ud.type AS user_type,
            ud.default_role,
            ud.last_success_login,
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
            CASE pu.privileged_role
                WHEN 'ACCOUNTADMIN' THEN 1 WHEN 'SECURITYADMIN' THEN 2
                WHEN 'SYSADMIN' THEN 3 ELSE 4
            END,
            risk_level DESC
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
            END AS grant_concentration,
            CASE
                WHEN COUNT(CASE WHEN privilege IN ('ALL', 'ALL PRIVILEGES') THEN 1 END) > 0
                    THEN 'Review ALL PRIVILEGES grants'
                WHEN COUNT(CASE WHEN privilege = 'OWNERSHIP' THEN 1 END) > 50
                    THEN 'Consider splitting role responsibilities'
                WHEN COUNT(*) > 100
                    THEN 'Consider more granular role structure'
                ELSE 'Acceptable'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE deleted_on IS NULL
          AND grantee_name NOT IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'USERADMIN', 'PUBLIC')
        GROUP BY 1
        HAVING COUNT(*) > 10
        ORDER BY total_grants DESC
        LIMIT 20
    """,
    "authn_auth_activity": """
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
    """,
    "authn_auth_failures": """
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
    """,
    "authn_credential_hygiene": """
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
    """,
    "authn_pwd_policies": """
        SELECT
            name AS policy_name,
            database_name AS db,
            schema_name AS schema,
            password_max_age_days,
            password_min_length,
            password_max_retries,
            password_lockout_time_mins,
            password_history,
            comment,
            CASE
                WHEN password_max_age_days > 90 OR password_max_age_days IS NULL THEN 'WEAK'
                WHEN password_max_age_days > 60 THEN 'MODERATE'
                ELSE 'STRONG'
            END AS age_rating
        FROM SNOWFLAKE.ACCOUNT_USAGE.PASSWORD_POLICIES
        WHERE deleted IS NULL
    """,
    "authn_session_policies": """
        SELECT
            name AS policy_name,
            database_name AS db,
            schema_name AS schema,
            session_idle_timeout_mins,
            session_ui_idle_timeout_mins,
            comment,
            CASE
                WHEN session_idle_timeout_mins > 60 THEN 'LONG_TIMEOUT'
                WHEN session_idle_timeout_mins > 30 THEN 'MODERATE_TIMEOUT'
                ELSE 'SHORT_TIMEOUT'
            END AS timeout_rating,
            CASE
                WHEN session_idle_timeout_mins > 60 THEN 'Consider reducing idle timeout'
                ELSE 'Acceptable'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.SESSION_POLICIES
        WHERE deleted IS NULL
    """,
    "ac_pat_users": """
        SELECT
            name AS user_name,
            type AS user_type,
            default_role,
            last_success_login,
            DATEDIFF('day', last_success_login, CURRENT_TIMESTAMP()) AS days_since_login,
            CASE
                WHEN last_success_login < DATEADD('day', -90, CURRENT_TIMESTAMP())
                     OR last_success_login IS NULL THEN 'INACTIVE'
                ELSE 'ACTIVE'
            END AS activity_status
        FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
        WHERE deleted_on IS NULL AND has_pat = 'true'
        ORDER BY last_success_login DESC NULLS LAST
    """,
    "authn_provisioning_method": """
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
    """,
    "authn_tc_scanner_data": """
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
    """,
    "ac_net_full_summary": """
        WITH policy_stats AS (
            SELECT
                COUNT(*) AS total_policies,
                COUNT(CASE WHEN deleted IS NULL THEN 1 END) AS active_policies
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES
        ),
        rule_stats AS (
            SELECT
                COUNT(*) AS total_rules,
                COUNT(CASE WHEN deleted IS NULL THEN 1 END) AS active_rules,
                COUNT(CASE WHEN mode = 'INGRESS' AND deleted IS NULL THEN 1 END) AS ingress_rules,
                COUNT(CASE WHEN mode = 'EGRESS' AND deleted IS NULL THEN 1 END) AS egress_rules
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES
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
            rs.total_rules, rs.active_rules, rs.ingress_rules, rs.egress_rules,
            es.account_level_policies, es.user_level_policies,
            es.integration_policies, es.users_with_policies,
            CASE
                WHEN es.account_level_policies > 0 THEN 'PROTECTED'
                WHEN es.user_level_policies > 0 THEN 'PARTIALLY_PROTECTED'
                ELSE 'UNPROTECTED'
            END AS account_protection_status,
            CASE
                WHEN es.account_level_policies = 0
                    THEN 'Consider implementing account-level network policy'
                WHEN rs.egress_rules = 0
                    THEN 'Consider adding egress rules for data exfiltration protection'
                ELSE 'Network security configuration appears adequate'
            END AS recommendation
        FROM policy_stats ps
        CROSS JOIN rule_stats rs
        CROSS JOIN enforcement_stats es
    """,
    "net_policies_data": """
        WITH policy_usage AS (
            SELECT
                policy_name,
                COUNT(CASE WHEN ref_entity_domain = 'ACCOUNT' THEN 1 END) AS applied_to_account,
                COUNT(CASE WHEN ref_entity_domain = 'USER' THEN 1 END) AS applied_to_users,
                COUNT(CASE WHEN ref_entity_domain = 'INTEGRATION' THEN 1 END) AS applied_to_integrations,
                COUNT(*) AS total_attachments
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE policy_kind = 'NETWORK_POLICY'
            GROUP BY policy_name
        )
        SELECT
            np.name AS policy_name,
            np.owner,
            CASE
                WHEN pu.applied_to_account > 0 THEN 'ENFORCED_ACCOUNT_LEVEL'
                WHEN pu.applied_to_users > 0 THEN 'ENFORCED_USER_LEVEL'
                WHEN pu.applied_to_integrations > 0 THEN 'ENFORCED_INTEGRATION'
                ELSE 'DANGLING_NOT_ENFORCED'
            END AS enforcement_status,
            COALESCE(pu.applied_to_account, 0) AS account_attachments,
            COALESCE(pu.applied_to_users, 0) AS user_attachments,
            COALESCE(pu.applied_to_integrations, 0) AS integration_attachments,
            COALESCE(pu.total_attachments, 0) AS total_attachments,
            np.created AS created_date,
            np.comment,
            CASE
                WHEN pu.applied_to_account > 0 THEN 'Account-wide protection active'
                WHEN pu.applied_to_users > 0 THEN 'User-specific restrictions active'
                WHEN pu.applied_to_integrations > 0 THEN 'Integration restrictions active'
                ELSE 'Policy exists but not protecting anything - review or remove'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES np
        LEFT JOIN policy_usage pu ON np.name = pu.policy_name
        WHERE np.deleted IS NULL
        ORDER BY enforcement_status ASC, np.name
    """,
    "ac_dangling_net_policies": """
        WITH policy_usage AS (
            SELECT DISTINCT policy_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE policy_kind = 'NETWORK_POLICY'
        )
        SELECT
            np.name AS policy_name,
            np.owner,
            np.created AS created_date,
            np.comment,
            DATEDIFF('day', np.created, CURRENT_TIMESTAMP()) AS days_since_created,
            CASE
                WHEN DATEDIFF('day', np.created, CURRENT_TIMESTAMP()) > 30 THEN 'STALE_UNUSED'
                ELSE 'RECENTLY_CREATED'
            END AS age_status
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
            SELECT network_rule_name, COUNT(*) AS reference_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULE_REFERENCES
            GROUP BY 1
        )
        SELECT
            nr.name AS rule_name,
            nr.database_name AS db,
            nr.schema_name AS schema,
            nr.mode AS rule_mode,
            nr.type AS rule_type,
            CASE WHEN ru.reference_count > 0 THEN 'ATTACHED' ELSE 'ORPHANED' END AS usage_status,
            COALESCE(ru.reference_count, 0) AS reference_count,
            nr.owner AS owned_by,
            nr.comment,
            CASE
                WHEN ru.reference_count > 0 THEN 'Rule is active in network policy'
                ELSE 'Orphaned rule - consider attaching or removing'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES nr
        LEFT JOIN rule_usage ru ON nr.name = ru.network_rule_name
        WHERE nr.deleted IS NULL
        ORDER BY usage_status ASC, nr.name
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
}

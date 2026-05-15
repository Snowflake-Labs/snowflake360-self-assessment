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

"""
Access Control Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers user, role, grant, and login data from ACCOUNT_USAGE and generates
recommendations via SNOWFLAKE.CORTEX.COMPLETE().
"""

import streamlit as st
import json
from core.config.design_tokens import BRAND_PRIMARY, TEXT_HEADING


def _call_cortex(session, model_name, prompt):
    try:
        safe_prompt = prompt.replace("$$", "$$$$").replace("'", "''")
        result = session.sql(f"""
            SELECT SNOWFLAKE.CORTEX.COMPLETE(
                $${model_name}$$,
                $${safe_prompt}$$
            ) AS RESPONSE
        """).collect()
        if result and len(result) > 0:
            raw = result[0]['RESPONSE']
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    raw = parsed.get("choices", [{}])[0].get("messages", raw) if "choices" in parsed else parsed.get("message", parsed.get("content", raw))
                    if isinstance(raw, dict):
                        raw = raw.get("content", str(raw))
            except (json.JSONDecodeError, TypeError, KeyError, IndexError):
                pass
            return str(raw)
        return "No response from Cortex"
    except Exception as e:
        err_msg = str(e)
        if "deprecated" in err_msg.lower() or "not available" in err_msg.lower() or "not found" in err_msg.lower():
            return "MODEL_UNAVAILABLE"
        return f"Error calling Cortex: {err_msg}"


def _gather_data(session):
    sections = []

    try:
        rows = session.sql("""
            SELECT COUNT(*) AS TOTAL_USERS,
                   SUM(CASE WHEN TYPE = 'PERSON' THEN 1 ELSE 0 END) AS PERSON_USERS,
                   SUM(CASE WHEN TYPE = 'SERVICE' THEN 1 ELSE 0 END) AS SERVICE_USERS,
                   SUM(CASE WHEN TYPE = 'LEGACY_SERVICE' THEN 1 ELSE 0 END) AS LEGACY_SERVICE_USERS,
                   SUM(CASE WHEN HAS_MFA = 'true' THEN 1 ELSE 0 END) AS MFA_ENABLED,
                   SUM(CASE WHEN DISABLED = 'true' THEN 1 ELSE 0 END) AS DISABLED_USERS,
                   SUM(CASE WHEN LAST_SUCCESS_LOGIN IS NULL THEN 1 ELSE 0 END) AS NEVER_LOGGED_IN,
                   SUM(CASE WHEN LAST_SUCCESS_LOGIN < DATEADD('day', -90, CURRENT_TIMESTAMP())
                            AND LAST_SUCCESS_LOGIN IS NOT NULL THEN 1 ELSE 0 END) AS INACTIVE_90D
            FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
            WHERE DELETED_ON IS NULL
        """).collect()
        if rows:
            r = rows[0]
            sections.append(
                f"USERS: total={r['TOTAL_USERS']}, person={r['PERSON_USERS']}, "
                f"service={r['SERVICE_USERS']}, legacy_service={r['LEGACY_SERVICE_USERS']}, "
                f"mfa_enabled={r['MFA_ENABLED']}, disabled={r['DISABLED_USERS']}, "
                f"never_logged_in={r['NEVER_LOGGED_IN']}, inactive_90d={r['INACTIVE_90D']}"
            )
    except Exception as e:
        sections.append(f"USERS: Error - {e}")

    try:
        rows = session.sql("""
            SELECT COUNT(*) AS TOTAL_ROLES,
                   SUM(CASE WHEN OWNER IS NULL THEN 1 ELSE 0 END) AS ORPHAN_ROLES,
                   SUM(CASE WHEN IS_DEFAULT = 'Y' THEN 1 ELSE 0 END) AS SYSTEM_ROLES
            FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES
            WHERE DELETED_ON IS NULL
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"ROLES: total={r['TOTAL_ROLES']}, orphan={r['ORPHAN_ROLES']}, "
                            f"system={r['SYSTEM_ROLES']}")
    except Exception as e:
        sections.append(f"ROLES: Error - {e}")

    try:
        rows = session.sql("""
            SELECT PRIVILEGE,
                   COUNT(*) AS GRANT_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE DELETED_ON IS NULL
            GROUP BY PRIVILEGE
            ORDER BY GRANT_COUNT DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["TOP 10 PRIVILEGES BY GRANT COUNT:"]
            for r in rows:
                lines.append(f"  {r['PRIVILEGE']}: {r['GRANT_COUNT']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"GRANTS_TO_ROLES: Error - {e}")

    try:
        rows = session.sql("""
            SELECT FIRST_AUTHENTICATION_FACTOR AS AUTH_METHOD,
                   COUNT(*) AS LOGIN_COUNT,
                   SUM(CASE WHEN IS_SUCCESS = 'NO' THEN 1 ELSE 0 END) AS FAILURES
            FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
            WHERE EVENT_TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY FIRST_AUTHENTICATION_FACTOR
            ORDER BY LOGIN_COUNT DESC
        """).collect()
        if rows:
            lines = ["LOGIN HISTORY (last 30 days by auth method):"]
            for r in rows:
                lines.append(f"  {r['AUTH_METHOD']}: logins={r['LOGIN_COUNT']}, failures={r['FAILURES']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"LOGIN_HISTORY: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def _gather_individual_data(session, role_name):
    sections = []

    try:
        rows = session.sql(f"""
            SELECT PRIVILEGE, GRANTED_ON, NAME AS OBJECT_NAME,
                   GRANT_OPTION, GRANTED_BY
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE GRANTEE_NAME = '{role_name}'
              AND DELETED_ON IS NULL
            ORDER BY GRANTED_ON, PRIVILEGE
            LIMIT 30
        """).collect()
        if rows:
            lines = [f"GRANTS TO ROLE {role_name} (top 30):"]
            for r in rows:
                lines.append(f"  {r['PRIVILEGE']} ON {r['GRANTED_ON']} {r['OBJECT_NAME']} "
                             f"(grant_option={r['GRANT_OPTION']}, by={r['GRANTED_BY']})")
            sections.append("\n".join(lines))
        else:
            sections.append(f"GRANTS TO ROLE: No grants found for {role_name}")
    except Exception as e:
        sections.append(f"GRANTS TO ROLE: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT GRANTEE_NAME AS CHILD_ROLE, GRANTED_BY
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE NAME = '{role_name}'
              AND PRIVILEGE = 'USAGE'
              AND GRANTED_ON = 'ROLE'
              AND DELETED_ON IS NULL
        """).collect()
        if rows:
            lines = [f"ROLES GRANTED {role_name}:"]
            for r in rows:
                lines.append(f"  {r['CHILD_ROLE']} (by={r['GRANTED_BY']})")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"ROLE GRANTS: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT GRANTEE_NAME AS USER_NAME
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
            WHERE ROLE = '{role_name}'
              AND DELETED_ON IS NULL
            ORDER BY GRANTEE_NAME
            LIMIT 20
        """).collect()
        if rows:
            users = [r['USER_NAME'] for r in rows]
            sections.append(f"USERS WITH ROLE ({len(users)}): {', '.join(users)}")
        else:
            sections.append(f"USERS WITH ROLE: No users assigned to {role_name}")
    except Exception as e:
        sections.append(f"USERS WITH ROLE: Error - {e}")

    try:
        rows = session.sql(f"""
            SELECT PRIVILEGE, COUNT(*) AS CNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE GRANTEE_NAME = '{role_name}'
              AND DELETED_ON IS NULL
            GROUP BY PRIVILEGE
            ORDER BY CNT DESC
            LIMIT 10
        """).collect()
        if rows:
            lines = ["PRIVILEGE DISTRIBUTION:"]
            for r in rows:
                lines.append(f"  {r['PRIVILEGE']}: {r['CNT']}")
            sections.append("\n".join(lines))
    except Exception as e:
        sections.append(f"PRIVILEGE DISTRIBUTION: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_access_control_analysis(entry_actions=None):
    st.markdown("### Access Control Analyzer")
    st.markdown("AI-powered analysis of your authentication, authorization, and security posture.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    model = st.session_state.get("selected_llm", "claude-3-7-sonnet")

    tab_summary, tab_individual, tab_authz, tab_authn, tab_net = st.tabs([
        "Summary Analysis", "Individual Role Analysis",
        "Authorization", "Authentication", "Network Security",
    ])

    with tab_summary:
        cache_key = f"access_control_analysis_result_{model}"

        if cache_key not in st.session_state:
            status_text = st.empty()
            progress_bar = st.empty()
            status_text.text("Gathering data...")
            progress_bar_widget = progress_bar.progress(0)
            progress_bar_widget.progress(0.3)
            data_summary = _gather_data(session)
            status_text.text("Running AI analysis...")
            progress_bar_widget.progress(0.7)
            with st.spinner("Running AI analysis..."):
                prompt = (
                    "You are a Snowflake expert specializing in access control, security, and identity management. "
                    "Analyze the following access control data from SNOWFLAKE.ACCOUNT_USAGE views. "
                    "Format your response using proper Markdown with ## headers, bullet points (- or *), and bold text (**). "
                    "Provide:\n"
                    "1. **Summary Assessment**: Overall security posture\n"
                    "2. **Key Findings**: Authentication risks, authorization gaps, privilege concerns\n"
                    "3. **Recommendations**: Specific steps to harden access controls\n"
                    "4. **Risk Areas**: MFA gaps, orphan roles, excessive privileges, login anomalies\n\n"
                    f"DATA:\n{data_summary}"
                )
                result = _call_cortex(session, model, prompt)
                if result == "MODEL_UNAVAILABLE":
                    st.warning(f"The model **{model}** is deprecated or unavailable. Please select a different LLM on the Home page.")
                    return
                st.session_state[cache_key] = result
            progress_bar.empty()
            status_text.empty()

        if cache_key in st.session_state:
            st.markdown("---")
            raw_text = st.session_state[cache_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

    with tab_authz:
        _render_subtopic_analysis(session, model, "authorization",
            "You are a Snowflake RBAC expert. Analyze the following authorization data. "
            "Focus on: role hierarchy health, orphan roles, excessive GRANT_OPTION usage, "
            "admin-owned objects, privileged access patterns, and role consolidation opportunities. "
            "Format with ## headers and bullet points.",
            _gather_authorization_data)

    with tab_authn:
        _render_subtopic_analysis(session, model, "authentication",
            "You are a Snowflake identity/security expert. Analyze the following authentication data. "
            "Focus on: login failure patterns, MFA adoption gaps, credential hygiene (password age, "
            "weak auth methods), PAT user risks, and session policy coverage. "
            "Format with ## headers and bullet points.",
            _gather_authentication_data)

    with tab_net:
        _render_subtopic_analysis(session, model, "network_security",
            "You are a Snowflake network security expert. Analyze the following network policy data. "
            "Focus on: policy coverage gaps, dangling policies, overly permissive IP rules, "
            "users without network policy protection, and network rule modernization opportunities. "
            "Format with ## headers and bullet points.",
            _gather_network_data)


def _render_subtopic_analysis(session, model, key, system_prompt, gather_fn):
    cache_key = f"ac_{key}_analysis"
    if st.button(f"Run {key.replace('_', ' ').title()} Analysis", key=f"ac_{key}_btn", type="primary"):
        _prog = st.progress(0)
        _stat = st.empty()
        _stat.text("Gathering data...")
        _prog.progress(30)
        data_summary = gather_fn(session)
        _stat.text("Running AI analysis...")
        _prog.progress(70)
        prompt = f"{system_prompt}\n\nDATA:\n{data_summary}"
        result = _call_cortex(session, model, prompt)
        if result == "MODEL_UNAVAILABLE":
            st.warning(f"The model **{model}** is deprecated or unavailable. Please select a different LLM on the Home page.")
            return
        st.session_state[cache_key] = result
        _prog.progress(100)
        _prog.empty()
        _stat.empty()

    if cache_key in st.session_state:
        st.markdown("---")
        raw_text = st.session_state[cache_key]
        if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
            raw_text = raw_text[1:-1]
        st.markdown(raw_text.replace("\\n", "\n").replace("\\t", "  "))


def _gather_authorization_data(session):
    sections = []
    queries = [
        ("ROLE_HIERARCHY", """
            SELECT r.NAME, r.OWNER, r.IS_DEFAULT,
                   COUNT(g.PRIVILEGE) AS GRANT_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES r
            LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES g
              ON g.GRANTEE_NAME = r.NAME AND g.DELETED_ON IS NULL
            WHERE r.DELETED_ON IS NULL
            GROUP BY r.NAME, r.OWNER, r.IS_DEFAULT
            ORDER BY GRANT_COUNT DESC
            LIMIT 20
        """),
        ("GRANT_OPTION_USAGE", """
            SELECT GRANTEE_NAME, COUNT(*) AS WITH_GRANT_OPTION_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE DELETED_ON IS NULL AND GRANT_OPTION = 'true'
            GROUP BY GRANTEE_NAME
            ORDER BY WITH_GRANT_OPTION_COUNT DESC
            LIMIT 15
        """),
        ("ADMIN_OWNED_OBJECTS", """
            SELECT TABLE_CATALOG AS DB, COUNT(*) AS OBJ_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE DELETED IS NULL AND TABLE_OWNER IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN')
            GROUP BY TABLE_CATALOG
            ORDER BY OBJ_COUNT DESC
            LIMIT 10
        """),
    ]
    for label, sql in queries:
        try:
            rows = session.sql(sql).collect()
            if rows:
                lines = [f"{label}:"]
                for r in rows[:15]:
                    lines.append(f"  {dict(r)}")
                sections.append("\n".join(lines))
        except Exception as e:
            sections.append(f"{label}: Error - {e}")
    return "\n\n".join(sections) if sections else "No authorization data gathered."


def _gather_authentication_data(session):
    sections = []
    queries = [
        ("LOGIN_FAILURES_BY_METHOD", """
            SELECT FIRST_AUTHENTICATION_FACTOR, IS_SUCCESS,
                   COUNT(*) AS EVENT_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
            WHERE EVENT_TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
            GROUP BY 1, 2
            ORDER BY EVENT_COUNT DESC
        """),
        ("MFA_ADOPTION", """
            SELECT TYPE,
                   COUNT(*) AS TOTAL,
                   SUM(CASE WHEN HAS_MFA = 'true' THEN 1 ELSE 0 END) AS MFA_ENABLED
            FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
            WHERE DELETED_ON IS NULL
            GROUP BY TYPE
        """),
        ("CREDENTIAL_AGE", """
            SELECT NAME, TYPE, PASSWORD_LAST_SET_TIME,
                   DATEDIFF('day', PASSWORD_LAST_SET_TIME, CURRENT_TIMESTAMP()) AS PASSWORD_AGE_DAYS
            FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
            WHERE DELETED_ON IS NULL AND PASSWORD_LAST_SET_TIME IS NOT NULL
            ORDER BY PASSWORD_AGE_DAYS DESC
            LIMIT 15
        """),
    ]
    for label, sql in queries:
        try:
            rows = session.sql(sql).collect()
            if rows:
                lines = [f"{label}:"]
                for r in rows[:15]:
                    lines.append(f"  {dict(r)}")
                sections.append("\n".join(lines))
        except Exception as e:
            sections.append(f"{label}: Error - {e}")
    return "\n\n".join(sections) if sections else "No authentication data gathered."


def _gather_network_data(session):
    sections = []
    queries = [
        ("NETWORK_POLICIES", """
            SELECT POLICY_NAME, CREATED_ON, POLICY_OWNER
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES
            WHERE DELETED_ON IS NULL
            ORDER BY CREATED_ON DESC
        """),
        ("NETWORK_RULES", """
            SELECT RULE_NAME, DATABASE_NAME, TYPE, MODE, VALUE_LIST
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES
            WHERE DELETED_ON IS NULL
            ORDER BY CREATED_ON DESC
            LIMIT 20
        """),
        ("USER_POLICY_COVERAGE", """
            SELECT
                COUNT(*) AS TOTAL_USERS,
                SUM(CASE WHEN u.HAS_NETWORK_POLICY = 'true' THEN 1 ELSE 0 END) AS WITH_POLICY,
                SUM(CASE WHEN u.HAS_NETWORK_POLICY = 'false' OR u.HAS_NETWORK_POLICY IS NULL THEN 1 ELSE 0 END) AS WITHOUT_POLICY
            FROM SNOWFLAKE.ACCOUNT_USAGE.USERS u
            WHERE u.DELETED_ON IS NULL
        """),
    ]
    for label, sql in queries:
        try:
            rows = session.sql(sql).collect()
            if rows:
                lines = [f"{label}:"]
                for r in rows[:20]:
                    lines.append(f"  {dict(r)}")
                sections.append("\n".join(lines))
        except Exception as e:
            sections.append(f"{label}: Error - {e}")
    return "\n\n".join(sections) if sections else "No network data gathered."

    with tab_individual:
        entity_cache = "ac_entity_list"
        if entity_cache not in st.session_state:
            try:
                rows = session.sql("SELECT NAME AS ROLE_NAME FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES WHERE DELETED_ON IS NULL ORDER BY NAME").collect()
                st.session_state[entity_cache] = [r[0] for r in rows] if rows else []
            except Exception:
                st.session_state[entity_cache] = []

        entities = st.session_state[entity_cache]
        if not entities:
            st.info("No roles found.")
            return

        selected = st.selectbox("Role Name", entities, key="ac_entity_select")

        if st.button("Analyze", key="ac_indiv_btn", type="secondary"):
            indiv_key = f"ac_indiv_{selected}"
            _prog = st.progress(0)
            _stat = st.empty()
            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Gathering data...</p>', unsafe_allow_html=True)
            _prog.progress(30)
            data_summary = _gather_individual_data(session, selected)

            try:
                grant_rows = session.sql(f"""
                    SELECT COUNT(*) AS GRANT_COUNT
                    FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
                    WHERE GRANTEE_NAME = '{selected}' AND DELETED_ON IS NULL
                """).collect()
                grant_count = int(grant_rows[0]['GRANT_COUNT']) if grant_rows else 0
            except Exception:
                grant_count = 0

            try:
                user_rows = session.sql(f"""
                    SELECT COUNT(*) AS USER_COUNT
                    FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
                    WHERE ROLE = '{selected}' AND DELETED_ON IS NULL
                """).collect()
                user_count = int(user_rows[0]['USER_COUNT']) if user_rows else 0
            except Exception:
                user_count = 0

            st.session_state[f"ac_indiv_metrics_{selected}"] = {
                "grants": grant_count, "users": user_count
            }

            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Analyzing with AI...</p>', unsafe_allow_html=True)
            _prog.progress(70)
            prompt = (
                f"You are a Snowflake expert specializing in access control and RBAC. "
                f"Analyze the following data for role '{selected}'. "
                f"Format your response using proper Markdown with ## headers, bullet points, and bold text. "
                f"Provide:\n"
                f"1. **Role Overview**: Purpose and scope of this role\n"
                f"2. **Privilege Analysis**: Distribution and appropriateness of grants\n"
                f"3. **User Assignment**: Who has this role and is it appropriate\n"
                f"4. **Security Concerns**: Over-privilege, grant_option risks, etc.\n"
                f"5. **Recommendations**: Specific improvements for this role\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[indiv_key] = result
            _prog.progress(100)
            _prog.empty()
            _stat.empty()

        indiv_key = f"ac_indiv_{selected}"
        if indiv_key in st.session_state:
            metrics = st.session_state.get(f"ac_indiv_metrics_{selected}", {})
            if metrics:
                c1, c2 = st.columns(2)
                c1.metric("Grants", metrics.get("grants", 0))
                c2.metric("Users Assigned", metrics.get("users", 0))

            st.markdown("---")
            raw_text = st.session_state[indiv_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

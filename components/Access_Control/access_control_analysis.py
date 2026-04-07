"""
Access Control Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers user, role, grant, and login data from ACCOUNT_USAGE and generates
recommendations via SNOWFLAKE.CORTEX.AI_COMPLETE().
"""

import streamlit as st
import json
from core.config.design_tokens import BRAND_PRIMARY, TEXT_HEADING


def _call_cortex(session, model_name, prompt):
    try:
        safe_prompt = prompt.replace("$$", "$$$$").replace("'", "''")
        result = session.sql(f"""
            SELECT SNOWFLAKE.CORTEX.AI_COMPLETE(
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
        return f"Error calling Cortex: {str(e)}"


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

    tab_summary, tab_individual = st.tabs(["Summary Analysis", "Individual Role Analysis"])

    with tab_summary:
        cache_key = "access_control_analysis_result"

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

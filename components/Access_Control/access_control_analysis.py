"""
Access Control Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers user, role, grant, and login data from ACCOUNT_USAGE and generates
recommendations via SNOWFLAKE.CORTEX.AI_COMPLETE().
"""

import streamlit as st
import json

AVAILABLE_MODELS = ["claude-3-7-sonnet", "llama3.1-70b", "mistral-large2"]


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
            return result[0]['RESPONSE']
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


def comp_access_control_analysis(entry_actions=None):
    st.markdown("### Access Control Analyzer")
    st.markdown("AI-powered analysis of your authentication, authorization, and security posture.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        model = st.selectbox("Cortex Model", AVAILABLE_MODELS, key="access_control_model")

    cache_key = "access_control_analysis_result"

    if st.button("Run Analysis", type="primary", key="access_control_run_btn"):
        with st.spinner("Gathering access control data and running AI analysis..."):
            data_summary = _gather_data(session)
            prompt = (
                "You are a Snowflake expert specializing in access control, security, and identity management. "
                "Analyze the following access control data from SNOWFLAKE.ACCOUNT_USAGE views. "
                "Provide:\n"
                "1. **Summary Assessment**: Overall security posture\n"
                "2. **Key Findings**: Authentication risks, authorization gaps, privilege concerns\n"
                "3. **Recommendations**: Specific steps to harden access controls\n"
                "4. **Risk Areas**: MFA gaps, orphan roles, excessive privileges, login anomalies\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[cache_key] = result

    if cache_key in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state[cache_key])

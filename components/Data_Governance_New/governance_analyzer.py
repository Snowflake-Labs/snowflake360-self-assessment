"""
Data Governance Analyzer - AI-powered analysis using Snowflake Cortex.
Gathers policy, tagging, and object metadata from ACCOUNT_USAGE and generates
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
            SELECT POLICY_KIND,
                   COUNT(DISTINCT POLICY_NAME) AS POLICY_COUNT,
                   COUNT(*) AS TOTAL_REFERENCES
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE DELETED IS NULL
            GROUP BY POLICY_KIND
            ORDER BY TOTAL_REFERENCES DESC
        """).collect()
        if rows:
            lines = ["POLICY REFERENCES:"]
            for r in rows:
                lines.append(f"  {r['POLICY_KIND']}: policies={r['POLICY_COUNT']}, references={r['TOTAL_REFERENCES']}")
            sections.append("\n".join(lines))
        else:
            sections.append("POLICY REFERENCES: No policies found")
    except Exception as e:
        sections.append(f"POLICY_REFERENCES: Error - {e}")

    try:
        rows = session.sql("""
            SELECT COUNT(DISTINCT TAG_NAME) AS TOTAL_TAGS,
                   COUNT(DISTINCT TAG_SCHEMA) AS TAG_SCHEMAS,
                   COUNT(*) AS TOTAL_TAG_ASSIGNMENTS,
                   COUNT(DISTINCT OBJECT_NAME) AS TAGGED_OBJECTS
            FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
            WHERE DELETED IS NULL
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"TAG REFERENCES: tags={r['TOTAL_TAGS']}, schemas={r['TAG_SCHEMAS']}, "
                            f"assignments={r['TOTAL_TAG_ASSIGNMENTS']}, tagged_objects={r['TAGGED_OBJECTS']}")
    except Exception as e:
        sections.append(f"TAG_REFERENCES: Error - {e}")

    try:
        rows = session.sql("""
            SELECT COUNT(*) AS TOTAL_TABLES,
                   SUM(CASE WHEN IS_TRANSIENT = 'YES' THEN 1 ELSE 0 END) AS TRANSIENT_TABLES,
                   COUNT(DISTINCT TABLE_SCHEMA) AS SCHEMA_COUNT,
                   COUNT(DISTINCT TABLE_CATALOG) AS DB_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE DELETED IS NULL
        """).collect()
        if rows:
            r = rows[0]
            sections.append(f"TABLES: total={r['TOTAL_TABLES']}, transient={r['TRANSIENT_TABLES']}, "
                            f"schemas={r['SCHEMA_COUNT']}, databases={r['DB_COUNT']}")
    except Exception as e:
        sections.append(f"TABLES: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_governance_analyzer(entry_actions=None):
    st.markdown("### Data Governance Analyzer")
    st.markdown("AI-powered analysis of your data governance posture including policies, tagging, and classification.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        model = st.selectbox("Cortex Model", AVAILABLE_MODELS, key="governance_model")

    cache_key = "governance_analysis_result"

    if st.button("Run Analysis", type="primary", key="governance_run_btn"):
        with st.spinner("Gathering governance data and running AI analysis..."):
            data_summary = _gather_data(session)
            prompt = (
                "You are a Snowflake expert specializing in data governance, security policies, and compliance. "
                "Analyze the following governance data from SNOWFLAKE.ACCOUNT_USAGE views. "
                "Provide:\n"
                "1. **Summary Assessment**: Overall governance maturity and posture\n"
                "2. **Key Findings**: Policy coverage gaps, tagging completeness, notable patterns\n"
                "3. **Recommendations**: Specific steps to improve governance posture\n"
                "4. **Risk Areas**: Unprotected data, missing policies, compliance concerns\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[cache_key] = result

    if cache_key in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state[cache_key])

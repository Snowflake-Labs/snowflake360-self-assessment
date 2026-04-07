import streamlit as st
import json
from core.config.design_tokens import BRAND_PRIMARY, TEXT_HEADING

GOVERNANCE_ENTITIES = [
    "CLASSIFICATION: Classification & Sensitive Data",
    "LINEAGE_GOVERNANCE: Lineage & Downstream Protection",
    "POLICY_PROTECTION: Policy & Data Protection",
    "TAG_COVERAGE: Tag Coverage Health",
    "TAG_DESIGN: Tag Design & Hygiene",
]


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


def _gather_data(session, progress_bar=None, status_text=None):
    sections = []
    queries = [
        ("Policy References", """
            SELECT POLICY_KIND,
                   COUNT(DISTINCT POLICY_NAME) AS POLICY_COUNT,
                   COUNT(*) AS TOTAL_REFERENCES
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE DELETED IS NULL
            GROUP BY POLICY_KIND
            ORDER BY TOTAL_REFERENCES DESC
        """),
        ("Tag References", """
            SELECT COUNT(DISTINCT TAG_NAME) AS TOTAL_TAGS,
                   COUNT(DISTINCT TAG_SCHEMA) AS TAG_SCHEMAS,
                   COUNT(*) AS TOTAL_TAG_ASSIGNMENTS,
                   COUNT(DISTINCT OBJECT_NAME) AS TAGGED_OBJECTS
            FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
            WHERE DELETED IS NULL
        """),
        ("Table Inventory", """
            SELECT COUNT(*) AS TOTAL_TABLES,
                   SUM(CASE WHEN IS_TRANSIENT = 'YES' THEN 1 ELSE 0 END) AS TRANSIENT_TABLES,
                   COUNT(DISTINCT TABLE_SCHEMA) AS SCHEMA_COUNT,
                   COUNT(DISTINCT TABLE_CATALOG) AS DB_COUNT
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE DELETED IS NULL
        """),
    ]
    total = len(queries) + 1
    for i, (label, sql) in enumerate(queries):
        if status_text is not None:
            status_text.text(f"Gathering data... ({i+1}/{total-1} queries: {label})")
        if progress_bar is not None:
            progress_bar.progress((i + 1) / total)
        try:
            rows = session.sql(sql).collect()
            if label == "Policy References" and rows:
                lines = ["POLICY REFERENCES:"]
                for r in rows:
                    lines.append(f"  {r['POLICY_KIND']}: policies={r['POLICY_COUNT']}, references={r['TOTAL_REFERENCES']}")
                sections.append("\n".join(lines))
            elif label == "Tag References" and rows:
                r = rows[0]
                sections.append(f"TAG REFERENCES: tags={r['TOTAL_TAGS']}, schemas={r['TAG_SCHEMAS']}, "
                                f"assignments={r['TOTAL_TAG_ASSIGNMENTS']}, tagged_objects={r['TAGGED_OBJECTS']}")
            elif label == "Table Inventory" and rows:
                r = rows[0]
                sections.append(f"TABLES: total={r['TOTAL_TABLES']}, transient={r['TRANSIENT_TABLES']}, "
                                f"schemas={r['SCHEMA_COUNT']}, databases={r['DB_COUNT']}")
        except Exception as e:
            sections.append(f"{label}: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def _gather_individual_data(session, entity_key):
    sections = []

    if entity_key == "CLASSIFICATION":
        try:
            rows = session.sql("""
                SELECT TAG_NAME, COUNT(*) AS REF_COUNT,
                       COUNT(DISTINCT OBJECT_DATABASE) AS DB_COUNT
                FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
                WHERE DELETED IS NULL
                  AND (TAG_NAME ILIKE '%CLASSIF%' OR TAG_NAME ILIKE '%SENSITIVE%'
                       OR TAG_NAME ILIKE '%PII%' OR TAG_NAME ILIKE '%PRIVACY%'
                       OR TAG_SCHEMA = 'CORE' OR TAG_DATABASE = 'SNOWFLAKE')
                GROUP BY TAG_NAME
                ORDER BY REF_COUNT DESC
                LIMIT 20
            """).collect()
            if rows:
                lines = ["CLASSIFICATION TAG REFERENCES:"]
                for r in rows:
                    lines.append(f"  {r['TAG_NAME']}: refs={r['REF_COUNT']}, databases={r['DB_COUNT']}")
                sections.append("\n".join(lines))
            else:
                sections.append("CLASSIFICATION: No classification-related tags found")
        except Exception as e:
            sections.append(f"CLASSIFICATION: Error - {e}")

        try:
            rows = session.sql("""
                SELECT COUNT(DISTINCT TABLE_CATALOG || '.' || TABLE_SCHEMA || '.' || TABLE_NAME) AS TOTAL_TABLES,
                       COUNT(DISTINCT CASE WHEN tr.TAG_NAME IS NOT NULL THEN t.TABLE_CATALOG || '.' || t.TABLE_SCHEMA || '.' || t.TABLE_NAME END) AS TAGGED_TABLES
                FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES t
                LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES tr
                  ON t.TABLE_CATALOG = tr.OBJECT_DATABASE
                  AND t.TABLE_SCHEMA = tr.OBJECT_SCHEMA
                  AND t.TABLE_NAME = tr.OBJECT_NAME
                  AND tr.DELETED IS NULL
                WHERE t.DELETED IS NULL
                  AND t.TABLE_TYPE = 'BASE TABLE'
            """).collect()
            if rows:
                r = rows[0]
                sections.append(f"CLASSIFICATION COVERAGE: total_tables={r['TOTAL_TABLES']}, tagged_tables={r['TAGGED_TABLES']}")
        except Exception as e:
            sections.append(f"CLASSIFICATION COVERAGE: Error - {e}")

    elif entity_key == "LINEAGE_GOVERNANCE":
        try:
            rows = session.sql("""
                SELECT REFERENCING_OBJECT_DOMAIN, REFERENCED_OBJECT_DOMAIN,
                       COUNT(*) AS DEP_COUNT
                FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES
                GROUP BY REFERENCING_OBJECT_DOMAIN, REFERENCED_OBJECT_DOMAIN
                ORDER BY DEP_COUNT DESC
                LIMIT 15
            """).collect()
            if rows:
                lines = ["OBJECT DEPENDENCIES:"]
                for r in rows:
                    lines.append(f"  {r['REFERENCING_OBJECT_DOMAIN']} -> {r['REFERENCED_OBJECT_DOMAIN']}: count={r['DEP_COUNT']}")
                sections.append("\n".join(lines))
            else:
                sections.append("LINEAGE: No object dependencies found")
        except Exception as e:
            sections.append(f"LINEAGE: Error - {e}")

    elif entity_key == "POLICY_PROTECTION":
        try:
            rows = session.sql("""
                SELECT POLICY_KIND, POLICY_NAME,
                       REF_DATABASE_NAME, REF_SCHEMA_NAME, REF_ENTITY_NAME,
                       REF_COLUMN_NAME
                FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
                WHERE DELETED IS NULL
                ORDER BY POLICY_KIND, POLICY_NAME
                LIMIT 30
            """).collect()
            if rows:
                lines = ["POLICY REFERENCES DETAIL:"]
                for r in rows:
                    col = r['REF_COLUMN_NAME'] or 'N/A'
                    lines.append(f"  {r['POLICY_KIND']}/{r['POLICY_NAME']} -> "
                                 f"{r['REF_DATABASE_NAME']}.{r['REF_SCHEMA_NAME']}.{r['REF_ENTITY_NAME']} (col={col})")
                sections.append("\n".join(lines))
            else:
                sections.append("POLICY PROTECTION: No policy references found")
        except Exception as e:
            sections.append(f"POLICY PROTECTION: Error - {e}")

    elif entity_key == "TAG_COVERAGE":
        try:
            rows = session.sql("""
                SELECT OBJECT_DATABASE,
                       COUNT(DISTINCT OBJECT_NAME) AS TAGGED_OBJECTS,
                       COUNT(DISTINCT TAG_NAME) AS TAGS_USED,
                       COUNT(*) AS TOTAL_ASSIGNMENTS
                FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
                WHERE DELETED IS NULL
                GROUP BY OBJECT_DATABASE
                ORDER BY TAGGED_OBJECTS DESC
                LIMIT 15
            """).collect()
            if rows:
                lines = ["TAG COVERAGE BY DATABASE:"]
                for r in rows:
                    lines.append(f"  {r['OBJECT_DATABASE']}: objects={r['TAGGED_OBJECTS']}, "
                                 f"tags_used={r['TAGS_USED']}, assignments={r['TOTAL_ASSIGNMENTS']}")
                sections.append("\n".join(lines))
            else:
                sections.append("TAG COVERAGE: No tag assignments found")
        except Exception as e:
            sections.append(f"TAG COVERAGE: Error - {e}")

    elif entity_key == "TAG_DESIGN":
        try:
            rows = session.sql("""
                SELECT TAG_DATABASE, TAG_SCHEMA, TAG_NAME,
                       COUNT(*) AS USAGE_COUNT,
                       COUNT(DISTINCT OBJECT_DATABASE) AS DB_SPREAD
                FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
                WHERE DELETED IS NULL
                GROUP BY TAG_DATABASE, TAG_SCHEMA, TAG_NAME
                ORDER BY USAGE_COUNT DESC
                LIMIT 20
            """).collect()
            if rows:
                lines = ["TAG USAGE PATTERNS:"]
                for r in rows:
                    lines.append(f"  {r['TAG_DATABASE']}.{r['TAG_SCHEMA']}.{r['TAG_NAME']}: "
                                 f"usage={r['USAGE_COUNT']}, db_spread={r['DB_SPREAD']}")
                sections.append("\n".join(lines))
            else:
                sections.append("TAG DESIGN: No tags found")
        except Exception as e:
            sections.append(f"TAG DESIGN: Error - {e}")

    return "\n\n".join(sections) if sections else "No data could be gathered."


def comp_governance_analyzer(entry_actions=None):
    st.markdown("### Data Governance Analyzer")
    st.markdown("AI-powered analysis of your data governance posture including policies, tagging, and classification.")

    session = st.session_state.get("session")
    if not session:
        st.warning("No active Snowflake session found.")
        return

    model = st.session_state.get("selected_llm", "claude-3-7-sonnet")

    tab_summary, tab_individual = st.tabs(["Summary Analysis", "Individual Governance Analysis"])

    with tab_summary:
        cache_key = "governance_analysis_result"

        if cache_key not in st.session_state:
            status_text = st.empty()
            progress_bar = st.empty()
            status_text.markdown(
                f'<p style="color: {TEXT_HEADING}; font-weight: 600;">Loading Data Governance Analyzer...</p>',
                unsafe_allow_html=True
            )
            progress_bar_widget = progress_bar.progress(0)
            data_summary = _gather_data(session, progress_bar=progress_bar_widget, status_text=status_text)
            status_text.text("Running AI analysis...")
            progress_bar_widget.progress(0.9)
            with st.spinner("Running AI analysis..."):
                prompt = (
                    "You are a Snowflake expert specializing in data governance, security policies, and compliance. "
                    "Analyze the following governance data from SNOWFLAKE.ACCOUNT_USAGE views. "
                    "Format your response using proper Markdown with headers (##), bullet points (- or *), "
                    "and bold text (**). Structure your analysis as follows:\n\n"
                    "## Summary Assessment\nOverall governance maturity and posture\n\n"
                    "## Key Findings\n- Policy coverage gaps, tagging completeness, notable patterns (use bullet points)\n\n"
                    "## Recommendations\n- Specific steps to improve governance posture (use numbered list)\n\n"
                    "## Risk Areas\n- Unprotected data, missing policies, compliance concerns (use bullet points)\n\n"
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
        selected = st.selectbox("Governance Entity / Component", GOVERNANCE_ENTITIES, key="gov_entity_select")
        entity_key = selected.split(":")[0].strip()

        if st.button("Analyze", key="gov_indiv_btn", type="secondary"):
            indiv_key = f"gov_indiv_{entity_key}"
            _prog = st.progress(0)
            _stat = st.empty()
            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Gathering data...</p>', unsafe_allow_html=True)
            _prog.progress(30)
            data_summary = _gather_individual_data(session, entity_key)

            entity_label = selected.split(":")[1].strip() if ":" in selected else selected
            _stat.markdown('<p style="color: #003D73; font-weight: 600;">Analyzing with AI...</p>', unsafe_allow_html=True)
            _prog.progress(70)
            prompt = (
                f"You are a Snowflake expert specializing in data governance. "
                f"Analyze the following data for the governance component '{entity_label}'. "
                f"Format your response using proper Markdown with ## headers, bullet points, and bold text. "
                f"Provide:\n"
                f"1. **Component Health**: Current state of this governance area\n"
                f"2. **Coverage Analysis**: How well this area is covered across the account\n"
                f"3. **Gaps & Risks**: Missing protections or governance gaps\n"
                f"4. **Recommendations**: Specific actions to improve this governance area\n\n"
                f"DATA:\n{data_summary}"
            )
            result = _call_cortex(session, model, prompt)
            st.session_state[indiv_key] = result
            _prog.progress(100)
            _prog.empty()
            _stat.empty()

        indiv_key = f"gov_indiv_{entity_key}"
        if indiv_key in st.session_state:
            st.markdown("---")
            raw_text = st.session_state[indiv_key]
            if isinstance(raw_text, str) and raw_text.startswith('"') and raw_text.endswith('"'):
                raw_text = raw_text[1:-1]
            clean_text = raw_text.replace("\\n", "\n").replace("\\t", "  ")
            st.markdown(clean_text)

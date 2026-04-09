import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'


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


_SQL_CS_OVERHEAD = """
WITH pattern_summary AS (
    SELECT 'SHOW Commands' AS pattern, SUM(credits_used_cloud_services) AS credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP()) AND query_type = 'SHOW'
    UNION ALL
    SELECT 'Short Queries (<100ms)', SUM(credits_used_cloud_services)
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP()) AND total_elapsed_time < 100
    UNION ALL
    SELECT 'Metadata Scans', SUM(credits_used_cloud_services)
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND (schema_name = 'INFORMATION_SCHEMA' OR query_text ILIKE '%INFORMATION_SCHEMA%')
    UNION ALL
    SELECT 'Single-Row Inserts', SUM(credits_used_cloud_services)
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND query_type = 'INSERT' AND rows_produced = 1
)
SELECT pattern AS PATTERN,
       ROUND(credits, 4) AS CLOUD_SERVICES_CREDITS_30D,
       ROUND(credits * 3.00, 2) AS ESTIMATED_COST_USD,
       ROUND(RATIO_TO_REPORT(credits) OVER () * 100, 1) AS PCT_OF_OVERHEAD
FROM pattern_summary WHERE credits > 0
ORDER BY credits DESC
"""

_SQL_COPY_SUMMARY = """
WITH copy_q AS (
    SELECT query_parameterized_hash, MIN(query_text) AS sample_text,
           COUNT(*) AS executions, SUM(credits_used_cloud_services) AS cs_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time > DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND REGEXP_LIKE(query_text, '^\\\\s*COPY\\\\s+INTO\\\\b', 'i')
    GROUP BY query_parameterized_hash
)
SELECT SUM(executions) AS TOTAL_COPY_COMMANDS_30D,
       COUNT(*) AS DISTINCT_COPY_PATTERNS,
       ROUND(SUM(cs_credits), 4) AS TOTAL_CLOUD_SERVICES_CREDITS
FROM copy_q
"""

_SQL_COPY_POOR_SELECTIVITY = """
SELECT
    SUBSTR(query_text, 1, 120) AS QUERY_PATTERN,
    COUNT(*) AS EXECUTION_COUNT,
    SUM(rows_produced) AS TOTAL_ROWS_LOADED,
    ROUND(AVG(compilation_time), 0) AS AVG_COMPILE_MS,
    ROUND(AVG(execution_time), 0) AS AVG_EXECUTION_MS,
    ROUND(SUM(credits_used_cloud_services), 4) AS CLOUD_SERVICES_CREDITS,
    CASE WHEN AVG(compilation_time) > 5000 THEN 'HIGH_FILE_LISTING_OVERHEAD'
         WHEN COUNT(*) > 100 AND SUM(rows_produced) < 1000 THEN 'REDUNDANT_PATTERN'
         ELSE 'INVESTIGATE' END AS ISSUE_TYPE
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type = 'COPY' AND execution_time > 1000 AND rows_produced < 100
GROUP BY SUBSTR(query_text, 1, 120)
ORDER BY EXECUTION_COUNT DESC
LIMIT 10
"""

_SQL_COPY_PATTERNS = """
WITH copy_q AS (
    SELECT query_parameterized_hash, MIN(query_text) AS sample_text,
           COUNT(*) AS executions, SUM(credits_used_cloud_services) AS cs_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time > DATEADD('day', -30, CURRENT_TIMESTAMP())
      AND REGEXP_LIKE(query_text, '^\\\\s*COPY\\\\s+INTO\\\\b', 'i')
    GROUP BY query_parameterized_hash
)
SELECT SUBSTR(sample_text, 1, 80) AS PATTERN_SHORT,
       executions AS EXECUTION_COUNT,
       ROUND(cs_credits, 4) AS CS_CREDITS,
       SUBSTR(sample_text, 1, 150) AS QUERY_PATTERN
FROM copy_q ORDER BY executions DESC LIMIT 10
"""

_SQL_SHORT_QUERIES = """
SELECT
    SUBSTR(REGEXP_REPLACE(q.query_text, '\\\\b\\\\d+\\\\b', '?'), 1, 80) AS QUERY_TEMPLATE_SHORT,
    q.user_name AS USER_NAME,
    s.client_application_id AS CLIENT_TOOL,
    COUNT(*) AS EXECUTION_COUNT,
    ROUND(SUM(q.credits_used_cloud_services), 4) AS CLOUD_SERVICES_CREDITS,
    'Short Queries (<100ms)' AS PATTERN_TYPE,
    REGEXP_REPLACE(q.query_text, '\\\\b\\\\d+\\\\b', '?') AS QUERY_TEMPLATE
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
JOIN SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND q.total_elapsed_time < 100 AND q.query_type = 'SELECT'
GROUP BY ALL
HAVING COUNT(*) > 1000
ORDER BY EXECUTION_COUNT DESC
LIMIT 10
"""

_SQL_SHOW_COMMANDS = """
SELECT
    q.query_type AS QUERY_TYPE,
    SUBSTR(q.query_text, 1, 80) AS COMMAND_TYPE,
    q.user_name AS USER_NAME,
    s.client_application_id AS CLIENT_TOOL,
    COUNT(*) AS EXECUTION_COUNT
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
JOIN SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND q.query_type = 'SHOW'
GROUP BY ALL
ORDER BY EXECUTION_COUNT DESC
LIMIT 10
"""

_SQL_INFO_SCHEMA = """
SELECT
    SUBSTR(q.query_text, 1, 80) AS QUERY_PREVIEW_SHORT,
    q.user_name AS USER_NAME,
    s.client_application_id AS CLIENT_TOOL,
    COUNT(*) AS EXECUTION_COUNT,
    ROUND(AVG(q.compilation_time), 0) AS AVG_COMPILE_MS,
    SUBSTR(q.query_text, 1, 100) AS QUERY_PREVIEW
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
JOIN SNOWFLAKE.ACCOUNT_USAGE.SESSIONS s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (q.schema_name = 'INFORMATION_SCHEMA' OR q.query_text ILIKE '%INFORMATION_SCHEMA%')
GROUP BY ALL
ORDER BY EXECUTION_COUNT DESC
LIMIT 10
"""

_SQL_SINGLE_ROW_INSERTS = """
SELECT
    REGEXP_SUBSTR(query_text, 'INSERT INTO ([a-zA-Z0-9_.]+)', 1, 1, 'i', 1) AS TARGET_TABLE,
    user_name AS USER_NAME,
    COUNT(*) AS INSERT_COUNT,
    SUM(rows_produced) AS TOTAL_ROWS_LOADED,
    ROUND(SUM(credits_used_cloud_services), 4) AS CLOUD_SERVICES_CREDITS,
    CASE WHEN COUNT(*) > 1000 THEN 'CRITICAL_BATCH_IMMEDIATELY'
         WHEN COUNT(*) > 100 THEN 'HIGH_CONSIDER_BATCHING'
         ELSE 'MODERATE' END AS SEVERITY
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type = 'INSERT' AND rows_produced = 1
GROUP BY REGEXP_SUBSTR(query_text, 'INSERT INTO ([a-zA-Z0-9_.]+)', 1, 1, 'i', 1), user_name
ORDER BY INSERT_COUNT DESC
LIMIT 10
"""

_SQL_DDL_SUMMARY = """
WITH ddl_q AS (
    SELECT query_parameterized_hash, MIN(query_text) AS sample_text,
           COUNT(*) AS executions, SUM(credits_used_cloud_services) AS cs_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
      AND REGEXP_LIKE(query_text, '^\\\\s*(CREATE|ALTER|DROP)\\\\b', 'i')
    GROUP BY query_parameterized_hash
)
SELECT SUM(executions) AS TOTAL_DDL_30D,
       COUNT(*) AS DISTINCT_DDL_PATTERNS,
       ROUND(SUM(cs_credits), 4) AS TOTAL_CS_CREDITS
FROM ddl_q
"""

_SQL_CLONE_OPS = """
SELECT query_type AS QUERY_TYPE,
       REGEXP_SUBSTR(query_text, ' (TABLE|VIEW|SCHEMA|DATABASE) [IF EXISTS ]*([a-zA-Z0-9_.]+)', 1, 1, 'i', 2) AS OBJECT_NAME,
       user_name AS USER_NAME,
       COUNT(*) AS OPERATION_COUNT,
       ROUND(SUM(credits_used_cloud_services), 4) AS CLOUD_SERVICES_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type IN ('CREATE_TABLE', 'DROP_TABLE', 'CREATE_VIEW', 'ALTER_TABLE', 'RESTORE', 'CREATE_TABLE_AS_SELECT')
  AND query_text ILIKE '%CLONE%'
GROUP BY ALL
ORDER BY OPERATION_COUNT DESC
LIMIT 10
"""

_SQL_CLONE_SUMMARY = """
WITH clone_q AS (
    SELECT query_parameterized_hash, MIN(query_text) AS sample_text,
           COUNT(*) AS executions, SUM(credits_used_cloud_services) AS cs_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
      AND REGEXP_LIKE(query_text, '\\\\bCLONE\\\\b', 'i')
    GROUP BY query_parameterized_hash
)
SELECT SUM(executions) AS TOTAL_CLONE_30D,
       COUNT(*) AS DISTINCT_CLONE_PATTERNS,
       ROUND(SUM(cs_credits), 4) AS TOTAL_CS_CREDITS
FROM clone_q
"""

_SQL_COMPLEX_QUERIES = """
SELECT query_id AS QUERY_ID,
       query_type AS QUERY_TYPE,
       user_name AS USER_NAME,
       warehouse_name AS WAREHOUSE_NAME,
       LENGTH(query_text) AS SQL_CHARACTER_LENGTH,
       compilation_time AS COMPILE_MS,
       execution_time AS EXEC_MS,
       ROUND(compilation_time / NULLIF(total_elapsed_time, 0) * 100, 1) AS PCT_TIME_COMPILING,
       ROUND(credits_used_cloud_services, 6) AS CLOUD_SERVICES_CREDITS,
       CASE WHEN compilation_time > 30000 THEN 'CRITICAL_SIMPLIFY_QUERY'
            WHEN compilation_time > 10000 THEN 'HIGH_REVIEW_COMPLEXITY'
            ELSE 'MODERATE' END AS SEVERITY
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND compilation_time > 5000
ORDER BY compilation_time DESC
LIMIT 10
"""

_ALL_OPT_QUERIES = {
    "fo_cs_overhead": _SQL_CS_OVERHEAD,
    "fo_copy_summary": _SQL_COPY_SUMMARY,
    "fo_copy_poor_sel": _SQL_COPY_POOR_SELECTIVITY,
    "fo_copy_patterns": _SQL_COPY_PATTERNS,
    "fo_short_queries": _SQL_SHORT_QUERIES,
    "fo_show_commands": _SQL_SHOW_COMMANDS,
    "fo_info_schema": _SQL_INFO_SCHEMA,
    "fo_single_row_inserts": _SQL_SINGLE_ROW_INSERTS,
    "fo_ddl_summary": _SQL_DDL_SUMMARY,
    "fo_clone_ops": _SQL_CLONE_OPS,
    "fo_clone_summary": _SQL_CLONE_SUMMARY,
    "fo_complex_queries": _SQL_COMPLEX_QUERIES,
}


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch():
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_OPT_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_run_query_thread, session, k, sql): k for k, sql in needed.items()}
        for f in as_completed(futures):
            key, df, _ = f.result()
            st.session_state[key] = df


def comp_finops_optimization(entry_actions=None):
    try:
        _prefetch()

        with st.expander("Cloud Services Overhead Summary (30d)", expanded=True):
            _render_cs_overhead()

        with st.expander("Inefficient COPY Commands (Poor Selectivity, 30d)", expanded=True):
            _render_copy_commands()

        with st.expander("High-Frequency Short Queries (<100ms, >1000 executions, 30d)", expanded=True):
            _render_short_queries()

        with st.expander("High-Frequency SHOW Commands (30d)", expanded=True):
            _render_show_commands()

        with st.expander("INFORMATION_SCHEMA Metadata Scans (30d)", expanded=True):
            _render_info_schema()

        with st.expander("Single-Row INSERT Anti-Pattern (30d)", expanded=True):
            _render_single_row_inserts()

        with st.expander("High-Frequency DDL & Clone Operations (30d)", expanded=True):
            _render_ddl_and_clones()

        with st.expander("Complex SQL Compilation Overhead (>5s compile time, 30d)", expanded=True):
            _render_complex_queries()

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid {_CA}; padding: 10px;">'
            f'Component Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_cs_overhead():
    df = _cached_sql("fo_cs_overhead", _SQL_CS_OVERHEAD)
    if df.empty:
        st.markdown(
            '<div style="background-color: #EAF8F0; border-left: 6px solid #29B5E8; padding: 10px;">'
            '\u2705 No significant cloud services overhead patterns detected.</div>',
            unsafe_allow_html=True)
        return
    st.dataframe(df, use_container_width=True)


def _render_copy_commands():
    df_summary = _cached_sql("fo_copy_summary", _SQL_COPY_SUMMARY)
    c1, c2, c3 = st.columns(3)
    if not df_summary.empty:
        r = df_summary.iloc[0]
        with c1:
            val = r.get('TOTAL_COPY_COMMANDS_30D')
            st.metric("Total COPY Commands (30d)", f"{int(val):,}" if pd.notna(val) and val else "N/A")
        with c2:
            val = r.get('DISTINCT_COPY_PATTERNS')
            st.metric("Distinct COPY Patterns", f"{int(val):,}" if pd.notna(val) and val else "0")
        with c3:
            val = r.get('TOTAL_CLOUD_SERVICES_CREDITS')
            st.metric("Cloud Services Credits", f"{float(val):.4f}" if pd.notna(val) and val else "N/A")

    df_poor = _cached_sql("fo_copy_poor_sel", _SQL_COPY_POOR_SELECTIVITY)
    if not df_poor.empty and 'ISSUE_TYPE' in df_poor.columns:
        st.markdown("##### Issue Type Distribution \u2014 Inefficient COPY Commands")
        issue_counts = df_poor.groupby("ISSUE_TYPE").size().reset_index(name="COUNT")
        fig = go.Figure(data=[go.Pie(
            labels=issue_counts["ISSUE_TYPE"].tolist(),
            values=issue_counts["COUNT"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3][:len(issue_counts)]),
            textinfo='percent', textposition='inside',
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

    df_patterns = _cached_sql("fo_copy_patterns", _SQL_COPY_PATTERNS)
    if not df_patterns.empty:
        st.markdown("##### COPY Executions by Pattern (truncated)")
        df_patterns['EXECUTION_COUNT'] = pd.to_numeric(df_patterns.get('EXECUTION_COUNT', 0), errors='coerce').fillna(0)
        fig2 = go.Figure(data=[go.Bar(
            y=df_patterns["PATTERN_SHORT"].tolist()[::-1],
            x=df_patterns["EXECUTION_COUNT"].tolist()[::-1],
            orientation="h", marker_color=_CA,
        )])
        fig2.update_layout(height=max(300, len(df_patterns) * 40 + 80),
                           margin=dict(t=10, b=40, l=300, r=20), showlegend=False,
                           xaxis_title="EXECUTION_COUNT")
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(df_patterns, use_container_width=True)


def _render_short_queries():
    df = _cached_sql("fo_short_queries", _SQL_SHORT_QUERIES)
    if df.empty:
        st.info("No high-frequency short query patterns detected.")
        return
    df['EXECUTION_COUNT'] = pd.to_numeric(df['EXECUTION_COUNT'], errors='coerce').fillna(0)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### High-Frequency Short Query Templates")
        top = df.head(10)
        fig = go.Figure(data=[go.Bar(
            y=top["QUERY_TEMPLATE_SHORT"].tolist()[::-1],
            x=top["EXECUTION_COUNT"].tolist()[::-1],
            orientation="h", marker_color=_C2,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=300, r=20), showlegend=False,
                          xaxis_title="EXECUTION_COUNT")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### High-Frequency Short Queries by Client Tool")
        tool = df.groupby("CLIENT_TOOL")["EXECUTION_COUNT"].sum().reset_index().sort_values("EXECUTION_COUNT", ascending=False)
        fig2 = go.Figure(data=[go.Bar(
            y=tool["CLIENT_TOOL"].tolist()[::-1],
            x=tool["EXECUTION_COUNT"].tolist()[::-1],
            orientation="h", marker_color=_C1,
        )])
        fig2.update_layout(height=400, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                           xaxis_title="EXECUTION_COUNT")
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_show_commands():
    st.markdown("##### Top SHOW Commands by Frequency")
    df = _cached_sql("fo_show_commands", _SQL_SHOW_COMMANDS)
    if df.empty:
        st.info("No high-frequency SHOW command patterns detected.")
        return
    df['EXECUTION_COUNT'] = pd.to_numeric(df['EXECUTION_COUNT'], errors='coerce').fillna(0)
    fig = go.Figure(data=[go.Bar(
        y=df["COMMAND_TYPE"].tolist()[::-1],
        x=df["EXECUTION_COUNT"].tolist()[::-1],
        orientation="h", marker_color=_C1,
    )])
    fig.update_layout(height=max(300, len(df) * 35 + 80),
                      margin=dict(t=10, b=40, l=300, r=20), showlegend=False,
                      xaxis_title="EXECUTION_COUNT")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_info_schema():
    df = _cached_sql("fo_info_schema", _SQL_INFO_SCHEMA)
    if df.empty:
        st.info("No high-frequency INFORMATION_SCHEMA queries detected.")
        return
    df['EXECUTION_COUNT'] = pd.to_numeric(df['EXECUTION_COUNT'], errors='coerce').fillna(0)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Metadata Scan Patterns")
        top = df.head(5)
        fig = go.Figure(data=[go.Bar(
            y=top["QUERY_PREVIEW_SHORT"].tolist()[::-1],
            x=top["EXECUTION_COUNT"].tolist()[::-1],
            orientation="h", marker_color=[_C1, _C2][:1] * len(top),
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=300, r=20), showlegend=False,
                          xaxis_title="EXECUTION_COUNT")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Metadata Scans by Client Tool")
        tool = df.groupby("CLIENT_TOOL")["EXECUTION_COUNT"].sum().reset_index().sort_values("EXECUTION_COUNT", ascending=False)
        fig2 = go.Figure(data=[go.Bar(
            y=tool["CLIENT_TOOL"].tolist()[::-1],
            x=tool["EXECUTION_COUNT"].tolist()[::-1],
            orientation="h", marker_color=_C1,
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=40, l=200, r=20), showlegend=False,
                           xaxis_title="EXECUTION_COUNT")
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_single_row_inserts():
    df = _cached_sql("fo_single_row_inserts", _SQL_SINGLE_ROW_INSERTS)
    if df.empty:
        st.info("No single-row INSERT patterns detected.")
        return
    df['INSERT_COUNT'] = pd.to_numeric(df['INSERT_COUNT'], errors='coerce').fillna(0)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Single-Row INSERTs by Table")
        top = df.head(10)
        fig = go.Figure(data=[go.Bar(
            y=top["TARGET_TABLE"].astype(str).tolist()[::-1],
            x=top["INSERT_COUNT"].tolist()[::-1],
            orientation="h", marker_color=_CA,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=20), showlegend=False,
                          xaxis_title="INSERT_COUNT")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Severity Distribution")
        sev = df.groupby("SEVERITY").size().reset_index(name="COUNT")
        fig2 = go.Figure(data=[go.Pie(
            labels=sev["SEVERITY"].tolist(),
            values=sev["COUNT"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3][:len(sev)]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)


def _render_ddl_and_clones():
    df_ddl = _cached_sql("fo_ddl_summary", _SQL_DDL_SUMMARY)
    df_clone = _cached_sql("fo_clone_summary", _SQL_CLONE_SUMMARY)
    df_clone_ops = _cached_sql("fo_clone_ops", _SQL_CLONE_OPS)

    if not df_ddl.empty:
        r = df_ddl.iloc[0]
        ddl_total = r.get('TOTAL_DDL_30D')
        ddl_patterns = r.get('DISTINCT_DDL_PATTERNS')
        ddl_cs = r.get('TOTAL_CS_CREDITS')
        if ddl_total is None or (pd.notna(ddl_total) and int(ddl_total) == 0):
            st.info("No DDL data available.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Total DDL Operations (30d)", f"{int(ddl_total):,}" if pd.notna(ddl_total) else "N/A")
            with c2:
                st.metric("Distinct DDL Patterns", f"{int(ddl_patterns):,}" if pd.notna(ddl_patterns) else "0")
            with c3:
                st.metric("DDL Cloud Services Credits", f"{float(ddl_cs):.4f}" if pd.notna(ddl_cs) else "N/A")
    else:
        st.info("No DDL data available.")

    if not df_clone.empty:
        r = df_clone.iloc[0]
        c1, c2, c3 = st.columns(3)
        with c1:
            val = r.get('TOTAL_CLONE_30D')
            st.metric("Total CLONE Operations (30d)", f"{int(val):,}" if pd.notna(val) and val else "N/A")
        with c2:
            val = r.get('DISTINCT_CLONE_PATTERNS')
            st.metric("Distinct CLONE Patterns", f"{int(val):,}" if pd.notna(val) and val else "0")
        with c3:
            val = r.get('TOTAL_CS_CREDITS')
            st.metric("CS Credits from CLONEs", f"{float(val):.4f}" if pd.notna(val) and val else "N/A")

    if not df_clone_ops.empty:
        st.markdown("Top clone operations")
        st.dataframe(df_clone_ops, use_container_width=True)


def _render_complex_queries():
    df = _cached_sql("fo_complex_queries", _SQL_COMPLEX_QUERIES)
    if df.empty:
        st.info("No complex query patterns detected (compilation time >5 seconds).")
        return
    df['COMPILE_MS'] = pd.to_numeric(df['COMPILE_MS'], errors='coerce').fillna(0)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Queries by Compilation Time (ms)")
        fig = go.Figure(data=[go.Bar(
            y=df["QUERY_ID"].tolist()[::-1],
            x=df["COMPILE_MS"].tolist()[::-1],
            orientation="h", marker_color=_CA,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=20), showlegend=False,
                          xaxis_title="COMPILE_MS")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("##### Complexity Severity Distribution")
        sev = df.groupby("SEVERITY").size().reset_index(name="COUNT")
        fig2 = go.Figure(data=[go.Pie(
            labels=sev["SEVERITY"].tolist(),
            values=sev["COUNT"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3][:len(sev)]),
            textinfo='percent', textposition='inside',
        )])
        fig2.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(df, use_container_width=True)

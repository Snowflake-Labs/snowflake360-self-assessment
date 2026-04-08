import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'


def comp_finops_optimization(entry_actions=None):
    try:
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
            _render_ddl_clone()
        with st.expander("Complex SQL Compilation Overhead (>5s compile time, 30d)", expanded=True):
            _render_complex_queries()
    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_cs_overhead():
    df = st.session_state.get("fo_cloud_svcs_overhead", pd.DataFrame())
    if df.empty:
        st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'No significant cloud services overhead patterns detected.'
                    '</div>', unsafe_allow_html=True)
        return
    st.dataframe(df, use_container_width=True)


def _render_copy_commands():
    summary = st.session_state.get("fo_copy_summary", pd.DataFrame())
    patterns = st.session_state.get("fo_copy_patterns", pd.DataFrame())

    total_cmds = "N/A"
    distinct = 0
    cs_credits = "N/A"
    if not summary.empty:
        r = summary.iloc[0]
        total_cmds = r.get("TOTAL_COPY_COMMANDS_30D", "N/A")
        distinct = r.get("DISTINCT_COPY_PATTERNS", 0)
        cs_credits = r.get("TOTAL_CLOUD_SERVICES_CREDITS", "N/A")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total COPY Commands (30d)", str(total_cmds))
    c2.metric("Distinct COPY Patterns", str(distinct))
    c3.metric("Cloud Services Credits", str(cs_credits))

    if patterns.empty:
        st.info("No inefficient COPY patterns found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Issue Type Distribution \u2014 Inefficient COPY Commands**")
        if "ISSUE_TYPE" in patterns.columns:
            tier = patterns.groupby("ISSUE_TYPE").size().reset_index(name="COUNT")
            fig = go.Figure(data=[go.Pie(
                labels=tier["ISSUE_TYPE"].tolist(), values=tier["COUNT"].tolist(),
                hole=0.45, marker=dict(colors=[_C1, _CA, _C3][:len(tier)]),
                textinfo="label+percent",
            )])
            fig.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**COPY Executions by Pattern (truncated)**")
        top = patterns.head(10).sort_values("EXECUTION_COUNT", ascending=True)
        display_col = "PATTERN_SHORT" if "PATTERN_SHORT" in top.columns else "QUERY_PATTERN"
        if display_col in top.columns:
            labels = [str(x)[:60] + "..." if len(str(x)) > 60 else str(x) for x in top[display_col].tolist()]
        else:
            labels = [f"Pattern {i}" for i in range(len(top))]
        fig2 = go.Figure(data=[go.Bar(
            y=labels, x=top["EXECUTION_COUNT"].tolist(),
            orientation="h", marker_color=_CA,
        )])
        fig2.update_layout(height=350, margin=dict(t=10, b=40, l=300, r=10), xaxis_title="EXECUTION_COUNT", showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(patterns, use_container_width=True)


def _render_short_queries():
    df = st.session_state.get("fo_short_queries", pd.DataFrame())
    if df.empty:
        st.info("No high-frequency short queries found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**High-Frequency Short Query Templates**")
        display_col = "QUERY_TEMPLATE_SHORT" if "QUERY_TEMPLATE_SHORT" in df.columns else "QUERY_TEMPLATE"
        if display_col in df.columns:
            top = df.head(10).sort_values("EXECUTION_COUNT", ascending=True)
            labels = [str(x)[:60] + "..." if len(str(x)) > 60 else str(x) for x in top[display_col].tolist()]
        else:
            top = df.head(10).sort_values("EXECUTION_COUNT", ascending=True)
            labels = [f"Query {i}" for i in range(len(top))]
        fig = go.Figure(data=[go.Bar(
            y=labels, x=top["EXECUTION_COUNT"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=300, r=10), xaxis_title="EXECUTION_COL", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**High-Frequency Short Queries by Client Tool**")
        if "CLIENT_TOOL" in df.columns:
            tool = df.groupby("CLIENT_TOOL")["EXECUTION_COUNT"].sum().reset_index().sort_values("EXECUTION_COUNT", ascending=True)
            fig2 = go.Figure(data=[go.Bar(
                y=tool["CLIENT_TOOL"].tolist(), x=tool["EXECUTION_COUNT"].tolist(),
                orientation="h", marker_color=_C1,
            )])
            fig2.update_layout(height=350, margin=dict(t=10, b=40, l=200, r=10), xaxis_title="EXECUTION_COUNT", showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_show_commands():
    df = st.session_state.get("fo_show_commands", pd.DataFrame())
    if df.empty:
        st.info("No high-frequency SHOW commands found.")
        return

    st.markdown("**Top SHOW Commands by Frequency**")
    display_col = "COMMAND_TYPE" if "COMMAND_TYPE" in df.columns else "QUERY_TYPE"
    top = df.head(10).sort_values("EXECUTION_COUNT", ascending=True)
    if display_col in top.columns:
        labels = top[display_col].tolist()
    else:
        labels = [f"Cmd {i}" for i in range(len(top))]
    fig = go.Figure(data=[go.Bar(
        y=labels, x=top["EXECUTION_COUNT"].tolist(),
        orientation="h", marker_color=_C1,
    )])
    fig.update_layout(height=400, margin=dict(t=10, b=40, l=350, r=10), xaxis_title="EXECUTION_COUNT", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_info_schema():
    df = st.session_state.get("fo_info_schema", pd.DataFrame())
    if df.empty:
        st.info("No INFORMATION_SCHEMA metadata scan patterns found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Metadata Scan Patterns**")
        display_col = "QUERY_PREVIEW_SHORT" if "QUERY_PREVIEW_SHORT" in df.columns else "QUERY_PREVIEW"
        top = df.head(5).sort_values("EXECUTION_COUNT", ascending=True)
        if display_col in top.columns:
            labels = [str(x)[:60] + "..." if len(str(x)) > 60 else str(x) for x in top[display_col].tolist()]
        else:
            labels = [f"Scan {i}" for i in range(len(top))]
        fig = go.Figure(data=[go.Bar(
            y=labels, x=top["EXECUTION_COUNT"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=300, margin=dict(t=10, b=40, l=350, r=10), xaxis_title="EXECUTION_COL", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Metadata Scans by Client Tool**")
        if "CLIENT_TOOL" in df.columns:
            tool = df.groupby("CLIENT_TOOL")["EXECUTION_COUNT"].sum().reset_index().sort_values("EXECUTION_COUNT", ascending=True)
            fig2 = go.Figure(data=[go.Bar(
                y=tool["CLIENT_TOOL"].tolist(), x=tool["EXECUTION_COUNT"].tolist(),
                orientation="h", marker_color=_C1,
            )])
            fig2.update_layout(height=300, margin=dict(t=10, b=40, l=200, r=10), xaxis_title="EXECUTION_COUNT", showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_single_row_inserts():
    df = st.session_state.get("fo_single_row_inserts", pd.DataFrame())
    if df.empty:
        st.info("No single-row INSERT patterns found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Single-Row INSERTs by Table**")
        top = df.head(10).sort_values("INSERT_COUNT", ascending=True)
        labels = top["TARGET_TABLE"].tolist() if "TARGET_TABLE" in top.columns else [f"Table {i}" for i in range(len(top))]
        fig = go.Figure(data=[go.Bar(
            y=labels, x=top["INSERT_COUNT"].tolist(),
            orientation="h", marker_color=_CA,
        )])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=300, r=10), xaxis_title="INSERT_COUNT", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Severity Distribution**")
        if "SEVERITY" in df.columns:
            tier = df.groupby("SEVERITY").size().reset_index(name="COUNT")
            fig2 = go.Figure(data=[go.Pie(
                labels=tier["SEVERITY"].tolist(), values=tier["COUNT"].tolist(),
                hole=0.45, marker=dict(colors=[_C1, _CA, _C3][:len(tier)]),
                textinfo="label+percent",
            )])
            fig2.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)


def _render_ddl_clone():
    ddl_df = st.session_state.get("fo_ddl_summary", pd.DataFrame())
    clone_df = st.session_state.get("fo_clone_summary", pd.DataFrame())
    detail_df = st.session_state.get("fo_ddl_clone", pd.DataFrame())

    total_ddl = "N/A"
    ddl_patterns = 0
    ddl_cs = "N/A"
    if not ddl_df.empty:
        r = ddl_df.iloc[0]
        total_ddl = r.get("TOTAL_DDL_30D", "N/A")
        ddl_patterns = r.get("DISTINCT_DDL_PATTERNS", 0)
        ddl_cs = r.get("TOTAL_CS_CREDITS", "N/A")

    if ddl_df.empty or (isinstance(total_ddl, (int, float)) and total_ddl == 0):
        st.info("No DDL data available.")

    total_clone = "N/A"
    clone_patterns = 0
    clone_cs = "N/A"
    if not clone_df.empty:
        r = clone_df.iloc[0]
        total_clone = r.get("TOTAL_CLONE_30D", "N/A")
        clone_patterns = r.get("DISTINCT_CLONE_PATTERNS", 0)
        clone_cs = r.get("TOTAL_CS_CREDITS", "N/A")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total CLONE Operations (30d)", str(total_clone))
    c2.metric("Distinct CLONE Patterns", str(clone_patterns))
    c3.metric("CS Credits from CLONEs", str(clone_cs))

    c4, c5, c6 = st.columns(3)
    c4.metric("Total DDL Operations (30d)", str(total_ddl))
    c5.metric("Distinct DDL Patterns", str(ddl_patterns))
    c6.metric("DDL Cloud Services Credits", str(ddl_cs))

    if not detail_df.empty:
        st.markdown("Top clone operations")
        st.dataframe(detail_df, use_container_width=True)


def _render_complex_queries():
    df = st.session_state.get("fo_complex_queries", pd.DataFrame())
    if df.empty:
        st.info("No complex SQL compilation patterns found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Queries by Compilation Time (ms)**")
        top = df.head(10).sort_values("COMPILE_MS", ascending=True)
        fig = go.Figure(data=[go.Bar(
            y=top["QUERY_ID"].astype(str).tolist(), x=top["COMPILE_MS"].tolist(),
            orientation="h", marker_color=_C1,
        )])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=10), xaxis_title="COMPILE_MS", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Complexity Severity Distribution**")
        if "SEVERITY" in df.columns:
            tier = df.groupby("SEVERITY").size().reset_index(name="COUNT")
            fig2 = go.Figure(data=[go.Pie(
                labels=tier["SEVERITY"].tolist(), values=tier["COUNT"].tolist(),
                hole=0.45, marker=dict(colors=[_C1, _CA, _C3][:len(tier)]),
                textinfo="label+percent",
            )])
            fig2.update_layout(height=400, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(df, use_container_width=True)

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

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = '#29B5E8'
_C2 = '#11567F'
_C3 = '#75C2D8'
_CA = '#E8A229'

_SQL_DBT_OBJECT_SPLIT = """
SELECT
    OBJECT_TYPE,
    COUNT(*) AS OBJECTS,
    COUNT(DISTINCT OBJECT_NAME) AS DISTINCT_OBJECTS,
    ROUND(SUM(DATEDIFF('second', QUERY_START_TIME, QUERY_END_TIME)) / 60.0, 1) AS TOTAL_MIN
FROM SNOWFLAKE.ACCOUNT_USAGE.DBT_PROJECT_EXECUTION_HISTORY
WHERE QUERY_START_TIME >= DATEADD('day', -90, CURRENT_DATE())
GROUP BY OBJECT_TYPE
ORDER BY OBJECTS DESC
"""

_SQL_DBT_SLOWEST = """
SELECT
    OBJECT_NAME, OBJECT_TYPE, DATABASE_NAME, SCHEMA_NAME,
    COUNT(*) AS EXECUTIONS,
    ROUND(AVG(DATEDIFF('second', QUERY_START_TIME, QUERY_END_TIME)), 1) AS AVG_RUNTIME_SEC,
    ROUND(MAX(DATEDIFF('second', QUERY_START_TIME, QUERY_END_TIME)), 1) AS MAX_RUNTIME_SEC
FROM SNOWFLAKE.ACCOUNT_USAGE.DBT_PROJECT_EXECUTION_HISTORY
WHERE QUERY_START_TIME >= DATEADD('day', -90, CURRENT_DATE())
  AND STATE = 'SUCCESS'
GROUP BY 1, 2, 3, 4
ORDER BY AVG_RUNTIME_SEC DESC
LIMIT 20
"""

_SQL_DBT_FAILURES = """
SELECT
    OBJECT_NAME, OBJECT_TYPE, DATABASE_NAME,
    COUNT(*) AS TOTAL_RUNS,
    SUM(CASE WHEN STATE != 'SUCCESS' THEN 1 ELSE 0 END) AS FAILURES,
    ROUND(100.0 * SUM(CASE WHEN STATE != 'SUCCESS' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS FAILURE_PCT
FROM SNOWFLAKE.ACCOUNT_USAGE.DBT_PROJECT_EXECUTION_HISTORY
WHERE QUERY_START_TIME >= DATEADD('day', -90, CURRENT_DATE())
GROUP BY 1, 2, 3
HAVING SUM(CASE WHEN STATE != 'SUCCESS' THEN 1 ELSE 0 END) > 0
ORDER BY FAILURE_PCT DESC
LIMIT 20
"""

_SQL_DBT_DAILY_TREND = """
SELECT
    DATE_TRUNC('day', QUERY_START_TIME)::DATE AS RUN_DATE,
    COUNT(*) AS TOTAL_RUNS,
    SUM(CASE WHEN STATE = 'SUCCESS' THEN 1 ELSE 0 END) AS SUCCESSES,
    SUM(CASE WHEN STATE != 'SUCCESS' THEN 1 ELSE 0 END) AS FAILURES,
    ROUND(SUM(DATEDIFF('second', QUERY_START_TIME, QUERY_END_TIME)) / 60.0, 1) AS TOTAL_MIN
FROM SNOWFLAKE.ACCOUNT_USAGE.DBT_PROJECT_EXECUTION_HISTORY
WHERE QUERY_START_TIME >= DATEADD('day', -90, CURRENT_DATE())
GROUP BY 1
ORDER BY RUN_DATE
"""

_SQL_DBT_SKIPPED = """
SELECT
    OBJECT_NAME, OBJECT_TYPE, DATABASE_NAME,
    COUNT(*) AS TIMES_SKIPPED
FROM SNOWFLAKE.ACCOUNT_USAGE.DBT_PROJECT_EXECUTION_HISTORY
WHERE QUERY_START_TIME >= DATEADD('day', -90, CURRENT_DATE())
  AND COMMAND = 'SKIP'
GROUP BY 1, 2, 3
ORDER BY TIMES_SKIPPED DESC
LIMIT 20
"""


def comp_dbt_projects(entry_actions=None):
    session = st.session_state.get("session")
    if not session:
        st.info("No active session.")
        return

    try:
        df_split = session.sql(_SQL_DBT_OBJECT_SPLIT).to_pandas()
    except Exception:
        st.info("No dbt Projects execution history found (`DBT_PROJECT_EXECUTION_HISTORY` not accessible or empty).")
        return

    if df_split.empty:
        st.info("No dbt project executions found in the last 90 days.")
        return

    total_objects = int(df_split["OBJECTS"].sum())
    total_min = round(float(df_split["TOTAL_MIN"].sum()), 1)

    try:
        df_failures = session.sql(_SQL_DBT_FAILURES).to_pandas()
    except Exception:
        df_failures = pd.DataFrame()

    failure_count = len(df_failures)

    try:
        df_skipped = session.sql(_SQL_DBT_SKIPPED).to_pandas()
    except Exception:
        df_skipped = pd.DataFrame()

    skipped_count = int(df_skipped["TIMES_SKIPPED"].sum()) if not df_skipped.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("dbt Object Executions", f"{total_objects:,}")
    c2.metric("Total Runtime (min)", f"{total_min:,.0f}")
    c3.metric("Objects with Failures", f"{failure_count:,}")
    c4.metric("Total Skipped Events", f"{skipped_count:,}")

    st.divider()

    st.markdown("#### dbt Object Type Distribution")
    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(data=[go.Pie(
            labels=df_split["OBJECT_TYPE"].tolist(),
            values=df_split["OBJECTS"].tolist(),
            hole=0.45,
            marker=dict(colors=[_C1, _C2, _C3, _CA][:len(df_split)]),
            textinfo='percent+label', textposition='inside')])
        fig.update_layout(height=350, margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = go.Figure(data=[go.Bar(
            x=df_split["OBJECT_TYPE"].tolist(), y=df_split["TOTAL_MIN"].tolist(),
            marker_color=_C1, text=[f"{v:,.0f}" for v in df_split["TOTAL_MIN"]], textposition="outside")])
        fig.update_layout(height=350, margin=dict(t=10, b=40, l=50, r=20), yaxis_title="Minutes", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    try:
        df_slow = session.sql(_SQL_DBT_SLOWEST).to_pandas()
        if not df_slow.empty:
            st.markdown("#### Slowest dbt Objects (by Avg Runtime)")
            top = df_slow.head(15)
            fig = go.Figure(data=[go.Bar(
                y=top["OBJECT_NAME"].tolist()[::-1], x=top["AVG_RUNTIME_SEC"].tolist()[::-1],
                orientation="h", marker_color=_C2)])
            fig.update_layout(height=420, margin=dict(t=10, b=40, l=250, r=20),
                showlegend=False, xaxis_title="Avg Runtime (sec)")
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass

    if not df_failures.empty:
        st.markdown("#### dbt Failure Rates")
        col1, col2 = st.columns(2)
        top = df_failures.head(15)
        with col1:
            fig = go.Figure(data=[go.Bar(
                y=top["OBJECT_NAME"].tolist()[::-1], x=top["FAILURE_PCT"].tolist()[::-1],
                orientation="h", marker_color='#E74C3C',
                text=[f"{v:.0f}%" for v in top["FAILURE_PCT"].tolist()[::-1]], textposition="outside")])
            fig.update_layout(height=420, margin=dict(t=10, b=40, l=250, r=20), showlegend=False, xaxis_title="Failure %")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = go.Figure(data=[go.Bar(
                y=top["OBJECT_NAME"].tolist()[::-1], x=top["FAILURES"].tolist()[::-1],
                orientation="h", marker_color=_CA)])
            fig.update_layout(height=420, margin=dict(t=10, b=40, l=250, r=20), showlegend=False, xaxis_title="Failure Count")
            st.plotly_chart(fig, use_container_width=True)

    try:
        df_trend = session.sql(_SQL_DBT_DAILY_TREND).to_pandas()
        if not df_trend.empty:
            st.markdown("#### dbt Daily Execution Trend (90d)")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_trend["RUN_DATE"], y=df_trend["SUCCESSES"], name="Successes", marker_color=_C1))
            fig.add_trace(go.Bar(x=df_trend["RUN_DATE"], y=df_trend["FAILURES"], name="Failures", marker_color='#E74C3C'))
            fig.update_layout(barmode="stack", height=350, margin=dict(t=10, b=40, l=50, r=20),
                yaxis_title="Executions", legend=dict(orientation="h", y=1.05, x=0))
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass

    if not df_skipped.empty:
        st.markdown("#### Persistently Skipped dbt Objects")
        top = df_skipped.head(15)
        fig = go.Figure(data=[go.Bar(
            y=top["OBJECT_NAME"].tolist()[::-1], x=top["TIMES_SKIPPED"].tolist()[::-1],
            orientation="h", marker_color=_C3)])
        fig.update_layout(height=400, margin=dict(t=10, b=40, l=250, r=20), showlegend=False, xaxis_title="Times Skipped")
        st.plotly_chart(fig, use_container_width=True)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
try:
    from streamlit_echarts import st_echarts
except ImportError:
    def st_echarts(**kwargs):
        import streamlit as st
        st.info("Chart unavailable (echarts not supported in SiS)")


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


def comp_finops_optimization(entry_actions=None):
    """
    FinOPS Optimization Component

    Provides optimization recommendations and pattern analysis.

    Expanders:
    1. FinOPS Optimization Overview
    2. FinOPS Optimization Analyzer
    3. Pattern: Copy commands with poor selectivity
    4. Pattern: High-frequency DDL operations and cloning
    5. Pattern: High-frequency, simple queries
    6. Pattern: High-frequency INFORMATION_SCHEMA queries
    7. Pattern: High-frequency SHOW commands (by data applications and third-party tools)
    8. Pattern: Single row inserts and fragmented schemas (by data applications)
    9. Pattern: Complex SQL queries
    """
    try:
        st.markdown("### Optimisation")

        # Expander 3: Pattern: Copy commands with poor selectivity
        with st.expander("Pattern: Copy commands with poor selectivity", expanded=True):
            st.markdown("#### Pattern: Copy commands with poor selectivity")
            _render_copy_poor_selectivity()

        # Expander 4: Pattern: High-frequency DDL operations and cloning
        with st.expander("Pattern: High-frequency DDL operations and cloning", expanded=True):
            _render_ddl_operations()

        # Expander 5: Pattern: High-frequency, simple queries
        with st.expander("Pattern: High-frequency, simple queries", expanded=True):
            _render_simple_queries()

        # Expander 6: Pattern: High-frequency INFORMATION_SCHEMA queries
        with st.expander("Pattern: High-frequency INFORMATION_SCHEMA queries", expanded=True):
            _render_info_schema_queries()

        # Expander 7: Pattern: High-frequency SHOW commands (by data applications and third-party tools)
        with st.expander("Pattern: High-frequency SHOW commands (by data applications and third-party tools)", expanded=True):
            _render_show_commands()

        # Expander 8: Pattern: Single row inserts and fragmented schemas (by data applications)
        with st.expander("Pattern: Single row inserts and fragmented schemas (by data applications)", expanded=True):
            _render_single_row_inserts()

        # Expander 9: Pattern: Complex SQL queries
        with st.expander("Pattern: Complex SQL queries", expanded=True):
            _render_complex_queries()

        with st.expander("Cloud Services Overhead Summary (30 Days)", expanded=True):
            _render_cloud_services_overhead()

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== DDL Operations Section ==========

def _render_ddl_operations():
    """Render DDL operations summary section."""

    st.markdown("#### Pattern: High-frequency DDL operations and cloning")


    # ========== Section 1: Cloning Operations (First) ==========
    _render_cloning_operations()

    # ========== Section 2: DDL Operations Summary ==========
    st.markdown("---")
    st.markdown("#### DDL Operations Summary")

    # Introduction text
    st.markdown("""
    **DDL operation summary** showing total executions and distinct query patterns for CREATE/ALTER/DROP commands over last 30 days.
    """)

    try:
        # DDL Operations Summary Query
        ddl_query = f"""
WITH ddl_q AS (
  SELECT
    query_parameterized_hash,
    MIN(query_text) AS sample_text,
    NVL(COUNT(*), 0) AS executions,
    NVL(SUM(credits_used_cloud_services), 0) AS cs_credits
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND REGEXP_LIKE(query_text, '^\\\\s*(CREATE|ALTER|DROP)\\\\b', 'i')
  GROUP BY query_parameterized_hash
)
SELECT
    NVL(SUM(executions), 0) AS total_ddl_30d,
    NVL(COUNT(*), 0) AS distinct_ddl_patterns_30d
FROM ddl_q
"""


        # Execute the query
        ddl_df = _cached_sql("fo_ddl", ddl_query)

        if not ddl_df.empty:
            st.dataframe(ddl_df, use_container_width=True)

            # Get values for charts
            total_ddl = int(ddl_df['TOTAL_DDL_30D'].iloc[0]) if 'TOTAL_DDL_30D' in ddl_df.columns else 0
            distinct_patterns = int(ddl_df['DISTINCT_DDL_PATTERNS_30D'].iloc[0]) if 'DISTINCT_DDL_PATTERNS_30D' in ddl_df.columns else 0

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### DDL Operations Analysis Charts")

            # Row 1: Total DDL Commands & Distinct Patterns
            ddl_chart_col1, ddl_chart_col2 = st.columns(2)

            with ddl_chart_col1.container():
                st.markdown(f"##### Total DDL Commands: {total_ddl:,}")
                _render_ddl_total_chart_content(total_ddl, distinct_patterns, key_prefix="ddl_total_")

            with ddl_chart_col2.container():
                st.markdown(f"##### Distinct DDL Patterns: {distinct_patterns:,}")
                _render_ddl_patterns_chart_content(total_ddl, distinct_patterns, key_prefix="ddl_patterns_")

            # ========== Top 10 DDL Patterns Section ==========
            _render_top_ddl_patterns()

            # ========== CLONE Operations Summary Section ==========
            _render_clone_summary()

        else:
            st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '✅&nbsp;&nbsp;No DDL operations detected in the last 30 days.'
                        '</div>', unsafe_allow_html=True)

            # Still show CLONE summary even if no DDL operations found
            _render_clone_summary()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading DDL operations: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== DDL Total Commands Chart Functions ==========

def _render_ddl_total_chart_content(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL total commands chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_ddl_total_bar_chart(total_ddl, distinct_patterns, key_prefix)
    elif chart_type == "Pie Chart":
        _render_ddl_total_standard_pie_chart(total_ddl, distinct_patterns, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_ddl_total_donut_pie_chart(total_ddl, distinct_patterns, key_prefix)
    else:
        _render_ddl_total_rose_pie_chart(total_ddl, distinct_patterns, key_prefix)


def _render_ddl_total_bar_chart(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL total commands bar chart using Plotly."""

    labels = ['Total DDL Commands', 'Distinct Patterns']
    values = [total_ddl, distinct_patterns]
    colors = ['#29B5E8', '#0077B6']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:,}" for v in values],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y:,}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_ddl_total_standard_pie_chart(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL total standard pie chart using ECharts."""

    chart_data = [
        {"value": total_ddl, "name": f"Total DDL ({total_ddl:,})"},
        {"value": distinct_patterns, "name": f"Distinct Patterns ({distinct_patterns:,})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c:,}"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#29B5E8", "#0077B6"],
        "series": [
            {
                "name": "DDL Operations",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_ddl_total_donut_pie_chart(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL total donut pie chart using ECharts."""

    chart_data = [
        {"value": total_ddl, "name": f"Total DDL ({total_ddl:,})"},
        {"value": distinct_patterns, "name": f"Distinct Patterns ({distinct_patterns:,})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c:,}"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#29B5E8", "#0077B6"],
        "series": [
            {
                "name": "DDL Operations",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_ddl_total_rose_pie_chart(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL total rose pie chart using ECharts."""

    chart_data = [
        {"value": total_ddl, "name": f"Total DDL ({total_ddl:,})"},
        {"value": distinct_patterns, "name": f"Distinct Patterns ({distinct_patterns:,})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c:,}"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#29B5E8", "#0077B6"],
        "series": [
            {
                "name": "DDL Operations",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== DDL Patterns Chart Functions ==========

def _render_ddl_patterns_chart_content(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL patterns chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_ddl_patterns_bar_chart(total_ddl, distinct_patterns, key_prefix)
    elif chart_type == "Pie Chart":
        _render_ddl_patterns_standard_pie_chart(total_ddl, distinct_patterns, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_ddl_patterns_donut_pie_chart(total_ddl, distinct_patterns, key_prefix)
    else:
        _render_ddl_patterns_rose_pie_chart(total_ddl, distinct_patterns, key_prefix)


def _render_ddl_patterns_bar_chart(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL patterns bar chart using Plotly - shows avg executions per pattern."""

    avg_per_pattern = total_ddl / distinct_patterns if distinct_patterns > 0 else 0

    labels = ['Distinct Patterns', 'Avg Executions/Pattern']
    values = [distinct_patterns, avg_per_pattern]
    colors = ['#0077B6', '#E8A229']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{distinct_patterns:,}", f"{avg_per_pattern:.1f}"],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Value: %{y:.1f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_ddl_patterns_standard_pie_chart(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL patterns standard pie chart using ECharts."""

    avg_per_pattern = total_ddl / distinct_patterns if distinct_patterns > 0 else 0

    chart_data = [
        {"value": distinct_patterns, "name": f"Patterns ({distinct_patterns:,})"},
        {"value": round(avg_per_pattern, 1), "name": f"Avg Exec/Pattern ({avg_per_pattern:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#0077B6", "#E8A229"],
        "series": [
            {
                "name": "Pattern Analysis",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_ddl_patterns_donut_pie_chart(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL patterns donut pie chart using ECharts."""

    avg_per_pattern = total_ddl / distinct_patterns if distinct_patterns > 0 else 0

    chart_data = [
        {"value": distinct_patterns, "name": f"Patterns ({distinct_patterns:,})"},
        {"value": round(avg_per_pattern, 1), "name": f"Avg Exec/Pattern ({avg_per_pattern:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#0077B6", "#E8A229"],
        "series": [
            {
                "name": "Pattern Analysis",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_ddl_patterns_rose_pie_chart(total_ddl, distinct_patterns, key_prefix=""):
    """Render DDL patterns rose pie chart using ECharts."""

    avg_per_pattern = total_ddl / distinct_patterns if distinct_patterns > 0 else 0

    chart_data = [
        {"value": distinct_patterns, "name": f"Patterns ({distinct_patterns:,})"},
        {"value": round(avg_per_pattern, 1), "name": f"Avg Exec/Pattern ({avg_per_pattern:.1f})"},
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "textStyle": {"fontSize": 10}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#0077B6", "#E8A229"],
        "series": [
            {
                "name": "Pattern Analysis",
                "type": "pie",
                "radius": [15, 100],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 6},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Top 10 DDL Patterns Section ==========

def _render_top_ddl_patterns():
    """Render Top 10 most frequently executed DDL patterns section."""

    st.markdown("---")
    st.markdown("#### Top 10 DDL Patterns")

    # Introduction text
    st.markdown("""
    **Top 10 most frequently executed DDL patterns** (CREATE/ALTER/DROP) over last 30 days with execution counts, cloud services credits, and sample query text.
    """)

    try:
        # Top 10 DDL Patterns Query
        top_ddl_query = f"""
WITH ddl_q AS (
  SELECT
    query_parameterized_hash,
    MIN(query_text) AS sample_text,
    NVL(COUNT(*), 0) AS executions,
    NVL(SUM(credits_used_cloud_services), 0) AS cs_credits
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND REGEXP_LIKE(query_text, '^\\\\s*(CREATE|ALTER|DROP)\\\\b', 'i')
  GROUP BY query_parameterized_hash
)
SELECT
    query_parameterized_hash,
    executions,
    cs_credits,
    sample_text
FROM ddl_q
ORDER BY executions DESC
LIMIT 10
"""


        # Execute the query
        top_ddl_df = _cached_sql("fo_top_ddl", top_ddl_query)

        if not top_ddl_df.empty:
            st.dataframe(top_ddl_df, use_container_width=True)

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Top DDL Patterns Analysis Charts")

            # Row 1: Execution Count by Pattern & CS Credits by Pattern
            top_ddl_chart_col1, top_ddl_chart_col2 = st.columns(2)

            with top_ddl_chart_col1.container():
                st.markdown("##### Execution Count by Pattern")
                _render_top_ddl_execution_chart_content(top_ddl_df, key_prefix="top_ddl_exec_")

            with top_ddl_chart_col2.container():
                st.markdown("##### Cloud Services Credits by Pattern")
                _render_top_ddl_credits_chart_content(top_ddl_df, key_prefix="top_ddl_credits_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No DDL patterns found for the last 30 days.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading top DDL patterns: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Top DDL Execution Count Chart Functions ==========

def _render_top_ddl_execution_chart_content(df, key_prefix=""):
    """Render top DDL execution count chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_top_ddl_execution_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_top_ddl_execution_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_top_ddl_execution_donut_pie_chart(df, key_prefix)
    else:
        _render_top_ddl_execution_rose_pie_chart(df, key_prefix)


def _render_top_ddl_execution_bar_chart(df, key_prefix=""):
    """Render top DDL execution bar chart using Plotly."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'EXECUTIONS' in df.columns:
        # Limit to top 10 for chart readability
        chart_df = df.head(10)
        labels = [f"Pattern {i+1}" for i in range(len(chart_df))]
        values = chart_df['EXECUTIONS'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color='#29B5E8',
                text=[f"{v:,}" for v in values],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{x}</b><br>Executions: %{y:,}<extra></extra>'
            )
        ])

        fig_bar.update_layout(
            height=350,
            xaxis_title='Pattern',
            yaxis_title='Executions',
            showlegend=False,
            margin=dict(t=20, b=40, l=50, r=20)
        )

        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No execution data available for chart.")


def _render_top_ddl_execution_standard_pie_chart(df, key_prefix=""):
    """Render top DDL execution standard pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'EXECUTIONS' in df.columns:
        # Limit to top 10 for chart readability
        chart_df = df.head(10)
        chart_data = [
            {"value": int(row['EXECUTIONS']), "name": f"Pattern {i+1} ({int(row['EXECUTIONS']):,})"}
            for i, row in chart_df.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c:,}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "Executions",
                    "type": "pie",
                    "radius": ["0%", "50%"],
                    "center": ["50%", "40%"],
                    "itemStyle": {"borderRadius": 5},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No execution data available for chart.")


def _render_top_ddl_execution_donut_pie_chart(df, key_prefix=""):
    """Render top DDL execution donut pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'EXECUTIONS' in df.columns:
        # Limit to top 10 for chart readability
        chart_df = df.head(10)
        chart_data = [
            {"value": int(row['EXECUTIONS']), "name": f"Pattern {i+1} ({int(row['EXECUTIONS']):,})"}
            for i, row in chart_df.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c:,}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "Executions",
                    "type": "pie",
                    "radius": ["30%", "50%"],
                    "center": ["50%", "40%"],
                    "itemStyle": {"borderRadius": 5},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No execution data available for chart.")


def _render_top_ddl_execution_rose_pie_chart(df, key_prefix=""):
    """Render top DDL execution rose pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'EXECUTIONS' in df.columns:
        # Limit to top 10 for chart readability
        chart_df = df.head(10)
        chart_data = [
            {"value": int(row['EXECUTIONS']), "name": f"Pattern {i+1} ({int(row['EXECUTIONS']):,})"}
            for i, row in chart_df.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c:,}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "Executions",
                    "type": "pie",
                    "radius": [15, 100],
                    "center": ["50%", "45%"],
                    "roseType": "area",
                    "itemStyle": {"borderRadius": 6},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No execution data available for chart.")


# ========== Top DDL Credits Chart Functions ==========

def _render_top_ddl_credits_chart_content(df, key_prefix=""):
    """Render top DDL credits chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_top_ddl_credits_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_top_ddl_credits_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_top_ddl_credits_donut_pie_chart(df, key_prefix)
    else:
        _render_top_ddl_credits_rose_pie_chart(df, key_prefix)


def _render_top_ddl_credits_bar_chart(df, key_prefix=""):
    """Render top DDL credits bar chart using Plotly."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'CS_CREDITS' in df.columns:
        # Limit to top 10 for chart readability
        chart_df = df.head(10)
        labels = [f"Pattern {i+1}" for i in range(len(chart_df))]
        values = chart_df['CS_CREDITS'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color='#E8A229',
                text=[f"{v:.4f}" for v in values],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{x}</b><br>CS Credits: %{y:.4f}<extra></extra>'
            )
        ])

        fig_bar.update_layout(
            height=350,
            xaxis_title='Pattern',
            yaxis_title='Cloud Services Credits',
            showlegend=False,
            margin=dict(t=20, b=40, l=50, r=20)
        )

        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No credits data available for chart.")


def _render_top_ddl_credits_standard_pie_chart(df, key_prefix=""):
    """Render top DDL credits standard pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'CS_CREDITS' in df.columns:
        # Limit to top 10 for chart readability
        chart_df = df.head(10)
        chart_data = [
            {"value": round(float(row['CS_CREDITS']), 4), "name": f"Pattern {i+1} ({float(row['CS_CREDITS']):.4f})"}
            for i, row in chart_df.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "CS Credits",
                    "type": "pie",
                    "radius": ["0%", "50%"],
                    "center": ["50%", "40%"],
                    "itemStyle": {"borderRadius": 5},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No credits data available for chart.")


def _render_top_ddl_credits_donut_pie_chart(df, key_prefix=""):
    """Render top DDL credits donut pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'CS_CREDITS' in df.columns:
        # Limit to top 10 for chart readability
        chart_df = df.head(10)
        chart_data = [
            {"value": round(float(row['CS_CREDITS']), 4), "name": f"Pattern {i+1} ({float(row['CS_CREDITS']):.4f})"}
            for i, row in chart_df.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "CS Credits",
                    "type": "pie",
                    "radius": ["30%", "50%"],
                    "center": ["50%", "40%"],
                    "itemStyle": {"borderRadius": 5},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No credits data available for chart.")


def _render_top_ddl_credits_rose_pie_chart(df, key_prefix=""):
    """Render top DDL credits rose pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'CS_CREDITS' in df.columns:
        # Limit to top 10 for chart readability
        chart_df = df.head(10)
        chart_data = [
            {"value": round(float(row['CS_CREDITS']), 4), "name": f"Pattern {i+1} ({float(row['CS_CREDITS']):.4f})"}
            for i, row in chart_df.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "CS Credits",
                    "type": "pie",
                    "radius": [15, 100],
                    "center": ["50%", "45%"],
                    "roseType": "area",
                    "itemStyle": {"borderRadius": 6},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Cloning Operations Section ==========

def _render_cloning_operations():
    """Render top 10 object cloning operations section."""

    # Introduction text
    st.markdown("""
    **Top 10 object cloning operations** over last 30 days by operation count, showing query type, object name, user, and cloud services credits consumed.
    """)

    try:
        # Cloning Operations Query
        cloning_query = f"""
SELECT
    query_type,
    REGEXP_SUBSTR(query_text, ' (TABLE|VIEW|SCHEMA|DATABASE) [IF EXISTS ]*([a-zA-Z0-9_.]+)', 1, 1, 'i', 2) AS object_name,
    user_name,
    NVL(COUNT(*), 0) AS operation_count,
    NVL(SUM(credits_used_cloud_services), 0) AS cloud_services_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type IN ('CREATE_TABLE', 'DROP_TABLE', 'CREATE_VIEW', 'ALTER_TABLE', 'RESTORE', 'CREATE_TABLE_AS_SELECT')
  AND query_text ILIKE '%CLONE%'
GROUP BY ALL
ORDER BY operation_count DESC
LIMIT 10
"""


        # Execute the query
        cloning_df = _cached_sql("fo_cloning", cloning_query)

        if not cloning_df.empty:
            st.dataframe(cloning_df, use_container_width=True)

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Cloning Operations Analysis Charts")

            # Row 1: Operations by Query Type & Operations by User
            cloning_chart_col1, cloning_chart_col2 = st.columns(2)

            with cloning_chart_col1.container():
                st.markdown("##### Operations by Query Type")
                _render_cloning_query_type_chart_content(cloning_df, key_prefix="cloning_query_type_")

            with cloning_chart_col2.container():
                st.markdown("##### Operations by User")
                _render_cloning_user_chart_content(cloning_df, key_prefix="cloning_user_")

        else:
            st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '✅&nbsp;&nbsp;No cloning operations detected in the last 30 days.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading cloning operations: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Cloning Query Type Chart Functions ==========

def _render_cloning_query_type_chart_content(df, key_prefix=""):
    """Render cloning query type chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_cloning_query_type_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_cloning_query_type_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_cloning_query_type_donut_pie_chart(df, key_prefix)
    else:
        _render_cloning_query_type_rose_pie_chart(df, key_prefix)


def _render_cloning_query_type_bar_chart(df, key_prefix=""):
    """Render cloning query type bar chart using Plotly."""

    if 'QUERY_TYPE' in df.columns and 'OPERATION_COUNT' in df.columns:
        # Group by query type
        grouped = df.groupby('QUERY_TYPE')['OPERATION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('OPERATION_COUNT', ascending=False)

        labels = grouped['QUERY_TYPE'].tolist()
        values = grouped['OPERATION_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color='#29B5E8',
                text=[f"{v:,}" for v in values],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{x}</b><br>Operations: %{y:,}<extra></extra>'
            )
        ])

        fig_bar.update_layout(
            height=350,
            xaxis_title='Query Type',
            yaxis_title='Operation Count',
            showlegend=False,
            margin=dict(t=20, b=80, l=50, r=20),
            xaxis_tickangle=-45
        )

        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No query type data available for chart.")


def _render_cloning_query_type_standard_pie_chart(df, key_prefix=""):
    """Render cloning query type standard pie chart using ECharts."""

    if 'QUERY_TYPE' in df.columns and 'OPERATION_COUNT' in df.columns:
        # Group by query type
        grouped = df.groupby('QUERY_TYPE')['OPERATION_COUNT'].sum().reset_index()

        chart_data = [
            {"value": int(row['OPERATION_COUNT']), "name": f"{row['QUERY_TYPE']} ({int(row['OPERATION_COUNT']):,})"}
            for _, row in grouped.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c:,}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "Query Type",
                    "type": "pie",
                    "radius": ["0%", "50%"],
                    "center": ["50%", "40%"],
                    "itemStyle": {"borderRadius": 5},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No query type data available for chart.")


def _render_cloning_query_type_donut_pie_chart(df, key_prefix=""):
    """Render cloning query type donut pie chart using ECharts."""

    if 'QUERY_TYPE' in df.columns and 'OPERATION_COUNT' in df.columns:
        # Group by query type
        grouped = df.groupby('QUERY_TYPE')['OPERATION_COUNT'].sum().reset_index()

        chart_data = [
            {"value": int(row['OPERATION_COUNT']), "name": f"{row['QUERY_TYPE']} ({int(row['OPERATION_COUNT']):,})"}
            for _, row in grouped.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c:,}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "Query Type",
                    "type": "pie",
                    "radius": ["30%", "50%"],
                    "center": ["50%", "40%"],
                    "itemStyle": {"borderRadius": 5},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No query type data available for chart.")


def _render_cloning_query_type_rose_pie_chart(df, key_prefix=""):
    """Render cloning query type rose pie chart using ECharts."""

    if 'QUERY_TYPE' in df.columns and 'OPERATION_COUNT' in df.columns:
        # Group by query type
        grouped = df.groupby('QUERY_TYPE')['OPERATION_COUNT'].sum().reset_index()

        chart_data = [
            {"value": int(row['OPERATION_COUNT']), "name": f"{row['QUERY_TYPE']} ({int(row['OPERATION_COUNT']):,})"}
            for _, row in grouped.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c:,}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "Query Type",
                    "type": "pie",
                    "radius": [15, 100],
                    "center": ["50%", "45%"],
                    "roseType": "area",
                    "itemStyle": {"borderRadius": 6},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No query type data available for chart.")


# ========== Cloning User Chart Functions ==========

def _render_cloning_user_chart_content(df, key_prefix=""):
    """Render cloning user chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_cloning_user_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_cloning_user_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_cloning_user_donut_pie_chart(df, key_prefix)
    else:
        _render_cloning_user_rose_pie_chart(df, key_prefix)


def _render_cloning_user_bar_chart(df, key_prefix=""):
    """Render cloning user bar chart using Plotly."""

    if 'USER_NAME' in df.columns and 'OPERATION_COUNT' in df.columns:
        # Group by user
        grouped = df.groupby('USER_NAME')['OPERATION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('OPERATION_COUNT', ascending=False).head(10)

        labels = grouped['USER_NAME'].tolist()
        values = grouped['OPERATION_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color='#0077B6',
                text=[f"{v:,}" for v in values],
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='<b>%{x}</b><br>Operations: %{y:,}<extra></extra>'
            )
        ])

        fig_bar.update_layout(
            height=350,
            xaxis_title='User',
            yaxis_title='Operation Count',
            showlegend=False,
            margin=dict(t=20, b=80, l=50, r=20),
            xaxis_tickangle=-45
        )

        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No user data available for chart.")


def _render_cloning_user_standard_pie_chart(df, key_prefix=""):
    """Render cloning user standard pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'OPERATION_COUNT' in df.columns:
        # Group by user
        grouped = df.groupby('USER_NAME')['OPERATION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('OPERATION_COUNT', ascending=False).head(10)

        chart_data = [
            {"value": int(row['OPERATION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['OPERATION_COUNT']):,})"}
            for _, row in grouped.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c:,}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "User",
                    "type": "pie",
                    "radius": ["0%", "50%"],
                    "center": ["50%", "40%"],
                    "itemStyle": {"borderRadius": 5},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No user data available for chart.")


def _render_cloning_user_donut_pie_chart(df, key_prefix=""):
    """Render cloning user donut pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'OPERATION_COUNT' in df.columns:
        # Group by user
        grouped = df.groupby('USER_NAME')['OPERATION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('OPERATION_COUNT', ascending=False).head(10)

        chart_data = [
            {"value": int(row['OPERATION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['OPERATION_COUNT']):,})"}
            for _, row in grouped.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c:,}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "User",
                    "type": "pie",
                    "radius": ["30%", "50%"],
                    "center": ["50%", "40%"],
                    "itemStyle": {"borderRadius": 5},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No user data available for chart.")


def _render_cloning_user_rose_pie_chart(df, key_prefix=""):
    """Render cloning user rose pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'OPERATION_COUNT' in df.columns:
        # Group by user
        grouped = df.groupby('USER_NAME')['OPERATION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('OPERATION_COUNT', ascending=False).head(10)

        chart_data = [
            {"value": int(row['OPERATION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['OPERATION_COUNT']):,})"}
            for _, row in grouped.iterrows()
        ]

        option = {
            "legend": {
                "bottom": "5",
                "left": "center",
                "orient": "horizontal",
                "textStyle": {"fontSize": 9},
                "type": "scroll"
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c:,}"
            },
            "toolbox": {
                "show": True,
                "feature": {
                    "dataView": {"show": True, "readOnly": False},
                    "restore": {"show": True},
                    "saveAsImage": {"show": True},
                },
            },
            "series": [
                {
                    "name": "User",
                    "type": "pie",
                    "radius": [15, 100],
                    "center": ["50%", "45%"],
                    "roseType": "area",
                    "itemStyle": {"borderRadius": 6},
                    "data": chart_data,
                }
            ],
        }

        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== CLONE Operations Summary Section ==========

def _render_clone_summary():
    """Render CLONE operation summary section."""

    st.markdown("---")
    st.markdown("#### CLONE Operations Summary")

    # Introduction text
    st.markdown("""
    **CLONE operation summary** showing total executions and distinct patterns over last 30 days, followed by top 10 most frequent clone patterns with execution counts, cloud services credits, and sample text.
    """)

    try:
        # CLONE Summary Query
        clone_summary_query = f"""
WITH clone_q AS (
  SELECT
    query_parameterized_hash,
    MIN(query_text) AS sample_text,
    NVL(COUNT(*), 0) AS executions,
    NVL(SUM(credits_used_cloud_services), 0) AS cs_credits
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND REGEXP_LIKE(query_text, '\\\\bCLONE\\\\b', 'i')
  GROUP BY query_parameterized_hash
)
SELECT
    NVL(SUM(executions), 0) AS total_clone_30d,
    NVL(COUNT(*), 0) AS distinct_clone_patterns_30d
FROM clone_q
"""


        # Execute the query
        clone_summary_df = _cached_sql("fo_clone_summary", clone_summary_query)

        if not clone_summary_df.empty:
            # Create Report Category and Metric

            # Display the table
            st.dataframe(
                clone_summary_df,
                use_container_width=True
            )

            # Get values for charts
            total_clone = int(clone_summary_df['TOTAL_CLONE_30D'].iloc[0]) if 'TOTAL_CLONE_30D' in clone_summary_df.columns else 0
            distinct_patterns = int(clone_summary_df['DISTINCT_CLONE_PATTERNS_30D'].iloc[0]) if 'DISTINCT_CLONE_PATTERNS_30D' in clone_summary_df.columns else 0

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### CLONE Summary Analysis Charts")

            clone_summary_chart_col1, clone_summary_chart_col2 = st.columns(2)

            with clone_summary_chart_col1.container():
                st.markdown(f"##### Total CLONE Commands: {total_clone:,}")
                _render_clone_total_chart_content(total_clone, distinct_patterns, key_prefix="clone_total_")

            with clone_summary_chart_col2.container():
                st.markdown(f"##### Distinct CLONE Patterns: {distinct_patterns:,}")
                _render_clone_patterns_summary_chart_content(total_clone, distinct_patterns, key_prefix="clone_patterns_summary_")

            # ========== Top 10 CLONE Patterns Section ==========
            _render_top_clone_patterns()

        else:
            st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '✅&nbsp;&nbsp;No CLONE operations detected in the last 30 days.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading CLONE summary: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== CLONE Total Chart Functions ==========

def _render_clone_total_chart_content(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE total chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_clone_total_bar_chart(total_clone, distinct_patterns, key_prefix)
    elif chart_type == "Pie Chart":
        _render_clone_total_standard_pie_chart(total_clone, distinct_patterns, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_clone_total_donut_pie_chart(total_clone, distinct_patterns, key_prefix)
    else:
        _render_clone_total_rose_pie_chart(total_clone, distinct_patterns, key_prefix)


def _render_clone_total_bar_chart(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE total bar chart using Plotly."""

    labels = ['Total CLONE Commands', 'Distinct Patterns']
    values = [total_clone, distinct_patterns]
    colors = ['#0077B6', '#00B4D8']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:,}" for v in values],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y:,}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_clone_total_standard_pie_chart(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE total standard pie chart using ECharts."""

    chart_data = [
        {"value": total_clone, "name": f"Total CLONE ({total_clone:,})"},
        {"value": distinct_patterns, "name": f"Distinct Patterns ({distinct_patterns:,})"},
    ]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 10}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#0077B6", "#00B4D8"],
        "series": [{"name": "CLONE Operations", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_clone_total_donut_pie_chart(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE total donut pie chart using ECharts."""

    chart_data = [
        {"value": total_clone, "name": f"Total CLONE ({total_clone:,})"},
        {"value": distinct_patterns, "name": f"Distinct Patterns ({distinct_patterns:,})"},
    ]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 10}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#0077B6", "#00B4D8"],
        "series": [{"name": "CLONE Operations", "type": "pie", "radius": ["30%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_clone_total_rose_pie_chart(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE total rose pie chart using ECharts."""

    chart_data = [
        {"value": total_clone, "name": f"Total CLONE ({total_clone:,})"},
        {"value": distinct_patterns, "name": f"Distinct Patterns ({distinct_patterns:,})"},
    ]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 10}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#0077B6", "#00B4D8"],
        "series": [{"name": "CLONE Operations", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== CLONE Patterns Summary Chart Functions ==========

def _render_clone_patterns_summary_chart_content(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE patterns summary chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_clone_patterns_summary_bar_chart(total_clone, distinct_patterns, key_prefix)
    elif chart_type == "Pie Chart":
        _render_clone_patterns_summary_standard_pie_chart(total_clone, distinct_patterns, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_clone_patterns_summary_donut_pie_chart(total_clone, distinct_patterns, key_prefix)
    else:
        _render_clone_patterns_summary_rose_pie_chart(total_clone, distinct_patterns, key_prefix)


def _render_clone_patterns_summary_bar_chart(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE patterns summary bar chart using Plotly."""

    avg_per_pattern = total_clone / distinct_patterns if distinct_patterns > 0 else 0

    labels = ['Distinct Patterns', 'Avg Executions/Pattern']
    values = [distinct_patterns, avg_per_pattern]
    colors = ['#00B4D8', '#E8A229']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{distinct_patterns:,}", f"{avg_per_pattern:.1f}"],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Value: %{y:.1f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_clone_patterns_summary_standard_pie_chart(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE patterns summary standard pie chart using ECharts."""

    avg_per_pattern = total_clone / distinct_patterns if distinct_patterns > 0 else 0

    chart_data = [
        {"value": distinct_patterns, "name": f"Patterns ({distinct_patterns:,})"},
        {"value": round(avg_per_pattern, 1), "name": f"Avg Exec/Pattern ({avg_per_pattern:.1f})"},
    ]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 10}},
        "tooltip": {"trigger": "item", "formatter": "{b}"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#00B4D8", "#E8A229"],
        "series": [{"name": "Pattern Analysis", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_clone_patterns_summary_donut_pie_chart(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE patterns summary donut pie chart using ECharts."""

    avg_per_pattern = total_clone / distinct_patterns if distinct_patterns > 0 else 0

    chart_data = [
        {"value": distinct_patterns, "name": f"Patterns ({distinct_patterns:,})"},
        {"value": round(avg_per_pattern, 1), "name": f"Avg Exec/Pattern ({avg_per_pattern:.1f})"},
    ]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 10}},
        "tooltip": {"trigger": "item", "formatter": "{b}"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#00B4D8", "#E8A229"],
        "series": [{"name": "Pattern Analysis", "type": "pie", "radius": ["30%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_clone_patterns_summary_rose_pie_chart(total_clone, distinct_patterns, key_prefix=""):
    """Render CLONE patterns summary rose pie chart using ECharts."""

    avg_per_pattern = total_clone / distinct_patterns if distinct_patterns > 0 else 0

    chart_data = [
        {"value": distinct_patterns, "name": f"Patterns ({distinct_patterns:,})"},
        {"value": round(avg_per_pattern, 1), "name": f"Avg Exec/Pattern ({avg_per_pattern:.1f})"},
    ]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 10}},
        "tooltip": {"trigger": "item", "formatter": "{b}"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#00B4D8", "#E8A229"],
        "series": [{"name": "Pattern Analysis", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Top 10 CLONE Patterns Section ==========

def _render_top_clone_patterns():
    """Render Top 10 most frequent CLONE patterns section."""

    st.markdown("---")
    st.markdown("#### Top 10 CLONE Patterns")

    try:
        # Top 10 CLONE Patterns Query
        top_clone_query = f"""
WITH clone_q AS (
  SELECT
    query_parameterized_hash,
    MIN(query_text) AS sample_text,
    NVL(COUNT(*), 0) AS executions,
    NVL(SUM(credits_used_cloud_services), 0) AS cs_credits
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time > DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND REGEXP_LIKE(query_text, '\\\\bCLONE\\\\b', 'i')
  GROUP BY query_parameterized_hash
)
SELECT
    query_parameterized_hash,
    executions,
    cs_credits,
    sample_text
FROM clone_q
ORDER BY executions DESC
LIMIT 10
"""


        # Execute the query
        top_clone_df = _cached_sql("fo_top_clone", top_clone_query)

        if not top_clone_df.empty:
            # Create Report Category and Metric

            # Display the table
            st.dataframe(
                top_clone_df,
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Top CLONE Patterns Analysis Charts")

            top_clone_chart_col1, top_clone_chart_col2 = st.columns(2)

            with top_clone_chart_col1.container():
                st.markdown("##### Execution Count by Pattern")
                _render_top_clone_execution_chart_content(top_clone_df, key_prefix="top_clone_exec_")

            with top_clone_chart_col2.container():
                st.markdown("##### Cloud Services Credits by Pattern")
                _render_top_clone_credits_chart_content(top_clone_df, key_prefix="top_clone_credits_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No CLONE patterns found for the last 30 days.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading top CLONE patterns: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Top CLONE Execution Chart Functions ==========

def _render_top_clone_execution_chart_content(df, key_prefix=""):
    """Render top CLONE execution chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_top_clone_execution_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_top_clone_execution_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_top_clone_execution_donut_pie_chart(df, key_prefix)
    else:
        _render_top_clone_execution_rose_pie_chart(df, key_prefix)


def _render_top_clone_execution_bar_chart(df, key_prefix=""):
    """Render top CLONE execution bar chart using Plotly."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'EXECUTIONS' in df.columns:
        chart_df = df.head(10)
        labels = [f"Pattern {i+1}" for i in range(len(chart_df))]
        values = chart_df['EXECUTIONS'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#0077B6', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Executions: %{y:,}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='Pattern', yaxis_title='Executions', showlegend=False, margin=dict(t=20, b=40, l=50, r=20))
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No execution data available for chart.")


def _render_top_clone_execution_standard_pie_chart(df, key_prefix=""):
    """Render top CLONE execution standard pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'EXECUTIONS' in df.columns:
        chart_df = df.head(10)
        chart_data = [{"value": int(row['EXECUTIONS']), "name": f"Pattern {i+1} ({int(row['EXECUTIONS']):,})"} for i, row in chart_df.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Executions", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No execution data available for chart.")


def _render_top_clone_execution_donut_pie_chart(df, key_prefix=""):
    """Render top CLONE execution donut pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'EXECUTIONS' in df.columns:
        chart_df = df.head(10)
        chart_data = [{"value": int(row['EXECUTIONS']), "name": f"Pattern {i+1} ({int(row['EXECUTIONS']):,})"} for i, row in chart_df.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Executions", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No execution data available for chart.")


def _render_top_clone_execution_rose_pie_chart(df, key_prefix=""):
    """Render top CLONE execution rose pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'EXECUTIONS' in df.columns:
        chart_df = df.head(10)
        chart_data = [{"value": int(row['EXECUTIONS']), "name": f"Pattern {i+1} ({int(row['EXECUTIONS']):,})"} for i, row in chart_df.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Executions", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No execution data available for chart.")


# ========== Top CLONE Credits Chart Functions ==========

def _render_top_clone_credits_chart_content(df, key_prefix=""):
    """Render top CLONE credits chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_top_clone_credits_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_top_clone_credits_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_top_clone_credits_donut_pie_chart(df, key_prefix)
    else:
        _render_top_clone_credits_rose_pie_chart(df, key_prefix)


def _render_top_clone_credits_bar_chart(df, key_prefix=""):
    """Render top CLONE credits bar chart using Plotly."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'CS_CREDITS' in df.columns:
        chart_df = df.head(10)
        labels = [f"Pattern {i+1}" for i in range(len(chart_df))]
        values = chart_df['CS_CREDITS'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#E8A229', text=[f"{v:.4f}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>CS Credits: %{y:.4f}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='Pattern', yaxis_title='Cloud Services Credits', showlegend=False, margin=dict(t=20, b=40, l=50, r=20))
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No credits data available for chart.")


def _render_top_clone_credits_standard_pie_chart(df, key_prefix=""):
    """Render top CLONE credits standard pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'CS_CREDITS' in df.columns:
        chart_df = df.head(10)
        chart_data = [{"value": round(float(row['CS_CREDITS']), 4), "name": f"Pattern {i+1} ({float(row['CS_CREDITS']):.4f})"} for i, row in chart_df.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "CS Credits", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No credits data available for chart.")


def _render_top_clone_credits_donut_pie_chart(df, key_prefix=""):
    """Render top CLONE credits donut pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'CS_CREDITS' in df.columns:
        chart_df = df.head(10)
        chart_data = [{"value": round(float(row['CS_CREDITS']), 4), "name": f"Pattern {i+1} ({float(row['CS_CREDITS']):.4f})"} for i, row in chart_df.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "CS Credits", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No credits data available for chart.")


def _render_top_clone_credits_rose_pie_chart(df, key_prefix=""):
    """Render top CLONE credits rose pie chart using ECharts."""

    if 'QUERY_PARAMETERIZED_HASH' in df.columns and 'CS_CREDITS' in df.columns:
        chart_df = df.head(10)
        chart_data = [{"value": round(float(row['CS_CREDITS']), 4), "name": f"Pattern {i+1} ({float(row['CS_CREDITS']):.4f})"} for i, row in chart_df.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "CS Credits", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== Simple Queries Section ==========

def _render_simple_queries():
    """Render high-frequency simple queries section."""

    st.markdown("#### Pattern: High-frequency, simple queries")

    # Introduction text
    st.markdown("""
    **Top 10 high-volume short query patterns** (<100ms, >1000 executions) over last 30 days showing normalized query template, user, client tool, execution count, and cloud services credits.
    """)


    try:
        # Simple Queries Query
        simple_queries_query = f"""
SELECT
    'Short Queries (<100ms)' AS pattern_type,
    REGEXP_REPLACE(q.query_text, '\\\\b\\\\d+\\\\b', '?') AS query_template,
    q.user_name,
    s.client_application_id AS client_tool,
    NVL(COUNT(*), 0) AS execution_count,
    NVL(SUM(q.credits_used_cloud_services), 0) AS cloud_services_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history q
JOIN SNOWFLAKE.ACCOUNT_USAGE.sessions s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND q.total_elapsed_time < 100
  AND q.query_type = 'SELECT'
GROUP BY ALL
HAVING NVL(COUNT(*), 0) > 1000
ORDER BY execution_count DESC
LIMIT 10
"""


        # Execute the query
        simple_df = _cached_sql("fo_simple_queries", simple_queries_query)

        if not simple_df.empty:
            # Create Report Category and Metric

            # Display the table
            st.dataframe(
                simple_df,
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Simple Queries Analysis Charts")

            simple_chart_col1, simple_chart_col2 = st.columns(2)

            with simple_chart_col1.container():
                st.markdown("##### Execution Count by User")
                _render_simple_user_chart_content(simple_df, key_prefix="simple_user_")

            with simple_chart_col2.container():
                st.markdown("##### Execution Count by Client Tool")
                _render_simple_client_chart_content(simple_df, key_prefix="simple_client_")

        else:
            st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '✅&nbsp;&nbsp;No high-frequency simple query patterns detected (>1000 executions, <100ms).'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading simple queries: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Simple User Chart Functions ==========

def _render_simple_user_chart_content(df, key_prefix=""):
    """Render simple queries user chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_simple_user_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_simple_user_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_simple_user_donut_pie_chart(df, key_prefix)
    else:
        _render_simple_user_rose_pie_chart(df, key_prefix)


def _render_simple_user_bar_chart(df, key_prefix=""):
    """Render simple queries user bar chart using Plotly."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        labels = grouped['USER_NAME'].tolist()
        values = grouped['EXECUTION_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#75C2D8', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Executions: %{y:,}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='User', yaxis_title='Execution Count', showlegend=False, margin=dict(t=20, b=80, l=50, r=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No user data available for chart.")


def _render_simple_user_standard_pie_chart(df, key_prefix=""):
    """Render simple queries user standard pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No user data available for chart.")


def _render_simple_user_donut_pie_chart(df, key_prefix=""):
    """Render simple queries user donut pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No user data available for chart.")


def _render_simple_user_rose_pie_chart(df, key_prefix=""):
    """Render simple queries user rose pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No user data available for chart.")


# ========== Simple Client Chart Functions ==========

def _render_simple_client_chart_content(df, key_prefix=""):
    """Render simple queries client chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_simple_client_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_simple_client_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_simple_client_donut_pie_chart(df, key_prefix)
    else:
        _render_simple_client_rose_pie_chart(df, key_prefix)


def _render_simple_client_bar_chart(df, key_prefix=""):
    """Render simple queries client bar chart using Plotly."""

    if 'CLIENT_TOOL' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('CLIENT_TOOL')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        labels = grouped['CLIENT_TOOL'].tolist()
        values = grouped['EXECUTION_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#48CAE4', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Executions: %{y:,}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='Client Tool', yaxis_title='Execution Count', showlegend=False, margin=dict(t=20, b=80, l=50, r=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No client tool data available for chart.")


def _render_simple_client_standard_pie_chart(df, key_prefix=""):
    """Render simple queries client standard pie chart using ECharts."""

    if 'CLIENT_TOOL' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('CLIENT_TOOL')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['CLIENT_TOOL']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Client Tool", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No client tool data available for chart.")


def _render_simple_client_donut_pie_chart(df, key_prefix=""):
    """Render simple queries client donut pie chart using ECharts."""

    if 'CLIENT_TOOL' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('CLIENT_TOOL')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['CLIENT_TOOL']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Client Tool", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No client tool data available for chart.")


def _render_simple_client_rose_pie_chart(df, key_prefix=""):
    """Render simple queries client rose pie chart using ECharts."""

    if 'CLIENT_TOOL' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('CLIENT_TOOL')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['CLIENT_TOOL']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Client Tool", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== INFORMATION_SCHEMA Queries Section ==========

def _render_info_schema_queries():
    """Render high-frequency INFORMATION_SCHEMA queries section."""

    st.markdown("#### Pattern: High-frequency INFORMATION_SCHEMA queries")

    # Introduction text
    st.markdown("""
    **Top 10 INFORMATION_SCHEMA metadata scan patterns** over last 30 days by execution count, showing user, client tool, query preview, and average compilation time.
    """)


    try:
        # INFORMATION_SCHEMA Queries Query
        info_schema_query = f"""
SELECT
    'Metadata Scan' AS pattern_type,
    q.user_name,
    s.client_application_id AS client_tool,
    SUBSTR(q.query_text, 1, 80) AS query_preview,
    NVL(COUNT(*), 0) AS execution_count,
    NVL(AVG(q.compilation_time), 0) AS avg_compile_ms
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history q
JOIN SNOWFLAKE.ACCOUNT_USAGE.sessions s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND (q.schema_name = 'INFORMATION_SCHEMA' OR q.query_text ILIKE '%INFORMATION_SCHEMA%')
GROUP BY ALL
ORDER BY execution_count DESC
LIMIT 10
"""


        # Execute the query
        info_schema_df = _cached_sql("fo_info_schema", info_schema_query)

        if not info_schema_df.empty:
            # Create Report Category and Metric

            # Display the table
            st.dataframe(
                info_schema_df,
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### INFORMATION_SCHEMA Analysis Charts")

            info_schema_chart_col1, info_schema_chart_col2 = st.columns(2)

            with info_schema_chart_col1.container():
                st.markdown("##### Execution Count by User")
                _render_info_schema_user_chart_content(info_schema_df, key_prefix="info_schema_user_")

            with info_schema_chart_col2.container():
                st.markdown("##### Execution Count by Client Tool")
                _render_info_schema_client_chart_content(info_schema_df, key_prefix="info_schema_client_")

        else:
            st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '✅&nbsp;&nbsp;No high-frequency INFORMATION_SCHEMA queries detected in the last 30 days.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading INFORMATION_SCHEMA queries: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Info Schema User Chart Functions ==========

def _render_info_schema_user_chart_content(df, key_prefix=""):
    """Render info schema user chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_info_schema_user_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_info_schema_user_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_info_schema_user_donut_pie_chart(df, key_prefix)
    else:
        _render_info_schema_user_rose_pie_chart(df, key_prefix)


def _render_info_schema_user_bar_chart(df, key_prefix=""):
    """Render info schema user bar chart using Plotly."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        labels = grouped['USER_NAME'].tolist()
        values = grouped['EXECUTION_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#11567F', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Executions: %{y:,}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='User', yaxis_title='Execution Count', showlegend=False, margin=dict(t=20, b=80, l=50, r=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No user data available for chart.")


def _render_info_schema_user_standard_pie_chart(df, key_prefix=""):
    """Render info schema user standard pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No user data available for chart.")


def _render_info_schema_user_donut_pie_chart(df, key_prefix=""):
    """Render info schema user donut pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No user data available for chart.")


def _render_info_schema_user_rose_pie_chart(df, key_prefix=""):
    """Render info schema user rose pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No user data available for chart.")


# ========== Info Schema Client Chart Functions ==========

def _render_info_schema_client_chart_content(df, key_prefix=""):
    """Render info schema client chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_info_schema_client_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_info_schema_client_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_info_schema_client_donut_pie_chart(df, key_prefix)
    else:
        _render_info_schema_client_rose_pie_chart(df, key_prefix)


def _render_info_schema_client_bar_chart(df, key_prefix=""):
    """Render info schema client bar chart using Plotly."""

    if 'CLIENT_TOOL' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('CLIENT_TOOL')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        labels = grouped['CLIENT_TOOL'].tolist()
        values = grouped['EXECUTION_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#E74C3C', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Executions: %{y:,}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='Client Tool', yaxis_title='Execution Count', showlegend=False, margin=dict(t=20, b=80, l=50, r=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No client tool data available for chart.")


def _render_info_schema_client_standard_pie_chart(df, key_prefix=""):
    """Render info schema client standard pie chart using ECharts."""

    if 'CLIENT_TOOL' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('CLIENT_TOOL')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['CLIENT_TOOL']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Client Tool", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No client tool data available for chart.")


def _render_info_schema_client_donut_pie_chart(df, key_prefix=""):
    """Render info schema client donut pie chart using ECharts."""

    if 'CLIENT_TOOL' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('CLIENT_TOOL')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['CLIENT_TOOL']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Client Tool", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No client tool data available for chart.")


def _render_info_schema_client_rose_pie_chart(df, key_prefix=""):
    """Render info schema client rose pie chart using ECharts."""

    if 'CLIENT_TOOL' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('CLIENT_TOOL')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['CLIENT_TOOL']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Client Tool", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ========== SHOW Commands Section ==========

def _render_show_commands():
    """Render high-frequency SHOW commands section."""

    st.markdown("#### Pattern: High-frequency SHOW commands (by data applications and third-party tools)")

    # Introduction text
    st.markdown("""
    **Top 10 most frequently executed SHOW commands** over last 30 days by execution count, showing command type, user, and client tool.
    """)


    try:
        # SHOW Commands Query
        show_commands_query = f"""
SELECT
    q.query_type,
    SUBSTR(q.query_text, 1, 50) AS command_type,
    q.user_name,
    s.client_application_id AS client_tool,
    NVL(COUNT(*), 0) AS execution_count
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history q
JOIN SNOWFLAKE.ACCOUNT_USAGE.sessions s
    ON q.session_id = s.session_id
    AND s.created_on >= DATEADD('day', -31, CURRENT_TIMESTAMP())
WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND q.query_type = 'SHOW'
GROUP BY ALL
ORDER BY execution_count DESC
LIMIT 10
"""


        # Execute the query
        show_df = _cached_sql("fo_show_commands", show_commands_query)

        if not show_df.empty:
            # Create Report Category and Metric

            # Display the table
            st.dataframe(
                show_df,
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### SHOW Commands Analysis Charts")

            show_chart_col1, show_chart_col2 = st.columns(2)

            with show_chart_col1.container():
                st.markdown("##### Execution Count by Command Type")
                _render_show_command_type_chart_content(show_df, key_prefix="show_cmd_type_")

            with show_chart_col2.container():
                st.markdown("##### Execution Count by User")
                _render_show_user_chart_content(show_df, key_prefix="show_user_")

        else:
            st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '✅&nbsp;&nbsp;No high-frequency SHOW command patterns detected.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading SHOW commands: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== SHOW Command Type Chart Functions ==========

def _render_show_command_type_chart_content(df, key_prefix=""):
    """Render SHOW commands command type chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_show_command_type_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_show_command_type_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_show_command_type_donut_pie_chart(df, key_prefix)
    else:
        _render_show_command_type_rose_pie_chart(df, key_prefix)


def _render_show_command_type_bar_chart(df, key_prefix=""):
    """Render SHOW commands command type bar chart using Plotly."""

    if 'COMMAND_TYPE' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('COMMAND_TYPE')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        labels = grouped['COMMAND_TYPE'].tolist()
        values = grouped['EXECUTION_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#00B4D8', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Executions: %{y:,}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='Command Type', yaxis_title='Execution Count', showlegend=False, margin=dict(t=20, b=100, l=50, r=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No command type data available for chart.")


def _render_show_command_type_standard_pie_chart(df, key_prefix=""):
    """Render SHOW commands command type standard pie chart using ECharts."""

    if 'COMMAND_TYPE' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('COMMAND_TYPE')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['COMMAND_TYPE'][:30]}... ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Command Type", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No command type data available for chart.")


def _render_show_command_type_donut_pie_chart(df, key_prefix=""):
    """Render SHOW commands command type donut pie chart using ECharts."""

    if 'COMMAND_TYPE' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('COMMAND_TYPE')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['COMMAND_TYPE'][:30]}... ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Command Type", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No command type data available for chart.")


def _render_show_command_type_rose_pie_chart(df, key_prefix=""):
    """Render SHOW commands command type rose pie chart using ECharts."""

    if 'COMMAND_TYPE' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('COMMAND_TYPE')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['COMMAND_TYPE'][:30]}... ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Command Type", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No command type data available for chart.")


# ========== SHOW User Chart Functions ==========

def _render_show_user_chart_content(df, key_prefix=""):
    """Render SHOW commands user chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_show_user_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_show_user_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_show_user_donut_pie_chart(df, key_prefix)
    else:
        _render_show_user_rose_pie_chart(df, key_prefix)


def _render_show_user_bar_chart(df, key_prefix=""):
    """Render SHOW commands user bar chart using Plotly."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        labels = grouped['USER_NAME'].tolist()
        values = grouped['EXECUTION_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#0077B6', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Executions: %{y:,}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='User', yaxis_title='Execution Count', showlegend=False, margin=dict(t=20, b=80, l=50, r=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No user data available for chart.")


def _render_show_user_standard_pie_chart(df, key_prefix=""):
    """Render SHOW commands user standard pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No user data available for chart.")


def _render_show_user_donut_pie_chart(df, key_prefix=""):
    """Render SHOW commands user donut pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No user data available for chart.")


def _render_show_user_rose_pie_chart(df, key_prefix=""):
    """Render SHOW commands user rose pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'EXECUTION_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['EXECUTION_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('EXECUTION_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['EXECUTION_COUNT']), "name": f"{row['USER_NAME']} ({int(row['EXECUTION_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No user data available for chart.")


# ========== Single Row Inserts Section ==========

def _render_single_row_inserts():
    """Render single row inserts and fragmented schemas section."""

    st.markdown("#### Pattern: Single row inserts and fragmented schemas (by data applications)")

    # Introduction text
    st.markdown("""
    **Top 10 single-row INSERT patterns** over last 30 days by frequency, showing target table, user, insert count, and total rows loaded for potential batching optimization.
    """)


    try:
        # Single Row Inserts Query
        single_row_inserts_query = f"""
SELECT
    'Single Row Insert' AS pattern_type,
    REGEXP_SUBSTR(query_text, 'INSERT INTO ([a-zA-Z0-9_.]+)', 1, 1, 'i', 1) AS target_table,
    user_name,
    NVL(COUNT(*), 0) AS insert_count,
    NVL(SUM(rows_produced), 0) AS total_rows_loaded
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND query_type = 'INSERT'
  AND rows_produced = 1
GROUP BY ALL
ORDER BY insert_count DESC
LIMIT 10
"""


        # Execute the query
        inserts_df = _cached_sql("fo_single_row_inserts", single_row_inserts_query)

        if not inserts_df.empty:
            # Create Report Category and Metric

            # Display the table
            st.dataframe(
                inserts_df,
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Single Row Inserts Analysis Charts")

            inserts_chart_col1, inserts_chart_col2 = st.columns(2)

            with inserts_chart_col1.container():
                st.markdown("##### Insert Count by Target Table")
                _render_inserts_table_chart_content(inserts_df, key_prefix="inserts_table_")

            with inserts_chart_col2.container():
                st.markdown("##### Insert Count by User")
                _render_inserts_user_chart_content(inserts_df, key_prefix="inserts_user_")

        else:
            st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '✅&nbsp;&nbsp;No single-row INSERT patterns detected.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading single row inserts: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Single Row Inserts Target Table Chart Functions ==========

def _render_inserts_table_chart_content(df, key_prefix=""):
    """Render single row inserts target table chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_inserts_table_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_inserts_table_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_inserts_table_donut_pie_chart(df, key_prefix)
    else:
        _render_inserts_table_rose_pie_chart(df, key_prefix)


def _render_inserts_table_bar_chart(df, key_prefix=""):
    """Render single row inserts target table bar chart using Plotly."""

    if 'TARGET_TABLE' in df.columns and 'INSERT_COUNT' in df.columns:
        grouped = df.groupby('TARGET_TABLE')['INSERT_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('INSERT_COUNT', ascending=False).head(10)

        labels = grouped['TARGET_TABLE'].tolist()
        values = grouped['INSERT_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#E8A229', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Insert Count: %{y:,}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='Target Table', yaxis_title='Insert Count', showlegend=False, margin=dict(t=20, b=100, l=50, r=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No target table data available for chart.")


def _render_inserts_table_standard_pie_chart(df, key_prefix=""):
    """Render single row inserts target table standard pie chart using ECharts."""

    if 'TARGET_TABLE' in df.columns and 'INSERT_COUNT' in df.columns:
        grouped = df.groupby('TARGET_TABLE')['INSERT_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('INSERT_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['INSERT_COUNT']), "name": f"{row['TARGET_TABLE'][:25]}... ({int(row['INSERT_COUNT']):,})"} if len(str(row['TARGET_TABLE'])) > 25 else {"value": int(row['INSERT_COUNT']), "name": f"{row['TARGET_TABLE']} ({int(row['INSERT_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Target Table", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No target table data available for chart.")


def _render_inserts_table_donut_pie_chart(df, key_prefix=""):
    """Render single row inserts target table donut pie chart using ECharts."""

    if 'TARGET_TABLE' in df.columns and 'INSERT_COUNT' in df.columns:
        grouped = df.groupby('TARGET_TABLE')['INSERT_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('INSERT_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['INSERT_COUNT']), "name": f"{row['TARGET_TABLE'][:25]}... ({int(row['INSERT_COUNT']):,})"} if len(str(row['TARGET_TABLE'])) > 25 else {"value": int(row['INSERT_COUNT']), "name": f"{row['TARGET_TABLE']} ({int(row['INSERT_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Target Table", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No target table data available for chart.")


def _render_inserts_table_rose_pie_chart(df, key_prefix=""):
    """Render single row inserts target table rose pie chart using ECharts."""

    if 'TARGET_TABLE' in df.columns and 'INSERT_COUNT' in df.columns:
        grouped = df.groupby('TARGET_TABLE')['INSERT_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('INSERT_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['INSERT_COUNT']), "name": f"{row['TARGET_TABLE'][:25]}... ({int(row['INSERT_COUNT']):,})"} if len(str(row['TARGET_TABLE'])) > 25 else {"value": int(row['INSERT_COUNT']), "name": f"{row['TARGET_TABLE']} ({int(row['INSERT_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "Target Table", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No target table data available for chart.")


# ========== Single Row Inserts User Chart Functions ==========

def _render_inserts_user_chart_content(df, key_prefix=""):
    """Render single row inserts user chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_inserts_user_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_inserts_user_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_inserts_user_donut_pie_chart(df, key_prefix)
    else:
        _render_inserts_user_rose_pie_chart(df, key_prefix)


def _render_inserts_user_bar_chart(df, key_prefix=""):
    """Render single row inserts user bar chart using Plotly."""

    if 'USER_NAME' in df.columns and 'INSERT_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['INSERT_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('INSERT_COUNT', ascending=False).head(10)

        labels = grouped['USER_NAME'].tolist()
        values = grouped['INSERT_COUNT'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#0077B6', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Insert Count: %{y:,}<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='User', yaxis_title='Insert Count', showlegend=False, margin=dict(t=20, b=80, l=50, r=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No user data available for chart.")


def _render_inserts_user_standard_pie_chart(df, key_prefix=""):
    """Render single row inserts user standard pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'INSERT_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['INSERT_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('INSERT_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['INSERT_COUNT']), "name": f"{row['USER_NAME']} ({int(row['INSERT_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No user data available for chart.")


def _render_inserts_user_donut_pie_chart(df, key_prefix=""):
    """Render single row inserts user donut pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'INSERT_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['INSERT_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('INSERT_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['INSERT_COUNT']), "name": f"{row['USER_NAME']} ({int(row['INSERT_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No user data available for chart.")


def _render_inserts_user_rose_pie_chart(df, key_prefix=""):
    """Render single row inserts user rose pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'INSERT_COUNT' in df.columns:
        grouped = df.groupby('USER_NAME')['INSERT_COUNT'].sum().reset_index()
        grouped = grouped.sort_values('INSERT_COUNT', ascending=False).head(10)

        chart_data = [{"value": int(row['INSERT_COUNT']), "name": f"{row['USER_NAME']} ({int(row['INSERT_COUNT']):,})"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,}"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No user data available for chart.")


# ========== Complex SQL Queries Section ==========

def _render_complex_queries():
    """Render complex SQL queries section with long compilation times."""

    st.markdown("#### Pattern: Complex SQL queries")

    # Introduction text
    st.markdown("""
    **Top 10 queries with longest compilation times** (>5 seconds) over last 30 days showing query ID, user, SQL length, compile/execution times, and percentage of time spent compiling.
    """)


    try:
        # Complex SQL Queries Query
        complex_queries_query = f"""
SELECT
    'Complex Compilation' AS pattern_type,
    query_id,
    user_name,
    LENGTH(query_text) AS sql_character_length,
    compilation_time AS compile_ms,
    execution_time AS exec_ms,
    ROUND(NVL(compilation_time, 0) / (NVL(total_elapsed_time, 0) * 100), 1) AS pct_time_compiling
FROM SNOWFLAKE.ACCOUNT_USAGE.query_history
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND compilation_time > 5000
ORDER BY compilation_time DESC
LIMIT 10
"""


        # Execute the query
        complex_df = _cached_sql("fo_complex_queries", complex_queries_query)

        if not complex_df.empty:
            # Create Report Category and Metric

            # Display the table
            st.dataframe(
                complex_df,
                use_container_width=True
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Complex Queries Analysis Charts")

            complex_chart_col1, complex_chart_col2 = st.columns(2)

            with complex_chart_col1.container():
                st.markdown("##### Compilation Time by User")
                _render_complex_user_chart_content(complex_df, key_prefix="complex_user_")

            with complex_chart_col2.container():
                st.markdown("##### SQL Character Length by Query")
                _render_complex_length_chart_content(complex_df, key_prefix="complex_length_")

        else:
            st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '✅&nbsp;&nbsp;No complex query patterns detected (compilation time >5 seconds).'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading complex queries: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Complex Queries User Chart Functions ==========

def _render_complex_user_chart_content(df, key_prefix=""):
    """Render complex queries user chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_complex_user_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_complex_user_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_complex_user_donut_pie_chart(df, key_prefix)
    else:
        _render_complex_user_rose_pie_chart(df, key_prefix)


def _render_complex_user_bar_chart(df, key_prefix=""):
    """Render complex queries user bar chart using Plotly."""

    if 'USER_NAME' in df.columns and 'COMPILE_MS' in df.columns:
        grouped = df.groupby('USER_NAME')['COMPILE_MS'].sum().reset_index()
        grouped = grouped.sort_values('COMPILE_MS', ascending=False).head(10)

        labels = grouped['USER_NAME'].tolist()
        values = grouped['COMPILE_MS'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#E74C3C', text=[f"{v:,.0f}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Compile Time: %{y:,.0f} ms<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='User', yaxis_title='Compilation Time (ms)', showlegend=False, margin=dict(t=20, b=80, l=50, r=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No user data available for chart.")


def _render_complex_user_standard_pie_chart(df, key_prefix=""):
    """Render complex queries user standard pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'COMPILE_MS' in df.columns:
        grouped = df.groupby('USER_NAME')['COMPILE_MS'].sum().reset_index()
        grouped = grouped.sort_values('COMPILE_MS', ascending=False).head(10)

        chart_data = [{"value": int(row['COMPILE_MS']), "name": f"{row['USER_NAME']} ({int(row['COMPILE_MS']):,} ms)"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ms"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No user data available for chart.")


def _render_complex_user_donut_pie_chart(df, key_prefix=""):
    """Render complex queries user donut pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'COMPILE_MS' in df.columns:
        grouped = df.groupby('USER_NAME')['COMPILE_MS'].sum().reset_index()
        grouped = grouped.sort_values('COMPILE_MS', ascending=False).head(10)

        chart_data = [{"value": int(row['COMPILE_MS']), "name": f"{row['USER_NAME']} ({int(row['COMPILE_MS']):,} ms)"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ms"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No user data available for chart.")


def _render_complex_user_rose_pie_chart(df, key_prefix=""):
    """Render complex queries user rose pie chart using ECharts."""

    if 'USER_NAME' in df.columns and 'COMPILE_MS' in df.columns:
        grouped = df.groupby('USER_NAME')['COMPILE_MS'].sum().reset_index()
        grouped = grouped.sort_values('COMPILE_MS', ascending=False).head(10)

        chart_data = [{"value": int(row['COMPILE_MS']), "name": f"{row['USER_NAME']} ({int(row['COMPILE_MS']):,} ms)"} for _, row in grouped.iterrows()]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ms"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "User", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No user data available for chart.")


# ========== Complex Queries SQL Length Chart Functions ==========

def _render_complex_length_chart_content(df, key_prefix=""):
    """Render complex queries SQL length chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_complex_length_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_complex_length_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_complex_length_donut_pie_chart(df, key_prefix)
    else:
        _render_complex_length_rose_pie_chart(df, key_prefix)


def _render_complex_length_bar_chart(df, key_prefix=""):
    """Render complex queries SQL length bar chart using Plotly."""

    if 'QUERY_ID' in df.columns and 'SQL_CHARACTER_LENGTH' in df.columns:
        chart_df = df.head(10).copy()
        # Create short labels for query IDs
        labels = [f"Q{i+1}" for i in range(len(chart_df))]
        values = chart_df['SQL_CHARACTER_LENGTH'].tolist()

        fig_bar = go.Figure(data=[
            go.Bar(x=labels, y=values, marker_color='#29B5E8', text=[f"{v:,}" for v in values], textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>SQL Length: %{y:,} chars<extra></extra>')
        ])
        fig_bar.update_layout(height=350, xaxis_title='Query', yaxis_title='SQL Character Length', showlegend=False, margin=dict(t=20, b=40, l=50, r=20))
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")
    else:
        st.info("No SQL length data available for chart.")


def _render_complex_length_standard_pie_chart(df, key_prefix=""):
    """Render complex queries SQL length standard pie chart using ECharts."""

    if 'QUERY_ID' in df.columns and 'SQL_CHARACTER_LENGTH' in df.columns:
        chart_df = df.head(10).copy()
        chart_data = [{"value": int(row['SQL_CHARACTER_LENGTH']), "name": f"Q{i+1} ({int(row['SQL_CHARACTER_LENGTH']):,})"} for i, (_, row) in enumerate(chart_df.iterrows())]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b} chars"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "SQL Length", "type": "pie", "radius": ["0%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")
    else:
        st.info("No SQL length data available for chart.")


def _render_complex_length_donut_pie_chart(df, key_prefix=""):
    """Render complex queries SQL length donut pie chart using ECharts."""

    if 'QUERY_ID' in df.columns and 'SQL_CHARACTER_LENGTH' in df.columns:
        chart_df = df.head(10).copy()
        chart_data = [{"value": int(row['SQL_CHARACTER_LENGTH']), "name": f"Q{i+1} ({int(row['SQL_CHARACTER_LENGTH']):,})"} for i, (_, row) in enumerate(chart_df.iterrows())]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b} chars"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "SQL Length", "type": "pie", "radius": ["30%", "50%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")
    else:
        st.info("No SQL length data available for chart.")


def _render_complex_length_rose_pie_chart(df, key_prefix=""):
    """Render complex queries SQL length rose pie chart using ECharts."""

    if 'QUERY_ID' in df.columns and 'SQL_CHARACTER_LENGTH' in df.columns:
        chart_df = df.head(10).copy()
        chart_data = [{"value": int(row['SQL_CHARACTER_LENGTH']), "name": f"Q{i+1} ({int(row['SQL_CHARACTER_LENGTH']):,})"} for i, (_, row) in enumerate(chart_df.iterrows())]

        option = {"legend": {"bottom": "5", "left": "center", "orient": "horizontal", "textStyle": {"fontSize": 9}, "type": "scroll"}, "tooltip": {"trigger": "item", "formatter": "{b} chars"}, "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}}, "series": [{"name": "SQL Length", "type": "pie", "radius": [15, 100], "center": ["50%", "45%"], "roseType": "area", "itemStyle": {"borderRadius": 6}, "data": chart_data}]}
        st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")
    else:
        st.info("No SQL length data available for chart.")


def _render_copy_poor_selectivity():
    import plotly.graph_objects as go
    import pandas as pd
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>COPY Commands with Poor Selectivity:</b> COPY commands that have high execution '
        'time (>1 second) but load fewer than 100 rows. This pattern indicates excessive file listing '
        'overhead — the query is scanning many files but extracting very little data.</div>',
        unsafe_allow_html=True)
    try:
        session = st.session_state.session
        summary_query = """
        WITH copy_q AS (
            SELECT
                QUERY_PARAMETERIZED_HASH,
                MIN(QUERY_TEXT) AS sample_text,
                COUNT(*) AS executions,
                SUM(CREDITS_USED_CLOUD_SERVICES) AS cs_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE START_TIME > DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND REGEXP_LIKE(QUERY_TEXT, '^\\s*COPY\\s+INTO\\b', 'i')
            GROUP BY QUERY_PARAMETERIZED_HASH
        )
        SELECT
            SUM(executions) AS total_copy_commands_30d,
            COUNT(*) AS distinct_copy_patterns,
            ROUND(SUM(cs_credits), 4) AS total_cloud_services_credits
        FROM copy_q
        """
        patterns_query = """
        SELECT
            SUBSTR(QUERY_TEXT, 1, 120) AS query_pattern,
            COUNT(*) AS execution_count,
            SUM(ROWS_PRODUCED) AS total_rows_loaded,
            ROUND(AVG(COMPILATION_TIME), 0) AS avg_compile_ms,
            ROUND(AVG(EXECUTION_TIME), 0) AS avg_execution_ms,
            ROUND(SUM(CREDITS_USED_CLOUD_SERVICES), 4) AS cloud_services_credits,
            CASE
                WHEN AVG(COMPILATION_TIME) > 5000 THEN 'HIGH_FILE_LISTING_OVERHEAD'
                WHEN COUNT(*) > 100 AND SUM(ROWS_PRODUCED) < 1000 THEN 'REDUNDANT_PATTERN'
                ELSE 'INVESTIGATE'
            END AS issue_type
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
          AND QUERY_TYPE = 'COPY'
          AND EXECUTION_TIME > 1000
          AND ROWS_PRODUCED < 100
        GROUP BY SUBSTR(QUERY_TEXT, 1, 120)
        ORDER BY execution_count DESC
        LIMIT 10
        """
        df_summary = _cached_sql("fo_summary", summary_query)
        df_patterns = _cached_sql("fo_patterns", patterns_query)
        col1, col2, col3 = st.columns(3)
        if not df_summary.empty:
            total_copy = df_summary['TOTAL_COPY_COMMANDS_30D'].iloc[0] if not df_summary.empty else 0
            distinct = df_summary['DISTINCT_COPY_PATTERNS'].iloc[0] if not df_summary.empty else 0
            cs_credits = df_summary['TOTAL_CLOUD_SERVICES_CREDITS'].iloc[0] if not df_summary.empty else 0
            with col1:
                st.metric("Total COPY Commands (30d)", f"{int(total_copy):,}" if pd.notna(total_copy) and total_copy else "0")
            with col2:
                st.metric("Distinct Patterns", f"{int(distinct):,}" if pd.notna(distinct) and distinct else "0")
            with col3:
                st.metric("Cloud Services Credits", f"{float(cs_credits):.4f}" if pd.notna(cs_credits) and cs_credits else "0.0000")
        if df_patterns.empty:
            st.success("No COPY commands with poor selectivity detected in the last 30 days.")
            return
        df_patterns['EXECUTION_COUNT'] = pd.to_numeric(df_patterns['EXECUTION_COUNT'], errors='coerce').fillna(0)
        df_patterns['CLOUD_SERVICES_CREDITS'] = pd.to_numeric(df_patterns['CLOUD_SERVICES_CREDITS'], errors='coerce').fillna(0)
        _issue_colors = {'HIGH_FILE_LISTING_OVERHEAD': '#E74C3C', 'REDUNDANT_PATTERN': '#E8A229', 'INVESTIGATE': '#75C2D8'}
        bar_colors = [_issue_colors.get(t, '#29B5E8') for t in df_patterns['ISSUE_TYPE']]
        short_labels = [p[:40] + '...' if len(p) > 40 else p for p in df_patterns['QUERY_PATTERN']]
        fig = go.Figure(go.Bar(
            y=short_labels, x=df_patterns['EXECUTION_COUNT'],
            orientation='h',
            marker_color=bar_colors,
            text=df_patterns['EXECUTION_COUNT'], textposition='outside',
            hovertemplate='%{y}<br>Executions: %{x}<extra></extra>'
        ))
        fig.update_layout(
            title='COPY Patterns with Poor Selectivity (Last 30 Days)',
            xaxis_title='Execution Count', yaxis_title='Query Pattern',
            height=max(300, len(df_patterns) * 45 + 80),
            margin=dict(t=50, l=280, r=20, b=60)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("**Inefficient COPY Command Detail**")
        st.dataframe(df_patterns[['QUERY_PATTERN', 'EXECUTION_COUNT', 'TOTAL_ROWS_LOADED', 'AVG_COMPILE_MS', 'AVG_EXECUTION_MS', 'CLOUD_SERVICES_CREDITS', 'ISSUE_TYPE']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_cloud_services_overhead():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Cloud Services Overhead:</b> Aggregated cloud services credits consumed by anti-pattern '
        'query types (SHOW commands, short queries, metadata scans, single-row inserts) over the last 30 days.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        WITH pattern_summary AS (
            SELECT 'SHOW Commands' AS pattern, SUM(credits_used_cloud_services) AS credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND query_type = 'SHOW'
            UNION ALL
            SELECT 'Short Queries (<100ms)', SUM(credits_used_cloud_services)
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              AND total_elapsed_time < 100
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
        SELECT
            pattern,
            ROUND(credits, 4) AS cloud_services_credits_30d,
            ROUND(credits * 3.00, 2) AS estimated_cost_usd,
            ROUND(RATIO_TO_REPORT(credits) OVER () * 100, 1) AS pct_of_overhead
        FROM pattern_summary
        WHERE credits > 0
        ORDER BY credits DESC
        """
        df = _cached_sql("fo_cloud_svcs_overhead", query)
        if df.empty:
            st.success("No significant cloud services overhead detected from anti-pattern queries.")
            return
        for c in ['CLOUD_SERVICES_CREDITS_30D', 'ESTIMATED_COST_USD', 'PCT_OF_OVERHEAD']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Overhead Credits", f"{df['CLOUD_SERVICES_CREDITS_30D'].sum():,.4f}")
        with col2:
            st.metric("Estimated Cost", f"${df['ESTIMATED_COST_USD'].sum():,.2f}")
        colors = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229']
        fig = go.Figure(go.Bar(
            x=df['PATTERN'], y=df['CLOUD_SERVICES_CREDITS_30D'],
            marker_color=colors[:len(df)],
            text=[f"{v:,.4f}" for v in df['CLOUD_SERVICES_CREDITS_30D']], textposition='outside'
        ))
        fig.update_layout(
            title='Cloud Services Overhead by Anti-Pattern (Last 30 Days)',
            yaxis_title='Credits',
            height=380, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        fig2 = go.Figure(go.Pie(
            labels=df['PATTERN'], values=df['PCT_OF_OVERHEAD'],
            hole=0.3,
            marker=dict(colors=colors[:len(df)])
        ))
        fig2.update_layout(title='Overhead Distribution', height=350, margin=dict(t=50, b=20))
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

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


def comp_cicd_automation(entry_actions=None):
    """CI/CD Tool Automation Component

    Analyzes CI/CD tool automation practices identifying deployment agents
    (GitHub Actions, GitLab CI, Jenkins, Terraform, Schemachange, service accounts, or human)
    with session and operation counts over last 30 days.

    Args:
        entry_actions: Optional entry actions for the component
    """
    try:
        # Get session and context
        try:
            from snowflake.snowpark.context import get_active_session
            session = get_active_session()
        except Exception as e:
            st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Unable to get Snowflake session: {str(e)}'
                        f'</div>', unsafe_allow_html=True)
            return

        if not session:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;Snowflake session not available.'
                        '</div>', unsafe_allow_html=True)
            return

        # CI/CD Tool Identification expander
        with st.expander("CI/CD Tool Identification Analysis", expanded=True):
            # Introduction text (no CSS styling)
            st.markdown("CI/CD tool identification analyzing DDL operations by deployment agent (GitHub Actions, GitLab CI, Jenkins, Terraform, Schemachange, service accounts, or human) with session and operation counts over last 30 days.")
            st.markdown("<br>", unsafe_allow_html=True)

            # Build and execute the query
            query = f"""
            SELECT
                CASE
                    -- CI/CD Tool Signatures
                    WHEN s.client_application_id ILIKE '%GitHub%' THEN 'GitHub Actions'
                    WHEN s.client_application_id ILIKE '%GitLab%' THEN 'GitLab CI'
                    WHEN s.client_application_id ILIKE '%Jenkins%' THEN 'Jenkins'
                    WHEN s.client_application_id ILIKE '%Terraform%' THEN 'Terraform'
                    WHEN s.client_application_id ILIKE '%Schemachange%' THEN 'Schemachange'
                    -- Fix: Explicitly use 'q.user_name' to avoid ambiguity
                    WHEN q.user_name ILIKE '%SVC_%' OR q.user_name ILIKE '%CI_%' THEN 'Service Account (Generic)'
                    ELSE 'Human / Other'
                END AS deployment_agent,

                COUNT(DISTINCT s.session_id) AS session_count,
                COUNT(DISTINCT q.query_id) AS ddl_operations_count

            FROM SNOWFLAKE.ACCOUNT_USAGE.sessions s
            JOIN SNOWFLAKE.ACCOUNT_USAGE.query_history q
                ON s.session_id = q.session_id
            WHERE q.start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
              -- Fix: Use wildcard matching because query_type is specific (e.g. 'CREATE_TABLE', 'ALTER_VIEW')
              AND (
                  q.query_type ILIKE 'CREATE%' OR
                  q.query_type ILIKE 'ALTER%' OR
                  q.query_type ILIKE 'DROP%' OR
                  q.query_type ILIKE 'GRANT%'
              )
            GROUP BY all
            ORDER BY 3 DESC
            """


            # Execute query
            try:
                df = _cached_sql("rd_cicd_automation", query)
            except Exception as e:
                st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            f'🛑&nbsp;&nbsp;Error executing query: {str(e)}'
                            f'</div>', unsafe_allow_html=True)
                return

            if df.empty:
                st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '⚠️&nbsp;&nbsp;No CI/CD tool data found for the last 30 days.'
                            '</div>', unsafe_allow_html=True)
                return

            # Rename columns for display
            df.columns = ['DEPLOYMENT_AGENT', 'SESSION_COUNT', 'DDL_OPERATIONS_COUNT']


            # Create metric object for dialogs
            # Initialize or update metric object in session state


            # Display the dataframe
            st.dataframe(
                df,
            )

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### CI/CD Analytics Charts")

            # Row 1: Two charts
            col1, col2 = st.columns(2)

            with col1.container():
                st.markdown("##### DDL Operations by Deployment Agent")
                _render_ddl_operations_chart(df, key_prefix="ddl_ops_")

            with col2.container():
                st.markdown("##### Session Count by Deployment Agent")
                _render_session_count_chart(df, key_prefix="session_")

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ============================
# Chart Type Selector & Charts for DDL Operations
# ============================

def _render_ddl_operations_chart(df, key_prefix=""):
    """Render DDL operations by deployment agent chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_ddl_ops_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_ddl_ops_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_ddl_ops_donut_chart(df, key_prefix)
    else:
        _render_ddl_ops_rose_chart(df, key_prefix)


def _render_ddl_ops_bar_chart(df, key_prefix=""):
    """Render DDL operations bar chart using Plotly."""
    # Sort ascending for horizontal bar layout
    plot_df = df.sort_values('DDL_OPERATIONS_COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DEPLOYMENT_AGENT'],
            x=plot_df['DDL_OPERATIONS_COUNT'],
            orientation='h',
            marker_color='#29B5E8',
            text=[f"{int(val):,}" for val in plot_df['DDL_OPERATIONS_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>DDL Operations: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='DDL Operations Count',
        yaxis_title='Deployment Agent',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )


def _render_ddl_ops_pie_chart(df, key_prefix=""):
    """Render DDL operations pie chart using ECharts."""
    chart_data = [
        {"value": int(row['DDL_OPERATIONS_COUNT']), "name": f"{row['DEPLOYMENT_AGENT']} ({int(row['DDL_OPERATIONS_COUNT']):,})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "DDL Operations",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_ddl_ops_donut_chart(df, key_prefix=""):
    """Render DDL operations donut chart using ECharts."""
    chart_data = [
        {"value": int(row['DDL_OPERATIONS_COUNT']), "name": f"{row['DEPLOYMENT_AGENT']} ({int(row['DDL_OPERATIONS_COUNT']):,})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "DDL Operations",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_ddl_ops_rose_chart(df, key_prefix=""):
    """Render DDL operations rose chart using ECharts."""
    chart_data = [
        {"value": int(row['DDL_OPERATIONS_COUNT']), "name": row['DEPLOYMENT_AGENT']}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} operations ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "series": [{
            "name": "DDL Operations",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")


# ============================
# Chart Type Selector & Charts for Session Count
# ============================

def _render_session_count_chart(df, key_prefix=""):
    """Render session count by deployment agent chart with selectable chart types."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_session_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_session_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_session_donut_chart(df, key_prefix)
    else:
        _render_session_rose_chart(df, key_prefix)


def _render_session_bar_chart(df, key_prefix=""):
    """Render session count bar chart using Plotly."""
    # Sort ascending for horizontal bar layout
    plot_df = df.sort_values('SESSION_COUNT', ascending=True)

    fig = go.Figure(data=[
        go.Bar(
            y=plot_df['DEPLOYMENT_AGENT'],
            x=plot_df['SESSION_COUNT'],
            orientation='h',
            marker_color='#E8A229',
            text=[f"{int(val):,}" for val in plot_df['SESSION_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Sessions: %{x:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=400,
        xaxis_title='Session Count',
        yaxis_title='Deployment Agent',
        showlegend=False,
        margin=dict(t=20, b=50, l=150, r=50)
    )


def _render_session_pie_chart(df, key_prefix=""):
    """Render session count pie chart using ECharts."""
    chart_data = [
        {"value": int(row['SESSION_COUNT']), "name": f"{row['DEPLOYMENT_AGENT']} ({int(row['SESSION_COUNT']):,})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#E8A229", "#0077B6", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8", "#29B5E8"],
        "series": [{
            "name": "Sessions",
            "type": "pie",
            "radius": ["0%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}pie")


def _render_session_donut_chart(df, key_prefix=""):
    """Render session count donut chart using ECharts."""
    chart_data = [
        {"value": int(row['SESSION_COUNT']), "name": f"{row['DEPLOYMENT_AGENT']} ({int(row['SESSION_COUNT']):,})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {d}%"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#E8A229", "#0077B6", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8", "#29B5E8"],
        "series": [{
            "name": "Sessions",
            "type": "pie",
            "radius": ["30%", "55%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}donut")


def _render_session_rose_chart(df, key_prefix=""):
    """Render session count rose chart using ECharts."""
    chart_data = [
        {"value": int(row['SESSION_COUNT']), "name": row['DEPLOYMENT_AGENT']}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 5,
            "itemWidth": 10,
            "textStyle": {"fontSize": 9}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} sessions ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True}
            }
        },
        "color": ["#E8A229", "#0077B6", "#E74C3C", "#0077B6", "#11567F", "#75C2D8", "#48CAE4", "#E8A229", "#00B4D8", "#29B5E8"],
        "series": [{
            "name": "Sessions",
            "type": "pie",
            "radius": ["10%", "55%"],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 5},
            "data": chart_data
        }]
    }

    st_echarts(options=option, height="400px", key=f"{key_prefix}rose")

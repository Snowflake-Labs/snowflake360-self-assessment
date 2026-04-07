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


def comp_finops_control(entry_actions=None):
    """
    FinOPS Control Component

    Provides control capabilities for resource monitors and warehouse management.

    Expanders:
    1. FinOPS Control Overview
    2. FinOPS Control Analyzer
    3. Resource Monitors (Inventory & Orphans)
    4. Warehouses Without Controls (Exposure Risk)
    5. Resource Monitors: Approaching Limits (Usage vs. Quota)
    6. Statement Timeouts (Parameters)
    7. Snowflake Budgets
    """
    try:
        st.markdown("### Control")

        # Expander 3: Resource Monitors (Inventory & Orphans)
        with st.expander("Resource Monitors (Inventory & Orphans)", expanded=True):
            _render_resource_monitors_inventory()

        # Expander 4: Warehouses Without Controls (Exposure Risk)
        with st.expander("Warehouses Without Controls (Exposure Risk)", expanded=True):
            st.markdown("#### Warehouses Without Controls (Exposure Risk)")
            _render_warehouses_without_controls()

        # Expander 5: Resource Monitors: Approaching Limits (Usage vs. Quota)
        with st.expander("Resource Monitors: Approaching Limits (Usage vs. Quota)", expanded=True):
            st.markdown("#### Resource Monitors: Approaching Limits (Usage vs. Quota)")
            _render_monitors_approaching_limits()

        # Expander 6: Statement Timeouts (Parameters)
        with st.expander("Statement Timeouts (Parameters)", expanded=True):
            st.markdown("#### Statement Timeouts (Parameters)")
            _render_statement_timeouts()

        # Expander 7: Snowflake Budgets
        with st.expander("Snowflake Budgets", expanded=True):
            _render_snowflake_budgets()

        with st.expander("Always-On Warehouse Pattern (7-Day)", expanded=True):
            _render_always_on_warehouses()

        with st.expander("Idle Time Analysis (Cost Savings Opportunity)", expanded=True):
            _render_idle_time_analysis()

        with st.expander("Resource Monitor Coverage Gap Analysis", expanded=True):
            _render_rm_coverage_gap()

        with st.expander("Week-over-Week Cost Trend", expanded=True):
            _render_wow_cost_trend()

        with st.expander("Spending Summary (30 Days)", expanded=True):
            _render_spending_summary()

        with st.expander("Monthly Spending Trend (12 Months)", expanded=True):
            _render_monthly_spending_trend()

        with st.expander("Serverless Compute Costs (30 Days)", expanded=True):
            _render_serverless_costs()

        with st.expander("Storage Costs (3 Months)", expanded=True):
            _render_storage_costs()

        with st.expander("Snowpark Container Services Credits (30 Days)", expanded=True):
            _render_spcs_credits()

        with st.expander("Dangling Custom Budgets", expanded=True):
            _render_dangling_budgets()

    except Exception as e:
        # st.error(f"Component Error: {str(e)}")
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_resource_monitors_inventory():
    """Render Resource Monitors Inventory & Orphans expander content."""

    st.markdown("#### Resource Monitors (Inventory & Orphans)")

    # Introduction text
    st.markdown("""
    **Resource monitor inventory** showing credit quotas, notification/suspension thresholds, schedules,
    and ownership ordered by quota size. This view helps identify monitors that may be under-utilized
    or orphaned (no warehouses assigned).
    """)

    try:

        # Resource Monitors Query
        resource_monitors_query = f"""
SELECT
    name AS monitor_name,
    credit_quota,
    notify,
    suspend,
    suspend_immediate,
    created,
    owner,
    warehouses
FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS
ORDER BY credit_quota DESC
"""


        # Execute the query
        resource_monitors_df = _cached_sql("fc_resource_monitors", resource_monitors_query)

        if not resource_monitors_df.empty:
            st.dataframe(resource_monitors_df, use_container_width=True)

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Resource Monitor Analysis")

            # Row 1: Credit Quota Distribution & Threshold Analysis
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container():
                st.markdown("##### Credit Quota by Monitor")
                _render_credit_quota_chart_content(resource_monitors_df, key_prefix="rm_quota_")

            with chart_col2.container():
                st.markdown("##### Threshold Comparison (Notify vs Suspend)")
                _render_threshold_chart_content(resource_monitors_df, key_prefix="rm_threshold_")

            # Row 2: Ownership Distribution & Warehouse Assignment
            chart_col3, chart_col4 = st.columns(2)

            with chart_col3.container():
                st.markdown("##### Resource Monitors by Owner")
                _render_owner_distribution_chart_content(resource_monitors_df, key_prefix="rm_owner_")

            with chart_col4.container():
                st.markdown("##### Warehouse Assignment Status")
                _render_warehouse_assignment_chart_content(resource_monitors_df, key_prefix="rm_wh_")

            # ========== NEW SECTION: Resource Monitor Risk Analysis ==========
            _render_resource_monitor_risk_analysis()

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No resource monitors data available for the current execution context.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading resource monitors: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Credit Quota Chart Functions ==========

def _render_credit_quota_chart_content(df, key_prefix=""):
    """Render credit quota chart content with selectable chart types."""

    # Add chart type selector
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,  # Default to Bar Chart
        key=f"{key_prefix}chart_type"
    )

    # Render selected chart type
    if chart_type == "Bar Chart":
        _render_credit_quota_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_credit_quota_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_credit_quota_donut_pie_chart(df, key_prefix)
    else:  # Pie - Rose Chart
        _render_credit_quota_rose_pie_chart(df, key_prefix)


def _render_credit_quota_bar_chart(df, key_prefix=""):
    """Render credit quota bar chart using Plotly."""

    fig_bar = go.Figure(data=[
        go.Bar(
            x=df['MONITOR_NAME'],
            y=df['CREDIT_QUOTA'],
            marker_color='#29B5E8',
            text=[f"{val:,.0f}" for val in df['CREDIT_QUOTA']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Quota: %{y:,.0f} credits<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Resource Monitor',
        yaxis_title='Credit Quota',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_credit_quota_standard_pie_chart(df, key_prefix=""):
    """Render credit quota standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDIT_QUOTA']), "name": f"{row['MONITOR_NAME']} ({row['CREDIT_QUOTA']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
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
                "name": "Credit Quota",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_credit_quota_donut_pie_chart(df, key_prefix=""):
    """Render credit quota donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDIT_QUOTA']), "name": f"{row['MONITOR_NAME']} ({row['CREDIT_QUOTA']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
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
                "name": "Credit Quota",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_credit_quota_rose_pie_chart(df, key_prefix=""):
    """Render credit quota rose-type pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDIT_QUOTA']), "name": f"{row['MONITOR_NAME']} ({row['CREDIT_QUOTA']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
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
                "name": "Credit Quota",
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


# ========== Threshold Chart Functions ==========

def _render_threshold_chart_content(df, key_prefix=""):
    """Render threshold comparison chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_threshold_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_threshold_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_threshold_donut_pie_chart(df, key_prefix)
    else:
        _render_threshold_rose_pie_chart(df, key_prefix)


def _render_threshold_bar_chart(df, key_prefix=""):
    """Render threshold comparison bar chart using Plotly."""

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Notify %',
        x=df['MONITOR_NAME'],
        y=df['NOTIFY'],
        marker_color='#E8A229',
        text=[f"{val}%" if pd.notna(val) else "N/A" for val in df['NOTIFY']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.add_trace(go.Bar(
        name='Suspend %',
        x=df['MONITOR_NAME'],
        y=df['SUSPEND'],
        marker_color='#E74C3C',
        text=[f"{val}%" if pd.notna(val) else "N/A" for val in df['SUSPEND']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.add_trace(go.Bar(
        name='Suspend Immediate %',
        x=df['MONITOR_NAME'],
        y=df['SUSPEND_IMMEDIATE'],
        marker_color='#0077B6',
        text=[f"{val}%" if pd.notna(val) else "N/A" for val in df['SUSPEND_IMMEDIATE']],
        textposition='outside',
        textfont=dict(size=9)
    ))

    fig.update_layout(
        height=350,
        barmode='group',
        xaxis_title='Resource Monitor',
        yaxis_title='Threshold (%)',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(t=40, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_threshold_standard_pie_chart(df, key_prefix=""):
    """Render threshold distribution pie chart - shows average thresholds."""

    avg_notify = df['NOTIFY'].mean() if df['NOTIFY'].notna().any() else 0
    avg_suspend = df['SUSPEND'].mean() if df['SUSPEND'].notna().any() else 0
    avg_suspend_imm = df['SUSPEND_IMMEDIATE'].mean() if df['SUSPEND_IMMEDIATE'].notna().any() else 0

    chart_data = [
        {"value": float(avg_notify), "name": f"Avg Notify ({avg_notify:.1f}%)"},
        {"value": float(avg_suspend), "name": f"Avg Suspend ({avg_suspend:.1f}%)"},
        {"value": float(avg_suspend_imm), "name": f"Avg Suspend Imm. ({avg_suspend_imm:.1f}%)"}
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
            "formatter": "{b}: {c}%"
        },
        "color": ["#E8A229", "#E74C3C", "#0077B6"],
        "series": [
            {
                "name": "Threshold Averages",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_threshold_donut_pie_chart(df, key_prefix=""):
    """Render threshold distribution donut chart."""

    avg_notify = df['NOTIFY'].mean() if df['NOTIFY'].notna().any() else 0
    avg_suspend = df['SUSPEND'].mean() if df['SUSPEND'].notna().any() else 0
    avg_suspend_imm = df['SUSPEND_IMMEDIATE'].mean() if df['SUSPEND_IMMEDIATE'].notna().any() else 0

    chart_data = [
        {"value": float(avg_notify), "name": f"Avg Notify ({avg_notify:.1f}%)"},
        {"value": float(avg_suspend), "name": f"Avg Suspend ({avg_suspend:.1f}%)"},
        {"value": float(avg_suspend_imm), "name": f"Avg Suspend Imm. ({avg_suspend_imm:.1f}%)"}
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
            "formatter": "{b}: {c}%"
        },
        "color": ["#E8A229", "#E74C3C", "#0077B6"],
        "series": [
            {
                "name": "Threshold Averages",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_threshold_rose_pie_chart(df, key_prefix=""):
    """Render threshold distribution rose chart."""

    avg_notify = df['NOTIFY'].mean() if df['NOTIFY'].notna().any() else 0
    avg_suspend = df['SUSPEND'].mean() if df['SUSPEND'].notna().any() else 0
    avg_suspend_imm = df['SUSPEND_IMMEDIATE'].mean() if df['SUSPEND_IMMEDIATE'].notna().any() else 0

    chart_data = [
        {"value": float(avg_notify), "name": f"Avg Notify ({avg_notify:.1f}%)"},
        {"value": float(avg_suspend), "name": f"Avg Suspend ({avg_suspend:.1f}%)"},
        {"value": float(avg_suspend_imm), "name": f"Avg Suspend Imm. ({avg_suspend_imm:.1f}%)"}
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
            "formatter": "{b}: {c}%"
        },
        "color": ["#E8A229", "#E74C3C", "#0077B6"],
        "series": [
            {
                "name": "Threshold Averages",
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


# ========== Owner Distribution Chart Functions ==========

def _render_owner_distribution_chart_content(df, key_prefix=""):
    """Render owner distribution chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_owner_distribution_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_owner_distribution_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_owner_distribution_donut_pie_chart(df, key_prefix)
    else:
        _render_owner_distribution_rose_pie_chart(df, key_prefix)


def _render_owner_distribution_bar_chart(df, key_prefix=""):
    """Render owner distribution bar chart using Plotly."""

    owner_counts = df['OWNER'].value_counts().reset_index()
    owner_counts.columns = ['OWNER', 'COUNT']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=owner_counts['OWNER'],
            y=owner_counts['COUNT'],
            marker_color='#27AE60',
            text=owner_counts['COUNT'],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Owner',
        yaxis_title='Number of Monitors',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_owner_distribution_standard_pie_chart(df, key_prefix=""):
    """Render owner distribution standard pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "series": [
            {
                "name": "Owner Distribution",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_owner_distribution_donut_pie_chart(df, key_prefix=""):
    """Render owner distribution donut pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "series": [
            {
                "name": "Owner Distribution",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_owner_distribution_rose_pie_chart(df, key_prefix=""):
    """Render owner distribution rose pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "series": [
            {
                "name": "Owner Distribution",
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


# ========== Warehouse Assignment Chart Functions ==========

def _render_warehouse_assignment_chart_content(df, key_prefix=""):
    """Render warehouse assignment chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_warehouse_assignment_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_warehouse_assignment_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_warehouse_assignment_donut_pie_chart(df, key_prefix)
    else:
        _render_warehouse_assignment_rose_pie_chart(df, key_prefix)


def _render_warehouse_assignment_bar_chart(df, key_prefix=""):
    """Render warehouse assignment bar chart using Plotly."""

    # Count warehouses assigned to each monitor
    def count_warehouses(warehouses):
        if pd.isna(warehouses) or warehouses == '' or warehouses == '[]':
            return 0
        if isinstance(warehouses, str):
            # Parse the array string
            warehouses = warehouses.strip('[]')
            if not warehouses:
                return 0
            return len([w.strip() for w in warehouses.split(',') if w.strip()])
        return 0

    df_copy = df.copy()
    df_copy['WH_COUNT'] = df_copy['WAREHOUSES'].apply(count_warehouses)

    fig_bar = go.Figure(data=[
        go.Bar(
            x=df_copy['MONITOR_NAME'],
            y=df_copy['WH_COUNT'],
            marker_color=['#E74C3C' if x == 0 else '#27AE60' for x in df_copy['WH_COUNT']],
            text=df_copy['WH_COUNT'],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Warehouses: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Resource Monitor',
        yaxis_title='Number of Warehouses',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_warehouse_assignment_standard_pie_chart(df, key_prefix=""):
    """Render warehouse assignment status pie chart (Assigned vs Orphaned)."""

    def has_warehouses(warehouses):
        if pd.isna(warehouses) or warehouses == '' or warehouses == '[]':
            return False
        if isinstance(warehouses, str):
            warehouses = warehouses.strip('[]')
            return bool(warehouses.strip())
        return False

    df_copy = df.copy()
    df_copy['HAS_WH'] = df_copy['WAREHOUSES'].apply(has_warehouses)

    assigned_count = df_copy['HAS_WH'].sum()
    orphaned_count = len(df_copy) - assigned_count

    chart_data = [
        {"value": int(assigned_count), "name": f"With Warehouses ({assigned_count})"},
        {"value": int(orphaned_count), "name": f"Orphaned ({orphaned_count})"}
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
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "color": ["#27AE60", "#E74C3C"],
        "series": [
            {
                "name": "Warehouse Assignment",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_warehouse_assignment_donut_pie_chart(df, key_prefix=""):
    """Render warehouse assignment status donut chart."""

    def has_warehouses(warehouses):
        if pd.isna(warehouses) or warehouses == '' or warehouses == '[]':
            return False
        if isinstance(warehouses, str):
            warehouses = warehouses.strip('[]')
            return bool(warehouses.strip())
        return False

    df_copy = df.copy()
    df_copy['HAS_WH'] = df_copy['WAREHOUSES'].apply(has_warehouses)

    assigned_count = df_copy['HAS_WH'].sum()
    orphaned_count = len(df_copy) - assigned_count

    chart_data = [
        {"value": int(assigned_count), "name": f"With Warehouses ({assigned_count})"},
        {"value": int(orphaned_count), "name": f"Orphaned ({orphaned_count})"}
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
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "color": ["#27AE60", "#E74C3C"],
        "series": [
            {
                "name": "Warehouse Assignment",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_warehouse_assignment_rose_pie_chart(df, key_prefix=""):
    """Render warehouse assignment status rose chart."""

    def has_warehouses(warehouses):
        if pd.isna(warehouses) or warehouses == '' or warehouses == '[]':
            return False
        if isinstance(warehouses, str):
            warehouses = warehouses.strip('[]')
            return bool(warehouses.strip())
        return False

    df_copy = df.copy()
    df_copy['HAS_WH'] = df_copy['WAREHOUSES'].apply(has_warehouses)

    assigned_count = df_copy['HAS_WH'].sum()
    orphaned_count = len(df_copy) - assigned_count

    chart_data = [
        {"value": int(assigned_count), "name": f"With Warehouses ({assigned_count})"},
        {"value": int(orphaned_count), "name": f"Orphaned ({orphaned_count})"}
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
            "formatter": "{b}: {c} monitors ({d}%)"
        },
        "color": ["#27AE60", "#E74C3C"],
        "series": [
            {
                "name": "Warehouse Assignment",
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


# ========== Resource Monitor Risk Analysis Section ==========

def _render_resource_monitor_risk_analysis():
    """Render Resource Monitor Risk Analysis section with warehouse spend analysis."""


    st.markdown("---")
    st.markdown("#### Resource Monitor Risk Analysis")

    # Introduction text
    st.markdown("""
    **Resource monitor risk analysis** identifying warehouses without resource monitors and their credit consumption,
    along with configured resource monitors and their total quotas. This helps identify cost exposure risks from
    unmonitored warehouse spending.
    """)

    try:

        # Resource Monitor Risk Analysis Query
        risk_analysis_query = f"""
WITH warehouse_spend AS (
    SELECT
        warehouse_name,
        NVL(SUM(credits_used), 0) AS monthly_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATE_TRUNC('month', CURRENT_DATE)
    GROUP BY warehouse_name
),
monitor_quotas AS (
    SELECT
        name AS monitor_name,
        credit_quota
    FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS
    ),
warehouses_without_monitors AS (
    SELECT
        ws.warehouse_name,
        ws.monthly_credits
    FROM warehouse_spend ws
    WHERE ws.monthly_credits > 100
)
SELECT
    '⚠️ Warehouses without Resource Monitors (>100 credits MTD)' AS risk_category,
    NVL(COUNT(DISTINCT warehouse_name), 0) AS item_count,
    ROUND(NVL(SUM(monthly_credits), 0), 2) AS credits_or_quota,
    LISTAGG(warehouse_name, ', ') WITHIN GROUP (ORDER BY monthly_credits DESC) AS item_list
FROM warehouses_without_monitors
UNION ALL
SELECT
    '📊 Resource Monitors Configured' AS risk_category,
    NVL(COUNT(*), 0) AS item_count,
    ROUND(NVL(SUM(credit_quota), 0), 2) AS credits_or_quota,
    LISTAGG(monitor_name, ', ') WITHIN GROUP (ORDER BY credit_quota DESC) AS item_list
FROM monitor_quotas
"""


        # Also display query in UI expander for visibility
        with st.expander("📝 View Risk Analysis Query", expanded=False):
            st.code(risk_analysis_query, language="sql")

        # Execute the query
        risk_analysis_df = _cached_sql("fc_risk_analysis", risk_analysis_query)

        if not risk_analysis_df.empty:
            st.dataframe(risk_analysis_df, use_container_width=True)

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Risk Analysis Charts")

            # Row 1: Risk Category Distribution & Credits/Quota Comparison
            risk_chart_col1, risk_chart_col2 = st.columns(2)

            with risk_chart_col1.container():
                st.markdown("##### Risk Category: Item Count")
                _render_risk_category_count_chart_content(risk_analysis_df, key_prefix="risk_count_")

            with risk_chart_col2.container():
                st.markdown("##### Risk Category: Credits/Quota")
                _render_risk_category_credits_chart_content(risk_analysis_df, key_prefix="risk_credits_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No risk analysis data available. This may indicate all warehouses have resource monitors configured.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading risk analysis: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Risk Category Count Chart Functions ==========

def _render_risk_category_count_chart_content(df, key_prefix=""):
    """Render risk category count chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_risk_category_count_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_risk_category_count_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_risk_category_count_donut_pie_chart(df, key_prefix)
    else:
        _render_risk_category_count_rose_pie_chart(df, key_prefix)


def _render_risk_category_count_bar_chart(df, key_prefix=""):
    """Render risk category count bar chart using Plotly."""

    fig_bar = go.Figure(data=[
        go.Bar(
            x=df['RISK_CATEGORY'],
            y=df['ITEM_COUNT'],
            marker_color=['#E74C3C' if '⚠️' in cat else '#27AE60' for cat in df['RISK_CATEGORY']],
            text=[f"{val:,.0f}" for val in df['ITEM_COUNT']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y:,.0f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Risk Category',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=100, l=50, r=20),
        xaxis_tickangle=-25
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_risk_category_count_standard_pie_chart(df, key_prefix=""):
    """Render risk category count standard pie chart using ECharts."""

    chart_data = [
        {"value": int(row['ITEM_COUNT']), "name": f"{row['RISK_CATEGORY']} ({row['ITEM_COUNT']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} items ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#E74C3C", "#27AE60"],
        "series": [
            {
                "name": "Item Count",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_risk_category_count_donut_pie_chart(df, key_prefix=""):
    """Render risk category count donut pie chart using ECharts."""

    chart_data = [
        {"value": int(row['ITEM_COUNT']), "name": f"{row['RISK_CATEGORY']} ({row['ITEM_COUNT']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} items ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#E74C3C", "#27AE60"],
        "series": [
            {
                "name": "Item Count",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_risk_category_count_rose_pie_chart(df, key_prefix=""):
    """Render risk category count rose pie chart using ECharts."""

    chart_data = [
        {"value": int(row['ITEM_COUNT']), "name": f"{row['RISK_CATEGORY']} ({row['ITEM_COUNT']:,.0f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} items ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#E74C3C", "#27AE60"],
        "series": [
            {
                "name": "Item Count",
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


# ========== Risk Category Credits Chart Functions ==========

def _render_risk_category_credits_chart_content(df, key_prefix=""):
    """Render risk category credits/quota chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_risk_category_credits_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_risk_category_credits_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_risk_category_credits_donut_pie_chart(df, key_prefix)
    else:
        _render_risk_category_credits_rose_pie_chart(df, key_prefix)


def _render_risk_category_credits_bar_chart(df, key_prefix=""):
    """Render risk category credits/quota bar chart using Plotly."""

    fig_bar = go.Figure(data=[
        go.Bar(
            x=df['RISK_CATEGORY'],
            y=df['CREDITS_OR_QUOTA'],
            marker_color=['#E74C3C' if '⚠️' in cat else '#27AE60' for cat in df['RISK_CATEGORY']],
            text=[f"{val:,.2f}" for val in df['CREDITS_OR_QUOTA']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Credits/Quota: %{y:,.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Risk Category',
        yaxis_title='Credits / Quota',
        showlegend=False,
        margin=dict(t=20, b=100, l=50, r=20),
        xaxis_tickangle=-25
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_risk_category_credits_standard_pie_chart(df, key_prefix=""):
    """Render risk category credits/quota standard pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDITS_OR_QUOTA']), "name": f"{row['RISK_CATEGORY']} ({row['CREDITS_OR_QUOTA']:,.2f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#E74C3C", "#27AE60"],
        "series": [
            {
                "name": "Credits/Quota",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_risk_category_credits_donut_pie_chart(df, key_prefix=""):
    """Render risk category credits/quota donut pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDITS_OR_QUOTA']), "name": f"{row['RISK_CATEGORY']} ({row['CREDITS_OR_QUOTA']:,.2f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#E74C3C", "#27AE60"],
        "series": [
            {
                "name": "Credits/Quota",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_risk_category_credits_rose_pie_chart(df, key_prefix=""):
    """Render risk category credits/quota rose pie chart using ECharts."""

    chart_data = [
        {"value": float(row['CREDITS_OR_QUOTA']), "name": f"{row['RISK_CATEGORY']} ({row['CREDITS_OR_QUOTA']:,.2f})"}
        for _, row in df.iterrows()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#E74C3C", "#27AE60"],
        "series": [
            {
                "name": "Credits/Quota",
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


# ========== Snowflake Budgets Section ==========

def _render_snowflake_budgets():
    """Render Snowflake Budgets expander content."""

    st.markdown("#### Snowflake Budgets")

    # Introduction text
    st.markdown("""
    **Budget configuration count** showing total number of active budgets defined in the account.
    Snowflake Budgets help you monitor and control spending by setting spending limits and alerts.
    """)

    try:

        # Snowflake Budgets Query
        budgets_query = f"""
SELECT
    'Total Budgets Configured' AS metric,
    NVL(COUNT(*), 0) AS count
FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
WHERE CLASS_NAME = 'BUDGET'
  AND DELETED IS NULL
"""


        # Execute the query
        budgets_df = _cached_sql("fc_budgets", budgets_query)

        if not budgets_df.empty:
            st.dataframe(budgets_df, use_container_width=True)

            # Get the budget count for charts
            budget_count = int(budgets_df['COUNT'].iloc[0]) if 'COUNT' in budgets_df.columns else 0

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Budget Analysis Charts")

            # Row 1: Budget Count Visualization & Budget Status
            budget_chart_col1, budget_chart_col2 = st.columns(2)

            with budget_chart_col1.container():
                st.markdown(f"##### Budget Count: {budget_count}")
                _render_budget_count_chart_content(budget_count, key_prefix="budget_count_")

            with budget_chart_col2.container():
                st.markdown("##### Budget Configuration Status")
                _render_budget_status_chart_content(budget_count, key_prefix="budget_status_")

            # ========== NEW SECTION: Budget Inventory Details ==========
            _render_budget_inventory()

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No budget data available for the current execution context.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading budgets: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Budget Count Chart Functions ==========

def _render_budget_count_chart_content(budget_count, key_prefix=""):
    """Render budget count chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_count_bar_chart(budget_count, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_count_standard_pie_chart(budget_count, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_count_donut_pie_chart(budget_count, key_prefix)
    else:
        _render_budget_count_rose_pie_chart(budget_count, key_prefix)


def _render_budget_count_bar_chart(budget_count, key_prefix=""):
    """Render budget count bar chart using Plotly."""

    fig_bar = go.Figure(data=[
        go.Bar(
            x=['Total Budgets'],
            y=[budget_count],
            marker_color='#29B5E8',
            text=[f"{budget_count}"],
            textposition='outside',
            textfont=dict(size=14),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
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


def _render_budget_count_standard_pie_chart(budget_count, key_prefix=""):
    """Render budget count standard pie chart using ECharts."""

    chart_data = [
        {"value": budget_count, "name": f"Configured ({budget_count})"},
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
            "formatter": "{b}: {c} budgets"
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
                "name": "Budget Count",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_count_donut_pie_chart(budget_count, key_prefix=""):
    """Render budget count donut pie chart using ECharts."""

    chart_data = [
        {"value": budget_count, "name": f"Configured ({budget_count})"},
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
            "formatter": "{b}: {c} budgets"
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
                "name": "Budget Count",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_count_rose_pie_chart(budget_count, key_prefix=""):
    """Render budget count rose pie chart using ECharts."""

    chart_data = [
        {"value": budget_count, "name": f"Configured ({budget_count})"},
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
            "formatter": "{b}: {c} budgets"
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
                "name": "Budget Count",
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


# ========== Budget Status Chart Functions ==========

def _render_budget_status_chart_content(budget_count, key_prefix=""):
    """Render budget status chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_status_bar_chart(budget_count, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_status_standard_pie_chart(budget_count, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_status_donut_pie_chart(budget_count, key_prefix)
    else:
        _render_budget_status_rose_pie_chart(budget_count, key_prefix)


def _render_budget_status_bar_chart(budget_count, key_prefix=""):
    """Render budget status bar chart using Plotly."""

    has_budgets = budget_count > 0
    status_labels = ['Budgets Configured', 'Budget Adoption']
    status_values = [budget_count, 100 if has_budgets else 0]
    colors = ['#27AE60' if has_budgets else '#E74C3C', '#29B5E8']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=status_labels,
            y=status_values,
            marker_color=colors,
            text=[f"{budget_count}", f"{'Active' if has_budgets else 'Not Configured'}"],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Value: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budget_status_standard_pie_chart(budget_count, key_prefix=""):
    """Render budget status standard pie chart using ECharts."""

    has_budgets = budget_count > 0

    chart_data = [
        {"value": budget_count if has_budgets else 1, "name": f"Configured ({budget_count})" if has_budgets else "Not Configured"},
    ]

    if not has_budgets:
        chart_data = [{"value": 1, "name": "No Budgets Configured"}]

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
        "color": ["#27AE60" if has_budgets else "#E74C3C"],
        "series": [
            {
                "name": "Budget Status",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_status_donut_pie_chart(budget_count, key_prefix=""):
    """Render budget status donut pie chart using ECharts."""

    has_budgets = budget_count > 0

    chart_data = [
        {"value": budget_count if has_budgets else 1, "name": f"Configured ({budget_count})" if has_budgets else "Not Configured"},
    ]

    if not has_budgets:
        chart_data = [{"value": 1, "name": "No Budgets Configured"}]

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
        "color": ["#27AE60" if has_budgets else "#E74C3C"],
        "series": [
            {
                "name": "Budget Status",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_status_rose_pie_chart(budget_count, key_prefix=""):
    """Render budget status rose pie chart using ECharts."""

    has_budgets = budget_count > 0

    chart_data = [
        {"value": budget_count if has_budgets else 1, "name": f"Configured ({budget_count})" if has_budgets else "Not Configured"},
    ]

    if not has_budgets:
        chart_data = [{"value": 1, "name": "No Budgets Configured"}]

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
        "color": ["#27AE60" if has_budgets else "#E74C3C"],
        "series": [
            {
                "name": "Budget Status",
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


# ========== Budget Inventory Section ==========

def _render_budget_inventory():
    """Render Budget Inventory section with budget details."""

    st.markdown("---")
    st.markdown("#### Budget Inventory")

    # Introduction text
    st.markdown("""
    **Budget inventory** listing all active budgets with their names, schema locations, creation dates,
    owners, and descriptions ordered by most recent. This provides visibility into all configured budgets
    across the account.
    """)

    try:
        # Budget Inventory Query
        budget_inventory_query = f"""
SELECT
    'Budget Details' AS section,
    NAME AS budget_name,
    DATABASE_NAME || '.' || SCHEMA_NAME AS full_path,
    CREATED AS created_date,
    OWNER_NAME AS owner,
    COMMENT
FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
WHERE CLASS_NAME = 'BUDGET'
  AND DELETED IS NULL
ORDER BY CREATED DESC
"""


        # Execute the query
        budget_inventory_df = _cached_sql("fc_budget_inventory", budget_inventory_query)

        if not budget_inventory_df.empty:
            st.dataframe(budget_inventory_df, use_container_width=True)

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Budget Inventory Charts")

            # Row 1: Budgets by Owner & Budgets by Schema/Database
            inv_chart_col1, inv_chart_col2 = st.columns(2)

            with inv_chart_col1.container():
                st.markdown("##### Budgets by Owner")
                _render_budgets_by_owner_chart_content(budget_inventory_df, key_prefix="budget_owner_")

            with inv_chart_col2.container():
                st.markdown("##### Budgets by Database/Schema")
                _render_budgets_by_path_chart_content(budget_inventory_df, key_prefix="budget_path_")

            # ========== Budget Statistics Section ==========
            _render_budget_statistics()

            # ========== Budget Utilization Section ==========
            _render_budget_utilization()

            # ========== End-of-Month Projection Section ==========
            _render_budget_projection()

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No budget inventory data available. No budgets are configured in this account.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading budget inventory: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Budgets by Owner Chart Functions ==========

def _render_budgets_by_owner_chart_content(df, key_prefix=""):
    """Render budgets by owner chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budgets_by_owner_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budgets_by_owner_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budgets_by_owner_donut_pie_chart(df, key_prefix)
    else:
        _render_budgets_by_owner_rose_pie_chart(df, key_prefix)


def _render_budgets_by_owner_bar_chart(df, key_prefix=""):
    """Render budgets by owner bar chart using Plotly."""

    owner_counts = df['OWNER'].value_counts().reset_index()
    owner_counts.columns = ['OWNER', 'COUNT']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=owner_counts['OWNER'],
            y=owner_counts['COUNT'],
            marker_color='#29B5E8',
            text=owner_counts['COUNT'],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Budgets: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Owner',
        yaxis_title='Number of Budgets',
        showlegend=False,
        margin=dict(t=20, b=80, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budgets_by_owner_standard_pie_chart(df, key_prefix=""):
    """Render budgets by owner standard pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Owner",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budgets_by_owner_donut_pie_chart(df, key_prefix=""):
    """Render budgets by owner donut pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Owner",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budgets_by_owner_rose_pie_chart(df, key_prefix=""):
    """Render budgets by owner rose pie chart using ECharts."""

    owner_counts = df['OWNER'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{owner} ({count})"}
        for owner, count in owner_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Owner",
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


# ========== Budgets by Path Chart Functions ==========

def _render_budgets_by_path_chart_content(df, key_prefix=""):
    """Render budgets by database/schema path chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budgets_by_path_bar_chart(df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budgets_by_path_standard_pie_chart(df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budgets_by_path_donut_pie_chart(df, key_prefix)
    else:
        _render_budgets_by_path_rose_pie_chart(df, key_prefix)


def _render_budgets_by_path_bar_chart(df, key_prefix=""):
    """Render budgets by path bar chart using Plotly."""

    path_counts = df['FULL_PATH'].value_counts().reset_index()
    path_counts.columns = ['FULL_PATH', 'COUNT']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=path_counts['FULL_PATH'],
            y=path_counts['COUNT'],
            marker_color='#27AE60',
            text=path_counts['COUNT'],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Budgets: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Database.Schema',
        yaxis_title='Number of Budgets',
        showlegend=False,
        margin=dict(t=20, b=100, l=50, r=20),
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budgets_by_path_standard_pie_chart(df, key_prefix=""):
    """Render budgets by path standard pie chart using ECharts."""

    path_counts = df['FULL_PATH'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{path} ({count})"}
        for path, count in path_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Path",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budgets_by_path_donut_pie_chart(df, key_prefix=""):
    """Render budgets by path donut pie chart using ECharts."""

    path_counts = df['FULL_PATH'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{path} ({count})"}
        for path, count in path_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Path",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budgets_by_path_rose_pie_chart(df, key_prefix=""):
    """Render budgets by path rose pie chart using ECharts."""

    path_counts = df['FULL_PATH'].value_counts()

    chart_data = [
        {"value": int(count), "name": f"{path} ({count})"}
        for path, count in path_counts.items()
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "itemWidth": 12,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} budgets ({d}%)"
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
                "name": "Budgets by Path",
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


# ========== Budget Statistics Section ==========

def _render_budget_statistics():
    """Render Budget Statistics section with breakdown of account vs custom budgets."""

    st.markdown("---")
    st.markdown("#### Budget Statistics")

    # Introduction text
    st.markdown("""
    **Budget statistics summary** showing total count broken down into account-level root budgets
    vs custom budgets. This helps understand the budget hierarchy and adoption across the account.
    """)

    try:
        # Budget Statistics Query
        budget_stats_query = f"""
WITH budget_analysis AS (
    SELECT
        NVL(COUNT(*), 0) AS total_budgets,
        NVL(COUNT(CASE WHEN NAME = 'ACCOUNT_ROOT_BUDGET' THEN 1 END), 0) AS account_budgets,
        NVL(COUNT(CASE WHEN NAME != 'ACCOUNT_ROOT_BUDGET' THEN 1 END), 0) AS custom_budgets
    FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
    WHERE CLASS_NAME = 'BUDGET'
      AND DELETED IS NULL
)
SELECT
    'Budget Statistics' AS section,
    total_budgets,
    account_budgets,
    custom_budgets
FROM budget_analysis
"""


        # Execute the query
        budget_stats_df = _cached_sql("fc_budget_stats", budget_stats_query)

        if not budget_stats_df.empty:
            st.dataframe(budget_stats_df, use_container_width=True)

            # Get values for charts
            total_budgets = int(budget_stats_df['TOTAL_BUDGETS'].iloc[0]) if 'TOTAL_BUDGETS' in budget_stats_df.columns else 0
            account_budgets = int(budget_stats_df['ACCOUNT_BUDGETS'].iloc[0]) if 'ACCOUNT_BUDGETS' in budget_stats_df.columns else 0
            custom_budgets = int(budget_stats_df['CUSTOM_BUDGETS'].iloc[0]) if 'CUSTOM_BUDGETS' in budget_stats_df.columns else 0

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Budget Statistics Charts")

            # Row 1: Budget Type Distribution & Total Budget Count
            stats_chart_col1, stats_chart_col2 = st.columns(2)

            with stats_chart_col1.container():
                st.markdown(f"##### Budget Type Distribution: {total_budgets} Total")
                _render_budget_type_dist_chart_content(account_budgets, custom_budgets, key_prefix="budget_type_dist_")

            with stats_chart_col2.container():
                st.markdown(f"##### Budget Breakdown")
                _render_budget_breakdown_chart_content(total_budgets, account_budgets, custom_budgets, key_prefix="budget_breakdown_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No budget statistics data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading budget statistics: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Budget Type Distribution Chart Functions ==========

def _render_budget_type_dist_chart_content(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_type_dist_bar_chart(account_budgets, custom_budgets, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_type_dist_standard_pie_chart(account_budgets, custom_budgets, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_type_dist_donut_pie_chart(account_budgets, custom_budgets, key_prefix)
    else:
        _render_budget_type_dist_rose_pie_chart(account_budgets, custom_budgets, key_prefix)


def _render_budget_type_dist_bar_chart(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution bar chart using Plotly."""

    labels = ['Account Root Budget', 'Custom Budgets']
    values = [account_budgets, custom_budgets]
    colors = ['#27AE60', '#E8A229']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=values,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Budget Type',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budget_type_dist_standard_pie_chart(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution standard pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root Budget ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom Budgets ({custom_budgets})"},
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
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#27AE60", "#E8A229"],
        "series": [
            {
                "name": "Budget Type",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_type_dist_donut_pie_chart(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution donut pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root Budget ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom Budgets ({custom_budgets})"},
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
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#27AE60", "#E8A229"],
        "series": [
            {
                "name": "Budget Type",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_type_dist_rose_pie_chart(account_budgets, custom_budgets, key_prefix=""):
    """Render budget type distribution rose pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root Budget ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom Budgets ({custom_budgets})"},
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
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#27AE60", "#E8A229"],
        "series": [
            {
                "name": "Budget Type",
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


# ========== Budget Breakdown Chart Functions ==========

def _render_budget_breakdown_chart_content(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_breakdown_bar_chart(total_budgets, account_budgets, custom_budgets, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_breakdown_standard_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_breakdown_donut_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix)
    else:
        _render_budget_breakdown_rose_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix)


def _render_budget_breakdown_bar_chart(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown bar chart using Plotly."""

    labels = ['Total Budgets', 'Account Root', 'Custom']
    values = [total_budgets, account_budgets, custom_budgets]
    colors = ['#29B5E8', '#27AE60', '#E8A229']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=values,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Category',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budget_breakdown_standard_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown standard pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom ({custom_budgets})"},
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
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#27AE60", "#E8A229"],
        "series": [
            {
                "name": "Budget Breakdown",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_breakdown_donut_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown donut pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom ({custom_budgets})"},
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
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#27AE60", "#E8A229"],
        "series": [
            {
                "name": "Budget Breakdown",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_breakdown_rose_pie_chart(total_budgets, account_budgets, custom_budgets, key_prefix=""):
    """Render budget breakdown rose pie chart using ECharts."""

    chart_data = [
        {"value": account_budgets, "name": f"Account Root ({account_budgets})"},
        {"value": custom_budgets, "name": f"Custom ({custom_budgets})"},
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
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#27AE60", "#E8A229"],
        "series": [
            {
                "name": "Budget Breakdown",
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


# ========== Budget Utilization Section ==========

def _render_budget_utilization():
    """Render Budget Utilization section with month-to-date spend tracking."""

    st.markdown("---")
    st.markdown("#### Budget Utilization (Month-to-Date)")

    # Introduction text
    st.markdown("""
    **Month-to-date budget utilization** tracking against 500 credit limit showing current spend,
    utilization percentage, remaining credits, and health status (warning at >90%, caution at >75%).
    """)

    try:
        # Budget Utilization Query
        budget_util_query = f"""
WITH current_month_spend AS (
    SELECT NVL(SUM(CREDITS_USED), 0) AS month_to_date_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE START_TIME >= DATE_TRUNC('month', CURRENT_TIMESTAMP())
)
SELECT
    'Budget Utilization (Month-to-Date)' AS section,
    500 AS budget_limit_credits,
    s.month_to_date_credits AS current_spend_credits,
    ROUND((s.month_to_date_credits / 500) * 100, 2) AS utilization_percent,
    500 - s.month_to_date_credits AS remaining_credits,
    CASE
        WHEN (s.month_to_date_credits / 500) > 0.9 THEN 'WARNING: >90% utilized'
        WHEN (s.month_to_date_credits / 500) > 0.75 THEN 'CAUTION: >75% utilized'
        ELSE 'HEALTHY: <75% utilized'
    END AS status
FROM current_month_spend s
"""


        # Execute the query
        budget_util_df = _cached_sql("fc_budget_util", budget_util_query)

        if not budget_util_df.empty:
            st.dataframe(budget_util_df, use_container_width=True)

            # Get values for charts
            budget_limit = float(budget_util_df['BUDGET_LIMIT_CREDITS'].iloc[0]) if 'BUDGET_LIMIT_CREDITS' in budget_util_df.columns else 500
            current_spend = float(budget_util_df['CURRENT_SPEND_CREDITS'].iloc[0]) if 'CURRENT_SPEND_CREDITS' in budget_util_df.columns else 0
            utilization_pct = float(budget_util_df['UTILIZATION_PERCENT'].iloc[0]) if 'UTILIZATION_PERCENT' in budget_util_df.columns else 0
            remaining = float(budget_util_df['REMAINING_CREDITS'].iloc[0]) if 'REMAINING_CREDITS' in budget_util_df.columns else 500
            status = str(budget_util_df['STATUS'].iloc[0]) if 'STATUS' in budget_util_df.columns else 'HEALTHY'

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### Budget Utilization Charts")

            # Row 1: Utilization Gauge & Spend vs Remaining
            util_chart_col1, util_chart_col2 = st.columns(2)

            with util_chart_col1.container():
                st.markdown(f"##### Budget Utilization: {utilization_pct:.1f}%")
                _render_budget_utilization_chart_content(current_spend, remaining, budget_limit, key_prefix="budget_util_gauge_")

            with util_chart_col2.container():
                st.markdown(f"##### Spend vs Remaining: {budget_limit:.0f} Credits")
                _render_spend_remaining_chart_content(current_spend, remaining, key_prefix="spend_remaining_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No budget utilization data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading budget utilization: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Budget Utilization Chart Functions ==========

def _render_budget_utilization_chart_content(current_spend, remaining, budget_limit, key_prefix=""):
    """Render budget utilization chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_budget_utilization_bar_chart(current_spend, remaining, budget_limit, key_prefix)
    elif chart_type == "Pie Chart":
        _render_budget_utilization_standard_pie_chart(current_spend, remaining, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_budget_utilization_donut_pie_chart(current_spend, remaining, key_prefix)
    else:
        _render_budget_utilization_rose_pie_chart(current_spend, remaining, key_prefix)


def _render_budget_utilization_bar_chart(current_spend, remaining, budget_limit, key_prefix=""):
    """Render budget utilization bar chart using Plotly."""

    # Determine color based on utilization
    utilization_pct = (current_spend / budget_limit) * 100 if budget_limit > 0 else 0
    if utilization_pct > 90:
        spend_color = '#E74C3C'  # Red - Warning
    elif utilization_pct > 75:
        spend_color = '#E8A229'  # Orange - Caution
    else:
        spend_color = '#27AE60'  # Green - Healthy

    labels = ['Current Spend', 'Remaining', 'Budget Limit']
    values = [current_spend, remaining, budget_limit]
    colors = [spend_color, '#29B5E8', '#666666']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:.1f}" for v in values],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Credits: %{y:.1f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='Category',
        yaxis_title='Credits',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_budget_utilization_standard_pie_chart(current_spend, remaining, key_prefix=""):
    """Render budget utilization standard pie chart using ECharts."""

    # Determine color based on utilization
    total = current_spend + remaining
    utilization_pct = (current_spend / total) * 100 if total > 0 else 0
    if utilization_pct > 90:
        spend_color = '#E74C3C'  # Red - Warning
    elif utilization_pct > 75:
        spend_color = '#E8A229'  # Orange - Caution
    else:
        spend_color = '#27AE60'  # Green - Healthy

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Current Spend ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
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
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [spend_color, "#29B5E8"],
        "series": [
            {
                "name": "Budget Utilization",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_budget_utilization_donut_pie_chart(current_spend, remaining, key_prefix=""):
    """Render budget utilization donut pie chart using ECharts."""

    # Determine color based on utilization
    total = current_spend + remaining
    utilization_pct = (current_spend / total) * 100 if total > 0 else 0
    if utilization_pct > 90:
        spend_color = '#E74C3C'  # Red - Warning
    elif utilization_pct > 75:
        spend_color = '#E8A229'  # Orange - Caution
    else:
        spend_color = '#27AE60'  # Green - Healthy

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Current Spend ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
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
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [spend_color, "#29B5E8"],
        "series": [
            {
                "name": "Budget Utilization",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_budget_utilization_rose_pie_chart(current_spend, remaining, key_prefix=""):
    """Render budget utilization rose pie chart using ECharts."""

    # Determine color based on utilization
    total = current_spend + remaining
    utilization_pct = (current_spend / total) * 100 if total > 0 else 0
    if utilization_pct > 90:
        spend_color = '#E74C3C'  # Red - Warning
    elif utilization_pct > 75:
        spend_color = '#E8A229'  # Orange - Caution
    else:
        spend_color = '#27AE60'  # Green - Healthy

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Current Spend ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
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
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [spend_color, "#29B5E8"],
        "series": [
            {
                "name": "Budget Utilization",
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


# ========== Spend vs Remaining Chart Functions ==========

def _render_spend_remaining_chart_content(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_spend_remaining_bar_chart(current_spend, remaining, key_prefix)
    elif chart_type == "Pie Chart":
        _render_spend_remaining_standard_pie_chart(current_spend, remaining, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_spend_remaining_donut_pie_chart(current_spend, remaining, key_prefix)
    else:
        _render_spend_remaining_rose_pie_chart(current_spend, remaining, key_prefix)


def _render_spend_remaining_bar_chart(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining bar chart using Plotly."""

    # Stacked bar chart showing spend vs remaining
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Current Spend',
        x=['Budget'],
        y=[current_spend],
        marker_color='#E8A229',
        text=[f"{current_spend:.1f}"],
        textposition='inside',
        textfont=dict(size=12, color='white')
    ))

    fig.add_trace(go.Bar(
        name='Remaining',
        x=['Budget'],
        y=[remaining],
        marker_color='#29B5E8',
        text=[f"{remaining:.1f}"],
        textposition='inside',
        textfont=dict(size=12, color='white')
    ))

    fig.update_layout(
        height=350,
        barmode='stack',
        xaxis_title='',
        yaxis_title='Credits',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        margin=dict(t=40, b=40, l=50, r=20)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_spend_remaining_standard_pie_chart(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining standard pie chart using ECharts."""

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Spent ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
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
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#E8A229", "#29B5E8"],
        "series": [
            {
                "name": "Spend vs Remaining",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_spend_remaining_donut_pie_chart(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining donut pie chart using ECharts."""

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Spent ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
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
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#E8A229", "#29B5E8"],
        "series": [
            {
                "name": "Spend vs Remaining",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_spend_remaining_rose_pie_chart(current_spend, remaining, key_prefix=""):
    """Render spend vs remaining rose pie chart using ECharts."""

    chart_data = [
        {"value": round(current_spend, 1), "name": f"Spent ({current_spend:.1f})"},
        {"value": round(remaining, 1), "name": f"Remaining ({remaining:.1f})"},
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
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#E8A229", "#29B5E8"],
        "series": [
            {
                "name": "Spend vs Remaining",
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


# ========== End-of-Month Projection Section ==========

def _render_budget_projection():
    """Render End-of-Month Projection section with spend forecast."""

    st.markdown("---")
    st.markdown("#### End-of-Month Projection")

    # Introduction text
    st.markdown("""
    **End-of-month credit spend forecast** using 30-day average daily spend to project month-end total
    against 500 credit budget limit with status alerts for exceeding or nearing budget.
    """)

    try:
        # End-of-Month Projection Query
        projection_query = f"""
WITH daily_avg AS (
    SELECT
        AVG(daily_credits) AS avg_daily_spend
    FROM (
        SELECT
            DATE(START_TIME) AS credit_date,
            NVL(SUM(CREDITS_USED), 0) AS daily_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE START_TIME >= DATEADD('day', -30, CURRENT_DATE)
        GROUP BY DATE(START_TIME)
    )
)
SELECT
    'End-of-Month Projection' AS section,
    500 AS budget_limit_credits,
    d.avg_daily_spend AS avg_daily_spend_30d,
    DAY(LAST_DAY(CURRENT_DATE)) AS days_in_month,
    DAY(CURRENT_DATE) AS days_elapsed,
    ROUND(d.avg_daily_spend * DAY(LAST_DAY(CURRENT_DATE)), 2) AS projected_month_end_credits,
    CASE
        WHEN (d.avg_daily_spend * DAY(LAST_DAY(CURRENT_DATE))) > 500
        THEN 'PROJECTED TO EXCEED BUDGET'
        WHEN (d.avg_daily_spend * DAY(LAST_DAY(CURRENT_DATE))) > 450
        THEN 'PROJECTED NEAR BUDGET LIMIT'
        ELSE 'PROJECTED WITHIN BUDGET'
    END AS projection_status
FROM daily_avg d
"""


        # Execute the query
        projection_df = _cached_sql("fc_projection", projection_query)

        if not projection_df.empty:
            st.dataframe(projection_df, use_container_width=True)

            # Get values for charts
            budget_limit = float(projection_df['BUDGET_LIMIT_CREDITS'].iloc[0]) if 'BUDGET_LIMIT_CREDITS' in projection_df.columns else 500
            avg_daily = float(projection_df['AVG_DAILY_SPEND_30D'].iloc[0]) if 'AVG_DAILY_SPEND_30D' in projection_df.columns else 0
            days_in_month = int(projection_df['DAYS_IN_MONTH'].iloc[0]) if 'DAYS_IN_MONTH' in projection_df.columns else 30
            days_elapsed = int(projection_df['DAYS_ELAPSED'].iloc[0]) if 'DAYS_ELAPSED' in projection_df.columns else 0
            projected_credits = float(projection_df['PROJECTED_MONTH_END_CREDITS'].iloc[0]) if 'PROJECTED_MONTH_END_CREDITS' in projection_df.columns else 0
            status = str(projection_df['PROJECTION_STATUS'].iloc[0]) if 'PROJECTION_STATUS' in projection_df.columns else 'UNKNOWN'

            # Charts Section - 2 charts per row
            st.markdown("---")
            st.markdown("#### End-of-Month Projection Charts")

            # Row 1: Projected vs Budget & Daily Progress
            proj_chart_col1, proj_chart_col2 = st.columns(2)

            with proj_chart_col1.container():
                st.markdown(f"##### Projected vs Budget: {projected_credits:.1f} / {budget_limit:.0f}")
                _render_projection_vs_budget_chart_content(projected_credits, budget_limit, key_prefix="proj_vs_budget_")

            with proj_chart_col2.container():
                st.markdown(f"##### Month Progress: Day {days_elapsed} of {days_in_month}")
                _render_month_progress_chart_content(days_elapsed, days_in_month, avg_daily, key_prefix="month_progress_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No projection data available. Insufficient spending history for forecast.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading projection: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ========== Projection vs Budget Chart Functions ==========

def _render_projection_vs_budget_chart_content(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_projection_vs_budget_bar_chart(projected_credits, budget_limit, key_prefix)
    elif chart_type == "Pie Chart":
        _render_projection_vs_budget_standard_pie_chart(projected_credits, budget_limit, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_projection_vs_budget_donut_pie_chart(projected_credits, budget_limit, key_prefix)
    else:
        _render_projection_vs_budget_rose_pie_chart(projected_credits, budget_limit, key_prefix)


def _render_projection_vs_budget_bar_chart(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget bar chart using Plotly."""

    # Determine color based on projection status
    if projected_credits > budget_limit:
        proj_color = '#E74C3C'  # Red - Exceeds
    elif projected_credits > budget_limit * 0.9:
        proj_color = '#E8A229'  # Orange - Near limit
    else:
        proj_color = '#27AE60'  # Green - Within budget

    labels = ['Projected Spend', 'Budget Limit']
    values = [projected_credits, budget_limit]
    colors = [proj_color, '#29B5E8']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:.1f}" for v in values],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Credits: %{y:.1f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='Credits',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_projection_vs_budget_standard_pie_chart(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget standard pie chart using ECharts."""

    # Determine color based on projection status
    if projected_credits > budget_limit:
        proj_color = '#E74C3C'  # Red - Exceeds
    elif projected_credits > budget_limit * 0.9:
        proj_color = '#E8A229'  # Orange - Near limit
    else:
        proj_color = '#27AE60'  # Green - Within budget

    # Show projected as portion of budget
    remaining_in_budget = max(0, budget_limit - projected_credits)

    chart_data = [
        {"value": round(projected_credits, 1), "name": f"Projected ({projected_credits:.1f})"},
        {"value": round(remaining_in_budget, 1), "name": f"Buffer ({remaining_in_budget:.1f})"},
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
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [proj_color, "#29B5E8"],
        "series": [
            {
                "name": "Projection vs Budget",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_projection_vs_budget_donut_pie_chart(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget donut pie chart using ECharts."""

    # Determine color based on projection status
    if projected_credits > budget_limit:
        proj_color = '#E74C3C'  # Red - Exceeds
    elif projected_credits > budget_limit * 0.9:
        proj_color = '#E8A229'  # Orange - Near limit
    else:
        proj_color = '#27AE60'  # Green - Within budget

    remaining_in_budget = max(0, budget_limit - projected_credits)

    chart_data = [
        {"value": round(projected_credits, 1), "name": f"Projected ({projected_credits:.1f})"},
        {"value": round(remaining_in_budget, 1), "name": f"Buffer ({remaining_in_budget:.1f})"},
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
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [proj_color, "#29B5E8"],
        "series": [
            {
                "name": "Projection vs Budget",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_projection_vs_budget_rose_pie_chart(projected_credits, budget_limit, key_prefix=""):
    """Render projection vs budget rose pie chart using ECharts."""

    # Determine color based on projection status
    if projected_credits > budget_limit:
        proj_color = '#E74C3C'  # Red - Exceeds
    elif projected_credits > budget_limit * 0.9:
        proj_color = '#E8A229'  # Orange - Near limit
    else:
        proj_color = '#27AE60'  # Green - Within budget

    remaining_in_budget = max(0, budget_limit - projected_credits)

    chart_data = [
        {"value": round(projected_credits, 1), "name": f"Projected ({projected_credits:.1f})"},
        {"value": round(remaining_in_budget, 1), "name": f"Buffer ({remaining_in_budget:.1f})"},
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
            "formatter": "{b}: {c} credits ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": [proj_color, "#29B5E8"],
        "series": [
            {
                "name": "Projection vs Budget",
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


# ========== Month Progress Chart Functions ==========

def _render_month_progress_chart_content(days_elapsed, days_in_month, avg_daily, key_prefix=""):
    """Render month progress chart content with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    if chart_type == "Bar Chart":
        _render_month_progress_bar_chart(days_elapsed, days_in_month, avg_daily, key_prefix)
    elif chart_type == "Pie Chart":
        _render_month_progress_standard_pie_chart(days_elapsed, days_in_month, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_month_progress_donut_pie_chart(days_elapsed, days_in_month, key_prefix)
    else:
        _render_month_progress_rose_pie_chart(days_elapsed, days_in_month, key_prefix)


def _render_month_progress_bar_chart(days_elapsed, days_in_month, avg_daily, key_prefix=""):
    """Render month progress bar chart using Plotly."""

    days_remaining = days_in_month - days_elapsed

    labels = ['Days Elapsed', 'Days Remaining', f'Avg Daily Spend']
    values = [days_elapsed, days_remaining, avg_daily]
    colors = ['#27AE60', '#29B5E8', '#E8A229']

    fig_bar = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{days_elapsed}", f"{days_remaining}", f"{avg_daily:.2f}"],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Value: %{y:.2f}<extra></extra>'
        )
    ])

    fig_bar.update_layout(
        height=350,
        xaxis_title='',
        yaxis_title='Days / Credits',
        showlegend=False,
        margin=dict(t=20, b=40, l=50, r=20)
    )

    st.plotly_chart(fig_bar, use_container_width=True, key=f"{key_prefix}bar_plotly")


def _render_month_progress_standard_pie_chart(days_elapsed, days_in_month, key_prefix=""):
    """Render month progress standard pie chart using ECharts."""

    days_remaining = days_in_month - days_elapsed

    chart_data = [
        {"value": days_elapsed, "name": f"Days Elapsed ({days_elapsed})"},
        {"value": days_remaining, "name": f"Days Remaining ({days_remaining})"},
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
            "formatter": "{b}: {c} days ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#27AE60", "#29B5E8"],
        "series": [
            {
                "name": "Month Progress",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_month_progress_donut_pie_chart(days_elapsed, days_in_month, key_prefix=""):
    """Render month progress donut pie chart using ECharts."""

    days_remaining = days_in_month - days_elapsed

    chart_data = [
        {"value": days_elapsed, "name": f"Days Elapsed ({days_elapsed})"},
        {"value": days_remaining, "name": f"Days Remaining ({days_remaining})"},
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
            "formatter": "{b}: {c} days ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#27AE60", "#29B5E8"],
        "series": [
            {
                "name": "Month Progress",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_month_progress_rose_pie_chart(days_elapsed, days_in_month, key_prefix=""):
    """Render month progress rose pie chart using ECharts."""

    days_remaining = days_in_month - days_elapsed

    chart_data = [
        {"value": days_elapsed, "name": f"Days Elapsed ({days_elapsed})"},
        {"value": days_remaining, "name": f"Days Remaining ({days_remaining})"},
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
            "formatter": "{b}: {c} days ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#27AE60", "#29B5E8"],
        "series": [
            {
                "name": "Month Progress",
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


def _render_warehouses_without_controls():
    import plotly.graph_objects as go
    import pandas as pd
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Exposure Risk:</b> Warehouses consuming more than 10 credits month-to-date '
        'that have no resource monitor attached. These warehouses have uncapped spend.</div>',
        unsafe_allow_html=True)
    try:
        session = st.session_state.session
        query = """
        WITH warehouse_spend AS (
            SELECT
                WAREHOUSE_NAME,
                ROUND(SUM(CREDITS_USED), 2) AS mtd_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATE_TRUNC('month', CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY WAREHOUSE_NAME
        ),
        monitored AS (
            SELECT DISTINCT OBJECT_NAME AS WAREHOUSE_NAME
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE POLICY_KIND = 'RESOURCE_MONITOR'
            UNION
            SELECT DISTINCT WAREHOUSE_NAME
            FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS rm
            WHERE rm.DELETED IS NULL
        )
        SELECT
            ws.WAREHOUSE_NAME,
            ws.mtd_credits,
            CASE WHEN m.WAREHOUSE_NAME IS NOT NULL THEN 'Monitored' ELSE 'UNMONITORED' END AS control_status
        FROM warehouse_spend ws
        LEFT JOIN monitored m ON ws.WAREHOUSE_NAME = m.WAREHOUSE_NAME
        WHERE ws.mtd_credits > 10
        ORDER BY control_status, ws.mtd_credits DESC
        """
        df = _cached_sql("fc_wh_without_controls", query)
        if df.empty:
            st.info("No warehouses consuming more than 10 credits MTD found.")
            return
        df['MTD_CREDITS'] = pd.to_numeric(df['MTD_CREDITS'], errors='coerce').fillna(0)
        unmonitored = df[df['CONTROL_STATUS'] == 'UNMONITORED']
        monitored = df[df['CONTROL_STATUS'] == 'Monitored']
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Warehouses >10 Credits MTD", len(df))
        with col2:
            st.metric("Unmonitored (Risk)", len(unmonitored))
        with col3:
            unmon_credits = unmonitored['MTD_CREDITS'].sum()
            st.metric("Unmonitored Credits MTD", f"{unmon_credits:.1f}")
        bar_colors = ['#E74C3C' if s == 'UNMONITORED' else '#29B5E8' for s in df['CONTROL_STATUS']]
        fig = go.Figure(go.Bar(
            x=df['WAREHOUSE_NAME'], y=df['MTD_CREDITS'],
            marker_color=bar_colors,
            text=[f"{v:.1f}" for v in df['MTD_CREDITS']], textposition='outside',
            hovertemplate='<b>%{x}</b><br>Credits: %{y:.2f}<br>Status: %{customdata[0]}<extra></extra>',
            customdata=df[['CONTROL_STATUS']].values
        ))
        fig.update_layout(
            title='MTD Credits by Warehouse (Red = Unmonitored)',
            xaxis_title='Warehouse', yaxis_title='Credits (MTD)',
            height=360, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        if not unmonitored.empty:
            st.markdown("**Unmonitored Warehouses — Governance Gap**")
            st.dataframe(unmonitored[['WAREHOUSE_NAME', 'MTD_CREDITS', 'CONTROL_STATUS']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_monitors_approaching_limits():
    import plotly.graph_objects as go
    import pandas as pd
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;Resource monitors where current month-to-date spend is approaching or exceeding '
        'the configured credit quota. Monitors above 75% utilisation may trigger suspension.</div>',
        unsafe_allow_html=True)
    try:
        session = st.session_state.session
        query = """
        WITH monitor_spend AS (
            SELECT
                WAREHOUSE_NAME,
                SUM(CREDITS_USED) AS mtd_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE START_TIME >= DATE_TRUNC('month', CURRENT_TIMESTAMP())
              AND WAREHOUSE_NAME IS NOT NULL
            GROUP BY WAREHOUSE_NAME
        )
        SELECT
            rm.NAME AS monitor_name,
            rm.CREDIT_QUOTA,
            rm.FREQUENCY,
            rm.SUSPEND_AT,
            rm.SUSPEND_IMMEDIATELY_AT,
            COALESCE(SUM(ms.mtd_credits), 0) AS mtd_credits_used,
            ROUND(COALESCE(SUM(ms.mtd_credits), 0) / NULLIF(rm.CREDIT_QUOTA, 0) * 100, 1) AS pct_quota_used,
            CASE
                WHEN COALESCE(SUM(ms.mtd_credits), 0) / NULLIF(rm.CREDIT_QUOTA, 0) >= 0.9 THEN 'CRITICAL (>90%)'
                WHEN COALESCE(SUM(ms.mtd_credits), 0) / NULLIF(rm.CREDIT_QUOTA, 0) >= 0.75 THEN 'HIGH (>75%)'
                WHEN COALESCE(SUM(ms.mtd_credits), 0) / NULLIF(rm.CREDIT_QUOTA, 0) >= 0.5 THEN 'MODERATE (>50%)'
                ELSE 'LOW (<50%)'
            END AS usage_status
        FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS rm
        LEFT JOIN monitor_spend ms ON ms.WAREHOUSE_NAME = rm.NAME
        WHERE rm.DELETED IS NULL
          AND rm.CREDIT_QUOTA > 0
        GROUP BY rm.NAME, rm.CREDIT_QUOTA, rm.FREQUENCY, rm.SUSPEND_AT, rm.SUSPEND_IMMEDIATELY_AT
        ORDER BY pct_quota_used DESC NULLS LAST
        """
        df = _cached_sql("fc_monitors_limits", query)
        if df.empty:
            st.info("No resource monitors configured. Set up resource monitors to track credit quota utilisation.")
            return
        df['PCT_QUOTA_USED'] = pd.to_numeric(df['PCT_QUOTA_USED'], errors='coerce').fillna(0)
        df['MTD_CREDITS_USED'] = pd.to_numeric(df['MTD_CREDITS_USED'], errors='coerce').fillna(0)
        df['CREDIT_QUOTA'] = pd.to_numeric(df['CREDIT_QUOTA'], errors='coerce').fillna(0)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Resource Monitors", len(df))
        with col2:
            critical = len(df[df['PCT_QUOTA_USED'] >= 90])
            st.metric("Critical (>90%)", critical)
        with col3:
            high = len(df[df['PCT_QUOTA_USED'] >= 75])
            st.metric("High (>75%)", high)
        _u_colors = {'CRITICAL (>90%)': '#E74C3C', 'HIGH (>75%)': '#E8A229', 'MODERATE (>50%)': '#75C2D8', 'LOW (<50%)': '#29B5E8'}
        bar_colors = [_u_colors.get(s, '#29B5E8') for s in df['USAGE_STATUS']]
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Credits Used MTD', x=df['MONITOR_NAME'], y=df['MTD_CREDITS_USED'],
                             marker_color=bar_colors, text=[f"{v:.1f}" for v in df['MTD_CREDITS_USED']], textposition='outside'))
        fig.add_trace(go.Scatter(name='Quota', x=df['MONITOR_NAME'], y=df['CREDIT_QUOTA'],
                                 mode='markers', marker=dict(symbol='diamond', size=10, color='#003D73')))
        fig.update_layout(
            title='Resource Monitor Credits Used vs Quota',
            xaxis_title='Monitor', yaxis_title='Credits',
            height=380, margin=dict(t=50, b=80),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['MONITOR_NAME', 'CREDIT_QUOTA', 'MTD_CREDITS_USED', 'PCT_QUOTA_USED', 'SUSPEND_AT', 'USAGE_STATUS']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_statement_timeouts():
    import plotly.graph_objects as go
    import pandas as pd
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Statement Timeouts:</b> Queries that were terminated by the statement timeout '
        'parameter. High counts indicate either over-complex queries or a timeout setting that is too aggressive.</div>',
        unsafe_allow_html=True)
    try:
        session = st.session_state.session
        query = """
        SELECT
            WAREHOUSE_NAME,
            USER_NAME,
            COUNT(*) AS timeout_count,
            ROUND(AVG(TOTAL_ELAPSED_TIME) / 1000.0, 1) AS avg_elapsed_sec,
            ROUND(MAX(TOTAL_ELAPSED_TIME) / 1000.0, 1) AS max_elapsed_sec,
            DATE_TRUNC('day', MIN(START_TIME)) AS first_seen,
            DATE_TRUNC('day', MAX(START_TIME)) AS last_seen
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
        WHERE ERROR_CODE = '100188'
          AND START_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
          AND WAREHOUSE_NAME IS NOT NULL
        GROUP BY WAREHOUSE_NAME, USER_NAME
        ORDER BY timeout_count DESC
        LIMIT 30
        """
        df = _cached_sql("fc_statement_timeouts", query)
        if df.empty:
            st.success("No statement timeouts detected in the last 30 days.")
            return
        df['TIMEOUT_COUNT'] = pd.to_numeric(df['TIMEOUT_COUNT'], errors='coerce').fillna(0)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Timeout Events (30d)", int(df['TIMEOUT_COUNT'].sum()))
        with col2:
            st.metric("Affected Warehouses", df['WAREHOUSE_NAME'].nunique())
        wh_counts = df.groupby('WAREHOUSE_NAME')['TIMEOUT_COUNT'].sum().reset_index().sort_values('TIMEOUT_COUNT', ascending=False).head(15)
        fig = go.Figure(go.Bar(
            x=wh_counts['WAREHOUSE_NAME'], y=wh_counts['TIMEOUT_COUNT'],
            marker_color='#E8A229',
            text=wh_counts['TIMEOUT_COUNT'], textposition='outside'
        ))
        fig.update_layout(
            title='Statement Timeouts by Warehouse (Last 30 Days)',
            xaxis_title='Warehouse', yaxis_title='Timeout Count',
            height=360, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['WAREHOUSE_NAME', 'USER_NAME', 'TIMEOUT_COUNT', 'AVG_ELAPSED_SEC', 'MAX_ELAPSED_SEC', 'LAST_SEEN']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_always_on_warehouses():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Always-On WH Pattern:</b> Warehouses running ≥12 hours/day on average over the last 7 days. '
        'These may need auto-suspend configuration review.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        WITH daily_usage AS (
            SELECT
                warehouse_name,
                DATE(start_time) AS usage_date,
                COUNT(DISTINCT HOUR(start_time)) AS hours_running_per_day
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE start_time >= DATEADD('day', -7, CURRENT_DATE)
            GROUP BY warehouse_name, DATE(start_time)
        )
        SELECT
            warehouse_name,
            ROUND(AVG(hours_running_per_day), 1) AS avg_hours_per_day,
            MAX(hours_running_per_day) AS max_hours_per_day,
            COUNT(*) AS days_tracked,
            CASE
                WHEN AVG(hours_running_per_day) >= 20 THEN 'ALWAYS_ON'
                WHEN AVG(hours_running_per_day) >= 12 THEN 'HIGH_UPTIME'
                ELSE 'NORMAL'
            END AS uptime_status
        FROM daily_usage
        GROUP BY warehouse_name
        HAVING AVG(hours_running_per_day) >= 12
        ORDER BY avg_hours_per_day DESC
        """
        df = _cached_sql("fc_always_on_wh", query)
        if df.empty:
            st.success("No warehouses detected running ≥12 hours/day on average.")
            return
        df['AVG_HOURS_PER_DAY'] = pd.to_numeric(df['AVG_HOURS_PER_DAY'], errors='coerce').fillna(0)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Always-On Warehouses", len(df[df['UPTIME_STATUS'] == 'ALWAYS_ON']))
        with col2:
            st.metric("High Uptime Warehouses", len(df[df['UPTIME_STATUS'] == 'HIGH_UPTIME']))
        status_colors = {'ALWAYS_ON': '#E8A229', 'HIGH_UPTIME': '#29B5E8', 'NORMAL': '#75C2D8'}
        bar_colors = [status_colors.get(s, '#29B5E8') for s in df['UPTIME_STATUS']]
        fig = go.Figure(go.Bar(
            x=df['WAREHOUSE_NAME'], y=df['AVG_HOURS_PER_DAY'],
            marker_color=bar_colors,
            text=[f"{v:.1f}h" for v in df['AVG_HOURS_PER_DAY']], textposition='outside'
        ))
        fig.add_hline(y=12, line_dash="dash", line_color="#003D73", annotation_text="12h threshold")
        fig.update_layout(
            title='Average Daily Uptime by Warehouse (Last 7 Days)',
            xaxis_title='Warehouse', yaxis_title='Avg Hours/Day',
            height=380, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_idle_time_analysis():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Idle Time Analysis:</b> Credits consumed during idle time vs active query execution. '
        'Warehouses with high idle percentages (>15–30%) are candidates for auto-suspend tuning.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            warehouse_name,
            ROUND(SUM(credits_used_compute), 2) AS total_compute_credits,
            ROUND(SUM(credits_attributed_compute_queries), 2) AS query_credits,
            ROUND(SUM(credits_used_compute) - SUM(credits_attributed_compute_queries), 2) AS idle_credits,
            ROUND(
                (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
                NULLIF(SUM(credits_used_compute), 0) * 100, 2
            ) AS idle_percent,
            CASE
                WHEN (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
                     NULLIF(SUM(credits_used_compute), 0) > 0.3 THEN 'HIGH_IDLE'
                WHEN (SUM(credits_used_compute) - SUM(credits_attributed_compute_queries)) /
                     NULLIF(SUM(credits_used_compute), 0) > 0.15 THEN 'MODERATE_IDLE'
                ELSE 'LOW_IDLE'
            END AS idle_status
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE start_time >= DATEADD('day', -10, CURRENT_DATE)
          AND credits_attributed_compute_queries IS NOT NULL
        GROUP BY warehouse_name
        HAVING SUM(credits_used_compute) - SUM(credits_attributed_compute_queries) > 0
        ORDER BY idle_credits DESC
        """
        df = _cached_sql("fc_idle_time", query)
        if df.empty:
            st.success("No significant idle credit waste detected.")
            return
        for c in ['TOTAL_COMPUTE_CREDITS', 'QUERY_CREDITS', 'IDLE_CREDITS', 'IDLE_PERCENT']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Idle Credits", f"{df['IDLE_CREDITS'].sum():,.1f}")
        with col2:
            st.metric("High Idle WHs", len(df[df['IDLE_STATUS'] == 'HIGH_IDLE']))
        with col3:
            avg_idle = df['IDLE_PERCENT'].mean()
            st.metric("Avg Idle %", f"{avg_idle:.1f}%")
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Query Credits', x=df['WAREHOUSE_NAME'], y=df['QUERY_CREDITS'],
                             marker_color='#29B5E8'))
        fig.add_trace(go.Bar(name='Idle Credits', x=df['WAREHOUSE_NAME'], y=df['IDLE_CREDITS'],
                             marker_color='#E8A229'))
        fig.update_layout(
            barmode='stack',
            title='Compute vs Idle Credits by Warehouse (Last 10 Days)',
            xaxis_title='Warehouse', yaxis_title='Credits',
            height=400, margin=dict(t=50, b=80),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['WAREHOUSE_NAME', 'TOTAL_COMPUTE_CREDITS', 'QUERY_CREDITS', 'IDLE_CREDITS', 'IDLE_PERCENT', 'IDLE_STATUS']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_rm_coverage_gap():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>RM Coverage Gap:</b> Compares unmonitored warehouses (>100 credits MTD) '
        'with configured resource monitors and their total quota allocation.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        WITH warehouse_spend AS (
            SELECT warehouse_name, SUM(credits_used) AS monthly_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE start_time >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY warehouse_name
        ),
        monitor_quotas AS (
            SELECT rm.name AS monitor_name, rm.credit_quota
            FROM SNOWFLAKE.ACCOUNT_USAGE.RESOURCE_MONITORS rm
            WHERE rm.deleted IS NULL
        ),
        combined AS (
            SELECT
                'Warehouses without Resource Monitors' AS risk_category,
                COUNT(DISTINCT warehouse_name) AS item_count,
                ROUND(SUM(monthly_credits), 2) AS credits_or_quota
            FROM warehouse_spend
            WHERE monthly_credits > 100
            UNION ALL
            SELECT
                'Resource Monitors Configured' AS risk_category,
                COUNT(*) AS item_count,
                ROUND(SUM(credit_quota), 2) AS credits_or_quota
            FROM monitor_quotas
        )
        SELECT risk_category, item_count, credits_or_quota
        FROM combined
        """
        df = _cached_sql("fc_rm_coverage_gap", query)
        if df.empty:
            st.info("No data available for resource monitor coverage analysis.")
            return
        df['ITEM_COUNT'] = pd.to_numeric(df['ITEM_COUNT'], errors='coerce').fillna(0)
        df['CREDITS_OR_QUOTA'] = pd.to_numeric(df['CREDITS_OR_QUOTA'], errors='coerce').fillna(0)
        col1, col2 = st.columns(2)
        for i, row in df.iterrows():
            target = col1 if i == 0 else col2
            with target:
                st.metric(row['RISK_CATEGORY'], f"{int(row['ITEM_COUNT'])} items", f"{row['CREDITS_OR_QUOTA']:,.0f} credits")
        colors = ['#E8A229', '#29B5E8']
        fig = go.Figure(go.Bar(
            x=df['RISK_CATEGORY'], y=df['CREDITS_OR_QUOTA'],
            marker_color=colors[:len(df)],
            text=[f"{v:,.0f}" for v in df['CREDITS_OR_QUOTA']], textposition='outside'
        ))
        fig.update_layout(
            title='Resource Monitor Coverage Gap',
            yaxis_title='Credits / Quota',
            height=360, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_wow_cost_trend():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Week-over-Week Cost Trend:</b> Compares warehouse credit consumption from the last 7 days '
        'vs the previous 7 days. Flags spikes (>50%) and increases (>25%).</div>',
        unsafe_allow_html=True)
    try:
        query = """
        WITH weekly_data AS (
            SELECT
                warehouse_name,
                SUM(CASE WHEN start_time >= DATEADD('day', -7, CURRENT_DATE) THEN credits_used ELSE 0 END) AS current_credits,
                SUM(CASE WHEN start_time >= DATEADD('day', -14, CURRENT_DATE) AND start_time < DATEADD('day', -7, CURRENT_DATE)
                         THEN credits_used ELSE 0 END) AS previous_credits
            FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
            WHERE start_time >= DATEADD('day', -14, CURRENT_DATE)
            GROUP BY warehouse_name
        )
        SELECT
            warehouse_name,
            ROUND(previous_credits, 2) AS previous_week_credits,
            ROUND(current_credits, 2) AS current_week_credits,
            ROUND(current_credits - previous_credits, 2) AS credit_change,
            ROUND((current_credits - previous_credits) / NULLIF(previous_credits, 0) * 100, 2) AS percent_change,
            CASE
                WHEN (current_credits - previous_credits) / NULLIF(previous_credits, 0) > 0.5 THEN 'COST_SPIKE_GT_50PCT'
                WHEN (current_credits - previous_credits) / NULLIF(previous_credits, 0) > 0.25 THEN 'COST_INCREASE_GT_25PCT'
                ELSE 'STABLE_OR_DECREASING'
            END AS trend_status
        FROM weekly_data
        WHERE current_credits > 10 OR previous_credits > 10
        ORDER BY credit_change DESC
        """
        df = _cached_sql("fc_wow_cost_trend", query)
        if df.empty:
            st.info("Insufficient data for week-over-week trend analysis.")
            return
        for c in ['PREVIOUS_WEEK_CREDITS', 'CURRENT_WEEK_CREDITS', 'CREDIT_CHANGE', 'PERCENT_CHANGE']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        spikes = len(df[df['TREND_STATUS'] == 'COST_SPIKE_GT_50PCT'])
        increases = len(df[df['TREND_STATUS'] == 'COST_INCREASE_GT_25PCT'])
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Warehouses Tracked", len(df))
        with col2:
            st.metric("Cost Spikes (>50%)", spikes)
        with col3:
            st.metric("Cost Increases (>25%)", increases)
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Previous Week', x=df['WAREHOUSE_NAME'], y=df['PREVIOUS_WEEK_CREDITS'],
                             marker_color='#75C2D8'))
        fig.add_trace(go.Bar(name='Current Week', x=df['WAREHOUSE_NAME'], y=df['CURRENT_WEEK_CREDITS'],
                             marker_color='#29B5E8'))
        fig.update_layout(
            barmode='group',
            title='Week-over-Week Credit Comparison',
            xaxis_title='Warehouse', yaxis_title='Credits',
            height=400, margin=dict(t=50, b=80),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['WAREHOUSE_NAME', 'PREVIOUS_WEEK_CREDITS', 'CURRENT_WEEK_CREDITS', 'CREDIT_CHANGE', 'PERCENT_CHANGE', 'TREND_STATUS']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_spending_summary():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Spending Summary:</b> Compares warehouse metering and serverless task credit consumption '
        'over the last 30 days.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            'WAREHOUSE_METERING' AS service_type,
            ROUND(SUM(credits_used), 2) AS total_credits,
            COUNT(DISTINCT DATE(start_time)) AS days_with_activity,
            ROUND(AVG(credits_used), 4) AS avg_per_event,
            ROUND(MIN(credits_used), 4) AS min_per_event,
            ROUND(MAX(credits_used), 4) AS max_per_event
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
        UNION ALL
        SELECT
            'SERVERLESS_TASKS' AS service_type,
            ROUND(SUM(credits_used), 2) AS total_credits,
            COUNT(DISTINCT DATE(start_time)) AS days_with_activity,
            ROUND(AVG(credits_used), 4) AS avg_per_event,
            ROUND(MIN(credits_used), 4) AS min_per_event,
            ROUND(MAX(credits_used), 4) AS max_per_event
        FROM SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY
        WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
        ORDER BY total_credits DESC
        """
        df = _cached_sql("fc_spending_summary", query)
        if df.empty:
            st.info("No spending data available for the last 30 days.")
            return
        df['TOTAL_CREDITS'] = pd.to_numeric(df['TOTAL_CREDITS'], errors='coerce').fillna(0)
        col1, col2 = st.columns(2)
        for i, row in df.iterrows():
            target = col1 if i == 0 else col2
            with target:
                st.metric(row['SERVICE_TYPE'], f"{row['TOTAL_CREDITS']:,.1f} credits",
                          f"{int(row.get('DAYS_WITH_ACTIVITY', 0))} active days")
        colors = ['#29B5E8', '#11567F']
        fig = go.Figure(go.Bar(
            x=df['SERVICE_TYPE'], y=df['TOTAL_CREDITS'],
            marker_color=colors[:len(df)],
            text=[f"{v:,.1f}" for v in df['TOTAL_CREDITS']], textposition='outside'
        ))
        fig.update_layout(
            title='Credit Spending by Service Type (Last 30 Days)',
            yaxis_title='Credits',
            height=360, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_monthly_spending_trend():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Monthly Spending Trend:</b> 12-month warehouse credit consumption trend showing '
        'total credits and active days per month.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            DATE_TRUNC('month', start_time) AS month,
            ROUND(SUM(credits_used), 2) AS monthly_credits,
            COUNT(DISTINCT DATE(start_time)) AS days_in_month
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        GROUP BY DATE_TRUNC('month', start_time)
        ORDER BY month DESC
        LIMIT 12
        """
        df = _cached_sql("fc_monthly_trend", query)
        if df.empty:
            st.info("No monthly spending data available.")
            return
        df['MONTHLY_CREDITS'] = pd.to_numeric(df['MONTHLY_CREDITS'], errors='coerce').fillna(0)
        df = df.sort_values('MONTH')
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['MONTH'], y=df['MONTHLY_CREDITS'],
            mode='lines+markers', name='Monthly Credits',
            line=dict(color='#29B5E8', width=3),
            marker=dict(size=8, color='#11567F'),
            fill='tozeroy', fillcolor='rgba(41,181,232,0.15)'
        ))
        fig.update_layout(
            title='Monthly Credit Spending Trend',
            xaxis_title='Month', yaxis_title='Credits',
            height=380, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_serverless_costs():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Serverless Compute Costs:</b> Credit breakdown across serverless services — '
        'tasks, materialized views, auto clustering, and search optimization (last 30 days).</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT service_type, total_credits, databases_using, executions
        FROM (
            SELECT 'SERVERLESS_TASK' AS service_type,
                   ROUND(SUM(credits_used), 2) AS total_credits,
                   COUNT(DISTINCT database_name) AS databases_using,
                   COUNT(*) AS executions
            FROM SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
            UNION ALL
            SELECT 'MATERIALIZED_VIEWS', ROUND(SUM(credits_used), 2),
                   COUNT(DISTINCT database_name), COUNT(*)
            FROM SNOWFLAKE.ACCOUNT_USAGE.MATERIALIZED_VIEW_REFRESH_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
            UNION ALL
            SELECT 'AUTO_CLUSTERING', ROUND(SUM(credits_used), 2),
                   COUNT(DISTINCT database_name), COUNT(*)
            FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
            UNION ALL
            SELECT 'SEARCH_OPTIMIZATION', ROUND(SUM(credits_used), 2),
                   COUNT(DISTINCT database_name), COUNT(*)
            FROM SNOWFLAKE.ACCOUNT_USAGE.SEARCH_OPTIMIZATION_HISTORY
            WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
        ) serverless_costs
        WHERE total_credits > 0
        ORDER BY total_credits DESC
        """
        df = _cached_sql("fc_serverless_costs", query)
        if df.empty:
            st.info("No serverless compute costs detected in the last 30 days.")
            return
        df['TOTAL_CREDITS'] = pd.to_numeric(df['TOTAL_CREDITS'], errors='coerce').fillna(0)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Serverless Credits", f"{df['TOTAL_CREDITS'].sum():,.2f}")
        with col2:
            st.metric("Active Service Types", len(df))
        colors = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229']
        fig = go.Figure(go.Bar(
            x=df['SERVICE_TYPE'], y=df['TOTAL_CREDITS'],
            marker_color=colors[:len(df)],
            text=[f"{v:,.2f}" for v in df['TOTAL_CREDITS']], textposition='outside'
        ))
        fig.update_layout(
            title='Serverless Compute Credits by Service (Last 30 Days)',
            yaxis_title='Credits',
            height=380, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_storage_costs():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Storage Costs:</b> Monthly average storage consumption in TB (database + stage + fail-safe) '
        'over the last 3 months. Note: Storage is NOT covered by compute budgets.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            DATE_TRUNC('month', usage_date) AS month,
            ROUND(AVG(storage_bytes + stage_bytes + failsafe_bytes) / POWER(1024, 4), 4) AS avg_storage_tb
        FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
        WHERE usage_date >= DATEADD('month', -3, CURRENT_DATE)
        GROUP BY DATE_TRUNC('month', usage_date)
        ORDER BY month DESC
        """
        df = _cached_sql("fc_storage_costs", query)
        if df.empty:
            st.info("No storage usage data available.")
            return
        df['AVG_STORAGE_TB'] = pd.to_numeric(df['AVG_STORAGE_TB'], errors='coerce').fillna(0)
        st.metric("Avg Storage (Latest Month)", f"{df['AVG_STORAGE_TB'].iloc[0]:,.4f} TB")
        df_sorted = df.sort_values('MONTH')
        fig = go.Figure(go.Bar(
            x=[str(m)[:10] for m in df_sorted['MONTH']], y=df_sorted['AVG_STORAGE_TB'],
            marker_color='#29B5E8',
            text=[f"{v:,.4f}" for v in df_sorted['AVG_STORAGE_TB']], textposition='outside'
        ))
        fig.update_layout(
            title='Average Monthly Storage (TB) — Last 3 Months',
            xaxis_title='Month', yaxis_title='TB',
            height=360, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(
            '<div style="background-color:#fff3cd;border-left:6px solid #F39C12;padding:10px;">'
            '⚠️&nbsp;&nbsp;Storage is <b>NOT covered</b> by compute budgets.</div>',
            unsafe_allow_html=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_spcs_credits():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>SPCS Credits:</b> Snowpark Container Services total credit consumption over the last 30 days.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            'SPCS Services' AS service_name,
            ROUND(SUM(credits_used), 2) AS total_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPARK_CONTAINER_SERVICES_HISTORY
        WHERE start_time >= DATEADD('day', -30, CURRENT_DATE)
        """
        df = _cached_sql("fc_spcs_credits", query)
        if df.empty or df['TOTAL_CREDITS'].iloc[0] is None:
            st.info("No Snowpark Container Services credits detected in the last 30 days.")
            return
        total = pd.to_numeric(df['TOTAL_CREDITS'].iloc[0], errors='coerce')
        if pd.isna(total) or total == 0:
            st.info("No Snowpark Container Services credits detected in the last 30 days.")
            return
        st.metric("SPCS Credits (30 Days)", f"{total:,.2f}")
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=float(total),
            title={'text': "SPCS Credits (30 Days)"},
            gauge={
                'axis': {'range': [0, max(float(total) * 1.5, 10)]},
                'bar': {'color': '#29B5E8'},
                'steps': [
                    {'range': [0, float(total) * 0.5], 'color': '#CAF0F8'},
                    {'range': [float(total) * 0.5, float(total)], 'color': '#90E0EF'}
                ]
            }
        ))
        fig.update_layout(height=300, margin=dict(t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_dangling_budgets():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Dangling Custom Budgets:</b> Custom budgets (non-root) that may not be attached to any resources. '
        'Use <code>&lt;budget&gt;!GET_LINKED_RESOURCES()</code> to verify.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        WITH all_budgets AS (
            SELECT
                name AS budget_name,
                database_name,
                schema_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.CLASS_INSTANCES
            WHERE class_name = 'BUDGET'
              AND deleted IS NULL
              AND name != 'ACCOUNT_ROOT_BUDGET'
        )
        SELECT
            COUNT(*) AS custom_budget_count,
            LISTAGG(budget_name, ', ') WITHIN GROUP (ORDER BY budget_name) AS budget_names
        FROM all_budgets
        """
        df = _cached_sql("fc_dangling_budgets", query)
        if df.empty:
            st.info("No custom budgets found.")
            return
        count = int(pd.to_numeric(df['CUSTOM_BUDGET_COUNT'].iloc[0], errors='coerce') or 0)
        if count == 0:
            st.success("No custom budgets found — only ACCOUNT_ROOT_BUDGET is configured.")
            return
        st.metric("Custom Budgets (Potential Dangling)", count)
        names = df['BUDGET_NAMES'].iloc[0]
        if names:
            st.markdown(f"**Budget Names:** {names}")
        st.markdown(
            '<div style="background-color:#fff3cd;border-left:6px solid #F39C12;padding:10px;">'
            '⚠️&nbsp;&nbsp;Use <code>&lt;budget&gt;!GET_LINKED_RESOURCES()</code> on each budget above to verify '
            'it is attached to resources. Unattached budgets may indicate stale configurations.</div>',
            unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

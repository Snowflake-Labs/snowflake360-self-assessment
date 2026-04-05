"""
Network Rules & Policies Component

Provides network security analysis including network policies audit
and network rules audit.
"""

import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import plotly.graph_objects as go


def comp_network_policies(entry_actions=None):
    """
    Network Rules & Policies Component

    Provides expanders for:
    - Network Rules & Policies Overview
    - Network Rules & Policies Analyzer
    - Network Policies Audit (Enforced vs. Dangling)
    - Network Rules Audit (Attached vs. Unused)

    Args:
        entry_actions: Optional callback actions on component entry
    """
    try:
        st.markdown("### Network Rules & Policies")

        with st.expander("Network Policies Audit (Enforced vs. Dangling)", expanded=True):
            _render_network_policies_audit()

        with st.expander("Network Rules Audit (Attached vs. Unused)", expanded=True):
            _render_network_rules_audit()

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Network Rules & Policies: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_network_policies_audit():
    """Render the Network Policies Audit section with table and charts."""

    st.markdown("#### Network Policies Audit (Enforced vs. Dangling)")

    st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                'ℹ️&nbsp;&nbsp;<b>Network Policy Inventory:</b> This section displays network policy inventory showing policy names, '
                'enforcement status (account/user/integration level or dangling), comments, user attachments, and creation dates. '
                'Policies not attached to any account, user, or integration are marked as "Dangling" and may represent security gaps or unused configurations.'
                '</div>', unsafe_allow_html=True)

    try:
        network_policies_query = """
        SELECT
            np.name AS "Policy Name",
            CASE
                WHEN pu.applied_to_account > 0 THEN '🔒 Enforced (Account Level)'
                WHEN pu.applied_to_users > 0 THEN '👤 Enforced (User Level)'
                WHEN pu.applied_to_integrations > 0 THEN '🔌 Enforced (Integration)'
                ELSE '⚠️ Dangling (Not Enforced)'
            END AS "Status",
            np.comment AS "Comment",
            COALESCE(pu.applied_to_users, 0) AS "User Attachments",
            np.created AS "Created Date"
        FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES np
        LEFT JOIN (
            SELECT policy_name,
                COUNT(CASE WHEN ref_entity_domain = 'ACCOUNT' THEN 1 END) AS applied_to_account,
                COUNT(CASE WHEN ref_entity_domain = 'USER' THEN 1 END) AS applied_to_users,
                COUNT(CASE WHEN ref_entity_domain = 'INTEGRATION' THEN 1 END) AS applied_to_integrations
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE policy_kind = 'NETWORK_POLICY'
            GROUP BY 1
        ) pu ON np.name = pu.policy_name
        WHERE np.deleted IS NULL
        ORDER BY "Status" DESC
        """

        network_policies_df = st.session_state.session.sql(network_policies_query).to_pandas()

        if not network_policies_df.empty:
            st.dataframe(
                network_policies_df,
                use_container_width=True
            )

            st.markdown("---")
            st.markdown("##### Network Policies Analysis Charts")

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container(border=True):
                st.markdown("##### Policy Status Distribution")
                _render_policy_status_chart(network_policies_df, key_prefix="np_status_")

            with chart_col2.container(border=True):
                st.markdown("##### User Attachments by Policy")
                _render_user_attachments_chart(network_policies_df, key_prefix="np_users_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No network policies data found for the current account and execution.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Network Policies Audit: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure network policies data is available.'
                    '</div>', unsafe_allow_html=True)


def _render_policy_status_chart(df, key_prefix=""):
    """Render policy status distribution chart with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    status_counts = df.groupby('Status').size().reset_index(name='Count')

    if status_counts.empty:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No status data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_status_bar_chart(status_counts, key_prefix)
    elif chart_type == "Pie Chart":
        _render_status_standard_pie_chart(status_counts, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_status_donut_pie_chart(status_counts, key_prefix)
    else:
        _render_status_rose_pie_chart(status_counts, key_prefix)


def _render_status_bar_chart(status_counts, key_prefix=""):
    """Render status distribution bar chart using ECharts."""

    categories = status_counts['Status'].tolist()
    values = status_counts['Count'].tolist()

    colors = ['#2ca02c' if '🔒' in cat else '#1f77b4' if '👤' in cat else '#9467bd' if '🔌' in cat else '#d62728' for cat in categories]

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "formatter": "{b}: {c} policies"
        },
        "xAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {
                "rotate": 25,
                "fontSize": 9,
                "interval": 0
            }
        },
        "yAxis": {
            "type": "value",
            "name": "Number of Policies",
            "nameTextStyle": {"fontSize": 11}
        },
        "series": [
            {
                "name": "Policy Count",
                "type": "bar",
                "data": [{"value": v, "itemStyle": {"color": c}} for v, c in zip(values, colors)],
                "label": {
                    "show": True,
                    "position": "top",
                    "fontSize": 10
                }
            }
        ],
        "grid": {
            "left": "15%",
            "right": "10%",
            "bottom": "25%",
            "top": "15%"
        }
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}bar_chart")


def _render_status_standard_pie_chart(status_counts, key_prefix=""):
    """Render status distribution standard pie chart using ECharts."""

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Status']} ({row['Count']})"}
        for _, row in status_counts.iterrows()
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
            "formatter": "{b}: {c} policies ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#1f77b4", "#9467bd", "#d62728"],
        "series": [
            {
                "name": "Policy Count",
                "type": "pie",
                "radius": ["0%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_status_donut_pie_chart(status_counts, key_prefix=""):
    """Render status distribution donut pie chart using ECharts."""

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Status']} ({row['Count']})"}
        for _, row in status_counts.iterrows()
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
            "formatter": "{b}: {c} policies ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#1f77b4", "#9467bd", "#d62728"],
        "series": [
            {
                "name": "Policy Count",
                "type": "pie",
                "radius": ["30%", "55%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_status_rose_pie_chart(status_counts, key_prefix=""):
    """Render status distribution rose-type pie chart using ECharts."""

    chart_data = [
        {"value": int(row['Count']), "name": f"{row['Status']} ({row['Count']})"}
        for _, row in status_counts.iterrows()
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
            "formatter": "{b}: {c} policies ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "color": ["#2ca02c", "#1f77b4", "#9467bd", "#d62728"],
        "series": [
            {
                "name": "Policy Count",
                "type": "pie",
                "radius": [15, 90],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


def _render_user_attachments_chart(df, key_prefix=""):
    """Render user attachments by policy chart with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    user_attach_df = df[['Policy Name', 'User Attachments']].copy()
    user_attach_df = user_attach_df.sort_values('User Attachments', ascending=False)

    if user_attach_df.empty or user_attach_df['User Attachments'].sum() == 0:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No user attachment data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_user_attach_bar_chart(user_attach_df, key_prefix)
    elif chart_type == "Pie Chart":
        _render_user_attach_standard_pie_chart(user_attach_df, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_user_attach_donut_pie_chart(user_attach_df, key_prefix)
    else:
        _render_user_attach_rose_pie_chart(user_attach_df, key_prefix)


def _render_user_attach_bar_chart(df, key_prefix=""):
    """Render user attachments bar chart using ECharts."""

    df_sorted = df.sort_values('User Attachments', ascending=True)

    categories = df_sorted['Policy Name'].tolist()
    values = df_sorted['User Attachments'].tolist()

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "formatter": "{b}: {c} users attached"
        },
        "xAxis": {
            "type": "value",
            "name": "User Attachments",
            "nameTextStyle": {"fontSize": 11}
        },
        "yAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {
                "fontSize": 9,
                "width": 100,
                "overflow": "truncate"
            }
        },
        "series": [
            {
                "name": "User Attachments",
                "type": "bar",
                "data": values,
                "itemStyle": {"color": "#1f77b4"},
                "label": {
                    "show": True,
                    "position": "right",
                    "fontSize": 10
                }
            }
        ],
        "grid": {
            "left": "25%",
            "right": "15%",
            "bottom": "10%",
            "top": "10%"
        }
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}bar_chart")


def _render_user_attach_standard_pie_chart(df, key_prefix=""):
    """Render user attachments standard pie chart using ECharts."""

    df_filtered = df[df['User Attachments'] > 0]

    if df_filtered.empty:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No policies with user attachments'
                    '</div>', unsafe_allow_html=True)
        return

    chart_data = [
        {"value": int(row['User Attachments']), "name": f"{row['Policy Name']} ({row['User Attachments']})"}
        for _, row in df_filtered.iterrows()
    ]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "itemWidth": 12, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} users ({d}%)"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "series": [{"name": "User Attachments", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_user_attach_donut_pie_chart(df, key_prefix=""):
    """Render user attachments donut pie chart using ECharts."""

    df_filtered = df[df['User Attachments'] > 0]

    if df_filtered.empty:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No policies with user attachments'
                    '</div>', unsafe_allow_html=True)
        return

    chart_data = [
        {"value": int(row['User Attachments']), "name": f"{row['Policy Name']} ({row['User Attachments']})"}
        for _, row in df_filtered.iterrows()
    ]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "itemWidth": 12, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} users ({d}%)"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "series": [{"name": "User Attachments", "type": "pie", "radius": ["30%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_user_attach_rose_pie_chart(df, key_prefix=""):
    """Render user attachments rose-type pie chart using ECharts."""

    df_filtered = df[df['User Attachments'] > 0]

    if df_filtered.empty:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No policies with user attachments'
                    '</div>', unsafe_allow_html=True)
        return

    chart_data = [
        {"value": int(row['User Attachments']), "name": f"{row['Policy Name']} ({row['User Attachments']})"}
        for _, row in df_filtered.iterrows()
    ]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "itemWidth": 12, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} users ({d}%)"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "series": [{"name": "User Attachments", "type": "pie", "radius": [15, 90], "center": ["50%", "40%"], "roseType": "area", "itemStyle": {"borderRadius": 8}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


# ============================================================================
# NETWORK RULES AUDIT SECTION
# ============================================================================

def _render_network_rules_audit():
    """Render the Network Rules Audit section with table and charts."""

    st.markdown("#### Network Rules Audit (Attached vs. Unused)")

    st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                'ℹ️&nbsp;&nbsp;<b>Network Rules Inventory:</b> This section displays network rules inventory showing rule name, '
                'mode (ingress/egress), type (IPV4/host/link), usage status (attached or orphaned), reference count, owner, and comments. '
                'Rules not attached to any network policy are marked as "Unused (Orphan)" and may represent security gaps or obsolete configurations.'
                '</div>', unsafe_allow_html=True)

    try:
        network_rules_query = """
        WITH rule_usage AS (
            SELECT
                network_rule_name,
                COUNT(*) AS distinct_policies_using_rule
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULE_REFERENCES
            GROUP BY 1
        )
        SELECT
            nr.name AS "Rule Name",
            nr.mode AS "Mode (Ingress/Egress)",
            nr.type AS "Type (IPV4/Host/Link)",

            CASE
                WHEN ru.distinct_policies_using_rule > 0 THEN '✅ Attached'
                ELSE '⚠️ Unused (Orphan)'
            END AS "Usage Status",

            COALESCE(ru.distinct_policies_using_rule, 0) AS "Reference Count",
            nr.owner AS "Owned By",
            nr.comment AS "Comment"

        FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES nr
        LEFT JOIN rule_usage ru ON nr.name = ru.network_rule_name
        WHERE nr.deleted IS NULL
        ORDER BY "Usage Status" ASC
        """

        network_rules_df = st.session_state.session.sql(network_rules_query).to_pandas()

        if not network_rules_df.empty:
            st.dataframe(
                network_rules_df,
                use_container_width=True
            )

            st.markdown("---")
            st.markdown("##### Network Rules Analysis Charts")

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1.container(border=True):
                st.markdown("##### Rule Usage Status Distribution")
                _render_rule_usage_status_chart(network_rules_df, key_prefix="nr_status_")

            with chart_col2.container(border=True):
                st.markdown("##### Rules by Mode (Ingress/Egress)")
                _render_rule_mode_chart(network_rules_df, key_prefix="nr_mode_")

        else:
            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        '⚠️&nbsp;&nbsp;No network rules data found for the current account and execution.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Network Rules Audit: {str(e)}'
                    f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure network rules data is available.'
                    '</div>', unsafe_allow_html=True)


def _render_rule_usage_status_chart(df, key_prefix=""):
    """Render rule usage status distribution chart with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    status_counts = df.groupby('Usage Status').size().reset_index(name='Count')

    if status_counts.empty:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No usage status data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_rule_status_bar_chart(status_counts, key_prefix)
    elif chart_type == "Pie Chart":
        _render_rule_status_standard_pie_chart(status_counts, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_rule_status_donut_pie_chart(status_counts, key_prefix)
    else:
        _render_rule_status_rose_pie_chart(status_counts, key_prefix)


def _render_rule_status_bar_chart(status_counts, key_prefix=""):
    """Render rule usage status bar chart using ECharts."""

    categories = status_counts['Usage Status'].tolist()
    values = status_counts['Count'].tolist()
    colors = ['#2ca02c' if '✅' in cat else '#d62728' for cat in categories]

    option = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "formatter": "{b}: {c} rules"},
        "xAxis": {"type": "category", "data": categories, "axisLabel": {"rotate": 0, "fontSize": 10, "interval": 0}},
        "yAxis": {"type": "value", "name": "Number of Rules", "nameTextStyle": {"fontSize": 11}},
        "series": [{"name": "Rule Count", "type": "bar", "data": [{"value": v, "itemStyle": {"color": c}} for v, c in zip(values, colors)], "label": {"show": True, "position": "top", "fontSize": 10}}],
        "grid": {"left": "15%", "right": "10%", "bottom": "15%", "top": "15%"}
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}bar_chart")


def _render_rule_status_standard_pie_chart(status_counts, key_prefix=""):
    """Render rule usage status standard pie chart using ECharts."""

    chart_data = [{"value": int(row['Count']), "name": f"{row['Usage Status']} ({row['Count']})"} for _, row in status_counts.iterrows()]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "itemWidth": 12, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} rules ({d}%)"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#2ca02c", "#d62728"],
        "series": [{"name": "Rule Count", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_rule_status_donut_pie_chart(status_counts, key_prefix=""):
    """Render rule usage status donut pie chart using ECharts."""

    chart_data = [{"value": int(row['Count']), "name": f"{row['Usage Status']} ({row['Count']})"} for _, row in status_counts.iterrows()]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "itemWidth": 12, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} rules ({d}%)"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#2ca02c", "#d62728"],
        "series": [{"name": "Rule Count", "type": "pie", "radius": ["30%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_rule_status_rose_pie_chart(status_counts, key_prefix=""):
    """Render rule usage status rose-type pie chart using ECharts."""

    chart_data = [{"value": int(row['Count']), "name": f"{row['Usage Status']} ({row['Count']})"} for _, row in status_counts.iterrows()]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "itemWidth": 12, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} rules ({d}%)"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#2ca02c", "#d62728"],
        "series": [{"name": "Rule Count", "type": "pie", "radius": [15, 90], "center": ["50%", "40%"], "roseType": "area", "itemStyle": {"borderRadius": 8}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")


def _render_rule_mode_chart(df, key_prefix=""):
    """Render rules by mode (Ingress/Egress) chart with selectable chart types."""

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key=f"{key_prefix}chart_type"
    )

    mode_counts = df.groupby('Mode (Ingress/Egress)').size().reset_index(name='Count')

    if mode_counts.empty:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No mode data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    if chart_type == "Bar Chart":
        _render_rule_mode_bar_chart(mode_counts, key_prefix)
    elif chart_type == "Pie Chart":
        _render_rule_mode_standard_pie_chart(mode_counts, key_prefix)
    elif chart_type == "Pie - Donut":
        _render_rule_mode_donut_pie_chart(mode_counts, key_prefix)
    else:
        _render_rule_mode_rose_pie_chart(mode_counts, key_prefix)


def _render_rule_mode_bar_chart(mode_counts, key_prefix=""):
    """Render rules by mode bar chart using ECharts."""

    categories = mode_counts['Mode (Ingress/Egress)'].tolist()
    values = mode_counts['Count'].tolist()
    colors = ['#1f77b4' if 'INGRESS' in str(cat).upper() else '#ff7f0e' for cat in categories]

    option = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}, "formatter": "{b}: {c} rules"},
        "xAxis": {"type": "category", "data": categories, "axisLabel": {"rotate": 0, "fontSize": 10, "interval": 0}},
        "yAxis": {"type": "value", "name": "Number of Rules", "nameTextStyle": {"fontSize": 11}},
        "series": [{"name": "Rule Count", "type": "bar", "data": [{"value": v, "itemStyle": {"color": c}} for v, c in zip(values, colors)], "label": {"show": True, "position": "top", "fontSize": 10}}],
        "grid": {"left": "15%", "right": "10%", "bottom": "15%", "top": "15%"}
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}bar_chart")


def _render_rule_mode_standard_pie_chart(mode_counts, key_prefix=""):
    """Render rules by mode standard pie chart using ECharts."""

    chart_data = [{"value": int(row['Count']), "name": f"{row['Mode (Ingress/Egress)']} ({row['Count']})"} for _, row in mode_counts.iterrows()]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "itemWidth": 12, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} rules ({d}%)"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
        "series": [{"name": "Rule Count", "type": "pie", "radius": ["0%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}pie_chart")


def _render_rule_mode_donut_pie_chart(mode_counts, key_prefix=""):
    """Render rules by mode donut pie chart using ECharts."""

    chart_data = [{"value": int(row['Count']), "name": f"{row['Mode (Ingress/Egress)']} ({row['Count']})"} for _, row in mode_counts.iterrows()]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "itemWidth": 12, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} rules ({d}%)"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
        "series": [{"name": "Rule Count", "type": "pie", "radius": ["30%", "55%"], "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}donut_chart")


def _render_rule_mode_rose_pie_chart(mode_counts, key_prefix=""):
    """Render rules by mode rose-type pie chart using ECharts."""

    chart_data = [{"value": int(row['Count']), "name": f"{row['Mode (Ingress/Egress)']} ({row['Count']})"} for _, row in mode_counts.iterrows()]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "itemWidth": 12, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} rules ({d}%)"},
        "toolbox": {"show": True, "feature": {"dataView": {"show": True, "readOnly": False}, "restore": {"show": True}, "saveAsImage": {"show": True}}},
        "color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
        "series": [{"name": "Rule Count", "type": "pie", "radius": [15, 90], "center": ["50%", "40%"], "roseType": "area", "itemStyle": {"borderRadius": 8}, "data": chart_data}],
    }

    st_echarts(options=option, height="350px", key=f"{key_prefix}rose_chart")

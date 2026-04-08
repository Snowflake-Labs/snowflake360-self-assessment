"""
Authorization Component

Provides authorization analysis including role hygiene, user inventory,
security hygiene, and object ownership.
"""

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


def comp_authorization(entry_actions=None):
    """
    Authorization Component

    Provides expanders for:
    - Authorization Overview
    - Authorization Analyzer
    - Role Hygiene & Hierarchy
    - User Inventory & Averages
    - Security Hygiene ("Unhealthy" Users)
    - Object Ownership (Admin Hoarding)

    Args:
        entry_actions: Optional callback actions on component entry
    """
    try:
        st.markdown("### Authorization")

        # Expander 2: Role Hygiene & Hierarchy
        with st.expander("Role Hygiene & Hierarchy", expanded=True):
            _render_role_hygiene_hierarchy()

        # Expander 4: User Inventory & Averages
        with st.expander("User Inventory & Averages", expanded=True):
            _render_user_inventory_averages()

        # Expander 5: Security Hygiene ("Unhealthy" Users)
        with st.expander("Security Hygiene (\"Unhealthy\" Users)", expanded=True):
            _render_security_hygiene()

        # Expander 6: Object Ownership (Admin Hoarding)
        with st.expander("Object Ownership (Admin Hoarding)", expanded=True):
            _render_object_ownership()

        with st.expander("Privileged Access Summary", expanded=True):
            _render_privileged_access()

        with st.expander("Role Grant Distribution", expanded=True):
            _render_role_grant_distribution()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Authorization: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_role_hygiene_hierarchy():
    """Render the Role Hygiene & Hierarchy section with table and charts."""

    st.markdown("#### Role Hygiene & Hierarchy")

    # Introduction
    st.markdown("""
    Role hygiene analysis identifying custom roles, orphaned roles (no parent), hermit roles (no parent or child),
    and active vs inactive roles based on 60-day query history.
    """)

    try:
        role_hygiene_query = """
        WITH system_roles AS (
            SELECT 'ACCOUNTADMIN' AS name UNION ALL SELECT 'SYSADMIN' UNION ALL
            SELECT 'SECURITYADMIN' UNION ALL SELECT 'USERADMIN' UNION ALL SELECT 'PUBLIC'
        ),
        role_hierarchy AS (
            SELECT
                name AS child_role,
                grantee_name AS parent_role
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
            WHERE deleted_on IS NULL
              AND privilege = 'USAGE'
              AND granted_on = 'ROLE'
        ),
        role_activity AS (
            SELECT DISTINCT role_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE start_time >= DATEADD('day', -60, CURRENT_TIMESTAMP())
        )

        SELECT
            COUNT(DISTINCT r.name) AS total_roles,
            COUNT(DISTINCT CASE WHEN sr.name IS NULL THEN r.name END) AS custom_roles,

            COUNT(DISTINCT CASE
                WHEN rh_parent.parent_role IS NULL
                     AND r.name NOT IN ('ACCOUNTADMIN')
                THEN r.name
            END) AS orphan_roles,

            COUNT(DISTINCT CASE
                WHEN rh_parent.parent_role IS NULL
                     AND rh_child.child_role IS NULL
                     AND r.name NOT IN ('ACCOUNTADMIN', 'PUBLIC')
                THEN r.name
            END) AS hermit_roles,

            COUNT(DISTINCT a.role_name) AS active_roles_60d,
            COUNT(DISTINCT r.name) - COUNT(DISTINCT a.role_name) AS inactive_roles

        FROM SNOWFLAKE.ACCOUNT_USAGE.ROLES r
        LEFT JOIN system_roles sr ON r.name = sr.name
        LEFT JOIN role_hierarchy rh_parent ON r.name = rh_parent.child_role
        LEFT JOIN role_hierarchy rh_child ON r.name = rh_child.parent_role
        LEFT JOIN role_activity a ON r.name = a.role_name
        WHERE r.deleted_on IS NULL
        """

        role_hygiene_df = _cached_sql("auth_role_hygiene", role_hygiene_query)

        if not role_hygiene_df.empty:
            st.dataframe(
                role_hygiene_df,
                use_container_width=True
            )

            # Extract values for charts
            row = role_hygiene_df.iloc[0]
            total_roles = int(row['TOTAL_ROLES'])
            custom_roles = int(row['CUSTOM_ROLES'])
            orphan_roles = int(row['ORPHAN_ROLES'])
            hermit_roles = int(row['HERMIT_ROLES'])
            active_roles = int(row['ACTIVE_ROLES_60D'])
            inactive_roles = int(row['INACTIVE_ROLES'])
            system_roles = total_roles - custom_roles

            # Create charts section
            st.markdown("---")
            st.markdown("##### Role Hygiene Analysis Charts")

            # Two charts per row
            chart_col1, chart_col2 = st.columns(2)

            # Chart 1: Role Type Distribution (Custom vs System)
            with chart_col1.container():
                st.markdown("##### Role Type Distribution")
                _render_role_type_chart(custom_roles, system_roles, key_prefix="role_type_")

            # Chart 2: Role Activity Status (Active vs Inactive)
            with chart_col2.container():
                st.markdown("##### Role Activity Status (60 Days)")
                _render_role_activity_chart(active_roles, inactive_roles, key_prefix="role_activity_")

            # Second row of charts
            chart_col3, chart_col4 = st.columns(2)

            # Chart 3: Role Hierarchy Health (Orphan & Hermit Roles)
            with chart_col3.container():
                st.markdown("##### Role Hierarchy Health")
                _render_role_hierarchy_health_chart(total_roles, orphan_roles, hermit_roles, key_prefix="role_hierarchy_")

            # Chart 4: Overall Role Hygiene Summary
            with chart_col4.container():
                st.markdown("##### Overall Role Hygiene Summary")
                _render_role_hygiene_summary_chart(total_roles, custom_roles, orphan_roles, hermit_roles, active_roles, inactive_roles, key_prefix="role_summary_")

        else:
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No role hygiene data available for the current execution context.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading role hygiene data: {str(e)}'
                    f'</div>', unsafe_allow_html=True)



def _render_role_type_chart(custom_roles, system_roles, key_prefix=""):
    """Render role type distribution chart with selectable chart types."""

    role_types = ['Custom Roles', 'System Roles']
    role_counts = [custom_roles, system_roles]
    _render_role_type_bar_chart(role_types, role_counts, key_prefix)


def _render_role_type_bar_chart(role_types, role_counts, key_prefix):
    """Render role type bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=role_types,
            y=role_counts,
            marker_color=['#29B5E8', '#0077B6'],
            text=role_counts,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Role Type',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_privileged_access():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Privileged Access Summary:</b> Users with elevated roles '
        '(ACCOUNTADMIN, SECURITYADMIN, SYSADMIN, USERADMIN) and their risk profile.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        WITH privileged_users AS (
            SELECT DISTINCT
                gu.grantee_name AS user_name,
                gu.role AS privileged_role
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS gu
            WHERE gu.role IN ('ACCOUNTADMIN', 'SECURITYADMIN', 'SYSADMIN', 'USERADMIN')
              AND gu.deleted_on IS NULL
        ),
        user_details AS (
            SELECT name, type, default_role, last_success_login,
                   has_password, ext_authn_duo, has_rsa_public_key
            FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
            WHERE deleted_on IS NULL
        )
        SELECT
            pu.user_name, pu.privileged_role,
            ud.type AS user_type, ud.default_role, ud.last_success_login,
            DATEDIFF('day', ud.last_success_login, CURRENT_TIMESTAMP()) AS days_since_login,
            CASE
                WHEN ud.default_role = 'ACCOUNTADMIN' THEN 'CRITICAL'
                WHEN ud.has_password = 'true' AND COALESCE(ud.ext_authn_duo, 'false') = 'false' THEN 'HIGH'
                WHEN DATEDIFF('day', ud.last_success_login, CURRENT_TIMESTAMP()) > 90 THEN 'MODERATE'
                ELSE 'LOW'
            END AS risk_level
        FROM privileged_users pu
        INNER JOIN user_details ud ON pu.user_name = ud.name
        ORDER BY
            CASE pu.privileged_role
                WHEN 'ACCOUNTADMIN' THEN 1 WHEN 'SECURITYADMIN' THEN 2
                WHEN 'SYSADMIN' THEN 3 ELSE 4
            END, risk_level DESC
        """
        df = _cached_sql("ac_privileged_access", query)
        if df.empty:
            st.info("No privileged users found.")
            return
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Privileged Users", df['USER_NAME'].nunique())
        with col2:
            st.metric("ACCOUNTADMIN Users", len(df[df['PRIVILEGED_ROLE'] == 'ACCOUNTADMIN']))
        with col3:
            high_risk = len(df[df['RISK_LEVEL'].isin(['CRITICAL', 'HIGH'])])
            st.metric("High/Critical Risk", high_risk)
        role_counts = df.groupby('PRIVILEGED_ROLE').size().reset_index(name='COUNT').sort_values('COUNT', ascending=False)
        colors = ['#E8A229', '#29B5E8', '#11567F', '#75C2D8']
        fig = go.Figure(go.Bar(
            x=role_counts['PRIVILEGED_ROLE'], y=role_counts['COUNT'],
            marker_color=colors[:len(role_counts)],
            text=role_counts['COUNT'], textposition='outside'
        ))
        fig.update_layout(title='Privileged Users by Role', yaxis_title='Users', height=360, margin=dict(t=50, b=60))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['USER_NAME', 'PRIVILEGED_ROLE', 'USER_TYPE', 'DEFAULT_ROLE', 'DAYS_SINCE_LOGIN', 'RISK_LEVEL']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_role_grant_distribution():
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Role Grant Distribution:</b> Roles with the most privilege grants. '
        'Roles with >100 grants may benefit from splitting into more granular roles.</div>',
        unsafe_allow_html=True)
    try:
        query = """
        SELECT
            grantee_name AS role_name,
            COUNT(*) AS total_grants,
            COUNT(DISTINCT granted_on) AS distinct_object_types,
            COUNT(CASE WHEN privilege = 'OWNERSHIP' THEN 1 END) AS ownership_grants,
            COUNT(CASE WHEN privilege IN ('ALL', 'ALL PRIVILEGES') THEN 1 END) AS all_privilege_grants,
            CASE
                WHEN COUNT(*) > 500 THEN 'VERY_HIGH'
                WHEN COUNT(*) > 100 THEN 'HIGH'
                WHEN COUNT(*) > 25 THEN 'MODERATE'
                ELSE 'LOW'
            END AS grant_concentration
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE deleted_on IS NULL
          AND grantee_name NOT IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'USERADMIN', 'PUBLIC')
        GROUP BY grantee_name
        HAVING COUNT(*) > 10
        ORDER BY total_grants DESC
        LIMIT 20
        """
        df = _cached_sql("ac_role_grant_dist", query)
        if df.empty:
            st.info("No custom roles with >10 grants found.")
            return
        for c in ['TOTAL_GRANTS', 'DISTINCT_OBJECT_TYPES', 'OWNERSHIP_GRANTS', 'ALL_PRIVILEGE_GRANTS']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        conc_colors = {'VERY_HIGH': '#E8A229', 'HIGH': '#11567F', 'MODERATE': '#75C2D8', 'LOW': '#29B5E8'}
        bar_colors = [conc_colors.get(c, '#29B5E8') for c in df['GRANT_CONCENTRATION']]
        fig = go.Figure(go.Bar(
            y=df['ROLE_NAME'], x=df['TOTAL_GRANTS'], orientation='h',
            marker_color=bar_colors,
            text=df['TOTAL_GRANTS'].astype(int), textposition='outside'
        ))
        fig.update_layout(
            title='Top 20 Roles by Grant Count',
            xaxis_title='Total Grants', yaxis_title='Role',
            height=max(300, len(df) * 30 + 80), margin=dict(t=50, l=200, r=40, b=60)
        )
        fig.update_yaxes(autorange='reversed')
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['ROLE_NAME', 'TOTAL_GRANTS', 'DISTINCT_OBJECT_TYPES', 'OWNERSHIP_GRANTS', 'ALL_PRIVILEGE_GRANTS', 'GRANT_CONCENTRATION']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_role_type_pie_chart(role_types, role_counts, key_prefix, donut=False):
    """Render role type pie chart using ECharts."""
    chart_data = [
        {"value": role_counts[i], "name": f"{role_types[i]} ({role_counts[i]})"}
        for i in range(len(role_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Role Type",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#29B5E8', '#0077B6']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_role_type_rose_chart(role_types, role_counts, key_prefix):
    """Render role type rose chart using ECharts."""
    chart_data = [
        {"value": role_counts[i], "name": f"{role_types[i]} ({role_counts[i]})"}
        for i in range(len(role_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Role Type",
                "type": "pie",
                "radius": [15, 80],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#29B5E8', '#0077B6']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_role_activity_chart(active_roles, inactive_roles, key_prefix=""):
    """Render role activity status chart with selectable chart types."""

    activity_types = ['Active Roles', 'Inactive Roles']
    activity_counts = [active_roles, inactive_roles]
    _render_activity_bar_chart(activity_types, activity_counts, key_prefix)


def _render_activity_bar_chart(activity_types, activity_counts, key_prefix):
    """Render activity bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=activity_types,
            y=activity_counts,
            marker_color=['#75C2D8', '#E8A229'],
            text=activity_counts,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Activity Status',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_activity_pie_chart(activity_types, activity_counts, key_prefix, donut=False):
    """Render activity pie chart using ECharts."""
    chart_data = [
        {"value": activity_counts[i], "name": f"{activity_types[i]} ({activity_counts[i]})"}
        for i in range(len(activity_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Activity Status",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#75C2D8', '#E8A229']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_activity_rose_chart(activity_types, activity_counts, key_prefix):
    """Render activity rose chart using ECharts."""
    chart_data = [
        {"value": activity_counts[i], "name": f"{activity_types[i]} ({activity_counts[i]})"}
        for i in range(len(activity_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Activity Status",
                "type": "pie",
                "radius": [15, 80],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#75C2D8', '#E8A229']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_role_hierarchy_health_chart(total_roles, orphan_roles, hermit_roles, key_prefix=""):
    """Render role hierarchy health chart with selectable chart types."""

    healthy_roles = total_roles - orphan_roles  # Orphan roles includes hermit roles
    health_types = ['Healthy Roles', 'Orphan Roles', 'Hermit Roles']
    health_counts = [healthy_roles, orphan_roles - hermit_roles, hermit_roles]
    _render_hierarchy_bar_chart(health_types, health_counts, key_prefix)


def _render_hierarchy_bar_chart(health_types, health_counts, key_prefix):
    """Render hierarchy health bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=health_types,
            y=health_counts,
            marker_color=['#0077B6', '#E8A229', '#E8A229'],
            text=health_counts,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Role Hierarchy Status',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_hierarchy_pie_chart(health_types, health_counts, key_prefix, donut=False):
    """Render hierarchy health pie chart using ECharts."""
    chart_data = [
        {"value": health_counts[i], "name": f"{health_types[i]} ({health_counts[i]})"}
        for i in range(len(health_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Hierarchy Health",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#E8A229', '#E8A229']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_hierarchy_rose_chart(health_types, health_counts, key_prefix):
    """Render hierarchy health rose chart using ECharts."""
    chart_data = [
        {"value": health_counts[i], "name": f"{health_types[i]} ({health_counts[i]})"}
        for i in range(len(health_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Hierarchy Health",
                "type": "pie",
                "radius": [15, 80],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#E8A229', '#E8A229']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_role_hygiene_summary_chart(total_roles, custom_roles, orphan_roles, hermit_roles, active_roles, inactive_roles, key_prefix=""):
    """Render overall role hygiene summary chart with selectable chart types."""

    summary_types = ['Total', 'Custom', 'Orphan', 'Hermit', 'Active', 'Inactive']
    summary_counts = [total_roles, custom_roles, orphan_roles, hermit_roles, active_roles, inactive_roles]
    _render_summary_bar_chart(summary_types, summary_counts, key_prefix)


def _render_summary_bar_chart(summary_types, summary_counts, key_prefix):
    """Render summary bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=summary_types,
            y=summary_counts,
            marker_color=['#29B5E8', '#0077B6', '#E8A229', '#E8A229', '#75C2D8', '#1A7DA8'],
            text=summary_counts,
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Role Category',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_summary_pie_chart(summary_types, summary_counts, key_prefix, donut=False):
    """Render summary pie chart using ECharts."""
    # Filter out Total for pie chart as it's a sum of others
    filtered_types = summary_types[1:]  # Exclude 'Total'
    filtered_counts = summary_counts[1:]  # Exclude total count

    chart_data = [
        {"value": filtered_counts[i], "name": f"{filtered_types[i]} ({filtered_counts[i]})"}
        for i in range(len(filtered_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Role Summary",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#E8A229', '#E8A229', '#75C2D8', '#0077B6']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_summary_rose_chart(summary_types, summary_counts, key_prefix):
    """Render summary rose chart using ECharts."""
    # Filter out Total for pie chart as it's a sum of others
    filtered_types = summary_types[1:]  # Exclude 'Total'
    filtered_counts = summary_counts[1:]  # Exclude total count

    chart_data = [
        {"value": filtered_counts[i], "name": f"{filtered_types[i]} ({filtered_counts[i]})"}
        for i in range(len(filtered_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Role Summary",
                "type": "pie",
                "radius": [15, 70],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#E8A229', '#E8A229', '#75C2D8', '#0077B6']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_user_inventory_averages():
    """Render the User Inventory & Averages section with table and charts."""

    st.markdown("#### User Inventory & Averages")

    # Introduction
    st.markdown("""
    User inventory analysis showing total users, person vs service account breakdown, 60-day activity status,
    and average roles per user and users per role.
    """)

    try:
        user_inventory_query = """
        WITH user_grants AS (
            SELECT grantee_name AS user_name, COUNT(*) AS role_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
            WHERE deleted_on IS NULL
            GROUP BY 1
        ),
        role_grants AS (
            SELECT role AS role_name, COUNT(*) AS user_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
            WHERE deleted_on IS NULL
            GROUP BY 1
        )
        SELECT
            COUNT(*) AS total_users,
            COUNT(CASE WHEN type = 'PERSON' OR type IS NULL THEN 1 END) AS type_person_count,
            COUNT(CASE WHEN type = 'SERVICE' OR type = 'LEGACY_SERVICE' THEN 1 END) AS type_service_count,
            COUNT(CASE WHEN last_success_login > DATEADD('day', -60, CURRENT_TIMESTAMP()) THEN 1 END) AS active_users_60d,
            COUNT(CASE WHEN last_success_login <= DATEADD('day', -60, CURRENT_TIMESTAMP()) OR last_success_login IS NULL THEN 1 END) AS inactive_users,
            ROUND(AVG(ug.role_count), 1) AS avg_roles_per_user,
            (SELECT ROUND(AVG(user_count), 1) FROM role_grants) AS avg_users_per_role
        FROM SNOWFLAKE.ACCOUNT_USAGE.USERS u
        LEFT JOIN user_grants ug ON u.name = ug.user_name
        WHERE u.deleted_on IS NULL
        """

        user_inventory_df = _cached_sql("auth_user_inventory", user_inventory_query)

        if not user_inventory_df.empty:
            st.dataframe(
                user_inventory_df,
                use_container_width=True
            )

            # Extract values for charts
            row = user_inventory_df.iloc[0]
            total_users = int(row['TOTAL_USERS'])
            type_person_count = int(row['TYPE_PERSON_COUNT'])
            type_service_count = int(row['TYPE_SERVICE_COUNT'])
            active_users_60d = int(row['ACTIVE_USERS_60D'])
            inactive_users = int(row['INACTIVE_USERS'])
            avg_roles_per_user = float(row['AVG_ROLES_PER_USER']) if row['AVG_ROLES_PER_USER'] is not None else 0.0
            avg_users_per_role = float(row['AVG_USERS_PER_ROLE']) if row['AVG_USERS_PER_ROLE'] is not None else 0.0

            # Create charts section
            st.markdown("---")
            st.markdown("##### User Inventory Analysis Charts")

            # Two charts per row
            chart_col1, chart_col2 = st.columns(2)

            # Chart 1: User Type Distribution (Person vs Service)
            with chart_col1.container():
                st.markdown("##### User Type Distribution")
                _render_user_type_chart(type_person_count, type_service_count, key_prefix="user_type_")

            # Chart 2: User Activity Status (Active vs Inactive)
            with chart_col2.container():
                st.markdown("##### User Activity Status (60 Days)")
                _render_user_activity_chart(active_users_60d, inactive_users, key_prefix="user_activity_")

            # Second row of charts
            chart_col3, chart_col4 = st.columns(2)

            # Chart 3: Average Roles per User vs Users per Role
            with chart_col3.container():
                st.markdown("##### Role Assignment Averages")
                _render_user_averages_chart(avg_roles_per_user, avg_users_per_role, key_prefix="user_averages_")

            # Chart 4: Overall User Inventory Summary
            with chart_col4.container():
                st.markdown("##### Overall User Inventory Summary")
                _render_user_inventory_summary_chart(total_users, type_person_count, type_service_count, active_users_60d, inactive_users, key_prefix="user_summary_")

        else:
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No user inventory data available for the current execution context.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading user inventory data: {str(e)}'
                    f'</div>', unsafe_allow_html=True)



def _render_user_type_chart(person_count, service_count, key_prefix=""):
    """Render user type distribution chart with selectable chart types."""

    user_types = ['Person Accounts', 'Service Accounts']
    user_counts = [person_count, service_count]
    _render_user_type_bar_chart(user_types, user_counts, key_prefix)


def _render_user_type_bar_chart(user_types, user_counts, key_prefix):
    """Render user type bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=user_types,
            y=user_counts,
            marker_color=['#29B5E8', '#E8A229'],
            text=user_counts,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='User Type',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_user_type_pie_chart(user_types, user_counts, key_prefix, donut=False):
    """Render user type pie chart using ECharts."""
    chart_data = [
        {"value": user_counts[i], "name": f"{user_types[i]} ({user_counts[i]})"}
        for i in range(len(user_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "User Type",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#29B5E8', '#E8A229']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_user_type_rose_chart(user_types, user_counts, key_prefix):
    """Render user type rose chart using ECharts."""
    chart_data = [
        {"value": user_counts[i], "name": f"{user_types[i]} ({user_counts[i]})"}
        for i in range(len(user_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "User Type",
                "type": "pie",
                "radius": [15, 80],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#29B5E8', '#E8A229']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_user_activity_chart(active_users, inactive_users, key_prefix=""):
    """Render user activity status chart with selectable chart types."""

    activity_types = ['Active Users', 'Inactive Users']
    activity_counts = [active_users, inactive_users]
    _render_user_activity_bar_chart(activity_types, activity_counts, key_prefix)


def _render_user_activity_bar_chart(activity_types, activity_counts, key_prefix):
    """Render user activity bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=activity_types,
            y=activity_counts,
            marker_color=['#0077B6', '#E8A229'],
            text=activity_counts,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Activity Status',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_user_activity_pie_chart(activity_types, activity_counts, key_prefix, donut=False):
    """Render user activity pie chart using ECharts."""
    chart_data = [
        {"value": activity_counts[i], "name": f"{activity_types[i]} ({activity_counts[i]})"}
        for i in range(len(activity_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Activity Status",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#E8A229']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_user_activity_rose_chart(activity_types, activity_counts, key_prefix):
    """Render user activity rose chart using ECharts."""
    chart_data = [
        {"value": activity_counts[i], "name": f"{activity_types[i]} ({activity_counts[i]})"}
        for i in range(len(activity_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Activity Status",
                "type": "pie",
                "radius": [15, 80],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#E8A229']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_user_averages_chart(avg_roles_per_user, avg_users_per_role, key_prefix=""):
    """Render role assignment averages chart with selectable chart types."""

    # Add chart type selector

    # Prepare data
    avg_types = ['Avg Roles/User', 'Avg Users/Role']
    avg_values = [avg_roles_per_user, avg_users_per_role]

    _render_user_averages_bar_chart(avg_types, avg_values, key_prefix)


def _render_user_averages_bar_chart(avg_types, avg_values, key_prefix):
    """Render user averages bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=avg_types,
            y=avg_values,
            marker_color=['#75C2D8', '#0077B6'],
            text=[f'{v:.1f}' for v in avg_values],
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Average: %{y:.1f}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Metric',
        yaxis_title='Average',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_user_averages_pie_chart(avg_types, avg_values, key_prefix, donut=False):
    """Render user averages pie chart using ECharts."""
    chart_data = [
        {"value": round(avg_values[i], 1), "name": f"{avg_types[i]} ({avg_values[i]:.1f})"}
        for i in range(len(avg_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Averages",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#75C2D8', '#0077B6']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_user_averages_rose_chart(avg_types, avg_values, key_prefix):
    """Render user averages rose chart using ECharts."""
    chart_data = [
        {"value": round(avg_values[i], 1), "name": f"{avg_types[i]} ({avg_values[i]:.1f})"}
        for i in range(len(avg_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Averages",
                "type": "pie",
                "radius": [15, 80],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#75C2D8', '#0077B6']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_user_inventory_summary_chart(total_users, person_count, service_count, active_users, inactive_users, key_prefix=""):
    """Render overall user inventory summary chart with selectable chart types."""

    summary_types = ['Total', 'Person', 'Service', 'Active', 'Inactive']
    summary_counts = [total_users, person_count, service_count, active_users, inactive_users]
    _render_user_summary_bar_chart(summary_types, summary_counts, key_prefix)


def _render_user_summary_bar_chart(summary_types, summary_counts, key_prefix):
    """Render user summary bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=summary_types,
            y=summary_counts,
            marker_color=['#29B5E8', '#0077B6', '#E8A229', '#75C2D8', '#E8A229'],
            text=summary_counts,
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='User Category',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_user_summary_pie_chart(summary_types, summary_counts, key_prefix, donut=False):
    """Render user summary pie chart using ECharts."""
    # Filter out Total for pie chart as it's a sum of others
    filtered_types = summary_types[1:]  # Exclude 'Total'
    filtered_counts = summary_counts[1:]  # Exclude total count

    chart_data = [
        {"value": filtered_counts[i], "name": f"{filtered_types[i]} ({filtered_counts[i]})"}
        for i in range(len(filtered_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "User Summary",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#E8A229', '#75C2D8', '#E8A229']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_user_summary_rose_chart(summary_types, summary_counts, key_prefix):
    """Render user summary rose chart using ECharts."""
    # Filter out Total for pie chart as it's a sum of others
    filtered_types = summary_types[1:]  # Exclude 'Total'
    filtered_counts = summary_counts[1:]  # Exclude total count

    chart_data = [
        {"value": filtered_counts[i], "name": f"{filtered_types[i]} ({filtered_counts[i]})"}
        for i in range(len(filtered_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "User Summary",
                "type": "pie",
                "radius": [15, 70],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#E8A229', '#75C2D8', '#E8A229']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_security_hygiene():
    """Render the Security Hygiene ("Unhealthy" Users) section with table and charts."""

    st.markdown("#### Security Hygiene (\"Unhealthy\" Users)")

    # Introduction
    st.markdown("""
    Authentication security assessment identifying users by auth method, unhealthy configurations
    (password without MFA, keypair users, ACCOUNTADMIN default roles), and privileged role assignments.
    """)

    try:
        security_hygiene_query = """
        SELECT
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'PASSWORD' THEN user_name END) AS users_using_password,
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'OAUTH_ACCESS_TOKEN' THEN user_name END) AS users_using_oauth,
            COUNT(DISTINCT CASE WHEN first_authentication_factor = 'RSA_KEYPAIR' THEN user_name END) AS users_using_keypair,

            (SELECT COUNT(*)
             FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE has_password = 'YES'
               AND ext_authn_duo = 'FALSE'
               AND deleted_on IS NULL) AS unhealthy_password_no_mfa,

            (SELECT COUNT(*)
             FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE has_rsa_public_key = 'YES'
               AND deleted_on IS NULL) AS keypair_users_check_net_policy,

            (SELECT COUNT(*)
             FROM SNOWFLAKE.ACCOUNT_USAGE.USERS
             WHERE default_role = 'ACCOUNTADMIN'
               AND deleted_on IS NULL) AS default_role_accountadmin,

            (SELECT COUNT(DISTINCT grantee_name)
             FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
             WHERE role IN ('ACCOUNTADMIN', 'SECURITYADMIN')
               AND deleted_on IS NULL) AS users_holding_admin_roles

        FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
        WHERE event_timestamp >= DATEADD('day', -30, CURRENT_TIMESTAMP())
        """

        security_hygiene_df = _cached_sql("auth_security_hygiene", security_hygiene_query)

        if not security_hygiene_df.empty:
            st.dataframe(
                security_hygiene_df,
                use_container_width=True
            )

            # Extract values for charts
            row = security_hygiene_df.iloc[0]
            users_using_password = int(row['USERS_USING_PASSWORD']) if row['USERS_USING_PASSWORD'] is not None else 0
            users_using_oauth = int(row['USERS_USING_OAUTH']) if row['USERS_USING_OAUTH'] is not None else 0
            users_using_keypair = int(row['USERS_USING_KEYPAIR']) if row['USERS_USING_KEYPAIR'] is not None else 0
            unhealthy_password_no_mfa = int(row['UNHEALTHY_PASSWORD_NO_MFA']) if row['UNHEALTHY_PASSWORD_NO_MFA'] is not None else 0
            keypair_users_check = int(row['KEYPAIR_USERS_CHECK_NET_POLICY']) if row['KEYPAIR_USERS_CHECK_NET_POLICY'] is not None else 0
            default_role_accountadmin = int(row['DEFAULT_ROLE_ACCOUNTADMIN']) if row['DEFAULT_ROLE_ACCOUNTADMIN'] is not None else 0
            users_holding_admin_roles = int(row['USERS_HOLDING_ADMIN_ROLES']) if row['USERS_HOLDING_ADMIN_ROLES'] is not None else 0

            # Create charts section
            st.markdown("---")
            st.markdown("##### Security Hygiene Analysis Charts")

            # Two charts per row
            chart_col1, chart_col2 = st.columns(2)

            # Chart 1: Authentication Methods Distribution
            with chart_col1.container():
                st.markdown("##### Authentication Methods (Last 30 Days)")
                _render_auth_methods_chart(users_using_password, users_using_oauth, users_using_keypair, key_prefix="auth_methods_")

            # Chart 2: Unhealthy User Configurations
            with chart_col2.container():
                st.markdown("##### Unhealthy User Configurations")
                _render_unhealthy_configs_chart(unhealthy_password_no_mfa, keypair_users_check, default_role_accountadmin, key_prefix="unhealthy_configs_")

            # Second row of charts
            chart_col3, chart_col4 = st.columns(2)

            # Chart 3: Privileged Access Overview
            with chart_col3.container():
                st.markdown("##### Privileged Access Overview")
                _render_privileged_access_chart(users_holding_admin_roles, default_role_accountadmin, key_prefix="privileged_access_")

            # Chart 4: Overall Security Hygiene Summary
            with chart_col4.container():
                st.markdown("##### Overall Security Hygiene Summary")
                _render_security_summary_chart(users_using_password, users_using_oauth, users_using_keypair,
                                               unhealthy_password_no_mfa, default_role_accountadmin, users_holding_admin_roles,
                                               key_prefix="security_summary_")

        else:
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No security hygiene data available for the current execution context.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading security hygiene data: {str(e)}'
                    f'</div>', unsafe_allow_html=True)



def _render_auth_methods_chart(password_users, oauth_users, keypair_users, key_prefix=""):
    """Render authentication methods distribution chart with selectable chart types."""

    # Add chart type selector

    # Prepare data
    auth_types = ['Password', 'OAuth', 'Keypair']
    auth_counts = [password_users, oauth_users, keypair_users]

    _render_auth_methods_bar_chart(auth_types, auth_counts, key_prefix)


def _render_auth_methods_bar_chart(auth_types, auth_counts, key_prefix):
    """Render auth methods bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=auth_types,
            y=auth_counts,
            marker_color=['#29B5E8', '#0077B6', '#E8A229'],
            text=auth_counts,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Users: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Auth Method',
        yaxis_title='User Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_auth_methods_pie_chart(auth_types, auth_counts, key_prefix, donut=False):
    """Render auth methods pie chart using ECharts."""
    chart_data = [
        {"value": auth_counts[i], "name": f"{auth_types[i]} ({auth_counts[i]})"}
        for i in range(len(auth_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Auth Method",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#29B5E8', '#0077B6', '#E8A229']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_auth_methods_rose_chart(auth_types, auth_counts, key_prefix):
    """Render auth methods rose chart using ECharts."""
    chart_data = [
        {"value": auth_counts[i], "name": f"{auth_types[i]} ({auth_counts[i]})"}
        for i in range(len(auth_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Auth Method",
                "type": "pie",
                "radius": [15, 80],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#29B5E8', '#0077B6', '#E8A229']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_unhealthy_configs_chart(password_no_mfa, keypair_check, default_admin, key_prefix=""):
    """Render unhealthy user configurations chart with selectable chart types."""

    # Add chart type selector

    # Prepare data
    config_types = ['Password No MFA', 'Keypair (Check Policy)', 'Default ACCOUNTADMIN']
    config_counts = [password_no_mfa, keypair_check, default_admin]

    _render_unhealthy_bar_chart(config_types, config_counts, key_prefix)


def _render_unhealthy_bar_chart(config_types, config_counts, key_prefix):
    """Render unhealthy configs bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=config_types,
            y=config_counts,
            marker_color=['#E8A229', '#E8A229', '#F39C12'],
            text=config_counts,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Users: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Configuration Issue',
        yaxis_title='User Count',
        showlegend=False,
        margin=dict(t=20, b=70, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_unhealthy_pie_chart(config_types, config_counts, key_prefix, donut=False):
    """Render unhealthy configs pie chart using ECharts."""
    chart_data = [
        {"value": config_counts[i], "name": f"{config_types[i]} ({config_counts[i]})"}
        for i in range(len(config_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Unhealthy Config",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#E8A229', '#E8A229', '#E8A229']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_unhealthy_rose_chart(config_types, config_counts, key_prefix):
    """Render unhealthy configs rose chart using ECharts."""
    chart_data = [
        {"value": config_counts[i], "name": f"{config_types[i]} ({config_counts[i]})"}
        for i in range(len(config_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "textStyle": {"fontSize": 10},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Unhealthy Config",
                "type": "pie",
                "radius": [15, 70],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#E8A229', '#E8A229', '#E8A229']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_privileged_access_chart(admin_role_users, default_admin_users, key_prefix=""):
    """Render privileged access overview chart with selectable chart types."""

    # Add chart type selector

    # Prepare data
    access_types = ['Admin Role Holders', 'Default ACCOUNTADMIN']
    access_counts = [admin_role_users, default_admin_users]

    _render_privileged_bar_chart(access_types, access_counts, key_prefix)


def _render_privileged_bar_chart(access_types, access_counts, key_prefix):
    """Render privileged access bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=access_types,
            y=access_counts,
            marker_color=['#0077B6', '#75C2D8'],
            text=access_counts,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Users: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Privileged Access Type',
        yaxis_title='User Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_privileged_pie_chart(access_types, access_counts, key_prefix, donut=False):
    """Render privileged access pie chart using ECharts."""
    chart_data = [
        {"value": access_counts[i], "name": f"{access_types[i]} ({access_counts[i]})"}
        for i in range(len(access_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Privileged Access",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#75C2D8']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_privileged_rose_chart(access_types, access_counts, key_prefix):
    """Render privileged access rose chart using ECharts."""
    chart_data = [
        {"value": access_counts[i], "name": f"{access_types[i]} ({access_counts[i]})"}
        for i in range(len(access_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 10,
            "textStyle": {"fontSize": 11}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Privileged Access",
                "type": "pie",
                "radius": [15, 80],
                "center": ["50%", "45%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#0077B6', '#75C2D8']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_security_summary_chart(password_users, oauth_users, keypair_users,
                                    password_no_mfa, default_admin, admin_role_users, key_prefix=""):
    """Render overall security hygiene summary chart with selectable chart types."""

    # Add chart type selector

    # Prepare data
    summary_types = ['Password Auth', 'OAuth Auth', 'Keypair Auth', 'No MFA', 'Admin Role', 'Default Admin']
    summary_counts = [password_users, oauth_users, keypair_users, password_no_mfa, admin_role_users, default_admin]

    _render_security_summary_bar_chart(summary_types, summary_counts, key_prefix)


def _render_security_summary_bar_chart(summary_types, summary_counts, key_prefix):
    """Render security summary bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=summary_types,
            y=summary_counts,
            marker_color=['#29B5E8', '#0077B6', '#E8A229', '#E8A229', '#0077B6', '#1A7DA8'],
            text=summary_counts,
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Security Category',
        yaxis_title='Count',
        showlegend=False,
        margin=dict(t=20, b=70, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_security_summary_pie_chart(summary_types, summary_counts, key_prefix, donut=False):
    """Render security summary pie chart using ECharts."""
    chart_data = [
        {"value": summary_counts[i], "name": f"{summary_types[i]} ({summary_counts[i]})"}
        for i in range(len(summary_types))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Security Summary",
                "type": "pie",
                "radius": radius,
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#29B5E8', '#0077B6', '#E8A229', '#E8A229', '#0077B6', '#E8A229']
            }
        ],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_security_summary_rose_chart(summary_types, summary_counts, key_prefix):
    """Render security summary rose chart using ECharts."""
    chart_data = [
        {"value": summary_counts[i], "name": f"{summary_types[i]} ({summary_counts[i]})"}
        for i in range(len(summary_types))
    ]

    option = {
        "legend": {
            "bottom": "5",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 6,
            "textStyle": {"fontSize": 9},
            "type": "scroll"
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} ({d}%)"
        },
        "toolbox": {
            "show": True,
            "feature": {
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Security Summary",
                "type": "pie",
                "radius": [15, 70],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
                "color": ['#29B5E8', '#0077B6', '#E8A229', '#E8A229', '#0077B6', '#E8A229']
            }
        ],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_object_ownership():
    """Render the Object Ownership (Admin Hoarding) section with table and charts."""

    st.markdown("#### Object Ownership (Admin Hoarding)")

    # Introduction
    st.markdown("""
    Object ownership distribution across admin roles (ACCOUNTADMIN, SYSADMIN, SECURITYADMIN) by object type,
    excluding user and role objects.
    """)

    try:
        object_ownership_query = """
        SELECT
            grantee_name AS role_owner,
            granted_on AS object_type,
            COUNT(*) AS object_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
        WHERE deleted_on IS NULL
          AND privilege = 'OWNERSHIP'
          AND grantee_name IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN')
          AND granted_on NOT IN ('USER', 'ROLE')
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
        """

        object_ownership_df = _cached_sql("auth_object_ownership", object_ownership_query)

        if not object_ownership_df.empty:
            st.dataframe(
                object_ownership_df,
                use_container_width=True
            )

            # Aggregate data for charts
            # Total objects by role
            role_totals = object_ownership_df.groupby('ROLE_OWNER')['OBJECT_COUNT'].sum().to_dict()
            accountadmin_total = role_totals.get('ACCOUNTADMIN', 0)
            sysadmin_total = role_totals.get('SYSADMIN', 0)
            securityadmin_total = role_totals.get('SECURITYADMIN', 0)

            # Total objects by type (top types)
            type_totals = object_ownership_df.groupby('OBJECT_TYPE')['OBJECT_COUNT'].sum().sort_values(ascending=False)

            # Create charts section
            st.markdown("---")
            st.markdown("##### Object Ownership Analysis Charts")

            # Two charts per row
            chart_col1, chart_col2 = st.columns(2)

            # Chart 1: Object Ownership by Admin Role
            with chart_col1.container():
                st.markdown("##### Object Ownership by Admin Role")
                _render_ownership_by_role_chart(accountadmin_total, sysadmin_total, securityadmin_total, key_prefix="ownership_role_")

            # Chart 2: Object Ownership by Object Type (Top 10)
            with chart_col2.container():
                st.markdown("##### Object Ownership by Type (Top 10)")
                _render_ownership_by_type_chart(type_totals.head(10), key_prefix="ownership_type_")

            # Second row of charts
            chart_col3, chart_col4 = st.columns(2)

            # Chart 3: ACCOUNTADMIN vs Other Admins
            with chart_col3.container():
                st.markdown("##### ACCOUNTADMIN vs Other Admin Roles")
                other_admins_total = sysadmin_total + securityadmin_total
                _render_accountadmin_comparison_chart(accountadmin_total, other_admins_total, key_prefix="admin_comparison_")

            # Chart 4: Ownership Distribution Heatmap-style
            with chart_col4.container():
                st.markdown("##### Admin Role Ownership Summary")
                _render_ownership_summary_chart(accountadmin_total, sysadmin_total, securityadmin_total,
                                                len(type_totals), key_prefix="ownership_summary_")

        else:
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No object ownership data available for the current execution context.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading object ownership data: {str(e)}'
                    f'</div>', unsafe_allow_html=True)



def _render_ownership_by_role_chart(accountadmin_count, sysadmin_count, securityadmin_count, key_prefix=""):
    """Render object ownership by admin role chart with selectable chart types."""

    role_names = ['ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN']
    role_counts = [accountadmin_count, sysadmin_count, securityadmin_count]
    _render_ownership_role_bar_chart(role_names, role_counts, key_prefix)


def _render_ownership_role_bar_chart(role_names, role_counts, key_prefix):
    """Render ownership by role bar chart using Plotly."""
    fig = go.Figure(data=[
        go.Bar(
            x=role_names,
            y=role_counts,
            marker_color=['#E8A229', '#29B5E8', '#0077B6'],
            text=role_counts,
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='<b>%{x}</b><br>Objects: %{y}<extra></extra>'
        )
    ])

    fig.update_layout(
        height=300,
        xaxis_title='Admin Role',
        yaxis_title='Object Count',
        showlegend=False,
        margin=dict(t=20, b=50, l=50, r=30)
    )

    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_ownership_role_pie_chart(role_names, role_counts, key_prefix, donut=False):
    """Render ownership by role pie chart using ECharts."""
    chart_data = [
        {"value": role_counts[i], "name": f"{role_names[i]} ({role_counts[i]})"}
        for i in range(len(role_names))
    ]

    radius = ["25%", "60%"] if donut else ["0%", "60%"]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 10, "textStyle": {"fontSize": 11}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "toolbox": {"show": True, "feature": {"saveAsImage": {"show": True}}},
        "series": [{"name": "Admin Role", "type": "pie", "radius": radius, "center": ["50%", "45%"],
                    "itemStyle": {"borderRadius": 5}, "data": chart_data, "color": ['#E8A229', '#29B5E8', '#0077B6']}],
    }

    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_ownership_role_rose_chart(role_names, role_counts, key_prefix):
    """Render ownership by role rose chart using ECharts."""
    chart_data = [{"value": role_counts[i], "name": f"{role_names[i]} ({role_counts[i]})"} for i in range(len(role_names))]

    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 10, "textStyle": {"fontSize": 11}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "toolbox": {"show": True, "feature": {"saveAsImage": {"show": True}}},
        "series": [{"name": "Admin Role", "type": "pie", "radius": [15, 80], "center": ["50%", "45%"],
                    "roseType": "area", "itemStyle": {"borderRadius": 5}, "data": chart_data, "color": ['#E8A229', '#29B5E8', '#0077B6']}],
    }

    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_ownership_by_type_chart(type_totals, key_prefix=""):
    """Render object ownership by object type chart with selectable chart types."""
    type_names = type_totals.index.tolist()
    type_counts = type_totals.values.tolist()
    _render_ownership_type_bar_chart(type_names, type_counts, key_prefix)

def _render_ownership_type_bar_chart(type_names, type_counts, key_prefix):
    """Render ownership by type bar chart using Plotly."""
    fig = go.Figure(data=[go.Bar(y=type_names, x=type_counts, orientation='h', marker_color='#75C2D8', text=type_counts, textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{y}</b><br>Objects: %{x}<extra></extra>')])
    fig.update_layout(height=300, xaxis_title='Object Count', yaxis_title='Object Type', showlegend=False, margin=dict(t=20, b=50, l=100, r=50))
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")


def _render_ownership_type_pie_chart(type_names, type_counts, key_prefix, donut=False):
    """Render ownership by type pie chart using ECharts."""
    chart_data = [{"value": int(type_counts[i]), "name": f"{type_names[i]} ({int(type_counts[i])})"} for i in range(len(type_names))]
    radius = ["25%", "60%"] if donut else ["0%", "60%"]
    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "toolbox": {"show": True, "feature": {"saveAsImage": {"show": True}}},
        "series": [{"name": "Object Type", "type": "pie", "radius": radius, "center": ["50%", "40%"], "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }
    chart_key = f"{key_prefix}donut" if donut else f"{key_prefix}pie"
    st_echarts(options=option, height="300px", key=chart_key)


def _render_ownership_type_rose_chart(type_names, type_counts, key_prefix):
    """Render ownership by type rose chart using ECharts."""
    chart_data = [{"value": int(type_counts[i]), "name": f"{type_names[i]} ({int(type_counts[i])})"} for i in range(len(type_names))]
    option = {
        "legend": {"bottom": "5", "left": "center", "orient": "horizontal", "itemGap": 6, "textStyle": {"fontSize": 9}, "type": "scroll"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "toolbox": {"show": True, "feature": {"saveAsImage": {"show": True}}},
        "series": [{"name": "Object Type", "type": "pie", "radius": [15, 70], "center": ["50%", "40%"], "roseType": "area", "itemStyle": {"borderRadius": 5}, "data": chart_data}],
    }
    st_echarts(options=option, height="300px", key=f"{key_prefix}rose")


def _render_accountadmin_comparison_chart(accountadmin_count, other_admins_count, key_prefix=""):
    """Render ACCOUNTADMIN vs other admins comparison chart."""
    comparison_types = ['ACCOUNTADMIN', 'Other Admins']
    comparison_counts = [accountadmin_count, other_admins_count]
    fig = go.Figure(data=[go.Bar(x=comparison_types, y=comparison_counts, marker_color=['#E8A229', '#0077B6'], text=comparison_counts, textposition='outside', textfont=dict(size=12), hovertemplate='<b>%{x}</b><br>Objects: %{y}<extra></extra>')])
    fig.update_layout(height=300, xaxis_title='Admin Category', yaxis_title='Object Count', showlegend=False, margin=dict(t=20, b=50, l=50, r=30))
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")

def _render_ownership_summary_chart(accountadmin_count, sysadmin_count, securityadmin_count, unique_object_types, key_prefix=""):
    """Render overall ownership summary chart."""
    total_objects = accountadmin_count + sysadmin_count + securityadmin_count
    summary_types = ['Total Objects', 'ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN', 'Object Types']
    summary_counts = [total_objects, accountadmin_count, sysadmin_count, securityadmin_count, unique_object_types]
    fig = go.Figure(data=[go.Bar(x=summary_types, y=summary_counts, marker_color=['#29B5E8', '#E8A229', '#75C2D8', '#0077B6', '#E8A229'], text=summary_counts, textposition='outside', textfont=dict(size=10), hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>')])
    fig.update_layout(height=300, xaxis_title='Category', yaxis_title='Count', showlegend=False, margin=dict(t=20, b=70, l=50, r=30))
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}bar")
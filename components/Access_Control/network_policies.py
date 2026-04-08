import streamlit as st
import pandas as pd
import plotly.graph_objects as go

_C1 = "#29B5E8"
_C2 = "#11567F"
_C3 = "#75C2D8"
_CA = "#E8A229"


def _get(key, sql):
    if key in st.session_state:
        return st.session_state[key]
    session = st.session_state.get("session")
    if not session:
        return pd.DataFrame()
    try:
        df = session.sql(sql).to_pandas()
    except Exception:
        df = pd.DataFrame()
    st.session_state[key] = df
    return df


def _bar(x, y, colors, h=300, xlabel="", ylabel="Count", horizontal=False, key=""):
    if horizontal:
        fig = go.Figure(go.Bar(
            y=x, x=y, orientation="h",
            marker_color=colors if isinstance(colors, list) else [colors] * len(x),
            text=y, textposition="outside",
        ))
        fig.update_layout(height=h, xaxis_title=ylabel, yaxis_title=xlabel,
                          margin=dict(t=20, b=40, l=200, r=50), showlegend=False)
    else:
        fig = go.Figure(go.Bar(
            x=x, y=y,
            marker_color=colors if isinstance(colors, list) else [colors] * len(x),
            text=y, textposition="outside",
        ))
        fig.update_layout(height=h, xaxis_title=xlabel, yaxis_title=ylabel,
                          margin=dict(t=20, b=60, l=50, r=30), showlegend=False)
    if key:
        st.plotly_chart(fig, use_container_width=True, key=key)
    else:
        st.plotly_chart(fig, use_container_width=True)


def _donut(labels, values, colors, h=320, key=""):
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.45, marker_colors=colors,
        textinfo="percent", textposition="inside",
    ))
    fig.update_layout(height=h, margin=dict(t=20, b=20, l=20, r=20),
                      legend=dict(orientation="v", x=1.02, y=0.5))
    if key:
        st.plotly_chart(fig, use_container_width=True, key=key)
    else:
        st.plotly_chart(fig, use_container_width=True)


def comp_network_policies(entry_actions=None):
    try:
        with st.expander("Network Security Summary", expanded=True):
            _render_network_summary()

        with st.expander("Network Policies Audit (Enforced vs Dangling)", expanded=True):
            _render_policies_audit()

        with st.expander("Network Rules Audit (Attached vs Orphaned)", expanded=True):
            _render_rules_audit()

        with st.expander("Dangling Policies Detail", expanded=True):
            _render_dangling_policies()

        with st.expander("User Network Policy Coverage", expanded=True):
            _render_user_coverage()

    except Exception as e:
        st.error(f"Error loading Network Rules & Policies: {e}")


def _render_network_summary():
    st.caption("High-level overview of network policy and rule coverage.")
    sql = """
        WITH policy_stats AS (
            SELECT
                COUNT(*) AS total_policies,
                COUNT(CASE WHEN deleted IS NULL THEN 1 END) AS active_policies
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES
        ),
        rule_stats AS (
            SELECT
                COUNT(*) AS total_rules,
                COUNT(CASE WHEN deleted IS NULL THEN 1 END) AS active_rules,
                COUNT(CASE WHEN mode = 'INGRESS' AND deleted IS NULL THEN 1 END) AS ingress_rules,
                COUNT(CASE WHEN mode = 'EGRESS' AND deleted IS NULL THEN 1 END) AS egress_rules
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES
        ),
        enforcement_stats AS (
            SELECT
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'ACCOUNT' THEN policy_name END) AS account_level_policies,
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'USER' THEN policy_name END) AS user_level_policies,
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'INTEGRATION' THEN policy_name END) AS integration_policies,
                COUNT(DISTINCT CASE WHEN ref_entity_domain = 'USER' THEN ref_entity_name END) AS users_with_policies
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE policy_kind = 'NETWORK_POLICY'
        )
        SELECT
            ps.total_policies, ps.active_policies,
            rs.total_rules, rs.active_rules, rs.ingress_rules, rs.egress_rules,
            es.account_level_policies, es.user_level_policies,
            es.integration_policies, es.users_with_policies,
            CASE
                WHEN es.account_level_policies > 0 THEN 'PROTECTED'
                WHEN es.user_level_policies > 0 THEN 'PARTIALLY_PROTECTED'
                ELSE 'UNPROTECTED'
            END AS account_protection_status,
            CASE
                WHEN es.account_level_policies = 0
                    THEN 'Consider implementing account-level network policy'
                WHEN rs.egress_rules = 0
                    THEN 'Consider adding egress rules for data exfiltration protection'
                ELSE 'Network security configuration appears adequate'
            END AS recommendation
        FROM policy_stats ps
        CROSS JOIN rule_stats rs
        CROSS JOIN enforcement_stats es
    """
    df = _get("ac_net_full_summary", sql)
    if df.empty:
        st.info("No network security data available.")
        return
    row = df.iloc[0]
    total_pol = int(row.get("TOTAL_POLICIES", 0))
    active_pol = int(row.get("ACTIVE_POLICIES", 0))
    total_rules = int(row.get("TOTAL_RULES", 0))
    active_rules = int(row.get("ACTIVE_RULES", 0))
    acct_pol = int(row.get("ACCOUNT_LEVEL_POLICIES", 0))
    user_pol = int(row.get("USER_LEVEL_POLICIES", 0))
    intg_pol = int(row.get("INTEGRATION_POLICIES", 0))
    users_cov = int(row.get("USERS_WITH_POLICIES", 0))
    ingress = int(row.get("INGRESS_RULES", 0))
    egress = int(row.get("EGRESS_RULES", 0))
    status = str(row.get("ACCOUNT_PROTECTION_STATUS", "UNKNOWN"))
    recommendation = str(row.get("RECOMMENDATION", ""))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Policies", f"{total_pol:,}")
    with c2:
        st.metric("Active Policies", f"{active_pol:,}")
    with c3:
        st.metric("Total Rules", f"{total_rules:,}")
    with c4:
        st.metric("Active Rules", f"{active_rules:,}")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.metric("Account-Level", f"{acct_pol:,}")
    with c6:
        st.metric("User-Level", f"{user_pol:,}")
    with c7:
        st.metric("Integration", f"{intg_pol:,}")
    with c8:
        st.metric("Users Covered", f"{users_cov:,}")

    status_icon = "✅" if status == "PROTECTED" else ("⚠️" if status == "PARTIALLY_PROTECTED" else "❌")
    status_color = "#E8F5E9" if status == "PROTECTED" else ("#FFFBE6" if status == "PARTIALLY_PROTECTED" else "#EBF5FB")
    border_color = "#2ECC71" if status == "PROTECTED" else (_CA if status == "PARTIALLY_PROTECTED" else "#2980B9")
    st.markdown(
        f'<div style="background-color:{status_color};border-left:4px solid {border_color};border-radius:4px;padding:10px;margin:8px 0;">'
        f'{status_icon} Account protection status: <b>{status}</b><br>'
        f'<span style="color:#555;">{recommendation}</span>'
        f'</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Policies by Enforcement Level**")
        _bar(["Account-Level", "User-Level", "Integration"],
             [acct_pol, user_pol, intg_pol],
             [_C1, _C1, _C1], xlabel="Enforcement Level", ylabel="Policies", key="ns_pol_enf")
    with col2:
        st.markdown("**Network Rules by Direction**")
        _bar(["Ingress", "Egress"], [ingress, egress],
             [_C1, _C1], xlabel="Direction", ylabel="Rules", key="ns_rules_dir")


def _render_policies_audit():
    st.caption("Network policy inventory — policies not attached to any account, user, or integration are marked as DANGLING and may represent security gaps.")
    sql = """
        WITH policy_usage AS (
            SELECT
                policy_name,
                COUNT(CASE WHEN ref_entity_domain = 'ACCOUNT' THEN 1 END) AS applied_to_account,
                COUNT(CASE WHEN ref_entity_domain = 'USER' THEN 1 END) AS applied_to_users,
                COUNT(CASE WHEN ref_entity_domain = 'INTEGRATION' THEN 1 END) AS applied_to_integrations,
                COUNT(*) AS total_attachments
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE policy_kind = 'NETWORK_POLICY'
            GROUP BY policy_name
        )
        SELECT
            np.name AS policy_name,
            np.owner,
            CASE
                WHEN pu.applied_to_account > 0 THEN 'ENFORCED_ACCOUNT_LEVEL'
                WHEN pu.applied_to_users > 0 THEN 'ENFORCED_USER_LEVEL'
                WHEN pu.applied_to_integrations > 0 THEN 'ENFORCED_INTEGRATION'
                ELSE 'DANGLING_NOT_ENFORCED'
            END AS enforcement_status,
            COALESCE(pu.applied_to_account, 0) AS account_attachments,
            COALESCE(pu.applied_to_users, 0) AS user_attachments,
            COALESCE(pu.applied_to_integrations, 0) AS integration_attachments,
            COALESCE(pu.total_attachments, 0) AS total_attachments,
            np.created AS created_date,
            np.comment,
            CASE
                WHEN pu.applied_to_account > 0 THEN 'Account-wide protection active'
                WHEN pu.applied_to_users > 0 THEN 'User-specific restrictions active'
                WHEN pu.applied_to_integrations > 0 THEN 'Integration restrictions active'
                ELSE 'Policy exists but not protecting anything - review or remove'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES np
        LEFT JOIN policy_usage pu ON np.name = pu.policy_name
        WHERE np.deleted IS NULL
        ORDER BY enforcement_status ASC, np.name
    """
    df = _get("net_policies_data", sql)
    if df.empty:
        st.info("No network policies found.")
        return

    total = len(df)
    enforced = len(df[df["ENFORCEMENT_STATUS"] != "DANGLING_NOT_ENFORCED"]) if "ENFORCEMENT_STATUS" in df.columns else 0
    dangling = total - enforced

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Policies", f"{total:,}")
    with c2:
        st.metric("Enforced Policies", f"{enforced:,}")
    with c3:
        st.metric("Dangling Policies", f"{dangling:,}",
                  delta="↑ Review" if dangling > 0 else None,
                  delta_color="inverse")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Policy Enforcement Status**")
        if "ENFORCEMENT_STATUS" in df.columns:
            status_agg = df.groupby("ENFORCEMENT_STATUS").size().reset_index(name="COUNT")
            status_colors_map = {
                "ENFORCED_ACCOUNT_LEVEL": _C2,
                "ENFORCED_USER_LEVEL": _C1,
                "ENFORCED_INTEGRATION": _C3,
                "DANGLING_NOT_ENFORCED": _CA,
            }
            colors = [status_colors_map.get(s, _C1) for s in status_agg["ENFORCEMENT_STATUS"]]
            _donut(status_agg["ENFORCEMENT_STATUS"].tolist(),
                   status_agg["COUNT"].tolist(), colors, key="pa_status")

    with col2:
        st.markdown("**User Attachments per Policy**")
        if "USER_ATTACHMENTS" in df.columns:
            ua_df = df[["POLICY_NAME", "USER_ATTACHMENTS"]].copy()
            ua_df["USER_ATTACHMENTS"] = pd.to_numeric(ua_df["USER_ATTACHMENTS"], errors="coerce").fillna(0).astype(int)
            ua_df = ua_df.sort_values("USER_ATTACHMENTS", ascending=True).tail(15)
            _bar(ua_df["POLICY_NAME"].tolist(), ua_df["USER_ATTACHMENTS"].tolist(),
                 _C1, ylabel="Users", horizontal=True, h=350, key="pa_users")

    display_cols = ["POLICY_NAME", "OWNER", "ENFORCEMENT_STATUS",
                    "ACCOUNT_ATTACHMENTS", "USER_ATTACHMENTS", "INTEGRATION_ATTACHMENTS",
                    "TOTAL_ATTACHMENTS", "CREATED_DATE", "COMMENT", "RECOMMENDATION"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "POLICY_NAME": "Policy", "OWNER": "Owner", "ENFORCEMENT_STATUS": "Status",
        "ACCOUNT_ATTACHMENTS": "Acct", "USER_ATTACHMENTS": "Users",
        "INTEGRATION_ATTACHMENTS": "Integrations", "TOTAL_ATTACHMENTS": "Total Attachments",
        "CREATED_DATE": "Created", "COMMENT": "Comment", "RECOMMENDATION": "Recommendation"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)


def _render_rules_audit():
    st.caption("Network rules inventory — rules not referenced by any policy are marked as Orphaned.")
    sql = """
        WITH rule_usage AS (
            SELECT network_rule_name, COUNT(*) AS reference_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULE_REFERENCES
            GROUP BY 1
        )
        SELECT
            nr.name AS rule_name,
            nr.database_name AS db,
            nr.schema_name AS schema,
            nr.mode AS rule_mode,
            nr.type AS rule_type,
            CASE WHEN ru.reference_count > 0 THEN 'ATTACHED' ELSE 'ORPHANED' END AS usage_status,
            COALESCE(ru.reference_count, 0) AS reference_count,
            nr.owner AS owned_by,
            nr.comment,
            CASE
                WHEN ru.reference_count > 0 THEN 'Rule is active in network policy'
                ELSE 'Orphaned rule - consider attaching or removing'
            END AS recommendation
        FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_RULES nr
        LEFT JOIN rule_usage ru ON nr.name = ru.network_rule_name
        WHERE nr.deleted IS NULL
        ORDER BY usage_status ASC, nr.name
    """
    df = _get("net_rules_data", sql)
    if df.empty:
        st.info("No network rules found.")
        return

    total = len(df)
    attached = len(df[df["USAGE_STATUS"] == "ATTACHED"]) if "USAGE_STATUS" in df.columns else 0
    orphaned = total - attached

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Rules", f"{total:,}")
    with c2:
        st.metric("Attached Rules", f"{attached:,}")
    with c3:
        st.metric("Orphaned Rules", f"{orphaned:,}",
                  delta="↑ Review" if orphaned > 0 else None,
                  delta_color="inverse")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Rule Attachment Status**")
        _donut(["ORPHANED", "ATTACHED"], [orphaned, attached], [_CA, _C1], key="ra_attach")

    with col2:
        st.markdown("**Rules by Direction (Ingress / Egress)**")
        if "RULE_MODE" in df.columns:
            mode_agg = df.groupby("RULE_MODE").size().reset_index(name="COUNT")
            _bar(mode_agg["RULE_MODE"].tolist(), mode_agg["COUNT"].tolist(),
                 [_C1] * len(mode_agg), xlabel="Direction", key="ra_dir")

    with col3:
        st.markdown("**Rules by Type**")
        if "RULE_TYPE" in df.columns:
            type_agg = df.groupby("RULE_TYPE").size().reset_index(name="COUNT")
            type_agg = type_agg.sort_values("COUNT", ascending=True)
            _bar(type_agg["RULE_TYPE"].tolist(), type_agg["COUNT"].tolist(),
                 _C1, ylabel="Count", horizontal=True, h=280, key="ra_type")

    display_cols = ["RULE_NAME", "DB", "SCHEMA", "RULE_MODE", "RULE_TYPE",
                    "USAGE_STATUS", "REFERENCE_COUNT", "OWNED_BY"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "RULE_NAME": "Rule", "DB": "DB", "SCHEMA": "Schema",
        "RULE_MODE": "Mode", "RULE_TYPE": "Type",
        "USAGE_STATUS": "Status", "REFERENCE_COUNT": "References", "OWNED_BY": "Owner"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)


def _render_dangling_policies():
    st.caption("Policies that exist but are not attached to anything — stale if older than 30 days.")
    sql = """
        WITH policy_usage AS (
            SELECT DISTINCT policy_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
            WHERE policy_kind = 'NETWORK_POLICY'
        )
        SELECT
            np.name AS policy_name,
            np.owner,
            np.created AS created_date,
            np.comment,
            DATEDIFF('day', np.created, CURRENT_TIMESTAMP()) AS days_since_created,
            CASE
                WHEN DATEDIFF('day', np.created, CURRENT_TIMESTAMP()) > 30 THEN 'STALE_UNUSED'
                ELSE 'RECENTLY_CREATED'
            END AS age_status
        FROM SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES np
        LEFT JOIN policy_usage pu ON np.name = pu.policy_name
        WHERE np.deleted IS NULL AND pu.policy_name IS NULL
        ORDER BY np.created DESC
    """
    df = _get("ac_dangling_net_policies", sql)

    stale = len(df[df["AGE_STATUS"] == "STALE_UNUSED"]) if not df.empty and "AGE_STATUS" in df.columns else 0
    recent = len(df[df["AGE_STATUS"] == "RECENTLY_CREATED"]) if not df.empty and "AGE_STATUS" in df.columns else 0

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Stale Unused Policies", f"{stale:,}",
                  delta="⚠ Review" if stale > 0 else None,
                  delta_color="inverse")
    with c2:
        st.metric("Recently Created (unused)", f"{recent:,}")

    if df.empty:
        st.info("No dangling (unattached) network policies found.")
        return

    display_cols = ["POLICY_NAME", "OWNER", "CREATED_DATE", "COMMENT"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "POLICY_NAME": "Policy", "OWNER": "Owner",
        "CREATED_DATE": "Created", "COMMENT": "Comment"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)


def _render_user_coverage():
    st.caption("Users that have specific network policies applied at the user level.")
    sql = """
        SELECT
            pr.ref_entity_name AS user_name,
            pr.policy_name,
            np.comment AS policy_description
        FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES pr
        INNER JOIN SNOWFLAKE.ACCOUNT_USAGE.NETWORK_POLICIES np
            ON pr.policy_name = np.name AND np.deleted IS NULL
        WHERE pr.policy_kind = 'NETWORK_POLICY'
          AND pr.ref_entity_domain = 'USER'
        ORDER BY pr.ref_entity_name
    """
    df = _get("ac_user_net_coverage", sql)
    if df.empty:
        st.markdown(
            '<div style="background-color:#EBF5FB;border-left:4px solid #2980B9;border-radius:4px;padding:10px;">'
            'ℹ️ No user-level network policy assignments found.'
            '</div>', unsafe_allow_html=True)
        return

    display_cols = ["USER_NAME", "POLICY_NAME", "POLICY_DESCRIPTION"]
    display_cols = [c for c in display_cols if c in df.columns]
    rename_map = {
        "USER_NAME": "User", "POLICY_NAME": "Policy Name",
        "POLICY_DESCRIPTION": "Policy Description"
    }
    st.dataframe(df[display_cols].rename(columns=rename_map), use_container_width=True)

"""
Per-topic export data collectors.
Each function reads cached data from st.session_state / module caches
and returns the structured HTML string for that topic's telemetry report.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
from core.export_telemetry import (
    build_report, build_sub_section, build_chart,
    _make_table, _kpi_cards, _fmt_num, _esc,
    _COLORS,
)
from core.config.design_tokens import (
    BRAND_SECONDARY, BRAND_PRIMARY_DARK, BRAND_SECONDARY_LIGHT, BRAND_ACCENT,
)

_P = BRAND_SECONDARY
_S = BRAND_PRIMARY_DARK
_T = BRAND_SECONDARY_LIGHT
_A = BRAND_ACCENT


def _safe_df(key: str, fallback=None):
    val = st.session_state.get(key)
    if val is not None and isinstance(val, pd.DataFrame) and not val.empty:
        return val
    if fallback is not None:
        return fallback
    return pd.DataFrame()


def _safe_text(key: str) -> str:
    val = st.session_state.get(key, "")
    return str(val) if val else ""


def _indiv_analyses(prefix: str, entity_list_key: str) -> list[dict]:
    entities = st.session_state.get(entity_list_key, [])
    results = []
    for e in entities:
        key = f"{prefix}{e}"
        text = _safe_text(key)
        if text:
            results.append({"title": str(e), "content": text})
    return results


def _col_vals(df: pd.DataFrame, col: str) -> list:
    if col in df.columns:
        return df[col].tolist()
    return []


def _trunc_labels(labels: list, maxlen: int = 40) -> list:
    return [str(l)[:maxlen] for l in labels]


def _df_table(df: pd.DataFrame, cols: list[str] | None = None, limit: int = 50) -> str:
    if df.empty:
        return ""
    if cols is None:
        cols = list(df.columns)
    else:
        cols = [c for c in cols if c in df.columns]
    if not cols:
        return ""
    return _make_table(cols, df.head(limit)[cols].values.tolist())


def _num(val, dec=2):
    try:
        return round(float(val), dec)
    except (TypeError, ValueError):
        return 0


# ─── DATABASE MANAGEMENT ──────────────────────────────────────────────

def export_database_management(account_name: str) -> str:
    from components.Database_Management.db_overview import _query_cache

    def _qc(key):
        df = _query_cache.get(key)
        if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
            return df
        return _safe_df(key)

    top_kpis = []
    df_stor = _qc("db_overview_1_total_storage_query")
    active = tt = fs = clone = 0
    if not df_stor.empty:
        r = df_stor.iloc[0]
        active = _num(r.get("ACTIVE_STORAGE_TB", 0), 3)
        tt = _num(r.get("TIME_TRAVEL_STORAGE_TB", 0), 3)
        fs = _num(r.get("FAILSAFE_STORAGE_TB", 0), 3)
        clone = _num(r.get("RETAINED_FOR_CLONE_STORAGE_TB", 0), 3)
        total = active + tt + fs + clone
        top_kpis = [
            {"value": f"{total:.3f} TB", "label": "Total Storage"},
            {"value": f"{active:.3f} TB", "label": "Active"},
            {"value": f"{tt:.3f} TB", "label": "Time Travel"},
            {"value": f"{fs:.3f} TB", "label": "Failsafe"},
            {"value": f"{clone:.3f} TB", "label": "Clone Retained"},
        ]

    df_sum = _qc("db_overview_2_storage_summary_query")
    db_count = tbl_count = 0
    if not df_sum.empty:
        r = df_sum.iloc[0]
        db_count = int(r.get("DATABASE_COUNT", 0) or 0)
        tbl_count = int(r.get("TABLE_COUNT", 0) or 0)
        top_kpis.append({"value": f"{db_count:,}", "label": "Databases"})
        top_kpis.append({"value": f"{tbl_count:,}", "label": "Tables"})

    sub_sections = []

    # --- Overview: storage pie + object counts ---
    ov_charts = ""
    if active or tt or fs or clone:
        ov_charts += '<div class="charts-row"><div class="chart-col">'
        ov_charts += build_chart("doughnut",
                                 labels=["Active", "Time Travel", "Failsafe", "Clone Retained"],
                                 data=[active, tt, fs, clone],
                                 colors=[_P, _S, _A, _T])
        ov_charts += "</div><div class='chart-col'>"
        df_obj = _qc("db_overview_14_object_count_query")
        if not df_obj.empty and "OBJECT_TYPE" in df_obj.columns and "OBJECT_COUNT" in df_obj.columns:
            ov_charts += build_chart("hbar",
                                     labels=_trunc_labels(df_obj["OBJECT_TYPE"].tolist()),
                                     datasets=[{"label": "Count", "data": [int(v) for v in df_obj["OBJECT_COUNT"].tolist()], "backgroundColor": _P}],
                                     title="Object Counts", x_title="Count")
        ov_charts += "</div></div>"
    sub_sections.append(build_sub_section("Overview", charts_html=ov_charts))

    # --- Database Storage: by-db stacked bar + top tables ---
    ds_charts = ""
    ds_tables = ""
    df_db = _qc("db_overview_3_db_storage_query")
    if not df_db.empty and "DATABASE_NAME" in df_db.columns:
        top20 = df_db.head(20)
        labels = _trunc_labels(top20["DATABASE_NAME"].tolist())
        ds_list = []
        for col, lbl, clr in [("ACTIVE_STORAGE_TB", "Active", _P), ("TIME_TRAVEL_TB", "Time Travel", _S),
                               ("FAILSAFE_TB", "Failsafe", _A), ("CLONE_TB", "Clone", _T)]:
            if col in top20.columns:
                ds_list.append({"label": lbl, "data": [_num(v, 4) for v in top20[col].tolist()], "backgroundColor": clr})
        if ds_list:
            ds_charts += build_chart("hbar", labels=labels, datasets=ds_list,
                                     title="Storage by Database (TB)", x_title="TB", stacked=True)
        ds_tables += _df_table(df_db, ["DATABASE_NAME", "ACTIVE_STORAGE_TB", "TIME_TRAVEL_TB", "FAILSAFE_TB", "CLONE_TB", "TOTAL_STORAGE_TB", "TABLE_COUNT"])

    df_top = _qc("db_overview_4_top_tables_query")
    if not df_top.empty and "FULL_TABLE_NAME" in df_top.columns:
        top30 = df_top.head(30)
        labels = _trunc_labels(top30["FULL_TABLE_NAME"].tolist())
        t_ds = []
        for col, lbl, clr in [("ACTIVE_STORAGE_GB", "Active GB", _P), ("TIME_TRAVEL_GB", "Time Travel GB", _S), ("FAILSAFE_GB", "Failsafe GB", _A)]:
            if col in top30.columns:
                t_ds.append({"label": lbl, "data": [_num(v) for v in top30[col].tolist()], "backgroundColor": clr})
        if t_ds:
            ds_charts += build_chart("hbar", labels=labels, datasets=t_ds,
                                     title="Top 30 Tables by Storage (GB)", x_title="GB", stacked=True)
        ds_tables += '<div class="section-subtitle">Top Tables</div>'
        ds_tables += _df_table(df_top, ["FULL_TABLE_NAME", "ACTIVE_STORAGE_GB", "TIME_TRAVEL_GB", "FAILSAFE_GB", "TOTAL_GB"])

    sub_sections.append(build_sub_section("Database Storage", charts_html=ds_charts, tables_html=ds_tables))

    # --- Clustering ---
    cl_kpis = []
    df_cl = _qc("db_overview_5_clustering_overview_query")
    if not df_cl.empty:
        r = df_cl.iloc[0]
        cl_kpis = [
            {"value": _fmt_num(r.get("TOTAL_TABLES"), 0), "label": "Total Tables"},
            {"value": _fmt_num(r.get("CLUSTERED_TABLES"), 0), "label": "Clustered"},
            {"value": _fmt_num(r.get("UNCLUSTERED_TABLES"), 0), "label": "Unclustered"},
            {"value": f"{_num(r.get('CLUSTER_PERCENTAGE', 0), 1)}%", "label": "Cluster %"},
        ]

    cl_charts = ""
    if not df_cl.empty:
        clustered = int(df_cl.iloc[0].get("CLUSTERED_TABLES", 0) or 0)
        unclustered = int(df_cl.iloc[0].get("UNCLUSTERED_TABLES", 0) or 0)
        cl_charts += '<div class="charts-row"><div class="chart-col">'
        cl_charts += build_chart("doughnut",
                                 labels=["Clustered", "Unclustered"],
                                 data=[clustered, unclustered],
                                 colors=[_P, _A])
        cl_charts += "</div><div class='chart-col'>"
        df_cred = _qc("db_overview_7_credit_history_query")
        if not df_cred.empty and "CLUSTER_DATE" in df_cred.columns and "DAILY_CREDITS" in df_cred.columns:
            cl_charts += build_chart("line",
                                     labels=[str(d)[:10] for d in df_cred["CLUSTER_DATE"].tolist()],
                                     datasets=[{"label": "Credits", "data": [_num(v) for v in df_cred["DAILY_CREDITS"].tolist()],
                                                "borderColor": _P, "backgroundColor": "rgba(41,181,232,0.15)", "fill": True}],
                                     title="Clustering Credits (Last 30 Days)", y_title="Credits")
        cl_charts += "</div></div>"

    cl_tables = ""
    df_ct = _qc("db_overview_6_clustered_tables_query")
    if not df_ct.empty:
        cl_tables = '<div class="section-subtitle">Clustered Tables</div>'
        cl_tables += _df_table(df_ct, ["FULL_TABLE_NAME", "CLUSTERING_KEY", "ROW_COUNT", "SIZE_GB", "AUTO_CLUSTERING_ON", "CREATED"])

    df_clcost = _qc("db_overview_16_credit_query")
    if not df_clcost.empty and "Table" in df_clcost.columns and "Credits" in df_clcost.columns:
        top15 = df_clcost.head(15).sort_values("Credits", ascending=True) if len(df_clcost) > 0 else df_clcost
        cl_charts += build_chart("hbar",
                                 labels=_trunc_labels(top15["Table"].tolist()),
                                 datasets=[{"label": "Credits", "data": [_num(v) for v in top15["Credits"].tolist()], "backgroundColor": _A}],
                                 title="Top 15 Tables by Clustering Credits (30d)", x_title="Credits")
        cl_tables += '<div class="section-subtitle">Automatic Clustering Cost Detail</div>'
        cl_tables += _df_table(df_clcost, ["Table", "Clustered", "Clustering Key", "Auto Clustering", "Credits", "Avg Credits/Day", "Active Days"])

    sub_sections.append(build_sub_section("Clustering", kpis=cl_kpis, charts_html=cl_charts, tables_html=cl_tables))

    # --- Low Lifespan Tables ---
    ll_kpis = []
    df_ll = _qc("db_overview_8_summary_query")
    if not df_ll.empty:
        r = df_ll.iloc[0]
        ll_kpis = [
            {"value": _fmt_num(r.get("TOTAL_SHORT_LIVED"), 0), "label": "Short-Lived Tables"},
            {"value": _fmt_num(r.get("PERMANENT_SHORT_LIVED"), 0), "label": "Permanent (Issue)"},
            {"value": _fmt_num(r.get("TRANSIENT_SHORT_LIVED"), 0), "label": "Transient (OK)"},
            {"value": f"{_num(r.get('AVG_LIFESPAN_MINUTES', 0), 0):.0f} min", "label": "Avg Lifespan"},
            {"value": f"{_num(r.get('TOTAL_CHURNED_STORAGE_GB', 0))} GB", "label": "Churned Storage"},
        ]

    ll_tables = ""
    df_detail = _qc("db_overview_9_detail_query")
    if not df_detail.empty:
        ll_tables += '<div class="section-subtitle">Short-Lived Table Details</div>'
        ll_tables += _df_table(df_detail, ["FULL_TABLE_NAME", "TABLE_OWNER", "TABLE_TYPE", "CREATED", "DELETED", "LIFESPAN_MINUTES", "SIZE_MB"])

    df_pattern = _qc("db_overview_10_pattern_query")
    if not df_pattern.empty:
        ll_tables += '<div class="section-subtitle">Users Creating Permanent Short-Lived Tables</div>'
        ll_tables += _df_table(df_pattern, ["OWNER", "SHORT_LIVED_COUNT", "AVG_LIFESPAN", "PERMANENT_COUNT"])

    ll_charts = ""
    df_schema = _qc("db_overview_21_schema_summary_query")
    if not df_schema.empty and "Schema" in df_schema.columns and "Short-Lived" in df_schema.columns:
        top15 = df_schema.head(15).sort_values("Short-Lived", ascending=True) if len(df_schema) > 0 else df_schema
        ll_charts += build_chart("hbar",
                                 labels=_trunc_labels(top15["Schema"].tolist()),
                                 datasets=[{"label": "Short-Lived", "data": [int(v) for v in top15["Short-Lived"].tolist()], "backgroundColor": _P}],
                                 title="Top 15 Schemas by Short-Lived Tables", x_title="Count")
        if "Recommendation" in df_schema.columns:
            rec_counts = df_schema["Recommendation"].value_counts()
            ll_charts += build_chart("doughnut",
                                     labels=rec_counts.index.tolist(),
                                     data=rec_counts.values.tolist(),
                                     colors=[_A, _P])
        ll_tables += '<div class="section-subtitle">Short-Lived Tables by Schema</div>'
        ll_tables += _df_table(df_schema, ["Schema", "Short-Lived", "Permanent (Issue)", "Transient (OK)", "Avg Lifespan (min)", "Recommendation"])

    sub_sections.append(build_sub_section("Low Lifespan Tables", kpis=ll_kpis, charts_html=ll_charts, tables_html=ll_tables))

    # --- High Churn Tables ---
    hc_kpis = []
    df_hc = _qc("db_overview_11_summary_query")
    if not df_hc.empty:
        r = df_hc.iloc[0]
        hc_kpis = [
            {"value": _fmt_num(r.get("TABLES_WITH_CHURN"), 0), "label": "Tables with Churn"},
            {"value": _fmt_num(r.get("HIGH_CHURN_TABLES"), 0), "label": "High Churn (>1x)"},
            {"value": f"{_num(r.get('TOTAL_CHURN_TB', 0), 4)} TB", "label": "Total Churn Storage"},
            {"value": f"{_num(r.get('AVG_CHURN_RATIO', 0))}x", "label": "Avg Churn Ratio"},
        ]

    hc_charts = ""
    df_dbc = _qc("db_overview_13_db_churn_query")
    if not df_dbc.empty and "DATABASE_NAME" in df_dbc.columns and "TOTAL_CHURN_TB" in df_dbc.columns:
        top15 = df_dbc.head(15)
        hc_charts += build_chart("hbar",
                                 labels=_trunc_labels(top15["DATABASE_NAME"].tolist()),
                                 datasets=[{"label": "Churn (TB)", "data": [_num(v, 4) for v in top15["TOTAL_CHURN_TB"].tolist()], "backgroundColor": _A}],
                                 title="Churn by Database (TB)", x_title="Churn (TB)")

    hc_tables = ""
    df_hcd = _qc("db_overview_12_detail_query")
    if not df_hcd.empty:
        hc_tables += '<div class="section-subtitle">High Churn Table Details</div>'
        hc_tables += _df_table(df_hcd, ["TABLE_NAME", "TABLE_TYPE", "ROW_COUNT", "ACTIVE_DATA_GB", "TIME_TRAVEL_GB", "FAILSAFE_GB", "TOTAL_CHURN_GB", "CHURN_RATIO"])

    sub_sections.append(build_sub_section("High Churn Tables", kpis=hc_kpis, charts_html=hc_charts, tables_html=hc_tables))

    # --- Potential Storage Savings Summary ---
    df_ps = _qc("db_overview_22_potential_savings_query")
    if not df_ps.empty and "Action" in df_ps.columns:
        ps_kpis = []
        for _, row in df_ps.iterrows():
            ps_kpis.append({"value": f"${_fmt_num(row.get('Est. Monthly Savings (USD)', 0), 0)}/mo", "label": str(row.get('Action', ''))})
            ps_kpis.append({"value": _fmt_num(row.get('Tables', 0), 0), "label": "Tables Affected"})
        ps_charts = ""
        actions = df_ps["Action"].tolist()
        savings = [_num(v, 0) for v in df_ps["Est. Monthly Savings (USD)"].tolist()]
        colors_list = [_P, _A]
        ds_list = []
        for i, (act, val) in enumerate(zip(actions, savings)):
            ds_list.append({"label": act, "data": [val if j == i else 0 for j in range(len(actions))], "backgroundColor": colors_list[i % len(colors_list)]})
        ps_charts = build_chart("vbar", labels=[str(a)[:40] for a in actions], datasets=ds_list,
                                title="Estimated Monthly Savings (USD)", y_title="USD / month")
        ps_tables = _df_table(df_ps, ["Action", "Tables", "Savings (TB)", "Est. Monthly Savings (USD)"])
        sub_sections.append(build_sub_section("Potential Storage Savings Summary", kpis=ps_kpis, charts_html=ps_charts, tables_html=ps_tables))

    return build_report(
        topic_name="Database Management",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ─── VIRTUAL WAREHOUSES ───────────────────────────────────────────────

def export_virtual_warehouses(account_name: str) -> str:
    top_kpis = []
    df_fleet = _safe_df("wh_fleet_data")
    if not df_fleet.empty:
        top_kpis.append({"value": str(len(df_fleet)), "label": "Active Warehouses"})
        if "WAREHOUSE_TYPE" in df_fleet.columns:
            top_kpis.append({"value": str(df_fleet["WAREHOUSE_TYPE"].nunique()), "label": "Warehouse Types"})
        if "WAREHOUSE_SIZE" in df_fleet.columns:
            top_kpis.append({"value": str(df_fleet["WAREHOUSE_SIZE"].nunique()), "label": "Size Variants"})

    sub_sections = []

    # --- Fleet Overview ---
    ov_charts = ""
    if not df_fleet.empty and "WAREHOUSE_SIZE" in df_fleet.columns:
        size_counts = df_fleet["WAREHOUSE_SIZE"].value_counts()
        ov_charts += '<div class="charts-row"><div class="chart-col">'
        ov_charts += build_chart("doughnut",
                                 labels=size_counts.index.tolist(),
                                 data=size_counts.values.tolist())
        ov_charts += "</div><div class='chart-col'>"

    df_cred = _safe_df("wh_credits_health")
    if not df_cred.empty:
        name_col = next((c for c in ["WAREHOUSE_NAME", "WH_NAME"] if c in df_cred.columns), None)
        cred_col = next((c for c in ["CREDITS_30_DAY", "TOTAL_CREDITS"] if c in df_cred.columns), None)
        if name_col and cred_col:
            top15 = df_cred.head(15)
            ov_charts += build_chart("hbar",
                                     labels=_trunc_labels(top15[name_col].tolist()),
                                     datasets=[{"label": "Credits (30d)", "data": [_num(v) for v in top15[cred_col].tolist()], "backgroundColor": _A}],
                                     title="Top 15 Warehouses by Credits (30d)", x_title="Credits")
    if not df_fleet.empty:
        ov_charts += "</div></div>"

    ov_tables = ""
    if not df_fleet.empty:
        show_cols = [c for c in ["WAREHOUSE_NAME", "WAREHOUSE_SIZE", "WAREHOUSE_TYPE", "AUTO_SUSPEND", "AUTO_RESUME", "MAX_CLUSTER_COUNT"] if c in df_fleet.columns]
        if show_cols:
            ov_tables = '<div class="section-subtitle">Warehouse Fleet</div>' + _df_table(df_fleet, show_cols)
    sub_sections.append(build_sub_section("Fleet Overview", kpis=top_kpis, charts_html=ov_charts, tables_html=ov_tables))

    # --- Credit Trends ---
    df_ts = _safe_df("wh_credit_ts_data")
    if not df_ts.empty:
        ts_charts = ""
        date_col = next((c for c in ["USAGE_DATE", "START_DATE"] if c in df_ts.columns), None)
        if date_col and "WAREHOUSE_NAME" in df_ts.columns:
            cred_col = next((c for c in ["COMPUTE_CREDITS", "CREDITS_USED", "TOTAL_CREDITS"] if c in df_ts.columns), None)
            if cred_col:
                pivot = df_ts.pivot_table(index=date_col, columns="WAREHOUSE_NAME", values=cred_col, aggfunc="sum").fillna(0)
                labels = [str(d) for d in pivot.index.tolist()]
                ds = []
                for i, wh in enumerate(pivot.columns[:10]):
                    ds.append({"label": str(wh), "data": [_num(v) for v in pivot[wh].tolist()],
                               "borderColor": _COLORS[i % len(_COLORS)], "fill": False})
                if ds:
                    ts_charts += build_chart("line", labels=labels, datasets=ds,
                                             title="Daily Credits by Warehouse", y_title="Credits")
        sub_sections.append(build_sub_section("Credit Trends", charts_html=ts_charts))

    # --- Heatmap / Hourly Activity ---
    df_heat = _safe_df("wh_heatmap_data")
    if not df_heat.empty:
        heat_cols = list(df_heat.columns)[:8]
        sub_sections.append(build_sub_section("Warehouse Heatmap", tables_html=_df_table(df_heat, heat_cols, limit=100)))

    # --- Scaling & Constraints ---
    df_const = _safe_df("wh_constraint_data")
    if not df_const.empty:
        sub_sections.append(build_sub_section("Scaling & Constraints", tables_html=_df_table(df_const, list(df_const.columns)[:8])))

    # --- Oversizing ---
    df_over = _safe_df("wh_oversizing_data")
    if not df_over.empty:
        sub_sections.append(build_sub_section("Oversizing Analysis", tables_html=_df_table(df_over, list(df_over.columns)[:8])))

    # --- Idle Warehouses ---
    df_idle = _safe_df("wh_idle_data")
    if not df_idle.empty:
        sub_sections.append(build_sub_section("Idle Warehouses", tables_html=_df_table(df_idle, list(df_idle.columns)[:8])))

    # --- Workload ---
    df_wl = _safe_df("wh_workload_data")
    if not df_wl.empty:
        sub_sections.append(build_sub_section("Workload Analysis", tables_html=_df_table(df_wl, list(df_wl.columns)[:8])))

    # --- Config Changes ---
    df_cc = _safe_df("wh_config_changes")
    if not df_cc.empty:
        sub_sections.append(build_sub_section("Configuration Changes", tables_html=_df_table(df_cc, list(df_cc.columns)[:8])))

    # --- Poor Pruning ---
    df_pp = _safe_df("wh_poor_pruning")
    if not df_pp.empty:
        sub_sections.append(build_sub_section("Poor Pruning Queries", tables_html=_df_table(df_pp, list(df_pp.columns)[:8])))

    return build_report(
        topic_name="Virtual Warehouses",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ─── ACCESS CONTROL ────────────────────────────────────────────────────

def export_access_control(account_name: str) -> str:
    top_kpis = []
    df_role = _safe_df("auth_role_hygiene")
    if not df_role.empty:
        r = df_role.iloc[0]
        for col, label in [("TOTAL_ROLES", "Total Roles"), ("CUSTOM_ROLES", "Custom Roles"),
                           ("ORPHAN_ROLES", "Orphan Roles"), ("ACTIVE_ROLES_60D", "Active Roles (60d)")]:
            if col in df_role.columns:
                top_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})

    df_users = _safe_df("auth_user_inventory")
    if not df_users.empty:
        r = df_users.iloc[0]
        for col, label in [("TOTAL_USERS", "Total Users"), ("ACTIVE_USERS_60D", "Active Users (60d)")]:
            if col in df_users.columns:
                top_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})

    sub_sections = []

    # --- Authorization ---
    auth_charts = ""
    df_grants = _safe_df("ac_role_grant_dist")
    if not df_grants.empty and "ROLE_NAME" in df_grants.columns:
        gc = next((c for c in ["TOTAL_GRANTS", "GRANT_COUNT"] if c in df_grants.columns), None)
        if gc:
            top15 = df_grants.head(15)
            auth_charts += build_chart("hbar",
                                       labels=_trunc_labels(top15["ROLE_NAME"].tolist()),
                                       datasets=[{"label": "Grants", "data": [int(v) for v in top15[gc].tolist()], "backgroundColor": _P}],
                                       title="Top Roles by Grant Count", x_title="Grants")
    auth_tables = ""
    df_priv = _safe_df("ac_privileged_access")
    if not df_priv.empty:
        auth_tables += '<div class="section-subtitle">Privileged Access</div>'
        auth_tables += _df_table(df_priv, ["USER_NAME", "PRIVILEGED_ROLE", "USER_TYPE", "DEFAULT_ROLE", "LAST_SUCCESS_LOGIN", "DAYS_SINCE_LOGIN", "RISK_LEVEL"])
    if not df_grants.empty:
        auth_tables += '<div class="section-subtitle">Role Grant Distribution</div>'
        auth_tables += _df_table(df_grants, list(df_grants.columns)[:7])
    sub_sections.append(build_sub_section("Authorization", charts_html=auth_charts, tables_html=auth_tables))

    # --- Security Hygiene ---
    df_sec = _safe_df("auth_security_hygiene")
    if not df_sec.empty:
        sec_kpis = []
        r = df_sec.iloc[0]
        for col, label in [("USERS_USING_PASSWORD", "Password Auth"), ("USERS_USING_OAUTH", "OAuth"),
                           ("USERS_USING_KEYPAIR", "Keypair"), ("UNHEALTHY_PASSWORD_NO_MFA", "Password No MFA")]:
            if col in df_sec.columns:
                sec_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})
        sec_charts = ""
        pw = int(r.get("USERS_USING_PASSWORD", 0) or 0)
        oauth = int(r.get("USERS_USING_OAUTH", 0) or 0)
        kp = int(r.get("USERS_USING_KEYPAIR", 0) or 0)
        if pw or oauth or kp:
            sec_charts = build_chart("doughnut", labels=["Password", "OAuth", "Keypair"], data=[pw, oauth, kp])
        sub_sections.append(build_sub_section("Security Hygiene", kpis=sec_kpis, charts_html=sec_charts))

    # --- Authentication ---
    df_auth = _safe_df("authn_auth_activity")
    if not df_auth.empty:
        sub_sections.append(build_sub_section("Authentication Activity", tables_html=_df_table(df_auth, list(df_auth.columns)[:7])))

    df_cred = _safe_df("authn_credential_hygiene")
    if not df_cred.empty:
        sub_sections.append(build_sub_section("Credential Hygiene", tables_html=_df_table(df_cred, list(df_cred.columns)[:4])))

    df_pol = _safe_df("authn_policy_audit")
    if not df_pol.empty:
        sub_sections.append(build_sub_section("Authentication Policies", tables_html=_df_table(df_pol, list(df_pol.columns)[:6])))

    df_prov = _safe_df("authn_provisioning_method")
    if not df_prov.empty:
        sub_sections.append(build_sub_section("Provisioning Methods", tables_html=_df_table(df_prov, list(df_prov.columns)[:3])))

    df_find = _safe_df("authn_findings")
    if not df_find.empty:
        sub_sections.append(build_sub_section("Security Findings", tables_html=_df_table(df_find, list(df_find.columns)[:6])))

    df_pat = _safe_df("ac_pat_users")
    if not df_pat.empty:
        sub_sections.append(build_sub_section("PAT Users", tables_html=_df_table(df_pat, list(df_pat.columns)[:6])))

    df_own = _safe_df("auth_object_ownership")
    if not df_own.empty:
        sub_sections.append(build_sub_section("Object Ownership", tables_html=_df_table(df_own, list(df_own.columns)[:3])))

    # --- Network Policies ---
    df_net_sum = _safe_df("ac_net_policy_summary")
    net_kpis = []
    if not df_net_sum.empty:
        r = df_net_sum.iloc[0]
        for col, label in [("TOTAL_POLICIES", "Total Policies"), ("ACTIVE_POLICIES", "Active"),
                           ("ACCOUNT_LEVEL_POLICIES", "Account-Level"), ("USERS_WITH_POLICIES", "Users with Policies")]:
            if col in df_net_sum.columns:
                net_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})

    net_tables = ""
    df_net = _safe_df("net_policies_data")
    if not df_net.empty:
        net_tables += '<div class="section-subtitle">Network Policies</div>' + _df_table(df_net, list(df_net.columns)[:5])
    df_dang = _safe_df("ac_dangling_net_policies")
    if not df_dang.empty:
        net_tables += '<div class="section-subtitle">Dangling Network Policies</div>' + _df_table(df_dang, list(df_dang.columns)[:5])
    df_cov = _safe_df("ac_user_net_coverage")
    if not df_cov.empty:
        net_tables += '<div class="section-subtitle">User Network Coverage</div>' + _df_table(df_cov, list(df_cov.columns)[:3])
    df_rules = _safe_df("net_rules_data")
    if not df_rules.empty:
        net_tables += '<div class="section-subtitle">Network Rules</div>' + _df_table(df_rules, list(df_rules.columns)[:7])
    sub_sections.append(build_sub_section("Network Policies", kpis=net_kpis, tables_html=net_tables))

    return build_report(
        topic_name="Access Control",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ─── DATA INGESTION ────────────────────────────────────────────────────

def export_data_ingestion(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    df_summary = _safe_df("ingestion_summary_data")
    if not df_summary.empty:
        for _, row in df_summary.iterrows():
            method = row.get("INGESTION_METHOD", "")
            gb = row.get("TOTAL_GB", 0)
            top_kpis.append({"value": f"{_fmt_num(gb)} GB", "label": str(method)})

        sum_charts = ""
        if "INGESTION_METHOD" in df_summary.columns and "TOTAL_GB" in df_summary.columns:
            sum_charts += '<div class="charts-row"><div class="chart-col">'
            sum_charts += build_chart("doughnut",
                                      labels=df_summary["INGESTION_METHOD"].tolist(),
                                      data=[_num(v) for v in df_summary["TOTAL_GB"].tolist()])
            sum_charts += "</div><div class='chart-col'>"
            sum_charts += build_chart("vbar",
                                      labels=df_summary["INGESTION_METHOD"].tolist(),
                                      datasets=[{"label": "GB", "data": [_num(v) for v in df_summary["TOTAL_GB"].tolist()], "backgroundColor": _P}],
                                      title="Data Loaded by Method (GB)", y_title="GB")
            sum_charts += "</div></div>"
        sub_sections.append(build_sub_section("Ingestion Summary", charts_html=sum_charts))

    # --- Bulk Load ---
    df_bulk = _safe_df("ig_bulk_load")
    if not df_bulk.empty:
        sub_sections.append(build_sub_section("Bulk Load (COPY INTO)", tables_html=_df_table(df_bulk, list(df_bulk.columns)[:8])))

    # --- Snowpipe ---
    df_pipe = _safe_df("ig_pipe_efficiency")
    if not df_pipe.empty:
        sub_sections.append(build_sub_section("Snowpipe Efficiency", tables_html=_df_table(df_pipe, list(df_pipe.columns)[:8])))

    df_detail = _safe_df("ig_snowpipe_detail")
    if not df_detail.empty:
        sub_sections.append(build_sub_section("Snowpipe Detail", tables_html=_df_table(df_detail, list(df_detail.columns)[:8])))

    df_cost = _safe_df("ig_pipe_cost_projection")
    if not df_cost.empty:
        sub_sections.append(build_sub_section("Snowpipe Cost Projection", tables_html=_df_table(df_cost, list(df_cost.columns)[:8])))

    # --- Streaming ---
    df_stream = _safe_df("ingestion_streaming_data")
    if not df_stream.empty:
        s_kpis = []
        date_col = next((c for c in ["USAGE_DATE", "START_DATE"] if c in df_stream.columns), None)
        cred_col = next((c for c in ["CREDITS_USED", "TOTAL_CREDITS"] if c in df_stream.columns), None)
        if cred_col:
            s_kpis.append({"value": f"{_fmt_num(df_stream[cred_col].sum(), 2)}", "label": "Total Streaming Credits (30d)"})
        ch = ""
        if date_col and cred_col:
            ch = build_chart("vbar",
                             labels=[str(d) for d in df_stream[date_col].tolist()],
                             datasets=[{"label": "Credits", "data": [_num(v) for v in df_stream[cred_col].tolist()], "backgroundColor": _P}],
                             title="Streaming Daily Credits", y_title="Credits")
        sub_sections.append(build_sub_section("Snowpipe Streaming", kpis=s_kpis, charts_html=ch))

    df_brk = _safe_df("ingestion_streaming_breakdown")
    if not df_brk.empty:
        sub_sections.append(build_sub_section("Streaming Breakdown", tables_html=_df_table(df_brk, list(df_brk.columns)[:8])))

    return build_report(
        topic_name="Data Ingestion",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ─── DATA TRANSFORMATION ──────────────────────────────────────────────

def export_data_transformation(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    df_ov = _safe_df("tf_overview")
    if not df_ov.empty:
        r = df_ov.iloc[0]
        for col, label in [("CLUSTERED_TABLES", "Clustered Tables"), ("UNCLUSTERED_TABLES", "Unclustered"),
                           ("NUM_MATERIALIZED_VIEWS", "Materialized Views"), ("NUM_DYNAMIC_TABLES", "Dynamic Tables"),
                           ("NUM_WAREHOUSES_SPILL_OR_QUEUE_LAST_30D", "Spill/Queue Issues"),
                           ("NUM_SHORT_UPSERTS_LAST_30D", "Short Upserts (30d)"),
                           ("NUM_SNOWPARK_QUERIES_LAST_30D", "Snowpark Queries (30d)")]:
            if col in df_ov.columns:
                top_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})

    # --- Problematic Queries ---
    df_prob = _safe_df("tf_problematic_queries")
    if not df_prob.empty:
        prob_charts = ""
        if "CATEGORY" in df_prob.columns and "OCCURRENCE_COUNT" in df_prob.columns:
            cat_counts = df_prob.groupby("CATEGORY")["OCCURRENCE_COUNT"].sum().sort_values(ascending=False)
            prob_charts = build_chart("hbar",
                                     labels=cat_counts.index.tolist(),
                                     datasets=[{"label": "Occurrences", "data": [int(v) for v in cat_counts.values.tolist()], "backgroundColor": _A}],
                                     title="Problematic Query Categories", x_title="Count")
        sub_sections.append(build_sub_section("Problematic Queries", charts_html=prob_charts,
                                              tables_html=_df_table(df_prob, list(df_prob.columns)[:5])))

    df_cat = _safe_df("tf_category_summary")
    if not df_cat.empty:
        sub_sections.append(build_sub_section("Category Summary", tables_html=_df_table(df_cat, list(df_cat.columns)[:4])))

    # --- Syntax Hunter ---
    df_syn = _safe_df("tf_syntax_hunter")
    if not df_syn.empty:
        sub_sections.append(build_sub_section("Syntax Hunter", tables_html=_df_table(df_syn, list(df_syn.columns)[:7])))

    df_freq = _safe_df("tf_syntax_frequency")
    if not df_freq.empty:
        freq_chart = ""
        if "DETECTION_TYPE" in df_freq.columns and "OCCURRENCE_COUNT" in df_freq.columns:
            freq_chart = build_chart("hbar",
                                     labels=df_freq["DETECTION_TYPE"].tolist(),
                                     datasets=[{"label": "Count", "data": [int(v) for v in df_freq["OCCURRENCE_COUNT"].tolist()], "backgroundColor": _P}],
                                     title="Syntax Detection Frequency", x_title="Count")
        sub_sections.append(build_sub_section("Syntax Frequency", charts_html=freq_chart))

    # --- Object Structure ---
    df_view = _safe_df("tf_view_dependency")
    if not df_view.empty:
        sub_sections.append(build_sub_section("View Dependencies", tables_html=_df_table(df_view, list(df_view.columns)[:3])))

    df_lc = _safe_df("tf_lifecycle")
    if not df_lc.empty:
        sub_sections.append(build_sub_section("Object Lifecycle", tables_html=_df_table(df_lc, list(df_lc.columns)[:4])))

    df_summ = _safe_df("tf_summary")
    if not df_summ.empty:
        summ_chart = ""
        if "METRIC_NAME" in df_summ.columns and "COUNT_OBJECTS" in df_summ.columns:
            summ_chart = build_chart("hbar",
                                     labels=df_summ["METRIC_NAME"].tolist(),
                                     datasets=[{"label": "Count", "data": [int(v) for v in df_summ["COUNT_OBJECTS"].tolist()], "backgroundColor": _P}],
                                     title="Object Summary", x_title="Count")
        sub_sections.append(build_sub_section("Object Summary", charts_html=summ_chart))

    # --- Workload Shape ---
    df_wl = _safe_df("tf_workload_shape")
    if not df_wl.empty:
        sub_sections.append(build_sub_section("Workload Shape", tables_html=_df_table(df_wl, list(df_wl.columns)[:4])))

    df_rap = _safe_df("tf_rap_query")
    if not df_rap.empty:
        sub_sections.append(build_sub_section("Row Access Policy Impact", tables_html=_df_table(df_rap, list(df_rap.columns)[:4])))

    df_mv = _safe_df("tf_mv_refresh_cost")
    if not df_mv.empty:
        sub_sections.append(build_sub_section("Materialized View Refresh Cost", tables_html=_df_table(df_mv, list(df_mv.columns)[:4])))

    df_perf = _safe_df("tf_perf_insights")
    if not df_perf.empty:
        sub_sections.append(build_sub_section("Performance Insights", tables_html=_df_table(df_perf, list(df_perf.columns)[:3])))

    # --- Object Lifecycle (DT) ---
    df_dtl = _safe_df("dt_object_lifecycle")
    if not df_dtl.empty:
        sub_sections.append(build_sub_section("Dynamic Table Lifecycle", tables_html=_df_table(df_dtl, list(df_dtl.columns)[:3])))

    df_micro = _safe_df("dt_micro_tx")
    if not df_micro.empty:
        sub_sections.append(build_sub_section("Micro-Transactions (Short Upserts)", tables_html=_df_table(df_micro, list(df_micro.columns)[:6])))

    return build_report(
        topic_name="Data Transformation",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ─── FINOPS (LITE) ─────────────────────────────────────────────────────

def export_finops(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    # --- Visibility ---
    df_fc = _safe_df("finops_exec_forecast")
    if not df_fc.empty:
        for _, row in df_fc.iterrows():
            cat = row.get("Category", "")
            actual = row.get("Actual Cost (Last 30 Days)", 0)
            if cat:
                top_kpis.append({"value": f"${_fmt_num(actual)}", "label": str(cat)})
        fc_tables = _df_table(df_fc, list(df_fc.columns)[:6])
        sub_sections.append(build_sub_section("Executive Forecast", tables_html=fc_tables))

    df_cb = _safe_df("finops_compute_breakdown")
    if not df_cb.empty:
        cb_charts = ""
        svc_col = next((c for c in ["Service Type", "SERVICE_TYPE"] if c in df_cb.columns), None)
        cred_col = next((c for c in ["Credits (Last 30 Days)", "CREDITS_USED", "TOTAL_CREDITS"] if c in df_cb.columns), None)
        if svc_col and cred_col:
            top15 = df_cb.head(15)
            cb_charts = build_chart("hbar",
                                    labels=_trunc_labels(top15[svc_col].tolist()),
                                    datasets=[{"label": "Credits", "data": [_num(v) for v in top15[cred_col].tolist()], "backgroundColor": _A}],
                                    title="Top Compute Consumers", x_title="Credits")
        sub_sections.append(build_sub_section("Compute Breakdown", charts_html=cb_charts, tables_html=_df_table(df_cb, list(df_cb.columns)[:6])))

    df_cq = _safe_df("finops_costliest_queries")
    if not df_cq.empty:
        sub_sections.append(build_sub_section("Costliest Queries", tables_html=_df_table(df_cq, list(df_cq.columns)[:5], limit=20)))

    df_sc = _safe_df("finops_storage_costs")
    if not df_sc.empty:
        sub_sections.append(build_sub_section("Storage Costs", tables_html=_df_table(df_sc, list(df_sc.columns)[:6])))

    df_dt = _safe_df("finops_data_transfer")
    if not df_dt.empty:
        sub_sections.append(build_sub_section("Data Transfer", tables_html=_df_table(df_dt, list(df_dt.columns)[:3])))

    df_anom = _safe_df("finops_anomalies")
    if not df_anom.empty:
        anom_chart = ""
        date_col = next((c for c in ["Anomaly Date", "ANOMALY_DATE"] if c in df_anom.columns), None)
        overspend_col = next((c for c in ["Overspend ($)", "OVERSPEND"] if c in df_anom.columns), None)
        if date_col and overspend_col:
            anom_chart = build_chart("vbar",
                                     labels=[str(d) for d in df_anom[date_col].tolist()],
                                     datasets=[{"label": "Overspend ($)", "data": [_num(v) for v in df_anom[overspend_col].tolist()], "backgroundColor": _A}],
                                     title="Cost Anomalies", y_title="Overspend ($)")
        sub_sections.append(build_sub_section("Cost Anomalies", charts_html=anom_chart, tables_html=_df_table(df_anom, list(df_anom.columns)[:7])))

    df_dct = _safe_df("fv_daily_cost_trend")
    if not df_dct.empty:
        dct_chart = ""
        date_col = next((c for c in ["Date", "DATE"] if c in df_dct.columns), None)
        cost_col = next((c for c in ["Total Cost ($)", "TOTAL_COST"] if c in df_dct.columns), None)
        avg_col = next((c for c in ["7-Day Rolling Avg ($)", "ROLLING_7D_AVG_COST"] if c in df_dct.columns), None)
        if date_col and cost_col:
            datasets = [{"label": "Daily Cost ($)", "data": [_num(v) for v in df_dct[cost_col].tolist()], "backgroundColor": _P}]
            if avg_col:
                datasets.append({"label": "7-Day Avg ($)", "data": [_num(v) for v in df_dct[avg_col].tolist()], "borderColor": _A, "type": "line", "fill": False})
            dct_chart = build_chart("vbar",
                                    labels=[str(d)[:10] for d in df_dct[date_col].tolist()],
                                    datasets=datasets,
                                    title="Daily Cost Trend (30 Days)", y_title="Cost ($)")
        sub_sections.append(build_sub_section("Daily Cost Trend", charts_html=dct_chart, tables_html=_df_table(df_dct, list(df_dct.columns)[:6])))

    df_stb = _safe_df("fv_service_type_breakdown")
    if not df_stb.empty:
        stb_chart = ""
        svc_col = next((c for c in ["Service Type", "SERVICE_TYPE"] if c in df_stb.columns), None)
        cost_col = next((c for c in ["Total Cost ($)", "TOTAL_COST_USD"] if c in df_stb.columns), None)
        if svc_col and cost_col:
            stb_chart = build_chart("doughnut",
                                    labels=df_stb[svc_col].tolist(),
                                    datasets=[{"data": [_num(v) for v in df_stb[cost_col].tolist()]}],
                                    title="Cost by Service Type")
        sub_sections.append(build_sub_section("Service Type Breakdown", charts_html=stb_chart, tables_html=_df_table(df_stb, list(df_stb.columns)[:5])))

    # --- Control ---
    df_rm = _safe_df("fc_resource_monitors")
    if not df_rm.empty:
        sub_sections.append(build_sub_section("Resource Monitors", tables_html=_df_table(df_rm, list(df_rm.columns)[:8])))

    df_risk = _safe_df("fc_risk_analysis")
    if not df_risk.empty:
        sub_sections.append(build_sub_section("Risk Analysis", tables_html=_df_table(df_risk, list(df_risk.columns)[:4])))

    df_budg = _safe_df("fc_budget_inventory")
    if not df_budg.empty:
        sub_sections.append(build_sub_section("Budget Inventory", tables_html=_df_table(df_budg, list(df_budg.columns)[:6])))

    df_butil = _safe_df("fc_budget_util")
    if not df_butil.empty:
        sub_sections.append(build_sub_section("Budget Utilization", tables_html=_df_table(df_butil, list(df_butil.columns)[:6])))

    df_proj = _safe_df("fc_projection")
    if not df_proj.empty:
        sub_sections.append(build_sub_section("Budget Projection", tables_html=_df_table(df_proj, list(df_proj.columns)[:7])))

    df_whnc = _safe_df("fc_wh_without_controls")
    if not df_whnc.empty:
        sub_sections.append(build_sub_section("Warehouses Without Controls", tables_html=_df_table(df_whnc, list(df_whnc.columns)[:3])))

    df_ml = _safe_df("fc_monitors_limits")
    if not df_ml.empty:
        sub_sections.append(build_sub_section("Monitor Limits", tables_html=_df_table(df_ml, list(df_ml.columns)[:8])))

    df_sto = _safe_df("fc_statement_timeouts")
    if not df_sto.empty:
        sub_sections.append(build_sub_section("Statement Timeouts", tables_html=_df_table(df_sto, list(df_sto.columns)[:7])))

    df_aon = _safe_df("fc_always_on_wh")
    if not df_aon.empty:
        sub_sections.append(build_sub_section("Always-On Warehouses", tables_html=_df_table(df_aon, list(df_aon.columns)[:5])))

    df_idl = _safe_df("fc_idle_time")
    if not df_idl.empty:
        idle_chart = ""
        if "WAREHOUSE_NAME" in df_idl.columns and "IDLE_PERCENT" in df_idl.columns:
            top15 = df_idl.head(15)
            idle_chart = build_chart("hbar",
                                     labels=_trunc_labels(top15["WAREHOUSE_NAME"].tolist()),
                                     datasets=[{"label": "Idle %", "data": [_num(v, 1) for v in top15["IDLE_PERCENT"].tolist()], "backgroundColor": _A}],
                                     title="Idle Time by Warehouse", x_title="Idle %")
        sub_sections.append(build_sub_section("Idle Time Analysis", charts_html=idle_chart, tables_html=_df_table(df_idl, list(df_idl.columns)[:6])))

    df_rmg = _safe_df("fc_rm_coverage_gap")
    if not df_rmg.empty:
        sub_sections.append(build_sub_section("Resource Monitor Coverage Gaps", tables_html=_df_table(df_rmg, list(df_rmg.columns)[:3])))

    df_wow = _safe_df("fc_wow_cost_trend")
    if not df_wow.empty:
        sub_sections.append(build_sub_section("Week-over-Week Cost Trend", tables_html=_df_table(df_wow, list(df_wow.columns)[:6])))

    df_spend = _safe_df("fc_spending_summary")
    if not df_spend.empty:
        sub_sections.append(build_sub_section("Spending Summary", tables_html=_df_table(df_spend, list(df_spend.columns)[:6])))

    df_mt = _safe_df("fc_monthly_trend")
    if not df_mt.empty:
        mt_chart = ""
        if "MONTH" in df_mt.columns and "MONTHLY_CREDITS" in df_mt.columns:
            mt_chart = build_chart("vbar",
                                   labels=[str(d) for d in df_mt["MONTH"].tolist()],
                                   datasets=[{"label": "Credits", "data": [_num(v) for v in df_mt["MONTHLY_CREDITS"].tolist()], "backgroundColor": _P}],
                                   title="Monthly Credit Trend", y_title="Credits")
        sub_sections.append(build_sub_section("Monthly Trend", charts_html=mt_chart))

    df_svl = _safe_df("fc_serverless_costs")
    if not df_svl.empty:
        sub_sections.append(build_sub_section("Serverless Costs", tables_html=_df_table(df_svl, list(df_svl.columns)[:4])))

    df_stc = _safe_df("fc_storage_costs")
    if not df_stc.empty:
        sub_sections.append(build_sub_section("Storage Trend", tables_html=_df_table(df_stc, list(df_stc.columns)[:2])))

    df_spcs = _safe_df("fc_spcs_credits")
    if not df_spcs.empty:
        sub_sections.append(build_sub_section("SPCS Credits", tables_html=_df_table(df_spcs, list(df_spcs.columns)[:2])))

    # --- Optimization ---
    df_ddl = _safe_df("fo_ddl")
    if not df_ddl.empty:
        ddl_kpis = []
        r = df_ddl.iloc[0]
        for col, label in [("TOTAL_DDL_30D", "DDL Operations (30d)"), ("DISTINCT_DDL_PATTERNS_30D", "Distinct DDL Patterns")]:
            if col in df_ddl.columns:
                ddl_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})
        ddl_tables = ""
        df_tddl = _safe_df("fo_top_ddl")
        if not df_tddl.empty:
            ddl_tables = _df_table(df_tddl, list(df_tddl.columns)[:4])
        sub_sections.append(build_sub_section("DDL Overhead", kpis=ddl_kpis, tables_html=ddl_tables))

    df_cln = _safe_df("fo_clone_summary")
    if not df_cln.empty:
        cln_tables = ""
        df_tc = _safe_df("fo_top_clone")
        if not df_tc.empty:
            cln_tables = _df_table(df_tc, list(df_tc.columns)[:4])
        sub_sections.append(build_sub_section("Clone Overhead", tables_html=cln_tables))

    df_sq = _safe_df("fo_simple_queries")
    if not df_sq.empty:
        sub_sections.append(build_sub_section("Simple Queries", tables_html=_df_table(df_sq, list(df_sq.columns)[:6])))

    df_is = _safe_df("fo_info_schema")
    if not df_is.empty:
        sub_sections.append(build_sub_section("Information Schema Queries", tables_html=_df_table(df_is, list(df_is.columns)[:5])))

    df_show = _safe_df("fo_show_commands")
    if not df_show.empty:
        sub_sections.append(build_sub_section("SHOW Commands", tables_html=_df_table(df_show, list(df_show.columns)[:5])))

    df_sri = _safe_df("fo_single_row_inserts")
    if not df_sri.empty:
        sub_sections.append(build_sub_section("Single Row Inserts", tables_html=_df_table(df_sri, list(df_sri.columns)[:5])))

    df_cx = _safe_df("fo_complex_queries")
    if not df_cx.empty:
        sub_sections.append(build_sub_section("Complex Queries", tables_html=_df_table(df_cx, list(df_cx.columns)[:7])))

    df_cp = _safe_df("fo_summary")
    if not df_cp.empty:
        sub_sections.append(build_sub_section("COPY Pattern Summary", tables_html=_df_table(df_cp, list(df_cp.columns)[:3])))

    df_pat = _safe_df("fo_patterns")
    if not df_pat.empty:
        sub_sections.append(build_sub_section("COPY Patterns", tables_html=_df_table(df_pat, list(df_pat.columns)[:7])))

    df_cs = _safe_df("fo_cloud_svcs_overhead")
    if not df_cs.empty:
        cs_chart = ""
        if "PATTERN" in df_cs.columns and "CLOUD_SERVICES_CREDITS_30D" in df_cs.columns:
            cs_chart = build_chart("hbar",
                                   labels=_trunc_labels(df_cs["PATTERN"].tolist()),
                                   datasets=[{"label": "Credits", "data": [_num(v) for v in df_cs["CLOUD_SERVICES_CREDITS_30D"].tolist()], "backgroundColor": _A}],
                                   title="Cloud Services Overhead", x_title="Credits")
        sub_sections.append(build_sub_section("Cloud Services Overhead", charts_html=cs_chart, tables_html=_df_table(df_cs, list(df_cs.columns)[:3])))

    return build_report(
        topic_name="FinOps (lite)",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ─── DATA GOVERNANCE ───────────────────────────────────────────────────

def export_data_governance(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    df_health = _safe_df("dg_health_score_data")
    if not df_health.empty:
        total_tbl = int(df_health["TOTAL_TABLES"].sum()) if "TOTAL_TABLES" in df_health.columns else 0
        tagged_tbl = int(df_health["TAGGED_TABLES"].sum()) if "TAGGED_TABLES" in df_health.columns else 0
        untagged = total_tbl - tagged_tbl
        pct = round(tagged_tbl / total_tbl * 100, 1) if total_tbl > 0 else 0
        top_kpis = [
            {"value": _fmt_num(total_tbl, 0), "label": "Total Tables"},
            {"value": _fmt_num(tagged_tbl, 0), "label": "Tagged Tables"},
            {"value": _fmt_num(untagged, 0), "label": "Untagged Tables"},
            {"value": f"{pct}%", "label": "Tag Coverage"},
        ]
        health_charts = ""
        if tagged_tbl or untagged:
            health_charts += '<div class="charts-row"><div class="chart-col">'
            health_charts += build_chart("doughnut", labels=["Tagged", "Untagged"], data=[tagged_tbl, untagged], colors=[_P, _A])
            health_charts += "</div><div class='chart-col'>"
        if "DATABASE_NAME" in df_health.columns and "COVERAGE_PCT" in df_health.columns:
            top10 = df_health.head(10)
            health_charts += build_chart("hbar",
                                         labels=_trunc_labels(top10["DATABASE_NAME"].tolist()),
                                         datasets=[{"label": "Coverage %", "data": [_num(v, 1) for v in top10["COVERAGE_PCT"].tolist()], "backgroundColor": _P}],
                                         title="Tag Coverage by Database", x_title="%")
        if tagged_tbl or untagged:
            health_charts += "</div></div>"
        hs_tables = _df_table(df_health, list(df_health.columns)[:5])
        sub_sections.append(build_sub_section("Governance Health Score", kpis=top_kpis, charts_html=health_charts, tables_html=hs_tables))

    # --- Classification ---
    df_class = _safe_df("dg_classification_data")
    if not df_class.empty:
        cls_chart = ""
        if "APPLY_METHOD" in df_class.columns and "TOTAL_TAGS" in df_class.columns:
            cls_chart = build_chart("vbar",
                                    labels=df_class["APPLY_METHOD"].tolist(),
                                    datasets=[{"label": "Tags", "data": [int(v) for v in df_class["TOTAL_TAGS"].tolist()], "backgroundColor": _P}],
                                    title="Tags by Apply Method", y_title="Count")
        sub_sections.append(build_sub_section("Classification Overview", charts_html=cls_chart, tables_html=_df_table(df_class, list(df_class.columns)[:3])))

    # --- Sensitivity Heatmap ---
    df_heat = _safe_df("dg_sensitivity_heatmap")
    if not df_heat.empty:
        heat_chart = ""
        if "SENSITIVITY_LEVEL" in df_heat.columns and "OBJECT_COUNT" in df_heat.columns:
            heat_chart = build_chart("hbar",
                                     labels=df_heat["SENSITIVITY_LEVEL"].tolist(),
                                     datasets=[{"label": "Objects", "data": [int(v) for v in df_heat["OBJECT_COUNT"].tolist()], "backgroundColor": _A}],
                                     title="Sensitivity Distribution", x_title="Objects")
        sub_sections.append(build_sub_section("Sensitivity Heatmap", charts_html=heat_chart))

    # --- Policy Inventory ---
    df_pol = _safe_df("dg_policy_inventory_data")
    if not df_pol.empty:
        pol_chart = ""
        if "POLICY_KIND" in df_pol.columns and "ACTIVE_COUNT" in df_pol.columns:
            pol_chart = build_chart("hbar",
                                    labels=df_pol["POLICY_KIND"].tolist(),
                                    datasets=[{"label": "Count", "data": [int(v) for v in df_pol["ACTIVE_COUNT"].tolist()], "backgroundColor": _P}],
                                    title="Policies by Type", x_title="Count")
        sub_sections.append(build_sub_section("Policy Inventory", charts_html=pol_chart, tables_html=_df_table(df_pol, list(df_pol.columns)[:2])))

    # --- Tagging ---
    df_tag = _safe_df("dg_tagging_audit_data")
    if not df_tag.empty:
        sub_sections.append(build_sub_section("Tagging Audit", tables_html=_df_table(df_tag, list(df_tag.columns)[:7])))

    df_sens = _safe_df("dg_sensitive_tagged")
    if not df_sens.empty:
        sub_sections.append(build_sub_section("Sensitive Tagged Columns", tables_html=_df_table(df_sens, list(df_sens.columns)[:7])))

    df_stale = _safe_df("dg_stale_tagged")
    if not df_stale.empty:
        sub_sections.append(build_sub_section("Stale Tagged Objects", tables_html=_df_table(df_stale, list(df_stale.columns)[:7])))

    df_dang = _safe_df("dg_dangling_tags")
    if not df_dang.empty:
        sub_sections.append(build_sub_section("Dangling Tags", tables_html=_df_table(df_dang, list(df_dang.columns)[:8])))

    df_heavy = _safe_df("dg_heavy_column_tagging")
    if not df_heavy.empty:
        sub_sections.append(build_sub_section("Heavy Column Tagging", tables_html=_df_table(df_heavy, list(df_heavy.columns)[:6])))

    df_noav = _safe_df("dg_tags_no_allowed_values")
    if not df_noav.empty:
        sub_sections.append(build_sub_section("Tags Without Allowed Values", tables_html=_df_table(df_noav, list(df_noav.columns)[:6])))

    df_share = _safe_df("dg_share_tag")
    if not df_share.empty:
        sub_sections.append(build_sub_section("Shared Tags", tables_html=_df_table(df_share, list(df_share.columns)[:8])))

    # --- Privacy & Protection ---
    df_rap = _safe_df("dg_rap")
    if not df_rap.empty:
        sub_sections.append(build_sub_section("Row Access Policies", tables_html=_df_table(df_rap, list(df_rap.columns)[:7])))

    df_unprot = _safe_df("dg_unprotected")
    if not df_unprot.empty:
        sub_sections.append(build_sub_section("Unprotected Tables", tables_html=_df_table(df_unprot, list(df_unprot.columns)[:3])))

    df_mask = _safe_df("dg_masking_coverage")
    if not df_mask.empty:
        sub_sections.append(build_sub_section("Masking Coverage", tables_html=_df_table(df_mask, list(df_mask.columns)[:7])))

    df_dpol = _safe_df("dg_dangling_policies")
    if not df_dpol.empty:
        sub_sections.append(build_sub_section("Dangling Policies", tables_html=_df_table(df_dpol, list(df_dpol.columns)[:8])))

    df_mdes = _safe_df("dg_masking_design")
    if not df_mdes.empty:
        sub_sections.append(build_sub_section("Masking Policy Design", tables_html=_df_table(df_mdes, list(df_mdes.columns)[:6])))

    df_down = _safe_df("dg_downstream_unmasked")
    if not df_down.empty:
        sub_sections.append(build_sub_section("Downstream Unmasked", tables_html=_df_table(df_down, list(df_down.columns)[:7])))

    df_saccess = _safe_df("dg_sensitive_access")
    if not df_saccess.empty:
        sub_sections.append(build_sub_section("Sensitive Data Access", tables_html=_df_table(df_saccess, list(df_saccess.columns)[:3])))

    df_deps = _safe_df("dg_downstream_deps")
    if not df_deps.empty:
        sub_sections.append(build_sub_section("Downstream Dependencies", tables_html=_df_table(df_deps, list(df_deps.columns)[:8])))

    return build_report(
        topic_name="Data Governance",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ─── DATA RECOVERY & DEVOPS ───────────────────────────────────────────

def export_recovery_devops(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    for key, label in [("devops_git_count", "Git Users"), ("devops_cicd_count", "CI/CD Users"),
                       ("devops_dt_count", "Dynamic Tables"), ("devops_task_count", "Task Executions")]:
        df = _safe_df(key)
        if not df.empty:
            val = df.iloc[0, 0] if len(df.columns) > 0 else 0
            top_kpis.append({"value": _fmt_num(val, 0), "label": label})

    # --- Combined Overview ---
    df_combined = _safe_df("devops_combined")
    if not df_combined.empty:
        sub_sections.append(build_sub_section("DevOps Overview", tables_html=_df_table(df_combined, list(df_combined.columns)[:6])))

    # --- DCM Adoption ---
    df_dcm = _safe_df("rd_dcm_adoption")
    if not df_dcm.empty:
        sub_sections.append(build_sub_section("Database Change Management (DCM)", tables_html=_df_table(df_dcm, list(df_dcm.columns)[:6])))

    # --- Git Integration ---
    df_git = _safe_df("rd_git_integration")
    if not df_git.empty:
        sub_sections.append(build_sub_section("Git Integration", tables_html=_df_table(df_git, list(df_git.columns)[:6])))

    # --- CI/CD Automation ---
    df_cicd = _safe_df("rd_cicd_automation")
    if not df_cicd.empty:
        sub_sections.append(build_sub_section("CI/CD Automation", tables_html=_df_table(df_cicd, list(df_cicd.columns)[:6])))

    # --- Declarative Pipelines ---
    df_pipe = _safe_df("rd_declarative_pipeline")
    if not df_pipe.empty:
        sub_sections.append(build_sub_section("Declarative Pipelines", tables_html=_df_table(df_pipe, list(df_pipe.columns)[:6])))

    return build_report(
        topic_name="Data Recovery & DevOps",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


TOPIC_EXPORTERS = {
    "Database Management": export_database_management,
    "Virtual Warehouses": export_virtual_warehouses,
    "Access Control": export_access_control,
    "Data Ingestion": export_data_ingestion,
    "Data Transformation": export_data_transformation,
    "FinOps (lite)": export_finops,
    "Data Governance": export_data_governance,
    "Data Recovery & DevOps": export_recovery_devops,
}

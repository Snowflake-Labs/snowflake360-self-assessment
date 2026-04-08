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


def export_database_management(account_name: str) -> str:
    from components.Database_Management._db_queries import ALL_DB_OVERVIEW_QUERIES
    from components.Database_Management.db_overview import _query_cache

    def _qc(key):
        df = _query_cache.get(key)
        if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
            return df
        return _safe_df(key)

    top_kpis = []
    df_stor = _qc("db_overview_1_total_storage_query")
    if not df_stor.empty:
        r = df_stor.iloc[0]
        for col, label in [("TOTAL_STORAGE_TB","Total Storage"), ("ACTIVE_TB","Active"),
                           ("TIME_TRAVEL_TB","Time Travel"), ("FAILSAFE_TB","Failsafe"),
                           ("CLONE_RETAINED_TB","Clone Retained")]:
            if col in df_stor.columns:
                top_kpis.append({"value": f"{_fmt_num(r.get(col))} TB", "label": label})

    sub_sections = []

    ov_kpis = list(top_kpis)
    df_sum = _qc("db_overview_2_storage_summary_query")
    if not df_sum.empty:
        r = df_sum.iloc[0]
        for col, label in [("DATABASE_COUNT","Databases"), ("TABLE_COUNT","Tables")]:
            if col in df_sum.columns:
                ov_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})

    ov_charts = ""
    df_obj = _qc("db_overview_14_object_count_query")
    if not df_obj.empty and "OBJECT_TYPE" in df_obj.columns and "OBJ_COUNT" in df_obj.columns:
        ov_charts += '<div class="charts-row"><div class="chart-col">'
        ov_charts += build_chart("hbar",
                                 labels=_trunc_labels(df_obj["OBJECT_TYPE"].tolist()),
                                 datasets=[{"label": "Count", "data": df_obj["OBJ_COUNT"].tolist(), "backgroundColor": _P}],
                                 title="Object Counts", x_title="Count")
        ov_charts += "</div></div>"

    sub_sections.append(build_sub_section("Overview", kpis=ov_kpis, charts_html=ov_charts))

    ds_kpis = []
    if not df_sum.empty:
        r = df_sum.iloc[0]
        for col, label in [("TOTAL_STORAGE_TB","Total Storage"), ("ACTIVE_STORAGE_TB","Active Storage"),
                           ("DATABASE_COUNT","Databases"), ("TABLE_COUNT","Tables")]:
            if col in df_sum.columns:
                suf = " TB" if "TB" in col else ""
                ds_kpis.append({"value": f"{_fmt_num(r.get(col), 2 if 'TB' in col else 0)}{suf}", "label": label})

    ds_charts = ""
    df_top = _qc("db_overview_4_top_tables_query")
    if not df_top.empty:
        top_n = df_top.head(30)
        lbl_col = None
        for c in ["TABLE_FQN", "TABLE_NAME"]:
            if c in top_n.columns:
                lbl_col = c
                break
        if lbl_col:
            labels = _trunc_labels(top_n[lbl_col].tolist())
            ds_list = []
            for col, clbl, clr in [("ACTIVE_GB","Active GB",_P), ("TIME_TRAVEL_GB","Time Travel GB",_S), ("FAILSAFE_GB","Failsafe GB",_A)]:
                if col in top_n.columns:
                    ds_list.append({"label": clbl, "data": [round(float(v), 2) for v in top_n[col].tolist()], "backgroundColor": clr})
            if ds_list:
                ds_charts += build_chart("hbar", labels=labels, datasets=ds_list,
                                         title="Top 30 Tables by Storage", x_title="Storage (GB)", stacked=True)

    ds_tables = ""
    if not df_top.empty:
        cols_show = [c for c in ["TABLE_FQN","TABLE_NAME","ACTIVE_GB","TIME_TRAVEL_GB","FAILSAFE_GB","TOTAL_GB"] if c in df_top.columns]
        if cols_show:
            ds_tables = _make_table(cols_show, df_top.head(50)[cols_show].values.tolist())

    sub_sections.append(build_sub_section("Database Storage", kpis=ds_kpis, charts_html=ds_charts, tables_html=ds_tables))

    cl_kpis = []
    df_cl = _qc("db_overview_5_clustering_overview_query")
    if not df_cl.empty:
        r = df_cl.iloc[0]
        for col, label in [("TOTAL_TABLES","Total Tables"), ("CLUSTERED","Clustered"),
                           ("UNCLUSTERED","Unclustered"), ("CLUSTER_PCT","Cluster %")]:
            if col in df_cl.columns:
                val = r.get(col)
                suf = "%" if "PCT" in col else ""
                cl_kpis.append({"value": f"{_fmt_num(val, 1 if 'PCT' in col else 0)}{suf}", "label": label})

    cl_charts = ""
    if not df_cl.empty and "CLUSTERED" in df_cl.columns and "UNCLUSTERED" in df_cl.columns:
        cl_charts += '<div class="charts-row"><div class="chart-col">'
        cl_charts += build_chart("doughnut",
                                 labels=["Unclustered", "Clustered"],
                                 data=[int(df_cl.iloc[0].get("UNCLUSTERED", 0)), int(df_cl.iloc[0].get("CLUSTERED", 0))],
                                 colors=[_A, _P])
        cl_charts += "</div><div class='chart-col'>"

        df_cred = _qc("db_overview_7_credit_history_query")
        if not df_cred.empty:
            date_col = None
            for c in ["USAGE_DATE", "START_DATE"]:
                if c in df_cred.columns:
                    date_col = c
                    break
            cred_col = None
            for c in ["CREDITS_USED", "TOTAL_CREDITS"]:
                if c in df_cred.columns:
                    cred_col = c
                    break
            if date_col and cred_col:
                cl_charts += build_chart("line",
                                         labels=[str(d) for d in df_cred[date_col].tolist()],
                                         datasets=[{"label": "Credits", "data": [round(float(v), 2) for v in df_cred[cred_col].tolist()],
                                                    "borderColor": _P, "backgroundColor": "rgba(41,181,232,0.15)", "fill": True}],
                                         title="Clustering Credits (Last 30 Days)", y_title="Credits")
        cl_charts += "</div></div>"

    cl_tables = ""
    df_ct = _qc("db_overview_6_clustered_tables_query")
    if not df_ct.empty:
        cols_show = [c for c in ["TABLE_NAME","CLUSTERING_KEY","ROW_COUNT","SIZE_GB","AUTO_CLUSTERING_ON","CREATED"] if c in df_ct.columns]
        if cols_show:
            cl_tables = f'<div class="section-subtitle">Clustered Tables</div>' + _make_table(cols_show, df_ct.head(50)[cols_show].values.tolist())

    sub_sections.append(build_sub_section("Clustering", kpis=cl_kpis, charts_html=cl_charts, tables_html=cl_tables))

    ll_kpis = []
    df_ll = _qc("db_overview_8_summary_query")
    if not df_ll.empty and len(df_ll) > 0:
        r = df_ll.iloc[0]
        for col, label in [("SHORT_LIVED_TABLES","Short-Lived Tables"), ("PERMANENT_COUNT","Permanent (Issue)"),
                           ("TRANSIENT_COUNT","Transient (OK)"), ("AVG_LIFESPAN_MINUTES","Avg Lifespan min"),
                           ("CHURNED_STORAGE_GB","Churned Storage GB")]:
            if col in df_ll.columns:
                val = r.get(col)
                ll_kpis.append({"value": _fmt_num(val, 0 if "COUNT" in col or "TABLES" in col else 2), "label": label})

    sub_sections.append(build_sub_section("Low Lifespan Tables", kpis=ll_kpis))

    hc_kpis = []
    df_hc = _qc("db_overview_11_summary_query")
    if not df_hc.empty and len(df_hc) > 0:
        r = df_hc.iloc[0]
        for col, label in [("TABLES_WITH_CHURN","Tables with Churn"), ("HIGH_CHURN_COUNT","High Churn (>1x)"),
                           ("TOTAL_CHURN_TB","Total Churn Storage TB"), ("AVG_CHURN_RATIO","Avg Churn Ratio")]:
            if col in df_hc.columns:
                val = r.get(col)
                suf = " TB" if "TB" in col else ("x" if "RATIO" in col else "")
                ll_dec = 4 if "TB" in col else (2 if "RATIO" in col else 0)
                hc_kpis.append({"value": f"{_fmt_num(val, ll_dec)}{suf}", "label": label})

    hc_charts = ""
    df_dbc = _qc("db_overview_13_db_churn_query")
    if not df_dbc.empty:
        db_col = None
        for c in ["DATABASE_NAME", "TABLE_CATALOG"]:
            if c in df_dbc.columns:
                db_col = c
                break
        churn_col = None
        for c in ["CHURN_TB", "TOTAL_CHURN_TB"]:
            if c in df_dbc.columns:
                churn_col = c
                break
        if db_col and churn_col:
            top15 = df_dbc.head(15)
            hc_charts += build_chart("hbar",
                                     labels=_trunc_labels(top15[db_col].tolist()),
                                     datasets=[{"label": "Churn (TB)", "data": [round(float(v), 4) for v in top15[churn_col].tolist()], "backgroundColor": _A}],
                                     title="Churn by Database (TB)", x_title="Churn (TB)")

    sub_sections.append(build_sub_section("High Churn Tables", kpis=hc_kpis, charts_html=hc_charts))

    analyzer_summary = _safe_text("db_mgmt_analysis_result")
    individual = _indiv_analyses("db_mgmt_indiv_", "db_mgmt_entity_list")

    return build_report(
        topic_name="Database Management",
        account_name=account_name,
        top_kpis=top_kpis,
        analyzer_summary=analyzer_summary,
        sub_sections=sub_sections,
        individual_analyses=individual,
    )


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

    ov_charts = ""
    if not df_fleet.empty and "WAREHOUSE_SIZE" in df_fleet.columns:
        size_counts = df_fleet["WAREHOUSE_SIZE"].value_counts()
        ov_charts += build_chart("vbar",
                                 labels=size_counts.index.tolist(),
                                 datasets=[{"label": "Count", "data": size_counts.values.tolist(), "backgroundColor": _P}],
                                 title="Fleet by Warehouse Size", y_title="Count")

    df_cred = _safe_df("wh_credits_health")
    if not df_cred.empty:
        name_col = None
        for c in ["WAREHOUSE_NAME", "WH_NAME"]:
            if c in df_cred.columns:
                name_col = c
                break
        cred_col = None
        for c in ["CREDITS_30_DAY", "TOTAL_CREDITS"]:
            if c in df_cred.columns:
                cred_col = c
                break
        if name_col and cred_col:
            ov_charts += build_chart("hbar",
                                     labels=_trunc_labels(df_cred[name_col].head(15).tolist()),
                                     datasets=[{"label": "Credits (30d)", "data": [round(float(v), 2) for v in df_cred[cred_col].head(15).tolist()], "backgroundColor": _A}],
                                     title="Top 15 Warehouses by Credits (30d)", x_title="Credits")

    sub_sections.append(build_sub_section("Overview", kpis=top_kpis, charts_html=ov_charts))

    df_ts = _safe_df("wh_credit_ts_data")
    if not df_ts.empty:
        ts_charts = ""
        date_col = None
        for c in ["USAGE_DATE", "START_DATE"]:
            if c in df_ts.columns:
                date_col = c
                break
        if date_col and "WAREHOUSE_NAME" in df_ts.columns and "COMPUTE_CREDITS" in df_ts.columns:
            pivot = df_ts.pivot_table(index=date_col, columns="WAREHOUSE_NAME", values="COMPUTE_CREDITS", aggfunc="sum").fillna(0)
            labels = [str(d) for d in pivot.index.tolist()]
            ds = []
            for i, wh in enumerate(pivot.columns[:8]):
                ds.append({"label": str(wh), "data": [round(float(v), 2) for v in pivot[wh].tolist()],
                           "backgroundColor": _COLORS[i % len(_COLORS)], "borderColor": _COLORS[i % len(_COLORS)], "fill": False})
            if ds:
                ts_charts += build_chart("line", labels=labels, datasets=ds,
                                         title="Daily Compute Credits by Warehouse", y_title="Credits")
        sub_sections.append(build_sub_section("Credit Trends", charts_html=ts_charts))

    analyzer_summary = _safe_text("wh_analysis_result")
    individual = _indiv_analyses("wh_indiv_", "wh_entity_list")

    return build_report(
        topic_name="Virtual Warehouses",
        account_name=account_name,
        top_kpis=top_kpis,
        analyzer_summary=analyzer_summary,
        sub_sections=sub_sections,
        individual_analyses=individual,
    )


def export_access_control(account_name: str) -> str:
    top_kpis = []
    df_role = _safe_df("auth_role_hygiene")
    if not df_role.empty:
        r = df_role.iloc[0]
        for col, label in [("TOTAL_ROLES","Total Roles"), ("CUSTOM_ROLES","Custom Roles"),
                           ("ORPHAN_ROLES","Orphan Roles"), ("ACTIVE_ROLES","Active Roles")]:
            if col in df_role.columns:
                top_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})

    sub_sections = []

    df_priv = _safe_df("ac_privileged_access")
    if not df_priv.empty:
        cols_show = [c for c in df_priv.columns if c not in ["_METADATA"]][:6]
        tbl = _make_table(cols_show, df_priv.head(30)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Privileged Access", tables_html=f'<div class="section-subtitle">Privileged Users</div>{tbl}'))

    df_users = _safe_df("auth_user_inventory")
    if not df_users.empty:
        u_kpis = []
        r = df_users.iloc[0]
        for col, label in [("TOTAL_USERS","Total Users"), ("ACTIVE_USERS","Active Users"),
                           ("INACTIVE_USERS","Inactive Users")]:
            if col in df_users.columns:
                u_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})
        sub_sections.append(build_sub_section("User Inventory", kpis=u_kpis))

    df_net = _safe_df("net_policies_data")
    if not df_net.empty:
        cols_show = [c for c in df_net.columns][:5]
        tbl = _make_table(cols_show, df_net.head(30)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Network Policies", tables_html=tbl))

    analyzer_summary = _safe_text("access_control_analysis_result")
    individual = _indiv_analyses("ac_indiv_", "ac_entity_list")

    return build_report(
        topic_name="Access Control",
        account_name=account_name,
        top_kpis=top_kpis,
        analyzer_summary=analyzer_summary,
        sub_sections=sub_sections,
        individual_analyses=individual,
    )


def export_data_ingestion(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    df_summary = _safe_df("ingestion_summary_data")
    if not df_summary.empty:
        for _, row in df_summary.iterrows():
            method = row.get("INGESTION_METHOD", "")
            gb = row.get("TOTAL_GB", 0)
            top_kpis.append({"value": f"{_fmt_num(gb)} GB", "label": str(method)})

        if "INGESTION_METHOD" in df_summary.columns and "TOTAL_GB" in df_summary.columns:
            ch = build_chart("vbar",
                             labels=df_summary["INGESTION_METHOD"].tolist(),
                             datasets=[{"label": "GB Loaded", "data": [round(float(v), 2) for v in df_summary["TOTAL_GB"].tolist()], "backgroundColor": _P}],
                             title="Data Loaded by Method (GB)", y_title="GB")
            sub_sections.append(build_sub_section("Ingestion Summary", charts_html=ch))

    df_bulk = _safe_df("ig_bulk_load")
    if not df_bulk.empty:
        cols_show = [c for c in df_bulk.columns][:6]
        tbl = _make_table(cols_show, df_bulk.head(30)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Bulk Load (COPY INTO)", tables_html=tbl))

    df_pipe = _safe_df("ig_pipe_efficiency")
    if not df_pipe.empty:
        cols_show = [c for c in df_pipe.columns][:6]
        tbl = _make_table(cols_show, df_pipe.head(30)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Snowpipe Analysis", tables_html=tbl))

    df_stream = _safe_df("ingestion_streaming_data")
    if not df_stream.empty:
        s_kpis = []
        date_col = None
        for c in ["USAGE_DATE", "START_DATE"]:
            if c in df_stream.columns:
                date_col = c
                break
        cred_col = None
        for c in ["CREDITS_USED", "TOTAL_CREDITS"]:
            if c in df_stream.columns:
                cred_col = c
                break
        if cred_col:
            s_kpis.append({"value": f"{_fmt_num(df_stream[cred_col].sum(), 2)}", "label": "Total Streaming Credits (30d)"})
        ch = ""
        if date_col and cred_col:
            ch = build_chart("vbar",
                             labels=[str(d) for d in df_stream[date_col].tolist()],
                             datasets=[{"label": "Credits", "data": [round(float(v), 2) for v in df_stream[cred_col].tolist()], "backgroundColor": _P}],
                             title="Snowpipe Streaming Daily Credits", y_title="Credits")
        sub_sections.append(build_sub_section("Snowpipe Streaming", kpis=s_kpis, charts_html=ch))

    analyzer_summary = _safe_text("ingestion_analysis_result")
    individual = _indiv_analyses("ing_indiv_", "ing_entity_list")

    return build_report(
        topic_name="Data Ingestion",
        account_name=account_name,
        top_kpis=top_kpis,
        analyzer_summary=analyzer_summary,
        sub_sections=sub_sections,
        individual_analyses=individual,
    )


def export_data_transformation(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    df_ov = _safe_df("tf_overview")
    if not df_ov.empty:
        r = df_ov.iloc[0]
        for col, label in [("CLUSTERED_TABLES","Clustered Tables"), ("UNCLUSTERED_TABLES","Unclustered Tables"),
                           ("MATERIALIZED_VIEWS","Materialized Views"), ("DYNAMIC_TABLES","Dynamic Tables"),
                           ("TABLES_WITH_SPILL_OR_QUEUING","Spill/Queue Issues")]:
            if col in df_ov.columns:
                top_kpis.append({"value": _fmt_num(r.get(col), 0), "label": label})

    df_prob = _safe_df("tf_problematic_queries")
    if not df_prob.empty:
        cols_show = [c for c in df_prob.columns][:6]
        tbl = _make_table(cols_show, df_prob.head(30)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Problematic Queries", tables_html=tbl))

    df_syn = _safe_df("tf_syntax_hunter")
    if not df_syn.empty:
        cols_show = [c for c in df_syn.columns][:6]
        tbl = _make_table(cols_show, df_syn.head(30)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Syntax Hunter", tables_html=tbl))

    df_wl = _safe_df("tf_workload_shape")
    if not df_wl.empty:
        cols_show = [c for c in df_wl.columns][:6]
        tbl = _make_table(cols_show, df_wl.head(30)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Workload Shape", tables_html=tbl))

    analyzer_summary = _safe_text("transformation_analysis_result")
    individual = _indiv_analyses("tx_indiv_", "tx_entity_list")

    return build_report(
        topic_name="Data Transformation",
        account_name=account_name,
        top_kpis=top_kpis,
        analyzer_summary=analyzer_summary,
        sub_sections=sub_sections,
        individual_analyses=individual,
    )


def export_finops(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    df_fc = _safe_df("finops_exec_forecast")
    if not df_fc.empty:
        r = df_fc.iloc[0]
        for col, label in [("TOTAL_CREDITS","Total Credits (30d)"), ("PROJECTED_CREDITS","Projected Credits"),
                           ("TOTAL_COST_USD","Total Cost (USD)")]:
            if col in df_fc.columns:
                val = r.get(col)
                pre = "$" if "USD" in col else ""
                top_kpis.append({"value": f"{pre}{_fmt_num(val)}", "label": label})

    df_cb = _safe_df("finops_compute_breakdown")
    if not df_cb.empty:
        name_col = None
        for c in ["WAREHOUSE_NAME", "SERVICE_TYPE"]:
            if c in df_cb.columns:
                name_col = c
                break
        cred_col = None
        for c in ["CREDITS_USED", "TOTAL_CREDITS"]:
            if c in df_cb.columns:
                cred_col = c
                break
        if name_col and cred_col:
            top15 = df_cb.head(15)
            ch = build_chart("hbar",
                             labels=_trunc_labels(top15[name_col].tolist()),
                             datasets=[{"label": "Credits", "data": [round(float(v), 2) for v in top15[cred_col].tolist()], "backgroundColor": _A}],
                             title="Top Compute Consumers", x_title="Credits")
            sub_sections.append(build_sub_section("Visibility — Compute Breakdown", charts_html=ch))

    df_cq = _safe_df("finops_costliest_queries")
    if not df_cq.empty:
        cols_show = [c for c in df_cq.columns][:6]
        tbl = _make_table(cols_show, df_cq.head(20)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Costliest Queries", tables_html=tbl))

    df_rm = _safe_df("fc_resource_monitors")
    if not df_rm.empty:
        cols_show = [c for c in df_rm.columns][:6]
        tbl = _make_table(cols_show, df_rm.head(20)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Control — Resource Monitors", tables_html=tbl))

    analyzer_summary = _safe_text("finops_analysis_result")
    individual = _indiv_analyses("fin_indiv_", "fin_entity_list")

    return build_report(
        topic_name="FinOps (lite)",
        account_name=account_name,
        top_kpis=top_kpis,
        analyzer_summary=analyzer_summary,
        sub_sections=sub_sections,
        individual_analyses=individual,
    )


def export_data_governance(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    df_health = _safe_df("dg_health_score_data")
    if not df_health.empty:
        total_tbl = 0
        tagged_tbl = 0
        if "TOTAL_TABLES" in df_health.columns:
            total_tbl = int(df_health["TOTAL_TABLES"].sum())
        if "TAGGED_TABLES" in df_health.columns:
            tagged_tbl = int(df_health["TAGGED_TABLES"].sum())
        untagged = total_tbl - tagged_tbl
        pct = round(tagged_tbl / total_tbl * 100, 1) if total_tbl > 0 else 0
        top_kpis = [
            {"value": _fmt_num(total_tbl, 0), "label": "Total Tables"},
            {"value": _fmt_num(tagged_tbl, 0), "label": "Tagged Tables"},
            {"value": _fmt_num(untagged, 0), "label": "Untagged Tables"},
            {"value": f"{pct}%", "label": "Tag Coverage"},
        ]

    df_class = _safe_df("dg_classification_data")
    if not df_class.empty and "APPLY_METHOD" in df_class.columns and "TAG_COUNT" in df_class.columns:
        ch = build_chart("vbar",
                         labels=df_class["APPLY_METHOD"].tolist(),
                         datasets=[{"label": "Tags", "data": [int(v) for v in df_class["TAG_COUNT"].tolist()], "backgroundColor": _P}],
                         title="Tags by Apply Method", y_title="Count")
        sub_sections.append(build_sub_section("Classification Overview", kpis=top_kpis, charts_html=ch))

    df_pol = _safe_df("dg_policy_inventory_data")
    if not df_pol.empty:
        cols_show = [c for c in df_pol.columns][:5]
        tbl = _make_table(cols_show, df_pol.head(20)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Policy Inventory", tables_html=tbl))

    df_mask = _safe_df("dg_masking_coverage")
    if not df_mask.empty:
        cols_show = [c for c in df_mask.columns][:6]
        tbl = _make_table(cols_show, df_mask.head(30)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Data Privacy & Protection", tables_html=tbl))

    analyzer_summary = _safe_text("governance_analysis_result")
    gov_entities = ["CLASSIFICATION", "LINEAGE_GOVERNANCE", "POLICY_PROTECTION", "TAG_COVERAGE", "TAG_DESIGN"]
    individual = []
    for e in gov_entities:
        key = f"gov_indiv_{e}"
        text = _safe_text(key)
        if text:
            individual.append({"title": e, "content": text})

    return build_report(
        topic_name="Data Governance",
        account_name=account_name,
        top_kpis=top_kpis,
        analyzer_summary=analyzer_summary,
        sub_sections=sub_sections,
        individual_analyses=individual,
    )


def export_recovery_devops(account_name: str) -> str:
    top_kpis = []
    sub_sections = []

    for key, label in [("devops_git_count", "Git Users"), ("devops_cicd_count", "CI/CD Users"),
                       ("devops_dt_count", "Dynamic Tables"), ("devops_task_count", "Task Executions")]:
        df = _safe_df(key)
        if not df.empty:
            val = df.iloc[0, 0] if len(df.columns) > 0 else 0
            top_kpis.append({"value": _fmt_num(val, 0), "label": label})

    df_dcm = _safe_df("rd_dcm_adoption")
    if not df_dcm.empty:
        cols_show = [c for c in df_dcm.columns][:6]
        tbl = _make_table(cols_show, df_dcm.head(20)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Database Change Management (DCM)", tables_html=tbl))

    df_git = _safe_df("rd_git_integration")
    if not df_git.empty:
        cols_show = [c for c in df_git.columns][:6]
        tbl = _make_table(cols_show, df_git.head(20)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Git Integration", tables_html=tbl))

    df_cicd = _safe_df("rd_cicd_automation")
    if not df_cicd.empty:
        cols_show = [c for c in df_cicd.columns][:6]
        tbl = _make_table(cols_show, df_cicd.head(20)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("CI/CD Automation", tables_html=tbl))

    df_pipe = _safe_df("rd_declarative_pipeline")
    if not df_pipe.empty:
        cols_show = [c for c in df_pipe.columns][:6]
        tbl = _make_table(cols_show, df_pipe.head(20)[cols_show].values.tolist())
        sub_sections.append(build_sub_section("Declarative Pipelines", tables_html=tbl))

    analyzer_summary = _safe_text("recovery_devops_analysis_result")
    individual = _indiv_analyses("rd_indiv_", "rd_entity_list")

    return build_report(
        topic_name="Data Recovery & DevOps",
        account_name=account_name,
        top_kpis=top_kpis,
        analyzer_summary=analyzer_summary,
        sub_sections=sub_sections,
        individual_analyses=individual,
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

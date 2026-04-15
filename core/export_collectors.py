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
    _COLORS, _next_chart_id,
)

_P  = "#29B5E8"   # cyan / primary
_S  = "#11567F"   # dark navy
_T  = "#75C2D8"   # light blue
_A  = "#E8A229"   # amber
_PALETTE = [_P, _S, _T, _A, "#023E8A", "#48CAE4", "#ADE8F4", "#0077B6"]


def _safe_df(key: str) -> pd.DataFrame:
    val = st.session_state.get(key)
    if val is not None and isinstance(val, pd.DataFrame) and not val.empty:
        return val
    prefix = key + "_"
    for k, v in st.session_state.items():
        if isinstance(k, str) and k.startswith(prefix) and isinstance(v, pd.DataFrame) and not v.empty:
            return v
    return pd.DataFrame()


def _col(df: pd.DataFrame, *names) -> str | None:
    for n in names:
        if n in df.columns:
            return n
    return None


def _trunc(labels: list, maxlen: int = 45) -> list:
    return [str(l)[:maxlen] for l in labels]


def _vals(df: pd.DataFrame, col: str) -> list:
    return df[col].tolist() if col in df.columns else []


def _row0(df: pd.DataFrame, col: str, default=None):
    if col in df.columns and len(df) > 0:
        return df.iloc[0][col]
    return default


def _charts_row(html: str) -> str:
    return f'<div class="charts-row">{html}</div>'


def _col_wrap(html: str) -> str:
    return f'<div class="chart-col">{html}</div>'


def _full_wrap(html: str) -> str:
    return f'<div class="chart-block-full">{html}</div>'


def _subtitle(text: str) -> str:
    return f'<div class="section-subtitle">{_esc(text)}</div>'


# ── Virtual Warehouses ──────────────────────────────────────────────────────

def export_virtual_warehouses(account_name: str) -> str:
    df_fleet    = _safe_df("wh_fleet_data")
    df_cred     = _safe_df("wh_credits_health")
    df_heatmap  = _safe_df("wh_heatmap_data")
    df_hourly   = _safe_df("wh_hourly_activity")
    df_over     = _safe_df("wh_oversizing_data")
    df_idle     = _safe_df("wh_idle_data")
    df_eff      = _safe_df("wh_scaling_efficiency")
    df_skew     = _safe_df("wh_data_skew")
    df_act      = _safe_df("wh_activity_summary")
    df_qas      = _safe_df("wh_qas_eligible")
    df_qas_use  = _safe_df("wh_qas_usage")
    df_work     = _safe_df("wh_workload_data")

    total_wh = len(df_fleet) if not df_fleet.empty else 0
    top_kpis = [{"value": str(total_wh), "label": "Total Warehouses"}]

    sub_sections = []

    # ── Overview ──────────────────────────────────────────────────────────
    ov_kpis = list(top_kpis)
    ov_html = ""
    if not df_fleet.empty:
        if "WAREHOUSE_SIZE" in df_fleet.columns:
            sc = df_fleet["WAREHOUSE_SIZE"].value_counts()
            ov_html += _col_wrap(build_chart("vbar",
                labels=sc.index.tolist(),
                datasets=[{"label": "Count", "data": sc.values.tolist(), "backgroundColor": _P}],
                title="Warehouse Distribution by Size"))
        if "WAREHOUSE_TYPE" in df_fleet.columns:
            tc = df_fleet["WAREHOUSE_TYPE"].value_counts()
            ov_html += _col_wrap(build_chart("doughnut",
                labels=tc.index.tolist(), data=tc.values.tolist(),
                colors=_PALETTE[:len(tc)], title="Warehouse Type Distribution"))
        if "RESOURCE_CONSTRAINT" in df_fleet.columns:
            rc = df_fleet["RESOURCE_CONSTRAINT"].value_counts()
            ov_html += _col_wrap(build_chart("vbar",
                labels=rc.index.tolist(),
                datasets=[{"label": "Count", "data": rc.values.tolist(), "backgroundColor": _T}],
                title="Warehouse Resource Constraint"))
    if ov_html:
        ov_html = _charts_row(ov_html)

    if not df_cred.empty:
        wh_col = _col(df_cred, "WAREHOUSE_NAME", "WH_NAME")
        cr_col = _col(df_cred, "CREDITS_30_DAY", "TOTAL_CREDITS")
        if wh_col and cr_col:
            top20 = df_cred.head(20)
            ov_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top20[wh_col].tolist()),
                datasets=[{"label": "Credits", "data": [round(float(v), 2) for v in top20[cr_col].tolist()], "backgroundColor": _P}],
                title="Top 20 Warehouses by Credits Used (30d)", x_title="Credits"))
            cred_map = [
                (wh_col, "Warehouse"), (cr_col, "Total Credits"),
                ("AVG_THREADS", "Avg Threads"), ("AVG_QUEUE", "Avg Queue"),
                ("HEALTH_STATUS", "Health Status"),
            ]
            cred_avail = [(r, h) for r, h in cred_map if r in df_cred.columns]
            ov_html += _subtitle("Credits by Warehouse (30d)")
            ov_html += _make_table(
                [h for _, h in cred_avail],
                df_cred[[r for r, _ in cred_avail]].values.tolist(),
            )

    if not df_heatmap.empty:
        hm_html = "<div class='chart-block-full'><div class='chart-block'><div class='chart-title'>Warehouse Load Heatmap</div>"
        pivot_wh = df_heatmap.drop_duplicates("WAREHOUSE_NAME")[["WAREHOUSE_NAME", "TOTAL_CREDITS"]].sort_values("TOTAL_CREDITS", ascending=False).head(15)
        hours = sorted(df_heatmap["HOUR_OF_DAY"].unique().tolist()) if "HOUR_OF_DAY" in df_heatmap.columns else []
        if hours:
            hm_rows = []
            for _, r in pivot_wh.iterrows():
                wn = r["WAREHOUSE_NAME"]
                hv = []
                for h in hours:
                    m = df_heatmap[(df_heatmap["WAREHOUSE_NAME"] == wn) & (df_heatmap["HOUR_OF_DAY"] == h)]
                    hv.append(f"{round(float(m['AVG_QUERY_LOAD'].values[0]), 2):.2f}" if len(m) > 0 else "0.00")
                hm_rows.append([round(float(r["TOTAL_CREDITS"]), 0), wn] + hv)
            hm_html += _make_table(["Credits", "Warehouse"] + [str(h) for h in hours], hm_rows)
        hm_html += "</div></div>"
        ov_html += hm_html

    sub_sections.append(build_sub_section("Overview", kpis=ov_kpis, charts_html=ov_html))

    # ── Scaling Management ───────────────────────────────────────────────
    sc_html = ""
    if not df_over.empty:
        wh_col  = _col(df_over, "WAREHOUSE_NAME")
        pct_col = _col(df_over, "PCT_OVERSIZED")
        if wh_col and pct_col:
            sc_html += _full_wrap(build_chart("hbar",
                labels=_trunc(df_over[wh_col].head(15).tolist()),
                datasets=[{"label": "% Oversized", "data": [round(float(v), 1) for v in df_over[pct_col].head(15).tolist()], "backgroundColor": _P}],
                title="Warehouse Oversizing Analysis (7d)", x_title="% Oversized"))
            over_map = [
                (wh_col, "Warehouse"), ("WAREHOUSE_SIZE", "Size"),
                ("TOTAL_QUERIES", "Total Queries"), ("OVERSIZED_QUERIES", "Oversized Queries"),
                ("PCT_OVERSIZED", "% Oversized"), ("SEVERITY", "Severity"),
            ]
            over_avail = [(r, h) for r, h in over_map if r in df_over.columns]
            sc_html += _subtitle("Oversizing Detail")
            sc_html += _make_table(
                [h for _, h in over_avail],
                df_over.head(20)[[r for r, _ in over_avail]].values.tolist(),
            )

    if not df_idle.empty:
        wh_col = _col(df_idle, "WAREHOUSE_NAME")
        if wh_col and "EST_UPTIME_HOURS" in df_idle.columns and "EST_IDLE_HOURS" in df_idle.columns:
            top30 = df_idle.head(30)
            sc_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top30[wh_col].tolist()),
                datasets=[
                    {"label": "Active", "data": [round(float(r["EST_UPTIME_HOURS"] - r["EST_IDLE_HOURS"]), 2) for _, r in top30.iterrows()], "backgroundColor": _P},
                    {"label": "Idle",   "data": [round(float(r["EST_IDLE_HOURS"]), 2) for _, r in top30.iterrows()], "backgroundColor": _A},
                ],
                title="Estimated Uptime vs Idle Hours (7d)", x_title="Hours", stacked=True))
            idle_map = [
                (wh_col, "Warehouse"), ("EST_UPTIME_HOURS", "Est Uptime Hours"),
                ("EST_IDLE_HOURS", "Est Idle Hours"), ("PCT_TIME_IDLE", "% Time Idle"),
            ]
            idle_avail = [(r, h) for r, h in idle_map if r in df_idle.columns]
            sc_html += _subtitle("Idle Time Detail")
            sc_html += _make_table(
                [h for _, h in idle_avail],
                df_idle.head(20)[[r for r, _ in idle_avail]].values.tolist(),
            )

        if wh_col and "PCT_TIME_IDLE" in df_idle.columns:
            top_idle = df_idle.head(20)
            idle_colors = [_A if float(v) >= 50 else _P for v in top_idle["PCT_TIME_IDLE"].tolist()]
            sc_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top_idle[wh_col].tolist()),
                datasets=[{"label": "Idle %", "data": [round(float(v), 1) for v in top_idle["PCT_TIME_IDLE"].tolist()], "backgroundColor": idle_colors}],
                title="Warehouse Idle % (7d)", x_title="Idle %"))
            sc_html += _subtitle("Idle % Detail")
            idlepct_map = [(wh_col, "Warehouse"), ("PCT_TIME_IDLE", "Idle %"), ("INTERVAL_COUNT", "Samples")]
            idlepct_avail = [(r, h) for r, h in idlepct_map if r in df_idle.columns]
            sc_html += _make_table(
                [h for _, h in idlepct_avail],
                df_idle.head(20)[[r for r, _ in idlepct_avail]].values.tolist(),
            )

    if not df_eff.empty and "WAREHOUSE_NAME" in df_eff.columns:
        eff_map = [
            ("WAREHOUSE_NAME", "Warehouse"), ("WAREHOUSE_SIZE", "Size"),
            ("NODE_COUNT", "Nodes"), ("CREDITS_PER_HOUR", "Credits/Hr"),
            ("TOTAL_QUERIES", "Total Queries"), ("PCT_OVERSIZED_FOR_DATA", "% Oversized"),
            ("PCT_IDLE_TIME", "% Idle"), ("OVERALL_RECOMMENDATION", "Recommendation"),
        ]
        eff_avail = [(r, h) for r, h in eff_map if r in df_eff.columns]
        if eff_avail:
            sc_html += _subtitle("Combined Efficiency Detail")
            sc_html += _make_table(
                [h for _, h in eff_avail],
                df_eff.head(25)[[r for r, _ in eff_avail]].values.tolist(),
            )

    if not df_skew.empty:
        wh_col = _col(df_skew, "WAREHOUSE_NAME")
        sp_col = _col(df_skew, "TOTAL_SPILL_GB")
        if wh_col and sp_col:
            spill_map = [
                (wh_col, "Warehouse"), ("QUERY_COUNT", "Total Queries"),
                ("TOTAL_REMOTE_SPILL_GB", "Remote Spill GB"),
                ("TOTAL_LOCAL_SPILL_GB", "Local Spill GB"),
                ("TOTAL_SPILL_GB", "Total Spill GB"),
            ]
            spill_avail = [(r, h) for r, h in spill_map if r in df_skew.columns]
            sc_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(df_skew[wh_col].head(15).tolist()),
                    datasets=[{"label": "Spill (GB)", "data": [round(float(v), 2) for v in df_skew[sp_col].head(15).tolist()], "backgroundColor": _A}],
                    title="Remote Spill by Warehouse (GB, 7d)", x_title="Spill (GB)")) +
                _col_wrap(_subtitle("Spill Detail") + _make_table(
                    [h for _, h in spill_avail],
                    df_skew.head(15)[[r for r, _ in spill_avail]].values.tolist(),
                ))
            )

    if sc_html:
        sub_sections.append(build_sub_section("Scaling Management", charts_html=sc_html))

    # ── Performance Monitoring ───────────────────────────────────────────
    pm_html = ""

    if not df_act.empty and "WAREHOUSE_NAME" in df_act.columns:
        if "TOTAL_EXECUTION_HOURS" in df_act.columns and "TOTAL_QUERIES" in df_act.columns:
            df_act2 = df_act.copy()
            df_act2["AVG_ELAPSED_SEC"] = (
                df_act2["TOTAL_EXECUTION_HOURS"] * 3600.0 /
                df_act2["TOTAL_QUERIES"].replace(0, float("nan"))
            ).round(1).fillna(0)
            df_act2 = df_act2.sort_values("AVG_ELAPSED_SEC", ascending=False).head(20)
            pm_html += _full_wrap(build_chart("hbar",
                labels=_trunc(df_act2["WAREHOUSE_NAME"].tolist()),
                datasets=[{"label": "Avg Elapsed (sec)", "data": df_act2["AVG_ELAPSED_SEC"].tolist(), "backgroundColor": _T}],
                title="Avg Query Duration by Warehouse (sec, 7d)"))
            perf_map = [
                ("WAREHOUSE_NAME", "Warehouse"), ("AVG_ELAPSED_SEC", "Avg Elapsed (sec)"),
                ("ACTIVE_HOURS", "Active Hours"), ("TOTAL_QUERIES", "Total Queries"),
            ]
            perf_avail = [(r, h) for r, h in perf_map if r in df_act2.columns]
            pm_html += _subtitle("Performance Detail")
            pm_html += _make_table(
                [h for _, h in perf_avail],
                df_act2[[r for r, _ in perf_avail]].values.tolist(),
            )

    if not df_idle.empty:
        wh_col = _col(df_idle, "WAREHOUSE_NAME")
        if wh_col and "PCT_TIME_IDLE" in df_idle.columns:
            top_idle = df_idle.head(20)
            idle_colors = [_A if float(v) >= 50 else _P for v in top_idle["PCT_TIME_IDLE"].tolist()]
            pm_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top_idle[wh_col].tolist()),
                datasets=[{"label": "Idle %", "data": [round(float(v), 1) for v in top_idle["PCT_TIME_IDLE"].tolist()], "backgroundColor": idle_colors}],
                title="Warehouse Idle % (7d)", x_title="Idle %"))
            idlepct_map2 = [(wh_col, "Warehouse"), ("PCT_TIME_IDLE", "Idle %"), ("INTERVAL_COUNT", "Samples")]
            idlepct_avail2 = [(r, h) for r, h in idlepct_map2 if r in df_idle.columns]
            pm_html += _subtitle("Idle % Detail")
            pm_html += _make_table(
                [h for _, h in idlepct_avail2],
                df_idle.head(20)[[r for r, _ in idlepct_avail2]].values.tolist(),
            )

        if wh_col and "EST_UPTIME_HOURS" in df_idle.columns and "IDLE_INTERVALS" in df_idle.columns:
            always_on = df_idle[df_idle["EST_UPTIME_HOURS"] >= 24].copy() if "EST_UPTIME_HOURS" in df_idle.columns else pd.DataFrame()
            if not always_on.empty and "PCT_TIME_IDLE" in always_on.columns:
                always_on = always_on.sort_values("PCT_TIME_IDLE", ascending=False).head(20)
                pm_html += _full_wrap(build_chart("hbar",
                    labels=_trunc(always_on[wh_col].tolist()),
                    datasets=[{"label": "Idle Time %", "data": [round(float(v), 1) for v in always_on["PCT_TIME_IDLE"].tolist()], "backgroundColor": _A}],
                    title="Always-On Warehouses — Idle Time % (7d)", x_title="Idle Time %"))
                ao_rows = []
                for _, r in always_on.iterrows():
                    idle_min  = int(round(float(r["IDLE_INTERVALS"]) * 5)) if "IDLE_INTERVALS" in always_on.columns else 0
                    total_min = int(round(float(r["INTERVAL_COUNT"]) * 5)) if "INTERVAL_COUNT" in always_on.columns else 0
                    idle_pct  = f"{round(float(r['PCT_TIME_IDLE']), 1)}%"
                    ao_rows.append([str(r[wh_col]), idle_min, total_min, idle_pct])
                pm_html += _subtitle("Always-On Detail")
                pm_html += _make_table(["Warehouse", "Idle Min", "Total Min", "Idle %"], ao_rows)

    if not df_skew.empty:
        wh_col_sk = _col(df_skew, "WAREHOUSE_NAME")
        sp_col_sk = _col(df_skew, "TOTAL_SPILL_GB")
        if wh_col_sk and sp_col_sk:
            spill_map2 = [
                (wh_col_sk, "Warehouse"), ("QUERY_COUNT", "Total Queries"),
                ("TOTAL_REMOTE_SPILL_GB", "Remote Spill GB"),
                ("TOTAL_LOCAL_SPILL_GB", "Local Spill GB"),
                ("TOTAL_SPILL_GB", "Total Spill GB"),
            ]
            spill_avail2 = [(r, h) for r, h in spill_map2 if r in df_skew.columns]
            pm_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(df_skew[wh_col_sk].head(15).tolist()),
                    datasets=[{"label": "Spill (GB)", "data": [round(float(v), 2) for v in df_skew[sp_col_sk].head(15).tolist()], "backgroundColor": _A}],
                    title="Remote Spill by Warehouse (GB, 7d)", x_title="Spill (GB)")) +
                _col_wrap(_subtitle("Spill Detail") + _make_table(
                    [h for _, h in spill_avail2],
                    df_skew.head(15)[[r for r, _ in spill_avail2]].values.tolist(),
                ))
            )

    if pm_html:
        sub_sections.append(build_sub_section("Performance Monitoring", charts_html=pm_html))

    # ── Fleet & Query Analysis ───────────────────────────────────────────
    fq_html = ""
    if not df_hourly.empty and "HOUR_OF_DAY" in df_hourly.columns:
        hrs = df_hourly["HOUR_OF_DAY"].tolist()
        row_h = ""
        if "QUERY_COUNT" in df_hourly.columns:
            row_h += _col_wrap(build_chart("vbar",
                labels=[str(h) for h in hrs],
                datasets=[{"label": "Queries", "data": df_hourly["QUERY_COUNT"].tolist(), "backgroundColor": _P}],
                title="Hourly Query Volume (7d)", y_title="Query Count"))
        if "TOTAL_TB_SCANNED" in df_hourly.columns:
            row_h += _col_wrap(build_chart("vbar",
                labels=[str(h) for h in hrs],
                datasets=[{"label": "TB Scanned", "data": [round(float(v), 3) for v in df_hourly["TOTAL_TB_SCANNED"].tolist()], "backgroundColor": _S}],
                title="TB Scanned by Hour (7d)", y_title="TB Scanned"))
        if row_h:
            fq_html += _charts_row(row_h)

    if not df_idle.empty:
        wh_col = _col(df_idle, "WAREHOUSE_NAME")
        if wh_col and "EST_UPTIME_HOURS" in df_idle.columns and "EST_IDLE_HOURS" in df_idle.columns:
            top20_fq = df_idle.head(20)
            fq_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top20_fq[wh_col].tolist()),
                datasets=[
                    {"label": "Active (hrs)", "data": [round(float(r["EST_UPTIME_HOURS"] - r["EST_IDLE_HOURS"]), 2) for _, r in top20_fq.iterrows()], "backgroundColor": _P},
                    {"label": "Idle (hrs)",   "data": [round(float(r["EST_IDLE_HOURS"]), 2) for _, r in top20_fq.iterrows()], "backgroundColor": _A},
                ],
                title="Active vs Idle Hours by Warehouse (7d)", x_title="Hours", stacked=True))

    if not df_work.empty and "WAREHOUSE_NAME" in df_work.columns:
        top20w = df_work.head(20)
        size_cols = [c for c in ["TINY_UNDER_100MB", "SMALL_100MB_1GB", "LARGE_1GB_100GB", "MASSIVE_OVER_100GB"] if c in df_work.columns]
        if size_cols:
            fq_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top20w["WAREHOUSE_NAME"].tolist()),
                datasets=[{"label": c.replace("_", " "), "data": top20w[c].tolist(), "backgroundColor": _PALETTE[i % len(_PALETTE)]} for i, c in enumerate(size_cols)],
                title="Query Volume by Data Size (7d)", stacked=True))

    if not df_qas.empty:
        wh_col = _col(df_qas, "WAREHOUSE_NAME")
        t_col  = _col(df_qas, "EST_QAS_TIME_SAVED_SEC", "ELIGIBLE_QUERY_ACCELERATION_TIME")
        if wh_col and t_col and "QUERY_ID" in df_qas.columns:
            labels_qas = [f"{str(row['QUERY_ID'])[:10]} @ {str(row[wh_col])[:30]}" for _, row in df_qas.head(10).iterrows()]
            qas_map = [
                (wh_col, "Warehouse"), ("QUERY_ID", "Query ID"),
                (t_col, "Est Saved (sec)"), ("SUGGESTED_MAX_SCALE_FACTOR", "Suggested Max Scale"),
                ("IMPACT_LEVEL", "Impact"),
            ]
            qas_avail = [(r, h) for r, h in qas_map if r in df_qas.columns]
            fq_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(labels_qas),
                    datasets=[{"label": "Saved (sec)", "data": [round(float(v), 0) for v in df_qas[t_col].head(10).tolist()], "backgroundColor": _S}],
                    title="QAS Eligible Queries — Estimated Time Savings (7d)", x_title="Saved (sec)")) +
                _col_wrap(_subtitle("QAS Eligible Query Detail") + _make_table(
                    [h for _, h in qas_avail],
                    df_qas.head(10)[[r for r, _ in qas_avail]].values.tolist(),
                ))
            )

    if not df_qas_use.empty:
        wh_col = _col(df_qas_use, "WAREHOUSE_NAME")
        cr_col = _col(df_qas_use, "QAS_CREDITS")
        ev_col = _col(df_qas_use, "ACCELERATION_EVENTS")
        if wh_col:
            row_html = ""
            if cr_col:
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(df_qas_use[wh_col].head(10).tolist()),
                    datasets=[{"label": "QAS Credits", "data": [round(float(v), 2) for v in df_qas_use[cr_col].head(10).tolist()], "backgroundColor": _P}],
                    title="QAS Credits by Warehouse (30d)", x_title="QAS Credits"))
            if ev_col:
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(df_qas_use[wh_col].head(10).tolist()),
                    datasets=[{"label": "Acceleration Events", "data": df_qas_use[ev_col].head(10).tolist(), "backgroundColor": _T}],
                    title="QAS Acceleration Events by Warehouse (30d)", x_title="Events"))
            if row_html:
                fq_html += _charts_row(row_html)
            qas_use_map = [
                (wh_col, "Warehouse"), (cr_col or "", "QAS Credits"),
                ("ACCELERATION_EVENTS", "Accel Events"), ("USAGE_TIER", "Usage Tier"),
            ]
            qas_use_avail = [(r, h) for r, h in qas_use_map if r and r in df_qas_use.columns]
            if qas_use_avail:
                fq_html += _make_table(
                    [h for _, h in qas_use_avail],
                    df_qas_use[[r for r, _ in qas_use_avail]].values.tolist(),
                )

    if fq_html:
        sub_sections.append(build_sub_section("Fleet & Query Analysis", charts_html=fq_html))

    return build_report(
        topic_name="Virtual Warehouses",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ── Database Management ─────────────────────────────────────────────────────

def export_database_management(account_name: str) -> str:
    from components.Database_Management._db_queries import ALL_DB_OVERVIEW_QUERIES
    from components.Database_Management.db_overview import _query_cache

    def _qc(key):
        df = _query_cache.get(key)
        if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
            return df
        return _safe_df(key)

    # Correct query keys & column names based on _db_queries.py
    df_stor      = _qc("db_overview_1_total_storage_query")          # ACTIVE_STORAGE_TB, TIME_TRAVEL_STORAGE_TB, FAILSAFE_STORAGE_TB, RETAINED_FOR_CLONE_STORAGE_TB
    df_sum       = _qc("db_overview_2_storage_summary_query")        # ACTIVE_STORAGE_TB, TIME_TRAVEL_STORAGE_TB, CLONE_STORAGE_TB, DATABASE_COUNT, TABLE_COUNT
    df_top       = _qc("db_overview_4_top_tables_query")             # FULL_TABLE_NAME, TABLE_NAME, ACTIVE_STORAGE_GB, TIME_TRAVEL_GB, FAILSAFE_GB, TOTAL_GB
    df_cl_ov     = _qc("db_overview_5_clustering_overview_query")    # TOTAL_TABLES, CLUSTERED_TABLES, UNCLUSTERED_TABLES, CLUSTER_PERCENTAGE
    df_cl_t      = _qc("db_overview_6_clustered_tables_query")       # FULL_TABLE_NAME, CLUSTERING_KEY, ROW_COUNT, SIZE_GB, AUTO_CLUSTERING_ON, CREATED
    df_cred      = _qc("db_overview_7_credit_history_query")         # CLUSTER_DATE, DAILY_CREDITS, TABLES_CLUSTERED
    df_ll        = _qc("db_overview_8_summary_query")                # TOTAL_SHORT_LIVED, PERMANENT_SHORT_LIVED, TRANSIENT_SHORT_LIVED, AVG_LIFESPAN_MINUTES, TOTAL_CHURNED_STORAGE_GB
    df_ll_t      = _qc("db_overview_9_detail_query")                 # FULL_TABLE_NAME, TABLE_OWNER, TABLE_TYPE, CREATED, DELETED, LIFESPAN_MINUTES, SIZE_MB
    df_ll_agg    = _qc("db_overview_19_aggregates_query")            # "Table Category", "Count of Short-Lived Tables", "Avg Lifespan (Minutes)"
    df_ll_s      = _qc("db_overview_24_short_lived_by_schema_query") # SCHEMA_NAME, SHORT_LIVED_COUNT, PERMANENT_COUNT, TRANSIENT_COUNT, AVG_LIFESPAN_MINUTES
    df_hc        = _qc("db_overview_11_summary_query")               # TABLES_WITH_CHURN, HIGH_CHURN_TABLES, TOTAL_CHURN_TB, AVG_CHURN_RATIO
    df_dbc       = _qc("db_overview_13_db_churn_query")              # DATABASE_NAME, TABLE_COUNT, TOTAL_CHURN_TB, AVG_CHURN_RATIO
    df_sav       = _qc("db_overview_25_savings_actions_query")       # OPTIMIZATION_ACTION, AFFECTED_TABLES, POTENTIAL_SAVINGS_TB, EST_MONTHLY_SAVINGS_USD
    df_obj       = _qc("db_overview_14_object_count_query")          # OBJECT_TYPE, OBJECT_COUNT
    df_obj_exp   = _qc("db_overview_26_expanded_object_count_query") # OBJECT_TYPE, OBJECT_COUNT
    df_cc        = _qc("db_overview_23_clustering_detail_query")     # TABLE_NAME, CLUSTERING_CREDITS, AVG_CREDITS_PER_DAY, AUTO_CLUSTERING_ON
    df_churn_det = _qc("db_overview_12_detail_query")                # TABLE_NAME, TABLE_TYPE, ACTIVE_DATA_GB, TIME_TRAVEL_GB, FAILSAFE_GB, TOTAL_CHURN_GB, CHURN_RATIO

    # ── Top KPIs — computed from query 1 actual columns ──────────────────
    top_kpis = []
    if not df_stor.empty:
        r = df_stor.iloc[0]
        act   = float(r.get("ACTIVE_STORAGE_TB", 0) or 0)
        tt    = float(r.get("TIME_TRAVEL_STORAGE_TB", 0) or 0)
        fs    = float(r.get("FAILSAFE_STORAGE_TB", 0) or 0)
        clone = float(r.get("RETAINED_FOR_CLONE_STORAGE_TB", 0) or 0)
        total = act + tt + fs + clone
        top_kpis = [
            {"value": f"{total:.3f} TB", "label": "Total Storage"},
            {"value": f"{act:.3f} TB",   "label": "Active"},
            {"value": f"{tt:.3f} TB",    "label": "Time Travel"},
            {"value": f"{fs:.3f} TB",    "label": "Failsafe"},
            {"value": f"{clone:.3f} TB", "label": "Clone Retained"},
        ]

    sub_sections = []

    # ── Overview ──────────────────────────────────────────────────────────
    ov_kpis = list(top_kpis)
    ov_html = ""

    if not df_stor.empty:
        r = df_stor.iloc[0]
        labels = ["Active", "Time Travel", "Failsafe", "Clone Retained"]
        data   = [float(r.get(c, 0) or 0) for c in
                  ["ACTIVE_STORAGE_TB", "TIME_TRAVEL_STORAGE_TB", "FAILSAFE_STORAGE_TB", "RETAINED_FOR_CLONE_STORAGE_TB"]]
        if any(d > 0 for d in data):
            ov_html += _col_wrap(build_chart("doughnut",
                labels=labels, data=data, colors=[_P, _S, _A, _T],
                title="Storage by Type"))

    if not df_obj.empty and "OBJECT_TYPE" in df_obj.columns and "OBJECT_COUNT" in df_obj.columns:
        ov_html += _col_wrap(build_chart("hbar",
            labels=_trunc(df_obj["OBJECT_TYPE"].tolist()),
            datasets=[{"label": "Count", "data": [int(v) for v in df_obj["OBJECT_COUNT"].tolist()],
                       "backgroundColor": _P}],
            title="Object Counts", x_title="Count"))

    if ov_html:
        ov_html = _charts_row(ov_html)

    sub_sections.append(build_sub_section("Overview", kpis=ov_kpis, charts_html=ov_html))

    # ── Database Storage ──────────────────────────────────────────────────
    ds_kpis = []
    if not df_sum.empty:
        r_sum = df_sum.iloc[0]
        if not df_stor.empty:
            r_stor = df_stor.iloc[0]
            total = sum(float(r_stor.get(c, 0) or 0) for c in
                        ["ACTIVE_STORAGE_TB", "TIME_TRAVEL_STORAGE_TB", "FAILSAFE_STORAGE_TB", "RETAINED_FOR_CLONE_STORAGE_TB"])
            ds_kpis.append({"value": f"{total:.3f} TB", "label": "Total Storage"})
        ds_kpis.append({"value": f"{float(r_sum.get('ACTIVE_STORAGE_TB', 0) or 0):.3f} TB", "label": "Active Storage"})
        if "DATABASE_COUNT" in df_sum.columns:
            ds_kpis.append({"value": _fmt_num(_row0(df_sum, "DATABASE_COUNT"), 0), "label": "Databases"})
        if "TABLE_COUNT" in df_sum.columns:
            ds_kpis.append({"value": _fmt_num(_row0(df_sum, "TABLE_COUNT"), 0), "label": "Tables"})

    ds_html = ""
    if not df_top.empty:
        lbl_col = _col(df_top, "FULL_TABLE_NAME", "TABLE_NAME")
        if lbl_col:
            top30 = df_top.head(30)
            ds_list = []
            for c, label, clr in [("ACTIVE_STORAGE_GB", "Active GB", _P),
                                    ("TIME_TRAVEL_GB", "Time Travel GB", _S),
                                    ("FAILSAFE_GB", "Failsafe GB", _A)]:
                if c in top30.columns:
                    ds_list.append({"label": label,
                                    "data": [round(float(v), 2) for v in top30[c].tolist()],
                                    "backgroundColor": clr})
            if ds_list:
                ds_html += _full_wrap(build_chart("hbar",
                    labels=_trunc(top30[lbl_col].tolist()),
                    datasets=ds_list,
                    title="Top 30 Tables by Storage — Active / TT / Failsafe (GB)",
                    x_title="Storage (GB)", stacked=True))
        cols_map = [("FULL_TABLE_NAME", "Table"), ("TABLE_NAME", "Table"),
                    ("ACTIVE_STORAGE_GB", "Active (GB)"), ("TIME_TRAVEL_GB", "Time Travel (GB)"),
                    ("FAILSAFE_GB", "Failsafe (GB)"), ("TOTAL_GB", "Total (GB)")]
        cols_avail = [(raw, hdr) for raw, hdr in cols_map if raw in df_top.columns]
        if cols_avail:
            raw_cols = [r for r, _ in cols_avail]
            hdr_cols = [h for _, h in cols_avail]
            ds_html += _subtitle("Top 50 Tables by Storage")
            ds_html += _make_table(hdr_cols, df_top.head(50)[raw_cols].values.tolist())

    sub_sections.append(build_sub_section("Database Storage", kpis=ds_kpis, charts_html=ds_html))

    # ── Database Object Count ─────────────────────────────────────────────
    _OBJ_COLORS = ["#11567F", "#725AA3", "#FF9F36", "#75CDD7", "#29B5E8", "#5B5B5B"]
    obj_tile_html = ""
    if not df_obj_exp.empty and "OBJECT_TYPE" in df_obj_exp.columns and "OBJECT_COUNT" in df_obj_exp.columns:
        df_sorted = df_obj_exp.sort_values("OBJECT_COUNT", ascending=False)
        n_cols = 4
        tile_css = (
            "display:grid;"
            f"grid-template-columns:repeat({n_cols},1fr);"
            "gap:8px;padding:8px 0;"
        )
        tiles_inner = ""
        for i, (_, row) in enumerate(df_sorted.iterrows()):
            bg = _OBJ_COLORS[i % len(_OBJ_COLORS)]
            obj_type = _esc(str(row["OBJECT_TYPE"]))
            count = f"{int(row['OBJECT_COUNT']):,}"
            tiles_inner += (
                f'<div style="background:{bg};color:#fff;border-radius:6px;'
                f'padding:14px 10px;text-align:center;min-height:72px;'
                f'display:flex;flex-direction:column;justify-content:center;">'
                f'<div style="font-size:11px;font-weight:700;margin-bottom:4px;">{obj_type}</div>'
                f'<div style="font-size:22px;font-weight:800;">{count}</div>'
                f'</div>'
            )
        obj_tile_html = _full_wrap(f'<div style="{tile_css}">{tiles_inner}</div>')

    sub_sections.append(build_sub_section("Database Object Count", kpis=[], charts_html=obj_tile_html))

    # ── Clustering ────────────────────────────────────────────────────────
    cl_kpis = []
    if not df_cl_ov.empty:
        r = df_cl_ov.iloc[0]
        for col, label in [("TOTAL_TABLES", "Total Tables"), ("CLUSTERED_TABLES", "Clustered"),
                           ("UNCLUSTERED_TABLES", "Unclustered"), ("CLUSTER_PERCENTAGE", "Cluster %")]:
            if col in df_cl_ov.columns:
                suf = "%" if "PERCENTAGE" in col else ""
                cl_kpis.append({"value": f"{_fmt_num(_row0(df_cl_ov, col), 1 if 'PERCENTAGE' in col else 0)}{suf}",
                                 "label": label})

    cl_html = ""
    if not df_cl_ov.empty and "CLUSTERED_TABLES" in df_cl_ov.columns:
        r       = df_cl_ov.iloc[0]
        clust   = int(r.get("CLUSTERED_TABLES", 0) or 0)
        unclust = int(r.get("UNCLUSTERED_TABLES", 0) or 0)
        if clust + unclust > 0:
            cl_html += _col_wrap(build_chart("doughnut",
                labels=["Unclustered", "Clustered"],
                data=[unclust, clust], colors=[_A, _P],
                title="Clustered vs Unclustered Tables"))

    if not df_cred.empty:
        date_col = _col(df_cred, "CLUSTER_DATE", "USAGE_DATE", "START_DATE")
        cred_col = _col(df_cred, "DAILY_CREDITS", "CREDITS_USED", "TOTAL_CREDITS")
        if date_col and cred_col:
            cl_html += _col_wrap(build_chart("line",
                labels=[str(d) for d in df_cred[date_col].tolist()],
                datasets=[{"label": "Credits",
                           "data": [round(float(v), 2) for v in df_cred[cred_col].tolist()],
                           "borderColor": _P, "backgroundColor": "rgba(41,181,232,0.15)", "fill": True}],
                title="Clustering Credits (Last 30 Days)", y_title="Credits"))

    if cl_html:
        cl_html = _charts_row(cl_html)

    if not df_cl_t.empty:
        lbl_col = _col(df_cl_t, "FULL_TABLE_NAME", "TABLE_NAME")
        cols_map = [(lbl_col, "Table"), ("CLUSTERING_KEY", "Clustering Key"),
                    ("ROW_COUNT", "Rows"), ("SIZE_GB", "Size (GB)"),
                    ("AUTO_CLUSTERING_ON", "Auto Clustering"), ("CREATED", "Created")]
        cols_avail = [(raw, hdr) for raw, hdr in cols_map if raw and raw in df_cl_t.columns]
        if cols_avail:
            raw_cols = [r for r, _ in cols_avail]
            hdr_cols = [h for _, h in cols_avail]
            cl_html += _subtitle("Clustered Tables")
            cl_html += _make_table(hdr_cols, df_cl_t.head(30)[raw_cols].values.tolist())

    if not df_cc.empty:
        tbl_col  = _col(df_cc, "TABLE_NAME")
        cred_col = _col(df_cc, "CLUSTERING_CREDITS", "CREDITS", "TOTAL_CREDITS", "CREDITS_USED")
        if tbl_col and cred_col:
            top_cc = df_cc[df_cc[cred_col].astype(float) > 0].head(20) if cred_col in df_cc.columns else df_cc.head(20)
            if top_cc.empty:
                top_cc = df_cc.head(20)
            if not top_cc.empty:
                cl_html += _full_wrap(build_chart("hbar",
                    labels=_trunc(top_cc[tbl_col].tolist()),
                    datasets=[{"label": "Credits",
                               "data": [round(float(v), 4) for v in top_cc[cred_col].tolist()],
                               "backgroundColor": _A}],
                    title="Clustering Cost by Table — Credits (30d)", x_title="Credits"))
                cc_cols_map = [(tbl_col, "Table"), (cred_col, "Credits (30d)"),
                               ("AVG_CREDITS_PER_DAY", "Avg Credits/Day"), ("AUTO_CLUSTERING_ON", "Auto Clustering")]
                cc_avail = [(raw, hdr) for raw, hdr in cc_cols_map if raw and raw in top_cc.columns]
                if cc_avail:
                    cl_html += _subtitle("Clustering Cost Detail")
                    cl_html += _make_table([h for _, h in cc_avail],
                                           top_cc[[r for r, _ in cc_avail]].values.tolist())

    sub_sections.append(build_sub_section("Clustering", kpis=cl_kpis, charts_html=cl_html))

    # ── Low Lifespan Tables ───────────────────────────────────────────────
    ll_kpis = []
    if not df_ll.empty:
        r = df_ll.iloc[0]
        for col, label, fmt, suf in [
            ("TOTAL_SHORT_LIVED",       "Short-Lived Tables", 0, ""),
            ("PERMANENT_SHORT_LIVED",   "Permanent (Issue)",  0, ""),
            ("TRANSIENT_SHORT_LIVED",   "Transient (OK)",     0, ""),
            ("AVG_LIFESPAN_MINUTES",    "Avg Lifespan",       0, " min"),
            ("TOTAL_CHURNED_STORAGE_GB","Churned Storage",    2, " GB"),
        ]:
            if col in df_ll.columns:
                val = _row0(df_ll, col)
                ll_kpis.append({"value": f"{_fmt_num(val, fmt)}{suf}", "label": label})

    ll_html = ""
    if not df_ll.empty:
        r    = df_ll.iloc[0]
        perm = float(r.get("PERMANENT_SHORT_LIVED", 0) or 0)
        tran = float(r.get("TRANSIENT_SHORT_LIVED", 0) or 0)
        if perm + tran > 0:
            ll_html += _col_wrap(build_chart("doughnut",
                labels=["Permanent (Issue)", "Transient (OK)"],
                data=[int(perm), int(tran)], colors=[_A, _P],
                title="Short-Lived by Table Type"))

    if not df_ll_agg.empty:
        cat_col   = "Table Category" if "Table Category" in df_ll_agg.columns else None
        count_col = "Count of Short-Lived Tables" if "Count of Short-Lived Tables" in df_ll_agg.columns else None
        life_col  = "Avg Lifespan (Minutes)" if "Avg Lifespan (Minutes)" in df_ll_agg.columns else None
        if cat_col and count_col:
            datasets = [{"label": "Table Count",
                         "data": [int(v) for v in df_ll_agg[count_col].tolist()],
                         "backgroundColor": _P}]
            if life_col:
                datasets.append({"label": "Avg Lifespan (Min)",
                                  "data": [round(float(v), 1) for v in df_ll_agg[life_col].tolist()],
                                  "backgroundColor": _A})
            ll_html += _col_wrap(build_chart("hbar",
                labels=_trunc(df_ll_agg[cat_col].tolist()),
                datasets=datasets,
                title="Tables by Type", x_title="Count / Minutes"))

    if ll_html:
        ll_html = _charts_row(ll_html)

    if not df_ll_t.empty:
        lbl_col = _col(df_ll_t, "FULL_TABLE_NAME", "TABLE_NAME")
        cols_map = [(lbl_col, "Table"), ("TABLE_OWNER", "Owner"), ("TABLE_TYPE", "Type"),
                    ("CREATED", "Created"), ("DELETED", "Deleted"),
                    ("LIFESPAN_MINUTES", "Lifespan (min)"), ("SIZE_MB", "Size (MB)")]
        cols_avail = [(raw, hdr) for raw, hdr in cols_map if raw and raw in df_ll_t.columns]
        if cols_avail:
            ll_html += _subtitle("Short-Lived Table Details (Last 30 Days, <24h Lifespan)")
            ll_html += _make_table([h for _, h in cols_avail],
                                    df_ll_t.head(30)[[r for r, _ in cols_avail]].values.tolist())

    if not df_ll_s.empty:
        schema_col = _col(df_ll_s, "SCHEMA_NAME", "SCHEMA")
        count_col  = _col(df_ll_s, "SHORT_LIVED_COUNT", "SHORT_LIVED")
        if schema_col and count_col:
            ll_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(df_ll_s[schema_col].head(15).tolist()),
                    datasets=[{"label": "Short-Lived Count",
                               "data": [int(v) for v in df_ll_s[count_col].head(15).tolist()],
                               "backgroundColor": _A}],
                    title="Short-Lived Tables by Schema", x_title="Count")) +
                _col_wrap(_subtitle("Short-Lived Tables by Schema") + _make_table(
                    [c for c in df_ll_s.columns][:5],
                    df_ll_s.head(15)[[c for c in df_ll_s.columns][:5]].values.tolist()
                ))
            )

    sub_sections.append(build_sub_section("Low Lifespan Tables", kpis=ll_kpis, charts_html=ll_html))

    # ── High Churn Tables ─────────────────────────────────────────────────
    hc_kpis = []
    if not df_hc.empty:
        r = df_hc.iloc[0]
        for col, label, suf, dec in [
            ("TABLES_WITH_CHURN", "Tables with Churn",   "",   0),
            ("HIGH_CHURN_TABLES", "High Churn (>1x)",    "",   0),
            ("TOTAL_CHURN_TB",    "Total Churn Storage", " TB", 4),
            ("AVG_CHURN_RATIO",   "Avg Churn Ratio",     "x",  2),
        ]:
            if col in df_hc.columns:
                hc_kpis.append({"value": f"{_fmt_num(_row0(df_hc, col), dec)}{suf}", "label": label})

    hc_html = ""
    if not df_dbc.empty:
        db_col    = _col(df_dbc, "DATABASE_NAME", "TABLE_CATALOG")
        churn_col = _col(df_dbc, "TOTAL_CHURN_TB", "CHURN_TB")
        ratio_col = _col(df_dbc, "AVG_CHURN_RATIO", "AVG_RATIO")
        if db_col and churn_col:
            top15     = df_dbc.head(15)
            side_cols = [c for c in [db_col, churn_col, ratio_col] if c and c in df_dbc.columns]
            hc_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top15[db_col].tolist()),
                    datasets=[{"label": "Churn (TB)",
                               "data": [round(float(v), 4) for v in top15[churn_col].tolist()],
                               "backgroundColor": _A}],
                    title="Churn by Database (TB)", x_title="Churn (TB)")) +
                _col_wrap(_subtitle("Churn by Database") + _make_table(
                    side_cols,
                    df_dbc.head(15)[side_cols].values.tolist()
                ))
            )

    if not df_sav.empty:
        act_col = _col(df_sav, "OPTIMIZATION_ACTION", "ACTION", "RECOMMENDATION")
        sav_col = _col(df_sav, "POTENTIAL_SAVINGS_TB", "SAVINGS_TB")
        cnt_col = _col(df_sav, "AFFECTED_TABLES")
        usd_col = _col(df_sav, "EST_MONTHLY_SAVINGS_USD")
        if act_col and sav_col:
            hc_html += _full_wrap(build_chart("vbar",
                labels=_trunc(df_sav[act_col].tolist(), 60),
                datasets=[{"label": "Savings (TB)",
                           "data": [round(float(v), 4) for v in df_sav[sav_col].tolist()],
                           "backgroundColor": [_P, _S]}],
                title="Potential Storage Savings by Action (TB)", y_title="Savings (TB)"))
            sav_cols_map = [(act_col, "Action"), (cnt_col, "Tables Affected"),
                            (sav_col, "Savings (TB)"), (usd_col, "Est. Monthly Savings (USD)")]
            sav_avail = [(raw, hdr) for raw, hdr in sav_cols_map if raw and raw in df_sav.columns]
            if sav_avail:
                hc_html += _subtitle("Potential Storage Savings Summary")
                hc_html += _make_table([h for _, h in sav_avail],
                                        df_sav[[r for r, _ in sav_avail]].values.tolist())

    if not df_churn_det.empty and "CHURN_RATIO" in df_churn_det.columns:
        ratios = df_churn_det["CHURN_RATIO"].dropna().astype(float)
        buckets = {
            ">2x (Critical)":  int((ratios > 2).sum()),
            "1-2x (High)":     int(((ratios > 1) & (ratios <= 2)).sum()),
            "0.5-1x (Medium)": int(((ratios > 0.5) & (ratios <= 1)).sum()),
            "<0.5x (Low)":     int((ratios <= 0.5).sum()),
        }
        if any(v > 0 for v in buckets.values()):
            hc_html += _charts_row(
                _col_wrap(build_chart("doughnut",
                    labels=list(buckets.keys()),
                    data=list(buckets.values()),
                    colors=[_A, _P, _S, _T],
                    title="Churn Ratio Distribution"))
            )

    if not df_churn_det.empty:
        cols_map = [("TABLE_NAME", "Table"), ("TABLE_TYPE", "Type"),
                    ("ACTIVE_DATA_GB", "Active (GB)"), ("TIME_TRAVEL_GB", "Time Travel (GB)"),
                    ("FAILSAFE_GB", "Failsafe (GB)"), ("TOTAL_CHURN_GB", "Churn (GB)"),
                    ("CHURN_RATIO", "Churn Ratio")]
        cols_avail = [(raw, hdr) for raw, hdr in cols_map if raw in df_churn_det.columns]
        if cols_avail:
            hc_html += _subtitle("High Churn Table Detail")
            hc_html += _make_table([h for _, h in cols_avail],
                                    df_churn_det.head(20)[[r for r, _ in cols_avail]].values.tolist())

    sub_sections.append(build_sub_section("High Churn Tables", kpis=hc_kpis, charts_html=hc_html))

    return build_report(
        topic_name="Database Management",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ── Access Control ──────────────────────────────────────────────────────────

def export_access_control(account_name: str) -> str:
    df_roles  = _safe_df("auth_role_hygiene")
    df_priv   = _safe_df("ac_privileged_access")
    df_users  = _safe_df("auth_user_inventory")
    df_sec    = _safe_df("auth_security_hygiene")
    df_own    = _safe_df("auth_object_ownership")
    df_grants = _safe_df("ac_role_grant_dist")
    df_authn  = _safe_df("authn_auth_activity")
    df_fail   = _safe_df("authn_failure_analysis")
    df_cred   = _safe_df("authn_credential_hygiene")
    df_prov   = _safe_df("authn_provisioning_method")
    df_finds  = _safe_df("authn_findings")
    df_net    = _safe_df("net_policies_data")
    df_rules  = _safe_df("net_rules_data")
    df_dangl  = _safe_df("ac_dangling_net_policies")
    df_pat    = _safe_df("ac_pat_users")
    df_pwd    = _safe_df("authn_password_policies")
    df_sess   = _safe_df("authn_session_policies")
    df_nps    = _safe_df("ac_net_policy_summary")
    df_nrs    = _safe_df("ac_net_rules_summary")
    df_npa    = _safe_df("ac_net_policy_audit")

    top_kpis = []
    if not df_roles.empty:
        for col, label in [("TOTAL_ROLES", "Total Roles"), ("CUSTOM_ROLES", "Custom Roles"),
                           ("ORPHAN_ROLES", "Orphan Roles"), ("HERMIT_ROLES", "Hermit Roles")]:
            if col in df_roles.columns:
                top_kpis.append({"value": _fmt_num(_row0(df_roles, col), 0), "label": label})

    sub_sections = []

    # ── Authorization ─────────────────────────────────────────────────────
    auth_kpis = list(top_kpis)
    if not df_roles.empty and "ACTIVE_ROLES_60D" in df_roles.columns:
        auth_kpis.append({"value": _fmt_num(_row0(df_roles, "ACTIVE_ROLES_60D"), 0), "label": "Active Roles (60d)"})

    auth_html = ""
    if not df_roles.empty:
        custom = int(_row0(df_roles, "CUSTOM_ROLES", 0) or 0)
        total  = int(_row0(df_roles, "TOTAL_ROLES", 0) or 0)
        system = total - custom
        auth_html += _col_wrap(build_chart("vbar",
            labels=["Custom", "System"],
            datasets=[{"label": "Count", "data": [custom, system], "backgroundColor": _P}],
            title="Role Type Distribution", y_title="Count"))
        active   = int(_row0(df_roles, "ACTIVE_ROLES_60D", 0) or 0)
        inactive = int(_row0(df_roles, "INACTIVE_ROLES", total - active) or 0)
        auth_html += _col_wrap(build_chart("vbar",
            labels=["Active", "Inactive"],
            datasets=[{"label": "Count", "data": [active, inactive], "backgroundColor": _S}],
            title="Role Activity Status (60d)", y_title="Count"))
        orphan  = int(_row0(df_roles, "ORPHAN_ROLES", 0) or 0)
        hermit  = int(_row0(df_roles, "HERMIT_ROLES", 0) or 0)
        healthy = total - orphan - hermit
        auth_html += _col_wrap(build_chart("vbar",
            labels=["Healthy", "Orphan Only", "Hermit"],
            datasets=[{"label": "Count", "data": [max(0, healthy), orphan, hermit], "backgroundColor": [_P, _S, _A]}],
            title="Role Hierarchy Health", y_title="Count"))

    if auth_html:
        auth_html = _charts_row(auth_html)

    if not df_users.empty:
        u_kpis = []
        for col, label in [("TOTAL_USERS", "Total Users"), ("PERSON_USERS", "Person Users"),
                           ("SERVICE_USERS", "Service Users"), ("LEGACY_SERVICE_USERS", "Legacy Service"),
                           ("AVG_ROLES_PER_USER", "Avg Roles/User"), ("AVG_USERS_PER_ROLE", "Avg Users/Role"),
                           ("MAX_ROLES_SINGLE_USER", "Max Roles/User")]:
            if col in df_users.columns:
                u_kpis.append({"value": _fmt_num(_row0(df_users, col), 1 if "AVG" in col else 0), "label": label})

        if u_kpis:
            auth_html += '<div class="kpi-grid sub-kpis">'
            for k in u_kpis:
                auth_html += f'<div class="kpi-card"><div class="kpi-value">{_esc(k["value"])}</div><div class="kpi-label">{_esc(k["label"])}</div></div>'
            auth_html += "</div>"

        row_html = ""
        active_u  = int(_row0(df_users, "ACTIVE_USERS_60D", 0) or 0)
        inactive_u = int(_row0(df_users, "INACTIVE_USERS", 0) or 0)
        row_html += _col_wrap(build_chart("vbar",
            labels=["Active (60d)", "Inactive"],
            datasets=[{"label": "Users", "data": [active_u, inactive_u], "backgroundColor": _P}],
            title="User Activity Status", y_title="Users"))
        person = int(_row0(df_users, "PERSON_USERS", 0) or 0)
        svc    = int(_row0(df_users, "SERVICE_USERS", 0) or 0)
        legacy = int(_row0(df_users, "LEGACY_SERVICE_USERS", 0) or 0)
        other  = max(0, int(_row0(df_users, "TOTAL_USERS", 0) or 0) - person - svc - legacy)
        row_html += _col_wrap(build_chart("doughnut",
            labels=["Person", "Service", "Legacy Service", "Other"],
            data=[person, svc, legacy, other], colors=[_P, _S, _T, _A],
            title="User Type Distribution"))
        auth_html += _charts_row(row_html)

    if not df_sec.empty:
        sec_html = ""
        methods = ["Password", "OAuth", "Keypair", "SAML"]
        method_cols = ["USERS_USING_PASSWORD", "USERS_USING_OAUTH", "USERS_USING_KEYPAIR"]
        method_vals = [int(_row0(df_sec, c, 0) or 0) for c in method_cols if c in df_sec.columns]
        saml_val = 0
        method_vals.append(saml_val)
        if len(method_vals) == 4:
            sec_html += _col_wrap(build_chart("vbar",
                labels=methods,
                datasets=[{"label": "Distinct Users", "data": method_vals, "backgroundColor": [_P, _S, _T, _A]}],
                title="Auth Methods (last 30d)", y_title="Users"))

        risk_labels = ["Password w/o MFA", "Default ACCOUNTADMIN", "Admin Role Holders", "Keypair Users"]
        risk_cols   = ["UNHEALTHY_PASSWORD_NO_MFA", "DEFAULT_ROLE_ACCOUNTADMIN", "USERS_HOLDING_ADMIN_ROLES", "KEYPAIR_USERS_CHECK_NET_POLICY"]
        risk_vals   = [int(_row0(df_sec, c, 0) or 0) for c in risk_cols if c in df_sec.columns]
        if risk_vals:
            sec_html += _col_wrap(build_chart("vbar",
                labels=risk_labels[:len(risk_vals)],
                datasets=[{"label": "Count", "data": risk_vals, "backgroundColor": [_A, _S, _P, _T]}],
                title="Security Risk Indicators", y_title="Count"))

        if sec_html:
            auth_html += _charts_row(sec_html)

    if not df_own.empty:
        obj_type_col = _col(df_own, "OBJECT_TYPE", "GRANTED_ON")
        count_col    = _col(df_own, "OBJECT_COUNT", "COUNT")
        owner_col    = _col(df_own, "ROLE_OWNER", "GRANTEE_NAME")
        status_col   = _col(df_own, "STATUS")
        row_html = ""
        if owner_col and count_col:
            by_role = df_own.groupby(owner_col)[count_col].sum().sort_values(ascending=False).head(5)
            row_html += _col_wrap(build_chart("vbar",
                labels=_trunc(by_role.index.tolist()),
                datasets=[{"label": "Objects Owned", "data": [int(v) for v in by_role.values.tolist()], "backgroundColor": _S}],
                title="Objects Owned by Admin Roles", y_title="Objects"))
        if obj_type_col and count_col:
            by_type = df_own.groupby(obj_type_col)[count_col].sum().sort_values(ascending=False).head(12)
            row_html += _col_wrap(build_chart("hbar",
                labels=_trunc(by_type.index.tolist()),
                datasets=[{"label": "Objects", "data": [int(v) for v in by_type.values.tolist()], "backgroundColor": _T}],
                title="Admin-Owned Objects by Type", x_title="Objects"))
        if row_html:
            auth_html += _charts_row(row_html)
            own_map = [
                (owner_col or "", "Role"), (obj_type_col or "", "Object Type"),
                (count_col or "", "Count"), ("STATUS", "Status"),
            ]
            own_avail = [(r, h) for r, h in own_map if r and r in df_own.columns]
            if own_avail:
                auth_html += _make_table(
                    [h for _, h in own_avail],
                    df_own.head(25)[[r for r, _ in own_avail]].values.tolist(),
                )

    if not df_priv.empty:
        priv_role_col = _col(df_priv, "PRIVILEGED_ROLE")
        priv_user_col = _col(df_priv, "USER_NAME")
        priv_risk_col = _col(df_priv, "RISK_LEVEL")
        priv_row_html = ""
        if priv_role_col:
            by_priv = df_priv[priv_role_col].value_counts()
            priv_row_html += _col_wrap(build_chart("vbar",
                labels=_trunc(by_priv.index.tolist()),
                datasets=[{"label": "Users", "data": by_priv.values.tolist(), "backgroundColor": _P}],
                title="Users per Privileged Role", y_title="Users"))
        if priv_risk_col:
            by_risk = df_priv[priv_risk_col].value_counts()
            priv_row_html += _col_wrap(build_chart("doughnut",
                labels=by_risk.index.tolist(), data=by_risk.values.tolist(),
                colors=[_A, _S, _T, _P][:len(by_risk)],
                title="Privileged User Risk Distribution"))
        if priv_row_html:
            auth_html += _charts_row(priv_row_html)
            priv_map = [
                ("USER_NAME", "User"), ("PRIVILEGED_ROLE", "Role"),
                ("USER_TYPE", "Type"), ("DEFAULT_ROLE", "Default Role"),
                ("AUTH_METHOD", "Auth Method"), ("RISK_LEVEL", "Risk"),
                ("DAYS_SINCE_LOGIN", "Days Since Login"),
            ]
            priv_avail = [(r, h) for r, h in priv_map if r in df_priv.columns]
            if priv_avail:
                auth_html += _make_table(
                    [h for _, h in priv_avail],
                    df_priv.head(25)[[r for r, _ in priv_avail]].values.tolist(),
                )

    if not df_grants.empty:
        r_col = _col(df_grants, "ROLE_NAME", "GRANTEE_NAME")
        g_col = _col(df_grants, "TOTAL_GRANTS", "GRANT_COUNT")
        if r_col and g_col:
            top15 = df_grants.head(15)
            auth_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top15[r_col].tolist()),
                datasets=[{"label": "Grants", "data": [int(v) for v in top15[g_col].tolist()], "backgroundColor": _P}],
                title="Top Roles by Grant Count", x_title="Grant Count"))
            grant_map = [
                ("ROLE_NAME", "Role"), ("TOTAL_GRANTS", "Total Grants"),
                ("DISTINCT_OBJECT_TYPES", "Object Types"), ("OWNERSHIP_GRANTS", "Ownership"),
                ("ALL_PRIVILEGE_GRANTS", "ALL Privileges"), ("GRANT_CONCENTRATION", "Concentration"),
            ]
            grant_avail = [(r, h) for r, h in grant_map if r in df_grants.columns]
            if grant_avail:
                auth_html += _subtitle("Role Grant Distribution")
                auth_html += _make_table(
                    [h for _, h in grant_avail],
                    df_grants.head(20)[[r for r, _ in grant_avail]].values.tolist(),
                )

    sub_sections.append(build_sub_section("Authorization", kpis=auth_kpis, charts_html=auth_html))

    # ── Authentication ────────────────────────────────────────────────────
    authn_kpis = []
    authn_html = ""

    if not df_authn.empty:
        cnt_c = _col(df_authn, "LOGIN_ATTEMPTS")
        stat_c = _col(df_authn, "STATUS")
        total_logins = int(df_authn[cnt_c].sum()) if cnt_c else 0
        success = 0
        if stat_c and cnt_c:
            success = int(df_authn[df_authn[stat_c] == "Success"][cnt_c].sum())
        failed = total_logins - success
        authn_kpis = [
            {"value": _fmt_num(total_logins, 0), "label": "Total Logins (30d)"},
            {"value": _fmt_num(success, 0), "label": "Successful"},
            {"value": _fmt_num(failed, 0), "label": "Failed"},
        ]

        meth_col = _col(df_authn, "AUTH_METHOD", "FIRST_AUTHENTICATION_FACTOR")
        cnt_col  = _col(df_authn, "LOGIN_ATTEMPTS")
        client_col = _col(df_authn, "CLIENT_TYPE", "REPORTED_CLIENT_TYPE")

        row_html = ""
        if meth_col and cnt_col:
            by_meth = df_authn.groupby(meth_col)[cnt_col].sum().sort_values(ascending=False).head(10)
            row_html += _col_wrap(build_chart("vbar",
                labels=_trunc(by_meth.index.tolist()),
                datasets=[{"label": "Attempts", "data": [int(v) for v in by_meth.values.tolist()], "backgroundColor": _P}],
                title="Login Attempts by Auth Method", y_title="Attempts"))

        if stat_c and cnt_col:
            by_stat = df_authn.groupby(stat_c)[cnt_col].sum()
            row_html += _col_wrap(build_chart("doughnut",
                labels=by_stat.index.tolist(),
                data=[int(v) for v in by_stat.values.tolist()],
                colors=[_P, _A],
                title="Login Attempts by Status"))
        if row_html:
            authn_html += _charts_row(row_html)

        row2_html = ""
        if client_col and cnt_col:
            by_client = df_authn.groupby(client_col)[cnt_col].sum().sort_values(ascending=False).head(10)
            row2_html += _col_wrap(build_chart("hbar",
                labels=_trunc(by_client.index.tolist()),
                datasets=[{"label": "Attempts", "data": [int(v) for v in by_client.values.tolist()], "backgroundColor": _S}],
                title="Top Client Types", x_title="Attempts"))
        ip_col = _col(df_authn, "UNIQUE_IPS")
        if meth_col and ip_col:
            by_ip = df_authn.groupby(meth_col)[ip_col].sum().sort_values(ascending=False).head(10)
            row2_html += _col_wrap(build_chart("vbar",
                labels=_trunc(by_ip.index.tolist()),
                datasets=[{"label": "Unique IPs", "data": [int(v) for v in by_ip.values.tolist()], "backgroundColor": _T}],
                title="Unique IPs by Auth Method", y_title="Unique IPs"))
        if row2_html:
            authn_html += _charts_row(row2_html)

        authn_map = [
            ("AUTH_METHOD", "Auth Method"), ("STATUS", "Status"),
            ("CLIENT_TYPE", "Client Type"), ("LOGIN_ATTEMPTS", "Attempts"),
            ("UNIQUE_IPS", "Unique IPs"), ("UNIQUE_USERS", "Unique Users"),
            ("FIRST_SEEN", "First Seen"), ("LAST_SEEN", "Last Seen"),
            ("PCT_OF_TOTAL", "% Total"),
        ]
        authn_avail = [(r, h) for r, h in authn_map if r in df_authn.columns]
        if authn_avail:
            authn_html += _make_table(
                [h for _, h in authn_avail],
                df_authn.head(20)[[r for r, _ in authn_avail]].values.tolist(),
            )

    if not df_fail.empty:
        fail_html = ""
        sev_col = _col(df_fail, "SEVERITY")
        cnt_col = _col(df_fail, "FAILURE_COUNT")
        user_col = _col(df_fail, "USER_NAME")
        if sev_col and cnt_col:
            by_sev = df_fail.groupby(sev_col)[cnt_col].sum().sort_values(ascending=False)
            fail_html += _col_wrap(build_chart("vbar",
                labels=by_sev.index.tolist(),
                datasets=[{"label": "Failures", "data": [int(v) for v in by_sev.values.tolist()], "backgroundColor": [_A, _S, _T, _P]}],
                title="Failure Volume by Severity", y_title="Failures"))
        if user_col and cnt_col:
            top_fail = df_fail.groupby(user_col)[cnt_col].sum().sort_values(ascending=False).head(10)
            fail_html += _col_wrap(build_chart("hbar",
                labels=_trunc(top_fail.index.tolist()),
                datasets=[{"label": "Failures", "data": [int(v) for v in top_fail.values.tolist()], "backgroundColor": _A}],
                title="Top Users by Repeated Failures", x_title="Failures"))
        if fail_html:
            authn_html += _charts_row(fail_html)
            fail_map = [
                ("USER_NAME", "User"), ("ERROR_CODE", "Error Code"),
                ("ERROR_MESSAGE", "Error Message"), ("CLIENT_TYPE", "Client Type"),
                ("CLIENT_IP", "Client IP"), ("FAILURE_COUNT", "Failure Count"),
                ("FIRST_FAILURE", "First Failure"), ("LAST_FAILURE", "Last Failure"),
                ("SEVERITY", "Severity"),
            ]
            fail_avail = [(r, h) for r, h in fail_map if r in df_fail.columns]
            if fail_avail:
                authn_html += _make_table(
                    [h for _, h in fail_avail],
                    df_fail.head(20)[[r for r, _ in fail_avail]].values.tolist(),
                )

    if not df_cred.empty:
        auth_prof_col = _col(df_cred, "AUTH_PROFILE")
        user_col_c    = _col(df_cred, "USER_COUNT")
        if auth_prof_col and user_col_c:
            row_html = _col_wrap(build_chart("doughnut",
                labels=_trunc(df_cred[auth_prof_col].tolist()),
                data=[int(v) for v in df_cred[user_col_c].tolist()],
                colors=_PALETTE[:len(df_cred)],
                title="User Distribution by Auth Profile"))
            inactive_col = _col(df_cred, "INACTIVE_KEYPAIR_USERS")
            if inactive_col:
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(df_cred[auth_prof_col].tolist()),
                    datasets=[{"label": "Inactive Users", "data": [int(v) for v in df_cred[inactive_col].tolist()], "backgroundColor": _A}],
                    title="Inactive Keypair Users by Auth Profile", x_title="Inactive Users"))
            authn_html += _charts_row(row_html)
            cred_map = [
                ("AUTH_PROFILE", "Auth Profile"), ("USER_COUNT", "Users"),
                ("INACTIVE_KEYPAIR_USERS", "Inactive Keypair Users"),
            ]
            cred_avail = [(r, h) for r, h in cred_map if r in df_cred.columns]
            if cred_avail:
                authn_html += _make_table(
                    [h for _, h in cred_avail],
                    df_cred[[r for r, _ in cred_avail]].values.tolist(),
                )

    if not df_pwd.empty:
        authn_html += _subtitle("Policy Audit (Password & Session)")
        pwd_map = [
            ("POLICY_NAME", "Policy"), ("DATABASE", "DB"), ("SCHEMA", "Schema"),
            ("PASSWORD_MAX_AGE_DAYS", "Max Age"), ("PASSWORD_MIN_LENGTH", "Min Length"),
            ("PASSWORD_MAX_RETRIES", "Max Retries"), ("PASSWORD_LOCKOUT_TIME_MINS", "Lockout (mins)"),
            ("PASSWORD_HISTORY", "History"), ("COMMENT", "Comment"),
        ]
        pwd_avail = [(r, h) for r, h in pwd_map if r in df_pwd.columns]
        if pwd_avail:
            authn_html += _make_table(
                [h for _, h in pwd_avail],
                df_pwd[[r for r, _ in pwd_avail]].values.tolist(),
            )

    if not df_sess.empty:
        sess_map = [
            ("POLICY_NAME", "Policy"), ("DATABASE", "DB"), ("SCHEMA", "Schema"),
            ("SESSION_IDLE_TIMEOUT_MINS", "Idle Timeout"),
            ("SESSION_UI_IDLE_TIMEOUT_MINS", "UI Idle Timeout"), ("COMMENT", "Comment"),
        ]
        sess_avail = [(r, h) for r, h in sess_map if r in df_sess.columns]
        if sess_avail:
            authn_html += _make_table(
                [h for _, h in sess_avail],
                df_sess[[r for r, _ in sess_avail]].values.tolist(),
            )

    if not df_pat.empty:
        act_col  = _col(df_pat, "ACTIVITY_STATUS")
        type_col = _col(df_pat, "USER_TYPE")
        row_html = ""
        if act_col:
            by_act = df_pat[act_col].value_counts()
            row_html += _col_wrap(build_chart("doughnut",
                labels=by_act.index.tolist(), data=by_act.values.tolist(),
                colors=[_P, _A],
                title="PAT User Activity Status"))
        if type_col:
            by_type = df_pat[type_col].value_counts()
            row_html += _col_wrap(build_chart("vbar",
                labels=by_type.index.tolist(),
                datasets=[{"label": "Users", "data": by_type.values.tolist(), "backgroundColor": _S}],
                title="PAT Users by User Type", y_title="Users"))
        if row_html:
            authn_html += _charts_row(row_html)
            pat_map = [
                ("USER_NAME", "User"), ("USER_TYPE", "User Type"),
                ("DEFAULT_ROLE", "Default Role"), ("LAST_SUCCESS_LOGIN", "Last Success Login"),
                ("DAYS_SINCE_LOGIN", "Days Since Login"), ("ACTIVITY_STATUS", "Activity Status"),
            ]
            pat_avail = [(r, h) for r, h in pat_map if r in df_pat.columns]
            if pat_avail:
                authn_html += _make_table(
                    [h for _, h in pat_avail],
                    df_pat[[r for r, _ in pat_avail]].values.tolist(),
                )

    if not df_prov.empty:
        meth_col = _col(df_prov, "PROVISIONING_METHOD")
        role_col = _col(df_prov, "ROLE_COUNT")
        owner_col = _col(df_prov, "PROVISIONED_BY_ROLE")
        if meth_col and role_col:
            by_meth_prov = df_prov.groupby(meth_col)[role_col].sum().sort_values(ascending=False)
            authn_html += _full_wrap(build_chart("doughnut",
                labels=_trunc(by_meth_prov.index.tolist()),
                data=[int(v) for v in by_meth_prov.values.tolist()],
                colors=_PALETTE[:len(by_meth_prov)],
                title="Role Provisioning Method"))
            prov_map = [
                ("PROVISIONED_BY_ROLE", "Owner Role"), ("PROVISIONING_METHOD", "Method"),
                ("ROLE_COUNT", "Roles"),
            ]
            prov_avail = [(r, h) for r, h in prov_map if r in df_prov.columns]
            if prov_avail:
                authn_html += _subtitle("Provisioning Method (SCIM vs Manual)")
                prov_df = df_prov.sort_values(role_col, ascending=False) if role_col in df_prov.columns else df_prov
                pct_col = _col(df_prov, "PCT_OF_TOTAL")
                prov_full_map = list(prov_map)
                if pct_col:
                    prov_full_map.append(("PCT_OF_TOTAL", "% of Total"))
                prov_full_avail = [(r, h) for r, h in prov_full_map if r in df_prov.columns]
                if prov_full_avail:
                    authn_html += _make_table(
                        [h for _, h in prov_full_avail],
                        prov_df.head(20)[[r for r, _ in prov_full_avail]].values.tolist(),
                    )

    if not df_finds.empty:
        pkg_col  = _col(df_finds, "SCANNER_PACKAGE")
        open_col = _col(df_finds, "OPEN_FINDINGS")
        sev_col  = _col(df_finds, "FINDINGS_SEVERITY")
        if pkg_col and open_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_finds[pkg_col].head(10).tolist()),
                datasets=[{"label": "Open Findings", "data": [int(v) for v in df_finds[open_col].head(10).tolist()], "backgroundColor": _A}],
                title="Open Findings by Scanner Package", x_title="Open Findings"))
            if sev_col:
                by_sev = df_finds[sev_col].value_counts()
                row_html += _col_wrap(build_chart("doughnut",
                    labels=by_sev.index.tolist(), data=by_sev.values.tolist(),
                    colors=_PALETTE[:len(by_sev)],
                    title="Scanner Package Severity Distribution"))
            authn_html += _charts_row(row_html)
            finds_map = [
                ("SCANNER_PACKAGE", "Scanner Package"), ("LAST_SCAN_RUN", "Last Scan Run"),
                ("HOURS_SINCE_LAST_SCAN", "Hours Since Scan"),
                ("TOTAL_FINDINGS", "Total Findings"), ("OPEN_FINDINGS", "Open"),
                ("RESOLVED_FINDINGS", "Resolved"), ("SUPPRESSED_FINDINGS", "Suppressed"),
                ("FINDINGS_SEVERITY", "Severity"),
            ]
            finds_avail = [(r, h) for r, h in finds_map if r in df_finds.columns]
            if finds_avail:
                authn_html += _make_table(
                    [h for _, h in finds_avail],
                    df_finds.head(10)[[r for r, _ in finds_avail]].values.tolist(),
                )

    if authn_html or authn_kpis:
        sub_sections.append(build_sub_section("Authentication", kpis=authn_kpis, charts_html=authn_html))

    # ── Network Rules & Policies ──────────────────────────────────────────
    net_kpis = []
    net_html = ""

    if not df_nps.empty:
        for col, label in [("TOTAL_POLICIES", "Total Policies"), ("ACTIVE_POLICIES", "Active Policies")]:
            if col in df_nps.columns:
                net_kpis.append({"value": _fmt_num(_row0(df_nps, col), 0), "label": label})
    elif not df_net.empty:
        net_kpis.append({"value": str(len(df_net)), "label": "Total Policies"})

    if not df_nrs.empty:
        for col, label in [("TOTAL_RULES", "Total Rules"), ("ACTIVE_RULES", "Active Rules")]:
            if col in df_nrs.columns:
                net_kpis.append({"value": _fmt_num(_row0(df_nrs, col), 0), "label": label})
    elif not df_rules.empty:
        net_kpis.append({"value": str(len(df_rules)), "label": "Total Rules"})

    if not df_nps.empty and "USERS_WITH_POLICIES" in df_nps.columns:
        net_kpis.append({"value": _fmt_num(_row0(df_nps, "USERS_WITH_POLICIES"), 0), "label": "Users Covered"})

    if not df_nps.empty:
        acct_lev = int(_row0(df_nps, "ACCOUNT_LEVEL_POLICIES", 0) or 0)
        user_lev = int(_row0(df_nps, "USER_LEVEL_POLICIES", 0) or 0)
        integ = int(_row0(df_nps, "INTEGRATION_POLICIES", 0) or 0)
        if acct_lev or user_lev or integ:
            row_html = _col_wrap(build_chart("vbar",
                labels=["Account-Level", "User-Level", "Integration"],
                datasets=[{"label": "Policies", "data": [acct_lev, user_lev, integ], "backgroundColor": [_P, _S, _T]}],
                title="Policies by Enforcement Level", y_title="Policies"))
        else:
            row_html = ""

        if not df_rules.empty:
            mode_col = _col(df_rules, "RULE_MODE")
            if mode_col:
                by_mode_raw = df_rules[mode_col].value_counts()
                ingress = int(by_mode_raw.get("ingress", by_mode_raw.get("INGRESS", 0)))
                egress = int(by_mode_raw.get("egress", by_mode_raw.get("EGRESS", 0)))
                row_html += _col_wrap(build_chart("vbar",
                    labels=["Ingress", "Egress"],
                    datasets=[{"label": "Rules", "data": [ingress, egress], "backgroundColor": [_P, _A]}],
                    title="Network Rules by Direction", y_title="Rules"))
        if row_html:
            net_html += _charts_row(row_html)

    if not df_npa.empty:
        enf_col = _col(df_npa, "ENFORCEMENT_STATUS")
        if enf_col:
            by_enf = df_npa[enf_col].value_counts()
            row_html = _col_wrap(build_chart("doughnut",
                labels=by_enf.index.tolist(), data=by_enf.values.tolist(),
                colors=_PALETTE[:len(by_enf)],
                title="Policy Enforcement Status"))
            ua_col = _col(df_npa, "USER_ATTACHMENTS")
            pn_col = _col(df_npa, "POLICY_NAME")
            if ua_col and pn_col:
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(df_npa[pn_col].head(20).tolist()),
                    datasets=[{"label": "Users", "data": [int(v) for v in df_npa[ua_col].head(20).tolist()], "backgroundColor": _P}],
                    title="User Attachments per Policy", x_title="Users"))
            net_html += _charts_row(row_html)

            npa_map = [
                ("POLICY_NAME", "Policy"), ("OWNER", "Owner"),
                ("ENFORCEMENT_STATUS", "Status"),
                ("ACCOUNT_ATTACHMENTS", "Acct"), ("USER_ATTACHMENTS", "Users"),
                ("CREATED_DATE", "Created"), ("COMMENT", "Comment"),
            ]
            npa_avail = [(r, h) for r, h in npa_map if r in df_npa.columns]
            if npa_avail:
                net_html += _make_table(
                    [h for _, h in npa_avail],
                    df_npa.head(30)[[r for r, _ in npa_avail]].values.tolist(),
                )

    if not df_rules.empty:
        rule_status_col = _col(df_rules, "USAGE_STATUS")
        rule_mode_col   = _col(df_rules, "RULE_MODE")
        rule_type_col   = _col(df_rules, "RULE_TYPE")

        row_html = ""
        if rule_status_col:
            by_status = df_rules[rule_status_col].value_counts()
            row_html += _col_wrap(build_chart("doughnut",
                labels=by_status.index.tolist(), data=by_status.values.tolist(),
                colors=[_P, _A],
                title="Rule Attachment Status"))
        if rule_mode_col:
            by_mode = df_rules[rule_mode_col].value_counts()
            row_html += _col_wrap(build_chart("vbar",
                labels=by_mode.index.tolist(),
                datasets=[{"label": "Count", "data": by_mode.values.tolist(), "backgroundColor": [_P, _S]}],
                title="Rules by Direction", y_title="Count"))
        if rule_type_col:
            by_rtype = df_rules[rule_type_col].value_counts()
            row_html += _col_wrap(build_chart("hbar",
                labels=by_rtype.index.tolist(),
                datasets=[{"label": "Count", "data": by_rtype.values.tolist(), "backgroundColor": _T}],
                title="Rules by Type", x_title="Count"))
        if row_html:
            net_html += _charts_row(row_html)

        rules_map = [
            ("RULE_NAME", "Rule"), ("DATABASE", "DB"), ("SCHEMA", "Schema"),
            ("RULE_MODE", "Mode"), ("RULE_TYPE", "Type"),
            ("USAGE_STATUS", "Status"), ("REFERENCE_COUNT", "References"),
            ("OWNED_BY", "Owner"), ("CREATED_ON", "Created"), ("COMMENT", "Comment"),
        ]
        rules_avail = [(r, h) for r, h in rules_map if r in df_rules.columns]
        if rules_avail:
            net_html += _make_table(
                [h for _, h in rules_avail],
                df_rules.head(30)[[r for r, _ in rules_avail]].values.tolist(),
            )

    if not df_dangl.empty:
        dangl_map = [
            ("POLICY_NAME", "Policy"), ("OWNER", "Owner"),
            ("CREATED_DATE", "Created"), ("COMMENT", "Comment"),
            ("DAYS_SINCE_CREATED", "Days Old"), ("AGE_STATUS", "Age Status"),
        ]
        dangl_avail = [(r, h) for r, h in dangl_map if r in df_dangl.columns]
        if dangl_avail:
            net_html += _subtitle("Dangling Policies Detail")
            net_html += _make_table(
                [h for _, h in dangl_avail],
                df_dangl.head(20)[[r for r, _ in dangl_avail]].values.tolist(),
            )

    if net_html or net_kpis:
        sub_sections.append(build_sub_section("Network Rules & Policies", kpis=net_kpis, charts_html=net_html))

    return build_report(
        topic_name="Access Control",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ── Data Governance ─────────────────────────────────────────────────────────

def export_data_governance(account_name: str) -> str:
    df_health   = _safe_df("dg_health_score_data")      # DATABASE_NAME, TOTAL_TABLES, TAGGED_TABLES, UNTAGGED_TABLES, COVERAGE_PCT
    df_class    = _safe_df("dg_classification_data")    # APPLY_METHOD, TOTAL_TAGS, OBJECTS_COVERED
    df_pol      = _safe_df("dg_policy_inventory_data")  # POLICY_KIND, ACTIVE_COUNT
    df_tags_dom = _safe_df("dg_tag_assignments_by_domain")  # DOMAIN, ASSIGNMENT_COUNT
    df_top_tags = _safe_df("dg_top_tag_names")          # TAG_NAME, USAGE_COUNT
    df_mask_sum = _safe_df("dg_masking_pattern_summary") # MASKING_PATTERN, PATTERN_COUNT
    df_sens_tag = _safe_df("dg_sensitive_tagged")       # DATABASE_NAME, SCHEMA_NAME, TABLE_NAME, COLUMN_NAME, TAG_NAME, TAG_VALUE, APPLY_METHOD
    df_dep      = _safe_df("dg_downstream_deps")        # REFERENCED_OBJECT_DOMAIN, REFERENCING_OBJECT_DOMAIN (+others)
    df_dangl_gt = _safe_df("dg_dangling_gov_tags")      # DATABASE_NAME, DANGLING_TAGS
    df_det_mask = _safe_df("dg_detailed_masking_coverage")  # DATABASE_NAME, SCHEMA_NAME, TABLE_NAME, COLUMN_NAME, TAG_NAME, TAG_VALUE, POLICY_NAME, PROTECTION_STATUS

    top_kpis = []
    total_tbl = 0
    tagged_tbl = 0
    if not df_health.empty:
        total_tbl  = int(df_health["TOTAL_TABLES"].sum()) if "TOTAL_TABLES" in df_health.columns else 0
        tagged_tbl = int(df_health["TAGGED_TABLES"].sum()) if "TAGGED_TABLES" in df_health.columns else 0
        pct = round(tagged_tbl / total_tbl * 100, 1) if total_tbl > 0 else 0
        top_kpis = [
            {"value": _fmt_num(total_tbl, 0), "label": "Total Tables"},
            {"value": _fmt_num(tagged_tbl, 0), "label": "Tagged Tables"},
            {"value": f"{pct}%", "label": "Tag Coverage"},
        ]
        if not df_pol.empty:
            top_kpis.append({"value": _fmt_num(len(df_pol), 0), "label": "Active Policies"})

    sub_sections = []

    # ── Overview ──────────────────────────────────────────────────────────
    ov_kpis = list(top_kpis)
    ov_html = ""

    if not df_class.empty and "APPLY_METHOD" in df_class.columns and "TOTAL_TAGS" in df_class.columns:
        filt = df_class[df_class["TOTAL_TAGS"] > 0]
        if not filt.empty:
            ov_html += _col_wrap(build_chart("doughnut",
                labels=filt["APPLY_METHOD"].tolist(),
                data=[int(v) for v in filt["TOTAL_TAGS"].tolist()],
                colors=_PALETTE[:len(filt)],
                title="Tag Application Method"))

    if not df_pol.empty and "POLICY_KIND" in df_pol.columns:
        if "ACTIVE_COUNT" in df_pol.columns:
            by_kind = df_pol.groupby("POLICY_KIND")["ACTIVE_COUNT"].sum()
        else:
            by_kind = df_pol["POLICY_KIND"].value_counts()
        ov_html += _col_wrap(build_chart("vbar",
            labels=_trunc(by_kind.index.tolist()),
            datasets=[{"label": "Count", "data": [int(v) for v in by_kind.values.tolist()], "backgroundColor": _S}],
            title="Active Policies by Kind", y_title="Count"))

    if ov_html:
        ov_html = _charts_row(ov_html)

    sub_sections.append(build_sub_section("Overview", kpis=ov_kpis, charts_html=ov_html))

    # ── Data Object Tagging & Classification ──────────────────────────────
    tag_kpis = []
    tag_html = ""

    unique_tags  = len(df_top_tags) if not df_top_tags.empty else 0
    tag_refs     = int(df_tags_dom["ASSIGNMENT_COUNT"].sum()) if not df_tags_dom.empty and "ASSIGNMENT_COUNT" in df_tags_dom.columns else 0
    dbs_with_tags = 0
    if not df_health.empty and "TAGGED_TABLES" in df_health.columns and "DATABASE_NAME" in df_health.columns:
        dbs_with_tags = int((df_health["TAGGED_TABLES"] > 0).sum())

    if unique_tags > 0:
        tag_kpis.append({"value": _fmt_num(unique_tags, 0), "label": "Unique Tags"})
    if dbs_with_tags > 0:
        tag_kpis.append({"value": _fmt_num(dbs_with_tags, 0), "label": "Tag Databases"})
    if tag_refs > 0:
        tag_kpis.append({"value": _fmt_num(tag_refs, 0), "label": "Tag References"})
    if tagged_tbl > 0:
        tag_kpis.append({"value": _fmt_num(tagged_tbl, 0), "label": "Tagged Objects"})

    row_html = ""
    if not df_health.empty and "DATABASE_NAME" in df_health.columns and "TAGGED_TABLES" in df_health.columns:
        db_tagged = df_health[df_health["TAGGED_TABLES"] > 0].sort_values("TAGGED_TABLES", ascending=False).head(10)
        if not db_tagged.empty:
            row_html += _col_wrap(build_chart("hbar",
                labels=_trunc(db_tagged["DATABASE_NAME"].tolist()),
                datasets=[{"label": "Tagged Tables", "data": [int(v) for v in db_tagged["TAGGED_TABLES"].tolist()], "backgroundColor": _P}],
                title="Tagged Tables by Database", x_title="Tagged Tables"))

    if not df_tags_dom.empty and "DOMAIN" in df_tags_dom.columns and "ASSIGNMENT_COUNT" in df_tags_dom.columns:
        row_html += _col_wrap(build_chart("doughnut",
            labels=_trunc(df_tags_dom["DOMAIN"].head(6).tolist()),
            data=[int(v) for v in df_tags_dom["ASSIGNMENT_COUNT"].head(6).tolist()],
            colors=_PALETTE[:6],
            title="Tag References by Domain"))

    if row_html:
        tag_html += _charts_row(row_html)

    if total_tbl > 0:
        tag_html += _full_wrap(build_chart("doughnut",
            labels=["Untagged", "Tagged"],
            data=[total_tbl - tagged_tbl, tagged_tbl],
            colors=[_P, _S],
            title="Tagged vs Untagged Tables"))

    if not df_top_tags.empty and "TAG_NAME" in df_top_tags.columns and "USAGE_COUNT" in df_top_tags.columns:
        top15 = df_top_tags.head(15)
        tag_html += _full_wrap(build_chart("hbar",
            labels=_trunc(top15["TAG_NAME"].tolist()),
            datasets=[{"label": "References", "data": [int(v) for v in top15["USAGE_COUNT"].tolist()], "backgroundColor": _S}],
            title="Top 15 Tag Names by Reference Count", x_title="References"))
        tag_html += _subtitle("Top Tag Names")
        tag_html += _make_table(["Tag Name", "References"], top15[["TAG_NAME", "USAGE_COUNT"]].values.tolist())

    if not df_sens_tag.empty and "TAG_NAME" in df_sens_tag.columns and "COLUMN_NAME" in df_sens_tag.columns:
        by_tag = df_sens_tag.groupby("TAG_NAME")["COLUMN_NAME"].count().reset_index()
        by_tag.columns = ["TAG_NAME", "TAGGED_COLUMNS"]
        by_tag = by_tag.sort_values("TAGGED_COLUMNS", ascending=False).head(10)
        if not by_tag.empty:
            tag_html += _full_wrap(build_chart("hbar",
                labels=_trunc(by_tag["TAG_NAME"].tolist()),
                datasets=[{"label": "Tagged Columns", "data": [int(v) for v in by_tag["TAGGED_COLUMNS"].tolist()], "backgroundColor": _T}],
                title="Sensitive Columns by Tag", x_title="Tagged Columns"))
        cols_map = [("DATABASE_NAME", "Database"), ("SCHEMA_NAME", "Schema"),
                    ("TABLE_NAME", "Table"), ("COLUMN_NAME", "Column"),
                    ("TAG_NAME", "Tag Name"), ("TAG_VALUE", "Tag Value"),
                    ("APPLY_METHOD", "Apply Method")]
        cols_avail = [(r, h) for r, h in cols_map if r in df_sens_tag.columns]
        if cols_avail:
            raw_cols = [r for r, _ in cols_avail]
            hdr_cols = [h for _, h in cols_avail]
            tag_html += _subtitle("Classification Insights Detail")
            tag_html += _make_table(hdr_cols, df_sens_tag.head(30)[raw_cols].values.tolist())

    if tag_html or tag_kpis:
        sub_sections.append(build_sub_section("Data Object Tagging & Classification",
                                               kpis=tag_kpis, charts_html=tag_html))

    # ── Data Privacy & Protection ─────────────────────────────────────────
    priv_html = ""
    priv_kpis = []

    if not df_pol.empty and "POLICY_KIND" in df_pol.columns:
        act_col = "ACTIVE_COUNT" if "ACTIVE_COUNT" in df_pol.columns else None
        mask_rows = df_pol[df_pol["POLICY_KIND"].str.contains("MASKING", na=False)]
        raw_rows  = df_pol[df_pol["POLICY_KIND"].str.contains("ROW_ACCESS", na=False)]
        mask_cnt  = int(mask_rows[act_col].sum()) if act_col else len(mask_rows)
        raw_cnt   = int(raw_rows[act_col].sum())  if act_col else len(raw_rows)
        pol_refs  = int(df_pol[act_col].sum())    if act_col else len(df_pol)

        priv_kpis.append({"value": _fmt_num(mask_cnt, 0), "label": "Masking Policies"})
        if pol_refs > 0:
            priv_kpis.append({"value": _fmt_num(pol_refs, 0), "label": "Policy References"})
        if raw_cnt > 0:
            priv_kpis.append({"value": _fmt_num(raw_cnt, 0), "label": "Row Access Policies"})

        if act_col:
            by_kind = df_pol.groupby("POLICY_KIND")[act_col].sum()
        else:
            by_kind = df_pol["POLICY_KIND"].value_counts()

        row_html = _col_wrap(build_chart("doughnut",
            labels=by_kind.index.tolist(),
            data=[int(v) for v in by_kind.values.tolist()],
            colors=_PALETTE[:len(by_kind)],
            title="Policies by Type"))
        row_html += _col_wrap(build_chart("vbar",
            labels=by_kind.index.tolist(),
            datasets=[{"label": "References", "data": [int(v) for v in by_kind.values.tolist()], "backgroundColor": _S}],
            title="Policy References by Type", y_title="References"))
        priv_html += _charts_row(row_html)

    if not df_det_mask.empty and "PROTECTION_STATUS" in df_det_mask.columns:
        prot_counts = df_det_mask["PROTECTION_STATUS"].value_counts()
        labels = ["Protected (Masked)" if l == "PROTECTED" else "Unprotected" for l in prot_counts.index]
        priv_html += _full_wrap(build_chart("doughnut",
            labels=labels,
            data=[int(v) for v in prot_counts.values.tolist()],
            colors=[_S, _P],
            title="Sensitive Column Protection Status"))

    if not df_mask_sum.empty and "MASKING_PATTERN" in df_mask_sum.columns and "PATTERN_COUNT" in df_mask_sum.columns:
        priv_html += _full_wrap(build_chart("doughnut",
            labels=_trunc(df_mask_sum["MASKING_PATTERN"].head(6).tolist()),
            data=[int(v) for v in df_mask_sum["PATTERN_COUNT"].head(6).tolist()],
            colors=_PALETTE[:6],
            title="Masking Policy Pattern Distribution"))

    if not df_det_mask.empty:
        cols_map = [("DATABASE_NAME", "Database"), ("SCHEMA_NAME", "Schema"),
                    ("TABLE_NAME", "Table"), ("COLUMN_NAME", "Column"),
                    ("TAG_NAME", "Tag Name"), ("TAG_VALUE", "Tag Value")]
        cols_avail = [(r, h) for r, h in cols_map if r in df_det_mask.columns]
        if cols_avail:
            raw_cols = [r for r, _ in cols_avail]
            hdr_cols = [h for _, h in cols_avail]
            priv_html += _subtitle("Sensitive Column Masking Coverage")
            priv_html += _make_table(hdr_cols, df_det_mask.head(30)[raw_cols].values.tolist())

    if priv_html:
        sub_sections.append(build_sub_section("Data Privacy & Protection", kpis=priv_kpis, charts_html=priv_html))

    # ── Data Lineage & Quality (Lite) ──────────────────────────────────────
    if not df_dep.empty:
        ref_dom = "REFERENCED_OBJECT_DOMAIN"
        ref_ing = "REFERENCING_OBJECT_DOMAIN"
        if ref_dom in df_dep.columns and ref_ing in df_dep.columns:
            dep_work = df_dep.copy()
            dep_work["TYPE_PAIR"] = dep_work[ref_dom] + " → " + dep_work[ref_ing]
            pair_counts = dep_work.groupby("TYPE_PAIR").size().reset_index(name="DEPENDENCIES")
            pair_counts = pair_counts.sort_values("DEPENDENCIES", ascending=False).head(15)
            if not pair_counts.empty:
                dep_html = _full_wrap(build_chart("hbar",
                    labels=_trunc(pair_counts["TYPE_PAIR"].tolist()),
                    datasets=[{"label": "Dependencies", "data": [int(v) for v in pair_counts["DEPENDENCIES"].tolist()], "backgroundColor": _P}],
                    title="Object Dependencies by Type Pair"))
                dep_html += _subtitle("Dependency Detail")
                dep_html += _make_table(["Object Type Pair", "Dependencies"],
                    pair_counts[["TYPE_PAIR", "DEPENDENCIES"]].values.tolist())
                sub_sections.append(build_sub_section("Data Lineage & Quality (Lite)", charts_html=dep_html))

    return build_report(
        topic_name="Data Governance",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ── Data Ingestion ──────────────────────────────────────────────────────────

def export_data_ingestion(account_name: str) -> str:
    df_bulk     = _safe_df("ig_bulk_load")
    df_pipe_eff = _safe_df("ig_pipe_efficiency")
    df_pipe_det = _safe_df("ig_snowpipe_detail")
    df_proj     = _safe_df("ig_pipe_cost_projection")
    df_stream   = _safe_df("ingestion_streaming_data")
    df_summary  = _safe_df("ingestion_summary_data")
    df_stream_b = _safe_df("ingestion_streaming_breakdown")

    top_kpis = []
    if not df_bulk.empty:
        tbl_col  = _col(df_bulk, "TARGET_TABLE")
        gb_col   = _col(df_bulk, "TOTAL_GB")
        jobs_col = _col(df_bulk, "JOB_COUNT")
        top_kpis = [
            {"value": str(len(df_bulk)), "label": "Tables Loaded"},
            {"value": _fmt_num(df_bulk[jobs_col].sum(), 0) if jobs_col else "—", "label": "Total Load Events"},
            {"value": f"{_fmt_num(df_bulk[gb_col].sum(), 2)} GB" if gb_col else "—", "label": "Total GB Ingested"},
        ]

    sub_sections = []

    # ── Bulk Load (COPY INTO) Analysis ────────────────────────────────────
    bulk_html = ""
    if not df_bulk.empty:
        tbl_col    = _col(df_bulk, "TARGET_TABLE")
        gb_col     = _col(df_bulk, "TOTAL_GB")
        jobs_col   = _col(df_bulk, "JOB_COUNT")
        rows_col   = _col(df_bulk, "TOTAL_ROWS_LOADED")
        file_col   = _col(df_bulk, "AVG_FILE_MB")
        health_col = _col(df_bulk, "HEALTH_CHECK")
        rec_col    = _col(df_bulk, "RECOMMENDATION")

        vol_map = [("TARGET_TABLE", "Target Table"), ("JOB_COUNT", "Job Count"),
                   ("TOTAL_GB", "Total GB"), ("TOTAL_ROWS_LOADED", "Rows Loaded"),
                   ("AVG_FILE_MB", "Avg File MB"), ("HEALTH_CHECK", "Health")]
        vol_avail = [(r, h) for r, h in vol_map if r in df_bulk.columns]

        if tbl_col and gb_col:
            top10 = df_bulk.head(10)
            bulk_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10[tbl_col].tolist()),
                    datasets=[{"label": "Total GB", "data": [round(float(v), 2) for v in top10[gb_col].tolist()], "backgroundColor": _P}],
                    title="Top Tables by Volume Ingested (GB)", x_title="Total GB")) +
                _col_wrap(_subtitle("Top Tables by Volume Ingested") + _make_table(
                    [h for _, h in vol_avail],
                    top10[[r for r, _ in vol_avail]].values.tolist())))

        if tbl_col and jobs_col:
            top10j = df_bulk.nlargest(10, jobs_col)
            bulk_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10j[tbl_col].tolist()),
                    datasets=[{"label": "Load Events", "data": [int(v) for v in top10j[jobs_col].tolist()], "backgroundColor": _S}],
                    title="Load Events by Table", x_title="Load Events")) +
                _col_wrap(_subtitle("Load Events by Table") + _make_table(
                    [h for _, h in vol_avail],
                    top10j[[r for r, _ in vol_avail]].values.tolist())))

        if tbl_col and file_col:
            top10f = df_bulk.nlargest(10, file_col)
            file_map = [("TARGET_TABLE", "Target Table"), ("AVG_FILE_MB", "Avg File MB"),
                        ("MIN_FILE_MB", "Min File MB"), ("MAX_FILE_MB", "Max File MB"),
                        ("STDDEV_FILE_MB", "Stddev File MB"), ("RECOMMENDATION", "Recommendation")]
            file_avail = [(r, h) for r, h in file_map if r in df_bulk.columns]
            bulk_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10f[tbl_col].tolist()),
                    datasets=[{"label": "Avg File MB", "data": [round(float(v), 2) for v in top10f[file_col].tolist()], "backgroundColor": _T}],
                    title="Average File Size by Table (MB)", x_title="Avg File (MB)")) +
                _col_wrap(_subtitle("Average File Size by Table") + _make_table(
                    [h for _, h in file_avail],
                    top10f[[r for r, _ in file_avail]].values.tolist())))

        if tbl_col and rows_col:
            top10r = df_bulk.nlargest(10, rows_col)
            rows_map = [("TARGET_TABLE", "Target Table"), ("TOTAL_ROWS_LOADED", "Rows Loaded"),
                        ("JOB_COUNT", "Job Count"), ("TOTAL_GB", "Total GB"),
                        ("HEALTH_CHECK", "Health"), ("RECOMMENDATION", "Recommendation")]
            rows_avail = [(r, h) for r, h in rows_map if r in df_bulk.columns]
            bulk_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10r[tbl_col].tolist()),
                    datasets=[{"label": "Rows Loaded", "data": [int(v) for v in top10r[rows_col].tolist()], "backgroundColor": _S}],
                    title="Rows Loaded by Table", x_title="Rows Loaded")) +
                _col_wrap(_subtitle("Rows Loaded by Table") + _make_table(
                    [h for _, h in rows_avail],
                    top10r[[r for r, _ in rows_avail]].values.tolist())))

        if health_col:
            by_health = df_bulk[health_col].value_counts()
            bulk_html += _full_wrap(build_chart("vbar",
                labels=by_health.index.tolist(),
                datasets=[{"label": "Tables", "data": by_health.values.tolist(),
                           "backgroundColor": [_P, _A][:len(by_health)]}],
                title="Bulk Load Health Status Distribution", y_title="Tables"))

            health_map = [("TARGET_TABLE", "Target Table"), ("HEALTH_CHECK", "Health"),
                          ("AVG_FILE_MB", "Avg File MB"), ("MAX_FILE_MB", "Max File MB"),
                          ("RECOMMENDATION", "Recommendation")]
            health_avail = [(r, h) for r, h in health_map if r in df_bulk.columns]
            if health_avail:
                bulk_html += _subtitle("Bulk Load Health Detail")
                bulk_html += _make_table(
                    [h for _, h in health_avail],
                    df_bulk[[r for r, _ in health_avail]].values.tolist())

            if rec_col:
                rec_map = [("TARGET_TABLE", "Target Table"), ("HEALTH_CHECK", "Health"),
                           ("RECOMMENDATION", "Recommendation")]
                rec_avail = [(r, h) for r, h in rec_map if r in df_bulk.columns]
                if rec_avail:
                    bulk_html += _subtitle("Bulk Load Recommendations")
                    bulk_html += _make_table(
                        [h for _, h in rec_avail],
                        df_bulk[[r for r, _ in rec_avail]].values.tolist())

        bulk_kpis = [
            {"value": str(len(df_bulk)), "label": "Tables Loaded"},
            {"value": _fmt_num(df_bulk[jobs_col].sum(), 0) if jobs_col else "—", "label": "Total Load Events"},
            {"value": f"{_fmt_num(df_bulk[gb_col].sum(), 2)} GB" if gb_col else "—", "label": "Total GB Ingested"},
        ]
        if health_col:
            healthy = len(df_bulk[df_bulk[health_col].str.contains("Healthy", na=False)])
            bulk_kpis.append({"value": f"{healthy} / {len(df_bulk)}", "label": "Healthy Tables"})

        sub_sections.append(build_sub_section("Bulk Load (COPY INTO) Analysis",
                                               kpis=bulk_kpis, charts_html=bulk_html))

    # ── Snowpipe Analysis (Cost vs. Volume) ───────────────────────────────
    pipe_html = ""
    if not df_pipe_eff.empty:
        pipe_col  = _col(df_pipe_eff, "PIPE_NAME")
        cred_col  = _col(df_pipe_eff, "CREDITS_USED")
        files_col = _col(df_pipe_eff, "FILES_LOADED")
        gb_col    = _col(df_pipe_eff, "GB_INGESTED")
        rows_col  = _col(df_pipe_eff, "ROWS_LOADED")
        cr_gb_col = _col(df_pipe_eff, "CREDITS_PER_GB")
        stat_col  = _col(df_pipe_eff, "EFFICIENCY_STATUS")
        rec_col   = _col(df_pipe_eff, "RECOMMENDATION")
        fmb_col   = _col(df_pipe_eff, "AVG_FILE_MB")

        pipe_kpis = [{"value": str(len(df_pipe_eff)), "label": "Active Pipes"}]
        if gb_col:
            pipe_kpis.append({"value": f"{_fmt_num(df_pipe_eff[gb_col].sum(), 2)} GB", "label": "Data Ingested"})
        if cred_col:
            pipe_kpis.append({"value": _fmt_num(df_pipe_eff[cred_col].sum(), 2), "label": "Credits Used"})

        cred_map = [("PIPE_NAME", "Pipe"), ("FILES_LOADED", "Files Loaded"),
                    ("GB_INGESTED", "GB Ingested"), ("ROWS_LOADED", "Rows Loaded"),
                    ("AVG_FILE_MB", "Avg File MB"), ("CREDITS_USED", "Credits Used"),
                    ("EFFICIENCY_STATUS", "Status")]
        cred_avail = [(r, h) for r, h in cred_map if r in df_pipe_eff.columns]

        if pipe_col and cred_col:
            top10 = df_pipe_eff.head(10)
            pipe_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10[pipe_col].tolist()),
                    datasets=[{"label": "Credits", "data": [round(float(v), 4) for v in top10[cred_col].tolist()], "backgroundColor": _P}],
                    title="Credits Used by Pipe (30d)", x_title="Credits")) +
                _col_wrap(_subtitle("Credits Used by Pipe") + _make_table(
                    [h for _, h in cred_avail],
                    top10[[r for r, _ in cred_avail]].values.tolist())))

        files_map = [("PIPE_NAME", "Pipe"), ("FILES_LOADED", "Files Loaded"),
                     ("ROWS_LOADED", "Rows Loaded"), ("AVG_FILE_MB", "Avg File MB"),
                     ("CREDITS_USED", "Credits Used"), ("EFFICIENCY_STATUS", "Status")]
        files_avail = [(r, h) for r, h in files_map if r in df_pipe_eff.columns]

        if pipe_col and files_col:
            top10 = df_pipe_eff.head(10)
            pipe_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10[pipe_col].tolist()),
                    datasets=[{"label": "Files", "data": [int(v) for v in top10[files_col].tolist()], "backgroundColor": _S}],
                    title="Files Loaded by Pipe (30d)", x_title="Files")) +
                _col_wrap(_subtitle("Files Loaded by Pipe") + _make_table(
                    [h for _, h in files_avail],
                    top10[[r for r, _ in files_avail]].values.tolist())))

        gb_map = [("PIPE_NAME", "Pipe"), ("GB_INGESTED", "GB Ingested"),
                  ("ROWS_LOADED", "Rows Loaded"), ("CREDITS_USED", "Credits Used"),
                  ("CREDITS_PER_GB", "Credits/GB"), ("EFFICIENCY_STATUS", "Status")]
        gb_avail = [(r, h) for r, h in gb_map if r in df_pipe_eff.columns]

        if pipe_col and gb_col:
            top10 = df_pipe_eff.head(10)
            pipe_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10[pipe_col].tolist()),
                    datasets=[{"label": "GB", "data": [round(float(v), 3) for v in top10[gb_col].tolist()], "backgroundColor": _T}],
                    title="GB Ingested by Pipe (30d)", x_title="GB")) +
                _col_wrap(_subtitle("GB Ingested by Pipe") + _make_table(
                    [h for _, h in gb_avail],
                    top10[[r for r, _ in gb_avail]].values.tolist())))

        eff_map = [("PIPE_NAME", "Pipe"), ("CREDITS_PER_GB", "Credits/GB"),
                   ("AVG_FILE_MB", "Avg File MB"), ("CREDITS_USED", "Credits Used"),
                   ("EFFICIENCY_STATUS", "Status"), ("RECOMMENDATION", "Recommendation")]
        eff_avail = [(r, h) for r, h in eff_map if r in df_pipe_eff.columns]

        if pipe_col and cr_gb_col:
            df_valid = df_pipe_eff.dropna(subset=[cr_gb_col])
            if not df_valid.empty:
                top10_crg = df_valid.nlargest(10, cr_gb_col)
            else:
                top10_crg = df_pipe_eff.head(10)
            pipe_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10_crg[pipe_col].tolist()),
                    datasets=[{"label": "Credits/GB", "data": [round(float(v), 4) if pd.notna(v) else 0 for v in top10_crg[cr_gb_col].tolist()], "backgroundColor": _A}],
                    title="Cost Efficiency: Credits per GB", x_title="Credits per GB")) +
                _col_wrap(_subtitle("Cost Efficiency by Pipe") + _make_table(
                    [h for _, h in eff_avail],
                    top10_crg[[r for r, _ in eff_avail]].values.tolist())))

        if stat_col:
            by_stat = df_pipe_eff[stat_col].value_counts()
            pipe_html += _full_wrap(build_chart("vbar",
                labels=by_stat.index.tolist(),
                datasets=[{"label": "Pipes", "data": by_stat.values.tolist(),
                           "backgroundColor": [_P, _A, _S][:len(by_stat)]}],
                title="Snowpipe Efficiency Status Distribution", y_title="Pipes"))

            eff_detail_map = [("PIPE_NAME", "Pipe"), ("EFFICIENCY_STATUS", "Status"),
                              ("CREDITS_PER_GB", "Credits/GB"), ("AVG_FILE_MB", "Avg File MB"),
                              ("RECOMMENDATION", "Recommendation")]
            eff_detail_avail = [(r, h) for r, h in eff_detail_map if r in df_pipe_eff.columns]
            if eff_detail_avail:
                pipe_html += _subtitle("Snowpipe Efficiency Detail")
                pipe_html += _make_table(
                    [h for _, h in eff_detail_avail],
                    df_pipe_eff[[r for r, _ in eff_detail_avail]].values.tolist())

            rec_stat_map = [("PIPE_NAME", "Pipe"), ("EFFICIENCY_STATUS", "Status"),
                            ("RECOMMENDATION", "Recommendation")]
            rec_stat_avail = [(r, h) for r, h in rec_stat_map if r in df_pipe_eff.columns]
            if rec_stat_avail:
                pipe_html += _subtitle("Efficiency Status & Recommendations")
                pipe_html += _make_table(
                    [h for _, h in rec_stat_avail],
                    df_pipe_eff[[r for r, _ in rec_stat_avail]].values.tolist())

        sub_sections.append(build_sub_section("Snowpipe Analysis (Cost vs. Volume)",
                                               kpis=pipe_kpis, charts_html=pipe_html))

    # ── Top Credit Consumers & Overhead Analysis ──────────────────────────
    overhead_html = ""
    if not df_pipe_det.empty:
        p_col  = _col(df_pipe_det, "PIPE_NAME")
        cr_col = _col(df_pipe_det, "CREDITS_BURNED")
        gb_col = _col(df_pipe_det, "GB_LOADED")
        fi_col = _col(df_pipe_det, "FILES_INSERTED")
        st_col = _col(df_pipe_det, "STATUS")
        rc_col = _col(df_pipe_det, "RECOMMENDATION")

        burn_map = [("PIPE_NAME", "Pipe"), ("CREDITS_BURNED", "Credits Burned"),
                    ("GB_LOADED", "GB Loaded"), ("FILES_INSERTED", "Files Inserted"),
                    ("STATUS", "Status")]
        burn_avail = [(r, h) for r, h in burn_map if r in df_pipe_det.columns]

        if p_col and cr_col:
            top10 = df_pipe_det.head(10)
            overhead_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10[p_col].tolist()),
                    datasets=[{"label": "Credits Burned", "data": [round(float(v), 4) for v in top10[cr_col].tolist()], "backgroundColor": _P}],
                    title="Credits Burned by Pipe (30d)", x_title="Credits")) +
                _col_wrap(_subtitle("Credits Burned by Pipe") + _make_table(
                    [h for _, h in burn_avail],
                    top10[[r for r, _ in burn_avail]].values.tolist())))

        gb_burn_map = [("PIPE_NAME", "Pipe"), ("GB_LOADED", "GB Loaded"),
                       ("CREDITS_BURNED", "Credits Burned"),
                       ("FILES_INSERTED", "Files Inserted"), ("STATUS", "Status")]
        gb_burn_avail = [(r, h) for r, h in gb_burn_map if r in df_pipe_det.columns]

        if p_col and gb_col:
            top10 = df_pipe_det.head(10)
            overhead_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(top10[p_col].tolist()),
                    datasets=[{"label": "GB Loaded", "data": [round(float(v), 3) for v in top10[gb_col].tolist()], "backgroundColor": _S}],
                    title="GB Loaded by Pipe (30d)", x_title="GB")) +
                _col_wrap(_subtitle("GB Loaded by Pipe") + _make_table(
                    [h for _, h in gb_burn_avail],
                    top10[[r for r, _ in gb_burn_avail]].values.tolist())))

        if p_col and cr_col and gb_col:
            top10 = df_pipe_det.head(10)
            overhead_html += _charts_row(
                _col_wrap(build_chart("vbar",
                    labels=_trunc(top10[p_col].tolist()),
                    datasets=[
                        {"label": "Credits Burned", "data": [round(float(v), 4) for v in top10[cr_col].tolist()], "backgroundColor": _P},
                        {"label": "GB Loaded", "data": [round(float(v), 3) for v in top10[gb_col].tolist()], "backgroundColor": _T},
                    ],
                    title="Credits vs GB Loaded Comparison", y_title="Value")) +
                _col_wrap(_subtitle("Credits vs GB Loaded Comparison") + _make_table(
                    ["Pipe", "Credits Burned", "GB Loaded", "Status", "Recommendation"],
                    top10[[c for c in [p_col, cr_col, gb_col, st_col, rc_col] if c and c in df_pipe_det.columns]].values.tolist())))

        if st_col and rc_col:
            oh_rec_map = [("PIPE_NAME", "Pipe"), ("STATUS", "Status"),
                          ("RECOMMENDATION", "Recommendation")]
            oh_rec_avail = [(r, h) for r, h in oh_rec_map if r in df_pipe_det.columns]
            if oh_rec_avail:
                overhead_html += _subtitle("Overhead Status & Recommendations")
                overhead_html += _make_table(
                    [h for _, h in oh_rec_avail],
                    df_pipe_det[[r for r, _ in oh_rec_avail]].values.tolist())

        sub_sections.append(build_sub_section("Top Credit Consumers & Overhead Analysis",
                                               charts_html=overhead_html))

    # ── Ingestion Credit Consumption & Cost Projections ───────────────────
    cost_html = ""
    cost_kpis = []
    if not df_proj.empty:
        im_col   = _col(df_proj, "INGEST_METHOD")
        cr30_col = _col(df_proj, "CREDITS_LAST_30_DAYS")
        gb30_col = _col(df_proj, "GB_INGESTED_30_DAYS")
        fi30_col = _col(df_proj, "FILES_PROCESSED_30_DAYS")
        e3_col   = _col(df_proj, "EST_CREDITS_3_MONTHS")
        e6_col   = _col(df_proj, "EST_CREDITS_6_MONTHS")
        e12_col  = _col(df_proj, "EST_CREDITS_12_MONTHS")
        tier_col = _col(df_proj, "USAGE_TIER")

        if im_col and cr30_col:
            methods = df_proj[im_col].tolist()
            credits = [round(float(v), 2) for v in df_proj[cr30_col].tolist()]

            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(methods),
                datasets=[{"label": "Credits", "data": credits, "backgroundColor": _P}],
                title="Credit Consumption — Last 30 Days", x_title="Credits"))

            if e3_col and e6_col and e12_col:
                row_html += _col_wrap(build_chart("vbar",
                    labels=_trunc(methods),
                    datasets=[
                        {"label": "3 Months", "data": [round(float(v), 0) for v in df_proj[e3_col].tolist()], "backgroundColor": _P},
                        {"label": "6 Months", "data": [round(float(v), 0) for v in df_proj[e6_col].tolist()], "backgroundColor": _S},
                        {"label": "12 Months", "data": [round(float(v), 0) for v in df_proj[e12_col].tolist()], "backgroundColor": _A},
                    ],
                    title="Projected Credits by Horizon", y_title="Credits"))
            cost_html += _charts_row(row_html)

        prof_map = [("INGEST_METHOD", "Method"), ("CREDITS_LAST_30_DAYS", "Credits (30d)"),
                    ("GB_INGESTED_30_DAYS", "GB Ingested (30d)"),
                    ("FILES_PROCESSED_30_DAYS", "Files Processed (30d)"),
                    ("USAGE_TIER", "Usage Tier")]
        prof_avail = [(r, h) for r, h in prof_map if r in df_proj.columns]
        if prof_avail:
            cost_html += _subtitle("Cost Profile by Ingestion Method")
            cost_html += _make_table(
                [h for _, h in prof_avail],
                df_proj[[r for r, _ in prof_avail]].values.tolist())

    if not df_summary.empty:
        m_col  = _col(df_summary, "INGESTION_METHOD")
        ev_col = _col(df_summary, "EVENTS_OR_CHANNELS")
        gb_col = _col(df_summary, "GB_LOADED_30D")
        rw_col = _col(df_summary, "ROWS_LOADED_30D")
        cr_col = _col(df_summary, "CREDITS_LAST_30_DAYS")

        if m_col:
            methods = df_summary[m_col].tolist()

            if cost_html == "":
                if cr_col:
                    credits = [round(float(v), 2) for v in df_summary[cr_col].tolist()]
                    cost_html += _charts_row(_col_wrap(build_chart("hbar",
                        labels=_trunc(methods),
                        datasets=[{"label": "Credits", "data": credits, "backgroundColor": _P}],
                        title="Credit Consumption — Last 30 Days", x_title="Credits")))

                summ_map = [("INGESTION_METHOD", "Method"), ("EVENTS_OR_CHANNELS", "Events / Channels"),
                            ("GB_LOADED_30D", "GB Loaded (30d)"), ("ROWS_LOADED_30D", "Rows Loaded (30d)"),
                            ("AVG_FILE_MB", "Avg File MB")]
                summ_avail = [(r, h) for r, h in summ_map if r in df_summary.columns]
                if summ_avail:
                    cost_html += _subtitle("Cost Profile by Ingestion Method")
                    cost_html += _make_table(
                        [h for _, h in summ_avail],
                        df_summary[[r for r, _ in summ_avail]].values.tolist())

    if cost_html:
        sub_sections.append(build_sub_section("Ingestion Credit Consumption & Cost Projections",
                                               kpis=cost_kpis, charts_html=cost_html))

    # ── Snowpipe Streaming ────────────────────────────────────────────────
    stream_kpis = []
    stream_html = ""
    if not df_stream.empty:
        date_col = _col(df_stream, "USAGE_DATE")
        cred_col = _col(df_stream, "CREDITS_USED")
        if cred_col:
            stream_kpis.append({"value": _fmt_num(df_stream[cred_col].sum(), 2), "label": "Total Streaming Credits (30d)"})
            active_days = len(df_stream)
            stream_kpis.append({"value": str(active_days), "label": "Active Days"})
        if date_col and cred_col:
            stream_html = build_chart("vbar",
                labels=[str(d) for d in df_stream[date_col].tolist()],
                datasets=[{"label": "Credits", "data": [round(float(v), 4) for v in df_stream[cred_col].tolist()], "backgroundColor": _P}],
                title="Snowpipe Streaming Daily Credits", y_title="Credits")

        if not df_stream_b.empty:
            ent_col  = _col(df_stream_b, "SERVICE_ENTITY")
            tcr_col  = _col(df_stream_b, "TOTAL_CREDITS")
            ad_col   = _col(df_stream_b, "ACTIVE_DAYS")
            if ent_col and tcr_col:
                stream_html += _full_wrap(build_chart("hbar",
                    labels=_trunc(df_stream_b[ent_col].head(10).tolist()),
                    datasets=[{"label": "Credits", "data": [round(float(v), 4) for v in df_stream_b[tcr_col].head(10).tolist()], "backgroundColor": _S}],
                    title="Streaming Credits by Entity", x_title="Credits"))

                brk_map = [("SERVICE_ENTITY", "Service Entity"), ("TOTAL_CREDITS", "Total Credits"),
                           ("ACTIVE_DAYS", "Active Days"), ("FIRST_SEEN", "First Seen"),
                           ("LAST_SEEN", "Last Seen")]
                brk_avail = [(r, h) for r, h in brk_map if r in df_stream_b.columns]
                if brk_avail:
                    stream_html += _subtitle("Streaming Service Breakdown")
                    stream_html += _make_table(
                        [h for _, h in brk_avail],
                        df_stream_b[[r for r, _ in brk_avail]].values.tolist())

        sub_sections.append(build_sub_section("Snowpipe Streaming",
                                               kpis=stream_kpis, charts_html=stream_html))
    else:
        sub_sections.append(build_sub_section("Snowpipe Streaming",
                                               charts_html='<p class="no-data-note">No data available.</p>'))

    # ── Ingestion Summary Dashboard ───────────────────────────────────────
    summ_html = ""
    if not df_summary.empty:
        m_col  = _col(df_summary, "INGESTION_METHOD")
        ev_col = _col(df_summary, "EVENTS_OR_CHANNELS")
        gb_col = _col(df_summary, "GB_LOADED_30D")
        rw_col = _col(df_summary, "ROWS_LOADED_30D")
        fm_col = _col(df_summary, "AVG_FILE_MB")
        cr_col = _col(df_summary, "CREDITS_LAST_30_DAYS")

        if m_col:
            methods = df_summary[m_col].tolist()

            topline_map = [("INGESTION_METHOD", "Method"), ("EVENTS_OR_CHANNELS", "Events / Channels"),
                           ("GB_LOADED_30D", "GB Loaded (30d)"), ("ROWS_LOADED_30D", "Rows Loaded (30d)"),
                           ("AVG_FILE_MB", "Avg File MB")]
            topline_avail = [(r, h) for r, h in topline_map if r in df_summary.columns]
            if topline_avail:
                summ_html += _subtitle("Top-Line Ingestion Summary")
                summ_html += _make_table(
                    [h for _, h in topline_avail],
                    df_summary[[r for r, _ in topline_avail]].values.tolist())

            row_html = ""
            if ev_col:
                row_html += _col_wrap(build_chart("doughnut",
                    labels=_trunc(methods),
                    data=[int(float(v)) for v in df_summary[ev_col].tolist()],
                    colors=_PALETTE[:len(methods)],
                    title="Events / Channels by Method"))
            if gb_col:
                row_html += _col_wrap(build_chart("doughnut",
                    labels=_trunc(methods),
                    data=[round(float(v), 3) for v in df_summary[gb_col].tolist()],
                    colors=_PALETTE[:len(methods)],
                    title="Data Volume (GB) by Method"))
            if cr_col:
                row_html += _col_wrap(build_chart("doughnut",
                    labels=_trunc(methods),
                    data=[round(float(v), 4) for v in df_summary[cr_col].tolist()],
                    colors=_PALETTE[:len(methods)],
                    title="Credits Consumed by Method"))
            if row_html:
                summ_html += _charts_row(row_html)

            if ev_col and rw_col:
                datasets = [
                    {"label": "Events / Channels", "data": [int(float(v)) for v in df_summary[ev_col].tolist()], "backgroundColor": _P},
                    {"label": "Rows", "data": [int(float(v)) for v in df_summary[rw_col].tolist()], "backgroundColor": _S},
                ]
                if cr_col:
                    datasets.append({"label": "Credits", "data": [round(float(v), 4) for v in df_summary[cr_col].tolist()], "backgroundColor": _A})
                summ_html += _full_wrap(build_chart("vbar",
                    labels=_trunc(methods),
                    datasets=datasets,
                    title="Side-by-Side Ingestion Comparison", y_title="Value"))

            comp_map = [("INGESTION_METHOD", "Method"), ("EVENTS_OR_CHANNELS", "Events / Channels"),
                        ("ROWS_LOADED_30D", "Rows Loaded (30d)"), ("GB_LOADED_30D", "GB Loaded (30d)"),
                        ("AVG_FILE_MB", "Avg File MB"), ("CREDITS_LAST_30_DAYS", "Credits (30d)")]
            comp_avail = [(r, h) for r, h in comp_map if r in df_summary.columns]
            if comp_avail:
                summ_html += _subtitle("Method Comparison Detail")
                summ_html += _make_table(
                    [h for _, h in comp_avail],
                    df_summary[[r for r, _ in comp_avail]].values.tolist())

    if summ_html:
        sub_sections.append(build_sub_section("Ingestion Summary Dashboard",
                                               charts_html=summ_html))

    return build_report(
        topic_name="Data Ingestion",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ── Data Transformation ─────────────────────────────────────────────────────

def export_data_transformation(account_name: str) -> str:
    df_ov      = _safe_df("tf_overview")
    df_prob    = _safe_df("tf_problematic_queries")
    df_cat_sum = _safe_df("tf_category_summary")
    df_syntax  = _safe_df("tf_syntax_hunter")
    df_syn_fr  = _safe_df("tf_syntax_frequency")
    df_views   = _safe_df("tf_view_dependency")
    df_views_v2= _safe_df("tf_view_dependency_v2")
    df_wl      = _safe_df("tf_workload_shape")
    df_wl_v2   = _safe_df("tf_workload_shape_v2")
    df_mv      = _safe_df("tf_mv_inventory")
    df_perf    = _safe_df("tf_perf_insights")
    df_lifecycle = _safe_df("tf_lifecycle")

    top_kpis = []
    if not df_ov.empty:
        r = df_ov.iloc[0]
        clustered   = int(r.get("CLUSTERED_TABLES", 0) or 0)
        unclustered = int(r.get("UNCLUSTERED_TABLES", 0) or 0)
        total_base  = clustered + unclustered
        auto_on     = int(r.get("NUM_TABLES_WITH_AUTO_CLUSTERING", 0) or 0)
        mvs         = int(r.get("NUM_MATERIALIZED_VIEWS", 0) or 0)
        dyn_tables  = int(r.get("NUM_DYNAMIC_TABLES", 0) or 0)
        semi_struct = int(r.get("NUM_TABLES_WITH_SEMI_STRUCTURED", 0) or 0)
        sem_views   = int(r.get("NUM_SEMANTIC_VIEWS", 0) or 0)
        spill_wh    = int(r.get("NUM_WAREHOUSES_SPILL_OR_QUEUE_LAST_30D", 0) or 0)
        short_ups   = int(r.get("NUM_SHORT_UPSERTS_LAST_30D", 0) or 0)
        snowpark_q  = int(r.get("NUM_SNOWPARK_QUERIES_LAST_30D", 0) or 0)
        hi_cloud    = int(r.get("NUM_WH_DAYS_HIGH_CLOUD_SERVICES_LAST_30D", 0) or 0)

        top_kpis = [
            {"value": _fmt_num(total_base, 0), "label": "Total Base Tables"},
            {"value": _fmt_num(clustered, 0), "label": "Clustered Tables"},
            {"value": _fmt_num(auto_on, 0), "label": "Auto Clustering ON"},
            {"value": _fmt_num(mvs, 0), "label": "Materialized Views"},
            {"value": _fmt_num(dyn_tables, 0), "label": "Dynamic Tables"},
            {"value": _fmt_num(semi_struct, 0), "label": "Semi-Structured Tables"},
            {"value": _fmt_num(sem_views, 0), "label": "Semantic Views"},
            {"value": _fmt_num(spill_wh, 0), "label": "WH with Spill/Queue (30d)"},
            {"value": _fmt_num(short_ups, 0), "label": "Short UPSERTs (30d)"},
            {"value": _fmt_num(snowpark_q, 0), "label": "Snowpark Queries (30d)"},
            {"value": _fmt_num(hi_cloud, 0), "label": "High Cloud Services Days (30d)"},
        ]

    sub_sections = []

    # ── 1. Overview ───────────────────────────────────────────────────────
    ov_html = ""
    if not df_ov.empty and top_kpis:
        r = df_ov.iloc[0]
        clustered   = int(r.get("CLUSTERED_TABLES", 0) or 0)
        unclustered = int(r.get("UNCLUSTERED_TABLES", 0) or 0)
        auto_on     = int(r.get("NUM_TABLES_WITH_AUTO_CLUSTERING", 0) or 0)
        ov_html += build_chart("hbar",
            labels=["Clustered Tables", "Unclustered Tables", "Auto Clustering ON"],
            datasets=[{"label": "Tables", "data": [clustered, unclustered, auto_on], "backgroundColor": _P}],
            title="Table Clustering Distribution")

        type_labels = ["Materialized Views", "Semi-Structured", "Dynamic Tables",
                       "Hybrid Tables", "Event Tables", "Semantic Views"]
        type_cols   = ["NUM_MATERIALIZED_VIEWS", "NUM_TABLES_WITH_SEMI_STRUCTURED",
                       "NUM_DYNAMIC_TABLES", "NUM_HYBRID_TABLES", "NUM_EVENT_TABLES", "NUM_SEMANTIC_VIEWS"]
        type_vals   = [int(r.get(c, 0) or 0) for c in type_cols]
        ov_html += build_chart("hbar",
            labels=type_labels,
            datasets=[{"label": "Count", "data": type_vals, "backgroundColor": _S}],
            title="Table Types Distribution")

        spill_wh  = int(r.get("NUM_WAREHOUSES_SPILL_OR_QUEUE_LAST_30D", 0) or 0)
        hi_cloud  = int(r.get("NUM_WH_DAYS_HIGH_CLOUD_SERVICES_LAST_30D", 0) or 0)
        row_html = _col_wrap(build_chart("hbar",
            labels=["WH with Spill/Queue", "High Cloud Services Days"],
            datasets=[{"label": "Count", "data": [spill_wh, hi_cloud], "backgroundColor": _A}],
            title="Warehouse Performance Issues (30 Days)"))

        short_ups  = int(r.get("NUM_SHORT_UPSERTS_LAST_30D", 0) or 0)
        snowpark_q = int(r.get("NUM_SNOWPARK_QUERIES_LAST_30D", 0) or 0)
        row_html += _col_wrap(build_chart("hbar",
            labels=["Short UPSERTs", "Snowpark Queries"],
            datasets=[{"label": "Count", "data": [short_ups, snowpark_q], "backgroundColor": _T}],
            title="Query & Usage Patterns (30 Days)"))
        ov_html += _charts_row(row_html)

    sub_sections.append(build_sub_section("Overview", kpis=top_kpis, charts_html=ov_html))

    # ── 2. Problematic Query Report (Native Insights) ─────────────────────
    pq_html = ""
    pq_kpis = []

    cat_col_cs  = _col(df_cat_sum, "PROBLEM_CATEGORY", "CATEGORY", "category")
    occ_col_cs  = _col(df_cat_sum, "TOTAL_OCCURRENCES", "OCCURRENCES", "total")
    dq_col_cs   = _col(df_cat_sum, "DISTINCT_QUERIES_AFFECTED", "DISTINCT_QUERIES", "distinct")
    codes_col   = _col(df_cat_sum, "SPECIFIC_INSIGHT_CODES")

    if not df_cat_sum.empty:
        pq_kpis = [
            {"value": str(len(df_cat_sum)), "label": "Total Insight Types"},
            {"value": _fmt_num(df_cat_sum[occ_col_cs].sum(), 0) if occ_col_cs else "—", "label": "Total Occurrences"},
            {"value": _fmt_num(df_cat_sum[dq_col_cs].sum(), 0) if dq_col_cs else "—", "label": "Distinct Queries"},
        ]

    code_col_p = _col(df_prob, "INSIGHT_CODE", "code")
    cat_col_p  = _col(df_prob, "CATEGORY", "category")
    occ_col_p  = _col(df_prob, "OCCURRENCE_COUNT", "OCCURRENCES", "total")
    dq_col_p   = _col(df_prob, "DISTINCT_QUERIES", "distinct_queries")

    if not df_cat_sum.empty and cat_col_cs and occ_col_cs:
        row_html = _col_wrap(build_chart("hbar",
            labels=_trunc(df_cat_sum[cat_col_cs].tolist()),
            datasets=[{"label": "Occurrences", "data": [int(v) for v in df_cat_sum[occ_col_cs].tolist()], "backgroundColor": _P}],
            title="Issue Occurrences by Category"))
        if dq_col_cs:
            row_html += _col_wrap(build_chart("hbar",
                labels=_trunc(df_cat_sum[cat_col_cs].tolist()),
                datasets=[{"label": "Distinct Queries", "data": [int(v) for v in df_cat_sum[dq_col_cs].tolist()], "backgroundColor": _S}],
                title="Distinct Queries by Category"))
        pq_html += _charts_row(row_html)

    if not df_prob.empty and code_col_p and occ_col_p:
        top10 = df_prob.head(10)
        row_html = _col_wrap(build_chart("hbar",
            labels=_trunc(top10[code_col_p].tolist()),
            datasets=[{"label": "Occurrences", "data": [int(v) for v in top10[occ_col_p].tolist()], "backgroundColor": _T}],
            title="Top Insight Codes by Occurrence"))
        if cat_col_p and occ_col_p:
            by_cat = df_prob.groupby(cat_col_p)[occ_col_p].sum().sort_values(ascending=False)
            row_html += _col_wrap(build_chart("doughnut",
                labels=by_cat.index.tolist(),
                data=[int(v) for v in by_cat.values.tolist()],
                colors=_PALETTE[:len(by_cat)],
                title="Category Distribution"))
        pq_html += _charts_row(row_html)

        prob_map = [("INSIGHT_CODE", "Insight Code"), ("CATEGORY", "Category"),
                    ("OCCURRENCE_COUNT", "Occurrences"), ("DISTINCT_QUERIES", "Distinct Queries")]
        prob_avail = [(r, h) for r, h in prob_map if r in df_prob.columns]
        if prob_avail:
            pq_html += _make_table(
                [h for _, h in prob_avail],
                df_prob[[r for r, _ in prob_avail]].values.tolist())

    if not df_cat_sum.empty and cat_col_cs and occ_col_cs and dq_col_cs:
        row_html = _col_wrap(build_chart("vbar",
            labels=_trunc(df_cat_sum[cat_col_cs].tolist()),
            datasets=[
                {"label": "Total Occurrences", "data": [int(v) for v in df_cat_sum[occ_col_cs].tolist()], "backgroundColor": _P},
                {"label": "Distinct Queries", "data": [int(v) for v in df_cat_sum[dq_col_cs].tolist()], "backgroundColor": _A},
            ],
            title="Occurrences vs Distinct Queries"))
        by_cat_cs = df_cat_sum.set_index(cat_col_cs)[occ_col_cs]
        row_html += _col_wrap(build_chart("doughnut",
            labels=by_cat_cs.index.tolist(),
            data=[int(v) for v in by_cat_cs.values.tolist()],
            colors=_PALETTE[:len(by_cat_cs)],
            title="Category Proportion"))
        pq_html += _charts_row(row_html)

        cat_sum_map = [("PROBLEM_CATEGORY", "Problem Category"), ("TOTAL_OCCURRENCES", "Total Occurrences"),
                       ("DISTINCT_QUERIES_AFFECTED", "Distinct Queries Affected"),
                       ("SPECIFIC_INSIGHT_CODES", "Specific Insight Codes")]
        cat_sum_avail = [(r, h) for r, h in cat_sum_map if r in df_cat_sum.columns]
        if cat_sum_avail:
            pq_html += _make_table(
                [h for _, h in cat_sum_avail],
                df_cat_sum[[r for r, _ in cat_sum_avail]].values.tolist())

    if pq_html or pq_kpis:
        sub_sections.append(build_sub_section("Problematic Query - Report (Native Insights)",
                                               kpis=pq_kpis, charts_html=pq_html))

    # ── 3. Syntax Hunter (Regex & Heuristics) ─────────────────────────────
    syn_html = ""

    pattern_labels = ["ORDER BY in CTE", "Sort + Aggregate", "DISTINCT Optimisation",
                      "Collation", "ASOF Join", "Directed Join"]
    pattern_cols   = ["ORDER_BY_IN_CTE", "SORT_AND_AGG", "DISTINCT_OPTIMIZATION_CHECK",
                      "USES_COLLATION", "USES_ASOF_JOIN", "USES_DIRECTED_JOIN"]
    yes_vals       = ["✅ Yes", "✅ Yes", "⚠️ Consider APPROX", "✅ Yes", "✅ Yes", "✅ Yes"]

    if not df_syntax.empty:
        counts = []
        for col, yes_v in zip(pattern_cols, yes_vals):
            if col in df_syntax.columns:
                counts.append(int((df_syntax[col] == yes_v).sum()))
            else:
                counts.append(0)

        row_html = _col_wrap(build_chart("hbar",
            labels=pattern_labels,
            datasets=[{"label": "Queries", "data": counts, "backgroundColor": _P}],
            title="SQL Pattern Usage (query sample)"))
        detected  = sum(1 for c in counts if c > 0)
        not_found = sum(1 for c in counts if c == 0)
        row_html += _col_wrap(build_chart("doughnut",
            labels=["Detected", "Not Found"],
            data=[detected, not_found], colors=[_P, "#d3d3d3"],
            title="Patterns Detected vs Not Found"))
        syn_html += _charts_row(row_html)

        all_colors = [_P if c > 0 else "#d3d3d3" for c in counts]
        row_html2 = _col_wrap(build_chart("hbar",
            labels=pattern_labels,
            datasets=[{"label": "Queries", "data": counts, "backgroundColor": all_colors}],
            title="All Patterns (incl. zero)"))
        approx_count = 0
        total_queries = len(df_syntax)
        if "DISTINCT_OPTIMIZATION_CHECK" in df_syntax.columns:
            approx_count = int((df_syntax["DISTINCT_OPTIMIZATION_CHECK"] == "⚠️ Consider APPROX").sum())
        row_html2 += _col_wrap(build_chart("doughnut",
            labels=["APPROX Candidates", "No Optimisation"],
            data=[approx_count, total_queries - approx_count],
            colors=[_A, _P],
            title="DISTINCT Optimisation Candidates"))
        syn_html += _charts_row(row_html2)

    if not df_syn_fr.empty:
        det_col = _col(df_syn_fr, "DETECTION_TYPE", "detection_type")
        occ_col = _col(df_syn_fr, "OCCURRENCE_COUNT", "occurrence_count")
        if det_col and occ_col:
            row_html3 = _col_wrap(build_chart("hbar",
                labels=_trunc(df_syn_fr[det_col].tolist()),
                datasets=[{"label": "Occurrences", "data": [int(v) for v in df_syn_fr[occ_col].tolist()], "backgroundColor": _S}],
                title="Detection Type Occurrences"))
            inefficiency_patterns = ["Sort + Aggregate (Heavy Compute)",
                                     "Order By inside CTE (Likely Redundant)",
                                     "Heavy Distinct (>1GB Scanned)"]
            feature_patterns = ['Directed Join Hints ("+")', "ASOF Join Used", "Collation Used"]
            ineff_sum = int(df_syn_fr[df_syn_fr[det_col].isin(inefficiency_patterns)][occ_col].sum())
            feat_sum  = int(df_syn_fr[df_syn_fr[det_col].isin(feature_patterns)][occ_col].sum())
            row_html3 += _col_wrap(build_chart("doughnut",
                labels=["Potential Inefficiencies", "Advanced Features"],
                data=[ineff_sum, feat_sum],
                colors=[_A, _P],
                title="Inefficiency vs Feature Usage"))
            syn_html += _charts_row(row_html3)

    if syn_html:
        sub_sections.append(build_sub_section("Syntax Hunter (Regex & Heuristics)", charts_html=syn_html))

    # ── 4. Object Structure Analysis (Stacked Views & Security) ───────────
    view_df = df_views_v2 if not df_views_v2.empty else df_views
    view_html = ""
    if not view_df.empty:
        view_col  = _col(view_df, "ROOT_VIEW", "view_name", "VIEW_NAME")
        depth_col = _col(view_df, "MAX_DEPTH", "depth")
        sev_col   = _col(view_df, "DEPTH_SEVERITY", "SEVERITY", "depth_severity")
        rec_col   = _col(view_df, "RECOMMENDATION", "recommendation")

        if view_col and depth_col:
            top20 = view_df.head(20)
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(top20[view_col].tolist()),
                datasets=[{"label": "Max Depth", "data": [int(v) for v in top20[depth_col].tolist()], "backgroundColor": _S}],
                title="Top 20 Deeply-Nested Views (depth>2)"))
            depth_dist = view_df[depth_col].value_counts().sort_index()
            row_html += _col_wrap(build_chart("vbar",
                labels=[str(d) for d in depth_dist.index.tolist()],
                datasets=[{"label": "Views", "data": depth_dist.values.tolist(), "backgroundColor": _P}],
                title="Views per Depth Level", y_title="Views"))
            view_html += _charts_row(row_html)

            if sev_col:
                by_sev = view_df[sev_col].value_counts()
                view_html += _full_wrap(build_chart("doughnut",
                    labels=by_sev.index.tolist(), data=by_sev.values.tolist(),
                    colors=[_A] + _PALETTE[:len(by_sev)],
                    title="Depth Severity Distribution"))

            detail_map = [("ROOT_VIEW", "Root View"), ("MAX_DEPTH", "Max Depth")]
            detail_avail = [(r, h) for r, h in detail_map if r in view_df.columns]
            if detail_avail:
                view_html += _subtitle("Deeply Nested View Detail")
                view_html += _make_table(
                    [h for _, h in detail_avail],
                    view_df.head(20)[[r for r, _ in detail_avail]].values.tolist())

    if view_html:
        sub_sections.append(build_sub_section("Object Structure Analysis (Stacked Views & Security)",
                                               charts_html=view_html))

    # ── 5. Workload Shape (Updates, MVs, RAPs) ────────────────────────────
    wl_df   = df_wl_v2 if not df_wl_v2.empty else df_wl
    wl_html = ""
    if not wl_df.empty:
        pat_col  = _col(wl_df, "QUERY_PATTERN", "pattern", "PATTERN")
        exe_col  = _col(wl_df, "EXECUTION_COUNT", "EXECUTIONS", "execution_count")
        rec_col  = _col(wl_df, "RECOMMENDATION", "recommendation")
        dml_col  = _col(wl_df, "QUERY_TYPE", "DML_TYPE", "dml_type")
        rows_col = _col(wl_df, "TOTAL_ROWS_AFFECTED", "ROWS_AFFECTED", "rows")
        dur_col  = _col(wl_df, "AVG_DURATION_MS", "avg_duration_ms")

        if pat_col and exe_col:
            top20 = wl_df.head(20)
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(top20[pat_col].tolist()),
                datasets=[{"label": "Executions", "data": [int(v) for v in top20[exe_col].tolist()], "backgroundColor": _P}],
                title="Top 20 Patterns by Execution Count"))
            if rec_col:
                by_rec = wl_df[rec_col].value_counts()
                row_html += _col_wrap(build_chart("doughnut",
                    labels=by_rec.index.tolist(), data=by_rec.values.tolist(),
                    colors=_PALETTE[:len(by_rec)],
                    title="Recommendation Distribution"))
            wl_html += _charts_row(row_html)

        if dml_col and exe_col:
            by_dml = wl_df.groupby(dml_col)[exe_col].sum().sort_values(ascending=False)
            row_html2 = _col_wrap(build_chart("hbar",
                labels=by_dml.index.tolist(),
                datasets=[{"label": "Executions", "data": [int(v) for v in by_dml.values.tolist()], "backgroundColor": _S}],
                title="Executions by DML Type", x_title="Executions"))
            if pat_col and rows_col:
                top20_r = wl_df.nlargest(20, rows_col) if rows_col in wl_df.columns else wl_df.head(20)
                row_html2 += _col_wrap(build_chart("hbar",
                    labels=_trunc(top20_r[pat_col].tolist()),
                    datasets=[{"label": "Rows Affected", "data": [int(v) for v in top20_r[rows_col].tolist()], "backgroundColor": _T}],
                    title="Rows Affected by Pattern", x_title="Rows Affected"))
            wl_html += _charts_row(row_html2)

        wl_tbl_map = [("QUERY_PATTERN", "Query Pattern"), ("QUERY_TYPE", "Query Type"),
                      ("EXECUTION_COUNT", "Execution Count"), ("AVG_DURATION_MS", "Avg Duration (ms)"),
                      ("TOTAL_ROWS_AFFECTED", "Total Rows Affected")]
        wl_tbl_avail = [(r, h) for r, h in wl_tbl_map if r in wl_df.columns]
        if wl_tbl_avail:
            wl_html += _make_table(
                [h for _, h in wl_tbl_avail],
                wl_df.head(30)[[r for r, _ in wl_tbl_avail]].values.tolist())

    df_perf_q = _safe_df("tf_perf_insights")
    if not df_perf_q.empty:
        cat_col_pf = _col(df_perf_q, "METRIC_CATEGORY", "CATEGORY", "category")
        nm_col_pf  = _col(df_perf_q, "METRIC_NAME", "metric_name")
        val_col_pf = _col(df_perf_q, "VALUE", "value")

        if cat_col_pf and nm_col_pf and val_col_pf:
            perf_labels = df_perf_q[nm_col_pf].tolist()
            perf_vals   = []
            for v in df_perf_q[val_col_pf].tolist():
                try:
                    perf_vals.append(round(float(v), 1))
                except (ValueError, TypeError):
                    perf_vals.append(0)

            wl_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(perf_labels),
                    datasets=[{"label": "Value", "data": perf_vals, "backgroundColor": _P}],
                    title="Workload Metrics by Category", x_title="Value")) +
                _col_wrap(build_chart("doughnut",
                    labels=df_perf_q[cat_col_pf].unique().tolist(),
                    data=[int(df_perf_q[df_perf_q[cat_col_pf] == c].shape[0]) for c in df_perf_q[cat_col_pf].unique()],
                    colors=_PALETTE[:len(df_perf_q[cat_col_pf].unique())],
                    title="Category Distribution")))

            perf_detail_map = [("METRIC_CATEGORY", "Category"), ("METRIC_NAME", "Metric"),
                               ("VALUE", "Value")]
            perf_detail_avail = [(r, h) for r, h in perf_detail_map if r in df_perf_q.columns]
            if perf_detail_avail:
                wl_html += _subtitle("Query Category Detail")
                wl_html += _make_table(
                    [h for _, h in perf_detail_avail],
                    df_perf_q[[r for r, _ in perf_detail_avail]].values.tolist())

    df_dml_7d = _safe_df("tf_workload_shape_v2")
    if df_dml_7d.empty:
        df_dml_7d = _safe_df("tf_workload_shape")
    if not df_dml_7d.empty:
        dml_7d_col = _col(df_dml_7d, "QUERY_TYPE", "DML_TYPE")
        exe_7d_col = _col(df_dml_7d, "EXECUTION_COUNT", "EXECUTIONS")
        if dml_7d_col and exe_7d_col:
            by_dml_7d = df_dml_7d.groupby(dml_7d_col)[exe_7d_col].sum().sort_values(ascending=False)
            wl_html += build_chart("vbar",
                labels=by_dml_7d.index.tolist(),
                datasets=[{"label": "Queries", "data": [int(v) for v in by_dml_7d.values.tolist()], "backgroundColor": _P}],
                title="DML Query Volume by Type (7d)")

    if not df_mv.empty:
        mv_name_col = _col(df_mv, "MV_NAME", "VIEW_NAME", "MATERIALIZED_VIEW", "name")
        size_col    = _col(df_mv, "SIZE_GB", "size_gb")
        refresh_col = _col(df_mv, "CREATED_DATE", "created_date")
        if mv_name_col and size_col:
            wl_html += _full_wrap(build_chart("hbar",
                labels=_trunc(df_mv[mv_name_col].head(15).tolist()),
                datasets=[{"label": "Size (GB)", "data": [round(float(v), 2) for v in df_mv[size_col].head(15).tolist()], "backgroundColor": _S}],
                title="Materialized Views by Size (GB)", x_title="GB"))
            mv_detail_map = [("MV_NAME", "View"), ("SIZE_GB", "Size (GB)"), ("CREATED_DATE", "Last Refresh")]
            mv_detail_avail = [(r, h) for r, h in mv_detail_map if r in df_mv.columns]
            if mv_detail_avail:
                wl_html += _subtitle("Materialized View Detail")
                wl_html += _make_table(
                    [h for _, h in mv_detail_avail],
                    df_mv.head(15)[[r for r, _ in mv_detail_avail]].values.tolist())

    if wl_html:
        sub_sections.append(build_sub_section("Workload Shape (Updates, MVs, RAPs)", charts_html=wl_html))

    return build_report(
        topic_name="Data Transformation",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ── FinOps ──────────────────────────────────────────────────────────────────

def export_finops(account_name: str) -> str:
    df_fc   = _safe_df("fv_exec_forecast")
    df_cb   = _safe_df("fv_compute_breakdown")
    df_cq   = _safe_df("fv_costliest_queries")
    df_stdb = _safe_df("fv_storage_by_db")
    df_mthly= _safe_df("fv_monthly_wh_credits")
    df_daily= _safe_df("fv_daily_cost_trend")
    df_user = _safe_df("fv_user_cost_attribution")
    df_svc  = _safe_df("fv_service_type_cost")
    df_eac  = _safe_df("fv_wh_eac_forecast")
    df_anom = _safe_df("fv_cost_anomalies")
    df_rm   = _safe_df("fc_resource_monitors")
    df_twh  = _safe_df("fc_top_wh_credits")
    df_uact = _safe_df("fc_unusual_activity")
    df_idle = _safe_df("fc_idle_time")
    df_rmgap= _safe_df("fc_rm_coverage_gap")
    df_wow  = _safe_df("fc_wow_cost_trend")
    df_serv = _safe_df("fc_serverless_costs")
    df_spend= _safe_df("fc_spending_summary")
    df_mtrnd= _safe_df("fc_monthly_trend")
    df_stcst= _safe_df("fc_storage_costs")
    df_bmtd = _safe_df("fc_budget_mtd")
    df_csoh = _safe_df("fo_cs_overhead")
    df_cpps = _safe_df("fo_copy_poor_sel")
    df_cpat = _safe_df("fo_copy_patterns")
    df_shrt = _safe_df("fo_short_queries")
    df_show = _safe_df("fo_show_commands")
    df_sri  = _safe_df("fo_single_row_inserts")
    df_cplx = _safe_df("fo_complex_queries")

    comp_cost = stor_cost = svc_cost = total30d = eac = 0.0
    if not df_fc.empty:
        for _, row in df_fc.iterrows():
            cat = str(row.get("CATEGORY", ""))
            cost = float(row.get("ACTUAL_COST_30D", 0) or 0)
            if "Compute" in cat:
                comp_cost = cost
            elif "Cloud" in cat:
                svc_cost = cost
            elif "Storage" in cat:
                stor_cost = cost
        total30d = comp_cost + svc_cost + stor_cost
        eac = total30d * 12

    top_kpis = []
    if total30d > 0 or eac > 0:
        top_kpis = [
            {"value": f"${_fmt_num(comp_cost)}", "label": "Compute (30d)"},
            {"value": f"${_fmt_num(svc_cost)}", "label": "Cloud Services (30d)"},
            {"value": f"${_fmt_num(stor_cost)}", "label": "Storage (30d)"},
            {"value": f"${_fmt_num(total30d)}", "label": "Total (30d)"},
            {"value": f"${_fmt_num(eac)}", "label": "EAC (Annual Est.)"},
        ]
    elif not df_fc.empty:
        eac_col = _col(df_fc, "EAC_ANNUAL")
        if eac_col:
            eac = float(df_fc[eac_col].sum())
            top_kpis = [{"value": f"${_fmt_num(eac)}", "label": "EAC (Annual Est.)"}]

    sub_sections = []

    # ── 1. Visibility ─────────────────────────────────────────────────────
    vis_kpis = list(top_kpis)
    vis_html = ""

    if comp_cost or svc_cost or stor_cost:
        vis_html += build_chart("doughnut",
            labels=["Compute", "Cloud Services", "Storage"],
            data=[comp_cost, svc_cost, stor_cost], colors=[_P, _S, _T],
            title="Cost Breakdown (30d)")
        vis_html += _full_wrap(build_chart("vbar",
            labels=["Compute", "Cloud Services", "Storage", "30-Day Total", "Annual EAC"],
            datasets=[{"label": "Cost ($)", "data": [comp_cost, svc_cost, stor_cost, total30d, eac],
                       "backgroundColor": [_P, _S, _T, "#1A7DA8", _A]}],
            title="EAC Overview", y_title="Cost ($)"))

    if not df_daily.empty:
        date_col = _col(df_daily, "USAGE_DATE")
        cost_col = _col(df_daily, "TOTAL_COST_USD", "DAILY_COST")
        ma_col   = _col(df_daily, "ROLLING_7D_AVG_COST")
        if date_col and cost_col:
            ds = [{"label": "Daily Cost ($)", "data": [round(float(v), 2) for v in df_daily[cost_col].tolist()],
                   "borderColor": _T, "backgroundColor": "rgba(117,194,216,0.15)", "fill": False}]
            if ma_col and ma_col in df_daily.columns:
                ds.append({"label": "7-Day MA ($)", "data": [round(float(v), 2) for v in df_daily[ma_col].tolist()],
                           "borderColor": _S, "backgroundColor": "rgba(17,86,127,0.12)", "fill": False})
            vis_html += build_chart("line",
                labels=[str(d) for d in df_daily[date_col].tolist()], datasets=ds,
                title="Daily Cost with 7-Day Moving Average", y_title="Cost ($)")

    if not df_cb.empty:
        name_col = _col(df_cb, "RESOURCE_NAME", "WAREHOUSE_NAME")
        cost_col = _col(df_cb, "COST_LAST_30D", "CREDITS_LAST_30D")
        if name_col and cost_col:
            top15 = df_cb.head(15)
            vis_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top15[name_col].tolist()),
                datasets=[{"label": "Cost ($)", "data": [round(float(v), 2) for v in top15[cost_col].tolist()], "backgroundColor": _S}],
                title="Top 15 Warehouses by Cost (30d, $)"))
            tbl_map = [("RESOURCE_NAME", "Warehouse"), ("COST_LAST_30D", "Cost (30d)")]
            tbl_avail = [(r, h) for r, h in tbl_map if r in df_cb.columns]
            if tbl_avail:
                vis_html += _subtitle("Warehouse Cost Detail")
                vis_html += _make_table(
                    [h for _, h in tbl_avail],
                    df_cb.head(15)[[r for r, _ in tbl_avail]].values.tolist())

    if not df_eac.empty and "WAREHOUSE_NAME" in df_eac.columns:
        m_cols = [f"M{i}" for i in range(1, 13) if f"M{i}" in df_eac.columns]
        if m_cols:
            data30 = df_eac.head(30)
            col_vals = {}
            for mc in m_cols:
                vals = [float(r.get(mc, 0) or 0) for _, r in data30.iterrows()]
                col_vals[mc] = (min(vals), max(vals))

            def _eac_cell_color(v, mn, mx):
                t = (v - mn) / (mx - mn) if mx > mn else 0.0
                t = max(0.0, min(1.0, t))
                if t < 0.5:
                    t2 = t / 0.5
                    r2 = int(255 + t2 * (41 - 255))
                    g2 = int(255 + t2 * (181 - 255))
                    b2 = int(255 + t2 * (232 - 255))
                else:
                    t2 = (t - 0.5) / 0.5
                    r2 = int(41 + t2 * (232 - 41))
                    g2 = int(181 + t2 * (162 - 181))
                    b2 = int(232 + t2 * (41 - 232))
                bg = f"#{r2:02X}{g2:02X}{b2:02X}"
                fg = "#ffffff" if t > 0.4 else "#333333"
                return f'style="background:{bg};color:{fg};text-align:right;padding:4px 8px;"'

            hdr_style = 'style="background:#11567F;color:white;padding:5px 8px;text-align:center;"'
            idx_style = 'style="text-align:left;padding:4px 8px;white-space:nowrap;font-size:12px;"'
            th_row = "<tr>" + f"<th {hdr_style}>Warehouse</th>" + "".join(
                f"<th {hdr_style}>{i}</th>" for i in range(1, len(m_cols) + 1)) + "</tr>"
            body_rows = ""
            for _, row in data30.iterrows():
                tds = f"<td {idx_style}>{row.get('WAREHOUSE_NAME','')}</td>"
                for mc in m_cols:
                    v = float(row.get(mc, 0) or 0)
                    mn, mx = col_vals[mc]
                    tds += f"<td {_eac_cell_color(v, mn, mx)}>${v:,.0f}</td>"
                body_rows += f"<tr>{tds}</tr>"

            eac_table = (
                f'<table style="border-collapse:collapse;width:100%;font-size:12px;">'
                f"<thead>{th_row}</thead><tbody>{body_rows}</tbody></table>"
            )
            vis_html += _subtitle("Top 30 Warehouse 12-Month EAC Forecast")
            vis_html += (
                '<p style="font-size:11px;color:#555;margin:0 0 6px 0;">'
                "Warehouse forecast heatmap. Low projected spend is shaded toward cyan, "
                "high projected spend toward orange (per-column scaling).</p>"
            )
            vis_html += f'<div style="overflow-x:auto;">{eac_table}</div>'

    if not df_cq.empty:
        q_col  = _col(df_cq, "QUERY_ID")
        cost_c = _col(df_cq, "QUERY_COST_USD", "CREDITS_USED")
        if q_col and cost_c:
            top20 = df_cq.head(20)
            vis_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top20[q_col].tolist()),
                datasets=[{"label": "Cost ($)", "data": [round(float(v), 4) for v in top20[cost_c].tolist()], "backgroundColor": _S}],
                title="Top 20 Queries by Attributed Compute Cost", x_title="Cost ($)"))
            tbl_map = [("QUERY_ID", "Query ID"), ("USER_NAME", "User"), ("WAREHOUSE_NAME", "Warehouse"),
                       ("QUERY_COST_USD", "Cost ($)"), ("CREDITS_USED", "Credits")]
            tbl_avail = [(r, h) for r, h in tbl_map if r in df_cq.columns]
            if tbl_avail:
                vis_html += _subtitle("Top Costliest Queries")
                vis_html += _make_table(
                    [h for _, h in tbl_avail],
                    df_cq.head(20)[[r for r, _ in tbl_avail]].values.tolist())

    if not df_stdb.empty:
        db_col   = _col(df_stdb, "DATABASE_NAME")
        cost_col = _col(df_stdb, "EST_MONTHLY_COST", "DAILY_COST_USD")
        avg_col  = _col(df_stdb, "AVG_TB")
        if db_col:
            row_html = ""
            if cost_col:
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(df_stdb[db_col].head(40).tolist()),
                    datasets=[{"label": "Cost ($)", "data": [round(float(v), 2) for v in df_stdb[cost_col].head(40).tolist()], "backgroundColor": _P}],
                    title="Estimated Monthly Storage Cost by Database", x_title="Cost ($)"))
            if avg_col:
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(df_stdb[db_col].head(40).tolist()),
                    datasets=[{"label": "Average TB", "data": [round(float(v), 4) for v in df_stdb[avg_col].head(40).tolist()], "backgroundColor": _S}],
                    title="Average Storage by Database (TB)", x_title="Average TB"))
            if row_html:
                vis_html += _charts_row(row_html)

    if not df_mthly.empty:
        mon_col  = _col(df_mthly, "MONTH")
        cred_col = _col(df_mthly, "MONTHLY_CREDITS")
        if mon_col and cred_col:
            vis_html += _full_wrap(build_chart("line",
                labels=[str(d) for d in df_mthly[mon_col].tolist()],
                datasets=[{"label": "Credits", "data": [round(float(v), 2) for v in df_mthly[cred_col].tolist()],
                           "borderColor": _P, "backgroundColor": "rgba(41,181,232,0.15)", "fill": False}],
                title="Monthly Warehouse Credits (Last 12 Months)", y_title="Credits"))

    if not df_user.empty:
        u_col    = _col(df_user, "USER_NAME")
        cost_col = _col(df_user, "TOTAL_COST_USD", "TOTAL_CREDITS")
        qry_col  = _col(df_user, "QUERY_COUNT")
        if u_col and cost_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_user[u_col].head(10).tolist()),
                datasets=[{"label": "Cost ($)", "data": [round(float(v), 2) for v in df_user[cost_col].head(10).tolist()], "backgroundColor": _S}],
                title="Top 10 Users by Attributed Cost", x_title="Cost ($)"))
            if qry_col and qry_col in df_user.columns:
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(df_user[u_col].head(10).tolist()),
                    datasets=[{"label": "Queries", "data": [int(v) for v in df_user[qry_col].head(10).tolist()], "backgroundColor": _T}],
                    title="Top 10 Users by Query Volume", x_title="Queries"))
            vis_html += _charts_row(row_html)

    if not df_svc.empty:
        svc_col  = _col(df_svc, "SERVICE_TYPE")
        cost_col = _col(df_svc, "TOTAL_COST_USD", "TOTAL_CREDITS")
        tier_col = _col(df_svc, "COST_TIER")
        if svc_col and cost_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_svc[svc_col].head(10).tolist()),
                datasets=[{"label": "Cost ($)", "data": [round(float(v), 2) for v in df_svc[cost_col].head(10).tolist()], "backgroundColor": _S}],
                title="Cost by Snowflake Service Type", x_title="Cost ($)"))
            if tier_col and tier_col in df_svc.columns:
                by_tier = df_svc[tier_col].value_counts()
                row_html += _col_wrap(build_chart("doughnut",
                    labels=by_tier.index.tolist(), data=by_tier.values.tolist(),
                    colors=[_P, _S, _A], title="Service Cost Tier Distribution"))
            vis_html += _charts_row(row_html)

    sub_sections.append(build_sub_section("Visibility", kpis=vis_kpis, charts_html=vis_html))

    # ── 2. Control ────────────────────────────────────────────────────────
    ctrl_html = ""

    if not df_twh.empty:
        wh_col   = _col(df_twh, "WAREHOUSE_NAME")
        cr_col   = _col(df_twh, "TOTAL_CREDITS_30D", "CREDITS_USED")
        tier_col = _col(df_twh, "USAGE_TIER")
        if wh_col and cr_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_twh[wh_col].head(20).tolist()),
                datasets=[{"label": "Credits", "data": [round(float(v), 2) for v in df_twh[cr_col].head(20).tolist()], "backgroundColor": _P}],
                title="Total Credits by Warehouse (30d)", x_title="Credits"))
            if tier_col and tier_col in df_twh.columns:
                by_tier = df_twh[tier_col].value_counts()
                row_html += _col_wrap(build_chart("doughnut",
                    labels=by_tier.index.tolist(), data=by_tier.values.tolist(),
                    colors=[_P, _S, _A], title="Usage Tier Distribution"))
            ctrl_html += _charts_row(row_html)

    if not df_uact.empty:
        wh_col  = _col(df_uact, "WAREHOUSE_NAME")
        hrs_col = _col(df_uact, "AVG_HOURS_PER_DAY")
        up_col  = _col(df_uact, "UPTIME_STATUS")
        if wh_col and hrs_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_uact[wh_col].tolist()),
                datasets=[{"label": "Hours/Day", "data": [round(float(v), 1) for v in df_uact[hrs_col].tolist()], "backgroundColor": _A}],
                title="Avg Hours/Day Running (last 7d)", x_title="Hours/Day"))
            if up_col and up_col in df_uact.columns:
                by_up = df_uact[up_col].value_counts()
                row_html += _col_wrap(build_chart("doughnut",
                    labels=by_up.index.tolist(), data=by_up.values.tolist(),
                    colors=[_A] + _PALETTE[:len(by_up)], title="Uptime Status Distribution"))
            ctrl_html += _charts_row(row_html)

    if not df_idle.empty:
        wh_col   = _col(df_idle, "WAREHOUSE_NAME")
        idle_col = _col(df_idle, "IDLE_CREDITS")
        pct_col  = _col(df_idle, "IDLE_PERCENT")
        if wh_col and idle_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_idle[wh_col].head(15).tolist()),
                datasets=[{"label": "Idle Credits", "data": [round(float(v), 2) for v in df_idle[idle_col].head(15).tolist()], "backgroundColor": _A}],
                title="Idle Credits by Warehouse (10d)", x_title="Idle Credits"))
            if pct_col and pct_col in df_idle.columns:
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(df_idle[wh_col].head(15).tolist()),
                    datasets=[{"label": "Idle %", "data": [round(float(v), 1) for v in df_idle[pct_col].head(15).tolist()], "backgroundColor": _S}],
                    title="Idle % by Warehouse (10d)", x_title="Idle %"))
            ctrl_html += _charts_row(row_html)

    if not df_rmgap.empty:
        cat_col  = _col(df_rmgap, "RISK_CATEGORY")
        cnt_col  = _col(df_rmgap, "ITEM_COUNT")
        cred_col = _col(df_rmgap, "CREDITS_OR_QUOTA")
        if cat_col and cnt_col:
            row_html = _col_wrap(build_chart("doughnut",
                labels=df_rmgap[cat_col].tolist(),
                data=[float(v) for v in df_rmgap[cnt_col].tolist()],
                colors=[_A, _P], title="Coverage Gap - Item Count"))
            if cred_col and cred_col in df_rmgap.columns:
                row_html += _col_wrap(build_chart("doughnut",
                    labels=df_rmgap[cat_col].tolist(),
                    data=[float(v) for v in df_rmgap[cred_col].tolist()],
                    colors=[_A, _P], title="Coverage Gap - Credits"))
            ctrl_html += _charts_row(row_html)

    if not df_wow.empty:
        wh_col   = _col(df_wow, "WAREHOUSE_NAME")
        prev_col = _col(df_wow, "PREVIOUS_WEEK_CREDITS")
        curr_col = _col(df_wow, "CURRENT_WEEK_CREDITS")
        stat_col = _col(df_wow, "TREND_STATUS")
        if wh_col and prev_col and curr_col:
            row_html = _col_wrap(build_chart("vbar",
                labels=_trunc(df_wow[wh_col].tolist()),
                datasets=[
                    {"label": "Previous Week", "data": [round(float(v), 2) for v in df_wow[prev_col].tolist()], "backgroundColor": _T},
                    {"label": "Current Week",  "data": [round(float(v), 2) for v in df_wow[curr_col].tolist()], "backgroundColor": _P},
                ],
                title="WoW Credits Comparison", y_title="Credits"))
            if stat_col and stat_col in df_wow.columns:
                by_stat = df_wow[stat_col].value_counts()
                row_html += _col_wrap(build_chart("doughnut",
                    labels=by_stat.index.tolist(), data=by_stat.values.tolist(),
                    colors=[_A] + _PALETTE[:len(by_stat)], title="Trend Status Distribution"))
            ctrl_html += _charts_row(row_html)

    if not df_serv.empty:
        svc_col = _col(df_serv, "SERVICE_TYPE")
        cr_col  = _col(df_serv, "TOTAL_CREDITS")
        if svc_col and cr_col:
            ctrl_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(df_serv[svc_col].tolist()),
                    datasets=[{"label": "Credits", "data": [round(float(v), 2) for v in df_serv[cr_col].tolist()], "backgroundColor": _S}],
                    title="Serverless Credits by Type (30d)", x_title="Credits")) +
                _col_wrap(build_chart("doughnut",
                    labels=_trunc(df_serv[svc_col].tolist()),
                    data=[float(v) for v in df_serv[cr_col].tolist()],
                    colors=_PALETTE[:len(df_serv)], title="Serverless Credit Distribution")))

    if not df_spend.empty:
        svc_col = _col(df_spend, "SERVICE_TYPE")
        cr_col  = _col(df_spend, "TOTAL_CREDITS")
        if svc_col and cr_col:
            ctrl_html += _charts_row(
                _col_wrap(build_chart("hbar",
                    labels=_trunc(df_spend[svc_col].tolist()),
                    datasets=[{"label": "Credits", "data": [round(float(v), 2) for v in df_spend[cr_col].tolist()], "backgroundColor": _P}],
                    title="Credits by Service Type", x_title="Credits")) +
                _col_wrap(build_chart("doughnut",
                    labels=_trunc(df_spend[svc_col].tolist()),
                    data=[float(v) for v in df_spend[cr_col].tolist()],
                    colors=_PALETTE[:len(df_spend)], title="Spend Mix")))

    if not df_mtrnd.empty:
        mon_col  = _col(df_mtrnd, "MONTH")
        comp_col = _col(df_mtrnd, "COMPUTE_CREDITS")
        svcs_col = _col(df_mtrnd, "CS_CREDITS")
        cost_col = _col(df_mtrnd, "ESTIMATED_COST_USD")
        if mon_col and comp_col:
            df_mt_sorted = df_mtrnd.sort_values(mon_col) if mon_col else df_mtrnd
            datasets = [{"label": "Compute", "data": [round(float(v), 2) for v in df_mt_sorted[comp_col].tolist()], "backgroundColor": _P}]
            if svcs_col and svcs_col in df_mt_sorted.columns:
                datasets.append({"label": "Cloud Services", "data": [round(float(v), 2) for v in df_mt_sorted[svcs_col].tolist()], "backgroundColor": _A})
            row_html = _col_wrap(build_chart("vbar",
                labels=[str(d) for d in df_mt_sorted[mon_col].tolist()],
                datasets=datasets,
                title="Monthly Credits", y_title="Credits"))
            if cost_col and cost_col in df_mt_sorted.columns:
                row_html += _col_wrap(build_chart("line",
                    labels=[str(d) for d in df_mt_sorted[mon_col].tolist()],
                    datasets=[{"label": "Estimated Cost ($)", "data": [round(float(v), 2) for v in df_mt_sorted[cost_col].tolist()],
                               "borderColor": _S, "backgroundColor": "rgba(17,86,127,0.12)", "fill": False}],
                    title="Monthly Estimated Cost USD ($3/credit)", y_title="Cost ($)"))
            ctrl_html += _charts_row(row_html)

    if not df_stcst.empty:
        mon_col = _col(df_stcst, "MONTH")
        tb_col  = _col(df_stcst, "AVG_STORAGE_TB")
        if mon_col and tb_col:
            df_st_sorted = df_stcst.sort_values(mon_col) if mon_col else df_stcst
            ctrl_html += _full_wrap(build_chart("vbar",
                labels=[str(d) for d in df_st_sorted[mon_col].tolist()],
                datasets=[{"label": "Average TB", "data": [round(float(v), 4) for v in df_st_sorted[tb_col].tolist()], "backgroundColor": _A}],
                title="Average Storage TB by Month", y_title="Average TB"))

    if not df_rm.empty:
        rm_map = [("MONITOR_NAME", "Monitor"), ("CREDIT_QUOTA", "Credit Quota"),
                  ("NOTIFY", "Notify %"), ("SUSPEND", "Suspend %"),
                  ("SUSPEND_IMMEDIATE", "Suspend Immediate %"), ("CREATED", "Created")]
        rm_avail = [(r, h) for r, h in rm_map if r in df_rm.columns]
        if rm_avail:
            ctrl_html += _subtitle("Resource Monitors")
            ctrl_html += _make_table(
                [h for _, h in rm_avail],
                df_rm.head(20)[[r for r, _ in rm_avail]].values.tolist())

    if ctrl_html:
        sub_sections.append(build_sub_section("Control", charts_html=ctrl_html))

    # ── 3. Optimization ───────────────────────────────────────────────────
    opt_html = ""

    if not df_idle.empty:
        wh_col  = _col(df_idle, "WAREHOUSE_NAME")
        pct_col = _col(df_idle, "IDLE_PERCENT")
        cr_col  = _col(df_idle, "TOTAL_COMPUTE_CREDITS")
        if wh_col and pct_col:
            top20 = df_idle.nlargest(20, pct_col) if pct_col in df_idle.columns else df_idle.head(20)
            opt_html += _full_wrap(build_chart("hbar",
                labels=_trunc(top20[wh_col].tolist()),
                datasets=[{"label": "Idle %", "data": [round(float(v), 1) for v in top20[pct_col].tolist()], "backgroundColor": _A}],
                title="Avg Idle % by Warehouse (30d)"))
            idle_tbl_map = [("WAREHOUSE_NAME", "Warehouse"), ("IDLE_PERCENT", "Avg Idle %"), ("TOTAL_COMPUTE_CREDITS", "Total Compute Credits")]
            idle_tbl_avail = [(r, h) for r, h in idle_tbl_map if r in df_idle.columns]
            if idle_tbl_avail:
                fmt_rows = []
                for _, row in top20.iterrows():
                    fmt_row = []
                    for r, _ in idle_tbl_avail:
                        v = row.get(r, "")
                        if r == "IDLE_PERCENT":
                            fmt_row.append(f"{float(v):.1f}%")
                        else:
                            fmt_row.append(v)
                    fmt_rows.append(fmt_row)
                opt_html += _subtitle("Idle Detail")
                opt_html += _make_table([h for _, h in idle_tbl_avail], fmt_rows)

    if not df_cpps.empty:
        issue_col = _col(df_cpps, "ISSUE_TYPE")
        exe_col   = _col(df_cpps, "EXECUTION_COUNT")
        pat_col   = _col(df_cpps, "QUERY_PATTERN")
        if issue_col:
            by_issue = df_cpps[issue_col].value_counts()
            row_html = _col_wrap(build_chart("doughnut",
                labels=by_issue.index.tolist(), data=by_issue.values.tolist(),
                colors=[_A] + _PALETTE[:len(by_issue)],
                title="Issue Type Distribution - Inefficient COPY Commands"))
            if exe_col and pat_col:
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(df_cpps[pat_col].head(10).tolist(), 60),
                    datasets=[{"label": "Executions", "data": [int(v) for v in df_cpps[exe_col].head(10).tolist()], "backgroundColor": _A}],
                    title="COPY Executions by Pattern", x_title="Executions"))
            opt_html += _charts_row(row_html)

    if not df_shrt.empty:
        tmpl_col = _col(df_shrt, "QUERY_TEMPLATE_SHORT")
        exe_col  = _col(df_shrt, "EXECUTION_COUNT")
        tool_col = _col(df_shrt, "CLIENT_TOOL")
        if tmpl_col and exe_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_shrt[tmpl_col].head(10).tolist(), 80),
                datasets=[{"label": "Executions", "data": [int(v) for v in df_shrt[exe_col].head(10).tolist()], "backgroundColor": _S}],
                title="High-Frequency Short Query Templates", x_title="Executions"))
            if tool_col and tool_col in df_shrt.columns:
                by_tool = df_shrt.groupby(tool_col)[exe_col].sum().sort_values(ascending=False)
                row_html += _col_wrap(build_chart("hbar",
                    labels=_trunc(by_tool.index.tolist()),
                    datasets=[{"label": "Executions", "data": [int(v) for v in by_tool.values.tolist()], "backgroundColor": _T}],
                    title="High-Frequency Short Queries by Client Tool", x_title="Executions"))
            opt_html += _charts_row(row_html)

    if not df_show.empty:
        cmd_col = _col(df_show, "COMMAND_TYPE")
        exe_col = _col(df_show, "EXECUTION_COUNT")
        if cmd_col and exe_col:
            opt_html += _full_wrap(build_chart("hbar",
                labels=_trunc(df_show[cmd_col].head(10).tolist(), 80),
                datasets=[{"label": "Executions", "data": [int(v) for v in df_show[exe_col].head(10).tolist()], "backgroundColor": _P}],
                title="Top SHOW Commands by Frequency", x_title="Executions"))

    if not df_sri.empty:
        tgt_col = _col(df_sri, "TARGET_TABLE")
        ins_col = _col(df_sri, "INSERT_COUNT")
        sev_col = _col(df_sri, "SEVERITY")
        if tgt_col and ins_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_sri[tgt_col].astype(str).head(10).tolist()),
                datasets=[{"label": "Inserts", "data": [int(v) for v in df_sri[ins_col].head(10).tolist()], "backgroundColor": _A}],
                title="Single-Row INSERTs by Table", x_title="Inserts"))
            if sev_col and sev_col in df_sri.columns:
                by_sev = df_sri[sev_col].value_counts()
                row_html += _col_wrap(build_chart("doughnut",
                    labels=by_sev.index.tolist(), data=by_sev.values.tolist(),
                    colors=_PALETTE[:len(by_sev)], title="Severity Distribution"))
            opt_html += _charts_row(row_html)

    if not df_cplx.empty:
        q_col   = _col(df_cplx, "QUERY_ID")
        comp_col= _col(df_cplx, "COMPILE_MS")
        sev_col = _col(df_cplx, "SEVERITY")
        if q_col and comp_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_cplx[q_col].head(10).tolist()),
                datasets=[{"label": "Compile (ms)", "data": [int(v) for v in df_cplx[comp_col].head(10).tolist()], "backgroundColor": _A}],
                title="Queries by Compilation Time (ms)", x_title="Compile (ms)"))
            if sev_col and sev_col in df_cplx.columns:
                by_sev = df_cplx[sev_col].value_counts()
                row_html += _col_wrap(build_chart("doughnut",
                    labels=by_sev.index.tolist(), data=by_sev.values.tolist(),
                    colors=_PALETTE[:len(by_sev)], title="Complexity Severity Distribution"))
            opt_html += _charts_row(row_html)

    if not df_csoh.empty:
        pat_col  = _col(df_csoh, "PATTERN")
        cred_col = _col(df_csoh, "CLOUD_SERVICES_CREDITS_30D")
        if pat_col and cred_col:
            opt_html += _full_wrap(build_chart("hbar",
                labels=_trunc(df_csoh[pat_col].tolist()),
                datasets=[{"label": "CS Credits", "data": [round(float(v), 4) for v in df_csoh[cred_col].tolist()], "backgroundColor": _S}],
                title="Cloud Services Overhead Patterns (30d)", x_title="Credits"))
            oh_map = [("PATTERN", "Pattern"), ("CLOUD_SERVICES_CREDITS_30D", "CS Credits"),
                      ("ESTIMATED_COST_USD", "Est. Cost ($)"), ("PCT_OF_OVERHEAD", "% of Overhead")]
            oh_avail = [(r, h) for r, h in oh_map if r in df_csoh.columns]
            if oh_avail:
                opt_html += _make_table(
                    [h for _, h in oh_avail],
                    df_csoh[[r for r, _ in oh_avail]].values.tolist())

    if opt_html:
        sub_sections.append(build_sub_section("Optimization", charts_html=opt_html))

    return build_report(
        topic_name="FinOps (lite)",
        account_name=account_name,
        top_kpis=top_kpis,
        sub_sections=sub_sections,
    )


# ── Data Recovery & DevOps ──────────────────────────────────────────────────

def export_recovery_devops(account_name: str) -> str:
    df_dcm      = _safe_df("rd_dcm_adoption")
    df_git      = _safe_df("rd_git_integration")
    df_cicd_sum = _safe_df("rd_cicd_summary")
    df_cicd_det = _safe_df("rd_cicd_detail")
    df_orch     = _safe_df("rd_orchestration")
    df_dt_inv   = _safe_df("rd_dt_inventory")
    df_dt_ref   = _safe_df("rd_dt_refresh_stats")
    df_dt_day   = _safe_df("rd_dt_daily_refresh")
    df_maturity = _safe_df("rd_maturity_score")
    df_metrics  = _safe_df("rd_summary_metrics")

    total_ddl = 0
    decl_ddl = 0
    git_dep = 0
    top_pattern = ""
    if not df_dcm.empty:
        exe_col = _col(df_dcm, "EXECUTION_COUNT")
        pat_col = _col(df_dcm, "DDL_PATTERN")
        if exe_col:
            total_ddl = int(df_dcm[exe_col].sum())
        if pat_col:
            for _, row in df_dcm.iterrows():
                p = str(row.get(pat_col, ""))
                e = int(row.get(exe_col, 0)) if exe_col else 0
                if "Declarative" in p:
                    decl_ddl += e
                elif "File/Git" in p or "Deployment from" in p:
                    git_dep += e
            if len(df_dcm) > 0:
                top_pattern = str(df_dcm.iloc[0][pat_col])

    top_kpis = []
    if total_ddl > 0:
        top_kpis.append({"value": f"{total_ddl:,}", "label": "Successful DDL Ops (30d)"})
    top_kpis.append({"value": f"{decl_ddl:,}", "label": "Declarative DDL"})
    top_kpis.append({"value": f"{git_dep:,}", "label": "Git-Based Deployments"})
    if top_pattern:
        top_kpis.append({"value": top_pattern, "label": "Top Pattern"})

    sub_sections = []

    # ── 1. DCM Adoption ───────────────────────────────────────────────────
    dcm_kpis = list(top_kpis)
    dcm_html = ""
    if not df_dcm.empty:
        pat_col = _col(df_dcm, "DDL_PATTERN")
        exe_col = _col(df_dcm, "EXECUTION_COUNT")
        usr_col = _col(df_dcm, "DISTINCT_USERS")
        rol_col = _col(df_dcm, "DISTINCT_ROLES")
        pct_col = _col(df_dcm, "PCT_OF_TOTAL")

        if pat_col and exe_col:
            row_html = _col_wrap(build_chart("doughnut",
                labels=_trunc(df_dcm[pat_col].tolist()),
                data=[int(v) for v in df_dcm[exe_col].tolist()],
                colors=_PALETTE[:len(df_dcm)],
                title="DDL Deployment Pattern Distribution (30d)"))
            row_html += _col_wrap(build_chart("hbar",
                labels=_trunc(df_dcm[pat_col].tolist()),
                datasets=[{"label": "Executions", "data": [int(v) for v in df_dcm[exe_col].tolist()], "backgroundColor": _S}],
                title="DDL Pattern Execution Count (30d)"))
            dcm_html += _charts_row(row_html)

        if pat_col and usr_col and usr_col in df_dcm.columns:
            ds = [{"label": "Distinct Users", "data": [int(v) for v in df_dcm[usr_col].tolist()], "backgroundColor": _P}]
            if rol_col and rol_col in df_dcm.columns:
                ds.append({"label": "Distinct Roles", "data": [int(v) for v in df_dcm[rol_col].tolist()], "backgroundColor": _A})
            tbl_map = [("DDL_PATTERN", "DDL Pattern"), ("EXECUTION_COUNT", "Executions"),
                       ("DISTINCT_USERS", "Distinct Users"), ("DISTINCT_ROLES", "Distinct Roles"),
                       ("PCT_OF_TOTAL", "Pct of Total")]
            tbl_avail = [(r, h) for r, h in tbl_map if r in df_dcm.columns]
            fmt_rows = []
            for _, row in df_dcm.iterrows():
                fmt_row = []
                for r, _ in tbl_avail:
                    v = row.get(r, "")
                    if r == "PCT_OF_TOTAL":
                        fmt_row.append(f"{float(v):.1f}%")
                    else:
                        fmt_row.append(v)
                fmt_rows.append(fmt_row)

            dcm_html += (
                '<div class="charts-row" style="align-items:flex-start;margin-top:14px;">\n'
                '  <div class="chart-col" style="flex:0 0 42%;">' +
                build_chart("vbar",
                    labels=_trunc(df_dcm[pat_col].tolist()),
                    datasets=ds,
                    title="Pattern Participation Coverage (Users vs Roles)", y_title="Count") +
                '</div>\n'
                '  <div class="chart-col" style="flex:1;overflow-x:auto;">' +
                _subtitle("Pattern Coverage Detail") +
                _make_table([h for _, h in tbl_avail], fmt_rows) +
                '</div>\n</div>')

    sub_sections.append(build_sub_section("Database Change Management (DCM) Adoption",
                                           kpis=dcm_kpis, charts_html=dcm_html))

    # ── 2. Git Integration ────────────────────────────────────────────────
    git_html = ""
    git_kpis = []
    if not df_git.empty:
        op_col  = _col(df_git, "OPERATION_TYPE")
        cnt_col = _col(df_git, "COUNT_OPS")
        usr_col = _col(df_git, "DISTINCT_USERS")
        if op_col and cnt_col:
            total_ops = int(df_git[cnt_col].sum())
            top_activity = str(df_git.iloc[0][op_col]) if len(df_git) > 0 else "N/A"
            max_users = int(df_git[usr_col].max()) if usr_col and usr_col in df_git.columns else 0
            git_kpis = [
                {"value": f"{total_ops:,}", "label": "Git Operations (30d)"},
                {"value": str(len(df_git)), "label": "Operation Categories"},
                {"value": top_activity, "label": "Top Git Activity"},
                {"value": str(max_users), "label": "Max Users / Operation"},
            ]
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_git[op_col].tolist()),
                datasets=[{"label": "Operations", "data": [int(v) for v in df_git[cnt_col].tolist()], "backgroundColor": _S}],
                title="Git Operation Categories (30d)"))
            row_html += _col_wrap(build_chart("doughnut",
                labels=_trunc(df_git[op_col].tolist()),
                data=[int(v) for v in df_git[cnt_col].tolist()],
                colors=_PALETTE[:len(df_git)],
                title="Git Activity Mix (30d)"))
            git_html += _charts_row(row_html)

            if usr_col and usr_col in df_git.columns:
                tbl_map = [("OPERATION_TYPE", "Operation Type"), ("COUNT_OPS", "Operation Count"),
                           ("DISTINCT_USERS", "Distinct Users")]
                tbl_avail = [(r, h) for r, h in tbl_map if r in df_git.columns]
                git_html += (
                    '<div class="charts-row" style="align-items:flex-start;margin-top:14px;">\n'
                    '  <div class="chart-col" style="flex:0 0 42%;">' +
                    build_chart("hbar",
                        labels=_trunc(df_git[op_col].tolist()),
                        datasets=[{"label": "Distinct Users", "data": [int(v) for v in df_git[usr_col].tolist()], "backgroundColor": _T}],
                        title="Distinct Users by Git Operation") +
                    '</div>\n'
                    '  <div class="chart-col" style="flex:1;overflow-x:auto;">' +
                    _subtitle("Git Integration Detail") +
                    _make_table(
                        [h for _, h in tbl_avail],
                        df_git[[r for r, _ in tbl_avail]].values.tolist()) +
                    '</div>\n</div>')

    sub_sections.append(build_sub_section("Git Integration Usage", kpis=git_kpis, charts_html=git_html))

    # ── 3. CI/CD Automation ───────────────────────────────────────────────
    cicd_html = ""
    cicd_kpis = []
    if not df_cicd_sum.empty:
        agent_col = _col(df_cicd_sum, "DEPLOYMENT_AGENT")
        ddl_col   = _col(df_cicd_sum, "DDL_OPERATIONS_COUNT")
        sess_col  = _col(df_cicd_sum, "SESSION_COUNT")
        pct_col   = _col(df_cicd_sum, "PCT_OF_DDL_OPS")

        total_ops = 0
        if ddl_col:
            total_ops = int(df_cicd_sum[ddl_col].sum())
            cicd_kpis.append({"value": f"{total_ops:,}", "label": "DDL Ops Attributed (30d)"})
        if agent_col:
            cicd_kpis.append({"value": str(len(df_cicd_sum)), "label": "Deployment Agents"})
        if agent_col and ddl_col:
            human_row = df_cicd_sum.loc[df_cicd_sum[agent_col] == "Human / Other"]
            automated = total_ops - (int(human_row[ddl_col].iloc[0]) if len(human_row) > 0 else 0)
            auto_pct = round(automated * 100.0 / total_ops, 1) if total_ops > 0 else 0.0
            cicd_kpis.append({"value": f"{auto_pct}%", "label": "Automated DDL Share"})
            top_agent = str(df_cicd_sum.iloc[0][agent_col]) if len(df_cicd_sum) > 0 else "N/A"
            cicd_kpis.append({"value": top_agent, "label": "Top Agent"})

            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_cicd_sum[agent_col].tolist()),
                datasets=[{"label": "DDL Operations", "data": [int(v) for v in df_cicd_sum[ddl_col].tolist()], "backgroundColor": _P}],
                title="CI/CD Tool Summary (30d)"))
            row_html += _col_wrap(build_chart("doughnut",
                labels=_trunc(df_cicd_sum[agent_col].tolist()),
                data=[int(v) for v in df_cicd_sum[ddl_col].tolist()],
                colors=_PALETTE[:len(df_cicd_sum)],
                title="DDL Automation Share by Agent"))
            cicd_html += _charts_row(row_html)

            if sess_col and sess_col in df_cicd_sum.columns:
                cicd_html += _full_wrap(build_chart("hbar",
                    labels=_trunc(df_cicd_sum[agent_col].tolist()),
                    datasets=[{"label": "Distinct Sessions", "data": [int(v) for v in df_cicd_sum[sess_col].tolist()], "backgroundColor": _T}],
                    title="Session Footprint by Deployment Agent"))

    if not df_cicd_det.empty:
        det_map = [("DEPLOYMENT_AGENT", "Deployment Agent"), ("CLIENT_APPLICATION_ID", "Client Application"),
                   ("SESSION_COUNT", "Distinct Sessions"), ("DDL_OPERATIONS_COUNT", "DDL Operations"),
                   ("DISTINCT_USERS", "Distinct Users")]
        det_avail = [(r, h) for r, h in det_map if r in df_cicd_det.columns]
        if det_avail:
            cicd_html += _subtitle("CI/CD Tool Identification Detail")
            cicd_html += _make_table(
                [h for _, h in det_avail],
                df_cicd_det.head(20)[[r for r, _ in det_avail]].values.tolist())

    sub_sections.append(build_sub_section("CI/CD Tool Automation", kpis=cicd_kpis, charts_html=cicd_html))

    # ── 4. Orchestration Patterns ─────────────────────────────────────────
    orch_html = ""
    orch_kpis = []

    dt_count = 0
    db_count = 0
    schema_count = 0
    if not df_dt_inv.empty:
        dt_c = _col(df_dt_inv, "DT_COUNT")
        db_c = _col(df_dt_inv, "DB_COUNT")
        sc_c = _col(df_dt_inv, "SCHEMA_COUNT")
        dt_count = int(_row0(df_dt_inv, dt_c, 0)) if dt_c else 0
        db_count = int(_row0(df_dt_inv, db_c, 0)) if db_c else 0
        schema_count = int(_row0(df_dt_inv, sc_c, 0)) if sc_c else 0

    refresh_count = 0
    avg_lag = 0.0
    if not df_dt_ref.empty:
        ref_c = _col(df_dt_ref, "REFRESH_COUNT")
        lag_c = _col(df_dt_ref, "AVG_LAG_MIN")
        refresh_count = int(_row0(df_dt_ref, ref_c, 0)) if ref_c else 0
        avg_lag = round(float(_row0(df_dt_ref, lag_c, 0) or 0), 1) if lag_c else 0.0

    orch_kpis = [
        {"value": f"{dt_count:,}", "label": "Dynamic Tables"},
        {"value": str(db_count), "label": "Databases"},
        {"value": str(schema_count), "label": "Schemas"},
        {"value": f"{refresh_count:,}", "label": "Refreshes (30d)"},
        {"value": str(avg_lag), "label": "Avg Lag (min)"},
    ]

    orch_html += _subtitle("Declarative vs Imperative Orchestration (7d)")
    if not df_orch.empty:
        type_col = _col(df_orch, "ORCHESTRATION_TYPE")
        cnt_col  = _col(df_orch, "ACTIVITY_COUNT")
        obj_col  = _col(df_orch, "DISTINCT_OBJECTS")
        if type_col and cnt_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_orch[type_col].tolist()),
                datasets=[{"label": "Activity Count", "data": [int(v) for v in df_orch[cnt_col].tolist()], "backgroundColor": _P}],
                title="Orchestration Activity Count"))
            if obj_col and obj_col in df_orch.columns:
                row_html += _col_wrap(build_chart("doughnut",
                    labels=_trunc(df_orch[type_col].tolist()),
                    data=[int(v) for v in df_orch[obj_col].tolist()],
                    colors=[_P, _S],
                    title="Distinct Orchestrated Objects"))
            orch_html += _charts_row(row_html)

    orch_html += _subtitle("Dynamic Table Operational Detail (30d)")
    if not df_dt_day.empty:
        date_col = _col(df_dt_day, "REFRESH_DATE")
        suc_col  = _col(df_dt_day, "SUCCESS")
        fail_col = _col(df_dt_day, "FAILURES")
        if date_col and suc_col:
            row_html = ""
            if refresh_count > 0:
                row_html += _col_wrap(build_chart("vbar",
                    labels=[str(d) for d in df_dt_day[date_col].tolist()],
                    datasets=[
                        {"label": "Success", "data": [int(v) for v in df_dt_day[suc_col].tolist()], "backgroundColor": _P},
                    ] + ([{"label": "Failures", "data": [int(v) for v in df_dt_day[fail_col].tolist()], "backgroundColor": _A}] if fail_col and fail_col in df_dt_day.columns else []),
                    title="Refreshes by Dynamic Table (30d)", y_title="Refreshes"))
                if fail_col and fail_col in df_dt_day.columns:
                    total_s = int(df_dt_day[suc_col].sum())
                    total_f = int(df_dt_day[fail_col].sum())
                    if total_s > 0 or total_f > 0:
                        row_html += _col_wrap(build_chart("doughnut",
                            labels=["Succeeded", "Failed"],
                            data=[total_s, total_f],
                            colors=[_P, _A],
                            title="Refresh Outcome Distribution (30d)"))
                orch_html += _charts_row(row_html)

                row_html2 = _col_wrap(build_chart("line",
                    labels=[str(d) for d in df_dt_day[date_col].tolist()],
                    datasets=[{"label": "Refreshes", "data": [int(v) for v in df_dt_day[suc_col].tolist()],
                               "borderColor": _P, "backgroundColor": "rgba(41,181,232,0.15)", "fill": False}],
                    title="Daily Refresh Trend (30d)", y_title="Refreshes"))
                orch_html += _charts_row(row_html2)
            else:
                orch_html += _charts_row(
                    _col_wrap('<div class="chart-block"><div class="chart-title">Refreshes by Dynamic Table (30d)</div>'
                              '<p class="no-data-note">No dynamic table refresh detail rows were available for this run.</p></div>') +
                    _col_wrap('<div class="chart-block"><div class="chart-title">Refresh Outcome Distribution (30d)</div>'
                              '<p class="no-data-note">No refresh outcome data was available for this run.</p></div>'))
                orch_html += _charts_row(
                    _col_wrap('<div class="chart-block"><div class="chart-title">Average Lag by Dynamic Table (30d)</div>'
                              '<p class="no-data-note">No lag metrics were available for this run.</p></div>') +
                    _col_wrap('<div class="chart-block"><div class="chart-title">Daily Refresh Trend (30d)</div>'
                              '<p class="no-data-note">No dynamic table refresh trend data was available for this run.</p></div>'))
        else:
            orch_html += '<p class="no-data-note">No dynamic table refresh detail rows were available for this run.</p>'
    else:
        orch_html += _charts_row(
            _col_wrap('<div class="chart-block"><div class="chart-title">Refreshes by Dynamic Table (30d)</div>'
                      '<p class="no-data-note">No dynamic table refresh detail rows were available for this run.</p></div>') +
            _col_wrap('<div class="chart-block"><div class="chart-title">Refresh Outcome Distribution (30d)</div>'
                      '<p class="no-data-note">No refresh outcome data was available for this run.</p></div>'))
        orch_html += _charts_row(
            _col_wrap('<div class="chart-block"><div class="chart-title">Average Lag by Dynamic Table (30d)</div>'
                      '<p class="no-data-note">No lag metrics were available for this run.</p></div>') +
            _col_wrap('<div class="chart-block"><div class="chart-title">Daily Refresh Trend (30d)</div>'
                      '<p class="no-data-note">No dynamic table refresh trend data was available for this run.</p></div>'))

    sub_sections.append(build_sub_section("Orchestration Patterns", kpis=orch_kpis, charts_html=orch_html))

    # ── 5. DevOps Maturity Summary ────────────────────────────────────────
    mat_html = ""
    mat_kpis = []

    level = ""
    decl_m = 0
    git_m = 0
    total_m = 0
    recommendation = ""
    if not df_maturity.empty:
        mat_col = _col(df_maturity, "DEVOPS_MATURITY_LEVEL")
        decl_col = _col(df_maturity, "DECLARATIVE_DDL")
        git_col  = _col(df_maturity, "GIT_DEPLOYS")
        total_col = _col(df_maturity, "TOTAL_DDL")
        rec_col  = _col(df_maturity, "PRIMARY_RECOMMENDATION")
        if mat_col:
            level = str(_row0(df_maturity, mat_col, ""))
        if decl_col:
            decl_m = int(_row0(df_maturity, decl_col, 0) or 0)
        if git_col:
            git_m = int(_row0(df_maturity, git_col, 0) or 0)
        if total_col:
            total_m = int(_row0(df_maturity, total_col, 0) or 0)
        if rec_col:
            recommendation = str(_row0(df_maturity, rec_col, ""))

    if level:
        mat_kpis.append({"value": level, "label": "Maturity Level"})
    mat_kpis.append({"value": f"{decl_m:,}", "label": "Declarative DDL"})
    mat_kpis.append({"value": f"{git_m:,}", "label": "Git Deployments"})
    if total_m > 0:
        mat_kpis.append({"value": f"{total_m:,}", "label": "Total Successful DDL"})

    if not df_metrics.empty:
        metric_col = _col(df_metrics, "METRIC_NAME")
        val_col    = _col(df_metrics, "METRIC_VALUE")
        cat_col    = _col(df_metrics, "METRIC_CATEGORY")
        pct_col    = _col(df_metrics, "PCT_OF_TOTAL")
        if metric_col and val_col:
            row_html = _col_wrap(build_chart("hbar",
                labels=_trunc(df_metrics[metric_col].tolist()),
                datasets=[{"label": "Metric Value", "data": [round(float(v or 0), 2) for v in df_metrics[val_col].tolist()], "backgroundColor": _P}],
                title="DevOps Summary Metrics"))
            if cat_col and cat_col in df_metrics.columns:
                cat_agg = df_metrics.groupby(cat_col)[val_col].sum()
                cat_agg = cat_agg[cat_agg > 0]
                if not cat_agg.empty:
                    row_html += _col_wrap(build_chart("doughnut",
                        labels=cat_agg.index.tolist(),
                        data=[round(float(v), 2) for v in cat_agg.values.tolist()],
                        colors=[_P, _S, _T],
                        title="Summary Metric Value Mix"))
            mat_html += _charts_row(row_html)

    level_map = {"NO_DATA": 0, "BASIC": 1, "INTERMEDIATE": 2, "ADVANCED": 3}
    score_val = level_map.get(level, 0)
    score_frac = score_val / 3.0
    filled_pct = round(score_frac * 50, 6)
    grey_pct = round(50 - filled_pct, 6)
    transparent_pct = 50.0
    gauge_color = "#F39C12"
    gauge_id = _next_chart_id()
    score_display = f"{score_val:.2f}"

    gauge_html = (
        f'<div class="chart-block" style="height:260px; position:relative;">\n'
        f'  <div class="chart-title">DevOps Maturity Score (0-3)</div>\n'
        f'  <div style="position:relative; height:224px;">\n'
        f'    <canvas id="{gauge_id}"></canvas>\n'
        f'    <div style="position:absolute; bottom:8%; left:50%; transform:translateX(-50%);'
        f'                font-size:1.6rem; font-weight:700; color:{gauge_color}; pointer-events:none;">\n'
        f'      {score_display}\n'
        f'    </div>\n'
        f'    <div style="position:absolute; bottom:2%; left:50%; transform:translateX(-50%);'
        f'                font-size:0.72rem; color:#6b7280; pointer-events:none;">\n'
        f'      0 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 1.5 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 3\n'
        f'    </div>\n'
        f'  </div>\n'
        f'  <script>\n'
        f'  (function(){{\n'
        f"    var ctx = document.getElementById('{gauge_id}').getContext('2d');\n"
        f'    new Chart(ctx, {{\n'
        f"      type: 'doughnut',\n"
        f'      data: {{\n'
        f'        datasets: [{{\n'
        f"          data: [{filled_pct}, {grey_pct}, {transparent_pct}],\n"
        f"          backgroundColor: ['{gauge_color}', '#E5E7EB', 'transparent'],\n"
        f'          borderWidth: 0,\n'
        f"          borderColor: 'transparent'\n"
        f'        }}]\n'
        f'      }},\n'
        f'      options: {{\n'
        f'        rotation: -90,\n'
        f'        circumference: 180,\n'
        f"        cutout: '70%',\n"
        f'        plugins: {{\n'
        f'          legend: {{ display: false }},\n'
        f'          tooltip: {{ enabled: false }},\n'
        f'          datalabels: {{ display: false }}\n'
        f'        }},\n'
        f'        responsive: true,\n'
        f'        maintainAspectRatio: false\n'
        f'      }}\n'
        f'    }});\n'
        f'  }})();\n'
        f'  </script>\n'
        f'</div>')

    rec_html = ""
    if recommendation:
        rec_html = _subtitle("Primary Recommendation") + _make_table(["Recommendation"], [[recommendation]])

    mat_html += (
        '<div class="charts-row" style="align-items:flex-start;margin-top:14px;">\n'
        '  <div class="chart-col" style="flex:0 0 42%;">' + gauge_html + '</div>\n'
        '  <div class="chart-col" style="flex:1;overflow-x:auto;">' + rec_html + '</div>\n'
        '</div>')

    if not df_metrics.empty:
        metric_col = _col(df_metrics, "METRIC_NAME")
        val_col    = _col(df_metrics, "METRIC_VALUE")
        cat_col    = _col(df_metrics, "METRIC_CATEGORY")
        pct_col    = _col(df_metrics, "PCT_OF_TOTAL")
        tbl_map = [("METRIC_CATEGORY", "Metric Category"), ("METRIC_NAME", "Metric Name"),
                   ("METRIC_VALUE", "Metric Value"), ("PCT_OF_TOTAL", "Pct of Total")]
        tbl_avail = [(r, h) for r, h in tbl_map if r in df_metrics.columns]
        if tbl_avail:
            fmt_rows = []
            for _, row in df_metrics.iterrows():
                fmt_row = []
                for r, _ in tbl_avail:
                    v = row.get(r, "")
                    if r == "PCT_OF_TOTAL":
                        try:
                            fmt_row.append(f"{float(v):.1f}%")
                        except (ValueError, TypeError):
                            fmt_row.append("N/A")
                    elif r == "METRIC_VALUE":
                        try:
                            fmt_row.append(f"{float(v):,.1f}")
                        except (ValueError, TypeError):
                            fmt_row.append(str(v))
                    else:
                        fmt_row.append(str(v))
                fmt_rows.append(fmt_row)
            mat_html += _make_table([h for _, h in tbl_avail], fmt_rows)

    sub_sections.append(build_sub_section("DevOps Maturity Summary", kpis=mat_kpis, charts_html=mat_html))

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

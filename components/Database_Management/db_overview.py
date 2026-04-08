import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import as_completed
from components.Database_Management._db_queries import ALL_DB_OVERVIEW_QUERIES
from core.config.design_tokens import (
    BRAND_SECONDARY, BRAND_PRIMARY_DARK, BRAND_SECONDARY_LIGHT, BRAND_ACCENT,
    CHART_SERIES, ERROR, INFO,
)

PRIMARY = BRAND_SECONDARY
SECONDARY = BRAND_PRIMARY_DARK
TERTIARY = BRAND_SECONDARY_LIGHT
ALERT = BRAND_ACCENT

STORAGE_ACTIVE = PRIMARY
STORAGE_TIME_TRAVEL = SECONDARY
STORAGE_FAILSAFE = ALERT
STORAGE_CLONE = TERTIARY
STORAGE_COLORS = [STORAGE_ACTIVE, STORAGE_TIME_TRAVEL, STORAGE_FAILSAFE, STORAGE_CLONE]

_query_cache = {}


def _cached_query(_session, query_key, sql):
    if query_key in _query_cache:
        return _query_cache[query_key]
    df = _session.sql(sql).to_pandas()
    _query_cache[query_key] = df
    return df


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_queries(session, queries_dict, progress_bar=None, status_text=None):
    total = len(queries_dict)
    completed = 0
    for k, sql in queries_dict.items():
        key, df, err = _run_query_thread(session, k, sql)
        _query_cache[key] = df
        completed += 1
        if progress_bar is not None:
            progress_bar.progress(completed / total)
        if status_text is not None:
            status_text.text(f"Loading data... ({completed}/{total} queries)")
    if progress_bar is not None:
        progress_bar.empty()
    if status_text is not None:
        status_text.empty()


def _no_data_info(msg="No data available."):
    st.info(msg)


def _error_box(label, err):
    st.error(f"{label}: {err}")


def _plotly_hbar(df, x_col, y_col, color, title="", x_title=""):
    fig = go.Figure(go.Bar(
        x=df[x_col].tolist(),
        y=df[y_col].tolist(),
        orientation="h",
        marker_color=color,
    ))
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title="",
        height=max(300, len(df) * 28),
        margin=dict(l=10, r=10, t=40, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)


def _plotly_stacked_hbar(df, y_col, value_cols, colors, title="", x_title="Storage (TB)"):
    traces = []
    for col, color in zip(value_cols, colors):
        if col in df.columns:
            traces.append(go.Bar(
                name=col.replace("_", " ").title(),
                x=df[col].tolist(),
                y=df[y_col].tolist(),
                orientation="h",
                marker_color=color,
            ))
    fig = go.Figure(data=traces)
    fig.update_layout(
        barmode="stack",
        title=title,
        xaxis_title=x_title,
        yaxis_title="",
        height=max(300, len(df) * 30),
        margin=dict(l=10, r=10, t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _plotly_line(df, x_col, y_col, color, title="", y_title=""):
    fig = go.Figure(go.Scatter(
        x=df[x_col].tolist(),
        y=df[y_col].tolist(),
        mode="lines+markers",
        fill="tozeroy",
        line=dict(color=color, width=2),
        marker=dict(size=6),
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_title,
        height=320,
        margin=dict(l=10, r=10, t=40, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)


def _plotly_pie(values, names, colors, title=""):
    fig = go.Figure(go.Pie(
        labels=names,
        values=values,
        marker_colors=colors,
        texttemplate="%{label} %{value:,.3f} (%{percent})",
        textposition="outside",
        hole=0.3,
    ))
    fig.update_layout(
        title=title,
        height=360,
        margin=dict(l=10, r=10, t=40, b=30),
        showlegend=True,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_overview_subtab():
    try:
        session = st.session_state.session
        total_df = _cached_query(session, "db_overview_1_total_storage_query",
                                 ALL_DB_OVERVIEW_QUERIES["db_overview_1_total_storage_query"])
        if len(total_df) == 0:
            _no_data_info("No storage data available.")
            return

        row = total_df.iloc[0]
        active = row.get("ACTIVE_STORAGE_TB", 0) or 0
        tt = row.get("TIME_TRAVEL_STORAGE_TB", 0) or 0
        fs = row.get("FAILSAFE_STORAGE_TB", 0) or 0
        clone = row.get("RETAINED_FOR_CLONE_STORAGE_TB", 0) or 0
        total = active + tt + fs + clone

        summary_df = _cached_query(session, "db_overview_2_storage_summary_query",
                                   ALL_DB_OVERVIEW_QUERIES["db_overview_2_storage_summary_query"])
        db_count = 0
        tbl_count = 0
        if len(summary_df) > 0:
            db_count = summary_df.iloc[0].get("DATABASE_COUNT", 0) or 0
            tbl_count = summary_df.iloc[0].get("TABLE_COUNT", 0) or 0

        st.subheader("Storage Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Storage", f"{total:.3f} TB")
        c2.metric("Active", f"{active:.3f} TB")
        c3.metric("Time Travel", f"{tt:.3f} TB")
        c4.metric("Failsafe", f"{fs:.3f} TB")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Clone Retained", f"{clone:.3f} TB")
        c6.metric("Databases", f"{int(db_count):,}")
        c7.metric("Tables", f"{int(tbl_count):,}")
        c8.metric("Analysis Window", "30 days")

        col_l, col_r = st.columns(2)
        with col_l:
            storage_types = ["Active", "Time Travel", "Failsafe", "Clone Retained"]
            storage_vals = [active, tt, fs, clone]
            _plotly_pie(storage_vals, storage_types, STORAGE_COLORS, title="Storage by Type")

        with col_r:
            obj_df = _cached_query(session, "db_overview_14_object_count_query",
                                   ALL_DB_OVERVIEW_QUERIES["db_overview_14_object_count_query"])
            if len(obj_df) > 0:
                obj_df = obj_df.sort_values("OBJECT_COUNT", ascending=True)
                _plotly_hbar(obj_df, "OBJECT_COUNT", "OBJECT_TYPE", PRIMARY, title="Object Counts", x_title="Count")

        st.divider()

        st.subheader("Top Databases by Storage")
        db_df = _cached_query(session, "db_overview_15_db_storage_query",
                              ALL_DB_OVERVIEW_QUERIES["db_overview_15_db_storage_query"])
        if len(db_df) > 0:
            top10 = db_df.head(10).sort_values("TOTAL_STORAGE", ascending=True)
            _plotly_stacked_hbar(
                top10, y_col="TABLE_CATALOG",
                value_cols=["ACTIVE_STORAGE", "TIME_TRAVEL_STORAGE", "FAILSAFE_STORAGE", "RETAINED_FOR_CLONE_STORAGE"],
                colors=STORAGE_COLORS,
                title="Top 10 Databases by Storage"
            )
        else:
            _no_data_info("No database storage data found.")

        with st.expander("Potential Savings Summary", expanded=True):
            _render_potential_savings()

    except Exception as e:
        _error_box("Overview tab error", e)


def _render_storage_subtab():
    try:
        session = st.session_state.session
        summary_df = _cached_query(session, "db_overview_2_storage_summary_query",
                                   ALL_DB_OVERVIEW_QUERIES["db_overview_2_storage_summary_query"])
        if len(summary_df) == 0:
            _no_data_info()
            return

        row = summary_df.iloc[0]
        active = row.get("ACTIVE_STORAGE_TB", 0) or 0
        tt = row.get("TIME_TRAVEL_STORAGE_TB", 0) or 0
        fs = row.get("FAILSAFE_STORAGE_TB", 0) or 0
        clone = row.get("CLONE_STORAGE_TB", 0) or 0
        db_count = row.get("DATABASE_COUNT", 0) or 0
        tbl_count = row.get("TABLE_COUNT", 0) or 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Active Storage", f"{active:.3f} TB")
        c2.metric("Time Travel", f"{tt:.3f} TB")
        c3.metric("Failsafe", f"{fs:.3f} TB")
        c4.metric("Clone", f"{clone:.3f} TB")

        c5, c6 = st.columns(2)
        c5.metric("Databases", f"{int(db_count):,}")
        c6.metric("Tables", f"{int(tbl_count):,}")

        st.divider()

        db_df = _cached_query(session, "db_overview_3_db_storage_query",
                              ALL_DB_OVERVIEW_QUERIES["db_overview_3_db_storage_query"])
        if len(db_df) > 0:
            st.subheader("Storage by Database")
            chart_df = db_df.head(20).sort_values("TOTAL_STORAGE_TB", ascending=True)
            _plotly_stacked_hbar(
                chart_df, y_col="DATABASE_NAME",
                value_cols=["ACTIVE_STORAGE_TB", "TIME_TRAVEL_TB", "FAILSAFE_TB", "CLONE_TB"],
                colors=STORAGE_COLORS,
                title="Storage by Database (TB)"
            )
            show_cols = [c for c in ["DATABASE_NAME", "ACTIVE_STORAGE_TB", "TIME_TRAVEL_TB", "FAILSAFE_TB", "CLONE_TB", "TABLE_COUNT"] if c in db_df.columns]
            st.dataframe(db_df[show_cols].rename(columns={
                "DATABASE_NAME": "Database",
                "ACTIVE_STORAGE_TB": "Active (TB)",
                "TIME_TRAVEL_TB": "Time Travel (TB)",
                "FAILSAFE_TB": "Failsafe (TB)",
                "CLONE_TB": "Clone (TB)",
                "TABLE_COUNT": "Tables",
            }), use_container_width=True)

        st.divider()
        st.subheader("Top 50 Tables by Storage")
        tbl_df = _cached_query(session, "db_overview_4_top_tables_query",
                               ALL_DB_OVERVIEW_QUERIES["db_overview_4_top_tables_query"])
        if len(tbl_df) > 0:
            chart_df = tbl_df.head(20).sort_values("TOTAL_GB", ascending=True)
            _plotly_stacked_hbar(
                chart_df, y_col="FULL_TABLE_NAME",
                value_cols=["ACTIVE_STORAGE_GB", "TIME_TRAVEL_GB", "FAILSAFE_GB"],
                colors=[PRIMARY, SECONDARY, ALERT],
                title="Top Tables by Storage Breakdown (GB)",
                x_title="Storage (GB)"
            )
            st.dataframe(tbl_df[["FULL_TABLE_NAME", "ACTIVE_STORAGE_GB", "TIME_TRAVEL_GB", "FAILSAFE_GB", "TOTAL_GB"]].rename(columns={
                "FULL_TABLE_NAME": "Table",
                "ACTIVE_STORAGE_GB": "Active (GB)",
                "TIME_TRAVEL_GB": "Time Travel (GB)",
                "FAILSAFE_GB": "Failsafe (GB)",
                "TOTAL_GB": "Total (GB)",
            }), use_container_width=True)
        else:
            _no_data_info("No table storage data found.")

    except Exception as e:
        _error_box("Database Storage tab error", e)


def _render_clustering_subtab():
    try:
        session = st.session_state.session
        overview_df = _cached_query(session, "db_overview_5_clustering_overview_query",
                                    ALL_DB_OVERVIEW_QUERIES["db_overview_5_clustering_overview_query"])
        if len(overview_df) == 0:
            _no_data_info()
            return

        row = overview_df.iloc[0]
        total = int(row.get("TOTAL_TABLES", 0) or 0)
        clustered = int(row.get("CLUSTERED_TABLES", 0) or 0)
        unclustered = int(row.get("UNCLUSTERED_TABLES", 0) or 0)
        pct = row.get("CLUSTER_PERCENTAGE", 0) or 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Tables", f"{total:,}")
        c2.metric("Clustered", f"{clustered:,}")
        c3.metric("Unclustered", f"{unclustered:,}")
        c4.metric("Cluster %", f"{pct:.1f}%")

        st.divider()
        col_l, col_r = st.columns(2)
        with col_l:
            _plotly_pie(
                [clustered, unclustered],
                ["Clustered", "Unclustered"],
                [PRIMARY, ALERT],
                title="Clustered vs Unclustered Tables"
            )
        with col_r:
            hist_df = _cached_query(session, "db_overview_7_credit_history_query",
                                    ALL_DB_OVERVIEW_QUERIES["db_overview_7_credit_history_query"])
            if len(hist_df) > 0:
                hist_df["CLUSTER_DATE"] = hist_df["CLUSTER_DATE"].astype(str).str[:10]
                _plotly_line(hist_df, "CLUSTER_DATE", "DAILY_CREDITS", color=PRIMARY,
                             title="Clustering Credits (Last 30 Days)", y_title="Credits")
            else:
                st.info("No clustering credit history found for the last 30 days.")

        st.divider()
        st.subheader("Automatic Clustering Cost Detail")
        detail_df = _cached_query(session, "db_overview_23_clustering_detail_query",
                                  ALL_DB_OVERVIEW_QUERIES["db_overview_23_clustering_detail_query"])
        if len(detail_df) > 0 and detail_df["CLUSTERING_CREDITS"].sum() > 0:
            chart_df = detail_df[detail_df["CLUSTERING_CREDITS"] > 0].head(15).sort_values("CLUSTERING_CREDITS", ascending=True)
            fig = go.Figure(go.Bar(
                x=chart_df["CLUSTERING_CREDITS"].tolist(),
                y=chart_df["TABLE_NAME"].tolist(),
                orientation="h",
                marker_color=PRIMARY,
                text=[f"{v:.4f}" for v in chart_df["CLUSTERING_CREDITS"].tolist()],
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Credits: %{x:.4f}<extra></extra>",
            ))
            fig.update_layout(
                title="Top Tables by Clustering Credits",
                xaxis_title="Credits",
                yaxis_title="",
                height=max(350, len(chart_df) * 28),
                margin=dict(l=10, r=80, t=50, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)
            show_cols = [c for c in ["TABLE_NAME", "IS_CLUSTERED", "CLUSTERING_KEY", "AUTO_CLUSTERING_ON",
                                     "CLUSTERING_CREDITS", "AVG_CREDITS_PER_DAY", "ACTIVE_DAYS"] if c in detail_df.columns]
            st.dataframe(detail_df[show_cols].rename(columns={
                "TABLE_NAME": "Table",
                "IS_CLUSTERED": "Clustered",
                "CLUSTERING_KEY": "Clustering Key",
                "AUTO_CLUSTERING_ON": "Auto Clustering",
                "CLUSTERING_CREDITS": "Credits",
                "AVG_CREDITS_PER_DAY": "Avg Credits/Day",
                "ACTIVE_DAYS": "Active Days",
            }), use_container_width=True)
        else:
            st.info("No automatic clustering cost data found for the last 30 days.")

        st.divider()
        st.subheader("Clustered Tables")
        clustered_df = _cached_query(session, "db_overview_6_clustered_tables_query",
                                     ALL_DB_OVERVIEW_QUERIES["db_overview_6_clustered_tables_query"])
        if len(clustered_df) > 0:
            if len(clustered_df) > 0:
                chart_df = clustered_df.head(15).sort_values("SIZE_GB", ascending=True)
                _plotly_hbar(chart_df, "SIZE_GB", "FULL_TABLE_NAME", PRIMARY,
                             title="Top Clustered Tables by Size", x_title="Size (GB)")
            st.dataframe(clustered_df.rename(columns={
                "FULL_TABLE_NAME": "Table",
                "DATABASE_NAME": "Database",
                "CLUSTERING_KEY": "Clustering Key",
                "ROW_COUNT": "Rows",
                "SIZE_GB": "Size (GB)",
                "AUTO_CLUSTERING_ON": "Auto Clustering",
                "CREATED": "Created",
            }), use_container_width=True)
        else:
            st.info("No clustered tables found.")

    except Exception as e:
        _error_box("Clustering tab error", e)


def _render_low_lifespan_subtab():
    try:
        session = st.session_state.session
        summary_df = _cached_query(session, "db_overview_8_summary_query",
                                   ALL_DB_OVERVIEW_QUERIES["db_overview_8_summary_query"])
        if len(summary_df) == 0:
            _no_data_info()
            return

        row = summary_df.iloc[0]
        total = int(row.get("TOTAL_SHORT_LIVED", 0) or 0)
        perm = int(row.get("PERMANENT_SHORT_LIVED", 0) or 0)
        trans = int(row.get("TRANSIENT_SHORT_LIVED", 0) or 0)
        avg_min = row.get("AVG_LIFESPAN_MINUTES", 0) or 0
        churned_gb = row.get("TOTAL_CHURNED_STORAGE_GB", 0) or 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Short-Lived Tables", f"{total:,}")
        c2.metric("Permanent (Issue)", f"{perm:,}")
        c3.metric("Transient (OK)", f"{trans:,}")
        c4.metric("Avg Lifespan", f"{avg_min:.0f} min")
        c5.metric("Churned Storage", f"{churned_gb:.2f} GB")

        st.divider()
        col_l, col_r = st.columns(2)
        with col_l:
            agg_df = _cached_query(session, "db_overview_19_aggregates_query",
                                   ALL_DB_OVERVIEW_QUERIES["db_overview_19_aggregates_query"])
            if len(agg_df) > 0:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name="Table Count",
                    x=agg_df["Count of Short-Lived Tables"].tolist(),
                    y=agg_df["Table Category"].tolist(),
                    orientation="h", marker_color=PRIMARY
                ))
                fig.add_trace(go.Bar(
                    name="Avg Lifespan (Min)",
                    x=[round(x, 1) if x else 0 for x in agg_df["Avg Lifespan (Minutes)"].tolist()],
                    y=agg_df["Table Category"].tolist(),
                    orientation="h", marker_color=ALERT
                ))
                fig.update_layout(barmode="group", title="Tables by Type",
                                  height=300, margin=dict(l=10, r=10, t=40, b=30))
                st.plotly_chart(fig, use_container_width=True)
        with col_r:
            _plotly_pie(
                [perm, trans],
                ["Permanent (Issue)", "Transient (OK)"],
                [ALERT, PRIMARY],
                title="Short-Lived by Table Type"
            )

        st.divider()
        st.subheader("Short-Lived Tables by Schema")
        schema_df = _cached_query(session, "db_overview_24_short_lived_by_schema_query",
                                   ALL_DB_OVERVIEW_QUERIES["db_overview_24_short_lived_by_schema_query"])
        if len(schema_df) > 0:
            col_bar, col_pie = st.columns(2)
            with col_bar:
                chart_df = schema_df.head(15).sort_values("SHORT_LIVED_COUNT", ascending=True)
                max_perm = chart_df["PERMANENT_COUNT"].max() if chart_df["PERMANENT_COUNT"].max() > 0 else 1
                bar_colors = [
                    f"rgba({int(17 + (41 - 17) * v / max_perm)},{int(86 + (181 - 86) * v / max_perm)},{int(127 + (232 - 127) * v / max_perm)},0.9)"
                    for v in chart_df["PERMANENT_COUNT"].tolist()
                ]
                fig_bar = go.Figure(go.Bar(
                    x=chart_df["SHORT_LIVED_COUNT"].tolist(),
                    y=chart_df["SCHEMA_NAME"].tolist(),
                    orientation="h",
                    marker_color=bar_colors,
                    customdata=chart_df["PERMANENT_COUNT"].tolist(),
                    hovertemplate="<b>%{y}</b><br>Short-Lived: %{x}<br>Permanent: %{customdata}<extra></extra>",
                ))
                fig_bar.update_layout(
                    title="Short-Lived Tables by Schema (top 15)",
                    xaxis_title="Count",
                    height=max(350, len(chart_df) * 28),
                    margin=dict(l=10, r=10, t=50, b=30),
                    coloraxis_colorbar=dict(title="PERMANENT_COUNT"),
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            with col_pie:
                rec_counts = schema_df["RECOMMENDATION"].value_counts()
                fig_pie = go.Figure(go.Pie(
                    labels=rec_counts.index.tolist(),
                    values=rec_counts.values.tolist(),
                    hole=0.4,
                    marker_colors=[ALERT if "⚠️" in lbl else PRIMARY for lbl in rec_counts.index.tolist()],
                    texttemplate="%{percent:.0%}",
                    textposition="inside",
                ))
                fig_pie.update_layout(
                    title="Recommendation Distribution",
                    height=380,
                    margin=dict(l=10, r=10, t=50, b=30),
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            st.dataframe(schema_df.rename(columns={
                "SCHEMA_NAME": "Schema",
                "SHORT_LIVED_COUNT": "Short-Lived",
                "PERMANENT_COUNT": "Permanent (Issue)",
                "TRANSIENT_COUNT": "Transient (OK)",
                "AVG_LIFESPAN_MINUTES": "Avg Lifespan (min)",
                "RECOMMENDATION": "Recommendation",
            }), use_container_width=True)
        else:
            st.info("No short-lived table schema data found in the last 30 days.")

        st.divider()
        st.subheader("Short-Lived Table Details (Last 30 Days, <24h Lifespan)")
        detail_df = _cached_query(session, "db_overview_9_detail_query",
                                  ALL_DB_OVERVIEW_QUERIES["db_overview_9_detail_query"])
        if len(detail_df) > 0:
            st.dataframe(detail_df.rename(columns={
                "FULL_TABLE_NAME": "Table",
                "TABLE_OWNER": "Owner",
                "TABLE_TYPE": "Type",
                "CREATED": "Created",
                "DELETED": "Deleted",
                "LIFESPAN_MINUTES": "Lifespan (min)",
                "SIZE_MB": "Size (MB)",
                "DAY_OF_WEEK": "Day",
            }), use_container_width=True)
        else:
            st.info("No short-lived tables found in the last 30 days.")

        st.divider()
        st.subheader("Users Creating Permanent Short-Lived Tables")
        pattern_df = _cached_query(session, "db_overview_10_pattern_query",
                                   ALL_DB_OVERVIEW_QUERIES["db_overview_10_pattern_query"])
        if len(pattern_df) > 0:
            st.dataframe(pattern_df.rename(columns={
                "OWNER": "Owner",
                "SHORT_LIVED_COUNT": "Short-Lived Count",
                "AVG_LIFESPAN": "Avg Lifespan (Min)",
                "PERMANENT_COUNT": "Permanent Tables",
            }), use_container_width=True)
        else:
            st.info("No pattern data available.")

    except Exception as e:
        _error_box("Low Lifespan Tables tab error", e)


def _render_high_churn_subtab():
    try:
        session = st.session_state.session
        summary_df = _cached_query(session, "db_overview_11_summary_query",
                                   ALL_DB_OVERVIEW_QUERIES["db_overview_11_summary_query"])
        if len(summary_df) == 0:
            _no_data_info()
            return

        row = summary_df.iloc[0]
        tables_with_churn = int(row.get("TABLES_WITH_CHURN", 0) or 0)
        high_churn = int(row.get("HIGH_CHURN_TABLES", 0) or 0)
        total_churn_tb = row.get("TOTAL_CHURN_TB", 0) or 0
        avg_ratio = row.get("AVG_CHURN_RATIO", 0) or 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tables with Churn", f"{tables_with_churn:,}")
        c2.metric("High Churn (>1x)", f"{high_churn:,}")
        c3.metric("Total Churn Storage", f"{total_churn_tb:.4f} TB")
        c4.metric("Avg Churn Ratio", f"{avg_ratio:.2f}x")

        st.divider()
        st.subheader("Churn by Database")
        db_churn_df = _cached_query(session, "db_overview_13_db_churn_query",
                                    ALL_DB_OVERVIEW_QUERIES["db_overview_13_db_churn_query"])
        if len(db_churn_df) > 0:
            chart_df = db_churn_df.head(10).sort_values("TOTAL_CHURN_TB", ascending=True)
            _plotly_hbar(chart_df, "TOTAL_CHURN_TB", "DATABASE_NAME", color=ALERT,
                         title="Top 10 Databases by Churn (TB)", x_title="Churn (TB)")
            st.dataframe(db_churn_df.rename(columns={
                "DATABASE_NAME": "Database",
                "TABLE_COUNT": "Tables",
                "TOTAL_CHURN_TB": "Churn (TB)",
                "AVG_CHURN_RATIO": "Avg Ratio",
            }), use_container_width=True)

        st.divider()
        st.subheader("High Churn Table Details")
        detail_df = _cached_query(session, "db_overview_12_detail_query",
                                  ALL_DB_OVERVIEW_QUERIES["db_overview_12_detail_query"])
        if len(detail_df) > 0:
            st.dataframe(detail_df.rename(columns={
                "TABLE_NAME": "Table",
                "TABLE_TYPE": "Type",
                "ROW_COUNT": "Rows",
                "ACTIVE_DATA_GB": "Active (GB)",
                "TIME_TRAVEL_GB": "Time Travel (GB)",
                "FAILSAFE_GB": "Failsafe (GB)",
                "TOTAL_CHURN_GB": "Churn (GB)",
                "CHURN_RATIO": "Churn Ratio",
            }), use_container_width=True)
        else:
            st.info("No high churn tables found.")

        st.divider()
        st.subheader("Top 20 High-Churn Tables")
        churn_df = _cached_query(session, "db_overview_20_churn_query",
                                 ALL_DB_OVERVIEW_QUERIES["db_overview_20_churn_query"])
        if len(churn_df) > 0:
            chart_df = churn_df.head(10).sort_values("Churn History (GB)", ascending=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Active Data (GB)",
                x=chart_df["Active Data (GB)"].tolist(),
                y=chart_df["Table"].tolist(),
                orientation="h", marker_color=PRIMARY
            ))
            fig.add_trace(go.Bar(
                name="Churn History (GB)",
                x=chart_df["Churn History (GB)"].tolist(),
                y=chart_df["Table"].tolist(),
                orientation="h", marker_color=ALERT
            ))
            fig.update_layout(
                barmode="group",
                title="Top High-Churn Tables: Active vs Churn",
                height=max(300, len(chart_df) * 30),
                margin=dict(l=10, r=10, t=40, b=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        _error_box("High Churn Tables tab error", e)


def comp_db_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        if not _query_cache:
            status_ph.markdown(
                '<p style="color: #003D73; font-weight: 600;">Loading Database Overview data...</p>',
                unsafe_allow_html=True
            )
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_queries(
                st.session_state.session,
                ALL_DB_OVERVIEW_QUERIES,
                progress_bar=progress_bar_widget,
                status_text=status_ph
            )
            progress_ph.empty()
            status_ph.empty()

        sub_tabs = st.tabs([
            "Overview",
            "Database Storage",
            "Clustering",
            "Low Lifespan Tables",
            "High Churn Tables"
        ])

        with sub_tabs[0]:
            _render_overview_subtab()

        with sub_tabs[1]:
            _render_storage_subtab()

        with sub_tabs[2]:
            _render_clustering_subtab()

        with sub_tabs[3]:
            _render_low_lifespan_subtab()

        with sub_tabs[4]:
            _render_high_churn_subtab()

    except Exception as e:
        st.error(f"Error loading Database Overview: {e}")


def comp_db_storage(entry_actions=None):
    _render_storage_subtab()


def comp_db_clustering(entry_actions=None):
    _render_clustering_subtab()


def comp_db_low_lifespan(entry_actions=None):
    _render_low_lifespan_subtab()


def comp_db_high_churn(entry_actions=None):
    _render_high_churn_subtab()


def _render_potential_savings():
    st.markdown("### Potential Storage Savings Summary")
    st.markdown(
        "Estimated monthly savings from converting high-churn tables to TRANSIENT or reducing "
        "Time Travel retention. Based on **$23.00/TB/month** standard storage rate.",
        unsafe_allow_html=False)
    try:
        session = st.session_state.session
        df = _cached_query(session, "db_overview_25_savings_actions_query",
                           ALL_DB_OVERVIEW_QUERIES["db_overview_25_savings_actions_query"])
        if df.empty or len(df) == 0:
            st.info("No significant savings opportunities detected.")
            return
        for c in ["AFFECTED_TABLES", "POTENTIAL_SAVINGS_TB", "EST_MONTHLY_SAVINGS_USD"]:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        transient_row = df[df["OPTIMIZATION_ACTION"].str.contains("TRANSIENT", case=False, na=False)]
        tt_row = df[df["OPTIMIZATION_ACTION"].str.contains("TIME_TRAVEL", case=False, na=False)]

        transient_savings = transient_row["EST_MONTHLY_SAVINGS_USD"].values[0] if len(transient_row) else 0
        transient_tables = transient_row["AFFECTED_TABLES"].values[0] if len(transient_row) else 0
        tt_savings = tt_row["EST_MONTHLY_SAVINGS_USD"].values[0] if len(tt_row) else 0
        tt_tables = tt_row["AFFECTED_TABLES"].values[0] if len(tt_row) else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Convert high-churn tables to TRANSIENT", f"${int(transient_savings):,}/mo")
        c2.metric("Tables Affected", f"{int(transient_tables):,}")
        c3.metric("Reduce TIME_TRAVEL retention on high-...", f"${int(tt_savings):,}/mo")
        c4.metric("Tables Affected", f"{int(tt_tables):,}")

        col_chart, col_table = st.columns(2)
        with col_chart:
            fig = go.Figure(go.Bar(
                x=df["OPTIMIZATION_ACTION"].tolist(),
                y=df["EST_MONTHLY_SAVINGS_USD"].tolist(),
                marker_color=[PRIMARY, ALERT],
                text=[f"${int(v):,}" for v in df["EST_MONTHLY_SAVINGS_USD"].tolist()],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>$%{y:,.0f}/mo<extra></extra>",
            ))
            fig.update_layout(
                title="Estimated Monthly Savings (USD)",
                yaxis_title="USD / month",
                height=380,
                margin=dict(l=10, r=20, t=50, b=120),
                xaxis=dict(tickangle=-30),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        with col_table:
            st.dataframe(df.rename(columns={
                "OPTIMIZATION_ACTION": "Action",
                "AFFECTED_TABLES": "Tables",
                "POTENTIAL_SAVINGS_TB": "Savings (TB)",
                "EST_MONTHLY_SAVINGS_USD": "Est. Monthly Savings (USD)",
            })[["Action", "Tables", "Savings (TB)", "Est. Monthly Savings (USD)"]],
            use_container_width=True)
    except Exception as e:
        st.markdown(
            f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">'
            f'🛑&nbsp;&nbsp;Error: {str(e)}</div>',
            unsafe_allow_html=True)

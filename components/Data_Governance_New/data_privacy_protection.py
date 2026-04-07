"""
Data Privacy & Protection Component

Provides functionality for data privacy and protection analysis
including Row Access Policy (RAP) auditing with metrics, charts,
unprotected object detection, and SHARE-domain tag reference analytics
(Data Clean Room / provider usage).
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


def _get_cached(cache_key):
    return st.session_state.get(cache_key, pd.DataFrame())


def _rap_st_echarts(options, key, height="400px"):
    """Render ECharts with SVG renderer (reliable default paint in Streamlit-in-Snowflake).

    Args:
        options: ECharts option dict
        key: Unique Streamlit widget key
        height: Chart height CSS value
    """
    try:
        st_echarts(options=options, height=height, key=key, renderer="svg")
    except TypeError:
        st_echarts(options=options, height=height, key=key)


def _rap_plotly_chart(fig, key):
    """Display Plotly figure with settings that render reliably on first paint in SiS.

    Args:
        fig: plotly.graph_objects.Figure
        key: Unique Streamlit widget key
    """
    try:
        st.plotly_chart(fig, use_container_width=True, key=key, theme=None)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key)




# ---------------------------------------------------------------------------
# KPI Tiles
# ---------------------------------------------------------------------------

def _render_rap_kpi_tiles(total_policies, total_protected, policies_per_obj, objects_per_policy):
    """Render RAP audit KPI tiles matching Governance Health Score style.

    Args:
        total_policies: Count of distinct RAP policies
        total_protected: Count of distinct protected objects
        policies_per_obj: Ratio of policies to protected objects
        objects_per_policy: Ratio of protected objects to policies
    """
    st.markdown(f"""
    <div style="display: flex; gap: 16px; padding: 10px 0;">
        <div style="flex: 1; text-align: left; padding: 18px; background: linear-gradient(135deg, #f0f7fb 0%, #f0f7fb 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Total Policies</div>
            <div style="font-size: 36px; font-weight: 700; color: #29B5E8; line-height: 1;">{total_policies:,}</div>
        </div>
        <div style="flex: 1; text-align: left; padding: 18px; background: linear-gradient(135deg, #EAF8F0 0%, #EAF8F0 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Protected Objects</div>
            <div style="font-size: 36px; font-weight: 700; color: #27AE60; line-height: 1;">{total_protected:,}</div>
        </div>
        <div style="flex: 1; text-align: left; padding: 18px; background: linear-gradient(135deg, #fff3cd 0%, #fff3cd 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Policies / Object</div>
            <div style="font-size: 36px; font-weight: 700; color: #E8A229; line-height: 1;">{policies_per_obj}</div>
        </div>
        <div style="flex: 1; text-align: left; padding: 18px; background: linear-gradient(135deg, #f0f7fb 0%, #f0f7fb 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Objects / Policy</div>
            <div style="font-size: 36px; font-weight: 700; color: #0077B6; line-height: 1;">{objects_per_policy}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chart helpers (aligned with Database Overview "Object Count by Object Type")
# ---------------------------------------------------------------------------

def _rap_horizontal_bar_plotly(categories, values, y_axis_title, key):
    """Horizontal bar chart using Plotly (same pattern as db_overview object count).

    Args:
        categories: Y-axis category labels
        values: Bar lengths (counts)
        y_axis_title: Y-axis title (e.g. Database, Object Type)
        key: Unique key for _rap_plotly_chart
    """
    df_sorted = pd.DataFrame({"CAT": categories, "VAL": values}).sort_values(
        "VAL", ascending=True
    )

    fig_bar = go.Figure(
        data=[
            go.Bar(
                y=df_sorted["CAT"],
                x=df_sorted["VAL"],
                orientation="h",
                marker_color="#29B5E8",
                text=df_sorted["VAL"],
                textposition="outside",
                textfont=dict(size=10),
                hovertemplate="<b>%{y}</b><br>Count: %{x:,}<extra></extra>",
            )
        ]
    )
    label_lens = [len(str(c)) for c in categories]
    max_label_len = max(label_lens) if label_lens else 0
    left_margin = min(320, max(120, max_label_len * 5))

    fig_bar.update_layout(
        height=400,
        xaxis_title="Count",
        yaxis_title=y_axis_title,
        showlegend=False,
        margin=dict(t=20, b=50, l=left_margin, r=50),
    )
    _rap_plotly_chart(fig_bar, key)


def _rap_pie_echarts(data_items, series_name, key, variant="pie"):
    """Pie, donut, or rose chart using ECharts (db_overview object-count style).

    Args:
        data_items: List of dicts with 'value' and 'name' keys
        series_name: Series name for legend/tooltip
        key: Unique Streamlit widget key (passed to _rap_st_echarts)
        variant: 'pie', 'donut', or 'rose'
    """
    if not data_items:
        data_items = [{"value": 0, "name": "No Data"}]

    if variant == "pie":
        series_cfg = {
            "name": series_name,
            "type": "pie",
            "radius": ["0%", "50%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 5},
            "data": data_items,
        }
    elif variant == "donut":
        series_cfg = {
            "name": series_name,
            "type": "pie",
            "radius": ["25%", "50%"],
            "center": ["50%", "40%"],
            "itemStyle": {"borderRadius": 8},
            "data": data_items,
        }
    else:
        series_cfg = {
            "name": series_name,
            "type": "pie",
            "radius": [15, 90],
            "center": ["50%", "40%"],
            "roseType": "area",
            "itemStyle": {"borderRadius": 8},
            "data": data_items,
        }

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {"fontSize": 10},
            "type": "scroll",
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "toolbox": {
            "show": True,
            "feature": {
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [series_cfg],
    }
    _rap_st_echarts(option, key, height="400px")


def _rap_switchable_chart(
    title,
    categories,
    values,
    series_name,
    key_prefix,
    default_chart="Bar Chart",
    y_axis_title="Category",
):
    """Title with total, Change Chart Type, Plotly bar or ECharts pies (db_overview pattern).

    Args:
        title: Section title (without total; total is appended)
        categories: Category labels
        values: Counts per category
        series_name: Name for chart series
        key_prefix: Unique prefix for widget keys
        default_chart: Default chart type in the selectbox
        y_axis_title: Y-axis label for horizontal bar chart
    """
    total_sum = int(sum(values)) if values else 0
    st.markdown(f"#### {title}: {total_sum:,}")

    chart_options = [
        "Bar Chart",
        "Pie Chart",
        "Pie - Donut",
        "Pie - Rose Chart",
    ]
    default_idx = chart_options.index(default_chart) if default_chart in chart_options else 0

    chart_type = st.selectbox(
        "Change Chart Type",
        chart_options,
        index=default_idx,
        key=f"{key_prefix}_chart_type",
    )

    if chart_type == "Bar Chart":
        _rap_horizontal_bar_plotly(
            categories,
            values,
            y_axis_title,
            f"{key_prefix}_plotly_bar",
        )
    else:
        data_items = [
            {"value": int(v), "name": f"{c} ({int(v):,})"}
            for c, v in zip(categories, values)
            if v > 0
        ]
        variant_map = {
            "Pie Chart": "pie",
            "Pie - Donut": "donut",
            "Pie - Rose Chart": "rose",
        }
        variant = variant_map[chart_type]
        _rap_pie_echarts(
            data_items,
            series_name,
            f"{key_prefix}_echarts_{variant}",
            variant,
        )


# ---------------------------------------------------------------------------
# Schema-Level Heatmap (with optional horizontal bar view)
# ---------------------------------------------------------------------------

def _rap_schema_level_panel(schema_df):
    """Render schema-level heatmap or horizontal bar chart (db_overview-style).

    Args:
        schema_df: DataFrame with PROTECTED_DB, PROTECTED_SCHEMA, OBJ_COUNT columns
    """
    total_objects = int(schema_df["OBJ_COUNT"].sum())
    st.markdown(f"#### Schema-Level Heatmap: {total_objects:,}")

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Heatmap", "Bar Chart"],
        index=0,
        key="rap_schema_chart_type",
    )

    if chart_type == "Bar Chart":
        df_sorted = schema_df.sort_values("OBJ_COUNT", ascending=False)
        labels = (
            df_sorted["PROTECTED_DB"].astype(str) + " / " + df_sorted["PROTECTED_SCHEMA"].astype(str)
        ).tolist()
        vals = [int(v) for v in df_sorted["OBJ_COUNT"].tolist()]
        _rap_horizontal_bar_plotly(
            labels,
            vals,
            "Database / Schema",
            "rap_schema_plotly_bar",
        )
        return

    databases = sorted(schema_df['PROTECTED_DB'].unique().tolist())
    schemas = sorted(schema_df['PROTECTED_SCHEMA'].unique().tolist())

    heat_data = []
    for _, row in schema_df.iterrows():
        x_idx = databases.index(row['PROTECTED_DB'])
        y_idx = schemas.index(row['PROTECTED_SCHEMA'])
        heat_data.append([x_idx, y_idx, int(row['OBJ_COUNT'])])

    max_val = max(v[2] for v in heat_data) if heat_data else 1

    option = {
        "tooltip": {"position": "top"},
        "grid": {"left": "15%", "right": "10%", "bottom": "20%", "top": "3%"},
        "xAxis": {
            "type": "category", "data": databases,
            "splitArea": {"show": True},
            "axisLabel": {"fontSize": 10, "rotate": 30}
        },
        "yAxis": {
            "type": "category", "data": schemas,
            "splitArea": {"show": True},
            "axisLabel": {"fontSize": 10}
        },
        "visualMap": {
            "min": 0, "max": max_val, "calculable": True,
            "orient": "horizontal", "left": "center", "bottom": "0",
            "inRange": {"color": ["#CAF0F8", "#75C2D8", "#29B5E8", "#0077B6"]}
        },
        "series": [{
            "name": "Protected Objects",
            "type": "heatmap",
            "data": heat_data,
            "label": {"show": True},
            "emphasis": {
                "itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0, 0, 0, 0.5)"}
            }
        }],
    }
    _rap_st_echarts(option, "rap_schema_heatmap", height="400px")


# ---------------------------------------------------------------------------
# Data Clean Room / SHARE tag references (TAG_REFERENCES, DOMAIN = SHARE)
# ---------------------------------------------------------------------------

def _dcr_normalize_columns(df):
    """Uppercase DataFrame columns for consistent access after Snowflake fetch.

    Args:
        df: pandas DataFrame from session.sql().to_pandas()

    Returns:
        DataFrame with uppercase column names
    """
    df = df.copy()
    df.columns = [str(c).upper() for c in df.columns]
    return df


def _dcr_object_key(df):
    """Build composite object key column for SHARE rows.

    Args:
        df: TAG_REFERENCES subset with OBJECT_* columns

    Returns:
        Series of string keys db.schema.name
    """
    return (
        df["OBJECT_DATABASE"].astype(str)
        + "."
        + df["OBJECT_SCHEMA"].astype(str)
        + "."
        + df["OBJECT_NAME"].astype(str)
    )


def _dcr_apply_method_bucket(method):
    """Map Snowflake APPLY_METHOD to Manual / Inherited / Automated / Unknown.

    Args:
        method: Raw APPLY_METHOD value

    Returns:
        str bucket label
    """
    if method is None or (isinstance(method, float) and pd.isna(method)):
        return "Unknown"
    u = str(method).strip().upper()
    if u in ("", "NONE", "NULL"):
        return "Unknown"
    if u == "MANUAL":
        return "Manual"
    if u in ("INHERITED", "PROPAGATED"):
        return "Inherited"
    if u == "CLASSIFIED":
        return "Automated"
    return "Other"


def _dcr_tag_value_nonempty(series):
    """True where TAG_VALUE is present and not an empty placeholder.

    Args:
        series: TAG_VALUE column

    Returns:
        Boolean Series
    """
    as_str = series.astype(str).str.strip()
    bad = as_str.str.upper().isin(["", "NONE", "NULL", "NAN"])
    return series.notna() & ~bad


def _dcr_classification_label(name_val_text):
    """Derive coarse classification label from concatenated tag name/value text.

    Args:
        name_val_text: Uppercase concatenated TAG_NAME and TAG_VALUE strings

    Returns:
        One of PII, Confidential, Public, Missing / Other
    """
    t = name_val_text or ""
    if "PII" in t:
        return "PII"
    if "CONFIDENTIAL" in t or " CONF " in t:
        return "Confidential"
    if "PUBLIC" in t:
        return "Public"
    return "Missing / Other"


def _render_dcr_kpi_tiles(
    distinct_objects,
    tag_coverage_pct,
    automation_rate_pct,
    avg_tags_per_object,
    distinct_tag_names,
    consistency_score,
):
    """KPI tiles for SHARE tag analytics (Governance Health Score style).

    Args:
        distinct_objects: Count of distinct SHARE objects with tag rows
        tag_coverage_pct: Share of tag rows with non-empty TAG_VALUE
        automation_rate_pct: Share of rows classified as Automated or Inherited
        avg_tags_per_object: Mean tag rows per distinct object
        distinct_tag_names: Count of distinct TAG_NAME values
        consistency_score: 0–100 score from dispersion of tags per object
    """
    cov_color = "#0077B6" if tag_coverage_pct >= 70 else "#E8A229" if tag_coverage_pct >= 40 else "#E74C3C"
    st.markdown(f"""
    <div style="display: flex; flex-wrap: wrap; gap: 16px; padding: 10px 0;">
        <div style="flex: 1 1 160px; min-width: 150px; text-align: left; padding: 18px; background: linear-gradient(135deg, #f0f7fb 0%, #f0f7fb 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Tagged SHARE objects</div>
            <div style="font-size: 32px; font-weight: 700; color: #29B5E8; line-height: 1;">{distinct_objects:,}</div>
        </div>
        <div style="flex: 1 1 160px; min-width: 150px; text-align: left; padding: 18px; background: linear-gradient(135deg, #EAF8F0 0%, #EAF8F0 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Tag coverage %</div>
            <div style="font-size: 32px; font-weight: 700; color: {cov_color}; line-height: 1;">{tag_coverage_pct:.1f}%</div>
        </div>
        <div style="flex: 1 1 160px; min-width: 150px; text-align: left; padding: 18px; background: linear-gradient(135deg, #fff3cd 0%, #fff3cd 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Automation rate %</div>
            <div style="font-size: 32px; font-weight: 700; color: #E8A229; line-height: 1;">{automation_rate_pct:.1f}%</div>
        </div>
        <div style="flex: 1 1 160px; min-width: 150px; text-align: left; padding: 18px; background: linear-gradient(135deg, #f0f7fb 0%, #f0f7fb 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Avg tags / object</div>
            <div style="font-size: 32px; font-weight: 700; color: #0077B6; line-height: 1;">{avg_tags_per_object:.2f}</div>
        </div>
        <div style="flex: 1 1 160px; min-width: 150px; text-align: left; padding: 18px; background: linear-gradient(135deg, #f0f7fb 0%, #f0f7fb 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Distinct tag names</div>
            <div style="font-size: 32px; font-weight: 700; color: #00B4D8; line-height: 1;">{distinct_tag_names:,}</div>
        </div>
        <div style="flex: 1 1 160px; min-width: 150px; text-align: left; padding: 18px; background: linear-gradient(135deg, #FDEDEC 0%, #FDEDEC 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Tag consistency score</div>
            <div style="font-size: 32px; font-weight: 700; color: #75C2D8; line-height: 1;">{consistency_score:.0f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_data_clean_room_provider_content():
    """SHARE-domain tag metrics and charts for Data Clean Room / provider usage.

    Loads TAG_REFERENCES (DOMAIN = 'SHARE'), computes KPIs, and renders six
    chart panels in a two-column layout.

    Args:
    """
    key_suffix = "dcr"

    try:
        raw_df = _get_cached("dg_share_tag")
        df = _dcr_normalize_columns(raw_df)

        if len(df) == 0:
            _render_dcr_kpi_tiles(0, 0.0, 0.0, 0.0, 0, 0.0)
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No SHARE-domain tag references for this account and execution.'
                        '</div>', unsafe_allow_html=True)
            return

        df["_OBJ_KEY"] = _dcr_object_key(df)
        n_rows = len(df)
        distinct_objects = int(df["_OBJ_KEY"].nunique())
        nonempty_val = _dcr_tag_value_nonempty(df["TAG_VALUE"])
        tag_coverage_pct = float(nonempty_val.mean() * 100) if n_rows else 0.0

        buckets = df["APPLY_METHOD"].map(_dcr_apply_method_bucket)
        auto_like = buckets.isin(["Automated", "Inherited"])
        denom_auto = int((buckets != "Unknown").sum())
        automation_rate_pct = float(auto_like.sum() / denom_auto * 100) if denom_auto else 0.0

        avg_tags_per_object = float(n_rows / distinct_objects) if distinct_objects else 0.0
        distinct_tag_names = int(df["TAG_NAME"].nunique())

        tags_per_obj = df.groupby("_OBJ_KEY", as_index=False).size()
        tmean = float(tags_per_obj["size"].mean()) if len(tags_per_obj) else 0.0
        tstd = float(tags_per_obj["size"].std(ddof=0)) if len(tags_per_obj) else 0.0
        cv = (tstd / tmean) if tmean > 0 else 0.0
        consistency_score = max(0.0, min(100.0, 100.0 * (1.0 - min(cv, 1.0))))

        _render_dcr_kpi_tiles(
            distinct_objects,
            tag_coverage_pct,
            automation_rate_pct,
            avg_tags_per_object,
            distinct_tag_names,
            consistency_score,
        )
        st.markdown("")

        # --- Charts 2–7: two columns per row ---
        # 2. Tag usage
        row1a, row1b = st.columns(2)
        with row1a.container():
            name_counts = (
                df.groupby("TAG_NAME", dropna=False)
                .size()
                .reset_index(name="CNT")
                .sort_values("CNT", ascending=False)
            )
            top_n = name_counts.head(25)
            _rap_switchable_chart(
                f"Tag usage (distinct tags: {distinct_tag_names})",
                top_n["TAG_NAME"].fillna("(null)").astype(str).tolist(),
                [int(v) for v in top_n["CNT"].tolist()],
                "Assignments",
                f"dcr_tag_usage_{key_suffix}",
                default_chart="Bar Chart",
                y_axis_title="TAG_NAME",
            )
            val_per_name = (
                df.groupby("TAG_NAME", dropna=False)["TAG_VALUE"]
                .nunique()
                .reset_index(name="DISTINCT_VALUES")
                .sort_values("DISTINCT_VALUES", ascending=False)
                .head(25)
            )
            _rap_switchable_chart(
                "Distinct TAG_VALUE count per TAG_NAME (top 25)",
                val_per_name["TAG_NAME"].fillna("(null)").astype(str).tolist(),
                [int(v) for v in val_per_name["DISTINCT_VALUES"].tolist()],
                "Distinct values",
                f"dcr_val_per_tag_{key_suffix}",
                default_chart="Bar Chart",
                y_axis_title="TAG_NAME",
            )

        with row1b.container():
            st.markdown("##### Tag value distribution")
            tag_names_sorted = sorted(
                df["TAG_NAME"].dropna().astype(str).unique().tolist()
            )
            if not tag_names_sorted:
                st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No TAG_NAME values to analyze.'
                            '</div>', unsafe_allow_html=True)
            else:
                sel_tag = st.selectbox(
                    "TAG_NAME",
                    tag_names_sorted,
                    key=f"dcr_tv_sel_{key_suffix}",
                )
                sub = df[df["TAG_NAME"].astype(str) == sel_tag]
                n_sub = len(sub)
                empty_sub = int((~_dcr_tag_value_nonempty(sub["TAG_VALUE"])).sum())
                pct_empty = (empty_sub / n_sub * 100) if n_sub else 0.0
                card_vals = sub["TAG_VALUE"].fillna("(null)").astype(str).str.strip()
                card_vals = card_vals.replace({"": "(empty)"})
                nunique_vals = int(card_vals.nunique())
                st.caption(
                    f"Null / empty / placeholder values: {pct_empty:.1f}%  ·  "
                    f"Cardinality (distinct values): {nunique_vals}"
                    + ("  ·  High cardinality" if nunique_vals > 15 else "  ·  Low cardinality")
                )
                vc = (
                    card_vals.value_counts()
                    .rename_axis("TAG_VALUE")
                    .reset_index(name="CNT")
                    .head(25)
                )
                _rap_switchable_chart(
                    f"TAG_VALUE distribution — {sel_tag}",
                    vc["TAG_VALUE"].astype(str).tolist(),
                    [int(v) for v in vc["CNT"].tolist()],
                    "Rows",
                    f"dcr_tv_dist_{key_suffix}",
                    default_chart="Bar Chart",
                    y_axis_title="TAG_VALUE",
                )

        row2a, row2b = st.columns(2)
        with row2a.container():
            dim = st.selectbox(
                "Aggregate tags by",
                ["OBJECT_DATABASE", "OBJECT_SCHEMA", "OBJECT_NAME (full)"],
                key=f"dcr_obj_dim_{key_suffix}",
            )
            if dim == "OBJECT_NAME (full)":
                grp = df.groupby("_OBJ_KEY", as_index=False).size()
                grp = grp.rename(columns={"_OBJ_KEY": "LABEL", "size": "CNT"})
            else:
                col = dim.replace(" (full)", "")
                grp = df.groupby(col, dropna=False).size().reset_index(name="CNT")
                grp = grp.rename(columns={col: "LABEL"})
            grp = grp.sort_values("CNT", ascending=False).head(25)
            top_obj = (
                df.groupby("_OBJ_KEY", as_index=False)
                .size()
                .nlargest(25, "size")
            )
            st.markdown("##### Object-level tag counts")
            _rap_switchable_chart(
                f"Top 25 by {dim}",
                grp["LABEL"].fillna("(null)").astype(str).tolist(),
                [int(v) for v in grp["CNT"].tolist()],
                "Tag rows",
                f"dcr_obj_agg_{key_suffix}",
                default_chart="Bar Chart",
                y_axis_title=dim,
            )
            _rap_switchable_chart(
                "Top 25 tagged SHARE objects (by tag row count)",
                top_obj["_OBJ_KEY"].astype(str).tolist(),
                [int(v) for v in top_obj["size"].tolist()],
                "Tag rows",
                f"dcr_top_obj_{key_suffix}",
                default_chart="Bar Chart",
                y_axis_title="Object",
            )
            low_tag = tags_per_obj[tags_per_obj["size"] <= 1].sort_values("size")
            st.caption(
                f"Under-tagged objects (≤1 tag row): {len(low_tag):,} of {distinct_objects:,} distinct objects"
            )

        with row2b.container():
            apply_grp = buckets.value_counts(dropna=False).reset_index()
            apply_grp.columns = ["BUCKET", "CNT"]
            order = ["Manual", "Inherited", "Automated", "Other", "Unknown"]
            apply_grp["_ord"] = apply_grp["BUCKET"].map({b: i for i, b in enumerate(order)})
            apply_grp = apply_grp.sort_values("_ord", na_position="last")
            _rap_switchable_chart(
                "Apply method (Manual / Inherited / Automated)",
                apply_grp["BUCKET"].tolist(),
                [int(v) for v in apply_grp["CNT"].tolist()],
                "Tag rows",
                f"dcr_apply_{key_suffix}",
                default_chart="Bar Chart",
                y_axis_title="Apply method",
            )

        row3a, row3b = st.columns(2)
        with row3a.container():
            st.markdown("##### Account-level governance")
            st.caption(
                "Single execution snapshot — cross-account and time-trend views need "
                "additional execution history in the app."
            )
            density = tags_per_obj["size"].value_counts().sort_index()
            cats = [str(int(i)) for i in density.index.tolist()]
            vals = [int(v) for v in density.tolist()]
            _rap_switchable_chart(
                "Tag density — SHARE objects by number of tag rows",
                cats,
                vals,
                "Objects",
                f"dcr_density_{key_suffix}",
                default_chart="Bar Chart",
                y_axis_title="Tags per object",
            )

        with row3b.container():
            cls_rows = []
            for obj_key, g in df.groupby("_OBJ_KEY", sort=False):
                parts = (
                    g["TAG_NAME"].fillna("").astype(str)
                    + " "
                    + g["TAG_VALUE"].fillna("").astype(str)
                ).str.upper()
                blob = " ".join(parts.tolist())
                cls_rows.append({"_OBJ_KEY": obj_key, "LABEL": _dcr_classification_label(blob)})
            cls_df = pd.DataFrame(cls_rows)
            cls_counts = cls_df.groupby("LABEL", as_index=False).size()
            cls_counts = cls_counts.rename(columns={"size": "CNT"})
            cls_counts = cls_counts.sort_values("CNT", ascending=False)
            missing_n = int((cls_df["LABEL"] == "Missing / Other").sum())
            total_o = len(cls_df)
            if total_o > 0:
                pct_parts = [
                    f"{r['LABEL']}: {100.0 * r['CNT'] / total_o:.1f}%"
                    for _, r in cls_counts.iterrows()
                ]
                st.caption("Share of distinct SHARE objects — " + " · ".join(pct_parts))
            _rap_switchable_chart(
                f"Classification-style grouping (heuristic) — missing/other: {missing_n:,} / {total_o:,} objects",
                cls_counts["LABEL"].tolist(),
                [int(v) for v in cls_counts["CNT"].tolist()],
                "Objects",
                f"dcr_class_{key_suffix}",
                default_chart="Bar Chart",
                y_axis_title="Category",
            )

    except Exception as e:
        st.markdown(
            f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
            f"🛑&nbsp;&nbsp;Error loading SHARE tag analytics: {str(e)}"
            f"</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# RAP Audit Content Renderer
# ---------------------------------------------------------------------------

def _render_rap_audit_content():
    """Render Row Access Policy audit with KPIs, charts, and unprotected objects.

    Layout:
        - Full-width KPI tiles (4 metrics)
        - Row 1: Policies by Database | Object Type Distribution
        - Row 2: Top 10 Policies by Usage | Schema-Level Heatmap
        - Row 3: Top 10 Tables by Usage | Unprotected Objects

    Args:
    """
    try:
        rap_df = _get_cached("dg_rap")
        unprotected_df = _get_cached("dg_unprotected")

        # --- 1. KPI Metrics ---
        if len(rap_df) == 0:
            _render_rap_kpi_tiles(0, 0, 0, 0)
            st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No active Row Access Policies found for this account.'
                        '</div>', unsafe_allow_html=True)
            return

        total_policies = int(rap_df['POLICY_NAME'].nunique())
        protected_objects = rap_df.drop_duplicates(
            subset=['PROTECTED_DB', 'PROTECTED_SCHEMA', 'PROTECTED_TABLE']
        )
        total_protected = len(protected_objects)
        policies_per_obj = round(total_policies / total_protected, 2) if total_protected > 0 else 0
        objects_per_policy = round(total_protected / total_policies, 2) if total_policies > 0 else 0

        _render_rap_kpi_tiles(total_policies, total_protected, policies_per_obj, objects_per_policy)
        st.markdown("")

        # --- 2. Policies by Database  |  3. Object Type Distribution ---
        col1, col2 = st.columns(2)

        with col1.container():
            db_counts = (
                rap_df.groupby('POLICY_DB')['POLICY_NAME']
                .nunique()
                .reset_index(name='POLICY_COUNT')
                .sort_values('POLICY_COUNT', ascending=False)
            )
            _rap_switchable_chart(
                "Policies by Database",
                db_counts['POLICY_DB'].tolist(),
                [int(v) for v in db_counts['POLICY_COUNT'].tolist()],
                "Policies",
                "rap_by_db",
                default_chart="Bar Chart",
                y_axis_title="Database",
            )

        with col2.container():
            type_counts = (
                rap_df.groupby('OBJECT_TYPE')
                .size()
                .reset_index(name='COUNT')
                .sort_values('COUNT', ascending=False)
            )
            _rap_switchable_chart(
                "Object Type Distribution",
                type_counts['OBJECT_TYPE'].tolist(),
                [int(v) for v in type_counts['COUNT'].tolist()],
                "Objects",
                "rap_obj_type",
                default_chart="Bar Chart",
                y_axis_title="Object Type",
            )

        # --- 4. Top 10 Policies by Usage  |  5. Schema-Level Heatmap ---
        col3, col4 = st.columns(2)

        with col3.container():
            policy_usage = (
                rap_df.groupby('POLICY_NAME')
                .size()
                .reset_index(name='USAGE_COUNT')
                .nlargest(10, 'USAGE_COUNT')
            )
            _rap_switchable_chart(
                "Top 10 Policies by Usage",
                policy_usage['POLICY_NAME'].tolist(),
                [int(v) for v in policy_usage['USAGE_COUNT'].tolist()],
                "Usage",
                "rap_top_policies",
                default_chart="Bar Chart",
                y_axis_title="Policy",
            )

        with col4.container():
            schema_counts = (
                rap_df.groupby(['PROTECTED_DB', 'PROTECTED_SCHEMA'])
                .size()
                .reset_index(name='OBJ_COUNT')
            )
            if len(schema_counts) > 0:
                _rap_schema_level_panel(schema_counts)
            else:
                st.markdown("#### Schema-Level Heatmap: 0")
                st.markdown('<div style="background-color: #f0f7fb; border-left: 6px solid #29B5E8; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No schema-level data available for heatmap.'
                            '</div>', unsafe_allow_html=True)

        # --- 6. Top 10 Tables by Usage  |  7. Unprotected Objects ---
        col5, col6 = st.columns(2)

        with col5.container():
            table_usage = rap_df.copy()
            table_usage['FULL_TABLE'] = (
                table_usage['PROTECTED_DB'] + '.' +
                table_usage['PROTECTED_SCHEMA'] + '.' +
                table_usage['PROTECTED_TABLE']
            )
            table_counts = (
                table_usage.groupby('FULL_TABLE')
                .size()
                .reset_index(name='POLICY_COUNT')
                .nlargest(10, 'POLICY_COUNT')
            )
            _rap_switchable_chart(
                "Top 10 Tables by Usage",
                table_counts['FULL_TABLE'].tolist(),
                [int(v) for v in table_counts['POLICY_COUNT'].tolist()],
                "Policies",
                "rap_top_tables",
                default_chart="Bar Chart",
                y_axis_title="Table",
            )

        with col6.container():
            unprotected_count = len(unprotected_df)
            if unprotected_count == 0:
                st.markdown("#### Unprotected Objects: 0")
                st.markdown('<div style="background-color: #EAF8F0; border-left: 6px solid #27AE60; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            '✅&nbsp;&nbsp;All tables have Row Access Policy protection.'
                            '</div>', unsafe_allow_html=True)
            else:
                up_by_db = (
                    unprotected_df.groupby("DATABASE_NAME")
                    .size()
                    .reset_index(name="COUNT")
                    .sort_values("COUNT", ascending=False)
                )
                _rap_switchable_chart(
                    "Unprotected Objects",
                    up_by_db["DATABASE_NAME"].tolist(),
                    [int(v) for v in up_by_db["COUNT"].tolist()],
                    "Tables",
                    "rap_unprotected",
                    default_chart="Bar Chart",
                    y_axis_title="Database",
                )
                display_df = unprotected_df.copy()
                display_df.columns = ["Database", "Schema", "Table"]
                st.dataframe(display_df, use_container_width=True, height=220)

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading RAP audit: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main Component Entry Point
# ---------------------------------------------------------------------------

def comp_data_privacy_protection(entry_actions=None):
    """
    Data Privacy & Protection Component

    Provides expanders for:
    - Masking Policy Coverage
    - Row Access Policy (RAP) Audit
    - Data Clean Room / Provider Usage

    Args:
        entry_actions: Optional callback actions on component entry
    """
    try:
        st.markdown("### Data Privacy & Protection")

        with st.expander("Masking Policy Coverage", expanded=True):
            st.markdown("#### Masking Policy Coverage")
            _render_masking_policy_coverage()

        with st.expander("Row Access Policy (RAP) Audit", expanded=True):
            st.markdown("#### Row Access Policy (RAP) Audit")
            _render_rap_audit_content()

        with st.expander("Data Clean Room / Provider Usage", expanded=True):
            st.markdown("#### Data Clean Room / Provider Usage")
            st.caption(
                "Metrics and charts from TAG_REFERENCES where DOMAIN = 'SHARE' "
                "(tag assignments on share objects for clean-room / provider governance)."
            )
            _render_data_clean_room_provider_content()

        with st.expander("Dangling Policies (Policies on Dropped Objects)", expanded=True):
            _render_dangling_policies()

        with st.expander("Masking Policy Design Patterns", expanded=True):
            _render_masking_design_patterns()

        with st.expander("Downstream Untagged/Unmasked Columns", expanded=True):
            _render_downstream_untagged()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Data Privacy & Protection: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_masking_policy_coverage():
    import plotly.graph_objects as go
    import pandas as pd
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Masking Policy Coverage:</b> Columns identified as sensitive (by tag) or '
        'already protected by an active masking policy. Unprotected sensitive columns represent '
        'governance gaps where masking policies should be added.</div>', unsafe_allow_html=True)
    try:
        df = _get_cached("dg_masking_coverage")
        if df.empty:
            st.info("No sensitive or masked columns found. Apply PII/PHI tags or masking policies to see coverage analysis.")
            return
        status_counts = df['PROTECTION_STATUS'].value_counts().reset_index()
        status_counts.columns = ['status', 'count']
        col1, col2, col3 = st.columns(3)
        protected = len(df[df['PROTECTION_STATUS'].str.startswith('Protected')])
        unprotected = len(df[df['PROTECTION_STATUS'].str.startswith('UNPROTECTED')])
        masked_only = len(df[df['PROTECTION_STATUS'].str.startswith('Masked')])
        with col1:
            st.metric("Total Sensitive Columns", len(df))
        with col2:
            st.metric("Unprotected (Gap)", unprotected)
        with col3:
            coverage_pct = (protected / len(df) * 100) if len(df) > 0 else 0
            st.metric("Coverage %", f"{coverage_pct:.1f}%")
        _status_colors = {
            'Protected (Tag + Mask)': '#29B5E8',
            'Masked (No Sensitive Tag)': '#75C2D8',
            'UNPROTECTED - Sensitive but No Mask': '#F39C12'
        }
        fig = go.Figure(go.Pie(
            labels=status_counts['status'],
            values=status_counts['count'],
            hole=0.3,
            marker_colors=[_status_colors.get(s, '#E8A229') for s in status_counts['status']]
        ))
        fig.update_layout(title='Masking Policy Coverage Status', height=340, margin=dict(t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
        unprotected_df = df[df['PROTECTION_STATUS'].str.startswith('UNPROTECTED')]
        if not unprotected_df.empty:
            st.markdown("**Unprotected Sensitive Columns (Governance Gaps)**")
            st.dataframe(unprotected_df[['DATABASE_NAME', 'SCHEMA_NAME', 'TABLE_NAME', 'COLUMN_NAME', 'PROTECTION_STATUS']])
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_dangling_policies():
    import plotly.graph_objects as go
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Dangling Policies:</b> Active policy references where the protected object or '
        'the policy database no longer exists in ACCOUNT_USAGE.TABLES.</div>',
        unsafe_allow_html=True)
    try:
        df = _get_cached("dg_dangling_policies")
        if df.empty:
            st.success("No dangling policies detected — all policies reference active objects.")
            return
        st.metric("Potentially Dangling Policy References", len(df))
        kind_counts = df.groupby('POLICY_KIND').size().reset_index(name='COUNT').sort_values('COUNT', ascending=False)
        colors = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229']
        fig = go.Figure(go.Bar(
            x=kind_counts['POLICY_KIND'], y=kind_counts['COUNT'],
            marker_color=colors[:len(kind_counts)],
            text=kind_counts['COUNT'], textposition='outside'
        ))
        fig.update_layout(title='Dangling Policies by Type', yaxis_title='Count', height=340, margin=dict(t=50, b=60))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_masking_design_patterns():
    import plotly.graph_objects as go
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Masking Policy Design:</b> Distribution of masking policies by the number of '
        'tables/columns they protect. Policies protecting many objects may indicate good reuse; policies '
        'protecting only 1 object may be overly specific.</div>',
        unsafe_allow_html=True)
    try:
        df = _get_cached("dg_masking_design")
        if df.empty:
            st.info("No masking policies found.")
            return
        for c in ['TABLES_PROTECTED', 'COLUMNS_PROTECTED', 'TOTAL_REFERENCES']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Masking Policies", len(df))
        with col2:
            single_use = len(df[df['TABLES_PROTECTED'] <= 1])
            st.metric("Single-Table Policies", single_use)
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Tables Protected', x=df['POLICY_NAME'], y=df['TABLES_PROTECTED'], marker_color='#29B5E8'))
        fig.add_trace(go.Bar(name='Columns Protected', x=df['POLICY_NAME'], y=df['COLUMNS_PROTECTED'], marker_color='#11567F'))
        fig.update_layout(
            barmode='group', title='Masking Policy Reuse Patterns',
            yaxis_title='Count', height=380, margin=dict(t=50, b=100),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)


def _render_downstream_untagged():
    import plotly.graph_objects as go
    st.markdown(
        '<div style="background-color:#f0f7fb;border-left:6px solid #29B5E8;padding:10px;">'
        'ℹ️&nbsp;&nbsp;<b>Downstream Untagged/Unmasked:</b> Columns tagged as PII or sensitive that lack '
        'a masking policy. These represent data protection gaps.</div>',
        unsafe_allow_html=True)
    try:
        df = _get_cached("dg_downstream_unmasked")
        if df.empty:
            st.success("All sensitive/PII-tagged columns have masking policies applied.")
            return
        st.metric("Unmasked Sensitive Columns", len(df))
        db_counts = df.groupby('DATABASE_NAME').size().reset_index(name='COUNT').sort_values('COUNT', ascending=False)
        colors = ['#29B5E8', '#11567F', '#75C2D8', '#E8A229', '#1A7DA8', '#023E8A']
        fig = go.Figure(go.Bar(
            x=db_counts['DATABASE_NAME'], y=db_counts['COUNT'],
            marker_color=colors[:len(db_counts)],
            text=db_counts['COUNT'], textposition='outside'
        ))
        fig.update_layout(
            title='Unmasked Sensitive Columns by Database',
            yaxis_title='Count', height=360, margin=dict(t=50, b=80)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(
            '<div style="background-color:#fff3cd;border-left:6px solid #F39C12;padding:10px;">'
            '⚠️&nbsp;&nbsp;These columns are tagged as sensitive/PII but lack masking policies. '
            'Consider applying tag-based masking for automated protection.</div>',
            unsafe_allow_html=True)
        st.dataframe(df)
    except Exception as e:
        st.markdown(f'<div style="background-color:#FDEDEC;border-left:6px solid #E74C3C;padding:10px;">🛑&nbsp;&nbsp;Error: {str(e)}</div>', unsafe_allow_html=True)

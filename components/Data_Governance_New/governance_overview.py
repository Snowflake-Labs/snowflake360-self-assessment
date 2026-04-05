"""
Data Governance Overview Component

Provides a high-level overview of data governance status with sub-tabs
for Overview, Object Tagging & Classification, Data Privacy & Protection,
and Data Lineage & Quality.
"""

import streamlit as st
import pandas as pd
try:
    from streamlit_echarts import st_echarts
except ImportError:
    def st_echarts(**kwargs):
        import streamlit as st
        st.info("Chart unavailable (echarts not supported in SiS)")
from .object_tagging_classification import comp_object_tagging_classification
from .data_privacy_protection import comp_data_privacy_protection
from .lineage_quality import comp_lineage_quality




def _render_tag_coverage_bar_chart(tag_df):
    """Render tag coverage by apply method as a horizontal stacked bar chart using ECharts."""
    df_sorted = tag_df.sort_values('TOTAL_TAGS', ascending=True)

    apply_methods = df_sorted['APPLY_METHOD'].tolist()
    total_tags = [int(v) for v in df_sorted['TOTAL_TAGS'].tolist()]
    objects_covered = [int(v) for v in df_sorted['OBJECTS_COVERED'].tolist()]

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 15,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "top": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "name": "Count",
            "nameLocation": "middle",
            "nameGap": 25
        },
        "yAxis": {
            "type": "category",
            "data": apply_methods,
            "axisLabel": {"fontSize": 10}
        },
        "color": ["#1f77b4", "#ff7f0e"],
        "series": [
            {
                "name": "Total Tags",
                "type": "bar",
                "stack": "total",
                "data": total_tags
            },
            {
                "name": "Objects Covered",
                "type": "bar",
                "stack": "total",
                "data": objects_covered
            }
        ]
    }

    st_echarts(options=option, height="400px", key="tag_coverage_bar_chart")


def _render_tag_coverage_pie_chart(tag_df):
    """Render tag coverage standard pie chart using ECharts."""
    chart_data = [
        {"value": int(row['TOTAL_TAGS']), "name": f"{row['APPLY_METHOD']} ({int(row['TOTAL_TAGS'])})"}
        for _, row in tag_df.iterrows() if int(row['TOTAL_TAGS']) > 0
    ]

    if not chart_data:
        chart_data = [{"value": 0, "name": "No Tags"}]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
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
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Tag Count",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="400px", key="tag_coverage_pie_chart")


def _render_tag_coverage_donut_chart(tag_df):
    """Render tag coverage donut pie chart using ECharts."""
    chart_data = [
        {"value": int(row['TOTAL_TAGS']), "name": f"{row['APPLY_METHOD']} ({int(row['TOTAL_TAGS'])})"}
        for _, row in tag_df.iterrows() if int(row['TOTAL_TAGS']) > 0
    ]

    if not chart_data:
        chart_data = [{"value": 0, "name": "No Tags"}]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
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
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Tag Count",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="400px", key="tag_coverage_donut_chart")


def _render_tag_coverage_rose_chart(tag_df):
    """Render tag coverage rose-type pie chart using ECharts."""
    chart_data = [
        {"value": int(row['TOTAL_TAGS']), "name": f"{row['APPLY_METHOD']} ({int(row['TOTAL_TAGS'])})"}
        for _, row in tag_df.iterrows() if int(row['TOTAL_TAGS']) > 0
    ]

    if not chart_data:
        chart_data = [{"value": 0, "name": "No Tags"}]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
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
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Tag Count",
                "type": "pie",
                "radius": ["15%", "55%"],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="400px", key="tag_coverage_rose_chart")


def _render_governance_kpi_tiles(total_tables, tagged_tables):
    """KPI tiles showing governance metrics using accurate counts."""
    untagged_tables = total_tables - tagged_tables
    coverage_pct = round(tagged_tables / total_tables * 100, 2) if total_tables > 0 else 0.0

    pct_color = "#2ca02c" if coverage_pct >= 70 else "#ff7f0e" if coverage_pct >= 40 else "#d62728"

    st.markdown(f"""
    <div style="display: flex; gap: 16px; padding: 10px 0;">
        <div style="flex: 1; text-align: left; padding: 18px; background: linear-gradient(135deg, #f0f4ff 0%, #e8eeff 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Total Tables</div>
            <div style="font-size: 36px; font-weight: 700; color: #1f77b4; line-height: 1;">{total_tables:,}</div>
        </div>
        <div style="flex: 1; text-align: left; padding: 18px; background: linear-gradient(135deg, #f0fff0 0%, #e0ffe0 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Tagged Tables</div>
            <div style="font-size: 36px; font-weight: 700; color: #2ca02c; line-height: 1;">{tagged_tables:,}</div>
        </div>
        <div style="flex: 1; text-align: left; padding: 18px; background: linear-gradient(135deg, #fff0f0 0%, #ffe0e0 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Untagged Tables</div>
            <div style="font-size: 36px; font-weight: 700; color: #d62728; line-height: 1;">{untagged_tables:,}</div>
        </div>
        <div style="flex: 1; text-align: left; padding: 18px; background: linear-gradient(135deg, #fff4e6 0%, #ffedcc 100%); border-radius: 12px;">
            <div style="font-size: 13px; color: #666; font-weight: 500; margin-bottom: 6px;">Tag Coverage %</div>
            <div style="font-size: 36px; font-weight: 700; color: {pct_color}; line-height: 1;">{coverage_pct:.2f}%</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_governance_health_score_content():
    """Render governance health score with tag coverage table, apply method chart, and tagging audit charts."""

    tag_coverage_by_db_query = """
    WITH Get_Tables AS (
        SELECT object_id, object_database, object_schema, object_name,
               ANY_VALUE(TAG_NAME) AS HAS_TAG
        FROM   SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES tr
        WHERE  tr.DOMAIN IN ('TABLE', 'COLUMN')
        AND    tr.OBJECT_DELETED IS NULL
GROUP BY object_id, object_database, object_schema, object_name
    )
    SELECT
        t.TABLE_CATALOG AS database_name,
        COUNT(*) AS total_tables,
        COUNT(DISTINCT CASE WHEN tr.HAS_TAG IS NOT NULL THEN t.TABLE_ID END) AS tagged_tables,
        COUNT(*) - COUNT(DISTINCT CASE WHEN tr.HAS_TAG IS NOT NULL THEN t.TABLE_ID END) AS untagged_tables,
        ROUND(COUNT(DISTINCT CASE WHEN tr.HAS_TAG IS NOT NULL THEN t.TABLE_ID END)
              / NULLIF(COUNT(*), 0) * 100, 2) AS coverage_pct
    FROM   SNOWFLAKE.ACCOUNT_USAGE.TABLES t
    LEFT JOIN Get_Tables tr ON t.TABLE_ID = tr.OBJECT_ID
    WHERE  t.DELETED IS NULL
    AND    t.TABLE_CATALOG != 'SNOWFLAKE'
    AND    t.TABLE_SCHEMA != 'INFORMATION_SCHEMA'
GROUP BY t.TABLE_CATALOG
    ORDER BY total_tables DESC
    """

    tag_apply_method_query = """
    WITH APM AS (
        SELECT $1 APPLY_METHOD FROM VALUES
            ('CLASSIFIED'), ('INHERITED'), ('MANUAL'), ('PROPAGATED'), ('NULL'), ('NONE')
    ),
    VEW AS (
        SELECT COALESCE(APPLY_METHOD, 'NULL') AS APPLY_METHOD,
               COUNT(*) AS total_tags,
               COALESCE(COUNT(DISTINCT OBJECT_NAME), 0) AS objects_covered
        FROM   SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
        WHERE  OBJECT_DELETED IS NULL
        AND    OBJECT_DATABASE != 'SNOWFLAKE'
        GROUP BY 1
    )
    SELECT APM.APPLY_METHOD,
           COALESCE(VEW.TOTAL_TAGS, 0) AS TOTAL_TAGS,
           COALESCE(VEW.OBJECTS_COVERED, 0) AS OBJECTS_COVERED
    FROM   APM
    LEFT OUTER JOIN VEW ON APM.APPLY_METHOD = VEW.APPLY_METHOD
    """

    try:
        coverage_by_db_df = st.session_state.session.sql(tag_coverage_by_db_query).to_pandas()
        tag_method_df = st.session_state.session.sql(tag_apply_method_query).to_pandas()

        total_tables = int(coverage_by_db_df['TOTAL_TABLES'].sum()) if len(coverage_by_db_df) > 0 else 0
        tagged_tables = int(coverage_by_db_df['TAGGED_TABLES'].sum()) if len(coverage_by_db_df) > 0 else 0

        _render_governance_kpi_tiles(total_tables, tagged_tables)

        st.markdown("")

        col1, col2 = st.columns([1, 1])

        with col1.container(border=True, height=550):
            st.markdown("##### Tag Coverage Metrics By Database")
            if len(coverage_by_db_df) > 0:
                display_df = coverage_by_db_df[['DATABASE_NAME', 'TOTAL_TABLES', 'TAGGED_TABLES', 'UNTAGGED_TABLES', 'COVERAGE_PCT']].copy()
                display_df.columns = ['Database', 'Total Tables', 'Tagged Tables', 'Untagged Tables', 'Coverage %']
                st.dataframe(display_df, use_container_width=True, height=450)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No tag coverage data available.'
                            '</div>', unsafe_allow_html=True)

        with col2.container(border=True, height=550):
            st.markdown("##### Tags by Apply Method")

            if len(tag_method_df) > 0:
                chart_type = st.selectbox(
                    "Change Chart Type",
                    ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                    index=0,
                    key="tag_coverage_chart_type"
                )

                if chart_type == "Bar Chart":
                    _render_tag_coverage_bar_chart(tag_method_df)
                elif chart_type == "Pie Chart":
                    _render_tag_coverage_pie_chart(tag_method_df)
                elif chart_type == "Pie - Donut":
                    _render_tag_coverage_donut_chart(tag_method_df)
                else:
                    _render_tag_coverage_rose_chart(tag_method_df)
            else:
                st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                            'ℹ️&nbsp;&nbsp;No tag apply method data available.'
                            '</div>', unsafe_allow_html=True)


    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading governance health score: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_policy_inventory_bar_chart(policy_df):
    """Render policy inventory vertical bar chart using ECharts."""
    df_sorted = policy_df.sort_values('ACTIVE_COUNT', ascending=False)

    policy_kinds = df_sorted['POLICY_KIND'].tolist()
    active_counts = [int(v) for v in df_sorted['ACTIVE_COUNT'].tolist()]

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
        },
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 15,
            "itemWidth": 14,
            "textStyle": {"fontSize": 11}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "top": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "category",
            "data": policy_kinds,
            "axisLabel": {"fontSize": 10, "rotate": 30}
        },
        "yAxis": {
            "type": "value",
            "name": "Active Count",
            "nameLocation": "middle",
            "nameGap": 35
        },
        "color": ["#1f77b4"],
        "series": [
            {
                "name": "Active Count",
                "type": "bar",
                "data": active_counts
            }
        ]
    }

    st_echarts(options=option, height="400px", key="policy_inventory_bar_chart")


def _render_policy_inventory_pie_chart(policy_df):
    """Render policy inventory standard pie chart using ECharts."""
    chart_data = [
        {"value": int(row['ACTIVE_COUNT']), "name": f"{row['POLICY_KIND']} ({int(row['ACTIVE_COUNT'])})"}
        for _, row in policy_df.iterrows() if int(row['ACTIVE_COUNT']) > 0
    ]

    if not chart_data:
        chart_data = [{"value": 0, "name": "No Active Policies"}]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
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
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Policy Count",
                "type": "pie",
                "radius": ["0%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="400px", key="policy_inventory_pie_chart")


def _render_policy_inventory_donut_chart(policy_df):
    """Render policy inventory donut pie chart using ECharts."""
    chart_data = [
        {"value": int(row['ACTIVE_COUNT']), "name": f"{row['POLICY_KIND']} ({int(row['ACTIVE_COUNT'])})"}
        for _, row in policy_df.iterrows() if int(row['ACTIVE_COUNT']) > 0
    ]

    if not chart_data:
        chart_data = [{"value": 0, "name": "No Active Policies"}]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
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
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Policy Count",
                "type": "pie",
                "radius": ["25%", "50%"],
                "center": ["50%", "40%"],
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="400px", key="policy_inventory_donut_chart")


def _render_policy_inventory_rose_chart(policy_df):
    """Render policy inventory rose-type pie chart using ECharts."""
    chart_data = [
        {"value": int(row['ACTIVE_COUNT']), "name": f"{row['POLICY_KIND']} ({int(row['ACTIVE_COUNT'])})"}
        for _, row in policy_df.iterrows() if int(row['ACTIVE_COUNT']) > 0
    ]

    if not chart_data:
        chart_data = [{"value": 0, "name": "No Active Policies"}]

    option = {
        "legend": {
            "bottom": "10",
            "left": "center",
            "orient": "horizontal",
            "itemGap": 8,
            "itemWidth": 14,
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
                "mark": {"show": True},
                "dataView": {"show": True, "readOnly": False},
                "restore": {"show": True},
                "saveAsImage": {"show": True},
            },
        },
        "series": [
            {
                "name": "Policy Count",
                "type": "pie",
                "radius": ["15%", "55%"],
                "center": ["50%", "40%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(options=option, height="400px", key="policy_inventory_rose_chart")


def _render_policy_inventory_content():
    """Render policy inventory with table + buttons and chart in two columns."""

    policy_inventory_query = """
    WITH SF   AS (SELECT DISTINCT POLICY_KIND
                  FROM   SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES),
         S360 AS (SELECT POLICY_KIND,
                         COUNT(*) AS ACTIVE_COUNT
                  FROM   SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES S360
                  WHERE  S360.POLICY_STATUS = 'ACTIVE'
                  AND    S360.POLICY_DB != 'SNOWFLAKE'
                  GROUP BY 1)
    SELECT SF.POLICY_KIND,
           NVL(S360.ACTIVE_COUNT, 0) AS ACTIVE_COUNT
    FROM   SF
    LEFT OUTER JOIN S360 ON SF.POLICY_KIND = S360.POLICY_KIND
    ORDER BY 1, 2
    """

    try:
        policy_df = st.session_state.session.sql(policy_inventory_query).to_pandas()

        if len(policy_df) > 0:
            table_col, chart_col = st.columns([1, 1])

            with table_col.container(border=True, height=600):
                display_df = policy_df.copy()
                display_df.columns = ['Policy Kind', 'Active Count']

                st.markdown("##### Policy Inventory")
                st.dataframe(display_df, use_container_width=True, height=422)

            with chart_col.container(border=True, height=600):
                st.markdown("##### Policy Inventory by Kind")

                chart_type = st.selectbox(
                    "Change Chart Type",
                    ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
                    index=0,
                    key="policy_inv_chart_type"
                )

                if chart_type == "Bar Chart":
                    _render_policy_inventory_bar_chart(policy_df)
                elif chart_type == "Pie Chart":
                    _render_policy_inventory_pie_chart(policy_df)
                elif chart_type == "Pie - Donut":
                    _render_policy_inventory_donut_chart(policy_df)
                else:
                    _render_policy_inventory_rose_chart(policy_df)
        else:
            st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        'ℹ️&nbsp;&nbsp;No policy inventory data available.'
                        '</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading policy inventory: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_overview_content():
    """Render the core governance overview content (health score, heatmap, policy inventory)."""
    st.markdown("### Data Governance Overview")

    with st.expander("Governance Health Score", expanded=True):
        st.markdown("#### Governance Health Score")
        _render_governance_health_score_content()

    with st.expander("Sensitivity Heatmap", expanded=False):
        st.markdown("#### Sensitivity Heatmap")
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;Content for Sensitivity Heatmap will be implemented here.'
                    '</div>', unsafe_allow_html=True)

    with st.expander("Policy Inventory", expanded=True):
        st.markdown("#### Policy Inventory")
        _render_policy_inventory_content()


def comp_governance_overview(entry_actions=None):
    """
    Data Governance Overview Component

    Renders sub-tabs for:
    - Overview: Governance Health Score, Sensitivity Heatmap, Policy Inventory
    - Data Object Tagging & Classification
    - Data Privacy & Protection
    - Data Lineage & Quality (Lite)

    Args:
        entry_actions: Optional callback actions on component entry
    """
    try:
        sub_tab_names = [
            "Overview",
            "Data Object Tagging & Classification",
            "Data Privacy & Protection",
            "Data Lineage & Quality (Lite)"
        ]
        sub_tabs = st.tabs(sub_tab_names)

        with sub_tabs[0]:
            _render_overview_content()

        with sub_tabs[1]:
            comp_object_tagging_classification()

        with sub_tabs[2]:
            comp_data_privacy_protection()

        with sub_tabs[3]:
            comp_lineage_quality()

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Data Governance Overview: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

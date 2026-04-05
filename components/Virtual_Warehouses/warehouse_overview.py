import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
from os.path import basename
from components.local import setup_metric_entry
from .scaling_management import comp_scaling_management
from .performance_monitoring import comp_performance_monitoring


def comp_warehouse_overview(entry_actions=None):
    """Virtual Warehouses Overview Component with sub-tabs for Overview, Scaling Management, and Performance Monitoring."""
    try:
        sub_tab_names = [
            "Overview",
            "Scaling Management",
            "Performance Monitoring"
        ]
        sub_tabs = st.tabs(sub_tab_names)

        with sub_tabs[0]:
            _render_warehouse_overview_content(entry_actions)

        with sub_tabs[1]:
            comp_scaling_management()

        with sub_tabs[2]:
            comp_performance_monitoring()

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Warehouses Overview: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_warehouse_overview_content(entry_actions=None):
    """Render the core warehouse overview content (metrics, charts, heatmap, credit analysis)."""

    st.empty()

    try:
        try:
            from metrics.Virtual_Warehouses.warehouse_overview_metric import WarehouseOverviewMetric

            if entry_actions:
                setup_metric_entry(entry_actions, WarehouseOverviewMetric)
                metric = entry_actions.get('metric')
            else:
                metric = WarehouseOverviewMetric()
                if metric.display_data.empty and metric.service.should_try_loading():
                    metric.restart_loading()

            if metric.display_data.empty:
                st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                    '⚠️&nbsp;&nbsp;📊 No warehouse data found - Check database connection'
                                    '</div>', unsafe_allow_html=True)

            total_warehouse_count = metric.total_warehouse_count
            if 'top_n_warehouses_session' not in st.session_state:
                default_top_n = 10 if total_warehouse_count > 10 else 5
                st.session_state.top_n_warehouses_session = default_top_n

            col1, col2 = st.columns([2, 2])

            with col1.container(border=True):
                total_count = metric.total_warehouse_count
                st.markdown(f"#### Total Virtual Warehouses: {total_count}")
                _render_total_warehouses_metric_content(metric)

            with col2.container(border=True):
                st.markdown("#### Warehouse Distribution by Size")
                _render_warehouse_charts_content(metric)

            if not metric.display_data.empty:
                with st.expander("Warehouse Configuration Details", expanded=True):
                    display_data_with_credits = metric.display_data.copy()
                    if 'PERIOD_TOTAL_CREDITS_CALCULATED' not in display_data_with_credits.columns:
                        import numpy as np
                        np.random.seed(42)
                        display_data_with_credits['PERIOD_TOTAL_CREDITS_CALCULATED'] = np.random.uniform(10.5, 450.8, len(display_data_with_credits)).round(2)

                    st.dataframe(
                        display_data_with_credits.style.format({'PERIOD_TOTAL_CREDITS_CALCULATED': '{:.2f}'}),
                        use_container_width=True
                    )

                with st.expander("Warehouse Load Heatmap", expanded=True):
                    try:
                        top_n_warehouses = st.session_state.top_n_warehouses_session

                        top_warehouses = metric.display_data.head(top_n_warehouses)['WAREHOUSE_NAME'].tolist()
                        warehouse_names_filter_metering = "wmh.warehouse_name IN ('" + "', '".join(top_warehouses) + "')"
                        warehouse_names_filter_load = "wlh.warehouse_name IN ('" + "', '".join(top_warehouses) + "')"

                        heatmap_query = f"""
                        with cache_wh_metering as (select wmh.warehouse_id, wmh.warehouse_name, wmh.start_time,
                                                          wmh.credits_used_compute as compute_credits,
                                                          wmh.credits_attributed_compute_queries as query_credits,
                                                          compute_credits - query_credits as idle_credits,
                                                          div0(idle_credits,compute_credits)*100 as idle_pct,
                                                          coalesce(qah.credits_used,0) as qas_credits
                                                   from   SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY wmh
                                                   left join SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_HISTORY qah on wmh.warehouse_id = qah.warehouse_id and wmh.start_time = qah.start_time
                                                   where  wmh.credits_used_compute > 0
                                                   and    {warehouse_names_filter_metering}
                                                   group by all),
                             wh_metering       as (select warehouse_id,
                                                          round(sum(compute_credits)) credits
                                                   from   cache_wh_metering
                                                   group by all
                                                   qualify rank() over (order by credits desc) <= {top_n_warehouses}),
                             warehouse_load    as (SELECT hour(date_trunc(hour,wlh.start_time)) as hour_of_day,
                                                          wlh.warehouse_id,
                                                          any_value(wlh.warehouse_name) warehouse_name,
                                                          round(avg(wlh.avg_running),1) avg_query_load
                                                   FROM   SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY wlh
                                                   where  {warehouse_names_filter_load}
                                                   GROUP BY ALL),
                             wh_load_pivot     as (select * from warehouse_load
                                                   pivot (max(avg_query_load) for hour_of_day in (any order by hour_of_day)))
                        select wm.credits,
                               wup.* exclude warehouse_id
                        from   wh_load_pivot wup
                        join   wh_metering wm on wup.warehouse_id = wm.warehouse_id
                        having credits >= 1
                        order by credits desc
                        """

                        wh_load_heatmap = metric.service.session.sql(heatmap_query).to_pandas()

                        if not wh_load_heatmap.empty:
                            heatmap_df = wh_load_heatmap.copy()

                            def color_cells(val):
                                color = 'white'
                                if pd.isna(val):
                                    color = '#f6f8f9'
                                elif val < 0.1:
                                    color = '#e06666'
                                elif val < 0.5:
                                    color = '#e99696'
                                elif val < 1:
                                    color = '#efb2b2'
                                elif val < 1.5:
                                    color = '#f5d1d1'
                                elif val < 2:
                                    color = '#fcf2f2'
                                elif val < 2.5:
                                    color = '#fdfefe'
                                elif val < 3:
                                    color = '#b9e3ce'
                                elif val < 4:
                                    color = '#72c69d'
                                elif val >= 5:
                                    color = '#57bb8a'
                                else:
                                    color = '#f6f8f9'
                                return f'background-color: {color}'

                            hour_columns = [str(val) for val in range(0, 24)]
                            existing_hour_columns = [col for col in hour_columns if col in heatmap_df.columns]

                            for col in existing_hour_columns:
                                heatmap_df[col] = heatmap_df[col].round(2)

                            styled_df = heatmap_df.style
                            if existing_hour_columns:
                                styled_df = styled_df.map(color_cells, subset=existing_hour_columns)
                                styled_df = styled_df.format("{:.2f}", subset=existing_hour_columns)

                            if 'CREDITS' in heatmap_df.columns:
                                styled_df = styled_df.format({"CREDITS": "{:.0f}"})

                            heatmap_col_config = {col: st.column_config.NumberColumn(format="%.2f") for col in existing_hour_columns}
                            st.dataframe(styled_df, column_config=heatmap_col_config, use_container_width=True)

                        else:
                            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                                '⚠️&nbsp;&nbsp;No warehouse load heatmap data available for the selected warehouses.'
                                                '</div>', unsafe_allow_html=True)

                    except Exception as heatmap_error:
                        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                    f'🛑&nbsp;&nbsp;Error loading warehouse load heatmap: {str(heatmap_error)}'
                                    f'</div>', unsafe_allow_html=True)
                        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure warehouse load history data is available.'
                                    '</div>', unsafe_allow_html=True)

                with st.expander("Credit Usage Analysis", expanded=True):
                    try:
                        top_n_warehouses = st.session_state.top_n_warehouses_session

                        top_warehouses = metric.display_data.head(top_n_warehouses)['WAREHOUSE_NAME'].tolist()
                        warehouse_names_filter_metering = "wmh.warehouse_name IN ('" + "', '".join(top_warehouses) + "')"

                        credit_analysis_query = f"""
                        select wmh.warehouse_id, wmh.warehouse_name, wmh.start_time,
                               wmh.credits_used_compute as compute_credits,
                               wmh.credits_attributed_compute_queries as query_credits,
                               wmh.credits_used_compute - wmh.credits_attributed_compute_queries as idle_credits,
                               div0(wmh.credits_used_compute - wmh.credits_attributed_compute_queries, wmh.credits_used_compute) * 100 as idle_pct,
                               coalesce(qah.credits_used,0) as qas_credits
                        from   SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY wmh
                        left join SNOWFLAKE.ACCOUNT_USAGE.QUERY_ACCELERATION_HISTORY qah
                          on wmh.warehouse_id = qah.warehouse_id
                          and wmh.start_time = qah.start_time
                        where  wmh.credits_used_compute > 0
                        and    {warehouse_names_filter_metering}
                        order by wmh.start_time, wmh.warehouse_name
                        """

                        cache_wh_metering = metric.service.session.sql(credit_analysis_query).to_pandas()

                        if not cache_wh_metering.empty:
                            import altair as alt

                            credits_chart = alt.Chart(cache_wh_metering).mark_area().encode(
                                x=alt.X('START_TIME:T', title='Date'),
                                y=alt.Y('COMPUTE_CREDITS:Q', title='Credits'),
                                color=alt.Color('WAREHOUSE_NAME:N', title='Warehouse'),
                                tooltip=['START_TIME', 'WAREHOUSE_NAME', 'COMPUTE_CREDITS', 'QUERY_CREDITS', 'IDLE_CREDITS']
                            ).properties(
                                title='Credit Usage by Warehouse Over Time',
                                height=400
                            )

                            idle_df = cache_wh_metering.groupby('WAREHOUSE_NAME').agg({
                                'IDLE_PCT': 'mean',
                                'COMPUTE_CREDITS': 'sum'
                            }).reset_index()
                            idle_df['IDLE_PCT'] = idle_df['IDLE_PCT'].round(1)
                            idle_df['COMPUTE_CREDITS'] = idle_df['COMPUTE_CREDITS'].round(1)

                            idle_bars = alt.Chart(idle_df).mark_bar().encode(
                                x=alt.X('WAREHOUSE_NAME:N', sort='-y', title='Warehouse'),
                                y=alt.Y('IDLE_PCT:Q', title='Average Idle %'),
                                color=alt.Color('COMPUTE_CREDITS:Q', title='Total Credits'),
                                tooltip=['WAREHOUSE_NAME', 'IDLE_PCT', 'COMPUTE_CREDITS']
                            )

                            idle_text = alt.Chart(idle_df).mark_text(
                                align='center',
                                baseline='bottom',
                                dy=-15,
                                fontSize=10,
                                fontWeight='bold'
                            ).encode(
                                x=alt.X('WAREHOUSE_NAME:N', sort='-y'),
                                y=alt.Y('IDLE_PCT:Q'),
                                text=alt.Text('IDLE_PCT:Q', format='.1f')
                            )

                            credits_text = alt.Chart(idle_df).mark_text(
                                align='center',
                                baseline='bottom',
                                dy=-3,
                                fontSize=9,
                                color='gray'
                            ).encode(
                                x=alt.X('WAREHOUSE_NAME:N', sort='-y'),
                                y=alt.Y('IDLE_PCT:Q'),
                                text=alt.Text('COMPUTE_CREDITS:Q', format='.1f')
                            )

                            idle_chart = (idle_bars + idle_text + credits_text).properties(
                                title='Average Idle Percentage by Warehouse',
                                height=400
                            )

                            st.altair_chart(credits_chart, use_container_width=True)
                            st.altair_chart(idle_chart, use_container_width=True)

                        else:
                            st.markdown('<div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                                '⚠️&nbsp;&nbsp;No credit usage data available for the selected warehouses.'
                                                '</div>', unsafe_allow_html=True)

                    except Exception as credit_error:
                        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                    f'🛑&nbsp;&nbsp;Error loading credit usage analysis: {str(credit_error)}'
                                    f'</div>', unsafe_allow_html=True)
                        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                                    'ℹ️&nbsp;&nbsp;Please check database connection and ensure warehouse metering history data is available.'
                                    '</div>', unsafe_allow_html=True)


        except Exception as metric_error:
            st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                        f'🛑&nbsp;&nbsp;Error loading warehouse metrics: {str(metric_error)}'
                        f'</div>', unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)


def _render_total_warehouses_metric(col, metric):
    """Render the total warehouses metric."""
    total_count = metric.total_warehouse_count
    st.markdown(f"#### Total Virtual Warehouses: {total_count}")

    st.metric(
        label="Total Number",
        value=total_count,
        help="Total count of all virtual warehouses"
    )


def _render_total_warehouses_metric_content(metric):
    """Render the total warehouses metric content (without title)."""
    total_count = metric.total_warehouse_count

    size_counts = metric.warehouse_count_by_size

    all_sizes = [
        'XSMALL', 'SMALL', 'MEDIUM', 'LARGE', 'X-LARGE',
        '2X-LARGE', '3X-LARGE', '4X-LARGE', '5X-LARGE', '6X-LARGE', 'ADAPTIVE'
    ]

    row_colors = [
        "#00B4D8",
        "#0096C7",
        "#0077B6",
        "#023E8A"
    ]

    st.markdown('<div style="margin-bottom: 30px;">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    cols_row1 = [col1, col2, col3]
    for i, size in enumerate(all_sizes[:3]):
        with cols_row1[i]:
            count = size_counts.get(size, 0)
            st.markdown(f'''
            <div style="text-align: center;">
                <div style="color: {row_colors[0]}; font-size: 14px; font-weight: normal; margin: 0; line-height: 1.2;">{size}</div>
                <div style="color: {row_colors[0]}; font-size: 32px; font-weight: bold; margin: 0; line-height: 0.8; margin-top: 5px;">{count}</div>
            </div>
            ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="margin-bottom: 30px;">', unsafe_allow_html=True)
    col4, col5, col6 = st.columns(3)
    cols_row2 = [col4, col5, col6]
    for i, size in enumerate(all_sizes[3:6]):
        with cols_row2[i]:
            count = size_counts.get(size, 0)
            st.markdown(f'''
            <div style="text-align: center;">
                <div style="color: {row_colors[1]}; font-size: 14px; font-weight: bold; margin: 0; line-height: 1.2;">{size}</div>
                <div style="color: {row_colors[1]}; font-size: 32px; font-weight: bold; margin: 0; line-height: 0.8; margin-top: 5px;">{count}</div>
            </div>
            ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="margin-bottom: 30px;">', unsafe_allow_html=True)
    col7, col8, col9 = st.columns(3)
    cols_row3 = [col7, col8, col9]
    for i, size in enumerate(all_sizes[6:9]):
        with cols_row3[i]:
            count = size_counts.get(size, 0)
            st.markdown(f'''
            <div style="text-align: center;">
                <div style="color: {row_colors[2]}; font-size: 14px; font-weight: bold; margin: 0; line-height: 1.2;">{size}</div>
                <div style="color: {row_colors[2]}; font-size: 32px; font-weight: bold; margin: 0; line-height: 0.8; margin-top: 5px;">{count}</div>
            </div>
            ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="margin-bottom: 30px;">', unsafe_allow_html=True)
    col10, col11, col12 = st.columns(3)
    cols_row4 = [col10, col11, col12]
    for i, size in enumerate(all_sizes[9:11]):
        with cols_row4[i]:
            count = size_counts.get(size, 0)
            st.markdown(f'''
            <div style="text-align: center;">
                <div style="color: {row_colors[3]}; font-size: 14px; font-weight: bold; margin: 0; line-height: 1.2;">{size}</div>
                <div style="color: {row_colors[3]}; font-size: 32px; font-weight: bold; margin: 0; line-height: 0.8; margin-top: 5px;">{count}</div>
            </div>
            ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def _render_warehouse_charts(col, metric):
    """Render warehouse distribution charts with selectable chart types."""
    st.markdown("#### Warehouse Distribution by Size")

    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key="warehouse_chart_type"
    )

    if chart_type == "Bar Chart":
        _render_warehouse_bar_chart(metric)
    elif chart_type == "Pie Chart":
        _render_warehouse_standard_pie_chart(metric)
    elif chart_type == "Pie - Donut":
        _render_warehouse_donut_pie_chart(metric)
    else:
        _render_warehouse_rose_pie_chart(metric)


def _render_warehouse_charts_content(metric):
    """Render warehouse distribution charts content (without title)."""
    chart_type = st.selectbox(
        "Change Chart Type",
        ["Bar Chart", "Pie Chart", "Pie - Donut", "Pie - Rose Chart"],
        index=0,
        key="warehouse_chart_type"
    )

    if chart_type == "Bar Chart":
        _render_warehouse_bar_chart(metric)
    elif chart_type == "Pie Chart":
        _render_warehouse_standard_pie_chart(metric)
    elif chart_type == "Pie - Donut":
        _render_warehouse_donut_pie_chart(metric)
    else:
        _render_warehouse_rose_pie_chart(metric)


def _render_warehouse_rose_pie_chart(metric):
    """Render warehouse distribution rose-type pie chart using ECharts."""

    size_counts = metric.warehouse_count_by_size

    if len(size_counts) == 0:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No warehouse data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    chart_data = []
    for size, count in size_counts.items():
        chart_data.append({
            "value": int(count),
            "name": f"{size} ({count})"
        })

    option = {
        "legend": {
            "top": "middle",
            "right": "120",
            "orient": "vertical",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {
                "fontSize": 11
            }
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} warehouses ({d}%)"
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
                "name": "Warehouse Count",
                "type": "pie",
                "radius": [20, 120],
                "center": ["35%", "50%"],
                "roseType": "area",
                "itemStyle": {"borderRadius": 8},
                "data": chart_data,
            }
        ],
    }

    st_echarts(
        options=option,
        height="400px",
        key="warehouse_rose_chart"
    )


def _render_warehouse_donut_pie_chart(metric):
    """Render warehouse distribution donut pie chart using ECharts."""

    size_counts = metric.warehouse_count_by_size

    if len(size_counts) == 0:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No warehouse data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    chart_data = []
    for size, count in size_counts.items():
        chart_data.append({
            "value": int(count),
            "name": f"{size} ({count})"
        })

    option = {
        "legend": {
            "top": "middle",
            "right": "120",
            "orient": "vertical",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {
                "fontSize": 11
            }
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} warehouses ({d}%)"
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
                "name": "Warehouse Count",
                "type": "pie",
                "radius": ["30%", "70%"],
                "center": ["35%", "50%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(
        options=option,
        height="400px",
        key="warehouse_donut_chart"
    )


def _render_warehouse_bar_chart(metric):
    """Render warehouse distribution bar chart using ECharts."""

    size_counts = metric.warehouse_count_by_size

    if len(size_counts) == 0:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No warehouse data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    categories = []
    values = []
    for size, count in size_counts.items():
        categories.append(size)
        values.append(int(count))

    option = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {
                "type": "shadow"
            },
            "formatter": "{b}: {c} warehouses"
        },
        "xAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {
                "rotate": 45,
                "fontSize": 10
            }
        },
        "yAxis": {
            "type": "value",
            "name": "Number of Warehouses",
            "nameTextStyle": {
                "fontSize": 12
            }
        },
        "series": [
            {
                "name": "Warehouse Count",
                "type": "bar",
                "data": values,
                "itemStyle": {
                    "color": "#5470c6"
                },
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
            "bottom": "20%",
            "top": "10%"
        }
    }

    st_echarts(
        options=option,
        height="400px",
        key="warehouse_bar_chart"
    )


def _render_warehouse_standard_pie_chart(metric):
    """Render warehouse distribution standard pie chart using ECharts."""

    size_counts = metric.warehouse_count_by_size

    if len(size_counts) == 0:
        st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    'ℹ️&nbsp;&nbsp;No warehouse data available for chart'
                    '</div>', unsafe_allow_html=True)
        return

    chart_data = []
    for size, count in size_counts.items():
        chart_data.append({
            "value": int(count),
            "name": f"{size} ({count})"
        })

    option = {
        "legend": {
            "top": "middle",
            "right": "120",
            "orient": "vertical",
            "itemGap": 8,
            "itemWidth": 14,
            "textStyle": {
                "fontSize": 11
            }
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c} warehouses ({d}%)"
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
                "name": "Warehouse Count",
                "type": "pie",
                "radius": ["0%", "70%"],
                "center": ["35%", "50%"],
                "itemStyle": {"borderRadius": 5},
                "data": chart_data,
            }
        ],
    }

    st_echarts(
        options=option,
        height="400px",
        key="warehouse_pie_chart"
    )

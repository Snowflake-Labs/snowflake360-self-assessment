# Copyright 2026 Snowflake, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import streamlit as st
import traceback as _tb
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(
    page_title="Snowflake 360 Self-Assessment",
    layout="wide",
    initial_sidebar_state="expanded"
)

_import_err = None
try:
    import streamlit.components.v1 as components
    from datetime import datetime
    from snowflake.snowpark.context import get_active_session
    import core as cr
    from components.local import load_catalog
    from components.Analysis.invoke_metrics_comps import get_analysis_comp_handler
    import pandas as _pd
    from components.Access_Control._all_ac_queries import _ALL_AC_QUERIES
    from components.Virtual_Warehouses.warehouse_overview import _ALL_WH_QUERIES
    from components.Data_Ingestion.ingestion_overview import _ALL_INGESTION_QUERIES
    from components.FinOps_Lite._all_finops_queries import _ALL_FINOPS_QUERIES
    from components.Data_Recovery_DevOps.recovery_devops_overview import _ALL_DEVOPS_QUERIES
    from components.Data_Transformation._all_tf_queries import _ALL_TF_QUERIES
    from components.Data_Governance_New._dg_queries import ALL_DG_QUERIES
    from components.Database_Management._db_queries import ALL_DB_OVERVIEW_QUERIES
    from components.Database_Management.db_overview import _query_cache as _DB_QUERY_CACHE
    from core.config.design_tokens import (
        BRAND_PRIMARY, BRAND_PRIMARY_DARK, BRAND_SECONDARY, BRAND_ACCENT,
        SURFACE_ALT, SURFACE_BASE,
        TEXT_SECONDARY, TEXT_HEADING,
        TEXT_INVERSE,
        ERROR, SUCCESS,
        CSS_CUSTOM_PROPERTIES,
    )
    from core.export_collectors import TOPIC_EXPORTERS
    global_settings = cr.config
except Exception as _e:
    _import_err = _tb.format_exc()

if _import_err:
    st.error("App failed to start — import error:")
    st.code(_import_err)
    st.stop()


_PREFS_TABLE = "DEMOS.S360_SELF_ASSESS.USER_PREFERENCES"


def _get_preference(key: str, default=None):
    try:
        session = get_active_session()
        rows = session.sql(
            f"SELECT SETTING_VALUE FROM {_PREFS_TABLE} "
            f"WHERE USER_NAME = CURRENT_USER() AND SETTING_KEY = '{key}'"
        ).collect()
        if rows:
            return rows[0]["SETTING_VALUE"]
    except Exception:
        pass
    return default


def _set_preference(key: str, value: str):
    try:
        session = get_active_session()
        session.sql(
            f"MERGE INTO {_PREFS_TABLE} t "
            f"USING (SELECT CURRENT_USER() AS USER_NAME, '{key}' AS SETTING_KEY, $${value}$$ AS SETTING_VALUE) s "
            f"ON t.USER_NAME = s.USER_NAME AND t.SETTING_KEY = s.SETTING_KEY "
            f"WHEN MATCHED THEN UPDATE SET SETTING_VALUE = s.SETTING_VALUE, UPDATED_AT = CURRENT_TIMESTAMP() "
            f"WHEN NOT MATCHED THEN INSERT (USER_NAME, SETTING_KEY, SETTING_VALUE) VALUES (s.USER_NAME, s.SETTING_KEY, s.SETTING_VALUE)"
        ).collect()
    except Exception:
        pass


def _persist_rates():
    _set_preference("rate_credit", str(st.session_state.rate_credit))
    _set_preference("rate_storage", str(st.session_state.rate_storage))
    _set_preference("rate_transfer", str(st.session_state.rate_transfer))


_LLM_FILTER_PREFIXES = (
    "claude-", "deepseek-", "gemini-", "llama3.", "llama4",
    "mistral-large", "openai-", "snowflake-llama",
)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_available_models():
    try:
        session = get_active_session()
        rows = session.sql("SHOW MODELS IN SNOWFLAKE.MODELS").collect()
        candidates = sorted(
            row["name"].lower() for row in rows
            if row["name"].lower().startswith(_LLM_FILTER_PREFIXES)
        )
        if not candidates:
            return []
        probe_sql = " UNION ALL ".join(
            f"SELECT '{m}' AS model WHERE SNOWFLAKE.CORTEX.TRY_COMPLETE('{m}', 'hi') IS NOT NULL"
            for m in candidates
        )
        valid_rows = session.sql(probe_sql).collect()
        valid = sorted(row["MODEL"] for row in valid_rows)
        return valid if valid else []
    except Exception:
        pass
    return []

st.markdown(global_settings.MAIN_MARKDOWN_BODY, unsafe_allow_html=True)
st.markdown(global_settings.DEFAULT2_MARKDOWN_BODY, unsafe_allow_html=True)

st.markdown(f"""
<style>
    {CSS_CUSTOM_PROPERTIES}
    section[data-testid="stSidebar"] {{
        background-color: {SURFACE_ALT};
        padding-top: 0px !important;
    }}
    [data-testid="stSidebar"][aria-expanded="true"] {{
        min-width: 320px !important;
        max-width: 320px !important;
    }}
    section[data-testid="stSidebar"] .block-container {{
        padding-top: 0px !important;
        margin-top: -29px !important;
    }}
    section[data-testid="stSidebar"] > div {{
        padding-top: 0px !important;
    }}
    section[data-testid="stSidebar"] .element-container:first-of-type {{
        margin-top: -37px !important;
    }}
    div[data-testid="stSidebar"] .stButton > button {{
        background-color: {SURFACE_BASE} !important;
        color: {TEXT_SECONDARY} !important;
        border-radius: 8px !important;
        font-size: 16px !important;
        font-weight: 400 !important;
        padding: 12px 16px !important;
        text-align: center !important;
    }}
    div[data-testid="stSidebar"] .stButton > button:hover {{
        border: 2px solid {BRAND_PRIMARY} !important;
        color: {BRAND_PRIMARY} !important;
    }}

    .stTabs [data-baseweb="tab-highlight"] {{
        background-color: {BRAND_PRIMARY} !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {TEXT_SECONDARY} !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: {BRAND_PRIMARY} !important;
    }}
    .stProgress > div > div > div > div {{
        background-color: {BRAND_PRIMARY} !important;
    }}
    h1, h2, h3 {{
        font-family: var(--font-family-app) !important;
    }}
    .stMarkdown h1 {{
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: {BRAND_PRIMARY} !important;
        margin-top: 1rem !important;
        margin-bottom: 0.5rem !important;
    }}
    .stMarkdown h2 {{
        font-size: 1.25rem !important;
        font-weight: 600 !important;
        color: {TEXT_HEADING} !important;
        margin-top: 0.8rem !important;
        margin-bottom: 0.4rem !important;
    }}
    .stMarkdown h3 {{
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: {TEXT_HEADING} !important;
    }}
    .stMarkdown p, .stMarkdown li {{
        font-size: 0.95rem !important;
        line-height: 1.6 !important;
    }}
    div[data-testid="stHorizontalBlock"]:has(.telemetry-btn-anchor) button {{
        background-color: #11567F !important;
        color: white !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        padding: 0.45rem 0.9rem !important;
    }}
    div[data-testid="stHorizontalBlock"]:has(.telemetry-btn-anchor) button:hover {{
        background-color: #0d4468 !important;
        color: white !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }}
    div[data-testid="stHorizontalBlock"]:has(.telemetry-btn-anchor) button:focus,
    div[data-testid="stHorizontalBlock"]:has(.telemetry-btn-anchor) button:focus-visible,
    div[data-testid="stHorizontalBlock"]:has(.telemetry-btn-anchor) button:active {{
        box-shadow: none !important;
        outline: none !important;
        border: none !important;
    }}
    .telemetry-btn-anchor {{ display: none; }}
    [data-testid="stCheckbox"] label[aria-checked="true"] [data-baseweb="checkbox"] {{
        background-color: {BRAND_PRIMARY} !important;
        border-color: {BRAND_PRIMARY} !important;
    }}
    [data-testid="stCheckbox"] label [data-baseweb="checkbox"] {{
        border-color: {BRAND_PRIMARY} !important;
    }}
    div[data-testid="column"]:has(.run-charts-btn-anchor) button {{
        background-color: {BRAND_PRIMARY} !important;
        color: white !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }}
    div[data-testid="column"]:has(.run-charts-btn-anchor) button:hover {{
        background-color: {BRAND_PRIMARY_DARK} !important;
        color: white !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }}
    div[data-testid="column"]:has(.run-charts-btn-anchor) button:focus,
    div[data-testid="column"]:has(.run-charts-btn-anchor) button:focus-visible,
    div[data-testid="column"]:has(.run-charts-btn-anchor) button:active {{
        box-shadow: none !important;
        outline: none !important;
        border: none !important;
    }}
    .run-charts-btn-anchor {{ display: none; }}
</style>
""", unsafe_allow_html=True)

if 'session' not in st.session_state:
    _loading_container = st.empty()
    _loading_container.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:60vh;gap:24px;">
        <img src="https://www.snowflake.com/wp-content/themes/snowflake/assets/img/snowflake-logo-blue.svg"
             style="width:160px;opacity:0.9;" onerror="this.style.display='none'"/>
        <div style="text-align:center;">
            <p style="font-size:1.2rem;font-weight:600;color:{BRAND_PRIMARY};margin-bottom:4px;">
                Snowflake 360 Self-Assessment
            </p>
            <p style="font-size:0.9rem;color:#888;margin:0;">Initialising application...</p>
        </div>
        <div style="width:320px;background:#e8edf2;border-radius:8px;overflow:hidden;height:8px;">
            <div style="height:8px;border-radius:8px;background:linear-gradient(90deg,{BRAND_PRIMARY},{BRAND_SECONDARY});
                        animation:loadbar 1.8s ease-in-out infinite;width:40%;">
            </div>
        </div>
        <style>
            @keyframes loadbar {{
                0%   {{ transform: translateX(-100%); }}
                100% {{ transform: translateX(900%); }}
            }}
        </style>
    </div>
    """, unsafe_allow_html=True)
    st.session_state.session = get_active_session()
    _loading_container.empty()
else:
    st.session_state.session = st.session_state.session

if 'analysis' not in st.session_state:
    st.session_state['analysis'] = {}

loaded_catalog = load_catalog()
menu_options = list(loaded_catalog.keys())

def _nav_key(label):
    safe = label
    for ch in ' ()&-/':
        safe = safe.replace(ch, '_')
    return f"nav_{safe}"

if 'selected_menu' not in st.session_state:
    st.session_state.selected_menu = "Home" if "Home" in menu_options else (menu_options[0] if menu_options else None)

if 'topic_nav_count' not in st.session_state:
    st.session_state.topic_nav_count = 0

if '_charts_completed' not in st.session_state:
    st.session_state._charts_completed = set()
if '_charts_running' not in st.session_state:
    st.session_state._charts_running = False
if 'rate_credit' not in st.session_state:
    st.session_state.rate_credit = float(_get_preference("rate_credit", "3.0"))
if 'rate_storage' not in st.session_state:
    st.session_state.rate_storage = float(_get_preference("rate_storage", "23.0"))
if 'rate_transfer' not in st.session_state:
    st.session_state.rate_transfer = float(_get_preference("rate_transfer", "0.0"))

_core_topics = [t for t in menu_options if t != "Home"]

with st.sidebar:
    st.markdown(
        f'<h2 style="color: {BRAND_PRIMARY}; margin-bottom: 5px; font-family: sans-serif;">Snowflake 360</h2>'
        f'<p style="color: {BRAND_SECONDARY}; font-size: 16px; margin-top: 0; font-family: sans-serif;">Self-Assessment</p>',
        unsafe_allow_html=True
    )

    if st.button("Home", key=_nav_key("Home"), use_container_width=True, type="secondary"):
        if st.session_state.selected_menu != "Home":
            st.session_state.topic_nav_count += 1
        st.session_state.selected_menu = "Home"

    st.markdown(
        f'<p style="color: {BRAND_PRIMARY}; font-size: 14px; font-weight: 600; '
        f'font-family: sans-serif; margin-bottom: 8px; margin-top: 16px;">'
        f'Core Topics</p>',
        unsafe_allow_html=True
    )

    for topic in _core_topics:
        _lbl = f"\u2705 {topic}" if topic in st.session_state._charts_completed else topic
        if st.button(_lbl, key=_nav_key(topic), use_container_width=True, type="secondary",
                     disabled=st.session_state._charts_running):
            if st.session_state.selected_menu != topic:
                st.session_state.topic_nav_count += 1
            st.session_state.selected_menu = topic
            _persist_rates()

    _sel_key = _nav_key(st.session_state.selected_menu) if st.session_state.selected_menu else ""
    if _sel_key:
        st.markdown(f"""<style>
            div[data-testid="stSidebar"] .st-key-{_sel_key} button {{
                background-color: {BRAND_ACCENT} !important;
                color: white !important;
                font-weight: 600 !important;
                border: 2px solid {BRAND_ACCENT} !important;
                box-shadow: none !important;
                outline: none !important;
            }}
            div[data-testid="stSidebar"] .st-key-{_sel_key} button:hover {{
                background-color: {BRAND_ACCENT} !important;
                color: white !important;
                border: 2px solid {BRAND_ACCENT} !important;
                opacity: 0.9;
                box-shadow: none !important;
                outline: none !important;
            }}
            div[data-testid="stSidebar"] .st-key-{_sel_key} button:focus,
            div[data-testid="stSidebar"] .st-key-{_sel_key} button:focus-visible,
            div[data-testid="stSidebar"] .st-key-{_sel_key} button:active {{
                background-color: {BRAND_ACCENT} !important;
                color: white !important;
                border: 2px solid {BRAND_ACCENT} !important;
                box-shadow: none !important;
                outline: none !important;
            }}
        </style>""", unsafe_allow_html=True)

current_selection = st.session_state.selected_menu
if current_selection not in menu_options and menu_options:
    current_selection = menu_options[0]
    st.session_state.selected_menu = current_selection

if not st.session_state.selected_menu or st.session_state.selected_menu == "Home":
    st.markdown(
        f'<h2 style="color: {BRAND_PRIMARY}; margin-bottom: 8px;">Welcome to Snowflake 360 Self-Assessment</h2>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<p style="font-size: 16px; color: {TEXT_SECONDARY}; margin-bottom: 24px;">'
        f'A comprehensive health-check of your Snowflake account across key operational areas. '
        f'Select a topic from the sidebar to begin your assessment.</p>',
        unsafe_allow_html=True
    )

    _features = [
        ("Database Management", "Analyse database storage, clustering efficiency, table lifespan, and churn patterns to optimise your data footprint."),
        ("Data Governance", "Review governance health scores, sensitivity heatmaps, policy inventory, tagging, privacy, and lineage."),
        ("Virtual Warehouses", "Monitor warehouse scaling, performance metrics, and identify right-sizing opportunities."),
        ("Access Control", "Audit authorisation, authentication, and network policies for security best practices."),
        ("Data Ingestion", "Evaluate bulk-load and Snowpipe ingestion costs, patterns, and efficiency."),
        ("Data Transformation", "Identify problematic queries, syntax issues, object structure, and workload shapes."),
        ("FinOps (lite)", "Gain visibility, control, and optimisation insights into your Snowflake spend."),
        ("Data Recovery & DevOps", "Assess data continuity management, Git adoption, CI/CD, and Dynamic Tables usage."),
    ]

    def _on_topic_cb_change():
        st.session_state['_all_charts_cb'] = False

    for _title, _desc in _features:
        _cb_col, _txt_col = st.columns([0.4, 9.6])
        with _cb_col:
            _ck = f"_cb_{_nav_key(_title)}"
            st.checkbox(
                _title, key=_ck, label_visibility="collapsed",
                disabled=st.session_state._charts_running,
                on_change=_on_topic_cb_change,
            )
        with _txt_col:
            _done_icon = f' <span style="color:{SUCCESS};">\u2705</span>' if _title in st.session_state._charts_completed else ''
            st.markdown(
                f'<div style="margin-top: 2px;">'
                f'<strong style="color: {BRAND_PRIMARY};">{_title}</strong>{_done_icon}<br>'
                f'<span style="color: {TEXT_SECONDARY}; font-size: 0.9rem;">{_desc}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown(
        '<p style="color: #C0392B; font-weight: 700; font-size: 1rem; margin-top: 16px;">'
        'Warning: Clicking on a Topic button on the left will kick off the analysis that can take over a minute to complete. '
        'Each Topic will also use AI to generate analysis based on those topics.'
        '</p>',
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.markdown(
        f'<h4 style="color: {BRAND_PRIMARY}; margin-bottom: 4px;">AI Model Configuration</h4>'
        f'<p style="color: {TEXT_SECONDARY}; font-size: 0.9rem; margin-bottom: 12px;">'
        f'Select the LLM used for Summary and Individual Analyser tabs.</p>',
        unsafe_allow_html=True
    )

    if "_available_models" not in st.session_state:
        st.session_state._available_models = []

    if "selected_llm" not in st.session_state:
        _persisted = _get_preference("selected_llm")
        st.session_state.selected_llm = _persisted if _persisted else "claude-sonnet-4-6"

    AVAILABLE_LLMS = st.session_state._available_models
    if not AVAILABLE_LLMS:
        AVAILABLE_LLMS = [st.session_state.selected_llm]

    _llm_col, _probe_col, _test_col, _all_col, _run_col = st.columns([3, 1.2, 0.6, 1.2, 1.2])
    with _llm_col:
        _chosen = st.selectbox(
            "Choose LLM",
            options=AVAILABLE_LLMS,
            index=AVAILABLE_LLMS.index(st.session_state.selected_llm)
                  if st.session_state.selected_llm in AVAILABLE_LLMS else 0,
            key="_llm_selector",
            label_visibility="collapsed",
        )
        if _chosen != st.session_state.selected_llm:
            st.session_state.selected_llm = _chosen
            _set_preference("selected_llm", _chosen)
        else:
            st.session_state.selected_llm = _chosen
    with _probe_col:
        if st.button("Probe Models", key="_probe_models_btn", type="secondary"):
            with st.spinner("Probing available AI models..."):
                _fetch_available_models.clear()
                _models = _fetch_available_models()
                if _models:
                    st.session_state._available_models = _models
                    if st.session_state.selected_llm not in _models:
                        st.session_state.selected_llm = "claude-sonnet-4-6" if "claude-sonnet-4-6" in _models else _models[0]
                        _set_preference("selected_llm", st.session_state.selected_llm)
                    st.experimental_rerun()
                else:
                    st.warning(
                        "No models found. An ACCOUNTADMIN must run "
                        "`CALL SNOWFLAKE.MODELS.CORTEX_BASE_MODELS_REFRESH();` "
                        "[Docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql#control-model-access)"
                    )
    with _test_col:
        if st.button("Test", key="_test_llm", type="secondary"):
            st.session_state._llm_test_running = True
    def _on_all_charts_change():
        if st.session_state.get('_all_charts_cb', False):
            for _t, _ in _features:
                st.session_state[f"_cb_{_nav_key(_t)}"] = False

    with _all_col:
        _all_charts = st.checkbox("All charts", key="_all_charts_cb",
                                  disabled=st.session_state._charts_running,
                                  on_change=_on_all_charts_change)
    with _run_col:
        st.markdown('<div class="run-charts-btn-anchor"></div>', unsafe_allow_html=True)
        _run_clicked = st.button("Run Charts", key="_run_charts_btn", type="primary",
                                 disabled=st.session_state._charts_running)

    st.markdown("---")
    st.markdown(
        f'<h4 style="color: {BRAND_PRIMARY}; margin-bottom: 4px;">Cost Rate Configuration</h4>'
        f'<p style="color: {TEXT_SECONDARY}; font-size: 0.9rem; margin-bottom: 12px;">'
        f'Set your Snowflake pricing rates to personalise cost estimates across the assessment.</p>',
        unsafe_allow_html=True
    )
    _rc1, _rc2, _rc3 = st.columns(3)
    with _rc1:
        st.session_state.rate_credit = st.number_input(
            "Compute Credit ($/credit)", min_value=0.0, step=0.25,
            value=float(st.session_state.rate_credit),
            key="_rate_credit_input", format="%.2f",
        )
    with _rc2:
        st.session_state.rate_storage = st.number_input(
            "Storage ($/TB/month)", min_value=0.0, step=1.0,
            value=float(st.session_state.rate_storage),
            key="_rate_storage_input", format="%.2f",
        )
    with _rc3:
        st.session_state.rate_transfer = st.number_input(
            "Data Transfer ($/GB)", min_value=0.0, step=0.01,
            value=float(st.session_state.rate_transfer),
            key="_rate_transfer_input", format="%.4f",
        )

    _run_status_ph = st.empty()

    _selected_topics = []
    if _all_charts:
        _selected_topics = [t for t, _ in _features]
    else:
        for _title, _ in _features:
            _ck = f"_cb_{_nav_key(_title)}"
            if st.session_state.get(_ck, False):
                _selected_topics.append(_title)

    st.session_state['_chart_sel'] = set(_selected_topics)

    _TOPIC_QUERY_DICTS = {
        "Database Management": ALL_DB_OVERVIEW_QUERIES,
        "Data Governance": ALL_DG_QUERIES,
        "Virtual Warehouses": _ALL_WH_QUERIES,
        "Access Control": _ALL_AC_QUERIES,
        "Data Ingestion": _ALL_INGESTION_QUERIES,
        "Data Transformation": _ALL_TF_QUERIES,
        "FinOps (lite)": _ALL_FINOPS_QUERIES,
        "Data Recovery & DevOps": _ALL_DEVOPS_QUERIES,
    }

    if _run_clicked and _selected_topics:
        _persist_rates()
        st.session_state._charts_running = True
        _session = st.session_state.get("session")

        _topic_counts = {}
        _per_topic_jobs = {}
        for _t in _selected_topics:
            _qdict = _TOPIC_QUERY_DICTS.get(_t, {})
            if _t == "Database Management":
                _needed = {k: v for k, v in _qdict.items() if k not in _DB_QUERY_CACHE}
            else:
                _needed = {k: v for k, v in _qdict.items() if k not in st.session_state}
            _n = len(_needed)
            _topic_counts[_t] = {"total": _n, "done": 0}
            if _n == 0:
                st.session_state._charts_completed.add(_t)
            else:
                _per_topic_jobs.setdefault(_t, []).extend([(_t, _k, _sql) for _k, _sql in _needed.items()])

        _all_jobs = []
        if _per_topic_jobs:
            _max_len = max(len(v) for v in _per_topic_jobs.values())
            for _idx in range(_max_len):
                for _t in _selected_topics:
                    _tl = _per_topic_jobs.get(_t, [])
                    if _idx < len(_tl):
                        _all_jobs.append(_tl[_idx])

        _total_q = sum(tc["total"] for tc in _topic_counts.values())
        _done_q = 0

        def _make_status_html(topic_counts, done_total, q_total, finished=False):
            _CT = BRAND_PRIMARY
            _CB = BRAND_SECONDARY
            overall_pct = int(done_total / q_total * 100) if q_total > 0 else 100
            if finished:
                hdr = (
                    f'<p style="color:{_CT};font-weight:600;font-size:0.9rem;margin:0 0 4px 0;">'
                    f'&#10003;&nbsp;All charts loaded!</p>'
                )
            else:
                hdr = (
                    f'<p style="color:{_CB};font-size:0.85rem;margin:0 0 8px 0;font-style:italic;">'
                    f'Please wait while the loading of your selected charts completes.</p>'
                    f'<p style="color:{_CT};font-weight:600;font-size:0.9rem;margin:0 0 4px 0;">'
                    f'Loading charts&hellip;&nbsp;&nbsp;{done_total}&nbsp;/&nbsp;{q_total} queries complete</p>'
                )
            overall_bar = (
                f'<div style="background:#e8edf2;border-radius:4px;height:6px;margin-bottom:12px;">'
                f'<div style="background:{_CB};width:{overall_pct}%;height:6px;border-radius:4px;">'
                f'</div></div>'
            )
            rows = ''
            for _ft, _ in _features:
                if _ft not in topic_counts:
                    continue
                tc = topic_counts[_ft]
                t_done = tc["done"]
                t_total = tc["total"]
                t_pct = int(t_done / t_total * 100) if t_total > 0 else 100
                is_done = t_done >= t_total
                lbl = f'&#10003;&nbsp;{_ft}' if is_done else _ft
                cnt_txt = f'{t_done}&nbsp;/&nbsp;{t_total}' if t_total > 0 else 'cached'
                rows += (
                    f'<div style="margin-bottom:6px;">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'font-size:0.8rem;color:{_CT};margin-bottom:2px;'
                    f'font-weight:{"600" if is_done else "400"};">'
                    f'<span>{lbl}</span>'
                    f'<span style="font-size:0.75rem;color:#888;">{cnt_txt}</span></div>'
                    f'<div style="background:#e8edf2;border-radius:4px;height:5px;">'
                    f'<div style="background:{_CB};width:{t_pct}%;height:5px;border-radius:4px;">'
                    f'</div></div></div>'
                )
            return f'<div style="margin:10px 0;">{hdr}{overall_bar}{rows}</div>'

        _run_status_ph.markdown(
            _make_status_html(_topic_counts, _done_q, _total_q),
            unsafe_allow_html=True,
        )

        if _all_jobs and _session:
            def _exec_query(_key, _sql):
                try:
                    return _key, _session.sql(_sql).to_pandas()
                except Exception:
                    return _key, _pd.DataFrame()

            with ThreadPoolExecutor(max_workers=len(_all_jobs)) as _exec:
                _job_meta = {
                    _exec.submit(_exec_query, _k, _sql): (_t, _k)
                    for _t, _k, _sql in _all_jobs
                }
                for _fut in as_completed(_job_meta):
                    _jt, _jk = _job_meta[_fut]
                    _rk, _df = _fut.result()
                    if _jt == "Database Management":
                        _DB_QUERY_CACHE[_rk] = _df
                    else:
                        st.session_state[_rk] = _df
                    _topic_counts[_jt]["done"] += 1
                    _done_q += 1
                    if _topic_counts[_jt]["done"] >= _topic_counts[_jt]["total"]:
                        st.session_state._charts_completed.add(_jt)
                        st.session_state[f"_topic_ready_{_nav_key(_jt)}"] = True
                    _run_status_ph.markdown(
                        _make_status_html(_topic_counts, _done_q, _total_q),
                        unsafe_allow_html=True,
                    )

        _run_status_ph.markdown(
            _make_status_html(_topic_counts, _total_q, _total_q, finished=True),
            unsafe_allow_html=True,
        )
        st.snow()
        _time.sleep(2)
        _run_status_ph.empty()
        st.session_state._charts_running = False
        st.experimental_rerun()

    if st.session_state.get("_llm_test_running"):
        st.session_state._llm_test_running = False
        _test_status = st.empty()
        _test_status.info(f"Testing **{st.session_state.selected_llm}**...")
        try:
            _test_result = st.session_state.session.sql(
                f"SELECT SNOWFLAKE.CORTEX.COMPLETE($${st.session_state.selected_llm}$$, 'Respond with only: OK')"
            ).collect()[0][0]
            _test_status.success(f"**{st.session_state.selected_llm}** is available and responding.")
        except Exception as _llm_err:
            _test_status.error(f"**{st.session_state.selected_llm}** is not available: {_llm_err}")

else:
    selected_menu = st.session_state.selected_menu
    _hdr_left, _hdr_right = st.columns([5, 2])
    with _hdr_left:
        st.markdown(
            f"<h3 style='margin-top: 0px; margin-bottom: 16px; font-size: 1.75rem; line-height: 1.2;'>{selected_menu}</h3>",
            unsafe_allow_html=True
        )
    with _hdr_right:
        if selected_menu in TOPIC_EXPORTERS and (
            st.session_state.get(f"_topic_ready_{_nav_key(selected_menu)}", False)
            or selected_menu in st.session_state._charts_completed
        ):
            try:
                st.markdown('<span class="telemetry-btn-anchor"></span>', unsafe_allow_html=True)
                _export_key = f"export_{_nav_key(selected_menu)}"
                _safe_topic = selected_menu.replace(" ", "_").replace("&", "and").replace("(", "").replace(")", "")
                _fname = f"Snowflake_Telemetry_{_safe_topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                if not st.session_state.get("_sf_account_name"):
                    st.session_state._sf_account_name = st.session_state.session.sql("SELECT CURRENT_ACCOUNT_NAME()").collect()[0][0]
                import base64 as _b64mod
                _html_bytes = TOPIC_EXPORTERS[selected_menu](st.session_state._sf_account_name).encode("utf-8")
                _b64 = _b64mod.b64encode(_html_bytes).decode("ascii")
                _dl_html = (
                    "<style>body{margin:0;padding:2px 0}"
                    "a{display:inline-block;padding:5px 14px;"
                    "background:#003D73;color:#fff!important;"
                    "border-radius:4px;text-decoration:none;"
                    "font:500 13px -apple-system,sans-serif;cursor:pointer}"
                    "a:hover{background:#11567F}</style>"
                    f'<a href="data:text/html;base64,{_b64}" download="{_fname}">'
                    "Export Telemetry for Printing</a>"
                )
                components.html(_dl_html, height=36)
            except Exception as _exp_err:
                st.error(f"Export unavailable: {_exp_err}")

    if selected_menu in loaded_catalog:
        available_tabs = [m['tab_name'] for m in loaded_catalog[selected_menu]]
        if available_tabs:
            _is_first_visit = not st.session_state.get(f"_topic_ready_{_nav_key(selected_menu)}", False)
            if _is_first_visit:
                st.session_state[f"_topic_ready_{_nav_key(selected_menu)}"] = True
                st.info("Loading topic data — this may take a moment on first visit.", icon="⏳")
            _cycle = st.session_state.topic_nav_count % 20
            for _ in range(_cycle):
                st.empty()
            tabs_display = st.tabs(available_tabs)
            for idx, tab_name in enumerate(available_tabs):
                with tabs_display[idx]:
                    metric_info = loaded_catalog[selected_menu][idx]
                    component_fn = metric_info.get('fn', '')
                    try:
                        if component_fn and '.' in component_fn:
                            method_name = component_fn.split('.')[-1]
                            handler = get_analysis_comp_handler()
                            if hasattr(handler, method_name):
                                getattr(handler, method_name)()
                            else:
                                st.info(f"Component `{method_name}` not yet implemented.")
                        else:
                            st.info(f"No component configured for {tab_name}.")
                    except Exception as e:
                        st.markdown(
                            f'<div style="background-color: #FDEDEC; border-left: 6px solid {ERROR}; padding: 10px; margin-top: 10px; margin-bottom: 10px;">'
                            f'Error loading {tab_name}: {str(e)}</div>',
                            unsafe_allow_html=True
                        )
            if selected_menu not in st.session_state._charts_completed:
                st.session_state._charts_completed.add(selected_menu)

st.markdown(global_settings.APP_VERSION_FOOTER, unsafe_allow_html=True)

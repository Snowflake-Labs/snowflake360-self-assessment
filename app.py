import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from snowflake.snowpark.context import get_active_session
import core as cr
from components.local import load_catalog
from components.Analysis.invoke_metrics_comps import get_analysis_comp_handler
from core.config.design_tokens import (
    BRAND_PRIMARY, BRAND_SECONDARY,
    SURFACE_ALT, SURFACE_BASE,
    TEXT_SECONDARY, TEXT_HEADING,
    TEXT_INVERSE,
    ERROR,
    CSS_CUSTOM_PROPERTIES,
)
from core.export_collectors import TOPIC_EXPORTERS
from components.Database_Management.db_overview import _query_cache as _db_cache

global_settings = cr.config

st.set_page_config(
    page_title="Snowflake 360 Self-Assessment",
    layout="wide",
    initial_sidebar_state="expanded"
)

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


_EXPORT_SENTINELS = {
    "Database Management":    lambda: bool(_db_cache),
    "Virtual Warehouses":     lambda: "wh_fleet_data" in st.session_state,
    "Access Control":         lambda: "auth_role_hygiene" in st.session_state,
    "Data Ingestion":         lambda: "di_copy_analysis" in st.session_state,
    "Data Transformation":    lambda: "tf_overview" in st.session_state,
    "FinOps (lite)":          lambda: "fv_exec_forecast" in st.session_state,
    "Data Recovery & DevOps": lambda: "rd_dcm_adoption" in st.session_state,
    "Data Governance":        lambda: "dg_health_score_data" in st.session_state,
}

def _export_ready(topic: str) -> bool:
    checker = _EXPORT_SENTINELS.get(topic)
    return bool(checker()) if checker else False

if 'selected_menu' not in st.session_state:
    st.session_state.selected_menu = "Home" if "Home" in menu_options else (menu_options[0] if menu_options else None)

if 'topic_nav_count' not in st.session_state:
    st.session_state.topic_nav_count = 0

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

    for topic in [t for t in menu_options if t != "Home"]:
        if st.button(topic, key=_nav_key(topic), use_container_width=True, type="secondary"):
            if st.session_state.selected_menu != topic:
                st.session_state.topic_nav_count += 1
            st.session_state.selected_menu = topic

    _sel_key = _nav_key(st.session_state.selected_menu) if st.session_state.selected_menu else ""
    if _sel_key:
        st.markdown(f"""<style>
            div[data-testid="stSidebar"] .st-key-{_sel_key} button {{
                background-color: {BRAND_SECONDARY} !important;
                color: white !important;
                font-weight: 600 !important;
                border: 2px solid {BRAND_SECONDARY} !important;
            }}
            div[data-testid="stSidebar"] .st-key-{_sel_key} button:hover {{
                background-color: {BRAND_SECONDARY} !important;
                color: white !important;
                border: 2px solid {BRAND_SECONDARY} !important;
                opacity: 0.9;
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
        ("Virtual Warehouses", "Monitor warehouse scaling, performance metrics, and identify right-sizing opportunities."),
        ("Data Ingestion", "Evaluate bulk-load and Snowpipe ingestion costs, patterns, and efficiency."),
        ("FinOps (lite)", "Gain visibility, control, and optimisation insights into your Snowflake spend."),
        ("Data Governance", "Review governance health scores, sensitivity heatmaps, policy inventory, tagging, privacy, and lineage."),
        ("Access Control", "Audit authorisation, authentication, and network policies for security best practices."),
        ("Data Transformation", "Identify problematic queries, syntax issues, object structure, and workload shapes."),
        ("Data Recovery & DevOps", "Assess data continuity management, Git adoption, CI/CD, and Dynamic Tables usage."),
    ]

    items_html = "".join(
        f'<li style="margin-bottom: 16px;">'
        f'<strong style="color: {BRAND_PRIMARY};">{title}</strong><br>'
        f'<span style="color: {TEXT_SECONDARY};">{desc}</span>'
        f'</li>'
        for title, desc in _features
    )
    st.markdown(
        f'<ul style="list-style-type: disc; padding-left: 24px; margin-top: 8px;">'
        f'{items_html}'
        f'</ul>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<p style="color: #C0392B; font-weight: 700; font-size: 1rem; margin-top: 16px;">'
        'Warning: Clicking on a Topic button on the left will kick off the analysis that can take over a minute to complete'
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

    AVAILABLE_LLMS = [
        "claude-3-7-sonnet",
        "claude-3-5-sonnet",
        "claude-4-sonnet",
        "claude-4-opus",
        "deepseek-r1",
        "llama3.1-70b",
        "llama3.1-405b",
        "llama3.3-70b",
        "llama4-maverick",
        "llama4-scout",
        "mistral-large2",
        "openai-gpt-4.1",
        "openai-o4-mini",
        "snowflake-llama-3.3-70b",
    ]

    if "selected_llm" not in st.session_state:
        st.session_state.selected_llm = "claude-3-7-sonnet"

    _llm_col, _test_col = st.columns([3, 1])
    with _llm_col:
        _chosen = st.selectbox(
            "Choose LLM",
            options=AVAILABLE_LLMS,
            index=AVAILABLE_LLMS.index(st.session_state.selected_llm)
                  if st.session_state.selected_llm in AVAILABLE_LLMS else 0,
            key="_llm_selector",
            label_visibility="collapsed",
        )
        st.session_state.selected_llm = _chosen
    with _test_col:
        if st.button("Test", key="_test_llm", type="secondary"):
            st.session_state._llm_test_running = True

    if st.session_state.get("_llm_test_running"):
        st.session_state._llm_test_running = False
        _test_status = st.empty()
        _test_status.info(f"Testing **{st.session_state.selected_llm}**...")
        try:
            _test_result = st.session_state.session.sql(
                f"SELECT SNOWFLAKE.CORTEX.AI_COMPLETE($${st.session_state.selected_llm}$$, 'Respond with only: OK')"
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
        if selected_menu in TOPIC_EXPORTERS and _export_ready(selected_menu):
            st.markdown('<span class="telemetry-btn-anchor"></span>', unsafe_allow_html=True)
            _safe_topic = selected_menu.replace(" ", "_").replace("&", "and").replace("(", "").replace(")", "")
            _fname = f"Snowflake_Telemetry_{_safe_topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            def _gen_export(menu=selected_menu, fname=_fname):
                _acct = st.session_state.session.sql("SELECT CURRENT_ACCOUNT_NAME()").collect()[0][0]
                return TOPIC_EXPORTERS[menu](_acct).encode()
            st.download_button(
                label="Export Telemetry for Printing",
                data=_gen_export,
                file_name=_fname,
                mime="text/html",
                key=f"export_{_nav_key(selected_menu)}",

            )

    if selected_menu in loaded_catalog:
        available_tabs = [m['tab_name'] for m in loaded_catalog[selected_menu]]
        if available_tabs:
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
                                with st.spinner(f"Loading {tab_name}..."):
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

st.markdown(global_settings.APP_VERSION_FOOTER, unsafe_allow_html=True)

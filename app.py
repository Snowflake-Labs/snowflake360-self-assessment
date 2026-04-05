import streamlit as st
from snowflake.snowpark.context import get_active_session
import core as cr
from components.local import load_catalog
from components.Analysis.invoke_metrics_comps import get_analysis_comp_handler

global_settings = cr.config

st.set_page_config(
    page_title="Snowflake 360 Self-Assessment",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(global_settings.MAIN_MARKDOWN_BODY, unsafe_allow_html=True)
st.markdown(global_settings.DEFAULT2_MARKDOWN_BODY, unsafe_allow_html=True)

if 'session' not in st.session_state:
    st.session_state.session = get_active_session()

if 'analysis' not in st.session_state:
    st.session_state['analysis'] = {}

loaded_catalog = load_catalog()
menu_options = [k for k in loaded_catalog.keys() if k != "Home"]

with st.sidebar:
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        padding-top: 0px !important;
    }
    [data-testid="stSidebar"][aria-expanded="true"] {
        min-width: 320px !important;
        max-width: 320px !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 0px !important;
        margin-top: -29px !important;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0px !important;
    }
    section[data-testid="stSidebar"] .element-container:first-of-type {
        margin-top: -37px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<h2 style="color: #1E3F66; margin-bottom: 5px;">Snowflake 360</h2>'
        '<p style="color: #528AAE; font-size: 16px; margin-top: 0;">Self-Assessment</p>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <style>
    div[data-testid="stRadio"] > label { display: none; }
    div[data-testid="stRadio"] > div { gap: 0px; }
    div[data-testid="stRadio"] > div > label {
        padding: 3px 12px;
        font-size: 16px;
        cursor: pointer;
        border-radius: 4px;
        margin: 0;
    }
    div[data-testid="stRadio"] > div > label:hover {
        background-color: #e6f3ff;
    }
    div[data-testid="stRadio"] > div > label[data-checked="true"] {
        background-color: #0C98DC;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

    if 'selected_menu' not in st.session_state:
        st.session_state.selected_menu = menu_options[0] if menu_options else None

    current_selection = st.session_state.selected_menu
    if current_selection not in menu_options and menu_options:
        current_selection = menu_options[0]
        st.session_state.selected_menu = current_selection

    selected = st.radio(
        "Navigation",
        options=menu_options,
        index=menu_options.index(current_selection) if current_selection in menu_options else 0,
        label_visibility="collapsed",
    )

    if selected != st.session_state.selected_menu:
        st.session_state.selected_menu = selected
        st.rerun()

if not st.session_state.selected_menu:
    st.markdown("## Welcome to Snowflake 360 Self-Assessment")
    st.markdown("Select a topic from the sidebar to begin.")
else:
    selected_menu = st.session_state.selected_menu
    st.markdown(
        f"<h3 style='margin-top: 0px; margin-bottom: 16px; font-size: 1.75rem; line-height: 1.2;'>{selected_menu}</h3>",
        unsafe_allow_html=True
    )

    if selected_menu in loaded_catalog:
        available_tabs = [m['tab_name'] for m in loaded_catalog[selected_menu]]
        if available_tabs:
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
                            f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; margin-top: 10px; margin-bottom: 10px;">'
                            f'Error loading {tab_name}: {str(e)}</div>',
                            unsafe_allow_html=True
                        )

st.markdown(global_settings.APP_VERSION_FOOTER, unsafe_allow_html=True)

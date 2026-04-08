import streamlit as st
import pandas as pd
from .dcm_adoption import comp_dcm_adoption
from .git_integration import comp_git_integration
from .cicd_automation import comp_cicd_automation
from .orchestration_patterns import comp_orchestration_patterns
from .devops_maturity_summary import comp_devops_maturity_summary
from ._all_devops_queries import _ALL_DEVOPS_QUERIES


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_devops_queries(progress_bar=None, status_text=None):
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_DEVOPS_QUERIES.items() if k not in st.session_state}
    if not needed:
        return
    total = len(needed)
    completed = 0
    for k, sql in needed.items():
        key, df, err = _run_query_thread(session, k, sql)
        st.session_state[key] = df
        completed += 1
        if progress_bar is not None:
            progress_bar.progress(completed / total)
        if status_text is not None:
            status_text.text(f"Loading data... ({completed}/{total} queries)")


def comp_recovery_devops_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in _ALL_DEVOPS_QUERIES)
        if not all_cached:
            status_ph.markdown(
                '<p style="color: #003D73; font-weight: 600;">Loading Data Recovery & DevOps data...</p>',
                unsafe_allow_html=True)
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_all_devops_queries(progress_bar=progress_bar_widget, status_text=status_ph)
            progress_ph.empty()
            status_ph.empty()
        else:
            _prefetch_all_devops_queries()

        tab_dcm, tab_git, tab_cicd, tab_orch, tab_summary = st.tabs([
            "Database Change Management (DCM) Adoption",
            "Git Integration Usage",
            "CI/CD Tool Automation",
            "Orchestration Patterns",
            "DevOps Maturity Summary"
        ])

        with tab_dcm:
            comp_dcm_adoption()

        with tab_git:
            comp_git_integration()

        with tab_cicd:
            comp_cicd_automation()

        with tab_orch:
            comp_orchestration_patterns()

        with tab_summary:
            comp_devops_maturity_summary()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px;">'
                    f'Component Error: {str(e)}</div>', unsafe_allow_html=True)

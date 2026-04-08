import streamlit as st
import pandas as pd
from .finops_visibility import comp_finops_visibility
from .finops_control import comp_finops_control
from .finops_optimization import comp_finops_optimization
from ._all_finops_queries import _ALL_FINOPS_QUERIES


def _run_query_thread(session, key, sql):
    try:
        return key, session.sql(sql).to_pandas(), None
    except Exception as e:
        return key, pd.DataFrame(), e


def _prefetch_all_finops_queries(progress_bar=None, status_text=None):
    session = st.session_state.get("session")
    if not session:
        return
    needed = {k: sql for k, sql in _ALL_FINOPS_QUERIES.items() if k not in st.session_state}
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


def comp_finops_overview(entry_actions=None):
    try:
        status_ph = st.empty()
        progress_ph = st.empty()
        all_cached = all(k in st.session_state for k in _ALL_FINOPS_QUERIES)
        if not all_cached:
            status_ph.markdown(
                '<p style="color: #003D73; font-weight: 600;">Loading FinOps data...</p>',
                unsafe_allow_html=True)
            progress_bar_widget = progress_ph.progress(0)
            _prefetch_all_finops_queries(progress_bar=progress_bar_widget, status_text=status_ph)
            progress_ph.empty()
            status_ph.empty()
        else:
            _prefetch_all_finops_queries()
        tab_visibility, tab_control, tab_optimization = st.tabs([
            "Visibility",
            "Control",
            "Optimisation"
        ])

        with tab_visibility:
            comp_finops_visibility()

        with tab_control:
            comp_finops_control()

        with tab_optimization:
            comp_finops_optimization()

    except Exception as e:
        st.markdown(f'<div style="background-color: #FDEDEC; border-left: 6px solid #E74C3C; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

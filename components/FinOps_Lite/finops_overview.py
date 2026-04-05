import streamlit as st
from .finops_visibility import comp_finops_visibility
from .finops_control import comp_finops_control
from .finops_optimization import comp_finops_optimization


def comp_finops_overview(entry_actions=None):
    """FinOPS (Lite) Overview Component

    Provides sub-tabs for:
    - Visibility: Cost analytics, forecasting, and breakdown analysis
    - Control: Resource monitors, warehouse controls, and budget management
    - Optimisation: Query patterns and optimization recommendations

    Args:
        entry_actions: Optional entry actions for the component
    """
    try:
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
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

import streamlit as st
from .dcm_adoption import comp_dcm_adoption
from .git_integration import comp_git_integration
from .cicd_automation import comp_cicd_automation
from .declarative_pipeline import comp_declarative_pipeline


def comp_recovery_devops_overview(entry_actions=None):
    """Data Recovery & DevOps Overview Component

    Provides an overview of data recovery and DevOps practices with sub-tabs:
    - Database Change Management (DCM) Adoption
    - Git Integration Usage
    - CI/CD Tool Automation
    - Declarative Pipeline Adoption (Dynamic Tables)

    Args:
        entry_actions: Optional entry actions for the component
    """
    try:
        tab_dcm, tab_git, tab_cicd, tab_pipeline = st.tabs([
            "Database Change Management (DCM) Adoption",
            "Git Integration Usage",
            "CI/CD Tool Automation",
            "Declarative Pipeline Adoption (Dynamic Tables)"
        ])

        with tab_dcm:
            comp_dcm_adoption()

        with tab_git:
            comp_git_integration()

        with tab_cicd:
            comp_cicd_automation()

        with tab_pipeline:
            comp_declarative_pipeline()

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Component Error: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

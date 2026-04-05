"""
Access Control Overview Component

Provides a unified overview with sub-tabs for Authorization,
Authentication, and Network Rules & Policies.
"""

import streamlit as st
from .authorization import comp_authorization
from .authentication import comp_authentication
from .network_policies import comp_network_policies


def comp_access_control_overview(entry_actions=None):
    """
    Access Control Overview Component

    Renders sub-tabs for:
    - Authorization
    - Authentication
    - Network Rules & Policies

    Args:
        entry_actions: Optional callback actions on component entry
    """
    try:
        sub_tab_names = [
            "Authorization",
            "Authentication",
            "Network Rules & Policies"
        ]
        sub_tabs = st.tabs(sub_tab_names)

        with sub_tabs[0]:
            comp_authorization()

        with sub_tabs[1]:
            comp_authentication()

        with sub_tabs[2]:
            comp_network_policies()

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Access Control Overview: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

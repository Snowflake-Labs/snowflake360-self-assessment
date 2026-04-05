"""
Warehouse Analyzer - delegates to the Warehouse Cortex Operations module
which already performs live Cortex AI analysis of warehouse configurations
and usage patterns.
"""

import streamlit as st


def comp_warehouse_analysis(entry_actions=None):
    st.markdown("### Virtual Warehouse Analyzer")
    st.markdown(
        "Warehouse AI analysis is available in the **Warehouse Cortex Operations** tab. "
        "That module performs comprehensive live Cortex analysis including per-warehouse "
        "and portfolio-level assessments with time-series data."
    )

    st.info(
        "Navigate to the **Warehouse Cortex Operations** tab for full AI-powered "
        "warehouse analysis with model selection, per-warehouse deep dives, "
        "and portfolio consolidation."
    )

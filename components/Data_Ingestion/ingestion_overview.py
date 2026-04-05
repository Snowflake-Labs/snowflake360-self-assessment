import streamlit as st
from .highest_cost import comp_highest_cost
from .bulk_load_analysis import comp_bulk_load_analysis
from .snowpipe_analysis import comp_snowpipe_analysis


def _render_overview_content():
    """Render the core data ingestion overview content."""
    st.markdown("### Data Ingestion Overview")

    st.markdown('<div style="background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                'ℹ️&nbsp;&nbsp;<strong>Data Ingestion</strong> provides comprehensive insights into your data '
                'ingestion patterns, costs, and optimization opportunities.<br><br>'
                'Navigate through the tabs to explore:<br>'
                '- <strong>Data Ingestion Analyzer</strong>: AI-powered analysis of ingestion patterns<br>'
                '- <strong>Highest Cost</strong>: Identify the most expensive ingestion operations<br>'
                '- <strong>Bulk Load (COPY INTO) Analysis</strong>: Analysis of bulk load operations<br>'
                '- <strong>Snowpipe Analysis</strong>: Cost vs. Volume analysis for Snowpipe'
                '</div>', unsafe_allow_html=True)


def comp_ingestion_overview(entry_actions=None):
    """
    Data Ingestion Overview Component

    Renders sub-tabs for:
    - Overview: High-level overview of the Data Ingestion module
    - Highest Cost
    - Bulk Load (COPY INTO) Analysis
    - Snowpipe Analysis (Cost vs. Volume)

    Args:
        entry_actions: Optional callback actions on component entry
    """
    try:
        sub_tab_names = [
            "Highest Cost",
            "Bulk Load (COPY INTO) Analysis",
            "Snowpipe Analysis (Cost vs. Volume)"
        ]
        sub_tabs = st.tabs(sub_tab_names)

        with sub_tabs[0]:
            comp_highest_cost()

        with sub_tabs[1]:
            comp_bulk_load_analysis()

        with sub_tabs[2]:
            comp_snowpipe_analysis()

    except Exception as e:
        st.markdown(f'<div style="background-color: #f8d7da; border-left: 6px solid #dc3545; padding: 10px; text-align:left; margin-top: 10px; margin-bottom: 10px;">'
                    f'🛑&nbsp;&nbsp;Error loading Data Ingestion Overview: {str(e)}'
                    f'</div>', unsafe_allow_html=True)

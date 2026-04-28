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

import os


def get_project_root():
    try:
        current_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(current_path, os.pardir, os.pardir))
    except (TypeError, ValueError):
        return os.getcwd()


# App settings
APP_VERSION = "1.0.0"
PROJECT_ROOT = get_project_root()
APP_SCHEMA_NAME = 'SNOWFLAKE.ACCOUNT_USAGE'
# Debug settings
APP_NAME: str = "Snowflake 360 Self-Assessment"

MAIN_MARKDOWN_BODY: str = '''
    <style>
        /* Ensure wide layout is maintained throughout the app */
        section.main > div,
        .main .block-container,
        .stApp > div:first-child,
        [data-testid="stAppViewContainer"] > div:first-child,
        section[data-testid="stMain"] > div:first-child {
            max-width: 100% !important;
            width: 100% !important;
        }

        .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        /* Force wide layout from the start */
        body {
            margin: 0 !important;
            width: 100% !important;
        }

        .stApp {
            max-width: 100% !important;
            width: 100% !important;
        }
    </style>
    <script>
        // Ensure layout is applied immediately
        document.addEventListener('DOMContentLoaded', function() {
            const containers = document.querySelectorAll('.main .block-container, section.main > div');
            containers.forEach(container => {
                container.style.maxWidth = '100%';
                container.style.width = '100%';
            });
        });
    </script>
'''

ANALYSIS_MARKDOWN_BODY: str = '''
    <style>
        section.main > div {
            max-width: 100% !important;  /* Set to full width with !important */
        }
        /* Ensure the container uses full width */
        .main .block-container {
            max-width: 100% !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
    </style>
'''

DEFAULT2_MARKDOWN_BODY: str = '''
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@300;400;600;700&family=Source+Code+Pro:wght@400&display=swap');

    /* Global Typography Styles */
    .app_title, h1.app_title {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #003D73 !important;
        font-size: 48px !important;
        font-weight: bold !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
    }

    /* Target Streamlit's markdown elements */
    .stMarkdown h1.app_title {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #003D73 !important;
        font-size: 48px !important;
        font-weight: bold !important;
    }

    .header01 {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #003D73 !important;
        font-size: 36px !important;
        font-weight: normal !important;
    }

    .header02 {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #11567F !important;
        font-size: 32px !important;
        font-weight: normal !important;
    }

    .header03 {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #29B5E8 !important;
        font-size: 28px !important;
        font-weight: normal !important;
    }

    .header04 {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #75C2D8 !important;
        font-size: 24px !important;
        font-weight: normal !important;
    }

    .body_text {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #262730 !important;
        font-size: 20px !important;
        font-weight: normal !important;
    }

    .code_text {
        font-family: 'Source Code Pro', monospace !important;
        color: #262730 !important;
        font-size: 12px !important;
        font-weight: normal !important;
    }

    /* Apply custom styles to Streamlit built-in components */

    /* st.title styling - use app_title style */
    [data-testid="stMarkdownContainer"] h1:not(.app_title),
    .stMarkdown h1:not(.app_title),
    h1:not(.app_title) {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #003D73 !important;
        font-size: 48px !important;
        font-weight: bold !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
    }

    /* st.header styling - use header01 style */
    [data-testid="stMarkdownContainer"] h2,
    .stMarkdown h2,
    h2 {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #003D73 !important;
        font-size: 36px !important;
        font-weight: normal !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
    }

    /* st.subheader styling - use header02 style */
    [data-testid="stMarkdownContainer"] h3,
    .stMarkdown h3,
    h3 {
        font-family: 'Source Sans Pro', sans-serif !important;
        color: #11567F !important;
        font-size: 32px !important;
        font-weight: normal !important;
        margin: 0 !important;
        padding: 5px !important;
        line-height: 1.2 !important;
    }

    /* Existing Streamlit component styles */
    [data-testid="stMetricValue"] {
        font-size: 25px;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        padding: 5px;
    }

    [data-testid="stSidebarHeader"] {
        padding: 0px;
    }

    /* Sidebar menu width - explicitly set */
    section[data-testid="stSidebar"] {
        width: 320px !important;
        min-width: 320px !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        width: 320px !important;
    }

    .block-container {
    padding: 20px
    }

    /* Button alignment */
    .button-container {
        display: flex;
        justify-content: flex-end;
        margin-top: 20px;
    }

    /* Reduce gap between labels and input fields */
    [data-testid="stMarkdownContainer"] p {
        margin-bottom: 0px !important;
    }

    /* Adjust input field spacing */
    [data-testid="stTextInput"],
    [data-testid="stSelectbox"],
    [data-testid="stNumberInput"] {
        margin-top: 0px !important;
    }

    /* Darker gray background for input fields */
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stNumberInput"] input {
        # background-color: #EFEFEF !important;
        background-color: #F0F2F6 !important;
    }

    /* Section headers with underline */
    .section-header {
        font-family: 'Source Sans Pro', sans-serif !important;
        # color: #003D73 !important;
        color: #0055A5 !important;
        font-size: 28px !important;
        font-weight: 600 !important;
        padding-bottom: 2px !important;
        line-height: 1.0 !important;
        # border-bottom: 2px solid #003D73 !important;
        border-bottom: 2px solid #0055A5 !important;
        margin-bottom: 20px !important;
        margin-top: 10px !important;
    }

    /* Reduce gap between input field rows */
    .stTextInput, .stSelectbox, .stNumberInput {
        margin-bottom: 0px !important;
    }

    /* Reduce gap between column containers */
    [data-testid="column"] {
        padding-bottom: 0px !important;
    }

    </style>
'''

METRIC_CONTAINER_MARKDOWN_BODY: str = '''
    <style>
    [data-testid="stMetricValue"] {
        font-size: 25px;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        padding: 5px;
    }

    .block-container {
    padding: 20px
    }

    </style>
'''

APP_VERSION_FOOTER = f"""
    <style>
    footer {{
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        color: #666666;
        text-align: right;
        padding: 2px 10px 2px;
    }}
    </style>
    <footer>
        ver: {APP_VERSION}
    </footer>
    """



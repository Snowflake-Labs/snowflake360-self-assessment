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

from math import isnan
import base64

import pandas as pd
import core as cr
import streamlit as st


# Function to format values to a percentage with a % sign
def convert_to_percentage(value):
    if isinstance(value, (int, float)):
        value = value * 100
        return f"{value:.1f}%"
    return value  # Non-numeric values remain unchanged


# Function to calculate percentages
def calculate_percentage(value, total):
    return convert_to_percentage(float(value) / total)


def format_number(value):
    if isinstance(value, (int, float)):
        if value < 100 and value % 1 != 0:
            new_value = f"{value:,.1f}"
        else:
            new_value = f"{value:,.0f}"

        # Cannot use isnan because it's a literal and generates an exception
        if new_value == "None" or new_value == "nan":
            return None
        return new_value

    return value


def apply_color(val, thresholds, colors):
    """Apply background color based on value ranges and provided thresholds, if the value is Nan the color is grey.
    @param val: value of the cell if number or float type
    @param thresholds: range of values use to apply background color
    @param colors: range of colors use to apply background color
    @return: the background color
    """
    if pd.isna(val):
        return f'background-color: {cr.config.component_settings.GREY}; color: {cr.config.component_settings.GREY}'  # Grey for None values

    for i, threshold in enumerate(thresholds):
        if val < threshold:
            return f'background-color: {colors[i]}'

    return f'background-color: {colors[-1]}'


general_map = {
    'wh_size': {
        'X-SMALL': 1,
        'SMALL': 2,
        'MEDIUM': 3,
        'LARGE': 4,
        'X-LARGE': 5,
        '2X-LARGE': 6,
        '3X-LARGE': 7,
        '4X-LARGE': 8,
        '5X-LARGE': 9,
        '6X-LARGE': 10
    },
    'database': {
        'Estimated Annual Cost': 1,
        'Total GB': 2,
        'Active GB': 3,
        '% Active': 4,
        'Time Travel GB': 5,
        '% Time Travel': 6,
        'Avg Retention Days': 7,
        'Fail-Safe GB': 8,
        '% Fail-Safe': 9,
        'Tables': 10,
        'Table Instances': 11
    },
    'daily_io_summary': {
        'Active EAC': 1,
        'Active GB': 2,
        'EAC': 3,
        'Exec Hours': 4,
        'Write GB': 5,
        'Write % of Active': 6,
        'Scan GB': 7,
        'Scan % of Active': 8,
        'Spill GB': 9,
        'Spill % of Active': 10,
        'Network GB': 11,
        'Network % of Active': 12
    }

}


def order_by_mapping(unordered_sizes, map_flag):
    map_type = general_map.get(map_flag, {})
    ordered_sizes = sorted(unordered_sizes, key=lambda size: map_type[size])
    return ordered_sizes


def on_change_pivot(key: str):
    st.session_state.is_first_pivot[f"is_first{key}"] = True


def prepare_markdown_text(raw_text):
    """
    Clean raw CLEANED_OUTPUT text by removing wrapping quotes and unescaping.

    Args:
        raw_text: Raw CLEANED_OUTPUT value from the database

    Returns:
        str: Cleaned markdown text ready for export
    """
    text = str(raw_text)
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].replace('\\"', '"').replace('\\n', '\n')
    return text


def render_report_download(output_text, file_prefix, label, dl_key):
    """
    Render a report-format dropdown and download link using the green
    gradient bar style.  The CSS :has() selector toggles between PDF and
    MD download links based on the <select> value — no JavaScript needed.

    Args:
        output_text: Cleaned markdown content for the report
        file_prefix: File name prefix without extension
        label: Label for the download link
        dl_key: Unique key prefix for CSS element IDs
    """
    uid = dl_key.replace('_', '-')

    md_b64 = base64.b64encode(output_text.encode('utf-8')).decode('utf-8')

    pdf_link = ''
    try:
        from services.Common.report_export_service import markdown_to_pdf_bytes
        pdf_bytes = markdown_to_pdf_bytes(output_text)
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
        pdf_link = (
            f'<a class="dl-btn dl-pdf" '
            f'href="data:application/pdf;base64,{pdf_b64}" '
            f'download="{file_prefix}.pdf">{label}</a>'
        )
    except Exception as e:
        pdf_link = (
            f'<span class="dl-btn dl-pdf" '
            f'style="background:#E74C3C !important;cursor:default;">'
            f'PDF unavailable: {str(e)}</span>'
        )

    md_link = (
        f'<a class="dl-btn dl-md" '
        f'href="data:text/markdown;base64,{md_b64}" '
        f'download="{file_prefix}.md">{label}</a>'
    )

    html = f'''
    <style>
        .rpt-{uid} {{
            background: linear-gradient(135deg, #f0f7fb 0%, #f0f7fb 100%);
            border-radius: 8px;
            padding: 14px 28px;
            margin-top: 10px;
            margin-bottom: 10px;
            display: flex;
            align-items: flex-end;
            gap: 18px;
            border: 1px solid #75C2D8;
        }}
        .rpt-{uid} .field-group {{
            display: flex;
            flex-direction: column;
            margin-left: -10px;
        }}
        .rpt-{uid} .field-label {{
            font-size: 12px;
            font-weight: 600;
            color: #003D73;
            margin-bottom: 5px;
        }}
        .rpt-{uid} select {{
            background-color: #fff;
            border: 1px solid #75C2D8;
            border-radius: 4px;
            padding: 7px 30px 7px 10px;
            font-size: 14px;
            color: #333;
            appearance: auto;
            cursor: pointer;
            outline: none;
        }}
        .rpt-{uid} select:focus {{
            border-color: #29B5E8;
            box-shadow: 0 0 0 2px rgba(41, 181, 232, 0.2);
        }}
        .rpt-{uid} .dl-btn {{
            display: none;
            background: linear-gradient(180deg, #29B5E8 0%, #11567F 100%);
            color: white !important;
            border: none;
            border-radius: 6px;
            padding: 5px 52px;
            font-size: 15px;
            font-weight: 600;
            letter-spacing: 0.3px;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
            text-decoration: none;
            position: relative;
            top: -2px;
        }}
        .rpt-{uid} .dl-btn:hover {{
            background: linear-gradient(180deg, #1A7DA8 0%, #003D73 100%);
            box-shadow: 0 2px 8px rgba(0, 61, 115, 0.35);
        }}
        .rpt-{uid} .dl-btn:active {{
            transform: scale(0.98);
        }}
        .rpt-{uid}:has(option[value="PDF"]:checked) .dl-pdf {{ display: inline-block; }}
        .rpt-{uid}:has(option[value="MD"]:checked) .dl-md {{ display: inline-block; }}
    </style>
    <div class="rpt-{uid}">
        <div class="field-group">
            <span class="field-label">Report Format</span>
            <select>
                <option value="PDF" selected>PDF</option>
                <option value="MD">MD</option>
            </select>
        </div>
        <div>
            {pdf_link}
            {md_link}
        </div>
    </div>
    '''

    st.markdown(html, unsafe_allow_html=True)

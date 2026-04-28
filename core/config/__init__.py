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

from .global_settings import (APP_SCHEMA_NAME,
                              APP_NAME,
                              MAIN_MARKDOWN_BODY,
                              DEFAULT2_MARKDOWN_BODY,
                              METRIC_CONTAINER_MARKDOWN_BODY,
                              ANALYSIS_MARKDOWN_BODY,
                              APP_VERSION,
                              APP_VERSION_FOOTER)
from .component_settings import SPACE_CONTAINER_MARKDOWN, METRIC_CONTAINER_MARKDOWN_BODY, SPACE_BUTTON_MARKDOWN, TOOL_TIP
from .design_tokens import DESIGN_TOKENS, CSS_CUSTOM_PROPERTIES
from .design_tokens import (
    BRAND_PRIMARY, BRAND_PRIMARY_DARK, BRAND_SECONDARY, BRAND_SECONDARY_LIGHT,
    BRAND_ACCENT, BRAND_HOVER,
    SUCCESS, WARNING, ERROR, INFO,
    SURFACE_BASE, SURFACE_SUBTLE, SURFACE_ALT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_HEADING, TEXT_INVERSE,
    BORDER_DEFAULT, BORDER_STRONG, BORDER_FOCUS,
    CHART_SERIES, CHART_EXTENDED,
    GAUGE_LOW, GAUGE_MEDIUM, GAUGE_HIGH, GAUGE_TRACK,
)

__all__ = ['APP_SCHEMA_NAME',
           'APP_NAME',
           'MAIN_MARKDOWN_BODY',
           'DEFAULT2_MARKDOWN_BODY',
           'METRIC_CONTAINER_MARKDOWN_BODY',
           'ANALYSIS_MARKDOWN_BODY',
           'SPACE_CONTAINER_MARKDOWN',
           'SPACE_BUTTON_MARKDOWN',
           'APP_VERSION_FOOTER', 'TOOL_TIP',
           'DESIGN_TOKENS', 'CSS_CUSTOM_PROPERTIES',
           'BRAND_PRIMARY', 'BRAND_PRIMARY_DARK', 'BRAND_SECONDARY',
           'BRAND_SECONDARY_LIGHT', 'BRAND_ACCENT', 'BRAND_HOVER',
           'SUCCESS', 'WARNING', 'ERROR', 'INFO',
           'SURFACE_BASE', 'SURFACE_SUBTLE', 'SURFACE_ALT',
           'TEXT_PRIMARY', 'TEXT_SECONDARY', 'TEXT_MUTED', 'TEXT_HEADING', 'TEXT_INVERSE',
           'BORDER_DEFAULT', 'BORDER_STRONG', 'BORDER_FOCUS',
           'CHART_SERIES', 'CHART_EXTENDED',
           'GAUGE_LOW', 'GAUGE_MEDIUM', 'GAUGE_HIGH', 'GAUGE_TRACK']

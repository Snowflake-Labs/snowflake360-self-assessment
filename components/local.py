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

from functools import partial
import streamlit as st
import core as cr

ANALYSIS_ENTRIES = 'analysis'
METRIC_ENTRY = 'metric'
SUMMARY_ENTRY = 'db_summary_pivot'
HOURLY_COST_ENTRY = 'hourly_cost_load_pivot'
OPTION_ENTRY = 'option'
CLASS_METRIC_ENTRY = 'class_metric'
ENTRY_ACTIONS = 'entry_actions'

required_component_entries = {OPTION_ENTRY, CLASS_METRIC_ENTRY}


class EntryAction:
    def __init__(self, define, get, has):
        self.define = define
        self.get = get
        self.has = has


def component_entries(comp_name, default_entries):
    def inner(func):
        def wrapper(*args, **kwargs):
            if comp_name not in st.session_state[ANALYSIS_ENTRIES]:
                st.session_state[ANALYSIS_ENTRIES][comp_name] = default_entries

            if ENTRY_ACTIONS not in st.session_state[ANALYSIS_ENTRIES][comp_name]:
                st.session_state[ANALYSIS_ENTRIES][comp_name][ENTRY_ACTIONS] = EntryAction(
                    partial(define_component_entry, comp_name),
                    partial(get_component_entry, comp_name),
                    partial(has_component_entry, comp_name)
                )

            kwargs[ENTRY_ACTIONS] = st.session_state[ANALYSIS_ENTRIES][comp_name][ENTRY_ACTIONS]

            return func(*args, **kwargs)

        return wrapper

    return inner


def define_component_entry(comp_name, entry_name, entry_value):
    if comp_name not in st.session_state[ANALYSIS_ENTRIES]:
        st.session_state[ANALYSIS_ENTRIES][comp_name] = {}

    if st.session_state[ANALYSIS_ENTRIES][comp_name].get(entry_name) is None:
        st.session_state[ANALYSIS_ENTRIES][comp_name][entry_name] = entry_value

    return st.session_state[ANALYSIS_ENTRIES][comp_name][entry_name]


def get_component_entry(comp_name, entry_name):
    if not has_component_entry(comp_name, entry_name):
        return None

    return st.session_state[ANALYSIS_ENTRIES][comp_name][entry_name]


def has_component_entry(comp_name, entry_name):
    return (
            comp_name in st.session_state[ANALYSIS_ENTRIES] and
            entry_name in st.session_state[ANALYSIS_ENTRIES][comp_name]
    )


def has_entry(comp_name):
    return comp_name in st.session_state[ANALYSIS_ENTRIES]


def setup_component_entries(comp_name, entries):
    if not required_component_entries.issubset(entries):
        missing_keys = required_component_entries - entries.keys()
        raise ValueError(f"The following keys are missing in: {', '.join(missing_keys)}")

    class_metric = entries[CLASS_METRIC_ENTRY]

    define_component_entry(comp_name, OPTION_ENTRY, entries[OPTION_ENTRY])
    setup_comp_metric_entry(comp_name, class_metric)


def setup_comp_metric_entry(comp_name, class_metric):
    setup_metric(
        lambda entry_name: get_component_entry(comp_name, entry_name),
        lambda entry_name, metric: define_component_entry(comp_name, entry_name, metric),
        class_metric,
    )


def setup_metric_entry(entry_actions, class_metric):
    setup_metric(
        lambda entry_name: entry_actions.get(entry_name),
        lambda entry_name, metric: entry_actions.define(entry_name, metric),
        class_metric
    )


def setup_metric(get_entry_func, define_entry_func, class_metric):
    metric = get_entry_func(METRIC_ENTRY)

    if metric is None:
        metric = class_metric()
        define_entry_func(METRIC_ENTRY, metric)

    if metric.display_data.empty and metric.service.should_try_loading():
        _try_reload_data(metric)


def _try_reload_data(metric):
    while metric.display_data.empty and metric.service.should_try_loading():
        metric.restart_loading()


def clear_app_state():
    if ANALYSIS_ENTRIES in st.session_state:
        for comp_name in st.session_state[ANALYSIS_ENTRIES]:
            if METRIC_ENTRY in st.session_state[ANALYSIS_ENTRIES][comp_name]:
                del st.session_state[ANALYSIS_ENTRIES][comp_name][METRIC_ENTRY]
            if ENTRY_ACTIONS in st.session_state[ANALYSIS_ENTRIES][comp_name]:
                del st.session_state[ANALYSIS_ENTRIES][comp_name][ENTRY_ACTIONS]
            if SUMMARY_ENTRY in st.session_state[ANALYSIS_ENTRIES][comp_name]:
                del st.session_state[ANALYSIS_ENTRIES][comp_name][SUMMARY_ENTRY]
            if HOURLY_COST_ENTRY in st.session_state[ANALYSIS_ENTRIES][comp_name]:
                del st.session_state[ANALYSIS_ENTRIES][comp_name][HOURLY_COST_ENTRY]

        del st.session_state[ANALYSIS_ENTRIES]
    if 'selected_menu' in st.session_state:
        del st.session_state['selected_menu']
    if 'selected_tabs' in st.session_state:
        del st.session_state['selected_tabs']


@st.cache_resource()
def load_catalog():
    return cr.load_catalog()

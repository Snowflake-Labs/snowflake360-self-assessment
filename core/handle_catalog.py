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

import json

CATALOG_PATH = 'core/data/catalog.json'


def load_catalog():
    try:
        with open(CATALOG_PATH, 'r') as file:
            catalog = json.load(file)
    except Exception as e:
        raise RuntimeError(f"Unexpected error while loading the account review catalog: {e}")
    return catalog

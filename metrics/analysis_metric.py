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

from services.Common.Data_Config import DataConfig
from .base_metric import BaseMetric


class AnalysisMetric(BaseMetric):
    def __init__(self, service) -> None:
        super().__init__()
        self.service = service
        self._display_data = self.service.data
        self.display_data_copy = self.service.data
        self.pivot_data = None
        self.pivot_data_copy = None
        self.has_custom_columns = False
        self._metric_key = None
        self.data_size = 20

    @property
    def metric_key (self):
        return self._metric_key

    @property
    def raw_data (self):
        return self.display_data_copy

    @property
    def display_data(self):
        if self._display_data is None or self._display_data.empty:
            return self._display_data

        if self.has_custom_columns:
            return self._display_data.head(self.data_size)

        if self._metric_key is not None and DataConfig.has_custom_columns(self._metric_key):
            return DataConfig.exclude_columns(self._metric_key,
                                              DataConfig.get_columns_to_exclude(self._metric_key),
                                              self._display_data.head(self.data_size))

        return self._display_data.head(self.data_size)

    @metric_key.setter
    def metric_key(self, value) -> None:
        self._metric_key = value

    @display_data.setter
    def display_data(self, value) -> None:
        self._display_data = value

    def restart_loading(self):
        self.service.start_loading()
        self.display_data = self.service.data

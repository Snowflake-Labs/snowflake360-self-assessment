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

from metrics.base_metric import BaseMetric
from services.Virtual_Warehouses.warehouse_overview_service import WarehouseOverviewService


class WarehouseOverviewMetric(BaseMetric):
    def __init__(self):
        super().__init__()
        self.service = WarehouseOverviewService()
        self.display_data = self.service.data
        self._warehouse_count_by_size = None
        self._total_warehouse_count = None
        self._warehouses_by_type = None
        self._warehouses_by_status = None

    def restart_loading(self):
        """Restart the data loading process."""
        self.service.start_loading()
        self.display_data = self.service.data
        # Reset cached properties
        self._warehouse_count_by_size = None
        self._total_warehouse_count = None
        self._warehouses_by_type = None
        self._warehouses_by_status = None

    @property
    def warehouse_count_by_size(self):
        """Get warehouse count by size with caching."""
        if self._warehouse_count_by_size is None:
            self._warehouse_count_by_size = self.service.get_warehouse_count_by_size()
        return self._warehouse_count_by_size

    @property
    def total_warehouse_count(self):
        """Get total warehouse count with caching."""
        if self._total_warehouse_count is None:
            self._total_warehouse_count = self.service.get_total_warehouse_count()
        return self._total_warehouse_count

    @property
    def warehouses_by_type(self):
        """Get warehouse count by type with caching."""
        if self._warehouses_by_type is None:
            self._warehouses_by_type = self.service.get_warehouses_by_type()
        return self._warehouses_by_type

    @property
    def warehouses_by_status(self):
        """Get warehouse count by status with caching."""
        if self._warehouses_by_status is None:
            self._warehouses_by_status = self.service.get_warehouses_by_status()
        return self._warehouses_by_status

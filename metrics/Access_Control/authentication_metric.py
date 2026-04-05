import pandas as pd
from ..base_metric import BaseMetric
from services.Access_Control.authentication_service import AuthenticationService


class AuthenticationMetric(BaseMetric):
    def __init__(self):
        super().__init__()
        self.service = AuthenticationService()
        self.display_data = self.service.data
        # Cached properties (like Virtual Warehouses pattern)
        self._logins_by_authentication_factor = None
        self._authentication_method_counts = None
        self._login_failure_counts = None

    def restart_loading(self):
        """Restart the data loading process."""
        self.service.start_loading()
        self.display_data = self.service.data
        # Reset cached properties
        self._logins_by_authentication_factor = None
        self._authentication_method_counts = None
        self._login_failure_counts = None

    @property
    def logins_by_authentication_factor(self):
        """Get logins count by authentication factor with caching."""
        if self._logins_by_authentication_factor is None:
            self._logins_by_authentication_factor = self.service.get_logins_by_authentication_factor()
        return self._logins_by_authentication_factor

    @property
    def authentication_method_counts(self):
        """Get authentication method counts with caching."""
        if self._authentication_method_counts is None:
            self._authentication_method_counts = self.service.get_authentication_method_counts()
        return self._authentication_method_counts

    @property
    def login_failure_counts(self):
        """Get login failure counts with caching."""
        if self._login_failure_counts is None:
            self._login_failure_counts = self.service.get_login_failure_counts()
        return self._login_failure_counts

    def has_data(self):
        """Check if any data is available."""
        result = self.service.has_data()
        print(f"🔍 AuthenticationMetric.has_data() returning: {result}")
        return result

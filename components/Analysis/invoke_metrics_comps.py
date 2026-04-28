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

import streamlit as st

# Import component modules directly to avoid circular imports
from components.Database_Management import (
    comp_db_overview,
    comp_db_management_analyzer,
    comp_db_storage,
    comp_db_clustering,
    comp_db_low_lifespan,
    comp_db_high_churn
)
from components.Virtual_Warehouses import comp_warehouse_overview, comp_warehouse_analysis, comp_scaling_management, comp_performance_monitoring
from components.Access_Control import comp_authorization, comp_access_control_analysis, comp_authentication, comp_network_policies, comp_access_control_overview
from components.Data_Ingestion import comp_ingestion_overview, comp_ingestion_analyzer, comp_highest_cost, comp_bulk_load_analysis, comp_snowpipe_analysis
from components.Data_Transformation import comp_transformation_overview, comp_transformation_analyzer, comp_problematic_query_report, comp_syntax_hunter, comp_object_structure_analysis, comp_workload_shape
from components.FinOps_Lite import comp_finops_overview, comp_finops_analyzer, comp_finops_visibility, comp_finops_control, comp_finops_optimization
from components.Data_Recovery_DevOps import comp_recovery_devops_overview, comp_recovery_devops_analyzer, comp_dcm_adoption, comp_git_integration, comp_cicd_automation, comp_declarative_pipeline
from components.Data_Governance_New import comp_governance_overview, comp_governance_analyzer, comp_object_tagging_classification, comp_data_privacy_protection, comp_lineage_quality


@st.cache_resource()
def get_analysis_comp_handler():
    return AnalysisCompsHandler()


class AnalysisCompsHandler:
    """
    Handler for new menu structure components.
    All old legacy menu handlers have been removed.
    Only the new 8-menu structure handlers are included.
    """

    # --------- New Menu Structure - Database Management --------
    @staticmethod
    def db_overview():
        comp_db_overview()

    @staticmethod
    def db_management_analyzer():
        comp_db_management_analyzer()

    @staticmethod
    def db_storage():
        comp_db_storage()

    @staticmethod
    def db_clustering():
        comp_db_clustering()

    @staticmethod
    def db_low_lifespan():
        comp_db_low_lifespan()

    @staticmethod
    def db_high_churn():
        comp_db_high_churn()

    # --------- New Menu Structure - Virtual Warehouses --------
    @staticmethod
    def warehouse_overview():
        comp_warehouse_overview()

    @staticmethod
    def warehouse_analysis():
        comp_warehouse_analysis()

    @staticmethod
    def scaling_management():
        comp_scaling_management()

    @staticmethod
    def performance_monitoring():
        comp_performance_monitoring()

    # --------- New Menu Structure - Access Control --------
    @staticmethod
    def access_control_overview():
        comp_access_control_overview()

    @staticmethod
    def authorization():
        comp_authorization()

    @staticmethod
    def access_control_analysis():
        comp_access_control_analysis()

    @staticmethod
    def authentication():
        comp_authentication()

    @staticmethod
    def network_policies():
        comp_network_policies()

    # --------- New Menu Structure - Data Ingestion --------
    @staticmethod
    def ingestion_overview():
        comp_ingestion_overview()

    @staticmethod
    def ingestion_analyzer():
        comp_ingestion_analyzer()

    @staticmethod
    def highest_cost():
        comp_highest_cost()

    @staticmethod
    def bulk_load_analysis():
        comp_bulk_load_analysis()

    @staticmethod
    def snowpipe_analysis():
        comp_snowpipe_analysis()

    # --------- New Menu Structure - Data Transformation --------
    @staticmethod
    def transformation_overview():
        comp_transformation_overview()

    @staticmethod
    def transformation_analyzer():
        comp_transformation_analyzer()

    @staticmethod
    def problematic_query_report():
        comp_problematic_query_report()

    @staticmethod
    def syntax_hunter():
        comp_syntax_hunter()

    @staticmethod
    def object_structure_analysis():
        comp_object_structure_analysis()

    @staticmethod
    def workload_shape():
        comp_workload_shape()

    # --------- New Menu Structure - FinOps (lite) --------
    @staticmethod
    def finops_overview():
        comp_finops_overview()

    @staticmethod
    def finops_analyzer():
        comp_finops_analyzer()

    @staticmethod
    def finops_visibility():
        comp_finops_visibility()

    # --------- New Menu Structure - Data Recovery & DevOps --------
    @staticmethod
    def recovery_devops_overview():
        comp_recovery_devops_overview()

    @staticmethod
    def recovery_devops_analyzer():
        comp_recovery_devops_analyzer()

    @staticmethod
    def dcm_adoption():
        comp_dcm_adoption()

    @staticmethod
    def git_integration():
        comp_git_integration()

    @staticmethod
    def cicd_automation():
        comp_cicd_automation()

    @staticmethod
    def declarative_pipeline():
        comp_declarative_pipeline()

    # --------- New Menu Structure - Data Governance --------
    @staticmethod
    def governance_overview():
        comp_governance_overview()

    @staticmethod
    def governance_analyzer():
        comp_governance_analyzer()

    @staticmethod
    def object_tagging_classification():
        comp_object_tagging_classification()

    @staticmethod
    def data_privacy_protection():
        comp_data_privacy_protection()

    @staticmethod
    def lineage_quality():
        comp_lineage_quality()

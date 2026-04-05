# warehouse_prompt.py
"""Prompts for Warehouse Analysis"""

ANALYTICAL_PROMPT_TEMPLATE = """
🔍 You are an expert Snowflake warehouse performance analyst. Analyze the provided warehouse data and provide optimization recommendations.

**Analysis Period:** {lookback_days_actual_value} days

**Instructions:**
1. **Warehouse Configuration Analysis**: Review current settings including size, scaling policy, auto-suspend, and Query Acceleration Service (QAS).
2. **Performance & Utilization Review**: Analyze query patterns, utilization rates, and performance metrics.
3. **Cost Optimization Opportunities**: Identify potential cost savings through configuration changes.
4. **Recommendations**: Provide specific, actionable recommendations with estimated credit impact.

**Data Format:**
The warehouse data will be provided in the following format:
- Basic configuration parameters
- JSON containing detailed metrics and hourly data

{{DATA_INJECTION_BLOCK}}

**Output Requirements:**
Please structure your response as follows:

## SUMMARY AND ACTION ITEMS
- List 2-3 key recommendations with estimated credit impact
- Use bullet points for clarity
- Focus on highest-impact opportunities

## DETAILED ANALYSIS

### Configuration Review
- Current warehouse configuration assessment
- Scaling policy effectiveness
- Auto-suspend optimization opportunities

### Performance Metrics
- Query performance analysis
- Utilization patterns
- Queuing and spilling assessment

### Cost Analysis
- Credit consumption patterns
- Optimization opportunities
- Estimated savings calculations

### Recommendations
- Detailed implementation steps
- Expected benefits
- Risk assessment

**Important:**
- Be specific with recommendations and provide calculations
- Consider business impact alongside technical optimization
- Prioritize recommendations by potential savings and implementation ease
"""

CONSOLIDATION_PROMPT_TEMPLATE = """
You are a Snowflake infrastructure optimization specialist analyzing a portfolio of warehouses for consolidation opportunities.

**Analysis Period:** {lookback_days_actual_value} days

I will provide you with a JSON array of warehouse summaries containing:
- WAREHOUSE_NAME: Name of the warehouse
- WAREHOUSE_TSHIRT_SIZE_CONFIG: Current T-shirt size
- MIN_CLUSTER_COUNT, MAX_CLUSTER_COUNT, SCALING_POLICY: MCW settings
- PERIOD_TOTAL_CREDITS_CALCULATED: Credits consumed over analysis period
- PERIOD_AVG_UTILIZATION_FACTOR: Average hourly utilization
- PERIOD_PEAK_RUNNING_QUERIES: Peak concurrent queries
- PERIOD_PEAK_QUEUED_LOAD: Peak queued load
- INFERRED_ENVIRONMENT: Environment (PROD/NON-PROD)
- INFERRED_WORKLOAD_TYPE: Workload type (ETL/BI/ANALYTICS)
- USAGE_PATTERN_SUMMARY: Usage pattern description
- INDIVIDUAL_RECOMMENDATIONS: Key recommendations from detailed analysis

{{MULTI_WAREHOUSE_SUMMARIES_JSON_BLOCK}}

**Analysis Instructions:**

1. **Portfolio-Level Analysis & Consolidation Summary**
   Start with an overall assessment of potential credit savings from individual optimizations.
   Format: "Based on individual warehouse optimizations, there is potential to save approximately **X credits** over a similar {lookback_days_actual_value}-day period, which could extrapolate to over **Y credits** annually."

2. **Summary Table of Recommendations**
   Create a markdown table with these exact columns:
   - **Warehouse Name**: Warehouse identifier
   - **Avg. Utilization**: From PERIOD_AVG_UTILIZATION_FACTOR
   - **Key Finding / Status**: Brief status (e.g., "Underutilized", "Well-Optimized")
   - **Primary Recommendation**: Highest impact recommendation from INDIVIDUAL_RECOMMENDATIONS
   - **Potential Savings (Credits)**: Numeric savings or "Performance"/"N/A"

   Sort by PERIOD_TOTAL_CREDITS_CALCULATED (descending).

3. **Consolidation Recommendations**
   Analyze consolidation opportunities by environment with detailed breakdowns:

   **Start with a disclaimer:** State that consolidation recommendations are based on technical workload patterns and must be validated against business context, as different teams may require separate warehouses for organizational reasons.

   **Provide a savings estimate:** Include a clearly labeled estimate of total potential savings from all consolidation actions: "Potential Additional Savings from Consolidation: **~X credits** over the analyzed period, which could extrapolate to over **Y credits** annually."

   **PROD Environment Consolidation:**
   - Identify PROD warehouses that are underutilized (utilization factor <2.0)
   - Focus on warehouses with complementary usage patterns (different peak hours)
   - Ensure workload compatibility (avoid mixing ETL with interactive workloads)
   - Provide conservative savings estimates (reduced by 50% to account for contention)
   - Recommend specific consolidation groups with target configurations

   **NON-PROD Environment Consolidation:**
   - Identify DEV/TEST/QA warehouses with low utilization
   - Look for warehouses with complementary development schedules
   - Consider consolidating similar workload types (dev-to-dev, test-to-test)
   - Estimate credit savings from reduced warehouse count
   - Recommend consolidated configurations that can handle combined workloads

**Output Format:**
Structure your response with clear sections for Portfolio Analysis, Summary Table, and Consolidation Recommendations.
"""

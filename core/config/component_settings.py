SPACE_CONTAINER_MARKDOWN: str = '''
    <div class="custom-container" style="margin-bottom:28px;"> </div>
'''

METRIC_CONTAINER_MARKDOWN_BODY: str = """
<style>
[data-testid="stMetricValue"] {
    font-size: 20px;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    padding: 5px;
}

.block-container {
padding: 20px
}
</style>
"""

SPACE_BUTTON_MARKDOWN: str = '''
    <div class="custom-container" style="margin-bottom:28px;"> </div>
'''



TOOL_TIP:str =              """
                <style>
                /* Tooltip container */
                .tooltip {
                  position: relative;
                  display: inline-block;
                  font-size: 16px;
                  cursor: pointer;
                  left: -4px;
                  margin-right= 11px;
                  margin-top: 35px;
                }
                .tooltip .tooltiptext::after {
                  content: '';
                  position: absolute;
                  bottom: -10px; /* Distance of the triangle from the tooltip */
                  left: 50%;
                  margin-left: -5px; /* Adjust the width of the triangle */
                  border-width: 5px;
                  border-style: solid;
                  border-color: #e0e0e0 transparent transparent transparent;
                }
                /* Tooltip text */
                .tooltip .tooltiptext {
                        visibility: hidden;
                        min-width: 210px;
                        color: #666666;
                        background-color: #F0F2F6;
                        text-align: center;
                        padding: 1px;
                        border-radius: 6px;
                        position: absolute;
                        z-index: 1;
                        top: -136px;
                        left: -97px;
                        opacity: 0.7;
                        font-size: 12px;
                        border: 0.2px solid #e0e0e0;
                }

                /* Show the tooltip text on hover */
                .tooltip:hover .tooltiptext {
                  visibility: visible;
                }
                </style>

                <div class="tooltip">&#9432;
                  <span class="tooltiptext">
                    You can search using the following options: <strong> CaseSafe Account ID,
                    Snowflake Account Name, Organization Name, Salesforce Account Name, Snowflake Account Alias</strong>
                  </span>
                </div>
                """

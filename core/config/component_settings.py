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

GREEN = '#70A572' #'rgba(112,165,114,1.0)'
GREEN_YELLOW = '#B3BB5F' # 'rgba(179,187,95,1.0)'
YELLOW = '#F5C242' # 'rgba(245,194,66,1.0)'
YELLOW_RED = '#E69150' # 'rgba(230,145,80,1.0)'
RED_YELLOW = '#CC4043' # 'rgba(204,67,67,1.0)'
RED = '#CC4343' # 'rgba(204,67,67,1.0)'
GREY = '#BAC4CF' # 'rgba(186,196,207,1.0)'

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
                  border-color: #D3D3D3 transparent transparent transparent; /* Same color as tooltip */
                }
                /* Tooltip text */
                .tooltip .tooltiptext {
                        visibility: hidden;
                        min-width: 210px;
                        color: #525252;
                        background-color: #e2e2e2;
                        text-align: center;
                        padding: 1px;
                        border-radius: 6px;
                        position: absolute;
                        z-index: 1;
                        top: -136px;
                        left: -97px;
                        opacity: 0.7;
                        font-size: 12px;
                        border: 0.2px solid gray;
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

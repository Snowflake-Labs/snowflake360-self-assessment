"""
Telemetry HTML export engine.
Produces self-contained, print-ready HTML reports using Chart.js.
"""

from __future__ import annotations
import html as _html
import json
from datetime import datetime
from typing import Any

from core.config.design_tokens import (
    BRAND_PRIMARY, BRAND_PRIMARY_DARK, BRAND_SECONDARY,
    BRAND_SECONDARY_LIGHT, BRAND_ACCENT,
    CHART_SERIES, CHART_EXTENDED,
)

_COLORS = CHART_SERIES + CHART_EXTENDED
_CHART_COUNTER = 0


def _next_chart_id() -> str:
    global _CHART_COUNTER
    _CHART_COUNTER += 1
    return f"tc{_CHART_COUNTER}"


def _reset_chart_counter():
    global _CHART_COUNTER
    _CHART_COUNTER = 0


_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "Helvetica Neue", Arial, sans-serif; color: #1a1a2e; background: #f4f6f9; font-size: 13px; }}
.report-header {{ background: linear-gradient(135deg, {BRAND_PRIMARY_DARK} 0%, {BRAND_SECONDARY} 100%); color: white;
                  padding: 24px 40px; display: flex; align-items: center; justify-content: space-between; }}
.header-text h1 {{ font-size: 1.4rem; font-weight: 700; }}
.header-text p  {{ font-size: 0.85rem; opacity: 0.85; margin-top: 4px; }}
.print-btn {{ background: white; color: {BRAND_PRIMARY_DARK}; border: none; border-radius: 8px;
              padding: 10px 20px; font-size: 0.88rem; font-weight: 700; cursor: pointer;
              box-shadow: 0 2px 6px rgba(0,0,0,0.25); transition: opacity 0.2s; white-space: nowrap; }}
.print-btn:hover {{ opacity: 0.85; }}
.section {{ background: white; border-radius: 10px; padding: 20px 32px; margin: 20px 40px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07); }}
.customer-bar {{ display: flex; gap: 32px; flex-wrap: wrap; }}
.customer-bar div {{ font-size: 0.85rem; color: #555; }}
.customer-bar strong {{ color: {BRAND_PRIMARY_DARK}; }}
.kpi-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0 16px; }}
.kpi-card {{ background: linear-gradient(135deg, {BRAND_PRIMARY_DARK}, {BRAND_SECONDARY}); color: white;
             border-radius: 8px; padding: 14px 18px; min-width: 110px; text-align: center; flex: 1; }}
.kpi-value {{ font-size: 1.4rem; font-weight: 700; }}
.kpi-label {{ font-size: 0.72rem; margin-top: 4px; opacity: 0.9; letter-spacing: 0.02em; }}
.sub-kpis .kpi-card {{ background: white; color: {BRAND_PRIMARY_DARK}; border: 1px solid #d0e8f5;
                        box-shadow: 0 1px 4px rgba(17,86,127,0.08); padding: 12px 14px; }}
.sub-kpis .kpi-value {{ font-size: 1.25rem; color: {BRAND_PRIMARY_DARK}; }}
.sub-kpis .kpi-label {{ color: #555; }}
.sub-section {{ border: 1px solid #e0ecf5; border-radius: 8px; padding: 16px 20px; margin-top: 18px; background: #fafcff; }}
.sub-section-title {{ font-size: 1.05rem; font-weight: 700; color: {BRAND_PRIMARY_DARK};
                       border-bottom: 2px solid {BRAND_SECONDARY}; padding-bottom: 7px; margin-bottom: 14px; }}
.section-subtitle {{ font-size: 0.9rem; font-weight: 600; color: {BRAND_PRIMARY_DARK};
                      margin: 18px 0 8px; padding-left: 8px;
                      border-left: 3px solid {BRAND_SECONDARY}; }}
.charts-row {{ display: flex; gap: 16px; margin-top: 14px; flex-wrap: wrap; align-items: flex-start; }}
.chart-col {{ flex: 1; min-width: 280px; }}
.chart-block {{ background: white; border-radius: 8px; padding: 12px 14px;
                border: 1px solid #e0ecf5; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
                overflow: hidden; }}
.chart-block-full {{ margin-top: 14px; background: white; border-radius: 8px;
                      padding: 12px 14px; border: 1px solid #e0ecf5;
                      box-shadow: 0 1px 4px rgba(0,0,0,0.05); overflow: hidden; }}
.chart-title {{ font-size: 0.83rem; font-weight: 600; color: {BRAND_PRIMARY_DARK}; margin-bottom: 6px;
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.data-table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.78rem; }}
.data-table thead tr {{ background: {BRAND_PRIMARY_DARK}; color: white; }}
.data-table th {{ padding: 7px 10px; text-align: left; font-weight: 600; font-size: 0.75rem; white-space: nowrap; }}
.data-table td {{ padding: 5px 10px; border-bottom: 1px solid #eef2f7; color: #333; }}
.data-table tr:nth-child(even) {{ background: #f5f9fd; }}
.data-table tr:hover {{ background: #e8f4fb; }}
.no-data-note {{ color: #999; font-style: italic; text-align: center; padding: 20px; font-size: 0.85rem; }}
.analysis-output {{ font-size: 0.85rem; line-height: 1.6; color: #333; background: #f8fbfe;
                    border: 1px solid #d9eaf6; border-radius: 8px; padding: 14px 16px; }}
.footer {{ text-align: center; padding: 20px 40px 30px; font-size: 0.72rem; color: #888; }}
h2 {{ font-size: 1.05rem; color: {BRAND_PRIMARY_DARK}; margin-bottom: 12px; font-weight: 700;
      border-left: 4px solid {BRAND_SECONDARY}; padding-left: 10px; }}
@media print {{
  .print-btn {{ display: none; }}
  body {{ background: white; font-size: 11px; }}
  .section {{ box-shadow: none; margin: 6px 0; padding: 14px 20px; }}
  .chart-block, .chart-block-full {{ border: 1px solid #ccc; page-break-inside: avoid; }}
  .sub-section {{ page-break-inside: avoid; }}
  .charts-row {{ flex-wrap: nowrap; }}
  .data-table {{ font-size: 0.7rem; }}
  .kpi-value {{ font-size: 1.1rem; }}
}}
"""


def _esc(text: Any) -> str:
    return _html.escape(str(text)) if text is not None else ""


def _fmt_num(val: Any, decimals: int = 2) -> str:
    if val is None:
        return "—"
    try:
        v = float(val)
        if v == int(v) and decimals == 0:
            return f"{int(v):,}"
        return f"{v:,.{decimals}f}"
    except (ValueError, TypeError):
        return str(val)


def _make_doughnut(chart_id: str, labels: list, data: list | None = None,
                   colors: list | None = None, datasets: list[dict] | None = None,
                   title: str = "") -> str:
    if datasets:
        for ds in datasets:
            if "backgroundColor" not in ds:
                ds["backgroundColor"] = _COLORS[: len(ds.get("data", []))]
        cfg = json.dumps({"labels": labels, "datasets": datasets})
    else:
        colors = colors or _COLORS[: len(data)]
        cfg = json.dumps({
            "labels": labels,
            "datasets": [{"data": data, "backgroundColor": colors}],
        })
    display_title = title or (_esc(labels[0]) if len(labels) == 1 else "")
    return f"""<div class="chart-block">
    <div class="chart-title">{display_title}</div>
    <div style="position:relative;height:274px;width:100%;">
        <canvas id="{chart_id}"></canvas>
    </div>
    <script>
    (function(){{
        var ctx = document.getElementById('{chart_id}').getContext('2d');
        new Chart(ctx, {{
            type: 'doughnut',
            data: {cfg},
            options: {{
                cutout: '40%',
                plugins: {{
                    legend: {{ position: 'bottom', labels: {{ font: {{ size: 11 }}, padding: 12 }} }},
                    datalabels: {{
                        color: '#1f2937', anchor: 'end', align: 'end', offset: 8, clamp: true,
                        font: {{ size: 10, weight: '600' }},
                        formatter: function(value, ctx) {{
                            var total = ctx.dataset.data.reduce(function(a,b){{return a+b;}},0);
                            var pct = total > 0 ? Math.round(value/total*1000)/10 : 0;
                            return ctx.chart.data.labels[ctx.dataIndex] + ' ' + Number(value).toLocaleString() + ' (' + pct + '%)';
                        }}
                    }},
                    tooltip: {{ callbacks: {{ label: function(ctx) {{
                        var total = ctx.dataset.data.reduce(function(a,b){{return a+b;}},0);
                        var pct = total > 0 ? Math.round(ctx.parsed/total*1000)/10 : 0;
                        return ctx.label + ': ' + ctx.parsed.toLocaleString() + ' (' + pct + '%)';
                    }}}}}}
                }},
                responsive: true, maintainAspectRatio: false
            }}
        }});
    }})();
    </script>
</div>"""


def _make_hbar(chart_id: str, labels: list, datasets: list[dict], title: str = "",
               x_title: str = "", stacked: bool = False, height: int = 0) -> str:
    if not height:
        height = max(154, len(labels) * 22 + 60)
    ds_json = json.dumps(datasets)
    opts_stack = ""
    if stacked:
        opts_stack = "stacked: true,"
    return f"""<div class="chart-block">
    <div class="chart-title">{_esc(title)}</div>
    <div style="position:relative;height:{height}px;width:100%;">
        <canvas id="{chart_id}"></canvas>
    </div>
    <script>
    (function(){{
        var ctx = document.getElementById('{chart_id}').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{ labels: {json.dumps(labels)}, datasets: {ds_json} }},
            options: {{
                indexAxis: 'y',
                responsive: true, maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: {str(len(datasets) > 1).lower()}, position: 'top', labels: {{ font: {{ size: 11 }} }} }},
                    tooltip: {{ callbacks: {{ label: function(ctx) {{ return ' ' + ctx.parsed.x.toLocaleString(); }} }} }}
                }},
                scales: {{
                    x: {{ {opts_stack} beginAtZero: true, grid: {{ color: 'rgba(0,0,0,0.06)' }},
                          title: {{ display: {str(bool(x_title)).lower()}, text: "{_esc(x_title)}", font: {{ size: 11 }} }} }},
                    y: {{ {opts_stack} ticks: {{ font: {{ size: 10 }}, crossAlign: 'far' }},
                          grid: {{ display: false }} }}
                }},
                layout: {{ padding: {{ right: 40 }} }}
            }}
        }});
    }})();
    </script>
</div>"""


def _make_vbar(chart_id: str, labels: list, datasets: list[dict], title: str = "",
               y_title: str = "", stacked: bool = False, height: int = 214) -> str:
    ds_json = json.dumps(datasets)
    opts_stack = "stacked: true," if stacked else ""
    return f"""<div class="chart-block">
    <div class="chart-title">{_esc(title)}</div>
    <div style="position:relative;height:{height}px;width:100%;">
        <canvas id="{chart_id}"></canvas>
    </div>
    <script>
    (function(){{
        var ctx = document.getElementById('{chart_id}').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{ labels: {json.dumps(labels)}, datasets: {ds_json} }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: {str(len(datasets) > 1).lower()}, position: 'top', labels: {{ font: {{ size: 11 }} }} }},
                    tooltip: {{ callbacks: {{ label: function(ctx) {{ return ' ' + ctx.parsed.y.toLocaleString(); }} }} }}
                }},
                scales: {{
                    y: {{ {opts_stack} beginAtZero: true, grid: {{ color: 'rgba(0,0,0,0.06)' }},
                          title: {{ display: {str(bool(y_title)).lower()}, text: "{_esc(y_title)}", font: {{ size: 11 }} }} }},
                    x: {{ {opts_stack} grid: {{ display: false }},
                          ticks: {{ font: {{ size: 10 }}, maxRotation: 45 }} }}
                }},
                layout: {{ padding: {{ top: 36 }} }}
            }}
        }});
    }})();
    </script>
</div>"""


def _make_line(chart_id: str, labels: list, datasets: list[dict], title: str = "",
               y_title: str = "", height: int = 214) -> str:
    ds_json = json.dumps(datasets)
    return f"""<div class="chart-block">
    <div class="chart-title">{_esc(title)}</div>
    <div style="position:relative;height:{height}px;width:100%;">
        <canvas id="{chart_id}"></canvas>
    </div>
    <script>
    (function(){{
        var ctx = document.getElementById('{chart_id}').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{ labels: {json.dumps(labels)}, datasets: {ds_json} }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ legend: {{ display: {str(len(datasets) > 1).lower()}, position: 'top' }} }},
                scales: {{
                    y: {{ beginAtZero: true, grid: {{ color: 'rgba(0,0,0,0.06)' }},
                          title: {{ display: {str(bool(y_title)).lower()}, text: "{_esc(y_title)}", font: {{ size: 11 }} }} }},
                    x: {{ grid: {{ color: 'rgba(0,0,0,0.04)' }},
                          ticks: {{ maxRotation: 45, font: {{ size: 10 }} }} }}
                }}
            }}
        }});
    }})();
    </script>
</div>"""


def _make_table(headers: list[str], rows: list[list]) -> str:
    ths = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    trs = ""
    for row in rows[:200]:
        tds = "".join(f"<td>{_esc(c)}</td>" for c in row)
        trs += f"<tr>{tds}</tr>"
    return f'<table class="data-table"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>'


def _kpi_cards(kpis: list[dict], sub: bool = False) -> str:
    cls = ' class="kpi-grid sub-kpis"' if sub else ' class="kpi-grid"'
    cards = "".join(
        f'<div class="kpi-card"><div class="kpi-value">{_esc(k["value"])}</div>'
        f'<div class="kpi-label">{_esc(k["label"])}</div></div>'
        for k in kpis
    )
    return f"<div{cls}>{cards}</div>"


def _analysis_block(title: str, content: str) -> str:
    safe = content.replace("\n", "<br>") if content else "<em>No analysis available.</em>"
    return (
        f'<div class="sub-section">'
        f'<div class="sub-section-title">{_esc(title)}</div>'
        f'<div class="analysis-output">{safe}</div>'
        f'</div>'
    )


def _make_gauge(chart_id: str, score: float, max_score: float = 3.0,
                color: str = "#F39C12", title: str = "") -> str:
    pct = min(score / max_score, 1.0) if max_score else 0
    filled = round(pct * 50, 2)
    unfilled = round((1 - pct) * 50, 2)
    mid = f"{max_score / 2:.1f}"
    data_json = json.dumps([filled, unfilled, 50])
    colors_json = json.dumps([color, "#E5E7EB", "transparent"])
    return f"""<div class="chart-block" style="height:260px; position:relative;">
  <div class="chart-title">{_esc(title)}</div>
  <div style="position:relative; height:224px;">
    <canvas id="{chart_id}"></canvas>
    <div style="position:absolute; bottom:8%; left:50%; transform:translateX(-50%);
                font-size:1.6rem; font-weight:700; color:{color}; pointer-events:none;">
      {score:.2f}
    </div>
    <div style="position:absolute; bottom:2%; left:50%; transform:translateX(-50%);
                font-size:0.72rem; color:#6b7280; pointer-events:none;">
      0 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {mid} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {max_score:.0f}
    </div>
  </div>
  <script>
  (function(){{
    var ctx = document.getElementById('{chart_id}').getContext('2d');
    new Chart(ctx, {{
      type: 'doughnut',
      data: {{
        datasets: [{{
          data: {data_json},
          backgroundColor: {colors_json},
          borderWidth: 0,
          borderColor: 'transparent'
        }}]
      }},
      options: {{
        rotation: -90,
        circumference: 180,
        cutout: '70%',
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ enabled: false }},
          datalabels: {{ display: false }}
        }},
        responsive: true,
        maintainAspectRatio: false
      }}
    }});
  }})();
  </script>
</div>"""


def build_chart(chart_type: str, **kwargs) -> str:
    cid = _next_chart_id()
    if chart_type == "doughnut":
        return _make_doughnut(cid, **kwargs)
    elif chart_type == "hbar":
        return _make_hbar(cid, **kwargs)
    elif chart_type == "vbar":
        return _make_vbar(cid, **kwargs)
    elif chart_type == "line":
        return _make_line(cid, **kwargs)
    elif chart_type == "gauge":
        return _make_gauge(cid, **kwargs)
    return ""


def build_sub_section(title: str, kpis: list[dict] | None = None,
                      charts_html: str = "", tables_html: str = "") -> str:
    parts = [f'<div class="sub-section"><div class="sub-section-title">{_esc(title)}</div>']
    if kpis:
        parts.append(_kpi_cards(kpis, sub=True))
    if charts_html:
        parts.append(charts_html)
    if tables_html:
        parts.append(tables_html)
    parts.append("</div>")
    return "\n".join(parts)


def build_report(topic_name: str, account_name: str,
                 top_kpis: list[dict] | None = None,
                 analyzer_summary: str = "",
                 sub_sections: list[str] | None = None,
                 individual_analyses: list[dict] | None = None) -> str:
    _reset_chart_counter()
    now_str = datetime.now().strftime("%B %d, %Y")

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>Snowflake 360 Telemetry Report — {_esc(topic_name)}</title>",
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>',
        '<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0"></script>',
        f"<style>{_CSS}</style>",
        "</head><body>",
        '<div class="report-header">',
        '  <div class="header-text">',
        "    <h1>Snowflake 360 Telemetry Report</h1>",
        f'    <p>{_esc(topic_name)} &mdash; {now_str}</p>',
        "  </div>",
        """  <button class="print-btn" onclick="window.print()">🖨️ Print / Save as PDF</button>""",
        "</div>",
        '<div class="section">',
        '  <div class="customer-bar">',
        f'    <div><strong>Account:</strong> {_esc(account_name)}</div>',
        f'    <div><strong>Generated:</strong> {now_str}</div>',
        "  </div>",
        "</div>",
    ]

    if top_kpis:
        parts.append('<div class="section">')
        parts.append(_kpi_cards(top_kpis, sub=False))
        parts.append("</div>")

    if analyzer_summary:
        safe_summary = analyzer_summary
        if isinstance(safe_summary, str) and safe_summary.startswith('"') and safe_summary.endswith('"'):
            safe_summary = safe_summary[1:-1]
        safe_summary = safe_summary.replace("\\n", "<br>").replace("\\t", "  ").replace("\n", "<br>")
        parts.append('<div class="section">')
        parts.append("  <h2>Analyzer Summary</h2>")
        parts.append(f'  <div class="analysis-output">{safe_summary}</div>')
        parts.append("</div>")

    if sub_sections:
        parts.append('<div class="section">')
        parts.extend(sub_sections)
        parts.append("</div>")

    if individual_analyses:
        parts.append('<div class="section">')
        parts.append("  <h2>Individual Analysis</h2>")
        for ia in individual_analyses:
            parts.append(_analysis_block(ia.get("title", ""), ia.get("content", "")))
        parts.append("</div>")

    parts.extend([
        '<div class="footer">',
        f"  <p><strong>Snowflake 360 Telemetry Report &mdash; {_esc(topic_name)}</strong></p>",
        f"  <p>Generated on {now_str} &bull; &copy; 2026 Snowflake Inc. All rights reserved.</p>",
        "</div>",
        "</body></html>",
    ])
    return "\n".join(parts)

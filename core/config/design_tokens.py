DESIGN_TOKENS = {
    "color": {
        "brand": {
            "primary": "#003D73",
            "primary_dark": "#11567F",
            "secondary": "#29B5E8",
            "secondary_light": "#75C2D8",
            "accent": "#E8A229",
            "hover": "#0055A5",
        },
        "semantic": {
            "success": "#27AE60",
            "warning": "#F39C12",
            "error": "#E74C3C",
            "info": "#29B5E8",
            "warning_soft_bg": "#fff3cd",
            "warning_soft_border": "#ffc107",
        },
        "surface": {
            "base": "#FFFFFF",
            "subtle": "#F0F2F6",
            "alt": "#f8f9fa",
        },
        "text": {
            "primary": "#262730",
            "secondary": "#666666",
            "muted": "#555555",
            "heading": "#003D73",
            "inverse": "#FFFFFF",
        },
        "border": {
            "default": "#e0e0e0",
            "strong": "#163f59",
            "focus": "#29B5E8",
        },
        "chart": {
            "series": ["#29B5E8", "#11567F", "#75C2D8", "#E8A229"],
            "extended": [
                "#1A7DA8", "#023E8A", "#48CAE4", "#ADE8F4",
                "#0077B6", "#90E0EF", "#CAF0F8", "#03045E",
                "#00B4D8", "#0096C7",
            ],
            "gauge": {
                "low": "#E74C3C",
                "medium": "#F39C12",
                "high": "#27AE60",
                "track": "#E5E7EB",
            },
        },
    },
    "font": {
        "family": {
            "app": "sans-serif",
            "export_primary": "'Inter', sans-serif",
            "export_system": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            "export_alt": "'Space Grotesk', sans-serif",
        },
        "size": {
            "xs": "10px",
            "sm": "11px",
            "md": "12px",
            "base": "14px",
            "lg": "18px",
            "xl": "24px",
            "2xl": "32px",
        },
        "weight": {
            "regular": 400,
            "medium": 500,
            "semibold": 600,
            "bold": 700,
        },
    },
}

C = DESIGN_TOKENS["color"]
F = DESIGN_TOKENS["font"]

BRAND_PRIMARY = C["brand"]["primary"]
BRAND_PRIMARY_DARK = C["brand"]["primary_dark"]
BRAND_SECONDARY = C["brand"]["secondary"]
BRAND_SECONDARY_LIGHT = C["brand"]["secondary_light"]
BRAND_ACCENT = C["brand"]["accent"]
BRAND_HOVER = C["brand"]["hover"]

SUCCESS = C["semantic"]["success"]
WARNING = C["semantic"]["warning"]
ERROR = C["semantic"]["error"]
INFO = C["semantic"]["info"]

SURFACE_BASE = C["surface"]["base"]
SURFACE_SUBTLE = C["surface"]["subtle"]
SURFACE_ALT = C["surface"]["alt"]

TEXT_PRIMARY = C["text"]["primary"]
TEXT_SECONDARY = C["text"]["secondary"]
TEXT_MUTED = C["text"]["muted"]
TEXT_HEADING = C["text"]["heading"]
TEXT_INVERSE = C["text"]["inverse"]

BORDER_DEFAULT = C["border"]["default"]
BORDER_STRONG = C["border"]["strong"]
BORDER_FOCUS = C["border"]["focus"]

CHART_SERIES = C["chart"]["series"]
CHART_EXTENDED = C["chart"]["extended"]
GAUGE_LOW = C["chart"]["gauge"]["low"]
GAUGE_MEDIUM = C["chart"]["gauge"]["medium"]
GAUGE_HIGH = C["chart"]["gauge"]["high"]
GAUGE_TRACK = C["chart"]["gauge"]["track"]

CSS_CUSTOM_PROPERTIES = """
:root {
  --color-brand-primary: #003D73;
  --color-brand-primary-dark: #11567F;
  --color-brand-secondary: #29B5E8;
  --color-brand-secondary-light: #75C2D8;
  --color-brand-accent: #E8A229;
  --color-brand-hover: #0055A5;

  --color-success: #27AE60;
  --color-warning: #F39C12;
  --color-error: #E74C3C;
  --color-info: #29B5E8;
  --color-warning-soft-bg: #fff3cd;
  --color-warning-soft-border: #ffc107;

  --color-surface-base: #FFFFFF;
  --color-surface-subtle: #F0F2F6;
  --color-surface-alt: #f8f9fa;

  --color-text-primary: #262730;
  --color-text-secondary: #666666;
  --color-text-muted: #555555;
  --color-text-heading: #003D73;
  --color-text-inverse: #FFFFFF;

  --color-border-default: #e0e0e0;
  --color-border-strong: #163f59;
  --color-border-focus: #29B5E8;

  --color-chart-1: #29B5E8;
  --color-chart-2: #11567F;
  --color-chart-3: #75C2D8;
  --color-chart-4: #E8A229;
  --color-chart-5: #1A7DA8;
  --color-chart-6: #023E8A;
  --color-chart-7: #48CAE4;
  --color-chart-8: #ADE8F4;

  --color-gauge-low: #E74C3C;
  --color-gauge-medium: #F39C12;
  --color-gauge-high: #27AE60;
  --color-gauge-track: #E5E7EB;

  --font-family-app: sans-serif;
  --font-family-export-primary: 'Inter', sans-serif;
  --font-family-export-system: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-family-export-alt: 'Space Grotesk', sans-serif;

  --font-size-xs: 10px;
  --font-size-sm: 11px;
  --font-size-md: 12px;
  --font-size-base: 14px;
  --font-size-lg: 18px;
  --font-size-xl: 24px;
  --font-size-2xl: 32px;

  --font-weight-regular: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;

  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;

  --shadow-sm: 0 2px 6px rgba(22, 63, 89, 0.08);
  --shadow-md: 0 8px 32px rgba(31, 38, 135, 0.15);
}
"""

"""Theme y paleta cromática del dashboard.

Inspirado en estética financiera (FT, Bloomberg, BIS): tipografía sans serif
sobria, paleta de azules profundos con acentos en gold y crimson para
señales de riesgo. El template `banks_arg` se registra en plotly al
importar este módulo.
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio


# ── Paleta de marca ──────────────────────────────────────────────────────
COLORS = {
    "primary": "#1B365D",       # navy profundo
    "secondary": "#4A6FA5",     # azul medio
    "tertiary": "#7B9DB5",      # azul claro
    "accent": "#C8A951",        # gold
    "accent_warm": "#9B6B43",   # terracotta
    "negative": "#C5283D",      # crimson (riesgo)
    "positive": "#2D5F3F",      # verde profundo
    "neutral_dark": "#2D2D2D",
    "neutral_mid": "#5C5C5C",
    "neutral_light": "#B5B5B5",
    "neutral_bg": "#FAFAFA",
    "neutral_panel": "#EFEFEF",
    "grid": "#E5E5E5",
}

CATEGORICAL = [
    COLORS["primary"],
    COLORS["accent_warm"],
    COLORS["secondary"],
    COLORS["accent"],
    COLORS["tertiary"],
    COLORS["negative"],
    COLORS["positive"],
    COLORS["neutral_mid"],
]

SEQUENTIAL_BLUE = [
    "#EAF1F7", "#C9DAEA", "#A2BFD8", "#7AA3C5",
    "#5288B0", "#3A6F99", "#27577F", "#1B365D",
]

DIVERGING_RED_BLUE = [
    "#C5283D", "#D67487", "#EAB1BD", "#F4F4F4",
    "#A2BFD8", "#5288B0", "#1B365D",
]


# ── Plotly template ──────────────────────────────────────────────────────
def _build_template() -> go.layout.Template:
    return go.layout.Template(
        layout=dict(
            font=dict(
                family='"Inter", "Helvetica Neue", Helvetica, Arial, sans-serif',
                size=13,
                color=COLORS["neutral_dark"],
            ),
            title=dict(
                font=dict(size=15, color=COLORS["neutral_dark"]),
                x=0.0,
                xanchor="left",
                pad=dict(l=0, t=8, b=8),
            ),
            colorway=CATEGORICAL,
            colorscale=dict(
                sequential=[[i / (len(SEQUENTIAL_BLUE) - 1), c] for i, c in enumerate(SEQUENTIAL_BLUE)],
                diverging=[[i / (len(DIVERGING_RED_BLUE) - 1), c] for i, c in enumerate(DIVERGING_RED_BLUE)],
            ),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            xaxis=dict(
                showgrid=False,
                showline=True,
                linecolor=COLORS["grid"],
                linewidth=1,
                ticks="outside",
                tickcolor=COLORS["grid"],
                ticklen=4,
                tickfont=dict(size=11, color=COLORS["neutral_mid"]),
                title=dict(font=dict(size=12, color=COLORS["neutral_mid"])),
                zeroline=False,
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor=COLORS["grid"],
                gridwidth=1,
                showline=False,
                ticks="",
                tickfont=dict(size=11, color=COLORS["neutral_mid"]),
                title=dict(font=dict(size=12, color=COLORS["neutral_mid"])),
                zeroline=True,
                zerolinecolor=COLORS["neutral_light"],
                zerolinewidth=1,
            ),
            legend=dict(
                bgcolor="rgba(255,255,255,0)",
                bordercolor=COLORS["grid"],
                borderwidth=0,
                font=dict(size=11, color=COLORS["neutral_dark"]),
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                title_text="",
            ),
            hoverlabel=dict(
                bgcolor="#FFFFFF",
                bordercolor=COLORS["primary"],
                font=dict(family='"Inter", sans-serif', size=12, color=COLORS["neutral_dark"]),
            ),
            margin=dict(l=10, r=10, t=50, b=30),
        )
    )


pio.templates["banks_arg"] = _build_template()
pio.templates.default = "banks_arg"


# ── Helpers de formato numérico ──────────────────────────────────────────
def fmt_money(v: float, units: str = "ars", precision: int = 1) -> str:
    """Formatea un valor monetario con prefijo y sufijo apropiados.

    units: "ars" → $X.XT/bn/M  |  "usd" → US$X.XB/M/K
    """
    if v is None or (isinstance(v, float) and (v != v)):  # NaN
        return "—"
    sign = "-" if v < 0 else ""
    a = abs(v)
    prefix = "US$" if units == "usd" else "$"
    if units == "usd":
        if a >= 1e9:
            return f"{sign}{prefix}{a/1e9:,.{precision}f} B"
        if a >= 1e6:
            return f"{sign}{prefix}{a/1e6:,.{precision}f} M"
        if a >= 1e3:
            return f"{sign}{prefix}{a/1e3:,.{precision}f} k"
        return f"{sign}{prefix}{a:,.0f}"
    # ARS
    if a >= 1e12:
        return f"{sign}{prefix}{a/1e12:,.{precision}f} T"
    if a >= 1e9:
        return f"{sign}{prefix}{a/1e9:,.{precision}f} bn"
    if a >= 1e6:
        return f"{sign}{prefix}{a/1e6:,.{precision}f} M"
    return f"{sign}{prefix}{a:,.0f}"


def fmt_pct(v: float, precision: int = 1) -> str:
    if v is None or (isinstance(v, float) and (v != v)):
        return "—"
    return f"{v*100:,.{precision}f}%"


def fmt_ratio(v: float, precision: int = 2, suffix: str = "x") -> str:
    if v is None or (isinstance(v, float) and (v != v)):
        return "—"
    return f"{v:,.{precision}f}{suffix}"

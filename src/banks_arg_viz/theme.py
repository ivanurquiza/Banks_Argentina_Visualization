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
                # Cuando la métrica usa SI ($,.2s) plotly muestra k/M/G/T por
                # default. "G" se confunde con USD-billion → forzamos formato
                # con "B" (k/M/B/T) que se entiende mejor en español también.
                exponentformat="B",
                separatethousands=True,
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
                exponentformat="B",
                separatethousands=True,
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
    """Formatea un valor monetario en notación amigable.

    Pesos (units="ars"):
      10¹² → "$1,5 bill" (billones, escala larga castellana = 10¹²)
      10⁹  → "$1.500 M" (mil millones, agregamos '.000' para que se vea grande)
      10⁶  → "$1,5 M" (millones)

    Dólares (units="usd"): usamos convención internacional:
      10⁹ → "US$1,5 B" (billion = 10⁹)
      10⁶ → "US$1,5 M"
    """
    if v is None or (isinstance(v, float) and (v != v)):  # NaN
        return "—"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if units == "usd":
        prefix = "US$"
        if a >= 1e9:
            return f"{sign}{prefix}{a/1e9:,.{precision}f} B"
        if a >= 1e6:
            return f"{sign}{prefix}{a/1e6:,.{precision}f} M"
        if a >= 1e3:
            return f"{sign}{prefix}{a/1e3:,.{precision}f} k"
        return f"{sign}{prefix}{a:,.0f}"
    # ARS — convención castellana
    prefix = "$"
    if a >= 1e12:
        return f"{sign}{prefix}{a/1e12:,.{precision}f} bill"
    if a >= 1e9:
        return f"{sign}{prefix}{a/1e9:,.{precision}f} mil M"
    if a >= 1e6:
        return f"{sign}{prefix}{a/1e6:,.{precision}f} M"
    if a >= 1e3:
        return f"{sign}{prefix}{a/1e3:,.{precision}f} k"
    return f"{sign}{prefix}{a:,.0f}"


def fmt_pct(v: float, precision: int = 1) -> str:
    if v is None or (isinstance(v, float) and (v != v)):
        return "—"
    return f"{v*100:,.{precision}f}%"


def fmt_ratio(v: float, precision: int = 2, suffix: str = "x") -> str:
    if v is None or (isinstance(v, float) and (v != v)):
        return "—"
    return f"{v:,.{precision}f}{suffix}"


def scale_for_axis(values, currency: str = "ars") -> tuple[float, str]:
    """Devuelve (divisor, label) para escalar el eje a una unidad legible.

    Pasamos a la escala donde el valor máximo cae entre 1 y 1000.
    Ejemplo: para ARS si max=8e13 → divisor=1e12, label="billones de ARS".
    """
    try:
        m = max(abs(float(x)) for x in values if x is not None and not (isinstance(x, float) and x != x))
    except (ValueError, TypeError):
        m = 0
    if currency == "usd":
        if m >= 1e9:
            return 1e9, "mil M USD"
        if m >= 1e6:
            return 1e6, "M USD"
        if m >= 1e3:
            return 1e3, "k USD"
        return 1, "USD"
    # ARS
    if m >= 1e12:
        return 1e12, "bill ARS"
    if m >= 1e9:
        return 1e9, "mil M ARS"
    if m >= 1e6:
        return 1e6, "M ARS"
    if m >= 1e3:
        return 1e3, "k ARS"
    return 1, "ARS"

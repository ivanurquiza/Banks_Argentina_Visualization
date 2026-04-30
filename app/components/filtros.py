"""Filtros globales y CSS reutilizables entre páginas."""
from __future__ import annotations

import streamlit as st

from banks_arg_viz.transforms import UNIT_LABELS, to_units, latest_anchor


GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=block');

:root {
    --color-primary: #1B365D;
    --color-secondary: #4A6FA5;
    --color-accent: #C8A951;
    --color-text: #1A1A1A;
    --color-mid: #5C5C5C;
    --color-light: #B5B5B5;
    --color-grid: #E5E5E5;
    --color-positive: #2D5F3F;
    --color-negative: #C5283D;
    --color-card-bg: #FFFFFF;
    --color-card-border: #E5E5E5;
}

html, body, [class*="st-"] {
    font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif !important;
}

h1 {
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
    color: var(--color-primary) !important;
    border-bottom: 2px solid var(--color-grid);
    padding-bottom: 0.4rem;
    margin-bottom: 1.2rem !important;
    font-size: 2rem !important;
}
h2 {
    font-weight: 600 !important;
    color: var(--color-primary) !important;
    letter-spacing: -0.01em !important;
    margin-top: 1.6rem !important;
    margin-bottom: 0.5rem !important;
    font-size: 1.2rem !important;
}
h3 {
    font-weight: 500 !important;
    color: var(--color-primary) !important;
    font-size: 1.05rem !important;
    margin-top: 1rem !important;
}

[data-testid="stSidebar"] {
    background-color: #FAFAFA;
    border-right: 1px solid var(--color-grid);
}
[data-testid="stSidebar"] h2 {
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-mid) !important;
    border-bottom: 1px solid var(--color-grid);
    padding-bottom: 0.3rem;
}

.section-note {
    color: var(--color-mid);
    font-size: 0.85rem;
    margin-top: -0.4rem;
    margin-bottom: 1.2rem;
    font-style: italic;
    line-height: 1.5;
}

hr {
    border: none;
    border-top: 1px solid var(--color-grid);
    margin: 1.6rem 0;
}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px;
}

/* === KPI GRID — responsive 4 cols → 2 cols mobile === */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.7rem;
    margin: 0.6rem 0 1.2rem 0;
}
.kpi-grid-5 { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.kpi-grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }

.kpi-card {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0.4rem 0.6rem 0.4rem 0;
    display: flex;
    flex-direction: column;
}
.kpi-label {
    color: var(--color-mid);
    font-size: 0.72rem;
    font-weight: 400;
    margin-bottom: 0.2rem;
    line-height: 1.2;
}
.kpi-value {
    color: var(--color-text);
    font-size: 1.55rem;
    font-weight: 400;
    line-height: 1.15;
    word-break: break-word;
}
.kpi-delta {
    font-size: 0.78rem;
    margin-top: 0.3rem;
    font-weight: 400;
}
.kpi-delta-positive { color: var(--color-positive); }
.kpi-delta-negative { color: var(--color-negative); }
.kpi-delta::before {
    display: inline-block;
    margin-right: 0.25rem;
    font-size: 0.7rem;
}
.kpi-delta-positive::before { content: "▲"; color: var(--color-positive); }
.kpi-delta-negative::before { content: "▼"; color: var(--color-negative); }
.kpi-help {
    color: var(--color-light);
    font-size: 0.68rem;
    margin-top: 0.3rem;
    line-height: 1.3;
}

/* === FIX DEFINITIVO: nombres de Material Icons leakeando como texto ===
   Si la fuente carga, vemos el ícono normalmente. Si no, ocultamos el texto y
   mostramos un chevron Unicode universal en su lugar. */
.material-symbols-rounded,
.material-symbols-outlined,
.material-icons,
[data-testid="stIconMaterial"] {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
    font-weight: normal;
    font-style: normal;
    font-size: 20px;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    -webkit-font-feature-settings: "liga";
    font-feature-settings: "liga" 1;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}

/* Botón de colapsar la sidebar: si la fuente Material no rasterizó el ligature,
   ocultamos el texto crudo (que muestra "keyboard_double_arrow_right") y
   pintamos un chevron Unicode encima. */
[data-testid="stSidebarCollapseButton"] {
    position: relative;
}
[data-testid="stSidebarCollapseButton"] span {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined" !important;
    font-feature-settings: "liga" 1;
    color: transparent !important;
    /* Si la fuente cargó, los caracteres de control no se ven, vemos el ícono.
       Si la fuente NO cargó (texto crudo "keyboard_double_arrow_right"), se ve
       transparente y el ::after toma protagonismo. */
}
[data-testid="stSidebarCollapseButton"]::after {
    content: "‹‹";
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: var(--color-mid);
    font-family: "Inter", sans-serif !important;
    font-size: 1rem;
    font-weight: 600;
    pointer-events: none;
}

/* Botón de expander si hubiera fuga similar */
[data-testid="stExpanderToggleIcon"] {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined" !important;
    font-feature-settings: "liga" 1;
}

/* === Plotly: títulos plotly tienen padding suficiente al top === */
.js-plotly-plot {
    margin-top: 0.4rem;
}

/* === MOBILE & TABLET (≤ 768px) === */
@media (max-width: 768px) {
    h1 { font-size: 1.4rem !important; padding-bottom: 0.3rem; }
    h2 { font-size: 1rem !important; margin-top: 1.2rem !important; }
    h3 { font-size: 0.95rem !important; }
    .section-note { font-size: 0.75rem; line-height: 1.4; }
    .block-container {
        padding-top: 0.8rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
    }
    .kpi-grid,
    .kpi-grid-5,
    .kpi-grid-3 {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.5rem;
    }
    .kpi-card {
        padding: 0.3rem 0.4rem 0.3rem 0;
    }
    .kpi-label { font-size: 0.66rem; margin-bottom: 0.15rem; }
    .kpi-value { font-size: 1.1rem; }
    .kpi-delta { font-size: 0.68rem; margin-top: 0.2rem; }
    .js-plotly-plot .legend text { font-size: 9px !important; }
    [data-testid="stDataFrame"] { overflow-x: auto; }
    hr { margin: 1rem 0; }
}

/* === MOBILE PEQUEÑO (≤ 480px) === */
@media (max-width: 480px) {
    .kpi-value { font-size: 0.95rem; }
    h1 { font-size: 1.25rem !important; }
}
</style>
"""


def inject_css() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def kpi_card(label: str, value: str, delta: str | None = None, help: str | None = None) -> str:
    """Devuelve HTML one-line para una sola KPI card.

    Crítico: NO usar indentación ni saltos de línea — Streamlit's markdown
    renderer interpreta líneas con 4+ espacios como code blocks y rompe el HTML.
    """
    delta_html = ""
    if delta:
        cls = "kpi-delta-positive" if not delta.lstrip().startswith("-") else "kpi-delta-negative"
        delta_html = f'<div class="kpi-delta {cls}">{delta}</div>'
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )


def kpi_grid(kpis: list[dict], cols: int = 4) -> None:
    """Renderiza una grilla de KPIs (HTML one-line para no romperse).

    En desktop usa `cols` columnas. En mobile (≤ 768px) la grilla colapsa a 2 columnas.

    Cada KPI es un dict con: label, value, delta? (str), help? (str).
    """
    cards = "".join(kpi_card(**k) for k in kpis)
    cls = f"kpi-grid kpi-grid-{cols}" if cols in (3, 5) else "kpi-grid"
    st.markdown(f'<div class="{cls}">{cards}</div>', unsafe_allow_html=True)


def filtro_unidades(default: str = "real") -> str:
    """Selector de unidades. Persiste en session_state."""
    key = "global_units"
    options = ["nominal", "real", "usd"]
    labels = {k: UNIT_LABELS[k] for k in options}
    if key not in st.session_state:
        st.session_state[key] = default

    label = st.radio(
        "Unidades de medida",
        options=options,
        format_func=lambda x: labels[x],
        index=options.index(st.session_state[key]),
        horizontal=False,
        key="_units_radio",
    )
    st.session_state[key] = label
    if label == "real":
        anchor = latest_anchor()
        st.caption(f"ARS constantes a {anchor // 100}-{anchor % 100:02d} (último IPC INDEC).")
    return label


def filtro_proforma() -> bool:
    return st.checkbox(
        "Consolidar fusiones (pro-forma)",
        value=True,
        help=(
            "Aplica fusiones bancarias hacia atrás (ej. Macro+BMA en 2024-11) "
            "para que las series por banco sean comparables en el tiempo."
        ),
    )


def sidebar_global() -> dict:
    """Renderiza la sidebar con filtros globales y devuelve un dict de estado."""
    with st.sidebar:
        st.markdown("## Filtros")
        units = filtro_unidades()
        proforma = filtro_proforma()
        st.markdown("---")
        st.caption(
            "Datos: BCRA (IEF, API monetarias) + INDEC IPC. "
            "Última actualización: archivo `data/sources.yaml`."
        )
    return {"units": units, "proforma": proforma}


def aplicar_unidades(df, value_col: str, units: str, yyyymm_col: str = "yyyymm"):
    if units == "nominal":
        return df
    return to_units(df, value_col=value_col, units=units, yyyymm_col=yyyymm_col)


def formato_valor(units: str) -> str:
    return {
        "nominal": "ARS nominales",
        "real": f"ARS const. ({latest_anchor() // 100}-{latest_anchor() % 100:02d})",
        "usd": "USD",
    }[units]


def section_header(title: str, note: str | None = None) -> None:
    """Encabezado de sección con nota subtitulada."""
    st.markdown(f"## {title}")
    if note:
        st.markdown(f"<p class='section-note'>{note}</p>", unsafe_allow_html=True)

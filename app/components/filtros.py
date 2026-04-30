"""Filtros globales y CSS reutilizables entre páginas."""
from __future__ import annotations

import streamlit as st

from banks_arg_viz.transforms import UNIT_LABELS, to_units, latest_anchor


GLOBAL_CSS = """
<style>
:root {
    --color-primary: #1B365D;
    --color-secondary: #4A6FA5;
    --color-accent: #C8A951;
    --color-text: #1A1A1A;
    --color-mid: #5C5C5C;
    --color-light: #B5B5B5;
    --color-grid: #E5E5E5;
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
}

h2 {
    font-weight: 600 !important;
    color: var(--color-primary) !important;
    letter-spacing: -0.01em !important;
    margin-top: 1.4rem !important;
    margin-bottom: 0.6rem !important;
    font-size: 1.25rem !important;
}

h3 {
    font-weight: 500 !important;
    color: var(--color-primary) !important;
    font-size: 1.05rem !important;
    margin-top: 1rem !important;
}

[data-testid="stMetricValue"] {
    color: var(--color-primary) !important;
    font-weight: 600 !important;
    font-size: 1.6rem !important;
}

[data-testid="stMetricLabel"] {
    color: var(--color-mid) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

[data-testid="stMetricDelta"] svg {
    display: none;
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
    margin-top: -0.6rem;
    margin-bottom: 1rem;
    font-style: italic;
}

.kpi-caption {
    color: var(--color-light);
    font-size: 0.7rem;
    margin-top: -0.8rem;
}

hr {
    border: none;
    border-top: 1px solid var(--color-grid);
    margin: 1.6rem 0;
}
</style>
"""


def inject_css() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


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
    """Encabezado de sección con nota subtitulada (sin emoji)."""
    st.markdown(f"## {title}")
    if note:
        st.markdown(f"<p class='section-note'>{note}</p>", unsafe_allow_html=True)

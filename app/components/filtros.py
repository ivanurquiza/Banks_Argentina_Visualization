"""Filtros globales reutilizables entre páginas."""
from __future__ import annotations

import streamlit as st

from banks_arg_viz.transforms import UNIT_LABELS, to_units, latest_anchor


def filtro_unidades(default: str = "real") -> str:
    """Selector de unidades. Persiste en session_state."""
    key = "global_units"
    options = ["nominal", "real", "usd"]
    labels = {k: UNIT_LABELS[k] for k in options}
    if key not in st.session_state:
        st.session_state[key] = default

    label = st.radio(
        "Unidades",
        options=options,
        format_func=lambda x: labels[x],
        index=options.index(st.session_state[key]),
        horizontal=False,
        key="_units_radio",
    )
    st.session_state[key] = label
    if label == "real":
        anchor = latest_anchor()
        st.caption(f"📌 Pesos constantes a {anchor // 100}-{anchor % 100:02d} (último IPC INDEC)")
    return label


def filtro_periodo(min_yyyymm: int, max_yyyymm: int, default_min: int | None = None) -> tuple[int, int]:
    """Slider de rango de fechas."""
    if default_min is None:
        default_min = max(min_yyyymm, max_yyyymm - 600)  # ~5 años por defecto
    rng = st.slider(
        "Período",
        min_value=min_yyyymm,
        max_value=max_yyyymm,
        value=(default_min, max_yyyymm),
        step=1,
        format="%d",
    )
    return int(rng[0]), int(rng[1])


def filtro_universo(default: str = "todos") -> str:
    """Selector de universo de bancos."""
    options = ["todos", "publicos", "privados_nac", "privados_ext", "aa100"]
    labels = {
        "todos": "Sistema completo",
        "publicos": "Bancos públicos",
        "privados_nac": "Privados nacionales",
        "privados_ext": "Privados extranjeros",
        "aa100": "Top-10 privados (AA100)",
    }
    return st.selectbox(
        "Universo",
        options=options,
        format_func=lambda x: labels[x],
        index=options.index(default),
    )


def filtro_proforma() -> bool:
    return st.checkbox(
        "Consolidar fusiones (proforma)",
        value=True,
        help="Aplica fusiones bancarias hacia atrás (ej. Macro+BMA en 2024-11) "
        "para que las series por banco sean comparables en el tiempo.",
    )


def sidebar_global() -> dict:
    """Renderiza la sidebar con todos los filtros globales y devuelve un dict."""
    with st.sidebar:
        st.markdown("### ⚙️ Filtros globales")
        units = filtro_unidades()
        st.divider()
        proforma = filtro_proforma()
        st.divider()
        st.caption(
            "Datos: BCRA (IEF, API monetarias) + INDEC IPC. "
            "Última actualización: ver archivo `data/sources.yaml`."
        )
    return {"units": units, "proforma": proforma}


def aplicar_unidades(df, value_col: str, units: str, yyyymm_col: str = "yyyymm"):
    if units == "nominal":
        return df
    return to_units(df, value_col=value_col, units=units, yyyymm_col=yyyymm_col)


def formato_valor(units: str) -> str:
    """Devuelve un sufijo legible para los KPIs según unidad."""
    return {
        "nominal": "ARS nominal",
        "real": f"ARS const. ({latest_anchor() // 100}-{latest_anchor() % 100:02d})",
        "usd": "USD",
    }[units]

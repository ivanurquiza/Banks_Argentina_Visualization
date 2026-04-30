"""Banks Argentina — landing page."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import streamlit as st

st.set_page_config(
    page_title="Bancos Argentina — Dashboard público",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

from banks_arg_viz.io import (
    load_balance_mensual,
    load_dim_entidades,
    load_indicadores,
    load_distribgeo,
    load_ipc_nacional,
    load_bcra_serie,
)
from components import inject_css, kpi_grid

inject_css()

st.markdown(
    """
    <h1 style='margin-bottom:0.2rem'>Bancos Argentina</h1>
    <p style='color:#5C5C5C; font-size:1rem; margin-top:0; margin-bottom:0.5rem'>
    Dashboard público del sistema bancario argentino.
    Información de Entidades Financieras (BCRA) + series macro (BCRA, INDEC).
    </p>
    <p style='margin-top:0; margin-bottom:1.4rem'>
    <a href='https://github.com/ivanurquiza' target='_blank' rel='noopener'
       style='display:inline-block; padding:0.35rem 0.85rem; font-size:0.78rem;
              color:#1B365D; background:#FAFAFA; border:1px solid #D5D5D5;
              border-radius:6px; text-decoration:none; font-weight:500;'>
    Iván Urquiza · github.com/ivanurquiza →
    </a>
    </p>
    """,
    unsafe_allow_html=True,
)

bal = load_balance_mensual()
ent = load_dim_entidades()
ind = load_indicadores()
geo = load_distribgeo()
ipc = load_ipc_nacional().dropna(subset=["indice"])
fx = load_bcra_serie("tc_a3500")

st.markdown("&nbsp;")

def _fmt_yyyymm(ym: int) -> str:
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    return f"{meses[ym % 100 - 1]} {ym // 100}"


kpi_grid([
    {"label": "Entidades vigentes", "value": str(int(ent.query("es_vigente == True").shape[0]))},
    {"label": "Período cubierto",
     "value": f"{_fmt_yyyymm(int(bal['yyyymm'].min()))} – {_fmt_yyyymm(int(bal['yyyymm'].max()))}"},
    {"label": "Observaciones balance", "value": f"{len(bal):,}"},
    {"label": "Indicadores publicados", "value": str(int(ind["codigo_linea"].nunique()))},
])

st.markdown("---")

st.markdown("### Secciones")
st.markdown(
    """
    | Sección | Contenido |
    | --- | --- |
    | **Sistema** | Stocks agregados (activo, pasivo, préstamos, depósitos), composición del balance, concentración, indicadores supervisorios. |
    | **Crédito en Pesos** | Capítulo 13 desagregado por destino económico: consumo, vivienda, comercial, automotor. UVA, L/D, cobertura. |
    | **Crédito en Dólares** | Stocks de préstamos y depósitos en moneda extranjera, ratio préstamos/depósitos, dolarización, cobertura de pasivos ME. |
    | **Demanda y Mora** | Estado de Situación de Deudores: irregularidad amplia (Sit. 2+) y estricta (Sit. 3+), por tipo de cartera y por banco. |
    | **Encajes y Liquidez** | Capítulo 11 desagregado: caja, BCRA cuenta corriente, computables, no computables. Tasa efectiva de integración. |
    | **Cartera de Títulos** | Capítulo 12 desagregado: Tesoro, BCRA, LeFi, privados; medición IFRS 9 (FVTPL/AC/FVOCI); exposición soberana por banco. |
    | **Por Banco** | Explorador entidad por entidad: KPIs, balance, indicadores comparados con peers, distribución geográfica. |
    | **Comparador** | Hasta seis bancos lado a lado en métricas seleccionadas. |
    | **Mapa** | Distribución geográfica de crédito y depósitos por provincia, con vista en montos y en participación nacional. |
    """
)

st.markdown("### Filtros globales")
st.markdown(
    """
    - **Unidades**: ARS nominales, ARS constantes (deflactados por IPC INDEC al último mes publicado), USD (TC mayorista A3500 mensual promedio).
    - **Consolidación pro-forma de fusiones**: aplica las fusiones hacia atrás para que las series por banco sean comparables en el tiempo (ej. Macro absorbió BMA en 2024-11).
    """
)

st.markdown("---")

st.markdown("### Última actualización de los datos")
a, b = st.columns(2)
with a:
    st.markdown("**Series macro**")
    st.markdown(f"- IPC INDEC Nacional: hasta **{_fmt_yyyymm(int(ipc['yyyymm'].max()))}**")
    st.markdown(f"- TC mayorista A3500: hasta **{fx['fecha'].max().strftime('%d %b %Y')}**")
with b:
    st.markdown("**Sistema bancario**")
    st.markdown(f"- Balance mensual: hasta **{_fmt_yyyymm(int(bal['yyyymm'].max()))}**")
    st.markdown(f"- Indicadores supervisorios: hasta **{_fmt_yyyymm(int(ind['yyyymm'].max()))}**")
    st.markdown(f"- Distribución geográfica: hasta **{_fmt_yyyymm(int(geo['yyyymm_corte'].max()))}**")

st.markdown("---")

st.markdown(
    """
    <div style='text-align:center; color:#999; font-size:0.78rem; font-style:italic;
                margin-top:2rem; margin-bottom:0.5rem; line-height:1.5;'>
    Iván agradece especialmente a Claude por su esfuerzo y dedicación.<br>
    Cualquier error que esta app pueda tener es, desde ya, inintencional<br>
    y responsabilidad directa de la IA.
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    "Repositorio: github.com/ivanurquiza/Banks_Argentina_Visualization · "
    "Licencia MIT · Datos en dominio público (BCRA / INDEC)."
)

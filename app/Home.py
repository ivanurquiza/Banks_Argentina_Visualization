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
from components import inject_css

inject_css()

st.markdown(
    """
    <h1 style='margin-bottom:0.2rem'>Bancos Argentina</h1>
    <p style='color:#5C5C5C; font-size:1rem; margin-top:0'>
    Dashboard público del sistema bancario argentino.
    Información de Entidades Financieras (BCRA) + series macro (BCRA, INDEC).
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

c1, c2, c3, c4 = st.columns(4)
c1.metric("Entidades vigentes", int(ent.query("es_vigente == True").shape[0]))
c2.metric("Período cubierto", f"{int(bal['yyyymm'].min())} – {int(bal['yyyymm'].max())}")
c3.metric("Observaciones balance", f"{len(bal):,}")
c4.metric("Indicadores publicados", int(ind["codigo_linea"].nunique()))

st.markdown("---")

st.markdown("### Secciones")
st.markdown(
    """
    | Sección | Contenido |
    | --- | --- |
    | **Sistema** | Stocks agregados (activo, pasivo, préstamos, depósitos), composición del balance, concentración, indicadores supervisorios. |
    | **Crédito en Pesos** | Capítulo 13 desagregado por destino económico: consumo, vivienda, comercial, automotor. UVA, L/D, cobertura. |
    | **Crédito en Dólares** | Stocks de préstamos y depósitos en moneda extranjera, ratio préstamos/depósitos, dolarización, cobertura de pasivos ME. |
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

with st.expander("Última actualización de los datos"):
    a, b = st.columns(2)
    with a:
        st.markdown("**Series macro**")
        st.write(f"- IPC INDEC Nacional: hasta **{int(ipc['yyyymm'].max())}**")
        st.write(f"- TC mayorista A3500: hasta **{fx['fecha'].max().date()}**")
    with b:
        st.markdown("**Sistema bancario**")
        st.write(f"- Balance mensual: hasta **{int(bal['yyyymm'].max())}**")
        st.write(f"- Indicadores supervisorios: hasta **{int(ind['yyyymm'].max())}**")
        st.write(f"- Distribución geográfica: hasta **{int(geo['yyyymm_corte'].max())}**")

st.markdown("&nbsp;")
st.caption(
    "Repositorio: github.com/ivanurquiza/Banks_Argentina_Visualization · "
    "Licencia MIT · Datos en dominio público (BCRA / INDEC)."
)

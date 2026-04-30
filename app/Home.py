"""Banks Argentina Visualization — landing page."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

st.set_page_config(
    page_title="Banks Argentina Visualization",
    page_icon="🏦",
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

st.title("🏦 Banks Argentina Visualization")
st.markdown(
    "Dashboard de libre acceso sobre el sistema bancario argentino. "
    "Datos del BCRA (Información de Entidades Financieras + API monetarias) e INDEC."
)

bal = load_balance_mensual()
ent = load_dim_entidades()
ind = load_indicadores()
geo = load_distribgeo()
ipc = load_ipc_nacional().dropna(subset=["indice"])
fx = load_bcra_serie("tc_a3500")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Entidades vigentes", int(ent.query("es_vigente == True").shape[0]))
c2.metric("Período cubierto", f"{int(bal['yyyymm'].min())} – {int(bal['yyyymm'].max())}")
c3.metric("Filas balance", f"{len(bal):,}")
c4.metric("Indicadores CAMELS", int(ind["codigo_linea"].nunique()))

st.divider()

st.subheader("Cómo navegar")
st.markdown(
    """
- **🏛️ Sistema** — agregados sistémicos: stock de crédito y depósitos, composición ME/$, cobertura, indicadores macro.
- **🏦 Por Banco** — explorador entidad por entidad: balance, indicadores CAMELS, evolución histórica.
- **⚖️ Comparador** — compara hasta 4 entidades lado a lado en métricas seleccionadas.
- **🗺️ Mapa** — distribución geográfica de crédito, depósitos y red de sucursales por provincia.

**Filtros globales** en la sidebar:
- Unidades: ARS nominal / ARS constante (deflactado IPC) / USD (TC mayorista A3500)
- Consolidación pro-forma de fusiones (recomendado)
"""
)

with st.expander("📐 Última actualización de datos"):
    a, b = st.columns(2)
    with a:
        st.markdown("**Series macro**")
        st.write(f"- IPC INDEC Nacional: hasta **{int(ipc['yyyymm'].max())}**")
        st.write(f"- TC A3500 BCRA: hasta **{fx['fecha'].max().date()}**")
    with b:
        st.markdown("**Sistema bancario**")
        st.write(f"- Balance mensual: hasta **{int(bal['yyyymm'].max())}**")
        st.write(f"- Indicadores CAMELS: hasta **{int(ind['yyyymm'].max())}**")
        st.write(f"- Distribución geográfica: hasta **{int(geo['yyyymm_corte'].max())}**")

st.divider()
st.caption(
    "Repositorio: github.com/ivanurquiza/Banks_Argentina_Visualization · "
    "Licencia MIT · Datos en dominio público (BCRA / INDEC)"
)

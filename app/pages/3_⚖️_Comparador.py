"""Página: comparador multi-entidad."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Comparador", page_icon="⚖️", layout="wide")

from banks_arg_viz.io import (
    load_balance_mensual,
    load_dim_entidades,
    load_indicadores,
)
from banks_arg_viz.transforms import to_units
from components import sidebar_global, formato_valor

flt = sidebar_global()
units = flt["units"]
proforma = flt["proforma"]

st.title("⚖️ Comparador de bancos")
st.caption(f"Unidades: **{formato_valor(units)}**")

ent = load_dim_entidades()
vigentes = ent[(ent["es_vigente"] == True) & (ent["es_agrupamiento"] != True)].sort_values("nombre")
opciones = {row["codigo_entidad"]: f"{row['nombre']}  ({row['codigo_entidad']})" for _, row in vigentes.iterrows()}

DEFAULT = [c for c in ["00007", "00072", "00285", "00017"] if c in opciones]
seleccion = st.multiselect(
    "Entidades a comparar (máximo 6)",
    options=list(opciones.keys()),
    format_func=lambda c: opciones[c],
    default=DEFAULT[:4],
    max_selections=6,
)

if not seleccion:
    st.info("Seleccioná al menos una entidad para empezar.")
    st.stop()

bal = load_balance_mensual(proforma=proforma)
bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
bal_sel = bal[bal["codigo_entidad"].isin(seleccion)].copy()
ult = int(bal_sel["yyyymm"].max())


def _agg_prefix_at(df, codigo, yyyymm, *prefixes):
    sub = df[
        (df["codigo_entidad"] == codigo)
        & (df["yyyymm"] == yyyymm)
        & df["codigo_cuenta"].str.startswith(tuple(prefixes))
    ]
    return float(sub["saldo"].sum())


def _conv(value, yyyymm):
    if units == "nominal":
        return value
    df = pd.DataFrame({"yyyymm": [yyyymm], "v": [value]})
    return float(to_units(df, value_col="v", units=units)["v"].iloc[0])


# ── Tabla de KPIs comparados
rows = []
for c in seleccion:
    a = _agg_prefix_at(bal, c, ult, "1", "2")
    p = _agg_prefix_at(bal, c, ult, "3")
    pn = _agg_prefix_at(bal, c, ult, "4")
    pres = _agg_prefix_at(bal, c, ult, "13")
    dep = _agg_prefix_at(bal, c, ult, "31")
    rows.append({
        "Banco": vigentes[vigentes["codigo_entidad"] == c]["nombre"].iloc[0],
        "Activo": _conv(a, ult),
        "Pasivo": _conv(p, ult),
        "Patrimonio": _conv(pn, ult),
        "Préstamos": _conv(pres, ult),
        "Depósitos": _conv(dep, ult),
        "Loans/Assets": pres / a if a else float("nan"),
        "Apalanc. (A/PN)": a / pn if pn else float("nan"),
    })
df_kpi = pd.DataFrame(rows).set_index("Banco")
st.subheader(f"KPIs comparados — último mes ({ult})")
st.dataframe(
    df_kpi.style.format({
        "Activo": "{:,.0f}",
        "Pasivo": "{:,.0f}",
        "Patrimonio": "{:,.0f}",
        "Préstamos": "{:,.0f}",
        "Depósitos": "{:,.0f}",
        "Loans/Assets": "{:.1%}",
        "Apalanc. (A/PN)": "{:,.2f}x",
    }),
    use_container_width=True,
)

st.divider()

# ── Series comparadas
st.subheader("Series comparadas")
metric = st.radio(
    "Métrica",
    options=["activo", "pasivo", "prestamos", "depositos", "patrimonio"],
    format_func=lambda x: {
        "activo": "Activo total",
        "pasivo": "Pasivo total",
        "prestamos": "Préstamos",
        "depositos": "Depósitos",
        "patrimonio": "Patrimonio neto",
    }[x],
    horizontal=True,
)

PREFIXES = {
    "activo": ("1", "2"),
    "pasivo": ("3",),
    "prestamos": ("13",),
    "depositos": ("31",),
    "patrimonio": ("4",),
}
prefixes = PREFIXES[metric]
series = (
    bal_sel[bal_sel["codigo_cuenta"].str.startswith(tuple(prefixes))]
    .groupby(["codigo_entidad", "yyyymm", "fecha"], as_index=False)["saldo"].sum()
)
series = series.merge(vigentes[["codigo_entidad", "nombre"]], on="codigo_entidad", how="left")
series = to_units(series, value_col="saldo", units=units)

if not series.empty:
    fig = px.line(
        series, x="fecha", y="saldo", color="nombre",
        title=f"{metric} ({formato_valor(units)})",
    )
    fig.update_layout(legend_title=None, xaxis_title=None, yaxis_title=None, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# ── Indicador CAMELS comparado
st.divider()
st.subheader("Indicador CAMELS comparado")

ind = load_indicadores()
ind_sel = ind[ind["codigo_entidad"].isin(seleccion)].copy()
if not ind_sel.empty:
    descrs = sorted(ind_sel["descripcion_indicador"].dropna().unique())
    sel = st.selectbox("Indicador", options=descrs)
    sub = ind_sel[ind_sel["descripcion_indicador"] == sel].copy()
    sub["fecha"] = pd.to_datetime(sub["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
    sub = sub.merge(vigentes[["codigo_entidad", "nombre"]], on="codigo_entidad", how="left")
    fig = px.line(sub, x="fecha", y="valor", color="nombre", title=sel)
    fig.update_layout(xaxis_title=None, yaxis_title=None, legend_title=None)
    st.plotly_chart(fig, use_container_width=True)

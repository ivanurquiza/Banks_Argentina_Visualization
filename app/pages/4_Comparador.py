"""Página: comparador multi-entidad."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Comparador", page_icon=None, layout="wide")

from banks_arg_viz.io import (
    load_balance_mensual,
    load_dim_entidades,
    load_indicadores,
)
from banks_arg_viz.transforms import to_units
from banks_arg_viz.theme import COLORS, fmt_money, fmt_pct
from components import sidebar_global, formato_valor, inject_css, section_header

inject_css()
flt = sidebar_global()
units = flt["units"]
proforma = flt["proforma"]

st.markdown("# Comparador de bancos")
st.markdown(
    f"<p class='section-note'>Hasta seis entidades lado a lado. Unidades: <b>{formato_valor(units)}</b>.</p>",
    unsafe_allow_html=True,
)

ent = load_dim_entidades()
vigentes = ent[(ent["es_vigente"] == True) & (ent["es_agrupamiento"] != True)].sort_values("nombre")
opciones = {row["codigo_entidad"]: f"{row['nombre']} ({row['codigo_entidad']})" for _, row in vigentes.iterrows()}

DEFAULT = [c for c in ["00007", "00072", "00285", "00017"] if c in opciones]
seleccion = st.multiselect(
    "Entidades a comparar",
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


def _agg_at(df, codigo, ym, *prefixes):
    sub = df[(df["codigo_entidad"] == codigo) & (df["yyyymm"] == ym)
             & df["codigo_cuenta"].str.startswith(tuple(prefixes))]
    return float(sub["saldo"].sum())


def _conv(value, ym):
    if units == "nominal":
        return value
    df = pd.DataFrame({"yyyymm": [ym], "v": [value]})
    return float(to_units(df, value_col="v", units=units)["v"].iloc[0])


units_kpi = "usd" if units == "usd" else "ars"

# ── Tabla KPIs
section_header(f"Snapshot — {ult // 100}-{ult % 100:02d}",
               "Métricas comparables al último mes con datos.")
rows = []
for c in seleccion:
    a = _agg_at(bal, c, ult, "1", "2")
    p = _agg_at(bal, c, ult, "3")
    pn = _agg_at(bal, c, ult, "4")
    pres = _agg_at(bal, c, ult, "13")
    dep = _agg_at(bal, c, ult, "31")
    rows.append({
        "Banco": vigentes[vigentes["codigo_entidad"] == c]["nombre"].iloc[0],
        "Activo": _conv(a, ult),
        "Préstamos": _conv(pres, ult),
        "Depósitos": _conv(dep, ult),
        "Patrimonio": _conv(pn, ult),
        "L/D": pres / dep if dep else float("nan"),
        "Loans/Assets": pres / a if a else float("nan"),
        "Leverage": a / pn if pn else float("nan"),
    })
df_kpi = pd.DataFrame(rows).set_index("Banco")
st.dataframe(
    df_kpi.style.format({
        "Activo": "{:,.0f}", "Préstamos": "{:,.0f}",
        "Depósitos": "{:,.0f}", "Patrimonio": "{:,.0f}",
        "L/D": "{:.1%}", "Loans/Assets": "{:.1%}", "Leverage": "{:,.2f}x",
    }),
    use_container_width=True,
)

st.markdown("---")

# ── Series
section_header("Series comparadas", "Selecciona la métrica para ver su evolución por banco.")

metric = st.radio(
    "Métrica",
    options=["activo", "pasivo", "prestamos", "depositos", "patrimonio"],
    format_func=lambda x: {
        "activo": "Activo total", "pasivo": "Pasivo total",
        "prestamos": "Préstamos", "depositos": "Depósitos",
        "patrimonio": "Patrimonio neto",
    }[x],
    horizontal=True,
)

PREFIXES = {
    "activo": ("1", "2"), "pasivo": ("3",), "prestamos": ("13",),
    "depositos": ("31",), "patrimonio": ("4",),
}
prefixes = PREFIXES[metric]
series = (
    bal_sel[bal_sel["codigo_cuenta"].str.startswith(tuple(prefixes))]
    .groupby(["codigo_entidad", "yyyymm", "fecha"], as_index=False)["saldo"].sum()
    .merge(vigentes[["codigo_entidad", "nombre"]], on="codigo_entidad", how="left")
)
series = to_units(series, value_col="saldo", units=units)

if not series.empty:
    fig = px.line(
        series, x="fecha", y="saldo", color="nombre",
        color_discrete_sequence=[COLORS["primary"], COLORS["accent_warm"], COLORS["secondary"], COLORS["accent"], COLORS["positive"], COLORS["negative"]],
    )
    fig.update_traces(line=dict(width=2.2),
                       hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %Y}<br>%{y:$,.2s}<extra></extra>")
    fig.update_layout(yaxis_tickformat="$,.2s", height=400, hovermode="x unified", yaxis_title=None, xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Indicador CAMELS
section_header("Indicador CAMELS comparado")
ind = load_indicadores()
ind_sel = ind[ind["codigo_entidad"].isin(seleccion)].copy()
if not ind_sel.empty:
    descrs = sorted(ind_sel["descripcion_indicador"].dropna().unique())
    sel = st.selectbox("Indicador", options=descrs)
    sub = ind_sel[ind_sel["descripcion_indicador"] == sel].copy()
    sub["fecha"] = pd.to_datetime(sub["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
    sub = sub.merge(vigentes[["codigo_entidad", "nombre"]], on="codigo_entidad", how="left")
    fig = px.line(
        sub, x="fecha", y="valor", color="nombre",
        color_discrete_sequence=[COLORS["primary"], COLORS["accent_warm"], COLORS["secondary"], COLORS["accent"], COLORS["positive"], COLORS["negative"]],
    )
    fig.update_traces(line=dict(width=2.2),
                       hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %Y}<br>%{y:.2f}<extra></extra>")
    fig.update_layout(height=400, hovermode="x unified", yaxis_title=None, xaxis_title=None,
                       title=dict(text=sel, font=dict(size=14)))
    st.plotly_chart(fig, use_container_width=True)

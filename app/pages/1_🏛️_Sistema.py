"""Página: agregados sistémicos."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Sistema", page_icon="🏛️", layout="wide")

from banks_arg_viz.io import (
    load_balance_mensual,
    load_indicadores,
    load_dim_cuentas,
    load_cuenta_categoria,
    load_dim_entidades,
)
from banks_arg_viz.transforms import to_units
from components import sidebar_global, formato_valor

flt = sidebar_global()
units = flt["units"]
proforma = flt["proforma"]

st.title("🏛️ Sistema bancario — agregados")
st.caption(f"Unidades: **{formato_valor(units)}**")

# ── Carga base
bal = load_balance_mensual(proforma=proforma)
bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
ult = int(bal["yyyymm"].max())
prev_12 = ult - 100


def _agg_prefix(prefix: str) -> pd.DataFrame:
    sub = bal[bal["codigo_cuenta"].str.startswith(prefix)]
    return sub.groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()


# Mapeo BCRA chart of accounts: 1+2 = ACTIVO, 3 = PASIVO, 4 = PATRIMONIO, 13 = PRÉSTAMOS, 31 = DEPÓSITOS
def _agg_prefixes(*prefixes: str) -> pd.DataFrame:
    sub = bal[bal["codigo_cuenta"].str.startswith(tuple(prefixes))]
    return sub.groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()


activo_sis = _agg_prefixes("1", "2")
pasivo_sis = _agg_prefix("3")
patrim_sis = _agg_prefix("4")
prestamos_sis = _agg_prefix("13")
depositos_sis = _agg_prefix("31")


def _at(df, yyyymm):
    return float(df[df["yyyymm"] == yyyymm]["saldo"].sum())


def _convert(value, yyyymm):
    if units == "nominal":
        return value
    df = pd.DataFrame({"yyyymm": [yyyymm], "v": [value]})
    return float(to_units(df, value_col="v", units=units)["v"].iloc[0])


fmt = lambda v: f"${v / 1e12:,.1f} T" if abs(v) >= 1e12 else f"${v / 1e9:,.1f} bn"

c1, c2, c3, c4 = st.columns(4)
for col, (label, df) in zip(
    [c1, c2, c3, c4],
    [
        ("Activo total", activo_sis),
        ("Préstamos", prestamos_sis),
        ("Depósitos", depositos_sis),
        ("Patrimonio neto", patrim_sis),
    ],
):
    v = _convert(_at(df, ult), ult)
    v_prev = _convert(_at(df, prev_12), prev_12)
    delta = None
    if units == "real" and v_prev:
        delta = f"{(v / v_prev - 1) * 100:+.1f}% YoY"
    col.metric(label, fmt(v), delta=delta)

st.caption(f"Datos al **{ult // 100}-{ult % 100:02d}**.")
st.divider()

# ── Series principales del sistema (4 series)
st.subheader("Evolución del sistema")
df_series = pd.concat([
    activo_sis.assign(serie="Activo"),
    pasivo_sis.assign(serie="Pasivo"),
    prestamos_sis.assign(serie="Préstamos"),
    depositos_sis.assign(serie="Depósitos"),
])
df_series = to_units(df_series, value_col="saldo", units=units)

fig = px.line(
    df_series, x="fecha", y="saldo", color="serie",
    title=f"Stocks principales — sistema ({formato_valor(units)})",
)
fig.update_layout(legend_title=None, xaxis_title=None, yaxis_title=None, hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# ── Préstamos vs Depósitos (ratio de cobertura)
st.subheader("Cobertura de depósitos por préstamos")
ratio_df = (
    prestamos_sis.rename(columns={"saldo": "prestamos"})
    .merge(depositos_sis.rename(columns={"saldo": "depositos"}), on=["yyyymm", "fecha"])
)
ratio_df["ratio"] = ratio_df["prestamos"] / ratio_df["depositos"]
fig = px.line(ratio_df, x="fecha", y="ratio", title="Préstamos / Depósitos")
fig.update_layout(xaxis_title=None, yaxis_title=None, yaxis_tickformat=".0%")
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Composición del activo (último mes)
st.subheader(f"Composición del activo del sistema — {ult}")
dim_c = load_dim_cuentas()
bal_ult = bal[bal["yyyymm"] == ult].copy()
bal_ult = bal_ult.merge(dim_c, on="codigo_cuenta", how="left")

# Sumar por sub-section (primer dígito + segundo dígito) para nivel de chapter
bal_ult["chapter"] = bal_ult["codigo_cuenta"].str[:2]
chapter_names = (
    dim_c[dim_c["codigo_cuenta"].str.endswith("0000")][["codigo_cuenta", "denominacion"]]
    .assign(chapter=lambda d: d["codigo_cuenta"].str[:2])
    .drop_duplicates(subset="chapter")
    .set_index("chapter")["denominacion"]
    .to_dict()
)
chap_act = (
    bal_ult[bal_ult["chapter"].str.startswith(("1", "2"))]
    .groupby("chapter", as_index=False)["saldo"].sum()
)
chap_act["denominacion"] = chap_act["chapter"].map(chapter_names).fillna(chap_act["chapter"])
chap_act = chap_act[chap_act["saldo"] > 0].sort_values("saldo", ascending=True)

col_a, col_b = st.columns(2)
with col_a:
    fig = px.bar(
        chap_act, x="saldo", y="denominacion", orientation="h",
        title="Activo — desglose por capítulo",
    )
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

chap_pas = (
    bal_ult[bal_ult["chapter"].str.startswith("3")]
    .groupby("chapter", as_index=False)["saldo"].sum()
)
chap_pas["denominacion"] = chap_pas["chapter"].map(chapter_names).fillna(chap_pas["chapter"])
chap_pas = chap_pas[chap_pas["saldo"] > 0].sort_values("saldo", ascending=True)
with col_b:
    fig = px.bar(
        chap_pas, x="saldo", y="denominacion", orientation="h",
        title="Pasivo — desglose por capítulo",
    )
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Concentración: top entidades
st.subheader("Concentración del sistema — top bancos por activo")
top = (
    bal[bal["codigo_cuenta"].str.startswith(("1", "2")) & (bal["yyyymm"] == ult)]
    .groupby("codigo_entidad", as_index=False)["saldo"]
    .sum()
    .sort_values("saldo", ascending=False)
    .head(20)
)
dim_e = load_dim_entidades()[["codigo_entidad", "nombre"]]
top = top.merge(dim_e, on="codigo_entidad", how="left")
top["share"] = top["saldo"] / top["saldo"].sum() * 100  # share dentro del top

top_units = to_units(top.assign(yyyymm=ult), value_col="saldo", units=units)
fig = px.bar(
    top_units.sort_values("saldo", ascending=True),
    x="saldo", y="nombre", orientation="h",
    title=f"Top 20 bancos por activo total ({formato_valor(units)})",
)
fig.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title=None, yaxis_title=None, height=600)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Categorías temáticas (cuenta_categoria.csv)
st.subheader("Vistas temáticas (CERA, encajes ME, etc.)")
cat = load_cuenta_categoria()[["codigo_cuenta", "categoria"]].dropna()
cat = cat[~cat["codigo_cuenta"].str.contains("%", na=False)]
panel_cat = bal.merge(cat, on="codigo_cuenta", how="inner")

if panel_cat.empty:
    st.info("Sin datos para vistas temáticas.")
else:
    cats = sorted(panel_cat["categoria"].unique())
    sel_cats = st.multiselect(
        "Categorías",
        options=cats,
        default=[c for c in cats if c.startswith("cera")] or cats[:3],
    )
    if sel_cats:
        agg_cat = (
            panel_cat[panel_cat["categoria"].isin(sel_cats)]
            .groupby(["yyyymm", "fecha", "categoria"], as_index=False)["saldo"]
            .sum()
        )
        agg_cat = to_units(agg_cat, value_col="saldo", units=units)
        fig = px.line(
            agg_cat, x="fecha", y="saldo", color="categoria",
            title=f"Series temáticas ({formato_valor(units)})",
        )
        fig.update_layout(legend_title=None, xaxis_title=None, yaxis_title=None, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Indicadores CAMELS (sistema)
st.subheader("Indicadores CAMELS — Sistema financiero")
ind = load_indicadores().copy()
ind = ind.dropna(subset=["valor_sistema_financiero", "descripcion_indicador"])
ind_sis = (
    ind.groupby(["yyyymm", "descripcion_indicador"], as_index=False)["valor_sistema_financiero"].first()
)
indicador = st.selectbox("Indicador", options=sorted(ind_sis["descripcion_indicador"].unique()))
serie = ind_sis[ind_sis["descripcion_indicador"] == indicador].sort_values("yyyymm").copy()
serie["fecha"] = pd.to_datetime(serie["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
fig = px.line(serie, x="fecha", y="valor_sistema_financiero", title=indicador)
fig.update_layout(xaxis_title=None, yaxis_title=None)
st.plotly_chart(fig, use_container_width=True)

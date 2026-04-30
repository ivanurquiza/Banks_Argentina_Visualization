"""Crédito en pesos del sistema bancario.

Disgrega el capítulo 13 (PRÉSTAMOS) en su componente en pesos. Foco en
crédito al Sector Privado (familias y empresas) residente en el país,
desagregado por destino económico, separación hogares/empresas, y
crédito UVA (indexado por inflación).
"""
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

st.set_page_config(page_title="Crédito en Pesos", page_icon=None, layout="wide")

from banks_arg_viz.io import load_dim_entidades, load_balance_mensual
from banks_arg_viz.kpis.credito import (
    stock_credito_pesos_sector,
    composicion_credito_spnf,
    composicion_credito_spnf_detalle,
    loan_to_deposit_pesos,
    share_uva,
    cobertura_previsiones_spnf,
    top_bancos_credito_pesos,
    TIPO_POR_CODIGO_1317,
)
from banks_arg_viz.transforms import to_units
from banks_arg_viz.theme import COLORS, fmt_money, fmt_pct
from components import sidebar_global, formato_valor, inject_css, section_header

inject_css()
flt = sidebar_global()
units = flt["units"]
proforma = flt["proforma"]


st.markdown("# Crédito en Pesos")
st.markdown(
    "<p class='section-note'>Capítulo 13 del plan BCRA — Préstamos en pesos. "
    "Foco en crédito al <b>Sector Privado</b> (familias y empresas) residente país, "
    "desagregado por destino económico, separación hogares vs empresas, y stock UVA.</p>",
    unsafe_allow_html=True,
)


# ── Datos ──────────────────────────────────────────────────────────────
spriv = stock_credito_pesos_sector("spnf", proforma=proforma)  # Sector Privado (cap. 1317)
spub = stock_credito_pesos_sector("sp", proforma=proforma)
ld = loan_to_deposit_pesos(proforma=proforma)
uva = share_uva(proforma=proforma)
cobertura = cobertura_previsiones_spnf(proforma=proforma)
ult = int(spriv["yyyymm"].max())
yoy = ult - 100


def _at(df, ym, col="saldo"):
    s = df[df["yyyymm"] == ym][col]
    return float(s.iloc[0]) if len(s) else float("nan")


def _conv(v, ym):
    if units == "nominal" or pd.isna(v):
        return v
    df = pd.DataFrame({"yyyymm": [ym], "v": [v]})
    return float(to_units(df, value_col="v", units=units)["v"].iloc[0])


units_kpi = "usd" if units == "usd" else "ars"

priv_ult = _at(spriv, ult)
priv_yoy = _at(spriv, yoy)


# ── KPIs ──────────────────────────────────────────────────────────────
st.markdown("## Indicadores principales")
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "Crédito al Sector Privado",
    fmt_money(_conv(priv_ult, ult), units=units_kpi),
    delta=(f"{(_conv(priv_ult, ult)/_conv(priv_yoy, yoy) - 1)*100:+.1f}% YoY" if priv_yoy else None),
    help="Préstamos en pesos a familias y empresas residentes país (capítulo 1317).",
)
c2.metric(
    "Loan-to-Deposit pesos",
    fmt_pct(_at(ld, ult, "ratio")),
    delta=f"{(_at(ld, ult, 'ratio') - _at(ld, yoy, 'ratio')) * 100:+.1f} pp YoY"
    if pd.notna(_at(ld, yoy, "ratio")) else None,
    help="Préstamos pesos / Depósitos pesos (residentes país + exterior).",
)
c3.metric(
    "Crédito al Sector Público",
    fmt_money(_conv(_at(spub, ult), ult), units=units_kpi),
    help="Préstamos al Sector Público no Financiero (provincias, municipios, organismos).",
)
c4.metric(
    "Share UVA en Privado",
    fmt_pct(_at(uva, ult, "share")),
    delta=f"{(_at(uva, ult, 'share') - _at(uva, yoy, 'share')) * 100:+.1f} pp YoY"
    if pd.notna(_at(uva, yoy, "share")) else None,
    help="% del crédito al Sector Privado en pesos indexado por UVA (CER).",
)
c5.metric(
    "Cobertura previsiones",
    fmt_pct(_at(cobertura, ult, "cobertura")),
    help="Previsiones por riesgo / Crédito al Sector Privado. Colchón ante mora.",
)

st.caption(f"Datos al **{ult // 100}-{ult % 100:02d}**.")
st.markdown("---")


# ── Stocks principales por sector
section_header(
    "Stocks de crédito en pesos por sector",
    "Sector Privado (familias + empresas), Sector Público (provincias, municipios, estado), "
    "Sector Financiero (interbancarios domésticos).",
)

sf = stock_credito_pesos_sector("sf", proforma=proforma)
df_series = pd.concat([
    spriv.assign(serie="Sector Privado"),
    spub.assign(serie="Sector Público"),
    sf.assign(serie="Sector Financiero"),
])
df_series = to_units(df_series, value_col="saldo", units=units)

color_map_sector = {
    "Sector Privado": COLORS["primary"],
    "Sector Público": COLORS["accent_warm"],
    "Sector Financiero": COLORS["secondary"],
}

fig = go.Figure()
for serie in ["Sector Privado", "Sector Público", "Sector Financiero"]:
    sub = df_series[df_series["serie"] == serie]
    fig.add_trace(go.Scatter(
        x=sub["fecha"], y=sub["saldo"], name=serie,
        line=dict(color=color_map_sector[serie], width=2.2),
        hovertemplate=f"<b>{serie}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
    ))
fig.update_layout(
    yaxis_tickformat="$,.2s",
    height=380, hovermode="x unified",
    yaxis_title=f"Stock ({formato_valor(units)})", xaxis_title=None,
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Hogares vs Empresas
section_header(
    "Hogares vs Empresas — composición del crédito al Sector Privado",
    "Hogares = consumo (tarjetas, personales, UVA personales) + vivienda (hipotecarios + UVA) "
    "+ automotor (prendarios). Empresas = adelantos cta. cte., documentos, otros préstamos comerciales.",
)


# Mapeo de categoría → grupo Hogares/Empresas
HOGARES_CATS = ("Consumo", "Vivienda", "Automotor / Prendario")
EMPRESAS_CATS = ("Comercial / Empresas",)

comp = composicion_credito_spnf(proforma=proforma)
comp_real = comp[~comp["categoria"].isin(["Intereses / regularizadoras", "Otros"])].copy()
comp_real["grupo"] = comp_real["categoria"].apply(
    lambda c: "Hogares" if c in HOGARES_CATS else ("Empresas" if c in EMPRESAS_CATS else "Otros")
)
agg_he = comp_real.groupby(["yyyymm", "fecha", "grupo"], as_index=False)["saldo"].sum()
agg_he = to_units(agg_he, value_col="saldo", units=units)

color_grupo = {"Hogares": COLORS["primary"], "Empresas": COLORS["accent_warm"]}

col_l, col_r = st.columns([3, 2])

with col_l:
    fig = go.Figure()
    for grp in ["Hogares", "Empresas"]:
        sub = agg_he[agg_he["grupo"] == grp]
        fig.add_trace(go.Scatter(
            x=sub["fecha"], y=sub["saldo"], name=grp, stackgroup="one",
            line=dict(color=color_grupo[grp], width=1.6),
            hovertemplate=f"<b>{grp}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
        ))
    fig.update_layout(
        yaxis_tickformat="$,.2s", height=360, hovermode="x unified",
        yaxis_title=f"Stock ({formato_valor(units)})", xaxis_title=None,
        title=dict(text="Evolución por grupo", font=dict(size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    he_ult = agg_he[agg_he["yyyymm"] == ult].copy()
    fig = px.pie(
        he_ult, values="saldo", names="grupo", hole=0.55,
        color="grupo", color_discrete_map=color_grupo,
    )
    fig.update_traces(
        textposition="inside", textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value:$,.2s} (%{percent})<extra></extra>",
    )
    fig.update_layout(
        height=360, margin=dict(l=20, r=20, t=40, b=10), showlegend=False,
        title=dict(text=f"Cartera al {ult}", font=dict(size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Composición por destino económico
section_header(
    "Composición por destino económico",
    "Apertura del Sector Privado por destino: consumo, vivienda, automotor, comercial.",
)

color_destino = {
    "Consumo": COLORS["accent"],
    "Comercial / Empresas": COLORS["primary"],
    "Vivienda": COLORS["secondary"],
    "Automotor / Prendario": COLORS["accent_warm"],
}

comp_real_units = to_units(comp_real, value_col="saldo", units=units)

col_l, col_r = st.columns([3, 2])

with col_l:
    fig = go.Figure()
    for cat in ["Consumo", "Comercial / Empresas", "Vivienda", "Automotor / Prendario"]:
        sub = comp_real_units[comp_real_units["categoria"] == cat]
        fig.add_trace(go.Scatter(
            x=sub["fecha"], y=sub["saldo"], name=cat,
            stackgroup="one",
            line=dict(color=color_destino[cat], width=1.5),
            hovertemplate=f"<b>{cat}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
        ))
    fig.update_layout(
        yaxis_tickformat="$,.2s", height=360, hovermode="x unified",
        yaxis_title=f"Stock ({formato_valor(units)})", xaxis_title=None,
        title=dict(text="Evolución por destino", font=dict(size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    comp_ult = comp_real_units[comp_real_units["yyyymm"] == ult].copy()
    fig = px.pie(
        comp_ult, values="saldo", names="categoria", hole=0.5,
        color="categoria", color_discrete_map=color_destino,
    )
    fig.update_traces(
        textposition="inside", textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value:$,.2s}<br>(%{percent})<extra></extra>",
    )
    fig.update_layout(
        height=360, margin=dict(l=20, r=20, t=40, b=10), showlegend=False,
        title=dict(text=f"Cartera al {ult}", font=dict(size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────
# UVA — Sección dedicada
# ─────────────────────────────────────────────────────────────────────────
section_header(
    "Crédito UVA — indexado por inflación",
    "Stock de préstamos al Sector Privado denominados en Unidades de Valor Adquisitivo "
    "(actualizadas diariamente por CER). Foco en hipotecarios UVA, personales UVA y otros instrumentos indexados.",
)

# Mapeo de códigos UVA
UVA_CODES = {
    "131745": "Hipotecarios UVA - vivienda",
    "131746": "Hipotecarios UVA - otras garantías",
    "131747": "Prendarios UVA - automotores",
    "131748": "Prendarios UVA - otras garantías",
    "131749": "Personales UVA",
    "131751": "Otros UVA",
    "131752": "Documentos UVA",
}

# Stock por subtipo UVA
det = composicion_credito_spnf_detalle(proforma=proforma)
det_uva = det[det["subtipo"].isin([
    "Hipotecarios UVA sobre vivienda",
    "Otras garantías hipotecarias UVA",
    "Prendarios UVA sobre automotores",
    "Otras garantías prendarias UVA",
    "Personales UVA",
    "Otros UVA",
    "Documentos UVA",
])].copy()

# KPIs de UVA
total_uva_ult = det_uva[det_uva["yyyymm"] == ult]["saldo"].sum()
total_uva_yoy = det_uva[det_uva["yyyymm"] == yoy]["saldo"].sum()

# Hipotecarios UVA específicos
hipot_uva_ult = det_uva[
    (det_uva["yyyymm"] == ult)
    & det_uva["subtipo"].str.contains("Hipotecarios UVA", case=False)
]["saldo"].sum()

# Personales UVA
pers_uva_ult = det_uva[
    (det_uva["yyyymm"] == ult) & (det_uva["subtipo"] == "Personales UVA")
]["saldo"].sum()

# Total hipotecarios (UVA + no UVA) para calcular share UVA en hipotecarios
hipot_total_ult = det[
    (det["yyyymm"] == ult)
    & det["subtipo"].str.contains("Hipotecarios", case=False, regex=False)
]["saldo"].sum()
share_uva_hipot = hipot_uva_ult / hipot_total_ult if hipot_total_ult else 0


# Crecimiento real YoY
total_uva_real_yoy = None
if total_uva_yoy and total_uva_yoy > 0 and units != "usd":
    df_yoy = pd.DataFrame({"yyyymm": [yoy], "v": [total_uva_yoy]})
    df_yoy_real = to_units(df_yoy, value_col="v", units="real")
    df_ult = pd.DataFrame({"yyyymm": [ult], "v": [total_uva_ult]})
    df_ult_real = to_units(df_ult, value_col="v", units="real")
    total_uva_real_yoy = (df_ult_real["v"].iloc[0] / df_yoy_real["v"].iloc[0] - 1) * 100

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Stock UVA total",
    fmt_money(_conv(total_uva_ult, ult), units=units_kpi),
    delta=f"{total_uva_real_yoy:+.1f}% real YoY" if total_uva_real_yoy is not None else None,
    help="Stock total préstamos UVA al Sector Privado (todos los destinos).",
)
c2.metric(
    "Hipotecarios UVA",
    fmt_money(_conv(hipot_uva_ult, ult), units=units_kpi),
    help="Stock hipotecarios UVA (vivienda + otras garantías).",
)
c3.metric(
    "Personales UVA",
    fmt_money(_conv(pers_uva_ult, ult), units=units_kpi),
    help="Préstamos personales en UVA.",
)
c4.metric(
    "% UVA en hipotecarios",
    fmt_pct(share_uva_hipot),
    help="Hipotecarios UVA / Hipotecarios totales (UVA + nominales).",
)


# Composición del UVA por subtipo
st.markdown("&nbsp;")
det_uva_units = to_units(det_uva, value_col="saldo", units=units)

col_l, col_r = st.columns([3, 2])

with col_l:
    fig = go.Figure()
    color_uva = [COLORS["primary"], COLORS["secondary"], COLORS["tertiary"],
                 COLORS["accent"], COLORS["accent_warm"], COLORS["positive"], COLORS["neutral_mid"]]
    subtipos_orden = (
        det_uva_units[det_uva_units["yyyymm"] == ult]
        .sort_values("saldo", ascending=False)["subtipo"].tolist()
    )
    for i, st_ in enumerate(subtipos_orden):
        sub = det_uva_units[det_uva_units["subtipo"] == st_]
        if sub["saldo"].abs().sum() == 0: continue
        fig.add_trace(go.Scatter(
            x=sub["fecha"], y=sub["saldo"], name=st_, stackgroup="one",
            line=dict(color=color_uva[i % len(color_uva)], width=1.5),
            hovertemplate=f"<b>{st_}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
        ))
    fig.update_layout(
        yaxis_tickformat="$,.2s", height=380, hovermode="x unified",
        yaxis_title=f"Stock ({formato_valor(units)})", xaxis_title=None,
        title=dict(text="Composición del crédito UVA", font=dict(size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    uva_ult_pie = det_uva_units[det_uva_units["yyyymm"] == ult].copy()
    uva_ult_pie = uva_ult_pie[uva_ult_pie["saldo"] > 0]
    fig = px.pie(
        uva_ult_pie, values="saldo", names="subtipo", hole=0.5,
        color_discrete_sequence=color_uva,
    )
    fig.update_traces(
        textposition="inside", textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value:$,.2s}<br>(%{percent})<extra></extra>",
    )
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=40, b=10), showlegend=True,
        legend=dict(font=dict(size=10)),
        title=dict(text=f"Cartera UVA al {ult}", font=dict(size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)


# Comparación UVA vs nominal en hipotecarios y personales
section_header(
    "UVA vs nominal — hipotecarios y personales",
    "Compara préstamos indexados (UVA) contra los nominales del mismo destino económico.",
)

# Hipotecarios: UVA (131745+131746) vs nominal (131708+131711)
hipot_uva = det[
    det["subtipo"].str.contains("Hipotecarios UVA|Otras garantías hipotecarias UVA", case=False, regex=True)
].groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum().assign(serie="Hipotecarios UVA")
hipot_nom = det[
    det["subtipo"].isin(["Hipotecarios sobre vivienda", "Otras garantías hipotecarias"])
].groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum().assign(serie="Hipotecarios nominales")

# Personales: UVA (131749) vs nominales (131731+131732)
pers_uva = det[det["subtipo"] == "Personales UVA"].groupby(
    ["yyyymm", "fecha"], as_index=False)["saldo"].sum().assign(serie="Personales UVA")
pers_nom = det[
    det["subtipo"].isin(["Personales", "Personales monto reducido"])
].groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum().assign(serie="Personales nominales")

col_l, col_r = st.columns(2)

for col, (uva_df, nom_df, titulo) in zip(
    [col_l, col_r],
    [
        (hipot_uva, hipot_nom, "Hipotecarios"),
        (pers_uva, pers_nom, "Personales"),
    ],
):
    df_h = pd.concat([uva_df, nom_df])
    df_h = to_units(df_h, value_col="saldo", units=units)
    fig = go.Figure()
    for s, c in [(f"{titulo} UVA", COLORS["accent_warm"]), (f"{titulo} nominales", COLORS["primary"])]:
        # Match by serie name suffix
        if "UVA" in s:
            sub = df_h[df_h["serie"].str.contains("UVA")]
        else:
            sub = df_h[df_h["serie"].str.contains("nominales")]
        fig.add_trace(go.Scatter(
            x=sub["fecha"], y=sub["saldo"], name=s,
            line=dict(color=c, width=2.2),
            hovertemplate=f"<b>{s}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
        ))
    fig.update_layout(
        yaxis_tickformat="$,.2s", height=320, hovermode="x unified",
        yaxis_title=None, xaxis_title=None,
        title=dict(text=f"{titulo}: UVA vs nominal", font=dict(size=13)),
    )
    col.plotly_chart(fig, use_container_width=True)


st.markdown("---")


# ── Detalle por subtipo
section_header(
    "Detalle completo por subtipo",
    "Apertura exhaustiva del Sector Privado por línea contable BCRA. Incluye distinción UVA / no-UVA.",
)
det_ult = det[det["yyyymm"] == ult].copy()
det_ult = det_ult[det_ult["categoria"] != "Otros"]
det_ult = det_ult.assign(yyyymm=ult)
det_ult = to_units(det_ult, value_col="saldo", units=units)
det_ult = det_ult.sort_values(["categoria", "saldo"], ascending=[True, False])
det_ult["es_uva"] = det_ult["subtipo"].str.contains("UVA", case=False, regex=False)

fig = px.bar(
    det_ult.sort_values("saldo", ascending=True),
    x="saldo", y="subtipo", orientation="h",
    color="categoria",
    color_discrete_map=color_destino,
    pattern_shape="es_uva", pattern_shape_map={True: "/", False: ""},
)
fig.update_layout(
    xaxis_tickformat="$,.2s", height=620,
    yaxis_title=None, xaxis_title=f"Stock ({formato_valor(units)})",
    margin=dict(l=0, r=0, t=20, b=20),
)
fig.update_traces(hovertemplate="<b>%{y}</b><br>%{fullData.name}<br>%{x:$,.2s}<extra></extra>")
st.plotly_chart(fig, use_container_width=True)
st.caption("Las barras con patrón rayado indican préstamos UVA (indexados por CER).")

st.markdown("---")


# ── L/D, share UVA y cobertura
section_header(
    "Indicadores macro del crédito en pesos",
)

col_l, col_m, col_r = st.columns(3)

with col_l:
    fig = go.Figure(go.Scatter(
        x=ld["fecha"], y=ld["ratio"],
        line=dict(color=COLORS["primary"], width=2.4),
        fill="tozeroy", fillcolor="rgba(27, 54, 93, 0.06)",
        hovertemplate="<b>%{x|%b %Y}</b><br>L/D: %{y:.1%}<extra></extra>",
    ))
    fig.update_layout(
        yaxis_tickformat=".0%", height=300, showlegend=False,
        title=dict(text="Loan-to-Deposit pesos", font=dict(size=13)),
        yaxis_title=None, xaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_m:
    fig = go.Figure(go.Scatter(
        x=uva["fecha"], y=uva["share"],
        line=dict(color=COLORS["accent_warm"], width=2.4),
        fill="tozeroy", fillcolor="rgba(155, 107, 67, 0.08)",
        hovertemplate="<b>%{x|%b %Y}</b><br>%{y:.1%}<extra></extra>",
    ))
    fig.update_layout(
        yaxis_tickformat=".0%", height=300, showlegend=False,
        title=dict(text="Share UVA / Sector Privado", font=dict(size=13)),
        yaxis_title=None, xaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    fig = go.Figure(go.Scatter(
        x=cobertura["fecha"], y=cobertura["cobertura"],
        line=dict(color=COLORS["positive"], width=2.4),
        fill="tozeroy", fillcolor="rgba(45, 95, 63, 0.08)",
        hovertemplate="<b>%{x|%b %Y}</b><br>Cob.: %{y:.1%}<extra></extra>",
    ))
    fig.update_layout(
        yaxis_tickformat=".0%", height=300, showlegend=False,
        title=dict(text="Cobertura previsiones / S. Privado", font=dict(size=13)),
        yaxis_title=None, xaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Top bancos
section_header(
    "Top bancos por stock de crédito al Sector Privado en pesos",
    "Ranking absoluto al último mes.",
)

top = top_bancos_credito_pesos(ult, proforma=proforma, top=15).copy()
ent = load_dim_entidades()[["codigo_entidad", "nombre"]]
top = top.merge(ent, on="codigo_entidad", how="left")
top = top.assign(yyyymm=ult)
top = to_units(top, value_col="saldo", units=units)

fig = px.bar(
    top.sort_values("saldo", ascending=True),
    x="saldo", y="nombre", orientation="h",
    color_discrete_sequence=[COLORS["primary"]],
)
fig.update_layout(
    xaxis_tickformat="$,.2s", height=480,
    yaxis_title=None, xaxis_title=f"Stock ({formato_valor(units)})",
    margin=dict(l=0, r=0, t=20, b=20),
)
fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:$,.2s}<extra></extra>")
st.plotly_chart(fig, use_container_width=True)


st.markdown("---")
st.caption(
    "Notas. (1) Sector Privado = capítulo 1317 del plan de cuentas BCRA — préstamos en pesos a familias y empresas residentes país. "
    "(2) Hogares = consumo + vivienda + automotor; Empresas = comercial / sola firma / documentos / otros préstamos productivos. "
    "(3) UVA = Unidad de Valor Adquisitivo, indexada al CER (inflación). Cuentas 13174x-13175x. "
    "(4) UVI (Unidad de Vivienda) es un instrumento alternativo discontinuado en la práctica. "
    "(5) Cobertura = previsiones (1319) / crédito al Sector Privado. Es una proxy de provisioning, no equivale al NPL ratio. "
    "Ver `docs/CONTABILIDAD.md`."
)

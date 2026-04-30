"""Crédito en pesos del sistema bancario.

Disgrega el capítulo 13 (PRÉSTAMOS) en su componente en pesos. Foco en
crédito al sector privado no financiero residente en el país (cap. 1317),
desagregado por destino económico (consumo, vivienda, automotor, comercial).
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
    "Foco en crédito al sector privado no financiero residente país (cap. 1317), "
    "desagregado por destino económico. KPIs diseñados para evaluar dinámica del crédito real, "
    "composición productiva vs consumo, y cobertura por riesgo.</p>",
    unsafe_allow_html=True,
)


# ── Datos ──────────────────────────────────────────────────────────────
spnf = stock_credito_pesos_sector("spnf", proforma=proforma)
sp = stock_credito_pesos_sector("sp", proforma=proforma)
ld = loan_to_deposit_pesos(proforma=proforma)
uva = share_uva(proforma=proforma)
cobertura = cobertura_previsiones_spnf(proforma=proforma)
ult = int(spnf["yyyymm"].max())
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

spnf_ult = _v_spnf = _at(spnf, ult)
spnf_yoy = _at(spnf, yoy)


# ── KPIs ──────────────────────────────────────────────────────────────
st.markdown("## Indicadores principales")
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "Crédito SPNF en pesos",
    fmt_money(_conv(spnf_ult, ult), units=units_kpi),
    delta=(f"{(_conv(spnf_ult, ult)/_conv(spnf_yoy, yoy) - 1)*100:+.1f}% YoY" if spnf_yoy else None),
)
c2.metric(
    "Loan-to-Deposit pesos",
    fmt_pct(_at(ld, ult, "ratio")),
    delta=f"{(_at(ld, ult, 'ratio') - _at(ld, yoy, 'ratio')) * 100:+.1f} pp YoY"
    if pd.notna(_at(ld, yoy, "ratio")) else None,
    help="Préstamos pesos (residentes país + exterior) / Depósitos pesos.",
)
c3.metric(
    "Crédito al SP No Fin.",
    fmt_money(_conv(_at(sp, ult), ult), units=units_kpi),
    help="Préstamos al Sector Público no Financiero (provincias, municipios, organismos).",
)
c4.metric(
    "Share UVA",
    fmt_pct(_at(uva, ult, "share")),
    delta=f"{(_at(uva, ult, 'share') - _at(uva, yoy, 'share')) * 100:+.1f} pp YoY"
    if pd.notna(_at(uva, yoy, "share")) else None,
    help="% del crédito SPNF en pesos indexado por UVA (riesgo de tasa real).",
)
c5.metric(
    "Cobertura previsiones",
    fmt_pct(_at(cobertura, ult, "cobertura")),
    help="Previsiones por riesgo / Crédito SPNF. Cuanto mayor, más colchón ante mora.",
)

st.caption(f"Datos al **{ult // 100}-{ult % 100:02d}**.")
st.markdown("---")


# ── Stocks principales
section_header(
    "Stocks de crédito en pesos por sector",
    "Tres sectores: Sector Público (provincias, municipios), Sector Financiero (interbancarios) "
    "y SPNF residentes país (el grueso del crédito al sector privado).",
)

sf = stock_credito_pesos_sector("sf", proforma=proforma)
df_series = pd.concat([
    spnf.assign(serie="SPNF"),
    sp.assign(serie="Sector Público"),
    sf.assign(serie="Sector Financiero"),
])
df_series = to_units(df_series, value_col="saldo", units=units)

color_map_sector = {
    "SPNF": COLORS["primary"],
    "Sector Público": COLORS["accent_warm"],
    "Sector Financiero": COLORS["secondary"],
}

fig = go.Figure()
for serie in ["SPNF", "Sector Público", "Sector Financiero"]:
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


# ── Composición del crédito SPNF
section_header(
    "Composición del crédito SPNF — destino económico",
    "Apertura del capítulo 1317 por destino económico. "
    "Permite distinguir crédito al consumo (tarjetas, personales) del crédito productivo (comercial, vivienda).",
)

color_destino = {
    "Consumo": COLORS["accent"],
    "Comercial / Empresas": COLORS["primary"],
    "Vivienda": COLORS["secondary"],
    "Automotor / Prendario": COLORS["accent_warm"],
    "Otros": COLORS["neutral_light"],
    "Intereses / regularizadoras": COLORS["neutral_light"],
}

comp = composicion_credito_spnf(proforma=proforma)
comp_real = comp[~comp["categoria"].isin(["Intereses / regularizadoras", "Otros"])].copy()
comp_real = to_units(comp_real, value_col="saldo", units=units)

col_l, col_r = st.columns([3, 2])

with col_l:
    fig = go.Figure()
    for cat in ["Consumo", "Comercial / Empresas", "Vivienda", "Automotor / Prendario"]:
        sub = comp_real[comp_real["categoria"] == cat]
        fig.add_trace(go.Scatter(
            x=sub["fecha"], y=sub["saldo"], name=cat,
            stackgroup="one",
            line=dict(color=color_destino[cat], width=1.5),
            hovertemplate=f"<b>{cat}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
        ))
    fig.update_layout(
        yaxis_tickformat="$,.2s", height=380, hovermode="x unified",
        yaxis_title=f"Stock ({formato_valor(units)})", xaxis_title=None,
        title=dict(text="Evolución por destino", font=dict(size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    comp_ult = comp_real[comp_real["yyyymm"] == ult].copy()
    comp_ult["share"] = comp_ult["saldo"] / comp_ult["saldo"].sum()
    fig = px.pie(
        comp_ult, values="saldo", names="categoria", hole=0.5,
        color="categoria", color_discrete_map=color_destino,
    )
    fig.update_traces(
        textposition="inside", textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value:$,.2s}<br>(%{percent})<extra></extra>",
    )
    fig.update_layout(
        height=380, margin=dict(l=20, r=20, t=40, b=10), showlegend=False,
        title=dict(text=f"Cartera al {ult}", font=dict(size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Detalle por subtipo
section_header(
    "Detalle por subtipo (último mes)",
    "Apertura completa de cada destino — incluye distinción UVA / no-UVA.",
)
det = composicion_credito_spnf_detalle(proforma=proforma)
det_ult = det[det["yyyymm"] == ult].copy()
det_ult = det_ult[det_ult["categoria"] != "Otros"]
det_ult = det_ult.assign(yyyymm=ult)
det_ult = to_units(det_ult, value_col="saldo", units=units)
det_ult = det_ult.sort_values(["categoria", "saldo"], ascending=[True, False])
det_ult["color"] = det_ult["categoria"].map(color_destino)

fig = px.bar(
    det_ult.sort_values("saldo", ascending=True),
    x="saldo", y="subtipo", orientation="h",
    color="categoria",
    color_discrete_map=color_destino,
)
fig.update_layout(
    xaxis_tickformat="$,.2s", height=600,
    yaxis_title=None, xaxis_title=f"Stock ({formato_valor(units)})",
    margin=dict(l=0, r=0, t=20, b=20),
)
fig.update_traces(hovertemplate="<b>%{y}</b><br>%{fullData.name}<br>%{x:$,.2s}<extra></extra>")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── L/D y UVA series
section_header(
    "Indicadores macro del crédito en pesos",
    "Loan-to-Deposit, share UVA y cobertura previsiones.",
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
        title=dict(text="Share UVA en SPNF pesos", font=dict(size=13)),
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
        title=dict(text="Cobertura previsiones / SPNF", font=dict(size=13)),
        yaxis_title=None, xaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Top bancos
section_header(
    "Top bancos por stock de crédito SPNF en pesos",
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
    "Notas. (1) Crédito SPNF pesos = capítulo 1317 (residentes país). "
    "(2) UVA: cuentas 13174x-13175x — préstamos indexados al CER. "
    "(3) Cobertura = previsiones (1319) / crédito SPNF. No es el NPL ratio "
    "(que requiere data de Estado de Situación de Deudores) sino una proxy de provisioning. "
    "(4) L/D pesos compara cap. 131+132 (préstamos pesos) con cap. 311+312 (depósitos pesos). "
    "Ver `docs/CONTABILIDAD.md`."
)

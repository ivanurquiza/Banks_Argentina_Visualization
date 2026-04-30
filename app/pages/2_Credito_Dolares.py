"""Sección dedicada al balance en moneda extranjera (USD).

Diseñada como cockpit para analistas, policy makers e inversores que
miran salud del balance ME del sistema bancario argentino.
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

st.set_page_config(page_title="Crédito en Dólares", page_icon=None, layout="wide")

from banks_arg_viz.io import load_dim_entidades
from banks_arg_viz.kpis import (
    stock_me_sistema,
    stock_me,
    loan_to_deposit_me,
    composicion_credito_me,
    share_credito_me,
    share_deposito_me,
    cobertura_encaje_me,
    top_bancos_me,
)
from banks_arg_viz.transforms import to_usd_native
from banks_arg_viz.theme import COLORS, fmt_money, fmt_pct, fmt_ratio
from components import sidebar_global, inject_css, section_header

inject_css()
flt = sidebar_global()
proforma = flt["proforma"]


# ── Header
st.markdown("# Crédito en Dólares")
st.markdown(
    "<p class='section-note'>Stocks en moneda extranjera del sistema bancario argentino. "
    "Capítulos BCRA 115/125/135/315. Reconvertidos a USD usando IPC INDEC y TC mayorista A3500 del mes original.</p>",
    unsafe_allow_html=True,
)


# ── Carga de series base
with st.spinner("Calculando agregados ME del sistema..."):
    pres_me = to_usd_native(stock_me_sistema("credito_spnf", proforma=proforma).rename(columns={"saldo": "valor"}), value_col="valor")
    dep_me = to_usd_native(stock_me_sistema("deposito_residentes", proforma=proforma).rename(columns={"saldo": "valor"}), value_col="valor")
    encaje_me = to_usd_native(stock_me_sistema("efectivo_bancos_me", proforma=proforma).rename(columns={"saldo": "valor"}), value_col="valor")

ult = int(pres_me["yyyymm"].max())
yoy = ult - 100
m12_ago = ult - 100


def _v(df, ym):
    s = df[df["yyyymm"] == ym]["valor"]
    return float(s.iloc[0]) if len(s) else float("nan")


pres_ult = _v(pres_me, ult)
pres_prev = _v(pres_me, yoy)
dep_ult = _v(dep_me, ult)
dep_prev = _v(dep_me, yoy)
ld_ratio = pres_ult / dep_ult if dep_ult else float("nan")
ld_ratio_prev = pres_prev / dep_prev if dep_prev else float("nan")

share_cred_df = share_credito_me(proforma=proforma)
share_dep_df = share_deposito_me(proforma=proforma)
share_cred_ult = float(share_cred_df[share_cred_df["yyyymm"] == ult]["share"].iloc[0]) if not share_cred_df.empty else float("nan")
share_dep_ult = float(share_dep_df[share_dep_df["yyyymm"] == ult]["share"].iloc[0]) if not share_dep_df.empty else float("nan")

cob = cobertura_encaje_me(proforma=proforma)
cob_ult = float(cob[cob["yyyymm"] == ult]["cobertura"].iloc[0]) if not cob.empty else float("nan")


def _delta(curr, prev, kind="pp"):
    if pd.isna(curr) or pd.isna(prev) or prev == 0:
        return None
    if kind == "pp":
        return f"{(curr - prev) * 100:+.1f} pp YoY"
    return f"{(curr / prev - 1) * 100:+.1f}% YoY"


# ── Top KPIs
st.markdown("## Indicadores principales")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Préstamos ME al SPNF", fmt_money(pres_ult, units="usd"), delta=_delta(pres_ult, pres_prev, "pct"))
c2.metric("Depósitos ME residentes", fmt_money(dep_ult, units="usd"), delta=_delta(dep_ult, dep_prev, "pct"))
c3.metric("Loan-to-Deposit ME", fmt_pct(ld_ratio), delta=_delta(ld_ratio, ld_ratio_prev, "pp"))
c4.metric("Dolarización del crédito", fmt_pct(share_cred_ult), help="Share préstamos ME / préstamos totales (residentes país).")
c5.metric("Cobertura encaje BCRA / dep. ME", fmt_pct(cob_ult), help="Saldo en cuenta corriente BCRA en ME (capítulo 115) sobre depósitos ME del SPNF.")

st.caption(
    f"Datos al **{ult // 100}-{ult % 100:02d}**. "
    "Variación interanual sobre el mismo mes 12 meses atrás."
)

st.markdown("---")


# ── Series principales
section_header(
    "Stocks en USD: préstamos vs depósitos",
    "Identidad clave para evaluar capacidad de prestar en moneda dura. "
    "El eje izquierdo está en USD; conversión por TC mayorista A3500 del mes.",
)

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=dep_me["fecha"], y=dep_me["valor"],
        name="Depósitos ME (residentes país)",
        line=dict(color=COLORS["primary"], width=2.2),
        fill="tozeroy", fillcolor="rgba(27, 54, 93, 0.07)",
        hovertemplate="<b>%{x|%b %Y}</b><br>Depósitos: US$%{y:,.0f}<extra></extra>",
    )
)
fig.add_trace(
    go.Scatter(
        x=pres_me["fecha"], y=pres_me["valor"],
        name="Préstamos ME al SPNF",
        line=dict(color=COLORS["accent_warm"], width=2.2),
        fill="tozeroy", fillcolor="rgba(155, 107, 67, 0.07)",
        hovertemplate="<b>%{x|%b %Y}</b><br>Préstamos: US$%{y:,.0f}<extra></extra>",
    )
)
fig.update_layout(
    yaxis_tickformat="$,.0s",
    height=380,
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)


# ── L/D ratio
section_header(
    "Loan-to-Deposit ratio en moneda extranjera",
    "Indicador de eficiencia en intermediación ME. Ratios bajos sugieren "
    "depósitos concentrados en encajes y reservas. El BCRA exige encaje 100% "
    "sobre depósitos en USD (Com. A 3498 y modificaciones).",
)

ld = loan_to_deposit_me(proforma=proforma)
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=ld["fecha"], y=ld["ratio"],
        line=dict(color=COLORS["primary"], width=2.4),
        fill="tozeroy", fillcolor="rgba(27, 54, 93, 0.05)",
        hovertemplate="<b>%{x|%b %Y}</b><br>L/D: %{y:.1%}<extra></extra>",
    )
)
fig.update_layout(
    yaxis_tickformat=".0%",
    yaxis_title=None,
    height=300,
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Dolarización
col_l, col_r = st.columns(2)

with col_l:
    section_header(
        "Dolarización del crédito",
        "Préstamos ME a residentes país / Préstamos totales.",
    )
    fig = go.Figure(
        go.Scatter(
            x=share_cred_df["fecha"], y=share_cred_df["share"],
            line=dict(color=COLORS["accent_warm"], width=2.4),
            fill="tozeroy", fillcolor="rgba(155, 107, 67, 0.08)",
            hovertemplate="<b>%{x|%b %Y}</b><br>%{y:.1%}<extra></extra>",
        )
    )
    fig.update_layout(yaxis_tickformat=".0%", height=300, showlegend=False, yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    section_header(
        "Dolarización de los depósitos",
        "Depósitos ME del SPNF residentes / Depósitos totales del SPNF.",
    )
    fig = go.Figure(
        go.Scatter(
            x=share_dep_df["fecha"], y=share_dep_df["share"],
            line=dict(color=COLORS["secondary"], width=2.4),
            fill="tozeroy", fillcolor="rgba(74, 111, 165, 0.08)",
            hovertemplate="<b>%{x|%b %Y}</b><br>%{y:.1%}<extra></extra>",
        )
    )
    fig.update_layout(yaxis_tickformat=".0%", height=300, showlegend=False, yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Composición del crédito
section_header(
    "Composición del crédito SPNF en USD",
    "Apertura por sub-rubros del capítulo 1357 (Préstamos ME al SPNF residentes país).",
)

comp = composicion_credito_me(proforma=proforma).rename(columns={"saldo": "valor"})
comp = to_usd_native(comp, value_col="valor")
fig = px.area(
    comp.sort_values("fecha"),
    x="fecha", y="valor", color="subcategoria",
    color_discrete_sequence=[COLORS["primary"], COLORS["accent_warm"], COLORS["secondary"], COLORS["accent"]],
)
fig.update_layout(
    yaxis_tickformat="$,.0s",
    height=380,
    hovermode="x unified",
    yaxis_title=None,
    xaxis_title=None,
)
fig.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %Y}<br>US$%{y:,.0f}<extra></extra>")
st.plotly_chart(fig, use_container_width=True)


# ── Cobertura encaje
section_header(
    "Cobertura de los pasivos ME",
    "Saldo del sistema bancario en cuenta corriente BCRA en ME (capítulo 115) "
    "sobre el stock de depósitos ME del SPNF residentes. "
    "Indicador del colchón regulatorio de liquidez en USD.",
)

fig = go.Figure(
    go.Scatter(
        x=cob["fecha"], y=cob["cobertura"],
        line=dict(color=COLORS["positive"], width=2.4),
        fill="tozeroy", fillcolor="rgba(45, 95, 63, 0.08)",
        hovertemplate="<b>%{x|%b %Y}</b><br>Cobertura: %{y:.1%}<extra></extra>",
    )
)
fig.update_layout(yaxis_tickformat=".0%", height=300, showlegend=False, yaxis_title=None)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Top bancos
section_header(
    "Distribución por entidad — último mes disponible",
    "Stocks ME a la fecha. Tablas separadas para préstamos y depósitos.",
)

ent = load_dim_entidades()[["codigo_entidad", "nombre"]]


def _top_table(serie: str, n: int = 15):
    df = top_bancos_me(serie, ult, top=n, proforma=proforma).rename(columns={"saldo": "valor"})
    df = to_usd_native(df, value_col="valor")
    df = df.merge(ent, on="codigo_entidad", how="left")
    return df


pres_top = _top_table("credito_spnf", n=15)
dep_top = _top_table("deposito_residentes", n=15)

col_l, col_r = st.columns(2)
with col_l:
    st.markdown("**Top 15 — Préstamos ME al SPNF**")
    fig = px.bar(
        pres_top.sort_values("valor", ascending=True),
        x="valor", y="nombre", orientation="h",
        color_discrete_sequence=[COLORS["accent_warm"]],
    )
    fig.update_layout(
        xaxis_tickformat="$,.0s",
        height=520, yaxis_title=None, xaxis_title=None,
        margin=dict(l=0, r=0, t=20, b=20),
    )
    fig.update_traces(hovertemplate="<b>%{y}</b><br>US$%{x:,.0f}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    st.markdown("**Top 15 — Depósitos ME residentes país**")
    fig = px.bar(
        dep_top.sort_values("valor", ascending=True),
        x="valor", y="nombre", orientation="h",
        color_discrete_sequence=[COLORS["primary"]],
    )
    fig.update_layout(
        xaxis_tickformat="$,.0s",
        height=520, yaxis_title=None, xaxis_title=None,
        margin=dict(l=0, r=0, t=20, b=20),
    )
    fig.update_traces(hovertemplate="<b>%{y}</b><br>US$%{x:,.0f}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)


# ── Loan/Deposit por banco
section_header(
    "L/D por entidad",
    f"Ratio L/D ME a {ult // 100}-{ult % 100:02d} para entidades con depósitos ME relevantes.",
)

pres_b = stock_me("credito_spnf", proforma=proforma)
dep_b = stock_me("deposito_residentes", proforma=proforma)
pres_b_u = pres_b[pres_b["yyyymm"] == ult].rename(columns={"saldo": "prestamos"})
dep_b_u = dep_b[dep_b["yyyymm"] == ult].rename(columns={"saldo": "depositos"})
ld_b = pres_b_u.merge(dep_b_u[["codigo_entidad", "depositos"]], on="codigo_entidad", how="outer").merge(ent, on="codigo_entidad", how="left")
ld_b["depositos"] = ld_b["depositos"].fillna(0)
ld_b["prestamos"] = ld_b["prestamos"].fillna(0)
# Filtrá entidades chicas: depósitos ME > USD 50M (en homogeneizado: ~10x equivalente).
ld_b = ld_b[ld_b["depositos"] > 5e10]
ld_b["ld"] = ld_b["prestamos"] / ld_b["depositos"]
ld_b = ld_b.sort_values("ld", ascending=True).head(20)

fig = px.bar(
    ld_b, x="ld", y="nombre", orientation="h",
    color="ld", color_continuous_scale="Blues",
)
fig.update_layout(
    xaxis_tickformat=".0%",
    coloraxis_showscale=False,
    height=560, yaxis_title=None, xaxis_title="L/D ME",
    margin=dict(l=0, r=0, t=20, b=20),
)
fig.update_traces(hovertemplate="<b>%{y}</b><br>L/D: %{x:.1%}<extra></extra>")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption(
    "Notas técnicas. El BCRA reporta stocks ME en pesos al TC del cierre del mes; "
    "el panel los homogeneíza por IPC. La conversión a USD nativo deshace ambos pasos: "
    "USD = saldo · (IPC_t / IPC_anchor) / FX_t, con FX = TC mayorista A3500 promedio mensual. "
    "Capítulos: 115 efectivo+depósitos en bancos en ME, 125 títulos en ME, 1357 préstamos ME al SPNF, 315 depósitos ME residentes país."
)

"""Encajes y liquidez bancaria.

Capítulo 11 del plan BCRA — EFECTIVO Y DEPÓSITOS EN BANCOS — desagregado por
moneda y componente. Incluye tasa efectiva de integración del Efectivo Mínimo.
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

st.set_page_config(page_title="Encajes y Liquidez", page_icon=None, layout="wide")

from banks_arg_viz.io import load_dim_entidades
from banks_arg_viz.kpis.reservas import (
    liquidez_componentes,
    deposito_total,
    tasa_integracion_efectiva,
    ENCAJE_BCRA_PESOS,
    ENCAJE_BCRA_ME,
)
from banks_arg_viz.transforms import to_units, to_usd_native
from banks_arg_viz.theme import COLORS, fmt_money, fmt_pct
from components import sidebar_global, formato_valor, inject_css, section_header, kpi_grid

inject_css()
flt = sidebar_global()
units = flt["units"]
proforma = flt["proforma"]


st.markdown("# Encajes y liquidez")
st.markdown(
    "<p class='section-note'>Capítulo 11 del plan BCRA. Desagrega los componentes "
    "del Efectivo Mínimo: caja, BCRA cuenta corriente, otras computables, no computables y "
    "corresponsalía. Calcula la tasa efectiva de integración por banco y por moneda.</p>",
    unsafe_allow_html=True,
)

st.info(
    "**Importante**: la tasa de integración mostrada usa solo **caja + BCRA cuenta corriente + cuentas computables del cap. 11** "
    "como numerador. La BCRA permite integrar el Efectivo Mínimo también con **títulos públicos del Tesoro** (BONTAM, LeFi) "
    "y otros instrumentos del cap. 12 que acá no contamos. Por eso la tasa ARS observada (~10-15%) es menor que la **Posición "
    "de Efectivo Mínimo** publicada oficialmente (~25-30% del sistema). Útil para ver liquidez estricta en BCRA, no para "
    "validar cumplimiento normativo.",
    icon=None,
)


# ── Datos
ti_ars = tasa_integracion_efectiva(moneda="ars", proforma=proforma)
ti_me = tasa_integracion_efectiva(moneda="me", proforma=proforma)
ult = int(ti_ars["yyyymm"].max())
yoy = ult - 100


def _at(df, ym, col):
    s = df[df["yyyymm"] == ym][col]
    return float(s.iloc[0]) if len(s) else float("nan")


# ── KPIs
st.markdown("## Indicadores principales")

t_ars = _at(ti_ars, ult, "tasa")
t_ars_prev = _at(ti_ars, yoy, "tasa")
t_me = _at(ti_me, ult, "tasa")
t_me_prev = _at(ti_me, yoy, "tasa")

# Encaje ME: convertir a USD nativo para legibilidad
me_encaje_homo = pd.DataFrame({"yyyymm": [ult], "v": [_at(ti_me, ult, "encaje")]})
me_encaje_usd = float(to_usd_native(me_encaje_homo, value_col="v")["v"].iloc[0])

kpi_grid([
    {"label": "Tasa integración ARS",
     "value": fmt_pct(t_ars),
     "delta": f"{(t_ars - t_ars_prev) * 100:+.1f} pp YoY" if pd.notna(t_ars_prev) else None},
    {"label": "Tasa integración ME",
     "value": fmt_pct(t_me),
     "delta": f"{(t_me - t_me_prev) * 100:+.1f} pp YoY" if pd.notna(t_me_prev) else None},
    {"label": "Encaje integrado ARS",
     "value": fmt_money(_at(ti_ars, ult, "encaje"), units="ars")},
    {"label": "Encaje integrado ME",
     "value": fmt_money(me_encaje_usd, units="usd")},
])

st.caption(f"Datos al **{ult // 100}-{ult % 100:02d}**.")
st.markdown("---")


# ── Series de tasa
section_header(
    "Tasa efectiva de integración del encaje",
    "Encaje integrado dividido por depósitos. La tasa puede oscilar por cambios "
    "regulatorios (modificación de coeficientes) o por gestión activa del balance bancario. "
    "No equivale a 'cumplimiento del encaje' porque el coeficiente exigido varía por tipo de depósito.",
)

ti_ars["fecha"] = pd.to_datetime(ti_ars["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
ti_me["fecha"] = pd.to_datetime(ti_me["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ti_ars["fecha"], y=ti_ars["tasa"], name="Pesos",
    line=dict(color=COLORS["primary"], width=2.4),
    hovertemplate="<b>Pesos</b><br>%{x|%b %Y}<br>%{y:.1%}<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=ti_me["fecha"], y=ti_me["tasa"], name="Moneda extranjera",
    line=dict(color=COLORS["accent_warm"], width=2.4),
    hovertemplate="<b>ME</b><br>%{x|%b %Y}<br>%{y:.1%}<extra></extra>",
))
fig.update_layout(
    yaxis_tickformat=".0%", height=380, hovermode="x unified",
    yaxis_title="Encaje / Depósitos", xaxis_title=None,
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Composición
section_header(
    "Composición del encaje (último mes)",
    "Cómo se distribuye el efectivo+encaje entre caja física, depósito en BCRA, "
    "otras cuentas computables, no computables y corresponsalía. "
    "BCRA cta. cte. es el componente principal de integración del Efectivo Mínimo.",
)

color_comp = {
    "Caja": COLORS["accent"],
    "BCRA cta. cte. (encaje)": COLORS["primary"],
    "Otras computables": COLORS["secondary"],
    "No computables": COLORS["neutral_light"],
    "Corresponsalía": COLORS["accent_warm"],
}

col_a, col_m = st.columns(2)
for moneda_lbl, moneda_key, col in [("Pesos", "ars", col_a), ("Moneda extranjera", "me", col_m)]:
    comp = liquidez_componentes(moneda=moneda_key, proforma=proforma)
    comp_ult = comp[comp["yyyymm"] == ult].copy()
    comp_ult["abs"] = comp_ult["saldo"].abs()
    if comp_ult.empty:
        continue

    with col:
        fig = px.pie(
            comp_ult, values="abs", names="componente",
            color="componente", color_discrete_map=color_comp, hole=0.5,
        )
        fig.update_traces(
            textposition="outside", textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>%{value:$,.2s}<br>(%{percent})<extra></extra>",
        )
        fig.update_layout(
            title=dict(text=moneda_lbl, font=dict(size=14)),
            height=380, margin=dict(l=20, r=20, t=40, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Evolución de la composición
section_header("Evolución de la composición")
moneda_sel = st.radio(
    "Moneda",
    options=["ars", "me"],
    format_func=lambda x: {"ars": "Pesos", "me": "Moneda extranjera"}[x],
    horizontal=True,
)
comp_t = liquidez_componentes(moneda=moneda_sel, proforma=proforma)
comp_t = to_units(comp_t, value_col="saldo", units=units)

fig = go.Figure()
for c in ["Caja", "BCRA cta. cte. (encaje)", "Otras computables", "Corresponsalía", "No computables"]:
    sub = comp_t[comp_t["componente"] == c]
    if sub["saldo"].abs().sum() == 0:
        continue
    fig.add_trace(go.Scatter(
        x=sub["fecha"], y=sub["saldo"], name=c, stackgroup="one",
        line=dict(color=color_comp[c], width=1.5),
        hovertemplate=f"<b>{c}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
    ))
fig.update_layout(
    yaxis_tickformat="$,.2s", height=380, hovermode="x unified",
    yaxis_title=f"Stock ({formato_valor(units)})", xaxis_title=None,
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Por banco
section_header(
    "Tasa de integración por banco",
    "Comparación de la tasa efectiva entre entidades. Tasas muy bajas pueden "
    "indicar défíict regulatorio; tasas muy altas, exceso de liquidez ociosa.",
)

ti_ars_b = tasa_integracion_efectiva(moneda="ars", proforma=proforma, by_entity=True)
ti_me_b = tasa_integracion_efectiva(moneda="me", proforma=proforma, by_entity=True)
ti_ars_b = ti_ars_b[ti_ars_b["yyyymm"] == ult]
ti_me_b = ti_me_b[ti_me_b["yyyymm"] == ult]

ent = load_dim_entidades()[["codigo_entidad", "nombre"]]
ti_ars_b = ti_ars_b.merge(ent, on="codigo_entidad", how="left")
ti_me_b = ti_me_b.merge(ent, on="codigo_entidad", how="left")

# Filtrar entidades con depósitos materiales
DEP_MIN = 1e10
ti_ars_b = ti_ars_b[ti_ars_b["depositos"] > DEP_MIN].copy()
ti_me_b = ti_me_b[ti_me_b["depositos"] > DEP_MIN].copy()

col_a, col_m = st.columns(2)
with col_a:
    df = ti_ars_b.sort_values("tasa", ascending=False).head(20).sort_values("tasa", ascending=True)
    fig = px.bar(
        df, x="tasa", y="nombre", orientation="h",
        color="tasa", color_continuous_scale="Blues",
    )
    fig.update_layout(
        title=dict(text="Pesos — top 20 por tasa de integración", font=dict(size=13)),
        xaxis_tickformat=".0%", coloraxis_showscale=False,
        height=560, yaxis_title=None, xaxis_title="Encaje / Depósitos",
        margin=dict(l=0, r=0, t=40, b=20),
    )
    fig.add_vline(x=t_ars, line_width=1, line_dash="dash", line_color=COLORS["neutral_mid"],
                  annotation_text="Sistema", annotation_position="top")
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Tasa: %{x:.1%}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)

with col_m:
    df = ti_me_b.sort_values("tasa", ascending=False).head(20).sort_values("tasa", ascending=True)
    fig = px.bar(
        df, x="tasa", y="nombre", orientation="h",
        color="tasa", color_continuous_scale="Oranges",
    )
    fig.update_layout(
        title=dict(text="Moneda extranjera — top 20 por tasa de integración", font=dict(size=13)),
        xaxis_tickformat=".0%", coloraxis_showscale=False,
        height=560, yaxis_title=None, xaxis_title="Encaje / Depósitos",
        margin=dict(l=0, r=0, t=40, b=20),
    )
    fig.add_vline(x=t_me, line_width=1, line_dash="dash", line_color=COLORS["neutral_mid"],
                  annotation_text="Sistema", annotation_position="top")
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Tasa: %{x:.1%}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)


# ── Tabla
section_header("Detalle por entidad")
moneda_tabla = st.radio(
    "Moneda",
    options=["ars", "me"],
    format_func=lambda x: {"ars": "Pesos", "me": "Moneda extranjera"}[x],
    horizontal=True,
    key="tabla_moneda",
)

t_b = ti_ars_b if moneda_tabla == "ars" else ti_me_b
t_b = t_b.assign(yyyymm=ult)
t_b_disp = to_units(t_b, value_col="encaje", units=units)
t_b_disp = to_units(t_b_disp, value_col="depositos", units=units)
t_b_disp = (
    t_b_disp[["nombre", "encaje", "depositos", "tasa"]]
    .rename(columns={
        "nombre": "Banco",
        "encaje": f"Encaje integrado ({formato_valor(units)})",
        "depositos": f"Depósitos ({formato_valor(units)})",
        "tasa": "Tasa integración",
    })
    .sort_values("Tasa integración", ascending=False)
)

st.dataframe(
    t_b_disp.style.format({
        f"Encaje integrado ({formato_valor(units)})": "{:,.0f}",
        f"Depósitos ({formato_valor(units)})": "{:,.0f}",
        "Tasa integración": "{:.1%}",
    }),
    use_container_width=True, hide_index=True, height=440,
)

st.markdown("---")
st.caption(
    "Notas. (1) Encaje integrado = Caja + BCRA cta. cte. + Otras computables (no incluye No computables ni Corresponsalía exterior). "
    "(2) Para pesos los depósitos son cap. 311+312 (residentes país y exterior); en ME son cap. 315+316. "
    "Excluimos 313 y 314 (depósitos de títulos públicos) por no ser encajables. "
    "(3) Sin acceso al coeficiente regulatorio mes a mes no separamos 'obligatorio' de 'voluntario / excedente'. "
    "Este indicador es una proxy útil pero no equivale a cumplimiento normativo. Ver `docs/CONTABILIDAD.md`."
)

"""Demanda y Mora — Estado de Situación de Deudores.

Página dedicada a la calidad de la cartera de crédito y a la dinámica de la mora.
Datos del Estado de Situación de Deudores (panel_esd) con frecuencia trimestral.
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

st.set_page_config(page_title="Demanda y Mora", page_icon=None, layout="wide")

from banks_arg_viz.kpis.mora import (
    irregularidad_sistema,
    irregularidad_por_tipo_cartera,
    composicion_situaciones_sistema,
    previsiones_sobre_cartera,
    irregularidad_por_banco,
)
from banks_arg_viz.theme import COLORS, fmt_money, fmt_pct
from components import sidebar_global, inject_css, section_header, kpi_grid

inject_css()
flt = sidebar_global()


st.markdown("# Demanda y Mora")
st.markdown(
    "<p class='section-note'>Estado de Situación de Deudores (ESD) del sistema bancario argentino. "
    "Datos trimestrales desde 2014 que abren la cartera por situación crediticia (1 a 5+) "
    "y por tipo de cartera (Comercial, Consumo/Vivienda, Comercial Asimilable a Consumo).</p>",
    unsafe_allow_html=True,
)

# Aclaración metodológica destacada
st.info(
    "**Definiciones de irregularidad usadas en esta página**:  \n"
    "• **Irregularidad amplia (Sit. 2+)**: créditos en seguimiento especial, riesgo medio, alto y irrecuperables. "
    "Captura deterioro temprano del crédito.  \n"
    "• **Mora estricta (Sit. 3+)**: definición utilizada por el BCRA en publicaciones oficiales — "
    "solo créditos con problemas, alto riesgo de insolvencia e irrecuperables.  \n\n"
    "Esta app expone ambas para cubrir señales tempranas de deterioro y mora oficial.",
    icon=None,
)


# ── Datos ────────────────────────────────────────────────────────────────
sis = irregularidad_sistema()
# Filtrar a 2018+ para evitar inconsistencias muy antiguas
sis = sis[sis["yyyymm"] >= 201801].copy()
ult = int(sis["yyyymm"].max())
yoy = ult - 100  # comparación interanual

tipo = irregularidad_por_tipo_cartera()
tipo = tipo[tipo["yyyymm"] >= 201801]

cob = previsiones_sobre_cartera()
cob = cob[cob["yyyymm"] >= 201801]


def _at(df, ym, col):
    s = df[df["yyyymm"] == ym][col]
    return float(s.iloc[0]) if len(s) else float("nan")


# ── KPIs ──────────────────────────────────────────────────────────────
amplia_ult = _at(sis, ult, "amplia") / 100
amplia_yoy = _at(sis, yoy, "amplia") / 100 if not pd.isna(_at(sis, yoy, "amplia")) else None
estricta_ult = _at(sis, ult, "estricta") / 100
estricta_yoy = _at(sis, yoy, "estricta") / 100 if not pd.isna(_at(sis, yoy, "estricta")) else None
cob_ult = _at(cob, ult, "cobertura_cartera")
cob_yoy = _at(cob, yoy, "cobertura_cartera") if not pd.isna(_at(cob, yoy, "cobertura_cartera")) else None

kpi_grid([
    {"label": "Irregularidad amplia (Sit. 2+)",
     "value": fmt_pct(amplia_ult),
     "delta": f"{(amplia_ult - amplia_yoy) * 100:+.1f} pp YoY" if amplia_yoy is not None else None},
    {"label": "Mora estricta (Sit. 3+)",
     "value": fmt_pct(estricta_ult),
     "delta": f"{(estricta_ult - estricta_yoy) * 100:+.1f} pp YoY" if estricta_yoy is not None else None},
    {"label": "Cobertura previsiones",
     "value": fmt_pct(cob_ult),
     "delta": f"{(cob_ult - cob_yoy) * 100:+.1f} pp YoY" if cob_yoy is not None else None},
    {"label": "Período",
     "value": f"{ult // 100}-{ult % 100:02d}"},
])

st.caption(
    "Frecuencia trimestral. Datos del último corte disponible. "
    "Cobertura previsiones = Previsiones por riesgo / Cartera total."
)
st.markdown("---")


# ── Series de irregularidad
section_header(
    "Evolución de la irregularidad",
    "Las dos definiciones — amplia (Sit. 2+) y estricta (Sit. 3+) — graficadas en paralelo. "
    "La distancia entre ambas refleja el peso de los créditos en seguimiento especial / riesgo bajo.",
)

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=sis["fecha"], y=sis["amplia"] / 100,
    name="Irregularidad amplia (Sit. 2+)",
    line=dict(color=COLORS["accent_warm"], width=2.4),
    fill="tozeroy", fillcolor="rgba(155, 107, 67, 0.06)",
    hovertemplate="<b>Amplia</b><br>%{x|%b %Y}<br>%{y:.1%}<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=sis["fecha"], y=sis["estricta"] / 100,
    name="Mora estricta (Sit. 3+)",
    line=dict(color=COLORS["primary"], width=2.4),
    fill="tozeroy", fillcolor="rgba(27, 54, 93, 0.06)",
    hovertemplate="<b>Estricta</b><br>%{x|%b %Y}<br>%{y:.1%}<extra></extra>",
))
fig.update_layout(
    yaxis_tickformat=".1%", height=380, hovermode="x unified",
    yaxis_title="% de la cartera total", xaxis_title=None,
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Composición por situación
section_header(
    "Composición de la cartera por situación crediticia",
    "Stack del 100% de la cartera del sistema, mostrando la distribución entre las 5 situaciones BCRA. "
    "La situación 1 corresponde a normal; situaciones 2 a 5 reflejan deterioro creciente.",
)

# Compute % stacked
sis_pct = sis[["yyyymm", "fecha", "sit1_pct", "sit2_pct", "sit3_pct", "sit4_pct", "sit5_pct", "sit6_pct"]].copy()

color_sit = {
    "Sit. 1 — Normal": COLORS["positive"],
    "Sit. 2 — Seguim. especial": COLORS["accent"],
    "Sit. 3 — Con problemas": COLORS["accent_warm"],
    "Sit. 4 — Alto riesgo": COLORS["negative"],
    "Sit. 5 — Irrecuperable": "#7F1D2A",
    "Sit. 6 — Irrec. téc.": "#5C5C5C",
}
SITS_LBL = [
    ("Sit. 1 — Normal", "sit1_pct"),
    ("Sit. 2 — Seguim. especial", "sit2_pct"),
    ("Sit. 3 — Con problemas", "sit3_pct"),
    ("Sit. 4 — Alto riesgo", "sit4_pct"),
    ("Sit. 5 — Irrecuperable", "sit5_pct"),
    ("Sit. 6 — Irrec. téc.", "sit6_pct"),
]

fig = go.Figure()
for label, col in SITS_LBL:
    if col not in sis_pct.columns:
        continue
    sub = sis_pct[["fecha", col]].dropna()
    fig.add_trace(go.Scatter(
        x=sub["fecha"], y=sub[col] / 100, name=label,
        stackgroup="one",
        line=dict(color=color_sit[label], width=1),
        hovertemplate=f"<b>{label}</b><br>%{{x|%b %Y}}<br>%{{y:.1%}}<extra></extra>",
    ))
fig.update_layout(
    yaxis_tickformat=".0%", height=380, hovermode="x unified",
    yaxis_title="% de la cartera total", xaxis_title=None,
    yaxis=dict(range=[0, 1]),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Por tipo de cartera
section_header(
    "Irregularidad por tipo de cartera",
    "Comercial (préstamos a empresas), Consumo o Vivienda (préstamos a familias), "
    "Comercial Asimilable a Consumo (créditos pequeños tratados como consumo). "
    "Los hogares típicamente muestran mayor mora que las empresas.",
)

color_cart = {
    "Comercial": COLORS["primary"],
    "Consumo / Vivienda": COLORS["accent_warm"],
    "Comercial asimilable a consumo": COLORS["secondary"],
}

fig = go.Figure()
for cart in ["Comercial", "Consumo / Vivienda", "Comercial asimilable a consumo"]:
    sub = tipo[tipo["cartera"] == cart]
    fig.add_trace(go.Scatter(
        x=sub["fecha"], y=sub["amplia"] / 100, name=cart,
        line=dict(color=color_cart[cart], width=2.2),
        hovertemplate=f"<b>{cart}</b><br>%{{x|%b %Y}}<br>%{{y:.1%}}<extra></extra>",
    ))
fig.update_layout(
    yaxis_tickformat=".1%", height=380, hovermode="x unified",
    yaxis_title="Irregularidad amplia (% cartera)", xaxis_title=None,
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Cobertura previsiones
section_header(
    "Cobertura por previsiones",
    "Previsiones constituidas como % de la cartera total. "
    "Indicador de cuán preparado está el sistema para absorber pérdidas crediticias.",
)

fig = go.Figure(go.Scatter(
    x=cob["fecha"], y=cob["cobertura_cartera"],
    line=dict(color=COLORS["positive"], width=2.4),
    fill="tozeroy", fillcolor="rgba(45, 95, 63, 0.08)",
    hovertemplate="<b>%{x|%b %Y}</b><br>Cobertura: %{y:.1%}<extra></extra>",
))
fig.update_layout(
    yaxis_tickformat=".1%", height=300, showlegend=False,
    yaxis_title="Previsiones / Cartera total", xaxis_title=None,
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Top bancos
section_header(
    "Bancos con mayor irregularidad — último trimestre disponible",
    "Filtramos entidades con cartera material (> $100 M en pesos homogéneos). "
    "Top 15 ordenados por irregularidad amplia (Sit. 2+).",
)

ib = irregularidad_por_banco(ult)
ib = ib[ib["total"] > 1e8].copy()
ib_top = ib.sort_values("amplia", ascending=False).head(15)

fig = go.Figure()
fig.add_trace(go.Bar(
    x=ib_top["amplia"] / 100,
    y=ib_top["nombre_entidad"],
    name="Amplia (Sit. 2+)",
    orientation="h",
    marker=dict(color=COLORS["accent_warm"]),
    hovertemplate="<b>%{y}</b><br>Amplia: %{x:.1%}<extra></extra>",
))
fig.add_trace(go.Bar(
    x=ib_top["estricta"] / 100,
    y=ib_top["nombre_entidad"],
    name="Estricta (Sit. 3+)",
    orientation="h",
    marker=dict(color=COLORS["primary"]),
    hovertemplate="<b>%{y}</b><br>Estricta: %{x:.1%}<extra></extra>",
))
fig.update_layout(
    barmode="overlay", height=560,
    yaxis=dict(autorange="reversed", title=None),
    xaxis=dict(title="% de la cartera de la entidad", tickformat=".0%"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    margin=dict(l=0, r=0, t=20, b=20),
)
st.plotly_chart(fig, use_container_width=True)

# Tabla detallada
section_header("Tabla — irregularidad por banco")
tabla = ib.sort_values("amplia", ascending=False).copy()
tabla["amplia_pct"] = tabla["amplia"] / 100
tabla["estricta_pct"] = tabla["estricta"] / 100
tabla_show = tabla[["nombre_entidad", "total", "amplia_pct", "estricta_pct"]].rename(columns={
    "nombre_entidad": "Banco",
    "total": "Cartera ($)",
    "amplia_pct": "Irreg. amplia",
    "estricta_pct": "Mora estricta",
})
st.dataframe(
    tabla_show.style.format({
        "Cartera ($)": "{:,.0f}",
        "Irreg. amplia": "{:.1%}",
        "Mora estricta": "{:.1%}",
    }),
    use_container_width=True, hide_index=True, height=440,
)


st.markdown("---")
st.caption(
    "Notas. (1) Datos trimestrales del Estado de Situación de Deudores (BCRA). "
    "(2) Irregularidad amplia = (Total - Sit. 1) / Total. Mora estricta = (Sit. 3+) / Total. "
    "(3) Las cuentas del ESD tienen totales en pesos homogéneos y porcentajes por situación. "
    "Para agregaciones a sistema usamos promedios ponderados por cartera. "
    "(4) Los códigos AA* y agregados (BANCOS, SISTEMA FINANCIERO) se filtran del ranking por banco. "
    "Ver `docs/CONTABILIDAD.md`."
)

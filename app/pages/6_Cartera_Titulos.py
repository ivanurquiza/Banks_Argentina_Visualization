"""Cartera de títulos del sistema bancario.

Disgrega el capítulo 12 del plan de cuentas BCRA por emisor (Tesoro/BCRA/LeFi/Privado),
moneda (ARS / USD país / USD exterior) y medición contable IFRS 9 (FVTPL / AC / FVOCI).
Diseñado para análisis de exposición soberana, riesgo de mark-to-market y concentración.
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

st.set_page_config(page_title="Cartera de Títulos", page_icon=None, layout="wide")

from banks_arg_viz.io import load_balance_mensual, load_dim_entidades
from banks_arg_viz.kpis.securities import (
    catalogo_titulos,
    stock_titulos_sistema,
    exposicion_por_banco,
    sov_exposure_pct_activo,
)
from banks_arg_viz.transforms import to_units
from banks_arg_viz.theme import COLORS, fmt_money, fmt_pct
from components import sidebar_global, formato_valor, inject_css, section_header

inject_css()
flt = sidebar_global()
units = flt["units"]
proforma = flt["proforma"]

st.markdown("# Cartera de Títulos")
st.markdown(
    "<p class='section-note'>Capítulo 12 del plan BCRA — TÍTULOS PÚBLICOS Y PRIVADOS — "
    "desagregado por emisor, moneda y medición contable IFRS 9. "
    "Indicadores diseñados para evaluar exposición soberana, riesgo de mark-to-market y concentración.</p>",
    unsafe_allow_html=True,
)


# ── Datos ────────────────────────────────────────────────────────────────
panel = stock_titulos_sistema(proforma=proforma, by=("emisor", "moneda", "medicion"))
ult = int(panel["yyyymm"].max())
yoy = ult - 100

bal = load_balance_mensual(proforma=proforma)
bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
activo_sis = (
    bal[bal["codigo_cuenta"].str.startswith(("1", "2"))]
    .groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
)


def _conv(v, ym):
    if units == "nominal" or pd.isna(v):
        return v
    df = pd.DataFrame({"yyyymm": [ym], "v": [v]})
    return float(to_units(df, value_col="v", units=units)["v"].iloc[0])


units_kpi = "usd" if units == "usd" else "ars"

# ── KPIs ──────────────────────────────────────────────────────────────
panel_ult = panel[panel["yyyymm"] == ult]
panel_yoy = panel[panel["yyyymm"] == yoy]

total_ult = panel_ult["saldo"].sum()
total_yoy = panel_yoy["saldo"].sum()
sov_mask = panel_ult["emisor"].str.startswith("Tesoro") | panel_ult["emisor"].str.startswith("LeFi")
bcra_mask = panel_ult["emisor"].str.startswith("BCRA")
priv_mask = panel_ult["emisor"].str.startswith("Privado")
fvtpl_mask = panel_ult["medicion"] == "FVTPL"

sov_ult = panel_ult[sov_mask]["saldo"].sum()
bcra_ult = panel_ult[bcra_mask]["saldo"].sum()
priv_ult = panel_ult[priv_mask]["saldo"].sum()
fvtpl_ult = panel_ult[fvtpl_mask]["saldo"].sum()

activo_ult = float(activo_sis[activo_sis["yyyymm"] == ult]["saldo"].iloc[0])

st.markdown("## Indicadores principales")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Stock total cartera", fmt_money(_conv(total_ult, ult), units=units_kpi),
          delta=f"{((total_ult / total_yoy - 1) * 100):+.1f}% YoY" if total_yoy else None)
c2.metric("Sovereign / Activo", fmt_pct(sov_ult / activo_ult), help="Exposición a deuda Tesoro+LeFi como % del activo total del sistema.")
c3.metric("BCRA / Activo", fmt_pct(bcra_ult / activo_ult), help="Exposición a paper del banco central como % del activo total.")
c4.metric("Privados / Activo", fmt_pct(priv_ult / activo_ult))
c5.metric("FVTPL / Cartera", fmt_pct(fvtpl_ult / total_ult), help="% de la cartera medida a Fair Value Through P&L. Se ajusta a mercado y pega en resultados ante volatilidad.")

st.caption(f"Datos al **{ult // 100}-{ult % 100:02d}**. "
           f"Activo total del sistema: {fmt_money(_conv(activo_ult, ult), units=units_kpi)}.")

st.markdown("---")


# ── Composición sistémica (matriz emisor × moneda) ─────────────────────
section_header(
    "Composición de la cartera",
    "Apertura por moneda y emisor en el último mes. El bloque de Tesoro/Sector Público "
    "agrupa títulos del gobierno nacional y provinciales (no separables a nivel de cuenta).",
)

comp = panel_ult.groupby(["moneda", "emisor"], as_index=False)["saldo"].sum()
comp = comp[comp["saldo"] > 0]


def _emisor_simple(e: str) -> str:
    if e.startswith("Tesoro"):
        return "Tesoro / Sector Público"
    if e.startswith("LeFi"):
        return "LeFi (Tesoro)"
    if e.startswith("BCRA"):
        return "BCRA"
    if e.startswith("Privado"):
        return "Privado"
    return e


comp["emisor_grupo"] = comp["emisor"].apply(_emisor_simple)
comp_grp = comp.groupby(["moneda", "emisor_grupo"], as_index=False)["saldo"].sum()

color_emisor = {
    "Tesoro / Sector Público": COLORS["primary"],
    "LeFi (Tesoro)": COLORS["secondary"],
    "BCRA": COLORS["accent_warm"],
    "Privado": COLORS["accent"],
}

col_l, col_r = st.columns([2, 1])
with col_l:
    fig = px.bar(
        comp_grp.sort_values(["moneda", "saldo"]),
        x="saldo", y="moneda", color="emisor_grupo", orientation="h",
        color_discrete_map=color_emisor,
        category_orders={"moneda": ["ARS", "USD país", "USD exterior"]},
    )
    fig.update_layout(
        height=320, barmode="stack", yaxis_title=None, xaxis_title=None,
        xaxis_tickformat="$,.2s",
    )
    fig.update_traces(hovertemplate="<b>%{y}</b> · %{fullData.name}<br>%{x:$,.2s}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    treemap_df = comp.copy()
    treemap_df["saldo_abs"] = treemap_df["saldo"].abs()
    fig = px.treemap(
        treemap_df,
        path=["moneda", "emisor_grupo", "emisor"],
        values="saldo_abs",
        color="emisor_grupo",
        color_discrete_map=color_emisor,
    )
    fig.update_traces(textposition="middle center",
                      hovertemplate="<b>%{label}</b><br>%{value:$,.2s}<extra></extra>")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


# ── Evolución temporal por emisor ────────────────────────────────────────
section_header(
    "Evolución por emisor (sistema)",
    "Series mensuales agregadas. El shift Tesoro ↔ BCRA refleja cambios de régimen monetario.",
)

panel_e = panel.copy()
panel_e["emisor_grupo"] = panel_e["emisor"].apply(_emisor_simple)
panel_e = panel_e.groupby(["yyyymm", "fecha", "emisor_grupo"], as_index=False)["saldo"].sum()
panel_e = to_units(panel_e, value_col="saldo", units=units)

fig = go.Figure()
for grp in ["Tesoro / Sector Público", "LeFi (Tesoro)", "BCRA", "Privado"]:
    sub = panel_e[panel_e["emisor_grupo"] == grp]
    if sub["saldo"].abs().sum() == 0:
        continue
    fig.add_trace(go.Scatter(
        x=sub["fecha"], y=sub["saldo"], name=grp, stackgroup="one",
        line=dict(color=color_emisor.get(grp, COLORS["neutral_mid"]), width=1.5),
        hovertemplate=f"<b>{grp}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
    ))
fig.update_layout(yaxis_tickformat="$,.2s", height=380, hovermode="x unified",
                   yaxis_title=f"Stock ({formato_valor(units)})", xaxis_title=None)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Por medición contable ────────────────────────────────────────────────
section_header(
    "Composición por medición contable (IFRS 9)",
    "FVTPL: mark-to-market en P&L (impacto inmediato ante volatilidad). "
    "AC: costo amortizado, held-to-maturity (sin volatilidad MtM). "
    "FVOCI: mark-to-market en patrimonio (no pega en P&L).",
)

med = panel.groupby(["yyyymm", "fecha", "medicion"], as_index=False)["saldo"].sum()
med = med[med["medicion"].isin(["FVTPL", "AC", "FVOCI"])]
med = to_units(med, value_col="saldo", units=units)

color_med = {"FVTPL": COLORS["negative"], "AC": COLORS["primary"], "FVOCI": COLORS["accent"]}

col_l, col_r = st.columns(2)
with col_l:
    med_ult = med[med["yyyymm"] == ult].copy()
    med_ult["share"] = med_ult["saldo"] / med_ult["saldo"].sum()
    fig = px.pie(
        med_ult, values="saldo", names="medicion", hole=0.5,
        color="medicion", color_discrete_map=color_med,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label",
                      hovertemplate="<b>%{label}</b><br>%{value:$,.2s} (%{percent})<extra></extra>")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0),
                       title=dict(text=f"Cartera al {ult}", font=dict(size=13)))
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    fig = go.Figure()
    for m in ["FVTPL", "AC", "FVOCI"]:
        sub = med[med["medicion"] == m]
        fig.add_trace(go.Scatter(
            x=sub["fecha"], y=sub["saldo"], name=m, stackgroup="one",
            line=dict(color=color_med[m], width=1.5),
            hovertemplate=f"<b>{m}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
        ))
    fig.update_layout(yaxis_tickformat="$,.2s", height=320, hovermode="x unified",
                       yaxis_title=None, xaxis_title=None,
                       title=dict(text="Evolución por medición", font=dict(size=13)))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Top bancos por exposición soberana ───────────────────────────────────
section_header(
    "Exposición soberana por banco",
    "Tesoro + LeFi sobre activo total. Bancos con sov/activo elevado son más sensibles "
    "a un evento de default soberano. Bench informativo: el sistema en conjunto está en " +
    fmt_pct(sov_ult / activo_ult) + ".",
)

sov_b = sov_exposure_pct_activo(ult, proforma=proforma)
ent = load_dim_entidades()[["codigo_entidad", "nombre"]]
sov_b = sov_b.merge(ent, on="codigo_entidad", how="left")
# Filtramos entidades no relevantes (activo > 100 bn ARS homogeneizado)
sov_b = sov_b[sov_b["activo"] > 1e11].copy()
top_sov = sov_b.sort_values("share_sov_activo", ascending=False).head(20)

fig = px.bar(
    top_sov.sort_values("share_sov_activo", ascending=True),
    x="share_sov_activo", y="nombre", orientation="h",
    color="share_sov_activo", color_continuous_scale="Reds",
)
fig.update_layout(
    xaxis_tickformat=".0%", coloraxis_showscale=False,
    height=620, yaxis_title=None, xaxis_title="(Tesoro + LeFi) / Activo total",
    margin=dict(l=0, r=0, t=20, b=20),
)
fig.update_traces(hovertemplate="<b>%{y}</b><br>Sov/Activo: %{x:.1%}<extra></extra>")
fig.add_vline(x=sov_ult / activo_ult, line_width=1, line_dash="dash", line_color=COLORS["neutral_mid"],
              annotation_text="Sistema", annotation_position="top")
st.plotly_chart(fig, use_container_width=True)


# ── Top holders absolutos ────────────────────────────────────────────────
section_header(
    "Concentración: principales tenedores",
    "Quién absorbe la deuda. En montos absolutos.",
)

exp = exposicion_por_banco(ult, proforma=proforma).merge(ent, on="codigo_entidad", how="left")
# Filtra entidades pequeñas
exp_big = exp[exp["total_titulos"] > 1e11].copy()


def _top_chart(df, value_col, title, color, n=15):
    df_top = df.sort_values(value_col, ascending=False).head(n).copy()
    df_top = df_top.assign(yyyymm=ult)
    df_top = to_units(df_top, value_col=value_col, units=units)
    fig = px.bar(
        df_top.sort_values(value_col, ascending=True),
        x=value_col, y="nombre", orientation="h",
        color_discrete_sequence=[color],
    )
    fig.update_layout(
        title=title, xaxis_tickformat="$,.2s",
        height=480, yaxis_title=None, xaxis_title=None,
        margin=dict(l=0, r=0, t=40, b=10),
    )
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:$,.2s}<extra></extra>")
    return fig


col_l, col_r = st.columns(2)
with col_l:
    st.plotly_chart(_top_chart(exp_big, "sov", "Top tenedores Tesoro + LeFi", COLORS["primary"]),
                     use_container_width=True)
with col_r:
    if exp_big["bcra"].sum() > 0:
        st.plotly_chart(_top_chart(exp_big, "bcra", "Top tenedores BCRA paper", COLORS["accent_warm"]),
                         use_container_width=True)
    else:
        st.info("Stock de BCRA paper material concentrado en pocos bancos al último mes — sin gráfico relevante.")


# ── Tabla detallada por banco ────────────────────────────────────────────
section_header(
    "Tabla — exposición por banco (último mes)",
    "Drill-down completo. Use el buscador del header para filtrar.",
)

tabla = exp.merge(ent, on="codigo_entidad", how="left", suffixes=("", "_x"))
tabla = tabla[tabla["total_titulos"] > 1e10].copy()
tabla = tabla.assign(yyyymm=ult)
tabla = to_units(tabla, value_col="total_titulos", units=units)
tabla_show = tabla[["nombre", "total_titulos", "share_sov", "share_bcra", "share_privado", "share_me", "share_fvtpl"]].rename(
    columns={
        "nombre": "Banco",
        "total_titulos": f"Cartera ({formato_valor(units)})",
        "share_sov": "Sov %", "share_bcra": "BCRA %", "share_privado": "Privado %",
        "share_me": "ME %", "share_fvtpl": "FVTPL %",
    }
).sort_values(f"Cartera ({formato_valor(units)})", ascending=False)
st.dataframe(
    tabla_show.style.format({
        f"Cartera ({formato_valor(units)})": "{:,.0f}",
        "Sov %": "{:.1%}", "BCRA %": "{:.1%}", "Privado %": "{:.1%}",
        "ME %": "{:.1%}", "FVTPL %": "{:.1%}",
    }),
    use_container_width=True, hide_index=True, height=440,
)

st.markdown("---")
st.caption(
    "Notas técnicas. (1) Todas las cuentas del capítulo 12 fueron clasificadas — 100% del stock cubierto. "
    "(2) Las cuentas Tesoro/Sector Público no separan emisor nacional de provincial — el plan BCRA agrupa todos en una misma línea. "
    "(3) LeFi (Letras Fiscales de Liquidez) son emitidas por Tesoro pero usadas funcionalmente por bancos como sustituto post-2024 de LELIQs. "
    "(4) La medición sigue convención IFRS 9: FVTPL (resultados), AC (costo amortizado), FVOCI (patrimonio/ORI). "
    "Ver `docs/CONTABILIDAD.md` para reglas de clasificación detalladas."
)

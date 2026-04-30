"""Página: agregados sistémicos del balance bancario."""
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

st.set_page_config(page_title="Sistema", page_icon=None, layout="wide")

from banks_arg_viz.io import (
    load_balance_mensual,
    load_indicadores,
    load_dim_cuentas,
    load_cuenta_categoria,
    load_dim_entidades,
)
from banks_arg_viz.transforms import to_units
from banks_arg_viz.theme import COLORS, fmt_money, fmt_pct
from components import sidebar_global, formato_valor, inject_css, section_header, kpi_grid

inject_css()
flt = sidebar_global()
units = flt["units"]
proforma = flt["proforma"]


# ── Header
st.markdown("# Sistema bancario")
st.markdown(
    f"<p class='section-note'>Agregados consolidados del sistema. Unidades: <b>{formato_valor(units)}</b>.</p>",
    unsafe_allow_html=True,
)


# ── Datos
bal = load_balance_mensual(proforma=proforma)
bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
ult = int(bal["yyyymm"].max())
yoy = ult - 100


def _agg_prefix(*prefixes):
    sub = bal[bal["codigo_cuenta"].str.startswith(tuple(prefixes))]
    return sub.groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()


activo = _agg_prefix("1", "2")
pasivo = _agg_prefix("3")
patrim = _agg_prefix("4")
prest = _agg_prefix("13")
dep = _agg_prefix("31")


def _v(df, ym):
    s = df[df["yyyymm"] == ym]["saldo"]
    return float(s.iloc[0]) if len(s) else float("nan")


def _conv(value, ym):
    if units == "nominal" or pd.isna(value):
        return value
    df = pd.DataFrame({"yyyymm": [ym], "v": [value]})
    return float(to_units(df, value_col="v", units=units)["v"].iloc[0])


def _delta_yoy(curr, prev):
    if pd.isna(curr) or pd.isna(prev) or prev == 0:
        return None
    if units == "real":
        return f"{(curr / prev - 1) * 100:+.1f}% real YoY"
    return f"{(curr / prev - 1) * 100:+.1f}% YoY"


units_kpi = "usd" if units == "usd" else "ars"

# ── KPIs
st.markdown("## Indicadores principales")

ld_total = _v(prest, ult) / _v(dep, ult) if _v(dep, ult) else float("nan")
ld_total_prev = _v(prest, yoy) / _v(dep, yoy) if _v(dep, yoy) else float("nan")
loans_assets = _v(prest, ult) / _v(activo, ult) if _v(activo, ult) else float("nan")
apalanc = _v(activo, ult) / _v(patrim, ult) if _v(patrim, ult) else float("nan")

kpi_grid([
    {"label": "Activo total",
     "value": fmt_money(_conv(_v(activo, ult), ult), units=units_kpi),
     "delta": _delta_yoy(_conv(_v(activo, ult), ult), _conv(_v(activo, yoy), yoy))},
    {"label": "Préstamos",
     "value": fmt_money(_conv(_v(prest, ult), ult), units=units_kpi),
     "delta": _delta_yoy(_conv(_v(prest, ult), ult), _conv(_v(prest, yoy), yoy))},
    {"label": "Depósitos",
     "value": fmt_money(_conv(_v(dep, ult), ult), units=units_kpi),
     "delta": _delta_yoy(_conv(_v(dep, ult), ult), _conv(_v(dep, yoy), yoy))},
    {"label": "Patrimonio neto",
     "value": fmt_money(_conv(_v(patrim, ult), ult), units=units_kpi),
     "delta": _delta_yoy(_conv(_v(patrim, ult), ult), _conv(_v(patrim, yoy), yoy))},
])

kpi_grid([
    {"label": "Loan-to-Deposit", "value": fmt_pct(ld_total),
     "delta": f"{(ld_total - ld_total_prev) * 100:+.1f} pp" if pd.notna(ld_total) and pd.notna(ld_total_prev) else None},
    {"label": "Loans / Assets", "value": fmt_pct(loans_assets)},
    {"label": "Apalancamiento", "value": f"{apalanc:.1f}x" if pd.notna(apalanc) else "—"},
    {"label": "Período", "value": f"{ult // 100}-{ult % 100:02d}"},
])

st.caption(
    f"Variaciones interanuales contra {yoy // 100}-{yoy % 100:02d}. "
    f"En modo {formato_valor(units)} las series se expresan en términos comparables."
)

st.markdown("---")


# ── Stocks principales
section_header(
    "Evolución de stocks",
    "Cuatro líneas en términos comparables. Zoom y crosshair en el gráfico.",
)
df_series = pd.concat([
    activo.assign(serie="Activo"),
    pasivo.assign(serie="Pasivo"),
    prest.assign(serie="Préstamos"),
    dep.assign(serie="Depósitos"),
])
df_series = to_units(df_series, value_col="saldo", units=units)

color_map = {
    "Activo": COLORS["primary"],
    "Pasivo": COLORS["accent_warm"],
    "Préstamos": COLORS["secondary"],
    "Depósitos": COLORS["accent"],
}
fig = go.Figure()
for nombre in ["Activo", "Pasivo", "Préstamos", "Depósitos"]:
    sub = df_series[df_series["serie"] == nombre]
    fig.add_trace(go.Scatter(
        x=sub["fecha"], y=sub["saldo"],
        name=nombre, line=dict(color=color_map[nombre], width=2.2),
        hovertemplate=f"<b>{nombre}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
    ))
fig.update_layout(yaxis_tickformat="$,.2s", height=380, hovermode="x unified", yaxis_title=None, xaxis_title=None)
st.plotly_chart(fig, use_container_width=True)


# ── Cobertura L/D
section_header(
    "Loan-to-Deposit ratio",
    "Indicador de eficiencia en la intermediación. Niveles bajos sugieren capacidad ociosa de prestar; "
    "niveles altos pueden señalar riesgo de liquidez.",
)
ratio_df = (
    prest.rename(columns={"saldo": "prestamos"})
    .merge(dep.rename(columns={"saldo": "depositos"}), on=["yyyymm", "fecha"])
)
ratio_df["ratio"] = ratio_df["prestamos"] / ratio_df["depositos"]
fig = go.Figure(go.Scatter(
    x=ratio_df["fecha"], y=ratio_df["ratio"],
    line=dict(color=COLORS["primary"], width=2.4),
    fill="tozeroy", fillcolor="rgba(27, 54, 93, 0.05)",
    hovertemplate="<b>%{x|%b %Y}</b><br>L/D: %{y:.1%}<extra></extra>",
))
fig.update_layout(yaxis_tickformat=".0%", height=300, showlegend=False, yaxis_title=None, xaxis_title=None)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Composición del balance al último mes
section_header(
    f"Composición del balance — {ult // 100}-{ult % 100:02d}",
    "Apertura por capítulos del plan de cuentas BCRA.",
)

dim_c = load_dim_cuentas()
bal_ult = bal[bal["yyyymm"] == ult].copy()
bal_ult["chapter"] = bal_ult["codigo_cuenta"].str[:2]

chapter_names = (
    dim_c[dim_c["codigo_cuenta"].str.endswith("0000")][["codigo_cuenta", "denominacion"]]
    .assign(chapter=lambda d: d["codigo_cuenta"].str[:2])
    .drop_duplicates(subset="chapter")
    .set_index("chapter")["denominacion"].to_dict()
)


def _chapter_bar(prefixes, title, color):
    df = bal_ult[bal_ult["chapter"].str.startswith(prefixes)].copy()
    df = df.groupby("chapter", as_index=False)["saldo"].sum()
    df["nombre"] = df["chapter"].map(chapter_names).fillna(df["chapter"]).str.strip().str.title()
    df = df[df["saldo"] > 0].sort_values("saldo", ascending=True)
    fig = px.bar(df, x="saldo", y="nombre", orientation="h", color_discrete_sequence=[color])
    fig.update_layout(
        title=title, xaxis_tickformat="$,.2s", height=320,
        yaxis_title=None, xaxis_title=None, margin=dict(l=0, r=0, t=40, b=10),
    )
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:$,.2s}<extra></extra>")
    return fig


col_a, col_p = st.columns(2)
with col_a:
    st.plotly_chart(_chapter_bar(("1", "2"), "Activo", COLORS["primary"]), use_container_width=True)
with col_p:
    st.plotly_chart(_chapter_bar(("3",), "Pasivo", COLORS["accent_warm"]), use_container_width=True)

st.markdown("---")


# ── Concentración
section_header(
    "Concentración del sistema",
    "Top 20 entidades por activo total. Indicador de competencia y riesgo sistémico.",
)

dim_e = load_dim_entidades()[["codigo_entidad", "nombre"]]
top = (
    bal[bal["codigo_cuenta"].str.startswith(("1", "2")) & (bal["yyyymm"] == ult)]
    .groupby("codigo_entidad", as_index=False)["saldo"].sum()
    .sort_values("saldo", ascending=False).head(20)
    .merge(dim_e, on="codigo_entidad", how="left")
)
top_total = top["saldo"].sum()
top["share"] = top["saldo"] / top_total
top_units = to_units(top.assign(yyyymm=ult), value_col="saldo", units=units)

fig = px.bar(
    top_units.sort_values("saldo", ascending=True),
    x="saldo", y="nombre", orientation="h",
    color="share", color_continuous_scale="Blues",
)
fig.update_layout(
    xaxis_tickformat="$,.2s",
    coloraxis_showscale=False,
    height=620, yaxis_title=None, xaxis_title=f"Activo total ({formato_valor(units)})",
    margin=dict(l=0, r=0, t=20, b=30),
)
fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:$,.2s}<br>Share top 20: %{marker.color:.1%}<extra></extra>")
st.plotly_chart(fig, use_container_width=True)

# HHI
hhi = ((top["saldo"] / top_total) ** 2).sum() * 10_000
hhi_label = "concentración alta" if hhi > 2500 else ("concentración moderada" if hhi > 1500 else "concentración baja")
st.caption(f"HHI sobre top 20: **{hhi:,.0f}** — {hhi_label} (criterio DOJ).")

st.markdown("---")


# ── Categorías temáticas
section_header(
    "Vistas temáticas",
    "Indicadores macroprudenciales (CERA, encajes en moneda extranjera, títulos públicos en USD, etc.).",
)
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
            .groupby(["yyyymm", "fecha", "categoria"], as_index=False)["saldo"].sum()
        )
        agg_cat = to_units(agg_cat, value_col="saldo", units=units)
        fig = go.Figure()
        for c in sel_cats:
            sub = agg_cat[agg_cat["categoria"] == c]
            fig.add_trace(go.Scatter(
                x=sub["fecha"], y=sub["saldo"], name=c,
                line=dict(width=2.2),
                hovertemplate=f"<b>{c}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
            ))
        fig.update_layout(yaxis_tickformat="$,.2s", height=380, hovermode="x unified", yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Indicadores supervisorios
section_header(
    "Indicadores supervisorios — sistema",
    "Indicadores publicados por el BCRA: capital, calidad de cartera, eficiencia, rentabilidad, liquidez y sensibilidad de tasa. "
    "Es el marco estándar internacional de supervisión bancaria.",
)
ind = load_indicadores().dropna(subset=["valor_sistema_financiero", "descripcion_indicador"])
ind_sis = ind.groupby(["yyyymm", "descripcion_indicador"], as_index=False)["valor_sistema_financiero"].first()
indicador = st.selectbox("Indicador", options=sorted(ind_sis["descripcion_indicador"].unique()))
serie = ind_sis[ind_sis["descripcion_indicador"] == indicador].sort_values("yyyymm").copy()
serie["fecha"] = pd.to_datetime(serie["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
fig = go.Figure(go.Scatter(
    x=serie["fecha"], y=serie["valor_sistema_financiero"],
    line=dict(color=COLORS["primary"], width=2.2),
    fill="tozeroy", fillcolor="rgba(27, 54, 93, 0.05)",
    hovertemplate="<b>%{x|%b %Y}</b><br>%{y:.2f}<extra></extra>",
))
fig.update_layout(height=320, yaxis_title=None, xaxis_title=None, showlegend=False)
st.plotly_chart(fig, use_container_width=True)

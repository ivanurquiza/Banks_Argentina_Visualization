"""Página: explorador entidad por entidad."""
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

st.set_page_config(page_title="Por Banco", page_icon=None, layout="wide")

from banks_arg_viz.io import (
    load_balance_mensual,
    load_dim_entidades,
    load_dim_cuentas,
    load_indicadores,
    load_estructura,
    load_distribgeo,
    load_cuenta_categoria,
)
from banks_arg_viz.transforms import to_units
from banks_arg_viz.theme import COLORS, fmt_money, fmt_pct
from components import sidebar_global, formato_valor, inject_css, section_header

inject_css()
flt = sidebar_global()
units = flt["units"]
proforma = flt["proforma"]

st.markdown("# Explorador por banco")
st.markdown(
    "<p class='section-note'>Drill-down entidad por entidad: balance, indicadores CAMELS, estructura y distribución geográfica.</p>",
    unsafe_allow_html=True,
)

# ── Selector de entidad
ent = load_dim_entidades()
vigentes = ent[(ent["es_vigente"] == True) & (ent["es_agrupamiento"] != True)].sort_values("nombre")
opciones = {row["codigo_entidad"]: f"{row['nombre']} ({row['codigo_entidad']})" for _, row in vigentes.iterrows()}

DEFAULT = "00007" if "00007" in opciones else list(opciones.keys())[0]
codigo_sel = st.selectbox(
    "Entidad",
    options=list(opciones.keys()),
    format_func=lambda c: opciones[c],
    index=list(opciones.keys()).index(DEFAULT),
)
nombre_sel = vigentes[vigentes["codigo_entidad"] == codigo_sel]["nombre"].iloc[0]
st.markdown(f"### {nombre_sel}")

bal = load_balance_mensual(proforma=proforma)
bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
bal_b = bal[bal["codigo_entidad"] == codigo_sel].copy()

if bal_b.empty:
    st.warning(f"No hay datos de balance para {nombre_sel}.")
    st.stop()

ult = int(bal_b["yyyymm"].max())
prim = int(bal_b["yyyymm"].min())
yoy = ult - 100


def _agg_prefix(df, *prefixes):
    sub = df[df["codigo_cuenta"].str.startswith(tuple(prefixes))]
    return sub.groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()


activo_b = _agg_prefix(bal_b, "1", "2")
pasivo_b = _agg_prefix(bal_b, "3")
patrim_b = _agg_prefix(bal_b, "4")
prest_b = _agg_prefix(bal_b, "13")
dep_b = _agg_prefix(bal_b, "31")


def _v(df, ym):
    s = df[df["yyyymm"] == ym]["saldo"]
    return float(s.iloc[0]) if len(s) else float("nan")


def _conv(value, ym):
    if units == "nominal" or pd.isna(value):
        return value
    df = pd.DataFrame({"yyyymm": [ym], "v": [value]})
    return float(to_units(df, value_col="v", units=units)["v"].iloc[0])


units_kpi = "usd" if units == "usd" else "ars"

# Ranking por activo
rank_df = (
    bal[bal["codigo_cuenta"].str.startswith(("1", "2")) & (bal["yyyymm"] == ult)]
    .groupby("codigo_entidad", as_index=False)["saldo"].sum()
    .sort_values("saldo", ascending=False).reset_index(drop=True)
)
rank_df["rank"] = rank_df.index + 1
rank_b = (
    int(rank_df[rank_df["codigo_entidad"] == codigo_sel]["rank"].iloc[0])
    if codigo_sel in rank_df["codigo_entidad"].values else None
)
total_n = len(rank_df)

# ── KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Activo total", fmt_money(_conv(_v(activo_b, ult), ult), units=units_kpi))
c2.metric("Préstamos", fmt_money(_conv(_v(prest_b, ult), ult), units=units_kpi))
c3.metric("Depósitos", fmt_money(_conv(_v(dep_b, ult), ult), units=units_kpi))
c4.metric("Ranking en activos", f"#{rank_b} de {total_n}" if rank_b else "—")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Patrimonio neto", fmt_money(_conv(_v(patrim_b, ult), ult), units=units_kpi))
loans_assets = _v(prest_b, ult) / _v(activo_b, ult) if _v(activo_b, ult) else float("nan")
c6.metric("Loans / Assets", fmt_pct(loans_assets))
ld = _v(prest_b, ult) / _v(dep_b, ult) if _v(dep_b, ult) else float("nan")
c7.metric("Loan-to-Deposit", fmt_pct(ld))
apalanc = _v(activo_b, ult) / _v(patrim_b, ult) if _v(patrim_b, ult) else float("nan")
c8.metric("Leverage (A/PN)", f"{apalanc:.1f}x" if pd.notna(apalanc) else "—")

st.caption(f"Cobertura temporal: {prim // 100}-{prim % 100:02d} → {ult // 100}-{ult % 100:02d}.")

st.markdown("---")

tab_balance, tab_indicadores, tab_estructura, tab_geo = st.tabs(
    ["Balance", "Indicadores CAMELS", "Estructura", "Distribución geográfica"]
)

# ── Balance
with tab_balance:
    section_header("Stocks principales", f"Series en {formato_valor(units)}.")
    df_series = pd.concat([
        activo_b.assign(serie="Activo"),
        pasivo_b.assign(serie="Pasivo"),
        prest_b.assign(serie="Préstamos"),
        dep_b.assign(serie="Depósitos"),
    ])
    df_series = to_units(df_series, value_col="saldo", units=units)
    color_map = {"Activo": COLORS["primary"], "Pasivo": COLORS["accent_warm"], "Préstamos": COLORS["secondary"], "Depósitos": COLORS["accent"]}
    fig = go.Figure()
    for nombre in ["Activo", "Pasivo", "Préstamos", "Depósitos"]:
        sub = df_series[df_series["serie"] == nombre]
        fig.add_trace(go.Scatter(
            x=sub["fecha"], y=sub["saldo"], name=nombre,
            line=dict(color=color_map[nombre], width=2.2),
            hovertemplate=f"<b>{nombre}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
        ))
    fig.update_layout(yaxis_tickformat="$,.2s", height=380, hovermode="x unified", yaxis_title=None, xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

    section_header(f"Composición del balance — {ult}")
    dim_c = load_dim_cuentas()
    bal_b_ult = bal_b[bal_b["yyyymm"] == ult].merge(dim_c, on="codigo_cuenta", how="left")
    activo_n1 = bal_b_ult[
        bal_b_ult["codigo_cuenta"].str.startswith(("1", "2"))
        & (bal_b_ult["nivel"] == 1)
        & (~bal_b_ult["es_regularizadora"].fillna(False))
        & (bal_b_ult["saldo"] > 0)
    ]
    pasivo_n1 = bal_b_ult[
        bal_b_ult["codigo_cuenta"].str.startswith("3")
        & (bal_b_ult["nivel"] == 1)
        & (~bal_b_ult["es_regularizadora"].fillna(False))
        & (bal_b_ult["saldo"] > 0)
    ]

    col_a, col_p = st.columns(2)
    if not activo_n1.empty:
        with col_a:
            fig = px.pie(
                activo_n1.head(10), values="saldo", names="denominacion",
                title="Activo", hole=0.4,
                color_discrete_sequence=[COLORS["primary"], COLORS["secondary"], COLORS["tertiary"], COLORS["accent"], COLORS["accent_warm"]],
            )
            fig.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
            fig.update_layout(showlegend=False, height=320, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
    if not pasivo_n1.empty:
        with col_p:
            fig = px.pie(
                pasivo_n1.head(10), values="saldo", names="denominacion",
                title="Pasivo", hole=0.4,
                color_discrete_sequence=[COLORS["accent_warm"], COLORS["accent"], COLORS["primary"], COLORS["secondary"]],
            )
            fig.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
            fig.update_layout(showlegend=False, height=320, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    section_header("Vistas temáticas")
    cat = load_cuenta_categoria()[["codigo_cuenta", "categoria"]].dropna()
    cat = cat[~cat["codigo_cuenta"].str.contains("%", na=False)]
    panel_cat = bal_b.merge(cat, on="codigo_cuenta", how="inner")
    if panel_cat.empty:
        st.info("Esta entidad no reporta cuentas en categorías temáticas mapeadas.")
    else:
        cats = sorted(panel_cat["categoria"].unique())
        sel = st.multiselect("Categorías", options=cats, default=cats[:3])
        if sel:
            agg = (
                panel_cat[panel_cat["categoria"].isin(sel)]
                .groupby(["yyyymm", "fecha", "categoria"], as_index=False)["saldo"].sum()
            )
            agg = to_units(agg, value_col="saldo", units=units)
            fig = go.Figure()
            for c in sel:
                sub = agg[agg["categoria"] == c]
                fig.add_trace(go.Scatter(
                    x=sub["fecha"], y=sub["saldo"], name=c, line=dict(width=2.2),
                    hovertemplate=f"<b>{c}</b><br>%{{x|%b %Y}}<br>%{{y:$,.2s}}<extra></extra>",
                ))
            fig.update_layout(yaxis_tickformat="$,.2s", height=350, hovermode="x unified", yaxis_title=None, xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

# ── Indicadores
with tab_indicadores:
    ind = load_indicadores()
    ind_b = ind[ind["codigo_entidad"] == codigo_sel].copy()
    if ind_b.empty:
        st.info("No hay indicadores CAMELS publicados para esta entidad.")
    else:
        ind_b["fecha"] = pd.to_datetime(ind_b["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
        descrs = sorted(ind_b["descripcion_indicador"].dropna().unique())
        sel = st.selectbox("Indicador", options=descrs)
        sub = ind_b[ind_b["descripcion_indicador"] == sel].sort_values("fecha")
        long = sub.melt(
            id_vars=["fecha"],
            value_vars=["valor", "valor_grupo_homogeneo", "valor_top10_privados", "valor_sistema_financiero"],
            var_name="serie", value_name="v",
        )
        label_map = {
            "valor": nombre_sel,
            "valor_grupo_homogeneo": "Grupo homogéneo",
            "valor_top10_privados": "Top-10 privados",
            "valor_sistema_financiero": "Sistema",
        }
        long["serie"] = long["serie"].map(label_map)
        color_map_i = {
            nombre_sel: COLORS["primary"],
            "Grupo homogéneo": COLORS["secondary"],
            "Top-10 privados": COLORS["accent"],
            "Sistema": COLORS["neutral_light"],
        }
        fig = go.Figure()
        for s in long["serie"].dropna().unique():
            sub_s = long[long["serie"] == s]
            fig.add_trace(go.Scatter(
                x=sub_s["fecha"], y=sub_s["v"], name=s,
                line=dict(color=color_map_i.get(s, COLORS["neutral_mid"]), width=2.2),
                hovertemplate=f"<b>{s}</b><br>%{{x|%b %Y}}<br>%{{y:.2f}}<extra></extra>",
            ))
        fig.update_layout(height=380, hovermode="x unified", yaxis_title=None, xaxis_title=None,
                          title=dict(text=sel, font=dict(size=14)))
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Tabla histórica"):
            st.dataframe(
                sub[["yyyymm", "valor", "valor_grupo_homogeneo", "valor_top10_privados", "valor_sistema_financiero"]],
                hide_index=True, use_container_width=True,
            )

# ── Estructura
with tab_estructura:
    est = load_estructura()
    est_b = est[est["codigo_entidad"] == codigo_sel].copy()
    if est_b.empty:
        st.info("No hay datos de estructura para esta entidad.")
    else:
        est_b["fecha"] = pd.to_datetime(est_b["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
        descrs = sorted(est_b["descripcion_informacion"].dropna().unique())
        sel = st.selectbox("Concepto", options=descrs)
        sub = est_b[est_b["descripcion_informacion"] == sel].sort_values("fecha")
        fig = go.Figure(go.Scatter(
            x=sub["fecha"], y=sub["valor"],
            line=dict(color=COLORS["primary"], width=2.2),
            fill="tozeroy", fillcolor="rgba(27, 54, 93, 0.05)",
            hovertemplate=f"<b>%{{x|%b %Y}}</b><br>%{{y:,.0f}}<extra></extra>",
        ))
        fig.update_layout(height=320, yaxis_title=None, xaxis_title=None, showlegend=False,
                          title=dict(text=sel, font=dict(size=14)))
        st.plotly_chart(fig, use_container_width=True)

# ── Geo
with tab_geo:
    geo = load_distribgeo()
    geo_b = geo[geo["codigo_entidad"] == codigo_sel].copy()
    if geo_b.empty:
        st.info("No hay datos de distribución geográfica para esta entidad.")
    else:
        ult_q = int(geo_b["yyyymm_corte"].max())
        sub = geo_b[geo_b["yyyymm_corte"] == ult_q]
        sub_conv = sub.copy().assign(yyyymm=ult_q)
        sub_conv = to_units(sub_conv, value_col="prestamos", units=units)
        sub_conv = to_units(sub_conv, value_col="depositos", units=units)
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                sub_conv.sort_values("prestamos", ascending=True),
                x="prestamos", y="provincia", orientation="h",
                color_discrete_sequence=[COLORS["secondary"]],
            )
            fig.update_layout(
                title=f"Préstamos por provincia ({ult_q})", xaxis_tickformat="$,.2s",
                height=560, yaxis_title=None, xaxis_title=None, margin=dict(l=0, r=0, t=40, b=10),
            )
            fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:$,.2s}<extra></extra>")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.bar(
                sub_conv.sort_values("depositos", ascending=True),
                x="depositos", y="provincia", orientation="h",
                color_discrete_sequence=[COLORS["primary"]],
            )
            fig.update_layout(
                title=f"Depósitos por provincia ({ult_q})", xaxis_tickformat="$,.2s",
                height=560, yaxis_title=None, xaxis_title=None, margin=dict(l=0, r=0, t=40, b=10),
            )
            fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:$,.2s}<extra></extra>")
            st.plotly_chart(fig, use_container_width=True)

"""Página: explorador entidad por entidad."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Por Banco", page_icon="🏦", layout="wide")

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
from components import sidebar_global, formato_valor

flt = sidebar_global()
units = flt["units"]
proforma = flt["proforma"]

st.title("🏦 Explorador por banco")

# ── Selector de entidad
ent = load_dim_entidades()
vigentes = ent[(ent["es_vigente"] == True) & (ent["es_agrupamiento"] != True)].sort_values("nombre")
opciones = {row["codigo_entidad"]: f"{row['nombre']}  ({row['codigo_entidad']})" for _, row in vigentes.iterrows()}

DEFAULT_CODIGO = "00007" if "00007" in opciones else list(opciones.keys())[0]
codigo_sel = st.selectbox(
    "Banco",
    options=list(opciones.keys()),
    format_func=lambda c: opciones[c],
    index=list(opciones.keys()).index(DEFAULT_CODIGO),
)
nombre_sel = vigentes[vigentes["codigo_entidad"] == codigo_sel]["nombre"].iloc[0]
st.subheader(nombre_sel)

bal = load_balance_mensual(proforma=proforma)
bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
bal_b = bal[bal["codigo_entidad"] == codigo_sel].copy()

if bal_b.empty:
    st.warning(f"No hay datos de balance para {nombre_sel}.")
    st.stop()

ult = int(bal_b["yyyymm"].max())
prim = int(bal_b["yyyymm"].min())


def _agg_prefix(df, *prefixes):
    sub = df[df["codigo_cuenta"].str.startswith(tuple(prefixes))]
    return sub.groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()


activo_b = _agg_prefix(bal_b, "1", "2")
pasivo_b = _agg_prefix(bal_b, "3")
patrim_b = _agg_prefix(bal_b, "4")
prestamos_b = _agg_prefix(bal_b, "13")
depositos_b = _agg_prefix(bal_b, "31")


def _at(df, yyyymm):
    return float(df[df["yyyymm"] == yyyymm]["saldo"].sum())


def _conv(value, yyyymm):
    if units == "nominal":
        return value
    df = pd.DataFrame({"yyyymm": [yyyymm], "v": [value]})
    return float(to_units(df, value_col="v", units=units)["v"].iloc[0])


fmt = lambda v: f"${v / 1e12:,.2f} T" if abs(v) >= 1e12 else f"${v / 1e9:,.1f} bn"

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

c1, c2, c3, c4 = st.columns(4)
c1.metric("Activo total", fmt(_conv(_at(activo_b, ult), ult)), help=formato_valor(units))
c2.metric("Préstamos", fmt(_conv(_at(prestamos_b, ult), ult)))
c3.metric("Depósitos", fmt(_conv(_at(depositos_b, ult), ult)))
c4.metric("Ranking en activos", f"#{rank_b} de {total_n}" if rank_b else "—")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Patrimonio neto", fmt(_conv(_at(patrim_b, ult), ult)))
loans_assets = _at(prestamos_b, ult) / _at(activo_b, ult) if _at(activo_b, ult) else float("nan")
c6.metric("Loans / Assets", f"{loans_assets:.1%}" if pd.notna(loans_assets) else "—")
apalanc = _at(activo_b, ult) / _at(patrim_b, ult) if _at(patrim_b, ult) else float("nan")
c7.metric("Apalancamiento (A/PN)", f"{apalanc:.1f}x" if pd.notna(apalanc) else "—")
c8.metric("Cobertura", f"{prim // 100}-{prim % 100:02d} → {ult // 100}-{ult % 100:02d}")

st.divider()

# ── Tabs
tab_balance, tab_indicadores, tab_estructura, tab_geo = st.tabs(
    ["📊 Balance", "📈 Indicadores CAMELS", "🏛 Estructura", "📍 Distribución geo"]
)

# ── Balance
with tab_balance:
    st.markdown("**Series principales del banco**")
    df_series = pd.concat([
        activo_b.assign(serie="Activo"),
        pasivo_b.assign(serie="Pasivo"),
        prestamos_b.assign(serie="Préstamos"),
        depositos_b.assign(serie="Depósitos"),
    ])
    df_series = to_units(df_series, value_col="saldo", units=units)
    fig = px.line(
        df_series, x="fecha", y="saldo", color="serie",
        title=f"Stocks principales ({formato_valor(units)})",
    )
    fig.update_layout(legend_title=None, xaxis_title=None, yaxis_title=None, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"**Composición del balance — {ult}**")
    dim_c = load_dim_cuentas()
    bal_b_ult = bal_b[bal_b["yyyymm"] == ult].merge(dim_c, on="codigo_cuenta", how="left")
    bal_b_ult["chapter"] = bal_b_ult["codigo_cuenta"].str[:2]

    chapter_names = (
        dim_c[dim_c["codigo_cuenta"].str.endswith("0000")][["codigo_cuenta", "denominacion"]]
        .assign(chapter=lambda d: d["codigo_cuenta"].str[:2])
        .drop_duplicates(subset="chapter")
        .set_index("chapter")["denominacion"]
        .to_dict()
    )

    col_a, col_p = st.columns(2)
    chap_act = (
        bal_b_ult[bal_b_ult["chapter"].str.startswith(("1", "2"))]
        .groupby("chapter", as_index=False)["saldo"].sum()
    )
    chap_act["denominacion"] = chap_act["chapter"].map(chapter_names).fillna(chap_act["chapter"])
    chap_act = chap_act[chap_act["saldo"] > 0]
    with col_a:
        if not chap_act.empty:
            fig = px.pie(chap_act, values="saldo", names="denominacion", title="Activo")
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

    chap_pas = (
        bal_b_ult[bal_b_ult["chapter"].str.startswith("3")]
        .groupby("chapter", as_index=False)["saldo"].sum()
    )
    chap_pas["denominacion"] = chap_pas["chapter"].map(chapter_names).fillna(chap_pas["chapter"])
    chap_pas = chap_pas[chap_pas["saldo"] > 0]
    with col_p:
        if not chap_pas.empty:
            fig = px.pie(chap_pas, values="saldo", names="denominacion", title="Pasivo")
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Vistas temáticas**")
    cat = load_cuenta_categoria()[["codigo_cuenta", "categoria"]].dropna()
    cat = cat[~cat["codigo_cuenta"].str.contains("%", na=False)]
    panel_cat = bal_b.merge(cat, on="codigo_cuenta", how="inner")
    if panel_cat.empty:
        st.info("Esta entidad no reporta cuentas en las categorías temáticas mapeadas.")
    else:
        cats = sorted(panel_cat["categoria"].unique())
        sel = st.multiselect("Categorías", options=cats, default=cats[:3])
        if sel:
            agg = (
                panel_cat[panel_cat["categoria"].isin(sel)]
                .groupby(["yyyymm", "fecha", "categoria"], as_index=False)["saldo"]
                .sum()
            )
            agg = to_units(agg, value_col="saldo", units=units)
            fig = px.line(agg, x="fecha", y="saldo", color="categoria")
            fig.update_layout(legend_title=None, xaxis_title=None, yaxis_title=None)
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
        long["serie"] = long["serie"].map({
            "valor": nombre_sel,
            "valor_grupo_homogeneo": "Grupo homogéneo",
            "valor_top10_privados": "Top-10 privados",
            "valor_sistema_financiero": "Sistema",
        })
        fig = px.line(long.dropna(), x="fecha", y="v", color="serie", title=sel)
        fig.update_layout(xaxis_title=None, yaxis_title=None, legend_title=None)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📋 Tabla completa"):
            st.dataframe(
                sub[["yyyymm", "valor", "valor_grupo_homogeneo", "valor_top10_privados", "valor_sistema_financiero"]],
                hide_index=True,
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
        fig = px.line(sub, x="fecha", y="valor", title=sel)
        fig.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

# ── Distribución geo
with tab_geo:
    geo = load_distribgeo()
    geo_b = geo[geo["codigo_entidad"] == codigo_sel].copy()
    if geo_b.empty:
        st.info("No hay datos de distribución geográfica para esta entidad.")
    else:
        ult_q = int(geo_b["yyyymm_corte"].max())
        sub = geo_b[geo_b["yyyymm_corte"] == ult_q]
        col1, col2 = st.columns(2)
        sub_conv = sub.copy().assign(yyyymm=ult_q)
        sub_conv = to_units(sub_conv, value_col="prestamos", units=units)
        sub_conv = to_units(sub_conv, value_col="depositos", units=units)
        with col1:
            fig = px.bar(
                sub_conv.sort_values("prestamos", ascending=True),
                x="prestamos", y="provincia", orientation="h",
                title=f"Préstamos por provincia ({ult_q})",
            )
            fig.update_layout(xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.bar(
                sub_conv.sort_values("depositos", ascending=True),
                x="depositos", y="provincia", orientation="h",
                title=f"Depósitos por provincia ({ult_q})",
            )
            fig.update_layout(xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

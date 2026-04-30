"""Página: distribución geográfica (crédito, depósitos, sucursales)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Mapa", page_icon="🗺️", layout="wide")

from banks_arg_viz.io import (
    load_distribgeo,
    load_sucursales_provincia,
    load_dim_entidades,
)
from banks_arg_viz.geo import geojson_argentina, normalize_provincia, add_iso
from banks_arg_viz.transforms import to_units
from components import sidebar_global, formato_valor

flt = sidebar_global()
units = flt["units"]

st.title("🗺️ Distribución geográfica")
st.caption("Crédito, depósitos y red de sucursales por provincia. Datos BCRA.")

geo_full = load_distribgeo()
geo_full["provincia_norm"] = geo_full["provincia"].map(normalize_provincia)
# El BCRA reporta Buenos Aires dividida en GBA + resto. Acá las consolidamos
# en BUENOS AIRES (la jurisdicción) para que matchee con el geojson.
geo_full = geo_full[geo_full["provincia_norm"].notna() & (geo_full["provincia_norm"] != "EXTERIOR")].copy()

ent = load_dim_entidades()
vigentes = ent[(ent["es_vigente"] == True) & (ent["es_agrupamiento"] != True)].sort_values("nombre")
opciones = {"__sistema__": "Sistema completo (suma de todas las entidades)"}
opciones.update({row["codigo_entidad"]: f"{row['nombre']}  ({row['codigo_entidad']})" for _, row in vigentes.iterrows()})

c1, c2 = st.columns([2, 1])
with c1:
    codigo_sel = st.selectbox(
        "Entidad",
        options=list(opciones.keys()),
        format_func=lambda c: opciones[c],
    )
with c2:
    cortes = sorted(geo_full["yyyymm_corte"].unique())
    corte = st.selectbox("Trimestre", options=cortes, index=len(cortes) - 1)

if codigo_sel == "__sistema__":
    sub = geo_full[geo_full["yyyymm_corte"] == corte]
else:
    sub = geo_full[
        (geo_full["yyyymm_corte"] == corte) & (geo_full["codigo_entidad"] == codigo_sel)
    ]
# Consolidamos por provincia normalizada (sumando GBA + resto BA si aplica)
sub_agg = (
    sub.groupby("provincia_norm", as_index=False)[["prestamos", "depositos"]].sum()
    .rename(columns={"provincia_norm": "provincia"})
)
sub_agg["provincia_norm"] = sub_agg["provincia"]

# Convertir a unidades
sub_agg = sub_agg.assign(yyyymm=corte)
sub_agg = to_units(sub_agg, value_col="prestamos", units=units)
sub_agg = to_units(sub_agg, value_col="depositos", units=units)

sub_agg = add_iso(sub_agg, prov_col="provincia_norm")

gj = geojson_argentina()

st.divider()
st.markdown(f"**{opciones[codigo_sel]} — Corte {corte}**")

if gj is None:
    st.warning(
        "El archivo de geometrías de provincias no está disponible. "
        "Mostrando barras horizontales como alternativa."
    )

tab_credito, tab_depositos, tab_sucursales, tab_tabla = st.tabs(
    ["💳 Crédito", "🏦 Depósitos", "📍 Sucursales", "📋 Tabla"]
)

def _make_choropleth(df, value_col, title):
    if gj is None:
        fig = px.bar(
            df.sort_values(value_col, ascending=True),
            x=value_col, y="provincia",
            orientation="h",
            title=title,
        )
        fig.update_layout(xaxis_title=None, yaxis_title=None, height=600)
        return fig
    fig = px.choropleth(
        df,
        geojson=gj,
        locations="provincia_norm",
        featureidkey="properties.provincia_canonica",
        color=value_col,
        color_continuous_scale="Blues",
        title=title,
        labels={value_col: formato_valor(units)},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=40, b=0))
    return fig


with tab_credito:
    fig = _make_choropleth(sub_agg, "prestamos", f"Préstamos ({formato_valor(units)})")
    st.plotly_chart(fig, use_container_width=True)

with tab_depositos:
    fig = _make_choropleth(sub_agg, "depositos", f"Depósitos ({formato_valor(units)})")
    st.plotly_chart(fig, use_container_width=True)

with tab_sucursales:
    suc = load_sucursales_provincia()
    if codigo_sel == "__sistema__":
        suc_sub = suc[suc["dump_yyyymm"] == suc["dump_yyyymm"].max()].copy()
        suc_agg = (
            suc_sub.groupby("nombre_provincia", as_index=False)
            [["sucursales_plenas", "sucursales_op_especifica", "sucursales_moviles", "cajeros_automaticos"]]
            .sum()
        )
    else:
        suc_sub = suc[
            (suc["codigo_entidad"] == codigo_sel) & (suc["dump_yyyymm"] == suc["dump_yyyymm"].max())
        ]
        suc_agg = suc_sub[["nombre_provincia", "sucursales_plenas", "sucursales_op_especifica", "sucursales_moviles", "cajeros_automaticos"]].copy()
    if suc_agg.empty:
        st.info("Sin datos de sucursales para esta selección.")
    else:
        suc_agg["provincia_norm"] = suc_agg["nombre_provincia"].map(normalize_provincia)
        suc_agg["total_sucursales"] = (
            suc_agg["sucursales_plenas"].fillna(0)
            + suc_agg["sucursales_op_especifica"].fillna(0)
            + suc_agg["sucursales_moviles"].fillna(0)
        )
        suc_agg = add_iso(suc_agg, prov_col="provincia_norm")

        metric = st.radio(
            "Métrica",
            ["total_sucursales", "sucursales_plenas", "cajeros_automaticos"],
            format_func=lambda x: {
                "total_sucursales": "Total sucursales (plenas + op. específica + móviles)",
                "sucursales_plenas": "Sucursales plenas",
                "cajeros_automaticos": "Cajeros automáticos",
            }[x],
            horizontal=True,
        )
        suc_agg = suc_agg.rename(columns={"nombre_provincia": "provincia"})
        if gj is None:
            fig = px.bar(
                suc_agg.sort_values(metric, ascending=True),
                x=metric, y="provincia", orientation="h",
                title=metric,
            )
        else:
            fig = px.choropleth(
                suc_agg,
                geojson=gj,
                locations="provincia_norm",
                featureidkey="properties.provincia_canonica",
                color=metric,
                color_continuous_scale="Greens",
                title=f"{metric} por provincia",
            )
            fig.update_geos(fitbounds="locations", visible=False)
            fig.update_layout(height=600, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)

with tab_tabla:
    st.dataframe(
        sub_agg[["provincia", "prestamos", "depositos"]]
        .sort_values("prestamos", ascending=False)
        .reset_index(drop=True),
        hide_index=True,
        use_container_width=True,
    )

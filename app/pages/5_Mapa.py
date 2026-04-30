"""Página: distribución geográfica del balance."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Mapa", page_icon=None, layout="wide")

from banks_arg_viz.io import (
    load_distribgeo,
    load_sucursales_provincia,
    load_dim_entidades,
)
from banks_arg_viz.geo import geojson_argentina, normalize_provincia, add_iso
from banks_arg_viz.transforms import to_units
from banks_arg_viz.theme import COLORS, fmt_money, fmt_pct
from components import sidebar_global, formato_valor, inject_css, section_header

inject_css()
flt = sidebar_global()
units = flt["units"]

st.markdown("# Distribución geográfica")
st.markdown(
    "<p class='section-note'>Crédito, depósitos y red de sucursales por provincia. "
    "Vista en montos absolutos o en participación nacional.</p>",
    unsafe_allow_html=True,
)

geo_full = load_distribgeo()
geo_full["provincia_norm"] = geo_full["provincia"].map(normalize_provincia)
geo_full = geo_full[geo_full["provincia_norm"].notna() & (geo_full["provincia_norm"] != "EXTERIOR")].copy()

ent = load_dim_entidades()
vigentes = ent[(ent["es_vigente"] == True) & (ent["es_agrupamiento"] != True)].sort_values("nombre")
opciones = {"__sistema__": "Sistema completo (suma de todas las entidades)"}
opciones.update({row["codigo_entidad"]: f"{row['nombre']} ({row['codigo_entidad']})" for _, row in vigentes.iterrows()})

c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    codigo_sel = st.selectbox(
        "Entidad", options=list(opciones.keys()),
        format_func=lambda c: opciones[c],
    )
with c2:
    cortes = sorted(geo_full["yyyymm_corte"].unique())
    corte = st.selectbox("Trimestre", options=cortes, index=len(cortes) - 1)
with c3:
    modo = st.selectbox(
        "Vista",
        options=["monto", "share"],
        format_func=lambda x: {"monto": "Monto", "share": "% del total nacional"}[x],
    )

if codigo_sel == "__sistema__":
    sub = geo_full[geo_full["yyyymm_corte"] == corte]
else:
    sub = geo_full[(geo_full["yyyymm_corte"] == corte) & (geo_full["codigo_entidad"] == codigo_sel)]

sub_agg = (
    sub.groupby("provincia_norm", as_index=False)[["prestamos", "depositos"]].sum()
    .rename(columns={"provincia_norm": "provincia"})
)
sub_agg["provincia_norm"] = sub_agg["provincia"]
sub_agg = sub_agg.assign(yyyymm=corte)

# Conversión a unidades
sub_agg = to_units(sub_agg, value_col="prestamos", units=units)
sub_agg = to_units(sub_agg, value_col="depositos", units=units)

# Calcular shares dentro del mes (totales nacionales)
total_pres_nac = sub_agg["prestamos"].sum()
total_dep_nac = sub_agg["depositos"].sum()
sub_agg["prestamos_share"] = sub_agg["prestamos"] / total_pres_nac if total_pres_nac else 0
sub_agg["depositos_share"] = sub_agg["depositos"] / total_dep_nac if total_dep_nac else 0
sub_agg["ld_provincia"] = sub_agg["prestamos"] / sub_agg["depositos"].where(sub_agg["depositos"] > 0)

sub_agg = add_iso(sub_agg, prov_col="provincia_norm")

gj = geojson_argentina()

st.markdown("---")
st.markdown(f"**{opciones[codigo_sel]}** · Corte {corte}")

if gj is None:
    st.warning("Geojson de provincias no disponible — mostrando barras como alternativa.")

tab_credito, tab_depositos, tab_ld, tab_sucursales, tab_tabla = st.tabs(
    ["Crédito", "Depósitos", "L/D por provincia", "Sucursales", "Datos"]
)


def _choropleth(df, value_col, title, color_scale, fmt_hover):
    if gj is None:
        fig = px.bar(
            df.sort_values(value_col, ascending=True),
            x=value_col, y="provincia", orientation="h",
            color_discrete_sequence=[COLORS["primary"]],
        )
        fig.update_layout(title=title, height=620, yaxis_title=None, xaxis_title=None)
        return fig
    fig = px.choropleth(
        df, geojson=gj,
        locations="provincia_norm",
        featureidkey="properties.provincia_canonica",
        color=value_col,
        color_continuous_scale=color_scale,
    )
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_traces(hovertemplate=fmt_hover, marker_line=dict(color="#FFFFFF", width=0.8))
    fig.update_layout(
        title=title, height=620, margin=dict(l=0, r=0, t=40, b=0),
        coloraxis_colorbar=dict(thickness=12, len=0.6, tickfont=dict(size=10)),
    )
    return fig


def _share_format(modo):
    return ".1%" if modo == "share" else "$,.2s"


with tab_credito:
    if modo == "monto":
        col, fmt = "prestamos", "<b>%{customdata[0]}</b><br>%{z:$,.2s}<extra></extra>"
        title = f"Préstamos por provincia ({formato_valor(units)})"
        scale = "Blues"
    else:
        col, fmt = "prestamos_share", "<b>%{customdata[0]}</b><br>Share nac.: %{z:.1%}<extra></extra>"
        title = "Share nacional de préstamos"
        scale = "Blues"
    df = sub_agg.assign(provincia_label=sub_agg["provincia"])
    if gj is not None:
        fig = px.choropleth(
            df, geojson=gj, locations="provincia_norm",
            featureidkey="properties.provincia_canonica",
            color=col,
            color_continuous_scale=scale,
            custom_data=["provincia_label"],
        )
        fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
        fig.update_traces(hovertemplate=fmt, marker_line=dict(color="#FFFFFF", width=0.8))
        fig.update_layout(
            title=title, height=620, margin=dict(l=0, r=0, t=40, b=0),
            coloraxis_colorbar=dict(thickness=12, len=0.6, tickfont=dict(size=10),
                                     tickformat=_share_format(modo)),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig = px.bar(df.sort_values(col, ascending=True), x=col, y="provincia", orientation="h",
                     color_discrete_sequence=[COLORS["secondary"]])
        fig.update_layout(title=title, height=620, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)


with tab_depositos:
    if modo == "monto":
        col, fmt = "depositos", "<b>%{customdata[0]}</b><br>%{z:$,.2s}<extra></extra>"
        title = f"Depósitos por provincia ({formato_valor(units)})"
    else:
        col, fmt = "depositos_share", "<b>%{customdata[0]}</b><br>Share nac.: %{z:.1%}<extra></extra>"
        title = "Share nacional de depósitos"
    df = sub_agg.assign(provincia_label=sub_agg["provincia"])
    if gj is not None:
        fig = px.choropleth(
            df, geojson=gj, locations="provincia_norm",
            featureidkey="properties.provincia_canonica",
            color=col,
            color_continuous_scale="Greens",
            custom_data=["provincia_label"],
        )
        fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
        fig.update_traces(hovertemplate=fmt, marker_line=dict(color="#FFFFFF", width=0.8))
        fig.update_layout(
            title=title, height=620, margin=dict(l=0, r=0, t=40, b=0),
            coloraxis_colorbar=dict(thickness=12, len=0.6, tickfont=dict(size=10),
                                     tickformat=_share_format(modo)),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig = px.bar(df.sort_values(col, ascending=True), x=col, y="provincia", orientation="h",
                     color_discrete_sequence=[COLORS["primary"]])
        fig.update_layout(title=title, height=620, yaxis_title=None, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)


with tab_ld:
    section_header(
        "Loan-to-Deposit ratio por provincia",
        "Indica si la provincia es generadora neta de fondeo (L/D bajo) o consumidora neta de crédito (L/D alto).",
    )
    df = sub_agg.assign(provincia_label=sub_agg["provincia"])
    df = df[df["depositos"] > 0]
    if gj is not None:
        fig = px.choropleth(
            df, geojson=gj, locations="provincia_norm",
            featureidkey="properties.provincia_canonica",
            color="ld_provincia",
            color_continuous_scale="RdBu_r",
            color_continuous_midpoint=1.0,
            custom_data=["provincia_label"],
        )
        fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
        fig.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>L/D: %{z:.2f}<extra></extra>",
                          marker_line=dict(color="#FFFFFF", width=0.8))
        fig.update_layout(
            title="L/D por provincia", height=620, margin=dict(l=0, r=0, t=40, b=0),
            coloraxis_colorbar=dict(thickness=12, len=0.6, tickfont=dict(size=10), tickformat=".2f"),
        )
        st.plotly_chart(fig, use_container_width=True)


with tab_sucursales:
    suc = load_sucursales_provincia()
    if codigo_sel == "__sistema__":
        suc_sub = suc[suc["dump_yyyymm"] == suc["dump_yyyymm"].max()]
        suc_agg = (
            suc_sub.groupby("nombre_provincia", as_index=False)
            [["sucursales_plenas", "sucursales_op_especifica", "sucursales_moviles", "cajeros_automaticos"]]
            .sum()
        )
    else:
        suc_sub = suc[(suc["codigo_entidad"] == codigo_sel) & (suc["dump_yyyymm"] == suc["dump_yyyymm"].max())]
        suc_agg = suc_sub[["nombre_provincia", "sucursales_plenas", "sucursales_op_especifica",
                           "sucursales_moviles", "cajeros_automaticos"]].copy()

    if suc_agg.empty:
        st.info("Sin datos de sucursales para esta selección.")
    else:
        suc_agg["provincia_norm"] = suc_agg["nombre_provincia"].map(normalize_provincia)
        suc_agg["total_sucursales"] = (
            suc_agg["sucursales_plenas"].fillna(0)
            + suc_agg["sucursales_op_especifica"].fillna(0)
            + suc_agg["sucursales_moviles"].fillna(0)
        )
        # Consolidar por provincia normalizada (suma GBA + resto BA si aplica)
        suc_agg = suc_agg.groupby("provincia_norm", as_index=False).agg({
            "total_sucursales": "sum", "sucursales_plenas": "sum",
            "cajeros_automaticos": "sum",
        })
        suc_agg["nombre_provincia"] = suc_agg["provincia_norm"]
        suc_agg = add_iso(suc_agg, prov_col="provincia_norm")

        metric = st.radio(
            "Métrica",
            ["total_sucursales", "sucursales_plenas", "cajeros_automaticos"],
            format_func=lambda x: {
                "total_sucursales": "Total sucursales",
                "sucursales_plenas": "Sucursales plenas",
                "cajeros_automaticos": "Cajeros automáticos",
            }[x],
            horizontal=True,
        )

        if gj is not None:
            fig = px.choropleth(
                suc_agg, geojson=gj, locations="provincia_norm",
                featureidkey="properties.provincia_canonica",
                color=metric, color_continuous_scale="Blues",
                custom_data=["nombre_provincia"],
            )
            fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
            fig.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>%{z:,.0f}<extra></extra>",
                              marker_line=dict(color="#FFFFFF", width=0.8))
            fig.update_layout(height=620, margin=dict(l=0, r=0, t=40, b=0),
                              coloraxis_colorbar=dict(thickness=12, len=0.6, tickfont=dict(size=10)))
            st.plotly_chart(fig, use_container_width=True)


with tab_tabla:
    tabla = sub_agg[["provincia", "prestamos", "depositos", "prestamos_share", "depositos_share", "ld_provincia"]].copy()
    tabla = tabla.rename(columns={
        "prestamos": "Préstamos", "depositos": "Depósitos",
        "prestamos_share": "% Préstamos nac.", "depositos_share": "% Depósitos nac.",
        "ld_provincia": "L/D",
    }).sort_values("Préstamos", ascending=False)
    st.dataframe(
        tabla.style.format({
            "Préstamos": "{:,.0f}", "Depósitos": "{:,.0f}",
            "% Préstamos nac.": "{:.1%}", "% Depósitos nac.": "{:.1%}", "L/D": "{:.2f}",
        }),
        use_container_width=True, hide_index=True,
    )

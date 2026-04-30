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

from banks_arg_viz.io import load_actividad_total
from banks_arg_viz.kpis.mora import (
    irregularidad_sistema,
    irregularidad_por_tipo_cartera,
    irregularidad_estricta_por_tipo_cartera,
    composicion_situaciones_sistema,
    previsiones_sobre_cartera,
    irregularidad_por_banco,
    serie_irregularidad_por_banco,
)
from banks_arg_viz.io import load_dim_entidades
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
    "Stack de las situaciones de la cartera (% del total). Por defecto se muestra solo el deterioro "
    "(Sit. 2 a 6) — la Sit. 1 (normal) puede agregarse desde el selector si querés ver el 100%.",
)

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

# Multiselect de situaciones — Sit.1 NO seleccionada por default
labels_sin_sit1 = [lbl for lbl, _ in SITS_LBL if not lbl.startswith("Sit. 1")]
sel_sits = st.multiselect(
    "Situaciones a mostrar",
    options=[lbl for lbl, _ in SITS_LBL],
    default=labels_sin_sit1,
    help="Sit. 1 (normal) está fuera por default para que se vea bien el deterioro. Agregala si querés el 100%.",
)

fig = go.Figure()
for label, col in SITS_LBL:
    if label not in sel_sits or col not in sis_pct.columns:
        continue
    sub = sis_pct[["fecha", col]].dropna()
    fig.add_trace(go.Scatter(
        x=sub["fecha"], y=sub[col] / 100, name=label,
        stackgroup="one",
        line=dict(color=color_sit[label], width=1),
        hovertemplate=f"<b>{label}</b><br>%{{x|%b %Y}}<br>%{{y:.2%}}<extra></extra>",
    ))
y_top = 1 if "Sit. 1 — Normal" in sel_sits else 0.20
fig.update_layout(
    yaxis_tickformat=".0%", height=380, hovermode="x unified",
    yaxis_title="% de la cartera total", xaxis_title=None,
    yaxis=dict(range=[0, y_top]),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Por tipo de cartera (sector)
section_header(
    "Mora por sector — tipo de cartera",
    "El BCRA agrupa la cartera en tres tipos: Comercial (empresas), Consumo o Vivienda (familias) "
    "y Comercial Asimilable a Consumo (créditos pequeños tratados como consumo). "
    "Permite filtrar y elegir entre serie temporal o foto del último trimestre.",
)

color_cart = {
    "Comercial": COLORS["primary"],
    "Consumo / Vivienda": COLORS["accent_warm"],
    "Comercial asimilable a consumo": COLORS["secondary"],
}

# Datos completos: amplia + estricta
tipo_full = irregularidad_estricta_por_tipo_cartera()
tipo_full = tipo_full[tipo_full["yyyymm"] >= 201801]

col_def, col_carteras = st.columns([1, 2])
with col_def:
    definicion_cart = st.radio(
        "Definición",
        options=["amplia", "estricta"],
        format_func=lambda x: {"amplia": "Amplia (Sit. 2+)", "estricta": "Estricta (Sit. 3+)"}[x],
        horizontal=False,
        key="def_cart",
    )
with col_carteras:
    carteras_sel = st.multiselect(
        "Carteras a mostrar",
        options=["Comercial", "Consumo / Vivienda", "Comercial asimilable a consumo"],
        default=["Comercial", "Consumo / Vivienda", "Comercial asimilable a consumo"],
        key="carteras_sel",
    )

tab_serie_c, tab_foto_c = st.tabs(["Serie temporal", "Foto último trimestre"])

with tab_serie_c:
    if not carteras_sel:
        st.info("Seleccioná al menos una cartera.")
    else:
        fig = go.Figure()
        for cart in carteras_sel:
            sub = tipo_full[tipo_full["cartera"] == cart]
            fig.add_trace(go.Scatter(
                x=sub["fecha"], y=sub[definicion_cart] / 100, name=cart,
                line=dict(color=color_cart.get(cart, COLORS["neutral_mid"]), width=2.2),
                hovertemplate=f"<b>{cart}</b><br>%{{x|%b %Y}}<br>%{{y:.1%}}<extra></extra>",
            ))
        fig.update_layout(
            yaxis_tickformat=".1%", height=380, hovermode="x unified",
            yaxis_title=f"Irregularidad {definicion_cart} (% cartera)", xaxis_title=None,
        )
        st.plotly_chart(fig, use_container_width=True)

with tab_foto_c:
    ult_q = tipo_full["yyyymm"].max()
    snap = tipo_full[(tipo_full["yyyymm"] == ult_q) & (tipo_full["cartera"].isin(carteras_sel))].copy()
    if snap.empty:
        st.info("Sin datos para la selección.")
    else:
        snap["valor"] = snap[definicion_cart] / 100
        fig = px.bar(
            snap.sort_values("valor", ascending=True),
            x="valor", y="cartera", orientation="h",
            color="cartera", color_discrete_map=color_cart,
        )
        fig.update_layout(
            xaxis_tickformat=".1%", height=320,
            yaxis_title=None, xaxis_title=f"Irregularidad {definicion_cart} ({ult_q})",
            showlegend=False, margin=dict(l=0, r=0, t=20, b=20),
        )
        fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:.1%}<extra></extra>")
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


# ── Mora por banco
section_header(
    "Mora por banco",
    "Selecciona los bancos para ver su evolución (serie temporal) o el snapshot del último trimestre. "
    "Las dos definiciones (amplia y estricta) se eligen arriba.",
)

# Datos snapshot último trimestre
ib = irregularidad_por_banco(ult)
ib = ib[ib["total"] > 1e8].copy()
ib_sorted = ib.sort_values("amplia", ascending=False)

# Defaults: top 6 bancos con mayor cartera, no por mora
TOP_BANCOS_DEFAULT = (
    ib.sort_values("total", ascending=False).head(6)["codigo_entidad"].tolist()
)

ent = load_dim_entidades()
codigo_to_nombre = dict(zip(ent["codigo_entidad"].astype(str), ent["nombre"]))

col_def_b, col_bancos = st.columns([1, 3])
with col_def_b:
    definicion_b = st.radio(
        "Definición",
        options=["amplia", "estricta"],
        format_func=lambda x: {"amplia": "Amplia (Sit. 2+)", "estricta": "Estricta (Sit. 3+)"}[x],
        key="def_banco",
    )
with col_bancos:
    bancos_options = ib_sorted["codigo_entidad"].astype(str).tolist()
    bancos_format = {c: codigo_to_nombre.get(c, c) for c in bancos_options}
    bancos_sel = st.multiselect(
        "Bancos",
        options=bancos_options,
        default=[c for c in TOP_BANCOS_DEFAULT if c in bancos_options],
        format_func=lambda c: bancos_format.get(c, c),
        key="bancos_sel",
        max_selections=12,
    )

tab_serie_b, tab_foto_b, tab_tabla_b = st.tabs(["Serie temporal", "Foto último trimestre", "Tabla"])

with tab_serie_b:
    if not bancos_sel:
        st.info("Seleccioná al menos un banco.")
    else:
        serie_b = serie_irregularidad_por_banco(bancos_sel)
        serie_b = serie_b[serie_b["yyyymm"] >= 201801]
        fig = go.Figure()
        palette = [COLORS["primary"], COLORS["accent_warm"], COLORS["secondary"], COLORS["accent"],
                   COLORS["positive"], COLORS["negative"], COLORS["neutral_mid"], COLORS["tertiary"],
                   "#7F1D2A", "#9B6B43", "#3A6F99", "#C8A951"]
        for i, c in enumerate(bancos_sel):
            sub = serie_b[serie_b["codigo_entidad"].astype(str) == str(c)]
            if sub.empty: continue
            fig.add_trace(go.Scatter(
                x=sub["fecha"], y=sub[definicion_b] / 100,
                name=codigo_to_nombre.get(str(c), str(c))[:35],
                line=dict(color=palette[i % len(palette)], width=2),
                hovertemplate=f"<b>%{{fullData.name}}</b><br>%{{x|%b %Y}}<br>%{{y:.1%}}<extra></extra>",
            ))
        fig.update_layout(
            yaxis_tickformat=".1%", height=440, hovermode="x unified",
            yaxis_title=f"Irregularidad {definicion_b}", xaxis_title=None,
        )
        st.plotly_chart(fig, use_container_width=True)

with tab_foto_b:
    if not bancos_sel:
        st.info("Seleccioná al menos un banco.")
    else:
        snap = ib[ib["codigo_entidad"].astype(str).isin([str(c) for c in bancos_sel])].copy()
        snap["valor"] = snap[definicion_b] / 100
        snap = snap.sort_values("valor", ascending=True)
        fig = px.bar(
            snap, x="valor", y="nombre_entidad", orientation="h",
            color="valor", color_continuous_scale="Reds",
        )
        fig.update_layout(
            xaxis_tickformat=".0%", coloraxis_showscale=False,
            height=max(280, 38 * len(snap)),
            yaxis_title=None, xaxis_title=f"Irregularidad {definicion_b} ({ult})",
            margin=dict(l=0, r=0, t=20, b=20),
        )
        sis_ratio = amplia_ult if definicion_b == "amplia" else estricta_ult
        fig.add_vline(
            x=sis_ratio, line_width=1, line_dash="dash", line_color=COLORS["neutral_mid"],
            annotation_text="Sistema", annotation_position="top",
        )
        fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:.1%}<extra></extra>")
        st.plotly_chart(fig, use_container_width=True)

with tab_tabla_b:
    tabla = ib.sort_values(definicion_b, ascending=False).copy()
    tabla["amplia_pct"] = tabla["amplia"] / 100
    tabla["estricta_pct"] = tabla["estricta"] / 100
    tabla_show = tabla[["nombre_entidad", "total", "amplia_pct", "estricta_pct"]].rename(columns={
        "nombre_entidad": "Banco",
        "total": "Cartera (miles $)",
        "amplia_pct": "Irreg. amplia",
        "estricta_pct": "Mora estricta",
    })
    st.dataframe(
        tabla_show.style.format({
            "Cartera (miles $)": "{:,.0f}",
            "Irreg. amplia": "{:.2%}",
            "Mora estricta": "{:.2%}",
        }),
        use_container_width=True, hide_index=True, height=440,
    )


st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────
# DEMANDA — Crédito por sector económico
# ─────────────────────────────────────────────────────────────────────────
section_header(
    "Demanda — crédito por sector económico",
    "Stock de préstamos por sector productivo (clasificación CIIU del BCRA). "
    "Refleja a quién va el crédito: empresas (industria, comercio, servicios, primaria, etc.) o personas físicas.",
)

act = load_actividad_total()

# Filtramos a top-level sectors (nom01) excluyendo Total y Discrepancia
SECTORES_VALIDOS = [
    "Producción primaria",
    "Industria manufacturera",
    "Electricidad, gas y agua",
    "Construcción",
    "Comercio al por mayor y al por menor: reparación de vehículos automotores, motocicletas, efectos personales y enseres domésticos",
    "Servicios",
    "Personas físicas en relación de dependencia laboral",
    "No identificada",
]

SECTOR_DISPLAY = {
    "Producción primaria": "Producción primaria",
    "Industria manufacturera": "Industria manufacturera",
    "Electricidad, gas y agua": "Electricidad, gas, agua",
    "Construcción": "Construcción",
    "Comercio al por mayor y al por menor: reparación de vehículos automotores, motocicletas, efectos personales y enseres domésticos": "Comercio",
    "Servicios": "Servicios",
    "Personas físicas en relación de dependencia laboral": "Personas físicas (consumo)",
    "No identificada": "No identificada",
}

# Sumamos act00t por nom01 + actfec
sub = act[act["nom01"].isin(SECTORES_VALIDOS)].copy()
sub["sector"] = sub["nom01"].map(SECTOR_DISPLAY)
sub["fecha"] = pd.to_datetime(sub["actfec"].astype(str), format="%Y%m%d")
agg = sub.groupby(["fecha", "sector"], as_index=False)["act00t"].sum()
agg = agg.rename(columns={"act00t": "stock"})

# Total por trimestre (para % share)
total_by_q = agg.groupby("fecha", as_index=False)["stock"].sum().rename(columns={"stock": "total"})
agg = agg.merge(total_by_q, on="fecha")
agg["share"] = agg["stock"] / agg["total"]

ult_q = agg["fecha"].max()
agg_ult = agg[agg["fecha"] == ult_q].copy().sort_values("stock", ascending=False)

# Color palette por sector
sector_colors = {
    "Producción primaria": COLORS["positive"],
    "Industria manufacturera": COLORS["primary"],
    "Electricidad, gas, agua": COLORS["secondary"],
    "Construcción": COLORS["accent_warm"],
    "Comercio": COLORS["accent"],
    "Servicios": COLORS["tertiary"],
    "Personas físicas (consumo)": "#9B6B43",
    "No identificada": COLORS["neutral_light"],
}

# Composición último trimestre (donut + ranking)
col_l, col_r = st.columns([2, 3])

with col_l:
    fig = px.pie(
        agg_ult, values="stock", names="sector", hole=0.5,
        color="sector", color_discrete_map=sector_colors,
    )
    fig.update_traces(
        textposition="inside", textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value:$,.2s}<br>(%{percent})<extra></extra>",
    )
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="v", yanchor="middle", y=0.5, x=1.05, font=dict(size=10)),
        title=dict(text=f"Composición — {ult_q.strftime('%b %Y')}", font=dict(size=13)),
    )
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    fig = px.bar(
        agg_ult.sort_values("stock", ascending=True),
        x="share", y="sector", orientation="h",
        color="sector", color_discrete_map=sector_colors,
    )
    fig.update_layout(
        xaxis_tickformat=".0%", height=380,
        yaxis_title=None, xaxis_title="% del crédito total",
        showlegend=False, margin=dict(l=0, r=0, t=40, b=10),
        title=dict(text="Ranking por participación", font=dict(size=13)),
    )
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:.1%}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)


# Evolución temporal: stack share over time
section_header(
    "Evolución de la composición por sector",
    "Cómo cambia la participación de cada sector en el stock total a lo largo del tiempo.",
)

fig = go.Figure()
sectores_ordenados = (
    agg_ult.sort_values("stock", ascending=False)["sector"].tolist()
)
for s in sectores_ordenados:
    sub_s = agg[agg["sector"] == s]
    fig.add_trace(go.Scatter(
        x=sub_s["fecha"], y=sub_s["share"],
        name=s, stackgroup="one",
        line=dict(color=sector_colors.get(s, COLORS["neutral_mid"]), width=0.5),
        hovertemplate=f"<b>{s}</b><br>%{{x|%b %Y}}<br>%{{y:.1%}}<extra></extra>",
    ))
fig.update_layout(
    yaxis_tickformat=".0%", height=380, hovermode="x unified",
    yaxis_title="Share del crédito total", xaxis_title=None,
    yaxis=dict(range=[0, 1]),
)
st.plotly_chart(fig, use_container_width=True)


st.markdown("---")
st.caption(
    "Notas. (1) Datos trimestrales del Estado de Situación de Deudores (BCRA). "
    "(2) Irregularidad amplia = (Total - Sit. 1) / Total. Mora estricta = (Sit. 3+) / Total. "
    "Definiciones expuestas para cubrir señales tempranas y mora oficial. "
    "(3) Promedios ponderados por cartera para agregaciones a sistema. "
    "(4) Códigos AA* y agregados (BANCOS, SISTEMA FINANCIERO) filtrados del ranking por banco. "
    "(5) Crédito por sector usa la clasificación CIIU del BCRA (panel_actividad_total). "
    "'Personas físicas' agrupa préstamos de consumo a hogares; el resto son sectores productivos. "
    "Ver `docs/CONTABILIDAD.md`."
)

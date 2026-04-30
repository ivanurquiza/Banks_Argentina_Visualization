"""Loaders cacheados para los parquet curados y series externas.

Diseño:
- Streamlit cacheado a nivel proceso (`@st.cache_data`) si está disponible.
- Si no estamos en Streamlit, fallback a `functools.lru_cache` para mantener
  la API uniforme entre app y scripts.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .. import paths


# ── caché unificado (Streamlit-aware) ─────────────────────────────────────
try:
    import streamlit as st
    _cache = st.cache_data(show_spinner=False)
except Exception:
    def _cache(fn):
        return lru_cache(maxsize=32)(fn)


# ── paneles principales ───────────────────────────────────────────────────
@_cache
def load_balance_mensual(proforma: bool = True) -> pd.DataFrame:
    """Balance mensual desde 2020 (moneda homogénea).

    Si `proforma=True` devuelve la versión con fusiones consolidadas.
    """
    name = "panel_balance_mensual_proforma" if proforma else "panel_balance_mensual"
    return pd.read_parquet(paths.panel(name))


@_cache
def load_balance_agregados() -> pd.DataFrame:
    return pd.read_parquet(paths.panel("panel_balance_agregados"))


@_cache
def load_indicadores() -> pd.DataFrame:
    return pd.read_parquet(paths.panel("panel_indicadores"))


@_cache
def load_estructura() -> pd.DataFrame:
    return pd.read_parquet(paths.panel("panel_estructura"))


@_cache
def load_distribgeo() -> pd.DataFrame:
    return pd.read_parquet(paths.panel("panel_distribgeo"))


@_cache
def load_sucursales_provincia() -> pd.DataFrame:
    return pd.read_parquet(paths.panel("panel_sucursales_provincia"))


@_cache
def load_actividad_grupo() -> pd.DataFrame:
    return pd.read_parquet(paths.panel("panel_actividad_grupo"))


@_cache
def load_actividad_total() -> pd.DataFrame:
    return pd.read_parquet(paths.panel("panel_actividad_total"))


@_cache
def load_actividad_localidad() -> pd.DataFrame:
    return pd.read_parquet(paths.panel("panel_actividad_localidad"))


@_cache
def load_esd() -> pd.DataFrame:
    return pd.read_parquet(paths.panel("panel_esd"))


# ── dimensiones ───────────────────────────────────────────────────────────
@_cache
def load_dim_entidades() -> pd.DataFrame:
    return pd.read_parquet(paths.dim("dim_entidades"))


@_cache
def load_dim_cuentas() -> pd.DataFrame:
    return pd.read_parquet(paths.dim("dim_cuentas"))


@_cache
def load_dim_grupos() -> pd.DataFrame:
    return pd.read_parquet(paths.dim("dim_grupos"))


@_cache
def load_dim_provincias() -> pd.DataFrame:
    return pd.read_parquet(paths.dim("dim_provincias"))


# ── crosswalks de referencia ──────────────────────────────────────────────
@_cache
def load_cuenta_categoria() -> pd.DataFrame:
    """Crosswalk cuenta → categoría temática.

    Renombra `codigo_cuenta_pattern` → `codigo_cuenta` para que el join
    con los paneles de balance funcione directo. Las filas con patrón
    (contienen `%`) se filtran porque hoy no aplicamos pattern matching.
    """
    df = pd.read_csv(paths.REFERENCE / "cuenta_categoria.csv")
    df = df.rename(columns={"codigo_cuenta_pattern": "codigo_cuenta"})
    df["codigo_cuenta"] = df["codigo_cuenta"].astype(str)
    return df


@_cache
def load_fusiones() -> pd.DataFrame:
    return pd.read_csv(paths.REFERENCE / "fusiones.csv")


@_cache
def load_provincias_iso() -> pd.DataFrame:
    return pd.read_csv(paths.REFERENCE / "provincias_iso.csv")


# ── series externas ───────────────────────────────────────────────────────
def _read_bcra_json(path: Path) -> pd.DataFrame:
    """Lee la respuesta JSON v4 BCRA → DataFrame (fecha, valor)."""
    with open(path) as f:
        payload = json.load(f)
    results = payload.get("results", [])
    rows: list[dict] = []
    for r in results:
        if isinstance(r, dict) and "detalle" in r:
            rows.extend(r["detalle"])
        else:
            rows.append(r)
    if not rows:
        return pd.DataFrame(columns=["fecha", "valor"])
    df = pd.DataFrame(rows)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df[["fecha", "valor"]].sort_values("fecha").reset_index(drop=True)


SERIE_BCRA = {
    "tc_a3500":   "005_tc_mayorista_a3500.json",
    "tc_minor":   "004_tc_minorista_vendedor.json",
    "reservas":   "001_reservas_internacionales.json",
    "base_mon":   "015_base_monetaria.json",
    "badlar":     "007_badlar_privados.json",
    "cer":        "030_cer.json",
    "uva":        "031_uva.json",
    "uvi":        "032_uvi.json",
}


@_cache
def load_bcra_serie(name: str) -> pd.DataFrame:
    """Devuelve una serie BCRA con columnas (fecha, valor).

    Nombres válidos: tc_a3500, tc_minor, reservas, base_mon, badlar, cer, uva, uvi.
    """
    if name not in SERIE_BCRA:
        raise ValueError(f"Serie BCRA desconocida: {name}. Opciones: {list(SERIE_BCRA)}")
    return _read_bcra_json(paths.BCRA_API / SERIE_BCRA[name])


@_cache
def load_ipc_nacional() -> pd.DataFrame:
    """IPC INDEC Nacional, Nivel General (Codigo=0).

    Devuelve DataFrame mensual con columnas: yyyymm (int), fecha (timestamp),
    indice (float, base dic-2016=100), v_m (variación mensual), v_ia (variación interanual).
    """
    raw = pd.read_csv(
        paths.INDEC / "serie_ipc_divisiones.csv",
        sep=";",
        dtype={"Periodo": str},
        encoding="latin-1",
    )
    nac = raw[(raw["Codigo"].astype(str) == "0") & (raw["Region"] == "Nacional")].copy()
    nac["yyyymm"] = nac["Periodo"].astype(int)
    nac["fecha"] = pd.to_datetime(nac["Periodo"] + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
    nac = nac.rename(columns={"Indice_IPC": "indice", "v_m_IPC": "v_m", "v_i_a_IPC": "v_ia"})

    def _ar_num(s: pd.Series) -> pd.Series:
        return pd.to_numeric(
            s.astype(str).str.replace(",", ".", regex=False).replace("NA", None),
            errors="coerce",
        )

    nac["indice"] = _ar_num(nac["indice"])
    nac["v_m"] = _ar_num(nac["v_m"])
    nac["v_ia"] = _ar_num(nac["v_ia"])
    return nac.sort_values("yyyymm")[["yyyymm", "fecha", "indice", "v_m", "v_ia"]].reset_index(drop=True)

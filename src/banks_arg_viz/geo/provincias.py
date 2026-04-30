"""Helpers geográficos: normalización de nombres y carga de geojson de provincias."""
from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .. import paths
from ..io import load_dim_provincias, load_provincias_iso

GEOJSON_PATH = paths.EXTERNAL / "geo" / "provincias_arg.geojson"


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def normalize_provincia(name: str | None) -> str | None:
    """Forma canónica para joins: mayúsculas, sin tildes, sin espacios extras."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return None
    s = _strip_accents(str(name)).upper().strip()
    s = " ".join(s.split())
    fixes = {
        "TIERRA DEL FUEGO": "TIERRA DEL FUEGO",
        "TIERRA DEL FUEGO ANTARTIDA E ISLAS DEL ATLANTICO SUR": "TIERRA DEL FUEGO",
        "TIERRA DEL FUEGO, ANTARTIDA E ISLAS DEL ATLANTICO SUR": "TIERRA DEL FUEGO",
        "CIUDAD AUTONOMA DE BUENOS AIRES": "CABA",
        "CABA": "CABA",
        "CIUDAD DE BUENOS AIRES": "CABA",
        "CIUDAD DE BUENOS AIRES CAPITAL FEDERAL": "CABA",
        "CIUDAD DE BUENOS AIRES - CAPITAL FEDERAL": "CABA",
        "CAPITAL FEDERAL": "CABA",
        # En el panel_distribgeo del BCRA Buenos Aires se reporta dividida.
        # Ambas sub-jurisdicciones se consolidan a la provincia.
        "GRAN BUENOS AIRES": "BUENOS AIRES",
        "RESTO DE LA PROVINCIA DE BUENOS AIRES": "BUENOS AIRES",
        "RESTO DE BUENOS AIRES": "BUENOS AIRES",
        "EXTERIOR": "EXTERIOR",
        "OPERAC.RESIDENTES EN EL EXTERIOR": "EXTERIOR",
    }
    return fixes.get(s, s)


@lru_cache(maxsize=1)
def _build_iso_map() -> dict[str, str]:
    iso_table = load_provincias_iso()
    out: dict[str, str] = {}
    for _, row in iso_table.iterrows():
        for col in ("nombre_bcra", "nombre_largo"):
            if col in iso_table.columns and pd.notna(row[col]):
                out[normalize_provincia(row[col])] = row["iso_codigo"]
    return out


PROVINCIA_TO_ISO = _build_iso_map


def add_iso(df: pd.DataFrame, prov_col: str = "provincia", iso_col: str = "iso_codigo") -> pd.DataFrame:
    iso_map = _build_iso_map()
    out = df.copy()
    out[iso_col] = out[prov_col].map(lambda x: iso_map.get(normalize_provincia(x)))
    return out


@lru_cache(maxsize=1)
def geojson_argentina() -> dict | None:
    """Carga el geojson de provincias y agrega un campo `iso_codigo` a cada feature.

    Devuelve None si el archivo no existe (la página de mapa muestra fallback).
    """
    if not GEOJSON_PATH.exists():
        return None
    with open(GEOJSON_PATH) as f:
        gj = json.load(f)

    iso_map = _build_iso_map()
    for feat in gj.get("features", []):
        props = feat.setdefault("properties", {})
        for cand in ("provincia", "name", "nombre", "NAME_1"):
            if cand in props and props[cand]:
                key = normalize_provincia(props[cand])
                props["iso_codigo"] = iso_map.get(key)
                props["provincia_canonica"] = key
                break
    return gj

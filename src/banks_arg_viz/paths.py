"""Rutas centrales del proyecto. Todas las cargas pasan por acá."""
from __future__ import annotations

import os
from pathlib import Path


def _resolve_root() -> Path:
    if env := os.environ.get("BANKS_ARG_VIZ_ROOT"):
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data" / "curated").is_dir():
            return parent
    raise RuntimeError(
        "No se encontró la raíz del proyecto. Definí BANKS_ARG_VIZ_ROOT."
    )


ROOT = _resolve_root()
DATA = ROOT / "data"

CURATED = DATA / "curated"
PANELES = CURATED / "paneles"
DIMENSIONES = CURATED / "dimensiones"

REFERENCE = DATA / "reference"
EXTERNAL = DATA / "external"
BCRA_API = EXTERNAL / "bcra_api"
INDEC = EXTERNAL / "indec"

SOURCES_YAML = DATA / "sources.yaml"


def panel(name: str) -> Path:
    return PANELES / f"{name}.parquet"


def dim(name: str) -> Path:
    return DIMENSIONES / f"{name}.parquet"

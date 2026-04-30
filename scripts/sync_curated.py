"""Sincroniza los parquet curados desde el repo de investigación.

Diseño del pipeline:
    [paper repo: Macroprudential_Regulation_Lending_Channel]
        data/interim/paneles_largos/*.parquet
        data/interim/dimensiones/*.parquet
        data/external/crosswalks/*.csv
                 │
                 ▼  (este script copia)
    [dashboard repo: Banks_Argentina_Visualization]
        data/curated/paneles/*.parquet
        data/curated/dimensiones/*.parquet
        data/reference/*.csv

El paper repo es la fuente de verdad. Este script lo asume como hermano
del dashboard repo en el filesystem, o configurable vía env var
PAPER_REPO_PATH.

Uso:
    python scripts/sync_curated.py             # usa autodetección
    PAPER_REPO_PATH=/ruta/al/paper python scripts/sync_curated.py
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from banks_arg_viz import paths


def _resolve_paper_root() -> Path | None:
    if env := os.environ.get("PAPER_REPO_PATH"):
        return Path(env).resolve()
    sibling = ROOT.parent / "Macroprudential_Regulation_Lending_Channel"
    if sibling.is_dir():
        return sibling
    return None


def _sync(src: Path, dst: Path, glob: str = "*") -> int:
    if not src.is_dir():
        print(f"SKIP {src} no existe")
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in src.glob(glob):
        if f.is_file():
            shutil.copy2(f, dst / f.name)
            n += 1
    return n


def main() -> int:
    paper = _resolve_paper_root()
    if paper is None:
        print("ERR No encuentro el paper repo. Definí PAPER_REPO_PATH.")
        return 1

    print(f"Source: {paper}")
    n_pan = _sync(paper / "data/interim/paneles_largos", paths.PANELES, "*.parquet")
    n_dim = _sync(paper / "data/interim/dimensiones", paths.DIMENSIONES, "*.parquet")
    n_cw = _sync(paper / "data/external/crosswalks", paths.REFERENCE, "*.csv")
    src_yaml = paper / "data/manifest/sources.yaml"
    if src_yaml.exists():
        shutil.copy2(src_yaml, paths.SOURCES_YAML)
        print(f"OK  sources.yaml ({src_yaml.stat().st_size:,} bytes)")

    print(f"OK  paneles: {n_pan}, dimensiones: {n_dim}, crosswalks: {n_cw}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

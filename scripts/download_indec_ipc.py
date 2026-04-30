"""Refresca el IPC de INDEC (serie por divisiones, nacional).

Fuente: https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-5-31  (CSV)

Como INDEC actualiza el CSV in-place, simplemente lo descargamos y
sobrescribimos. Si el endpoint cambia, hay que ajustar la URL.

Uso:
    python scripts/download_indec_ipc.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from banks_arg_viz import paths

URL = "https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv"


def main() -> int:
    dest = paths.INDEC / "serie_ipc_divisiones.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "banks-arg-viz/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = resp.read()
    except Exception as e:
        print(f"ERR descarga IPC: {e}")
        return 1
    with open(dest, "wb") as f:
        f.write(payload)
    print(f"OK  {dest.name} ({len(payload):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

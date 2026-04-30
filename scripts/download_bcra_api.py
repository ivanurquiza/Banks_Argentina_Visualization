"""Refresca las series monetarias diarias del BCRA (API v4).

Idempotente: sobrescribe los JSON locales con la última versión completa.
Series mantenidas: TC mayorista A3500, TC minorista, reservas, base monetaria,
BADLAR privados, CER, UVA, UVI.

Uso:
    python scripts/download_bcra_api.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from banks_arg_viz import paths

BASE = "https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias"
DESDE = "2015-01-01"
LIMIT = 3000

SERIES = [
    (5,  "tc_mayorista_a3500"),
    (4,  "tc_minorista_vendedor"),
    (1,  "reservas_internacionales"),
    (15, "base_monetaria"),
    (7,  "badlar_privados"),
    (30, "cer"),
    (31, "uva"),
    (32, "uvi"),
]


def fetch_serie(varid: int, short: str, dest_dir: Path) -> Path:
    today = time.strftime("%Y-%m-%d")
    url = f"{BASE}/{varid}?desde={DESDE}&hasta={today}&limit={LIMIT}"
    dest = dest_dir / f"{varid:03d}_{short}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.load(resp)
    with open(dest, "w") as f:
        json.dump(payload, f, ensure_ascii=False)
    return dest


def main() -> int:
    dest_dir = paths.BCRA_API
    failed = []
    for varid, short in SERIES:
        try:
            d = fetch_serie(varid, short, dest_dir)
            print(f"OK  {d.name}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"ERR {varid:03d}_{short}: {e}")
            failed.append((varid, short))
    if failed:
        print(f"\nFallaron {len(failed)} series: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

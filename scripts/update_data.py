"""Punto de entrada del pipeline de actualización de datos.

Ejecuta:
1. Refresh de series monetarias diarias del BCRA (rápido, autocontenido).
2. Refresh del IPC INDEC (rápido, autocontenido).
3. Sync de parquets curados desde el paper repo (requiere PAPER_REPO_PATH).

Uso:
    python scripts/update_data.py                  # todo
    python scripts/update_data.py --skip-curated   # sólo series macro
    python scripts/update_data.py --only-curated   # sólo parquets

Salida: imprime un resumen y devuelve exit code 0 si todo OK, 1 si algo falló.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, cmd: list[str]) -> tuple[str, int]:
    print(f"\n[{name}] starting...")
    r = subprocess.run(cmd, cwd=ROOT)
    print(f"[{name}] exit={r.returncode}")
    return name, r.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualiza datos del dashboard.")
    parser.add_argument("--skip-curated", action="store_true", help="No sincronizar parquets desde el paper repo")
    parser.add_argument("--only-curated", action="store_true", help="Sólo sincronizar parquets curados")
    args = parser.parse_args()

    py = sys.executable
    results = []

    if not args.only_curated:
        results.append(run_step("BCRA API", [py, "scripts/download_bcra_api.py"]))
        results.append(run_step("INDEC IPC", [py, "scripts/download_indec_ipc.py"]))

    if not args.skip_curated:
        results.append(run_step("Sync curated", [py, "scripts/sync_curated.py"]))

    print("\n=== Resumen ===")
    failed = 0
    for name, rc in results:
        flag = "OK" if rc == 0 else "FAIL"
        print(f"  [{flag}] {name}")
        failed += int(rc != 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

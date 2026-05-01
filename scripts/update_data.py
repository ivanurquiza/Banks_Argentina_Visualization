"""Punto de entrada del pipeline de actualización completo.

Ejecuta de punta a punta:
1. Refresh de series monetarias diarias del BCRA (rápido).
2. Refresh del IPC INDEC (rápido).
3. Descarga del último dump IEF disponible (~30MB, 1-2 min).
4. Procesamiento de los parquets curados (balance, esd, indicadores, etc).
5. Limpieza de archivos temporales.

Diseñado para correr autónomamente desde GitHub Actions cada mes después
de que el BCRA publica un nuevo dump IEF (típicamente entre el día 1 y el 6).

Uso:
    python scripts/update_data.py                    # pipeline completa
    python scripts/update_data.py --solo-macro       # solo BCRA API + IPC
    python scripts/update_data.py --solo-ief         # solo IEF download+process
    python scripts/update_data.py --skip-process     # download sin procesar
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, cmd: list[str], timeout: int = 1800) -> int:
    print(f"\n========= [{name}] =========")
    r = subprocess.run(cmd, cwd=ROOT, timeout=timeout)
    print(f"========= [{name}] exit={r.returncode}\n")
    return r.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualiza datos del dashboard.")
    parser.add_argument("--solo-macro", action="store_true", help="Solo BCRA API + INDEC IPC")
    parser.add_argument("--solo-ief", action="store_true", help="Solo IEF download + process")
    parser.add_argument("--skip-process", action="store_true", help="Saltar procesamiento de IEF")
    parser.add_argument("--cleanup", action="store_true", default=True, help="Borrar _raw extraído al final (default true)")
    parser.add_argument("--no-cleanup", dest="cleanup", action="store_false")
    parser.add_argument(
        "--ventana-ief", type=str, default="last",
        help="Ventana del download IEF: 'last' (default) | 'last-N' | 'YYYYMM-YYYYMM'",
    )
    args = parser.parse_args()

    py = sys.executable
    failed = []

    # 1+2. Macro APIs
    if not args.solo_ief:
        if run_step("BCRA API", [py, "scripts/download_bcra_api.py"], timeout=300) != 0:
            failed.append("BCRA API")
        if run_step("INDEC IPC", [py, "scripts/download_indec_ipc.py"], timeout=300) != 0:
            failed.append("INDEC IPC")

    # 3. IEF download
    if not args.solo_macro:
        if run_step(
            "Download IEF",
            [py, "scripts/download_bcra_ief.py", "--ventana", args.ventana_ief],
            timeout=900,
        ) != 0:
            failed.append("Download IEF")

        # 4. IEF processing
        if not args.skip_process:
            if run_step("Process IEF", [py, "scripts/process_ief.py"], timeout=1800) != 0:
                failed.append("Process IEF")

        # 5. Cleanup raw extracted dirs (mantiene .7z archivos para diagnóstico)
        if args.cleanup:
            raw_ief = ROOT / "data/_raw/bcra_ief"
            if raw_ief.exists():
                for d in raw_ief.iterdir():
                    if d.is_dir() and d.name.isdigit():
                        try:
                            shutil.rmtree(d)
                        except Exception as e:
                            print(f"⚠ no pude borrar {d}: {e}")
                print(f"[cleanup] removidos directorios extraídos en {raw_ief.relative_to(ROOT)}")

    print("\n=== RESUMEN ===")
    if failed:
        print(f"FALLÓ: {failed}")
        return 1
    print("Todos los pasos OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

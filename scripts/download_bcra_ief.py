"""Descarga incremental de los dumps mensuales IEF del BCRA.

Cada dump (.7z, ~30MB) contiene la historia completa hasta el mes corriente.
Para mantener el dashboard actualizado basta con descargar el último mes
publicado y reprocesar.

Cadencia: BCRA publica cada mes con un mes de lag (dump 202604 contiene datos
hasta 202603). Este script:

1. Detecta los meses disponibles en el sitio del BCRA (probe vía GET-range)
2. Descarga los que falten en data/_raw/bcra_ief/_archives/
3. Extrae cada uno a data/_raw/bcra_ief/{yyyymm}/

Idempotente: salta archivos ya descargados con tamaño correcto.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_IEF = ROOT / "data/_raw/bcra_ief"
ARCHIVES = RAW_IEF / "_archives"

BASE = "https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/Entidades"


def probe_existencia(yyyymm: str) -> tuple[str, int | None, int]:
    """Devuelve (yyyymm, status, full_size). status=206 -> existe."""
    url = f"{BASE}/{yyyymm}d.7z"
    r = subprocess.run(
        ["curl", "-sI", "-X", "GET", "-r", "0-0", "--max-time", "20", url],
        capture_output=True, text=True
    )
    status = None
    full_size = 0
    for line in r.stdout.splitlines():
        if line.startswith("HTTP/"):
            m = re.search(r"\s(\d{3})", line)
            if m:
                status = int(m.group(1))
        if line.lower().startswith("content-range:"):
            m = re.search(r"/(\d+)", line)
            if m:
                full_size = int(m.group(1))
    return yyyymm, status, full_size


def construir_inventario(min_yyyymm: int, max_yyyymm: int) -> list[tuple[str, int]]:
    """Lista los meses disponibles en BCRA dentro de la ventana."""
    meses = [f"{y}{m:02d}" for y in range(2002, 2030) for m in range(1, 13)]
    meses = [m for m in meses if min_yyyymm <= int(m) <= max_yyyymm]

    with ThreadPoolExecutor(max_workers=12) as ex:
        resultados = list(ex.map(probe_existencia, meses))

    disponibles = [(m, sz) for (m, st, sz) in resultados if st == 206]
    return disponibles


def descargar_y_extraer(yyyymm: str, expected_size: int) -> tuple[bool, bool]:
    """Descarga el .7z y lo extrae. Idempotente."""
    import py7zr

    url = f"{BASE}/{yyyymm}d.7z"
    archive = ARCHIVES / f"{yyyymm}.7z"
    extract_dir = RAW_IEF / yyyymm

    descargado = False
    if not (archive.exists() and archive.stat().st_size == expected_size):
        archive.parent.mkdir(parents=True, exist_ok=True)
        tmp = archive.with_suffix(".7z.part")
        r = subprocess.run(
            ["curl", "-sS", "--fail", "--max-time", "600", "-o", str(tmp), url],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            if tmp.exists():
                tmp.unlink()
            raise RuntimeError(f"curl falló para {yyyymm}: {r.stderr.strip()}")
        tmp.rename(archive)
        descargado = True

    extraido = False
    if not (extract_dir.exists() and any(extract_dir.iterdir())):
        extract_dir.mkdir(parents=True, exist_ok=True)
        with py7zr.SevenZipFile(archive, mode="r") as z:
            z.extractall(path=extract_dir)
        extraido = True

    return descargado, extraido


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga IEF dumps. Por default solo el último publicado."
    )
    parser.add_argument(
        "--ventana", type=str, default="last",
        help="'last' (default) = solo último; 'last-6' = últimos 6 meses; "
             "'YYYYMM-YYYYMM' = rango explícito.",
    )
    parser.add_argument(
        "--solo-listar", action="store_true",
        help="Listar meses disponibles sin descargar.",
    )
    args = parser.parse_args()

    today = time.strftime("%Y%m")
    today_int = int(today)
    if args.ventana == "last":
        # Probar el mes actual y el anterior
        min_y, max_y = today_int - 1, today_int
    elif args.ventana.startswith("last-"):
        n = int(args.ventana.split("-", 1)[1])
        # Aproximación: bajar n meses
        y, m = today_int // 100, today_int % 100
        m -= n
        while m < 1:
            m += 12
            y -= 1
        min_y = y * 100 + m
        max_y = today_int
    else:
        a, b = args.ventana.split("-")
        min_y, max_y = int(a), int(b)

    print(f"Buscando dumps IEF en ventana {min_y}-{max_y}...")
    disponibles = construir_inventario(min_y, max_y)
    print(f"Disponibles: {len(disponibles)} dumps → {[m for m, _ in disponibles]}")

    if args.solo_listar:
        return 0

    if not disponibles:
        print("Nada nuevo para descargar.")
        return 0

    failed = []
    for i, (yyyymm, expected_size) in enumerate(disponibles, 1):
        try:
            dl, ex = descargar_y_extraer(yyyymm, expected_size)
            print(f"[{i}/{len(disponibles)}] {yyyymm}  dl={dl} ex={ex}")
        except Exception as e:
            print(f"[{i}/{len(disponibles)}] {yyyymm}  ERROR: {e}")
            failed.append(yyyymm)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

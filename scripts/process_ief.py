"""Procesa los dumps IEF crudos en parquets curados.

Cada dump (en data/_raw/bcra_ief/{yyyymm}/) tiene la estructura:
  Entfin/Tec_Cont/
    bal_hist/balhist.txt    — historia completa de balance mensual
    balres/AA*.txt          — balance por agrupamientos
    esd/{cod}.txt           — Estado de Situación de Deudores (5 trimestres)
    indicad/{cod}.txt       — indicadores supervisorios
    inf_adi/{cod}.txt       — info adicional (estructura)
    entidad/{cod}.txt       — fechas y nombre de cada entidad
    distribgeo/*.xlsx       — préstamos/depósitos por provincia
  Entfin/Distrib/
    Suc_pcia/{cod}.txt      — sucursales por provincia

Los panels que cubren historia completa (balhist) se sobreescriben.
Los panels que rolan (esd, indicad, inf_adi, distribgeo) se MERGEAN con
las versiones existentes en data/curated/paneles/ — concat + drop_duplicates
keep="last" para que el dump más nuevo gane sobre los viejos.

Uso:
    python scripts/process_ief.py            # procesa todos los dumps en _raw
    python scripts/process_ief.py --panels balance,esd
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

RAW_IEF = ROOT / "data/_raw/bcra_ief"
PANELES = ROOT / "data/curated/paneles"
DIMENSIONES = ROOT / "data/curated/dimensiones"
REFERENCE = ROOT / "data/reference"

# Fecha mínima para el balance mensual (anteriores quedan en panel pre2020)
BALANCE_MIN_YYYYMM = 202001


# ── helpers comunes ──────────────────────────────────────────────────────
ENTIDAD_FECHA_IDX_BALANCE = list(range(12, 17))  # cols 13-17 (1-based)
ENTIDAD_FECHA_IDX_ESD = list(range(17, 22))      # cols 18-22 (1-based)


def _leer_fechas(entidad_file: Path, idx_list: list[int]) -> list[str]:
    """Lee las fechas de un archivo entidad/{cod}.txt (5 valores)."""
    texto = entidad_file.read_text(encoding="ISO-8859-1")
    campos = [c.strip().strip('"') for c in texto.split("\t")]
    if len(campos) <= idx_list[-1]:
        return []
    return [campos[i] for i in idx_list]


def _yyyymm_de_string_mes(s: str) -> str | None:
    """Convierte 'Mar-2024' → '202403'. Devuelve None si no parseable."""
    meses = {"Ene": "01", "Feb": "02", "Mar": "03", "Abr": "04", "May": "05", "Jun": "06",
             "Jul": "07", "Ago": "08", "Set": "09", "Sep": "09", "Oct": "10", "Nov": "11", "Dic": "12"}
    try:
        mes_str, yy = s.split("-")
        return yy + meses[mes_str]
    except Exception:
        return None


def _list_dumps() -> list[Path]:
    if not RAW_IEF.exists():
        return []
    return sorted([d for d in RAW_IEF.iterdir() if d.is_dir() and d.name.isdigit()])


def _ultimo_dump() -> Path | None:
    dumps = _list_dumps()
    return dumps[-1] if dumps else None


# ── 1) panel_balance_mensual (de balhist.txt) ────────────────────────────
def procesar_balance() -> None:
    """Reemplaza panel_balance_mensual.parquet con el último dump (full history)."""
    dump = _ultimo_dump()
    if dump is None:
        print("[balance] sin dumps en _raw, skip")
        return
    fpath = dump / "Entfin/Tec_Cont/bal_hist/balhist.txt"
    if not fpath.exists():
        print(f"[balance] no existe {fpath}, skip")
        return

    print(f"[balance] leyendo {fpath.relative_to(ROOT)} (puede tardar)...")
    raw = pd.read_csv(
        fpath, sep="\t", header=None,
        names=["codigo_entidad", "yyyymm", "codigo_cuenta", "saldo_miles_pesos"],
        encoding="ISO-8859-1",
        dtype={"codigo_entidad": str, "yyyymm": str, "codigo_cuenta": str, "saldo_miles_pesos": float},
    )
    print(f"[balance] filas leídas: {len(raw):,}")

    raw["yyyymm_int"] = raw["yyyymm"].astype(int)
    panel = raw[raw["yyyymm_int"] >= BALANCE_MIN_YYYYMM].copy()
    panel = panel[~panel["codigo_entidad"].str.startswith("AA")].copy()
    panel["fecha"] = pd.to_datetime(panel["yyyymm"], format="%Y%m") + pd.offsets.MonthEnd(0)
    panel["saldo"] = panel["saldo_miles_pesos"] * 1000
    panel["yyyymm"] = panel["yyyymm"].astype(int)
    panel = panel[["codigo_entidad", "yyyymm", "fecha", "codigo_cuenta", "saldo"]]

    out = PANELES / "panel_balance_mensual.parquet"
    panel.to_parquet(out, index=False)
    print(f"[balance] escrito {out.relative_to(ROOT)}: {len(panel):,} filas")

    # pre2020 (mantenemos en moneda corriente para análisis histórico)
    pre = raw[raw["yyyymm_int"] < BALANCE_MIN_YYYYMM].copy()
    pre = pre[~pre["codigo_entidad"].str.startswith("AA")].copy()
    pre["fecha"] = pd.to_datetime(pre["yyyymm"], format="%Y%m") + pd.offsets.MonthEnd(0)
    pre["saldo"] = pre["saldo_miles_pesos"] * 1000
    pre["yyyymm"] = pre["yyyymm"].astype(int)
    pre["moneda_homogenea"] = False
    pre = pre[["codigo_entidad", "yyyymm", "fecha", "codigo_cuenta", "saldo", "moneda_homogenea"]]
    out_pre = PANELES / "panel_balance_mensual_pre2020.parquet"
    pre.to_parquet(out_pre, index=False)
    print(f"[balance] escrito pre2020: {len(pre):,} filas")


def procesar_balance_proforma() -> None:
    """Aplica fusiones al panel mensual y guarda panel_balance_mensual_proforma.parquet."""
    panel_path = PANELES / "panel_balance_mensual.parquet"
    if not panel_path.exists():
        print("[proforma] panel_balance_mensual no existe, skip")
        return

    fusiones_path = REFERENCE / "fusiones.csv"
    if not fusiones_path.exists():
        print("[proforma] fusiones.csv no existe, skip")
        return

    fusiones = pd.read_csv(fusiones_path, dtype=str)
    absorciones = fusiones[
        (fusiones["tipo_evento"] == "absorcion")
        & fusiones["codigo_absorbido"].notna()
        & fusiones["codigo_absorbente"].notna()
        & (fusiones["codigo_absorbido"] != "")
        & (fusiones["codigo_absorbente"] != "")
        & (fusiones["aplicar_en_proforma"] == "TRUE")
    ].copy()

    mapeo = dict(zip(absorciones["codigo_absorbido"], absorciones["codigo_absorbente"]))

    panel = pd.read_parquet(panel_path)
    panel["codigo_entidad"] = panel["codigo_entidad"].map(lambda c: mapeo.get(c, c))

    panel = panel.groupby(
        ["codigo_entidad", "yyyymm", "fecha", "codigo_cuenta"], as_index=False
    )["saldo"].sum()
    panel = panel.sort_values(["codigo_entidad", "yyyymm", "codigo_cuenta"])

    out = PANELES / "panel_balance_mensual_proforma.parquet"
    panel.to_parquet(out, index=False)
    print(f"[proforma] escrito {out.relative_to(ROOT)}: {len(panel):,} filas")


# ── 2) panel_balance_agregados (de balres/AA*.txt) ───────────────────────
def procesar_agregados() -> None:
    """Apila balres por agrupamientos AA* desde todos los dumps."""
    dumps = _list_dumps()
    if not dumps:
        print("[agregados] sin dumps, skip")
        return
    BALRES_FECHA_COLS = ["v1", "v2", "v3", "v4", "v5"]
    bloques = []
    for d in dumps:
        balres_dir = d / "Entfin/Tec_Cont/balres"
        entidad_dir = d / "Entfin/Tec_Cont/entidad"
        if not balres_dir.exists() or not entidad_dir.exists():
            continue
        for balres_file in balres_dir.glob("AA*.txt"):
            cod = balres_file.stem
            entidad_file = entidad_dir / f"{cod}.txt"
            if not entidad_file.exists():
                continue
            try:
                fechas = _leer_fechas(entidad_file, ENTIDAD_FECHA_IDX_BALANCE)
                if len(fechas) != 5:
                    continue
                cols = ["codigo_entidad", "nombre_entidad", "fecha_corte", "codigo_linea",
                        "denominacion_cuenta", "v1", "v2", "v3", "v4", "v5"]
                df = pd.read_csv(balres_file, sep="\t", header=None, names=cols,
                                 encoding="ISO-8859-1", dtype=str)
                for c in BALRES_FECHA_COLS:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                mapeo = dict(zip(BALRES_FECHA_COLS, fechas))
                long = df.melt(
                    id_vars=["codigo_entidad", "nombre_entidad", "codigo_linea", "denominacion_cuenta"],
                    value_vars=BALRES_FECHA_COLS, var_name="slot_fecha", value_name="saldo_miles_pesos"
                )
                long["yyyymm"] = long["slot_fecha"].map(mapeo)
                long = long.drop(columns=["slot_fecha"]).dropna(subset=["yyyymm"])
                long["dump_yyyymm"] = int(d.name)
                bloques.append(long)
            except Exception:
                continue

    if not bloques:
        print("[agregados] no se pudo apilar nada")
        return
    raw = pd.concat(bloques, ignore_index=True)
    raw = raw[raw["yyyymm"].astype(str).str.match(r"^\d{6}$")].copy()
    raw["yyyymm"] = raw["yyyymm"].astype(int)
    raw["saldo"] = raw["saldo_miles_pesos"] * 1000
    raw = raw.sort_values(["codigo_entidad", "yyyymm", "codigo_linea", "dump_yyyymm"])
    panel = raw.drop_duplicates(subset=["codigo_entidad", "yyyymm", "codigo_linea"], keep="last")
    panel = panel[["codigo_entidad", "nombre_entidad", "yyyymm", "codigo_linea",
                   "denominacion_cuenta", "saldo", "dump_yyyymm"]]
    out = PANELES / "panel_balance_agregados.parquet"
    panel.to_parquet(out, index=False)
    print(f"[agregados] escrito {out.relative_to(ROOT)}: {len(panel):,} filas")


# ── 3) panel_esd (de esd/{cod}.txt) ──────────────────────────────────────
def procesar_esd() -> None:
    """Apila ESD desde todos los dumps. Requiere fechas del entidad/{cod}.txt."""
    dumps = _list_dumps()
    if not dumps:
        print("[esd] sin dumps, skip")
        return
    ESD_FECHA_COLS = ["v1", "v2", "v3", "v4", "v5"]
    bloques = []
    for d in dumps:
        esd_dir = d / "Entfin/Tec_Cont/esd"
        entidad_dir = d / "Entfin/Tec_Cont/entidad"
        if not esd_dir.exists() or not entidad_dir.exists():
            continue
        for esd_file in esd_dir.glob("*.txt"):
            if esd_file.name == "formato.txt":
                continue
            cod = esd_file.stem
            entidad_file = entidad_dir / f"{cod}.txt"
            if not entidad_file.exists():
                continue
            try:
                fechas_str = _leer_fechas(entidad_file, ENTIDAD_FECHA_IDX_ESD)
                fechas = [_yyyymm_de_string_mes(f) for f in fechas_str]
                if len(fechas) != 5 or any(f is None for f in fechas):
                    continue
                cols = ["codigo_entidad", "nombre_entidad", "fecha_corte", "codigo_linea",
                        "descripcion_situacion", "v1", "v2", "v3", "v4", "v5", "formato_valor"]
                df = pd.read_csv(esd_file, sep="\t", header=None, names=cols,
                                 encoding="ISO-8859-1", dtype=str)
                for c in ESD_FECHA_COLS:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                mapeo = dict(zip(ESD_FECHA_COLS, fechas))
                long = df.melt(
                    id_vars=["codigo_entidad", "nombre_entidad", "codigo_linea",
                             "descripcion_situacion", "formato_valor"],
                    value_vars=ESD_FECHA_COLS, var_name="slot_fecha", value_name="valor"
                )
                long["yyyymm"] = long["slot_fecha"].map(mapeo)
                long = long.drop(columns=["slot_fecha"]).dropna(subset=["yyyymm"])
                long["dump_yyyymm"] = int(d.name)
                bloques.append(long)
            except Exception:
                continue

    if not bloques:
        print("[esd] no se pudo apilar nada")
        return
    raw = pd.concat(bloques, ignore_index=True)
    raw = raw[raw["yyyymm"].astype(str).str.match(r"^\d{6}$")].copy()
    raw["yyyymm"] = raw["yyyymm"].astype(int)

    # MERGE con existente: las dump nuevas ganan sobre las viejas para el mismo (entidad, mes, línea)
    out = PANELES / "panel_esd.parquet"
    if out.exists():
        old = pd.read_parquet(out)
        combined = pd.concat([old, raw], ignore_index=True)
    else:
        combined = raw
    combined = combined.sort_values(["codigo_entidad", "yyyymm", "codigo_linea", "dump_yyyymm"])
    panel = combined.drop_duplicates(subset=["codigo_entidad", "yyyymm", "codigo_linea"], keep="last")
    panel.to_parquet(out, index=False)
    print(f"[esd] escrito {out.relative_to(ROOT)}: {len(panel):,} filas")


# ── 4) panel_indicadores (de indicad/{cod}.txt) ──────────────────────────
def procesar_indicadores() -> None:
    dumps = _list_dumps()
    if not dumps:
        print("[indicadores] sin dumps, skip")
        return
    FCOLS = ["v1", "v2", "v3", "v4", "v5"]
    bloques = []
    for d in dumps:
        ind_dir = d / "Entfin/Tec_Cont/indicad"
        entidad_dir = d / "Entfin/Tec_Cont/entidad"
        if not ind_dir.exists() or not entidad_dir.exists():
            continue
        for ind_file in ind_dir.glob("*.txt"):
            if ind_file.name == "formato.txt":
                continue
            cod = ind_file.stem
            entidad_file = entidad_dir / f"{cod}.txt"
            if not entidad_file.exists():
                continue
            try:
                fechas = _leer_fechas(entidad_file, ENTIDAD_FECHA_IDX_BALANCE)
                if len(fechas) != 5:
                    continue
                cols = ["codigo_entidad", "nombre_entidad", "fecha_corte", "codigo_linea",
                        "descripcion_indicador", "v1", "v2", "v3", "v4", "v5",
                        "valor_grupo_homogeneo", "valor_top10_privados", "valor_sistema_financiero",
                        "formato_valor"]
                df = pd.read_csv(ind_file, sep="\t", header=None, names=cols,
                                 encoding="ISO-8859-1", dtype=str)
                for c in FCOLS + ["valor_grupo_homogeneo", "valor_top10_privados", "valor_sistema_financiero"]:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                mapeo = dict(zip(FCOLS, fechas))
                long = df.melt(
                    id_vars=["codigo_entidad", "nombre_entidad", "codigo_linea", "descripcion_indicador",
                             "valor_grupo_homogeneo", "valor_top10_privados", "valor_sistema_financiero",
                             "formato_valor"],
                    value_vars=FCOLS, var_name="slot_fecha", value_name="valor"
                )
                long["yyyymm"] = long["slot_fecha"].map(mapeo)
                long = long.drop(columns=["slot_fecha"]).dropna(subset=["yyyymm"])
                long["dump_yyyymm"] = int(d.name)
                bloques.append(long)
            except Exception:
                continue

    if not bloques:
        print("[indicadores] no se pudo apilar nada")
        return
    raw = pd.concat(bloques, ignore_index=True)
    raw = raw[raw["yyyymm"].astype(str).str.match(r"^\d{6}$")].copy()
    raw["yyyymm"] = raw["yyyymm"].astype(int)

    out = PANELES / "panel_indicadores.parquet"
    if out.exists():
        old = pd.read_parquet(out)
        combined = pd.concat([old, raw], ignore_index=True)
    else:
        combined = raw
    combined = combined.sort_values(["codigo_entidad", "yyyymm", "codigo_linea", "dump_yyyymm"])
    panel = combined.drop_duplicates(subset=["codigo_entidad", "yyyymm", "codigo_linea"], keep="last")
    panel.to_parquet(out, index=False)
    print(f"[indicadores] escrito {out.relative_to(ROOT)}: {len(panel):,} filas")


# ── 5) panel_estructura (de inf_adi/{cod}.txt) ───────────────────────────
def procesar_estructura() -> None:
    dumps = _list_dumps()
    if not dumps:
        return
    FCOLS = ["v1", "v2", "v3", "v4", "v5"]
    bloques = []
    for d in dumps:
        inf_dir = d / "Entfin/Tec_Cont/inf_adi"
        entidad_dir = d / "Entfin/Tec_Cont/entidad"
        if not inf_dir.exists() or not entidad_dir.exists():
            continue
        for inf_file in inf_dir.glob("*.txt"):
            if inf_file.name == "formato.txt":
                continue
            cod = inf_file.stem
            entidad_file = entidad_dir / f"{cod}.txt"
            if not entidad_file.exists():
                continue
            try:
                fechas = _leer_fechas(entidad_file, ENTIDAD_FECHA_IDX_BALANCE)
                if len(fechas) != 5:
                    continue
                cols = ["codigo_entidad", "nombre_entidad", "fecha_corte", "codigo_linea",
                        "descripcion_informacion", "v1", "v2", "v3", "v4", "v5"]
                df = pd.read_csv(inf_file, sep="\t", header=None, names=cols,
                                 encoding="ISO-8859-1", dtype=str)
                for c in FCOLS:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                mapeo = dict(zip(FCOLS, fechas))
                long = df.melt(
                    id_vars=["codigo_entidad", "nombre_entidad", "codigo_linea", "descripcion_informacion"],
                    value_vars=FCOLS, var_name="slot_fecha", value_name="valor"
                )
                long["yyyymm"] = long["slot_fecha"].map(mapeo)
                long = long.drop(columns=["slot_fecha"]).dropna(subset=["yyyymm"])
                long["dump_yyyymm"] = int(d.name)
                bloques.append(long)
            except Exception:
                continue

    if not bloques:
        return
    raw = pd.concat(bloques, ignore_index=True)
    raw = raw[raw["yyyymm"].astype(str).str.match(r"^\d{6}$")].copy()
    raw["yyyymm"] = raw["yyyymm"].astype(int)
    out = PANELES / "panel_estructura.parquet"
    if out.exists():
        old = pd.read_parquet(out)
        combined = pd.concat([old, raw], ignore_index=True)
    else:
        combined = raw
    combined = combined.sort_values(["codigo_entidad", "yyyymm", "codigo_linea", "dump_yyyymm"])
    panel = combined.drop_duplicates(subset=["codigo_entidad", "yyyymm", "codigo_linea"], keep="last")
    panel.to_parquet(out, index=False)
    print(f"[estructura] escrito {out.relative_to(ROOT)}: {len(panel):,} filas")


# ── 6) panel_sucursales_provincia (de Distrib/Suc_pcia/{cod}.txt) ────────
def procesar_sucursales() -> None:
    dumps = _list_dumps()
    if not dumps:
        return
    cols = ["codigo_entidad", "nombre_entidad", "fecha_corte", "codigo_provincia", "nombre_provincia",
            "sucursales_plenas", "sucursales_op_especifica", "sucursales_moviles",
            "dependencias_automatizadas", "cajeros_automaticos", "terminales_autoservicio",
            "puestos_promocion", "agencias_complementarias", "cantidad_entidades"]
    bloques = []
    for d in dumps:
        sc_dir = d / "Entfin/Distrib/Suc_pcia"
        if not sc_dir.exists():
            continue
        for f in sc_dir.glob("*.txt"):
            if f.name == "formato.txt":
                continue
            try:
                df = pd.read_csv(f, sep="\t", header=None, names=cols,
                                 encoding="ISO-8859-1", dtype=str)
                df["dump_yyyymm"] = int(d.name)
                bloques.append(df)
            except Exception:
                continue

    if not bloques:
        return
    raw = pd.concat(bloques, ignore_index=True)
    for c in ["sucursales_plenas", "sucursales_op_especifica", "sucursales_moviles",
              "dependencias_automatizadas", "cajeros_automaticos", "terminales_autoservicio",
              "puestos_promocion", "agencias_complementarias", "cantidad_entidades"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw["fecha_corte_int"] = pd.to_numeric(raw["fecha_corte"], errors="coerce").fillna(0).astype(int)
    raw = raw.sort_values(["codigo_entidad", "fecha_corte_int", "codigo_provincia", "dump_yyyymm"])
    panel = raw.drop_duplicates(subset=["codigo_entidad", "fecha_corte_int", "codigo_provincia"], keep="last")
    panel = panel.drop(columns=["fecha_corte_int"])
    out = PANELES / "panel_sucursales_provincia.parquet"
    panel.to_parquet(out, index=False)
    print(f"[sucursales] escrito {out.relative_to(ROOT)}: {len(panel):,} filas")


# ── 7) panel_distribgeo (de distribgeo/*.xlsx) ───────────────────────────
def procesar_distribgeo() -> None:
    dumps = _list_dumps()
    if not dumps:
        return
    bloques = []
    for d in dumps:
        xlsx_files = list((d / "Entfin/Tec_Cont/distribgeo").glob("*.xlsx"))
        if not xlsx_files:
            continue
        try:
            df = pd.read_excel(xlsx_files[0], header=3)
            df["dump_yyyymm"] = int(d.name)
            bloques.append(df)
        except Exception:
            continue

    if not bloques:
        return
    raw = pd.concat(bloques, ignore_index=True)
    rename = {
        "Fecha": "fecha_corte_int",
        "Código": "codigo_entidad",
        "Entidad": "nombre_entidad",
        "Provincia": "provincia",
        "Préstamos (1)": "prestamos_miles_pesos",
        "Depósitos (2)": "depositos_miles_pesos",
    }
    raw = raw.rename(columns=rename)
    fecha_num = pd.to_numeric(raw["fecha_corte_int"], errors="coerce")
    raw = raw[fecha_num.notna() & raw["codigo_entidad"].notna()].copy()
    raw["fecha_corte_int"] = fecha_num.dropna().astype(int)
    raw["codigo_entidad"] = pd.to_numeric(raw["codigo_entidad"], errors="coerce").astype("Int64").astype(str).str.zfill(5)
    raw["fecha_corte"] = pd.to_datetime(raw["fecha_corte_int"].astype(str), format="%Y%m%d", errors="coerce")
    raw["yyyymm_corte"] = raw["fecha_corte"].dt.strftime("%Y%m").astype(int)
    raw["prestamos"] = raw["prestamos_miles_pesos"] * 1000
    raw["depositos"] = raw["depositos_miles_pesos"] * 1000
    raw = raw[["codigo_entidad", "nombre_entidad", "yyyymm_corte", "fecha_corte",
               "provincia", "prestamos", "depositos", "dump_yyyymm"]]
    raw = raw.sort_values(["codigo_entidad", "yyyymm_corte", "provincia", "dump_yyyymm"])
    panel = raw.drop_duplicates(subset=["codigo_entidad", "yyyymm_corte", "provincia"], keep="last")
    out = PANELES / "panel_distribgeo.parquet"
    panel.to_parquet(out, index=False)
    print(f"[distribgeo] escrito {out.relative_to(ROOT)}: {len(panel):,} filas")


# ── orquestador ──────────────────────────────────────────────────────────
PANELS = {
    "balance": procesar_balance,
    "proforma": procesar_balance_proforma,
    "agregados": procesar_agregados,
    "esd": procesar_esd,
    "indicadores": procesar_indicadores,
    "estructura": procesar_estructura,
    "sucursales": procesar_sucursales,
    "distribgeo": procesar_distribgeo,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Procesa IEF dumps a parquets.")
    parser.add_argument(
        "--panels",
        type=str,
        default=",".join(PANELS.keys()),
        help=f"Lista separada por coma. Disponibles: {','.join(PANELS.keys())}",
    )
    args = parser.parse_args()

    PANELES.mkdir(parents=True, exist_ok=True)
    targets = [p.strip() for p in args.panels.split(",") if p.strip()]
    failed = []
    for t in targets:
        if t not in PANELS:
            print(f"⚠ panel desconocido: {t}, opciones: {list(PANELS)}")
            continue
        try:
            print(f"\n=== Procesando: {t} ===")
            PANELS[t]()
        except Exception as e:
            print(f"⚠ error procesando {t}: {e}")
            failed.append(t)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

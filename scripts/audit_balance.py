"""Auditoría contable del panel_balance_mensual.

Para cada mes del panel verifica:
1. La identidad Activo = Pasivo + Patrimonio + Resultado_curso, con signo flip aplicado.
2. La discrepancia debe ser < 0.1% del activo (tolerancia de redondeo en NIIF).
3. No haya cuentas memo (9xxxxx) ni partidas fuera de balance (7xxxxx) infiltradas.
4. La cobertura del clasificador de títulos sea 100%.

Uso:
    python scripts/audit_balance.py            # último mes
    python scripts/audit_balance.py --all      # todos los meses
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from banks_arg_viz.io import load_balance_mensual
from banks_arg_viz.kpis.securities import catalogo_titulos


def audit_mes(bal: pd.DataFrame, yyyymm: int, tolerance_pct: float = 0.1) -> dict:
    sub = bal[bal["yyyymm"] == yyyymm]
    if sub.empty:
        return {"yyyymm": yyyymm, "ok": False, "razon": "sin datos"}

    def _ssum(prefix):
        return sub[sub["codigo_cuenta"].str.startswith(prefix)]["saldo"].sum()

    A = _ssum("1") + _ssum("2")
    P = _ssum("3")
    PN = _ssum("4")
    R = _ssum("5") + _ssum("6")
    OB7 = _ssum("7")
    M9 = _ssum("9")

    res_implicito = A - P - PN
    res_nominal = -R
    diff = res_implicito - res_nominal

    return {
        "yyyymm": yyyymm,
        "activo_T": A / 1e12,
        "pasivo_T": P / 1e12,
        "patrim_T": PN / 1e12,
        "resultados_T": R / 1e12,
        "off_balance_T": OB7 / 1e12,
        "memo_T": M9 / 1e12,
        "diff_T": diff / 1e12,
        "diff_pct_activo": 100 * diff / A if A else 0,
        "ok": (
            abs(diff) < abs(A) * tolerance_pct / 100
            and abs(M9) < 1e6  # esencialmente 0
            and abs(OB7) < abs(A) * 0.001  # off-balance debe netar a 0
        ),
    }


def audit_titulos() -> dict:
    bal = load_balance_mensual()
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    cat = catalogo_titulos()
    cubiertas = set(cat["codigo_cuenta"].astype(str))

    cuentas_12 = (
        bal[bal["codigo_cuenta"].str.startswith("12")]
        .groupby("codigo_cuenta")["saldo"].sum()
    )
    no_cub = cuentas_12[~cuentas_12.index.isin(cubiertas)]

    sin_emisor = (cat["emisor"] == "Sin clasificar").sum()
    sin_med = (cat["medicion"] == "Sin clasificar").sum()

    return {
        "cuentas_12_total": len(cuentas_12),
        "cuentas_no_clasificadas": len(no_cub),
        "saldo_no_clasificado_T": no_cub.sum() / 1e12,
        "catalogo_emisor_sin": sin_emisor,
        "catalogo_medicion_sin": sin_med,
        "ok_cobertura": len(no_cub) == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoría contable")
    parser.add_argument("--all", action="store_true", help="Auditar todos los meses")
    parser.add_argument("--tolerance", type=float, default=0.1, help="Tolerancia % activo")
    args = parser.parse_args()

    bal = load_balance_mensual()
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)

    if args.all:
        meses = sorted(bal["yyyymm"].unique())
    else:
        meses = [int(bal["yyyymm"].max())]

    print("="*78)
    print(f"AUDITORÍA CONTABLE — {len(meses)} mes(es)")
    print("="*78)
    print(f"{'mes':<8}{'A (T)':>10}{'P (T)':>10}{'PN (T)':>10}{'R (T)':>10}{'diff %':>10}  ok")
    print("-"*78)

    n_ok = 0
    for m in meses:
        r = audit_mes(bal, m, tolerance_pct=args.tolerance)
        flag = "✓" if r["ok"] else "✗"
        print(
            f"{r['yyyymm']:<8}{r['activo_T']:>10.2f}{r['pasivo_T']:>10.2f}"
            f"{r['patrim_T']:>10.2f}{r['resultados_T']:>10.2f}"
            f"{r['diff_pct_activo']:>9.4f}%  {flag}"
        )
        if r["ok"]:
            n_ok += 1

    print("-"*78)
    print(f"Total: {n_ok}/{len(meses)} meses OK")

    print("\n" + "="*78)
    print("AUDITORÍA — CLASIFICADOR DE TÍTULOS")
    print("="*78)
    t = audit_titulos()
    for k, v in t.items():
        print(f"  {k}: {v}")
    flag = "✓" if t["ok_cobertura"] else "✗"
    print(f"\n  Clasificador títulos OK: {flag}")

    return 0 if (n_ok == len(meses) and t["ok_cobertura"]) else 1


if __name__ == "__main__":
    sys.exit(main())

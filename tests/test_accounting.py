"""Tests de integridad contable. Si fallan, hay un problema con el flip de signos
o con la cobertura de cuentas."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd
import pytest


def test_identidad_contable_cierra_al_centavo():
    """Activo - Pasivo - Patrimonio - Resultados ≈ 0 para todo el panel."""
    from banks_arg_viz.io import load_balance_mensual

    bal = load_balance_mensual()
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)

    for ym in bal["yyyymm"].unique():
        sub = bal[bal["yyyymm"] == ym]

        def _sumar(prefix):
            return sub[sub["codigo_cuenta"].str.startswith(prefix)]["saldo"].sum()

        A = _sumar("1") + _sumar("2")
        P = _sumar("3")
        PN = _sumar("4")
        R = _sumar("5") + _sumar("6")
        diff = A - P - PN - (-R)  # -R porque resultados se almacenan haber-side
        if A == 0:
            continue
        assert abs(diff) / abs(A) < 1e-4, (
            f"Identidad rota en {ym}: diff={diff:.0f}, "
            f"diff%activo={100*diff/A:.6f}%"
        )


def test_no_memo_accounts_en_balance():
    """Las cuentas 9xxxxx son memo y no deben aparecer en panel_balance_mensual."""
    from banks_arg_viz.io import load_balance_mensual

    bal = load_balance_mensual()
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    en_balance = set(bal["codigo_cuenta"].unique())
    memo = [c for c in en_balance if c.startswith("9")]
    assert len(memo) == 0, f"Cuentas memo (9xxxxx) infiltradas: {memo[:5]}"


def test_off_balance_neta_a_cero():
    """Capítulo 7 (PARTIDAS FUERA DE BALANCE) debe netar a aprox. cero por mes."""
    from banks_arg_viz.io import load_balance_mensual

    bal = load_balance_mensual()
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)

    for ym in bal["yyyymm"].unique():
        ob = bal[(bal["yyyymm"] == ym) & bal["codigo_cuenta"].str.startswith("7")]["saldo"].sum()
        # Con flip aplicado, deudoras + (-acreedoras inv) ≈ 0; dejamos margen
        assert abs(ob) < 1e10 or ob == 0, f"Off-balance no balancea en {ym}: {ob:,.0f}"


def test_titulos_clasificacion_cobertura_100pct():
    """El clasificador de títulos debe cubrir 100% de las cuentas 12xxxx con saldo."""
    from banks_arg_viz.io import load_balance_mensual
    from banks_arg_viz.kpis.securities import catalogo_titulos

    bal = load_balance_mensual()
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    cuentas_reportadas = set(
        bal[bal["codigo_cuenta"].str.startswith("12")]["codigo_cuenta"].unique()
    )

    cat = catalogo_titulos()
    catalogadas = set(cat["codigo_cuenta"].astype(str))
    no_cubiertas = cuentas_reportadas - catalogadas

    assert len(no_cubiertas) == 0, (
        f"{len(no_cubiertas)} cuentas 12xxxx en panel_balance no están en el catálogo. "
        f"Ejemplos: {list(no_cubiertas)[:5]}"
    )


def test_titulos_emisor_completamente_clasificado():
    """Todos los emisores en el catálogo deben estar clasificados (sin 'Sin clasificar')."""
    from banks_arg_viz.kpis.securities import catalogo_titulos

    cat = catalogo_titulos()
    sin = cat[cat["emisor"] == "Sin clasificar"]
    assert len(sin) == 0, f"{len(sin)} cuentas sin emisor clasificado: {sin['codigo_cuenta'].tolist()[:5]}"


def test_signo_flip_pasivos_y_patrimonio():
    """Después del flip, el activo, pasivo y patrimonio deben ser positivos en agregado."""
    from banks_arg_viz.io import load_balance_mensual

    bal = load_balance_mensual()
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)

    sub = bal[bal["yyyymm"] == int(bal["yyyymm"].max())]
    A = sub[sub["codigo_cuenta"].str.startswith(("1", "2"))]["saldo"].sum()
    P = sub[sub["codigo_cuenta"].str.startswith("3")]["saldo"].sum()
    PN = sub[sub["codigo_cuenta"].str.startswith("4")]["saldo"].sum()

    assert A > 0, f"Activo agregado debe ser positivo, es {A:,.0f}"
    assert P > 0, f"Pasivo agregado (post-flip) debe ser positivo, es {P:,.0f}"
    assert PN > 0, f"Patrimonio agregado (post-flip) debe ser positivo, es {PN:,.0f}"

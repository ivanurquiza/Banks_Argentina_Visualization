"""Cálculos sobre el panel de balance mensual.

Convención: trabajamos con `panel_balance_mensual_proforma` (fusiones consolidadas)
joineado con `dim_cuentas` y `cuenta_categoria` para sumar por categoría temática.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from ..io import load_balance_mensual, load_cuenta_categoria, load_dim_cuentas

# Códigos de cuenta de primer nivel (capítulos del plan de cuentas BCRA).
ACTIVO_PREFIX = "1"
PASIVO_PREFIX = "2"
PATRIMONIO_PREFIX = "3"
RESULTADOS_PREFIX = "5"


def _balance_with_meta(proforma: bool = True) -> pd.DataFrame:
    bal = load_balance_mensual(proforma=proforma)
    dim = load_dim_cuentas()[["codigo_cuenta", "denominacion", "nivel", "es_regularizadora", "es_cera"]]
    return bal.merge(dim, on="codigo_cuenta", how="left")


def saldos_por_categoria(
    categorias: Iterable[str] | None = None,
    entidades: Iterable[str] | None = None,
    proforma: bool = True,
) -> pd.DataFrame:
    """Suma saldos por categoría temática (cuenta_categoria.csv).

    Devuelve panel: codigo_entidad × yyyymm × categoria × saldo.
    """
    bal = load_balance_mensual(proforma=proforma)
    cat = load_cuenta_categoria()[["codigo_cuenta", "categoria"]].dropna()
    cat = cat[~cat["codigo_cuenta"].str.contains("%", na=False)]

    bal = bal.copy()
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    df = bal.merge(cat, on="codigo_cuenta", how="inner")

    if categorias:
        df = df[df["categoria"].isin(list(categorias))]
    if entidades:
        df = df[df["codigo_entidad"].isin(list(entidades))]

    return (
        df.groupby(["codigo_entidad", "yyyymm", "fecha", "categoria"], as_index=False)["saldo"]
        .sum()
    )


def _agregar_cuenta_raiz(prefix: str, label: str, proforma: bool = True) -> pd.DataFrame:
    """Suma todas las cuentas de detalle (no regularizadoras) que comienzan con `prefix`.

    Esto reproduce el saldo del capítulo (ACTIVO, PASIVO, etc.) sumando las hojas.
    """
    bal = _balance_with_meta(proforma=proforma)
    bal = bal[
        bal["codigo_cuenta"].astype(str).str.startswith(prefix)
        & (~bal["es_regularizadora"].fillna(False))
    ]
    out = bal.groupby(["codigo_entidad", "yyyymm", "fecha"], as_index=False)["saldo"].sum()
    out["serie"] = label
    return out


def activo_total(proforma: bool = True) -> pd.DataFrame:
    return _agregar_cuenta_raiz(ACTIVO_PREFIX, "ACTIVO", proforma=proforma)


def pasivo_total(proforma: bool = True) -> pd.DataFrame:
    return _agregar_cuenta_raiz(PASIVO_PREFIX, "PASIVO", proforma=proforma)


def credito_spnf(proforma: bool = True) -> pd.DataFrame:
    """Crédito al Sector Privado No Financiero residente del país (ARS+ME).

    Suma las categorías deposito_*_spnf_* del crosswalk; si no existieran,
    cae a una agregación por prefix simple.
    """
    df = saldos_por_categoria(
        categorias=["credito_me_spnf", "canal_credito_me_residentes_pais"],
        proforma=proforma,
    )
    return df


def deposito_spnf(proforma: bool = True) -> pd.DataFrame:
    df = saldos_por_categoria(
        categorias=["deposito_ars_spnf_total", "deposito_me_spnf_total"],
        proforma=proforma,
    )
    return df


def composicion_activo(codigo_entidad: str, yyyymm: int, proforma: bool = True) -> pd.DataFrame:
    """Composición del activo a una fecha: cuentas de nivel 1 dentro del 1xxxxx."""
    bal = _balance_with_meta(proforma=proforma)
    sub = bal[
        (bal["codigo_entidad"] == codigo_entidad)
        & (bal["yyyymm"] == yyyymm)
        & (bal["codigo_cuenta"].astype(str).str.startswith(ACTIVO_PREFIX))
        & (bal["nivel"] == 1)
    ]
    return sub[["codigo_cuenta", "denominacion", "saldo"]].sort_values("saldo", ascending=False)


def composicion_pasivo(codigo_entidad: str, yyyymm: int, proforma: bool = True) -> pd.DataFrame:
    bal = _balance_with_meta(proforma=proforma)
    sub = bal[
        (bal["codigo_entidad"] == codigo_entidad)
        & (bal["yyyymm"] == yyyymm)
        & (bal["codigo_cuenta"].astype(str).str.startswith(PASIVO_PREFIX))
        & (bal["nivel"] == 1)
    ]
    return sub[["codigo_cuenta", "denominacion", "saldo"]].sort_values("saldo", ascending=False)

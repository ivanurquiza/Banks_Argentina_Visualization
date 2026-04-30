"""KPIs y agregaciones del balance en moneda extranjera (ME = USD principalmente).

Aprovecha los patrones del crosswalk `cuenta_categoria.csv` para identificar
los capítulos 115 (efectivo+depósitos en bancos en ME), 125 (títulos en ME),
135 (préstamos ME residentes país), 136 (préstamos ME exterior),
315 (depósitos ME residentes país), 316 (depósitos ME exterior).
"""
from __future__ import annotations

import pandas as pd

from ..io import load_balance_mensual

# Capítulos del plan BCRA en moneda extranjera. Los stocks se reportan en
# pesos al tipo de cambio del cierre del mes; con `to_usd_native` los
# reconvertimos al USD original.
PREFIX_ME = {
    "credito_residentes": ("135",),               # Préstamos ME a residentes país (incl. SPNF + SF + SP)
    "credito_spnf": ("1357",),                    # Préstamos ME al SPNF residentes país (familias y empresas)
    "credito_sp": ("1351",),                      # Préstamos ME al Sector Público
    "credito_sf": ("1354",),                      # Préstamos ME interbancarios domésticos
    "credito_exterior": ("136",),                 # Préstamos ME a residentes exterior
    # NOTA: 315xxx incluye SP no fin (3151), SF (3154) y SPNF (3157). Para
    # comparar con préstamos al Sector Privado (1357) usamos el espejo 3157.
    "deposito_residentes": ("3157",),             # Depósitos ME del Sector Privado residentes país (incl. CERA USD)
    "deposito_residentes_total": ("315",),        # Total cap. 315: incluye SP, SF y SPNF
    "deposito_publico_me": ("3151",),             # Depósitos ME del Sector Público
    "deposito_exterior": ("316",),                # Depósitos ME residentes exterior
    "efectivo_bancos_me": ("115",),               # Efectivo + depósitos en bancos en ME (incl. encaje)
    "titulos_publicos_me": ("125",),              # Títulos públicos en ME (incl. Tesoro USD, Letras BCRA)
    "otros_activos_me": ("145",),                 # Otros créditos por interm. fin. en ME
}

# Capítulos para la cobertura de pasivos ME (encajes + reserva interna).
ENCAJE_BCRA_ME = "115015"   # BCRA cuenta corriente en ME (cuenta principal de integración)


def stock_me(
    serie: str,
    proforma: bool = True,
    entidades: list[str] | None = None,
) -> pd.DataFrame:
    """Stock mensual del agregado ME `serie` en pesos homogéneos.

    Para convertir a USD nativo aplicar `transforms.to_usd_native` después.
    """
    if serie not in PREFIX_ME:
        raise ValueError(f"Serie ME desconocida: {serie}. Opciones: {list(PREFIX_ME)}")
    bal = load_balance_mensual(proforma=proforma)
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    sub = bal[bal["codigo_cuenta"].str.startswith(PREFIX_ME[serie])]
    if entidades is not None:
        sub = sub[sub["codigo_entidad"].isin(entidades)]
    return (
        sub.groupby(["codigo_entidad", "yyyymm", "fecha"], as_index=False)["saldo"]
        .sum()
    )


def stock_me_sistema(serie: str, proforma: bool = True) -> pd.DataFrame:
    """Stock ME agregado al sistema (suma de todas las entidades)."""
    by_ent = stock_me(serie, proforma=proforma)
    return by_ent.groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()


def loan_to_deposit_me(proforma: bool = True) -> pd.DataFrame:
    """L/D ratio del sistema en moneda extranjera (residentes país)."""
    pres = stock_me_sistema("credito_spnf", proforma=proforma).rename(columns={"saldo": "prestamos"})
    dep = stock_me_sistema("deposito_residentes", proforma=proforma).rename(columns={"saldo": "depositos"})
    df = pres.merge(dep, on=["yyyymm", "fecha"], how="outer").sort_values("fecha")
    df["ratio"] = df["prestamos"] / df["depositos"]
    return df


def composicion_credito_me(proforma: bool = True) -> pd.DataFrame:
    """Desagrega el crédito ME al SPNF por subcategoría (hipotecarios, documentos, etc.)."""
    bal = load_balance_mensual(proforma=proforma)
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    sub = bal[bal["codigo_cuenta"].str.startswith("1357")].copy()
    sub_codes = {
        "135708": "Hipotecarios",
        "135715": "Documentos a sola firma",
        "135721": "Documentos comprados",
    }
    # Capitulos 1357xx — sub-rubros del crédito SPNF en ME.
    sub["subcategoria"] = sub["codigo_cuenta"].map(
        lambda c: sub_codes.get(c, "Otros préstamos SPNF ME")
    )
    return (
        sub.groupby(["yyyymm", "fecha", "subcategoria"], as_index=False)["saldo"]
        .sum()
    )


def share_credito_me(proforma: bool = True) -> pd.DataFrame:
    """% de los préstamos totales que están en moneda extranjera (residentes país)."""
    bal = load_balance_mensual(proforma=proforma)
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    pres_total = (
        bal[bal["codigo_cuenta"].str.startswith("13")]
        .groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
        .rename(columns={"saldo": "total"})
    )
    pres_me = (
        bal[bal["codigo_cuenta"].str.startswith("135")]
        .groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
        .rename(columns={"saldo": "me"})
    )
    df = pres_total.merge(pres_me, on=["yyyymm", "fecha"], how="left")
    df["share"] = df["me"] / df["total"]
    return df


def share_deposito_me(proforma: bool = True) -> pd.DataFrame:
    """% de los depósitos totales que están en moneda extranjera (residentes país)."""
    bal = load_balance_mensual(proforma=proforma)
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    dep_total = (
        bal[bal["codigo_cuenta"].str.startswith("31")]
        .groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
        .rename(columns={"saldo": "total"})
    )
    dep_me = (
        bal[bal["codigo_cuenta"].str.startswith("315")]
        .groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
        .rename(columns={"saldo": "me"})
    )
    df = dep_total.merge(dep_me, on=["yyyymm", "fecha"], how="left")
    df["share"] = df["me"] / df["total"]
    return df


def cobertura_encaje_me(proforma: bool = True) -> pd.DataFrame:
    """Encaje en BCRA en ME / Depósitos ME del SPNF (cobertura de pasivos)."""
    bal = load_balance_mensual(proforma=proforma)
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    enc = (
        bal[bal["codigo_cuenta"] == ENCAJE_BCRA_ME]
        .groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
        .rename(columns={"saldo": "encaje"})
    )
    dep = stock_me_sistema("deposito_residentes", proforma=proforma).rename(columns={"saldo": "depositos"})
    df = enc.merge(dep, on=["yyyymm", "fecha"], how="outer").sort_values("fecha")
    df["cobertura"] = df["encaje"] / df["depositos"]
    return df


def top_bancos_me(
    serie: str,
    yyyymm: int,
    top: int = 15,
    proforma: bool = True,
) -> pd.DataFrame:
    """Top entidades por stock ME a un mes dado."""
    sub = stock_me(serie, proforma=proforma)
    sub = sub[sub["yyyymm"] == yyyymm]
    return sub.sort_values("saldo", ascending=False).head(top).reset_index(drop=True)

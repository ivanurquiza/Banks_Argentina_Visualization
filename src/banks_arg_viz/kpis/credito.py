"""Crédito bancario en pesos — desagregación por sector y tipo.

Capítulo 13 del plan BCRA — PRÉSTAMOS — desagregado:

Sub-capítulos por moneda y residencia:
- 131xxx Pesos residentes país
- 132xxx Pesos residentes exterior
- 135xxx ME residentes país (canal regulado)
- 136xxx ME residentes exterior

Sub-capítulos por sector (segundo dígito de cada bloque):
- 1311 / 1351 Sector Público no Financiero
- 1314 / 1354 Sector Financiero (interbancarios domésticos)
- 1317 / 1357 SPNF residentes país (el grueso del crédito al sector privado)

El detalle por tipo de crédito (consumo, vivienda, comercial) se obtiene
mapeando los códigos de hoja a las categorías que define este módulo.
"""
from __future__ import annotations

import pandas as pd

from ..io import load_balance_mensual

# Capítulos por sector (en pesos)
PREFIX_PESOS_SP = "1311"        # Sector Público no Financiero
PREFIX_PESOS_SF = "1314"        # Interbancarios domésticos (Sector Financiero)
PREFIX_PESOS_SPNF = "1317"      # Sector Privado no Financiero (residentes país)
PREFIX_PESOS_PREVISIONES = "1319"  # Previsiones (regularizadora)
PREFIX_PESOS_NIIF = "1318"      # Intereses y diferencias de cotización

# Tipo de crédito en cap. 1317 (SPNF pesos). Códigos espejo en 1311 (SP) y otros.
# Mapeo basado en denominación BCRA.
TIPO_POR_CODIGO_1317 = {
    # Consumo
    "131731": ("Consumo", "Personales"),
    "131732": ("Consumo", "Personales monto reducido"),
    "131742": ("Consumo", "Tarjetas de crédito"),
    "131749": ("Consumo", "Personales UVA"),
    "131751": ("Consumo", "Otros UVA"),

    # Vivienda
    "131708": ("Vivienda", "Hipotecarios sobre vivienda"),
    "131745": ("Vivienda", "Hipotecarios UVA sobre vivienda"),
    "131711": ("Vivienda", "Otras garantías hipotecarias"),
    "131746": ("Vivienda", "Otras garantías hipotecarias UVA"),

    # Automotor / Prendarios
    "131713": ("Automotor / Prendario", "Prendarios sobre automotores"),
    "131714": ("Automotor / Prendario", "Otras garantías prendarias"),
    "131747": ("Automotor / Prendario", "Prendarios UVA sobre automotores"),
    "131748": ("Automotor / Prendario", "Otras garantías prendarias UVA"),

    # Comercial / Empresas
    "131709": ("Comercial / Empresas", "Adelantos cuenta corriente"),
    "131712": ("Comercial / Empresas", "Otros adelantos"),
    "131715": ("Comercial / Empresas", "Documentos a sola firma"),
    "131718": ("Comercial / Empresas", "Documentos descontados"),
    "131719": ("Comercial / Empresas", "Títulos de crédito descontados"),
    "131721": ("Comercial / Empresas", "Documentos comprados"),
    "131733": ("Comercial / Empresas", "Créditos documentarios"),
    "131736": ("Comercial / Empresas", "De títulos públicos"),
    "131740": ("Comercial / Empresas", "Microemprendedores"),
    "131741": ("Comercial / Empresas", "Otros préstamos"),
    "131752": ("Comercial / Empresas", "Documentos UVA"),
    "131753": ("Comercial / Empresas", "MiPyMEs sueldos"),
}

# Códigos espejo para sector público (1311) — ya con tipo
TIPO_POR_CODIGO_1311 = {
    "131109": ("Adelantos cuenta corriente",),
    "131112": ("Otros adelantos",),
    "131113": ("Prendarios sobre automotores",),
    "131114": ("Otras garantías prendarias",),
    "131115": ("Documentos a sola firma",),
    "131118": ("Documentos descontados",),
    "131121": ("Documentos comprados",),
    "131140": ("Garantizados Decreto 1387/01",),
    "131141": ("Otros préstamos",),
    "131151": ("Tarjetas de crédito",),
}


def _bal(proforma: bool = True) -> pd.DataFrame:
    bal = load_balance_mensual(proforma=proforma)
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    return bal


def stock_credito_pesos_sector(
    sector: str = "spnf",
    proforma: bool = True,
    by_entity: bool = False,
) -> pd.DataFrame:
    """Stock total de créditos en pesos por sector.

    sector: "sp" (1311), "sf" (1314), "spnf" (1317), "total" (131x).
    """
    bal = _bal(proforma)
    if sector == "sp":
        prefixes = (PREFIX_PESOS_SP,)
    elif sector == "sf":
        prefixes = (PREFIX_PESOS_SF,)
    elif sector == "spnf":
        prefixes = (PREFIX_PESOS_SPNF,)
    elif sector == "total":
        prefixes = ("1311", "1314", "1317")
    else:
        raise ValueError(f"sector desconocido: {sector}")

    sub = bal[bal["codigo_cuenta"].str.startswith(prefixes)]
    keys = ["codigo_entidad", "yyyymm", "fecha"] if by_entity else ["yyyymm", "fecha"]
    return sub.groupby(keys, as_index=False)["saldo"].sum()


def composicion_credito_spnf(
    proforma: bool = True,
    by_entity: bool = False,
) -> pd.DataFrame:
    """Crédito SPNF en pesos desagregado por tipo (Consumo / Vivienda / Auto / Comercial).

    Excluye intereses/diferencias y previsiones (que son regularizadoras del stock).
    """
    bal = _bal(proforma)
    sub = bal[bal["codigo_cuenta"].str.startswith(PREFIX_PESOS_SPNF)].copy()

    def _categoria(c):
        if c in TIPO_POR_CODIGO_1317:
            return TIPO_POR_CODIGO_1317[c][0]
        # Códigos 13179x son intereses / regularizadoras
        if c.startswith("13179"):
            return "Intereses / regularizadoras"
        return "Otros"

    def _subtipo(c):
        if c in TIPO_POR_CODIGO_1317:
            return TIPO_POR_CODIGO_1317[c][1]
        return c

    sub["categoria"] = sub["codigo_cuenta"].apply(_categoria)
    sub["subtipo"] = sub["codigo_cuenta"].apply(_subtipo)

    keys = ["codigo_entidad"] if by_entity else []
    keys += ["yyyymm", "fecha", "categoria"]
    return sub.groupby(keys, as_index=False)["saldo"].sum()


def composicion_credito_spnf_detalle(proforma: bool = True) -> pd.DataFrame:
    """Stock por subtipo (más detallado que composicion_credito_spnf)."""
    bal = _bal(proforma)
    sub = bal[bal["codigo_cuenta"].str.startswith(PREFIX_PESOS_SPNF)].copy()

    def _info(c):
        if c in TIPO_POR_CODIGO_1317:
            return TIPO_POR_CODIGO_1317[c]
        return ("Otros", c)

    sub["categoria"] = sub["codigo_cuenta"].apply(lambda c: _info(c)[0])
    sub["subtipo"] = sub["codigo_cuenta"].apply(lambda c: _info(c)[1])
    return sub.groupby(["yyyymm", "fecha", "categoria", "subtipo"], as_index=False)["saldo"].sum()


def loan_to_deposit_pesos(proforma: bool = True) -> pd.DataFrame:
    """L/D ratio en pesos del sistema.

    Préstamos pesos / Depósitos pesos (residentes país + exterior).
    """
    bal = _bal(proforma)
    pres = (
        bal[bal["codigo_cuenta"].str.startswith(("131", "132"))]
        .groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
        .rename(columns={"saldo": "prestamos"})
    )
    dep = (
        bal[bal["codigo_cuenta"].str.startswith(("311", "312"))]
        .groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
        .rename(columns={"saldo": "depositos"})
    )
    df = pres.merge(dep, on=["yyyymm", "fecha"], how="outer").sort_values("fecha")
    df["ratio"] = df["prestamos"] / df["depositos"]
    return df


def share_uva(proforma: bool = True) -> pd.DataFrame:
    """% del crédito SPNF en pesos que está indexado por UVA."""
    bal = _bal(proforma)
    sub = bal[bal["codigo_cuenta"].str.startswith(PREFIX_PESOS_SPNF)]

    UVA_CODES = ["131745", "131746", "131747", "131748", "131749", "131751", "131752"]
    total = (
        sub.groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
        .rename(columns={"saldo": "total"})
    )
    uva = (
        sub[sub["codigo_cuenta"].isin(UVA_CODES)]
        .groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()
        .rename(columns={"saldo": "uva"})
    )
    df = total.merge(uva, on=["yyyymm", "fecha"], how="left").fillna({"uva": 0})
    df["share"] = df["uva"] / df["total"]
    return df


def previsiones_spnf_pesos(proforma: bool = True) -> pd.DataFrame:
    """Stock de previsiones por riesgo de incobrabilidad — SPNF pesos."""
    bal = _bal(proforma)
    sub = bal[bal["codigo_cuenta"].str.startswith(PREFIX_PESOS_PREVISIONES)]
    return sub.groupby(["yyyymm", "fecha"], as_index=False)["saldo"].sum()


def cobertura_previsiones_spnf(proforma: bool = True) -> pd.DataFrame:
    """Previsiones SPNF / Crédito SPNF — proxy de cobertura ante incobrabilidad."""
    pres = stock_credito_pesos_sector(sector="spnf", proforma=proforma).rename(columns={"saldo": "credito"})
    prev = previsiones_spnf_pesos(proforma=proforma).rename(columns={"saldo": "previsiones"})
    # Las previsiones son regularizadoras — su saldo es negativo. Lo invertimos.
    prev["previsiones"] = prev["previsiones"].abs()
    df = pres.merge(prev, on=["yyyymm", "fecha"], how="left").fillna({"previsiones": 0})
    df["cobertura"] = df["previsiones"] / df["credito"]
    return df


def top_bancos_credito_pesos(
    yyyymm: int,
    proforma: bool = True,
    sector: str = "spnf",
    top: int = 15,
) -> pd.DataFrame:
    """Top bancos por stock de crédito pesos al sector."""
    by_ent = stock_credito_pesos_sector(sector=sector, proforma=proforma, by_entity=True)
    by_ent = by_ent[by_ent["yyyymm"] == yyyymm]
    return by_ent.sort_values("saldo", ascending=False).head(top).reset_index(drop=True)

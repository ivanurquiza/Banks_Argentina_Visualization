"""Cartera de títulos: clasificación por emisor, instrumento, moneda y medición.

Contexto. El capítulo 12 del plan de cuentas BCRA — TÍTULOS PÚBLICOS Y PRIVADOS —
agrupa todas las posiciones en valores negociables del activo bancario. Para análisis
de riesgo soberano, exposición a BCRA y clasificación contable IFRS 9, se requiere
una desagregación fina que no se obtiene del prefijo de código solamente.

Este módulo clasifica cada cuenta de 12xxxx según:

1. **Moneda**: ARS (121xxx), USD país (125xxx), USD exterior (126xxx).
2. **Emisor**:
   - Tesoro: títulos del gobierno nacional/provincial.
   - BCRA: Letras (LELIQ histórico, LELIQs), Notas, NoCom (Notas de Compensación),
           Letras de Liquidez.
   - LeFi: Letras Fiscales de Liquidez — emite Tesoro pero usadas por bancos como
           sustituto post-2024 de LELIQs. Las clasificamos aparte por relevancia.
   - Privado: ON, acciones, FCI, certificados, etc.
3. **Medición** (IFRS 9):
   - FVTPL: Fair Value Through Profit & Loss (mark-to-market en resultados).
   - AC: Amortized Cost (held-to-maturity, sin volatilidad MtM).
   - FVOCI: Fair Value Through OCI (mark-to-market en patrimonio).

La clasificación se basa en (a) keywords de la denominación y (b) sub-rangos de
código cuando la denominación está truncada en el dim. Si una cuenta cae en
'sin_clasificar', conviene auditar manualmente y extender los patrones acá.
"""
from __future__ import annotations

from typing import Literal

import pandas as pd

from ..io import load_balance_mensual, load_dim_cuentas


Emisor = Literal["Tesoro", "BCRA", "LeFi", "Privado", "Sin clasificar"]
Medicion = Literal["FVTPL", "AC", "FVOCI", "Sin clasificar"]
Moneda = Literal["ARS", "USD país", "USD exterior"]


# Mapa de medición por sub-código (BCRA convention).
# La denominación está truncada en muchas cuentas — usamos el sub-código
# como fuente de verdad cuando los keywords no alcanzan.
MEDICION_BY_LAST3 = {
    # FVTPL — valor razonable con cambios en resultados (P&L MtM)
    "003": "FVTPL", "017": "FVTPL", "018": "FVTPL", "019": "FVTPL",
    "020": "FVTPL", "021": "FVTPL", "022": "FVTPL", "023": "FVTPL",
    "024": "FVTPL", "027": "FVTPL", "031": "FVTPL", "036": "FVTPL",
    "039": "FVTPL", "041": "FVTPL", "042": "FVTPL", "056": "FVTPL",
    "060": "FVTPL", "092": "FVTPL", "010": "FVTPL", "011": "FVTPL",
    # AC — costo amortizado (held-to-maturity)
    "016": "AC", "026": "AC", "029": "AC", "057": "AC",
    "059": "AC", "061": "AC", "091": "AC",
    # FVOCI — valor razonable con cambios en patrimonio (OCI)
    "040": "FVOCI", "043": "FVOCI", "044": "FVOCI", "045": "FVOCI",
    "046": "FVOCI", "047": "FVOCI", "048": "FVOCI", "049": "FVOCI",
    "050": "FVOCI", "051": "FVOCI", "052": "FVOCI", "053": "FVOCI",
    "054": "FVOCI", "055": "FVOCI", "058": "FVOCI", "062": "FVOCI",
    "093": "FVOCI", "014": "FVOCI", "015": "FVOCI",
}


# ── Clasificación por keywords de denominación + sub-rango de código ─────
def _clasificar_emisor(codigo: str, denom: str) -> str:
    d = denom.upper().strip()
    last3 = codigo[-3:]

    # Cabeceras / regularizadoras / NIIF
    if last3 == "000":
        return "Cabecera"
    if last3 in {"100", "135", "137", "600", "610"}:
        return "Regularizadora / NIIF"
    if "PREVISIÓN" in d or "PREVISION" in d:
        return "Regularizadora / NIIF"
    if "REGULARIZADORAS" in d:
        return "Regularizadora / NIIF"
    if "PRORRAT" in d or "NIIF" in d:
        return "Regularizadora / NIIF"

    # LeFi: Letras Fiscales de Liquidez (post-2024, emite Tesoro)
    if "FISCALES" in d and "LIQUIDEZ" in d:
        return "LeFi (Tesoro)"
    if "LETRAS FISCALES" in d:
        return "LeFi (Tesoro)"

    # BCRA: cualquier mención al banco central
    if "BCRA" in d or "B.C.R.A." in d:
        if "LIQUIDEZ" in d:
            return "BCRA - Letras de Liquidez"
        if "COMPENSACI" in d:
            return "BCRA - NoCom"
        if "LETRAS" in d:
            return "BCRA - Letras"
        if "NOTAS" in d:
            return "BCRA - Notas"
        return "BCRA - Otros"

    # Tesoro / Sector Público
    if "TÍTULO PÚB" in d or "TITULO PUB" in d or "TÍTULOS PÚB" in d or "TITULOS PUB" in d:
        return "Tesoro / Sector Público"
    if d.startswith("TITULOS PUBLICOS") or d.startswith("Titulos publicos".upper()):
        return "Tesoro / Sector Público"

    # Privados (con sub-tipo)
    if "OBLIGACIONES NEG" in d:
        return "Privado - ON"
    if "OBLIGACIONES SUB" in d:
        return "Privado - ON Subordinada"
    if "ACCIONES" in d:
        return "Privado - Acciones"
    if "FONDOS COMUNES" in d or "FCI" in d:
        return "Privado - FCI"
    if "CERTIFICADO" in d:
        return "Privado - Certificados"
    if "EN EMPRESAS DE S" in d:
        return "Privado - Empresas de Servicios"
    if "TÍTULOS DE DEUDA" in d or "TITULOS DE DEUDA" in d:
        return "Privado - Títulos de Deuda"
    if "TÍTULO PRIV" in d or "TITULO PRIV" in d:
        return "Privado"
    if "TÍTULOS PRIV" in d or "TITULOS PRIV" in d:
        return "Privado"
    return "Sin clasificar"


def _clasificar_medicion(codigo: str, denom: str) -> str:
    d = denom.upper()
    last3 = codigo[-3:]

    # Cabeceras y regularizadoras: no aplica medición
    if last3 in {"000", "100", "135", "137", "600", "610"}:
        return "N/A"
    if "PREVISIÓN" in d or "PREVISION" in d or "REGULARIZADORA" in d or "PRORRAT" in d:
        return "N/A"

    # Keywords explícitos en denominación
    if "CAMBIOS EN RESULTADOS" in d:
        return "FVTPL"
    if "CAMBIOS EN PATRIMONIO" in d or "CAMBIOS EN ORI" in d or " ORI" in d:
        return "FVOCI"
    if "COSTO AMORTIZADO" in d or "MEDICIÓN A COSTO" in d or "MEDICION A COSTO" in d:
        return "AC"

    # Fallback por sub-código (BCRA convention)
    if last3 in MEDICION_BY_LAST3:
        return MEDICION_BY_LAST3[last3]

    # Último recurso: si dice "VALOR RAZONABLE" sin más, asumir FVTPL
    if "VALOR RAZONABLE" in d or "MEDICIÓN A VALOR" in d:
        return "FVTPL"
    return "Sin clasificar"


def _moneda_de_codigo(codigo: str) -> str:
    if codigo.startswith("121"):
        return "ARS"
    if codigo.startswith("125"):
        return "USD país"
    if codigo.startswith("126"):
        return "USD exterior"
    return "Otra"


# ── Tabla maestra de cuentas de títulos ──────────────────────────────────
def catalogo_titulos() -> pd.DataFrame:
    """Devuelve el catálogo completo de cuentas 12xxxx clasificadas.

    Columnas: codigo_cuenta, denominacion, moneda, emisor, medicion, es_regularizadora.
    Excluye cuentas con fecha_baja (discontinuadas).
    """
    dc = load_dim_cuentas().copy()
    dc["codigo_cuenta"] = dc["codigo_cuenta"].astype(str)
    titulos = dc[
        dc["codigo_cuenta"].str.startswith("12")
        & dc["fecha_baja"].isna()
    ].copy()
    titulos["moneda"] = titulos["codigo_cuenta"].apply(_moneda_de_codigo)
    titulos["emisor"] = titulos.apply(
        lambda r: _clasificar_emisor(r["codigo_cuenta"], r["denominacion"]), axis=1
    )
    titulos["medicion"] = titulos.apply(
        lambda r: _clasificar_medicion(r["codigo_cuenta"], r["denominacion"]), axis=1
    )
    return titulos[["codigo_cuenta", "denominacion", "moneda", "emisor", "medicion", "es_regularizadora"]]


# ── Agregaciones del sistema ─────────────────────────────────────────────
def _balance_titulos(proforma: bool = True) -> pd.DataFrame:
    cat = catalogo_titulos()
    bal = load_balance_mensual(proforma=proforma)
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    panel = bal.merge(cat, on="codigo_cuenta", how="inner")
    return panel


def stock_titulos_sistema(
    proforma: bool = True,
    by: tuple[str, ...] = ("emisor", "moneda"),
) -> pd.DataFrame:
    """Stock agregado del sistema desagregado por las dimensiones pedidas."""
    panel = _balance_titulos(proforma=proforma)
    return (
        panel.groupby(["yyyymm", "fecha", *by], as_index=False)["saldo"].sum()
    )


def stock_titulos_entidad(
    codigo_entidad: str,
    proforma: bool = True,
    by: tuple[str, ...] = ("emisor", "moneda"),
) -> pd.DataFrame:
    panel = _balance_titulos(proforma=proforma)
    panel = panel[panel["codigo_entidad"] == codigo_entidad]
    return panel.groupby(["yyyymm", "fecha", *by], as_index=False)["saldo"].sum()


def exposicion_por_banco(yyyymm: int, proforma: bool = True) -> pd.DataFrame:
    """Por cada entidad: total títulos, %sov, %BCRA, %privado, %ME, %FVTPL.

    "Sov" = Tesoro + LeFi (deuda soberana directa o indirecta).
    %FVTPL = exposición a mark-to-market que pega en P&L con stress.
    """
    panel = _balance_titulos(proforma=proforma)
    panel = panel[panel["yyyymm"] == yyyymm]

    # Total cartera de títulos por banco
    total = panel.groupby("codigo_entidad", as_index=False)["saldo"].sum().rename(columns={"saldo": "total_titulos"})

    def _share(filtro):
        sub = panel[filtro].groupby("codigo_entidad", as_index=False)["saldo"].sum()
        return sub.rename(columns={"saldo": "v"}).set_index("codigo_entidad")["v"]

    sov_mask = panel["emisor"].str.startswith("Tesoro") | panel["emisor"].str.startswith("LeFi")
    bcra_mask = panel["emisor"].str.startswith("BCRA")
    priv_mask = panel["emisor"].str.startswith("Privado")
    me_mask = panel["moneda"].isin(["USD país", "USD exterior"])
    fvtpl_mask = panel["medicion"] == "FVTPL"

    sov = _share(sov_mask)
    bcra = _share(bcra_mask)
    priv = _share(priv_mask)
    me = _share(me_mask)
    fvtpl = _share(fvtpl_mask)

    out = total.copy().set_index("codigo_entidad")
    out["sov"] = sov.reindex(out.index).fillna(0)
    out["bcra"] = bcra.reindex(out.index).fillna(0)
    out["privado"] = priv.reindex(out.index).fillna(0)
    out["me"] = me.reindex(out.index).fillna(0)
    out["fvtpl"] = fvtpl.reindex(out.index).fillna(0)
    out["share_sov"] = out["sov"] / out["total_titulos"]
    out["share_bcra"] = out["bcra"] / out["total_titulos"]
    out["share_privado"] = out["privado"] / out["total_titulos"]
    out["share_me"] = out["me"] / out["total_titulos"]
    out["share_fvtpl"] = out["fvtpl"] / out["total_titulos"]
    return out.reset_index()


def sov_exposure_pct_activo(yyyymm: int, proforma: bool = True) -> pd.DataFrame:
    """Exposición soberana = (Tesoro + LeFi) / Activo total, por banco.

    Indicador clave de riesgo de default soberano para cada banco.
    """
    panel = _balance_titulos(proforma=proforma)
    panel_ult = panel[panel["yyyymm"] == yyyymm]
    sov_mask = panel_ult["emisor"].str.startswith("Tesoro") | panel_ult["emisor"].str.startswith("LeFi")
    sov_b = panel_ult[sov_mask].groupby("codigo_entidad", as_index=False)["saldo"].sum().rename(columns={"saldo": "sov"})

    bal = load_balance_mensual(proforma=proforma)
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    activo_b = (
        bal[(bal["yyyymm"] == yyyymm) & bal["codigo_cuenta"].str.startswith(("1", "2"))]
        .groupby("codigo_entidad", as_index=False)["saldo"].sum().rename(columns={"saldo": "activo"})
    )
    out = activo_b.merge(sov_b, on="codigo_entidad", how="left")
    out["sov"] = out["sov"].fillna(0)
    out["share_sov_activo"] = out["sov"] / out["activo"]
    return out

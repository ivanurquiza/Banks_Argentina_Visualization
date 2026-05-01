"""Encajes y liquidez bancaria.

El capítulo 11 del plan BCRA — EFECTIVO Y DEPÓSITOS EN BANCOS — contiene
todos los activos líquidos del banco, incluyendo el encaje obligatorio
integrado en cuenta corriente del BCRA.

Sub-capítulos:
- 111xxx Pesos en el país
- 112xxx Pesos en el exterior
- 115xxx Moneda extranjera en el país (incluye oro)
- 116xxx Moneda extranjera en el exterior

Cuentas clave de encaje (integración del Efectivo Mínimo):
- 111015 BCRA Cuenta Corriente en pesos (encaje principal)
- 111017 Otras ctas. ctes. computables p/integración efvo. mín. ($)
- 115015 BCRA Cuenta Corriente en ME (encaje principal ME)
- 115017 Otras ctas. ctes. computables p/integración efvo. mín. (ME)

El régimen vigente exige integración 100% sobre depósitos en USD por
Comunicación A 3498 (con sus modificatorias). Para pesos el coeficiente
varía según tipo de depósito, vigencia y normativa específica.

Sin acceso al coeficiente regulatorio mes a mes (publicado en boletines BCRA),
no podemos separar 'obligatorio' de 'voluntario' a nivel de exigencia.
Lo que sí podemos calcular:

1. **Tasa efectiva de integración** = stock de encaje integrado / stock de depósitos.
   Si está debajo del 100% (USD) o del coeficiente vigente ($), hay defecto.
2. **Composición** del encaje: cuánto es caja física, cuánto BCRA, cuánto otras
   computables.
3. **Comparación entre bancos** para identificar outliers.
"""
from __future__ import annotations

import pandas as pd

from ..io import load_balance_mensual

# Cuentas exactas que computan para integración del Efectivo Mínimo
ENCAJE_BCRA_PESOS = "111015"   # BCRA cuenta corriente $
ENCAJE_BCRA_ME = "115015"      # BCRA cuenta corriente ME
COMPUTABLES_PESOS = "111017"   # otras ctas. ctes. computables $
COMPUTABLES_ME = "115017"      # otras ctas. ctes. computables ME

# Cuentas de "caja" (efectivo físico, no BCRA)
CAJA_PESOS = ("111001", "111007", "111009")    # caja, transp. caudales, tránsito
CAJA_ME = ("115001", "115005", "115009")        # caja, transp. caudales, tránsito

# Cuentas no computables (otras a la vista pero fuera del cómputo de encajes)
NO_COMPUT_PESOS = "111021"
NO_COMPUT_ME = "115018"

# Corresponsalía (cuentas en otros bancos)
CORRESP_PESOS = ("111019", "112019")
CORRESP_ME = ("115019", "116019")


def _bal(proforma: bool = True) -> pd.DataFrame:
    bal = load_balance_mensual(proforma=proforma)
    bal["codigo_cuenta"] = bal["codigo_cuenta"].astype(str)
    return bal


def liquidez_componentes(
    moneda: str = "ars",
    proforma: bool = True,
    by_entity: bool = False,
) -> pd.DataFrame:
    """Stock de cada componente de liquidez por mes (y opcionalmente por entidad).

    moneda='ars' usa cuentas en pesos (111xxx, 112xxx);
    moneda='me'  usa cuentas en moneda extranjera (115xxx, 116xxx).
    """
    bal = _bal(proforma)
    if moneda == "ars":
        caja_codes = list(CAJA_PESOS)
        bcra_code = ENCAJE_BCRA_PESOS
        comput_code = COMPUTABLES_PESOS
        nocomput_code = NO_COMPUT_PESOS
        corresp_codes = list(CORRESP_PESOS)
    elif moneda == "me":
        caja_codes = list(CAJA_ME)
        bcra_code = ENCAJE_BCRA_ME
        comput_code = COMPUTABLES_ME
        nocomput_code = NO_COMPUT_ME
        corresp_codes = list(CORRESP_ME)
    else:
        raise ValueError(f"moneda debe ser 'ars' o 'me', no {moneda!r}")

    def _sum_codes(codes: list[str], serie: str) -> pd.DataFrame:
        sub = bal[bal["codigo_cuenta"].isin(codes if isinstance(codes, list) else [codes])].copy()
        keys = ["codigo_entidad", "yyyymm", "fecha"] if by_entity else ["yyyymm", "fecha"]
        out = sub.groupby(keys, as_index=False)["saldo"].sum()
        out["componente"] = serie
        return out

    parts = pd.concat([
        _sum_codes(caja_codes, "Caja"),
        _sum_codes([bcra_code], "BCRA cta. cte. (encaje)"),
        _sum_codes([comput_code], "Otras computables"),
        _sum_codes([nocomput_code], "No computables"),
        _sum_codes(corresp_codes, "Corresponsalía"),
    ])
    return parts


def deposito_total(
    moneda: str = "ars",
    proforma: bool = True,
    by_entity: bool = False,
) -> pd.DataFrame:
    """Stock de depósitos del Sector Privado residentes país.

    moneda='ars' → cuentas 3117xx (SPNF residentes país en $)
    moneda='me'  → cuentas 3157xx (SPNF residentes país en ME)

    Excluimos:
    - 3151xx / 3111-3115xx: Sector Público y Sector Financiero (interbancarios)
    - 3118x / 3158x: intereses devengados (no son depósitos en sentido estricto)
    - 3119x / 3159x: previsiones (regularizadoras)
    - 313xxx / 314xxx: depósitos de títulos públicos en custodia (no encajables)

    Esto da el universo principal sobre el que BCRA aplica el coeficiente
    de Efectivo Mínimo en pesos / ME.
    """
    bal = _bal(proforma)
    if moneda == "ars":
        prefix = "3117"
    elif moneda == "me":
        prefix = "3157"
    else:
        raise ValueError(f"moneda debe ser 'ars' o 'me'")
    sub = bal[bal["codigo_cuenta"].str.startswith(prefix)].copy()
    # Excluir intereses devengados (3117 8x) y previsiones (3117 9x)
    last_two = sub["codigo_cuenta"].str[4:6]
    sub = sub[~last_two.str.startswith(("8", "9"))]
    keys = ["codigo_entidad", "yyyymm", "fecha"] if by_entity else ["yyyymm", "fecha"]
    return sub.groupby(keys, as_index=False)["saldo"].sum()


def tasa_integracion_efectiva(
    moneda: str = "ars",
    proforma: bool = True,
    by_entity: bool = False,
) -> pd.DataFrame:
    """Tasa efectiva de integración = encaje integrado / depósitos.

    Encaje integrado = Caja + BCRA cta. cte. + Otras computables (no incluye
    No computables ni Corresponsalía exterior).

    Si está debajo del coeficiente regulatorio del período → hay defecto.
    """
    comp = liquidez_componentes(moneda=moneda, proforma=proforma, by_entity=by_entity)
    integrables = comp[comp["componente"].isin(
        ["Caja", "BCRA cta. cte. (encaje)", "Otras computables"]
    )]
    keys = ["codigo_entidad", "yyyymm", "fecha"] if by_entity else ["yyyymm", "fecha"]
    encaje = integrables.groupby(keys, as_index=False)["saldo"].sum().rename(columns={"saldo": "encaje"})

    dep = deposito_total(moneda=moneda, proforma=proforma, by_entity=by_entity).rename(columns={"saldo": "depositos"})

    out = encaje.merge(dep, on=keys, how="outer").fillna(0)
    out["tasa"] = out["encaje"] / out["depositos"].where(out["depositos"] > 0)
    return out

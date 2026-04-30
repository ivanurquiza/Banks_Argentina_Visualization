"""Demanda y Mora — Estado de Situación de Deudores (panel_esd).

El BCRA publica trimestralmente el Estado de Situación de Deudores (ESD)
con la cartera bancaria abierta por situación crediticia (1 a 5+) y por
tipo de cartera (Comercial, Consumo o Vivienda, Comercial Asimilable a Consumo).

**Estructura del panel_esd**:

- Las líneas con formato_valor='N' son montos en pesos (typically miles de pesos).
- Las líneas con formato_valor='P' son porcentajes que aplican sobre el total.
- Por ejemplo, "TF.Sit.1: En situación normal (%)" trae el % de cartera total
  en situación 1. Para obtener el monto: total_pesos * sit1_pct / 100.

**Definiciones de irregularidad**:

- **Irregularidad amplia (Sit. 2+)**: 100% - Sit. 1%.
  Incluye créditos en seguimiento especial / riesgo bajo.
  Refleja deterioro temprano del crédito.
- **Mora estricta (Sit. 3+)**: Sit. 3% + Sit. 4% + Sit. 5% + Sit. 6%.
  Definición utilizada por el BCRA en publicaciones oficiales.
  Solo cuenta créditos con problemas / alto riesgo / irrecuperables.

Para agregaciones a nivel sistema usamos promedios ponderados por el
total (pesos) de cada entidad — no promedios simples.
"""
from __future__ import annotations

import pandas as pd

from ..io import load_esd

# ── Códigos clave ───────────────────────────────────────────────────────
# Total de financiaciones y garantías (en pesos)
TOTAL_PORTFOLIO = "500110001000"

# Porcentaje del total en cada situación
TOTAL_SIT1 = "500110001010"   # Normal
TOTAL_SIT2 = "500110001020"   # Seguimiento especial / Riesgo bajo
TOTAL_SIT3 = "500110001030"   # Con problemas / Riesgo medio
TOTAL_SIT4 = "500110001040"   # Alto riesgo insolvencia / Riesgo alto
TOTAL_SIT5 = "500110001050"   # Irrecuperable
TOTAL_SIT6 = "500110001060"   # Irrecuperable disp. técnica

# Por tipo de cartera: Comercial, Consumo/Vivienda, Comercial Asimilable Consumo
COM_TOTAL = "500110101000"
COM_SIT1 = "500110101010"
CON_TOTAL = "500110201000"
CON_SIT1 = "500110201010"
CAC_TOTAL = "500110301000"
CAC_SIT1 = "500110301010"

# Previsiones constituidas (en pesos)
PREVISIONES = "500130003000"


# ── Helper: extraer total en pesos y % por situación, por entidad y mes
def _esd_pivoted() -> pd.DataFrame:
    """Devuelve un DataFrame entidad × mes con columnas:
    total ($), sit1_pct, sit2_pct, sit3_pct, sit4_pct, sit5_pct, sit6_pct
    para el total de la cartera.
    """
    df = load_esd().copy()
    df["codigo_linea"] = df["codigo_linea"].astype(str)

    cols_map = {
        TOTAL_PORTFOLIO: "total",
        TOTAL_SIT1: "sit1_pct",
        TOTAL_SIT2: "sit2_pct",
        TOTAL_SIT3: "sit3_pct",
        TOTAL_SIT4: "sit4_pct",
        TOTAL_SIT5: "sit5_pct",
        TOTAL_SIT6: "sit6_pct",
    }
    sub = df[df["codigo_linea"].isin(cols_map.keys())].copy()
    sub["serie"] = sub["codigo_linea"].map(cols_map)
    pivot = sub.pivot_table(
        index=["codigo_entidad", "nombre_entidad", "yyyymm"],
        columns="serie",
        values="valor",
        aggfunc="first",
    ).reset_index()
    return pivot


def _agregar_sistema(pivot: pd.DataFrame) -> pd.DataFrame:
    """Agrega a nivel sistema con promedio ponderado por total."""
    # Por mes, suma totales en pesos
    out = pivot.groupby("yyyymm", as_index=False).apply(
        lambda g: pd.Series({
            "total": g["total"].sum(),
            # Pondera cada % por el total $ de su entidad
            "sit1_pct": (g["sit1_pct"] * g["total"]).sum() / g["total"].sum() if g["total"].sum() > 0 else None,
            "sit2_pct": (g["sit2_pct"] * g["total"]).sum() / g["total"].sum() if g["total"].sum() > 0 else None,
            "sit3_pct": (g["sit3_pct"] * g["total"]).sum() / g["total"].sum() if g["total"].sum() > 0 else None,
            "sit4_pct": (g["sit4_pct"] * g["total"]).sum() / g["total"].sum() if g["total"].sum() > 0 else None,
            "sit5_pct": (g["sit5_pct"] * g["total"]).sum() / g["total"].sum() if g["total"].sum() > 0 else None,
            "sit6_pct": (g["sit6_pct"] * g["total"] if "sit6_pct" in g.columns else 0).sum() / g["total"].sum()
                        if g["total"].sum() > 0 else None,
        }),
        include_groups=False,
    ).reset_index(drop=True)
    out["fecha"] = pd.to_datetime(out["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
    return out.sort_values("yyyymm")


def irregularidad_sistema() -> pd.DataFrame:
    """Tasa de irregularidad sistémica con ambas definiciones.

    Devuelve columnas:
        yyyymm, fecha, total ($),
        amplia (Sit.2+, en %), estricta (Sit.3+, en %),
        sit1_pct, sit2_pct, ..., sit6_pct.
    """
    pivot = _esd_pivoted()
    sis = _agregar_sistema(pivot)
    sis["amplia"] = (
        sis["sit2_pct"].fillna(0)
        + sis["sit3_pct"].fillna(0)
        + sis["sit4_pct"].fillna(0)
        + sis["sit5_pct"].fillna(0)
        + sis["sit6_pct"].fillna(0)
    )
    sis["estricta"] = (
        sis["sit3_pct"].fillna(0)
        + sis["sit4_pct"].fillna(0)
        + sis["sit5_pct"].fillna(0)
        + sis["sit6_pct"].fillna(0)
    )
    return sis


def composicion_situaciones_sistema() -> pd.DataFrame:
    """Stock por situación al sistema (en pesos), descomponiendo el total.

    Devuelve long format: yyyymm × situación × stock.
    """
    pivot = _esd_pivoted()
    sis = _agregar_sistema(pivot)
    rows = []
    SITS = [
        ("Sit. 1 — Normal", "sit1_pct"),
        ("Sit. 2 — Seguim. especial", "sit2_pct"),
        ("Sit. 3 — Con problemas", "sit3_pct"),
        ("Sit. 4 — Alto riesgo insolvencia", "sit4_pct"),
        ("Sit. 5 — Irrecuperable", "sit5_pct"),
    ]
    for _, r in sis.iterrows():
        for label, col in SITS:
            stock = (r["total"] or 0) * (r[col] or 0) / 100
            rows.append({
                "yyyymm": r["yyyymm"], "fecha": r["fecha"],
                "situacion": label, "stock": stock,
            })
    return pd.DataFrame(rows)


def irregularidad_por_tipo_cartera() -> pd.DataFrame:
    """Irregularidad amplia (Sit. 2+) por tipo de cartera, sistema.

    Devuelve: yyyymm × cartera × ratio (en %).
    """
    df = load_esd().copy()
    df["codigo_linea"] = df["codigo_linea"].astype(str)

    def _calc(prefix_total: str, prefix_sit1: str, label: str) -> pd.DataFrame:
        # Pondera con el total de cada entidad (en pesos)
        tot = df[df["codigo_linea"] == prefix_total][["codigo_entidad", "yyyymm", "valor"]].rename(columns={"valor": "tot"})
        s1 = df[df["codigo_linea"] == prefix_sit1][["codigo_entidad", "yyyymm", "valor"]].rename(columns={"valor": "s1_pct"})
        m = tot.merge(s1, on=["codigo_entidad", "yyyymm"], how="inner")
        # Sistema: total ponderado de % en sit.1
        agg = m.groupby("yyyymm", as_index=False).apply(
            lambda g: pd.Series({
                "tot": g["tot"].sum(),
                "s1_w": (g["s1_pct"] * g["tot"]).sum() / g["tot"].sum() if g["tot"].sum() > 0 else None,
            }),
            include_groups=False,
        ).reset_index(drop=True)
        agg["amplia"] = 100 - agg["s1_w"]
        agg["cartera"] = label
        return agg

    com = _calc(COM_TOTAL, COM_SIT1, "Comercial")
    con = _calc(CON_TOTAL, CON_SIT1, "Consumo / Vivienda")
    cac = _calc(CAC_TOTAL, CAC_SIT1, "Comercial asimilable a consumo")

    out = pd.concat([com, con, cac])
    out["fecha"] = pd.to_datetime(out["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
    return out.sort_values(["cartera", "yyyymm"]).reset_index(drop=True)


def previsiones_sobre_cartera() -> pd.DataFrame:
    """Previsiones constituidas / Cartera total.

    Indicador de cobertura: cuánto está provisionado contra la cartera.
    """
    df = load_esd().copy()
    df["codigo_linea"] = df["codigo_linea"].astype(str)
    prev = (
        df[df["codigo_linea"] == PREVISIONES]
        .groupby("yyyymm", as_index=False)["valor"].sum()
        .rename(columns={"valor": "previsiones"})
    )
    pivot = _esd_pivoted()
    sis = _agregar_sistema(pivot)
    out = prev.merge(sis[["yyyymm", "total"]], on="yyyymm", how="left")
    # Previsiones absolutas (es regularizadora — saldo negativo, abs)
    out["previsiones_abs"] = out["previsiones"].abs()
    out["cobertura_cartera"] = out["previsiones_abs"] / out["total"].where(out["total"] > 0)
    out["fecha"] = pd.to_datetime(out["yyyymm"].astype(str) + "01", format="%Y%m%d") + pd.offsets.MonthEnd(0)
    return out


def irregularidad_por_banco(yyyymm: int) -> pd.DataFrame:
    """Tasas de irregularidad (amplia y estricta) por banco a un mes dado.

    Excluye códigos de agrupamiento (BANCOS, SISTEMA FINANCIERO, etc.).
    """
    pivot = _esd_pivoted()
    sub = pivot[pivot["yyyymm"] == yyyymm].copy()
    # Excluir agrupamientos: códigos AA*, o nombres en mayúsculas que no son bancos individuales
    sub = sub[~sub["codigo_entidad"].astype(str).str.startswith("AA")]
    sub = sub[~sub["nombre_entidad"].isin(["BANCOS", "SISTEMA FINANCIERO"])]
    for c in ["sit1_pct", "sit2_pct", "sit3_pct", "sit4_pct", "sit5_pct", "sit6_pct"]:
        if c not in sub.columns:
            sub[c] = 0
    sub["amplia"] = (
        sub["sit2_pct"].fillna(0) + sub["sit3_pct"].fillna(0)
        + sub["sit4_pct"].fillna(0) + sub["sit5_pct"].fillna(0) + sub["sit6_pct"].fillna(0)
    )
    sub["estricta"] = (
        sub["sit3_pct"].fillna(0) + sub["sit4_pct"].fillna(0)
        + sub["sit5_pct"].fillna(0) + sub["sit6_pct"].fillna(0)
    )
    return sub[["codigo_entidad", "nombre_entidad", "total", "amplia", "estricta"]].reset_index(drop=True)

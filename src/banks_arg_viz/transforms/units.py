"""Conversión entre unidades: nominal, real (anclado a último mes), USD.

Las series del BCRA están en pesos corrientes homogéneos (ya convertidas al
TC del mes para los stocks ME en el origen). Por eso:
- "real" = deflactar por IPC al mes anchor.
- "usd"  = dividir por el TC mayorista A3500 promedio del mes (no del anchor).

Nota: para reconstruir USD "verdadero" sobre stocks que el BCRA ya pesificó,
habría que reconvertir con el TC original — eso se haría a nivel ETL, no acá.
La conversión "usd" en esta capa es una primera aproximación para visualización.
"""
from __future__ import annotations

from typing import Literal

import pandas as pd

from ..io import load_bcra_serie, load_ipc_nacional


Unit = Literal["nominal", "real", "usd"]

UNIT_LABELS = {
    "nominal": "ARS nominales",
    "real": "ARS constantes (a último mes)",
    "usd": "USD (TC mayorista A3500)",
}


def latest_anchor() -> int:
    """Último yyyymm con IPC publicado — usado como anchor por defecto."""
    ipc = load_ipc_nacional().dropna(subset=["indice"])
    return int(ipc["yyyymm"].max())


def deflactor_table(anchor: int | None = None) -> pd.DataFrame:
    """Tabla yyyymm → factor para llevar a pesos del mes anchor.

    factor = indice(anchor) / indice(yyyymm)
    Multiplicar valores nominales por este factor da pesos del mes anchor.
    """
    ipc = load_ipc_nacional().dropna(subset=["indice"]).copy()
    if anchor is None:
        anchor = int(ipc["yyyymm"].max())
    ix_anchor = ipc.loc[ipc["yyyymm"] == anchor, "indice"]
    if ix_anchor.empty:
        raise ValueError(f"No hay IPC para yyyymm={anchor}.")
    ipc["factor"] = ix_anchor.iloc[0] / ipc["indice"]
    return ipc[["yyyymm", "factor"]].reset_index(drop=True)


def fx_table() -> pd.DataFrame:
    """Tabla mensual yyyymm → TC mayorista A3500 (promedio del mes)."""
    fx = load_bcra_serie("tc_a3500").copy()
    fx["yyyymm"] = fx["fecha"].dt.year * 100 + fx["fecha"].dt.month
    monthly = fx.groupby("yyyymm", as_index=False)["valor"].mean()
    monthly = monthly.rename(columns={"valor": "tc"})
    return monthly


def to_usd_native(
    df: pd.DataFrame,
    value_col: str = "saldo",
    yyyymm_col: str = "yyyymm",
    anchor: int | None = None,
    out_col: str | None = None,
) -> pd.DataFrame:
    """Reconstruye el USD original de cuentas ME pesificadas y homogeneizadas.

    El BCRA reporta stocks ME en pesos al TC del cierre de cada mes; luego
    el panel los homogeneiza por IPC al mes anchor. Para volver al USD:
        USD = saldo_homogeneo · (IPC_T / IPC_anchor) / FX_T
    Donde FX_T es el TC mayorista A3500 promedio mensual.

    Aplicar SÓLO a cuentas en moneda extranjera. Si lo aplicás a una cuenta
    en pesos, el resultado no significa nada.
    """
    if df.empty:
        return df.copy()
    ipc = load_ipc_nacional().dropna(subset=["indice"]).copy()
    if anchor is None:
        anchor = int(ipc["yyyymm"].max())
    ipc_anchor = float(ipc.loc[ipc["yyyymm"] == anchor, "indice"].iloc[0])

    fx = load_bcra_serie("tc_a3500").copy()
    fx["yyyymm"] = fx["fecha"].dt.year * 100 + fx["fecha"].dt.month
    fx_monthly = fx.groupby("yyyymm", as_index=False)["valor"].mean().rename(columns={"valor": "fx"})

    out = df.merge(ipc[["yyyymm", "indice"]], left_on=yyyymm_col, right_on="yyyymm", how="left", suffixes=("", "_ipc"))
    if "yyyymm_ipc" in out.columns:
        out = out.drop(columns=["yyyymm_ipc"])
    out = out.merge(fx_monthly, left_on=yyyymm_col, right_on="yyyymm", how="left", suffixes=("", "_fx"))
    if "yyyymm_fx" in out.columns:
        out = out.drop(columns=["yyyymm_fx"])

    target = out_col or value_col
    out[target] = out[value_col] * (out["indice"] / ipc_anchor) / out["fx"]
    return out.drop(columns=["indice", "fx"])


def to_units(
    df: pd.DataFrame,
    value_col: str = "saldo",
    units: Unit = "nominal",
    anchor: int | None = None,
    yyyymm_col: str = "yyyymm",
    out_col: str | None = None,
) -> pd.DataFrame:
    """Devuelve `df` con `value_col` convertido a la unidad pedida.

    - nominal: deja como está.
    - real:    multiplica por factor IPC al mes anchor (default = último mes IPC).
    - usd:     divide por TC mayorista A3500 promedio del mes.

    Si `out_col` se omite, sobrescribe `value_col`.
    """
    if df.empty or units == "nominal":
        out = df.copy()
        if out_col and out_col != value_col:
            out[out_col] = out[value_col]
        return out

    out = df.copy()
    target_col = out_col or value_col

    if units == "real":
        defl = deflactor_table(anchor=anchor)
        out = out.merge(defl, left_on=yyyymm_col, right_on="yyyymm", how="left", suffixes=("", "_defl"))
        if "yyyymm_defl" in out.columns:
            out = out.drop(columns=["yyyymm_defl"])
        out[target_col] = out[value_col] * out["factor"]
        out = out.drop(columns=["factor"])
        return out

    if units == "usd":
        fx = fx_table()
        out = out.merge(fx, left_on=yyyymm_col, right_on="yyyymm", how="left", suffixes=("", "_fx"))
        if "yyyymm_fx" in out.columns:
            out = out.drop(columns=["yyyymm_fx"])
        out[target_col] = out[value_col] / out["tc"]
        out = out.drop(columns=["tc"])
        return out

    raise ValueError(f"units desconocida: {units}")

"""Acceso al panel de indicadores CAMELS calculados por el BCRA."""
from __future__ import annotations

import pandas as pd

from ..io import load_indicadores


def indicadores_disponibles() -> pd.DataFrame:
    """Catálogo de indicadores: codigo_linea + descripcion + formato_valor."""
    df = load_indicadores()
    return (
        df[["codigo_linea", "descripcion_indicador", "formato_valor"]]
        .drop_duplicates()
        .sort_values("codigo_linea")
        .reset_index(drop=True)
    )


def indicador_entidad(
    codigo_entidad: str,
    codigo_linea: str | None = None,
) -> pd.DataFrame:
    """Serie temporal del indicador para la entidad, con benchmarks.

    Devuelve columnas:
      yyyymm, valor, valor_grupo_homogeneo, valor_top10_privados, valor_sistema_financiero
    """
    df = load_indicadores()
    sub = df[df["codigo_entidad"] == codigo_entidad].copy()
    if codigo_linea:
        sub = sub[sub["codigo_linea"] == codigo_linea]
    return sub.sort_values("yyyymm").reset_index(drop=True)


def ranking_entidades(codigo_linea: str, yyyymm: int, top: int = 20) -> pd.DataFrame:
    """Top entidades por valor del indicador en un mes dado."""
    df = load_indicadores()
    sub = df[(df["codigo_linea"] == codigo_linea) & (df["yyyymm"] == yyyymm)]
    return (
        sub[["codigo_entidad", "nombre_entidad", "valor"]]
        .sort_values("valor", ascending=False)
        .head(top)
        .reset_index(drop=True)
    )

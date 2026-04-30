"""Smoke tests del paquete y los datos curados."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_loaders_basicos():
    from banks_arg_viz.io import (
        load_balance_mensual,
        load_indicadores,
        load_distribgeo,
        load_dim_entidades,
        load_dim_cuentas,
        load_ipc_nacional,
        load_bcra_serie,
    )
    assert len(load_balance_mensual()) > 1_000_000
    assert load_indicadores()["codigo_linea"].nunique() >= 30
    assert len(load_distribgeo()) > 5_000
    assert load_dim_entidades().query("es_vigente").shape[0] > 50
    assert load_dim_cuentas().shape[0] > 5_000
    assert load_ipc_nacional()["indice"].notna().sum() > 50
    assert len(load_bcra_serie("tc_a3500")) > 1000


def test_deflactacion():
    import pandas as pd
    from banks_arg_viz.transforms import to_units, latest_anchor, deflactor_table

    anchor = latest_anchor()
    assert anchor > 202500

    defl = deflactor_table(anchor=anchor)
    assert (defl["yyyymm"] == anchor).any()
    # El factor en el mes anchor debe ser 1.0
    f = defl[defl["yyyymm"] == anchor]["factor"].iloc[0]
    assert abs(f - 1.0) < 1e-6

    # Conversión "real" devuelve un valor distinto al nominal en años pasados
    test = pd.DataFrame({"yyyymm": [202001, 202301, anchor], "saldo": [100.0, 100.0, 100.0]})
    real = to_units(test, units="real", anchor=anchor)
    assert real.iloc[0]["saldo"] > real.iloc[1]["saldo"] > real.iloc[2]["saldo"] - 1e-6


def test_conversion_usd():
    import pandas as pd
    from banks_arg_viz.transforms import to_units

    test = pd.DataFrame({"yyyymm": [202001, 202301, 202601], "saldo": [1000.0, 1000.0, 1000.0]})
    usd = to_units(test, units="usd")
    # En 202001 el TC era ~60, en 202601 ~1300+. 1000 / TC debe ser una secuencia decreciente.
    assert usd.iloc[0]["saldo"] > usd.iloc[1]["saldo"] > usd.iloc[2]["saldo"]


def test_geojson():
    from banks_arg_viz.geo import geojson_argentina, normalize_provincia
    gj = geojson_argentina()
    assert gj is not None
    assert len(gj["features"]) >= 24

    # Normalización: aliases comunes de Buenos Aires deben caer en CABA o BUENOS AIRES
    assert normalize_provincia("Capital Federal") == "CABA"
    assert normalize_provincia("Ciudad Autónoma de Buenos Aires") == "CABA"
    assert normalize_provincia("Gran Buenos Aires") == "BUENOS AIRES"

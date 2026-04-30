"""banks_arg_viz — backend del dashboard de balances bancarios Argentina.

Estructura:
- io        carga de parquet/csv con caché
- transforms deflactación, conversión USD, agregaciones
- kpis      cálculo de indicadores (NPL, ROA, ME/Activo, etc.)
- geo       helpers geográficos (mapeo provincia ↔ ISO)
"""

__version__ = "0.1.0"

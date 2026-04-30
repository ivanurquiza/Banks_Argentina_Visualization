"""banks_arg_viz — backend del dashboard de balances bancarios Argentina.

Estructura:
- io        carga de parquet/csv con caché
- transforms deflactación, conversión USD, agregaciones
- kpis      cálculo de indicadores (NPL, ROA, ME/Activo, etc.)
- geo       helpers geográficos (mapeo provincia ↔ ISO)
- theme     paleta y plotly template
"""

# Registra el plotly template "banks_arg" como default global del proceso.
from . import theme  # noqa: F401

__version__ = "0.2.0"

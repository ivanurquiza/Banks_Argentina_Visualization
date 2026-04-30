# Bancos Argentina

Dashboard público sobre el sistema bancario argentino. Datos del **BCRA** (Información de Entidades Financieras + API monetarias) e **INDEC** (IPC).

**App en vivo: [bancos-argentina.streamlit.app](https://bancos-argentina.streamlit.app/)**

> Construido a partir del pipeline ETL del paper *Macroprudential Regulation Lending Channel*.

---

## Qué muestra

| Página | Contenido |
|---|---|
| **🏛️ Sistema** | Agregados sistémicos: stocks (activo, pasivo, préstamos, depósitos), composición del balance, concentración, vistas temáticas (CERA, encajes ME), indicadores CAMELS. |
| **🏦 Por Banco** | Explorador entidad por entidad: KPIs, balance, indicadores CAMELS comparados con grupo / sistema, estructura, distribución geográfica. |
| **⚖️ Comparador** | Hasta 6 bancos lado a lado: tabla de KPIs + series superpuestas + indicadores CAMELS. |
| **🗺️ Mapa** | Choropleth de Argentina: préstamos, depósitos y red de sucursales por provincia. |

### Filtros globales (sidebar)
- **Unidades**: ARS nominal / ARS constante (deflactado por IPC INDEC, anclado al último mes publicado) / USD (TC mayorista A3500 promedio mensual)
- **Consolidación pro-forma de fusiones** (recomendado): aplica fusiones bancarias hacia atrás (ej. Macro+BMA en 2024-11) para series comparables.

---

## Cómo correrlo localmente

```bash
git clone https://github.com/ivanurquiza/Banks_Argentina_Visualization
cd Banks_Argentina_Visualization
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/Home.py
```

App abre en `http://localhost:8501`.

---

## Estructura

```
Banks_Argentina_Visualization/
├── app/                   # Streamlit (UI)
│   ├── Home.py
│   ├── pages/
│   └── components/        # filtros globales reutilizables
├── src/banks_arg_viz/     # paquete Python (lógica)
│   ├── io/                # carga de parquet/csv con caché
│   ├── transforms/        # deflactación + conversión USD
│   ├── kpis/              # cálculo de indicadores
│   └── geo/               # helpers geográficos
├── data/
│   ├── curated/           # parquets publicables (panel_*, dim_*)
│   ├── reference/         # crosswalks (cuenta_categoria, fusiones)
│   └── external/          # series macro (BCRA API JSON, INDEC IPC)
├── scripts/               # pipeline de actualización
└── .github/workflows/     # CI: actualización automática + smoke tests
```

---

## Datos

### Capas

| Capa | Contenido | Tamaño |
|---|---|---|
| `data/curated/` | Parquets ya procesados que la app consume directamente. | ~66 MB |
| `data/reference/` | Crosswalks estables (planes de cuentas, fusiones, ISO provincias). | ~30 KB |
| `data/external/` | Series macro de actualización frecuente (TC, IPC, CER, etc.). | ~5 MB |

Los datos crudos del BCRA (~25 GB de dumps IEF mensuales) **no** se versionan — se procesan en el repo del paper (`Macroprudential_Regulation_Lending_Channel`) y los parquets resultantes se sincronizan acá.

### Fuente

Cobertura, fechas y SHAs en `data/sources.yaml` (regenerado por el pipeline en cada actualización).

- **BCRA IEF** — Información de Entidades Financieras (datos abiertos): publicación mensual con un mes de lag.
- **BCRA API v4 (Monetarias)** — TC A3500, reservas, base monetaria, BADLAR, CER, UVA, UVI: serie diaria.
- **INDEC IPC** — Serie por divisiones, Nacional, base dic-2016: publicación mensual.

---

## Actualización de datos

### Manual

```bash
# Refresca series macro (rápido, sólo BCRA API + INDEC IPC)
python scripts/update_data.py

# Sólo sync de parquets desde el paper repo
PAPER_REPO_PATH=/ruta/al/paper python scripts/sync_curated.py

# Todo (series macro + parquets)
PAPER_REPO_PATH=/ruta/al/paper python scripts/update_data.py
```

### Automatizado

`.github/workflows/update-data.yml` corre **dos veces por mes**:
- Día 1 a 13:00 UTC (captura el IPC publicado fin de mes)
- Día 6 a 12:00 UTC (un día después del corte habitual del IEF/IPC)

Refresca los JSON de la API BCRA y el CSV de IPC; commitea sólo si hay cambios. El sync de los parquets curados desde el paper repo se hace manualmente — esos cambian una vez al mes y requieren acceso al pipeline ETL completo.

---

## Deploy a Streamlit Community Cloud

1. Push a GitHub (este repo).
2. En [share.streamlit.io](https://share.streamlit.io), conectar el repo.
3. Apuntar al main file: `app/Home.py`.
4. Python version: 3.12.

Re-deploy automático en cada commit a `main`.

---

## Stack

- Python ≥3.10 (testeado en 3.12 / 3.14)
- pandas + pyarrow para datos
- Streamlit + plotly para UI

---

## Licencia

MIT — ver `LICENSE`.

Datos en dominio público (BCRA / INDEC). Citar el origen es buena práctica si reutilizás.

---

## Atribución

Este dashboard es un companion del trabajo de investigación *Macroprudential Regulation Lending Channel* (Iván Urquiza, 2026). El paper y el pipeline ETL viven en un repo separado.

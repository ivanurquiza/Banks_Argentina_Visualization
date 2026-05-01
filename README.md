# Bancos Argentina

Dashboard público sobre el sistema bancario argentino. Datos del **BCRA** (Información de Entidades Financieras + API monetarias) e **INDEC** (IPC).

**App en vivo: [bancos-argentina.streamlit.app](https://bancos-argentina.streamlit.app/)**

Construido a partir del pipeline ETL del proyecto *Macroprudential Regulation Lending Channel*.

En construcción, puede haber errores. Me podés escribir por mis links de contacto (También podés ver las series directo de los anexos del Informe de Entidades Financieras, mensualmente publicado por el BCRA).

---

### Fuente

Cobertura, fechas y SHAs en `data/sources.yaml` (regenerado por el pipeline en cada actualización).

- **BCRA IEF** — Información de Entidades Financieras (datos abiertos): publicación mensual con un mes de lag.
- **BCRA API v4 (Monetarias)** — TC A3500, reservas, base monetaria, BADLAR, CER, UVA, UVI: serie diaria.
- **INDEC IPC** — Serie por divisiones, Nacional, base dic-2016: publicación mensual.

---

## Actualización de datos

### Manual

```bash
# Refresca series macro (sólo BCRA API + INDEC IPC)
python scripts/update_data.py

# Sólo sync de parquets desde el paper repo
PAPER_REPO_PATH=/ruta/al/paper python scripts/sync_curated.py

# Todo (series macro + parquets)
PAPER_REPO_PATH=/ruta/al/paper python scripts/update_data.py
```

### Ahora automatizado

`.github/workflows/update-data.yml` corre **dos veces por mes**:
- Día 1 a 13:00 UTC (captura el IPC publicado fin de mes)
- Día 6 a 12:00 UTC (un día después del corte habitual del IEF/IPC)

Refreshea los JSON de la API BCRA y el CSV de IPC; commitea sólo si hay cambios. El sync de los parquets desde el repo se hace manualmente -esos cambian una vez al mes y requieren acceso al pipeline ETL completo-.

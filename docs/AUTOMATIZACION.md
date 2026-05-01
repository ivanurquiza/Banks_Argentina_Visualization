# Pipeline de auto-actualización

El dashboard se actualiza solo. Esta nota explica cómo y cuándo.

## Cadencia

| Día del mes | Hora UTC | Qué corre |
|---|---|---|
| 1 | 13:00 | Refresh IPC INDEC + BCRA API + check IEF |
| 5, 10, 15, 20, 25 | 12:00 | Check IEF y procesa si hay nuevo + macro |

El BCRA publica el dump IEF mensualmente, típicamente entre el día 1 y el 6 del mes siguiente al cierre. Las corridas hasta el día 25 captan publicaciones tardías.

## Qué hace

```
GitHub Action cron
   │
   ├─ scripts/download_bcra_api.py      # series monetarias (TC, CER, UVA, BADLAR)
   ├─ scripts/download_indec_ipc.py     # IPC nacional
   ├─ scripts/download_bcra_ief.py      # detecta y baja último .7z (~30MB)
   ├─ scripts/process_ief.py            # genera parquets curados
   ├─ smoke test                        # valida que cargue todo
   └─ git commit + push                 # Streamlit Cloud redeploya
```

## Pipeline completa

`scripts/update_data.py` orquesta todo. Modos:

```bash
python scripts/update_data.py                  # pipeline completa
python scripts/update_data.py --solo-macro     # solo BCRA API + IPC INDEC
python scripts/update_data.py --solo-ief       # solo IEF download + process
python scripts/update_data.py --skip-process   # baja sin procesar
python scripts/update_data.py --ventana-ief last-3  # baja últimos 3 meses
```

## Detalle del IEF

Cada dump IEF (.7z, ~30MB) contiene la **historia completa** del balance hasta el mes de corte. Para los demás panels (ESD, indicadores, estructura) cada dump trae los **últimos 5 trimestres**, así que el procesador hace MERGE con el parquet existente: concat + drop_duplicates(keep="last") sobre la combinación entidad×mes×línea.

Resultado:
- `panel_balance_mensual.parquet`: se reemplaza con cada dump (history full).
- `panel_balance_mensual_proforma.parquet`: igual, recalcula con `fusiones.csv`.
- `panel_balance_agregados.parquet`, `panel_esd.parquet`, `panel_indicadores.parquet`, `panel_estructura.parquet`, `panel_sucursales_provincia.parquet`, `panel_distribgeo.parquet`: se MERGEAN con datos previos (rolling).

## Trigger manual

Desde GitHub UI → Actions → "Auto-actualización de datos" → Run workflow:
- **modo**: `completo` | `solo-macro` | `solo-ief`
- **ventana_ief**: `last` (default) | `last-3` | `202501-202604` (rango explícito)

## Concurrencia

`concurrency: update-data` con `cancel-in-progress: false`. Si una corrida arranca mientras hay otra activa, espera. Evita conflictos de commit.

## Disco

GitHub Actions runners tienen ~14 GB libres. Cada IEF dump pesa:
- .7z: ~30 MB
- Extraído: ~250 MB

Procesamiento usa ~2 GB de RAM (balhist tiene 9M filas). Bien dentro de los 7 GB del runner.

## Limpieza automática

Después de procesar, `update_data.py --cleanup` borra los directorios extraídos en `data/_raw/bcra_ief/{yyyymm}/` para no inflar el repo. Mantiene los `.7z` archivos por trazabilidad (~30MB c/u).

Para borrar también los `.7z`:
```bash
rm -rf data/_raw/bcra_ief/_archives/*.7z
```

## Modificar la cadencia

Editar `.github/workflows/update-data.yml`. El cron usa expresión estándar:

```yaml
schedule:
  - cron: '0 13 1 * *'   # día 1 del mes a las 13:00 UTC
  - cron: '0 12 5,10,15,20,25 * *'
```

## Diagnóstico

Si una corrida falla, ver Actions en GitHub:
1. ¿Falló el download IEF? Probablemente BCRA no publicó aún ese mes. Reintenta más tarde.
2. ¿Falló el procesamiento? Revisar logs de `process_ief.py` — buscar el panel que rompió.
3. ¿Falló el smoke test? Algún parquet quedó corrupto. Revertir el commit problemático.
4. ¿Sin push? El job no encontró cambios — normal si no había dump nuevo.

Para correr localmente y ver qué falla:
```bash
python scripts/update_data.py
```

## Reset completo

Si los parquets se corrompen, reset:

```bash
# 1. Borrar todos los curados
rm -rf data/curated/paneles/*.parquet

# 2. Bajar todos los dumps que querés (puede tardar mucho)
python scripts/download_bcra_ief.py --ventana 202001-202604

# 3. Procesar todo
python scripts/process_ief.py

# 4. Verificar
pytest tests/

# 5. Commit
git add data/curated/
git commit -m "data: reset completo desde IEF"
git push
```

## Limitaciones conocidas

- Si BCRA cambia el formato de los archivos `.txt` dentro del .7z, el procesamiento puede romperse. Hay que adaptar `scripts/process_ief.py` y los índices de columnas.
- El procesamiento de balhist.txt es pesado (~9M filas). Tarda ~30s en runners decentes.
- `panel_actividad_*` (préstamos por actividad CIIU) no se reprocesa automáticamente — usa datos cargados desde el repo del paper. Si querés actualizarlo, descargar manualmente desde el sitio del BCRA (panel `bcra_prestamos_actividad`).

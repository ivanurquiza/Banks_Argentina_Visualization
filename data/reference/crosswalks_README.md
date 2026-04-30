# Crosswalks

Esta carpeta contiene las **decisiones de investigador** necesarias para pasar de los paneles largos (raw del BCRA) a las tablas de análisis. Son CSV editables a mano, versionados en git, joinables vía SQL desde DuckDB.

A diferencia de los datos en `data/raw/` y `data/interim/`, los crosswalks **sí son juicio del investigador** y deben revisarse antes de cada regresión.

## Archivos

| Archivo | Propósito | Documentación detallada |
|---|---|---|
| [`cuenta_categoria.csv`](cuenta_categoria.csv) | Mapea códigos del plan de cuentas BCRA a categorías económicas estables del paper (CERA, crédito USD SPNF, depósitos USD, deuda BCRA, etc.) | [docs/notas/crosswalks.md §1](../../../docs/notas/crosswalks.md) |
| [`fusiones.csv`](fusiones.csv) | Registro de fusiones, absorciones y cambios de denominación. Insumo para el panel pro-forma alternativo (decisión §3.1 metodología) | [docs/notas/crosswalks.md §2](../../../docs/notas/crosswalks.md) |
| [`provincias_iso.csv`](provincias_iso.csv) | 24 jurisdicciones argentinas + exterior, con códigos ISO 3166-2:AR | (autoexplicativo) |

## Esquema de `cuenta_categoria.csv`

Una fila por par `(categoria, codigo_cuenta)`. Una cuenta puede pertenecer a varias categorías (ej. `311793` está en `cera_total`, `cera_ars` y `cera_residente_pais`).

| Campo | Tipo | Descripción |
|---|---|---|
| `categoria` | str | Identificador snake_case de la categoría económica |
| `codigo_cuenta_pattern` | str | Código completo de 6 dígitos, o pattern SQL LIKE con `%` (ej. `135%` matchea todo el capítulo 135) |
| `nivel` | enum | `principal` (capítulo entero) o `detalle` (cuenta específica) |
| `moneda` | enum | `ars`, `me`, `mixta` |
| `sector` | enum | `spnf`, `sf`, `publico`, `bcra`, `mixto`, `patrimonio`, etc. |
| `nota` | str | Aclaración legible |

## Esquema de `fusiones.csv`

Una fila por evento institucional relevante. Se usa para construir `panel_balance_mensual_proforma.parquet` (decisión §3.1 de la metodología).

| Campo | Tipo | Descripción |
|---|---|---|
| `codigo_absorbente` | str | 5 dígitos del banco que sobrevive (vacío si nadie absorbió) |
| `nombre_absorbente` | str | Nombre legible |
| `codigo_absorbido` | str | 5 dígitos del banco que desaparece (vacío si es solo cambio de denominación) |
| `nombre_absorbido` | str | Nombre legible |
| `fecha_evento` | date (YYYY-MM-DD) | Fecha exacta del evento; usar `XX` para campos pendientes de verificar |
| `tipo_evento` | enum | `absorcion`, `cambio_denominacion`, `cambio_control`, `baja_voluntaria` |
| `nota` | str | Aclaración + flag explícito si el evento cae en la ventana 2020+ del paper |

## Cómo usar desde un notebook

```python
import duckdb
duckdb.sql("""
    select p.codigo_entidad, p.yyyymm, cw.categoria, sum(p.saldo) as saldo
    from 'data/interim/paneles_largos/panel_balance_mensual.parquet' p
    join 'data/external/crosswalks/cuenta_categoria.csv' cw
      on p.codigo_cuenta like cw.codigo_cuenta_pattern
    where cw.categoria = 'cera_total'
    group by p.codigo_entidad, p.yyyymm, cw.categoria
""").df()
```

DuckDB resuelve el `LIKE` correctamente para los patterns con `%` y para los códigos exactos.

## Mantenimiento

- **Cuando se agrega una categoría nueva**: editá el CSV, agregá filas, documentá en `docs/notas/crosswalks.md`.
- **Cuando se descubre una fusión nueva**: agregá fila a `fusiones.csv` y verificá si afecta la ventana del paper.
- **Antes de cada regresión nueva**: re-leer estos archivos y confirmar que las definiciones siguen siendo las correctas.

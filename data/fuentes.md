# Fuentes de datos — trazabilidad

Documento de lectura rápida. Cada sección describe **qué bajamos**, **de dónde**, **con qué loop** y **dónde vive en el repo**. La referencia formal (URL, sha256, tamaño, fecha) está en [`sources.yaml`](sources.yaml); este archivo explica el contexto.

---

## 1. BCRA · Información de Entidades Financieras (IEF) — dumps mensuales

**Qué es.** Snapshot completo del "Directorio IEF" del BCRA, un `.7z` por mes que contiene:
- `Entfin/Tec_Cont/bal_hist/balhist.txt` → balance histórico mensual (~9 M filas, 1994-11 hasta la fecha del dump), por entidad × cuenta × mes.
- Subcarpetas de snapshot (sólo fecha del corte): `distribgeo/`, `Distrib/`, `Casas/`, `Accioni/`, `ranking/`, `indicad/`, `esd/`, `inf_adi/`, etc.
- Diccionarios (`cuentas/cuentas.txt`, `Nomina.txt`, `Grupos.txt`) e historia institucional (`Info_Hist/`).

**URL pattern.** `https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/Entidades/{yyyymm}d.7z`, donde `yyyymm` es el mes de **publicación** (el corte de datos es el mes anterior).

**Cobertura efectiva.** El BCRA publica dumps históricos desde 2002-07; hasta 2010 sólo hay un dump por año (diciembre); desde 2011 son mensuales con gaps puntuales en 2011-02, 2011-06, 2013-05.

**Ventana bajada en este repo.** `yyyymm ∈ [201501, 202601]` (publicación) → corte de datos `[2014-12, 2025-12]`. **133 dumps**, ~2.2 GB comprimido.

**Cómo se construyó el loop.**

1. Script: `/tmp/bcra_download.py` (no está en el repo; guardable bajo `code/python/` si lo queremos persistir).
2. Inventario real: probado con `GET` + `Range: 0-0` (HEAD estaba roto en el servidor del BCRA — devolvía HTML falso con status 200).
3. Para cada `yyyymm` listado:
   - descarga `.7z` a `data/raw/bcra_ief/_archives/{yyyymm}.7z`;
   - computa SHA-256 del archivo bajado;
   - extrae con `py7zr` a `data/raw/bcra_ief/{yyyymm}/`;
   - appendea una entrada a `sources.yaml` con `id = bcra_ief_{yyyymm}`.
4. Idempotente: saltea descarga si el `.7z` ya existe con tamaño correcto y saltea extracción si el directorio destino ya tiene contenido.

**Dónde vive.**
```
data/raw/bcra_ief/
├── _archives/{yyyymm}.7z    # inmutable, con sha256 registrado
└── {yyyymm}/                # contenido extraído
```

**Caveats.**
- `bal_hist/balhist.txt` del dump más reciente (202601) **ya contiene toda la serie histórica 1994-11 → 2025-12** sin necesidad de dumps anteriores. Los dumps previos son útiles sólo para las **carpetas-snapshot** (`distribgeo`, `Distrib`, `ranking`, `Accioni`, etc.), que cambian con cada corte.
- Los códigos de entidad son de 5 dígitos (`"00007"` = Galicia, `"00011"` = Nación, etc.). Ver `Nomina.txt` dentro de cualquier dump.

---

## 2. BCRA · Estadísticas del sistema (agregado y por grupo, sin granularidad por entidad)

**Qué es.** Series del Boletín Estadístico, del Anexo del Informe sobre Bancos y de Financiaciones por actividad económica. Ninguna llega a nivel entidad individual; la granularidad máxima es **grupo homogéneo** (sistema / públicos / privados nacionales / extranjeros / EFNB).

**Para qué nos sirve.** Benchmark agregado para validar los proxies banco-por-banco que construiremos desde `bal_hist` (PGNME, RPC, Efectivo Mínimo no se publican por entidad; ver sección 3).

**URL pattern.** `https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/{nombre}.xls[x]`.

**Qué bajamos (54 archivos, ~345 MB):**

| Subdir de `data/raw/bcra_sistema/` | Archivos | Fuente | Qué trae |
|---|---|---|---|
| `informe_sobre_bancos/` | `InfBanc_Anexo.xlsx` | Informe sobre Bancos | Indicadores por grupo homogéneo: **RPC, Tier 1, posición de capital, liquidez amplia/restringida, irregularidad, ROA, ROE**, etc. Cobertura 2002 en adelante. Es el archivo-benchmark clave para validar proxies. |
| `boletin_estadistico/` | `panhis`, `balsishis`, `balbanhis`, `balenthis`, `baldethis`, `balbcrhis`, `liqhis`, `pashis`, `calhis`, `perser_priv`, `perser_pub`, `perser_dest`, `titpubser`, `tasser`, `preser_mon`, `preser_pla`, `preser_tas` | Boletín Estadístico | Series históricas del sistema: balance, liquidez, pasivos, calidad de cartera, préstamos y depósitos por sector/moneda/plazo/tasa, tenencias de títulos. |
| `series_diarias/` | `diar_fin`, `diar_dep`, `diar_tim` | Boletín Estadístico | Saldos diarios de préstamos, depósitos y tasas. Útil para event study alrededor del blanqueo (ago-2024). |

**Préstamos por actividad económica — vive aparte en `data/raw/bcra_prestamos_actividad/`** por su centralidad en la estrategia empírica (canal transables, test placebo sectorial).

| Carpeta | Archivos | Fuente | Qué trae |
|---|---|---|---|
| `data/raw/bcra_prestamos_actividad/` | `act{2015..2025}.xls` (11), `act{YYYY}grup.xls` (11), `loc{YYYY}.xls` (11) | BCRA – Préstamos por actividad económica | Financiaciones trimestrales al sector privado por CIIU (total sistema), por CIIU × grupo de entidad, y por localidad/provincia. **No hay cruce banco × provincia × CIIU × moneda** — documentado como limitación en `VIABILIDAD_DATOS_vs_PROPUESTA.md`. |

**Cómo se construyó el loop.**

1. Script: `/tmp/bcra_sistema_download.py`.
2. La lista de archivos se armó a partir de (a) el dropdown de `/prestamos-y-otros-activos-de-las-entidades-financieras/` y (b) los URLs extraídos del PDF del Boletín Estadístico (`boldat202601.pdf`) — ~60 `.xls` referenciados desde ese PDF.
3. Para cada archivo: descarga a `data/raw/bcra_sistema/<subdir>/<nombre>`, computa sha256, registra una entrada en `sources.yaml`.
4. Idempotente: saltea si el archivo ya existe con tamaño > 0.

**Caveat clave.** Estos archivos son la **versión "vigente"** en el servidor BCRA — cada descarga te trae la última actualización de la serie. No son snapshots mensuales como los IEF. Si querés comparar qué cambió entre descargas, hay que versionarlos por `downloaded_at` (hoy lo trackeamos en `sources.yaml`, pero sobrescribimos el archivo).

---

## 3. Lo que NO está público por entidad (pendiente: proxies y/o pedido formal)

Después de revisar Boletín Estadístico, Informe sobre Bancos y la sección de estadísticas del BCRA, confirmamos que las tres medidas regulatorias centrales **no se publican por entidad**:

- **PGNME** (Posición Global Neta en Moneda Extranjera).
- **RPC** (Responsabilidad Patrimonial Computable oficial) y **Capitales Mínimos exigencia**.
- **Efectivo Mínimo** – integración, exigencia, defecto/exceso por entidad.

**Plan pactado**:

1. Construir proxies desde `bal_hist` (capítulos documentados en `docs/notas/` — pendiente).
2. Validar los proxies **agregados al sistema** contra los indicadores 11/12/13 del Anexo del Informe sobre Bancos (y los equivalentes de liquidez). Si la suma ponderada de los proxies replica el valor-sistema con error < ~5 %, se validan como medida de heterogeneidad transversal aunque el nivel no sea la medida regulatoria exacta.
3. Si los proxies no discriminan bien, activar pedido formal al BCRA vía Ley 27.275 (Acceso a la Información Pública).

---

## 4. BCRA API v4 — Series monetarias diarias (fuente primaria)

**Organismo**: Banco Central de la República Argentina (BCRA), API oficial.
**Endpoint base**: `https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/{idVariable}?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&limit=3000`.
**Catálogo de series**: `GET https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias` (1220 variables disponibles).
**Metodología**: cada serie trae en el catálogo su `descripcion`, `tipoSerie`, `periodicidad`, `unidadExpresion`, `moneda`, `primerFechaInformada`, `ultFechaInformada`.

**Ventana bajada**: 2015-01-01 → hoy, en match con el IEF. 9 series JSON:

| idVar | Serie | Primer dato | Uso en el paper |
|---|---|---|---|
| 5 | **Tipo de cambio mayorista de referencia (Com. A-3500)** | 2002-03-04 | TC oficial; cross-check de cotizaciones secundarias |
| 4 | Tipo de cambio minorista (promedio vendedor) | 2010-06-01 | Benchmark minorista |
| 1 | Reservas internacionales | 1996-01-03 | Contexto macro |
| 15 | Base monetaria | 1996-01-02 | Contexto macro |
| 7 | Tasa BADLAR bancos privados | 1996-01-02 | Tasa mayorista; benchmark de tasas de depósito |
| 30 | Coeficiente de Estabilización de Referencia (CER) | 2002-02-02 | Ajuste real |
| 31 | Unidad de Valor Adquisitivo (UVA) | 2016-03-31 | Créditos ajustables |
| 32 | Unidad de Vivienda (UVI) | 2016-03-31 | Créditos hipotecarios |
| 81 | Variación de reservas internacionales por efectivo mínimo | 2003-01-02 | Proxy agregado del canal encajes |

**Carpeta**: `data/raw/bcra_api/{idVar:03d}_{short_name}.json`.

---

## 5. INDEC · Índice de Precios al Consumidor (IPC) — fuente primaria

**Organismo**: Instituto Nacional de Estadística y Censos (INDEC).
**Página institucional del producto**: [https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-5-31](https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-5-31) (incluye informes técnicos, metodología, ISSN 2545-6636).
**Base de índice**: diciembre 2016 = 100.
**Carpeta FTP primaria**: `https://www.indec.gob.ar/ftp/cuadros/economia/`.

| Archivo | Qué trae |
|---|---|
| `sh_ipc_aperturas.xls` | Serie histórica IPC nacional con **variaciones mensuales por aperturas** (nivel general + bienes/servicios + capítulos + regiones). Se refresca con cada informe mensual. |
| `serie_ipc_aperturas.csv` | Serie completa en CSV, idéntica cobertura que el xls. |
| `serie_ipc_divisiones.csv` | Serie por **divisiones y subdivisiones de la COICOP** (Alimentos, Vestimenta, Transporte, etc.) + por región geográfica. |

**Caveat temporal**: el IPC-GBA corre 2012-04 → 2017-04; el nacional base dic-2016 corre 2016-12 → presente. Para series largas hay que empalmar con IPC-GBA (informado como ruptura en el mismo xls) o con IPC-San Luis / IPC-Congreso para el hueco 2007-2015 (**no hecho automáticamente** — decisión de investigador).

**Carpeta**: `data/raw/indec_ipc/`.

---

## 6. SIPA vía OEDE — Empleo y remuneraciones por provincia (fuente primaria)

**Organismo**: Ministerio de Capital Humano — Observatorio de Empleo y Dinámica Empresarial (OEDE). Los datos provienen del **Sistema Integrado Previsional Argentino (SIPA)** con integración del Simplificado Registro Tributario.
**Página institucional**: [https://www.argentina.gob.ar/trabajo/estadisticas/oede-estadisticas-provinciales](https://www.argentina.gob.ar/trabajo/estadisticas/oede-estadisticas-provinciales).
**Nota metodológica**: `https://www.argentina.gob.ar/sites/default/files/mteyss_oede_estimacion-por-departamento-nota_metodologica.pdf`.
**Carpeta primaria**: `https://www.argentina.gob.ar/sites/default/files/`.

| Archivo | Granularidad | Frecuencia | Cobertura |
|---|---|---|---|
| `provinciales_serie_empleo_trimestral_2dig_5.xlsx` | Provincia × CIIU 2 dígitos, empleo asalariado registrado sector privado | Trimestral | 1T1996 → actual |
| `provinciales_serie_empleo_trimestral_4dig_6.xlsx` | Provincia × CIIU 4 dígitos | Trimestral | 1T1996 → actual |
| `provinciales_serie_empleo_anual_2.xlsx` | Provincia (totales) | Anual | 1996 → actual |
| `provinciales_serie_remuneraciones_mensual_2dig_7.xlsx` | Provincia × CIIU 2 dígitos, remuneración promedio | Mensual | 2007 → actual |
| `provinciales_serie_remuneraciones_anual_2.xlsx` | Provincia (totales) | Anual | 1996 → actual |

**Carpeta**: `data/raw/sipa_oede/`.

---

## 7. INDEC · Origen Provincial de las Exportaciones (OPEX) — histórico 1993-2018

**Organismo**: INDEC — Dirección Nacional de Cuentas Internacionales / Comercio Exterior. ISSN 2545-6636.
**Página institucional (sitio anterior)**: [https://sitioanterior.indec.gob.ar/nivel4_default.asp?id_tema_1=3&id_tema_2=2&id_tema_3=79](https://sitioanterior.indec.gob.ar/nivel4_default.asp?id_tema_1=3&id_tema_2=2&id_tema_3=79).
**Informes trimestrales post-2018** (PDF por trimestre): `https://www.indec.gob.ar/uploads/informesdeprensa/opex_{MM}_{YY}{...hash}.pdf`.
**Portal interactivo nuevo (post-2018)**: [https://opex.indec.gob.ar/](https://opex.indec.gob.ar/) — SPA en JavaScript; **no exporta bulk directamente**, habría que scrapear XHR o parsear los PDFs.

**Carpeta FTP primaria (series históricas)**: `https://sitioanterior.indec.gob.ar/ftp/cuadros/economia/`.

| Archivo | Qué trae | Rango |
|---|---|---|
| `sh_opex_principales_grubros_1993_2018.xls` | Exportaciones por grandes rubros (Productos primarios / MOA / MOI / Combustibles) | 1993-2018 |
| `sh_opex_regiones_economicas_grubros_1993_2018.xls` | Grandes rubros × región económica | 1993-2018 |
| `sh_opex_regiones_economicas_provincias_1993_2018.xls` | Exportaciones totales × provincia × región | 1993-2018 |
| `opex_anexo_cuadros.xls` | Cuadros anexos: diccionario de complejos exportadores, definiciones metodológicas | — |

**Caveat crítico**: la ventana de la propuesta (blanqueo ago-2024) **está fuera del rango 1993-2018**. Los archivos sirven para construir **shares predeterminados** de exposición exportadora provincial (p. ej., promedio 2015-2018 como "pre-cepo"), pero no para medir outcomes durante el evento. Decisión por tomar: (a) usar esos shares como exposición ex-ante invariante en el tiempo; (b) scrapear el portal interactivo para 2019-2025; (c) parsear los PDFs trimestrales (los 10 que cubren 2019-2025).

**Carpeta**: `data/raw/indec_opex/`.

---

## 8. INDEC / Censo 2022 — Proyecciones poblacionales provinciales

**Organismo**: INDEC — Dirección Nacional de Estadísticas Sociales y de Población. Publicación conjunta con el Censo Nacional de Población, Hogares y Viviendas 2022.
**Página institucional**: [https://censo.gob.ar/index.php/proyecciones/](https://censo.gob.ar/index.php/proyecciones/).
**Metodología**: bajada junto con los datos (`metadatos_proyecciones_provinciales_2022_2040_base.pdf`).
**Carpeta primaria**: `https://censo.gob.ar/wp-content/uploads/2025/10/`.

| Archivo | Qué trae |
|---|---|
| `proyecciones_jurisdicciones_2022_2040_base.csv` | **Base de datos principal** — población proyectada por jurisdicción × sexo × edad simple × año (2022-2040) |
| `proyecciones_jurisdicciones_2022_2040_c1.xlsx` | Cuadro 1 — totales por jurisdicción y año |
| `proyecciones_jurisdicciones_2022_2040_c2.xlsx` | Cuadro 2 — por sexo |
| `proyecciones_jurisdicciones_2022_2040_c3_c4.xlsx` | Cuadros 3 y 4 — por grupos quinquenales de edad |
| `proyecciones_jurisdicciones_2022_2040.pdf` | Publicación PDF con las tablas |
| `proyecciones_nacionales_2022_2040.pdf` | Totales país (cross-check) |
| `metadatos_proyecciones_provinciales_2022_2040_base.pdf` | **Metodología oficial** |

**Uso**: normalizar outcomes reales per cápita (préstamos per cápita, empleo per cápita) y ponderar regresiones por tamaño poblacional.

**Carpeta**: `data/raw/indec_poblacion/`.

---

## 9. Cotizaciones de dólar (argentinadatos.com) — FUENTE SECUNDARIA

**Organismo**: proyecto comunitario open source. El API `api.argentinadatos.com` scrapea el sitio [DolarHoy.com](https://dolarhoy.com/), que a su vez agrega cotizaciones de medios financieros (Ámbito, Rava, IOL, BNA).
**Repo del scraper** (leído directamente): [`enzonotario/esjs-dolar-api`](https://github.com/enzonotario/esjs-dolar-api) — código en `cron/ar/dolarhoy.dolares.extractor.esjs`.
**Endpoint**: `https://api.argentinadatos.com/v1/cotizaciones/dolares/{casa}`.

| `casa` | Serie | Cobertura | Origen en DolarHoy |
|---|---|---|---|
| `oficial` | Dólar oficial minorista | 2011-01-03 → actual | BNA (Banco Nación) |
| `mayorista` | Dólar mayorista | 2011-01-03 → actual | MAE / MULC |
| `blue` | Dólar blue (informal) | 2011-01-03 → actual | Polled — no tiene upstream primario |
| `bolsa` | Dólar MEP | 2018-10-29 → actual | Computado desde AL30/AL30D |
| `contadoconliqui` | Dólar CCL | 2013-01-02 → actual | Computado desde GD30/GD30D |

**Por qué es secundaria y no primaria**. Los cálculos canónicos de MEP/CCL se harían desde precios de cierre de bonos AL30/AL30D/GD30/GD30D publicados por BYMA/MAE. BYMA tiene un producto comercial de índice MEP y CCL ([info](https://www.byma.com.ar/en/products/data-products/indice-ccl-byma-historico)) pero no es gratis. Para blue no existe fuente primaria — es OTC puro.

**Protocolo de validación (obligatorio antes de usar en regresiones)**:

1. Leer la serie `oficial`/`mayorista` de argentinadatos.
2. Cruzar con `bcra_api/005_tc_mayorista_a3500.json` (primary) por fecha.
3. Calcular ratio = (valor_argentinadatos / valor_BCRA); esperar media ≈ 1.00 y desvío estándar < 0.5%.
4. Si el cross-check falla en la ventana de interés, investigar y en el peor caso bajar los bonos directamente de BYMAdata para recomputar MEP/CCL.

**Carpeta**: `data/raw/cotizaciones_dolar/`.

---

## 10. Fuentes pendientes a resolver después

1. **OPEX 2019-2025** — scraping del portal interactivo o parsing de los PDFs trimestrales.
2. **PGNME / RPC / EfMin por entidad** — proxies desde `bal_hist` (plan §3); si no discriminan, pedido formal al BCRA vía Ley 27.275.
3. **MEP / CCL recomputados desde bonos** — solo si el cross-check de la §9 falla.
4. **Central de Deudores (CENDEU)** — si queremos granularidad banco × deudor, pedido formal.

---

## Convenciones

- **Nombres de id en `sources.yaml`**: `{fuente}_{serie}_{periodo|year|version}`, todo minúscula, snake_case.
- **`snapshot_date`**: fecha a la que se refiere el dato (no la de descarga). Para series "vigentes" sin snapshot explícito usamos el literal `current`.
- **`sha256`**: siempre sobre el archivo original tal como vino del servidor (sin recomprimir ni convertir).
- **Retención**: `data/raw/` es inmutable — nunca se edita a mano. Si hay que corregir algo, se re-baja y se actualiza la entrada en `sources.yaml`.

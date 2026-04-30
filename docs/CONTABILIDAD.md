# Reglas contables del dashboard

Documento técnico de referencia. Explica cómo el dashboard interpreta el plan
de cuentas BCRA y cómo se garantiza la integridad de los agregados.

---

## 1. Plan de cuentas BCRA — estructura

El plan de cuentas BCRA (Manual de Cuentas, Sec. F. C. R. y A.) usa códigos de
6 dígitos con estructura jerárquica:

| Capítulo raíz | Tipo | Notas |
|---|---|---|
| `1xxxxx` | ACTIVO | Sub-capítulos 11–19: efectivo, títulos, préstamos, otros créditos, etc. |
| `2xxxxx` | ACTIVO (cont.) | Sub-capítulos 21–23: intangibles, filiales, partidas pendientes saldos deudores |
| `3xxxxx` | PASIVO | 31–36: depósitos, otras obligaciones, obligaciones diversas, provisiones, partidas pendientes saldos acreedores, obligaciones subordinadas |
| `4xxxxx` | PATRIMONIO NETO | 41–46: capital social, aportes, ajustes, reservas, resultados no asignados, ORI |
| `5xxxxx` | RESULTADOS | 51–59: ingresos/egresos financieros, cargos, ingresos/egresos por servicios, gastos, utilidades/pérdidas diversas |
| `6xxxxx` | RESULTADOS (cont.) | 61 impuesto a las ganancias, 62 resultado monetario, 65 ORI |
| `7xxxxx` | PARTIDAS FUERA DE BALANCE | 71 deudoras, 72 acreedoras (off-balance, suma a cero por construcción) |
| `9xxxxx` | Memo accounts | Cuentas históricas/discontinuadas, no se reportan en panel_balance_mensual |

### Sub-capítulos dentro del activo (cap. 1)

- `11xxxx` — Efectivo y depósitos en bancos
- `12xxxx` — Títulos públicos y privados (ver §4)
- `13xxxx` — Préstamos
- `14xxxx` — Otros créditos por intermediación financiera
- `15xxxx` — Créditos por arrendamientos financieros
- `16xxxx` — Participaciones en otras sociedades
- `17xxxx` — Créditos diversos
- `18xxxx` — Propiedad, planta y equipo
- `19xxxx` — Bienes diversos

### Sub-capítulos dentro del pasivo (cap. 3)

- `31xxxx` — Depósitos (subdivisión por moneda y residencia: 311 ARS res. país, 312 ARS res. exterior, 315 ME res. país, 316 ME res. exterior)
- `32xxxx` — Otras obligaciones por intermediación financiera
- `33xxxx` — Obligaciones diversas
- `34xxxx` — Provisiones
- `35xxxx` — Partidas pendientes de imputación, saldos acreedores
- `36xxxx` — Obligaciones subordinadas

---

## 2. Convención de signos

El BCRA reporta saldos siguiendo la convención contable de doble partida:

- **Cuentas de saldo deudor** (activos típicos): almacenadas con **signo positivo**
- **Cuentas de saldo acreedor** (pasivos, patrimonio, ingresos): almacenadas con **signo negativo**

Esto produce una identidad contable que cierra a cero pero confunde la
visualización: un usuario que ve "Depósitos: -27 T" naturalmente espera ver +27 T.

### Solución implementada

`banks_arg_viz.io.loaders._flip_passive_signs` invierte el signo de todas las
cuentas con prefijo `3` o `4` al cargar el panel. Después del flip:

- Activo, Pasivo y Patrimonio se muestran todos con signo **positivo**.
- La identidad contable se mantiene como `Activo = Pasivo + Patrimonio + Resultado_curso`.
- Las **regularizadoras** (`es_regularizadora == True`, denominación con paréntesis)
  conservan el signo correcto: las de activo restan del activo, las de pasivo restan del pasivo.

Las cuentas de resultados (5xxxxx, 6xxxxx) **no se invierten** — se las usa como
cuentas de flujo del período, no como stocks.

---

## 3. Identidad contable

Para cualquier mes-T en el panel:

```
Activo(T) = Pasivo(T) + PatrimonioNeto(T) + Resultado_del_ejercicio_en_curso(T)
```

Con la convención post-flip:

```
sum(saldo | prefix in {1,2}) = sum(saldo | prefix=3) + sum(saldo | prefix=4) − sum(saldo | prefix in {5,6})
```

### Verificación

`scripts/audit_balance.py --all` recorre los 73 meses del panel y verifica que
la identidad cierre con discrepancia menor a `1e-4 = 0.01%` del activo. En la
práctica el panel cierra a `0.0000%` para todos los meses.

`tests/test_accounting.py` corre la misma verificación como parte del CI.

---

## 4. Capítulo 12 — Cartera de títulos

Para análisis de exposición soberana y riesgo de mark-to-market, el dashboard
desagrega `12xxxx` en tres dimensiones:

### Moneda

| Sub-capítulo | Moneda |
|---|---|
| `121xxx` | Pesos (ARS) |
| `125xxx` | Moneda extranjera del país (USD país) |
| `126xxx` | Moneda extranjera del exterior (USD exterior) |

### Emisor

Clasificación por keywords de denominación. Categorías:

- **Tesoro / Sector Público** — títulos del gobierno nacional o provincial.
  El plan BCRA agrupa ambos en una misma línea (no es separable a nivel de cuenta).
- **LeFi (Tesoro)** — Letras Fiscales de Liquidez. Emite el Tesoro pero los bancos
  las usan funcionalmente como sustituto post-2024 de las LELIQs.
- **BCRA - Letras** — Letras del BCRA (instrumento histórico, casi inexistente en stock vigente).
- **BCRA - Notas** — Notas del BCRA.
- **BCRA - Letras de Liquidez** — LELIQ (instrumento del régimen pre-2024).
- **BCRA - NoCom** — Notas de Compensación de Efectivo (post-2024).
- **Privado - ON / ON Subordinada** — Obligaciones Negociables.
- **Privado - Acciones / FCI / Certificados / Títulos de Deuda / Empresas de Servicios** — instrumentos de capital y deuda privada.
- **Regularizadora / NIIF** — previsiones por riesgo, saldos de prorrateo NIIF.
- **Cabecera** — cuentas tipo header (`xx0000`) sin saldo propio.

### Medición contable (IFRS 9)

Cada cuenta tiene una de tres categorías:

- **FVTPL** (Fair Value Through Profit and Loss) — mark-to-market en resultados.
  Volatilidad pega directamente en P&L. Riesgo más alto bajo stress.
- **AC** (Amortized Cost) — costo amortizado, held-to-maturity.
  Sin volatilidad MtM. Mantiene valor nominal hasta vencimiento.
- **FVOCI** (Fair Value Through OCI) — mark-to-market en patrimonio (Otros Resultados Integrales).
  Volatilidad afecta capital pero no P&L del período.

La clasificación se hace por (a) keywords en denominación cuando completa, y
(b) sub-código según convención BCRA cuando la denominación está truncada:

| Sub-código | Medición típica |
|---|---|
| `xxx003`, `xxx024`, `xxx027`, `xxx041`, `xxx042`, `xxx056`, `xxx060`, `xxx092` | FVTPL |
| `xxx016`, `xxx026`, `xxx029`, `xxx057`, `xxx059`, `xxx061`, `xxx091` | AC |
| `xxx040`, `xxx043`–`xxx055`, `xxx058`, `xxx062`, `xxx093` | FVOCI |

`tests/test_accounting.test_titulos_clasificacion_cobertura_100pct` verifica
que el clasificador cubre el 100% de las cuentas reportadas.

---

## 5. Capítulos relevantes en moneda extranjera (ME)

Para la página `Crédito en Dólares`:

- `115xxx` — Efectivo + depósitos en bancos en ME (incluye encaje BCRA en ME)
- `125xxx`, `126xxx` — Títulos en ME
- `1351xx` — Préstamos ME al Sector Público no Financiero
- `1354xx` — Préstamos ME interbancarios domésticos
- `1357xx` — Préstamos ME al SPNF residentes país (canal de destino regulado)
- `136xxx` — Préstamos ME a residentes en el exterior
- `315xxx` — Depósitos ME residentes país (incluye CERA USD)
- `316xxx` — Depósitos ME residentes exterior

### Reconstrucción del valor original en USD

El BCRA reporta stocks ME en pesos al TC del cierre de cada mes; el panel
homogeneiza esos pesos por IPC al mes anchor (último IPC publicado). Para
recuperar el USD nativo:

```
USD = saldo_homogeneo · (IPC_t / IPC_anchor) / FX_t
```

donde `FX_t` es el TC mayorista A3500 promedio del mes-T.

Esta reconstrucción la hace `transforms.to_usd_native`. **Aplicar sólo a
cuentas ME** — usarla en cuentas en pesos da un resultado sin sentido.

---

## 6. Auditoría rutinaria

```bash
# Identidad contable + cobertura clasificador títulos
python scripts/audit_balance.py --all

# Tests automáticos (CI)
pytest tests/test_accounting.py -v
```

Si una auditoría falla:
1. Revisar `_flip_passive_signs` en `src/banks_arg_viz/io/loaders.py`.
2. Revisar el catálogo de `kpis/securities.py` si el problema es de cobertura de títulos.
3. Confirmar que el panel raw del paper repo no tenga corrupción (`scripts/sync_curated.py`).

---

## 7. Limitaciones conocidas

- **Tesoro nacional vs provincial**: el plan BCRA no distingue. Para una visión
  de exposición a deuda provincial específicamente, hay que recurrir a fuentes
  externas (BCRA boletín de estabilidad, MEP).
- **2 cuentas con medición no clasificada**: `121090` y `125090` ("Titulos publicos"
  genérico, sin sufijo de medición). Saldos chicos (~145 bn ARS, 0.18% del cap.12).
  Probablemente cuentas pre-IFRS preservadas por compatibilidad histórica.
- **`Resultado del ejercicio en curso`** vs `Patrimonio neto`: en períodos interim
  (mid-year), los resultados acumulados aún no se cierran a `RESULTADOS NO ASIGNADOS`.
  La identidad contable los suma como término separado. El dashboard muestra
  `Patrimonio neto = Σ(4xxxxx)` que excluye el resultado en curso.

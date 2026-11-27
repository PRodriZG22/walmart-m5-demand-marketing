# Paso 01 — ETL Eficiente en RAM e Ingeniería de Características (Cero Data Leakage)

## Objetivo

Construir el script `src/01_etl_features.py` para transformar los 3 archivos crudos de Kaggle M5 en conjuntos de datos limpios, optimizados en memoria (`.parquet`) y listos para modelado temporal a horizonte `H = 28` días sin ningún tipo de fuga de datos (*data leakage*).

---

## 1. Carga selectiva y recorte temprano (ahorro crítico de RAM)

Para mantener el consumo holgadamente dentro de los ~4.6 GB libres del equipo:

1. **Leer `calendar.csv` primero:**
   - Seleccionar únicamente: `["date", "wm_yr_wk", "wday", "month", "year", "d", "event_type_1", "snap_CA"]` (descartar explícitamente `snap_TX`, `snap_WI`, `event_name_1`, `event_name_2`, `event_type_2`, `weekday`).
   - Parsear `date` a `datetime64[ns]`.
   - Determinar dinámicamente desde `calendar.csv`:
     - Rango histórico con buffer: `2013-03-24` a `2016-05-22` (60 días de buffer + 3 años completos hasta `d_1941`).
     - Rango 3 años efectivos: `2013-05-23` a `2016-05-22`.
     - Rango futuro 28 días: `2016-05-23` a `2016-06-19` (`d_1942..d_1969`).
   - Imputar `event_type_1` nulo como `"No_Event"`.
2. **Leer `sales_train_evaluation.csv` solo con las columnas necesarias:**
   - Leer únicamente `["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]` más las columnas `d_*` del rango histórico con buffer (`2013-03-24` a `2016-05-22`).
   - Filtrar inmediatamente a `cat_id == "FOODS"` y `state_id == "CA"` (5,748 filas) y descartar `cat_id` y `state_id` tras verificar con `assert`.
   - Medir memoria antes del downcasting (`ram_before_mb`).
3. **Filtrar `sell_prices.csv` antes del `merge`:**
   - Leer únicamente filas cuyo `store_id` esté en `["CA_1", "CA_2", "CA_3", "CA_4"]` y cuyo `item_id` pertenezca al conjunto de los 1,437 ítems de `FOODS` (y `wm_yr_wk` dentro del rango buffer..futuro).
   - Convertir `sell_price` a `float32` y `wm_yr_wk` a `int16`.

---

## 2. Transformación Wide → Long, uniones y limpieza obligatoria

1. **Wide → Long (`pd.melt`):**
   - Convertir las 5,748 series históricas (con buffer de 60 días) a formato largo con columnas `id, item_id, dept_id, store_id, d, units_sold`.
   - Convertir `units_sold` a `int16` (o `float32` solo cuando se añada la cola futura con `NaN`).
2. **Construir grilla futura de 28 días (`d_1942..d_1969`):**
   - Producto cartesiano de las 5,748 series únicas (`id, item_id, dept_id, store_id`) × los 28 días futuros (`d_1942..d_1969`) con `units_sold = np.nan` y marcador booleano `is_future = True`.
   - Concatenar el histórico (con buffer) y los 28 días futuros para calcular rezagos y precios relativos de manera unificada y 100% libre de fuga.
3. **Uniones exactas:**
   - Unir con `calendar.csv` por `d` (`left`).
   - Unir con `sell_prices.csv` por `["store_id", "item_id", "wm_yr_wk"]` (`left`).
   - Liberar DataFrames intermedios (`del`, `gc.collect()`).
4. **Limpieza obligatoria y auditoría de calidad:**
   - **Pre-lanzamiento:** para cada `id`, identificar la primera fecha histórica con `sell_price.notna()` y **eliminar todos los días anteriores** a ese lanzamiento.
   - **Ceros reales:** conservar **todos** los días posteriores al lanzamiento donde `sell_price > 0` y `units_sold == 0` (demanda intermitente real).
   - **Precios en horizonte futuro / huecos aislados post-lanzamiento:** verificar si existe algún `sell_price` nulo después de la fecha de lanzamiento (especialmente en `d_1942..d_1969`); si existiera, aplicar `ffill()` estrictamente dentro del mismo `id` y registrar el conteo exacto en `etl_audit.json`.
   - **Controles con `assert` obligatorios:**
     - `0` duplicados en `(id, date)`.
     - `0` registros con `sell_price <= 0` o nulo post-limpieza.
     - `0` registros históricos con `units_sold < 0`.
   - **Downcasting de tipos:** `float32` para precios/medias/rezagos, `int16`/`int8` para conteos/calendario/códigos, `category` para identificadores de texto. Registrar memoria después del downcasting (`ram_after_mb`) y `%` de reducción de RAM.

---

## 3. Ingeniería de características (estrictamente sin *data leakage*)

Ordenar el DataFrame por `["id", "date"]` de forma ascendente antes de calcular cualquier operación temporal por grupo `id`:

| Variable | Definición exacta (sin fuga) | Tipo |
|---|---|---|
| `lag_28` | `units_sold.shift(28)` por `id` | `float32` |
| `lag_35` | `units_sold.shift(35)` por `id` | `float32` |
| `lag_56` | `units_sold.shift(56)` por `id` | `float32` |
| `rolling_mean_7` | Media móvil de 7 días de `units_sold.shift(28)` (`t-34..t-28`, `min_periods=7`) | `float32` |
| `rolling_mean_28` | Media móvil de 28 días de `units_sold.shift(28)` (`t-55..t-28`, `min_periods=28`) | `float32` |
| `sell_price` | Precio vigente de venta de la semana `wm_yr_wk` | `float32` |
| `price_change` | Variación porcentual semanal vs `t-7`: `(sell_price - sell_price.shift(7)) / sell_price.shift(7)` (0.0 si no hay `t-7`) | `float32` |
| `relative_price` | `sell_price / expanding_mean(sell_price)` histórico acumulado hasta `t` por `id` (nunca usa precios `> t`) | `float32` |
| `wday` | Día de la semana M5 (`1..7`) | `int8` |
| `month` | Mes calendario (`1..12`) | `int8` |
| `year` | Año calendario (`2013..2016`) | `int16` |
| `event_type_1_code` | Código entero determinístico de `event_type_1` (`"No_Event"` incluido) | `int8` |
| `snap_CA` | Indicador binario de pago SNAP en California (`0` o `1`) | `int8` |
| `item_code` | Código entero determinístico de `item_id` (ordenado alfabéticamente) | `int16` |
| `dept_code` | Código entero determinístico de `dept_id` (`FOODS_1..3`) | `int8` |
| `store_code` | Código entero determinístico de `store_id` (`CA_1..CA_4`) | `int8` |

> **Nota técnica:** Gracias a que todos los rezagos y medias móviles de ventas parten de `t-28` o antes, el horizonte futuro de 28 días (`d_1942..d_1969`) solo necesita ventas observadas hasta `d_1941` (`1969 - 28 = 1941`), permitiendo pronóstico directo sin propagación recursiva de errores.

---

## 4. Recorte final, prueba anti-fuga y persistencia

1. **Separación de datasets:**
   - **`data/processed/active_sales_3y.parquet`**: todos los días activos reales dentro de la ventana de 3 años (`2013-05-23` a `2016-05-22`, sin el buffer previo y sin días pre-lanzamiento). Contiene `id, item_id, dept_id, store_id, d, date, units_sold, sell_price, relative_price, snap_CA, wday, month, year, event_type_1`. Se usa como base exacta para diagnósticos comerciales, intermitencia, sensibilidad y denominadores de RMSSE.
   - **`data/processed/features_3y.parquet`**: días de la ventana de 3 años (`2013-05-23` a `2016-05-22`) que cuentan con las variables de rezago completas (`lag_56` no nulo; los primeros 56 días de productos lanzados después de `2013-03-24` se descartan del set de entrenamiento y se reporta su conteo exacto en `etl_audit.json`).
   - **`data/processed/future_28d_features.parquet`**: los 28 días futuros (`d_1942..d_1969`, `2016-05-23` a `2016-06-19`) para las 5,748 series (`160,944` filas exactas), con todas las features calculadas sin fuga. Verificar que no existan `NaN` en las features de modelado (si un producto recién lanzado en los últimos 56 días tuviera algún rezago `NaN` en futuro, imputarlo con `0.0` y documentar cuántos registros afectó).
2. **Guardar codificadores (`data/processed/encoders.json`):**
   - Mapas exactos `item_code`, `dept_code`, `store_code` y `event_type_1_code`.
3. **Prueba automatizada anti-leakage (obligatoria antes de terminar):**
   - Seleccionar aleatoriamente (con `seed=42`) 200 registros de `features_3y.parquet` y validar mediante `assert` que:
     - `lag_28` en fecha `t` es **exactamente igual** a `units_sold` del mismo `id` en fecha `t - 28 días` en `active_sales_3y.parquet` (o historial con buffer).
     - `rolling_mean_7` en fecha `t` coincide (`np.isclose`) con el promedio de `units_sold` en `[t-34, t-28]`.
     - `relative_price` en fecha `t` coincide con `sell_price[t] / mean(sell_price[<= t])`.
4. **Auditoría ETL (`outputs/metrics/etl_audit.json`):**
   - Filas brutas vs filas post-limpieza (pre-lanzamiento eliminado).
   - Memoria RAM antes y después del downcasting (`ram_before_mb`, `ram_after_mb`, `ram_reduction_pct`).
   - Porcentaje real de ceros (`units_sold == 0`) sobre días activos de 3 años.
   - Conteo de series únicas en cada parquet (confirmar `5,748`), conteos de `features_3y` y `future_28d_features`, y resultado `PASS` de todas las pruebas anti-leakage.

---

## Criterio de finalización del Paso 01

- Generados y verificados:
  - `data/processed/active_sales_3y.parquet`
  - `data/processed/features_3y.parquet`
  - `data/processed/future_28d_features.parquet`
  - `data/processed/encoders.json`
  - `outputs/metrics/etl_audit.json`
- Cero fallas en las aserciones de duplicados, precios, valores negativos y auditoría anti-leakage.

# AGENTS.md — Reglas Maestras del Proyecto Walmart M5 Demand & Marketing

Este documento define las reglas obligatorias de alcance, veracidad metodológica, prevención de *data leakage*, control de memoria RAM y ejecución secuencial que deben cumplirse en todas las fases (`plan/00` a `plan/05`).

---

## 1. Alcance 100% real del dataset Kaggle M5

- **Archivos fuente permitidos (`data/raw/`):**
  - `sales_train_evaluation.csv` (ventas diarias hasta `d_1941` = `2016-05-22`)
  - `calendar.csv` (calendario completo hasta `d_1969` = `2016-06-19`)
  - `sell_prices.csv` (precios semanales por `store_id`, `item_id`, `wm_yr_wk`)
- **Filtro geográfico y de categoría obligatorio:**
  - `cat_id == "FOODS"` (departamentos `FOODS_1`, `FOODS_2`, `FOODS_3`)
  - `state_id == "CA"` (tiendas `CA_1`, `CA_2`, `CA_3`, `CA_4`)
  - Exactamente **1,437 productos × 4 tiendas = 5,748 series producto-tienda**.
- **Ventana histórica exacta:**
  - **3 años completos** de historia para modelado y diagnóstico: **`2013-05-23` a `2016-05-22`** (`d_846` a `d_1941`, 1,096 días incluyendo año bisiesto 2016).
  - **Buffer previo de 60 días** (`2013-03-24` a `2013-05-22`, `d_786` a `d_845`) cargado exclusivamente para calcular los rezagos y medias móviles iniciales sin generar valores `NaN` al inicio de la ventana de 3 años.
  - **Horizonte futuro de pronóstico:** 28 días calendario posteriores al cierre real (`d_1942` a `d_1969`, **`2016-05-23` a `2016-06-19`**).

---

## 2. Veracidad estricta y transparencia de datos

- **Prohibido inventar o simular variables ausentes en M5.** El dataset M5 **NO contiene**:
  - Stock físico en góndola o almacén,
  - Costo unitario de adquisición ni margen bruto real,
  - Fechas de vencimiento o merma física observada,
  - Identificadores de clientes, tickets o canastas de compra.
- Todo diagnóstico, KPI, modelo y recomendación prescriptiva debe sustentarse exclusivamente en las variables reales disponibles: unidades vendidas (`units_sold`), precio de venta (`sell_price`), calendario/eventos (`wday`, `month`, `year`, `event_type_1`) y beneficio gubernamental (`snap_CA`).
- El impacto económico se cuantifica rigurosamente como **Ingreso en Riesgo (USD)** a partir de la caída proyectada de ventas respecto al ritmo reciente (`v90` vs `pred_v28`) multiplicada por el precio vigente (`current_price`).
- **Cero cifras ficticias o pre-llenadas:** ningún número de resultados, métricas, porcentajes o montos puede ser hardcodeado. Toda cifra presentada en tablas, gráficos, dashboard o texto académico debe provenir de la ejecución real y auditable de los scripts.

---

## 3. Política de cero *data leakage*

- **Horizonte de pronóstico:** `H = 28` días.
- **Rezagos y medias móviles de ventas:** toda característica derivada de `units_sold` en el día `t` debe utilizar estrictamente información de **`t - 28` o anterior** (`lag_28`, `lag_35`, `lag_56`, `rolling_mean_7` desde `t-28`, `rolling_mean_28` desde `t-28`). Nunca usar `lag_1..lag_27` ni ventanas centradas.
- **Partición 100% temporal:** prohibido usar `train_test_split` aleatorio o K-Fold aleatorio. La validación debe realizarse por origen rodante estrictamente cronológico (4 ventanas consecutivas de 28 días sobre `d_1830..d_1941`).
- **Precios relativos sin fuga:** `relative_price` se calcula como `sell_price / expanding_mean_price` histórico pasado acumulado por SKU-tienda hasta el día `t` (sin incluir jamás precios futuros posteriores a `t`).
- **Preprocesamiento de baselines y modelos:** cualquier parámetro (como `alpha` de SES o escaladores) se ajusta únicamente con datos previos al inicio de la ventana evaluada.

---

## 4. Control estricto de memoria RAM y CPU

Hardware objetivo verificado: **Windows, Python 3.14.3 (64-bit), 16 GB RAM totales (~4.6 GB libres actuales), Intel Core i7-1255U (10 núcleos / 12 hilos)**.

- **Filtrar antes de transformar:** recortar `sales_train_evaluation.csv` a `FOODS` + `CA` y únicamente a las columnas de días necesarias (`d_786..d_1941`) antes de ejecutar `pd.melt`. Filtrar `sell_prices.csv` por `CA_1..CA_4` e ítems de `FOODS` antes del `merge`.
- **Downcasting inmediato:** convertir columnas numéricas y categóricas apenas se crean (`float32`, `int16`, `int8`, `category`).
- **Arreglos contiguos para `scikit-learn`:** convertir las matrices de entrenamiento `X_train` con `np.asfortranarray(..., dtype=np.float32)` y `y_train` a `float32` antes de `.fit()` para evitar copias duplicadas en memoria dentro del constructor de árboles.
- **Persistencia columnar eficiente:** almacenar todas las tablas intermedias en `.parquet` con `pyarrow` (nunca CSV para tablas de millones de filas).
- **Liberación explícita:** usar `del` sobre DataFrames/arrays temporales y llamar a `gc.collect()` entre etapas de ETL y entre cada una de las 4 ventanas rodantes de validación.
- **Hiperparámetros conservadores obligatorios (`RF_PARAMS`):**
  ```python
  RF_PARAMS = {
      "n_estimators": 100,
      "max_depth": 16,
      "min_samples_leaf": 25,
      "max_samples": 0.30,
      "max_features": "sqrt",
      "random_state": 42,
      "n_jobs": 6,
  }
  ```
  - **Nunca usar `n_jobs=-1`** en este equipo para evitar picos de RAM y *thermal throttling* en el i7-1255U.
- **Compatibilidad Python 3.14.3:** NO instalar ni depender de `statsmodels`. Implementar SES de forma vectorizada con `numpy`.

---

## 5. Ejecución estrictamente secuencial y auditoría

1. Ejecutar estrictamente en orden: **`00` → `01` → `02` → `03` → `04` → `05`**.
2. Cada script debe terminar imprimiendo un resumen claro de validación y escribiendo sus archivos de auditoría/salidas en `outputs/` y `data/processed/`.
3. No pasar al siguiente paso si existe algún error de integridad, fuga detectada, inconsistencia de conteos (`1,437` productos / `5,748` series) o falla de memoria.
4. En el Paso 02, ejecutar primero el modo `--fast-dev` (300 series) para verificar el flujo completo, las métricas y el consumo de RAM antes de lanzar la corrida completa sobre las 5,748 series.
5. **Sistema de diseño UI:** Antes de realizar cualquier cambio de interfaz o estilos en `app/dashboard.py`, leer y respetar estrictamente los tokens, reglas tipográficas y principios de `DESIGN.md`.

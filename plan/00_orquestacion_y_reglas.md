# Paso 00 — Orquestación, Entorno Virtual, Configuración y Verificación de Datos

## Objetivo

Preparar un entorno Python reproducible calibrado para **Python 3.14.3** y **16 GB RAM (~4.6 GB libres)**, centralizar todas las constantes del proyecto en `src/config.py`, y verificar la integridad exacta de los 3 archivos CSV crudos de Kaggle M5 antes de iniciar el ETL.

---

## 1. Creación de `requirements.txt`

Crear `requirements.txt` en la raíz del proyecto con las librerías estrictamente necesarias y compatibles con Python 3.14.3:

```text
pandas
numpy
scikit-learn
pyarrow
matplotlib
seaborn
plotly
streamlit
joblib
```

> **Regla de compatibilidad Python 3.14.3:** NO incluir `statsmodels` para evitar errores de compilación C/Cython por falta de *wheels* binarios. El baseline de Suavizado Exponencial Simple (SES) del Paso 02 se implementará de forma vectorizada en `numpy`.

---

## 2. Entorno virtual `.venv` e instalación controlada

Ejecutar en PowerShell desde la raíz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Protocolo de fallo:** Si cualquier paquete de `requirements.txt` falla al instalarse por falta de *wheel* precompilado para Python 3.14.3 (intento de compilación desde fuente que falle), **detener inmediatamente**, reportar el paquete exacto y el error, y proponer la solución (versión alternativa, `--only-binary=:all:` o versión de Python compatible) antes de continuar.

---

## 3. Creación de `src/config.py`

Crear `src/config.py` usando `pathlib.Path` para garantizar portabilidad y una única fuente de verdad para todo el pipeline:

- **Rutas principales:**
  - `PROJECT_ROOT = Path(__file__).resolve().parent.parent`
  - `DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"`
  - `DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"`
  - `OUTPUTS_DIR = PROJECT_ROOT / "outputs"`
  - `METRICS_DIR = OUTPUTS_DIR / "metrics"`
  - `TABLES_DIR = OUTPUTS_DIR / "tables"`
  - `FIGURES_DIR = OUTPUTS_DIR / "figures"`
  - `DOCS_DIR = PROJECT_ROOT / "docs"`
- **Archivos crudos esperados:**
  - `SALES_RAW_PATH = DATA_RAW_DIR / "sales_train_evaluation.csv"`
  - `CALENDAR_RAW_PATH = DATA_RAW_DIR / "calendar.csv"`
  - `PRICES_RAW_PATH = DATA_RAW_DIR / "sell_prices.csv"`
- **Constantes de alcance y modelado:**
  - `TARGET_CATEGORY = "FOODS"`
  - `TARGET_STATE = "CA"`
  - `STORES = ["CA_1", "CA_2", "CA_3", "CA_4"]`
  - `HORIZON = 28`
  - `NUM_ROLLING_WINDOWS = 4`
  - `YEARS_HISTORY = 3`
  - `LAG_BUFFER_DAYS = 60`
  - `RANDOM_SEED = 42`
  - `EXPECTED_ITEMS = 1437`
  - `EXPECTED_SERIES = 5748`
- **Umbrales de riesgo y marketing:**
  - `DECLINE_HIGH = 30.0`
  - `DECLINE_MED = 10.0`
  - `INTERMITTENCY_HIGH = 70.0`
  - `INTERMITTENCY_MED = 40.0`
  - `REVENUE_TOP_QUANTILE = 0.80`
  - `PRICE_PROMO_THRESHOLD = 0.95`
  - `PRICE_SENSITIVITY_MIN = 0.10`
  - `PRICE_PROMO_MIN_DAYS = 7`
  - `SNAP_SENSITIVITY_MIN = 0.10`
  - `SNAP_PRIORITY_THRESHOLD = 0.15`
- **Hiperparámetros de Random Forest (calibrados para i7-1255U + 16 GB RAM / ~4.6 GB libres):**
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
- Incluir una función auxiliar `ensure_directories()` que asegure que existen `DATA_PROCESSED_DIR`, `METRICS_DIR`, `TABLES_DIR` y `FIGURES_DIR`.

---

## 4. Script de verificación `src/00_verify_data.py`

Crear y ejecutar `src/00_verify_data.py` con el Python del `.venv` para validar:

1. Existencia y tamaño (MB) de los 3 archivos en `data/raw/`:
   - `sales_train_evaluation.csv`
   - `calendar.csv`
   - `sell_prices.csv`
2. Integridad de `calendar.csv`:
   - Confirmar que contiene `d_1` a `d_1969`.
   - Confirmar exactamente que `d_1941` corresponde a `2016-05-22` y `d_1969` corresponde a `2016-06-19`.
   - Confirmar existencia de columnas `date`, `wm_yr_wk`, `wday`, `month`, `year`, `d`, `event_type_1`, `snap_CA`.
   - Identificar los `d_*` exactos que delimitan:
     - Buffer 60 días (`2013-03-24` a `2013-05-22`)
     - Ventana 3 años (`2013-05-23` a `2016-05-22`)
     - 4 ventanas rodantes de validación (`d_1830..d_1941`, 112 días)
     - Horizonte futuro de pronóstico (`d_1942..d_1969`, 28 días)
3. Integridad de `sales_train_evaluation.csv` (leyendo únicamente metadatos `id, item_id, dept_id, cat_id, store_id, state_id` y encabezados para ahorrar RAM):
   - Confirmar presencia de columnas `d_1` hasta `d_1941`.
   - Filtrar `cat_id == "FOODS"` y `state_id == "CA"` y verificar mediante `assert`:
     - Exactamente **1,437 productos únicos** (`item_id`).
     - Exactamente **4 tiendas** (`CA_1`, `CA_2`, `CA_3`, `CA_4`).
     - Exactamente **5,748 series producto-tienda** (`id`).
   - Desglose de conteo de series por tienda y departamento (`FOODS_1`, `FOODS_2`, `FOODS_3`).
4. Integridad de `sell_prices.csv`:
   - Verificar columnas `store_id`, `item_id`, `wm_yr_wk`, `sell_price`.
   - Verificar cobertura de precios para las tiendas `CA_1..CA_4`, los 1,437 ítems de `FOODS` y las semanas `wm_yr_wk` correspondientes al rango histórico y futuro (`d_1942..d_1969`).
5. Persistir resultados de la verificación en `outputs/metrics/data_verification.json` (versiones de Python y librerías instaladas, conteos exactos, fechas clave y estado `PASS`).

---

## Criterio de finalización del Paso 00

- `.venv` operativo con todas las dependencias de `requirements.txt` instaladas sin errores.
- `src/config.py` creado e importable sin errores.
- `src/00_verify_data.py` ejecutado con salida `0` y `outputs/metrics/data_verification.json` generado confirmando `1,437` productos, `5,748` series, `d_1941 = 2016-05-22` y `d_1969 = 2016-06-19`.

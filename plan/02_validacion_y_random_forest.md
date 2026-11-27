# Paso 02 — Validación Temporal Rodante, Baselines y Random Forest

## Objetivo

Construir y ejecutar `src/02_train_validate.py` para evaluar rigurosamente `RandomForestRegressor` frente a 3 modelos baseline mediante validación temporal por origen rodante (4 ventanas consecutivas de 28 días), reportar MAE, RMSE y **RMSSE oficial de M5**, entrenar el modelo final con el historial completo hasta `d_1941`, generar el pronóstico futuro de 28 días (`d_1942..d_1969`) y exportar las figuras `fig01` a `fig04`.

---

## 1. Modo de desarrollo rápido (`--fast-dev`) vs ejecución completa

El script `src/02_train_validate.py` debe soportar el argumento CLI `--fast-dev`:
- **`--fast-dev`**: selecciona una muestra estratificada de **300 series** (75 por tienda `CA_1..CA_4`, semilla `42`) y ejecuta todo el flujo de 4 ventanas + baselines + métricas sin sobrescribir los artefactos definitivos (o marcándolos en modo prueba) para verificar integridad, tiempos de cómputo y pico de RAM antes de la corrida completa.
- **Ejecución completa (sin bandera):** corre sobre las **5,748 series** completas y genera todos los artefactos definitivos en `data/processed/` y `outputs/`.

---

## 2. Esquema de validación por origen rodante (últimos 112 días: `d_1830..d_1941`)

Evaluar 4 ventanas consecutivas de 28 días sin solapamiento (febrero–mayo 2016):

| Ventana | Días de prueba (`d`) | Fechas de prueba | Entrenamiento permitido |
|---|---|---|---|
| **Ventana 1** | `d_1830..d_1857` | `2016-02-01` a `2016-02-28` | Estrictamente `<= d_1829` (`<= 2016-01-31`) |
| **Ventana 2** | `d_1858..d_1885` | `2016-02-29` a `2016-03-27` | Estrictamente `<= d_1857` (`<= 2016-02-28`) |
| **Ventana 3** | `d_1886..d_1913` | `2016-03-28` a `2016-04-24` | Estrictamente `<= d_1885` (`<= 2016-03-27`) |
| **Ventana 4** | `d_1914..d_1941` | `2016-04-25` a `2016-05-22` | Estrictamente `<= d_1913` (`<= 2016-04-24`) |

> **Gestión obligatoria de RAM entre ventanas:** al terminar cada ventana, eliminar `X_train`, `y_train`, `X_val`, el modelo `rf` y ejecutar `gc.collect()` antes de iniciar la siguiente ventana. Convertir `X_train` con `np.asfortranarray(X_train, dtype=np.float32)` para evitar copias internas innecesarias en `scikit-learn`.

---

## 3. Modelos comparados

Todos los pronósticos se truncan en cero (`np.clip(y_pred, 0.0, None)`) porque la demanda no puede ser negativa:

1. **Random Forest (`RandomForestRegressor`):**
   - Hiperparámetros exactos de `src/config.py`:
     `RF_PARAMS = {"n_estimators": 100, "max_depth": 16, "min_samples_leaf": 25, "max_samples": 0.30, "max_features": "sqrt", "random_state": 42, "n_jobs": 6}`
   - Features (16 variables): `lag_28`, `lag_35`, `lag_56`, `rolling_mean_7`, `rolling_mean_28`, `sell_price`, `price_change`, `relative_price`, `wday`, `month`, `year`, `event_type_1_code`, `snap_CA`, `item_code`, `dept_code`, `store_code`.
2. **Baseline 1 — Promedio Móvil 28 días (`MA28`):**
   - Pronóstico plano igual al promedio diario de ventas observadas en los últimos 28 días estrictamente anteriores al inicio de la ventana (`t_cutoff - 27 .. t_cutoff`).
3. **Baseline 2 — Seasonal Naïve (`lag_28`):**
   - Pronóstico igual al valor real observado exactamente 28 días antes (`y_{t - 28}`), capturando estacionalidad semanal (mismo día de la semana).
4. **Baseline 3 — Suavizado Exponencial Simple (`SES`, vectorizado en `numpy`):**
   - Implementación 100% en `numpy` (sin `statsmodels`) sobre la matriz `(N_series, T_train)` del historial activo previo al corte:
     $$\ell_t = \alpha y_t + (1 - \alpha)\ell_{t-1}, \quad \hat{y}_{T+1..T+28} = \ell_T$$
   - Evaluar una grilla de $\alpha \in \{0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50\}$ minimizando el error cuadrático un paso adelante sobre el periodo de entrenamiento de cada serie (o el global óptimo documentado en `outputs/metrics/validation_audit.json`), usando exclusivamente datos `<= t_cutoff`.

---

## 4. Métricas oficiales de evaluación

Calcular para cada modelo, en cada una de las 4 ventanas y en el promedio general:

- **MAE:** $\frac{1}{N} \sum |y - \hat{y}|$
- **RMSE:** $\sqrt{\frac{1}{N} \sum (y - \hat{y})^2}$
- **RMSSE oficial de M5 (por serie y promediado sobre las series evaluables):**
  $$\text{RMSSE}_i = \sqrt{\frac{\frac{1}{h} \sum_{t=n+1}^{n+h} (Y_{i,t} - \hat{Y}_{i,t})^2}{\frac{1}{n - t_0} \sum_{t=t_0+1}^{n} (Y_{i,t} - Y_{i,t-1})^2}}$$
  donde $h = 28$ y $t_0$ es el primer día con demanda distinta de cero en el periodo activo previo a la ventana (`<= n`). Documentar y proteger contra división por cero si alguna serie tuvo ventas exclusivamente cero antes de una ventana.
- **Desglose obligatorio de Random Forest (promedio 4 ventanas y Ventana 4):**
  - Por tienda (`CA_1`, `CA_2`, `CA_3`, `CA_4`)
  - Por departamento (`FOODS_1`, `FOODS_2`, `FOODS_3`)
  - Por condición SNAP (`snap_CA == 1` vs `snap_CA == 0`)

---

## 5. Modelo final y pronóstico futuro (`d_1942..d_1969`)

1. Entrenar un `RandomForestRegressor(**RF_PARAMS)` final utilizando **todo** `features_3y.parquet` (hasta `d_1941` = `2016-05-22`).
2. Predecir sobre `data/processed/future_28d_features.parquet` (`d_1942..d_1969`, 160,944 filas), aplicando `np.clip(pred, 0.0, None)`.
3. Extraer `feature_importances_` del modelo final.
4. No es obligatorio guardar el `.joblib` en Git (está en `.gitignore`), pero sí se puede guardar localmente si se desea o liberar tras exportar predicciones e importancias para conservar disco/RAM.

---

## 6. Salidas obligatorias del Paso 02

### Tablas y datos procesados
- `data/processed/val_window4_predictions.parquet` (predicciones de RF y baselines en Ventana 4: `d_1914..d_1941` para el dashboard).
- `data/processed/forecast_28d.parquet` (pronóstico futuro 28 días `d_1942..d_1969` con `id, item_id, dept_id, store_id, d, date, sell_price, snap_CA, pred_units`).
- `outputs/tables/validation_metrics_by_window.csv`
- `outputs/tables/validation_metrics_summary.csv`
- `outputs/tables/validation_breakdown_store_snap.csv`
- `outputs/tables/feature_importance.csv`
- `outputs/metrics/validation_audit.json` (tiempos, pico de RAM aproximado, `alpha` SES y resumen clave).

### Figuras académicas (PNG a 300 DPI en `outputs/figures/`)
1. `fig01_validation_metrics_comparison.png` — Comparación de Random Forest vs MA28, Seasonal Naïve y SES en MAE, RMSE y RMSSE (promedio y por ventana).
2. `fig02_rmsse_store_snap_breakdown.png` — Desglose de RMSSE de Random Forest por tienda (`CA_1..CA_4`), departamento (`FOODS_1..3`) y días `snap_CA = 1` vs `0`.
3. `fig03_feature_importance_rf.png` — Ranking de importancia de variables (`feature_importances_`) del Random Forest final.
4. `fig04_actual_vs_forecast_examples.png` — Series de tiempo reales vs predichas (Ventana 4 + pronóstico 28 días) para 3 casos representativos (alta rotación, demanda intermitente y alta sensibilidad SNAP).

---

## Criterio de finalización del Paso 02

- Corrida `--fast-dev` exitosa y sin alertas de RAM.
- Corrida completa sobre las 5,748 series finalizada con todos los `.parquet`, `.csv`, `.json` y `fig01`–`fig04` generados y verificados.

# Paso 03 — Diagnóstico Comercial, Segmentación K-Means y Motor Prescriptivo de Marketing

## Objetivo

Construir y ejecutar `src/03_diagnosis_kmeans_marketing.py` sobre las **5,748 series producto-tienda** (`FOODS` en `CA_1..CA_4`) para cuantificar el riesgo comercial en **Ingreso en Riesgo (USD)**, segmentar el portafolio mediante **K-Means** validado empíricamente y asignar recomendaciones prescriptivas de marketing alineadas a las 3 líneas estratégicas del informe.

---

## 1. Indicadores comerciales reales (cero variables simuladas)

Combinar `data/processed/active_sales_3y.parquet` y `data/processed/forecast_28d.parquet` para calcular por cada `id` (`item_id`, `dept_id`, `store_id`):

1. **`sales_velocity_28d`**: promedio diario real de `units_sold` en los últimos 28 días observados (`d_1914..d_1941`).
2. **`sales_velocity_90d` (`v90`)**: promedio diario real de `units_sold` en los últimos 90 días activos (`d_1852..d_1941`).
3. **`pred_velocity_28d` (`pred_v28`)**: promedio diario pronosticado de `pred_units` en los próximos 28 días (`d_1942..d_1969`).
4. **`current_price`**: último `sell_price` vigente del SKU-tienda (cierre en `d_1941` o inicio de `d_1942`).
5. **`intermittency_pct`**: porcentaje de días con `units_sold == 0` sobre el total de días activos (`sell_price > 0`) en el historial de 3 años (`active_sales_3y.parquet`). *(Guardar también `intermittency_90d_pct` como columna informativa complementaria).*
6. **`projected_decline_pct`**:
   $$\text{projected\_decline\_pct} = \max\left(0,\; \frac{v_{90} - \text{pred\_v}_{28}}{v_{90}} \times 100\right)$$
   *(Si $v_{90} == 0$, asignar `0.0`).*
7. **`revenue_at_risk_usd`**:
   $$\text{revenue\_at\_risk\_usd} = \max\left(0,\; 28 \times (v_{90} - \text{pred\_v}_{28})\right) \times \text{current\_price}$$
8. **`price_sensitivity`**:
   - Comparar el promedio diario de ventas en días con rebaja (`relative_price < 0.95`) frente a días con precio normal (`relative_price >= 0.95`):
     $$\text{price\_sensitivity} = \frac{\bar{y}_{\text{promo}} - \bar{y}_{\text{normal}}}{\bar{y}_{\text{normal}}}$$
   - Requerir un mínimo de **7 días** en condición de rebaja (`PRICE_PROMO_MIN_DAYS = 7`) y $\bar{y}_{\text{normal}} > 0$. Si no cumple este mínimo, marcar `has_promo_history = False` y dejar `price_sensitivity = NaN` (sin imputar elasticidad falsa para markdowns).
9. **`snap_sensitivity`**:
   - Comparar el promedio diario de ventas en días `snap_CA == 1` frente a `snap_CA == 0` sobre los días activos del historial:
     $$\text{snap\_sensitivity} = \frac{\bar{y}_{\text{SNAP}=1} - \bar{y}_{\text{SNAP}=0}}{\bar{y}_{\text{SNAP}=0}}$$
   - Si $\bar{y}_{\text{SNAP}=0} == 0$, asignar `0.0`.

---

## 2. Clasificación de niveles de riesgo comercial

Aplicar las reglas exactas usando las constantes de `src/config.py`:

- **Riesgo Alto:**
  - `projected_decline_pct >= 30.0` **OR**
  - (`intermittency_pct >= 70.0` **AND** `revenue_at_risk_usd > 0` **AND** `revenue_at_risk_usd >= Q80_tienda`), donde `Q80_tienda` es el percentil 80 (`REVENUE_TOP_QUANTILE = 0.80`) de `revenue_at_risk_usd` dentro del mismo `store_id`.
- **Riesgo Medio:**
  - No es Riesgo Alto **AND** (`10.0 <= projected_decline_pct < 30.0` **OR** `40.0 <= intermittency_pct < 70.0`).
- **Riesgo Bajo:**
  - Todos los demás registros.

---

> **Avisos de presentación (no cambian la regla):** el tablero marca «Casi sin ventas» a las series de riesgo bajo con intermitencia de 70% o más, y «Alerta sin monto en riesgo» a las de riesgo alto o medio con ingreso en riesgo 0.

---

## 3. Segmentación no supervisada K-Means

1. **Variables de entrada al clustering:**
   - `sales_velocity_28d`, `intermittency_pct`, `projected_decline_pct`, `revenue_at_risk_usd`, `snap_sensitivity` y `price_sensitivity` (usando una copia temporal con `NaN -> 0.0` solo para la matriz de clustering, preservando `NaN` en la tabla diagnóstica real).
2. **Preprocesamiento controlado:**
   - Aplicar winsorización documentada al percentil 99 (`p99`, y `p01` para sensibilidades con valores negativos) **únicamente para el cálculo de distancias de K-Means** para evitar que outliers extremos distorsionen los centroides; nunca alterar los indicadores originales reportados.
   - Estandarizar con `StandardScaler`.
3. **Evaluación de `K = 2..6`:**
   - Ajustar `KMeans(n_clusters=k, n_init=20, random_state=42)` para $k \in \{2, 3, 4, 5, 6\}$.
   - Calcular y guardar en `outputs/tables/kmeans_evaluation.csv` la inercia **WCSS (Método del Codo)** y el **Coeficiente de Silueta**.
   - Seleccionar el `K` óptimo con mejor balance entre Coeficiente de Silueta, codo de WCSS e interpretabilidad comercial (documentando la decisión en `outputs/metrics/diagnosis_audit.json`).
4. **Perfilado y etiquetado empírico:**
   - Calcular los centroides reales en escala original (media y mediana por clúster) en `outputs/tables/kmeans_cluster_profiles.csv`.
   - Asignar nombres comerciales descriptivos a cada clúster estrictamente en función de sus centroides reales observados.

---

## 4. Motor prescriptivo de marketing (3 líneas estratégicas + EDLP)

Asignar a cada una de las 5,748 series su estrategia principal, capa SNAP y acciones operativas concretas:

1. **Línea 1 — Precios Dinámicos / Markdown 20%–35%:**
   - **Condición:** `risk_level` en `["Riesgo Alto", "Riesgo Medio"]` **AND** `has_promo_history == True` **AND** `price_sensitivity >= 0.10` (`PRICE_SENSITIVITY_MIN`).
   - **Acción:** Sugerir banda de descuento calibrada según severidad (`25%–35%` en Riesgo Alto; `20%–25%` en Riesgo Medio), acompañar con **migración operativa LEFO → FEFO** y activar bandera `stockpiling_alert = True` (**reducir reposición post-promoción entre -20% y -30%** para evitar rebote de sobreinventario por acaparamiento).
2. **Línea 2 — Cross-Selling y Visibilidad Omnicanal (sin descuento):**
   - **Condición:** `risk_level` en `["Riesgo Alto", "Riesgo Medio"]` **AND** inelástico al precio (`price_sensitivity < 0.10` o `has_promo_history == False`).
   - **Acción:** Evitar erosión innecesaria de margen con descuentos; ejecutar exhibición conjunta, *bundling* y visibilidad omnicanal. Asignar automáticamente un **`suggested_anchor_item`** seleccionando un producto de **Riesgo Bajo** y alta rotación (`sales_velocity_28d` en el top del grupo, distinto al SKU evaluado) dentro del **mismo `store_id` y `dept_id`**.
3. **Línea 3 — Prioridad SNAP (Sincronización Bifásica):**
   - **Condición:** `snap_sensitivity >= 0.15` (`SNAP_PRIORITY_THRESHOLD`). (Registrar también `snap_sensitive_flag` con `>= 0.10` para análisis exploratorio).
   - **Acción bifásica (`snap_priority_flag = True` y `snap_action`):**
     - **Días 1–10 del mes (ciclo de abono SNAP CA):** encartes destacados, multipacks familiares y refuerzo preventivo de reposición/stock en góndola.
     - **Días 20–31 del mes (cierre de presupuesto):** cupones dirigidos de fin de mes específicamente para los SKUs en Riesgo Alto o Medio.
   - Si un SKU en Riesgo Bajo tiene `snap_sensitivity >= 0.15`, mantener política base EDLP pero activar sincronización de inventario/encartes SNAP en Días 1–10.
4. **Mantenimiento EDLP y Producto Ancla:**
   - **Condición:** `risk_level == "Riesgo Bajo"` (y sin prioridad SNAP especial o como base de precio).
   - **Acción:** Preservar estrategia *Everyday Low Price* (EDLP) sin descuentos agresivos y habilitar como candidato a producto ancla para cross-selling.

---

## 5. Salidas obligatorias del Paso 03

### Tablas (`outputs/tables/`)
- `sku_store_diagnosis.csv` (tabla maestra de 5,748 filas con todos los indicadores, nivel de riesgo, clúster K-Means, estrategia, `suggested_anchor_item`, `snap_priority_flag`, `stockpiling_alert` y acción detallada).
- `risk_summary_by_store_dept.csv` (conteos, % de portafolio e Ingreso en Riesgo USD agregados por tienda, departamento y nivel de riesgo).
- `kmeans_evaluation.csv` (WCSS y Silueta para `K = 2..6`).
- `kmeans_cluster_profiles.csv` (centroides reales por clúster, tamaño, % e Ingreso en Riesgo USD).
- `top_50_priority_promotions.csv` (Top 50 SKUs prioritarios ordenados por `revenue_at_risk_usd` descendente con recomendación completa).
- `outputs/metrics/diagnosis_audit.json` (resumen ejecutivo de cifras clave, umbrales, K seleccionado y validaciones).

### Figuras académicas (PNG a 300 DPI en `outputs/figures/`)
5. `fig05_risk_distribution_store_dept.png` — Distribución de niveles de riesgo e Ingreso en Riesgo (USD) por tienda (`CA_1..CA_4`) y departamento (`FOODS_1..3`).
6. `fig06_kmeans_elbow_silhouette.png` — Curva del Método del Codo (WCSS) y Coeficiente de Silueta para `K = 2..6`.
7. `fig07_kmeans_cluster_profiles.png` — Mapa de calor / perfil normalizado y de centroides reales de los clústeres K-Means seleccionados.
8. `fig08_prescriptive_marketing_revenue_risk.png` — Ingreso en Riesgo (USD) y número de SKUs cubiertos por cada estrategia prescriptiva (Markdown, Cross-Selling, Prioridad SNAP y EDLP).

---

## Criterio de finalización del Paso 03

- Exactamente 5,748 filas en `sku_store_diagnosis.csv` sin nulos inesperados en nivel de riesgo, clúster ni estrategia.
- Todos los `suggested_anchor_item` verificados dentro del mismo `store_id` y `dept_id` con `risk_level == "Riesgo Bajo"`.
- Las 5 tablas CSV, el JSON de auditoría y las 4 figuras (`fig05`–`fig08`) generados correctamente.

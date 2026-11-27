# Paso 04 — Dashboard Interactivo de Decisión Comercial (Streamlit + Plotly)

## Objetivo

Desarrollar la aplicación web interactiva `app/dashboard.py` en **Streamlit + Plotly** para que el equipo de marketing y abastecimiento de Walmart California explore los pronósticos a 28 días, valide el desempeño del modelo Random Forest, inspeccione los clústeres K-Means y simule promociones Markdown sobre las 5,748 series de `FOODS`.

---

## 1. Arquitectura, rendimiento e identidad visual

- **Framework:** `streamlit` + `plotly.express` / `plotly.graph_objects`.
- **Paleta corporativa Walmart:**
  - Azul Walmart primario: `#0071CE`
  - Amarillo Spark (acentos / alertas / SNAP): `#FFC220`
  - Azul marino oscuro (encabezados / contraste): `#041E42`
  - Semáforo de riesgo accesible: Alto `#D62828`, Medio `#F77F00`, Bajo `#2A9D8F`.
- **Optimización de memoria y velocidad:**
  - Todas las funciones de lectura de `.parquet` y `.csv` deben estar decoradas con `@st.cache_data`.
  - Cargar únicamente las columnas necesarias de `active_sales_3y.parquet` (por ejemplo, filtrar los últimos 90 días históricos para la pestaña del explorador o leer bajo demanda por `id` usando filtros de `pyarrow` para mantener el uso de RAM mínimo).
- **Manejo robusto de filtros vacíos:**
  - Si la combinación de filtros del sidebar devuelve 0 filas, mostrar un mensaje claro (`st.warning("No hay series que coincidan con los filtros seleccionados. Ajusta los criterios en el panel lateral.")`) y detener el renderizado de las pestañas (`st.stop()`) sin lanzar excepciones.

---

## 2. Panel lateral (`st.sidebar`) — Filtros globales

- **Tienda (`store_id`):** multiselección (`CA_1`, `CA_2`, `CA_3`, `CA_4`, todas seleccionadas por defecto).
- **Departamento (`dept_id`):** multiselección (`FOODS_1`, `FOODS_2`, `FOODS_3`).
- **Nivel de Riesgo:** multiselección (`Riesgo Alto`, `Riesgo Medio`, `Riesgo Bajo`).
- **Clúster K-Means:** multiselección con los nombres reales generados en el Paso 03.
- **Estrategia Prescriptiva:** multiselección de las estrategias activas.
- **Toggle SNAP:** `st.checkbox` / `st.toggle` "Mostrar solo productos con Prioridad SNAP (`snap_sensitivity >= 15%`)".
- **Buscador de SKU:** campo de texto (`st.text_input`) para filtrar por subcadena de `item_id` o `id`.

---

## 3. Estructura de las 4 pestañas principales (`st.tabs`)

### Pestaña 1 — Resumen Ejecutivo y Riesgo Comercial
- **Tarjetas KPI principales (`st.metric`):**
  - Series filtradas / total portafolio (`5,748`)
  - Ingreso en Riesgo Total (USD, horizonte 28 días)
  - % y conteo de SKUs en Riesgo Alto y Riesgo Medio
  - % de SKUs con Prioridad SNAP
- **Visualizaciones Plotly:**
  - Gráfico de barras apiladas / agrupadas de Ingreso en Riesgo (USD) por tienda y departamento.
  - Distribución de series por nivel de riesgo y estrategia prescriptiva.
- **Nota explícita de transparencia M5 (`st.info`):**
  - Explicar claramente que el dataset Kaggle M5 contiene ventas reales, precios y calendario/SNAP, y **no** incluye stock físico, costo unitario ni vencimientos; por lo tanto, el indicador financiero principal es **Ingreso en Riesgo (USD)** calculado sobre la desaceleración proyectada real.

### Pestaña 2 — Explorador de Pronóstico (Nivel SKU-Tienda)
- Selector interactivo del SKU-tienda (`id`) dentro del subconjunto filtrado (ordenado por `revenue_at_risk_usd` descendente por defecto).
- **Serie temporal interactiva Plotly:**
  - Últimos **90 días históricos reales** (`d_1852..d_1941`).
  - Predicción de **Ventana 4** (`d_1914..d_1941`) superpuesta para evaluar ajuste visual real vs predicho.
  - **Pronóstico futuro de 28 días** (`d_1942..d_1969`) con línea diferenciada y marca vertical de separación en `2016-05-22` (`d_1941`).
  - **Sombreado vertical (`add_vrect`)** en color amarillo suave (`#FFC220` con baja opacidad) sobre los días con `snap_CA == 1`.
- **Ficha prescriptiva del SKU seleccionado:**
  - Velocidad 90d vs 28d real vs 28d proyectada, intermitencia, precio vigente, Ingreso en Riesgo USD, sensibilidad a precio y sensibilidad SNAP.
  - Estrategia asignada, alerta de migración **LEFO → FEFO** y reducción de reposición post-promoción (**-20%/-30%** por *stockpiling*) cuando corresponda, producto ancla sugerido (`suggested_anchor_item`) si aplica Cross-Selling, y táctica bifásica SNAP (Días 1–10 / Días 20–31).

### Pestaña 3 — Validación del Modelo y Segmentación K-Means
- **Subsección A — Validación temporal (4 ventanas rodantes):**
  - Tabla resumen y gráfico comparativo interactivo de **MAE, RMSE y RMSSE oficial M5** (Random Forest vs MA28, Seasonal Naïve y SES).
  - Desglose de RMSSE por tienda, departamento y días `snap_CA == 1` vs `0`.
  - Gráfico horizontal de importancia de variables (`feature_importance.csv`).
- **Subsección B — Segmentación K-Means:**
  - Gráfico dual de **Método del Codo (WCSS)** y **Coeficiente de Silueta** (`K = 2..6`).
  - Tabla y visualización interactiva de centroides reales por clúster (`kmeans_cluster_profiles.csv`) y dispersión interactiva (`intermittency_pct` vs `projected_decline_pct` coloreada por clúster, tamaño por `revenue_at_risk_usd`).

### Pestaña 4 — Plan de Promociones y Simulador Markdown
- **Simulador interactivo de Markdown (`20%` a `35%`):**
  - Slider de descuento (`st.slider("Descuento Markdown simulado (%)", 20, 35, 25, 1)`).
  - Aplicado al subconjunto filtrado elegible para Precios Dinámicos (Riesgo Alto/Medio y `price_sensitivity >= 0.10`), calculando de forma transparente:
    - Precio promocional simulado (`current_price * (1 - d)`),
    - Factor de respuesta estimado con base en la sensibilidad histórica observada (`price_sensitivity`, acotado conservadoramente y documentado como estimación referencial sin margen de costo),
    - Volumen adicional estimado, ingreso proyectado con promo vs escenario base sin promo, e ingreso recuperado potencial (USD),
    - Recordatorio operativo automático de ajuste de pedido post-promoción (`-20%` a `-30%`) por *stockpiling*.
- **Tabla priorizada y descarga:**
  - Tabla interactiva ordenada por `revenue_at_risk_usd` descendente.
  - Botón `st.download_button` para exportar el plan filtrado en formato **CSV** (`plan_promociones_walmart_ca.csv`).

---

## 4. Verificación de ejecución del Paso 04

- Validar sintaxis e importaciones de `app/dashboard.py` con el Python del `.venv`.
- Ejecutar prueba de arranque local (`streamlit run app/dashboard.py --server.headless true`) y verificar que carga sin errores de runtime, sin advertencias críticas y con todos los archivos de datos leídos correctamente.

# Paso 05 — Generación Automática del Paquete de Resultados para el Informe Word UNDC

## Objetivo

Construir y ejecutar `src/05_generate_report_package.py` para leer **programáticamente** todos los archivos de `outputs/metrics/` y `outputs/tables/` (cero cifras hardcodeadas) y compilar el documento final `outputs/RESULTADOS_PARA_INFORME_WORD.md`, redactado con tono académico formal de la **UNDC (2026)** listo para incorporar en `docs/Walmart informe final .docx` y actualizar las cifras de `docs/Pronóstico M5 con Random Forest_20261126_182808_0000.pdf`.

---

## 1. Fuentes de entrada obligatorias del script

El script `src/05_generate_report_package.py` debe cargar y validar que existan:
- `outputs/metrics/data_verification.json`
- `outputs/metrics/etl_audit.json`
- `outputs/metrics/validation_audit.json`
- `outputs/metrics/diagnosis_audit.json`
- `outputs/tables/validation_metrics_by_window.csv`
- `outputs/tables/validation_metrics_summary.csv`
- `outputs/tables/validation_breakdown_store_snap.csv`
- `outputs/tables/feature_importance.csv`
- `outputs/tables/risk_summary_by_store_dept.csv`
- `outputs/tables/kmeans_evaluation.csv`
- `outputs/tables/kmeans_cluster_profiles.csv`
- `outputs/tables/top_50_priority_promotions.csv`
- `outputs/tables/sku_store_diagnosis.csv`

Verificar también la existencia de las 8 figuras PNG en `outputs/figures/` (`fig01` a `fig08`).

---

## 2. Estructura exacta de `outputs/RESULTADOS_PARA_INFORME_WORD.md`

El documento generado debe incluir las siguientes secciones listas para copiar y pegar en Word:

### A. Encabezado y ficha técnica de trazabilidad
- Alcance real (`FOODS` en California `CA_1..CA_4`, 1,437 productos, 5,748 series, 3 años `2013-05-23` a `2016-05-22` + horizonte `2016-05-23` a `2016-06-19`).
- Resumen de auditoría ETL (reducción de RAM %, % de ceros reales, verificación de cero fuga temporal).

### B. Sección 8 — Resultados Empíricos (redacción académica UNDC)
Organizada en subsecciones numeradas con análisis interpretativo y tablas Markdown formateadas con datos 100% reales:
- **8.1. Preparación de datos y características de la demanda en California (`FOODS`)**: volumen de registros activos, intermitencia observada (% ceros), efecto de limpieza pre-lanzamiento y eficiencia computacional.
- **8.2. Evaluación comparativa del modelo Random Forest frente a baselines (validación rodante 4×28 días)**:
  - Tabla resumen general (MAE, RMSE, RMSSE oficial M5 y % de mejora de RF frente a MA28, Seasonal Naïve y SES).
  - Tabla detallada por ventana temporal (Ventanas 1 a 4).
  - Tabla de desempeño desagregado por tienda (`CA_1..CA_4`), departamento (`FOODS_1..3`) y efecto SNAP (`snap_CA == 1` vs `0`).
  - Tabla de importancia de variables del modelo Random Forest final (Top variables explicativas).
- **8.3. Diagnóstico comercial de riesgo y cuantificación del Ingreso en Riesgo (USD)**:
  - Tabla de resumen por tienda, departamento y nivel de riesgo (`Riesgo Alto`, `Riesgo Medio`, `Riesgo Bajo`).
  - Nota metodológica transparente sobre el uso de **Ingreso en Riesgo (USD)** ante la ausencia de stock físico, costo unitario y fechas de vencimiento en M5.
- **8.4. Segmentación no supervisada K-Means del portafolio**:
  - Tabla de evaluación de `K = 2..6` (WCSS y Coeficiente de Silueta) y justificación del `K` elegido.
  - Tabla de perfiles y centroides reales de cada clúster nombrado empíricamente.
- **8.5. Plan prescriptivo de marketing omnicanal y sincronización SNAP**:
  - Tabla resumen de cobertura e Ingreso en Riesgo (USD) por estrategia (Precios Dinámicos/Markdown 20%–35% con LEFO→FEFO y control de *stockpiling*, Cross-Selling sin descuento con producto ancla, Prioridad SNAP bifásica Días 1–10 / 20–31 y Mantenimiento EDLP).
  - Muestra estructurada del Top 15 (con referencia completa a `top_50_priority_promotions.csv`).

### C. Sección 9 — Conclusiones y Recomendaciones
- **9.1. Conclusiones (4 conclusiones numeradas)** alineadas una a una con los objetivos específicos del proyecto:
  1. Calidad del pipeline de datos y prevención de *data leakage* en series intermitentes de alimentos.
  2. Capacidad predictiva real de `RandomForestRegressor` frente a los baselines (citando MAE, RMSE y RMSSE exactos obtenidos).
  3. Magnitud empírica del riesgo comercial (Ingreso en Riesgo USD) y estructura de clústeres K-Means en California.
  4. Diferenciación prescriptiva entre SKUs elásticos al precio, inelásticos (cross-selling con ancla) y dependientes del ciclo SNAP.
- **9.2. Recomendaciones (3 recomendaciones estratégicas accionables)**:
  1. Implementación operativa de Precios Dinámicos (20%–35%), transición LEFO→FEFO y regla de desaceleración de pedidos (-20%/-30%) post-promoción.
  2. Programa de Cross-Selling omnicanal basado en productos ancla EDLP por tienda y departamento (sin erosionar margen en SKUs inelásticos).
  3. Calendario promocional bifásico sincronizado con SNAP California (Días 1–10 refuerzo/multipacks; Días 20–31 cupones para SKUs en riesgo) e integración futura con ERP de inventario y costos reales.

### D. Guía de inserción de figuras (`fig01` a `fig08`)
Tabla con el orden de inserción en el documento Word, nombre de archivo en `outputs/figures/`, sección recomendada, título académico sugerido (estilo APA/UNDC) y pie explicativo basado en los hallazgos reales.

### E. Tabla de actualización de placeholders de las diapositivas PDF
Tabla explícita que mapea las cifras referenciales/placeholder presentes en `docs/Pronóstico M5 con Random Forest_20261126_182808_0000.pdf` — específicamente el **"37%"** y **"USD 1.2M"** (y cualquier otro valor proyectado preliminar de las láminas) — hacia su **cifra empírica real exacta** obtenida en este pipeline, indicando el origen de cada dato y la explicación clara de su interpretación correcta para la sustentación.

---

## Criterio de finalización del Paso 05

- `src/05_generate_report_package.py` ejecutado con código de salida `0`.
- `outputs/RESULTADOS_PARA_INFORME_WORD.md` creado, verificado sin placeholders sin rellenar (`TODO`, `NaN`, `{...}`) y 100% consistente con las tablas CSV y los JSON de auditoría.

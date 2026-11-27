# Paquete de Resultados Empíricos para Informe Final (UNDC 2026)

> **Nota editorial de inserción en `docs/Walmart informe final .docx`:**
> Pegar las secciones **8. Resultados Empíricos del Prototipo** (`8.1` a `8.5`) y **9. Conclusiones y Recomendaciones** (`9.1` y `9.2`) inmediatamente después de la Sección 7 del informe Word, y **renumerar la actual `8. Referencias Bibliográficas` a `10. Referencias Bibliográficas`**. Todas las cifras de este documento fueron generadas programáticamente desde las salidas auditables del pipeline (`outputs/metrics/` y `outputs/tables/`), sin valores ficticios ni simulados.

---

## 8. Resultados Empíricos del Prototipo

El prototipo analítico se ejecutó íntegramente en Python (`3.14.3`) sobre los datos reales del dataset abierto Kaggle M5 Forecasting (`sales_train_evaluation.csv`, `calendar.csv` y `sell_prices.csv`), acotado a la categoría de alimentos (`cat_id = "FOODS"`, departamentos `FOODS_1`, `FOODS_2` y `FOODS_3`) en las cuatro tiendas de California (`CA_1`, `CA_2`, `CA_3` y `CA_4`), conformando exactamente **1,437 productos únicos** y **5,748 series producto-tienda**. Todas las pruebas de integridad, control de memoria y prevención de *data leakage* finalizaron con estado **PASS**.

---

### 8.1. Auditoría de Datos y Perfil de la Demanda `FOODS` en California

Durante la fase de preparación de datos (`src/01_etl_features.py`), se integró la ventana histórica de tres años completos (`2013-05-23` a `2016-05-22`, `d_846` a `d_1941`, equivalente a `1,096` días calendario incluyendo el año bisiesto 2016) más un margen previo de 60 días (`2013-03-24` a `2013-05-22`) dedicado exclusivamente al cómputo de rezagos iniciales sin valores faltantes, junto con la grilla del horizonte operativo futuro de 28 días (`2016-05-23` a `2016-06-19`, `d_1942` a `d_1969`).

Al depurar los días previos al lanzamiento comercial de cada producto (registros con `sell_price` nulo), se eliminaron **682,592 observaciones pre-lanzamiento**, preservando íntegros los ceros reales posteriores con precio vigente (`sell_price > 0`). Como resultado, el panel histórico activo consolidó **5,710,335 registros diarios válidos** (`data/processed/active_sales_3y.parquet`) con cero duplicados por `(id, date)`, cero precios no positivos y cero ventas negativas. La aplicación sistemática de *downcasting* (`float32`, `int16`, `int8` y tipos categóricos) redujo el consumo de memoria RAM del panel consolidado de **1,031.38 MB a 193.09 MB**, logrando una **reducción efectiva del 81.28%**.

En términos de comportamiento comercial, el análisis empírico registró **2,848,868 días sin ventas sobre 5,710,335 días activos**, lo que equivale a una **tasa global de intermitencia real del 49.89%** en alimentos de California. Esta cifra resulta diez puntos porcentuales inferior al **59.89%** reportado para el conjunto global de los tres estados y tres categorías del dataset M5 por Makridakis et al. [2], lo cual es coherente con la mayor frecuencia de compra inherente a los alimentos (`FOODS`) respecto a bienes duraderos (`HOUSEHOLD` y `HOBBIES`), aunque confirma que casi la mitad de las observaciones SKU-día continúan siendo ceros reales. Finalmente, la verificación automatizada sobre 200 muestras aleatorias confirmó cumplimiento estricto de cero *data leakage*: `lag_28`, `rolling_mean_7` (en `[t-34, t-28]`) y `relative_price` (contra la media expansiva histórica pasada `<= t`) coincidieron exactamente en el 100% de los casos auditados.

**Tabla 8.1.** *Resumen de auditoría ETL e ingeniería de características sin fuga temporal (`FOODS` · California).*

| Indicador de Auditoría ETL | Valor Empírico Real |
| :--- | ---: |
| Alcance del catálogo (`FOODS` · `CA_1`–`CA_4`) | 1,437 productos × 4 tiendas = **5,748 series** |
| Ventana histórica efectiva (3 años + bisiesto 2016) | 2013-05-23 a 2016-05-22 (`d_846`–`d_1941`, 1,096 días) |
| Horizonte operativo futuro pronosticado | 2016-05-23 a 2016-06-19 (`d_1942`–`d_1969`, 28 días = 160,944 filas) |
| Registros brutos `wide → long` (buffer 60d + 3 años + futuro) | 6,805,632 |
| Registros pre-lanzamiento eliminados (`sell_price` nulo) | 682,592 |
| Registros activos reales en 3 años (`active_sales_3y.parquet`) | **5,710,335** |
| Registros de modelado sin NaN (`features_3y.parquet`) | 5,623,708 (86,627 filas *cold-start* excluidas) |
| Días en cero con precio vigente (intermitencia real 3 años) | 2,848,868 / 5,710,335 (**49.89%**) |
| Optimización de memoria RAM (downcasting `float32`/`int8`/`category`) | 1,031.38 MB → 193.09 MB (**-81.28%**) |
| Controles de integridad y prueba anti-fuga (`n = 200`) | 0 duplicados, 0 precios <= 0, 0 ventas < 0, **PASS 200/200** |

---

### 8.2. Evaluación Predictiva: Random Forest frente a Líneas Base

La capacidad predictiva de `RandomForestRegressor` (`n_estimators=100`, `max_depth=16`, `min_samples_leaf=25`, `max_samples=0.30`, `max_features="sqrt"`, `n_jobs=6`) se validó mediante origen rodante estrictamente cronológico en **4 ventanas consecutivas de 28 días** sobre los últimos 112 días reales (`d_1830` a `d_1941`, del `2016-02-01` al `2016-05-22`), entrenando cada modelo y cada línea base (Promedio Móvil `MA28`, Suavizado Exponencial Simple `SES` implementado vectorizadamente en `NumPy` y `Seasonal Naïve` `lag_28`) exclusivamente con información anterior al corte `t_cut`. La corrida completa sobre las 5,748 series (4 ventanas + modelo operativo final) concluyó en **717.8 segundos** con un pico de memoria de **2,298.9 MB**.

**Tabla 8.2.** *Comparativa promedio de desempeño predictivo sobre las 4 ventanas rodantes de 28 días (`FOODS` · California).*

| Modelo | MAE | RMSE | RMSSE (M5) | Mejora RF en MAE | Mejora RF en RMSE | Mejora RF en RMSSE |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| MA28 | 1.4028 | 2.7586 | 0.7785 | -2.33% | **+1.43%** | -2.15% |
| SES (NumPy) | 1.4288 | 2.8982 | 0.7807 | -0.47% | **+6.18%** | -1.87% |
| **Random Forest** | 1.4355 | **2.7190** | 0.7953 | +0.00% | 0.00% | +0.00% |
| Seasonal Naïve (lag_28) | 1.7070 | 3.4311 | 1.0361 | +15.91% | **+20.75%** | +23.24% |

**Tabla 8.3.** *Evolución del error (RMSE / RMSSE) por ventana temporal rodante (`d_1830` a `d_1941`).*

| Ventana Rodante (28 días) | Random Forest (RMSE / RMSSE) | MA28 (RMSE / RMSSE) | SES NumPy (RMSE / RMSSE) | Seasonal Naïve (RMSE / RMSSE) | Excl. (`scale=0`) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Ventana 1 (2016-02-01 a 2016-02-28) | 2.7397 / 0.7797 | 2.6962 / 0.7529 | 2.7329 / 0.7532 | 3.3364 / 0.9976 | 2 |
| Ventana 2 (2016-02-29 a 2016-03-27) | 2.8589 / 0.7977 | 2.9097 / 0.7758 | 2.9887 / 0.7780 | 3.5842 / 1.0377 | 2 |
| Ventana 3 (2016-03-28 a 2016-04-24) | 2.6221 / 0.7904 | 2.7305 / 0.7742 | 3.1828 / 0.7802 | 3.4638 / 1.0347 | 0 |
| Ventana 4 (2016-04-25 a 2016-05-22) | 2.6553 / 0.8134 | 2.6979 / 0.8111 | 2.6883 / 0.8113 | 3.3399 / 1.0743 | 0 |

Los resultados empíricos revelan hallazgos de alto rigor metodológico que dialogan directamente con la literatura de la competencia M5:

1. **Superioridad en RMSE global y frente a `Seasonal Naïve`:** Random Forest obtuvo el **menor RMSE global (`2.7190`)** entre los cuatro modelos evaluados, superando a `SES` en **`+6.18%`**, a `MA28` en **`+1.43%`** y a `Seasonal Naïve` en **`+20.75%`**. Asimismo, redujo el error frente a `Seasonal Naïve` en **`+23.24%`** en RMSSE y **`+15.91%`** en MAE. Al penalizar cuadráticamente las desviaciones grandes, la victoria en RMSE confirma que Random Forest captura con mayor precisión los picos de demanda en los productos de mayor volumen y rotación semanal.
2. **Competitividad en RMSSE no ponderado frente a `MA28` y `SES`:** En el promedio simple de RMSSE a nivel de serie individual (`0.7953`), `MA28` (`0.7785`) y `SES` (`0.7807`) registraron valores entre **`1.87%` y `2.15%`** menores, aunque convergiendo prácticamente en empate técnico en la Ventana 4 (`RF = 0.8134` frente a `SES = 0.8113` y `MA28 = 0.8111`). Este resultado coincide con las conclusiones oficiales de Makridakis et al. [1] y el análisis práctico de Xcope [5]: a nivel desagregado de SKU con alta proporción de ceros, los métodos de suavizado exponencial de nivel plano son muy difíciles de superar en métricas no ponderadas porque `MA28` y `SES` anclan su proyección en las ventas inmediatas hasta `t_cut`, mientras que un modelo directo sin recursividad a `H = 28` días opera únicamente con rezagos `>= t-28`. Sin embargo, a diferencia de los promedios planos, Random Forest incorpora explícitamente variaciones de precio (`sell_price`, `relative_price`), día de la semana (`wday`) y pagos `snap_CA`, brindando un pronóstico diario accionable para el calendario promocional.
3. **Desempeño por tienda, departamento y efecto SNAP:** Como detalla la Tabla 8.4, el error absoluto y cuadrático aumenta durante los días con abono de beneficios alimentarios (`snap_CA = 1`: `RMSE = 2.7798`, `MAE = 1.4613`) frente a los días regulares (`snap_CA = 0`: `RMSE = 2.6842`, `MAE = 1.4212`), representando un incremento del **`+3.56%`** en RMSE y **`+2.82%`** en MAE. Esta mayor volatilidad en días de pago SNAP respalda lo documentado por Nowak y Kościelniak [8] y Harris-Lagoudakis y Wich [14] sobre los picos bruscos de consumo al inicio del mes; no obstante, el RMSSE escalado se mantiene prácticamente estable (`0.7791` vs `0.7811`), evidenciando buena calibración relativa. Entre establecimientos, `CA_3` y `CA_1` logran los mejores RMSSE (`0.7631` y `0.7667`), mientras `CA_2` presenta la mayor volatilidad relativa (`0.8639`).

**Tabla 8.4.** *Desglose del desempeño de Random Forest por tienda, departamento y condición SNAP (`snap_CA`).*

| Dimensión | Segmento | MAE (4 vent.) | RMSE (4 vent.) | RMSSE (4 vent.) | RMSSE Ventana 4 |
| :--- | :--- | ---: | ---: | ---: | ---: |
| Tienda | `CA_1` | 1.4814 | 2.7176 | 0.7667 | 0.7975 |
| Tienda | `CA_2` | 1.4413 | 2.5421 | 0.8639 | 0.8872 |
| Tienda | `CA_3` | 1.7817 | 3.5857 | 0.7631 | 0.7579 |
| Tienda | `CA_4` | 1.0376 | 1.6828 | 0.7873 | 0.8110 |
| Departamento | `FOODS_1` | 1.4259 | 2.4871 | 0.7949 | 0.8447 |
| Departamento | `FOODS_2` | 1.0755 | 1.6699 | 0.7853 | 0.7978 |
| Departamento | `FOODS_3` | 1.6121 | 3.1494 | 0.8002 | 0.8127 |
| Beneficio SNAP | `snap_CA=0` | 1.4212 | 2.6842 | 0.7791 | 0.7926 |
| Beneficio SNAP | `snap_CA=1` | 1.4613 | 2.7798 | 0.7811 | 0.8070 |

4. **Importancia de variables del modelo operativo final:** Entrenado sobre todo el historial hasta `d_1941`, el modelo operativo proyectó **337,565.9 unidades** totales para el horizonte `d_1942`–`d_1969`. El análisis de `feature_importance.csv` (Tabla 8.5) demuestra que las cinco variables de memoria reciente de demanda (`>= t-28`) concentran el **91.80%** del poder explicativo, lideradas por `rolling_mean_28` (**29.62%**), `rolling_mean_7` (**23.51%**) y `lag_28` (**15.90%**), seguidas por el bloque de precios (`sell_price`, `relative_price` y `price_change`, con **3.96%** conjunto), la identidad del SKU (`item_code`, `1.30%`) y la estacionalidad semanal y mensual (`wday`, `1.07%`; `month`, `0.83%`).

**Tabla 8.5.** *Top 10 de importancia relativa de variables predictoras en el Random Forest operativo final.*

| Rango | Variable Predictora | Importancia Relativa (%) | Importancia Acumulada (%) |
| ---: | :--- | ---: | ---: |
| 1 | `rolling_mean_28` | 29.62% | 29.62% |
| 2 | `rolling_mean_7` | 23.51% | 53.13% |
| 3 | `lag_28` | 15.90% | 69.03% |
| 4 | `lag_35` | 12.74% | 81.77% |
| 5 | `lag_56` | 10.03% | 91.80% |
| 6 | `sell_price` | 2.19% | 93.99% |
| 7 | `relative_price` | 1.74% | 95.73% |
| 8 | `item_code` | 1.30% | 97.03% |
| 9 | `wday` | 1.07% | 98.11% |
| 10 | `month` | 0.83% | 98.94% |

> *[Insertar aquí: **Figura 1** (`fig01_validation_metrics_comparison.png`), **Figura 2** (`fig02_rmsse_store_snap_breakdown.png`), **Figura 3** (`fig03_feature_importance_rf.png`) y **Figura 4** (`fig04_actual_vs_forecast_examples.png`).]*

---

### 8.3. Diagnóstico Comercial y Niveles de Riesgo

A partir del contraste entre la velocidad de venta reciente de los últimos 90 días reales (`v90`) y la velocidad diaria proyectada por Random Forest para los próximos 28 días (`pred_v28`), valorizada al precio vigente de cierre en `d_1941` (`current_price`), el sistema cuantificó una exposición comercial total de **`$59,362.23` USD en Ingreso en Riesgo** para el horizonte de 28 días, equivalente a **22,113.9 unidades** en desaceleración a lo largo de las 5,748 series evaluadas. En estricto apego a la transparencia metodológica sobre las limitaciones del dataset M5 [1], [2], esta métrica representa exclusivamente desaceleración de ingresos valorizados a `sell_price` y no asume costos unitarios, inventario físico ni fechas de vencimiento inexistentes en la fuente.

**Tabla 8.6.** *Distribución del portafolio e Ingreso en Riesgo (28 días) por nivel de riesgo comercial.*

| Nivel de Riesgo Comercial | SKUs | % del Portafolio | Ingreso en Riesgo 28d (USD) | % del Riesgo Total |
| :--- | ---: | ---: | ---: | ---: |
| **Riesgo Alto** | 125 | 2.17% | $10,633.90 | 17.91% |
| **Riesgo Medio** | 3,118 | 54.24% | $38,696.44 | 65.19% |
| **Riesgo Bajo** | 2,505 | 43.58% | $10,031.89 | 16.90% |
| **Total Portafolio FOODS CA** | **5,748** | **100.00%** | **$59,362.23** | **100.00%** |

**Tabla 8.7.** *Desglose por tienda en California y umbrales del quintil superior (`p80`) de Ingreso en Riesgo.*

| Tienda | SKUs | Riesgo Alto | Riesgo Medio | Riesgo Bajo | Corte Quintil `p80` (USD) | Ingreso en Riesgo (USD) | % del Total |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `CA_1` | 1,437 | 21 | 810 | 606 | $12.82 | $15,039.26 | 25.33% |
| `CA_2` | 1,437 | 29 | 784 | 624 | $9.52 | $11,470.95 | 19.32% |
| `CA_3` | 1,437 | 41 | 765 | 631 | $20.14 | $25,363.34 | 42.73% |
| `CA_4` | 1,437 | 34 | 759 | 644 | $6.80 | $7,488.68 | 12.62% |

Los resultados evidencian tres patrones estratégicos clave para la gestión comercial en California:

- **Concentración en riesgo accionable:** Los niveles **Riesgo Alto** (`125` SKUs, `2.17%`) y **Riesgo Medio** (`3,118` SKUs, `54.24%`) suman **3,243 series (56.42% del portafolio)** y concentran **`$49,330.34` USD (83.10% del Ingreso en Riesgo total)**. En particular, los `125` SKUs en Riesgo Alto explican por sí solos el `17.91%` del riesgo económico pese a representar apenas el `2.17%` del catálogo.
- **Asimetría geográfica y departamental:** La tienda **`CA_3`** concentra **`$25,363.34` USD (42.73% del Ingreso en Riesgo total)** y exhibe el corte `p80` más elevado (`$20.14` USD frente a `$6.80` USD en `CA_4`). A nivel departamental, `FOODS_3` agrupa el `59.80%` del riesgo económico total (`$35,499.34` USD).
- **Peso transversal del ciclo SNAP:** Un total de **1,831 series (31.9% del portafolio)** registran una sensibilidad positiva a SNAP igual o superior al 15% (`snap_sensitivity >= 0.15`), abarcando **`$24,009.32` USD (40.4% del Ingreso en Riesgo total)**, lo que valida la necesidad de sincronizar la activación promocional con los pagos gubernamentales mensuales [14], [15].

> *[Insertar aquí: **Figura 5** (`fig05_risk_distribution_store_dept.png`).]*

---

### 8.4. Segmentación K-Means y Validación por Coeficiente de Silueta

Sobre los seis indicadores comerciales estandarizados (`sales_velocity_28d`, `intermittency_pct`, `projected_decline_pct`, `revenue_at_risk_usd`, `price_sensitivity` y `snap_sensitivity`), una inspección preliminar sin recorte de valores extremos detectó que los valores atípicos de demanda y elasticidad formaban clústeres degenerados de apenas `0.09%` (~`5` SKUs extremos) para `K = 3..6`. En consecuencia, siguiendo buenas prácticas de preprocesamiento en segmentación minorista [18], se aplicó **winsorización controlada** (`p99` en variables no negativas y `p01–p99` en sensibilidades) únicamente sobre la copia enviada a `StandardScaler`, preservando intactos los valores reales originales en el perfilado e informe final.

**Tabla 8.8.** *Evaluación de K-Means para `K = 2..6` mediante Método del Codo (WCSS) y Coeficiente de Silueta.*

| `K` | WCSS (Inercia) | Coeficiente de Silueta | Tamaño Mínimo Clúster (SKUs) | % Mínimo Clúster | % Máximo Clúster |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 2 | 25,887.40 | 0.3985 | 1,126 | 19.59% | 80.41% |
| 3 | 22,140.32 | 0.2348 | 652 | 11.34% | 58.77% |
| **4 (Elegido)** | 19,060.63 | **0.2824** | 228 | 3.97% | 61.67% |
| 5 | 16,394.68 | 0.2356 | 197 | 3.43% | 41.65% |
| 6 | 14,086.67 | 0.2560 | 197 | 3.43% | 40.07% |

Aunque `K = 2` alcanza la mayor silueta matemática (`0.3985`) por tratarse de una partición binaria gruesa (`80.4%` vs `19.6%`), carece de granularidad suficiente para diferenciar tácticas de marketing. Entre las configuraciones accionables (`K = 3..6`), **`K = 4`** obtiene el **máximo local del Coeficiente de Silueta (`0.2824`)** con un punto de inflexión claro en WCSS (`19,060.63`) y sin clústeres degenerados (`tamaño mínimo = 228` SKUs, `3.97%`), separando cuatro arquetipos comerciales nítidos (Tabla 8.9).

**Tabla 8.9.** *Perfiles empíricos de los 4 clústeres K-Means (centroides reales en escala original).*

| Clúster | Nombre Empírico | SKUs (%) | Vel. 28d (u/d) | Intermit. (%) | Declive (%) | Riesgo/SKU (USD) | Riesgo Total USD (%) | Sens. Precio | Sens. SNAP |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **C3** | Desaceleración Crítica e Ingreso en Riesgo | 653 (11.4%) | 3.74 | 32.0% | 20.4% | $66.04 | $43,126.87 (72.7%) | -29.8% | +11.7% |
| **C1** | Alta Rotación y Productos Ancla | 1,322 (23.0%) | 4.67 | 24.9% | 3.1% | $6.89 | $9,107.61 (15.3%) | -23.2% | +9.6% |
| **C2** | Cola Larga de Baja Rotación e Intermitencia | 3,545 (61.7%) | 0.88 | 62.4% | 1.5% | $1.52 | $5,403.56 (9.1%) | -17.5% | +9.6% |
| **C0** | Intermitentes de Alta Elasticidad Promocional | 228 (4.0%) | 1.68 | 70.7% | 4.0% | $7.56 | $1,724.20 (2.9%) | +620.1% | +9.7% |

El resultado más notable de la segmentación no supervisada es una **concentración extrema tipo Pareto en el Clúster C3 (*Desaceleración Crítica e Ingreso en Riesgo*)**: apenas **`653` series (`11.4%` del catálogo)** presentan un declive promedio del `20.4%` y concentran **`$43,126.87` USD, equivalentes al `72.7%` de todo el Ingreso en Riesgo** en California. En contraste, el **Clúster C1 (*Alta Rotación y Productos Ancla*)** agrupa `1,322` series (`23.0%`) de elevada velocidad (`4.67` u/día) y baja intermitencia (`24.9%`) ideales como productos ancla; el **Clúster C2 (*Cola Larga de Baja Rotación e Intermitencia*)** representa el núcleo mayoritario de baja velocidad (`0.88` u/día, `61.7%` de SKUs pero solo `9.1%` del riesgo); y el **Clúster C0 (*Intermitentes de Alta Elasticidad Promocional*)** aísla `228` artículos altamente intermitentes (`70.7%` ceros) que disparan su demanda bajo rebajas (`+620.1%`), constituyendo el nicho óptimo para descuentos tácticos.

> *[Insertar aquí: **Figura 6** (`fig06_kmeans_elbow_silhouette.png`) y **Figura 7** (`fig07_kmeans_cluster_profiles.png`).]*

---

### 8.5. Plan Promocional Prescriptivo y Despliegue en Dashboard

El motor prescriptivo (`src/03_diagnosis_kmeans_marketing.py`) tradujo el diagnóstico de riesgo y las elasticidades reales en un plan diferenciado para las 5,748 series (Tabla 8.10). Un hallazgo crucial para la rentabilidad es que, de los `1,789` SKUs que registraron al menos 7 días históricos con rebaja (`relative_price < 0.95`), solo `755` evidenciaron elasticidad positiva (`>= 10%`), y de ellos únicamente **`425` series (`7.39%`)** se encuentran en Riesgo Alto o Medio.

**Tabla 8.10.** *Mix prescriptivo de estrategias de marketing y cobertura de Ingreso en Riesgo (28 días).*

| Estrategia Principal Prescrita | SKUs | % Portafolio | Ingreso en Riesgo (USD) | % Riesgo USD | Con Prioridad SNAP (`>=15%`) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Cross-Selling y Visibilidad Omnicanal (Sin Descuento) | 2,818 | 49.03% | $43,336.22 | 73.00% | 920 |
| Mantenimiento EDLP y Producto Ancla | 1,725 | 30.01% | $7,272.08 | 12.25% | 0 |
| Precios Dinámicos / Markdown (20%–35%) | 425 | 7.39% | $5,994.12 | 10.10% | 131 |
| Sincronización SNAP (Base EDLP) | 780 | 13.57% | $2,759.81 | 4.65% | 780 |
| **Total Portafolio** | **5,748** | **100.00%** | **$59,362.23** | **100.00%** | **1,831 (31.9%)** |

En concordancia directa con Riesenegger y Hübner [12], el motor **bloquea explícitamente los descuentos directos** sobre los `2,818` SKUs en riesgo (`73.00%` del Ingreso en Riesgo, `$43,336.22` USD) cuya `price_sensitivity` es negativa o carece de historial promocional suficiente: rebajar el precio en artículos inelásticos destruye margen bruto sin acelerar significativamente la evacuación de inventario. Para este grupo, el sistema prescribe **Cross-Selling y visibilidad omnicanal sin descuento**, asignando automáticamente un producto ancla real de Riesgo Bajo y máxima rotación dentro de la misma tienda y departamento (por ejemplo, `FOODS_3_090` en `FOODS_3` y `FOODS_2_360` en `FOODS_2`).

Por su parte, para las **`425` series elegibles a Precios Dinámicos / Markdown (`20%–35%`)** (`$5,994.12` USD en riesgo), se activa el rango escalonado de descuento acompañado de transición operativa **LEFO → FEFO** [12] y una alerta obligatoria de **reducción de reposición post-promoción entre `-20%` y `-30%`** para evitar sobreinventario por acaparamiento (*stockpiling*) [7]. En el escenario base del simulador interactivo (`d = 25%`, elasticidad `ε = 0.6` según [12]), el descuento proyecta un incremento de demanda del **`+18.84%`** (`+4,169` unidades adicionales en 28 días) y un ingreso incremental recuperado estimado de **`$9,169.40` USD**. Complementariamente, la capa transversal de **Prioridad SNAP (`1,831` SKUs)** despliega una táctica bifásica: Fase A (Días 1–10: encartes, multipacks y refuerzo de stock) y Fase B (Días 20–31: cupones dirigidos de fin de mes para SKUs en riesgo) [14], [15].

**Tabla 8.11.** *Top 10 de series prioritarias del plan promocional (extracto de `top_50_priority_promotions.csv`).*

| # | Serie (`id`) | Riesgo | Precio | Declive | Riesgo 28d (USD) | Sens. Precio | Sens. SNAP | Estrategia | Ancla |
| ---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- |
| 1 | `FOODS_3_282_CA_3_evaluation` | Riesgo Alto | $2.56 | 37.5% | $1,156.11 | -99.0% | +19.7% | Cross-Selling (Sin Desc.) | `FOODS_3_090` |
| 2 | `FOODS_3_511_CA_1_evaluation` | Riesgo Medio | $6.98 | 18.7% | $886.97 | -88.1% | +27.0% | Cross-Selling (Sin Desc.) | `FOODS_3_090` |
| 3 | `FOODS_3_362_CA_3_evaluation` | Riesgo Medio | $2.56 | 27.5% | $547.88 | -98.0% | +15.5% | Cross-Selling (Sin Desc.) | `FOODS_3_090` |
| 4 | `FOODS_3_382_CA_3_evaluation` | Riesgo Alto | $1.98 | 85.3% | $496.01 | Sin hist. | +16.7% | Cross-Selling (Sin Desc.) | `FOODS_3_090` |
| 5 | `FOODS_3_587_CA_1_evaluation` | Riesgo Medio | $2.48 | 23.9% | $423.60 | +63.8% | +11.2% | Markdown (20%–35%) | — |
| 6 | `FOODS_3_516_CA_3_evaluation` | Riesgo Medio | $3.78 | 29.9% | $411.99 | Sin hist. | +23.3% | Cross-Selling (Sin Desc.) | `FOODS_3_090` |
| 7 | `FOODS_3_202_CA_3_evaluation` | Riesgo Medio | $4.68 | 13.8% | $407.04 | -90.5% | +9.9% | Cross-Selling (Sin Desc.) | `FOODS_3_090` |
| 8 | `FOODS_2_029_CA_3_evaluation` | Riesgo Medio | $9.98 | 17.9% | $376.45 | -96.6% | +30.8% | Cross-Selling (Sin Desc.) | `FOODS_2_360` |
| 9 | `FOODS_3_233_CA_3_evaluation` | Riesgo Medio | $2.56 | 23.0% | $372.42 | -98.4% | +17.1% | Cross-Selling (Sin Desc.) | `FOODS_3_090` |
| 10 | `FOODS_3_329_CA_3_evaluation` | Riesgo Medio | $2.98 | 15.7% | $359.28 | Sin hist. | +11.4% | Cross-Selling (Sin Desc.) | `FOODS_3_090` |

Todo el sistema fue desplegado operativamente en el dashboard interactivo `app/dashboard.py` (Streamlit 1.67 + Plotly 7.2), optimizado con lectura selectiva *pushdown* en PyArrow (consumo de apenas `8.58 MB` para los últimos 90 días de las 5,748 series), filtros globales en barra lateral, cuatro pestañas ejecutivas, simulador de Markdown en tiempo real y exportación directa a CSV para Excel (`utf-8-sig`).

> *[Insertar aquí: **Figura 8** (`fig08_prescriptive_marketing_revenue_risk.png`).]*
>
> *[Espacio reservado para Captura 1 del Dashboard Streamlit: **Tab 1 — Resumen Ejecutivo y Riesgo Comercial** (mostrar KPIs globales, alerta de Clúster C3, barras por tienda y Treemap).]*
>
> *[Espacio reservado para Captura 2 del Dashboard Streamlit: **Tab 2 — Explorador de Pronóstico (RF vs Real)** sobre `FOODS_3_282_CA_3_evaluation` o `FOODS_3_587_CA_1_evaluation` (mostrar 90d reales, Ventana 4, pronóstico 28d, franjas SNAP y ficha prescriptiva).]*
>
> *[Espacio reservado para Captura 3 del Dashboard Streamlit: **Tab 4 — Simulador Interactivo de Markdown (`20%–35%`) y Plan de Promociones**.]*

---

## 9. Conclusiones y Recomendaciones

### 9.1. Conclusiones

Alineadas estrictamente con los cuatro objetivos específicos planteados en la Sección 4.2, se formulan las siguientes conclusiones empíricas:

1. **Preparación de datos e ingeniería sin *data leakage* (Objetivo Específico 1):** Se construyó e integró exitosamente un pipeline reproducible sobre los tres archivos reales del dataset Kaggle M5 para `FOODS` en California (1,437 productos, 5,748 series, `5,710,335` registros activos de 3 años), eliminando `682,592` observaciones pre-lanzamiento y logrando una reducción de memoria RAM del **81.28%** mediante *downcasting* y almacenamiento columnar `.parquet`. La intermitencia real observada alcanzó el **49.89%** de días en cero, y todas las variables predictoras (`lag_28`, `lag_35`, `lag_56`, medias móviles desde `t-28` y `relative_price` expansivo pasado) superaron al 100% la auditoría automatizada de cero fuga temporal.
2. **Evaluación empírica de precisión de Random Forest frente a líneas base (Objetivo Específico 2):** En validación temporal por origen rodante de 4 ventanas × 28 días, `RandomForestRegressor` alcanzó el **mejor RMSE global (`2.7190`)**, superando a `Seasonal Naïve` (`+20.75%`), `SES` (`+6.18%`) y `MA28` (`+1.43%`), además de mejorar en `+23.24%` el RMSSE respecto a `Seasonal Naïve`. Asimismo, se comprobó que `MA28` (`0.7785`) y `SES` (`0.7807`) mantienen una ventaja acotada de `1.87%–2.15%` en RMSSE no ponderado por serie (convergiendo en empate técnico en Ventana 4), lo que ratifica la literatura M5 [1], [5] y evidencia que el mayor aporte de Random Forest radica en reducir errores grandes en productos de alto volumen y modelar variables explicativas de calendario, precio y días `snap_CA`.
3. **Diagnóstico comercial cuantitativo y exposición financiera real (Objetivo Específico 3):** La estimación simultánea de rotación, intermitencia, declive proyectado, sensibilidad a precio y respuesta SNAP sobre las 5,748 series identificó **`$59,362.23` USD en Ingreso en Riesgo** para el horizonte de 28 días (`22,113.9` unidades), con el **83.10%** concentrado en Riesgo Alto (`125` SKUs) y Riesgo Medio (`3,118` SKUs). La tienda **`CA_3`** concentra por sí sola el **42.73%** del riesgo (`$25,363.34` USD, corte `p80 = $20.14` USD), y los `1,831` SKUs con Prioridad SNAP (`>=15%`) abarcan el **40.4%** de la exposición económica total.
4. **Segmentación K-Means y motor prescriptivo desplegado en dashboard (Objetivo Específico 4):** La segmentación K-Means con winsorización controlada y validación por Silueta determinó **`K = 4`** (`Silhouette = 0.2824`) como la partición óptima, descubriendo que el **Clúster C3 (`11.4%` de los SKUs)** concentra el **`72.7%`** del Ingreso en Riesgo (`$43,126.87` USD). A partir de estas elasticidades reales, el motor prescriptivo desplegado en Streamlit evita descuentos destructores de margen en el `49.0%` del catálogo (asignando Cross-Selling con productos ancla verificados), focaliza Markdowns (`20%–35%` + alerta FEFO/*stockpiling*) únicamente en las `425` series elásticas en riesgo y sincroniza `1,831` series con el calendario bifásico SNAP.

---

### 9.2. Recomendaciones

1. **Integración futura con ERP de inventario físico, costos unitarios y fechas de vencimiento:** Conectar la salida diaria del prototipo (`forecast_28d.parquet` y `sku_store_diagnosis.csv`) con los registros internos de stock en tienda, costo de adquisición (`COGS`) y vida útil remanente de Walmart. Ello permitirá pasar del *Ingreso en Riesgo* estimado a una optimización exacta de **margen neto rescatado y reducción real de merma física**, calibrando de forma automática el punto de disparo de los descuentos FEFO [12].
2. **Escalamiento geográfico y de categorías con arquitectura híbrida de pronóstico:** Extender el pipeline validado desde `FOODS` en California hacia las tiendas de **Texas (`TX_1`–`TX_3`) y Wisconsin (`WI_1`–`WI_3`)**, así como a las categorías **`HOUSEHOLD` y `HOBBIES`**, evaluando un ensamble ligero (`Random Forest` + `SES`/`MA28` o *Gradient Boosting* con distribución Tweedie) que combine la ventaja de los árboles en volumen/variables explicativas (RMSE) con la estabilidad de los métodos de suavizado en series ultraintermitentes (RMSSE) [1], [4].
3. **Ejecución de pruebas A/B controladas en tienda para calibrar la elasticidad de los Markdowns (`20%–35%`) y la táctica SNAP:** Antes del despliegue masivo, ejecutar un piloto controlado de 8 semanas en **`CA_3`** (tienda de mayor exposición, `$25,363.34` USD) comparando grupos tratamiento y control sobre los SKUs del **Clúster C3** y las series elegibles a Markdown, midiendo empíricamente: (a) la elasticidad real de liquidación frente al rango `ε ∈ [0.4, 0.8]` [12], (b) la efectividad de reducir el pedido post-promoción en `-20%/-30%` para neutralizar el *stockpiling* [7], y (c) el retorno de los cupones de fin de mes en la Fase B del ciclo SNAP (Días 20–31) [15].

---

## Anexo A — Guía de Inserción de Figuras Reales (`outputs/figures/`)

Todas las figuras fueron verificadas a **300 DPI** con la identidad visual corporativa de Walmart (`#0071CE`, `#FFC220`, `#041E42`):

| N.º | Archivo exacto (`outputs/figures/`) | Tamaño | Subsección Word | Título académico sugerido |
| :--- | :--- | ---: | :--- | :--- |
| Figura 1 | `fig01_validation_metrics_comparison.png` | 329.4 KB | 8.2. Evaluación Predictiva | Comparativa global de error (MAE, RMSE y RMSSE) y estabilidad temporal por ventana rodante: Random Forest frente a líneas base. |
| Figura 2 | `fig02_rmsse_store_snap_breakdown.png` | 218.3 KB | 8.2. Evaluación Predictiva | Desglose del RMSSE de Random Forest por tienda de California (CA_1–CA_4), departamento (FOODS_1–3) y días con beneficio SNAP (snap_CA). |
| Figura 3 | `fig03_feature_importance_rf.png` | 237.2 KB | 8.2. Evaluación Predictiva | Ranking de importancia relativa de las 16 variables predictoras en el modelo operativo Random Forest final. |
| Figura 4 | `fig04_actual_vs_forecast_examples.png` | 776.0 KB | 8.2. Evaluación Predictiva | Series reales frente a validación Ventana 4 y pronóstico operativo a 28 días (d_1942–d_1969) en tres arquetipos representativos de demanda. |
| Figura 5 | `fig05_risk_distribution_store_dept.png` | 268.5 KB | 8.3. Diagnóstico Comercial y Riesgo | Distribución del Ingreso en Riesgo proyectado a 28 días (USD) y conteo de SKUs por tienda, departamento y nivel de riesgo. |
| Figura 6 | `fig06_kmeans_elbow_silhouette.png` | 258.6 KB | 8.4. Segmentación K-Means | Validación empírica del número óptimo de clústeres (K = 2..6): Método del Codo (WCSS) y Coeficiente de Silueta. |
| Figura 7 | `fig07_kmeans_cluster_profiles.png` | 376.2 KB | 8.4. Segmentación K-Means | Perfiles empíricos de los 4 clústeres K-Means (centroides reales y concentración del Ingreso en Riesgo USD frente al volumen de SKUs). |
| Figura 8 | `fig08_prescriptive_marketing_revenue_risk.png` | 261.0 KB | 8.5. Plan Promocional Prescriptivo | Cobertura de portafolio e Ingreso en Riesgo (USD) asignado a cada línea del motor prescriptivo de marketing y capa transversal SNAP. |

---

## Anexo B — Tabla de Actualización para Diapositivas PDF (`Pronóstico M5 con Random Forest_20261126_182808_0000.pdf`)

La siguiente tabla reemplaza los valores maqueta/placeholder de las láminas (especialmente la Diapositiva 5) por las cifras empíricas reales y auditables obtenidas en la ejecución del proyecto:

| Elemento Placeholder en PDF | Cifra Empírica Real de Reemplazo | Fuente Auditable | Nota de Interpretación para Sustentación |
| :--- | :--- | :--- | :--- |
| Diapositiva 5 — Tarjeta `37% Baja Rotación` | **`56.4%` en Riesgo Comercial** (`3,243` SKUs: `2.2%` Riesgo Alto + `54.2%` Riesgo Medio) · Intermitencia global real: **`49.89%`** · Clúster C3 Crítico: **`11.4%` SKUs = `72.7%` del Riesgo** | `sku_store_diagnosis.csv`, `etl_audit.json`, `kmeans_cluster_profiles.csv` | Reemplazar el placeholder `37%` por `56.4% SKUs en Riesgo Comercial` (o destacar el dato Pareto del Clúster C3: `11.4% SKUs concentran 72.7% del riesgo`). |
| Diapositiva 5 — Tarjeta `USD 1.2M Ingreso en Riesgo` | **`$59,362.23` USD en 28 días** (`22,114` unidades proyectadas en desaceleración en `FOODS` CA_1–CA_4; tienda `CA_3` lidera con `$25,363.34` = `42.7%`) | `diagnosis_audit.json`, `sku_store_diagnosis.csv` | La cifra maqueta `USD 1.2M` sobreestimaba la ventana mensual de 4 tiendas; la exposición real auditable para el horizonte de 28 días en California FOODS es **`$59,362.23` USD**. |
| Diapositiva 5 — Fila maqueta `Producto A` | **`FOODS_3_282_CA_3_evaluation`** (`$2.56` · Declive `37.5%` · Riesgo **`$1,156.11`** · Sens. Precio `-99.0%` · SNAP `+19.7%` → **Cross-Selling con ancla `FOODS_3_090` + SNAP Bifásico**) | `top_50_priority_promotions.csv` (Rango #1) | Sustituye al genérico `Producto A` por el SKU #1 de mayor exposición económica en Riesgo Alto (demanda inelástica al precio, sin descuento para proteger margen). |
| Diapositiva 5 — Fila maqueta `Producto B` | **`FOODS_3_587_CA_1_evaluation`** (`$2.48` · Declive `23.9%` · Riesgo **`$423.60`** · Sens. Precio **`+63.8%`** · SNAP `+11.2%` → **Markdown `20%–25%` + LEFO→FEFO + reposición -20%/-30%**) | `top_50_priority_promotions.csv` (Rango #5) | Sustituye al genérico `Producto B` por el principal SKU elegible para Precios Dinámicos con elasticidad promocional positiva comprobada. |
| Diapositiva 5 — Fila maqueta `Producto C` | **`FOODS_2_029_CA_3_evaluation`** (`$9.98` · Declive `17.9%` · Riesgo **`$376.45`** · Sens. Precio `-96.6%` · SNAP **`+30.8%`** → **Cross-Selling con `FOODS_2_360` + Prioridad SNAP**) | `top_50_priority_promotions.csv` (Rango #8) | Sustituye al genérico `Producto C` por un SKU de `FOODS_2` con fuerte dependencia del ciclo SNAP (`+30.8%`) y alto ticket unitario. |
| Diapositivas de Modelado / Resultados RF | **Random Forest RMSE = `2.7190`** (mejor modelo: `+20.75%` vs Seasonal Naïve, `+6.18%` vs SES, `+1.43%` vs MA28) · **RMSSE = `0.7953`** (`+23.24%` vs Seasonal Naïve) · Top features: `rolling_mean_28` (`29.62%`) y `rolling_mean_7` (`23.51%`) | `validation_metrics_summary.csv`, `feature_importance.csv` | Respaldar la defensa oral con el resultado exacto de las 4 ventanas rodantes (5,748 series, cero *data leakage*). |
| Diapositiva de Estrategia SNAP y Marketing | **Prioridad SNAP (`>=15%`):** `1,831` SKUs (`31.9%`) cubren **`$24,009.32` USD** (`40.4%` del riesgo) · **Cross-Selling:** `2,818` SKUs (`73.0%` riesgo) · **Markdown 20%–35%:** `425` SKUs (`10.1%` riesgo) | `diagnosis_audit.json`, `sku_store_diagnosis.csv` | Demuestra que la gran mayoría del riesgo (`73.0%`) requiere Cross-Selling sin erosionar margen y solo el `7.4%` (`425` SKUs) justifica rebajas directas. |

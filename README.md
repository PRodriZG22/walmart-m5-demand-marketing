# Pronóstico de Demanda y Marketing Prescriptivo — Walmart M5 (FOODS · California)

**Universidad Nacional de Cañete (UNDC) — 2026**  
**Curso:** Inteligencia Artificial Aplicada al Marketing Digital

> 🌐 **Dashboard público en Streamlit Community Cloud:** `https://walmart-m5-california.streamlit.app/`

Proyecto analítico reproducible de pronóstico de demanda a 28 días (`RandomForestRegressor`), diagnóstico de riesgo comercial (Ingreso en Riesgo en USD), segmentación de portafolio (`K-Means`) y motor prescriptivo de acciones promocionales (Precios Dinámicos/Markdown, Cross-Selling Omnicanal y Sincronización SNAP), basado exclusivamente en datos reales del dataset **Kaggle M5 Forecasting** (`FOODS` en California: `CA_1`, `CA_2`, `CA_3`, `CA_4` — 1,437 productos × 4 tiendas = 5,748 series producto-tienda).

---

## Guía rápida para el equipo (3 comandos, sin descargar Kaggle)

El repositorio ya incluye los archivos ligeros procesados (`dashboard_sales_90d.parquet`, `val_window4_predictions.parquet`, `forecast_28d.parquet`) y todas las tablas/métricas en `outputs/`. **No necesitas descargar los 310 MB de Kaggle** para revisar ni ejecutar el dashboard en local:

```bash
git clone <URL_DEL_REPOSITORIO> && cd walmart-m5-demand-marketing
pip install -r requirements.txt
streamlit run app/dashboard.py
```

*(Opcional recomendado: crea un entorno virtual con `python -m venv .venv` y actívalo antes de `pip install -r requirements.txt`.)*

---

## Solo si deseas re-entrenar Random Forest desde cero (pipeline completo)

Si algún integrante necesita regenerar el ETL, re-entrenar el modelo o reconstruir los entregables Word/PPTX/PDF:

1. **Instala las dependencias completas de desarrollo:**
   ```bash
   pip install -r requirements-dev.txt
   ```
2. **Descarga el dataset oficial de Kaggle M5 Forecasting (Accuracy)** y coloca estos **3 archivos CSV** dentro de `data/raw/`:
   - `data/raw/sales_train_evaluation.csv`
   - `data/raw/calendar.csv`
   - `data/raw/sell_prices.csv`
3. Ejecuta los scripts de `src/` en orden secuencial (`00` → `05`), según el detalle al final de este documento.

---

## Flujo simple de colaboración en Git (para el equipo)

Para evitar conflictos al trabajar entre los 4 integrantes:

1. **Antes de empezar a editar**, actualiza tu copia local:
   ```bash
   git checkout main
   git pull origin main
   ```
2. **Crea una rama corta para tu cambio** (ej. ajustes al informe, presentación o dashboard):
   ```bash
   git checkout -b feat/descripcion-corta
   ```
3. **Guarda y sube tu rama** para revisión en GitHub (Pull Request hacia `main`):
   ```bash
   git add <archivos_modificados>
   git commit -m "feat: describe brevemente tu cambio"
   git push -u origin feat/descripcion-corta
   ```
4. **Regla de higiene:** nunca subas manualmente los CSV crudos de `data/raw/`, los `.parquet` pesados ni la carpeta `.venv/` (ya están protegidos por `.gitignore`).

---

## Estructura del proyecto

```text
walmart-m5-demand-marketing/
├── AGENTS.md                        # Reglas maestras, alcance real, anti-leakage y control de RAM
├── DESIGN.md                        # Sistema de diseño Apple Bento del dashboard
├── README.md                        # Guía del equipo, despliegue y pipeline reproducible
├── .gitignore                       # Exclusiones de entorno, CSVs crudos y parquets pesados
├── .streamlit/config.toml           # Tema claro Apple Bento para Streamlit Cloud y local
├── requirements.txt                 # Dependencias ligeras para Streamlit Community Cloud
├── requirements-dev.txt             # Dependencias completas para pipeline local y entregables
├── plan/                            # Especificaciones ejecutables paso a paso (00 al 05)
├── docs/                            # Documentos académicos base de referencia
├── data/
│   ├── raw/                         # CSV originales de Kaggle M5 (ignorados en Git)
│   └── processed/                   # 3 parquets ligeros en Git (dashboard_sales_90d, val_window4, forecast_28d)
├── src/                             # Scripts numerados del pipeline (00 al 09) + config.py
├── app/                             # Dashboard interactivo autocontenido (app/dashboard.py)
└── outputs/
    ├── metrics/                     # Auditorías y métricas en JSON
    ├── tables/                      # Tablas finales en CSV para análisis e informe
    ├── figures/                     # Gráficos académicos y capturas PNG (fig01–fig11)
    ├── presentacion_web/            # Presentación HTML interactiva
    └── Walmart_*                    # Entregables finales (.docx, .pdf, .pptx) y guiones
```

---

## Perfil de hardware calibrado (entrenamiento local)

- **Sistema operativo:** Windows (64-bit) · **Nube:** Streamlit Community Cloud (Linux, 1 GB RAM)
- **Python:** `3.14.3` (sin `statsmodels`; Suavizado Exponencial Simple implementado vectorizado en `numpy`)
- **CPU:** Intel Core i7-1255U (10 núcleos / 12 hilos) — ejecución limitada a `n_jobs=6` para estabilidad térmica y de memoria
- **RAM:** 16 GB físicos (~4.6 GB libres típicos) — downcasting estricto (`float32`, `int16`, `int8`, `category`), persistencia `.parquet` y limpieza explícita con `gc.collect()`

---

## Orden estricto de ejecución (re-entrenamiento completo)

Cada fase depende directamente de los artefactos validados de la fase anterior. Ejecutar siempre en secuencia:

1. **`plan/00_orquestacion_y_reglas.md`** — Verificar entorno, `src/config.py` y ejecutar `src/00_verify_data.py` para auditar los 3 CSV crudos.
2. **`plan/01_etl_y_feature_engineering.md`** — Ejecutar `src/01_etl_features.py` para filtrar `FOODS` + `CA`, limpiar pre-lanzamientos, aplicar downcasting y construir variables sin *data leakage*.
3. **`plan/02_validacion_y_random_forest.md`** — Ejecutar `src/02_train_validate.py` (primero con `--fast-dev` y luego completo) para validación rodante de 4 ventanas de 28 días, comparación contra 3 baselines, métricas MAE/RMSE/RMSSE, pronóstico futuro de 28 días y figuras `fig01`–`fig04`.
4. **`plan/03_diagnostico_y_kmeans.md`** — Ejecutar `src/03_diagnosis_kmeans_marketing.py` para calcular los indicadores de riesgo comercial, ajustar K-Means, ejecutar el motor prescriptivo de marketing y generar `fig05`–`fig08`.
5. **`plan/04_dashboard_interactivo.md`** — Ejecutar y verificar `app/dashboard.py` (Streamlit + Plotly) con 4 pestañas ejecutivas, filtros globales y simulador interactivo de Markdown.
6. **`plan/05_reporte_para_informe_word.md`** — Ejecutar `src/05_generate_report_package.py` para compilar `outputs/RESULTADOS_PARA_INFORME_WORD.md` y construir los entregables finales.

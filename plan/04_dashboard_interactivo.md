# Paso 04 — Dashboard Interactivo de Decisión Comercial (Streamlit + Plotly)

## Objetivo

Desarrollar la aplicación web interactiva `app/dashboard.py` en **Streamlit + Plotly** para que el equipo de marketing y abastecimiento de Walmart California explore los pronósticos a 28 días, valide el desempeño del modelo Random Forest, inspeccione los clústeres K-Means y simule promociones Markdown sobre las 5,748 series de `FOODS`.

---

## 1. Arquitectura, rendimiento e identidad visual

- **Framework:** `streamlit` + `plotly.express` / `plotly.graph_objects`, con las versiones fijadas en `requirements.txt`.
- **Identidad visual y lenguaje:** manda `DESIGN.md` (paleta, tarjetas HTML sin `st.metric`, vistas por usuario).
- **Memoria y velocidad:** lecturas con `@st.cache_data` y solo las columnas necesarias.
- **Filtros sin resultados:** `st.warning` en cada pestaña de negocio, indicando qué filtro revisar; la auditoría sigue visible.

---

## 2. Panel lateral: vista y filtros

- **Vista (`?vista=`):** gerente, gestor o analista (ver `DESIGN.md`, sección 10).
- **Filtros:** tienda, departamento, nivel de riesgo, búsqueda de producto, estrategia, grupo K-Means, solo sensibles a SNAP y, en la vista de gestor, solo con ingreso en riesgo mayor que 0.
- Botón para restablecer, selección guardada en la URL y total de series por opción.

---

## 3. Contenido por pestaña

Las pestañas visibles dependen de la vista.

### Resumen o Cartera de decisiones
- Indicadores: ingreso en riesgo (USD) frente a 90 días y su comparación con 28 días; series en riesgo alto y medio; series sensibles a SNAP; series casi sin ventas en riesgo bajo; alertas sin monto.
- Gráficos: riesgo por tienda; riesgo según evidencia de respuesta a rebajas; tienda por departamento; series por estrategia y riesgo; caídas frente a subidas.
- Nota de transparencia M5: sin stock físico, costos ni vencimientos.

### Decisión por producto
- Serie de 90 días, ventana 4 de validación, pronóstico de 28 días, corte histórico y días SNAP.
- Ficha: velocidades, intermitencia, precio, ingreso en riesgo, respuesta a precio y SNAP, estrategia, ancla, avisos y calendario (días SNAP 1–10; cupones de fin de mes fuera de SNAP).

### Simulador y plan
- Descuento de 20% a 35% sobre series elegibles (riesgo alto o medio y `price_sensitivity >= 0.10`).
- Escenarios supuestos (ε = 0.4, 0.6, 0.8) y un escenario de referencia con `price_sensitivity` acotado entre 0 y el tope optimista.
- Ingreso base, ingreso con rebaja, diferencia neta y respuesta necesaria para no perder ingreso. No calcula margen.
- Tabla priorizada, descarga del plan (`plan_promociones_walmart_ca.csv`) y lista de revisión manual de reposición. El tablero no envía alertas a otros sistemas.

### Respaldo IA
- Métricas por ventana, comparación de métodos, acierto de la señal de caída, desglose, importancia de variables y K-Means (indicando que K = 4 se eligió por utilidad comercial).

---

## 4. Verificación de ejecución del Paso 04

- Validar sintaxis e importaciones de `app/dashboard.py` con el Python del `.venv`.
- Ejecutar prueba de arranque local (`streamlit run app/dashboard.py --server.headless true`) y verificar que carga sin errores de runtime, sin advertencias críticas y con todos los archivos de datos leídos correctamente.

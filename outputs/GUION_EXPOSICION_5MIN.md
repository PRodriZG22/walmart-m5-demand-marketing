# Guion de Sustentación (5 Minutos) y Demostración en Vivo (2 Minutos)

**Proyecto:** Pronóstico de Demanda con Random Forest para Orientar Promociones en Walmart California (`FOODS`)  
**Universidad Nacional de Cañete (UNDC) — 2026** · Facultad de Ingeniería — Escuela Profesional de Ingeniería de Sistemas  
**Integrantes:**
1. Chulluncuy Cambillo, Adolfo Milton
2. Felix Delgado, Alexander
3. Siccha Dávila, Angel
4. Zavala Gamero, Piero Rodrigo

> **Nota de ritmo:** Total presentación con diapositivas = **5:00 min** (~35–40 s por lámina, 1:15 min por expositor) + **2:00 min** de recorrido en vivo por el dashboard (`http://localhost:8501`). Todas las cifras están 100% auditadas con el pipeline real.

---

## Parte 1 — Guion Diapositiva por Diapositiva (5 Minutos)

### Expositor 1 · Adolfo Milton Chulluncuy Cambillo (0:00 – 1:15 · Diapositivas 1 y 2)

- **Diapositiva 1 — Portada (0:00 – 0:30):**
  > *"Buenos días con todos. Somos estudiantes de Ingeniería de Sistemas de la UNDC y presentamos nuestro prototipo de Inteligencia Artificial Aplicada al Marketing Digital: un sistema de pronóstico de demanda con Random Forest orientado a decisiones promocionales reales en alimentos de Walmart California."*
- **Diapositiva 2 — La empresa: Walmart (0:30 – 1:15):**
  > *"Walmart opera bajo un modelo omnicanal y la promesa 'Save money. Live better.'. En este proyecto aterrizamos esa estrategia sobre datos reales publicados en el dataset M5: analizamos exclusivamente la categoría de alimentos (`FOODS`) en las cuatro tiendas de California (`CA_1` a `CA_4`), lo que representa 1,437 productos y 5,748 series producto-tienda."*

---

### Expositor 2 · Alexander Felix Delgado (1:15 – 2:30 · Diapositivas 3 y 4)

- **Diapositiva 3 — Realidad Problemática y La Brecha (1:15 – 1:50):**
  > *"En retail enfrentamos tres problemas concretos: cada error de pronóstico inmoviliza capital o genera quiebres; las promociones mal diseñadas destruyen margen y provocan caídas post-oferta de 20% a 30% por acaparamiento; y la competencia original M5 se quedó solo en la precisión estadística sin decirle a marketing qué hacer. Nuestra brecha es conectar el pronóstico directamente con acciones promocionales diferenciadas."*
- **Diapositiva 4 — La Data Real M5 (1:50 – 2:30):**
  > *"Integramos tres archivos reales —ventas diarias, precios semanales y calendario con días SNAP— sobre tres años completos (mayo 2013 a mayo 2016). Eliminamos 682,592 filas pre-lanzamiento y conservamos 5,710,335 días activos reales, logrando una reducción de 81.28% en memoria RAM. Descubrimos que el 49.89% de los días activos tienen venta cero, y dejamos constancia transparente de que M5 no incluye stock físico ni costos unitarios."*

---

### Expositor 3 · Angel Siccha Dávila (2:30 – 3:45 · Diapositivas 5 y 6)

- **Diapositiva 5 — Objetivo General y Resultados Clave *(usar `Diapositiva_05_Actualizada.png`)* (2:30 – 3:10):**
  > *"Nuestro objetivo general fue evaluar este prototipo de extremo a extremo en cuatro objetivos específicos: preparar datos sin data leakage, medir precisión frente a líneas base, cuantificar el ingreso en riesgo real y desplegar un plan promocional en dashboard. Como ven en la lámina actualizada, identificamos **$59,362.23 USD en Ingreso en Riesgo** para los próximos 28 días (22,114 unidades), con un **56.4%** del catálogo en riesgo accionable y un hallazgo Pareto decisivo: apenas el **11.4%** de los productos (Clúster C3) concentra el **72.7%** del dinero en riesgo."*
- **Diapositiva 6 — Marco Teórico (3:10 – 3:45):**
  > *"El diseño se respalda en seis pilares científicos: la evolución hacia aprendizaje automático en retail, la capacidad híbrida de Random Forest, las lecciones de la competencia M5 (donde 92.5% de equipos no venció al suavizado exponencial), la analítica comercial, la teoría de precios dinámicos 20%–35% con migración LEFO a FEFO de Riesenegger y Hübner (2026), y el ciclo mensual de pagos SNAP."*

---

### Expositor 4 · Piero Rodrigo Zavala Gamero (3:45 – 5:00 · Diapositivas 7 y 8)

- **Diapositiva 7 — Metodología CRISP-DM y Validación (3:45 – 4:25):**
  > *"Bajo CRISP-DM construimos 16 variables estrictamente libres de fuga temporal —todo rezago y media móvil usa `t-28` o anterior— y validamos por origen rodante en 4 ventanas consecutivas de 28 días. **Random Forest obtuvo el mejor RMSE global (`2.7190`)**, superando a Seasonal Naïve en **+20.75%**, a SES en **+6.18%** y a MA28 en **+1.43%**, con `rolling_mean_28` (29.62%) y `rolling_mean_7` (23.51%) como variables líderes."*
- **Diapositiva 8 — Diagnóstico Comercial, K-Means y Plan Prescriptivo (4:25 – 5:00):**
  > *"Tradujimos el pronóstico a 5 indicadores reales y segmentamos las 5,748 series con K-Means validado por Silueta en **`K = 4`** (`0.2824`). Así el motor prescriptivo bloquea rebajas donde no funcionan —asignando **Cross-Selling sin descuento al 73.0% del riesgo** (`2,818` SKUs)—, reserva **Markdowns del 20%–35%** solo para los **`425` productos realmente elásticos** y sincroniza **`1,831` productos** (40.4% del riesgo) con el calendario SNAP. Ahora veremos el prototipo funcionando en vivo."*

---

## Parte 2 — Recorrido Guiado en Vivo por el Dashboard (2 Minutos)

Antes de iniciar, tener abierto `http://localhost:8501` en Brave (ejecutado con `.\.venv\Scripts\streamlit.exe run app\dashboard.py`):

1. **Pestaña 1 — Resumen Ejecutivo (0:00 – 0:30):**
   - Señalar las 4 tarjetas KPI (`$59,362` en riesgo, `125` alertas críticas, `72.7%` Foco Pareto en 653 productos, `40.4%` impacto SNAP).
   - Mostrar las **3 Decisiones Inmediatas** y destacar en los 2 gráficos que **`CA_3`** concentra el `42.7%` (`$25,363`) del riesgo y que **Cross-Selling sin descuento** protege el `73.0%` del ingreso.
2. **Pestaña 2 — Decisión por Producto (0:30 – 1:05):**
   - Mostrar el producto #1 por defecto (**`FOODS_3_282` en `CA_3`**, `$1,156.11` en riesgo): señalar la **Tarjeta Semáforo** que prohíbe rebajar precio y recomienda empaquetarlo con el ancla **`FOODS_3_090`**, mostrar la curva de 90d reales vs pronóstico 28d con franjas amarillas SNAP y el eje de precios limpio.
   - *(Opcional rápido)*: escribir `FOODS_3_587` en el buscador lateral para mostrar un caso que **sí** activa **Markdown `20%–25%`** por sensibilidad positiva (`+63.8%`).
3. **Pestaña 3 — Simulador de Campañas (1:05 – 1:35):**
   - Mover el deslizador de descuento de `25%` a `30%` y alternar `Esperado (ε=0.6)` → `Optimista (ε=0.8)` para evidenciar el recálculo en tiempo real de demanda extra, ingreso recuperado y el aviso de **Ajuste de reposición `-20% a -30%`**.
   - Señalar la tabla priorizada sin scroll horizontal y el botón de descarga `.CSV` para Excel.
4. **Pestaña 4 — Respaldo IA / Auditoría Técnica (1:35 – 2:00):**
   - Mostrar rápidamente la tabla comparativa (Random Forest primero con mejor `RMSE = 2.7190`), las 16 variables predictoras y el gráfico Codo + Silueta (`K = 4`) con el mapa de clústeres.

---

## Parte 3 — Banco de 4 Respuestas Cortas para el Jurado

1. **¿Por qué hablaron de "Ingreso en Riesgo" y no de merma física o pérdida de margen real?**
   > *"Por rigor y veracidad metodológica. El dataset oficial Kaggle M5 publica ventas diarias, precios de venta y calendario/SNAP, pero no incluye stock físico en almacén, costo de compra (COGS) ni fechas de vencimiento. En lugar de inventar costos o inventarios simulados, cuantificamos la desaceleración real proyectada (`v90` frente a `pred_v28`) valorizada a precio vigente en tienda, dejando el prototipo listo para conectarse al ERP de Walmart en producción."*

2. **¿Por qué Random Forest tiene el mejor RMSE (`2.7190`), pero `MA28` (`0.7785`) y `SES` (`0.7807`) quedaron ~2% por debajo en RMSSE no ponderado?**
   > *"Es un hallazgo empírico esperado que coincide exactamente con los resultados oficiales de Makridakis et al. en la competencia M5. En promedios simples por SKU con 49.9% de días en cero, un nivel plano anclado en el último día (`SES`/`MA28`) es muy difícil de batir; además nuestro Random Forest pronostica directamente a 28 días usando solo rezagos `>= t-28` para garantizar cero data leakage. Sin embargo, Random Forest vence claramente en **RMSE** (+6.18% vs SES y +20.75% vs Seasonal Naïve) porque acierta mejor en los productos de mayor volumen y aporta lo que SES no puede hacer: modelar estacionalidad semanal, cambios de precio y días SNAP."*

3. **¿Por qué el motor bloquea los descuentos en el 73.0% del dinero en riesgo (`2,818` SKUs) y solo aprueba rebajas en `425` productos?**
   > *"Porque la evidencia empírica mostró que la mayoría de SKUs en desaceleración tienen sensibilidad nula o negativa ante rebajas históricas (o nunca fueron descontados). Como demuestran Riesenegger y Hübner (2026), bajar precios a productos inelásticos regala margen sin evacuar inventario. Por eso nuestro motor protege la rentabilidad prescribiendo **Cross-Selling con productos ancla verificados** en ese 73.0% y reservando los Markdowns 20%–35% únicamente donde hay elasticidad positiva comprobada (`>= 10%`), siempre con alerta de reducir pedidos post-oferta en `-20% a -30%`."*

4. **¿Qué valor práctico aporta K-Means (`K = 4`) si ya tenían reglas de Riesgo Alto, Medio y Bajo?**
   > *"Las reglas de riesgo miden urgencia individual, pero K-Means revela la estructura multidimensional del portafolio y genera una priorización ejecutiva inmediata: descubrió el **Clúster C3**, donde apenas el **11.4% de los productos (`653` SKUs) concentran el 72.7% de todo el Ingreso en Riesgo** (`$43,126.87` USD), y aisló además un nicho de `228` artículos altamente elásticos (`+620%` en oferta, Clúster C0). Eso permite al gerente de marketing focalizar su presupuesto donde está tres cuartas partes del impacto económico."*

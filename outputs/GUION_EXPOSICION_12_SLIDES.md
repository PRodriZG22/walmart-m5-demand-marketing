# Guion de Sustentación (12 Diapositivas · 5 Minutos) y Demo en Vivo (2 Minutos)

**Proyecto:** Pronóstico de Demanda con Random Forest para Orientar Promociones en Walmart California (`FOODS`)  
**Universidad Nacional de Cañete (UNDC) — 2026** · Facultad de Ingeniería — Escuela Profesional de Ingeniería de Sistemas  
**Curso:** IA Aplicada al Marketing Digital  

**Distribución equilibrada (3 diapositivas y 1:15 min por expositor):**
- **Bloque 1 (Slides 1–3 · `0:00 – 1:15`):** Chulluncuy Cambillo, Adolfo Milton
- **Bloque 2 (Slides 4–6 · `1:15 – 2:30`):** Felix Delgado, Alexander
- **Bloque 3 (Slides 7–9 · `2:30 – 3:45`):** Siccha Dávila, Angel
- **Bloque 4 (Slides 10–12 · `3:45 – 5:00` + Demo 2 min):** Zavala Gamero, Piero Rodrigo

> **Consejo de ejecución:** Abrir `outputs/presentacion_web/index.html` en Brave/Edge (o `outputs/Walmart_Presentacion_Final.pptx`) en pantalla completa (`F`) y tener pre-abierto `http://localhost:8501` en otra pestaña con `.\.venv\Scripts\streamlit.exe run app\dashboard.py`. En la versión web pueden activar las notas discretas con la tecla `N`.

---

## Parte 1 — Guion Exacto por Diapositiva (5:00 Minutos)

### Bloque 1 · Chulluncuy Cambillo, Adolfo Milton (`0:00 – 1:15` · Slides 1–3)

- **Slide 1 — Portada (`0:00 – 0:25`):**
  > *"Buenos días señores miembros del jurado y compañeros. Somos estudiantes de Ingeniería de Sistemas de la UNDC y presentamos nuestro prototipo de IA Aplicada al Marketing Digital: un sistema de pronóstico de demanda con Random Forest orientado a decidir promociones reales en alimentos de Walmart California."*

- **Slide 2 — La Problemática: "La Brecha" (`0:25 – 0:50`):**
  > *"En retail alimentario existen tres dolores concretos: primero, el error de pronóstico cuesta dinero —alrededor de 2% en mermas y 8% en quiebres de stock—; segundo, las promociones sin criterio destruyen margen y desploman la venta post-oferta entre -20% y -30% por acaparamiento; y tercero, en la competencia Kaggle M5 el 92.5% de equipos no superó al suavizado exponencial y ninguno conectó la predicción con marketing. Nuestra brecha es cerrar exactamente ese puente."*

- **Slide 3 — Alcance, Datos M5 y Objetivos (`0:50 – 1:15`):**
  > *"Aterrizamos el estudio en datos 100% reales de Kaggle M5 para alimentos (`FOODS`) en las cuatro tiendas de California (`CA_1` a `CA_4`): **1,437 productos**, **5,748 series** durante **3 años completos** y **49.89% de intermitencia real**. Definimos cuatro objetivos específicos —desde ETL sin fuga hasta el dashboard en Streamlit— declarando con total transparencia que M5 no incluye stock físico ni costos simulados. Doy pase a mi compañero Alexander."*

---

### Bloque 2 · Felix Delgado, Alexander (`1:15 – 2:30` · Slides 4–6)

- **Slide 4 — Metodología CRISP-DM y Pipeline sin Fuga (`1:15 – 1:40`):**
  > *"Gracias Adolfo. Ejecutamos el prototipo bajo CRISP-DM en seis fases auditadas con cuatro logros técnicos clave: depuramos 682,592 filas pre-lanzamiento conservando **5.71 millones de registros activos**, redujimos la RAM en **81.28%** vía downcasting y Parquet, construimos **16 variables estrictamente >= t-28** con auditoría anti-fuga **PASS 200/200**, y validamos cronológicamente en **4 ventanas rodantes** de 28 días."*

- **Slide 5 — Evaluación Predictiva: Random Forest vs. Baselines (`1:40 – 2:05`):**
  > *"En la Figura 1 vemos los resultados sobre las 5,748 series: **Random Forest logra el menor RMSE global (2.7190)**, superando a Seasonal Naïve en **+20.75%**, a SES en **+6.18%** y a MA28 en **+1.43%**. Con transparencia científica, en el RMSSE simple (0.7953) MA28 y SES lideran ~2% en series planas —exactamente como reporta la literatura M5—, pero solo Random Forest captura picos de volumen e incorpora precio, calendario y días SNAP."*

- **Slide 6 — Variables Clave y Volatilidad SNAP (`2:05 – 2:30`):**
  > *"Al auditar la importancia de variables en la Figura 3, la memoria reciente de demanda (`>= t-28`) concentra el **91.8%** del poder explicativo —liderada por `rolling_mean_28` (29.6%) y `rolling_mean_7` (23.5%)—, seguida del bloque de precios con **3.96%**. Complementariamente, el desglose por segmento demuestra que en días `snap_CA = 1` el RMSE sube **+3.56%** por picos de inicio de mes, siendo `CA_3` la tienda mejor calibrada (`0.763`) y `CA_2` la más volátil (`0.864`). Adelante Angel."*

---

### Bloque 3 · Siccha Dávila, Angel (`2:30 – 3:45` · Slides 7–9)

- **Slide 7 — Diagnóstico de Riesgo en 28 Días (`2:30 – 2:55`):**
  > *"Gracias Alexander. Al traducir las caídas proyectadas frente al ritmo reciente de 90 días a precio vigente, cuantificamos **$59,362 USD en Ingreso en Riesgo** para los próximos 28 días (**22,114 unidades**). El **56.4%** del catálogo está en Riesgo Alto o Medio (concentrando el 83.1% del dinero) y la tienda **`CA_3`** lidera sola con **$25,363 USD**, es decir el **42.7%** del riesgo total, mientras `FOODS_3` agrupa casi el 60%."*

- **Slide 8 — Segmentación K-Means y Hallazgo Pareto (`2:55 – 3:20`):**
  > *"Con K-Means estandarizado y winsorización controlada, **`K = 4`** alcanzó el óptimo accionable con Silueta **`0.2824`**, como muestran las figuras 6 y 7. Aquí emerge nuestro hallazgo estratégico más potente: una concentración tipo Pareto en el **Clúster C3**, donde apenas el **11.4% de los productos (653 SKUs)** concentran el **72.7% de todo el Ingreso en Riesgo ($43,127 USD)**, permitiéndole a gerencia focalizar el esfuerzo con precisión quirúrgica."*

- **Slide 9 — Plan Prescriptivo de Marketing (`3:20 – 3:45`):**
  > *"Con las elasticidades reales comprobadas, nuestro motor prescriptivo protege la rentabilidad en tres líneas claras: primero, **Cross-Selling sin descuento** para el **73.0% del riesgo (2,818 SKUs inelásticos)** empaquetados con un producto ancla; segundo, **Markdown selectivo del 20%–35%** exclusivamente en los **425 SKUs con elasticidad positiva**, acompañado de rotación FEFO y alerta de recorte de reposición de **-20% a -30%**; y tercero, una capa transversal **SNAP bifásica** sobre **1,831 SKUs (40.4% del riesgo)**. Doy pase a Piero para el cierre y la demo en vivo."*

---

### Bloque 4 · Zavala Gamero, Piero Rodrigo (`3:45 – 5:00` · Slides 10–12)

- **Slide 10 — Dashboard Interactivo y Demo en Vivo (`3:45 – 4:10`):**
  > *"Gracias Angel. Integramos todo el pipeline en un dashboard ejecutivo en Streamlit de 4 pestañas que consume solo **8.58 MB de RAM** gracias a PyArrow pushdown. Como ven en pantalla, permite auditar casos reales: **`FOODS_3_282`** en `CA_3` protegido con Cross-Selling (**$1,156** en riesgo), **`FOODS_3_587`** en `CA_1` apto para Markdown por su **+63.8%** de elasticidad, y el simulador al **25%** proyectando recuperar **+$9,169 USD**."*

- **Slide 11 — Conclusiones Empíricas y Alcances Futuros (`4:10 – 4:40`):**
  > *"Validamos cuantitativamente los cuatro objetivos específicos: datos 100% reales sin fuga (`5.71M` filas, `-81.28%` RAM), Random Forest líder en RMSE (`2.7190`), `$59,362` USD geolocalizados y un motor prescriptivo Pareto operativo en Streamlit. Como trabajo futuro proponemos tres pasos: integrar el ERP de stock, costos y vencimientos; escalar a Texas y Wisconsin con un ensamble híbrido `RF + SES/Tweedie`; y ejecutar un piloto A/B de 8 semanas en `CA_3`."*

- **Slide 12 — Cierre (`4:40 – 5:00`):**
  > *"Para resumir el impacto en tres cifras: **$59,362 USD** detectados a 28 días, **72.7%** concentrado en el Clúster C3 y **cero descuentos destructores de margen** en productos inelásticos. Muchas gracias por su atención; pasamos ahora a la demostración en vivo de dos minutos en Streamlit y quedamos atentos a sus preguntas."*

---

## Parte 2 — Recorrido Guiado en Vivo por Streamlit (2:00 Minutos · Piero Zavala)

Pre-requisito: `.\.venv\Scripts\streamlit.exe run app\dashboard.py` abierto en `http://localhost:8501`.

1. **Pestaña 1 — Resumen Ejecutivo (`0:00 – 0:30`):**
   - Señalar las 4 tarjetas KPI (`$59,362` en riesgo · `125` alertas críticas · `72.7%` Foco Pareto en 653 SKUs · `40.4%` impacto SNAP).
   - Mostrar las **3 Decisiones Inmediatas** y los dos gráficos que confirman `CA_3` (`$25,363` = `42.7%`) y **Cross-Selling sin descuento** (`73.0%`).
2. **Pestaña 2 — Decisión por Producto (`0:30 – 1:05`):**
   - Mostrar el SKU #1 por defecto (**`FOODS_3_282` · `CA_3`**, `$1,156.11` en riesgo): explicar la tarjeta semáforo que **prohíbe rebajar precio** y sugiere empaquetarlo con el ancla **`FOODS_3_090`**, junto a las franjas amarillas SNAP y el eje de precio real.
   - Escribir **`FOODS_3_587`** en el buscador para contrastar un producto que **sí activa Markdown `20%–25%`** por elasticidad positiva (`+63.8%`).
3. **Pestaña 3 — Simulador de Campañas (`1:05 – 1:35`):**
   - Mover el deslizador de descuento de `25%` (`+$9,169.40`, `+4,169` u) a `30%` y cambiar de `Esperado (ε=0.6)` a `Optimista (ε=0.8)` para mostrar el recálculo instantáneo y la alerta de reposición **`-20% a -30%`**.
   - Señalar la tabla priorizada y el botón **Descargar plan (`.CSV` para Excel)**.
4. **Pestaña 4 — Respaldo IA / Auditoría Técnica (`1:35 – 2:00`):**
   - Mostrar rápidamente la tabla comparativa (`Random Forest RMSE = 2.7190`), las 16 variables predictoras y la validación Codo + Silueta (`K = 4`, `0.2824`).

---

## Parte 3 — Banco de 4 Respuestas Cortas para el Jurado

1. **¿Por qué miden "Ingreso en Riesgo" y no merma física o pérdida de margen real?**
   > *"Por rigor y veracidad científica. El dataset oficial Kaggle M5 publica ventas diarias, precios de góndola y calendario SNAP, pero no contiene stock físico en almacén, costo de compra (COGS) ni fechas de vencimiento. En lugar de inventar costos o inventarios, cuantificamos la desaceleración real proyectada (`v90` vs. `pred_v28`) valorizada a precio vigente, dejando el prototipo listo para conectarse al ERP de Walmart."*

2. **¿Por qué Random Forest tiene el mejor RMSE (`2.7190`), pero `MA28` (`0.7785`) y `SES` (`0.7807`) quedan ~2% abajo en RMSSE no ponderado?**
   > *"Es un resultado empírico consistente con las conclusiones oficiales de Makridakis et al. en la competencia M5. Con 49.89% de días en cero, un nivel plano anclado en el último corte (`SES`/`MA28`) es difícil de batir en promedio simple por SKU, mientras nuestro Random Forest pronostica directamente a 28 días usando solo rezagos `>= t-28` para asegurar cero data leakage. Sin embargo, Random Forest vence en **RMSE** (+6.18% vs. SES y +20.75% vs. Naïve) porque acierta mejor en los productos de mayor volumen y aporta lo que SES no puede hacer: modelar precio, estacionalidad semanal y días SNAP."*

3. **¿Por qué bloquean descuentos en el 73.0% del dinero en riesgo (`2,818` SKUs) y solo aprueban Markdown en `425` productos?**
   > *"Porque el historial real de precios demostró que la mayoría de SKUs en caída tienen sensibilidad negativa o nula ante rebajas (o nunca tuvieron descuentos previos). Como documentan Riesenegger y Hübner (2026), rebajar artículos inelásticos destruye margen bruto sin acelerar la salida de góndola. Por eso protegemos el 73.0% con **Cross-Selling junto a productos ancla** y reservamos los Markdowns `20%–35%` únicamente donde hay elasticidad comprobada (`>= 10%`), siempre con alerta de recorte de pedido `-20% a -30%`."*

4. **¿Qué valor práctico aporta K-Means (`K = 4`) si ya habían clasificado Riesgo Alto, Medio y Bajo?**
   > *"Las reglas de riesgo miden urgencia individual por SKU, pero K-Means descubre la estructura multidimensional del portafolio y genera priorización ejecutiva inmediata: reveló el **Clúster C3**, donde solo **11.4% de los productos (`653` SKUs) concentran el 72.7% del Ingreso en Riesgo** (`$43,127` USD), y aisló el nicho del **Clúster C0** (`228` artículos altamente elásticos `+620%` en rebaja). Así marketing concentra su presupuesto donde está casi tres cuartas partes del impacto financiero."*

# DESIGN.md — Sistema de Diseño Ejecutivo (Estilo Apple Bento)

> Especificación visual estándar de 9 secciones (formato Stitch / `awesome-design-md`) para el dashboard de inteligencia comercial **Walmart California · Radar de Promociones e Ingresos en Riesgo**. Diseñado para gerentes de marketing y tomadores de decisiones no técnicos.

---

## 1. Visual Theme & Atmosphere

Minimalismo editorial de precisión inspirado en las interfaces ejecutivas de Apple: máxima claridad de lectura en menos de cinco segundos, jerarquía tipográfica nítida, abundante espacio en blanco (*whitespace*) y organización modular en **Bento Grid**. Cada bloque responde una única pregunta de negocio sin adornos, sin contenedores pesados ni ruido visual técnico.

---

## 2. Color Palette & Roles

| Rol | Token / Hex | Uso específico |
|---|---|---|
| **Canvas principal** | `#F5F5F7` *(Apple Light Gray)* | Fondo general de la aplicación para crear contraste suave con las tarjetas. |
| **Superficie / Tarjeta Bento** | `#FFFFFF` *(Pure White)* | Contenedores KPI, tarjetas de decisión, gráficos Plotly y tablas ejecutivas. |
| **Texto principal** | `#1D1D1F` *(Apple Space Black Ink)* | Titulares, cifras KPI, nombres de productos y encabezados de sección. |
| **Texto secundario** | `#6E6E73` *(Apple Muted Gray)* | Subtítulos, explicaciones breves, ejes de gráficos y metadatos contextuales. |
| **Acento interactivo primario** | `#0071E3` *(Apple Blue · hover `#0077ED`)* | Eyebrows, botones principales, pestaña activa, etiquetas de filtro y trazas clave. |
| **Semántica — Crítico / Riesgo Alto** | `#D70015` *(fondo suave `#FFF2F2`)* | Alertas de riesgo alto, pronósticos en caída severa y badges críticos. |
| **Semántica — Alerta / Riesgo Medio** | `#B25000` *(fondo suave `#FFF8EB`, gráfico `#FF9500`)* | Advertencias operativas (*stockpiling*), riesgo medio y combos sin rebaja. |
| **Semántica — Saludable / Positivo** | `#1E7E34` *(fondo suave `#EFFAF1`, gráfico `#34C759`)* | Productos saludables/ancla, métricas positivas y sincronización SNAP. |
| **Semántica — Ciclo SNAP** | `#9A6700` *(fondo suave `#FFFBEB`, banda `#FEF3C7`)* | Badges de prioridad SNAP y sombreado sutil de días de pago gubernamental. |
| **Bordes Hairline y Grilla** | `rgba(0, 0, 0, 0.08)` / `#E5E5EA` | Separadores sutiles de tarjetas, divisores y cuadrícula mínima en gráficos. |

---

## 3. Typography Rules

- **Familia tipográfica:** `-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", "Segoe UI", sans-serif`.
- **Titulares principales:** peso `700`, `letter-spacing: -0.03em` (subtítulos de sección `600`, `-0.02em`), interlineado compacto `1.15–1.25`.
- **Cifras y KPIs:** obligatorio `font-variant-numeric: tabular-nums` y peso `700` para alineación vertical impecable y lectura instantánea de montos y porcentajes.
- **Restricciones:** evitar bloques extensos en MAYÚSCULAS (reservado únicamente a *eyebrows* cortos de 12 px con `letter-spacing: 0.08em`) y evitar tipografías monoespaciadas en títulos orientados a negocio.

---

## 4. Component Stylings

- **Tarjetas Bento (`kpi-card`, `decision-card`, `chart-card`):** `background: #FFFFFF`, `border-radius: 18px`, `padding: 20px 24px`, `border: 1px solid rgba(0, 0, 0, 0.06)`, `box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04)`.
- **Badges / Píldoras de estado:** `border-radius: 999px`, `padding: 4px 12px`, `font-size: 12px`, `font-weight: 600`, alto contraste sobre fondos pastel semánticos.
- **Botones primarios:** forma píldora (`border-radius: 999px`), relleno `#0071E3` (hover `#0077ED`), texto blanco `#FFFFFF`, peso `600`.
- **Selectores e inputs:** superficies blancas `#FFFFFF`, bordes finos `#D2D2D7`, etiquetas en español de negocio sin nombres técnicos de columna entre paréntesis; pills de multiselección en `#0071E3`.
- **Gráficos Plotly:** plantilla `plotly_white`, `paper_bgcolor="#FFFFFF"`, `plot_bgcolor="#FFFFFF"`, `theme=None` en `st.plotly_chart`, grilla mínima `#E5E5EA`, leyendas ubicadas con holgura sin solapamiento.

---

## 5. Layout Principles

- **Rejilla Bento simétrica:** filas equilibradas de 4 KPIs, 3 decisiones estratégicas y máximo **2 gráficos por fila**.
- **Espaciado generoso:** `20px–24px` de separación entre secciones y `16px` de *gap* entre tarjetas para respiración visual.
- **Un mensaje por bloque:** cada gráfico se encabeza con una pregunta directa de negocio (*"¿En qué tienda actuar primero?"*) seguida de una lectura ejecutiva de una sola línea.
- **Flujo progresivo de pestañas:** de decisión gerencial a detalle técnico (`1. Resumen Ejecutivo` → `2. Decisión por Producto` → `3. Simulador de Campañas` → `4. Respaldo IA`).

---

## 6. Depth & Elevation

- La jerarquía visual se construye mediante **contraste limpio de superficie** (`#F5F5F7` de fondo frente a `#FFFFFF` en tarjetas) y sombras ambientales difusas (`0 2px 12px rgba(0, 0, 0, 0.04)`).
- Prohibido usar encabezados oscuros pesados, degradados saturados, bordes gruesos o sombras duras.

---

## 7. Do's and Don'ts

### Do
- Traducir todas las métricas a lenguaje de negocio directo (*"Dinero en riesgo"*, *"Respuesta a rebajas"*, *"Ajuste de reposición"*).
- Construir tarjetas KPI con HTML/CSS Flexbox/Grid propio para mostrar siempre **cifras completas sin truncar** (`$1,156.11`, `-20% a -30%`).
- Ocultar elementos de interfaz irrelevantes de Streamlit (`Deploy`, menú superior redundante y *footer*), preservando siempre el control de colapso del sidebar.
- Formatear fechas en Plotly como strings ISO `"YYYY-MM-DD"` con `type="date"` y usar `add_shape` + `add_annotation`.

### Don't
- No usar `st.metric` en tarjetas clave donde los valores se corten con `...`.
- No exponer jerga técnica (`d_1941`, `_evaluation`, `WCSS`, `RMSSE`, `snap_CA`) en las pestañas gerenciales (reservar el detalle metodológico para la Pestaña 4 *Respaldo IA*).
- No utilizar treemaps densos e ilegibles ni superponer anotaciones sobre etiquetas de barras.
- No aplicar estilos oscuros ni depender de `theme="streamlit"` en Plotly.

---

## 8. Responsive Behavior

- Todas las rejillas Bento (`kpi-grid-4`, `kpi-grid-5`, `kpi-grid-6`, `decision-grid-3`) usan CSS Grid adaptable con tipografía fluida `clamp(...)` para verse nítidas sin recortes en laptops `1366×768` y monitores `1920×1080`.
- En anchos reducidos (`<= 1100px` / `<= 768px`), las grillas colapsan progresivamente a 2 columnas y 1 columna manteniendo legibilidad completa de montos y subtítulos.

---

## 9. Agent Prompt Guide

Al realizar futuras modificaciones sobre `app/dashboard.py`:
1. Mantener `.streamlit/config.toml` con `base="light"`, `primaryColor="#0071E3"`, `backgroundColor="#F5F5F7"`, `secondaryBackgroundColor="#FFFFFF"` y `textColor="#1D1D1F"`.
2. Respetar los tokens de color de la Sección 2, `border-radius: 18px` en tarjetas Bento, `tabular-nums` en cifras y `theme=None` + `plotly_white` en todo gráfico Plotly.
3. En las pestañas 1–3 usar lenguaje ejecutivo sin sufijos técnicos (`_evaluation`, `d_1941`); concentrar toda la auditoría estadística en la Pestaña 4 (`Respaldo IA`).
4. Verificar siempre con `AppTest`, auditoría de fechas ISO en la Pestaña 2 y prueba headless antes de finalizar.

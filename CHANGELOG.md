# Registro de versiones

## 1.1.0 — 2026-11-27

### Agregado
- Vistas por usuario (`?vista=gerente`, `?vista=gestor`, `?vista=analista`) con pestañas, filtros iniciales y vocabulario propios.
- Gráficos: evidencia del riesgo, caídas frente a subidas, tienda por departamento, series por estrategia y riesgo, cascada de ingreso con rebaja, respuesta pasada frente al equilibrio, error por ventana y acierto de la señal de caída.
- Simulador: escenario «Según historial (acotado)» y lista descargable para revisar la reposición.
- Filtros: botón para restablecer, selección guardada en la URL, totales por opción y aviso del filtro que deja la selección vacía.
- Avisos «Casi sin ventas» y «Alerta sin monto en riesgo».

### Corregido
- El simulador compara el ingreso sin y con rebaja. Antes sumaba solo las unidades adicionales (+$9,169); la diferencia neta del escenario esperado al 25% es −$7,054.
- Se distingue «sin historial de rebajas» de «respuesta baja o negativa».
- La tarjeta de grupo se calcula sobre la selección en lugar de depender de un clúster fijo.
- Una selección vacía ya no oculta la auditoría; la serie elegida se conserva o se avisa si queda fuera.
- El ingreso en riesgo se muestra frente a 90 y a 28 días.

### Cambiado
- El indicador se llama «Ingreso en riesgo» en todas las vistas.
- La tabla del plan muestra 6 columnas, con opción de ver todas.
- Versiones fijadas en `requirements.txt` (requiere Python 3.11 o superior).
- `DESIGN.md`, `plan/03` y `plan/04` actualizados.

### Pendiente
- El informe, las diapositivas y los guiones de `outputs/` corresponden a la versión 1.0.0.
- La regla de riesgo no cambió: hay series casi sin ventas en riesgo bajo, ahora marcadas con un aviso.
- La reposición es una lista para revisión manual; no hay integración con otros sistemas.
- La barra de filtros aún es extensa y tiendas y departamentos se identifican por código.

## 1.0.0 — 2026-11-27

- Versión inicial: pipeline, dashboard, informe y presentación.

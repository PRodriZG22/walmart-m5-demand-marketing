import { useEffect, useMemo, useState } from 'react'
import { loadSeries } from './data'
import { Card, Chart, Kpi } from './ui'
import { C, NO_SALES, RESTOCK, SNAP_PCT, displayName, num, plus, tr, usd } from './logic'

const addDays = (iso, days) => new Date(Date.parse(iso) + days * 864e5).toISOString().slice(0, 10)

function ForecastChart({ series, baselines }) {
  const { hist, w4, forecast } = series
  const dates = hist.date.concat(forecast.date)
  const prices = hist.sell_price.concat(forecast.sell_price)
  const snap = hist.snap_CA.concat(forecast.snap_CA)
  const shapes = dates.flatMap((d, i) => snap[i] === 1
    ? [{ type: 'rect', xref: 'x', yref: 'paper', x0: d, x1: addDays(d, 1), y0: 0, y1: 1, fillcolor: 'rgba(254,243,199,0.58)', line: { width: 0 }, layer: 'below' }] : [])
  const close = addDays(forecast.date[0], -1)
  shapes.push({ type: 'line', xref: 'x', yref: 'paper', x0: close, x1: close, y0: 0, y1: 1, line: { color: C.gray, width: 1.5, dash: 'dot' } })
  const line = (name, x, y, color, extra = {}) => ({ type: 'scatter', mode: 'lines', name, x, y, line: { color, width: 2, ...extra } })
  const valid = prices.filter((p) => p !== null)
  const lo = Math.min(...valid), hi = Math.max(...valid), pad = Math.max((hi - lo) * 0.35, 0.15)
  const data = [
    { type: 'scatter', mode: 'markers', name: 'Días de pago SNAP', x: [null], y: [null], marker: { size: 10, color: '#FDE68A', symbol: 'square' } },
    line('Ventas reales (90 días)', hist.date, hist.units_sold, C.ink),
    line('Prueba reciente del pronóstico', w4.date, w4.pred_rf, C.blue, { dash: 'dash' }),
    ...(baselines ? [line('Referencia SES', w4.date, w4.pred_ses, C.bright, { dash: 'dot' }), line('Referencia MA28', w4.date, w4.pred_ma28, C.orange, { dash: 'dot' })] : []),
    { ...line('Pronóstico próximos 28 días', forecast.date, forecast.pred_units, C.red, { width: 2.6 }), mode: 'lines+markers', marker: { size: 4.5 } },
    { ...line('Precio en tienda (USD)', dates, prices, C.gray, { width: 1.4, dash: 'dot' }), yaxis: 'y2', hovertemplate: '$%{y:.2f}' },
  ]
  return (
    <Chart
      height={440} data={data}
      layout={{
        shapes, hovermode: 'x unified', margin: { t: 46, r: 58 },
        annotations: [{ x: close, y: 1.06, xref: 'x', yref: 'paper', xanchor: 'right', showarrow: false, bgcolor: C.bg, font: { size: 11, color: C.muted }, text: `Cierre histórico (${close.split('-').reverse().join('/')}) · Inicio pronóstico 28d` }],
        xaxis: { type: 'date', range: [addDays(close, -90), addDays(forecast.date.at(-1), 1)] },
        yaxis: { title: 'Unidades por día', rangemode: 'tozero' },
        yaxis2: { title: 'Precio (USD)', tickformat: '$.2f', range: [Math.max(0, lo - pad), hi + pad] },
      }}
    />
  )
}

function advice(r) {
  if (r.aviso === NO_SALES) return ['Revisar surtido y disponibilidad: casi no registra ventas', `No vendió en el ${num(r.intermittency_pct, 1)}% de los días. La regla documentada lo clasifica en riesgo bajo, pero no debe tratarse como estable ni usarse como ancla. Verificar stock antes de decidir.`]
  if (r.primary_strategy.includes('Markdown')) return [`Estrategia recomendada: Aplicar Markdown ${r.discount_range} + revisar pedido post-oferta (${RESTOCK}, supuesto)`, 'Este artículo responde positivamente a rebajas. Activar rotación FEFO en góndola y ajustar a la baja la orden de compra posterior para evitar sobrestock por acaparamiento.']
  if (r.primary_strategy.includes('Cross-Selling')) {
    const why = r.has_price_promo_history ? 'Su respuesta observada a rebajas fue baja o negativa.' : 'No hay historial suficiente para saber si responde a rebajas.'
    return [`Estrategia recomendada: Cross-Selling sin descuento — Empaquetar junto al producto ancla ${r.suggested_anchor_item}`, `${why} Probar combo o cabecera junto a ${r.suggested_anchor_item}, líder de rotación en ${r.store_id} (${r.dept_id}).`]
  }
  if (r.primary_strategy.includes('SNAP')) return ['Estrategia recomendada: Sincronización SNAP sin descuento — Reforzar stock y multipacks del día 1 al 10', 'Demanda saludable con pico fuerte en fechas de pago SNAP. Conservar precio habitual y asegurar disponibilidad.']
  return ['Estrategia recomendada: Mantener precio habitual (EDLP) y usar como producto ancla', 'Producto estable sin urgencia promocional. Ideal para traccionar combos junto a artículos en desaceleración.']
}

function priceResponse(r) {
  const v = r.price_sensitivity
  if (!r.has_price_promo_history || v === null) return ['Sin historial', 'Sin rebajas previas · No descontar', '']
  if (v >= 0.1) return [`+${num(v * 100, 1)}%`, 'Responde bien · Apto para rebaja', 'green']
  if (v < 0) return [`${num(v * 100, 1)}% (No rebajar)`, 'Vendió menos con rebaja (dato observado)', 'red']
  return [`+${num(v * 100, 1)}% (No rebajar)`, 'Respuesta débil · Usar combos', 'amber']
}

export default function Producto({ rows, view, selected, onSelect }) {
  const ordered = useMemo(() => [...rows].sort((a, b) => b.revenue_at_risk_usd - a.revenue_at_risk_usd), [rows])
  const kept = ordered.find((r) => r.id === selected)
  const row = kept || ordered[0]
  const [loaded, setLoaded] = useState({})
  const [baselines, setBaselines] = useState(false)
  useEffect(() => {
    let alive = true
    loadSeries(row.id).then((s) => alive && setLoaded({ id: row.id, s }), (e) => alive && setLoaded({ id: row.id, error: e.message }))
    return () => { alive = false }
  }, [row.id])

  const [headline, detail] = advice(row)
  const [prValue, prSub, prClass] = priceResponse(row)
  const level = { 'Riesgo Alto': 'high', 'Riesgo Medio': 'med', 'Riesgo Bajo': 'low' }[row.risk_level]
  const t = (s) => tr(s, view)

  return (
    <>
      {selected && !kept && <div className="notice">La serie que veías ({displayName(selected)}) quedó fuera de los filtros. Ahora se muestra la de mayor ingreso en riesgo.</div>}
      <div className="row">
        <label className="field grow">Elegir producto y tienda (de mayor a menor ingreso en riesgo):
          <select value={row.id} onChange={(e) => onSelect(e.target.value)}>
            {ordered.map((r) => <option key={r.id} value={r.id}>{`${r.display_name}  |  ${r.risk_level}  |  ${usd(r.revenue_at_risk_usd, 2)} en riesgo`}</option>)}
          </select>
        </label>
        {view === 'analista' && <label className="check"><input type="checkbox" checked={baselines} onChange={(e) => setBaselines(e.target.checked)} /> Ver referencias</label>}
      </div>

      <div className={`semaphore ${level}`}>
        <div>
          <span className={`pill ${level}`}>{row.risk_level}</span>
          {row.aviso && <span className="pill med">{row.aviso}</span>}
          {row.caida_previa && <span className="pill info">La caída ya ocurrió en los últimos 28 días</span>}
          {row.snap_priority && <span className="pill snap">Prioridad SNAP (+{SNAP_PCT}% o más)</span>}
          {row.stockpiling_alert && <span className="pill info">Revisar pedido post-oferta: {RESTOCK}</span>}
          <span className="pill info">{row.cluster_name}</span>
        </div>
        <div className="headline">{t(headline)}</div>
        <p className="takeaway">{t(detail)} <strong>Calendario:</strong> {t(row.snap_tactical_plan)}.</p>
      </div>

      <Card title={`Evolución de ventas y pronóstico a 28 días — ${row.display_name}`} note="Línea negra: ventas reales recientes · Línea roja: demanda proyectada próximos 28 días · Franjas amarillas: días de pago SNAP.">
        {loaded.id !== row.id ? <div className="loading">Cargando serie…</div> : loaded.error ? <div className="notice">No se pudo cargar la serie: {loaded.error}</div> : <ForecastChart series={loaded.s} baselines={baselines && view === 'analista'} />}
      </Card>

      <div className="grid g6">
        <Kpi label="Venta reciente (90d)" value={`${num(row.sales_velocity_90d, 2)} u/día`} sub={`Últimos 28d: ${num(row.sales_velocity_28d, 2)} u/día`} />
        <Kpi label="Pronóstico (28 días)" accent="blue" value={`${num(row.pred_velocity_28d, 2)} u/día`} sub={row.projected_decline_pct > 0 ? `-${num(row.projected_decline_pct, 1)}% vs ritmo reciente` : 'Sin caída proyectada'} />
        <Kpi label="Ingreso en riesgo (vs. 90d)" accent="red" value={usd(row.revenue_at_risk_usd, 2)} sub={`Vs. 28d: ${usd(row.riesgo_vs_28d_usd, 2)} · Precio ${usd(row.current_price, 2)}`} />
        <Kpi label="Días sin ventas (3 años)" value={`${num(row.intermittency_pct, 1)}%`} sub="Frecuencia de días en cero" />
        <Kpi label="Respuesta a rebajas" accent={prClass} value={prValue} sub={prSub} />
        <Kpi label="Impulso en días SNAP" accent={row.snap_priority ? 'amber' : ''} value={`${plus(row.snap_sensitivity * 100)}%`} sub={row.snap_priority ? 'Prioridad SNAP activa' : 'Impacto moderado o bajo'} />
      </div>
    </>
  )
}

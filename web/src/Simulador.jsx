import { useState } from 'react'
import { Card, Chart, Kpi, Table, Waterfall } from './ui'
import { C, ELASTICITIES, HIST_SCENARIO, MARKDOWN, RESTOCK, STRATEGY_SHORT, downloadCsv, num, plus, scenario, signed, usd } from './logic'

const EXPORT = ['id', 'store_id', 'dept_id', 'risk_level', 'cluster_name', 'current_price', 'sales_velocity_90d', 'pred_velocity_28d', 'projected_decline_pct', 'intermittency_pct', 'revenue_at_risk_usd', 'price_sensitivity', 'snap_sensitivity', 'snap_priority', 'primary_strategy', 'discount_range', 'suggested_anchor_item', 'snap_tactical_plan', 'tactical_action', 'aviso', 'riesgo_vs_28d_usd']
const money = (v) => usd(v, 2)
const dec = (v) => num(v, 2)
const SHORT_COLUMNS = [['display_name', 'Producto y Tienda'], ['risk_level', 'Prioridad'], ['revenue_at_risk_usd', 'Ingreso en riesgo (USD)', money], ['strategy_short', 'Estrategia Recomendada'], ['suggested_anchor_item', 'Producto Ancla'], ['aviso', 'Aviso']]
const ALL_COLUMNS = [
  ...SHORT_COLUMNS.slice(0, 3), ['projected_decline_pct', 'Caída (%)', (v) => `${num(v, 1)}%`], ...SHORT_COLUMNS.slice(3, 5),
  ['current_price', 'Precio', money], ['store_id', 'Tienda'], ['dept_id', 'Departamento'], ['cluster_name', 'Grupo Comercial'],
  ['sales_velocity_90d', 'Venta 90d', dec], ['pred_velocity_28d', 'Pronóstico 28d', dec], ['price_sensitivity', 'Sensibilidad Precio', (v) => plus(v, 2)],
  ['snap_sensitivity', 'Sensibilidad SNAP', (v) => plus(v, 2)], ['snap_priority', 'Prioridad SNAP'], ['aviso', 'Aviso'],
]

export default function Simulador({ rows, view, filters }) {
  const [pct, setPct] = useState(25)
  const [label, setLabel] = useState('Esperado')
  const [all, setAll] = useState(false)
  const options = { ...ELASTICITIES, [HIST_SCENARIO]: null }
  const markdown = rows.filter((r) => r.primary_strategy === MARKDOWN)
  const plan = [...rows].sort((a, b) => b.revenue_at_risk_usd - a.revenue_at_risk_usd)
  const restock = plan.filter((r) => r.stockpiling_alert).map((r) => ({ ...r, ajuste_sugerido_post_oferta: RESTOCK }))
  const d = pct / 100
  const esc = scenario(markdown, d, options[label])
  const required = esc.breakEven * 100
  const range = Array.from({ length: 16 }, (_, i) => 20 + i)
  const colors = { Conservador: C.gray, Esperado: C.blue, Optimista: C.bright, [HIST_SCENARIO]: C.orange }
  const points = markdown.filter((r) => r.revenue_at_risk_usd > 0)

  const reason = !filters.estrategia.includes(MARKDOWN)
    ? (view === 'analista' ? `Marca «${STRATEGY_SHORT[MARKDOWN]}» en «Acción recomendada».` : 'Elige «Probar rebajas» en «¿Qué quieres hacer?».')
    : !filters.riesgo.some((r) => r !== 'Riesgo Bajo')
      ? `Las rebajas solo aplican a riesgo alto o medio: ${view === 'analista' ? 'marca uno en «Nivel de riesgo»' : 'pulsa «Volver al inicio»'}.`
      : 'Ningún producto de la selección respondió a rebajas en el pasado.'

  return (
    <>
      <h2>Simulador de Descuentos</h2>
      <p className="takeaway">Escenarios supuestos, no medidos en estos datos. Calcula ingreso, no ganancia: no hay costos ni merma. Solo incluye productos por tienda en riesgo que respondieron a rebajas en el pasado.</p>
      {!markdown.length ? <div className="notice">No hay productos para simular. {reason}</div> : (
        <>
          <Card>
            <div className="row">
              <label className="field grow">Nivel de descuento a simular: <strong>{pct}%</strong>
                <input type="range" min="20" max="35" value={pct} onChange={(e) => setPct(Number(e.target.value))} />
              </label>
              <fieldset className="field grow"><legend>Respuesta supuesta del consumidor:</legend>
                <div className="radios">
                  {Object.entries(options).map(([k, e]) => (
                    <label key={k}><input type="radio" checked={label === k} onChange={() => setLabel(k)} /> {view === 'analista' && e ? `${k} (ε=${e})` : k}</label>
                  ))}
                </div>
              </fieldset>
            </div>
            {options[label] === null && <p className="takeaway">Usa la venta observada con rebajas de cada producto, limitada al escenario optimista. Mezcla cualquier rebaja mayor de 5% y no prueba causa.</p>}
          </Card>
          <div className="grid g5">
            <Kpi label="Ingreso sin rebaja (28 días)" value={usd(esc.base)} sub={`${num(markdown.length)} productos por tienda`} />
            <Kpi label="Ingreso con rebaja" accent="blue" value={usd(esc.withDiscount)} sub={`Descuento ${pct}%`} />
            <Kpi label="Diferencia neta" accent={esc.net < 0 ? 'red' : 'green'} value={signed(esc.net)} sub={`${plus(esc.base ? esc.net / esc.base * 100 : 0)}% sobre el ingreso base`} />
            <Kpi label="Más unidades supuestas" value={`+${num(esc.lift * 100, 1)}%`} sub={`+${num(esc.extraUnits)} sobre ${num(esc.units)}`} />
            <Kpi label="Necesario para no perder ingreso" accent="amber" value={`+${num(required, 1)}%`} sub="unidades adicionales" />
          </div>
          <div className="grid g2">
            <Card title="¿Qué pasa con el ingreso al rebajar?" note={`Lo que se vende de más (${signed(esc.extra)}) ${esc.net < 0 ? 'no compensa' : 'compensa'} la rebaja sobre lo que ya se vendía (${signed(esc.discount)}).`}>
              <Waterfall steps={[['Sin rebaja', esc.base, false, usd(esc.base)], ['Rebaja', esc.discount, false, signed(esc.discount)], ['Unidades extra', esc.extra, false, signed(esc.extra)], ['Con rebaja', esc.withDiscount, true, usd(esc.withDiscount)]]} />
            </Card>
            <Card title="¿Cuánto cambia el ingreso según el descuento?" note="Diferencia frente a no rebajar. Bajo la línea cero se ingresa menos.">
              <Chart
                data={Object.entries(options).map(([k, e]) => ({ type: 'scatter', mode: 'lines+markers', name: k, x: range, y: range.map((v) => scenario(markdown, v / 100, e).net), line: { color: colors[k] }, hovertemplate: '%{x}%: $%{y:,.0f}' }))}
                layout={{
                  xaxis: { title: 'Descuento (%)' }, yaxis: { tickprefix: '$', rangemode: 'tozero', title: 'Diferencia neta (USD)' }, margin: { l: 70 }, legend: { orientation: 'h', y: -0.3 },
                  shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 0, y1: 0, line: { color: C.ink, width: 1.2 } }, { type: 'line', yref: 'paper', y0: 0, y1: 1, x0: pct, x1: pct, line: { color: C.red, width: 1.4, dash: 'dash' } }],
                }}
              />
            </Card>
          </div>
          <Card title="¿Qué respuesta pasada tuvo cada producto frente al equilibrio?" note={<>La línea marca el +{num(required, 1)}% necesario con {pct}% de descuento. <strong>Estar encima no garantiza ganancia:</strong> la respuesta pasada mezcla cualquier rebaja mayor de 5% en 3 años y puede deberse a otras causas. Solo se muestran productos por tienda con ingreso en riesgo.</>}>
            {!points.length ? <div className="notice">No hay productos aptos con ingreso en riesgo.</div> : (
              <Chart
                height={400}
                data={[{ type: 'scatter', mode: 'markers', x: points.map((r) => r.revenue_at_risk_usd), y: points.map((r) => r.price_sensitivity * 100), text: points.map((r) => `${r.display_name}<br>Días con rebaja: ${r.promo_days_count}`), marker: { color: C.blue, size: 8, opacity: 0.7 }, hovertemplate: '%{text}<br>$%{x:.2f} · %{y:.1f}%<extra></extra>' }]}
                layout={{
                  xaxis: { type: 'log', title: 'Ingreso en riesgo (USD, escala logarítmica)' }, yaxis: { type: 'log', title: 'Venta con rebaja vs. normal (%, log)' }, margin: { l: 70, b: 60 },
                  shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: required, y1: required, line: { color: C.red, width: 1.6, dash: 'dash' } }],
                }}
              />
            )}
          </Card>
        </>
      )}

      <h2>Plan de Acción Comercial (Lista Priorizada)</h2>
      <div className="row">
        <label className="check"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> Ver todas las columnas</label>
        <span className="takeaway grow">{num(plan.length)} productos por tienda, ordenados de mayor a menor ingreso en riesgo.</span>
        <button className="primary" onClick={() => downloadCsv('plan_promociones_walmart_ca.csv', plan, EXPORT)}>Descargar plan (.CSV para Excel)</button>
      </div>
      {restock.length > 0 && (
        <p className="takeaway">
          <button className="secondary" onClick={() => downloadCsv('revision_reposicion_post_oferta.csv', restock, ['id', 'store_id', 'dept_id', 'risk_level', 'discount_range', 'pred_total_28d_units', 'ajuste_sugerido_post_oferta'])}>Descargar lista de revisión de reposición ({num(restock.length)})</button>
          <br />Solo para revisión manual tras una rebaja: el ajuste {RESTOCK} es un supuesto de la literatura y el tablero no envía alertas a ningún sistema.
        </p>
      )}
      <Table rows={plan} columns={all ? ALL_COLUMNS : SHORT_COLUMNS} />
    </>
  )
}

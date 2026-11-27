import { Card, Chart, Kpi, Waterfall } from './ui'
import {
  C, CROSS, DEPTS, ELASTICITIES, INTERMITTENCY, MARKDOWN, NO_AMOUNT, NO_SALES, RISKS, RISK_COLORS, SNAP_PCT, STORES,
  groupSum, num, scenario, signed, sum, topEntry, tr, usd,
} from './logic'

const Decision = ({ color, kicker, title, metric, children }) => (
  <div className="decision" style={{ borderTopColor: color }}>
    <div className="kicker" style={{ color }}>{kicker}</div>
    <div className="decision-title">{title}</div>
    <div className="decision-metric">{metric}</div>
    <div className="takeaway">{children}</div>
  </div>
)

export default function Resumen({ rows, scope, view }) {
  const n = rows.length
  const risk = sum(rows, 'revenue_at_risk_usd')
  const where = (f) => rows.filter(f)
  const high = where((r) => r.risk_level === 'Riesgo Alto')
  const medium = where((r) => r.risk_level === 'Riesgo Medio')
  const snap = where((r) => r.snap_priority)
  const snapRisk = sum(snap, 'revenue_at_risk_usd')
  const [group, groupRisk] = topEntry(groupSum(rows, 'cluster_name', 'revenue_at_risk_usd'))
  const groupCount = rows.filter((r) => r.cluster_name === group).length
  const already = sum(where((r) => r.caida_previa), 'revenue_at_risk_usd')
  const markdown = where((r) => r.primary_strategy === MARKDOWN)
  const cross = where((r) => r.primary_strategy === CROSS)
  const noHistory = cross.filter((r) => !r.has_price_promo_history)
  const esc = scenario(markdown, 0.25, ELASTICITIES.Esperado)
  const empty = 'No hay productos de este grupo con los filtros actuales.'
  const t = (s) => tr(s, view)

  const byStore = groupSum(rows, 'store_id', 'revenue_at_risk_usd')
  const [topStore, topStoreValue] = topEntry(byStore)

  const evidence = [
    ['Respondió a rebajas', markdown, C.blue],
    ['Respuesta baja<br>o negativa', cross.filter((r) => r.has_price_promo_history), C.orange],
    ['Sin historial<br>de rebajas', noHistory, C.gray],
    ['Riesgo bajo', where((r) => r.risk_level === 'Riesgo Bajo'), C.bright],
  ].map(([label, list, color]) => ({ label, color, count: list.length, amount: sum(list, 'revenue_at_risk_usd') }))

  const heat = DEPTS.map((d) => STORES.map((s) => sum(where((r) => r.dept_id === d && r.store_id === s), 'revenue_at_risk_usd')))
  const depts = DEPTS.filter((d) => rows.some((r) => r.dept_id === d))
  const stores = STORES.filter((s) => s in byStore)
  const z = depts.map((d) => stores.map((s) => heat[DEPTS.indexOf(d)][STORES.indexOf(s)]))
  let best = { v: -1 }
  depts.forEach((d, i) => stores.forEach((s, j) => { if (z[i][j] > best.v) best = { d, s, v: z[i][j] } }))

  const strategies = Object.keys(groupSum(rows, 'strategy_short'))
  const [topStrategy, topStrategyCount] = topEntry(groupSum(rows, 'strategy_short'))

  const falls = sum(scope, 'revenue_at_risk_usd')
  const rises = sum(scope, (r) => Math.max((r.pred_velocity_28d - r.sales_velocity_90d) * 28 * r.current_price, 0))

  return (
    <>
      <div className="grid g4">
        <Kpi label="Ingreso en riesgo (frente a 90 días)" accent="red" value={usd(risk)} sub={`${num(sum(rows, 'units_at_risk_28d'))} unidades menos en los próximos 28 días`} />
        <Kpi label="Productos por tienda en alerta crítica" value={num(high.length)} sub={`${num(high.length / n * 100, 1)}% del catálogo visible · ${usd(sum(high, 'revenue_at_risk_usd'))} en riesgo`} />
        <Kpi label="Grupo con más riesgo" accent="blue" value={risk > 0 ? `${num(groupRisk / risk * 100, 1)}%` : '—'} sub={risk > 0 ? `del riesgo visible en ${num(groupCount)} productos por tienda del grupo «${group}»` : 'No hay ingreso en riesgo en la selección'} />
        <Kpi label="Impacto de días SNAP" accent="amber" value={`${num(risk > 0 ? snapRisk / risk * 100 : 0, 1)}%`} sub={`${usd(snapRisk)} en riesgo en ${num(snap.length)} productos por tienda`} />
        <Kpi label="Productos por tienda en riesgo medio" value={num(medium.length)} sub={`${num(medium.length / n * 100, 1)}% de lo visible · ${usd(sum(medium, 'revenue_at_risk_usd'))} en riesgo`} />
        <Kpi label={`Sensibles a SNAP (${SNAP_PCT}% o más)`} value={`${num(snap.length / n * 100, 1)}%`} sub={`${num(snap.length)} productos por tienda`} />
        <Kpi label="Casi sin ventas, en riesgo bajo" accent="amber" value={num(where((r) => r.aviso === NO_SALES).length)} sub={`Sin venta ${INTERMITTENCY}% de los días o más: revisar surtido`} />
        <Kpi label="Alertas sin monto" value={num(where((r) => r.aviso === NO_AMOUNT).length)} sub="Riesgo alto o medio por rotación, con $0 en riesgo" />
      </div>
      <div className="footnote">
        <strong>Cómo leer el ingreso en riesgo:</strong> compara el pronóstico con los últimos 90 días. De {usd(risk)}, <strong>{usd(already)}</strong> corresponde
        a caídas ya ocurridas (el pronóstico no baja frente a los últimos 28 días). Medida contra esos 28 días, la caída sería de <strong>{usd(sum(rows, 'riesgo_vs_28d_usd'))}</strong>.
      </div>

      <h2>3 Decisiones para Marketing</h2>
      <div className="grid g3">
        <Decision color={C.blue} kicker="Decisión 1 · Rebajas a prueba" title={t('Probar la rebaja antes de extenderla: vende más, pero ingresa menos')} metric={`${num(markdown.length)} productos por tienda · ${usd(sum(markdown, 'revenue_at_risk_usd'))} en riesgo`}>
          {markdown.length ? <>Con 25% de descuento y una respuesta supuesta, el ingreso de 28 días pasaría de <strong>{usd(esc.base)}</strong> a <strong>{usd(esc.withDiscount)}</strong> ({signed(esc.net)}). No incluye costos ni merma evitada.</> : empty}
        </Decision>
        <Decision color={C.amber} kicker="Decisión 2 · Combos sin rebajar precio" title="Probar combos con un producto de alta rotación" metric={`${num(cross.length)} productos por tienda · ${usd(sum(cross, 'revenue_at_risk_usd'))} en riesgo`}>
          {cross.length ? <><strong>{num(noHistory.length)}</strong> no tienen historial suficiente de rebajas y <strong>{num(cross.length - noHistory.length)}</strong> mostraron respuesta baja o negativa. El efecto del combo no está probado con estos datos.</> : empty}
        </Decision>
        <Decision color={C.green} kicker="Decisión 3 · Calendario SNAP" title="Sincronizar stock y cupones con el ciclo mensual" metric={`${num(snap.length)} productos por tienda · ${usd(snapRisk)} en riesgo`}>
          {snap.length ? <><strong>Días 1–10 (pagos SNAP):</strong> reforzar exhibición, multipacks y stock.<br /><strong>Días 20–31 (fuera de SNAP):</strong> plan de cupones de fin de mes.</> : empty}
        </Decision>
      </div>

      <div className="grid g2">
        <Card title="¿En qué tienda actuar primero?" note={<><strong>{topStore}</strong> concentra el {num(risk > 0 ? topStoreValue / risk * 100 : 0, 1)}% del ingreso en riesgo ({usd(topStoreValue)}), liderando la prioridad de campaña.</>}>
          <Chart
            data={RISKS.map((level) => ({
              type: 'bar', name: level, x: stores, marker: { color: RISK_COLORS[level] },
              y: stores.map((s) => sum(where((r) => r.store_id === s && r.risk_level === level), 'revenue_at_risk_usd')),
              hovertemplate: `Tienda %{x} · ${level}<br>$%{y:,.0f}<extra></extra>`,
            }))}
            layout={{
              barmode: 'stack', yaxis: { tickprefix: '$', title: 'Ingreso en riesgo (USD)', range: [0, Math.max(topStoreValue, 1) * 1.18] },
              annotations: stores.map((s) => ({ x: s, y: byStore[s], text: `<b>${usd(byStore[s])}</b>`, showarrow: false, yshift: 10 })),
            }}
          />
        </Card>
        <Card title="¿Qué sabemos sobre el ingreso en riesgo?" note={<>El <strong>{num(risk > 0 ? evidence[2].amount / sum(evidence, 'amount') * 100 : 0, 1)}%</strong> está en productos por tienda sin historial suficiente de rebajas: no se sabe si responderían.</>}>
          <Chart
            data={[{
              type: 'bar', orientation: 'h', x: evidence.map((e) => e.amount), y: evidence.map((e) => e.label), marker: { color: evidence.map((e) => e.color) },
              text: evidence.map((e) => `${usd(e.amount)} · ${num(e.count)}`), textposition: 'outside', cliponaxis: false, hovertemplate: '%{y}<br>$%{x:,.0f} en riesgo<extra></extra>',
            }]}
            layout={{ showlegend: false, xaxis: { tickprefix: '$', nticks: 4, title: 'USD en riesgo', range: [0, Math.max(...evidence.map((e) => e.amount), 7) * 1.55] }, yaxis: { autorange: 'reversed', showgrid: false } }}
          />
        </Card>
        <Card title="¿Qué departamento de qué tienda pesa más?" note={<><strong>{best.d}</strong> en <strong>{best.s}</strong> suma {usd(best.v)} en riesgo.</>}>
          <Chart height={340} data={[{ type: 'heatmap', x: stores, y: depts, z, colorscale: [[0, '#EFF6FF'], [1, C.blue]], texttemplate: '%{z:,.0f}', hovertemplate: '%{y} · %{x}: $%{z:,.0f}<extra></extra>' }]} layout={{ yaxis: { autorange: 'reversed', showgrid: false } }} />
        </Card>
        <Card title="¿Cuántos productos por tienda hay en cada acción?" note={<>La acción con más casos es <strong>{topStrategy}</strong> ({num(topStrategyCount)}).</>}>
          <Chart
            height={340}
            data={RISKS.map((level) => ({
              type: 'bar', orientation: 'h', name: level, y: strategies, marker: { color: RISK_COLORS[level] },
              x: strategies.map((s) => where((r) => r.strategy_short === s && r.risk_level === level).length),
            }))}
            layout={{ barmode: 'stack', xaxis: { title: 'Productos por tienda' }, yaxis: { showgrid: false } }}
          />
        </Card>
      </div>
      <Card title="¿Cae toda la venta o solo parte del catálogo?" note={<>Frente al ritmo de los últimos 90 días: caídas por <strong>{usd(falls)}</strong>, subidas por <strong>{usd(rises)}</strong> y saldo de <strong>{signed(rises - falls)}</strong>. El ingreso en riesgo suma solo las caídas. Aquí solo aplican tienda, departamento y búsqueda.</>}>
        <Waterfall height={340} yTitle="USD en 28 días" steps={[['Caídas', -falls, false, signed(-falls)], ['Subidas', rises, false, signed(rises)], ['Saldo', rises - falls, true, signed(rises - falls)]]} />
      </Card>
      <div className="footnote">
        <strong>Transparencia de datos (Walmart M5):</strong> Todas las cifras se calculan exclusivamente sobre ventas diarias reales, precios de góndola y calendario SNAP de las 4 tiendas
        de California. Al no existir datos públicos de stock físico ni costos de compra, la exposición comercial se expresa como <strong>Ingreso en Riesgo (USD)</strong> proyectado a 28 días.
      </div>
    </>
  )
}

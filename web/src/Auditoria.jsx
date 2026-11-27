import { useState } from 'react'
import { Card, Chart, Table } from './ui'
import { C, num, plus, usd } from './logic'

const MODEL_COLORS = { 'Random Forest': C.blue, 'SES (NumPy)': C.bright, SES: C.bright, MA28: C.orange, 'Seasonal Naïve (lag_28)': C.gray }
const CLUSTER_COLORS = [C.red, C.blue, C.gray, C.orange, C.bright, C.ink]
const METRICS = ['mae', 'rmse', 'rmsse']
const f4 = (v) => num(v, 4)
const pc = (v) => `${num(v, 1)}%`

const family = (f) => /^(lag_|rolling_)/.test(f) ? 'Rezagos / Medias (>= t-28)'
  : f.includes('price') ? 'Precios'
    : ['snap_CA', 'wday', 'month', 'year', 'event_type_1_code'].includes(f) ? 'Calendario / SNAP' : 'Identificadores'
const FAMILY_COLORS = { 'Rezagos / Medias (>= t-28)': C.blue, Precios: C.orange, 'Calendario / SNAP': C.bright, Identificadores: C.gray }

export default function Auditoria({ rows, total, reports }) {
  const { val_summary: summary, val_by_window: byWindow, val_breakdown: breakdown, feature_importance: fi, kmeans_eval: km, kmeans_profiles: profiles, audits, senal_caida: signal } = reports
  const [win, setWin] = useState(0)
  const [metric, setMetric] = useState('RMSE')
  const [threshold, setThreshold] = useState('20')
  const windows = [...new Map(byWindow.map((r) => [r.window, r])).values()].sort((a, b) => a.window - b.window)
  const winLabel = win ? `Ventana ${win}` : 'Promedio 4 Ventanas'

  let table = summary
  if (win) {
    const list = byWindow.filter((r) => r.window === win)
    const rf = list.find((r) => r.model === 'Random Forest')
    table = list.map((r) => ({ ...r, ...Object.fromEntries(METRICS.map((m) => [`rf_improvement_vs_model_${m}_pct`, (r[m] - rf[m]) / r[m] * 100])) }))
  }
  table = [...table].sort((a, b) => (b.model === 'Random Forest') - (a.model === 'Random Forest') || a.rmsse - b.rmsse)

  const col = metric.toLowerCase()
  const models = [...new Set(byWindow.map((r) => r.model))]
  const wins = windows.filter((w) => {
    const list = byWindow.filter((r) => r.window === w.window)
    return list.find((r) => r.model === 'Random Forest')[col] <= Math.min(...list.map((r) => r[col]))
  }).length

  const res = signal[threshold]
  const bases = [...new Set(res.map((r) => r['Periodo base']))]
  const globalRmsse = summary.find((r) => r.model === 'Random Forest').rmsse
  const sortedFi = [...fi].sort((a, b) => a.importance_pct - b.importance_pct)
  const k = audits.diagnosis?.kmeans?.selected_k ?? 4
  const maxRisk = Math.max(...rows.map((r) => r.revenue_at_risk_usd), 1)
  const GROUPS = { store_id: ['Tienda', C.blue], dept_id: ['Departamento', C.ink], snap_CA: ['Condición SNAP', C.orange] }

  return (
    <>
      <h2>A. Validación Temporal por Origen Rodante (4 Ventanas × 28 Días)</h2>
      <p className="takeaway">Evaluación cronológica sobre las {num(total)} series. Auditoría anti-fuga por muestreo en el paso de preparación.</p>
      <div className="notice">Las métricas, la importancia de variables y la tabla de grupos son globales: los filtros no cambian esas cifras. Solo el mapa de grupos responde a los filtros.</div>
      <label className="field">Corte de validación:
        <select value={win} onChange={(e) => setWin(Number(e.target.value))}>
          <option value={0}>Promedio 4 Ventanas</option>
          {windows.map((w) => <option key={w.window} value={w.window}>{`Ventana ${w.window} (${w.start_date} a ${w.end_date})`}</option>)}
        </select>
      </label>
      <Table rows={table} columns={[['model', 'Modelo'], ['mae', 'MAE', f4], ['rmse', 'RMSE', f4], ['rmsse', 'RMSSE (M5)', f4], ...METRICS.map((m) => [`rf_improvement_vs_model_${m}_pct`, `Mejora RF ${m.toUpperCase()} (%)`, (v) => `${plus(v, 2)}%`])]} />

      <Card title="¿Gana Random Forest en todas las ventanas?">
        <div className="radios">Métrica de error: {['RMSE', 'MAE', 'RMSSE'].map((m) => <label key={m}><input type="radio" checked={metric === m} onChange={() => setMetric(m)} /> {m}</label>)}</div>
        <p className="takeaway">Random Forest tiene el menor {metric} en <strong>{wins} de {windows.length}</strong> ventanas. Menor es mejor. El eje no empieza en cero para ver las diferencias.</p>
        <Chart
          data={models.map((m) => { const l = byWindow.filter((r) => r.model === m); return { type: 'scatter', mode: 'lines+markers', name: m, x: l.map((r) => r.window), y: l.map((r) => r[col]), line: { color: MODEL_COLORS[m] } } })}
          layout={{ xaxis: { title: 'Ventana de 28 días', dtick: 1 }, yaxis: { title: metric }, legend: { orientation: 'h', y: -0.25 } }}
        />
      </Card>

      <Card title="Cuando el modelo avisa una caída, ¿ocurre?">
        <label className="field">Caída mínima que se considera aviso:
          <select value={threshold} onChange={(e) => setThreshold(e.target.value)}>{['10', '20', '30'].map((u) => <option key={u} value={u}>{u}%</option>)}</select>
        </label>
        <p className="takeaway">Compare cada barra con el rombo: es la proporción de series que cayó, se avisara o no. <strong>El resultado cambia mucho según el periodo base</strong>; es una sola ventana y no usa la regla de riesgo del tablero (90 días e intermitencia). Con la base de 28 días, MA28 no emite avisos porque su pronóstico es esa misma base.</p>
        <Chart
          data={[
            ...['Random Forest', 'SES', 'MA28'].map((m) => ({ type: 'bar', name: m, x: bases, y: res.filter((r) => r['Método'] === m).map((r) => r['Acierto (%)']), marker: { color: MODEL_COLORS[m] } })),
            { type: 'scatter', mode: 'markers', name: 'Proporción que cayó (referencia)', x: bases, y: bases.map((b) => res.find((r) => r['Periodo base'] === b)['Series que cayeron, referencia (%)']), marker: { symbol: 'diamond', size: 13, color: C.ink } },
          ]}
          layout={{ barmode: 'group', yaxis: { range: [0, 100], title: 'Avisos que sí cayeron (%)' } }}
        />
        <Table rows={res} columns={Object.keys(res[0]).map((c) => [c, c, c.includes('(%)') ? (v) => num(v, 1) : undefined])} />
      </Card>

      <div className="grid g2">
        <Card title={`Comparativa de Error por Modelo (${winLabel})`}>
          <Chart height={405} data={table.map((r) => ({ type: 'bar', name: r.model, x: ['MAE', 'RMSE', 'RMSSE'], y: METRICS.map((m) => r[m]), texttemplate: '%{y:.2f}', textposition: 'outside', cliponaxis: false, marker: { color: MODEL_COLORS[r.model] } }))} layout={{ barmode: 'group' }} />
        </Card>
        <Card title="Desglose de RMSSE de Random Forest (Tienda, Depto y SNAP)">
          <Chart
            height={405}
            data={Object.entries(GROUPS).map(([dim, [name, color]]) => { const l = breakdown.filter((r) => r.dimension === dim); return { type: 'bar', name, x: l.map((r) => String(r.segment)), y: l.map((r) => r.rmsse), texttemplate: '%{y:.3f}', textposition: 'outside', marker: { color } } })}
            layout={{
              xaxis: { type: 'category' }, yaxis: { range: [0, 1.08], title: 'RMSSE promedio (4 ventanas)' },
              shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: globalRmsse, y1: globalRmsse, line: { color: C.red, width: 1.6, dash: 'dash' } }],
              annotations: [{ xref: 'paper', x: 0.99, y: globalRmsse, yanchor: 'bottom', xanchor: 'right', showarrow: false, text: `Promedio global: ${num(globalRmsse, 3)}`, font: { size: 11, color: C.red }, bgcolor: '#FFF2F2' }],
            }}
          />
        </Card>
      </div>

      <Card title="Importancia de las 16 Variables Predictoras — Random Forest Final">
        <Chart
          height={500}
          data={Object.entries(FAMILY_COLORS).map(([fam, color]) => { const l = sortedFi.filter((r) => family(r.feature) === fam); return { type: 'bar', orientation: 'h', name: fam, y: l.map((r) => r.feature), x: l.map((r) => r.importance_pct), texttemplate: '%{x:.2f}%', textposition: 'outside', cliponaxis: false, marker: { color } } })}
          layout={{ yaxis: { showgrid: false, categoryorder: 'array', categoryarray: sortedFi.map((r) => r.feature) }, xaxis: { showgrid: true, title: 'Importancia relativa (%)', range: [0, sortedFi.at(-1).importance_pct * 1.16] } }}
        />
      </Card>

      <h2>B. Segmentación No Supervisada K-Means (K = {k})</h2>
      <p className="takeaway">K se eligió por utilidad comercial. La silueta más alta no corresponde necesariamente al K elegido: compare la curva.</p>
      <div className="grid g2">
        <Card title="Método del Codo (WCSS) y Coeficiente de Silueta">
          <Chart
            height={440}
            data={[
              { type: 'scatter', mode: 'lines+markers', name: 'WCSS (Inercia)', x: km.map((r) => r.k), y: km.map((r) => r.wcss), line: { color: C.blue, width: 2.4 } },
              { type: 'scatter', mode: 'lines+markers', name: 'Coeficiente de Silueta', x: km.map((r) => r.k), y: km.map((r) => r.silhouette_score), yaxis: 'y2', line: { color: C.ink, width: 2.4, dash: 'dash' }, marker: { symbol: 'square' } },
            ]}
            layout={{
              hovermode: 'x unified', xaxis: { title: 'Número de clústeres (K)', dtick: 1 }, yaxis: { title: 'WCSS' }, yaxis2: { title: 'Silueta' }, margin: { r: 55 },
              shapes: [{ type: 'line', yref: 'paper', x0: k, x1: k, y0: 0, y1: 1, line: { color: C.red, width: 1.5, dash: 'dot' } }],
              annotations: [{ x: k, y: 1.06, yref: 'paper', showarrow: false, text: `K elegido = ${k}`, font: { size: 11, color: C.red } }],
            }}
          />
        </Card>
        <Card title="Mapa de Clústeres: Intermitencia vs Declive Proyectado" note={rows.length ? null : 'Sin productos con los filtros actuales: el mapa aparece vacío.'}>
          <Chart
            height={440}
            data={profiles.map((p, i) => {
              const l = rows.filter((r) => r.cluster_name === p.cluster_name)
              return {
                type: 'scatter', mode: 'markers', name: p.cluster_name, x: l.map((r) => r.intermittency_pct), y: l.map((r) => r.projected_decline_pct),
                text: l.map((r) => `${r.display_name}<br>${r.risk_level} · ${usd(r.revenue_at_risk_usd, 2)}<br>${r.strategy_short}`),
                hovertemplate: '%{text}<br>Intermitencia %{x:.1f}% · Declive %{y:.1f}%<extra></extra>',
                marker: { color: CLUSTER_COLORS[i % 6], opacity: 0.72, sizemode: 'area', sizeref: 2 * maxRisk / 34 ** 2, sizemin: 3, size: l.map((r) => Math.max(r.revenue_at_risk_usd, 1)) },
              }
            })}
            layout={{ xaxis: { title: 'Intermitencia (% días en cero)' }, yaxis: { title: 'Declive proyectado (%)' }, legend: { orientation: 'h', y: -0.2 } }}
          />
        </Card>
      </div>
      <h3 className="question">Perfiles Empíricos de los 4 Clústeres (centroides reales en escala original)</h3>
      <Table rows={profiles} columns={[
        ['cluster_id', 'ID'], ['cluster_name', 'Nombre del Clúster'], ['sku_count', 'SKUs'], ['portfolio_pct', '% Portafolio', (v) => `${num(v, 2)}%`],
        ['sales_velocity_28d_mean', 'Vel. 28d (u/d)', (v) => num(v, 2)], ['intermittency_pct_mean', 'Intermit. (%)', pc], ['projected_decline_pct_mean', 'Declive (%)', pc],
        ['revenue_at_risk_usd_mean', 'Riesgo/SKU', (v) => usd(v, 2)], ['revenue_at_risk_usd_total', 'Riesgo Total', (v) => usd(v, 2)], ['revenue_at_risk_share_pct', '% Riesgo Total', pc],
        ['price_sensitivity_mean', 'Sensib. Precio', (v) => plus(v, 2)], ['snap_sensitivity_mean', 'Sensib. SNAP', (v) => plus(v, 2)],
        ['pct_high_risk', '% Riesgo Alto', pc], ['pct_med_risk', '% Riesgo Medio', pc], ['pct_low_risk', '% Riesgo Bajo', pc],
      ]} />
    </>
  )
}

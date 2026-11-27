import { useEffect, useRef, useState } from 'react'
import Plotly from 'plotly.js-cartesian-dist-min'
import { C } from './logic'

const axis = (a = {}) => ({
  linecolor: C.grid, zerolinecolor: C.grid, gridcolor: C.grid, tickfont: { color: C.muted, size: 11 }, automargin: true,
  ...a, title: a.title ? { text: a.title, font: { size: 12 } } : undefined,
})

export function Chart({ data, layout = {}, height = 360 }) {
  const ref = useRef(null)
  useEffect(() => {
    const { xaxis, yaxis, yaxis2, margin, ...rest } = layout
    Plotly.react(ref.current, data, {
      height, paper_bgcolor: C.surface, plot_bgcolor: C.surface,
      font: { family: '-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif', size: 12, color: C.ink },
      margin: { t: 32, b: 48, l: 55, r: 24, ...margin },
      legend: { orientation: 'h', yanchor: 'top', y: -0.2, x: 0, font: { size: 11.5 } },
      xaxis: axis({ showgrid: false, ...xaxis }), yaxis: axis(yaxis),
      ...(yaxis2 && { yaxis2: axis({ overlaying: 'y', side: 'right', showgrid: false, ...yaxis2 }) }),
      ...rest,
    }, { responsive: true, displaylogo: false })
  })
  useEffect(() => {
    const node = ref.current
    const observer = new ResizeObserver(() => node.offsetWidth && node.data && Plotly.Plots.resize(node))
    observer.observe(node)
    return () => { observer.disconnect(); Plotly.purge(node) }
  }, [])
  return <div ref={ref} className="chart" style={{ minHeight: height }} />
}

// Cascada construida con barras: cada paso es [etiqueta, valor, esTotal].
export function Waterfall({ steps, yTitle, height }) {
  let run = 0
  const bars = steps.map(([label, value, total], i) => {
    const base = total || i === 0 && steps.at(-1)[2] && value > 0 ? 0 : run
    run = total ? value : base + value
    return { label, value, base, color: total ? C.blue : value < 0 ? C.red : C.bright }
  })
  return (
    <Chart
      height={height}
      data={[{
        type: 'bar', x: bars.map((b) => b.label), y: bars.map((b) => b.value), base: bars.map((b) => b.base),
        marker: { color: bars.map((b) => b.color) }, textposition: 'outside', cliponaxis: false,
        text: steps.map((s) => s[3]), hovertemplate: '%{x}: %{text}<extra></extra>', textangle: 0,
      }]}
      layout={{ showlegend: false, yaxis: { tickprefix: '$', title: yTitle }, margin: { l: 70 } }}
    />
  )
}

export const Card = ({ title, children, note }) => (
  <section className="card">
    {title && <h3 className="question">{title}</h3>}
    {note && <p className="takeaway">{note}</p>}
    {children}
  </section>
)

export const Kpi = ({ label, value, sub, accent = '' }) => (
  <div className="kpi">
    <div className="kpi-label">{label}</div>
    <div className={`kpi-value ${accent}`}>{value}</div>
    <div className="kpi-sub">{sub}</div>
  </div>
)

export function Table({ rows, columns, limit = 200 }) {
  const [shown, setShown] = useState(limit)
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead><tr>{columns.map(([k, label]) => <th key={k}>{label}</th>)}</tr></thead>
          <tbody>
            {rows.slice(0, shown).map((r, i) => (
              <tr key={r.id || i}>
                {columns.map(([k, , format]) => (
                  <td key={k} className={typeof r[k] === 'number' ? 'n' : ''}>
                    {r[k] === null || r[k] === undefined ? '—' : format ? format(r[k]) : typeof r[k] === 'boolean' ? (r[k] ? '✓' : '') : r[k]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > shown && <button className="link" onClick={() => setShown(shown + limit)}>Mostrar más filas ({shown} de {rows.length})</button>}
    </>
  )
}

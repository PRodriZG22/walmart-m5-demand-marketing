import { StrictMode, useDeferredValue, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { loadBase } from './data'
import Resumen from './Resumen'
import Producto from './Producto'
import Simulador from './Simulador'
import Auditoria from './Auditoria'
import {
  DEPTS, RISKS, STORES, STRATEGY_SHORT, VIEWS, applyFilters, defaults, filtersFromUrl, filtersToUrl, groupSum, num, tr,
} from './logic'
import './styles.css'

function Multi({ label, options, value, onChange, totals, format = (x) => x }) {
  return (
    <fieldset className="multi">
      <legend>{label}</legend>
      {options.map((o) => (
        <label key={o}>
          <input type="checkbox" checked={value.includes(o)} onChange={(e) => onChange(e.target.checked ? [...value, o] : value.filter((v) => v !== o))} />
          <span>{format(o)} <small>({num(totals[o] || 0)})</small></span>
        </label>
      ))}
    </fieldset>
  )
}

function Dashboard({ diag, reports }) {
  const clusters = useMemo(() => reports.kmeans_profiles.map((p) => p.cluster_name), [reports])
  const [view, setView] = useState(() => {
    const v = new URLSearchParams(window.location.search).get('vista')
    return v in VIEWS ? v : 'gerente'
  })
  const [filters, setFilters] = useState(() => filtersFromUrl(view, clusters))
  const [tab, setTab] = useState(null)
  const [selected, setSelected] = useState(null)
  const [open, setOpen] = useState(false)
  const tabs = VIEWS[view].tabs
  const current = tabs.some(([k]) => k === tab) ? tab : tabs[0][0]
  const set = (key) => (value) => setFilters((f) => ({ ...f, [key]: value }))

  useEffect(() => filtersToUrl(view, filters, clusters), [view, filters, clusters])

  const changeView = (next) => {
    // Riesgo, estrategia y el filtro de monto son propios de cada vista.
    const d = defaults(next, clusters)
    setFilters((f) => ({ ...f, riesgo: d.riesgo, estrategia: d.estrategia, usd: d.usd }))
    setView(next)
  }

  const deferred = useDeferredValue(filters)
  const { rows, scope, reason } = useMemo(() => applyFilters(diag, view, deferred), [diag, view, deferred])
  const totals = useMemo(() => Object.fromEntries(['store_id', 'dept_id', 'risk_level', 'primary_strategy', 'cluster_name'].map((k) => [k, groupSum(diag, k)])), [diag])

  return (
    <div className="layout">
      <button className="menu" onClick={() => setOpen(!open)}>{open ? 'Cerrar filtros' : 'Filtros y vista'}</button>
      <aside className={open ? 'open' : ''}>
        <label className="field">Ver como
          <select value={view} onChange={(e) => changeView(e.target.value)}>
            {Object.entries(VIEWS).map(([k, v]) => <option key={k} value={k}>{v.name}</option>)}
          </select>
        </label>
        <h4>Filtrar catálogo</h4>
        <label className="field">Buscar producto
          <input type="text" placeholder="Ej. FOODS_3_282 o CA_3" value={filters.q} onChange={(e) => set('q')(e.target.value)} />
        </label>
        <Multi label="Tiendas" options={STORES} value={filters.tienda} onChange={set('tienda')} totals={totals.store_id} />
        <Multi label="Departamentos" options={DEPTS} value={filters.depto} onChange={set('depto')} totals={totals.dept_id} />
        <Multi label="Nivel de prioridad" options={RISKS} value={filters.riesgo} onChange={set('riesgo')} totals={totals.risk_level} />
        <Multi label="Estrategia recomendada" options={Object.keys(STRATEGY_SHORT)} value={filters.estrategia} onChange={set('estrategia')} totals={totals.primary_strategy} format={(x) => tr(STRATEGY_SHORT[x], view)} />
        <Multi label="Grupo comercial" options={clusters} value={filters.grupo} onChange={set('grupo')} totals={totals.cluster_name} />
        <label className="check"><input type="checkbox" checked={filters.snap} onChange={(e) => set('snap')(e.target.checked)} /> Solo sensibles a pagos SNAP</label>
        {view === 'gestor' && <label className="check"><input type="checkbox" checked={filters.usd} onChange={(e) => set('usd')(e.target.checked)} /> Solo con ingreso en riesgo mayor que $0</label>}
        <button className="secondary" onClick={() => setFilters(defaults(view, clusters))}>Restablecer filtros</button>
        <p className="takeaway">Entre paréntesis: total de productos por tienda en todo el portafolio.</p>
        <div className="counter">Mostrando <strong>{num(rows.length)}</strong> de <strong>{num(diag.length)}</strong> productos por tienda<br />({num(rows.length / diag.length * 100, 1)}% del portafolio de alimentos CA)</div>
      </aside>
      <main>
        <header>
          <div className="eyebrow">Walmart California · Inteligencia Comercial</div>
          <h1>Radar de Promociones e Ingresos en Riesgo</h1>
          <p>Identifica qué alimentos venderían menos que en sus últimos 90 días según el pronóstico a 28 días, cuánto ingreso representa y qué acción conviene probar.</p>
        </header>
        <nav>{tabs.map(([k, name]) => <button key={k} className={k === current ? 'active' : ''} onClick={() => setTab(k)}>{name}</button>)}</nav>
        {current === 'auditoria' ? <Auditoria rows={rows} total={diag.length} reports={reports} />
          : !rows.length ? <div className="notice">Ningún producto coincide con los filtros actuales. {reason}</div>
            : current === 'resumen' ? <Resumen rows={rows} scope={scope} view={view} />
              : current === 'producto' ? <Producto rows={rows} view={view} selected={selected} onSelect={setSelected} />
                : <Simulador rows={rows} view={view} filters={filters} />}
      </main>
    </div>
  )
}

function App() {
  const [state, setState] = useState({})
  useEffect(() => { loadBase().then(setState, (e) => setState({ error: e.message })) }, [])
  if (state.error) return <div className="screen"><p>No se pudieron cargar los datos desde Supabase: {state.error}</p><button className="primary" onClick={() => window.location.reload()}>Reintentar</button></div>
  if (!state.diag) return <div className="screen">Cargando diagnóstico comercial…</div>
  return <Dashboard {...state} />
}

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>)

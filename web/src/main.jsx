import { StrictMode, useDeferredValue, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { loadBase } from './data'
import Resumen from './Resumen'
import Producto from './Producto'
import Simulador from './Simulador'
import Auditoria from './Auditoria'
import {
  ACTIONS, DEPTS, RISKS, STORES, STRATEGY_SHORT, VIEWS, activeAction, applyFilters, countRows, defaults, filtersFromUrl, filtersToUrl, num,
} from './logic'
import './styles.css'

// Lista de una sola elección: «Todas» significa sin restricción. Las opciones sin casos se desactivan.
function Pick({ label, all, options, value, onChange, count }) {
  const current = value.length === options.length ? '' : value.length === 1 ? value[0] : 'varias'
  return (
    <label className="field">{label}
      <select value={current} onChange={(e) => onChange(e.target.value ? [e.target.value] : options)}>
        <option value="">{all} ({num(count(options))})</option>
        {current === 'varias' && <option value="varias" disabled>{value.length ? `Varias (${value.length})` : 'Ninguna'}</option>}
        {options.map((o) => {
          const n = count([o])
          return <option key={o} value={o} disabled={!n && current !== o}>{o} ({num(n)})</option>
        })}
      </select>
    </label>
  )
}

// Selección múltiple con cantidades, para el nivel experto.
function Multi({ label, options, value, onChange, count, format = (x) => x }) {
  const all = value.length === options.length
  return (
    <details className="more">
      <summary>{label}: <em>{all ? 'sin filtrar' : value.length ? `${value.length} de ${options.length}` : 'ninguna'}</em></summary>
      {options.map((o) => {
        const n = count([o])
        const on = value.includes(o)
        return (
          <label key={o} className={!n && !on ? 'check off' : 'check'}>
            <input type="checkbox" checked={on} disabled={!n && !on} onChange={(e) => onChange(e.target.checked ? [...value, o] : value.filter((v) => v !== o))} />
            <span>{format(o)} <small>({num(n)})</small></span>
          </label>
        )
      })}
      {!all && <button type="button" className="link" onClick={() => onChange(options)}>Marcar todo</button>}
    </details>
  )
}

// Cada perfil ve solo lo que necesita. `hidden` son los filtros que esa vista no ofrece.
const PROFILES = {
  gerente: {
    actions: ['todo', 'rebaja', 'combo', 'snap'], main: ['tienda'], more: [],
    hidden: ['depto', 'q', 'grupo', 'snap'],
  },
  gestor: {
    actions: ['intervenir', 'rebaja', 'combo', 'urgentes', 'todo'], main: ['tienda', 'q'], more: ['depto', 'usd'],
    hidden: ['grupo', 'snap'],
  },
  analista: {
    actions: [], main: ['q', 'mtienda', 'mriesgo'], more: ['mdepto', 'mestrategia', 'mgrupo', 'snap'],
    hidden: [],
  },
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
    // Acción, prioridad y monto vuelven a los de la vista; se limpia lo que la nueva vista no ofrece.
    const d = defaults(next, clusters)
    setFilters((f) => ({ ...f, riesgo: d.riesgo, estrategia: d.estrategia, usd: d.usd, ...Object.fromEntries(PROFILES[next].hidden.map((k) => [k, d[k]])) }))
    setView(next)
  }

  const deferred = useDeferredValue(filters)
  const { rows, scope, reason } = useMemo(() => applyFilters(diag, view, deferred), [diag, view, deferred])
  const count = (patch) => countRows(diag, view, { ...deferred, ...patch })
  const profile = PROFILES[view]
  const actions = profile.actions.map((k) => ACTIONS.find((a) => a.key === k))
  const found = activeAction(view, filters)
  const action = found && profile.actions.includes(found.key) ? found : null

  // Etiquetas de lo que está restringiendo la lista, cada una con su forma de quitarlo.
  const chips = []
  const chip = (key, text, value) => chips.push({ key, text, clear: () => set(key)(value) })
  const brief = (list) => (list.length === 1 ? list[0] : list.length ? `${list.length} elegidos` : 'ninguno')
  if (filters.tienda.length !== STORES.length) chip('tienda', `Tienda: ${brief(filters.tienda)}`, STORES)
  if (filters.depto.length !== DEPTS.length) chip('depto', `Departamento: ${brief(filters.depto)}`, DEPTS)
  if (filters.q.trim()) chip('q', `Búsqueda: ${filters.q.trim()}`, '')
  if (filters.riesgo.length !== RISKS.length && action?.key !== 'urgentes') chip('riesgo', `Prioridad: ${brief(filters.riesgo)}`, RISKS)
  const allStrategies = ACTIONS[0].estrategia
  if (!action && filters.estrategia.length !== allStrategies.length) {
    chip('estrategia', `Estrategia: ${brief(filters.estrategia.map((x) => STRATEGY_SHORT[x]))}`, allStrategies)
  }
  if (filters.grupo.length !== clusters.length) chip('grupo', `Grupo: ${brief(filters.grupo)}`, clusters)
  if (filters.snap) chip('snap', 'Solo sensibles a SNAP', false)
  if (view === 'gestor' && filters.usd) chip('usd', 'Sin los de $0 en riesgo', false)

  const controls = {
    tienda: <Pick key="tienda" label="Tienda" all="Todas las tiendas" options={STORES} value={filters.tienda} onChange={set('tienda')} count={(v) => count({ tienda: v })} />,
    q: (
      <label key="q" className="field">Buscar por código
        <input type="text" placeholder="Ej. FOODS_3_282" value={filters.q} onChange={(e) => set('q')(e.target.value)} />
      </label>
    ),
    depto: <Pick key="depto" label="Departamento" all="Todos" options={DEPTS} value={filters.depto} onChange={set('depto')} count={(v) => count({ depto: v })} />,
    grupo: <Pick key="grupo" label="Grupo comercial" all="Todos" options={clusters} value={filters.grupo} onChange={set('grupo')} count={(v) => count({ grupo: v })} />,
    snap: <label key="snap" className="check"><input type="checkbox" checked={filters.snap} onChange={(e) => set('snap')(e.target.checked)} /> Solo sensibles a pagos SNAP</label>,
    usd: <label key="usd" className="check"><input type="checkbox" checked={!filters.usd} onChange={(e) => set('usd')(!e.target.checked)} /> Incluir productos con $0 en riesgo</label>,
    mtienda: <Multi key="mtienda" label="Tiendas" options={STORES} value={filters.tienda} onChange={set('tienda')} count={(v) => count({ tienda: v })} />,
    mdepto: <Multi key="mdepto" label="Departamentos" options={DEPTS} value={filters.depto} onChange={set('depto')} count={(v) => count({ depto: v })} />,
    mriesgo: <Multi key="mriesgo" label="Nivel de riesgo" options={RISKS} value={filters.riesgo} onChange={set('riesgo')} count={(v) => count({ riesgo: v })} />,
    mestrategia: <Multi key="mestrategia" label="Acción recomendada" options={allStrategies} value={filters.estrategia} onChange={set('estrategia')} count={(v) => count({ estrategia: v })} format={(x) => STRATEGY_SHORT[x]} />,
    mgrupo: <Multi key="mgrupo" label="Grupo (K-Means)" options={clusters} value={filters.grupo} onChange={set('grupo')} count={(v) => count({ grupo: v })} />,
  }
  const hidden = chips.filter((c) => profile.more.includes(c.key)).length

  return (
    <div className="layout">
      <button className="menu" onClick={() => setOpen(!open)}>{open ? 'Cerrar filtros' : 'Filtros y vista'}</button>
      <aside className={open ? 'open' : ''}>
        <label className="field">Ver como
          <select value={view} onChange={(e) => changeView(e.target.value)}>
            {Object.entries(VIEWS).map(([k, v]) => <option key={k} value={k}>{v.name}</option>)}
          </select>
        </label>
        {actions.length > 0 && (
          <div className="actions" role="group" aria-label="¿Qué quieres hacer?">
            <h4>1. ¿Qué quieres hacer?</h4>
            {actions.map((a) => {
              const n = count({ riesgo: a.riesgo, estrategia: a.estrategia })
              const on = action?.key === a.key
              return (
                <button key={a.key} type="button" className={on ? 'action active' : 'action'} aria-pressed={on} disabled={!n && !on}
                  onClick={() => setFilters((f) => ({ ...f, riesgo: a.riesgo, estrategia: a.estrategia }))}>
                  <span>{a.label}<small>{a.desc}</small></span><b>{num(n)}</b>
                </button>
              )
            })}
          </div>
        )}
        <h4>{actions.length ? '2. ¿Dónde?' : 'Filtrar'}</h4>
        {profile.main.map((k) => controls[k])}
        {profile.more.length > 0 && (
          <details className="more">
            <summary>Más opciones{hidden ? ` (${hidden} en uso)` : ''}</summary>
            {profile.more.map((k) => controls[k])}
          </details>
        )}
        <button className="secondary" onClick={() => setFilters(defaults(view, clusters))}>Volver al inicio</button>
      </aside>
      <main>
        <header>
          <div className="eyebrow">Walmart California · Inteligencia Comercial</div>
          <h1>Radar de Promociones e Ingresos en Riesgo</h1>
          <p>Identifica qué alimentos venderían menos que en sus últimos 90 días según el pronóstico a 28 días, cuánto ingreso representa y qué acción conviene probar.</p>
        </header>
        <div className="summary" aria-live="polite">
          <span>Estás viendo <strong>{num(rows.length)}</strong> de {num(diag.length)} productos por tienda: <strong>{action ? action.label : chips.length ? 'Selección personalizada' : 'Sin filtros'}</strong></span>
          {chips.map((c) => <button key={c.key} type="button" className="chip" onClick={c.clear} title="Quitar este filtro">{c.text} ×</button>)}
        </div>
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

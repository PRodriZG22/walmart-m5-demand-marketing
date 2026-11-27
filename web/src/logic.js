// Reglas de presentación portadas de app/dashboard.py. Los cálculos pesados ya vienen resueltos en Supabase.
export const C = {
  bg: '#F5F5F7', surface: '#FFFFFF', ink: '#1D1D1F', muted: '#6E6E73', blue: '#0071E3', red: '#D70015',
  amber: '#B25000', orange: '#FF9500', green: '#1E7E34', bright: '#34C759', gray: '#8E8E93', grid: '#E5E5EA',
}
export const STORES = ['CA_1', 'CA_2', 'CA_3', 'CA_4']
export const DEPTS = ['FOODS_1', 'FOODS_2', 'FOODS_3']
export const RISKS = ['Riesgo Alto', 'Riesgo Medio', 'Riesgo Bajo']
export const RISK_COLORS = { 'Riesgo Alto': C.red, 'Riesgo Medio': C.orange, 'Riesgo Bajo': C.bright }
export const MARKDOWN = 'Precios Dinámicos / Markdown (20%–35%)'
export const CROSS = 'Cross-Selling y Visibilidad Omnicanal (Sin Descuento)'
const STRATEGY_URL = {
  rebaja: MARKDOWN,
  combo: CROSS,
  snap: 'Sincronización SNAP (Base EDLP)',
  habitual: 'Mantenimiento EDLP y Producto Ancla',
}
export const STRATEGY_SHORT = {
  [CROSS]: 'Combos Cross-Selling',
  [MARKDOWN]: 'Descuentos Inteligentes',
  'Sincronización SNAP (Base EDLP)': 'Calendario SNAP',
  'Mantenimiento EDLP y Producto Ancla': 'Precio Habitual',
}
export const ELASTICITIES = { Conservador: 0.4, Esperado: 0.6, Optimista: 0.8 }
export const HIST_SCENARIO = 'Según historial (acotado)'
export const NO_SALES = 'Casi sin ventas'
export const NO_AMOUNT = 'Alerta sin monto en riesgo'
export const RESTOCK = '-20% a -30%'
export const SNAP_PCT = 15
export const INTERMITTENCY = 70

export const VIEWS = {
  gerente: { name: 'Gerente de marketing', tabs: [['resumen', 'Resumen Ejecutivo'], ['producto', 'Decisión por Producto']] },
  gestor: {
    name: 'Gestor de categoría o precios',
    tabs: [['resumen', 'Cartera de Decisiones'], ['producto', 'Decisión por Producto'], ['simulador', 'Simulador y Plan']],
  },
  analista: {
    name: 'Analista o docente',
    tabs: [['auditoria', 'Respaldo IA (Auditoría Técnica)'], ['resumen', 'Resumen de Negocio'], ['producto', 'Decisión por Producto'], ['simulador', 'Simulador y Plan']],
  },
}

const VOCAB = {
  gerente: [
    ['migración operativa LEFO→FEFO', 'rotar primero lo que vence antes'], ['Combos Cross-Selling', 'Venta conjunta'],
    ['Cross-Selling', 'Venta conjunta'], ['en base EDLP', 'con precio habitual'], ['(EDLP)', ''],
    ['rotación FEFO', 'rotación de lo que vence antes'], ['Markdown', 'Rebaja temporal'], ['EDLP', 'precio habitual'],
  ],
  gestor: [
    ['migración operativa LEFO→FEFO', 'rotación FEFO'], ['Combos Cross-Selling', 'Venta cruzada (combo)'],
    ['Cross-Selling', 'Venta cruzada'], ['en base EDLP', 'con precio habitual (EDLP)'], ['Markdown', 'Rebaja táctica (markdown)'],
  ],
  analista: [],
}
export const tr = (text, view) => VOCAB[view].reduce((t, [a, b]) => t.replaceAll(a, b), String(text))

export const num = (v, d = 0) => Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
export const usd = (v, d = 0) => `$${num(v, d)}`
export const signed = (v) => `${v < 0 ? '−' : '+'}$${num(Math.abs(v))}`
export const plus = (v, d = 1) => `${v >= 0 ? '+' : ''}${num(v, d)}`
export const sum = (rows, f) => rows.reduce((a, r) => a + (typeof f === 'string' ? r[f] || 0 : f(r)), 0)
export const groupSum = (rows, key, field) => {
  const out = {}
  for (const r of rows) out[r[key]] = (out[r[key]] || 0) + (field ? r[field] : 1)
  return out
}
export const topEntry = (obj) => Object.entries(obj).sort((a, b) => b[1] - a[1])[0] || ['—', 0]
export const displayName = (id) => id.replace('_evaluation', '').replace(/_CA_(\d)$/, ' · Tienda CA_$1')

export function scenario(rows, d, eps) {
  const cap = (1 - d) ** -Math.max(...Object.values(ELASTICITIES)) - 1
  let base = 0, extra = 0, units = 0, extraUnits = 0
  for (const r of rows) {
    const u = r.pred_total_28d_units, p = r.current_price
    const lift = eps == null ? Math.min(Math.max(r.price_sensitivity || 0, 0), cap) : (1 - d) ** -eps - 1
    base += u * p
    extra += u * lift * p * (1 - d)
    units += u
    extraUnits += u * lift
  }
  const discount = -d * base
  return {
    base, extra, discount, units, extraUnits, withDiscount: base + discount + extra, net: discount + extra,
    lift: units ? extraUnits / units : 0, breakEven: d / (1 - d),
  }
}

// ---- Filtros y URL ----
export const defaults = (view, clusters) => ({
  tienda: STORES,
  depto: DEPTS,
  riesgo: RISKS,
  q: '',
  estrategia: view === 'gestor' ? [MARKDOWN, CROSS] : Object.values(STRATEGY_URL),
  grupo: clusters,
  snap: false,
  usd: view === 'gestor',
})

const codes = (key, clusters) => {
  const same = (list) => Object.fromEntries(list.map((v) => [v, v]))
  if (key === 'tienda') return same(STORES)
  if (key === 'depto') return same(DEPTS)
  if (key === 'riesgo') return Object.fromEntries(RISKS.map((v) => [v.split(' ').pop().toLowerCase(), v]))
  if (key === 'estrategia') return STRATEGY_URL
  if (key === 'grupo') return Object.fromEntries(clusters.map((v, i) => [String(i), v]))
  return null
}

export function filtersFromUrl(view, clusters) {
  const params = new URLSearchParams(window.location.search)
  const out = defaults(view, clusters)
  for (const key of Object.keys(out)) {
    if (!params.has(key)) continue
    const map = codes(key, clusters)
    if (map) {
      const raw = params.getAll(key)
      const valid = raw.filter((c) => c in map).map((c) => map[c])
      if (valid.length || raw.join() === '-') out[key] = valid
    } else out[key] = typeof out[key] === 'boolean' ? params.get(key) === '1' : params.get(key)
  }
  return out
}

export function filtersToUrl(view, filters, clusters) {
  const params = new URLSearchParams({ vista: view })
  for (const [key, def] of Object.entries(defaults(view, clusters))) {
    const value = filters[key]
    const map = codes(key, clusters)
    const equal = map ? [...value].sort().join() === [...def].sort().join() : value === def
    if (equal) continue
    if (map) {
      const inverse = Object.fromEntries(Object.entries(map).map(([c, v]) => [v, c]))
      if (value.length) value.forEach((v) => params.append(key, inverse[v]))
      else params.set(key, '-')
    } else params.set(key, typeof def === 'boolean' ? (value ? '1' : '0') : value)
  }
  window.history.replaceState(null, '', `?${params}`)
}

// ---- Atajos «¿Qué quieres hacer?»: cada uno fija prioridad y estrategia a la vez ----
const ALL_STRATEGIES = Object.values(STRATEGY_URL)
export const ACTIONS = [
  { key: 'todo', label: 'Ver todo', desc: 'Todos los productos', riesgo: RISKS, estrategia: ALL_STRATEGIES },
  { key: 'intervenir', label: 'Por intervenir', desc: 'Todos los de riesgo alto o medio', riesgo: RISKS, estrategia: [MARKDOWN, CROSS], views: ['gestor'] },
  { key: 'urgentes', label: 'Casos urgentes', desc: 'Solo riesgo alto', riesgo: [RISKS[0]], estrategia: ALL_STRATEGIES },
  { key: 'rebaja', label: 'Probar rebajas', desc: 'Antes respondieron a un descuento', riesgo: RISKS, estrategia: [MARKDOWN] },
  { key: 'combo', label: 'Ofrecer en combo', desc: 'En riesgo, sin bajar el precio', riesgo: RISKS, estrategia: [CROSS] },
  { key: 'snap', label: 'Días de pago SNAP', desc: 'Reforzar stock del 1 al 10', riesgo: RISKS, estrategia: [STRATEGY_URL.snap] },
  { key: 'habitual', label: 'Mantener precio', desc: 'Riesgo bajo, sin promoción', riesgo: RISKS, estrategia: [STRATEGY_URL.habitual] },
]
const sameSet = (a, b) => a.length === b.length && a.every((v) => b.includes(v))
export const activeAction = (view, f) => ACTIONS.find((a) => (!a.views || a.views.includes(view))
  && sameSet(a.riesgo, f.riesgo) && sameSet(a.estrategia, f.estrategia))

function buildTests(view, f) {
  const q = f.q.trim().toLowerCase()
  const matches = (r) => !q || [r.id, r.item_id, r.display_name].some((s) => s.toLowerCase().includes(q))
  const inList = (field, list) => { const s = new Set(list); return (r) => s.has(r[field]) }
  const tests = {
    Tiendas: inList('store_id', f.tienda),
    Departamentos: inList('dept_id', f.depto),
    'Nivel de prioridad': inList('risk_level', f.riesgo),
    'Estrategia recomendada': inList('primary_strategy', f.estrategia),
    'Grupo comercial': inList('cluster_name', f.grupo),
  }
  if (view === 'gestor' && f.usd) tests['Solo con ingreso en riesgo'] = (r) => r.revenue_at_risk_usd > 0
  if (f.snap) tests['Solo sensibles a SNAP'] = (r) => r.snap_priority
  if (q) tests['Buscar producto'] = matches
  return { tests, matches }
}

// Cuántos casos quedarían con esos filtros (para mostrar cantidades y desactivar opciones vacías).
export function countRows(diag, view, f) {
  const all = Object.values(buildTests(view, f).tests)
  let n = 0
  for (const r of diag) if (all.every((t) => t(r))) n++
  return n
}

// Nombre con el que cada vista muestra el control que aplica ese filtro.
function controlName(test, view) {
  const expert = view === 'analista'
  const names = {
    Tiendas: expert ? 'Tiendas' : 'Tienda',
    Departamentos: expert ? 'Departamentos' : 'Departamento',
    'Nivel de prioridad': expert ? 'Nivel de riesgo' : '¿Qué quieres hacer?',
    'Estrategia recomendada': expert ? 'Acción recomendada' : '¿Qué quieres hacer?',
    'Grupo comercial': 'Grupo (K-Means)',
    'Solo con ingreso en riesgo': 'Incluir productos con $0 en riesgo',
    'Solo sensibles a SNAP': 'Solo sensibles a pagos SNAP',
    'Buscar producto': 'Buscar por código',
  }
  return `«${names[test]}»`
}

export function applyFilters(diag, view, f) {
  const { tests, matches } = buildTests(view, f)
  const all = Object.values(tests)
  const rows = diag.filter((r) => all.every((t) => t(r))).map((r) => ({ ...r, strategy_short: tr(r.strategy_short, view) }))
  const scope = diag.filter((r) => tests.Tiendas(r) && tests.Departamentos(r) && matches(r))
  let reason = ''
  if (!rows.length) {
    const guilty = Object.keys(tests).filter((n) =>
      diag.some((r) => Object.entries(tests).every(([m, t]) => m === n || t(r))))
    reason = guilty.length
      ? `Revisa: ${[...new Set(guilty.map((n) => controlName(n, view)))].join(', ')}. Al ampliar cualquiera de ellos vuelven los resultados.`
      : 'Hay más de un filtro que deja la selección vacía. Usa «Volver al inicio».'
  }
  return { rows, scope, reason }
}

export function downloadCsv(name, rows, columns) {
  const cell = (v) => {
    if (v === null || v === undefined) return ''
    if (typeof v === 'boolean') return v ? 'True' : 'False'
    const s = String(v)
    return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s
  }
  const text = [columns.join(','), ...rows.map((r) => columns.map((c) => cell(r[c])).join(','))].join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob(['﻿', text], { type: 'text/csv;charset=utf-8' }))
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}

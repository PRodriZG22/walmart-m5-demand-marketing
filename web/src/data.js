import { createClient } from '@supabase/supabase-js'

// Clave publicable: es pública por diseño. Las políticas RLS solo permiten leer.
const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL || 'https://iunhctzixsuetrsanfty.supabase.co',
  import.meta.env.VITE_SUPABASE_KEY || 'sb_publishable_JA85ButxYiRva0R7OmkrIw_EikLtMgO',
)

const check = ({ data, error }) => {
  if (error) throw new Error(error.message)
  return data
}

export async function loadBase() {
  const PAGE = 1000
  const first = await supabase.from('diagnosis').select('*', { count: 'exact' }).order('id').range(0, PAGE - 1)
  const rows = check(first)
  const rest = []
  for (let i = PAGE; i < first.count; i += PAGE) {
    rest.push(supabase.from('diagnosis').select('*').order('id').range(i, i + PAGE - 1).then(check))
  }
  const [pages, reports] = await Promise.all([Promise.all(rest), supabase.from('reports').select('*').then(check)])
  return {
    diag: rows.concat(...pages),
    reports: Object.fromEntries(reports.map((r) => [r.key, r.data])),
  }
}

const cache = new Map()
export function loadSeries(id) {
  if (!cache.has(id)) {
    const p = supabase.from('series').select('*').eq('id', id).single().then(check)
    p.catch(() => cache.delete(id))
    cache.set(id, p)
  }
  return cache.get(id)
}

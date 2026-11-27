# Dashboard Walmart M5 en React + Supabase

- **Web pública:** https://walmart-m5-radar.vercel.app/ (vistas: `?vista=gerente`, `?vista=gestor`, `?vista=analista`)
- **Datos:** Supabase, proyecto `walmart-m5-dashboard` (tablas `diagnosis`, `series`, `reports`; solo lectura pública con RLS)
- **Alojamiento:** Vercel, proyecto `walmart-m5-radar`

La app de Streamlit (`app/dashboard.py`) sigue siendo la fuente de los cálculos. Esta web los muestra.

## Ejecutar en local

```bash
cd web
npm install
npm run dev
```

## Publicar cambios

Vercel no está conectado a GitHub: un `git push` no actualiza la web. Desde `web/`:

```bash
npx vercel --prod
```

## Actualizar los datos (solo si se reentrena el modelo)

`scripts/cargar_supabase.py` solo inserta. Antes hay que vaciar las tres tablas y crear en cada una una
política temporal de inserción para `anon` que exija una cabecera `x-load-token`; al terminar, borrar la
política y retirar el permiso de inserción. Ejecutar con las variables `SUPABASE_URL`, `SUPABASE_KEY` y `LOAD_TOKEN`.

## Límites del plan gratuito

- Supabase puede pausar el proyecto tras una semana sin actividad; se reactiva desde su panel.
- El plan Hobby de Vercel es para uso no comercial.

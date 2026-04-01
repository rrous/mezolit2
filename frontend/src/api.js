// ── Data fetching layer ────────────────────────────────────────────────────────
// In static mode (CZ branch): loads GeoJSON from /data/cz/
// In Supabase mode (master): calls Supabase RPC functions

import { SUPABASE_URL, SUPABASE_ANON_KEY, STATIC_MODE, REGION } from './config.js'

const _cache = {}

// ── Static GeoJSON loader ────────────────────────────────────────────────────

async function loadStatic(filename) {
  if (_cache[filename]) return _cache[filename]

  const res = await fetch(`/data/${REGION}/${filename}`)
  if (!res.ok) throw new Error(`Failed to load ${filename} (${res.status})`)

  const data = await res.json()
  _cache[filename] = data
  return data
}

// ── Supabase RPC wrapper (kept for Yorkshire/master) ─────────────────────────

async function rpc(fn, params = {}, { cache = false } = {}) {
  const key = fn + JSON.stringify(params)
  if (cache && _cache[key]) return _cache[key]

  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: {
      'apikey':       SUPABASE_ANON_KEY,
      'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
      'Content-Type': 'application/json',
      'Accept':       'application/json',
      'Content-Profile': 'public'
    },
    body: JSON.stringify(params)
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`RPC ${fn} failed (${res.status}): ${text}`)
  }

  const data = await res.json()
  if (cache) _cache[key] = data
  return data
}

// ── Public API ────────────────────────────────────────────────────────────────

export function fetchTerrain(west, south, east, north, zoom) {
  if (STATIC_MODE) return loadStatic('terrain_features_with_biotopes_cz.geojson')
  return rpc('get_terrain', { west, south, east, north, zoom })
}

export function fetchRivers(west, south, east, north, zoom) {
  if (STATIC_MODE) return loadStatic('rivers_cz.geojson')
  return rpc('get_rivers', { west, south, east, north, zoom })
}

export function fetchEcotones(west, south, east, north) {
  if (STATIC_MODE) return loadStatic('ecotones_cz.geojson')
  return rpc('get_ecotones', { west, south, east, north })
}

export function fetchCoastline() {
  // No coastline in CZ
  if (STATIC_MODE) return Promise.resolve({ type: 'FeatureCollection', features: [] })
  return rpc('get_coastline', {}, { cache: true })
}

export function fetchSites() {
  if (STATIC_MODE) return loadStatic('sites_cz.geojson')
  return rpc('get_sites', {}, { cache: true })
}

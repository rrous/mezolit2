// ── Supabase RPC wrapper ───────────────────────────────────────────────────────
// Calls Supabase RPC functions via plain fetch (no supabase-js dependency).
// Static data (coastline, sites) is cached in memory.

import { SUPABASE_URL, SUPABASE_ANON_KEY } from './config.js'

const _cache = {}

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
  return rpc('get_terrain', { west, south, east, north, zoom })
}

export function fetchRivers(west, south, east, north, zoom) {
  return rpc('get_rivers', { west, south, east, north, zoom })
}

export function fetchEcotones(west, south, east, north) {
  return rpc('get_ecotones', { west, south, east, north })
}

export function fetchCoastline() {
  return rpc('get_coastline', {}, { cache: true })
}

export function fetchSites() {
  return rpc('get_sites', {}, { cache: true })
}

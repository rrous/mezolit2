// ── Supabase connection ────────────────────────────────────────────────────────
export const SUPABASE_URL     = import.meta.env.VITE_SUPABASE_URL
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY

// ── Map defaults ───────────────────────────────────────────────────────────────
export const MAP_CENTER = [54.1, -1.2]  // centre of Yorkshire
export const MAP_ZOOM   = 8
export const RIVERS_MIN_ZOOM   = 10  // don't fetch rivers below this zoom
export const ECOTONES_MIN_ZOOM = 10  // ecotones are complex MultiLineStrings, hide at low zoom

// ── Biotope fill colours ───────────────────────────────────────────────────────
export const BIOTOPE_COLOR = {
  bt_001: '#4A90D9',  // Lake
  bt_002: '#7FB069',  // Wetland
  bt_003: '#2D6A4F',  // Boreal forest
  bt_004: '#E9C46A',  // Open upland
  bt_005: '#F4A261',  // Coastal saltmarsh
  bt_006: '#D4A373',  // Chalk scrub
  bt_007: '#52B788',  // Riparian forest
  bt_008: '#ADB5BD',  // Intertidal
  bt_009: '#95D5B2',  // Forest glade (micro)
  bt_010: '#F2CC8F',  // Post-fire grassland
  bt_011: '#A8DADC',  // Drought-stressed wetland
  _default: '#CCCCCC'
}

// ── Certainty → base polygon opacity ──────────────────────────────────────────
export const CERTAINTY_OPACITY = {
  DIRECT:      0.90,
  INDIRECT:    0.75,
  INFERENCE:   0.60,
  SPECULATION: 0.45,
  _default:    0.60
}

// ── Certainty → stroke dash pattern ───────────────────────────────────────────
export const CERTAINTY_DASH = {
  DIRECT:      null,
  INDIRECT:    '8 4',
  INFERENCE:   '4 4',
  SPECULATION: null,
  _default:    null
}

// ── Certainty badge colours (for panel) ───────────────────────────────────────
export const CERTAINTY_COLOR = {
  DIRECT:      '#2d6a4f',
  INDIRECT:    '#e9c46a',
  INFERENCE:   '#f4a261',
  SPECULATION: '#e63946',
  _default:    '#aaa'
}

// ── Site marker config ─────────────────────────────────────────────────────────
export const SITE_ROLE = {
  primary_camp: { label: 'Primary camp', symbol: '★', css: 'role-primary' },
  island_site:  { label: 'Island site',  symbol: '◉', css: 'role-island'  },
  shore_camp:   { label: 'Shore camp',   symbol: '▲', css: 'role-shore'   },
  find_scatter: { label: 'Find scatter', symbol: '●', css: 'role-scatter' },
  _default:     { label: 'Site',         symbol: '●', css: 'role-scatter' }
}

// ── Terrain subtype fill colours (for terrain-subtype color mode) ─────────────
export const TERRAIN_SUBTYPE_COLOR = {
  tst_001: '#1d6f9a',  // Glacial lake basin
  tst_002: '#38bdf8',  // Floodplain / River valley
  tst_003: '#b8956a',  // Limestone plateau
  tst_004: '#4d7c3f',  // Fenland / Wetland
  tst_005: '#c8b84a',  // Chalk Wold
  tst_006: '#166534',  // Upland peat basin
  tst_007: '#0d9488',  // Rocky coast
  tst_008: '#78350f',  // Estuary / mudflat
  _default: '#6b7280'
}

export const TERRAIN_SUBTYPE_LABEL = {
  tst_001: 'Glacial lake basin',
  tst_002: 'Floodplain',
  tst_003: 'Limestone plateau',
  tst_004: 'Fenland / Wetland',
  tst_005: 'Chalk Wold',
  tst_006: 'Upland peat basin',
  tst_007: 'Rocky coast',
  tst_008: 'Estuary / mudflat'
}

// ── Ecotone edge-effect colour scale ─────────────────────────────────────────
export function ecotoneColor(factor) {
  // factor 1.0–1.3 → yellow, 1.3–1.6 → orange, 1.6+ → red
  if (factor >= 1.6) return '#e63946'
  if (factor >= 1.3) return '#f4a261'
  return '#e9c46a'
}

// ── Supabase connection ────────────────────────────────────────────────────────
export const SUPABASE_URL     = import.meta.env.VITE_SUPABASE_URL
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY

// ── Region detection ─────────────────────────────────────────────────────────
// CZ mode: uses same Supabase DB as Yorkshire — bbox-based queries return CZ data
export const REGION = 'cz'
export const STATIC_MODE = !SUPABASE_URL  // fallback to static if no Supabase configured

// ── Map defaults ───────────────────────────────────────────────────────────────
export const MAP_CENTER = [49.08, 14.73]  // Třeboňsko (Švarcenberk)
export const MAP_ZOOM   = 11
export const RIVERS_MIN_ZOOM   = 10
export const ECOTONES_MIN_ZOOM = 10

// ── Biotope fill colours ───────────────────────────────────────────────────────
export const BIOTOPE_COLOR = {
  // CZ biotopes (Třeboňsko ~7000 BCE)
  bt_cz_001: '#5B8C5A',  // Bor na krystaliku (pine-birch on bedrock)
  bt_cz_002: '#2D6A4F',  // Smíšený les na pískovci (pine-oak)
  bt_cz_003: '#7FB069',  // Vlhký les na jílovci (wet alder)
  bt_cz_004: '#A3BE8C',  // Mokřadní olšina (alder carr)
  bt_cz_005: '#8B6914',  // Habrový les na terase (hornbeam-oak)
  bt_cz_006: '#52B788',  // Lužní les (floodplain elm-ash)
  bt_cz_007: '#D4A373',  // Borový bor na píscích (pine on sand)
  bt_cz_008: '#8B5E3C',  // Rašelinný bor (peat bog)
  bt_cz_009: '#4A90D9',  // Otevřené jezero (paleolake)
  bt_cz_010: '#38A169',  // Říční lužní les (riparian)
  bt_cz_011: '#95D5B2',  // Lesní palouk (forest glade)
  // Yorkshire biotopes (kept for compatibility)
  bt_001: '#4A90D9', bt_002: '#7FB069', bt_003: '#2D6A4F',
  bt_004: '#E9C46A', bt_005: '#F4A261', bt_006: '#D4A373',
  bt_007: '#52B788', bt_008: '#ADB5BD', bt_009: '#95D5B2',
  bt_010: '#F2CC8F', bt_011: '#A8DADC',
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
  // CZ terrain subtypes
  tst_cz_001: '#8B7D6B',  // Crystalline basement
  tst_cz_002: '#C4A35A',  // Cretaceous sandstone
  tst_cz_003: '#9E8E7E',  // Cretaceous claystone
  tst_cz_004: '#6B8E23',  // Neogene lacustrine
  tst_cz_005: '#D2B48C',  // River terrace
  tst_cz_006: '#7CB342',  // Floodplain
  tst_cz_007: '#F5DEB3',  // Aeolian sand
  tst_cz_008: '#654321',  // Peat
  tst_cz_009: '#4682B4',  // Paleolake
  tst_cz_010: '#4A90D9',  // River
  // Yorkshire (kept for compat)
  tst_001: '#1d6f9a', tst_002: '#38bdf8', tst_003: '#b8956a',
  tst_004: '#4d7c3f', tst_005: '#c8b84a', tst_006: '#166534',
  tst_007: '#0d9488', tst_008: '#78350f',
  _default: '#6b7280'
}

export const TERRAIN_SUBTYPE_LABEL = {
  tst_cz_001: 'Krystalické podloží',
  tst_cz_002: 'Pískovcová plošina',
  tst_cz_003: 'Jílovcová deprese',
  tst_cz_004: 'Neogenní sedimenty',
  tst_cz_005: 'Říční terasa',
  tst_cz_006: 'Říční niva',
  tst_cz_007: 'Eolický písek',
  tst_cz_008: 'Rašeliniště',
  tst_cz_009: 'Jezerní pánev',
  tst_cz_010: 'Řeka',
  // Yorkshire
  tst_001: 'Glacial lake basin', tst_002: 'Floodplain',
  tst_003: 'Limestone plateau', tst_004: 'Fenland / Wetland',
  tst_005: 'Chalk Wold', tst_006: 'Upland peat basin',
  tst_007: 'Rocky coast', tst_008: 'Estuary / mudflat'
}

// ── Ecotone edge-effect colour scale ─────────────────────────────────────────
export function ecotoneColor(factor) {
  // factor 1.0–1.3 → yellow, 1.3–1.6 → orange, 1.6+ → red
  if (factor >= 1.6) return '#e63946'
  if (factor >= 1.3) return '#f4a261'
  return '#e9c46a'
}

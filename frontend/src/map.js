import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import {
  MAP_CENTER, MAP_ZOOM,
  BIOTOPE_COLOR, TERRAIN_SUBTYPE_COLOR, TERRAIN_SUBTYPE_LABEL,
  CERTAINTY_COLOR, CERTAINTY_OPACITY, CERTAINTY_DASH, SITE_ROLE
} from './config.js'

// ── Legend state ──────────────────────────────────────────────────────────────
let _legendEl          = null
let _visBiotopes       = null   // Set<string> | null (null = show all)
let _visSiteRoles      = null   // Set<string> | null
let _visTerrainSubtypes = null  // Set<string> | null
let _colorMode         = 'biotope'  // 'biotope' | 'subtype'

// ── Basemap state ─────────────────────────────────────────────────────────────
let _currentBasemap = null

const BASEMAP_DEFS = {
  osm: {
    url:  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    opts: { attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 18 }
  },
  relief: {
    url:  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}',
    opts: { attribution: '© Esri, USGS, NOAA', maxZoom: 13 }
  },
  blank: null   // no tile layer — CSS background shows
}

// ── Init ──────────────────────────────────────────────────────────────────────

export function initMap() {
  const map = L.map('map', {
    center: MAP_CENTER,
    zoom:   MAP_ZOOM,
    zoomControl: true
  })

  const def = BASEMAP_DEFS.osm
  _currentBasemap = L.tileLayer(def.url, def.opts).addTo(map)

  L.control.scale({ position: 'bottomleft', imperial: true, metric: true }).addTo(map)

  map.on('mousemove', (e) => {
    const el = document.getElementById('coords')
    if (el) el.textContent = `${e.latlng.lat.toFixed(4)}°N  ${e.latlng.lng.toFixed(4)}°E`
  })
  map.on('mouseout', () => {
    const el = document.getElementById('coords')
    if (el) el.textContent = 'Move cursor over map'
  })

  const updateZoom = () => {
    const el = document.getElementById('zoom-display')
    if (el) el.textContent = `Zoom: ${map.getZoom()}`
  }
  map.on('zoomend', updateZoom)
  updateZoom()

  addLegend(map)
  return map
}

// ── Basemap switcher ──────────────────────────────────────────────────────────

export function setBasemap(name) {
  const map = window._map
  if (!map) return

  if (_currentBasemap) {
    _currentBasemap.remove()
    _currentBasemap = null
  }

  const def = BASEMAP_DEFS[name]
  if (def) {
    _currentBasemap = L.tileLayer(def.url, def.opts).addTo(map)
    _currentBasemap.bringToBack()
  }

  // For blank map use a warm parchment bg so polygons are legible
  document.getElementById('map').style.background =
    name === 'blank' ? '#f0ebe0' : ''
}

// ── Dynamic legend ────────────────────────────────────────────────────────────

// biotopes/siteRoles/terrainSubtypes:
//   null           → show all (initial state / reset)
//   []  (empty)    → show none (layer hidden)
//   ['bt_001',...] → show only those
// colorMode: 'biotope' | 'subtype' — which legend section to render for terrain
export function updateLegend({ biotopes, siteRoles, terrainSubtypes, colorMode } = {}) {
  if (colorMode !== undefined)       _colorMode          = colorMode
  if (biotopes !== undefined)        _visBiotopes        = biotopes        !== null ? new Set(biotopes)        : null
  if (siteRoles !== undefined)       _visSiteRoles       = siteRoles       !== null ? new Set(siteRoles)       : null
  if (terrainSubtypes !== undefined) _visTerrainSubtypes = terrainSubtypes !== null ? new Set(terrainSubtypes) : null
  if (_legendEl) _renderLegend()
}

function addLegend(map) {
  const legend = L.control({ position: 'bottomright' })

  legend.onAdd = () => {
    const div = L.DomUtil.create('div', 'map-legend')
    _legendEl = div
    _renderLegend()
    L.DomEvent.disableClickPropagation(div)
    L.DomEvent.disableScrollPropagation(div)
    return div
  }

  legend.addTo(map)
}

function _renderLegend() {
  const allBiotopes       = new Set(Object.keys(BIOTOPE_COLOR).filter(k => k !== '_default'))
  const allSiteRoles      = new Set(Object.keys(SITE_ROLE).filter(k => k !== '_default'))
  const allTerrainSubtypes = new Set(Object.keys(TERRAIN_SUBTYPE_COLOR).filter(k => k !== '_default'))

  const siteRoles = _visSiteRoles ?? allSiteRoles

  let terrainSection
  if (_colorMode === 'subtype') {
    const subtypes = _visTerrainSubtypes ?? allTerrainSubtypes
    terrainSection = subtypes.size > 0
      ? `<div class="legend-title">Terrain types</div>${terrainSubtypeLegendRows(subtypes)}`
      : ''
  } else {
    const biotopes = _visBiotopes ?? allBiotopes
    terrainSection = biotopes.size > 0
      ? `<div class="legend-title">Biotopes</div>${biotopeLegendRows(biotopes)}`
      : ''
  }

  _legendEl.innerHTML = `
    ${terrainSection}
    ${terrainSection ? '<div class="legend-divider"></div>' : ''}
    <div class="legend-title">Certainty</div>
    ${certaintyLegendRows()}
    ${siteRoles.size > 0 ? `
    <div class="legend-divider"></div>
    <div class="legend-title">Sites</div>
    ${siteLegendRows(siteRoles)}` : ''}
  `
}

// ── Legend row renderers ───────────────────────────────────────────────────────

const BIOTOPE_LABELS = {
  bt_001: 'Lake',
  bt_002: 'Wetland',
  bt_003: 'Boreal forest',
  bt_004: 'Open upland',
  bt_005: 'Coastal saltmarsh',
  bt_006: 'Chalk scrub',
  bt_007: 'Riparian forest',
  bt_008: 'Intertidal',
  bt_009: 'Forest glade',
  bt_010: 'Post-fire grassland',
  bt_011: 'Drought wetland'
}

function terrainSubtypeLegendRows(visibleSet) {
  return Object.entries(TERRAIN_SUBTYPE_LABEL)
    .filter(([id]) => visibleSet.has(id))
    .map(([id, label]) =>
      `<div class="legend-row">
        <span class="legend-swatch" style="background:${TERRAIN_SUBTYPE_COLOR[id]}"></span>
        <span>${label}</span>
      </div>`
    ).join('')
}

function biotopeLegendRows(visibleSet) {
  return Object.entries(BIOTOPE_LABELS)
    .filter(([id]) => visibleSet.has(id))
    .map(([id, label]) =>
      `<div class="legend-row">
        <span class="legend-swatch" style="background:${BIOTOPE_COLOR[id]}"></span>
        <span>${label}</span>
      </div>`
    ).join('')
}

// Certainty → legend line style (must match CERT_BORDER in layers.js)
const CERT_LEGEND = {
  DIRECT:      { color: '#ffffff', style: 'solid' },
  INDIRECT:    { color: '#e9c46a', style: 'dashed' },
  INFERENCE:   { color: '#f4a261', style: 'dotted' },
  SPECULATION: { color: '#e63946', style: 'solid' }
}

function certaintyLegendRows() {
  return ['DIRECT', 'INDIRECT', 'INFERENCE', 'SPECULATION'].map(cert => {
    const { color, style } = CERT_LEGEND[cert]
    return `<div class="legend-row">
      <span class="legend-cert" style="
        border-top-style:${style};
        border-top-color:${color};
        border-top-width:2px;
        opacity:${CERTAINTY_OPACITY[cert] ?? 0.85}
      "></span>
      <span>${certLabel(cert)}</span>
    </div>`
  }).join('')
}

function certLabel(cert) {
  return { DIRECT: 'Direct evidence', INDIRECT: 'Indirect evidence', INFERENCE: 'Inference', SPECULATION: 'Speculation' }[cert] ?? cert
}

function siteLegendRows(visibleSet) {
  return Object.entries(SITE_ROLE)
    .filter(([k]) => k !== '_default' && visibleSet.has(k))
    .map(([, v]) =>
      `<div class="legend-row">
        <span class="legend-site-symbol ${v.css}">${v.symbol}</span>
        <span>${v.label}</span>
      </div>`
    ).join('')
}

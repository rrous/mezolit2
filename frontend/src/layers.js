import L from 'leaflet'
import {
  BIOTOPE_COLOR, TERRAIN_SUBTYPE_COLOR,
  CERTAINTY_OPACITY, CERTAINTY_DASH,
  ecotoneColor, SITE_ROLE, RIVERS_MIN_ZOOM, ECOTONES_MIN_ZOOM
} from './config.js'
import { fetchTerrain, fetchRivers, fetchEcotones, fetchCoastline, fetchSites } from './api.js'
import { openPanel } from './panel.js'
import { updateLegend } from './map.js'

// ── Layer groups ──────────────────────────────────────────────────────────────

export const layerGroups = {
  coastline: L.layerGroup(),
  terrain:   L.layerGroup(),
  ecotones:  L.layerGroup(),
  rivers:    L.layerGroup(),
  sites:     L.layerGroup()
}

// Current season (null = all)
let currentSeason = null

// Current terrain color mode: 'biotope' | 'subtype'
let currentColorMode = 'biotope'

// Whether ecotones are currently visible — drives terrain border style
let _ecotonessVisible = true

// Certainty → polygon border when ecotones are OFF (certainty mode)
const CERT_BORDER = {
  DIRECT:      { color: '#ffffff', weight: 2.5, opacity: 0.95 },
  INDIRECT:    { color: '#e9c46a', weight: 2,   opacity: 0.90 },
  INFERENCE:   { color: '#f4a261', weight: 2,   opacity: 0.85 },
  SPECULATION: { color: '#e63946', weight: 2,   opacity: 0.80 },
  _default:    { color: 'rgba(255,255,255,0.4)', weight: 1,   opacity: 0.6 }
}
// Subtle border when ecotones are ON (polygon separation only, no distraction)
const BORDER_SUBTLE = { color: 'rgba(255,255,255,0.2)', weight: 0.5, opacity: 0.4 }

// Debounce handle for viewport changes
let _refreshTimer = null

// ── Hover info (static status bar text, no floating tooltip) ──────────────────

function setHoverInfo(html) {
  const el = document.getElementById('hover-name')
  if (el) el.innerHTML = html
}

function clearHoverInfo() {
  const el = document.getElementById('hover-name')
  if (el) el.innerHTML = ''
}

// ── Init ──────────────────────────────────────────────────────────────────────

export async function initLayers(map) {
  // Z-order: coastline → terrain → rivers → sites → ecotones (on top of everything)
  layerGroups.coastline.addTo(map)
  layerGroups.terrain.addTo(map)
  layerGroups.rivers.addTo(map)
  layerGroups.sites.addTo(map)
  layerGroups.ecotones.addTo(map)

  setLoading(true)
  try {
    await Promise.all([
      loadCoastline(),
      loadSites()
    ])
    await refreshDynamic(map)
  } finally {
    setLoading(false)
  }

  map.on('moveend zoomend', () => {
    clearTimeout(_refreshTimer)
    _refreshTimer = setTimeout(() => refreshDynamic(map), 400)
  })
}

// ── Dynamic layers (terrain + rivers + ecotones) ──────────────────────────────

async function refreshDynamic(map) {
  const bounds = map.getBounds()
  const west  = bounds.getWest()
  const south = bounds.getSouth()
  const east  = bounds.getEast()
  const north = bounds.getNorth()
  const zoom  = map.getZoom()

  setLoading(true)
  try {
    await Promise.all([
      loadTerrain(west, south, east, north, zoom),
      zoom >= ECOTONES_MIN_ZOOM
        ? loadEcotones(west, south, east, north)
        : Promise.resolve(layerGroups.ecotones.clearLayers()),
      zoom >= RIVERS_MIN_ZOOM
        ? loadRivers(west, south, east, north, zoom)
        : Promise.resolve(layerGroups.rivers.clearLayers())
    ])
  } finally {
    setLoading(false)
  }
}

export function forceRefresh(map) {
  return refreshDynamic(map)
}

// ── Layer loaders ─────────────────────────────────────────────────────────────

async function loadCoastline() {
  const fc = await fetchCoastline()
  layerGroups.coastline.clearLayers()
  if (!fc?.features?.length) return

  L.geoJSON(fc, {
    style: {
      fillColor:   '#b0c4de',
      fillOpacity: 0.35,
      color:       '#6699bb',
      weight:      1.5,
      dashArray:   '6 3'
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties
      layer.on('mouseover', () => setHoverInfo(
        `<strong>Reconstructed coastline</strong>`
        + ` <span class="hi-sub">· Sea level: ${p.sea_level_offset_m} m</span>`
        + ` ${certBadge(p.certainty)}`
      ))
      layer.on('mouseout', clearHoverInfo)
    }
  }).addTo(layerGroups.coastline)
}

async function loadTerrain(west, south, east, north, zoom) {
  const fc = await fetchTerrain(west, south, east, north, zoom)
  layerGroups.terrain.clearLayers()
  if (!fc?.features?.length) return

  // Sort glades (bt_009) to end → rendered last → on top → intercepts clicks
  fc.features.sort((a, b) => {
    const aGlade = a.properties.biotope_id === 'bt_009' ? 1 : 0
    const bGlade = b.properties.biotope_id === 'bt_009' ? 1 : 0
    return aGlade - bGlade
  })

  L.geoJSON(fc, {
    style: (feature) => terrainStyle(feature.properties, currentSeason),
    onEachFeature: (feature, layer) => {
      const p = feature.properties
      attachTerrainHandlers(layer, p)
    }
  }).addTo(layerGroups.terrain)

  if (currentColorMode === 'subtype') {
    const visibleSubtypes = [...new Set(fc.features.map(f => f.properties.terrain_subtype_id).filter(Boolean))]
    updateLegend({ colorMode: 'subtype', terrainSubtypes: visibleSubtypes })
  } else {
    const visibleBiotopes = [...new Set(fc.features.map(f => f.properties.biotope_id).filter(Boolean))]
    updateLegend({ colorMode: 'biotope', biotopes: visibleBiotopes })
  }
}

async function loadRivers(west, south, east, north, zoom) {
  const fc = await fetchRivers(west, south, east, north, zoom)
  layerGroups.rivers.clearLayers()
  if (!fc?.features?.length) return

  L.geoJSON(fc, {
    style: (feature) => {
      const p = feature.properties
      const opacity = CERTAINTY_OPACITY[p.certainty] ?? 0.6
      return {
        color:     '#4A90D9',
        weight:    p.permanence === 'permanent' ? 1.5 : 0.8,
        opacity:   opacity,
        dashArray: p.permanence === 'seasonal' ? '4 3' : null
      }
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties
      layer.on('mouseover', () => setHoverInfo(
        `<strong>River${p.name ? ': ' + p.name : ''}</strong>`
        + ` <span class="hi-sub">· ${p.permanence ?? ''}</span>`
        + ` ${certBadge(p.certainty)}`
      ))
      layer.on('mouseout', clearHoverInfo)
    }
  }).addTo(layerGroups.rivers)
}

async function loadEcotones(west, south, east, north) {
  const fc = await fetchEcotones(west, south, east, north)
  layerGroups.ecotones.clearLayers()
  if (!fc?.features?.length) return

  L.geoJSON(fc, {
    style: (feature) => {
      const p = feature.properties
      const col = ecotoneColor(p.edge_effect_factor ?? 1.2)
      return { color: col, weight: 3, opacity: 0.85, dashArray: '10 5' }
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties
      layer.on('mouseover', () => setHoverInfo(
        `<strong>${p.name ?? 'Ecotone'}</strong>`
        + ` <span class="hi-sub">· ${p.biotope_a_name ?? ''} / ${p.biotope_b_name ?? ''}`
        + ` · ×${p.edge_effect_factor?.toFixed(1)}</span>`
        + ` ${certBadge(p.certainty)}`
      ))
      layer.on('mouseout', clearHoverInfo)
      layer.on('click', (e) => {
        L.DomEvent.stopPropagation(e)
        openPanel({ type: 'ecotone', props: p })
      })
    }
  }).addTo(layerGroups.ecotones)
}

async function loadSites() {
  const fc = await fetchSites()
  layerGroups.sites.clearLayers()
  if (!fc?.features?.length) return

  L.geoJSON(fc, {
    pointToLayer: (feature, latlng) => {
      const role = feature.properties.lakescape_role
      return L.marker(latlng, { icon: siteIcon(role) })
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties
      const roleInfo = SITE_ROLE[p.lakescape_role] ?? SITE_ROLE._default
      const label = p.name || p.ident_cely || p.katastr || 'Site'
      layer.bindTooltip(
        `<strong>${label}</strong><br>${roleInfo.label} ${certBadge(p.certainty)}`,
        { sticky: false, direction: 'top', offset: [0, -12] }
      )
      layer.on('click', (e) => {
        L.DomEvent.stopPropagation(e)
        openPanel({ type: 'site', props: p })
      })
    }
  }).addTo(layerGroups.sites)

  const visibleRoles = [...new Set(fc.features.map(f => f.properties.lakescape_role).filter(Boolean))]
  updateLegend({ siteRoles: visibleRoles })
}

// ── Season update ─────────────────────────────────────────────────────────────

export function setSeason(season) {
  currentSeason = season || null
  _restyleTerrainLayers()
}

export function setEcotonesVisible(visible) {
  _ecotonessVisible = visible
  _restyleTerrainLayers()
}

export function setTerrainColorMode(mode) {
  currentColorMode = mode
  _restyleTerrainLayers()
  // Rebuild legend from currently displayed features
  const features = []
  layerGroups.terrain.eachLayer(g => {
    if (typeof g.eachLayer === 'function') {
      g.eachLayer(l => { if (l.feature) features.push(l.feature) })
    }
  })
  if (mode === 'subtype') {
    const visibleSubtypes = [...new Set(features.map(f => f.properties.terrain_subtype_id).filter(Boolean))]
    updateLegend({ colorMode: 'subtype', terrainSubtypes: visibleSubtypes })
  } else {
    const visibleBiotopes = [...new Set(features.map(f => f.properties.biotope_id).filter(Boolean))]
    updateLegend({ colorMode: 'biotope', biotopes: visibleBiotopes })
  }
}

function _restyleTerrainLayers() {
  // layerGroups.terrain is a LayerGroup whose single child is a L.geoJSON FeatureGroup.
  // We must iterate one level deeper to reach individual polygon layers.
  layerGroups.terrain.eachLayer(geoJsonGroup => {
    if (typeof geoJsonGroup.eachLayer === 'function') {
      geoJsonGroup.eachLayer(layer => {
        if (layer.setStyle && layer.feature) {
          layer.setStyle(terrainStyle(layer.feature.properties, currentSeason))
        }
      })
    }
  })
}

// ── Styling helpers ───────────────────────────────────────────────────────────

function terrainStyle(props, season) {
  const color = currentColorMode === 'subtype'
    ? (TERRAIN_SUBTYPE_COLOR[props.terrain_subtype_id] ?? TERRAIN_SUBTYPE_COLOR._default)
    : (BIOTOPE_COLOR[props.biotope_id] ?? BIOTOPE_COLOR._default)
  const baseOpacity = CERTAINTY_OPACITY[props.certainty] ?? CERTAINTY_OPACITY._default

  let fillOpacity = baseOpacity
  if (season) {
    const mod = props[`seasonal_${season}`] ?? 1.0
    fillOpacity = Math.min(0.95, Math.max(0.10, baseOpacity * mod))
  }

  // When ecotones are visible: subtle separator only (ecotone lines carry the scientific info)
  // When ecotones are hidden: full colored certainty borders
  const border = _ecotonessVisible
    ? BORDER_SUBTLE
    : (CERT_BORDER[props.certainty] ?? CERT_BORDER._default)
  return {
    fillColor:   color,
    fillOpacity: fillOpacity,
    color:       border.color,
    weight:      border.weight,
    opacity:     border.opacity,
    dashArray:   _ecotonessVisible ? null : (CERTAINTY_DASH[props.certainty] ?? null)
  }
}

// Builds one-line HTML for the hover info bar
function buildTerrainHoverText(props) {
  const name    = props.biotope_name ?? props.subtype_name ?? props.terrain_subtype_id
  const subtype = props.biotope_name && props.subtype_name
    ? ` <span class="hi-sub">· ${props.subtype_name}</span>`
    : ''

  let seasonStr = ''
  if (currentSeason) {
    const mod = props[`seasonal_${currentSeason}`] ?? 1.0
    const pct = Math.round(mod * 100)
    const lbl = currentSeason.charAt(0).toUpperCase() + currentSeason.slice(1)
    seasonStr = ` <span class="hi-season">[${lbl}: ${pct}%]</span>`
  }

  return `<strong>${name}</strong>${subtype}${seasonStr} ${certBadge(props.certainty)}`
}

function attachTerrainHandlers(layer, props) {
  layer.on('mouseover', () => setHoverInfo(buildTerrainHoverText(props)))
  layer.on('mouseout',  clearHoverInfo)
  layer.on('click', (e) => {
    L.DomEvent.stopPropagation(e)
    openPanel({ type: 'terrain', props })
  })
}

// ── Site marker icons ─────────────────────────────────────────────────────────

function siteIcon(role) {
  const cfg = SITE_ROLE[role] ?? SITE_ROLE._default
  return L.divIcon({
    html:       `<div class="site-icon ${cfg.css}">${cfg.symbol}</div>`,
    iconSize:   [26, 26],
    iconAnchor: [13, 13],
    className:  ''
  })
}

// ── Utility ───────────────────────────────────────────────────────────────────

function certBadge(cert) {
  return cert
    ? `<span class="tt-cert cert-${cert}">${cert}</span>`
    : ''
}

function setLoading(on) {
  const el = document.getElementById('loading-indicator')
  if (el) el.hidden = !on
}

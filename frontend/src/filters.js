// ── Filters: season buttons + ecotone toggle + basemap + URL hash state ───────

import { setSeason, layerGroups, setTerrainColorMode, setEcotonesVisible } from './layers.js'
import { setBasemap }                                  from './map.js'

export function initFilters(map) {
  initSeasonButtons()
  initColorModeButtons()
  initEcotoneToggle()
  initBasemapButtons()
  initInfoModal()
  initFullscreen()
  restoreFromHash(map)
  map.on('moveend zoomend', () => saveToHash(map))
}

// ── Season buttons ────────────────────────────────────────────────────────────

function initSeasonButtons() {
  document.querySelectorAll('.season-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.season-btn').forEach(b => b.classList.remove('active'))
      btn.classList.add('active')
      setSeason(btn.dataset.season)
      saveSeasonToHash()
    })
  })
}

// ── Ecotone toggle ────────────────────────────────────────────────────────────

function initEcotoneToggle() {
  const btn = document.getElementById('ecotone-toggle')
  if (!btn) return
  btn.addEventListener('click', () => {
    const nowActive = btn.classList.toggle('active')
    setEcotonesVisible(nowActive)
    if (nowActive) {
      layerGroups.ecotones.addTo(window._map)
      window._map.fire('moveend')  // reload data for current viewport
    } else {
      layerGroups.ecotones.remove()
    }
  })
}

// ── Terrain color mode buttons ────────────────────────────────────────────────

function initColorModeButtons() {
  document.querySelectorAll('.color-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('active'))
      btn.classList.add('active')
      setTerrainColorMode(btn.dataset.color)
    })
  })
}

// ── Basemap buttons ───────────────────────────────────────────────────────────

function initBasemapButtons() {
  document.querySelectorAll('.basemap-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.basemap-btn').forEach(b => b.classList.remove('active'))
      btn.classList.add('active')
      setBasemap(btn.dataset.basemap)
    })
  })
}

// ── Info modal ────────────────────────────────────────────────────────────────

function initInfoModal() {
  const modal = document.getElementById('info-modal')
  document.getElementById('info-btn').addEventListener('click', () => modal.showModal())
}

// ── Fullscreen ────────────────────────────────────────────────────────────────

function initFullscreen() {
  document.getElementById('fullscreen-btn').addEventListener('click', () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {})
    } else {
      document.exitFullscreen()
    }
  })

  document.addEventListener('fullscreenchange', () => {
    const btn = document.getElementById('fullscreen-btn')
    btn.title   = document.fullscreenElement ? 'Exit fullscreen' : 'Fullscreen'
    btn.textContent = document.fullscreenElement ? '⊡' : '⛶'
  })
}

// ── URL hash state: lat/lon/zoom/season ───────────────────────────────────────
// Format: #54.1/-1.2/8/summer

function saveToHash(map) {
  const { lat, lng } = map.getCenter()
  const zoom   = map.getZoom()
  const season = getActiveSeason()
  window.location.hash = `${lat.toFixed(4)}/${lng.toFixed(4)}/${zoom}${season ? '/' + season : ''}`
}

function saveSeasonToHash() {
  if (window._map) saveToHash(window._map)
}

function restoreFromHash(map) {
  const hash = window.location.hash.replace('#', '')
  if (!hash) return

  const parts = hash.split('/')
  if (parts.length >= 3) {
    const lat  = parseFloat(parts[0])
    const lng  = parseFloat(parts[1])
    const zoom = parseInt(parts[2])
    if (!isNaN(lat) && !isNaN(lng) && !isNaN(zoom)) {
      map.setView([lat, lng], zoom, { animate: false })
    }
  }
  if (parts[3]) {
    const btn = document.querySelector(`.season-btn[data-season="${parts[3]}"]`)
    if (btn) btn.click()
  }
}

function getActiveSeason() {
  const active = document.querySelector('.season-btn.active')
  return active ? active.dataset.season : ''
}

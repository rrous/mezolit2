// ── Side panel ────────────────────────────────────────────────────────────────
// Renders detail for terrain features, ecotones, and archaeological sites.

import { CERTAINTY_COLOR, SITE_ROLE, BIOTOPE_COLOR } from './config.js'

const panel    = () => document.getElementById('panel')
const panelTitle = () => document.getElementById('panel-title')
const panelBody  = () => document.getElementById('panel-body')

export function initPanel() {
  document.getElementById('panel-close').addEventListener('click', closePanel)
}

export function openPanel({ type, props }) {
  panelTitle().textContent = props.name ?? props.subtype_name ?? 'Detail'

  let html = ''
  if (type === 'terrain')  html = renderTerrain(props)
  if (type === 'ecotone')  html = renderEcotone(props)
  if (type === 'site')     html = renderSite(props)

  panelBody().innerHTML = html
  panel().hidden = false
}

export function closePanel() {
  panel().hidden = true
  panelBody().innerHTML = ''
}

// ── Terrain ───────────────────────────────────────────────────────────────────

function renderTerrain(p) {
  const biotopeSwatch = p.biotope_id
    ? `<span class="swatch" style="background:${BIOTOPE_COLOR[p.biotope_id] ?? '#ccc'}"></span>`
    : ''

  return `
    <section class="panel-section">
      <h4>Terrain subtype</h4>
      <p class="panel-id">${p.terrain_subtype_id}</p>
      <p>${p.description ?? ''}</p>
    </section>

    ${p.biotope_name ? `
    <section class="panel-section">
      <h4>Dominant biotope</h4>
      <div class="panel-row">${biotopeSwatch} <strong>${p.biotope_name}</strong></div>
      ${p.productivity_kcal
        ? `<div class="panel-row">Productivity: <strong>${fmtKcal(p.productivity_kcal)}</strong></div>`
        : `<div class="panel-row">Productivity class: <strong>${p.productivity_class ?? '—'}</strong></div>`
      }
      <div class="panel-row">Trafficability: <strong>${p.trafficability ?? '—'}</strong>
        ${p.energy_multiplier ? ` (energy ×${p.energy_multiplier})` : ''}</div>
    </section>` : ''}

    <section class="panel-section">
      <h4>Terrain</h4>
      ${p.elevation_min_m != null
        ? `<div class="panel-row">Elevation: <strong>${p.elevation_min_m}–${p.elevation_max_m} m</strong></div>`
        : ''}
      ${p.hydrology   ? `<div class="panel-row">Hydrology: <strong>${p.hydrology}</strong></div>` : ''}
      ${p.slope       ? `<div class="panel-row">Slope: <strong>${p.slope}</strong></div>`       : ''}
      ${p.substrate   ? `<div class="panel-row">Substrate: <strong>${p.substrate}</strong></div>` : ''}
      ${p.flint_availability ? `<div class="panel-row">Flint: <strong>${p.flint_availability}</strong></div>` : ''}
      ${p.anchor_site ? `<div class="panel-row anchor-flag">⚓ Anchor site</div>` : ''}
    </section>

    ${renderSeasonTable(p)}

    <section class="panel-section panel-meta">
      <h4>Epistemics</h4>
      <div class="panel-row">${certBadge(p.certainty)}</div>
      ${p.source ? `<div class="panel-row source-text">${p.source}</div>` : ''}
      <div class="panel-row panel-id">${p.id}</div>
    </section>
  `
}

// ── Ecotone ───────────────────────────────────────────────────────────────────

function renderEcotone(p) {
  const peaks = p.seasonal_peaks && typeof p.seasonal_peaks === 'object'
    ? Object.entries(p.seasonal_peaks)
        .map(([s, note]) => `<tr><td>${s}</td><td>${note}</td></tr>`)
        .join('')
    : ''

  return `
    <section class="panel-section">
      <h4>Ecotone transition</h4>
      <div class="panel-row">
        <span class="zone-label">${p.biotope_a_name ?? p.biotope_a_id}</span>
        <span class="zone-sep">⟷</span>
        <span class="zone-label">${p.biotope_b_name ?? p.biotope_b_id}</span>
      </div>
    </section>

    <section class="panel-section">
      <h4>Edge effect</h4>
      <div class="panel-row">Factor: <strong>×${p.edge_effect_factor?.toFixed(2) ?? '—'}</strong></div>
      <div class="panel-row">Human relevance: <strong>${p.human_relevance ?? '—'}</strong></div>
    </section>

    ${peaks ? `
    <section class="panel-section">
      <h4>Seasonal peaks</h4>
      <table class="season-table">
        <thead><tr><th>Season</th><th>Activity</th></tr></thead>
        <tbody>${peaks}</tbody>
      </table>
    </section>` : ''}

    <section class="panel-section panel-meta">
      <h4>Epistemics</h4>
      <div class="panel-row">${certBadge(p.certainty)}</div>
      ${p.source ? `<div class="panel-row source-text">${p.source}</div>` : ''}
    </section>
  `
}

// ── Archaeological site ───────────────────────────────────────────────────────

function renderSite(p) {
  const roleInfo = SITE_ROLE[p.lakescape_role] ?? SITE_ROLE._default
  return `
    <section class="panel-section">
      <h4>Archaeological site</h4>
      <div class="panel-row">
        <span class="site-icon-inline ${roleInfo.css}">${roleInfo.symbol}</span>
        <strong>${roleInfo.label}</strong>
      </div>
      <p>Part of the Star Carr / Lake Flixton lakescape complex.</p>
    </section>

    <section class="panel-section panel-meta">
      <h4>Epistemics</h4>
      <div class="panel-row">${certBadge(p.certainty)}</div>
      ${p.source ? `<div class="panel-row source-text">${p.source}</div>` : ''}
      <div class="panel-row panel-id">${p.id}</div>
    </section>
  `
}

// ── Seasonal modifier table ───────────────────────────────────────────────────

function renderSeasonTable(p) {
  const seasons = [
    { key: 'spring', label: 'Spring' },
    { key: 'summer', label: 'Summer' },
    { key: 'autumn', label: 'Autumn' },
    { key: 'winter', label: 'Winter' }
  ]

  const rows = seasons.map(({ key, label }) => {
    const mod  = p[`seasonal_${key}`]
    const note = p[`note_${key}`]
    if (mod == null && !note) return ''
    const arrow = mod == null ? '' : mod >= 1.05 ? ' ▲' : mod <= 0.85 ? ' ▼' : ''
    const cls   = mod == null ? '' : mod >= 1.05 ? 'mod-up' : mod <= 0.85 ? 'mod-down' : ''
    return `<tr>
      <td>${label}</td>
      <td class="${cls}">${mod != null ? mod.toFixed(2) + arrow : '—'}</td>
      <td class="note-col">${note ?? ''}</td>
    </tr>`
  }).filter(Boolean)

  if (!rows.length) return ''

  return `
    <section class="panel-section">
      <h4>Seasonal activity</h4>
      <table class="season-table">
        <thead><tr><th>Season</th><th>Modifier</th><th>Notes</th></tr></thead>
        <tbody>${rows.join('')}</tbody>
      </table>
    </section>
  `
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function certBadge(cert) {
  const col = CERTAINTY_COLOR[cert] ?? CERTAINTY_COLOR._default
  return cert
    ? `<span class="cert-badge" style="background:${col}">${cert}</span>`
    : '—'
}

function fmtKcal(val) {
  return val >= 1_000_000
    ? `${(val / 1_000_000).toFixed(2)} M kcal/km²/yr`
    : `${(val / 1_000).toFixed(0)} k kcal/km²/yr`
}

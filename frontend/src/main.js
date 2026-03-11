import './style.css'
import { initMap }    from './map.js'
import { initLayers } from './layers.js'
import { initPanel }  from './panel.js'
import { initFilters } from './filters.js'

async function boot() {
  const map = initMap()

  // Expose map globally so filters.js can access it for hash saving
  window._map = map

  // Init panel close button
  initPanel()

  // Load data layers
  await initLayers(map)

  // Filters, toggles, URL hash, modals
  initFilters(map)
}

boot().catch(err => {
  console.error('App init failed:', err)
  document.body.innerHTML = `
    <div style="padding:2rem;font-family:monospace;color:#e63946">
      <h2>Failed to load map</h2>
      <pre>${err.message}</pre>
      <p>Check that VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are set in <code>.env</code></p>
    </div>
  `
})

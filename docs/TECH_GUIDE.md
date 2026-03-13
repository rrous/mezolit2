# Mezolit2 — Technical & Deployment Guide

> GitHub repo: **[github.com/rrous/mezolit2](https://github.com/rrous/mezolit2)**
> Branch: `master`
> CZ: Průvodce pro vývojáře, deployment a údržbu.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Repository Structure](#2-repository-structure)
3. [Prerequisites](#3-prerequisites)
4. [Environment Setup](#4-environment-setup)
5. [Database Setup (Supabase)](#5-database-setup-supabase)
6. [Pipeline — Step by Step](#6-pipeline--step-by-step)
7. [Frontend Development](#7-frontend-development)
8. [Verification Scripts](#8-verification-scripts)
9. [Deployment](#9-deployment)
10. [API Reference (Future)](#10-api-reference-future)
11. [Key Config Values](#11-key-config-values)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  LOCAL PIPELINE (Python)                                        │
│                                                                 │
│  data/raw/          pipeline/           data/processed/         │
│  ┌──────────┐       ┌──────────┐        ┌──────────────┐        │
│  │ DEM .tif │──02──►│04_terrain│──────► │terrain.geojson│       │
│  │ GEBCO.nc │──03──►│03_coast  │──────► │coast.geojson  │       │
│  │ rivers   │──04──►│05_kb_rules│─────► │ecotones.json  │       │
│  │ ADS .gml │──02b─►│          │        │sites.geojson  │       │
│  └──────────┘       └──────────┘        └──────────────┘        │
│               kb_data/schema_examples_v04.json ─► 01_seed ─►    │
└──────────────────────────────────────────────────┼──────────────┘
                                                   │ 06_import
                                                   ▼
┌──────────────────────────────────────────────────────────────┐
│  SUPABASE (PostGIS)                                          │
│  terrain_subtypes │ biotopes │ can_host │ ecotones │ rivers  │
│  terrain_features │ coastline │ site_instances               │
│  ─── Spatial indexes (GIST) ───────────────────────────────  │
└─────────────────────────────────────────────────────────────-┘
         │                                    │
         │ Direct PostGIS REST               (future) FastAPI
         ▼                                    ▼
┌──────────────────────────┐        ┌──────────────────┐
│  FRONTEND (Vite + Leaflet)│        │  API (Railway)   │
│  Vercel (auto-deploy)     │        │  FastAPI + CORS  │
│  frontend/src/*.js        │        │  (Milestone 3)   │
└──────────────────────────┘        └──────────────────┘
```

**Stack:**
| Layer | Technology | Hosting |
|-------|-----------|---------|
| Database | Supabase PostGIS (PostgreSQL 15) | Supabase free |
| Pipeline | Python 3.10+ (rasterio, geopandas, shapely) | Local |
| Frontend | Vite 5 + Leaflet 1.9 + Vanilla JS | Vercel (free) |
| API (future) | FastAPI + psycopg2 | Railway ($5/mo) |

---

## 2. Repository Structure

```
mezolit2/
│
├── .env                              ← Local secrets (NOT committed)
├── .env - kopie.example              ← Template — copy to .env
├── vercel.json                       ← Root Vercel config (delegates to frontend/)
├── verify_visual.html                ← Manual visual verification UI
│
├── _Docs/                            ← Design documents (source of truth)
│   ├── mezoliticky_design_plan_v9.md ← Main design (v0.9)
│   ├── poc_design_v02.md             ← PoC technical spec
│   ├── visual_fixes_plan_v01.md      ← Milestone 2 visual fix plan
│   ├── schema_examples_v04.json      ← KB schema (terrain, biotopes, ecotones)
│   └── vocabulary_v02.json           ← Enum definitions
│
├── docs/                             ← THIS DOCUMENTATION
│   ├── SCIENCE_GUIDE.md              ← For scientists & content contributors
│   └── TECH_GUIDE.md                 ← This file
│
├── data/
│   ├── raw/
│   │   ├── dem/yorkshire_cop30.tif   ← Copernicus DEM (download first)
│   │   ├── gebco/*.nc or .tif        ← GEBCO 2023 (download first)
│   │   ├── rivers/oprvrs_gb.gpkg     ← OS Open Rivers (download first)
│   │   └── ads/                      ← ADS Lake Flixton + sites (auto via 02b)
│   │       ├── lake2_wgs84.gml
│   │       └── sites_wgs84.gml
│   └── processed/                    ← Pipeline output (regenerated, safe to delete)
│
├── kb_data/                          ← Knowledge Base reference data
│   ├── schema_examples_v04.json      ← Copy of _Docs version (used by pipeline)
│   └── vocabulary_v02.json
│
├── pipeline/
│   ├── 00_schema.sql                 ← PostGIS DDL (run once in Supabase)
│   ├── 01_seed_kb_data.py            ← Import KB data (terrain_subtypes, biotopes, can_host)
│   ├── 02_download_dem.py            ← Download Copernicus DEM
│   ├── 02_download.md                ← Manual download instructions
│   ├── 02b_download_ads.py           ← Download ADS Lake Flixton + sites
│   ├── 03_coastline.py               ← GEBCO → coastline at -25 m
│   ├── 04_terrain.py                 ← DEM → terrain polygons + rivers
│   ├── 05_kb_rules.py                ← CAN_HOST traversal → biotopes + ecotones
│   ├── 06_import_supabase.py         ← GeoJSON → PostGIS
│   ├── verify_db.py                  ← Database integrity check (9 areas)
│   ├── verify_deep.py                ← Deep verification (P1–P5 issues)
│   └── requirements.txt
│
└── frontend/
    ├── package.json                  ← Vite + Leaflet
    ├── vite.config.js
    ├── index.html
    ├── vercel.json                   ← Frontend Vercel override (framework:null)
    └── src/
        ├── main.js                   ← App boot
        ├── map.js                    ← Leaflet map init
        ├── config.js                 ← Colors, constants, enums
        ├── layers.js                 ← Load + render GeoJSON layers
        ├── panel.js                  ← Click panel (feature details)
        ├── filters.js                ← Season/certainty filters + URL hash
        ├── api.js                    ← Supabase REST calls
        └── style.css
```

---

## 3. Prerequisites

### Python (pipeline)

```bash
# Python 3.10+ with GDAL
conda create -n mezolit python=3.10
conda activate mezolit
conda install -c conda-forge gdal rasterio fiona geopandas shapely psycopg2

# Or pip (GDAL must be system-installed separately on Windows)
pip install -r pipeline/requirements.txt
```

[`pipeline/requirements.txt`](https://github.com/rrous/mezolit2/blob/master/pipeline/requirements.txt):
```
rasterio>=1.3
fiona>=1.9
shapely>=2.0
geopandas>=0.14
numpy>=1.24
psycopg2-binary>=2.9
python-dotenv>=1.0
requests>=2.31
tqdm>=4.64
```

### Node.js (frontend)

```bash
# Node.js 18+ required
node --version  # should be 18+
cd frontend
npm install     # installs Vite + Leaflet
```

### External services

- **Supabase** account — create project at supabase.com, enable PostGIS extension
- **Vercel** account — connect to GitHub repo for auto-deploy
- **OpenTopography API key** — for `02_download_dem.py` (free registration)

---

## 4. Environment Setup

Copy the template:
```bash
cp ".env - kopie.example" .env
```

Fill in `.env` (root-level, used by pipeline):
```env
# Supabase PostGIS connection
DATABASE_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# Supabase REST (for future API)
SUPABASE_URL=https://[project-ref].supabase.co

# OpenTopography API (for DEM download)
OPENTOPO_API_KEY=your_key_here

# CORS origins (for future FastAPI)
CORS_ORIGINS=https://mesolithic-kb.vercel.app
```

Fill in `frontend/.env` (used by Vite at build time):
```env
VITE_SUPABASE_URL=https://[project-ref].supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key_here
```

> **Security:** Both `.env` files are gitignored. Never commit secrets.
> `DATABASE_URL` uses the postgres **direct** connection string (port 5432), not the pooler.

---

## 5. Database Setup (Supabase)

### One-time setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. In the SQL Editor, enable PostGIS:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```
3. Run the schema DDL:
   ```sql
   -- Paste contents of pipeline/00_schema.sql
   ```

### Schema reference

[`pipeline/00_schema.sql`](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql) — 142 lines total

| Table | Lines | Purpose |
|-------|-------|---------|
| `terrain_subtypes` | [L7–L24](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L7) | KB reference — 10 geological types (no geometry) |
| `terrain_features` | [L27–L37](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L27) | Geometry polygons, FK to terrain_subtypes + biotopes |
| `biotopes` | [L40–L64](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L40) | KB — 11 ecological types (no geometry) |
| `can_host` | [L67–L79](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L67) | M:N link: biotope ↔ terrain_subtype with trigger + quality |
| `ecotones` | [L82–L95](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L82) | Boundary zones (MultiLineString geometry) |
| `rivers` | [L98–L105](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L98) | River network (LineString) |
| `coastline` | [L108–L116](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L108) | Reconstructed ~6200 BCE coastline |
| `site_instances` | [L119–L129](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L119) | Archaeological sites from ADS |
| Spatial indexes | [L132–L141](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L132) | GIST indexes on all geom columns |

### Useful queries

```sql
-- Check terrain_features count and subtype distribution
SELECT t.id, COUNT(f.id) as features
FROM terrain_subtypes t
LEFT JOIN terrain_features f ON f.terrain_subtype_id = t.id
GROUP BY t.id ORDER BY t.id;

-- Check ecotones validity
SELECT id, name, human_relevance, certainty
FROM ecotones ORDER BY id;

-- Spatial query: features in viewport
SELECT id, name, ST_AsGeoJSON(geom) as geometry
FROM terrain_features
WHERE ST_Intersects(geom, ST_MakeEnvelope(-1.5, 54.0, -0.2, 54.5, 4326));
```

---

## 6. Pipeline — Step by Step

Run scripts from the `pipeline/` directory with `.venv` or conda activated.
**Order matters** — each script depends on the previous one's output.

### Step 0: Download raw data

#### 02_download_dem.py — Copernicus DEM
[`pipeline/02_download_dem.py`](https://github.com/rrous/mezolit2/blob/master/pipeline/02_download_dem.py)

```bash
python 02_download_dem.py
# or with explicit API key:
python 02_download_dem.py --api-key YOUR_KEY
```

- **Input:** OpenTopography API, Yorkshire bbox
  - [`L34–L38`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py#L34): YORKSHIRE_BBOX = `{west: -2.5, east: 0.1, south: 53.5, north: 54.7}`
- **Output:** `data/raw/dem/yorkshire_cop30.tif` (30 m GeoTIFF)
- **Manual alternative:** See [`pipeline/02_download.md`](https://github.com/rrous/mezolit2/blob/master/pipeline/02_download.md)

#### 02b_download_ads.py — ADS Lake Flixton + Sites
[`pipeline/02b_download_ads.py`](https://github.com/rrous/mezolit2/blob/master/pipeline/02b_download_ads.py)

```bash
python 02b_download_ads.py
```

- **Input:** ADS archive (doi:10.5284/1041580) — Palmer et al. 2015
- **Output:**
  - `data/raw/ads/lake2_wgs84.gml` — Lake Flixton polygon (234 vertices, ~5.52 km²)
  - `data/raw/ads/sites_wgs84.gml` — 20 archaeological sites
- **Note:** Requires internet. If ADS URL changes, check `02_download.md` for alternatives.

#### GEBCO (manual download)

Download from [gebco.net](https://www.gebco.net/data_and_products/gridded_bathymetry_data/):
- Select region: -5° to 2°E, 50° to 60°N
- Format: GeoTIFF or NetCDF
- Save to: `data/raw/gebco/`

### Step 1: Seed KB data

#### 01_seed_kb_data.py
[`pipeline/01_seed_kb_data.py`](https://github.com/rrous/mezolit2/blob/master/pipeline/01_seed_kb_data.py)

```bash
python 01_seed_kb_data.py
```

- **Input:** `kb_data/schema_examples_v04.json` + `DATABASE_URL`
- **Output:** Populated tables: `terrain_subtypes` (10), `biotopes` (11), `can_host` (~30 edges), `ecotones` (6 — attributes only, geometry added later)
- **Re-runnable:** Script uses `INSERT ... ON CONFLICT DO UPDATE`
- **CZ:** Spustit vždy po změně KB JSON dat

### Step 2: Generate coastline

#### 03_coastline.py
[`pipeline/03_coastline.py`](https://github.com/rrous/mezolit2/blob/master/pipeline/03_coastline.py)

```bash
python 03_coastline.py
```

- **Input:** `data/raw/gebco/` (GEBCO 2023 raster)
- **Output:** `data/processed/coastline_6200bce.geojson`
- **Key logic:** Extract -25 m contour from GEBCO bathymetry → polygonize → classify land (>-25 m) as Mesolithic land area
- **Sea level source:** Shennan et al. 2018 — certainty: INDIRECT

### Step 3: Generate terrain polygons

#### 04_terrain.py — Most complex script
[`pipeline/04_terrain.py`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py)

```bash
python 04_terrain.py
```

- **Input:**
  - `data/raw/dem/*.tif` (Copernicus DEM)
  - `data/raw/ads/lake2_wgs84.gml` (Lake Flixton)
  - `data/raw/rivers/oprvrs_gb.gpkg` (OS Open Rivers)
  - `data/processed/coastline_6200bce.geojson`
- **Output:**
  - `data/processed/terrain_features.geojson`
  - `data/processed/rivers_yorkshire.geojson`
  - `data/processed/sites.geojson` (from ADS sites_wgs84.gml)

**Key constants:**
- [`L35–L38`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py#L35): Yorkshire bbox
- [`L43–L47`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py#L43): Star Carr coordinates (54.214°N, -0.403°W)
- [`L54–L75`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py#L54): Site-to-lakescape-role mapping (20 ADS sites)
- [`L77–L80`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py#L77): Wolds chalk detection parameters

**Classification logic:**

| tst_id | Condition |
|--------|-----------|
| tst_001 | ADS GML boundary (Lake Flixton) |
| tst_002 | elevation < 150 m, slope < 5°, near river |
| tst_003 | elevation 150–500 m, west of -0.8°E |
| tst_004 | slope < 1°, elevation < 50 m, not lake |
| tst_005 | elevation 50–300 m, east of -0.8°E (Wolds escarpment) |
| tst_006 | elevation > 300 m, Pennines |
| tst_007 | coastal clip, steep |
| tst_008 | coastal clip, flat, low elevation |

**Polygon simplification:** `ST_SimplifyPreserveTopology` tolerance ~20 m — natural appearance, no gaps between polygons.

### Step 4: Apply KB rules

#### 05_kb_rules.py
[`pipeline/05_kb_rules.py`](https://github.com/rrous/mezolit2/blob/master/pipeline/05_kb_rules.py)

```bash
python 05_kb_rules.py
```

- **Input:**
  - `data/processed/terrain_features.geojson`
  - `kb_data/schema_examples_v04.json`
- **Output:**
  - `data/processed/terrain_features_with_biotopes.geojson`
  - `data/processed/ecotones.geojson`

**CAN_HOST traversal** ([`L37–L60`](https://github.com/rrous/mezolit2/blob/master/pipeline/05_kb_rules.py#L37)):
```
For each terrain polygon:
  1. Find all biotopes where can_host[].terrain_subtype = this polygon's tst_id
  2. Filter: trigger = "baseline"
  3. Priority: spatial_scale landscape > local > micro
  4. Among same scale: highest quality_modifier wins
  5. Assign dominant biotope_id to polygon
```

**Ecotone generation:** For each shared boundary between two polygons with different `biotope_id` → create MultiLineString ecotone with `edge_effect_factor` from KB.

**Glade features:** Smart-hole algorithm — polygons with interior voids 0.5–5 ha in forested terrain → assigned as `bt_009` (forest glade).

### Step 5: Import to PostGIS

#### 06_import_supabase.py
[`pipeline/06_import_supabase.py`](https://github.com/rrous/mezolit2/blob/master/pipeline/06_import_supabase.py)

```bash
python 06_import_supabase.py
```

- **Input:** All 4 processed GeoJSON files + `DATABASE_URL`
- **Output:** PostGIS tables populated:
  - `terrain_features` — with geometry + biotope_id FK
  - `ecotones` — geometry added to KB rows from step 1
  - `rivers` — river lines
  - `coastline` — reconstructed coastline
  - `site_instances` — 20 archaeological sites

**Key behaviors** ([`L44–L50`](https://github.com/rrous/mezolit2/blob/master/pipeline/06_import_supabase.py#L44)):
- Clears dependent tables before re-import (FK cascade: `DELETE FROM site_instances` first)
- Normalizes MultiPolygon → Polygon for `terrain_features` (schema requires POLYGON)
- Uses `ST_GeomFromGeoJSON()` for geometry insertion

### Full pipeline execution order

```bash
cd pipeline

# One-time: schema + KB seed
# (run 00_schema.sql in Supabase SQL Editor first)
python 01_seed_kb_data.py

# Download raw data (once, ~1-2 GB)
python 02_download_dem.py
python 02b_download_ads.py
# + manually download GEBCO

# Generate geodata
python 03_coastline.py
python 04_terrain.py
python 05_kb_rules.py
python 06_import_supabase.py

# Verify
python verify_db.py
python verify_deep.py
```

---

## 7. Frontend Development

### Start dev server

```bash
cd frontend
npm install          # first time only
npm run dev          # starts on http://localhost:5173
```

Or use the launcher:
```bat
start_frontend.bat
```

### Build for production

```bash
cd frontend
npm run build        # outputs to frontend/dist/
```

### Key source files

| File | Lines | Purpose |
|------|-------|---------|
| [`src/main.js`](https://github.com/rrous/mezolit2/blob/master/frontend/src/main.js) | 33 | App boot: `initMap → initPanel → initLayers → initFilters` |
| [`src/config.js`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js) | 94 | All constants: colors, coordinates, enums |
| [`src/map.js`](https://github.com/rrous/mezolit2/blob/master/frontend/src/map.js) | — | Leaflet init, basemap switcher, legend |
| [`src/layers.js`](https://github.com/rrous/mezolit2/blob/master/frontend/src/layers.js) | — | Layer groups, viewport-based data loading, styling |
| [`src/panel.js`](https://github.com/rrous/mezolit2/blob/master/frontend/src/panel.js) | — | Click panel (right sidebar, full KB record) |
| [`src/filters.js`](https://github.com/rrous/mezolit2/blob/master/frontend/src/filters.js) | — | Season/certainty filters, URL hash persistence |
| [`src/api.js`](https://github.com/rrous/mezolit2/blob/master/frontend/src/api.js) | — | Supabase REST calls (`fetchTerrain`, `fetchRivers`, etc.) |

### Biotope colors
[`frontend/src/config.js L12–L25`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js#L12)

```javascript
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
}
```

### Certainty visual encoding
[`frontend/src/config.js L28–L43`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js#L28)

| Certainty | Opacity | Border style |
|-----------|---------|--------------|
| DIRECT | 0.90 | Solid white |
| INDIRECT | 0.75 | Dashed `'8 4'` |
| INFERENCE | 0.60 | Dotted `'4 4'` |
| SPECULATION | 0.45 | No border |

### Layer visibility thresholds
[`frontend/src/config.js L8–L9`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js#L8)

```javascript
RIVERS_MIN_ZOOM   = 10  // rivers hidden below zoom 10
ECOTONES_MIN_ZOOM = 10  // ecotones hidden below zoom 10
```

### Site markers
[`frontend/src/config.js L55–L61`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js#L55)

| Role | Symbol | CSS class |
|------|--------|-----------|
| primary_camp | ★ | role-primary |
| island_site | ◉ | role-island |
| shore_camp | ▲ | role-shore |
| find_scatter | ● | role-scatter |

### Map center
[`frontend/src/config.js L6–L7`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js#L6)

```javascript
export const MAP_CENTER = [54.1, -1.2]  // centre of Yorkshire
export const MAP_ZOOM   = 8
```

---

## 8. Verification Scripts

### verify_db.py — Database integrity (9 checks)
[`pipeline/verify_db.py`](https://github.com/rrous/mezolit2/blob/master/pipeline/verify_db.py)

```bash
python verify_db.py
```

Checks:
1. terrain_features count + subtype FK validity
2. biotope FK validity in terrain_features
3. can_host graph completeness (each tst_id has ≥1 baseline biotope)
4. Ecotone attributes (no NULL human_relevance)
5. Geometry validity (no self-intersecting polygons)
6. Orphaned nodes (biotopes with no can_host edges)
7. River permanence values against vocabulary
8. Site instances FK validity
9. Coastline presence

### verify_deep.py — P1–P5 deep checks
[`pipeline/verify_deep.py`](https://github.com/rrous/mezolit2/blob/master/pipeline/verify_deep.py)

```bash
python verify_deep.py
```

Checks the 4 known Milestone 2 issues:
- **P1:** Ecotone NULL attributes — expected: 6/6 VALID
- **P2:** Lake Flixton shape — expected: ADS polygon (≥100 vertices, area ~5.5 km²)
- **P5:** Terrain feature holes — expected: max 1 hole per polygon (glades = separate features)
- **Rivers in floodplain:** % of rivers with floodplain buffer coverage

**Expected clean output:**
```
P1 Ecotones: 6/6 VALID ✓
P2 Lake Flixton: ADS polygon, 234 vertices, 5.52 km² ✓
P5 Holes: tf_0384 has 1 hole, 200 glade features (bt_009) ✓
Rivers: Ouse 87% in floodplain, Derwent 79% ✓
```

---

## 9. Deployment

### Frontend → Vercel (auto-deploy)

Connected to GitHub `master` branch — pushes auto-deploy.

**Vercel config** ([root `vercel.json`](https://github.com/rrous/mezolit2/blob/master/vercel.json)):
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "frontend/dist",
  "installCommand": "cd frontend && npm install",
  "framework": null
}
```

**Frontend override** ([`frontend/vercel.json`](https://github.com/rrous/mezolit2/blob/master/frontend/vercel.json)):
- `"framework": null` — prevents Vercel from overriding the build command with Vite preset

**Environment variables** (set in Vercel dashboard):
```
VITE_SUPABASE_URL     = https://[project-ref].supabase.co
VITE_SUPABASE_ANON_KEY = [anon key from Supabase dashboard]
```

> **Important:** Vite only exposes env vars prefixed with `VITE_` to the browser bundle.

### API → Railway (Milestone 3, future)

The FastAPI backend is planned for Milestone 3. When implemented:
```
railway up --detach
```

Required env vars on Railway:
```
DATABASE_URL       = postgresql://... (Supabase direct connection)
CORS_ORIGINS       = https://your-vercel-domain.vercel.app
PORT               = 8000
```

### Supabase — Row Level Security (RLS)

For the PoC, RLS is disabled on spatial tables (read-only public data).
The `anon` key has `SELECT` access only — no write access from frontend.

```sql
-- Verify RLS status
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public';
```

---

## 10. API Reference (Future)

Planned FastAPI endpoints (Milestone 3):

```
GET /api/terrain?bbox={west},{south},{east},{north}
    Returns terrain_features within bbox as GeoJSON FeatureCollection

GET /api/biotope/{id}
    Returns full biotope record with can_host edges

GET /api/ecotones?bbox=...
    Returns ecotone MultiLineStrings within bbox

GET /api/rivers?bbox=...
    Returns river lines (min_zoom=10 enforced server-side)

GET /api/coastline
    Returns coastline MultiPolygon

GET /api/sites
    Returns all 20 archaeological site_instances

GET /health
    Returns {"status": "ok", "version": "1.0"}
```

Spatial queries use PostGIS:
```sql
ST_Intersects(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))
ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, $zoom_tolerance))
```

---

## 11. Key Config Values

| Parameter | Value | Where defined |
|-----------|-------|---------------|
| Yorkshire bbox | W:-2.5, E:0.1, S:53.5, N:54.7 | [`04_terrain.py L35`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py#L35) |
| Star Carr coords | 54.214°N, -0.403°W | [`04_terrain.py L43`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py#L43) |
| Sea level offset | -25 m | [`00_schema.sql L112`](https://github.com/rrous/mezolit2/blob/master/pipeline/00_schema.sql#L112) |
| Wolds longitude boundary | -0.8°E (west limit) | [`04_terrain.py L79`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py#L79) |
| DEM resolution | 30 m (Copernicus GLO-30) | `02_download_dem.py` |
| Polygon simplify tolerance | ~20 m (~0.0002°) | `04_terrain.py` |
| River buffer | 400 m | `04_terrain.py` |
| Glade size range | 0.5–5 ha | `04_terrain.py` |
| Map center | [54.1, -1.2] | [`config.js L6`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js#L6) |
| Default zoom | 8 | [`config.js L7`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js#L7) |
| Rivers min zoom | 10 | [`config.js L8`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js#L8) |
| Ecotones min zoom | 10 | [`config.js L9`](https://github.com/rrous/mezolit2/blob/master/frontend/src/config.js#L9) |
| PostGIS SRID | 4326 (WGS84) | `00_schema.sql` throughout |
| Lake Flixton water level | ~24 m aOD | [`04_terrain.py L42`](https://github.com/rrous/mezolit2/blob/master/pipeline/04_terrain.py#L42) |

---

## 12. Troubleshooting

### Pipeline errors

**`ModuleNotFoundError: rasterio`**
```bash
# GDAL must be installed before rasterio on Windows
conda install -c conda-forge gdal
pip install rasterio
```

**`ERROR: DATABASE_URL not set`**
```bash
# Check .env file exists in repo root (not in pipeline/)
ls .env   # should exist
# Check content
cat .env  # should have DATABASE_URL=postgresql://...
```

**`ERROR: data/raw/dem/ not found`**
```bash
# Run download script first
python 02_download_dem.py
# Or manually place tiles in data/raw/dem/
```

**`psycopg2.OperationalError: FATAL: remaining connection slots`**
- Supabase free tier limits connections — wait a few minutes and retry
- Or increase pool size in `06_import_supabase.py`

### Frontend errors

**`Failed to load map` + `VITE_SUPABASE_URL` error**
```bash
# frontend/.env must exist
cat frontend/.env
# Should contain VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
```
See [`frontend/src/main.js L27–L31`](https://github.com/rrous/mezolit2/blob/master/frontend/src/main.js#L27) for the error handler.

**No terrain polygons loading**
1. Open browser DevTools → Network tab
2. Check Supabase REST calls to `/rest/v1/terrain_features`
3. If 401: check `VITE_SUPABASE_ANON_KEY` is correct
4. If 0 results: check `06_import_supabase.py` was run successfully

**Vercel deploy fails with "framework mismatch"**
- Ensure `frontend/vercel.json` contains `"framework": null`
- See commit [`820af5b`](https://github.com/rrous/mezolit2/commit/820af5b) for the fix

### Database issues

**Terrain features missing biotope_id**
```bash
# Re-run KB rules
python 05_kb_rules.py
python 06_import_supabase.py
```

**Ecotone geometry NULL**
```bash
# 01_seed adds KB data without geometry
# 06_import adds geometry — both must run
python 01_seed_kb_data.py
python 06_import_supabase.py
```

**Verify everything is correct:**
```bash
python verify_db.py && python verify_deep.py
```

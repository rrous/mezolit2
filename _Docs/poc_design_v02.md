# Mezolitický KB — PoC Design Document
## Yorkshire / Star Carr | Online architektura | v0.2

---

## 1. Cíl PoC

Interaktivní mapa Yorkshire ~6200 BCE zobrazující terrain subtypes, biotopy a ekotony nad rekonstruovanou geografií. Přístupná z jakéhokoliv zařízení (desktop, mobil) přes URL. Uživatel může procházet mapu jako Google Maps — od celkového pohledu až po detail říční nivy nebo ekotonu u Star Carr.

**Mimo scope PoC:** fauna, flora, kalorické modelování, simulace skupiny, autentikace, multi-user.

---

## 2. Architektura

```
[Lokální pipeline — jednorázový batch job]
  Copernicus DEM 30m (GeoTIFF)
  GEBCO 2023 (GeoTIFF)
  OS Open Rivers (GeoJSON)
        │
        ▼
  Python/GDAL skripty
  - rekonstrukce pobřeží (-25m kontura z GEBCO)
  - odvození terrain polygonů z DEM
  - aplikace CAN_HOST pravidel z KB
  - import seed dat z schema_examples_v04.json
        │
        ▼ (jednorázový import přes psycopg2)
        │
        ▼
  [Supabase — PostGIS]
  - tabulka terrain_subtypes   (KB referenční data)
  - tabulka terrain_features   (geometrie + KB atributy)
  - tabulka biotopes           (KB data)
  - tabulka can_host           (CAN_HOST hrany)
  - tabulka ecotones           (geometrie + KB atributy)
  - tabulka rivers             (liniová vrstva)
        │
        ▼
  [FastAPI — Railway]
  auto-deploy z GitHub při push
  - /api/terrain?bbox=...
  - /api/ecotones?bbox=...
  - /api/rivers?bbox=...
  - /api/biotope/{id}
  - /api/coastline
        │
        ▼
  [Leaflet.js frontend — Vercel]
  auto-deploy z GitHub při push
  - OSM base tiles (free)
  - vektorové overlay vrstvy
  - hover tooltip / click panel
  - sezónní + certainty filtr
```

---

## 3. Hosting a služby

| Vrstva | Služba | Tier | Cena |
|---|---|---|---|
| DB + prostorové dotazy | Supabase PostGIS | Free | $0 |
| REST API | Railway | Hobby ($5/měsíc) | ~$5 |
| Frontend | Vercel | Free | $0 |
| Base tiles | OpenStreetMap | Free | $0 |
| CI/CD | GitHub Actions | Free | $0 |

**Railway Hobby** je potřeba pro trvalý běh (free tier uspí kontejner po nečinnosti).

---

## 4. Data sources

### 4.1 Copernicus DEM GLO-30
- **Co:** digitální model terénu, 30m rozlišení
- **Odkaz:** https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model
- **Licence:** free, attribution required
- **Použití:** slope, drainage basins, elevation zones → terrain_subtype placement

### 4.2 GEBCO 2023
- **Co:** batometrie, 15 arc-second rozlišení
- **Odkaz:** https://www.gebco.net/data_and_products/gridded_bathymetry_data/
- **Licence:** free
- **Použití:** kontura -25m = rekonstruované mesolítické pobřeží

### 4.3 OS Open Rivers
- **Co:** hydrografická síť Anglie a Walesu
- **Odkaz:** https://www.ordnancesurvey.co.uk/products/os-open-rivers
- **Licence:** OGL — free
- **Použití:** říční síť jako liniová vrstva

---

## 5. PostGIS schema

### 5.1 `terrain_subtypes` (KB referenční data, bez geometrie)
```sql
id TEXT PRIMARY KEY,              -- tst_001
name TEXT,
description TEXT,
hydrology TEXT,
slope TEXT,
substrate TEXT,
elevation_min_m REAL,
elevation_max_m REAL,
flint_availability TEXT,          -- NONE | LOW | MEDIUM | HIGH
trafficability TEXT,
energy_multiplier REAL,
certainty TEXT,                   -- DIRECT | INDIRECT | INFERENCE | SPECULATION
source TEXT,
status TEXT                       -- VALID | REVISED | DISPUTED | REFUTED | HYPOTHESIS
```

### 5.2 `terrain_features` (geometrie + reference na subtype)
```sql
id TEXT PRIMARY KEY,              -- tf_001
name TEXT,
terrain_subtype_id TEXT,          -- FK → terrain_subtypes.id
geom GEOMETRY(POLYGON, 4326),     -- WGS84
anchor_site BOOLEAN,              -- true = lokalita s přímým dokladem
notes TEXT,
certainty TEXT,
source TEXT
```

### 5.3 `biotopes` (KB data, bez geometrie)
```sql
id TEXT PRIMARY KEY,              -- bt_001
name TEXT,
description TEXT,
productivity_class TEXT,
productivity_kcal_km2_year REAL,
trafficability TEXT,
energy_multiplier REAL,
seasonal_spring_modifier REAL,
seasonal_summer_modifier REAL,
seasonal_autumn_modifier REAL,
seasonal_winter_modifier REAL,
seasonal_spring_note TEXT,
seasonal_summer_note TEXT,
seasonal_autumn_note TEXT,
seasonal_winter_note TEXT,
certainty TEXT,
source TEXT,
status TEXT
```

### 5.4 `can_host` (CAN_HOST hrany — M:N biotop ↔ terrain_subtype)
```sql
id SERIAL PRIMARY KEY,
biotope_id TEXT,                  -- FK → biotopes.id
terrain_subtype_id TEXT,          -- FK → terrain_subtypes.id
trigger TEXT,                     -- baseline | event_fire | event_flood | ...
spatial_scale TEXT,               -- landscape | local | micro
quality_modifier REAL,            -- 0.0–1.0
duration_years INTEGER,           -- NULL = permanentní
certainty TEXT,
source TEXT
```

### 5.5 `ecotones` (geometrie + atributy)
```sql
id TEXT PRIMARY KEY,              -- ec_001
name TEXT,
biotope_a_id TEXT,                -- FK → biotopes.id
biotope_b_id TEXT,                -- FK → biotopes.id
geom GEOMETRY(MULTILINESTRING, 4326),
edge_effect_factor REAL,          -- typicky 1.2–1.8
human_relevance TEXT,             -- LOW | MEDIUM | HIGH | CRITICAL
certainty TEXT,
source TEXT,
status TEXT
```

### 5.6 `rivers` (liniová vrstva)
```sql
id TEXT PRIMARY KEY,
name TEXT,
geom GEOMETRY(LINESTRING, 4326),
permanence TEXT,                  -- permanent | seasonal | reconstructed
certainty TEXT,
source TEXT
```

### 5.7 `coastline` (rekonstruované pobřeží)
```sql
id TEXT PRIMARY KEY,              -- coast_6200bce
name TEXT,
geom GEOMETRY(MULTIPOLYGON, 4326),
sea_level_offset_m REAL,          -- -25.0
certainty TEXT,
source TEXT,
status TEXT
```

### 5.8 Prostorové indexy
```sql
CREATE INDEX terrain_features_geom_idx ON terrain_features USING GIST(geom);
CREATE INDEX ecotones_geom_idx ON ecotones USING GIST(geom);
CREATE INDEX rivers_geom_idx ON rivers USING GIST(geom);
CREATE INDEX coastline_geom_idx ON coastline USING GIST(geom);
```

---

## 6. API endpoints (FastAPI na Railway)

Všechny spatial endpointy vrací GeoJSON s KB atributy embedded jako `properties`.

### 6.1 Spatial endpointy
```
GET /api/terrain?bbox={west,south,east,north}&season={optional}
GET /api/ecotones?bbox={west,south,east,north}
GET /api/rivers?bbox={west,south,east,north}
GET /api/coastline
```

### 6.2 Detail endpointy
```
GET /api/biotope/{id}
GET /api/terrain_feature/{id}
GET /api/ecotone/{id}
```

### 6.3 Response struktura
```json
{
  "type": "FeatureCollection",
  "features": [...],
  "meta": {
    "bbox": [...],
    "season": "AUTUMN",
    "feature_count": 42,
    "certainty_distribution": {
      "DIRECT": 5,
      "INDIRECT": 12,
      "INFERENCE": 25
    }
  }
}
```

---

## 7. Frontend (Leaflet.js na Vercel)

### 7.1 Stack
- Leaflet.js — map library
- OSM tiles — base mapa (free)
- Vanilla JS + Vite — build tool, žádný framework

### 7.2 Vrstvy (pořadí renderování)
1. OSM base tiles
2. Rekonstruované pobřeží — zatopené oblasti šedý overlay
3. Terrain subtypes — polygony, barvy dle biotopu
4. Ekotony — linie, barva dle edge_effect_factor
5. Řeky — modré linie, tloušťka dle permanence

### 7.3 Barevné kódování biotopů
```
LAKE          → #4A90D9 (modrá)
WETLAND       → #7FB069 (zeleno-modrá)
BOREAL_FOREST → #2D6A4F (tmavě zelená)
OPEN_LAND     → #E9C46A (světle žlutá)
COASTAL       → #F4A261 (béžová)
RIPARIAN      → #52B788 (světle zelená)
CHALK_SCRUB   → #D4A373 (světle hnědá)
INTERTIDAL    → #ADB5BD (pískově šedá)
FOREST_GLADE  → #95D5B2 (světle zelená — micro, zobrazí se jen při velkém zoomu)
```

### 7.4 Epistemické kódování
```
DIRECT       → solid border, 90% opacity
INDIRECT     → dashed border, 75% opacity
INFERENCE    → dotted border, 60% opacity
SPECULATION  → no border, 45% opacity
```

### 7.5 Hover tooltip
```
[Název terrain feature]
Biotop: Mokřad (boreální)
Produktivita: VERY_HIGH
Jistota: DIRECT ●
```

### 7.6 Click panel (pravý panel ~300px)
```
[Název]
[Popis]

Biotop: Mokřad (boreální)
Produktivita: 1,200,000 kcal/km²/rok
Průchodnost: LOW (energy ×1.8)

Sezónní modifikátory:
  Jaro:   ×1.4 — hnízdiště, jedlé výhonky
  Léto:   ×1.2 — maximum vegetace
  Podzim: ×1.1
  Zima:   ×0.5 — zmrznutí

Epistemika:
  Jistota: DIRECT
  Zdroj: Mellars & Dark 1998
  Status: VALID
```

### 7.7 Filtry (toolbar)
- **Sezóna:** SPRING | SUMMER | AUTUMN | WINTER
- **Jistota:** DIRECT | INDIRECT | INFERENCE | SPECULATION
- **Vrstvy:** terrain | ecotones | rivers (toggle)

---

## 8. Pipeline: geodata → PostGIS

```
pipeline/
  01_download.md          ← instrukce ke stažení (manuální — data jsou velká)
  02_coastline.py         ← GEBCO → coastline_6200bce.geojson
  03_terrain.py           ← DEM → terrain polygony s atributy
  04_kb_rules.py          ← aplikace CAN_HOST pravidel ze schema_examples_v04.json
  05_import_supabase.py   ← GeoJSON + KB JSON → PostGIS přes psycopg2
```

Pipeline běží lokálně, výsledky jdou přímo do Supabase přes connection string.

---

## 9. Struktura repozitáře

```
mesolithic-kb/
  pipeline/
    01_download.md
    02_coastline.py
    03_terrain.py
    04_kb_rules.py
    05_import_supabase.py
  api/
    main.py               ← FastAPI app
    models.py             ← Pydantic modely
    db.py                 ← PostGIS query funkce
    requirements.txt
    Dockerfile            ← pro Railway deploy
  frontend/
    index.html
    src/
      map.js
      layers.js           ← vrstva logika
      panel.js            ← click panel
      filters.js          ← sezóna / certainty filtry
    vite.config.js
  kb_data/
    schema_examples_v04.json
    vocabulary_v02.json
  .env.example            ← SUPABASE_URL, SUPABASE_KEY, DATABASE_URL
  .gitignore              ← data/raw/, .env
  README.md
```

---

## 10. Environment variables

```
# Supabase
SUPABASE_URL=https://xxx.supabase.co
DATABASE_URL=postgresql://postgres:xxx@db.xxx.supabase.co:5432/postgres

# API (Railway)
CORS_ORIGINS=https://mesolithic-kb.vercel.app
```

---

## 11. Yorkshire anchor

```
Yorkshire bounding box:
  west:  -2.5
  east:   0.1
  south: 53.5
  north: 54.7

Star Carr / Lake Flixton:
  lat: 54.2778
  lon: -0.5833
  terrain_subtype: tst_001 (glacial_lake_basin)
```

---

## 12. Definice hotovo (PoC)

1. Mapa zobrazuje Yorkshire s rekonstruovaným mesolítickým pobřežím
2. Terrain polygony viditelné a klikatelné na všech zoom úrovních
3. Hover tooltip zobrazí název + biotop + certainty
4. Click panel zobrazí plný KB záznam včetně seasonal modifiers
5. Sezónní filtr změní vizuální styl polygonů
6. Star Carr lokalita identifikovatelná na mapě
7. Řeky sledovatelné při zoom jako Google Maps cyklotrasy
8. Funguje na mobilu (responsive layout)
9. URL sdílitelná — kdokoliv s linkem uvidí mapu

---

## 13. Otevřené otázky pro implementaci

- **Terrain polygonizace:** elevation bands pro PoC (jednodušší), watersheds pro v2
- **Ekotony:** automaticky z hranice sousedních polygonů; Star Carr zpřesnit ručně
- **Supabase free tier limity:** 500 MB storage, 2 GB bandwidth/měsíc — pro PoC dostatečné
- **Polygon simplifikace:** API vrátí různé rozlišení dle zoom parametru (ST_SimplifyPreserveTopology v PostGIS)
- **Rozlišení tst_003 vs tst_005 bez geologických dat:** Pro PoC použít Yorkshire Wolds = tst_005 (chalk, elevace 50–200m, east Yorkshire východně od -0.8°), North York Moors = tst_003 (limestone, elevace 200–450m, central/west Yorkshire)

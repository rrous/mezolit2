# Implementační plán: Mezolitické Polabí v PostGIS

## 1. OBLAST ZÁJMU

### Bounding box (~100 × 100 km)

```
Západ:  14.45° E    (Brandýs nad Labem / Stará Boleslav)
Východ: 15.75° E    (Pardubice / Přelouč)
Jih:    49.70° N    (okraj Vysočiny — Čáslav, Kutná Hora)
Sever:  50.30° N    (Pojizeří — Mladá Boleslav, Jičín)
```

**Co je uvnitř:**
- Jádro Polabí: Kolín → Poděbrady → Nymburk → Lysá nad Labem
- Soutok Labe s Cidlinou, Mrlinou, Výrovkou, Jizerou
- Hrabanov (klíčový pylový profil)
- Přechod do pahorkatin na J a S (kontrastní biotopy)
- Železné hory na JV (geologický kontrast)

### Rozlišení — kompromis

| Účel | Rozlišení | Velikost rastru | Poznámka |
|---|---|---|---|
| Plná oblast 100×100 km | **25 m** | 4000 × 4000 = 16M buněk | Hlavní pracovní rozlišení |
| Detailní výřez (niva Labe) | **5 m** | variabilní | Pro meandrování, mokřady |

> **Proč ne 5 m na celou oblast?** Při 100×100 km to je 400M buněk — Supabase
> to nezvládne jako raster efektivně, a většina analýz (biotopy, ekotony) to nepotřebuje.
> 25 m je standard pro krajinnou ekologii na této škále.

---

## 2. DATA — CO STÁHNOUT A ODKUD

### 2.1 DMR 5G (výškový model)

**Zdroj:** ČÚZK Geoprohlížeč — https://ags.cuzk.cz/geoprohlizec/

**Postup:**
1. Jít na https://geoportal.cuzk.cz → Výškopis → DMR 5G
2. Data jsou rozdělena na dlaždice (~2.5 × 2 km)
3. Pro 100×100 km potřebuješ cca 2000 dlaždic
4. **Lepší varianta:** Atom feed pro hromadné stažení, nebo kontaktovat ČÚZK pro blokové stažení

**Alternativa (rychlejší start):**
- **EU-DEM v1.1** (Copernicus): rozlišení 25 m, pokrývá celou Evropu, volně ke stažení
- URL: https://land.copernicus.eu/imagery-in-situ/eu-dem/eu-dem-v1.1
- Stačí pro 25m pracovní rozlišení!
- **Doporučuji začít s tímto** a DMR 5G použít jen pro detailní výřezy

### 2.2 Vodní toky (DIBAVOD)

**Zdroj:** VÚV TGM — https://www.dibavod.cz/
- Vrstva A01 — vodní toky (linie)
- Vrstva A05 — vodní plochy
- Vrstva A07 — povodí
- Formát: shapefile → import do PostGIS

### 2.3 Geologická mapa

**Zdroj:** Česká geologická služba — https://mapy.geology.cz/
- Geologická mapa 1:50 000 — WMS/WFS služba
- Použití: substrát ovlivňuje půdu → vegetaci

### 2.4 Půdní mapa

**Zdroj:** Výzkumný ústav meliorací a ochrany půdy — https://bpej.vumop.cz/
- BPEJ (bonitované půdně ekologické jednotky)
- Kódují skeletovitost, hloubku, typ půdy

### 2.5 Pylová data

**Zdroj:** European Pollen Database + Česká pylová databáze
- Klíčové lokality v oblasti: **Hrabanov** (Lysá n.L.), **Švarcenberk** (J Čechy, mimo bbox ale referenční)
- Data ke stažení: https://www.europeanpollendatabase.net/

---

## 3. PREPROCESSING PIPELINE

### Nástroje (lokálně nebo v kontejneru, NE v Supabase)

```bash
# Instalace
pip install rasterio geopandas
# nebo
conda install gdal rasterio geopandas

# WhiteboxTools pro hydrologické analýzy
pip install whitebox
```

### 3.1 Příprava DEM

```bash
# Pokud EU-DEM (jeden GeoTIFF):
# Ořez na bounding box
gdalwarp -te 14.45 49.70 15.75 50.30 \
         -t_srs EPSG:32633 \
         eu_dem_v11.tif \
         polabi_dem_25m.tif

# Převzorkování na přesně 25 m grid
gdalwarp -tr 25 25 -r bilinear \
         polabi_dem_25m.tif \
         polabi_dem_25m_aligned.tif
```

### 3.2 Odvozené vrstvy z DEM

```python
# slope.py — příklad, Claude Code vygeneruje celý skript
import whitebox

wbt = whitebox.WhiteboxTools()

# Sklon (ve stupních)
wbt.slope("polabi_dem_25m.tif", "polabi_slope.tif", units="degrees")

# Expozice
wbt.aspect("polabi_dem_25m.tif", "polabi_aspect.tif")

# Topografický index vlhkosti (TWI)
wbt.wetness_index("polabi_dem_25m.tif", "polabi_twi.tif")

# Flow accumulation
wbt.d_inf_flow_accumulation("polabi_dem_25m.tif", "polabi_flowacc.tif")

# Extrakce vodní sítě (threshold = 1 km² povodí = 1600 buněk při 25 m)
wbt.extract_streams("polabi_flowacc.tif", "polabi_streams.tif", threshold=1600)

# Strahler stream order
wbt.strahler_stream_order("polabi_streams.tif", "polabi_dem_25m.tif", "polabi_strahler.tif")

# Výška nad nejbližším tokem (HAND — Height Above Nearest Drainage)
wbt.elevation_above_stream("polabi_dem_25m.tif", "polabi_streams.tif", "polabi_hand.tif")
```

### 3.3 Výstup preprocessingu

Po tomto kroku máš **7 rastrových vrstev**, všechny zarovnané na stejný grid:

| Soubor | Obsah | Jednotky |
|---|---|---|
| `polabi_dem_25m.tif` | Nadmořská výška | m n.m. |
| `polabi_slope.tif` | Sklon | stupně |
| `polabi_aspect.tif` | Expozice | stupně (0–360) |
| `polabi_twi.tif` | Topografický index vlhkosti | bezrozměrný |
| `polabi_flowacc.tif` | Akumulace odtoku | počet buněk |
| `polabi_strahler.tif` | Řád toku | 1–7+ |
| `polabi_hand.tif` | Výška nad tokem | m |

---

## 4. POSTGIS SCHÉMA

### 4.1 Rastrová data — přístup

PostGIS raster na Supabase: rastrové vrstvy importovat jako tabulky pomocí `raster2pgsql`.

```bash
# Import DEM do PostGIS
raster2pgsql -s 32633 -t 100x100 -I -C -M \
  polabi_dem_25m.tif public.dem | psql $SUPABASE_DB_URL

# Totéž pro ostatní vrstvy
raster2pgsql -s 32633 -t 100x100 -I -C -M \
  polabi_slope.tif public.slope | psql $SUPABASE_DB_URL

raster2pgsql -s 32633 -t 100x100 -I -C -M \
  polabi_twi.tif public.twi | psql $SUPABASE_DB_URL

raster2pgsql -s 32633 -t 100x100 -I -C -M \
  polabi_hand.tif public.hand | psql $SUPABASE_DB_URL

raster2pgsql -s 32633 -t 100x100 -I -C -M \
  polabi_strahler.tif public.strahler | psql $SUPABASE_DB_URL
```

### 4.2 Alternativa — rastr jako vektorový grid (doporučeno pro Supabase)

Supabase má limity na raster extension. **Robustnější přístup:**
konvertovat rastr na vektorový grid (jeden řádek = jedna buňka 25×25 m).

```sql
-- Hlavní tabulka krajinného modelu
CREATE TABLE landscape_cells (
    id BIGSERIAL PRIMARY KEY,

    -- Prostorové souřadnice
    geom GEOMETRY(Polygon, 32633) NOT NULL,  -- 25×25 m čtverec
    col INTEGER NOT NULL,
    row INTEGER NOT NULL,

    -- Vrstva 1: Terén (z DEM, neměnné)
    elevation REAL,          -- m n.m.
    slope REAL,              -- stupně
    aspect REAL,             -- stupně 0-360
    twi REAL,                -- topografický index vlhkosti
    hand REAL,               -- výška nad nejbližším tokem (m)
    flow_acc REAL,           -- akumulace odtoku
    strahler_order SMALLINT, -- řád toku (NULL pokud buňka není tok)

    -- Vrstva 2: Hydrologie (odvozená, mezolitická rekonstrukce)
    hydro_type VARCHAR(30),  -- 'hlavní_koryto', 'vedlejší_rameno', 'tůň', 'mokřad', 'záplavová_zóna', 'suchá_niva', NULL
    flood_frequency REAL,    -- roky (Q1 = každý rok, Q100 = jednou za 100 let)
    water_distance REAL,     -- vzdálenost k nejbližší vodě (m)

    -- Vrstva 3: Biotop (klasifikovaný)
    biotope VARCHAR(40),     -- viz klasifikační tabulka
    biotope_confidence REAL, -- 0-1, jistota klasifikace

    -- Vrstva 4: Ekoton
    is_ecotone BOOLEAN DEFAULT FALSE,
    ecotone_type VARCHAR(60),     -- např. 'lužní_les/mokřad'
    ecotone_blend REAL,           -- 0-1, míra prolnutí

    -- Vrstva 5: Disturbance (dynamická)
    disturbance_type VARCHAR(30), -- 'požár', 'bobr', 'vývrat', NULL
    disturbance_age INTEGER,      -- roky od poslední disturbance
    succession_stage VARCHAR(20), -- 'holá', 'byliny', 'keře', 'mladý_les', 'zralý_les'

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Prostorový index
CREATE INDEX idx_landscape_geom ON landscape_cells USING GIST (geom);

-- Indexy pro dotazy
CREATE INDEX idx_landscape_biotope ON landscape_cells (biotope);
CREATE INDEX idx_landscape_colrow ON landscape_cells (col, row);
```

### 4.3 Pomocné tabulky

```sql
-- Vodní toky jako linie (z DIBAVOD nebo odvozené)
CREATE TABLE waterways (
    id SERIAL PRIMARY KEY,
    geom GEOMETRY(LineString, 32633) NOT NULL,
    strahler_order SMALLINT,
    channel_type VARCHAR(30),   -- 'meandrující', 'anastomózní', 'divočící'
    active_width REAL,          -- šířka aktivního koryta (m)
    meander_belt_width REAL,    -- šířka meandrovacího pásu (m)
    sinuosity REAL,
    name VARCHAR(100)
);

-- Biotopová klasifikační pravidla (referenční)
CREATE TABLE biotope_rules (
    id SERIAL PRIMARY KEY,
    biotope VARCHAR(40) NOT NULL,
    elev_min REAL,
    elev_max REAL,
    slope_min REAL,
    slope_max REAL,
    twi_min REAL,
    twi_max REAL,
    hand_min REAL,
    hand_max REAL,
    aspect_condition VARCHAR(50),  -- 'S' pro jižní, NULL pro jakoukoliv
    priority INTEGER,              -- vyšší = přednost při konfliktu
    description TEXT
);

-- Pylová data (referenční body pro validaci)
CREATE TABLE pollen_sites (
    id SERIAL PRIMARY KEY,
    geom GEOMETRY(Point, 32633),
    name VARCHAR(100),
    age_min INTEGER,  -- cal BC
    age_max INTEGER,  -- cal BC
    tree_pollen_pct REAL,
    dominant_taxa TEXT[],
    source VARCHAR(200)
);

-- Archeologické lokality (validace osídlení)
CREATE TABLE archaeological_sites (
    id SERIAL PRIMARY KEY,
    geom GEOMETRY(Point, 32633),
    name VARCHAR(200),
    period VARCHAR(50),
    site_type VARCHAR(50),
    elevation REAL,
    distance_to_water REAL,
    source VARCHAR(200)
);
```

---

## 5. SQL KLASIFIKACE BIOTOPŮ

### 5.1 Naplnění pravidel

```sql
INSERT INTO biotope_rules (biotope, elev_min, elev_max, slope_min, slope_max, twi_min, twi_max, hand_min, hand_max, aspect_condition, priority, description) VALUES
-- Mokřad má nejvyšší prioritu (voda dominuje)
('mokřad',         100, 400,  0,  1,  12, 99,  0,   1,   NULL, 100, 'Trvale/sezónně zaplavená plocha, rákos, ostřice'),
('lužní_les',      100, 300,  0,  3,  10, 14,  0,   3,   NULL, 90,  'Periodicky zaplavovaný les: jilm, jasan, dub, lípa'),
('štěrková_lavice', 100, 300, 0,  2,  NULL, NULL, 0, 0.5, NULL, 95,  'Aktivní říční koryto, pionýrská vegetace'),
('nížinný_smíšený', 100, 400, 3,  25, 5,   10,  3,   99,  NULL, 50,  'Dub, lípa, jilm, líska — hlavní lesní biotop nížin'),
('pahorkatina_les', 400, 700, 3,  25, 5,   10,  NULL, NULL, NULL, 50,  'Buk, jedle, dub, lípa'),
('suťový_les',     200, 800, 25, 90, 0,   5,   NULL, NULL, NULL, 60,  'Strmé svahy: javor, lípa, jilm'),
('xerotermní_step', 100, 500, 15, 45, 0,   4,   NULL, NULL, 'S',  70,  'Jižní svahy: trávy, keře, rozvolněné stromy'),
('horský_les',     700, 1200, 0, 35, NULL, NULL, NULL, NULL, NULL, 50,  'Buk, jedle, přirozeně smrk ve vyšších polohách'),
('subalpínský',    1200, 9999, 0, 90, NULL, NULL, NULL, NULL, NULL, 50,  'Nad hranicí lesa: kleč, louky'),
('rašeliniště',    500, 1000, 0,  3,  14, 99,  NULL, NULL, NULL, 85,  'Podhorské rašeliniště');

-- Poznámka k aspect_condition:
-- 'S' = jižní expozice (135°–225°), 'N' = severní, NULL = jakákoliv
```

### 5.2 Klasifikační query

```sql
-- Klasifikace biotopů: pravidla se aplikují podle priority
UPDATE landscape_cells lc SET
    biotope = matched.biotope,
    biotope_confidence = matched.confidence
FROM (
    SELECT DISTINCT ON (lc2.id)
        lc2.id,
        br.biotope,
        -- Confidence: jak dobře buňka sedí do středu pravidla (ne na okraji)
        LEAST(
            CASE WHEN br.elev_min IS NOT NULL
                 THEN 1.0 - ABS(lc2.elevation - (br.elev_min + br.elev_max)/2.0)
                          / NULLIF((br.elev_max - br.elev_min)/2.0, 0)
                 ELSE 1.0 END,
            CASE WHEN br.twi_min IS NOT NULL
                 THEN 1.0 - ABS(lc2.twi - (br.twi_min + br.twi_max)/2.0)
                          / NULLIF((br.twi_max - br.twi_min)/2.0, 0)
                 ELSE 1.0 END
        ) AS confidence
    FROM landscape_cells lc2
    CROSS JOIN biotope_rules br
    WHERE
        (br.elev_min IS NULL OR lc2.elevation >= br.elev_min)
        AND (br.elev_max IS NULL OR lc2.elevation <= br.elev_max)
        AND (br.slope_min IS NULL OR lc2.slope >= br.slope_min)
        AND (br.slope_max IS NULL OR lc2.slope <= br.slope_max)
        AND (br.twi_min IS NULL OR lc2.twi >= br.twi_min)
        AND (br.twi_max IS NULL OR lc2.twi <= br.twi_max)
        AND (br.hand_min IS NULL OR lc2.hand >= br.hand_min)
        AND (br.hand_max IS NULL OR lc2.hand <= br.hand_max)
        AND (br.aspect_condition IS NULL
             OR (br.aspect_condition = 'S' AND lc2.aspect BETWEEN 135 AND 225)
             OR (br.aspect_condition = 'N' AND (lc2.aspect < 45 OR lc2.aspect > 315)))
    ORDER BY lc2.id, br.priority DESC
) matched
WHERE lc.id = matched.id;
```

### 5.3 Prevence děr a překryvů (kritické — lekce z Yorkshire/Třeboňsko)

Revize 2026-04 ukázala, že Yorkshire mapa má **1 215 děr** v terénu, **911 z nich ≥ 5 ha**, největší **185 km²** (~6 % území v dírách), a **61 děr ve vodních biotopech s 791 km řek uvnitř** (potoky vykrajují jezera). Třeboňsko je lepší (192 děr), ale stále má 6 děr > 100 ha. Tyto chyby **žádný test v v0.2 nezachytil**. Pro Polabí platí:

**Pravidlo 1 — Pokrytí jako invariant:**
Po klasifikaci musí každá `landscape_cells` buňka uvnitř bbox mít `biotope IS NOT NULL`. Každé pravidlo musí mít catch-all variantu (bez thresholdů), nebo běží finální „default biotope" UPDATE:

```sql
-- Po hlavní klasifikaci doplň chybějící buňky podle elevace/terénu
UPDATE landscape_cells SET biotope = 'nížinný_smíšený',
                           biotope_confidence = 0.3
WHERE biotope IS NULL AND elevation < 400;

UPDATE landscape_cells SET biotope = 'pahorkatina_les',
                           biotope_confidence = 0.3
WHERE biotope IS NULL AND elevation >= 400 AND elevation < 700;

-- Sanity check — žádná buňka nesmí zůstat NULL
SELECT COUNT(*) FROM landscape_cells WHERE biotope IS NULL;
-- MUSÍ vrátit 0 před exportem
```

**Pravidlo 2 — Řeky neprořezávají vodní biotopy:**
Pořadí operací musí být: (a) klasifikuj biotopy → (b) generuj river buffery → (c) river buffery **sjednoť** s vodními biotopy (UNION), **nevyřezávej** je. Pipeline musí otestovat T-GEOM-02 před exportem.

```sql
-- ŠPATNĚ (Yorkshire): ST_Difference(wetland, river_buffer) → díra, kterou řeka protéká
-- SPRÁVNĚ: řeka uvnitř wetland polygonu = OK, wetland zůstává celý
-- Pokud chceš řeku vizuálně rozlišit, použij separátní liniovou vrstvu přes polygon
```

**Pravidlo 3 — Vektorová konverze grid→polygon:**
Při exportu `landscape_cells` → polygony biotopů použij `ST_Union` nad buňkami stejného biotopu a **ST_SnapToGrid** na 25 m, aby nevznikaly mikro-mezery mezi sousedními polygony. Po `ST_Union` pouze:

```sql
-- Fill tiny holes < 0.5 ha (rasterizační artefakty, NE glades)
UPDATE biotope_polygons SET geom = ST_MakeValid(
    ST_Collect(ST_ExteriorRing(geom))  -- odstraní interior rings menší než práh
)
WHERE ST_NumInteriorRings(geom) > 0;
-- Smart Holes: ponech jen díry 0.5-5 ha (glades, palouky) a s DIFFERENT biotope reklasifikovaným jako bt_glade
```

**Pravidlo 4 — Overlap check:**
Dva biotopy nesmí sdílet více než 1 m² plochy. Po exportu:
```sql
SELECT a.id, b.id, ST_Area(ST_Intersection(a.geom, b.geom)::geography) AS overlap_m2
FROM biotope_polygons a JOIN biotope_polygons b ON a.id < b.id
WHERE ST_Intersects(a.geom, b.geom)
  AND ST_Area(ST_Intersection(a.geom, b.geom)::geography) > 1;
-- MUSÍ být prázdné (kromě shared boundaries, které nemají plochu)
```

**Pravidlo 5 — Glade strategie:**
Díry 0,5–5 ha uvnitř lesního biotopu jsou **přijatelné jako palouky** (bt_glade), ale musí být **explicitně reklasifikovány** jako glade biotop s vlastním záznamem, ne ponechány jako prázdné díry. Viz `polabi_implementace.md §5.3 → bt_glade` a audit T-GEOM-01.

### 5.4 Detekce ekotonů

```sql
-- Ekoton = buňka, jejíž sousedé mají jiný biotop
-- a vzdálenost k hranici je menší než definovaná šířka ekotonu

-- Krok 1: Najdi buňky na hranici biotopů
WITH neighbors AS (
    SELECT
        c.id,
        c.biotope AS my_biotope,
        n.biotope AS neighbor_biotope
    FROM landscape_cells c
    JOIN landscape_cells n ON (
        ABS(c.col - n.col) <= 1
        AND ABS(c.row - n.row) <= 1
        AND c.id != n.id
    )
    WHERE c.biotope != n.biotope
)
UPDATE landscape_cells lc SET
    is_ecotone = TRUE,
    ecotone_type = edge.transition
FROM (
    SELECT DISTINCT
        id,
        my_biotope || '/' || neighbor_biotope AS transition
    FROM neighbors
) edge
WHERE lc.id = edge.id;

-- Krok 2: Rozšíření ekotonu o definovanou šířku
-- (iterativní buffer — spustit N-krát podle šířky ekotonu / 25 m)
-- Toto je zjednodušená verze; plná implementace potřebuje lookup tabulku šířek
```

---

## 6. HYDROLOGICKÁ REKONSTRUKCE — SQL

### 6.1 Klasifikace hydrologických zón

```sql
-- Na základě HAND (výška nad tokem) a Strahlera
UPDATE landscape_cells SET hydro_type = CASE
    -- Aktivní koryto
    WHEN strahler_order IS NOT NULL AND strahler_order >= 3
        THEN 'hlavní_koryto'

    -- Bezprostřední niva (sezónně zaplavená)
    WHEN hand < 1.0 AND slope < 2 AND flow_acc > 500
        THEN 'mokřad'
    WHEN hand < 2.0 AND slope < 3
        THEN 'záplavová_zóna'

    -- Širší niva (výjimečně zaplavená)
    WHEN hand < 5.0 AND slope < 5
        THEN 'suchá_niva'

    ELSE NULL  -- mimo nivu
END;

-- Vzdálenost k vodě
-- (Toto je lepší počítat v preprocessingu přes proximity raster,
-- ale v PostGIS jde taky:)
UPDATE landscape_cells lc SET
    water_distance = sub.dist
FROM (
    SELECT
        lc2.id,
        MIN(ST_Distance(lc2.geom, w.geom)) AS dist
    FROM landscape_cells lc2
    CROSS JOIN LATERAL (
        SELECT geom FROM waterways
        ORDER BY lc2.geom <-> geom
        LIMIT 1
    ) w
    GROUP BY lc2.id
) sub
WHERE lc.id = sub.id;
```

---

## 7. GENEROVÁNÍ MEANDRŮ (preprocessing, Python)

Meandry se negenerují v PostGIS — to je preprocessing krok.

```python
"""
Generování realistických říčních koryt pro mezolitické Polabí.
Vstup: přímočaré osy toků z flow accumulation
Výstup: meandrující/anastomózní linie pro import do PostGIS
"""
import numpy as np
from shapely.geometry import LineString, MultiLineString
import geopandas as gpd


def add_meanders(centerline: LineString, order: int, seed: int = 42) -> LineString:
    """
    Přidá meandry k přímé ose toku.

    Parametry závisí na Strahlerově řádu:
    - Řád 3-4: mírné meandrování, sinuosita 1.2-1.5
    - Řád 5-6: výrazné meandry, sinuosita 1.5-2.0
    - Řád 7+:  anastomózní — více souběžných koryt
    """
    rng = np.random.default_rng(seed)

    # Parametry podle řádu
    params = {
        3: {"sinuosity": 1.2, "wavelength_factor": 12, "amplitude_factor": 3},
        4: {"sinuosity": 1.3, "wavelength_factor": 12, "amplitude_factor": 4},
        5: {"sinuosity": 1.6, "wavelength_factor": 11, "amplitude_factor": 5},
        6: {"sinuosity": 1.8, "wavelength_factor": 10, "amplitude_factor": 6},
        7: {"sinuosity": 2.0, "wavelength_factor": 10, "amplitude_factor": 7},
    }

    p = params.get(min(order, 7), params[3])

    # Odhadovaná šířka koryta (m) z řádu
    width = {3: 5, 4: 12, 5: 30, 6: 80, 7: 200}.get(min(order, 7), 5)

    wavelength = width * p["wavelength_factor"]
    amplitude = width * p["amplitude_factor"]

    # Převzorkovat osu na body po wavelength/10
    length = centerline.length
    n_points = max(int(length / (wavelength / 10)), 10)
    fractions = np.linspace(0, 1, n_points)
    points = np.array([centerline.interpolate(f, normalized=True).coords[0]
                       for f in fractions])

    # Směrový vektor (tangenta)
    dx = np.gradient(points[:, 0])
    dy = np.gradient(points[:, 1])

    # Normálový vektor (kolmice)
    norm = np.sqrt(dx**2 + dy**2)
    nx = -dy / norm
    ny = dx / norm

    # Sinusoidální posun + šum
    s = np.linspace(0, length, n_points)
    displacement = amplitude * np.sin(2 * np.pi * s / wavelength)
    displacement += rng.normal(0, amplitude * 0.15, n_points)  # šum

    # Aplikovat posun
    new_x = points[:, 0] + nx * displacement
    new_y = points[:, 1] + ny * displacement

    return LineString(zip(new_x, new_y))


def generate_side_channels(main_channel: LineString, order: int,
                           n_channels: int = 3, seed: int = 42) -> list:
    """
    Pro anastomózní řeky (řád 7+): generuje vedlejší ramena.
    """
    rng = np.random.default_rng(seed)
    channels = []

    for i in range(n_channels):
        # Vedlejší rameno se odpojuje a připojuje zpět
        start_frac = rng.uniform(0.05, 0.7)
        end_frac = min(start_frac + rng.uniform(0.1, 0.4), 0.95)

        sub = LineString([
            main_channel.interpolate(f, normalized=True)
            for f in np.linspace(start_frac, end_frac, 50)
        ])

        # Posunout od hlavního koryta
        offset = rng.choice([-1, 1]) * rng.uniform(50, 300)
        side = sub.parallel_offset(offset, 'left' if offset > 0 else 'right')

        if not side.is_empty:
            channels.append(add_meanders(side, order - 1, seed=seed + i))

    return channels
```

---

## 8. FRAKTÁLNÍ HRANICE BIOTOPŮ (preprocessing, Python)

```python
"""
Rozfraktálení hranic biotopů pomocí midpoint displacement.
Vstup: hladké hranice z klasifikace (polygony biotopů)
Výstup: fraktální hranice s realistickými přechody
"""
import numpy as np
from shapely.geometry import Polygon, LineString


def fractalize_boundary(line: LineString, fractal_dim: float = 1.3,
                        min_segment: float = 25.0, seed: int = 42) -> LineString:
    """
    Midpoint displacement pro fraktální hranice.

    fractal_dim: cílová fraktální dimenze (1.0 = hladká, 1.5 = velmi členitá)
    min_segment: minimální délka segmentu (= rozlišení gridu)
    """
    rng = np.random.default_rng(seed)

    # Hurst exponent z fraktální dimenze
    H = 2.0 - fractal_dim  # pro 2D křivku: D = 2 - H

    coords = np.array(line.coords)

    # Iterativní midpoint displacement
    while True:
        new_coords = [coords[0]]

        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i + 1]
            segment_len = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

            if segment_len < min_segment:
                new_coords.append(p2)
                continue

            # Midpoint
            mid = (p1 + p2) / 2

            # Displacement kolmo na segment
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            normal = np.array([-dy, dx]) / segment_len

            # Velikost displacement škáluje se vzdáleností^H
            sigma = segment_len * 0.3 * (segment_len ** (H - 1))
            displacement = rng.normal(0, sigma)

            mid_displaced = mid + normal * displacement

            new_coords.append(mid_displaced)
            new_coords.append(p2)

        new_coords = np.array(new_coords)

        if len(new_coords) == len(coords):
            break
        coords = new_coords

    return LineString(coords)


# Fraktální dimenze podle typu přechodu
FRACTAL_DIMS = {
    'lužní_les/mokřad': 1.4,
    'nížinný_smíšený/lužní_les': 1.3,
    'nížinný_smíšený/pahorkatina_les': 1.15,
    'nížinný_smíšený/xerotermní_step': 1.25,
    'default': 1.3,
}
```

---

## 9. VALIDACE

### 9.1 Kontrolní metriky

Po vygenerování krajiny ověřit tyto metriky v PostGIS:

```sql
-- Poměr biotopů (porovnat s pylovými daty)
SELECT
    biotope,
    COUNT(*) AS cells,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 1) AS pct
FROM landscape_cells
WHERE biotope IS NOT NULL
GROUP BY biotope
ORDER BY pct DESC;

-- Očekávané hodnoty pro Polabí v atlantiku:
-- nížinný_smíšený:  40-55 %
-- lužní_les:        10-20 %
-- mokřad:            5-15 %
-- pahorkatina_les:  10-20 %
-- xerotermní_step:   2-5 %
-- otevřené plochy:   5-10 %
-- voda/koryto:       2-5 %

-- Podíl ekotonů
SELECT
    ROUND(COUNT(*) FILTER (WHERE is_ecotone)::numeric
        / COUNT(*) * 100, 1) AS ecotone_pct
FROM landscape_cells;
-- Očekávaná hodnota: 15-25 % plochy

-- Hortonovy poměry (vodní síť)
SELECT
    strahler_order,
    COUNT(*) AS n_segments,
    ROUND(AVG(ST_Length(geom))::numeric, 0) AS avg_length_m
FROM waterways
GROUP BY strahler_order
ORDER BY strahler_order;
-- Poměr bifurkace N(i)/N(i+1) by měl být 3-5
-- Poměr délek L(i+1)/L(i) by měl být 1.5-3.5
```

### 9.2 Vizuální validace

Export z PostGIS → QGIS pro vizuální kontrolu:
- Vypadají řeky jako řeky? (sinuosita, ramena)
- Jsou mokřady v nivách? (ne na kopcích)
- Je xerotermní step na jižních svazích?
- Jsou ekotony na hranicích biotopů?

### 9.3 Geometrické quality gates (POVINNÉ před exportem)

Polabí nesmí opakovat chyby Yorkshire/Třeboňsko. Pipeline **musí** projít
všemi testy z kategorie GEOM v [MAP_VALIDATION_TESTS_v02.md](MAP_VALIDATION_TESTS_v02.md):

| Test | Práh pro PASS | Proč to selhalo u Yorkshire |
|---|---|---|
| **T-GEOM-01** (díry) | max 5 % plochy v dírách, max 10 děr ≥ 100 ha, max 300 děr / 1 000 km² | 6 % plochy, díra 185 km², 1 215 děr |
| **T-GEOM-02** (řeky vyřezávající vodu) | **0 děr ve vodních biotopech obsahujících řeku** | 61 takových děr, 791 km řek uvnitř |
| **T-GEOM-03** (konektivita) | max 5 % polygonů pod 1 ha | neměřeno, ale v YORK 656 features / 2 673 parts = hodně drobků |
| **T-PHY-08** (řeka skrz vodu, všechny zdroje) | < 5 % řek s > 20 % délky uvnitř vodního polygonu | maskováno — testoval jen DIBAVOD |
| **T-SUPP-01** (pokrytí) | ≥ 95 % pokrytí bbox | ~99 % bylo OK, ale coverage není jediná metrika |

**Pipeline gate:** před krokem „Import do Supabase" (`06_import_supabase.py`) běží
`run_validation_tests.py --region polabi --fail-on GEOM,PHY`. Pokud jakýkoliv
GEOM nebo PHY test skončí FAIL, import se **nespustí** a operátor musí opravit
preprocessing. Tím se eliminuje scénář „data jsou v DB, teprve pak vidíme, že
je polygon plný děr".

### 9.4 Referenční metriky pro Polabí (kalibrace z předchozích regionů)

| Metrika | Yorkshire (revize 2026-04) | Třeboňsko | Polabí (cíl) |
|---|---|---|---|
| Počet děr / 1 000 km² | 49 | 206 | **< 50** |
| % plochy v dírách | 6,0 % | ~0,3 % | **< 1 %** |
| Max velikost díry | 185 km² | 5 km² | **< 1 km²** |
| Díry ve vodě s řekou | 61 (791 km řek) | 1 (57 m) | **0** |
| Coverage bbox | 98,9 % | 98,5 % | **≥ 99 %** |

---

## 10. POKYNY PRO CLAUDE CODE

### Co Claude Code DĚLÁ:
1. Generuje Python skripty pro preprocessing (WhiteboxTools, GDAL)
2. Generuje SQL pro PostGIS (klasifikace, analýzy)
3. Generuje Python pro meandry a fraktální hranice
4. Spouští validační dotazy a interpretuje výsledky

### Co Claude Code NEDĚLÁ:
1. Nevymýšlí tvary krajiny — aplikuje pravidla na reálná data
2. Nehádá biotopy — klasifikuje z parametrů
3. Nekreslí řeky ručně — generuje je matematicky z DEM
4. Nepřeskakuje validaci

### Pořadí práce:
```
1. Preprocessing DEM → 7 rastrových vrstev (Python/WhiteboxTools)
2. Import do PostGIS (raster2pgsql nebo vektorový grid)
3. Hydrologická rekonstrukce (SQL + Python pro meandry)
4. Klasifikace biotopů (SQL)
5. Ekotony (SQL)
6. Disturbance (Python — stochastický model)
7. Fraktální hranice (Python)
8. Validace (SQL + vizuální v QGIS)
9. Iterace na základě výsledků validace
```

-- Mezolit2 PoC — Polabí PostGIS Schema (incremental)
-- Run AFTER 00_schema.sql, BEFORE 06_import_supabase_polabi.py
--
-- This script DOES NOT replace 00_schema.sql; it adds Polabí-specific tables
-- (biotope_rules, pollen_sites, archaeological_sites) and extends shared tables
-- (terrain_features, rivers, ecotones) with a `region` column so that data from
-- multiple regions (yorkshire / cz / polabi) can co-exist in one Supabase project.
--
-- Polabí KB seed (terrain_subtypes / biotopes records with `pl_` prefix) is
-- inserted by 01c_seed_kb_data_polabi.py (NOT this SQL file).
--
-- Usage:
--   psql $SUPABASE_DB_URL -f 00_polabi_schema.sql
-- or paste into Supabase SQL Editor.
--
-- Dependencies: postgis extension; tables terrain_subtypes, biotopes, ecotones,
-- terrain_features, rivers from 00_schema.sql.

BEGIN;

-- ---------------------------------------------------------------------------
-- 5.10 region columns on shared tables
-- ---------------------------------------------------------------------------
-- Allows region filtering in RPC (e.g., WHERE region = 'polabi'). Existing
-- Yorkshire/CZ rows will have NULL region; backfill via UPDATE if/when needed.

ALTER TABLE terrain_features    ADD COLUMN IF NOT EXISTS region TEXT;
ALTER TABLE rivers              ADD COLUMN IF NOT EXISTS region TEXT;
ALTER TABLE ecotones            ADD COLUMN IF NOT EXISTS region TEXT;
ALTER TABLE site_instances      ADD COLUMN IF NOT EXISTS region TEXT;

CREATE INDEX IF NOT EXISTS terrain_features_region_idx ON terrain_features(region);
CREATE INDEX IF NOT EXISTS rivers_region_idx           ON rivers(region);
CREATE INDEX IF NOT EXISTS ecotones_region_idx         ON ecotones(region);
CREATE INDEX IF NOT EXISTS site_instances_region_idx   ON site_instances(region);

-- ---------------------------------------------------------------------------
-- 5.11 biotope_rules — referenční klasifikační pravidla (per polabi_implementace.md §5.1)
-- ---------------------------------------------------------------------------
-- Drží explicitní mapping rastrových thresholdů (elevation/slope/twi/hand/aspect)
-- na biotop. Není to runtime-classification table (klasifikace běží v Pythonu
-- v 04_terrain_polabi.py); slouží jako auditovatelný záznam pravidel pro
-- explainability ("proč tento polygon dostal tento biotop").

CREATE TABLE IF NOT EXISTS biotope_rules (
    id SERIAL PRIMARY KEY,
    region TEXT NOT NULL DEFAULT 'polabi',
    biotope_id TEXT REFERENCES biotopes(id),
    terrain_subtype_id TEXT REFERENCES terrain_subtypes(id),

    -- Raster thresholds (NULL = no constraint)
    elev_min REAL, elev_max REAL,         -- m a.s.l.
    slope_min REAL, slope_max REAL,       -- degrees
    twi_min REAL, twi_max REAL,           -- topographic wetness index
    hand_min REAL, hand_max REAL,         -- m above nearest drainage
    strahler_min SMALLINT,                -- minimum Strahler order (NULL = any)
    aspect_condition TEXT,                -- 'S' (135-225°) / 'N' (<45 OR >315) / NULL

    priority INTEGER NOT NULL,            -- vyšší = vyhrává při shodě
    description TEXT,
    source TEXT
);

CREATE INDEX IF NOT EXISTS biotope_rules_region_idx ON biotope_rules(region);
CREATE INDEX IF NOT EXISTS biotope_rules_priority_idx ON biotope_rules(priority DESC);

-- ---------------------------------------------------------------------------
-- 5.12 pollen_sites — referenční pylové profily pro validaci
-- ---------------------------------------------------------------------------
-- Hrabanov (Lysá nad Labem) je primární referenční bod pro Polabí ~7000-6000 BCE.
-- Další lokality (Branná, Komořanské jezero, Vracov) lze přidat z literatury.

CREATE TABLE IF NOT EXISTS pollen_sites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT NOT NULL DEFAULT 'polabi',
    geom GEOMETRY(POINT, 4326),
    age_min_cal_bce INTEGER,              -- e.g. 7000
    age_max_cal_bce INTEGER,              -- e.g. 5500
    tree_pollen_pct REAL,                 -- AP% (arboreal pollen percentage)
    dominant_taxa JSONB DEFAULT '[]',     -- e.g. ["Quercus", "Tilia", "Ulmus", "Corylus"]
    elevation_m REAL,
    notes TEXT,
    source TEXT,
    status TEXT DEFAULT 'VALID'
);

CREATE INDEX IF NOT EXISTS pollen_sites_geom_idx   ON pollen_sites USING GIST(geom);
CREATE INDEX IF NOT EXISTS pollen_sites_region_idx ON pollen_sites(region);

-- ---------------------------------------------------------------------------
-- 5.13 archaeological_sites — širší soubor mezolitických lokalit Polabí
-- ---------------------------------------------------------------------------
-- Pozn.: existující site_instances (00_schema.sql §5.8) drží Star Carr
-- lakescape entries jako epistemological anchors (POLYGON, lakescape_role).
-- archaeological_sites je doplňková tabulka pro bodové nálezy z AMCR / IA AV ČR
-- (Polabí má desítky až stovky mezolitických lokalit, většinou jako bodové záznamy).

CREATE TABLE IF NOT EXISTS archaeological_sites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT NOT NULL DEFAULT 'polabi',
    geom GEOMETRY(POINT, 4326),

    period TEXT,                          -- 'mezolit', 'pozdni_mezolit', etc.
    site_type TEXT,                       -- 'sídliště', 'rozptyl_štípaná', 'depo'
    elevation_m REAL,
    distance_to_water_m REAL,             -- nejbližší vodní tok / nádrž

    ident_cely TEXT,                      -- AMCR identifier
    katastr TEXT,                         -- katastrální území

    certainty TEXT,                       -- 'DIRECT' / 'INDIRECT' / 'INFERENCE'
    source TEXT,
    status TEXT DEFAULT 'VALID'
);

CREATE INDEX IF NOT EXISTS arch_sites_geom_idx   ON archaeological_sites USING GIST(geom);
CREATE INDEX IF NOT EXISTS arch_sites_region_idx ON archaeological_sites(region);
CREATE INDEX IF NOT EXISTS arch_sites_period_idx ON archaeological_sites(period);

COMMIT;

-- ---------------------------------------------------------------------------
-- Sanity checks (run manually after script)
-- ---------------------------------------------------------------------------
--   SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'terrain_features' AND column_name = 'region';
--   -- expects: 1 row
--
--   SELECT count(*) FROM biotope_rules;          -- 0 until 01c_seed runs
--   SELECT count(*) FROM pollen_sites;           -- 0 until 01c_seed runs
--   SELECT count(*) FROM archaeological_sites;   -- 0 until 04_terrain_polabi runs

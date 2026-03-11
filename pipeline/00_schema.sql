-- Mezolit2 PoC — PostGIS Schema
-- Yorkshire ~6200 BCE Knowledge Base
-- Execute in Supabase SQL Editor after enabling PostGIS:
--   CREATE EXTENSION IF NOT EXISTS postgis;

-- 5.1 terrain_subtypes (KB reference, no geometry)
CREATE TABLE IF NOT EXISTS terrain_subtypes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    hydrology TEXT,
    slope TEXT,
    substrate TEXT,
    elevation_min_m REAL,
    elevation_max_m REAL,
    flint_availability TEXT,
    trafficability TEXT,
    energy_multiplier REAL,
    nonrenewable_resources JSONB DEFAULT '[]',
    anchor_instances JSONB DEFAULT '[]',
    certainty TEXT,
    source TEXT,
    status TEXT DEFAULT 'VALID'
);

-- 5.2 terrain_features (geometry + FK to terrain_subtypes)
CREATE TABLE IF NOT EXISTS terrain_features (
    id TEXT PRIMARY KEY,
    name TEXT,
    terrain_subtype_id TEXT REFERENCES terrain_subtypes(id),
    biotope_id TEXT REFERENCES biotopes(id),
    geom GEOMETRY(POLYGON, 4326),
    anchor_site BOOLEAN DEFAULT FALSE,
    notes TEXT,
    certainty TEXT,
    source TEXT
);

-- 5.3 biotopes (KB data, no geometry)
CREATE TABLE IF NOT EXISTS biotopes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    productivity_class TEXT,
    productivity_kcal_km2_year REAL,
    productivity_certainty TEXT,
    productivity_source TEXT,
    trafficability TEXT,
    energy_multiplier REAL,
    dominant_species JSONB DEFAULT '[]',
    seasonal_spring_modifier REAL,
    seasonal_summer_modifier REAL,
    seasonal_autumn_modifier REAL,
    seasonal_winter_modifier REAL,
    seasonal_spring_note TEXT,
    seasonal_summer_note TEXT,
    seasonal_autumn_note TEXT,
    seasonal_winter_note TEXT,
    primary_threats_human JSONB DEFAULT '[]',
    extra_attributes JSONB DEFAULT '{}',
    certainty TEXT,
    source TEXT,
    status TEXT DEFAULT 'VALID'
);

-- 5.4 can_host (M:N biotope <-> terrain_subtype)
CREATE TABLE IF NOT EXISTS can_host (
    id SERIAL PRIMARY KEY,
    biotope_id TEXT REFERENCES biotopes(id),
    terrain_subtype_id TEXT REFERENCES terrain_subtypes(id),
    trigger TEXT DEFAULT 'baseline',
    spatial_scale TEXT DEFAULT 'landscape',
    quality_modifier REAL DEFAULT 1.0,
    duration_years INTEGER,
    duration_note TEXT,
    note TEXT,
    certainty TEXT,
    source TEXT
);

-- 5.5 ecotones (geometry + attributes)
CREATE TABLE IF NOT EXISTS ecotones (
    id TEXT PRIMARY KEY,
    name TEXT,
    biotope_a_id TEXT REFERENCES biotopes(id),
    biotope_b_id TEXT REFERENCES biotopes(id),
    geom GEOMETRY(MULTILINESTRING, 4326),
    edge_effect_factor REAL,
    edge_effect_source TEXT,
    human_relevance TEXT,
    seasonal_peaks JSONB DEFAULT '{}',
    certainty TEXT,
    source TEXT,
    status TEXT DEFAULT 'VALID'
);

-- 5.6 rivers (line layer)
CREATE TABLE IF NOT EXISTS rivers (
    id TEXT PRIMARY KEY,
    name TEXT,
    geom GEOMETRY(LINESTRING, 4326),
    permanence TEXT,
    certainty TEXT,
    source TEXT
);

-- 5.7 coastline (reconstructed coastline)
CREATE TABLE IF NOT EXISTS coastline (
    id TEXT PRIMARY KEY,
    name TEXT,
    geom GEOMETRY(MULTIPOLYGON, 4326),
    sea_level_offset_m REAL DEFAULT -25.0,
    certainty TEXT,
    source TEXT,
    status TEXT DEFAULT 'VALID'
);

-- 5.8 site_instances (archaeological sites — epistemological anchors)
CREATE TABLE IF NOT EXISTS site_instances (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lakescape_role TEXT,
    terrain_feature_id TEXT REFERENCES terrain_features(id),
    biotope_id TEXT REFERENCES biotopes(id),
    geom GEOMETRY(POLYGON, 4326),
    certainty TEXT,
    source TEXT,
    status TEXT DEFAULT 'VALID'
);

-- 5.9 Spatial indexes
CREATE INDEX IF NOT EXISTS terrain_features_geom_idx ON terrain_features USING GIST(geom);
CREATE INDEX IF NOT EXISTS ecotones_geom_idx ON ecotones USING GIST(geom);
CREATE INDEX IF NOT EXISTS rivers_geom_idx ON rivers USING GIST(geom);
CREATE INDEX IF NOT EXISTS coastline_geom_idx ON coastline USING GIST(geom);

-- Additional useful indexes
CREATE INDEX IF NOT EXISTS can_host_biotope_idx ON can_host(biotope_id);
CREATE INDEX IF NOT EXISTS can_host_terrain_idx ON can_host(terrain_subtype_id);
CREATE INDEX IF NOT EXISTS terrain_features_subtype_idx ON terrain_features(terrain_subtype_id);
CREATE INDEX IF NOT EXISTS site_instances_geom_idx ON site_instances USING GIST(geom);

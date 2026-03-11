-- ============================================================
-- Mezolit2 — Supabase RPC funkce pro frontend
-- Spustit v Supabase SQL Editoru (celý soubor najednou)
-- ============================================================

-- MIGRACE: přidat biotope_id sloupec do terrain_features (pokud chybí)
-- Spustit jednou před ostatními příkazy:
ALTER TABLE terrain_features
    ADD COLUMN IF NOT EXISTS biotope_id TEXT REFERENCES biotopes(id);

-- ============================================================

-- 1. TERRAIN FEATURES
--    Vrací GeoJSON FeatureCollection s terrain polygony + biotop info.
--    Zoom parameter řídí toleranci simplifikace geometrie.
CREATE OR REPLACE FUNCTION get_terrain(
    west  float8,
    south float8,
    east  float8,
    north float8,
    zoom  int DEFAULT 8
)
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
AS $$
DECLARE
    _bbox geometry;
    _tol  float8;
    result json;
BEGIN
    _bbox := ST_MakeEnvelope(west, south, east, north, 4326);
    _tol  := CASE
        WHEN zoom >= 12 THEN 0.0002
        WHEN zoom >= 9  THEN 0.001
        ELSE 0.002
    END;

    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(feat), '[]'::json)
    ) INTO result
    FROM (
        SELECT json_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(
                ST_SimplifyPreserveTopology(tf.geom, _tol)
            )::json,
            'properties', json_build_object(
                -- terrain feature
                'id',                   tf.id,
                'terrain_subtype_id',   tf.terrain_subtype_id,
                'anchor_site',          tf.anchor_site,
                'certainty',            tf.certainty,
                'source',               tf.source,
                'notes',                tf.notes,
                -- terrain subtype
                'subtype_name',         ts.name,
                'description',          ts.description,
                'elevation_min_m',      ts.elevation_min_m,
                'elevation_max_m',      ts.elevation_max_m,
                'hydrology',            ts.hydrology,
                'slope',                ts.slope,
                'substrate',            ts.substrate,
                'flint_availability',   ts.flint_availability,
                -- biotope (directly from terrain feature, assigned by 05_kb_rules.py)
                'biotope_id',           b.id,
                'biotope_name',         b.name,
                'productivity_class',   b.productivity_class,
                'productivity_kcal',    b.productivity_kcal_km2_year,
                'trafficability',       b.trafficability,
                'energy_multiplier',    b.energy_multiplier,
                -- seasonal modifiers
                'seasonal_spring',      b.seasonal_spring_modifier,
                'seasonal_summer',      b.seasonal_summer_modifier,
                'seasonal_autumn',      b.seasonal_autumn_modifier,
                'seasonal_winter',      b.seasonal_winter_modifier,
                'note_spring',          b.seasonal_spring_note,
                'note_summer',          b.seasonal_summer_note,
                'note_autumn',          b.seasonal_autumn_note,
                'note_winter',          b.seasonal_winter_note
            )
        ) AS feat
        FROM terrain_features tf
        JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
        LEFT JOIN biotopes b ON tf.biotope_id = b.id
        WHERE ST_Intersects(tf.geom, _bbox)
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- 2. RIVERS
--    Zoom < 9 → přeskočit (frontend řeší), ale funkce zvládne bbox filtr.
--    15k segmentů bez názvů → ukazujeme jen v malém bbox (zoom >= 9).
CREATE OR REPLACE FUNCTION get_rivers(
    west  float8,
    south float8,
    east  float8,
    north float8,
    zoom  int DEFAULT 10
)
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
AS $$
DECLARE
    _bbox geometry;
    _tol  float8;
    result json;
BEGIN
    _bbox := ST_MakeEnvelope(west, south, east, north, 4326);
    _tol  := CASE
        WHEN zoom >= 12 THEN 0.0001
        WHEN zoom >= 10 THEN 0.0003
        ELSE 0.0007
    END;

    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(feat), '[]'::json)
    ) INTO result
    FROM (
        SELECT json_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(
                ST_SimplifyPreserveTopology(r.geom, _tol)
            )::json,
            'properties', json_build_object(
                'id',         r.id,
                'name',       r.name,
                'permanence', r.permanence,
                'certainty',  r.certainty
            )
        ) AS feat
        FROM rivers r
        WHERE ST_Intersects(r.geom, _bbox)
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- 3. ECOTONES
--    Jen 6 záznamů — vrátíme všechny v bbox (bez simplifikace, jsou to linie).
CREATE OR REPLACE FUNCTION get_ecotones(
    west  float8,
    south float8,
    east  float8,
    north float8
)
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
AS $$
DECLARE
    _bbox geometry;
    result json;
BEGIN
    _bbox := ST_MakeEnvelope(west, south, east, north, 4326);

    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(feat), '[]'::json)
    ) INTO result
    FROM (
        SELECT json_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(e.geom)::json,
            'properties', json_build_object(
                'id',                e.id,
                'name',              e.name,
                'biotope_a_id',      e.biotope_a_id,
                'biotope_b_id',      e.biotope_b_id,
                'biotope_a_name',    ba.name,
                'biotope_b_name',    bb.name,
                'edge_effect_factor',e.edge_effect_factor,
                'human_relevance',   e.human_relevance,
                'seasonal_peaks',    e.seasonal_peaks,
                'certainty',         e.certainty,
                'source',            e.source
            )
        ) AS feat
        FROM ecotones e
        LEFT JOIN biotopes ba ON e.biotope_a_id = ba.id
        LEFT JOIN biotopes bb ON e.biotope_b_id = bb.id
        WHERE ST_Intersects(e.geom, _bbox)
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- 4. COASTLINE
--    Jeden polygon — rekonstruované pobřeží ~6200 BCE.
CREATE OR REPLACE FUNCTION get_coastline()
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
AS $$
DECLARE result json;
BEGIN
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', json_build_array(
            json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(
                    ST_SimplifyPreserveTopology(geom, 0.001)
                )::json,
                'properties', json_build_object(
                    'id',                id,
                    'name',              name,
                    'sea_level_offset_m',sea_level_offset_m,
                    'certainty',         certainty,
                    'source',            source
                )
            )
        )
    ) INTO result
    FROM coastline
    LIMIT 1;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- 5. ARCHAEOLOGICAL SITES
--    20 lokalit z Lake Flixton / Star Carr — vždy všechny (žádná bbox omezení).
--    Geometrie → centroid bodu pro marker.
CREATE OR REPLACE FUNCTION get_sites()
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
AS $$
DECLARE result json;
BEGIN
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(feat), '[]'::json)
    ) INTO result
    FROM (
        SELECT json_build_object(
            'type', 'Feature',
            'geometry', json_build_object(
                'type', 'Point',
                'coordinates', json_build_array(
                    round(ST_X(ST_Centroid(geom))::numeric, 6),
                    round(ST_Y(ST_Centroid(geom))::numeric, 6)
                )
            ),
            'properties', json_build_object(
                'id',             id,
                'name',           name,
                'lakescape_role', lakescape_role,
                'certainty',      certainty,
                'source',         source
            )
        ) AS feat
        FROM site_instances
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- ============================================================
-- Ověření: po spuštění otestujte v SQL Editoru:
--   SELECT get_coastline();
--   SELECT get_sites();
--   SELECT get_terrain(-2.5, 53.5, 0.1, 54.7, 8);
-- ============================================================

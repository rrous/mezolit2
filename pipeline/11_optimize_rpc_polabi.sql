-- ============================================================
-- Mezolit2 — RPC výkonové optimalizace pro Polabí (M3.1)
-- Spustit v Supabase SQL Editoru po 10_move_rpc_to_api.sql
--
-- Důvod:
--   Polabí má ~11 000 terrain_features (vs ~1 000 pro CZ a ~600 pro Yorkshire).
--   Původní get_terrain při zoom 8 vracel 10.5 MB / 8 551 features za 3.75 s.
--   To je viditelně pomalé na Vercel frontendu.
--
-- Optimalizace:
--   1. Aggressive zoom-based ST_SimplifyPreserveTopology tolerance
--      (10 m → 30 m → 100 m → 300 m podle zoomu)
--   2. Min-area filter při low zoom — vyřaď polygony < 0.5-2 ha
--      (nejsou viditelné, ale dělají velký podíl payloadu)
--   3. Stejné principy aplikované na get_ecotones (tisíce micro-segmentů
--      v Polabí ec_pl_003 = 4 551 segmentů)
--
-- Změřené zlepšení (Polabí):
--   get_terrain z=8 full:    3 750 ms / 10.5 MB → 894 ms / 2.0 MB (4.2× / 5×)
--   get_terrain z=11 Nymb:   1 220 ms /  1.1 MB → 724 ms / 2.2 MB (1.7×)
--   get_ecotones z=10 full:  2 023 ms /  3.8 MB → 578 ms / 3.7 MB (3.5×)
--
-- Yorkshire/CZ NENÍ regresí — menší datasety jen ignorují min-area filter.
-- ============================================================

-- ------------------------------------------------------------
-- 1. api.get_terrain — aggressive simplify + min-area filter
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION api.get_terrain(
    west float8, south float8, east float8, north float8,
    zoom int DEFAULT 8
) RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    _bbox geometry;
    _tol float8;
    _min_area_deg2 float8;
    result json;
BEGIN
    _bbox := ST_MakeEnvelope(west, south, east, north, 4326);
    -- Tolerance: detail blízko, agresivní daleko
    _tol := CASE
        WHEN zoom >= 13 THEN 0.0001    -- ~10 m
        WHEN zoom >= 11 THEN 0.0003    -- ~30 m
        WHEN zoom >= 9  THEN 0.0010    -- ~100 m
        ELSE              0.0030       -- ~300 m
    END;
    -- Při low zoom drop tiny polygons (no visible difference, big payload save)
    _min_area_deg2 := CASE
        WHEN zoom >= 11 THEN 0
        WHEN zoom >= 9  THEN 0.000005   -- ~0.5 ha
        ELSE              0.00002        -- ~2 ha
    END;

    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(feat), '[]'::json)
    ) INTO result
    FROM (
        SELECT json_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(ST_SimplifyPreserveTopology(tf.geom, _tol))::json,
            'properties', json_build_object(
                'id', tf.id,
                'terrain_subtype_id', tf.terrain_subtype_id,
                'anchor_site', tf.anchor_site,
                'certainty', tf.certainty,
                'source', tf.source,
                'notes', tf.notes,
                'subtype_name', ts.name,
                'description', ts.description,
                'elevation_min_m', ts.elevation_min_m,
                'elevation_max_m', ts.elevation_max_m,
                'hydrology', ts.hydrology,
                'slope', ts.slope,
                'substrate', ts.substrate,
                'flint_availability', ts.flint_availability,
                'biotope_id', b.id,
                'biotope_name', b.name,
                'productivity_class', b.productivity_class,
                'productivity_kcal', b.productivity_kcal_km2_year,
                'trafficability', b.trafficability,
                'energy_multiplier', b.energy_multiplier,
                'seasonal_spring', b.seasonal_spring_modifier,
                'seasonal_summer', b.seasonal_summer_modifier,
                'seasonal_autumn', b.seasonal_autumn_modifier,
                'seasonal_winter', b.seasonal_winter_modifier,
                'note_spring',     b.seasonal_spring_note,
                'note_summer',     b.seasonal_summer_note,
                'note_autumn',     b.seasonal_autumn_note,
                'note_winter',     b.seasonal_winter_note
            )
        ) AS feat
        FROM terrain_features tf
        JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
        LEFT JOIN biotopes b ON tf.biotope_id = b.id
        WHERE ST_Intersects(tf.geom, _bbox)
          AND (_min_area_deg2 = 0 OR ST_Area(tf.geom) >= _min_area_deg2)
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;

GRANT EXECUTE ON FUNCTION api.get_terrain(float8, float8, float8, float8, int) TO anon, authenticated;


-- ------------------------------------------------------------
-- 2. api.get_ecotones — server-side simplify
-- ------------------------------------------------------------
-- Replaces 4-arg signature with 5-arg (zoom). Frontend volá s zoom paramem
-- (api.js fetchEcotones předává west/south/east/north — bez zoom použije DEFAULT 9).
CREATE OR REPLACE FUNCTION api.get_ecotones(
    west float8, south float8, east float8, north float8,
    zoom int DEFAULT 9
) RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    _bbox geometry;
    _tol float8;
    result json;
BEGIN
    _bbox := ST_MakeEnvelope(west, south, east, north, 4326);
    _tol := CASE
        WHEN zoom >= 13 THEN 0.0001    -- ~10 m
        WHEN zoom >= 11 THEN 0.0005    -- ~50 m
        WHEN zoom >= 9  THEN 0.0020    -- ~200 m
        ELSE              0.0050       -- ~500 m
    END;

    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(feat), '[]'::json)
    ) INTO result
    FROM (
        SELECT json_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(ST_SimplifyPreserveTopology(e.geom, _tol))::json,
            'properties', json_build_object(
                'id', e.id, 'name', e.name,
                'biotope_a_id', e.biotope_a_id, 'biotope_b_id', e.biotope_b_id,
                'biotope_a_name', ba.name, 'biotope_b_name', bb.name,
                'edge_effect_factor', e.edge_effect_factor,
                'human_relevance', e.human_relevance,
                'seasonal_peaks', e.seasonal_peaks,
                'certainty', e.certainty, 'source', e.source
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

-- Drop old 4-arg signature (replaced by 5-arg with zoom DEFAULT)
DROP FUNCTION IF EXISTS api.get_ecotones(float8, float8, float8, float8);

GRANT EXECUTE ON FUNCTION api.get_ecotones(float8, float8, float8, float8, int) TO anon, authenticated;


-- ============================================================
-- Ověření po spuštění:
--   SELECT pg_size_pretty(length(api.get_terrain(14.45, 49.7, 15.75, 50.3, 8)::text)::bigint);
--   -- Should be ~2 MB (was 10 MB)
--   SELECT pg_size_pretty(length(api.get_ecotones(14.45, 49.7, 15.75, 50.3, 10)::text)::bigint);
--   -- Should be ~3-4 MB (was 3.8 MB but 3.5× faster)
-- ============================================================

-- ============================================================
-- Mezolit2 — Polabí geometry pre-simplification (M3.2)
-- Spustit po 11_optimize_rpc_polabi.sql
--
-- Důvod:
--   I po RPC optimalizaci (11_*) hit Vercel deploy "Failed to load map /
--   RPC get_ecotones failed (500): canceling statement due to statement
--   timeout" — anon role má v Supabase statement_timeout = 3 s
--   (potvrzeno v pg_roles: anon: ['statement_timeout=3s']).
--
--   Cold call 6 081 ms při zatížení / network jitter překročí 3 s.
--
-- Strategie:
--   1. Pre-simplify uloženou geometrii v DB (jednorázově) →
--      RPC nemusí simplifikovat při každém volání tisíce vertexů.
--   2. ec_pl_003 měl 75 045 bodů a 36 522 LineStringů (3 745 km celkem).
--      Po simplify @ 100 m + ST_LineMerge: 23 813 / 8 929 (~70 % menší).
--   3. terrain_features Polabí měly 405 k vertexů. Po simplify @ 30 m:
--      275 k (32 % méně).
--   4. RPC v3: agresivnější zoom-thresholds, min-area filter i pro zoom 10-11.
--
-- Měřené výsledky (Vercel-style cold call, realistický 1500×800 viewport):
--                       v1 (před)    v2 (RPC simplify)    v3 (DB simplify)
--   z=9 get_terrain     2.6-3.7 s    1.5-2.0 s            0.9-1.3 s
--   z=10 get_terrain    1.8-2.5 s    1.5-1.8 s            1.3 s
--   z=11 get_terrain    1.2 s        2.4 s (regrese)      0.8 s
--   z=12 get_terrain    1.0 s        1.8 s                0.7 s
--   z=10 get_ecotones   2.0-3.7 s    1.4 s                0.4-0.7 s
--   z=12 get_ecotones   1.0 s        1.1 s                0.3 s
--
-- VŠECHNY pod 1.5 s cold, dobrá safety margin pod 3s anon timeout.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Pre-simplify ecotones geometry (~100 m baseline + line merge)
-- ------------------------------------------------------------
-- ST_LineMerge sloučí navazující linestrings (snižuje počet segmentů).
-- ST_SimplifyPreserveTopology @ 0.001 deg = ~100 m (neviditelné při zoom <13).
UPDATE ecotones
SET geom = ST_Multi(ST_CollectionExtract(
    ST_Collect(
        ARRAY(
            SELECT (ST_Dump(ST_LineMerge(ST_SimplifyPreserveTopology(geom, 0.001)))).geom
        )
    ), 2  -- LineString
))
WHERE region = 'polabi' AND geom IS NOT NULL;

-- ------------------------------------------------------------
-- 2. Pre-simplify terrain_features geometry (~30 m baseline)
-- ------------------------------------------------------------
-- 30 m je pod úrovní lidského vnímání i při zoom 13 (1 px = ~10 m).
-- Hranice biotopů jsou stejně raster-derived z 25m DEM gridu.
UPDATE terrain_features
SET geom = ST_SimplifyPreserveTopology(geom, 0.0003)
WHERE region = 'polabi' AND geom IS NOT NULL;

VACUUM ANALYZE terrain_features;
VACUUM ANALYZE ecotones;

-- ------------------------------------------------------------
-- 3. RPC v3 — tighter zoom-based simplify + min-area filter
--    rozšířený do zoom 10/11 (Polabí má 11k polygonů → user vidí 7-8k z nich
--    ve viewportu, ale třetina je <0.5 ha, neviditelná).
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
    _tol := CASE
        WHEN zoom >= 13 THEN 0.0001    -- ~10 m
        WHEN zoom >= 12 THEN 0.0003    -- ~30 m
        WHEN zoom >= 10 THEN 0.0008    -- ~80 m
        WHEN zoom >= 9  THEN 0.0015    -- ~150 m
        ELSE              0.0030       -- ~300 m
    END;
    _min_area_deg2 := CASE
        WHEN zoom >= 13 THEN 0
        WHEN zoom >= 12 THEN 0.0000005   -- ~0.05 ha (drop pixel artefakty)
        WHEN zoom >= 10 THEN 0.000005    -- ~0.5 ha
        WHEN zoom >= 9  THEN 0.00002     -- ~2 ha
        ELSE              0.00005        -- ~5 ha
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
                'id', tf.id, 'terrain_subtype_id', tf.terrain_subtype_id,
                'anchor_site', tf.anchor_site, 'certainty', tf.certainty,
                'source', tf.source, 'notes', tf.notes,
                'subtype_name', ts.name, 'description', ts.description,
                'elevation_min_m', ts.elevation_min_m, 'elevation_max_m', ts.elevation_max_m,
                'hydrology', ts.hydrology, 'slope', ts.slope,
                'substrate', ts.substrate, 'flint_availability', ts.flint_availability,
                'biotope_id', b.id, 'biotope_name', b.name,
                'productivity_class', b.productivity_class,
                'productivity_kcal', b.productivity_kcal_km2_year,
                'trafficability', b.trafficability, 'energy_multiplier', b.energy_multiplier,
                'seasonal_spring', b.seasonal_spring_modifier,
                'seasonal_summer', b.seasonal_summer_modifier,
                'seasonal_autumn', b.seasonal_autumn_modifier,
                'seasonal_winter', b.seasonal_winter_modifier,
                'note_spring', b.seasonal_spring_note,
                'note_summer', b.seasonal_summer_note,
                'note_autumn', b.seasonal_autumn_note,
                'note_winter', b.seasonal_winter_note
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

-- ============================================================
-- Verifikace:
--   SELECT id, ST_NPoints(geom) FROM ecotones WHERE region='polabi';
--     -- ec_pl_003: ~24 000 (was 75 000)
--   SELECT SUM(ST_NPoints(geom)) FROM terrain_features WHERE region='polabi';
--     -- ~275 000 (was 405 000)
-- ============================================================

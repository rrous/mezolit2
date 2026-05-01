-- ============================================================
-- Mezolit2 — api.get_pollen_sites RPC (M3.3)
-- Spustit po 12_optimize_polabi_geometry.sql
--
-- Důvod:
--   Tabulka pollen_sites (přidaná v 00_polabi_schema.sql) obsahuje pylové
--   referenční profily (pro Polabí: Hrabanov 50.20°N, 14.83°E, AP 70 %,
--   7000-5500 cal BCE). Frontend potřebuje RPC, aby mohl tyto body zobrazit.
--
-- Konvence:
--   - Zrcadlí api.get_sites: bbox-volitelné, vrací GeoJSON FeatureCollection
--   - Vždy se vrací všechny vlastnosti relevantní pro panel detail (name,
--     taxa, AP%, age_min/max_cal_bce, elevation, notes, source)
--
-- Frontend integrace:
--   - frontend/src/api.js: fetchPollenSites() s cache:true
--   - frontend/src/layers.js: layerGroups.pollenSites + loadPollenSites()
--   - frontend/src/panel.js: renderPollen() pro side-panel detail
--   - frontend/src/map.js: legend section "Pylové profily"
-- ============================================================

CREATE OR REPLACE FUNCTION api.get_pollen_sites(
    west float8 DEFAULT NULL, south float8 DEFAULT NULL,
    east float8 DEFAULT NULL, north float8 DEFAULT NULL
) RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    _bbox geometry;
    result json;
BEGIN
    IF west IS NOT NULL THEN
        _bbox := ST_MakeEnvelope(west, south, east, north, 4326);
    END IF;

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
                    round(ST_X(geom)::numeric, 6),
                    round(ST_Y(geom)::numeric, 6)
                )
            ),
            'properties', json_build_object(
                'id', id,
                'name', name,
                'region', region,
                'age_min_cal_bce', age_min_cal_bce,
                'age_max_cal_bce', age_max_cal_bce,
                'tree_pollen_pct', tree_pollen_pct,
                'dominant_taxa', dominant_taxa,
                'elevation_m', elevation_m,
                'notes', notes,
                'source', source
            )
        ) AS feat
        FROM public.pollen_sites
        WHERE _bbox IS NULL OR ST_Intersects(geom, _bbox)
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;

GRANT EXECUTE ON FUNCTION api.get_pollen_sites(float8, float8, float8, float8) TO anon, authenticated;

-- Trigger PostgREST schema cache reload (Supabase auto-refreshes ~10s,
-- but explicit notify is faster)
NOTIFY pgrst, 'reload schema';

-- ============================================================
-- Verifikace:
--   SELECT api.get_pollen_sites();
--   -- → FeatureCollection s 1 záznamem (Hrabanov)
--   SELECT api.get_pollen_sites(14.45, 49.7, 15.75, 50.3);
--   -- → totéž (Hrabanov je v Polabí bboxu)
--   SELECT api.get_pollen_sites(-2.5, 53.5, 0.1, 54.7);
--   -- → prázdné (žádný Yorkshire pollen profile)
-- ============================================================

-- ============================================================
-- Mezolit2 — Přesun RPC funkcí z "public" do "api" schématu
-- Spustit v Supabase SQL Editoru po 08_security_hardening.sql
--
-- Cíl:
--   Umlčet lint "RLS Disabled in Public" na public.spatial_ref_sys.
--   Splinter lintuje jen schémata vystavená přes PostgREST (Exposed schemas).
--   Přesunem RPC do "api" schématu můžeme "public" z Exposed schemas odebrat.
--
-- Strategie:
--   - RPC funkce:    public.get_*  →  api.get_*
--   - Tabulky:       ZŮSTÁVAJÍ v public (FK, indexy, data se nesahá)
--   - Přístup:       RPC jsou SECURITY DEFINER + SET search_path = public, extensions
--                    → běží jako postgres a sahají na tabulky přes search_path
--   - Frontend:      frontend/src/api.js:28 volá /rest/v1/rpc/<name> bez schema
--                    → PostgREST resolvuje podle Exposed schemas (api je exposed)
--   - Po migraci:    v UI Supabase odebrat "public" z Exposed schemas
--
-- Předpoklady:
--   - Schema "api" je už v Exposed schemas (potvrzeno uživatelem).
--   - Extensions schema existuje (postgis tam NENÍ, ale search_path extensions
--     neublíží).
-- ============================================================

-- ------------------------------------------------------------
-- 0. Schema api (idempotentní)
-- ------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS api;

-- Minimální potřebné granty (PostgREST potřebuje USAGE, aby schema vůbec viděl)
GRANT USAGE ON SCHEMA api TO anon, authenticated, service_role;

-- ------------------------------------------------------------
-- 1. api.get_terrain
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION api.get_terrain(
    west  float8,
    south float8,
    east  float8,
    north float8,
    zoom  int DEFAULT 8
)
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, extensions
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
                'id',                   tf.id,
                'terrain_subtype_id',   tf.terrain_subtype_id,
                'anchor_site',          tf.anchor_site,
                'certainty',            tf.certainty,
                'source',               tf.source,
                'notes',                tf.notes,
                'subtype_name',         ts.name,
                'description',          ts.description,
                'elevation_min_m',      ts.elevation_min_m,
                'elevation_max_m',      ts.elevation_max_m,
                'hydrology',            ts.hydrology,
                'slope',                ts.slope,
                'substrate',            ts.substrate,
                'flint_availability',   ts.flint_availability,
                'biotope_id',           b.id,
                'biotope_name',         b.name,
                'productivity_class',   b.productivity_class,
                'productivity_kcal',    b.productivity_kcal_km2_year,
                'trafficability',       b.trafficability,
                'energy_multiplier',    b.energy_multiplier,
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
        FROM public.terrain_features tf
        JOIN public.terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
        LEFT JOIN public.biotopes b ON tf.biotope_id = b.id
        WHERE ST_Intersects(tf.geom, _bbox)
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- ------------------------------------------------------------
-- 2. api.get_rivers
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION api.get_rivers(
    west  float8,
    south float8,
    east  float8,
    north float8,
    zoom  int DEFAULT 10
)
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, extensions
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
        FROM public.rivers r
        WHERE ST_Intersects(r.geom, _bbox)
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- ------------------------------------------------------------
-- 3. api.get_ecotones
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION api.get_ecotones(
    west  float8,
    south float8,
    east  float8,
    north float8
)
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, extensions
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
        FROM public.ecotones e
        LEFT JOIN public.biotopes ba ON e.biotope_a_id = ba.id
        LEFT JOIN public.biotopes bb ON e.biotope_b_id = bb.id
        WHERE ST_Intersects(e.geom, _bbox)
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- ------------------------------------------------------------
-- 4. api.get_coastline
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION api.get_coastline()
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, extensions
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
    FROM public.coastline
    LIMIT 1;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- ------------------------------------------------------------
-- 5. api.get_sites
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION api.get_sites()
RETURNS json
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public, extensions
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
        FROM public.site_instances
    ) sub;

    RETURN COALESCE(result, '{"type":"FeatureCollection","features":[]}'::json);
END;
$$;


-- ------------------------------------------------------------
-- 6. Granty na EXECUTE — aby je PostgREST mohl volat jako anon/authenticated
-- ------------------------------------------------------------
GRANT EXECUTE ON FUNCTION api.get_terrain(float8, float8, float8, float8, int) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION api.get_rivers(float8, float8, float8, float8, int)  TO anon, authenticated;
GRANT EXECUTE ON FUNCTION api.get_ecotones(float8, float8, float8, float8)     TO anon, authenticated;
GRANT EXECUTE ON FUNCTION api.get_coastline()                                  TO anon, authenticated;
GRANT EXECUTE ON FUNCTION api.get_sites()                                      TO anon, authenticated;

-- ------------------------------------------------------------
-- 7. Drop starých funkcí z public
--    (staré public.get_* by jinak dál visely; navíc kdyby public zůstal v
--     Exposed schemas, PostgREST by mohl vybírat nejednoznačně.)
-- ------------------------------------------------------------
DROP FUNCTION IF EXISTS public.get_terrain(float8, float8, float8, float8, int);
DROP FUNCTION IF EXISTS public.get_rivers(float8, float8, float8, float8, int);
DROP FUNCTION IF EXISTS public.get_ecotones(float8, float8, float8, float8);
DROP FUNCTION IF EXISTS public.get_coastline();
DROP FUNCTION IF EXISTS public.get_sites();

-- ============================================================
-- Ověření v SQL Editoru:
--   SELECT api.get_coastline();
--   SELECT api.get_sites();
--   SELECT api.get_terrain(-2.5, 53.5, 0.1, 54.7, 8);
--   SELECT api.get_rivers(-0.6, 54.1, -0.2, 54.3, 10);
--   SELECT api.get_ecotones(-2.5, 53.5, 0.1, 54.7);
--
-- Kontrola přes REST (zvenčí):
--   curl -X POST "$SUPABASE_URL/rest/v1/rpc/get_sites" \
--        -H "apikey: $SUPABASE_ANON_KEY" \
--        -H "Content-Type: application/json" -d '{}'
--   → musí vrátit FeatureCollection.
-- ============================================================

-- ============================================================
-- PO TÉTO MIGRACI — KROK V UI SUPABASE:
--
--   Project Settings → API → Data API Settings → Exposed schemas
--   Hodnotu "public, api" změnit na jen "api"
--   (Extra search path NECHAT s "public" — RPC potřebují vidět tabulky.)
--
-- Po uložení:
--   - Advisors → Security Advisor → Rerun
--   - RLS Disabled in Public na spatial_ref_sys ZMIZÍ
--     (public už není exposed, splinter tento schema ignoruje).
-- ============================================================

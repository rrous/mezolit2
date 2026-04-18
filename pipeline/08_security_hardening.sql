-- ============================================================
-- Mezolit2 — Security hardening (Supabase linter fixes)
-- Spustit v Supabase SQL Editoru po 07_supabase_rpc.sql
-- ============================================================

-- ============================================================
-- 1. ENABLE RLS on all public tables + read-only policy for anon
--    Data jsou veřejná (read-only PoC mapa), takže povolíme SELECT pro anon.
-- ============================================================

-- terrain_subtypes
ALTER TABLE terrain_subtypes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access"
    ON terrain_subtypes FOR SELECT
    USING (true);

-- terrain_features
ALTER TABLE terrain_features ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access"
    ON terrain_features FOR SELECT
    USING (true);

-- biotopes
ALTER TABLE biotopes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access"
    ON biotopes FOR SELECT
    USING (true);

-- can_host
ALTER TABLE can_host ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access"
    ON can_host FOR SELECT
    USING (true);

-- ecotones
ALTER TABLE ecotones ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access"
    ON ecotones FOR SELECT
    USING (true);

-- rivers
ALTER TABLE rivers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access"
    ON rivers FOR SELECT
    USING (true);

-- coastline
ALTER TABLE coastline ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access"
    ON coastline FOR SELECT
    USING (true);

-- site_instances
ALTER TABLE site_instances ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read access"
    ON site_instances FOR SELECT
    USING (true);

-- spatial_ref_sys: PostGIS systémová tabulka vlastněná supabase_admin.
-- Co NEFUNGUJE na Supabase jako postgres role:
--   * ALTER TABLE ... ENABLE RLS          → must be owner of table
--   * ALTER TABLE ... OWNER TO postgres   → must be owner
--   * ALTER EXTENSION postgis SET SCHEMA  → postgis is not relocatable
--   * ALTER EXTENSION postgis DROP TABLE  → must be owner of extension
--
-- Co FUNGUJE:
--   Splinter lint 0013_rls_disabled_in_public kontroluje i granty přes
--   has_table_privilege(anon|authenticated, ...). Tato funkce respektuje
--   i dědičnost z role PUBLIC. Takže stačí odebrat SELECT grant:
--
--     - z role PUBLIC (zdroj dědění pro anon/authenticated)
--     - přímo z anon a authenticated (kdyby měly explicitní grant)
--
--   → has_table_privilege vrátí FALSE → lint zmizí.
--
-- Proč to nerozbije web:
--   - Frontend komunikuje VÝHRADNĚ přes RPC /rest/v1/rpc/get_* (frontend/src/api.js).
--   - Všechny RPC jsou SECURITY DEFINER → běží jako postgres/supabase_admin,
--     který má na spatial_ref_sys přímý přístup (ne přes PUBLIC dědičnost).
--   - PUBLIC roli NESAHÁME plošně (to minule rozbilo web) — jen tuhle jednu tabulku.
REVOKE ALL ON TABLE public.spatial_ref_sys FROM PUBLIC;
REVOKE ALL ON TABLE public.spatial_ref_sys FROM anon;
REVOKE ALL ON TABLE public.spatial_ref_sys FROM authenticated;

-- ============================================================
-- 2. FIX mutable search_path on all RPC functions
--    Přidáme SET search_path = public ke každé funkci.
-- ============================================================

-- get_terrain
ALTER FUNCTION get_terrain(float8, float8, float8, float8, int)
    SET search_path = public;

-- get_rivers
ALTER FUNCTION get_rivers(float8, float8, float8, float8, int)
    SET search_path = public;

-- get_ecotones
ALTER FUNCTION get_ecotones(float8, float8, float8, float8)
    SET search_path = public;

-- get_coastline
ALTER FUNCTION get_coastline()
    SET search_path = public;

-- get_sites
ALTER FUNCTION get_sites()
    SET search_path = public;

-- ============================================================
-- 3. PostGIS extension in public schema (WARN)
--    Řešeno v samostatném skriptu 09_move_postgis.sql.
-- ============================================================

-- ============================================================
-- Ověření: po spuštění zkontrolujte v Supabase Dashboard:
--   Security Advisor → žádné ERRORS
--   SELECT schemaname, tablename, rowsecurity
--     FROM pg_tables WHERE schemaname = 'public';
-- ============================================================

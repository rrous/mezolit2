"""
Mezolit2 PoC — Milestone 2: Database Verification Script
Connects to Supabase PostGIS and runs comprehensive checks.
"""

import os
import sys
import json
sys.stdout.reconfigure(encoding='utf-8')
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

# Star Carr / Lake Flixton landscape center (ADS postglacial_2013)
STAR_CARR_LAT = 54.214
STAR_CARR_LON = -0.403

# Yorkshire bbox
YORKSHIRE_BBOX = {"west": -2.5, "east": 0.1, "south": 53.5, "north": 54.7}

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def subsection(title):
    print(f"\n--- {title} ---")

def ok(msg):
    print(f"  [OK] {msg}")

def warn(msg):
    print(f"  [!!] {msg}")

def fail(msg):
    print(f"  [FAIL] {msg}")

def info(msg):
    print(f"  [..] {msg}")


def run_checks():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # =========================================================
    section("1. CONNECTIVITY & TABLE STATS")
    # =========================================================

    # PostGIS version
    cur.execute("SELECT PostGIS_Full_Version() as v")
    row = cur.fetchone()
    ok(f"PostGIS: {row['v'][:60]}...")

    # Table row counts + sizes
    tables = ["terrain_subtypes", "terrain_features", "biotopes",
              "can_host", "ecotones", "rivers", "coastline"]
    subsection("Row counts")
    counts = {}
    for t in tables:
        cur.execute(f"SELECT COUNT(*) as c FROM {t}")
        c = cur.fetchone()["c"]
        counts[t] = c
        status = ok if c > 0 else warn
        status(f"{t}: {c} rows")

    # DB size
    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database())) as s")
    info(f"Database size: {cur.fetchone()['s']}")

    # =========================================================
    section("2. SPATIAL DATA INTEGRITY")
    # =========================================================

    # Check SRIDs
    subsection("SRID checks (expect 4326)")
    geo_tables = [
        ("terrain_features", "geom"),
        ("ecotones", "geom"),
        ("rivers", "geom"),
        ("coastline", "geom"),
    ]
    for tbl, col in geo_tables:
        if counts.get(tbl, 0) == 0:
            warn(f"{tbl}: EMPTY — skipping")
            continue
        cur.execute(f"SELECT DISTINCT ST_SRID({col}) as srid FROM {tbl}")
        srids = [r["srid"] for r in cur.fetchall()]
        if srids == [4326]:
            ok(f"{tbl}.{col}: SRID=4326")
        else:
            fail(f"{tbl}.{col}: SRID={srids} (expected [4326])")

    # Geometry validity
    subsection("Geometry validity")
    for tbl, col in geo_tables:
        if counts.get(tbl, 0) == 0:
            continue
        cur.execute(f"""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN ST_IsValid({col}) THEN 1 ELSE 0 END) as valid,
                   SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) as nulls
            FROM {tbl}
        """)
        r = cur.fetchone()
        invalid = r["total"] - r["valid"]
        if invalid == 0 and r["nulls"] == 0:
            ok(f"{tbl}: all {r['total']} geometries valid, 0 nulls")
        else:
            warn(f"{tbl}: {invalid} invalid, {r['nulls']} null out of {r['total']}")

    # Bounding boxes — should be within Yorkshire area
    subsection("Bounding boxes (expect within Yorkshire region)")
    for tbl, col in geo_tables:
        if counts.get(tbl, 0) == 0:
            continue
        cur.execute(f"""
            SELECT ST_XMin(ext) as xmin, ST_YMin(ext) as ymin,
                   ST_XMax(ext) as xmax, ST_YMax(ext) as ymax
            FROM (SELECT ST_Extent({col}) as ext FROM {tbl}) t
        """)
        r = cur.fetchone()
        if r and r["xmin"] is not None:
            bbox_str = f"[{r['xmin']:.3f}, {r['ymin']:.3f}] → [{r['xmax']:.3f}, {r['ymax']:.3f}]"
            # Loose check: should overlap Yorkshire
            if (r["xmin"] < 1.0 and r["xmax"] > -3.0 and
                r["ymin"] < 55.0 and r["ymax"] > 53.0):
                ok(f"{tbl}: {bbox_str}")
            else:
                warn(f"{tbl}: bbox outside Yorkshire! {bbox_str}")

    # Empty geometries
    subsection("Empty geometries check")
    for tbl, col in geo_tables:
        if counts.get(tbl, 0) == 0:
            continue
        cur.execute(f"SELECT COUNT(*) as c FROM {tbl} WHERE ST_IsEmpty({col})")
        c = cur.fetchone()["c"]
        if c == 0:
            ok(f"{tbl}: no empty geometries")
        else:
            warn(f"{tbl}: {c} empty geometries")

    # =========================================================
    section("3. STAR CARR VERIFICATION")
    # =========================================================

    # Find terrain feature at Star Carr
    subsection(f"Features at Star Carr ({STAR_CARR_LAT}°N, {STAR_CARR_LON}°E)")
    cur.execute("""
        SELECT tf.id, tf.name, tf.terrain_subtype_id, tf.anchor_site,
               tf.certainty,
               ts.name as subtype_name, ts.hydrology, ts.substrate,
               ST_Area(tf.geom::geography) / 1e6 as area_km2,
               ST_Distance(
                   tf.geom::geography,
                   ST_SetSRID(ST_Point(%s, %s), 4326)::geography
               ) as dist_m
        FROM terrain_features tf
        JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
        ORDER BY ST_Distance(
            tf.geom,
            ST_SetSRID(ST_Point(%s, %s), 4326)
        )
        LIMIT 5
    """, (STAR_CARR_LON, STAR_CARR_LAT, STAR_CARR_LON, STAR_CARR_LAT))
    rows = cur.fetchall()
    for r in rows:
        marker = " *** ANCHOR" if r["anchor_site"] else ""
        info(f"{r['id']} ({r['subtype_name']}) — {r['dist_m']:.0f}m away, "
             f"{r['area_km2']:.1f} km², {r['certainty']}{marker}")

    # Check if Star Carr point falls inside a polygon
    cur.execute("""
        SELECT tf.id, tf.name, tf.terrain_subtype_id, ts.name as subtype_name
        FROM terrain_features tf
        JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
        WHERE ST_Contains(tf.geom, ST_SetSRID(ST_Point(%s, %s), 4326))
    """, (STAR_CARR_LON, STAR_CARR_LAT))
    containing = cur.fetchall()
    if containing:
        for r in containing:
            ok(f"Star Carr is INSIDE: {r['id']} ({r['subtype_name']})")
    else:
        warn("Star Carr point is NOT inside any terrain polygon!")

    # Expected: tst_001 (glacial_lake_basin) should be nearby
    cur.execute("""
        SELECT tf.id, tf.name, ts.name as subtype_name,
               ST_Distance(
                   tf.geom::geography,
                   ST_SetSRID(ST_Point(%s, %s), 4326)::geography
               ) as dist_m
        FROM terrain_features tf
        JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
        WHERE tf.terrain_subtype_id = 'tst_001'
        ORDER BY dist_m
        LIMIT 3
    """, (STAR_CARR_LON, STAR_CARR_LAT))
    rows = cur.fetchall()
    if rows:
        subsection("Nearest tst_001 (glacial_lake_basin) features")
        for r in rows:
            info(f"{r['id']} ({r['subtype_name']}): {r['dist_m']:.0f}m from Star Carr")
    else:
        warn("No tst_001 (glacial_lake_basin) features found!")

    # Ecotones near Star Carr
    subsection("Ecotones within 5km of Star Carr")
    cur.execute("""
        SELECT e.id, e.name, e.edge_effect_factor,
               ba.name as biotope_a, bb.name as biotope_b,
               ST_Distance(
                   e.geom::geography,
                   ST_SetSRID(ST_Point(%s, %s), 4326)::geography
               ) as dist_m
        FROM ecotones e
        LEFT JOIN biotopes ba ON e.biotope_a_id = ba.id
        LEFT JOIN biotopes bb ON e.biotope_b_id = bb.id
        WHERE ST_DWithin(
            e.geom::geography,
            ST_SetSRID(ST_Point(%s, %s), 4326)::geography,
            5000
        )
        ORDER BY dist_m
    """, (STAR_CARR_LON, STAR_CARR_LAT, STAR_CARR_LON, STAR_CARR_LAT))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            info(f"{r['id']}: {r['biotope_a']}/{r['biotope_b']} — "
                 f"{r['dist_m']:.0f}m, edge_effect={r['edge_effect_factor']}")
    else:
        warn("No ecotones within 5km of Star Carr")

    # Rivers near Star Carr
    subsection("Rivers within 3km of Star Carr")
    cur.execute("""
        SELECT r.id, r.name, r.permanence,
               ST_Distance(
                   r.geom::geography,
                   ST_SetSRID(ST_Point(%s, %s), 4326)::geography
               ) as dist_m
        FROM rivers r
        WHERE ST_DWithin(
            r.geom::geography,
            ST_SetSRID(ST_Point(%s, %s), 4326)::geography,
            3000
        )
        ORDER BY dist_m
        LIMIT 10
    """, (STAR_CARR_LON, STAR_CARR_LAT, STAR_CARR_LON, STAR_CARR_LAT))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            info(f"{r['name'] or r['id']}: {r['permanence']}, {r['dist_m']:.0f}m away")
    else:
        warn("No rivers within 3km of Star Carr")

    # =========================================================
    section("4. CAN_HOST GRAPH CONSISTENCY")
    # =========================================================

    # Every terrain_subtype should have at least 1 baseline biotope
    subsection("Terrain subtypes with baseline biotopes")
    cur.execute("""
        SELECT ts.id, ts.name,
               COUNT(ch.id) as baseline_count
        FROM terrain_subtypes ts
        LEFT JOIN can_host ch ON ts.id = ch.terrain_subtype_id AND ch.trigger = 'baseline'
        GROUP BY ts.id, ts.name
        ORDER BY ts.id
    """)
    rows = cur.fetchall()
    for r in rows:
        if r["baseline_count"] > 0:
            ok(f"{r['id']} ({r['name']}): {r['baseline_count']} baseline biotope(s)")
        else:
            fail(f"{r['id']} ({r['name']}): NO baseline biotope!")

    # Orphaned biotopes (not referenced by any can_host)
    subsection("Orphaned biotopes (no can_host edges)")
    cur.execute("""
        SELECT b.id, b.name
        FROM biotopes b
        LEFT JOIN can_host ch ON b.id = ch.biotope_id
        WHERE ch.id IS NULL
    """)
    orphans = cur.fetchall()
    if orphans:
        for r in orphans:
            warn(f"Orphaned: {r['id']} ({r['name']})")
    else:
        ok("No orphaned biotopes")

    # Quality modifier distribution
    subsection("CAN_HOST quality_modifier distribution")
    cur.execute("""
        SELECT trigger, COUNT(*) as cnt,
               MIN(quality_modifier) as qmin,
               AVG(quality_modifier) as qavg,
               MAX(quality_modifier) as qmax
        FROM can_host
        GROUP BY trigger
        ORDER BY trigger
    """)
    for r in cur.fetchall():
        info(f"trigger={r['trigger']}: {r['cnt']} edges, "
             f"quality [{r['qmin']:.2f} – {r['qavg']:.2f} – {r['qmax']:.2f}]")

    # =========================================================
    section("5. POLYGON NATURALNESS")
    # =========================================================

    subsection("Vertex density per terrain feature")
    cur.execute("""
        SELECT tf.id, tf.terrain_subtype_id, ts.name as subtype_name,
               ST_NPoints(tf.geom) as vertices,
               ST_Area(tf.geom::geography) / 1e6 as area_km2,
               ST_NPoints(tf.geom) / GREATEST(ST_Area(tf.geom::geography) / 1e6, 0.01) as verts_per_km2,
               ST_Perimeter(tf.geom::geography) / 1000 as perim_km
        FROM terrain_features tf
        JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
        ORDER BY area_km2 DESC
        LIMIT 15
    """)
    rows = cur.fetchall()
    info(f"{'ID':<12} {'Type':<25} {'Verts':>7} {'Area km²':>10} {'V/km²':>8} {'Perim km':>10}")
    for r in rows:
        info(f"{r['id']:<12} {r['subtype_name'][:25]:<25} {r['vertices']:>7} "
             f"{r['area_km2']:>10.1f} {r['verts_per_km2']:>8.1f} {r['perim_km']:>10.1f}")

    # Shape compactness (Polsby-Popper: 4π·Area/Perimeter²)
    # Perfect circle = 1.0, very irregular < 0.2
    subsection("Shape compactness (Polsby-Popper ratio)")
    cur.execute("""
        SELECT tf.terrain_subtype_id,
               COUNT(*) as cnt,
               AVG(4 * 3.14159 * ST_Area(tf.geom::geography) /
                   GREATEST(POWER(ST_Perimeter(tf.geom::geography), 2), 1)) as avg_pp,
               MIN(4 * 3.14159 * ST_Area(tf.geom::geography) /
                   GREATEST(POWER(ST_Perimeter(tf.geom::geography), 2), 1)) as min_pp,
               MAX(4 * 3.14159 * ST_Area(tf.geom::geography) /
                   GREATEST(POWER(ST_Perimeter(tf.geom::geography), 2), 1)) as max_pp
        FROM terrain_features tf
        GROUP BY tf.terrain_subtype_id
        ORDER BY tf.terrain_subtype_id
    """)
    rows = cur.fetchall()
    info("(< 0.3 = very irregular/natural, 0.3-0.6 = moderate, > 0.6 = suspiciously round)")
    for r in rows:
        marker = ""
        if r["avg_pp"] and r["avg_pp"] > 0.6:
            marker = " ← TOO ROUND?"
        elif r["avg_pp"] and r["avg_pp"] < 0.15:
            marker = " ← very fragmented"
        info(f"{r['terrain_subtype_id']}: avg={r['avg_pp']:.3f} "
             f"[{r['min_pp']:.3f}–{r['max_pp']:.3f}] n={r['cnt']}{marker}")

    # Simplified: sample a few small polygons for coordinate regularity
    subsection("Coordinate regularity check (sample small polygons)")
    cur.execute("""
        SELECT tf.id, ST_NPoints(tf.geom) as npts,
               ST_AsGeoJSON(ST_Centroid(tf.geom)) as centroid
        FROM terrain_features tf
        WHERE ST_NPoints(tf.geom) BETWEEN 20 AND 200
        ORDER BY RANDOM()
        LIMIT 5
    """)
    sample_ids = cur.fetchall()
    for s in sample_ids:
        # Get first 20 coords and check for grid-like patterns
        cur.execute("""
            SELECT ST_X((dp).geom) as x, ST_Y((dp).geom) as y
            FROM (SELECT ST_DumpPoints(geom) as dp FROM terrain_features WHERE id = %s) t
            LIMIT 20
        """, (s["id"],))
        pts = cur.fetchall()
        # Check if coordinates snap to a grid (DEM pixel boundaries)
        x_diffs = set()
        y_diffs = set()
        for i in range(1, len(pts)):
            dx = abs(pts[i]["x"] - pts[i-1]["x"])
            dy = abs(pts[i]["y"] - pts[i-1]["y"])
            if dx > 0.00001: x_diffs.add(round(dx, 6))
            if dy > 0.00001: y_diffs.add(round(dy, 6))
        unique_steps = len(x_diffs) + len(y_diffs)
        if unique_steps < 5:
            warn(f"{s['id']} ({s['npts']} pts): only {unique_steps} unique step sizes -> GRID ARTIFACT")
        else:
            ok(f"{s['id']} ({s['npts']} pts): {unique_steps} unique steps -> looks natural")

    # =========================================================
    section("6. COASTLINE VERIFICATION")
    # =========================================================

    if counts.get("coastline", 0) > 0:
        cur.execute("""
            SELECT id, name, sea_level_offset_m, certainty, source,
                   ST_Area(geom::geography) / 1e6 as area_km2,
                   ST_NPoints(geom) as vertices,
                   ST_XMin(geom) as xmin, ST_YMin(geom) as ymin,
                   ST_XMax(geom) as xmax, ST_YMax(geom) as ymax
            FROM coastline
        """)
        for r in cur.fetchall():
            info(f"ID: {r['id']}, name: {r['name']}")
            info(f"Sea level offset: {r['sea_level_offset_m']}m")
            info(f"Area: {r['area_km2']:.0f} km²")
            info(f"Vertices: {r['vertices']}")
            info(f"Bbox: [{r['xmin']:.3f}, {r['ymin']:.3f}] → [{r['xmax']:.3f}, {r['ymax']:.3f}]")
            info(f"Certainty: {r['certainty']}, Source: {r['source']}")

            if r["sea_level_offset_m"] == -25.0:
                ok("Sea level offset is -25m (correct for ~6200 BCE)")
            else:
                warn(f"Sea level offset is {r['sea_level_offset_m']}m, expected -25m")
    else:
        warn("No coastline data!")

    # =========================================================
    section("7. KB DATA QUALITY")
    # =========================================================

    # Biotope seasonal modifiers
    subsection("Seasonal modifiers (winter should generally be lower)")
    cur.execute("""
        SELECT id, name,
               seasonal_spring_modifier as spring,
               seasonal_summer_modifier as summer,
               seasonal_autumn_modifier as autumn,
               seasonal_winter_modifier as winter,
               productivity_class, productivity_kcal_km2_year
        FROM biotopes
        ORDER BY id
    """)
    rows = cur.fetchall()
    for r in rows:
        mods = f"Sp={r['spring']} Su={r['summer']} Au={r['autumn']} Wi={r['winter']}"
        marker = ""
        if r["winter"] is not None and r["summer"] is not None:
            if r["winter"] > r["summer"]:
                marker = " ← WINTER > SUMMER??"
            elif r["winter"] == r["summer"] == 1.0:
                marker = " ← all flat (no seasonality)"
        prod = f"prod={r['productivity_class']}"
        if r["productivity_kcal_km2_year"]:
            prod += f" ({r['productivity_kcal_km2_year']:.0f} kcal)"
        info(f"{r['id']} ({r['name'][:20]}): {mods} | {prod}{marker}")

    # Terrain subtypes coverage
    subsection("Terrain subtype area coverage")
    cur.execute("""
        SELECT ts.id, ts.name,
               COUNT(tf.id) as feature_count,
               COALESCE(SUM(ST_Area(tf.geom::geography) / 1e6), 0) as total_area_km2
        FROM terrain_subtypes ts
        LEFT JOIN terrain_features tf ON ts.id = tf.terrain_subtype_id
        GROUP BY ts.id, ts.name
        ORDER BY total_area_km2 DESC
    """)
    rows = cur.fetchall()
    total_area = sum(r["total_area_km2"] for r in rows)
    for r in rows:
        pct = (r["total_area_km2"] / total_area * 100) if total_area > 0 else 0
        info(f"{r['id']} ({r['name'][:30]}): {r['feature_count']} features, "
             f"{r['total_area_km2']:.0f} km² ({pct:.1f}%)")
    info(f"TOTAL: {total_area:.0f} km²")

    # Expected Yorkshire area ~ 12,000 km² (rough)
    if 5000 < total_area < 25000:
        ok(f"Total area {total_area:.0f} km² is in reasonable range for Yorkshire")
    else:
        warn(f"Total area {total_area:.0f} km² seems off for Yorkshire (expected ~8000-15000)")

    # =========================================================
    section("8. TERRAIN FEATURE TOPOLOGY")
    # =========================================================

    # Gaps and overlaps
    subsection("Overlap detection (sample — top 5 overlapping pairs)")
    cur.execute("""
        SELECT a.id as id_a, b.id as id_b,
               ST_Area(ST_Intersection(a.geom, b.geom)::geography) / 1e6 as overlap_km2
        FROM terrain_features a
        JOIN terrain_features b ON a.id < b.id
            AND ST_Intersects(a.geom, b.geom)
            AND NOT ST_Touches(a.geom, b.geom)
        ORDER BY overlap_km2 DESC
        LIMIT 5
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            if r["overlap_km2"] > 1.0:
                warn(f"Overlap: {r['id_a']} ∩ {r['id_b']} = {r['overlap_km2']:.2f} km²")
            else:
                info(f"Minor overlap: {r['id_a']} ∩ {r['id_b']} = {r['overlap_km2']:.2f} km²")
    else:
        ok("No polygon overlaps detected")

    # =========================================================
    section("9. SAMPLE SPATIAL QUERIES (API simulation)")
    # =========================================================

    # Simulate bbox query for Star Carr area
    subsection("Bbox query: Star Carr area (±0.1°)")
    sc_bbox = {
        "west": STAR_CARR_LON - 0.1,
        "east": STAR_CARR_LON + 0.1,
        "south": STAR_CARR_LAT - 0.05,
        "north": STAR_CARR_LAT + 0.05,
    }
    cur.execute("""
        SELECT tf.id, ts.name as subtype,
               ST_Area(ST_Intersection(
                   tf.geom,
                   ST_MakeEnvelope(%s, %s, %s, %s, 4326)
               )::geography) / 1e6 as visible_km2
        FROM terrain_features tf
        JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
        WHERE ST_Intersects(tf.geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
        ORDER BY visible_km2 DESC
    """, (sc_bbox["west"], sc_bbox["south"], sc_bbox["east"], sc_bbox["north"],
          sc_bbox["west"], sc_bbox["south"], sc_bbox["east"], sc_bbox["north"]))
    rows = cur.fetchall()
    info(f"Features in Star Carr bbox: {len(rows)}")
    for r in rows[:8]:
        info(f"  {r['id']} ({r['subtype']}): {r['visible_km2']:.2f} km² visible")

    # Full Yorkshire bbox query timing
    import time
    subsection("Full Yorkshire bbox query performance")
    t0 = time.time()
    cur.execute("""
        SELECT COUNT(*) as c
        FROM terrain_features
        WHERE ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
    """, (YORKSHIRE_BBOX["west"], YORKSHIRE_BBOX["south"],
          YORKSHIRE_BBOX["east"], YORKSHIRE_BBOX["north"]))
    c = cur.fetchone()["c"]
    dt = time.time() - t0
    info(f"Full bbox: {c} features in {dt*1000:.0f}ms")
    if dt < 1.0:
        ok(f"Query time {dt*1000:.0f}ms — fast enough for API")
    else:
        warn(f"Query time {dt*1000:.0f}ms — may be slow for API")

    # =========================================================
    section("10. SITE INSTANCES (Archaeological Sites)")
    # =========================================================

    try:
        cur.execute("SELECT COUNT(*) as c FROM site_instances")
        si_count = cur.fetchone()["c"]
        info(f"Total site_instances: {si_count}")

        if si_count > 0:
            cur.execute("SELECT COUNT(*) as c FROM site_instances WHERE geom IS NOT NULL")
            si_geom = cur.fetchone()["c"]
            if si_geom == si_count:
                ok(f"All {si_count} sites have geometry")
            else:
                warn(f"{si_geom}/{si_count} sites have geometry")

            subsection("Site instances by lakescape_role")
            cur.execute("""
                SELECT lakescape_role, COUNT(*) as c
                FROM site_instances
                GROUP BY lakescape_role ORDER BY c DESC
            """)
            for r in cur.fetchall():
                info(f"  {r['lakescape_role']}: {r['c']}")

            subsection("Star Carr site check")
            cur.execute("""
                SELECT id, name, lakescape_role, certainty,
                       ST_Area(geom::geography) as area_m2
                FROM site_instances
                WHERE name ILIKE '%star carr%'
            """)
            sc = cur.fetchone()
            if sc:
                ok(f"Star Carr found: {sc['id']}, role={sc['lakescape_role']}, "
                   f"area={sc['area_m2']:.0f} m2")
                if sc['lakescape_role'] == 'primary_camp':
                    ok("Star Carr lakescape_role = primary_camp")
                else:
                    warn(f"Star Carr lakescape_role = {sc['lakescape_role']} (expected primary_camp)")
            else:
                warn("Star Carr NOT FOUND in site_instances")

            subsection("Site bbox check (expect within Lake Flixton area)")
            cur.execute("""
                SELECT ST_XMin(ST_Collect(geom)) as xmin, ST_YMin(ST_Collect(geom)) as ymin,
                       ST_XMax(ST_Collect(geom)) as xmax, ST_YMax(ST_Collect(geom)) as ymax
                FROM site_instances WHERE geom IS NOT NULL
            """)
            bb = cur.fetchone()
            if bb and bb['xmin']:
                info(f"Sites bbox: [{bb['xmin']:.4f}, {bb['ymin']:.4f}] -> [{bb['xmax']:.4f}, {bb['ymax']:.4f}]")
                if -0.5 < bb['xmin'] and bb['xmax'] < -0.3 and 54.2 < bb['ymin'] and bb['ymax'] < 54.23:
                    ok("All sites within expected Lake Flixton area")
                else:
                    warn("Some sites outside expected Lake Flixton bbox")
        else:
            info("No site_instances — run 04_terrain.py with ADS data and 06_import_supabase.py")
    except Exception as e:
        warn(f"site_instances table not accessible: {e}")
        conn.rollback()

    # =========================================================
    section("SUMMARY")
    # =========================================================

    print(f"""
    Tables:     {', '.join(f'{t}={counts[t]}' for t in tables)}
    Total area: {total_area:.0f} km²
    PostGIS:    Working
    """)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    run_checks()

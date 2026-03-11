"""
Mezolit2 — Deep verification of P1, P2, P5, rivers-in-floodplains
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, options="-c statement_timeout=60000")
cur = conn.cursor(cursor_factory=RealDictCursor)

def section(t): print(f"\n{'='*60}\n  {t}\n{'='*60}")
def sub(t): print(f"\n--- {t} ---")
def ok(m): print(f"  [OK] {m}")
def warn(m): print(f"  [!!] {m}")
def fail(m): print(f"  [FAIL] {m}")
def info(m): print(f"  [..] {m}")

# =============================================================
section("P1: EKOTONY — detail")
# =============================================================

sub("All 6 ecotones — full record")
cur.execute("""
    SELECT e.id, e.name,
           e.biotope_a_id, ba.name as biotope_a_name,
           e.biotope_b_id, bb.name as biotope_b_name,
           e.edge_effect_factor, e.human_relevance,
           e.certainty, e.source, e.status,
           e.seasonal_peaks,
           CASE WHEN e.geom IS NULL THEN 'NULL'
                WHEN ST_IsValid(e.geom) THEN 'VALID'
                ELSE 'INVALID: ' || ST_IsValidReason(e.geom)
           END as geom_status,
           CASE WHEN e.geom IS NOT NULL THEN ST_NPoints(e.geom) ELSE 0 END as vertices,
           CASE WHEN e.geom IS NOT NULL THEN ST_Length(e.geom::geography) / 1000 ELSE 0 END as length_km,
           ST_SRID(e.geom) as srid
    FROM ecotones e
    LEFT JOIN biotopes ba ON e.biotope_a_id = ba.id
    LEFT JOIN biotopes bb ON e.biotope_b_id = bb.id
    ORDER BY e.id
""")
for r in cur.fetchall():
    status_marker = "[OK]" if r["geom_status"] == "VALID" else "[FAIL]"
    print(f"\n  {status_marker} {r['id']}: {r['name']}")
    info(f"  Biotopes: {r['biotope_a_id']} ({r['biotope_a_name']}) <-> {r['biotope_b_id']} ({r['biotope_b_name']})")
    info(f"  Geometry: {r['geom_status']}, SRID={r['srid']}, {r['vertices']} vertices, {r['length_km']:.1f} km")
    info(f"  edge_effect={r['edge_effect_factor']}, relevance={r['human_relevance']}")
    info(f"  certainty={r['certainty']}, source={r['source']}")
    info(f"  seasonal_peaks={r['seasonal_peaks']}")

sub("Where ARE the 3 valid ecotones?")
cur.execute("""
    SELECT e.id, e.name,
           ST_AsText(ST_Centroid(e.geom)) as centroid,
           ST_XMin(e.geom) as xmin, ST_YMin(e.geom) as ymin,
           ST_XMax(e.geom) as xmax, ST_YMax(e.geom) as ymax
    FROM ecotones e
    WHERE e.geom IS NOT NULL AND ST_IsValid(e.geom)
""")
for r in cur.fetchall():
    info(f"{r['id']}: centroid={r['centroid']}, bbox=[{r['xmin']:.3f},{r['ymin']:.3f}]->[{r['xmax']:.3f},{r['ymax']:.3f}]")

# =============================================================
section("P2: STAR CARR / LAKE FLIXTON polygon shape")
# =============================================================

sub("tf_star_carr geometry detail")
cur.execute("""
    SELECT id, name, terrain_subtype_id, anchor_site,
           ST_NPoints(geom) as vertices,
           ST_Area(geom::geography) / 1e6 as area_km2,
           ST_Perimeter(geom::geography) / 1000 as perim_km,
           4 * 3.14159 * ST_Area(geom::geography) / POWER(ST_Perimeter(geom::geography), 2) as polsby_popper,
           ST_XMin(geom) as xmin, ST_YMin(geom) as ymin,
           ST_XMax(geom) as xmax, ST_YMax(geom) as ymax,
           (ST_XMax(geom) - ST_XMin(geom)) / NULLIF(ST_YMax(geom) - ST_YMin(geom), 0) as aspect_ratio
    FROM terrain_features
    WHERE id = 'tf_star_carr'
""")
r = cur.fetchone()
if r:
    info(f"ID: {r['id']}, name: {r['name']}")
    info(f"Vertices: {r['vertices']}")
    info(f"Area: {r['area_km2']:.3f} km2")
    info(f"Perimeter: {r['perim_km']:.3f} km")
    pp = r['polsby_popper']
    info(f"Polsby-Popper: {pp:.3f} (1.0=circle, <0.5=natural)")
    info(f"Aspect ratio (W/H): {r['aspect_ratio']:.2f}")
    info(f"Bbox: [{r['xmin']:.5f}, {r['ymin']:.5f}] -> [{r['xmax']:.5f}, {r['ymax']:.5f}]")

    # Dump actual coordinates to see the shape
    sub("tf_star_carr vertex coordinates (all)")
    cur.execute("""
        SELECT ST_X((dp).geom) as x, ST_Y((dp).geom) as y,
               (dp).path[1] as ring, (dp).path[2] as pt_idx
        FROM (SELECT ST_DumpPoints(geom) as dp FROM terrain_features WHERE id = 'tf_star_carr') t
        ORDER BY ring, pt_idx
    """)
    pts = cur.fetchall()
    info(f"Total points: {len(pts)}")
    for p in pts:
        info(f"  [{p['pt_idx']:3d}] ({p['x']:.6f}, {p['y']:.6f})")

# =============================================================
section("P5: HUGE POLYGONS — what are they?")
# =============================================================

sub("Top 10 largest terrain features")
cur.execute("""
    SELECT tf.id, ts.name as subtype, ts.id as subtype_id,
           ST_NPoints(tf.geom) as vertices,
           ST_Area(tf.geom::geography) / 1e6 as area_km2,
           ST_Perimeter(tf.geom::geography) / 1000 as perim_km,
           ST_NumGeometries(tf.geom) as num_parts,
           ST_XMin(tf.geom) as xmin, ST_YMin(tf.geom) as ymin,
           ST_XMax(tf.geom) as xmax, ST_YMax(tf.geom) as ymax,
           (ST_XMax(tf.geom) - ST_XMin(tf.geom)) * 111 as width_km_approx,
           (ST_YMax(tf.geom) - ST_YMin(tf.geom)) * 111 as height_km_approx
    FROM terrain_features tf
    JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
    ORDER BY area_km2 DESC
    LIMIT 10
""")
rows = cur.fetchall()
info(f"{'ID':<14} {'Subtype':<12} {'Area km2':>10} {'Verts':>8} {'Parts':>6} {'W km':>7} {'H km':>7}")
for r in rows:
    marker = ""
    if r["area_km2"] > 1000:
        marker = " <<< VERY LARGE"
    elif r["area_km2"] > 500:
        marker = " << large"
    info(f"{r['id']:<14} {r['subtype_id']:<12} {r['area_km2']:>10.1f} {r['vertices']:>8} "
         f"{r['num_parts']:>6} {r['width_km_approx']:>7.1f} {r['height_km_approx']:>7.1f}{marker}")

sub("Feature count and area distribution by subtype")
cur.execute("""
    SELECT ts.id, ts.name,
           COUNT(tf.id) as cnt,
           MIN(ST_Area(tf.geom::geography) / 1e6) as min_km2,
           AVG(ST_Area(tf.geom::geography) / 1e6) as avg_km2,
           MAX(ST_Area(tf.geom::geography) / 1e6) as max_km2,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ST_Area(tf.geom::geography) / 1e6) as median_km2
    FROM terrain_features tf
    JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
    GROUP BY ts.id, ts.name
    ORDER BY max_km2 DESC
""")
rows = cur.fetchall()
info(f"{'Subtype':<12} {'Name':<30} {'Cnt':>5} {'Min':>8} {'Median':>8} {'Avg':>8} {'Max':>8}")
for r in rows:
    info(f"{r['id']:<12} {r['name'][:30]:<30} {r['cnt']:>5} {r['min_km2']:>8.1f} "
         f"{r['median_km2']:>8.1f} {r['avg_km2']:>8.1f} {r['max_km2']:>8.1f}")

sub("How many terrain features > 100 km2?")
cur.execute("""
    SELECT ts.id, ts.name, COUNT(*) as big_ones
    FROM terrain_features tf
    JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
    WHERE ST_Area(tf.geom::geography) / 1e6 > 100
    GROUP BY ts.id, ts.name
    ORDER BY big_ones DESC
""")
for r in cur.fetchall():
    warn(f"{r['id']} ({r['name']}): {r['big_ones']} features > 100 km2")

# Is the 1297 km2 limestone plateau one single connected polygon or multipolygon?
sub("tf_0384 (1297 km2) — is it one piece or many holes?")
cur.execute("""
    SELECT ST_GeometryType(geom) as gtype,
           ST_NumInteriorRings(geom) as holes,
           ST_NRings(geom) as total_rings
    FROM terrain_features
    WHERE id = 'tf_0384'
""")
r = cur.fetchone()
if r:
    info(f"Type: {r['gtype']}, Interior rings (holes): {r['holes']}, Total rings: {r['total_rings']}")

# =============================================================
section("RIVERS IN FLOODPLAINS check")
# =============================================================

sub("Do major rivers (by length) lie within tst_002 (ricni niva)?")
cur.execute("""
    SELECT r.id, r.name, r.permanence,
           ST_Length(r.geom::geography) / 1000 as length_km
    FROM rivers r
    ORDER BY ST_Length(r.geom::geography) DESC
    LIMIT 20
""")
long_rivers = cur.fetchall()
info(f"Top 20 longest rivers:")
for rv in long_rivers:
    info(f"  {rv['name'] or rv['id']}: {rv['length_km']:.1f} km, {rv['permanence']}")

sub("River segments inside tst_002 (ricni niva) vs outside")
cur.execute("""
    WITH top_rivers AS (
        SELECT id, name, geom, ST_Length(geom::geography) as total_len
        FROM rivers
        ORDER BY ST_Length(geom::geography) DESC
        LIMIT 20
    ),
    overlap AS (
        SELECT tr.id, tr.name, tr.total_len,
               COALESCE(SUM(
                   ST_Length(ST_Intersection(tr.geom, tf.geom)::geography)
               ), 0) as len_in_niva
        FROM top_rivers tr
        LEFT JOIN terrain_features tf ON tf.terrain_subtype_id = 'tst_002'
            AND ST_Intersects(tr.geom, tf.geom)
        GROUP BY tr.id, tr.name, tr.total_len
    )
    SELECT id, name,
           total_len / 1000 as total_km,
           len_in_niva / 1000 as in_niva_km,
           ROUND((100.0 * len_in_niva / GREATEST(total_len, 1))::numeric, 1) as pct_in_niva
    FROM overlap
    ORDER BY total_km DESC
""")
rows = cur.fetchall()
info(f"{'River':<25} {'Total km':>10} {'In niva km':>12} {'% in niva':>10}")
for r in rows:
    marker = ""
    if float(r["pct_in_niva"]) < 30:
        marker = " ← mostly outside floodplain!"
    info(f"{(r['name'] or r['id'])[:25]:<25} {r['total_km']:>10.1f} {r['in_niva_km']:>12.1f} {r['pct_in_niva']:>9}%{marker}")

sub("What terrain types do long rivers actually cross?")
cur.execute("""
    WITH top5 AS (
        SELECT id, name, geom
        FROM rivers
        ORDER BY ST_Length(geom::geography) DESC
        LIMIT 5
    )
    SELECT r.name as river, ts.id as terrain, ts.name as terrain_name,
           SUM(ST_Length(ST_Intersection(r.geom, tf.geom)::geography)) / 1000 as km_in_type
    FROM top5 r
    JOIN terrain_features tf ON ST_Intersects(r.geom, tf.geom)
    JOIN terrain_subtypes ts ON tf.terrain_subtype_id = ts.id
    GROUP BY r.name, ts.id, ts.name
    ORDER BY r.name, km_in_type DESC
""")
rows = cur.fetchall()
current_river = None
for r in rows:
    if r["river"] != current_river:
        current_river = r["river"]
        print(f"\n  River: {current_river}")
    info(f"  {r['terrain']:<10} ({r['terrain_name'][:30]}): {r['km_in_type']:.1f} km")

conn.close()
print("\n\nDone.")

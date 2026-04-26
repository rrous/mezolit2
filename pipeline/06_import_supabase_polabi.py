"""
Import Polabí processed GeoJSON data into Supabase PostGIS (same DB as
Yorkshire/CZ).

IMPORTANT: Only deletes/replaces Polabí-prefixed records (region = 'polabi'
OR id LIKE 'tf_pl_%' / 'rv_pl_%'). Yorkshire + CZ data is preserved.

Imports:
  - terrain_features_with_biotopes_polabi.geojson → terrain_features (region='polabi')
  - ecotones_polabi.geojson                       → ecotones (UPDATE geom on existing KB rows)
  - rivers_polabi.geojson                         → rivers (region='polabi')
  - sites_polabi.geojson    (optional)            → archaeological_sites
  - pollen_sites_polabi.geojson                   → pollen_sites (also via 01c_seed)

Prerequisites:
  - 00_polabi_schema.sql applied (provides biotope_rules / pollen_sites / archaeological_sites + region column)
  - 01c_seed_kb_data_polabi.py run (terrain_subtypes / biotopes / can_host / ecotones KB rows)
  - 04_terrain_polabi.py + 05_kb_rules_polabi.py finished successfully

Usage:
  python pipeline/06_import_supabase_polabi.py
  python pipeline/06_import_supabase_polabi.py --dry-run   # validate only, no commit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Create .env from .env.example")
    sys.exit(1)

DATA_DIR = ROOT / "data" / "processed" / "polabi"


def load_geojson(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        print(f"  WARNING: {filename} not found, skipping")
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"  Loaded {filename}: {len(data['features'])} features")
    return data


# ---------------------------------------------------------------------------
# Terrain features
# ---------------------------------------------------------------------------

def import_terrain_features(cur, gj):
    if not gj:
        return
    cur.execute("DELETE FROM terrain_features WHERE id LIKE 'tf_pl_%' OR region = 'polabi'")
    print(f"  Deleted {cur.rowcount} existing Polabí terrain_features")

    count = 0
    skipped = 0
    for feature in gj["features"]:
        props = feature["properties"]
        geom = feature["geometry"]
        if geom is None:
            skipped += 1
            continue

        # Schema expects POLYGON; flatten MultiPolygon → largest ring
        if geom["type"] == "MultiPolygon":
            coords_list = geom["coordinates"]
            if len(coords_list) == 1:
                geom = {"type": "Polygon", "coordinates": coords_list[0]}
            else:
                largest = max(coords_list, key=lambda c: len(c[0]) if c else 0)
                geom = {"type": "Polygon", "coordinates": largest}

        if geom["type"] == "GeometryCollection":
            polys = [g for g in geom.get("geometries", [])
                     if g["type"] in ("Polygon", "MultiPolygon")]
            if not polys:
                skipped += 1
                continue
            geom = polys[0]
            if geom["type"] == "MultiPolygon":
                geom = {"type": "Polygon", "coordinates": geom["coordinates"][0]}

        if geom["type"] != "Polygon":
            skipped += 1
            continue

        geom_json = json.dumps(geom)
        feature_id = props.get("id", f"tf_pl_{count+1:04d}")

        cur.execute("""
            INSERT INTO terrain_features (
                id, name, terrain_subtype_id, biotope_id, geom,
                anchor_site, notes, certainty, source, region
            ) VALUES (
                %s, %s, %s, %s,
                ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                %s, %s, %s, %s, 'polabi'
            )
            ON CONFLICT (id) DO UPDATE SET
                terrain_subtype_id = EXCLUDED.terrain_subtype_id,
                biotope_id = EXCLUDED.biotope_id,
                geom = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                certainty = EXCLUDED.certainty,
                source = EXCLUDED.source,
                region = 'polabi'
        """, (
            feature_id,
            props.get("name"),
            props.get("terrain_subtype_id"),
            props.get("biotope_id"),
            geom_json,
            bool(props.get("anchor_site", False)),
            props.get("notes"),
            props.get("certainty", "INFERENCE"),
            props.get("source", "Polabí pipeline (DEM + DIBAVOD)"),
            geom_json,
        ))
        count += 1

    if skipped:
        print(f"  Skipped {skipped} non-polygon features")
    print(f"  Imported {count} Polabí terrain_features")


# ---------------------------------------------------------------------------
# Ecotones
# ---------------------------------------------------------------------------

def import_ecotones(cur, gj):
    if not gj:
        return
    n_updated = 0
    n_inserted = 0

    for feature in gj["features"]:
        props = feature["properties"]
        geom = feature["geometry"]
        if geom is None:
            continue

        # Generic ecotone has biotope_a_id='multiple' which violates FK
        bt_a = props.get("biotope_a_id")
        bt_b = props.get("biotope_b_id")
        eco_id = props.get("id")
        if bt_a == "multiple" or bt_b == "multiple":
            print(f"    Skipping {eco_id} (generic — no FK)")
            continue

        # Schema expects MULTILINESTRING; coerce LineString → MultiLineString
        if geom["type"] == "LineString":
            geom = {"type": "MultiLineString", "coordinates": [geom["coordinates"]]}
        if geom["type"] != "MultiLineString":
            print(f"    Skipping {eco_id}: geometry {geom['type']} != MultiLineString")
            continue

        geom_json = json.dumps(geom)

        # Try UPDATE existing KB row (created by 01c_seed)
        cur.execute("""
            UPDATE ecotones
            SET geom = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                certainty = COALESCE(%s, certainty),
                source = COALESCE(%s, source),
                region = 'polabi'
            WHERE id = %s
        """, (geom_json, props.get("certainty"), props.get("source"), eco_id))
        if cur.rowcount > 0:
            n_updated += 1
        else:
            cur.execute("""
                INSERT INTO ecotones (
                    id, name, biotope_a_id, biotope_b_id, geom,
                    edge_effect_factor, human_relevance,
                    certainty, source, status, region
                ) VALUES (
                    %s, %s, %s, %s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                    %s, %s, %s, %s, 'VALID', 'polabi'
                )
            """, (
                eco_id, props.get("name"), bt_a, bt_b, geom_json,
                props.get("edge_effect_factor"), props.get("human_relevance"),
                props.get("certainty", "INFERENCE"),
                props.get("source", "Polabí ecotone analysis"),
            ))
            n_inserted += 1

    print(f"  Ecotones: {n_updated} updated (geom added to KB rows), {n_inserted} inserted")


# ---------------------------------------------------------------------------
# Rivers
# ---------------------------------------------------------------------------

def import_rivers(cur, gj):
    if not gj:
        return
    cur.execute("DELETE FROM rivers WHERE id LIKE 'rv_pl_%' OR region = 'polabi'")
    print(f"  Deleted {cur.rowcount} existing Polabí rivers")

    count = 0
    for feature in gj["features"]:
        props = feature["properties"]
        geom = feature["geometry"]
        if geom is None:
            continue
        base_id = props.get("id", f"rv_pl_{count+1:04d}")

        if geom["type"] == "LineString":
            line_geoms = [geom]
        elif geom["type"] == "MultiLineString":
            line_geoms = [{"type": "LineString", "coordinates": c}
                          for c in geom["coordinates"]]
        else:
            continue

        for sub_idx, gline in enumerate(line_geoms):
            seg_id = base_id if len(line_geoms) == 1 else f"{base_id}_{sub_idx}"
            cur.execute("""
                INSERT INTO rivers (
                    id, name, geom, permanence, certainty, source, region
                ) VALUES (
                    %s, %s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                    %s, %s, %s, 'polabi'
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    geom = EXCLUDED.geom,
                    permanence = EXCLUDED.permanence,
                    certainty = EXCLUDED.certainty,
                    source = EXCLUDED.source,
                    region = 'polabi'
            """, (
                seg_id,
                props.get("name"),
                json.dumps(gline),
                props.get("permanence", "permanent"),
                props.get("certainty", "INFERENCE"),
                props.get("source", "DIBAVOD A01"),
            ))
            count += 1
    print(f"  Imported {count} Polabí river segments")


# ---------------------------------------------------------------------------
# Archaeological sites (optional — file may not exist yet)
# ---------------------------------------------------------------------------

def import_archaeological_sites(cur, gj):
    if not gj:
        return
    cur.execute("DELETE FROM archaeological_sites WHERE region = 'polabi'")
    print(f"  Deleted {cur.rowcount} existing Polabí archaeological_sites")

    count = 0
    for i, feature in enumerate(gj["features"], start=1):
        props = feature["properties"]
        geom = feature["geometry"]
        if geom is None or geom["type"] != "Point":
            continue
        lon, lat = geom["coordinates"][:2]

        cur.execute("""
            INSERT INTO archaeological_sites (
                id, name, region, geom,
                period, site_type, elevation_m, distance_to_water_m,
                ident_cely, katastr, certainty, source, status
            ) VALUES (
                %s, %s, 'polabi',
                ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                %s, %s, %s, %s,
                %s, %s, %s, %s, 'VALID'
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                geom = EXCLUDED.geom,
                period = EXCLUDED.period,
                site_type = EXCLUDED.site_type,
                elevation_m = EXCLUDED.elevation_m,
                distance_to_water_m = EXCLUDED.distance_to_water_m,
                source = EXCLUDED.source
        """, (
            props.get("id", f"as_pl_{i:04d}"),
            props.get("name") or props.get("ident_cely") or props.get("katastr"),
            lon, lat,
            props.get("period"), props.get("site_type"),
            props.get("elevation_m"), props.get("distance_to_water_m"),
            props.get("ident_cely"), props.get("katastr"),
            props.get("certainty", "DIRECT"),
            props.get("source", "AMCR digiarchiv"),
        ))
        count += 1
    print(f"  Imported {count} Polabí archaeological_sites")


# ---------------------------------------------------------------------------
# Pollen sites (geometry — already inserted by 01c_seed_kb_data_polabi)
# ---------------------------------------------------------------------------

def verify_pollen_sites(cur, gj):
    if not gj:
        return
    n_in_db = 0
    for feature in gj["features"]:
        ps_id = feature["properties"].get("id")
        if ps_id:
            cur.execute("SELECT 1 FROM pollen_sites WHERE id = %s AND region = 'polabi'", (ps_id,))
            if cur.fetchone():
                n_in_db += 1
    print(f"  Verified {n_in_db}/{len(gj['features'])} Polabí pollen_sites already in DB")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_counts(cur):
    print("\n" + "=" * 60)
    print("Database verification")
    print("=" * 60)

    queries = [
        ("terrain_features", "WHERE region = 'polabi'"),
        ("rivers",            "WHERE region = 'polabi'"),
        ("ecotones",          "WHERE region = 'polabi' AND geom IS NOT NULL"),
        ("ecotones",          "WHERE region = 'polabi'"),
        ("pollen_sites",      "WHERE region = 'polabi'"),
        ("archaeological_sites", "WHERE region = 'polabi'"),
        ("biotope_rules",     "WHERE region = 'polabi'"),
        ("terrain_subtypes",  "WHERE id LIKE 'tst_pl_%'"),
        ("biotopes",          "WHERE id LIKE 'bt_pl_%'"),
        ("can_host",          "WHERE biotope_id LIKE 'bt_pl_%'"),
    ]
    for table, where in queries:
        cur.execute(f"SELECT COUNT(*) FROM {table} {where}")
        print(f"  {table:24s} {where:50s}: {cur.fetchone()[0]:>6}")

    # Sanity: bbox of imported terrain
    cur.execute("""
        SELECT ST_AsText(ST_Envelope(ST_Collect(geom)))
        FROM terrain_features WHERE region = 'polabi'
    """)
    bbox = cur.fetchone()[0]
    if bbox:
        print(f"\n  Polabí terrain_features bbox: {bbox[:80]}…")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Polabí GeoJSON → Supabase import")
    ap.add_argument("--dry-run", action="store_true",
                    help="Run all steps but rollback at the end")
    args = ap.parse_args()

    print("=" * 60)
    print("Mezolit2 — Import Polabí GeoJSON → PostGIS")
    print("=" * 60)

    print("\nLoading GeoJSON files...")
    terrain_gj = load_geojson("terrain_features_with_biotopes_polabi.geojson")
    if terrain_gj is None:
        # Fallback if 05 hasn't been run
        terrain_gj = load_geojson("terrain_features_polabi.geojson")
    ecotones_gj = load_geojson("ecotones_polabi.geojson")
    rivers_gj = load_geojson("rivers_polabi.geojson")
    sites_gj = load_geojson("sites_polabi.geojson")  # optional
    pollen_gj = load_geojson("pollen_sites_polabi.geojson")

    if not any([terrain_gj, rivers_gj]):
        print("\nERROR: missing required GeoJSON files. Run 04_terrain_polabi.py + 05_kb_rules_polabi.py first.")
        sys.exit(1)

    print(f"\nConnecting to database ({DATABASE_URL.split('@')[1].split('/')[0]})...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        print("\nImporting Polabí terrain_features...")
        import_terrain_features(cur, terrain_gj)

        print("Importing Polabí ecotones (UPDATE existing KB rows)...")
        import_ecotones(cur, ecotones_gj)

        print("Importing Polabí rivers...")
        import_rivers(cur, rivers_gj)

        print("Importing Polabí archaeological_sites (if any)...")
        import_archaeological_sites(cur, sites_gj)

        print("Verifying pollen_sites...")
        verify_pollen_sites(cur, pollen_gj)

        if args.dry_run:
            conn.rollback()
            print("\n--dry-run: rolled back. Re-run without --dry-run to commit.")
        else:
            conn.commit()
            print("\nAll Polabí data committed successfully.")

        verify_counts(cur)

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    print(f"\nDone! Polabí data in Supabase.")
    print(f"  Frontend: open http://localhost:5173/?region=polabi")
    print(f"  (after frontend/src/config.js is updated to support region=polabi)")


if __name__ == "__main__":
    main()

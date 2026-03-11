"""
Import processed GeoJSON data into Supabase PostGIS.

Imports:
  - terrain_features_with_biotopes.geojson → terrain_features
  - ecotones.geojson → ecotones (updates geometry on existing KB rows)
  - rivers_yorkshire.geojson → rivers
  - coastline_6200bce.geojson → coastline

Prerequisite: Run 01_seed_kb_data.py first (populates KB tables).

Usage:
    python 06_import_supabase.py
"""

import json
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Create .env from .env.example")
    sys.exit(1)

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')


def load_geojson(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"  WARNING: {filename} not found, skipping")
        return None
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    print(f"  Loaded {filename}: {len(data['features'])} features")
    return data


def import_terrain_features(cur, geojson):
    """Import terrain features with biotope assignments."""
    if not geojson:
        return

    # Clear dependent tables first (FK constraints), then terrain features
    cur.execute("DELETE FROM site_instances")
    cur.execute("DELETE FROM terrain_features")

    count = 0
    for feature in geojson['features']:
        props = feature['properties']
        geom = feature['geometry']

        # Normalize MultiPolygon → largest Polygon (schema expects POLYGON)
        if geom['type'] == 'MultiPolygon':
            # Pick the largest polygon by coordinate count (approx area proxy)
            coords_list = geom['coordinates']
            if len(coords_list) == 1:
                geom = {'type': 'Polygon', 'coordinates': coords_list[0]}
            else:
                largest = max(coords_list, key=lambda c: len(c[0]) if c else 0)
                geom = {'type': 'Polygon', 'coordinates': largest}

        geom_json = json.dumps(geom)

        cur.execute("""
            INSERT INTO terrain_features (
                id, name, terrain_subtype_id, biotope_id, geom,
                anchor_site, notes, certainty, source
            ) VALUES (
                %s, %s, %s, %s,
                ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                %s, %s, %s, %s
            )
        """, (
            props.get('id', f'tf_{count:04d}'),
            props.get('name'),
            props.get('terrain_subtype_id'),
            props.get('biotope_id'),
            geom_json,
            props.get('anchor_site', False),
            props.get('notes'),
            props.get('certainty', 'INFERENCE'),
            props.get('source', 'DEM classification'),
        ))
        count += 1

    print(f"  Imported {count} terrain features")


def import_ecotones(cur, geojson):
    """Update ecotone rows with merged geometry (one feature per ecotone type)."""
    if not geojson:
        return

    # Clean up legacy segment entries from previous pipeline runs
    cur.execute("DELETE FROM ecotones WHERE id LIKE '%\\_seg\\_%'")
    cleaned = cur.rowcount
    if cleaned > 0:
        print(f"  Cleaned {cleaned} legacy ecotone segment rows")

    count_updated = 0
    count_not_found = 0

    for feature in geojson['features']:
        props = feature['properties']
        geom_json = json.dumps(feature['geometry'])
        eco_id = props.get('id')

        # Update existing KB row with geometry + optional source override
        cur.execute("""
            UPDATE ecotones
            SET geom = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                certainty = COALESCE(%s, certainty),
                source = COALESCE(%s, source)
            WHERE id = %s
        """, (geom_json, props.get('certainty'), props.get('source'), eco_id))

        if cur.rowcount > 0:
            count_updated += 1
        else:
            print(f"  WARNING: Ecotone {eco_id} not found in DB (run 01_seed_kb_data.py first)")
            count_not_found += 1

    print(f"  Ecotones: {count_updated} updated, {count_not_found} not found")


def import_rivers(cur, geojson):
    """Import river features."""
    if not geojson:
        return

    # Clear existing rivers
    cur.execute("DELETE FROM rivers")

    count = 0
    skipped = 0
    for feature in geojson['features']:
        geom_type = feature['geometry']['type']
        props = feature['properties']
        base_id = props.get('id', f'rv_{count:04d}')

        if geom_type == 'LineString':
            line_geoms = [feature['geometry']]
        elif geom_type == 'MultiLineString':
            # Decompose into individual LineStrings
            line_geoms = [
                {'type': 'LineString', 'coordinates': coords}
                for coords in feature['geometry']['coordinates']
            ]
        else:
            skipped += 1
            continue

        for sub_idx, geom in enumerate(line_geoms):
            seg_id = base_id if len(line_geoms) == 1 else f'{base_id}_{sub_idx}'
            cur.execute("""
                INSERT INTO rivers (
                    id, name, geom, permanence, certainty, source
                ) VALUES (
                    %s, %s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                    %s, %s, %s
                )
            """, (
                seg_id,
                props.get('name'),
                json.dumps(geom),
                props.get('permanence', 'permanent'),
                props.get('certainty', 'INDIRECT'),
                props.get('source', 'OS Open Rivers'),
            ))
            count += 1

    if skipped:
        print(f"  Skipped {skipped} non-line features (Points/other)")
    print(f"  Imported {count} rivers")


def import_coastline(cur, geojson):
    """Import reconstructed coastline."""
    if not geojson:
        return

    # Clear existing coastline
    cur.execute("DELETE FROM coastline")

    count = 0
    for feature in geojson['features']:
        props = feature['properties']
        geom_json = json.dumps(feature['geometry'])

        # Ensure geometry is MultiPolygon
        geom_type = feature['geometry']['type']
        if geom_type == 'Polygon':
            multi_geom = {
                'type': 'MultiPolygon',
                'coordinates': [feature['geometry']['coordinates']]
            }
            geom_json = json.dumps(multi_geom)
        elif geom_type == 'GeometryCollection':
            # Extract only Polygon geometries, discard LineStrings etc.
            polys = [
                g['coordinates'] for g in feature['geometry']['geometries']
                if g['type'] == 'Polygon'
            ]
            if not polys:
                print(f"  Skipping coastline feature with no polygons in GeometryCollection")
                continue
            multi_geom = {'type': 'MultiPolygon', 'coordinates': polys}
            geom_json = json.dumps(multi_geom)

        cur.execute("""
            INSERT INTO coastline (
                id, name, geom, sea_level_offset_m,
                certainty, source, status
            ) VALUES (
                %s, %s,
                ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                %s, %s, %s, %s
            )
        """, (
            props.get('id', f'coast_{count}'),
            props.get('name', 'Yorkshire coastline ~6200 BCE'),
            geom_json,
            props.get('sea_level_offset_m', -25.0),
            props.get('certainty', 'INFERENCE'),
            props.get('source', 'GEBCO 2023, -25m contour'),
            props.get('status', 'VALID'),
        ))
        count += 1

    print(f"  Imported {count} coastline features")


def import_site_instances(cur, geojson):
    """Import archaeological sites from sites.geojson."""
    if not geojson:
        return

    # Clear existing ADS-sourced site instances (preserve KB seed rows without geometry)
    cur.execute("DELETE FROM site_instances WHERE source LIKE '%ADS%'")

    count = 0
    for feature in geojson['features']:
        props = feature['properties']
        geom = feature['geometry']

        # Normalize MultiPolygon → largest Polygon
        if geom['type'] == 'MultiPolygon':
            coords_list = geom['coordinates']
            if len(coords_list) == 1:
                geom = {'type': 'Polygon', 'coordinates': coords_list[0]}
            else:
                largest = max(coords_list, key=lambda c: len(c[0]) if c else 0)
                geom = {'type': 'Polygon', 'coordinates': largest}

        geom_json = json.dumps(geom)

        cur.execute("""
            INSERT INTO site_instances (
                id, name, lakescape_role, geom, certainty, source, status
            ) VALUES (
                %s, %s, %s,
                ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                lakescape_role = EXCLUDED.lakescape_role,
                geom = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                certainty = EXCLUDED.certainty,
                source = EXCLUDED.source,
                status = EXCLUDED.status
        """, (
            props.get('id', f'site_{count:04d}'),
            props.get('name'),
            props.get('lakescape_role'),
            geom_json,
            props.get('certainty', 'DIRECT'),
            props.get('source', 'ADS postglacial_2013'),
            'VALID',
            geom_json,
        ))
        count += 1

    print(f"  Imported {count} site instances")


def verify_counts(cur):
    """Print record counts for all spatial tables."""
    tables = ['terrain_subtypes', 'biotopes', 'can_host',
              'terrain_features', 'ecotones', 'rivers', 'coastline',
              'site_instances']
    print("\nDatabase record counts:")
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table}: {cur.fetchone()[0]}")
        except Exception:
            cur.connection.rollback()
            print(f"  {table}: (table not found)")

    # Count features with geometry
    for table in ['terrain_features', 'ecotones', 'rivers', 'coastline', 'site_instances']:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE geom IS NOT NULL")
            print(f"  {table} (with geometry): {cur.fetchone()[0]}")
        except Exception:
            cur.connection.rollback()


def main():
    print("=" * 60)
    print("Mezolit2 — Import GeoJSON to PostGIS")
    print("=" * 60)

    print("\nLoading GeoJSON files...")
    terrain_gj = load_geojson('terrain_features_with_biotopes.geojson')
    ecotones_gj = load_geojson('ecotones.geojson')
    rivers_gj = load_geojson('rivers_yorkshire.geojson')
    coastline_gj = load_geojson('coastline_6200bce.geojson')
    sites_gj = load_geojson('sites.geojson')

    if not any([terrain_gj, ecotones_gj, rivers_gj, coastline_gj]):
        print("\nERROR: No GeoJSON files found. Run pipeline steps 03-05 first.")
        sys.exit(1)

    print(f"\nConnecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        print("\nImporting terrain features...")
        import_terrain_features(cur, terrain_gj)

        print("Importing ecotones...")
        import_ecotones(cur, ecotones_gj)

        print("Importing rivers...")
        import_rivers(cur, rivers_gj)

        print("Importing coastline...")
        import_coastline(cur, coastline_gj)

        print("Importing site instances...")
        import_site_instances(cur, sites_gj)

        conn.commit()
        print("\nAll data committed successfully.")

        verify_counts(cur)

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    print(f"\nDone!")
    print("Next step: Milestone 2 — verify data against reference sources")


if __name__ == '__main__':
    main()

"""
Import CZ processed GeoJSON data into Supabase PostGIS (same DB as Yorkshire).

IMPORTANT: Only deletes/replaces CZ-prefixed records. Yorkshire data is preserved.

Imports:
  - terrain_features_with_biotopes_cz.geojson → terrain_features (id LIKE 'tf_cz_%')
  - ecotones_cz.geojson → ecotones (id LIKE 'ec_cz_%')
  - rivers_cz.geojson → rivers (id LIKE 'rv_cz_%')
  - sites_cz.geojson → site_instances (id LIKE 'site_cz_%')

Prerequisite: Run 01b_seed_kb_data_cz.py first (populates CZ KB tables).

Usage:
    python 06_import_supabase_cz.py
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

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed', 'cz')


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
    """Import CZ terrain features. Only deletes CZ records."""
    if not geojson:
        return

    # Delete only CZ terrain features (preserve Yorkshire)
    cur.execute("DELETE FROM site_instances WHERE id LIKE 'site_cz_%'")
    cur.execute("DELETE FROM terrain_features WHERE id LIKE 'tf_cz_%'")
    deleted = cur.rowcount
    print(f"  Deleted {deleted} existing CZ terrain features")

    count = 0
    skipped = 0
    for feature in geojson['features']:
        props = feature['properties']
        geom = feature['geometry']

        if geom is None:
            skipped += 1
            continue

        # Skip Point geometries (Svarcenberk anchor is a Point)
        if geom['type'] == 'Point':
            skipped += 1
            continue

        # Normalize MultiPolygon → largest Polygon (schema expects POLYGON)
        if geom['type'] == 'MultiPolygon':
            coords_list = geom['coordinates']
            if len(coords_list) == 1:
                geom = {'type': 'Polygon', 'coordinates': coords_list[0]}
            else:
                largest = max(coords_list, key=lambda c: len(c[0]) if c else 0)
                geom = {'type': 'Polygon', 'coordinates': largest}

        if geom['type'] == 'GeometryCollection':
            # Extract largest polygon from collection
            polys = [g for g in geom.get('geometries', []) if g['type'] in ('Polygon', 'MultiPolygon')]
            if not polys:
                skipped += 1
                continue
            geom = polys[0]
            if geom['type'] == 'MultiPolygon':
                geom = {'type': 'Polygon', 'coordinates': geom['coordinates'][0]}

        if geom['type'] != 'Polygon':
            skipped += 1
            continue

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
            ON CONFLICT (id) DO UPDATE SET
                terrain_subtype_id = EXCLUDED.terrain_subtype_id,
                biotope_id = EXCLUDED.biotope_id,
                geom = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                certainty = EXCLUDED.certainty,
                source = EXCLUDED.source
        """, (
            props.get('id', f'tf_cz_{count:04d}'),
            props.get('biotope_name'),
            props.get('terrain_subtype_id'),
            props.get('biotope_id'),
            geom_json,
            props.get('anchor_site', False),
            props.get('notes'),
            props.get('certainty', 'INFERENCE'),
            props.get('source', 'CGS + CZ pipeline'),
            geom_json,
        ))
        count += 1

    if skipped:
        print(f"  Skipped {skipped} non-polygon features (Points, etc.)")
    print(f"  Imported {count} CZ terrain features")


def import_ecotones(cur, geojson):
    """Update CZ ecotone rows with geometry."""
    if not geojson:
        return

    count_updated = 0
    count_inserted = 0

    for feature in geojson['features']:
        props = feature['properties']
        geom_json = json.dumps(feature['geometry'])
        eco_id = props.get('id')

        # Try to update existing KB row
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
            # Insert new ecotone row if not in KB
            cur.execute("""
                INSERT INTO ecotones (
                    id, name, biotope_a_id, biotope_b_id,
                    geom, edge_effect_factor, human_relevance,
                    certainty, source, status
                ) VALUES (
                    %s, %s, %s, %s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                    %s, %s, %s, %s, 'VALID'
                )
            """, (
                eco_id, props.get('name'),
                props.get('biotope_a_id'), props.get('biotope_b_id'),
                geom_json,
                props.get('edge_effect_factor'),
                props.get('human_relevance'),
                props.get('certainty', 'INFERENCE'),
                props.get('source', 'CZ pipeline'),
            ))
            count_inserted += 1

    print(f"  Ecotones: {count_updated} updated, {count_inserted} inserted")


def import_rivers(cur, geojson):
    """Import CZ river features. Only deletes CZ records."""
    if not geojson:
        return

    cur.execute("DELETE FROM rivers WHERE id LIKE 'rv_cz_%'")
    deleted = cur.rowcount
    print(f"  Deleted {deleted} existing CZ rivers")

    count = 0
    for feature in geojson['features']:
        geom_type = feature['geometry']['type']
        props = feature['properties']
        base_id = props.get('id', f'rv_cz_{count:04d}')

        if geom_type == 'LineString':
            line_geoms = [feature['geometry']]
        elif geom_type == 'MultiLineString':
            line_geoms = [
                {'type': 'LineString', 'coordinates': coords}
                for coords in feature['geometry']['coordinates']
            ]
        else:
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
                props.get('certainty', 'INFERENCE'),
                props.get('source', 'DIBAVOD A02'),
            ))
            count += 1

    print(f"  Imported {count} CZ river segments")


def import_sites(cur, geojson):
    """Import CZ archaeological sites. Only deletes CZ records."""
    if not geojson:
        return

    cur.execute("DELETE FROM site_instances WHERE id LIKE 'site_cz_%'")
    deleted = cur.rowcount
    print(f"  Deleted {deleted} existing CZ sites")

    count = 0
    for feature in geojson['features']:
        props = feature['properties']
        geom = feature['geometry']

        # Sites are Points — schema expects POLYGON, so create small buffer
        if geom['type'] == 'Point':
            # Insert as point, convert to tiny polygon in SQL
            lon, lat = geom['coordinates'][:2]
            cur.execute("""
                INSERT INTO site_instances (
                    id, name, lakescape_role, geom,
                    certainty, source, status
                ) VALUES (
                    %s, %s, %s,
                    ST_Buffer(ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 50)::geometry,
                    %s, %s, 'VALID'
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    geom = ST_Buffer(ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 50)::geometry,
                    certainty = EXCLUDED.certainty,
                    source = EXCLUDED.source
            """, (
                props.get('id', f'site_cz_{count:04d}'),
                props.get('ident_cely') or props.get('katastr') or props.get('name'),
                props.get('lakescape_role'),
                lon, lat,
                props.get('certainty', 'DIRECT'),
                props.get('source', 'AMCR digiarchiv'),
                lon, lat,
            ))
        else:
            # Polygon geometry — normalize MultiPolygon
            if geom['type'] == 'MultiPolygon':
                coords_list = geom['coordinates']
                largest = max(coords_list, key=lambda c: len(c[0]) if c else 0)
                geom = {'type': 'Polygon', 'coordinates': largest}

            cur.execute("""
                INSERT INTO site_instances (
                    id, name, lakescape_role, geom,
                    certainty, source, status
                ) VALUES (
                    %s, %s, %s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                    %s, %s, 'VALID'
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    geom = ST_SetSRID(ST_GeomFromGeoJSON(%%s), 4326),
                    certainty = EXCLUDED.certainty,
                    source = EXCLUDED.source
            """, (
                props.get('id', f'site_cz_{count:04d}'),
                props.get('ident_cely') or props.get('katastr') or props.get('name'),
                props.get('lakescape_role'),
                json.dumps(geom),
                props.get('certainty', 'DIRECT'),
                props.get('source', 'AMCR digiarchiv'),
            ))
        count += 1

    print(f"  Imported {count} CZ site instances")


def verify_counts(cur):
    """Print record counts split by region."""
    print("\nDatabase record counts (Yorkshire + CZ):")
    spatial_tables = {
        'terrain_features': 'tf_cz_%',
        'ecotones': 'ec_cz_%',
        'rivers': 'rv_cz_%',
        'site_instances': 'site_cz_%',
    }
    for table, cz_pattern in spatial_tables.items():
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE id LIKE %s", (cz_pattern,))
        cz = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE geom IS NOT NULL AND id LIKE %s", (cz_pattern,))
        cz_geom = cur.fetchone()[0]
        print(f"  {table}: {total} total ({cz} CZ, {cz_geom} with geometry)")

    # KB tables
    for table in ['terrain_subtypes', 'biotopes']:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE id LIKE '%%cz%%'")
        cz = cur.fetchone()[0]
        print(f"  {table}: {total} total ({cz} CZ)")


def main():
    print("=" * 60)
    print("Mezolit2 — Import CZ GeoJSON to PostGIS")
    print("=" * 60)

    print("\nLoading GeoJSON files...")
    terrain_gj = load_geojson('terrain_features_with_biotopes_cz.geojson')
    ecotones_gj = load_geojson('ecotones_cz.geojson')
    rivers_gj = load_geojson('rivers_cz.geojson')
    sites_gj = load_geojson('sites_cz.geojson')

    if not any([terrain_gj, ecotones_gj, rivers_gj]):
        print("\nERROR: No CZ GeoJSON files found. Run 04_terrain_cz.py + 05_kb_rules_cz.py first.")
        sys.exit(1)

    print(f"\nConnecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        print("\nImporting CZ terrain features...")
        import_terrain_features(cur, terrain_gj)

        print("Importing CZ ecotones...")
        import_ecotones(cur, ecotones_gj)

        print("Importing CZ rivers...")
        import_rivers(cur, rivers_gj)

        print("Importing CZ sites...")
        import_sites(cur, sites_gj)

        conn.commit()
        print("\nAll CZ data committed successfully.")

        verify_counts(cur)

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    print(f"\nDone! CZ data in Supabase.")
    print("Next: switch frontend STATIC_MODE=false and push.")


if __name__ == '__main__':
    main()

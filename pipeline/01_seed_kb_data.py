"""
Import KB seed data from schema_examples_v04.json into PostGIS.
Populates: terrain_subtypes, biotopes, can_host tables.
Ecotone KB data is also inserted (without geometry — geometry added later by pipeline).

Usage:
    python 01_seed_kb_data.py

Requires DATABASE_URL in .env or environment variable.
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

KB_PATH = os.path.join(os.path.dirname(__file__), '..', 'kb_data', 'schema_examples_v04.json')


def load_kb():
    with open(KB_PATH, encoding='utf-8') as f:
        return json.load(f)


def insert_terrain_subtypes(cur, kb):
    records = kb['terrain_subtypes']['records']
    for r in records:
        ka = r.get('key_attributes', {})
        elev = ka.get('elevation_typical_m', {})
        cur.execute("""
            INSERT INTO terrain_subtypes (
                id, name, description, hydrology, slope, substrate,
                elevation_min_m, elevation_max_m, flint_availability,
                nonrenewable_resources, anchor_instances,
                certainty, source, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                hydrology = EXCLUDED.hydrology,
                slope = EXCLUDED.slope,
                substrate = EXCLUDED.substrate,
                elevation_min_m = EXCLUDED.elevation_min_m,
                elevation_max_m = EXCLUDED.elevation_max_m,
                flint_availability = EXCLUDED.flint_availability,
                nonrenewable_resources = EXCLUDED.nonrenewable_resources,
                anchor_instances = EXCLUDED.anchor_instances,
                certainty = EXCLUDED.certainty,
                source = EXCLUDED.source,
                status = EXCLUDED.status
        """, (
            r['id'],
            r['name'],
            r.get('description'),
            ka.get('hydrology'),
            ka.get('slope'),
            ka.get('substrate'),
            elev.get('min'),
            elev.get('max'),
            None,  # flint_availability is on nonrenewable_resources, not a direct field
            json.dumps(r.get('nonrenewable_resources', []), ensure_ascii=False),
            json.dumps(r.get('anchor_instances', []), ensure_ascii=False),
            r['epistemics']['certainty'],
            r['epistemics']['source'],
            r['epistemics']['status'],
        ))
    print(f"  Inserted {len(records)} terrain_subtypes")


def insert_biotopes(cur, kb):
    records = kb['biotopes']['records']
    for r in records:
        attrs = r.get('attributes', {})
        sm = r.get('seasonal_modifiers', {})

        # Extract productivity kcal
        prod = attrs.get('primary_productivity_kcal_km2_year', {})
        prod_value = prod.get('value') if isinstance(prod, dict) else None
        prod_certainty = prod.get('certainty') if isinstance(prod, dict) else None
        prod_source = prod.get('source') if isinstance(prod, dict) else None

        # Collect extra attributes not in flat columns
        extra = {}
        skip_keys = {
            'productivity_class', 'primary_productivity_kcal_km2_year',
            'trafficability', 'energy_multiplier', 'dominant_species'
        }
        for k, v in attrs.items():
            if k not in skip_keys:
                extra[k] = v

        cur.execute("""
            INSERT INTO biotopes (
                id, name, description,
                productivity_class, productivity_kcal_km2_year,
                productivity_certainty, productivity_source,
                trafficability, energy_multiplier,
                dominant_species,
                seasonal_spring_modifier, seasonal_summer_modifier,
                seasonal_autumn_modifier, seasonal_winter_modifier,
                seasonal_spring_note, seasonal_summer_note,
                seasonal_autumn_note, seasonal_winter_note,
                primary_threats_human, extra_attributes,
                certainty, source, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                productivity_class = EXCLUDED.productivity_class,
                productivity_kcal_km2_year = EXCLUDED.productivity_kcal_km2_year,
                productivity_certainty = EXCLUDED.productivity_certainty,
                productivity_source = EXCLUDED.productivity_source,
                trafficability = EXCLUDED.trafficability,
                energy_multiplier = EXCLUDED.energy_multiplier,
                dominant_species = EXCLUDED.dominant_species,
                seasonal_spring_modifier = EXCLUDED.seasonal_spring_modifier,
                seasonal_summer_modifier = EXCLUDED.seasonal_summer_modifier,
                seasonal_autumn_modifier = EXCLUDED.seasonal_autumn_modifier,
                seasonal_winter_modifier = EXCLUDED.seasonal_winter_modifier,
                seasonal_spring_note = EXCLUDED.seasonal_spring_note,
                seasonal_summer_note = EXCLUDED.seasonal_summer_note,
                seasonal_autumn_note = EXCLUDED.seasonal_autumn_note,
                seasonal_winter_note = EXCLUDED.seasonal_winter_note,
                primary_threats_human = EXCLUDED.primary_threats_human,
                extra_attributes = EXCLUDED.extra_attributes,
                certainty = EXCLUDED.certainty,
                source = EXCLUDED.source,
                status = EXCLUDED.status
        """, (
            r['id'],
            r['name'],
            r.get('description'),
            attrs.get('productivity_class'),
            prod_value,
            prod_certainty,
            prod_source,
            attrs.get('trafficability'),
            attrs.get('energy_multiplier'),
            json.dumps(attrs.get('dominant_species', []), ensure_ascii=False),
            sm.get('SPRING', {}).get('productivity_modifier'),
            sm.get('SUMMER', {}).get('productivity_modifier'),
            sm.get('AUTUMN', {}).get('productivity_modifier'),
            sm.get('WINTER', {}).get('productivity_modifier'),
            sm.get('SPRING', {}).get('note'),
            sm.get('SUMMER', {}).get('note'),
            sm.get('AUTUMN', {}).get('note'),
            sm.get('WINTER', {}).get('note'),
            json.dumps(r.get('primary_threats_human', []), ensure_ascii=False),
            json.dumps(extra, ensure_ascii=False),
            r['epistemics']['certainty'],
            r['epistemics']['source'],
            r['epistemics']['status'],
        ))
    print(f"  Inserted {len(records)} biotopes")


def insert_can_host(cur, kb):
    records = kb['biotopes']['records']
    count = 0
    # Clear existing can_host edges before re-import
    cur.execute("DELETE FROM can_host")
    for r in records:
        biotope_id = r['id']
        for ch in r.get('can_host', []):
            cur.execute("""
                INSERT INTO can_host (
                    biotope_id, terrain_subtype_id,
                    trigger, spatial_scale, quality_modifier,
                    duration_years, duration_note, note,
                    certainty, source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                biotope_id,
                ch['terrain_subtype'],
                ch.get('trigger', 'baseline'),
                ch.get('spatial_scale', 'landscape'),
                ch.get('quality_modifier', 1.0),
                ch.get('duration_years'),
                ch.get('duration_note'),
                ch.get('note'),
                r['epistemics']['certainty'],  # inherit from parent biotope
                r['epistemics']['source'],
            ))
            count += 1
    print(f"  Inserted {count} can_host edges")


def insert_ecotone_kb_data(cur, kb):
    """Insert ecotone KB data without geometry (geometry added by pipeline later)."""
    records = kb['ecotones']['records']
    for r in records:
        attrs = r.get('attributes', {})
        cur.execute("""
            INSERT INTO ecotones (
                id, name, biotope_a_id, biotope_b_id,
                edge_effect_factor, edge_effect_source,
                human_relevance, seasonal_peaks,
                certainty, source, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                biotope_a_id = EXCLUDED.biotope_a_id,
                biotope_b_id = EXCLUDED.biotope_b_id,
                edge_effect_factor = EXCLUDED.edge_effect_factor,
                edge_effect_source = EXCLUDED.edge_effect_source,
                human_relevance = EXCLUDED.human_relevance,
                seasonal_peaks = EXCLUDED.seasonal_peaks,
                certainty = EXCLUDED.certainty,
                source = EXCLUDED.source,
                status = EXCLUDED.status
        """, (
            r['id'],
            r['name'],
            r['ecotone_of'][0],
            r['ecotone_of'][1],
            attrs.get('edge_effect_factor'),
            attrs.get('edge_effect_source'),
            attrs.get('human_relevance'),
            json.dumps(r.get('seasonal_peaks', {}), ensure_ascii=False),
            r['epistemics']['certainty'],
            r['epistemics']['source'],
            r['epistemics']['status'],
        ))
    print(f"  Inserted {len(records)} ecotones (KB data, no geometry)")


def insert_site_instances(cur, kb):
    """Insert site instance KB data without geometry (geometry added by pipeline later)."""
    si = kb.get('site_instances')
    if not si:
        print("  No site_instances in KB data — skipping")
        return
    records = si.get('records', [])
    for r in records:
        ep = r.get('epistemics', {})
        cur.execute("""
            INSERT INTO site_instances (
                id, name, lakescape_role, terrain_feature_id, biotope_id,
                certainty, source, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                lakescape_role = EXCLUDED.lakescape_role,
                terrain_feature_id = EXCLUDED.terrain_feature_id,
                biotope_id = EXCLUDED.biotope_id,
                certainty = EXCLUDED.certainty,
                source = EXCLUDED.source,
                status = EXCLUDED.status
        """, (
            r['id'],
            r['name'],
            r.get('lakescape_role'),
            r.get('terrain_feature_id'),
            r.get('biotope_id'),
            ep.get('certainty', 'DIRECT'),
            ep.get('source'),
            ep.get('status', 'VALID'),
        ))
    print(f"  Inserted {len(records)} site_instances (KB data, no geometry)")


def main():
    print("Loading KB data...")
    kb = load_kb()

    print(f"Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        print("Importing terrain_subtypes...")
        insert_terrain_subtypes(cur, kb)

        print("Importing biotopes...")
        insert_biotopes(cur, kb)

        print("Importing can_host edges...")
        insert_can_host(cur, kb)

        print("Importing ecotone KB data...")
        insert_ecotone_kb_data(cur, kb)

        print("Importing site instance KB data...")
        insert_site_instances(cur, kb)

        conn.commit()
        print("\nDone! All KB seed data imported successfully.")

        # Verification counts
        cur.execute("SELECT COUNT(*) FROM terrain_subtypes")
        print(f"  terrain_subtypes: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM biotopes")
        print(f"  biotopes: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM can_host")
        print(f"  can_host: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM ecotones")
        print(f"  ecotones: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM site_instances")
        print(f"  site_instances: {cur.fetchone()[0]}")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()

"""
Import CZ KB seed data into PostGIS (same DB as Yorkshire).
Populates: terrain_subtypes, biotopes, can_host, ecotones (KB rows, no geometry).

Does NOT touch Yorkshire data — uses ON CONFLICT upsert for all inserts.

Usage:
    python 01b_seed_kb_data_cz.py

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


# ---------------------------------------------------------------------------
# CZ terrain_subtypes (GEO_DESIGN_v02 section 3.2)
# ---------------------------------------------------------------------------

CZ_TERRAIN_SUBTYPES = [
    {
        'id': 'tst_cz_001', 'name': 'Krystalické podloží',
        'description': 'Moldanubické ruly, granulity, migmatity — okraje Třeboňské pánve',
        'hydrology': 'well_drained', 'slope': 'moderate',
        'substrate': 'crystalline_basement',
        'elevation_min_m': 450, 'elevation_max_m': 650,
        'certainty': 'DIRECT', 'source': 'CGS geologická mapa 1:50 000',
    },
    {
        'id': 'tst_cz_002', 'name': 'Pískovcová plošina',
        'description': 'Křídové pískovce Klikovského souvrství (svrchní vrstvy) — hlavní výplň pánve',
        'hydrology': 'well_drained', 'slope': 'flat',
        'substrate': 'cretaceous_sandstone',
        'elevation_min_m': 400, 'elevation_max_m': 500,
        'certainty': 'DIRECT', 'source': 'CGS geologická mapa 1:50 000',
    },
    {
        'id': 'tst_cz_003', 'name': 'Jílovcová deprese',
        'description': 'Křídové jílovce a prachovce Klikovského souvrství (spodní vrstvy)',
        'hydrology': 'high_water_table', 'slope': 'flat',
        'substrate': 'cretaceous_claystone',
        'elevation_min_m': 400, 'elevation_max_m': 460,
        'certainty': 'DIRECT', 'source': 'CGS geologická mapa 1:50 000',
    },
    {
        'id': 'tst_cz_004', 'name': 'Neogenní jezerní sedimenty',
        'description': 'Neogenní jíly, diatomity, křemenci — západní část pánve',
        'hydrology': 'high_water_table', 'slope': 'flat',
        'substrate': 'neogene_lacustrine',
        'elevation_min_m': 410, 'elevation_max_m': 470,
        'certainty': 'DIRECT', 'source': 'CGS geologická mapa 1:50 000',
    },
    {
        'id': 'tst_cz_005', 'name': 'Říční terasa',
        'description': 'Pleistocénní štěrkopísky podél Lužnice a Nežárky',
        'hydrology': 'well_drained', 'slope': 'flat',
        'substrate': 'river_gravel',
        'elevation_min_m': 400, 'elevation_max_m': 440,
        'certainty': 'DIRECT', 'source': 'CGS geologická mapa 1:50 000',
    },
    {
        'id': 'tst_cz_006', 'name': 'Říční niva',
        'description': 'Holocénní nivní sedimenty — niva Lužnice, sezónní záplavy',
        'hydrology': 'seasonal_flooding', 'slope': 'flat',
        'substrate': 'alluvial_clay_peat',
        'elevation_min_m': 400, 'elevation_max_m': 430,
        'certainty': 'INDIRECT', 'source': 'CGS geologická mapa 1:50 000',
    },
    {
        'id': 'tst_cz_007', 'name': 'Eolický písek',
        'description': 'Váté písky z pozdního glaciálu — pás Majdalena→Veselí n.L.',
        'hydrology': 'well_drained', 'slope': 'flat',
        'substrate': 'aeolian_sand',
        'elevation_min_m': 410, 'elevation_max_m': 450,
        'certainty': 'INDIRECT', 'source': 'CGS geologická mapa 1:50 000',
    },
    {
        'id': 'tst_cz_008', 'name': 'Rašeliniště',
        'description': 'Holocénní rašeliny a slatiny',
        'hydrology': 'permanent_saturation', 'slope': 'flat',
        'substrate': 'peat',
        'elevation_min_m': 410, 'elevation_max_m': 450,
        'certainty': 'INDIRECT', 'source': 'CGS geologická mapa 1:50 000',
    },
    {
        'id': 'tst_cz_009', 'name': 'Jezerní pánev (zaniklá)',
        'description': 'Jezerní sedimenty — paleolakes (Švarcenberk + další)',
        'hydrology': 'permanent_standing_water', 'slope': 'flat',
        'substrate': 'organic_lacustrine_sediment',
        'elevation_min_m': 400, 'elevation_max_m': 440,
        'certainty': 'INDIRECT', 'source': 'CGS + Pokorný et al. 2010',
    },
    {
        'id': 'tst_cz_010', 'name': 'Velká řeka',
        'description': 'Stálé vodní toky — Lužnice, Nežárka',
        'hydrology': 'permanent_flow', 'slope': None,
        'substrate': 'river_gravel',
        'elevation_min_m': None, 'elevation_max_m': None,
        'certainty': 'INDIRECT', 'source': 'DIBAVOD A02',
    },
]

# ---------------------------------------------------------------------------
# CZ biotopes (~7000 BCE — early Atlantic)
# ---------------------------------------------------------------------------

CZ_BIOTOPES = [
    {
        'id': 'bt_cz_001', 'name': 'Bor na krystaliku (borovice-bříza)',
        'description': 'Pine-birch forest on crystalline bedrock slopes',
        'productivity_class': 'Low',
        'productivity_kcal': 180000,
        'trafficability': 'difficult',
        'energy_multiplier': 1.3,
        'dominant_species': ['Pinus sylvestris', 'Betula pendula', 'Vaccinium myrtillus'],
        'seasonal': {'spring': 0.8, 'summer': 1.2, 'autumn': 1.0, 'winter': 0.5},
    },
    {
        'id': 'bt_cz_002', 'name': 'Smíšený les na pískovci (borovice-dub)',
        'description': 'Pine-oak forest on well-drained Cretaceous sandstone',
        'productivity_class': 'Medium',
        'productivity_kcal': 280000,
        'trafficability': 'moderate',
        'energy_multiplier': 1.1,
        'dominant_species': ['Pinus sylvestris', 'Quercus robur', 'Corylus avellana', 'Tilia cordata'],
        'seasonal': {'spring': 0.9, 'summer': 1.3, 'autumn': 1.2, 'winter': 0.4},
    },
    {
        'id': 'bt_cz_003', 'name': 'Vlhký les na jílovci (olše-vrba)',
        'description': 'Wet alder-willow forest on impermeable claystone',
        'productivity_class': 'Medium',
        'productivity_kcal': 250000,
        'trafficability': 'difficult',
        'energy_multiplier': 1.4,
        'dominant_species': ['Alnus glutinosa', 'Salix cinerea', 'Frangula alnus'],
        'seasonal': {'spring': 1.1, 'summer': 1.2, 'autumn': 0.9, 'winter': 0.3},
    },
    {
        'id': 'bt_cz_004', 'name': 'Mokřadní olšina (neogén)',
        'description': 'Alder carr on waterlogged Neogene lacustrine sediments',
        'productivity_class': 'Medium',
        'productivity_kcal': 220000,
        'trafficability': 'very_difficult',
        'energy_multiplier': 1.5,
        'dominant_species': ['Alnus glutinosa', 'Carex spp.', 'Phragmites australis'],
        'seasonal': {'spring': 1.2, 'summer': 1.3, 'autumn': 0.8, 'winter': 0.2},
    },
    {
        'id': 'bt_cz_005', 'name': 'Habrový les na terase (líska-habr-dub)',
        'description': 'Hazel-hornbeam-oak forest on well-drained river terrace',
        'productivity_class': 'High',
        'productivity_kcal': 350000,
        'trafficability': 'easy',
        'energy_multiplier': 1.0,
        'dominant_species': ['Corylus avellana', 'Carpinus betulus', 'Quercus robur', 'Tilia cordata'],
        'seasonal': {'spring': 1.0, 'summer': 1.3, 'autumn': 1.4, 'winter': 0.4},
    },
    {
        'id': 'bt_cz_006', 'name': 'Lužní les (jilm-jasan-olše)',
        'description': 'Elm-ash-alder floodplain forest with seasonal flooding',
        'productivity_class': 'High',
        'productivity_kcal': 380000,
        'trafficability': 'moderate',
        'energy_multiplier': 1.2,
        'dominant_species': ['Ulmus laevis', 'Fraxinus excelsior', 'Alnus glutinosa', 'Quercus robur'],
        'seasonal': {'spring': 1.2, 'summer': 1.1, 'autumn': 1.3, 'winter': 0.3},
    },
    {
        'id': 'bt_cz_007', 'name': 'Borový bor na vátých píscích',
        'description': 'Pine woodland on dry acidic aeolian sand',
        'productivity_class': 'Low',
        'productivity_kcal': 150000,
        'trafficability': 'easy',
        'energy_multiplier': 1.0,
        'dominant_species': ['Pinus sylvestris', 'Calluna vulgaris', 'Cladonia spp.'],
        'seasonal': {'spring': 0.8, 'summer': 1.1, 'autumn': 0.9, 'winter': 0.5},
    },
    {
        'id': 'bt_cz_008', 'name': 'Rašelinný bor (rašeliniště)',
        'description': 'Peat bog with Sphagnum, scattered Pinus rotundata',
        'productivity_class': 'Very Low',
        'productivity_kcal': 80000,
        'trafficability': 'very_difficult',
        'energy_multiplier': 2.0,
        'dominant_species': ['Sphagnum spp.', 'Pinus rotundata', 'Eriophorum vaginatum', 'Drosera rotundifolia'],
        'seasonal': {'spring': 0.7, 'summer': 1.0, 'autumn': 0.8, 'winter': 0.2},
    },
    {
        'id': 'bt_cz_009', 'name': 'Otevřené jezero (paleolake)',
        'description': 'Open water with littoral reed belt',
        'productivity_class': 'Medium',
        'productivity_kcal': 200000,
        'trafficability': 'impassable',
        'energy_multiplier': 5.0,
        'dominant_species': ['Phragmites australis', 'Nymphaea alba', 'Nuphar lutea', 'Chara spp.'],
        'seasonal': {'spring': 1.0, 'summer': 1.4, 'autumn': 1.0, 'winter': 0.1},
    },
    {
        'id': 'bt_cz_010', 'name': 'Říční lužní les (riparian)',
        'description': 'Riparian gallery forest along major river corridors',
        'productivity_class': 'High',
        'productivity_kcal': 400000,
        'trafficability': 'moderate',
        'energy_multiplier': 1.1,
        'dominant_species': ['Salix alba', 'Alnus glutinosa', 'Fraxinus excelsior'],
        'seasonal': {'spring': 1.3, 'summer': 1.2, 'autumn': 1.1, 'winter': 0.3},
    },
    {
        'id': 'bt_cz_011', 'name': 'Lesní palouk (micro)',
        'description': 'Forest glade — small clearing within continuous forest',
        'productivity_class': 'High',
        'productivity_kcal': 320000,
        'trafficability': 'easy',
        'energy_multiplier': 0.9,
        'dominant_species': ['Poaceae spp.', 'Rubus spp.', 'Fragaria vesca', 'Corylus avellana'],
        'seasonal': {'spring': 1.2, 'summer': 1.5, 'autumn': 1.3, 'winter': 0.3},
    },
]

# CAN_HOST mapping: biotope_id -> [terrain_subtype_id, ...]
CZ_CAN_HOST = {
    'bt_cz_001': [('tst_cz_001', 1.0)],
    'bt_cz_002': [('tst_cz_002', 1.0)],
    'bt_cz_003': [('tst_cz_003', 0.9)],
    'bt_cz_004': [('tst_cz_004', 0.8)],
    'bt_cz_005': [('tst_cz_005', 1.0)],
    'bt_cz_006': [('tst_cz_006', 0.9)],
    'bt_cz_007': [('tst_cz_007', 1.0)],
    'bt_cz_008': [('tst_cz_008', 0.7)],
    'bt_cz_009': [('tst_cz_009', 0.8)],
    'bt_cz_010': [('tst_cz_006', 1.0), ('tst_cz_005', 0.8)],
    'bt_cz_011': [('tst_cz_001', 0.8), ('tst_cz_002', 0.8), ('tst_cz_005', 0.8), ('tst_cz_007', 0.8)],
}

# CZ ecotones
CZ_ECOTONES = [
    {
        'id': 'ec_cz_001', 'name': 'Les / Mokřad',
        'biotope_a': 'bt_cz_002', 'biotope_b': 'bt_cz_003',
        'edge_effect_factor': 1.4,
        'human_relevance': 'Hunting/gathering transition zone, freshwater access',
    },
    {
        'id': 'ec_cz_002', 'name': 'Mokřad / Jezero',
        'biotope_a': 'bt_cz_004', 'biotope_b': 'bt_cz_009',
        'edge_effect_factor': 1.5,
        'human_relevance': 'Fishing, waterfowl, plant resources (reed, sedge)',
    },
    {
        'id': 'ec_cz_003', 'name': 'Borový bor / Lužní les',
        'biotope_a': 'bt_cz_007', 'biotope_b': 'bt_cz_006',
        'edge_effect_factor': 1.3,
        'human_relevance': 'Dry camping on sand + wet resources in floodplain',
    },
    {
        'id': 'ec_cz_004', 'name': 'Říční niva / Les',
        'biotope_a': 'bt_cz_010', 'biotope_b': 'bt_cz_002',
        'edge_effect_factor': 1.4,
        'human_relevance': 'Water corridor edge, seasonal resources',
    },
    {
        'id': 'ec_cz_005', 'name': 'Borový bor / Rašelina',
        'biotope_a': 'bt_cz_007', 'biotope_b': 'bt_cz_008',
        'edge_effect_factor': 1.2,
        'human_relevance': 'Dry/wet transition on sand, peat resources',
    },
    {
        'id': 'ec_cz_006', 'name': 'Les / Palouk (micro ekoton)',
        'biotope_a': 'bt_cz_002', 'biotope_b': 'bt_cz_011',
        'edge_effect_factor': 1.5,
        'human_relevance': 'High biodiversity edge, grazing, berries, hunting ambush',
    },
    {
        'id': 'ec_cz_007', 'name': 'Krystalinikum / Pískovcová plošina',
        'biotope_a': 'bt_cz_001', 'biotope_b': 'bt_cz_002',
        'edge_effect_factor': 1.2,
        'human_relevance': 'Geological boundary, spring line, lithic source access',
    },
    {
        'id': 'ec_cz_008', 'name': 'Terasa / Niva',
        'biotope_a': 'bt_cz_005', 'biotope_b': 'bt_cz_006',
        'edge_effect_factor': 1.3,
        'human_relevance': 'Dry ground overlooking floodplain — camp site preference',
    },
]


# ---------------------------------------------------------------------------
# Insert functions
# ---------------------------------------------------------------------------

def insert_terrain_subtypes(cur):
    for r in CZ_TERRAIN_SUBTYPES:
        cur.execute("""
            INSERT INTO terrain_subtypes (
                id, name, description, hydrology, slope, substrate,
                elevation_min_m, elevation_max_m,
                certainty, source, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'VALID')
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                hydrology = EXCLUDED.hydrology,
                slope = EXCLUDED.slope,
                substrate = EXCLUDED.substrate,
                elevation_min_m = EXCLUDED.elevation_min_m,
                elevation_max_m = EXCLUDED.elevation_max_m,
                certainty = EXCLUDED.certainty,
                source = EXCLUDED.source
        """, (
            r['id'], r['name'], r['description'],
            r['hydrology'], r['slope'], r['substrate'],
            r.get('elevation_min_m'), r.get('elevation_max_m'),
            r['certainty'], r['source'],
        ))
    print(f"  Upserted {len(CZ_TERRAIN_SUBTYPES)} CZ terrain_subtypes")


def insert_biotopes(cur):
    for r in CZ_BIOTOPES:
        sm = r.get('seasonal', {})
        cur.execute("""
            INSERT INTO biotopes (
                id, name, description,
                productivity_class, productivity_kcal_km2_year,
                productivity_certainty, productivity_source,
                trafficability, energy_multiplier,
                dominant_species,
                seasonal_spring_modifier, seasonal_summer_modifier,
                seasonal_autumn_modifier, seasonal_winter_modifier,
                certainty, source, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, 'VALID'
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                productivity_class = EXCLUDED.productivity_class,
                productivity_kcal_km2_year = EXCLUDED.productivity_kcal_km2_year,
                trafficability = EXCLUDED.trafficability,
                energy_multiplier = EXCLUDED.energy_multiplier,
                dominant_species = EXCLUDED.dominant_species,
                seasonal_spring_modifier = EXCLUDED.seasonal_spring_modifier,
                seasonal_summer_modifier = EXCLUDED.seasonal_summer_modifier,
                seasonal_autumn_modifier = EXCLUDED.seasonal_autumn_modifier,
                seasonal_winter_modifier = EXCLUDED.seasonal_winter_modifier,
                certainty = EXCLUDED.certainty,
                source = EXCLUDED.source
        """, (
            r['id'], r['name'], r['description'],
            r['productivity_class'], r['productivity_kcal'],
            'INFERENCE', 'Paleoecological estimates based on Pokorny et al. 2010',
            r['trafficability'], r['energy_multiplier'],
            json.dumps(r['dominant_species'], ensure_ascii=False),
            sm.get('spring'), sm.get('summer'),
            sm.get('autumn'), sm.get('winter'),
            'INFERENCE', 'CZ biotope model — 05_kb_rules_cz.py',
        ))
    print(f"  Upserted {len(CZ_BIOTOPES)} CZ biotopes")


def insert_can_host(cur):
    # Only delete CZ can_host edges (preserve Yorkshire)
    cur.execute("DELETE FROM can_host WHERE biotope_id LIKE 'bt_cz_%'")
    count = 0
    for bt_id, hosts in CZ_CAN_HOST.items():
        for tst_id, quality in hosts:
            cur.execute("""
                INSERT INTO can_host (
                    biotope_id, terrain_subtype_id,
                    trigger, spatial_scale, quality_modifier,
                    certainty, source
                ) VALUES (%s, %s, 'baseline', 'landscape', %s, 'INFERENCE', 'CZ biotope model')
            """, (bt_id, tst_id, quality))
            count += 1
    print(f"  Inserted {count} CZ can_host edges")


def insert_ecotones(cur):
    for e in CZ_ECOTONES:
        cur.execute("""
            INSERT INTO ecotones (
                id, name, biotope_a_id, biotope_b_id,
                edge_effect_factor, human_relevance,
                certainty, source, status
            ) VALUES (%s, %s, %s, %s, %s, %s, 'INFERENCE', 'CZ ecotone model', 'VALID')
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                biotope_a_id = EXCLUDED.biotope_a_id,
                biotope_b_id = EXCLUDED.biotope_b_id,
                edge_effect_factor = EXCLUDED.edge_effect_factor,
                human_relevance = EXCLUDED.human_relevance
        """, (
            e['id'], e['name'], e['biotope_a'], e['biotope_b'],
            e['edge_effect_factor'], e['human_relevance'],
        ))
    print(f"  Upserted {len(CZ_ECOTONES)} CZ ecotones (KB data, no geometry)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Mezolit2 — CZ KB Seed Data")
    print("=" * 60)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        print("\nInserting CZ terrain_subtypes...")
        insert_terrain_subtypes(cur)

        print("Inserting CZ biotopes...")
        insert_biotopes(cur)

        print("Inserting CZ can_host edges...")
        insert_can_host(cur)

        print("Inserting CZ ecotones...")
        insert_ecotones(cur)

        conn.commit()
        print("\nDone! CZ KB seed data imported.")

        # Verification
        for table in ['terrain_subtypes', 'biotopes', 'ecotones']:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            total = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE id LIKE '%%cz%%'")
            cz = cur.fetchone()[0]
            print(f"  {table}: {total} total ({cz} CZ)")
        cur.execute("SELECT COUNT(*) FROM can_host")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM can_host WHERE biotope_id LIKE '%%cz%%'")
        cz = cur.fetchone()[0]
        print(f"  can_host: {total} total ({cz} CZ)")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()

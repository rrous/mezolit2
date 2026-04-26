"""
Import Polabí KB seed data into PostGIS (same DB as Yorkshire/CZ).
Populates: terrain_subtypes, biotopes, can_host, ecotones (KB rows, no geometry),
           biotope_rules (Polabí-specific table from 00_polabi_schema.sql),
           pollen_sites (Hrabanov reference).

Does NOT touch Yorkshire / CZ data — uses ON CONFLICT upsert for all inserts.

Usage:
    python pipeline/01c_seed_kb_data_polabi.py

Requires DATABASE_URL in .env or environment variable, plus 00_polabi_schema.sql
already applied (provides biotope_rules + pollen_sites tables).
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
# Polabí terrain_subtypes (matches TERRAIN_RULES in 04_terrain_polabi.py)
# ---------------------------------------------------------------------------

PL_TERRAIN_SUBTYPES = [
    {
        'id': 'tst_pl_001', 'name': 'Aktivní koryto',
        'description': 'Hlavní toky Labe + významných přítoků (Strahler ≥ 3)',
        'hydrology': 'permanent_flow', 'slope': 'flat',
        'substrate': 'river_gravel',
        'elevation_min_m': 160, 'elevation_max_m': 250,
        'certainty': 'INFERENCE', 'source': 'DIBAVOD A01 + DEM Strahler ordering',
    },
    {
        'id': 'tst_pl_002', 'name': 'Mokřad',
        'description': 'Trvale/sezónně zaplavená plocha v nivě, rákosy, ostřice',
        'hydrology': 'permanent_saturation', 'slope': 'flat',
        'substrate': 'alluvial_clay_peat',
        'elevation_min_m': 160, 'elevation_max_m': 220,
        'certainty': 'INFERENCE', 'source': 'DEM HAND<1 + slope<2 + TWI>12',
    },
    {
        'id': 'tst_pl_003', 'name': 'Lužní les',
        'description': 'Periodicky zaplavovaný tvrdý luh: jilm, jasan, dub, lípa',
        'hydrology': 'seasonal_flooding', 'slope': 'flat',
        'substrate': 'alluvial_clay_peat',
        'elevation_min_m': 160, 'elevation_max_m': 250,
        'certainty': 'INFERENCE', 'source': 'DEM HAND<3 + slope<3 + Pokorný 2012',
    },
    {
        'id': 'tst_pl_004', 'name': 'Záplavová zóna',
        'description': 'Širší niva — vyšší terasy, výjimečně zaplavované',
        'hydrology': 'seasonal_flooding', 'slope': 'flat',
        'substrate': 'alluvial_clay_peat',
        'elevation_min_m': 170, 'elevation_max_m': 280,
        'certainty': 'INFERENCE', 'source': 'DEM HAND<5 + slope<5',
    },
    {
        'id': 'tst_pl_005', 'name': 'Xerotermní step',
        'description': 'Jižní svahy strmých údolí — trávy, keře, rozvolněné stromy',
        'hydrology': 'well_drained', 'slope': 'steep',
        'substrate': 'crystalline_basement',  # placeholder; varies
        'elevation_min_m': 200, 'elevation_max_m': 500,
        'certainty': 'INFERENCE', 'source': 'DEM slope≥15 + aspect 135-225°',
    },
    {
        'id': 'tst_pl_006', 'name': 'Suťový les',
        'description': 'Strmé svahy, javorobukový les: javor, lípa, jilm',
        'hydrology': 'well_drained', 'slope': 'very_steep',
        'substrate': 'crystalline_basement',
        'elevation_min_m': 200, 'elevation_max_m': 500,
        'certainty': 'INFERENCE', 'source': 'DEM slope≥25 + TWI<5',
    },
    {
        'id': 'tst_pl_007', 'name': 'Pahorkatinný les',
        'description': 'Buk-jedle-dub-lípa na svazích pahorkatin (Železné hory, Polabská tabule)',
        'hydrology': 'well_drained', 'slope': 'moderate',
        'substrate': 'crystalline_basement',
        'elevation_min_m': 400, 'elevation_max_m': 700,
        'certainty': 'INFERENCE', 'source': 'DEM elevation 400-700 m',
    },
    {
        'id': 'tst_pl_008', 'name': 'Nížinný smíšený les',
        'description': 'Dub-lípa-jilm-líska — hlavní lesní biotop nížin (catch-all)',
        'hydrology': 'mixed_permeability', 'slope': 'flat',
        'substrate': 'alluvial_clay_peat',
        'elevation_min_m': 160, 'elevation_max_m': 400,
        'certainty': 'INFERENCE', 'source': 'DEM elevation < 400 m (default)',
    },
]


# ---------------------------------------------------------------------------
# Polabí biotopes (~6200 BCE — late Boreal / early Atlantic)
# ---------------------------------------------------------------------------

PL_BIOTOPES = [
    {
        'id': 'bt_pl_001', 'name': 'Říční koryto + břeh (Labe)',
        'description': 'Hlavní toky s pionýrskou vegetací na štěrkových lavicích',
        'productivity_class': 'High',
        'productivity_kcal': 320000,
        'trafficability': 'difficult',
        'energy_multiplier': 1.5,
        'dominant_species': ['Salix alba', 'Populus nigra', 'Phalaris arundinacea'],
        'seasonal': {'spring': 1.3, 'summer': 1.4, 'autumn': 1.0, 'winter': 0.4},
    },
    {
        'id': 'bt_pl_002', 'name': 'Nivní mokřad',
        'description': 'Rákosiny, ostřice, vrbiny — sezónně zaplavené plochy',
        'productivity_class': 'High',
        'productivity_kcal': 350000,
        'trafficability': 'very_difficult',
        'energy_multiplier': 1.6,
        'dominant_species': ['Phragmites australis', 'Carex spp.', 'Salix cinerea', 'Typha latifolia'],
        'seasonal': {'spring': 1.4, 'summer': 1.3, 'autumn': 0.9, 'winter': 0.2},
    },
    {
        'id': 'bt_pl_003', 'name': 'Tvrdý luh (jilm-jasan-dub)',
        'description': 'Periodicky zaplavovaný luh — Pokorný 2012 dominanty',
        'productivity_class': 'Very High',
        'productivity_kcal': 420000,
        'trafficability': 'moderate',
        'energy_multiplier': 1.2,
        'dominant_species': ['Ulmus laevis', 'Fraxinus excelsior', 'Quercus robur', 'Tilia cordata', 'Alnus glutinosa'],
        'seasonal': {'spring': 1.3, 'summer': 1.2, 'autumn': 1.4, 'winter': 0.3},
    },
    {
        'id': 'bt_pl_004', 'name': 'Měkký luh (vrba-olše-topol)',
        'description': 'Bližší okraji koryta, časté záplavy — širší niva mimo jádro',
        'productivity_class': 'High',
        'productivity_kcal': 350000,
        'trafficability': 'moderate',
        'energy_multiplier': 1.3,
        'dominant_species': ['Salix alba', 'Salix fragilis', 'Alnus glutinosa', 'Populus nigra'],
        'seasonal': {'spring': 1.3, 'summer': 1.1, 'autumn': 1.2, 'winter': 0.3},
    },
    {
        'id': 'bt_pl_005', 'name': 'Skalní step (xerotermní)',
        'description': 'Jižní svahy nad údolími, vápnité podloží — trávy + keře + rozvolněné duby',
        'productivity_class': 'Medium',
        'productivity_kcal': 220000,
        'trafficability': 'moderate',
        'energy_multiplier': 1.1,
        'dominant_species': ['Stipa pennata', 'Festuca rupicola', 'Cornus mas', 'Quercus pubescens'],
        'seasonal': {'spring': 1.4, 'summer': 1.0, 'autumn': 0.9, 'winter': 0.6},
    },
    {
        'id': 'bt_pl_006', 'name': 'Suťový les',
        'description': 'Strmé svahy, balvanitá suť — javor, jilm, lípa, jasan',
        'productivity_class': 'Medium',
        'productivity_kcal': 240000,
        'trafficability': 'difficult',
        'energy_multiplier': 1.4,
        'dominant_species': ['Acer pseudoplatanus', 'Tilia platyphyllos', 'Ulmus glabra', 'Fraxinus excelsior'],
        'seasonal': {'spring': 1.0, 'summer': 1.2, 'autumn': 1.2, 'winter': 0.4},
    },
    {
        'id': 'bt_pl_007', 'name': 'Pahorkatinný buko-dubový les',
        'description': 'Buk, jedle, dub, lípa — Železné hory + svahy pahorkatin',
        'productivity_class': 'High',
        'productivity_kcal': 320000,
        'trafficability': 'easy',
        'energy_multiplier': 1.0,
        'dominant_species': ['Fagus sylvatica', 'Abies alba', 'Quercus petraea', 'Tilia cordata', 'Acer platanoides'],
        'seasonal': {'spring': 1.0, 'summer': 1.2, 'autumn': 1.4, 'winter': 0.5},
    },
    {
        'id': 'bt_pl_008', 'name': 'Nížinný dubo-lipový les',
        'description': 'Dominantní biotop Polabí — dub, lípa, jilm, líska',
        'productivity_class': 'Very High',
        'productivity_kcal': 380000,
        'trafficability': 'easy',
        'energy_multiplier': 1.0,
        'dominant_species': ['Quercus robur', 'Tilia cordata', 'Ulmus laevis', 'Corylus avellana', 'Fraxinus excelsior'],
        'seasonal': {'spring': 1.1, 'summer': 1.3, 'autumn': 1.5, 'winter': 0.4},
    },
    {
        'id': 'bt_pl_glade', 'name': 'Lesní palouk (glade)',
        'description': 'Otevřená místa v lese 0.5-5 ha — disturbance, bobr, vývrat, požár',
        'productivity_class': 'Very High',
        'productivity_kcal': 360000,
        'trafficability': 'easy',
        'energy_multiplier': 0.9,
        'dominant_species': ['Poaceae spp.', 'Rubus idaeus', 'Fragaria vesca', 'Corylus avellana', 'Crataegus monogyna'],
        'seasonal': {'spring': 1.3, 'summer': 1.5, 'autumn': 1.3, 'winter': 0.3},
    },
]


# ---------------------------------------------------------------------------
# can_host: biotope_id → [(terrain_subtype_id, quality_modifier), ...]
# ---------------------------------------------------------------------------

PL_CAN_HOST = {
    'bt_pl_001':   [('tst_pl_001', 1.0)],
    'bt_pl_002':   [('tst_pl_002', 1.0)],
    'bt_pl_003':   [('tst_pl_003', 1.0)],
    'bt_pl_004':   [('tst_pl_004', 1.0), ('tst_pl_003', 0.6)],
    'bt_pl_005':   [('tst_pl_005', 1.0)],
    'bt_pl_006':   [('tst_pl_006', 1.0)],
    'bt_pl_007':   [('tst_pl_007', 1.0)],
    'bt_pl_008':   [('tst_pl_008', 1.0)],
    # Glade may host on any forest type
    'bt_pl_glade': [('tst_pl_003', 0.7), ('tst_pl_004', 0.7),
                    ('tst_pl_007', 0.8), ('tst_pl_008', 0.8)],
}


# ---------------------------------------------------------------------------
# ecotones (KB metadata; geometry is generated by 05_kb_rules_polabi.py)
# ---------------------------------------------------------------------------

PL_ECOTONES = [
    {
        'id': 'ec_pl_001', 'name': 'Lužní les / Mokřad',
        'biotope_a': 'bt_pl_003', 'biotope_b': 'bt_pl_002',
        'edge_effect_factor': 1.5,
        'human_relevance': 'Klíčový lov vodního ptactva, ryby, rákos, kořeny',
    },
    {
        'id': 'ec_pl_002', 'name': 'Nížinný les / Lužní les',
        'biotope_a': 'bt_pl_008', 'biotope_b': 'bt_pl_003',
        'edge_effect_factor': 1.4,
        'human_relevance': 'Suchá kempovací plocha s přístupem k zaplavované nivě',
    },
    {
        'id': 'ec_pl_003', 'name': 'Nížinný les / Záplavová zóna',
        'biotope_a': 'bt_pl_008', 'biotope_b': 'bt_pl_004',
        'edge_effect_factor': 1.3,
        'human_relevance': 'Přechod k občasně zaplavovaným polohám, sezónní zdroje',
    },
    {
        'id': 'ec_pl_004', 'name': 'Nížinný les / Pahorkatinný les',
        'biotope_a': 'bt_pl_008', 'biotope_b': 'bt_pl_007',
        'edge_effect_factor': 1.15,
        'human_relevance': 'Změna druhové skladby s elevací, zvěř využívá obě patra',
    },
    {
        'id': 'ec_pl_005', 'name': 'Nížinný les / Xerotermní step',
        'biotope_a': 'bt_pl_008', 'biotope_b': 'bt_pl_005',
        'edge_effect_factor': 1.4,
        'human_relevance': 'Lov v otevřené stepi, dohled z lesa, rozdílná fenologie',
    },
    {
        'id': 'ec_pl_006', 'name': 'Nížinný les / Palouk (micro)',
        'biotope_a': 'bt_pl_008', 'biotope_b': 'bt_pl_glade',
        'edge_effect_factor': 1.5,
        'human_relevance': 'Vysoká diverzita, spárkatá zvěř, plody, líska',
    },
    {
        'id': 'ec_pl_007', 'name': 'Pahorkatina / Suťový les',
        'biotope_a': 'bt_pl_007', 'biotope_b': 'bt_pl_006',
        'edge_effect_factor': 1.2,
        'human_relevance': 'Geomorfologická hranice, výchozy hornin, suroviny',
    },
    {
        'id': 'ec_pl_008', 'name': 'Aktivní koryto / Mokřad',
        'biotope_a': 'bt_pl_001', 'biotope_b': 'bt_pl_002',
        'edge_effect_factor': 1.6,
        'human_relevance': 'Říční rybolov, vodní ptactvo, mokřadní rostliny',
    },
]


# ---------------------------------------------------------------------------
# biotope_rules — explicit rules from 04_terrain_polabi.py TERRAIN_RULES
# (auditable record of what the classifier did)
# ---------------------------------------------------------------------------

PL_BIOTOPE_RULES = [
    {'biotope_id': 'bt_pl_001', 'terrain_subtype_id': 'tst_pl_001', 'priority': 100,
     'strahler_min': 3,
     'description': 'Strahler ≥ 3 stream cells (Labe + main tributaries)'},
    {'biotope_id': 'bt_pl_002', 'terrain_subtype_id': 'tst_pl_002', 'priority': 95,
     'hand_max': 1.0, 'slope_max': 2.0, 'twi_min': 12.0,
     'description': 'Permanent / seasonal wetland — HAND<1, slope<2, TWI>12'},
    {'biotope_id': 'bt_pl_003', 'terrain_subtype_id': 'tst_pl_003', 'priority': 90,
     'hand_max': 3.0, 'slope_max': 3.0, 'elev_max': 300.0,
     'description': 'Floodplain forest — HAND<3, slope<3, elev<300'},
    {'biotope_id': 'bt_pl_004', 'terrain_subtype_id': 'tst_pl_004', 'priority': 80,
     'hand_max': 5.0, 'slope_max': 5.0,
     'description': 'Wider floodplain — HAND<5, slope<5'},
    {'biotope_id': 'bt_pl_005', 'terrain_subtype_id': 'tst_pl_005', 'priority': 70,
     'slope_min': 15.0, 'aspect_condition': 'S',
     'description': 'South-facing dry slopes — slope≥15, aspect 135-225°'},
    {'biotope_id': 'bt_pl_006', 'terrain_subtype_id': 'tst_pl_006', 'priority': 65,
     'slope_min': 25.0, 'twi_max': 5.0,
     'description': 'Steep scree — slope≥25, TWI<5'},
    {'biotope_id': 'bt_pl_007', 'terrain_subtype_id': 'tst_pl_007', 'priority': 50,
     'elev_min': 400.0, 'elev_max': 700.0,
     'description': 'Hill / lower-mountain forest — 400 ≤ elev < 700'},
    {'biotope_id': 'bt_pl_008', 'terrain_subtype_id': 'tst_pl_008', 'priority': 40,
     'elev_max': 400.0,
     'description': 'Lowland mixed forest — elev<400 (catch-all default)'},
]


# ---------------------------------------------------------------------------
# pollen_sites — Hrabanov reference (for §9.4 biotope distribution validation)
# ---------------------------------------------------------------------------

PL_POLLEN_SITES = [
    {
        'id': 'ps_pl_001',
        'name': 'Hrabanov',
        'lat': 50.2030, 'lon': 14.8350,
        'age_min_cal_bce': 7000, 'age_max_cal_bce': 5500,
        'tree_pollen_pct': 70.0,
        'dominant_taxa': ['Quercus', 'Tilia', 'Ulmus', 'Corylus', 'Alnus'],
        'elevation_m': 175.0,
        'notes': 'Mire near Lysá nad Labem; Boreal-Atlantic transition profile.',
        'source': 'Pokorný et al. 2012; EPD record HRBNV',
    },
]


# ---------------------------------------------------------------------------
# Insert functions
# ---------------------------------------------------------------------------

def insert_terrain_subtypes(cur):
    for r in PL_TERRAIN_SUBTYPES:
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
    print(f"  Upserted {len(PL_TERRAIN_SUBTYPES)} Polabí terrain_subtypes")


def insert_biotopes(cur):
    for r in PL_BIOTOPES:
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
            'INFERENCE', 'Pokorný 2012; Polabí biotope model — 04_terrain_polabi.py §5',
            r['trafficability'], r['energy_multiplier'],
            json.dumps(r['dominant_species'], ensure_ascii=False),
            sm.get('spring'), sm.get('summer'),
            sm.get('autumn'), sm.get('winter'),
            'INFERENCE', 'Polabí biotope model',
        ))
    print(f"  Upserted {len(PL_BIOTOPES)} Polabí biotopes")


def insert_can_host(cur):
    cur.execute("DELETE FROM can_host WHERE biotope_id LIKE 'bt_pl_%'")
    count = 0
    for bt_id, hosts in PL_CAN_HOST.items():
        for tst_id, quality in hosts:
            cur.execute("""
                INSERT INTO can_host (
                    biotope_id, terrain_subtype_id,
                    trigger, spatial_scale, quality_modifier,
                    certainty, source
                ) VALUES (%s, %s, 'baseline', 'landscape', %s, 'INFERENCE', 'Polabí biotope model')
            """, (bt_id, tst_id, quality))
            count += 1
    print(f"  Inserted {count} Polabí can_host edges")


def insert_ecotones(cur):
    for e in PL_ECOTONES:
        cur.execute("""
            INSERT INTO ecotones (
                id, name, biotope_a_id, biotope_b_id,
                edge_effect_factor, human_relevance,
                certainty, source, status, region
            ) VALUES (%s, %s, %s, %s, %s, %s, 'INFERENCE', 'Polabí ecotone model', 'VALID', 'polabi')
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                biotope_a_id = EXCLUDED.biotope_a_id,
                biotope_b_id = EXCLUDED.biotope_b_id,
                edge_effect_factor = EXCLUDED.edge_effect_factor,
                human_relevance = EXCLUDED.human_relevance,
                region = EXCLUDED.region
        """, (
            e['id'], e['name'], e['biotope_a'], e['biotope_b'],
            e['edge_effect_factor'], e['human_relevance'],
        ))
    print(f"  Upserted {len(PL_ECOTONES)} Polabí ecotones (KB rows, no geometry)")


def insert_biotope_rules(cur):
    cur.execute("DELETE FROM biotope_rules WHERE region = 'polabi'")
    for r in PL_BIOTOPE_RULES:
        cur.execute("""
            INSERT INTO biotope_rules (
                region, biotope_id, terrain_subtype_id,
                elev_min, elev_max, slope_min, slope_max,
                twi_min, twi_max, hand_min, hand_max,
                strahler_min, aspect_condition,
                priority, description, source
            ) VALUES (
                'polabi', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
        """, (
            r['biotope_id'], r['terrain_subtype_id'],
            r.get('elev_min'), r.get('elev_max'),
            r.get('slope_min'), r.get('slope_max'),
            r.get('twi_min'), r.get('twi_max'),
            r.get('hand_min'), r.get('hand_max'),
            r.get('strahler_min'), r.get('aspect_condition'),
            r['priority'], r['description'],
            'docs/polabi_implementace.md §5.1; pipeline/04_terrain_polabi.py TERRAIN_RULES',
        ))
    print(f"  Inserted {len(PL_BIOTOPE_RULES)} Polabí biotope_rules")


def insert_pollen_sites(cur):
    for r in PL_POLLEN_SITES:
        cur.execute("""
            INSERT INTO pollen_sites (
                id, name, region, geom,
                age_min_cal_bce, age_max_cal_bce, tree_pollen_pct,
                dominant_taxa, elevation_m, notes, source, status
            ) VALUES (
                %s, %s, 'polabi', ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                %s, %s, %s, %s::jsonb, %s, %s, %s, 'VALID'
            )
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                geom = EXCLUDED.geom,
                age_min_cal_bce = EXCLUDED.age_min_cal_bce,
                age_max_cal_bce = EXCLUDED.age_max_cal_bce,
                tree_pollen_pct = EXCLUDED.tree_pollen_pct,
                dominant_taxa = EXCLUDED.dominant_taxa,
                elevation_m = EXCLUDED.elevation_m,
                notes = EXCLUDED.notes,
                source = EXCLUDED.source
        """, (
            r['id'], r['name'], r['lon'], r['lat'],
            r['age_min_cal_bce'], r['age_max_cal_bce'], r['tree_pollen_pct'],
            json.dumps(r['dominant_taxa'], ensure_ascii=False),
            r['elevation_m'], r['notes'], r['source'],
        ))
    print(f"  Upserted {len(PL_POLLEN_SITES)} Polabí pollen_sites")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Mezolit2 — Polabí KB Seed Data")
    print("=" * 60)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    try:
        print("\nInserting Polabí terrain_subtypes...")
        insert_terrain_subtypes(cur)

        print("Inserting Polabí biotopes...")
        insert_biotopes(cur)

        print("Inserting Polabí can_host edges...")
        insert_can_host(cur)

        print("Inserting Polabí ecotones (KB rows)...")
        insert_ecotones(cur)

        print("Inserting Polabí biotope_rules...")
        insert_biotope_rules(cur)

        print("Inserting Polabí pollen_sites...")
        insert_pollen_sites(cur)

        conn.commit()
        print("\nDone! Polabí KB seed data imported.")

        # Verification
        print("\nVerification:")
        for table in ['terrain_subtypes', 'biotopes']:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE id LIKE '%%pl%%'")
            n = cur.fetchone()[0]
            print(f"  {table} (pl_): {n} rows")
        cur.execute("SELECT COUNT(*) FROM can_host WHERE biotope_id LIKE 'bt_pl_%'")
        print(f"  can_host (pl_): {cur.fetchone()[0]} edges")
        cur.execute("SELECT COUNT(*) FROM ecotones WHERE region = 'polabi'")
        print(f"  ecotones (polabi): {cur.fetchone()[0]} rows")
        cur.execute("SELECT COUNT(*) FROM biotope_rules WHERE region = 'polabi'")
        print(f"  biotope_rules (polabi): {cur.fetchone()[0]} rules")
        cur.execute("SELECT COUNT(*) FROM pollen_sites WHERE region = 'polabi'")
        print(f"  pollen_sites (polabi): {cur.fetchone()[0]} sites")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()

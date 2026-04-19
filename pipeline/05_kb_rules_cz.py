"""
Apply KB rules to Trebonsko terrain polygons:
1. Assign dominant biotope to each terrain polygon (CZ-specific CAN_HOST graph)
2. Create riparian zones along rivers in floodplains
3. Detect forest glades (small clearings within forest-dominated terrain)
4. Generate ecotone lines from boundaries of adjacent polygons with different biotopes

Input:  data/processed/cz/terrain_features_cz.geojson
        data/processed/cz/rivers_cz.geojson
Output: data/processed/cz/terrain_features_with_biotopes_cz.geojson
        data/processed/cz/ecotones_cz.geojson

Usage:
    python 05_kb_rules_cz.py
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json

try:
    from shapely.geometry import shape, mapping, MultiLineString
    from shapely.ops import unary_union
    from shapely.validation import make_valid
    import geopandas as gpd
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed', 'cz')

# ---------------------------------------------------------------------------
# CZ Biotope definitions for Trebonsko ~7000 BCE
# Based on GEO_DESIGN_v02 terrain_subtypes + palaeoecological reconstructions
# (Pokorny et al. 2010, pylove profily z Svarcenberku)
#
# ~7000 BCE = early Atlantic (Boreal/Atlantic transition):
# - Forest: dominated by Pinus, Corylus, Betula, early Quercus/Tilia
# - No agriculture, ~100% forest cover outside water/peat/sand
# - Paleolakes still open (Svarcenberk ~ open water)
# ---------------------------------------------------------------------------

CZ_BIOTOPES = {
    'bt_cz_001': {
        'name': 'Bor na krystaliku (borovice-bříza)',
        'description': 'Pine-birch forest on crystalline bedrock slopes',
        'can_host': ['tst_cz_001'],
    },
    'bt_cz_002': {
        'name': 'Smíšený les na pískovci (borovice-dub)',
        'description': 'Pine-oak forest on well-drained Cretaceous sandstone',
        'can_host': ['tst_cz_002'],
    },
    'bt_cz_003': {
        'name': 'Vlhký les na jílovci (olše-vrba)',
        'description': 'Wet alder-willow forest on impermeable claystone',
        'can_host': ['tst_cz_003'],
    },
    'bt_cz_004': {
        'name': 'Mokřadní olšina (neogén)',
        'description': 'Alder carr on waterlogged Neogene lacustrine sediments',
        'can_host': ['tst_cz_004'],
    },
    'bt_cz_005': {
        'name': 'Habrový les na terase (líska-habr-dub)',
        'description': 'Hazel-hornbeam-oak forest on well-drained river terrace',
        'can_host': ['tst_cz_005'],
    },
    'bt_cz_006': {
        'name': 'Lužní les (jilm-jasan-olše)',
        'description': 'Elm-ash-alder floodplain forest with seasonal flooding',
        'can_host': ['tst_cz_006'],
    },
    'bt_cz_007': {
        'name': 'Borový bor na vátých píscích',
        'description': 'Pine woodland on dry acidic aeolian sand',
        'can_host': ['tst_cz_007'],
    },
    'bt_cz_008': {
        'name': 'Rašelinný bor (rašeliniště)',
        'description': 'Peat bog with Sphagnum, scattered Pinus rotundata',
        'can_host': ['tst_cz_008'],
    },
    'bt_cz_009': {
        'name': 'Otevřené jezero (paleolake)',
        'description': 'Open water with littoral reed belt',
        'can_host': ['tst_cz_009'],
    },
    'bt_cz_010': {
        'name': 'Říční lužní les (riparian)',
        'description': 'Riparian gallery forest along major river corridors',
        'can_host': ['tst_cz_006', 'tst_cz_005'],  # created from river buffer
    },
    'bt_cz_011': {
        'name': 'Lesní palouk (micro)',
        'description': 'Forest glade — small clearing within continuous forest',
        'can_host': ['tst_cz_001', 'tst_cz_002', 'tst_cz_005', 'tst_cz_007'],
    },
}

# Primary terrain -> biotope mapping (first match wins)
TERRAIN_TO_BIOTOPE = {
    'tst_cz_001': ('bt_cz_001', 1.0),
    'tst_cz_002': ('bt_cz_002', 1.0),
    'tst_cz_003': ('bt_cz_003', 0.9),
    'tst_cz_004': ('bt_cz_004', 0.8),
    'tst_cz_005': ('bt_cz_005', 1.0),
    'tst_cz_006': ('bt_cz_006', 0.9),
    'tst_cz_007': ('bt_cz_007', 1.0),
    'tst_cz_008': ('bt_cz_008', 0.7),
    'tst_cz_009': ('bt_cz_009', 0.8),
}

# CZ ecotone definitions: (biotope_a, biotope_b) -> ecotone record
CZ_ECOTONES = {
    'ec_cz_001': {
        'name': 'Les / Mokřad',
        'ecotone_of': ['bt_cz_002', 'bt_cz_003'],
        'edge_effect_factor': 1.4,
        'human_relevance': 'Hunting/gathering transition zone, freshwater access',
    },
    'ec_cz_002': {
        'name': 'Mokřad / Jezero',
        'ecotone_of': ['bt_cz_004', 'bt_cz_009'],
        'edge_effect_factor': 1.5,
        'human_relevance': 'Fishing, waterfowl, plant resources (reed, sedge)',
    },
    'ec_cz_003': {
        'name': 'Borový bor / Lužní les',
        'ecotone_of': ['bt_cz_007', 'bt_cz_006'],
        'edge_effect_factor': 1.3,
        'human_relevance': 'Dry camping on sand + wet resources in floodplain',
    },
    'ec_cz_004': {
        'name': 'Říční niva / Les',
        'ecotone_of': ['bt_cz_010', 'bt_cz_002'],
        'edge_effect_factor': 1.4,
        'human_relevance': 'Water corridor edge, seasonal resources',
    },
    'ec_cz_005': {
        'name': 'Borový bor / Rašelina',
        'ecotone_of': ['bt_cz_007', 'bt_cz_008'],
        'edge_effect_factor': 1.2,
        'human_relevance': 'Dry/wet transition on sand, peat resources',
    },
    'ec_cz_006': {
        'name': 'Les / Palouk (micro ekoton)',
        'ecotone_of': ['bt_cz_002', 'bt_cz_011'],
        'edge_effect_factor': 1.5,
        'human_relevance': 'High biodiversity edge, grazing, berries, hunting ambush',
    },
    'ec_cz_007': {
        'name': 'Krystalinikum / Pískovcová plošina',
        'ecotone_of': ['bt_cz_001', 'bt_cz_002'],
        'edge_effect_factor': 1.2,
        'human_relevance': 'Geological boundary, spring line, lithic source access',
    },
    'ec_cz_008': {
        'name': 'Terasa / Niva',
        'ecotone_of': ['bt_cz_005', 'bt_cz_006'],
        'edge_effect_factor': 1.3,
        'human_relevance': 'Dry ground overlooking floodplain — camp site preference',
    },
}

# Riparian zone width (~100m buffer in degrees at 49°N)
RIPARIAN_BUFFER_DEG = 0.0013  # ~100m at 49°N
# Glade detection: holes 0.5-5 ha within forest terrain
MIN_GLADE_AREA_DEG2 = 0.000005   # ~0.5 ha at 49°N
MAX_GLADE_AREA_DEG2 = 0.0005     # ~5 ha at 49°N
# Forest biotopes (where glades can occur)
FOREST_BIOTOPES = {'bt_cz_001', 'bt_cz_002', 'bt_cz_005', 'bt_cz_007'}


# ---------------------------------------------------------------------------
# Step 1: Assign biotopes
# ---------------------------------------------------------------------------

def assign_biotopes(terrain_geojson):
    """Assign dominant biotope to each terrain feature based on terrain_subtype."""
    print("=" * 60)
    print("Step 1: Assign biotopes")
    print("=" * 60)

    assigned = 0
    unassigned = 0

    for feature in terrain_geojson['features']:
        tst_id = feature['properties'].get('terrain_subtype_id')
        if tst_id and tst_id in TERRAIN_TO_BIOTOPE:
            bt_id, quality = TERRAIN_TO_BIOTOPE[tst_id]
            bt = CZ_BIOTOPES[bt_id]
            feature['properties']['biotope_id'] = bt_id
            feature['properties']['biotope_name'] = bt['name']
            feature['properties']['quality_modifier'] = quality
            assigned += 1
        else:
            feature['properties']['biotope_id'] = None
            feature['properties']['biotope_name'] = None
            feature['properties']['quality_modifier'] = 0.0
            unassigned += 1

    print(f"  Assigned: {assigned}, Unassigned: {unassigned}")

    # Distribution
    from collections import Counter
    dist = Counter(f['properties'].get('biotope_id') for f in terrain_geojson['features'])
    for bt_id, count in dist.most_common():
        name = CZ_BIOTOPES.get(bt_id, {}).get('name', '(none)') if bt_id else '(none)'
        print(f"    {bt_id}: {count}  {name}")

    return terrain_geojson


# ---------------------------------------------------------------------------
# Step 2: Create riparian zones
# ---------------------------------------------------------------------------

def create_riparian_zones(terrain_geojson):
    """Create riparian forest (bt_cz_010) sub-zones along rivers within floodplain polygons."""
    print("\n" + "=" * 60)
    print("Step 2: Riparian zones")
    print("=" * 60)

    rivers_path = os.path.join(DATA_DIR, 'rivers_cz.geojson')
    if not os.path.exists(rivers_path):
        print("  WARNING: rivers_cz.geojson not found, skipping riparian zones")
        return terrain_geojson, 0

    with open(rivers_path, encoding='utf-8') as f:
        rivers = json.load(f)

    # Build river union and buffer
    river_lines = []
    for feat in rivers['features']:
        try:
            river_lines.append(shape(feat['geometry']))
        except Exception:
            continue

    if not river_lines:
        print("  No river geometries found")
        return terrain_geojson, 0

    print(f"  Building riparian buffer from {len(river_lines)} river segments...")
    river_union = unary_union(river_lines)
    riparian_buffer = river_union.buffer(RIPARIAN_BUFFER_DEG)
    riparian_buffer = riparian_buffer.simplify(0.0002, preserve_topology=True)

    new_features = []
    riparian_count = 0
    feat_id = 2000

    # Terrain types where riparian corridors are created:
    # Primary (floodplain/terrace): tst_cz_005, tst_cz_006 — always create riparian
    # Secondary (other substrates rivers cross): create narrower riparian strip
    primary_riparian = {'tst_cz_005', 'tst_cz_006'}
    # All terrain types eligible for riparian zones (rivers cross them)
    riparian_eligible = {
        'tst_cz_001', 'tst_cz_002', 'tst_cz_003', 'tst_cz_004',
        'tst_cz_005', 'tst_cz_006', 'tst_cz_007', 'tst_cz_008', 'tst_cz_009',
    }

    for feature in terrain_geojson['features']:
        tst_id = feature['properties'].get('terrain_subtype_id')
        if tst_id not in riparian_eligible:
            new_features.append(feature)
            continue

        poly = shape(feature['geometry'])
        riparian_zone = poly.intersection(riparian_buffer)

        if riparian_zone.is_empty or riparian_zone.area < 0.000005:
            new_features.append(feature)
            continue

        remainder = poly.difference(riparian_buffer)

        # Skip if riparian is too small relative to total
        # For non-floodplain terrain, require at least 3% of polygon area
        min_pct = 0.03 if tst_id not in primary_riparian else 0.05
        if riparian_zone.area < poly.area * min_pct:
            new_features.append(feature)
            continue

        # Keep remainder with original biotope
        if not remainder.is_empty and remainder.area > 0.000005:
            remainder_feat = json.loads(json.dumps(feature))
            remainder_feat['geometry'] = mapping(make_valid(remainder) if not remainder.is_valid else remainder)
            new_features.append(remainder_feat)

        # Simplify and add riparian zone
        riparian_zone = riparian_zone.simplify(0.0002, preserve_topology=True)
        if not riparian_zone.is_valid:
            riparian_zone = make_valid(riparian_zone)
        if riparian_zone.is_empty:
            new_features.append(feature)
            continue

        feat_id += 1
        riparian_feat = {
            'type': 'Feature',
            'properties': {
                'id': f'tf_cz_rip_{feat_id:04d}',
                'terrain_subtype_id': tst_id,
                'biotope_id': 'bt_cz_010',
                'biotope_name': CZ_BIOTOPES['bt_cz_010']['name'],
                'quality_modifier': 1.0,
                'substrate': feature['properties'].get('substrate', ''),
                'hydrology': 'permanent_flow',
                'certainty': 'INFERENCE',
                'source': 'DIBAVOD river corridor + 100m buffer',
                'notes': 'riparian_zone',
            },
            'geometry': mapping(riparian_zone)
        }
        new_features.append(riparian_feat)
        riparian_count += 1

    terrain_geojson['features'] = new_features
    print(f"  Created {riparian_count} riparian zones")
    return terrain_geojson, riparian_count


# ---------------------------------------------------------------------------
# Step 3: Detect forest glades
# ---------------------------------------------------------------------------

def detect_glades(terrain_geojson):
    """Detect small clearings (glades) within forest-dominated terrain using polygon holes."""
    print("\n" + "=" * 60)
    print("Step 3: Glade detection")
    print("=" * 60)

    glade_count = 0
    glade_features = []
    feat_id = 3000

    for feature in terrain_geojson['features']:
        bt_id = feature['properties'].get('biotope_id')
        if bt_id not in FOREST_BIOTOPES:
            continue

        geom = shape(feature['geometry'])
        if geom.geom_type != 'Polygon':
            continue

        # Check interior rings (holes) as potential glades
        for interior in geom.interiors:
            from shapely.geometry import Polygon as ShapelyPolygon
            hole = ShapelyPolygon(interior)
            area = hole.area
            if MIN_GLADE_AREA_DEG2 <= area <= MAX_GLADE_AREA_DEG2:
                feat_id += 1
                glade_features.append({
                    'type': 'Feature',
                    'properties': {
                        'id': f'tf_cz_glade_{feat_id:04d}',
                        'terrain_subtype_id': feature['properties'].get('terrain_subtype_id'),
                        'biotope_id': 'bt_cz_011',
                        'biotope_name': CZ_BIOTOPES['bt_cz_011']['name'],
                        'quality_modifier': 0.8,
                        'substrate': feature['properties'].get('substrate', ''),
                        'hydrology': feature['properties'].get('hydrology', ''),
                        'certainty': 'INFERENCE',
                        'source': 'Polygon hole analysis (0.5-5 ha clearings)',
                        'notes': 'auto_glade',
                    },
                    'geometry': mapping(hole)
                })
                glade_count += 1

    terrain_geojson['features'].extend(glade_features)
    print(f"  Detected {glade_count} forest glades")
    return terrain_geojson


# ---------------------------------------------------------------------------
# Step 4: Generate ecotones
# ---------------------------------------------------------------------------

def generate_ecotones(terrain_geojson):
    """Generate ecotone lines from boundaries between adjacent polygons with different biotopes."""
    print("\n" + "=" * 60)
    print("Step 4: Ecotone generation")
    print("=" * 60)

    # Build ecotone lookup: frozenset of biotope pair -> ecotone definition
    ecotone_lookup = {}
    for eco_id, eco in CZ_ECOTONES.items():
        pair = frozenset(eco['ecotone_of'])
        ecotone_lookup[pair] = (eco_id, eco)

    # Build GeoDataFrame for spatial analysis
    features = terrain_geojson['features']
    gdf = gpd.GeoDataFrame.from_features(features, crs='EPSG:4326')

    sindex = gdf.sindex
    raw_segments = []
    processed_pairs = set()

    # Also collect generic ecotones for ANY adjacent different-biotope polygons
    generic_segments = []  # (bt_pair_frozenset, geometry)

    for idx, row in gdf.iterrows():
        if not row.get('biotope_id'):
            continue

        possible = list(sindex.intersection(row.geometry.bounds))
        for match_idx in possible:
            if match_idx == idx:
                continue

            pair_key = frozenset([idx, match_idx])
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            neighbor = gdf.iloc[match_idx]
            if not neighbor.get('biotope_id'):
                continue

            # Skip same-biotope boundaries (not ecotones)
            if row['biotope_id'] == neighbor['biotope_id']:
                continue

            if not row.geometry.intersects(neighbor.geometry):
                continue

            try:
                boundary = row.geometry.intersection(neighbor.geometry)
                if boundary.is_empty:
                    continue

                # Convert to line geometry
                if boundary.geom_type in ('Polygon', 'MultiPolygon'):
                    boundary = boundary.boundary
                elif boundary.geom_type == 'GeometryCollection':
                    lines = [g for g in boundary.geoms
                             if g.geom_type in ('LineString', 'MultiLineString')]
                    if not lines:
                        continue
                    boundary = unary_union(lines)

                if boundary.is_empty or boundary.geom_type == 'Point':
                    continue

                if boundary.geom_type == 'LineString':
                    boundary = MultiLineString([boundary])
                elif boundary.geom_type != 'MultiLineString':
                    continue

            except Exception:
                continue

            bt_pair = frozenset([row['biotope_id'], neighbor['biotope_id']])

            # Named ecotone (pre-defined pair)
            if bt_pair in ecotone_lookup:
                eco_id, eco = ecotone_lookup[bt_pair]
                raw_segments.append({
                    'eco_id': eco_id,
                    'eco': eco,
                    'geometry': boundary
                })

            # Generic ecotone (any different-biotope boundary)
            generic_segments.append({
                'bt_pair': bt_pair,
                'geometry': boundary
            })

    print(f"  Raw named ecotone segments: {len(raw_segments)}")
    print(f"  Raw generic ecotone segments: {len(generic_segments)}")

    # Merge segments by ecotone type
    from collections import defaultdict
    by_type = defaultdict(list)
    for seg in raw_segments:
        by_type[seg['eco_id']].append(seg['geometry'])

    ecotone_features = []
    for eco_id, geoms in by_type.items():
        eco = CZ_ECOTONES[eco_id]
        merged = unary_union(geoms)

        if merged.geom_type == 'LineString':
            merged = MultiLineString([merged])
        elif merged.geom_type == 'GeometryCollection':
            lines = [g for g in merged.geoms
                     if g.geom_type in ('LineString', 'MultiLineString')]
            if not lines:
                continue
            merged = unary_union(lines)
            if merged.geom_type == 'LineString':
                merged = MultiLineString([merged])
        elif merged.geom_type != 'MultiLineString':
            continue

        if merged.is_empty:
            continue

        ecotone_features.append({
            'type': 'Feature',
            'properties': {
                'id': eco_id,
                'name': eco['name'],
                'biotope_a_id': eco['ecotone_of'][0],
                'biotope_b_id': eco['ecotone_of'][1],
                'edge_effect_factor': eco['edge_effect_factor'],
                'human_relevance': eco['human_relevance'],
                'certainty': 'INFERENCE',
                'source': 'Polygon boundary analysis',
            },
            'geometry': mapping(merged)
        })

    print(f"  Merged named ecotone types: {len(ecotone_features)}")

    # Add generic ecotones: merge ALL different-biotope boundaries into one feature
    if generic_segments:
        all_generic_geoms = [seg['geometry'] for seg in generic_segments]
        generic_merged = unary_union(all_generic_geoms)
        if generic_merged.geom_type == 'LineString':
            generic_merged = MultiLineString([generic_merged])
        elif generic_merged.geom_type == 'GeometryCollection':
            lines = [g for g in generic_merged.geoms
                     if g.geom_type in ('LineString', 'MultiLineString')]
            if lines:
                generic_merged = unary_union(lines)
                if generic_merged.geom_type == 'LineString':
                    generic_merged = MultiLineString([generic_merged])

        if not generic_merged.is_empty and generic_merged.geom_type in ('MultiLineString', 'LineString'):
            if generic_merged.geom_type == 'LineString':
                generic_merged = MultiLineString([generic_merged])

            # Collect unique biotope pairs
            all_bt_ids = set()
            for seg in generic_segments:
                all_bt_ids.update(seg['bt_pair'])

            ecotone_features.append({
                'type': 'Feature',
                'properties': {
                    'id': 'ec_cz_generic',
                    'name': 'Obecny ekoton (vsechny biotopove hranice)',
                    'biotope_a_id': 'multiple',
                    'biotope_b_id': 'multiple',
                    'edge_effect_factor': 1.2,
                    'human_relevance': 'All biotope boundaries — ecotone diversity indicator',
                    'certainty': 'INFERENCE',
                    'source': 'Automatic boundary extraction from terrain+biotope polygons',
                    'biotope_ids': sorted(all_bt_ids),
                },
                'geometry': mapping(generic_merged)
            })
            print(f"  Added generic ecotone layer: ec_cz_generic ({len(generic_segments)} segments, {len(all_bt_ids)} biotope types)")

    # Add synthetic ecotones for lake boundaries
    ecotone_features = add_synthetic_lake_ecotone(ecotone_features, gdf)

    # Report
    found_ids = set(f['properties']['id'] for f in ecotone_features)
    for eco_id, eco in CZ_ECOTONES.items():
        status = "OK" if eco_id in found_ids else "MISSING (no adjacency)"
        print(f"    {eco_id}: {eco['name']} — {status}")

    return {
        'type': 'FeatureCollection',
        'name': 'ecotones_cz',
        'features': ecotone_features
    }


def add_synthetic_lake_ecotone(ecotone_features, gdf):
    """Add ec_cz_002 (Mokřad/Jezero) from paleolake polygon boundaries."""
    found_ids = set(f['properties']['id'] for f in ecotone_features)

    if 'ec_cz_002' not in found_ids:
        eco = CZ_ECOTONES['ec_cz_002']
        print(f"  Generating synthetic ec_cz_002 ({eco['name']}) from paleolake boundaries...")

        lake_rows = gdf[gdf['terrain_subtype_id'] == 'tst_cz_009']
        boundaries = []
        for _, row in lake_rows.iterrows():
            boundary = row.geometry.boundary
            if boundary and not boundary.is_empty:
                boundaries.append(boundary)

        if boundaries:
            merged = unary_union(boundaries)
            if merged.geom_type == 'LineString':
                merged = MultiLineString([merged])

            ecotone_features.append({
                'type': 'Feature',
                'properties': {
                    'id': 'ec_cz_002',
                    'name': eco['name'],
                    'biotope_a_id': eco['ecotone_of'][0],
                    'biotope_b_id': eco['ecotone_of'][1],
                    'edge_effect_factor': eco['edge_effect_factor'],
                    'human_relevance': eco['human_relevance'],
                    'certainty': 'INFERENCE',
                    'source': 'Synthetic — paleolake boundary as wetland/lake transition',
                },
                'geometry': mapping(merged)
            })
            print(f"    Added synthetic ec_cz_002")

    return ecotone_features


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def save_geojson(data, filename):
    out_path = os.path.join(DATA_DIR, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  Saved: {filename} ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Mezolit2 — KB Rules Application (Třeboňsko)")
    print("=" * 60)

    terrain_path = os.path.join(DATA_DIR, 'terrain_features_cz.geojson')
    if not os.path.exists(terrain_path):
        print(f"ERROR: {terrain_path} not found. Run 04_terrain_cz.py first.")
        sys.exit(1)

    with open(terrain_path, encoding='utf-8') as f:
        terrain_geojson = json.load(f)

    print(f"Loaded {len(terrain_geojson['features'])} terrain features\n")

    # Step 1: Assign biotopes
    terrain_geojson = assign_biotopes(terrain_geojson)

    # Step 2: Create riparian zones
    terrain_geojson, rip_count = create_riparian_zones(terrain_geojson)

    # Step 3: Detect glades
    terrain_geojson = detect_glades(terrain_geojson)

    # Step 4: Generate ecotones
    ecotones_geojson = generate_ecotones(terrain_geojson)

    # Export
    print("\n" + "=" * 60)
    print("EXPORT")
    print("=" * 60)
    save_geojson(terrain_geojson, 'terrain_features_with_biotopes_cz.geojson')
    save_geojson(ecotones_geojson, 'ecotones_cz.geojson')

    # Summary
    from collections import Counter
    bt_dist = Counter(f['properties'].get('biotope_id') for f in terrain_geojson['features'])
    print(f"\n  Final biotope distribution ({len(terrain_geojson['features'])} features):")
    for bt_id, count in bt_dist.most_common():
        name = CZ_BIOTOPES.get(bt_id, {}).get('name', '(none)') if bt_id else '(none)'
        print(f"    {bt_id}: {count}  {name}")

    print(f"\n  Ecotones: {len(ecotones_geojson['features'])} types")
    print("\nDone! Next: update frontend or run 06_import_supabase_cz.py")


if __name__ == '__main__':
    main()

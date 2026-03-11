"""
Apply KB rules to terrain polygons:
1. Assign dominant biotope to each terrain polygon via CAN_HOST graph traversal
2. Generate ecotone lines from boundaries of adjacent polygons with different biotopes

Input:  data/processed/terrain_features.geojson
        kb_data/schema_examples_v04.json
Output: data/processed/terrain_features_with_biotopes.geojson
        data/processed/ecotones.geojson

Usage:
    python 05_kb_rules.py
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json

try:
    from shapely.geometry import shape, mapping, MultiLineString
    from shapely.ops import unary_union, linemerge
    import geopandas as gpd
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
KB_PATH = os.path.join(os.path.dirname(__file__), '..', 'kb_data', 'schema_examples_v04.json')


def load_kb():
    with open(KB_PATH, encoding='utf-8') as f:
        return json.load(f)


def build_terrain_to_biotope_map(kb):
    """
    Build lookup: terrain_subtype_id -> dominant biotope.

    Selection rule:
    1. Filter: trigger = "baseline"
    2. Prefer: spatial_scale = "landscape" > "local" > "micro"
    3. Among same scale: highest quality_modifier
    """
    scale_priority = {'landscape': 3, 'local': 2, 'micro': 1}
    terrain_biotope = {}  # tst_id -> (biotope_id, biotope_name, quality_modifier)

    for biotope in kb['biotopes']['records']:
        bid = biotope['id']
        bname = biotope['name']

        for ch in biotope.get('can_host', []):
            if ch.get('trigger') != 'baseline':
                continue

            tst_id = ch['terrain_subtype']
            scale = ch.get('spatial_scale', 'landscape')
            quality = ch.get('quality_modifier', 1.0)
            priority = scale_priority.get(scale, 0)

            current = terrain_biotope.get(tst_id)
            if current is None:
                terrain_biotope[tst_id] = (bid, bname, quality, priority)
            else:
                _, _, cur_quality, cur_priority = current
                # Higher scale priority wins; same scale → higher quality wins
                if priority > cur_priority or (priority == cur_priority and quality > cur_quality):
                    terrain_biotope[tst_id] = (bid, bname, quality, priority)

    result = {}
    for tst_id, (bid, bname, quality, _) in terrain_biotope.items():
        result[tst_id] = {'biotope_id': bid, 'biotope_name': bname, 'quality_modifier': quality}

    return result


def create_riparian_zones(terrain_geojson):
    """
    Create riparian forest (bt_007) sub-zones along rivers within floodplain polygons.
    Splits large floodplain polygons into:
      - 0-100m from river → bt_007 (riparian)
      - remainder → bt_002 (wetland)
    """
    from shapely.geometry import shape as _shape
    from shapely.ops import unary_union as _union

    RIVERS_PATH = os.path.join(DATA_DIR, 'rivers_yorkshire.geojson')
    if not os.path.exists(RIVERS_PATH):
        return terrain_geojson, 0

    print("  Creating riparian zones (bt_007) along rivers in floodplains...")
    with open(RIVERS_PATH, encoding='utf-8') as f:
        rivers = json.load(f)

    # Merge all river lines and buffer by ~100m (in degrees)
    river_lines = []
    for feat in rivers['features']:
        try:
            river_lines.append(_shape(feat['geometry']))
        except Exception:
            continue

    if not river_lines:
        return terrain_geojson, 0

    river_union = _union(river_lines)
    riparian_buffer = river_union.buffer(0.001)  # ~100m at 54°N
    # Simplify the buffer to reduce vertex count (~20m tolerance)
    riparian_buffer = riparian_buffer.simplify(0.0002, preserve_topology=True)

    new_features = []
    riparian_count = 0
    feat_id = len(terrain_geojson['features']) + 1000

    for feature in terrain_geojson['features']:
        tst_id = feature['properties'].get('terrain_subtype_id')
        # Only split floodplain polygons
        if tst_id != 'tst_002':
            new_features.append(feature)
            continue

        poly = _shape(feature['geometry'])

        # Intersect with riparian buffer
        riparian_zone = poly.intersection(riparian_buffer)
        if riparian_zone.is_empty or riparian_zone.area < 0.000005:
            new_features.append(feature)
            continue

        # Remainder = floodplain minus riparian
        remainder = poly.difference(riparian_buffer)

        # Keep original if riparian is too small relative to total
        if riparian_zone.area < poly.area * 0.05:
            new_features.append(feature)
            continue

        # Add remainder as floodplain
        if not remainder.is_empty and remainder.area > 0.000005:
            remainder_feat = dict(feature)
            remainder_feat['properties'] = dict(feature['properties'])
            remainder_feat['geometry'] = mapping(remainder)
            new_features.append(remainder_feat)

        # Simplify and add riparian zone
        riparian_zone = riparian_zone.simplify(0.0002, preserve_topology=True)
        if not riparian_zone.is_valid:
            riparian_zone = riparian_zone.buffer(0)
        if riparian_zone.is_empty:
            new_features.append(feature)
            continue

        feat_id += 1
        riparian_feat = {
            'type': 'Feature',
            'properties': {
                'id': f'tf_rip_{feat_id:04d}',
                'terrain_subtype_id': 'tst_002',
                'anchor_site': False,
                'notes': 'riparian_zone',
                'certainty': 'INFERENCE',
                'source': 'DEM river corridor + 100m buffer'
            },
            'geometry': mapping(riparian_zone)
        }
        new_features.append(riparian_feat)
        riparian_count += 1

    terrain_geojson['features'] = new_features
    return terrain_geojson, riparian_count


def assign_biotopes(terrain_geojson, terrain_biotope_map):
    """
    Assign dominant biotope to each terrain feature.
    Smart glade detection: auto_glade features surrounded by forest get bt_009.
    Riparian zones get bt_007, chalk scrub gets bt_006.
    """
    print("Assigning dominant biotopes...")

    # Create riparian sub-zones before assignment
    terrain_geojson, rip_count = create_riparian_zones(terrain_geojson)
    if rip_count > 0:
        print(f"  Created {rip_count} riparian zones")

    assigned = 0
    unassigned = 0
    glades_detected = 0

    # First pass: assign standard biotopes
    for feature in terrain_geojson['features']:
        tst_id = feature['properties'].get('terrain_subtype_id')
        if tst_id and tst_id in terrain_biotope_map:
            bt = terrain_biotope_map[tst_id]
            feature['properties']['biotope_id'] = bt['biotope_id']
            feature['properties']['biotope_name'] = bt['biotope_name']
            feature['properties']['quality_modifier'] = bt['quality_modifier']
            assigned += 1
        else:
            feature['properties']['biotope_id'] = None
            feature['properties']['biotope_name'] = None
            unassigned += 1

    # Second pass: override auto_glade features with bt_009 (forest glade)
    FOREST_BIOTOPE = 'bt_003'
    GLADE_BIOTOPE_ID = 'bt_009'
    GLADE_BIOTOPE_NAME = 'Lesni palouk (micro)'

    for feature in terrain_geojson['features']:
        notes = feature['properties'].get('notes', '')
        if notes == 'auto_glade':
            tst_id = feature['properties'].get('terrain_subtype_id')
            parent_bt = terrain_biotope_map.get(tst_id, {})
            if parent_bt.get('biotope_id') == FOREST_BIOTOPE:
                feature['properties']['biotope_id'] = GLADE_BIOTOPE_ID
                feature['properties']['biotope_name'] = GLADE_BIOTOPE_NAME
                feature['properties']['quality_modifier'] = 0.8
                glades_detected += 1

    # Third pass: override riparian zones with bt_007
    riparian_assigned = 0
    for feature in terrain_geojson['features']:
        notes = feature['properties'].get('notes', '')
        if notes == 'riparian_zone':
            feature['properties']['biotope_id'] = 'bt_007'
            feature['properties']['biotope_name'] = 'Ricni luzni les (riparian)'
            feature['properties']['quality_modifier'] = 1.0
            riparian_assigned += 1

    # Fourth pass: mark sea polygon
    for feature in terrain_geojson['features']:
        if feature['properties'].get('notes') == 'open_sea':
            feature['properties']['biotope_id'] = None
            feature['properties']['biotope_name'] = 'Open sea'
            feature['properties']['quality_modifier'] = 0.0

    print(f"  Assigned: {assigned}, Unassigned: {unassigned}")
    print(f"  Glades (bt_009): {glades_detected}, Riparian (bt_007): {riparian_assigned}")
    return terrain_geojson


def build_ecotone_lookup(kb):
    """Build set of valid biotope pairs that form ecotones."""
    ecotone_lookup = {}  # frozenset({bt_a, bt_b}) -> ecotone record
    for eco in kb['ecotones']['records']:
        pair = frozenset(eco['ecotone_of'])
        ecotone_lookup[pair] = eco
    return ecotone_lookup


def generate_ecotones(terrain_geojson, ecotone_lookup):
    """
    Generate ecotone lines from boundaries between adjacent terrain polygons
    with different biotopes that match ecotone definitions.
    """
    print("Generating ecotones from polygon boundaries...")

    # Build GeoDataFrame for spatial analysis
    features = terrain_geojson['features']
    gdf = gpd.GeoDataFrame.from_features(features, crs='EPSG:4326')

    # Build spatial index
    sindex = gdf.sindex

    ecotone_features = []
    processed_pairs = set()

    for idx, row in gdf.iterrows():
        if not row.get('biotope_id'):
            continue

        # Find neighboring polygons
        possible_matches = list(sindex.intersection(row.geometry.bounds))

        for match_idx in possible_matches:
            if match_idx == idx:
                continue

            # Avoid processing same pair twice
            pair_key = frozenset([idx, match_idx])
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            neighbor = gdf.iloc[match_idx]
            if not neighbor.get('biotope_id'):
                continue

            # Check if this biotope pair forms a known ecotone
            bt_pair = frozenset([row['biotope_id'], neighbor['biotope_id']])
            if bt_pair not in ecotone_lookup:
                continue

            # Check if polygons actually touch
            if not row.geometry.touches(neighbor.geometry) and not row.geometry.intersects(neighbor.geometry):
                continue

            # Extract shared boundary
            try:
                boundary = row.geometry.intersection(neighbor.geometry)
                if boundary.is_empty:
                    continue

                # Convert to line if it's a polygon boundary
                if boundary.geom_type in ('Polygon', 'MultiPolygon'):
                    boundary = boundary.boundary
                elif boundary.geom_type == 'GeometryCollection':
                    lines = [g for g in boundary.geoms if g.geom_type in ('LineString', 'MultiLineString')]
                    if not lines:
                        continue
                    boundary = unary_union(lines)

                if boundary.is_empty or boundary.geom_type == 'Point':
                    continue

                # Ensure MultiLineString
                if boundary.geom_type == 'LineString':
                    boundary = MultiLineString([boundary])
                elif boundary.geom_type != 'MultiLineString':
                    continue

            except Exception:
                continue

            eco = ecotone_lookup[bt_pair]
            ecotone_features.append({
                'type': 'Feature',
                'properties': {
                    'id': eco['id'],
                    'name': eco['name'],
                    'biotope_a_id': eco['ecotone_of'][0],
                    'biotope_b_id': eco['ecotone_of'][1],
                    'edge_effect_factor': eco['attributes'].get('edge_effect_factor'),
                    'human_relevance': eco['attributes'].get('human_relevance'),
                    'certainty': eco['epistemics']['certainty'],
                    'source': eco['epistemics']['source']
                },
                'geometry': mapping(boundary)
            })

    print(f"  Generated {len(ecotone_features)} raw ecotone segments")

    # Merge segments: group by ecotone ID, merge into single MultiLineString each
    ecotone_features = merge_ecotone_segments(ecotone_features)
    print(f"  After merging: {len(ecotone_features)} unique ecotone types")

    # Synthetic fallbacks for ecotones that weren't generated naturally
    found_ids = set(f['properties']['id'] for f in ecotone_features)
    ecotone_features = add_synthetic_ecotones(
        ecotone_features, ecotone_lookup, found_ids, gdf
    )

    # Report missing ecotones
    final_ids = set(f['properties']['id'] for f in ecotone_features)
    all_eco_ids = set(eco['id'] for eco in ecotone_lookup.values())
    still_missing = all_eco_ids - final_ids
    if still_missing:
        for mid in sorted(still_missing):
            eco = next(e for e in ecotone_lookup.values() if e['id'] == mid)
            print(f"  NOTE: {mid} ({eco['name']}) — no geometry (insufficient adjacency)")

    return {
        'type': 'FeatureCollection',
        'features': ecotone_features
    }


def merge_ecotone_segments(ecotone_features):
    """Merge all segments belonging to the same ecotone ID into one MultiLineString."""
    from collections import defaultdict

    segments_by_id = defaultdict(list)
    props_by_id = {}

    for f in ecotone_features:
        eco_id = f['properties']['id']
        geom = shape(f['geometry'])
        segments_by_id[eco_id].append(geom)
        if eco_id not in props_by_id:
            props_by_id[eco_id] = f['properties']

    merged_features = []
    for eco_id, segments in segments_by_id.items():
        merged = unary_union(segments)

        # Ensure MultiLineString
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
        elif merged.geom_type == 'MultiLineString':
            pass  # already correct type
        else:
            continue

        if merged.is_empty:
            continue

        merged_features.append({
            'type': 'Feature',
            'properties': props_by_id[eco_id],
            'geometry': mapping(merged)
        })

    return merged_features


def add_synthetic_ecotones(ecotone_features, ecotone_lookup, found_ids, gdf):
    """Add synthetic ecotone lines for types not generated from polygon boundaries."""

    # ec_002 (Mokřad/Jezero): use Lake Flixton boundary as wetland/lake transition
    bt_pair_002 = frozenset(['bt_002', 'bt_001'])
    if bt_pair_002 in ecotone_lookup:
        eco = ecotone_lookup[bt_pair_002]
        if eco['id'] not in found_ids:
            print(f"  Generating synthetic {eco['id']} ({eco['name']}) from lake boundary...")
            lake_rows = gdf[gdf['terrain_subtype_id'] == 'tst_001']
            for _, row in lake_rows.iterrows():
                boundary = row.geometry.boundary
                if boundary and not boundary.is_empty:
                    if boundary.geom_type == 'LineString':
                        boundary = MultiLineString([boundary])
                    ecotone_features.append({
                        'type': 'Feature',
                        'properties': {
                            'id': eco['id'],
                            'name': eco['name'],
                            'biotope_a_id': eco['ecotone_of'][0],
                            'biotope_b_id': eco['ecotone_of'][1],
                            'edge_effect_factor': eco['attributes'].get('edge_effect_factor'),
                            'human_relevance': eco['attributes'].get('human_relevance'),
                            'certainty': 'INFERENCE',
                            'source': 'synthetic — lake boundary as wetland/lake transition'
                        },
                        'geometry': mapping(boundary)
                    })
                    found_ids.add(eco['id'])
                    print(f"    Added synthetic {eco['id']}")

    # ec_004 (Říční niva / Les): use floodplain/forest boundaries if not found
    bt_pair_004 = frozenset(['bt_007', 'bt_003'])
    if bt_pair_004 in ecotone_lookup:
        eco = ecotone_lookup[bt_pair_004]
        if eco['id'] not in found_ids:
            # Try bt_002/bt_003 boundary as fallback (wetland is dominant for floodplain)
            bt_pair_alt = frozenset(['bt_002', 'bt_003'])
            if bt_pair_alt in ecotone_lookup:
                # Already covered by ec_001 (Les/Mokřad) — create synthetic from
                # floodplain polygon boundaries touching forest polygons
                print(f"  Generating synthetic {eco['id']} ({eco['name']}) from floodplain/forest boundaries...")
                floodplain_rows = gdf[gdf['terrain_subtype_id'] == 'tst_002']
                forest_rows = gdf[gdf['biotope_id'] == 'bt_003']

                if len(floodplain_rows) > 0 and len(forest_rows) > 0:
                    fp_union = unary_union(floodplain_rows.geometry.values)
                    forest_union = unary_union(forest_rows.geometry.values)
                    boundary = fp_union.intersection(forest_union)

                    if not boundary.is_empty:
                        # Extract lines
                        if boundary.geom_type in ('Polygon', 'MultiPolygon'):
                            boundary = boundary.boundary
                        elif boundary.geom_type == 'GeometryCollection':
                            lines = [g for g in boundary.geoms
                                     if g.geom_type in ('LineString', 'MultiLineString')]
                            boundary = unary_union(lines) if lines else None

                        if boundary and not boundary.is_empty:
                            if boundary.geom_type == 'LineString':
                                boundary = MultiLineString([boundary])
                            ecotone_features.append({
                                'type': 'Feature',
                                'properties': {
                                    'id': eco['id'],
                                    'name': eco['name'],
                                    'biotope_a_id': eco['ecotone_of'][0],
                                    'biotope_b_id': eco['ecotone_of'][1],
                                    'edge_effect_factor': eco['attributes'].get('edge_effect_factor'),
                                    'human_relevance': eco['attributes'].get('human_relevance'),
                                    'certainty': 'INFERENCE',
                                    'source': 'synthetic — floodplain/forest boundary'
                                },
                                'geometry': mapping(boundary)
                            })
                            found_ids.add(eco['id'])
                            print(f"    Added synthetic {eco['id']}")

    # ec_005 (Pobřeží/Mokřad): use tidal/floodplain boundary if not found naturally
    bt_pair_005 = frozenset(['bt_005', 'bt_002'])
    if bt_pair_005 in ecotone_lookup:
        eco = ecotone_lookup[bt_pair_005]
        if eco['id'] not in found_ids:
            print(f"  Generating synthetic {eco['id']} ({eco['name']}) from tidal/wetland boundaries...")
            tidal_rows = gdf[gdf['terrain_subtype_id'] == 'tst_008']
            wetland_rows = gdf[gdf['biotope_id'] == 'bt_002']
            if len(tidal_rows) > 0 and len(wetland_rows) > 0:
                tidal_union = unary_union(tidal_rows.geometry.values)
                wetland_union = unary_union(wetland_rows.geometry.values)
                boundary = tidal_union.intersection(wetland_union)
                if not boundary.is_empty:
                    if boundary.geom_type in ('Polygon', 'MultiPolygon'):
                        boundary = boundary.boundary
                    elif boundary.geom_type == 'GeometryCollection':
                        lines = [g for g in boundary.geoms
                                 if g.geom_type in ('LineString', 'MultiLineString')]
                        boundary = unary_union(lines) if lines else None
                    if boundary and not boundary.is_empty:
                        if boundary.geom_type == 'LineString':
                            boundary = MultiLineString([boundary])
                        ecotone_features.append({
                            'type': 'Feature',
                            'properties': {
                                'id': eco['id'],
                                'name': eco['name'],
                                'biotope_a_id': eco['ecotone_of'][0],
                                'biotope_b_id': eco['ecotone_of'][1],
                                'edge_effect_factor': eco['attributes'].get('edge_effect_factor'),
                                'human_relevance': eco['attributes'].get('human_relevance'),
                                'certainty': 'INFERENCE',
                                'source': 'synthetic — tidal/wetland boundary'
                            },
                            'geometry': mapping(boundary)
                        })
                        found_ids.add(eco['id'])
                        print(f"    Added synthetic {eco['id']}")

    return ecotone_features


def save_geojson(data, filename):
    out_path = os.path.join(DATA_DIR, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  Saved: {filename} ({size_mb:.1f} MB)")


def main():
    print("=" * 60)
    print("Mezolit2 — KB Rules Application")
    print("=" * 60)

    # Load KB
    print("Loading KB data...")
    kb = load_kb()

    # Load terrain features
    terrain_path = os.path.join(DATA_DIR, 'terrain_features.geojson')
    if not os.path.exists(terrain_path):
        print(f"ERROR: {terrain_path} not found. Run 04_terrain.py first.")
        sys.exit(1)

    with open(terrain_path, encoding='utf-8') as f:
        terrain_geojson = json.load(f)

    print(f"Loaded {len(terrain_geojson['features'])} terrain features")

    # Build biotope assignment map
    terrain_biotope_map = build_terrain_to_biotope_map(kb)
    print(f"Biotope mapping: {len(terrain_biotope_map)} terrain_subtypes → biotopes")
    for tst_id, bt in sorted(terrain_biotope_map.items()):
        print(f"  {tst_id} → {bt['biotope_id']} ({bt['biotope_name']})")

    # Assign biotopes
    terrain_geojson = assign_biotopes(terrain_geojson, terrain_biotope_map)
    save_geojson(terrain_geojson, 'terrain_features_with_biotopes.geojson')

    # Generate ecotones
    ecotone_lookup = build_ecotone_lookup(kb)
    print(f"Ecotone definitions: {len(ecotone_lookup)} biotope pairs")
    ecotones_geojson = generate_ecotones(terrain_geojson, ecotone_lookup)
    save_geojson(ecotones_geojson, 'ecotones.geojson')

    print(f"\nDone!")
    print("Next step: python 06_import_supabase.py")


if __name__ == '__main__':
    main()

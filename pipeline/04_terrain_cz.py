"""
Generate terrain_subtype polygons for Trebonsko from CGS geology + DEM + DIBAVOD.

Unlike Yorkshire (DEM-only classification), Czech pipeline uses vector geology
from CGS geological map 1:50000 as primary source, with DEM for slope/elevation
enrichment and DIBAVOD for river network.

Input:  data/raw/cz/dem/trebonsko_dmr5g_10m.tif
        data/raw/cz/cgs/geologicka_mapa50.geojson
        data/raw/cz/dibavod/A02/A02_Vodni_tok_JU.shp
        data/raw/cz/dibavod/A05/A05_Vodni_nadrze.shp
        data/raw/cz/dibavod/A06/A06_Bazina_mocal.shp
        data/raw/cz/paleolakes_cz.geojson
        data/raw/cz/vmb/vmb_biotopy.geojson
        data/raw/cz/amcr/amcr_mezolit_trebonsko.geojson

Output: data/processed/cz/terrain_features_cz.geojson
        data/processed/cz/rivers_cz.geojson
        data/processed/cz/paleolakes_cz.geojson
        data/processed/cz/sites_cz.geojson

Usage:
    python 04_terrain_cz.py [--skip-dem] [--only STEP]
"""

import os
import sys
import json
import argparse
import numpy as np

try:
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.features import shapes
    from shapely.geometry import shape, mapping, box, Point, MultiPolygon, Polygon
    from shapely.ops import unary_union
    from shapely.validation import make_valid
    import geopandas as gpd
    import pandas as pd
    import fiona
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install -r requirements.txt")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trebonsko bounding box (WGS84)
BBOX_WGS84 = {
    'west': 14.53, 'east': 14.95,
    'south': 48.93, 'north': 49.22
}

# Svarcenberk anchor (49.148N, 14.707E)
SVARCENBERK = {
    'lat': 49.148, 'lon': 14.707,
    'terrain_subtype': 'tst_cz_009',
    'name': 'Svarcenberk paleolake',
    'certainty': 'INDIRECT',
    'source': 'Pokorny et al. 2010; Sida et al. 2007'
}

# Helper: check if CGS feature is Cretaceous
def _is_krida(f):
    o = f.get('oblast', '').lower()
    return 'křída' in o or 'krida' in o or 'kříd' in o

# Helper: check if CGS feature is moldanubikum
def _is_moldanubikum(f):
    s = f.get('soustava', '').lower()
    o = f.get('oblast', '').lower()
    return 'moldanubik' in s or 'moldanubik' in o or 'krystalinikum' in s

# CGS geneze -> terrain_subtype mapping (GEO_DESIGN_v02 section 3.2)
# Key: (geneze, oblast/soustava pattern) -> terrain_subtype_id
# CGS fields: geneze, hor_typ, hor_karto, soustava, oblast

CGS_MAPPING = {
    # tst_cz_001: Crystalline basement (moldanubikum)
    'crystalline': {
        'id': 'tst_cz_001',
        'substrate': 'crystalline_basement',
        'hydrology': 'well_drained',
        'match': lambda f: (
            _is_moldanubikum(f)
            and 'kvart' not in f.get('oblast', '').lower()
        )
    },
    # tst_cz_002: Cretaceous sandstone (Klikovské souvrství svrchní)
    # Note: CGS hor_karto="pískovce, slepence, jílovce a prachovce" for ALL
    # Cretaceous features -- cannot differentiate by hor_karto alone.
    # Use 'vrstvy' field: "klikovské svrchní" = predominantly sandstone,
    #                      "klikovské spodní" = predominantly claystone.
    'cret_sand': {
        'id': 'tst_cz_002',
        'substrate': 'cretaceous_sandstone',
        'hydrology': 'well_drained',
        'match': lambda f: (
            _is_krida(f)
            and 'svrchní' in f.get('vrstvy', '').lower()
        )
    },
    # tst_cz_003: Cretaceous claystone (Klikovské souvrství spodní)
    'cret_clay': {
        'id': 'tst_cz_003',
        'substrate': 'cretaceous_claystone',
        'hydrology': 'high_water_table',
        'match': lambda f: (
            _is_krida(f)
            and 'spodní' in f.get('vrstvy', '').lower()
        )
    },
    # tst_cz_004: Neogene lacustrine
    'neogene': {
        'id': 'tst_cz_004',
        'substrate': 'neogene_lacustrine',
        'hydrology': 'high_water_table',
        'match': lambda f: (
            'terci' in f.get('oblast', '').lower()
            or ('neog' in f.get('utvar', '').lower() if f.get('utvar') else False)
        )
    },
    # tst_cz_005: River terrace (pleistocene gravel)
    'terrace': {
        'id': 'tst_cz_005',
        'substrate': 'river_gravel',
        'hydrology': 'well_drained',
        'match': lambda f: (
            'kvart' in f.get('oblast', '').lower()
            and any(k in f.get('geneze', '').lower() for k in ['fluviální', 'fluvi', 'terasov'])
            and any(k in f.get('hor_karto', '').lower() for k in [
                'štěrk', 'písek', 'štěrkopís', 'stěrk', 'stěrkopis'
            ])
        )
    },
    # tst_cz_006: Floodplain (holocene alluvium)
    'floodplain': {
        'id': 'tst_cz_006',
        'substrate': 'alluvial_clay_peat',
        'hydrology': 'seasonal_flooding',
        'match': lambda f: (
            'kvart' in f.get('oblast', '').lower()
            and any(k in f.get('geneze', '').lower() for k in ['fluvi', 'nivní', 'aluviáln', 'deluvio'])
            and not any(k in f.get('hor_karto', '').lower() for k in ['štěrk', 'štěrkopís'])
        )
    },
    # tst_cz_007: Aeolian sand
    'aeolian': {
        'id': 'tst_cz_007',
        'substrate': 'aeolian_sand',
        'hydrology': 'well_drained',
        'match': lambda f: (
            any(k in f.get('geneze', '').lower() for k in ['eolick', 'eolic', 'vátý', 'váté'])
        )
    },
    # tst_cz_008: Peat
    'peat': {
        'id': 'tst_cz_008',
        'substrate': 'peat',
        'hydrology': 'permanent_saturation',
        'match': lambda f: (
            any(k in f.get('geneze', '').lower() for k in ['organick', 'organická'])
            or any(k in f.get('hor_karto', '').lower() for k in ['rašelin', 'slatin', 'rašelina'])
        )
    },
    # tst_cz_009: Paleolake (lacustrine sediments) -- also matched from paleolakes layer
    'lacustrine': {
        'id': 'tst_cz_009',
        'substrate': 'organic_lacustrine_sediment',
        'hydrology': 'permanent_standing_water',
        'match': lambda f: (
            any(k in f.get('geneze', '').lower() for k in ['lakustrin', 'jezerní', 'jezern'])
        )
    },
    # Fallback for remaining Quaternary
    'quaternary_other': {
        'id': 'tst_cz_006',  # default to floodplain for unclassified quaternary
        'substrate': 'alluvial_clay_peat',
        'hydrology': 'moderate_moisture',
        'match': lambda f: 'kvart' in f.get('oblast', '').lower()
    },
    # Fallback for remaining Cretaceous
    'cretaceous_other': {
        'id': 'tst_cz_002',  # default to sandstone for unclassified cretaceous
        'substrate': 'cretaceous_sandstone',
        'hydrology': 'well_drained',
        'match': lambda f: _is_krida(f)
    },
}

# Ordered matching (first match wins)
CGS_MATCH_ORDER = [
    'aeolian', 'peat', 'lacustrine', 'terrace', 'floodplain',
    'crystalline', 'neogene',
    'cret_clay', 'cret_sand',
    'quaternary_other', 'cretaceous_other'
]

# Polygon processing
MIN_POLYGON_AREA_DEG2 = 0.000005   # ~0.05 km2 at 49N
SIMPLIFY_TOLERANCE = 0.0002         # ~20m
LARGE_POLYGON_AREA = 0.001          # ~10 km2
LARGE_SIMPLIFY_TOLERANCE = 0.0005   # ~50m

# Rivers
RIVER_BUFFER_M = 400  # Default river corridor width

# Paths
BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
RAW_CZ = os.path.join(BASE_DIR, 'data', 'raw', 'cz')
OUT_DIR = os.path.join(BASE_DIR, 'data', 'processed', 'cz')


# ---------------------------------------------------------------------------
# Step 1: Load CGS geology and classify terrain_subtypes
# ---------------------------------------------------------------------------

def classify_cgs_geology():
    """Map CGS geological polygons to KB terrain_subtypes."""
    print("=" * 60)
    print("Step 1: CGS geology -> terrain_subtypes")
    print("=" * 60)

    cgs_path = os.path.join(RAW_CZ, 'cgs', 'geologicka_mapa50.geojson')
    if not os.path.exists(cgs_path):
        print(f"  ERROR: {cgs_path} not found. Run 02c_download_cz.py first.")
        return None

    print(f"  Loading {cgs_path}...")
    gdf = gpd.read_file(cgs_path)
    print(f"  Loaded {len(gdf)} features")

    # Clip to bbox
    bbox_poly = box(BBOX_WGS84['west'], BBOX_WGS84['south'],
                    BBOX_WGS84['east'], BBOX_WGS84['north'])
    gdf = gdf[gdf.geometry.intersects(bbox_poly)].copy()
    gdf['geometry'] = gdf.geometry.intersection(bbox_poly)
    # Remove empty geometries
    gdf = gdf[~gdf.geometry.is_empty].copy()
    print(f"  After bbox clip: {len(gdf)} features")

    # Classify each polygon
    stats = {}
    terrain_data = []

    for idx, row in gdf.iterrows():
        props = row.to_dict()
        props.pop('geometry', None)

        # Try matchers in order
        matched = False
        for key in CGS_MATCH_ORDER:
            rule = CGS_MAPPING[key]
            try:
                if rule['match'](props):
                    tst = rule['id']
                    stats[tst] = stats.get(tst, 0) + 1
                    terrain_data.append({
                        'geometry': row.geometry,
                        'terrain_subtype_id': tst,
                        'substrate': rule['substrate'],
                        'hydrology': rule['hydrology'],
                        'cgs_geneze': props.get('geneze', ''),
                        'cgs_oblast': props.get('oblast', ''),
                        'cgs_hor_karto': props.get('hor_karto', ''),
                        'certainty': 'DIRECT',
                        'source': 'CGS geologicka mapa 1:50000'
                    })
                    matched = True
                    break
            except Exception:
                continue

        if not matched:
            # Absolute fallback: crystalline basement
            stats['tst_cz_001'] = stats.get('tst_cz_001', 0) + 1
            terrain_data.append({
                'geometry': row.geometry,
                'terrain_subtype_id': 'tst_cz_001',
                'substrate': 'crystalline_basement',
                'hydrology': 'well_drained',
                'cgs_geneze': props.get('geneze', ''),
                'cgs_oblast': props.get('oblast', ''),
                'cgs_hor_karto': props.get('hor_karto', ''),
                'certainty': 'INFERENCE',
                'source': 'CGS geologicka mapa 1:50000 (unmatched fallback)'
            })

    print("\n  Terrain subtype distribution:")
    for tst in sorted(stats.keys()):
        print(f"    {tst}: {stats[tst]} polygons")

    terrain_gdf = gpd.GeoDataFrame(terrain_data, crs='EPSG:4326')
    return terrain_gdf


# ---------------------------------------------------------------------------
# Step 2: Dissolve by terrain_subtype and simplify
# ---------------------------------------------------------------------------

def dissolve_and_simplify(terrain_gdf):
    """Dissolve adjacent polygons with same terrain_subtype, then simplify."""
    print("\n" + "=" * 60)
    print("Step 2: Dissolve and simplify")
    print("=" * 60)

    # Dissolve by terrain_subtype_id
    print("  Dissolving by terrain_subtype_id...")
    dissolved = terrain_gdf.dissolve(by='terrain_subtype_id', aggfunc='first').reset_index()
    print(f"  After dissolve: {len(dissolved)} multipolygons")

    # Explode multipolygons to individual polygons
    print("  Exploding multipolygons...")
    exploded = dissolved.explode(index_parts=False).reset_index(drop=True)
    print(f"  After explode: {len(exploded)} polygons")

    # Filter tiny polygons
    before = len(exploded)
    exploded = exploded[exploded.geometry.area >= MIN_POLYGON_AREA_DEG2].copy()
    print(f"  Removed {before - len(exploded)} tiny polygons (< {MIN_POLYGON_AREA_DEG2} deg2)")

    # Simplify
    print("  Simplifying...")
    simplified_geoms = []
    for idx, row in exploded.iterrows():
        geom = row.geometry
        tol = LARGE_SIMPLIFY_TOLERANCE if geom.area > LARGE_POLYGON_AREA else SIMPLIFY_TOLERANCE
        simp = geom.simplify(tol, preserve_topology=True)
        if simp.is_valid and not simp.is_empty:
            simplified_geoms.append(simp)
        else:
            simplified_geoms.append(make_valid(simp) if not simp.is_empty else geom)

    exploded = exploded.copy()
    exploded['geometry'] = simplified_geoms

    # Assign feature IDs
    exploded['id'] = [f'tf_cz_{i:04d}' for i in range(1, len(exploded) + 1)]

    print(f"  Final: {len(exploded)} terrain features")
    return exploded


# ---------------------------------------------------------------------------
# Step 3: Overlay paleolakes (tst_cz_009)
# ---------------------------------------------------------------------------

def overlay_paleolakes(terrain_gdf):
    """Overlay paleolake polygons as tst_cz_009, replacing underlying terrain."""
    print("\n" + "=" * 60)
    print("Step 3: Paleolakes overlay")
    print("=" * 60)

    paleo_path = os.path.join(RAW_CZ, 'paleolakes_cz.geojson')
    if not os.path.exists(paleo_path):
        print(f"  WARNING: {paleo_path} not found, skipping paleolakes overlay")
        return terrain_gdf

    paleo = gpd.read_file(paleo_path)
    print(f"  Loaded {len(paleo)} paleolake features")

    # Clip to bbox
    bbox_poly = box(BBOX_WGS84['west'], BBOX_WGS84['south'],
                    BBOX_WGS84['east'], BBOX_WGS84['north'])
    paleo = paleo[paleo.geometry.intersects(bbox_poly)].copy()
    paleo['geometry'] = paleo.geometry.intersection(bbox_poly)
    paleo = paleo[~paleo.geometry.is_empty].copy()
    print(f"  After bbox clip: {len(paleo)} paleolake features")

    if len(paleo) == 0:
        return terrain_gdf

    # Explode MultiPolygons into individual polygons to break mega-clusters
    # (CGS dissolves related sediment types into huge MultiPolygons, e.g. 6000 ha)
    before_explode = len(paleo)
    paleo = paleo.explode(index_parts=False).reset_index(drop=True)
    # Filter out tiny fragments
    paleo = paleo[paleo.geometry.area >= MIN_POLYGON_AREA_DEG2].copy()
    print(f"  After explode: {before_explode} -> {len(paleo)} individual polygons")

    # Cap max paleolake size at ~200 ha (0.002 deg2 at 49N ≈ 200 ha)
    MAX_PALEOLAKE_DEG2 = 0.002
    oversized = paleo[paleo.geometry.area > MAX_PALEOLAKE_DEG2]
    if len(oversized) > 0:
        print(f"  WARNING: {len(oversized)} paleolake polygons exceed ~200 ha cap")
        print(f"    (keeping them but flagging as INFERENCE certainty)")
        paleo.loc[paleo.geometry.area > MAX_PALEOLAKE_DEG2, 'certainty'] = 'INFERENCE'

    # Union all paleolake polygons
    paleo_union = unary_union(paleo.geometry.tolist())

    # Cut paleolake areas out of terrain polygons
    print("  Cutting paleolake areas from terrain...")
    cut_records = []
    for idx, row in terrain_gdf.iterrows():
        diff = row.geometry.difference(paleo_union)
        if diff.is_empty:
            continue
        rec = row.to_dict()
        rec['geometry'] = diff
        cut_records.append(rec)

    # Add paleolake features
    print("  Adding paleolake terrain features...")
    for idx, row in paleo.iterrows():
        cert = row.get('certainty', 'INFERENCE')
        cut_records.append({
            'geometry': row.geometry,
            'terrain_subtype_id': row.get('terrain_subtype', 'tst_cz_009'),
            'substrate': 'organic_lacustrine_sediment',
            'hydrology': 'permanent_standing_water',
            'cgs_geneze': 'lacustrine/organic',
            'cgs_oblast': 'quaternary',
            'cgs_hor_karto': '',
            'certainty': cert,
            'source': 'CGS geology + Pokorny et al. 2010',
            'id': f'tf_cz_paleo_{idx:03d}'
        })

    result = gpd.GeoDataFrame(cut_records, crs='EPSG:4326')
    # Re-assign IDs
    result['id'] = [f'tf_cz_{i:04d}' for i in range(1, len(result) + 1)]
    print(f"  After overlay: {len(result)} features")
    return result


# ---------------------------------------------------------------------------
# Step 4: Process rivers from DIBAVOD
# ---------------------------------------------------------------------------

def process_rivers():
    """Load DIBAVOD river network, clip to bbox, filter artificial channels."""
    print("\n" + "=" * 60)
    print("Step 4: Rivers from DIBAVOD")
    print("=" * 60)

    a02_path = os.path.join(RAW_CZ, 'dibavod', 'A02', 'A02_Vodni_tok_JU.shp')
    if not os.path.exists(a02_path):
        print(f"  ERROR: {a02_path} not found")
        return None

    print(f"  Loading {a02_path}...")
    rivers = gpd.read_file(a02_path)
    print(f"  Loaded {len(rivers)} river segments (nationwide)")

    # Reproject from S-JTSK to WGS84
    if rivers.crs and rivers.crs.to_epsg() != 4326:
        print(f"  Reprojecting from {rivers.crs} to EPSG:4326...")
        rivers = rivers.to_crs('EPSG:4326')

    # Clip to bbox
    bbox_poly = box(BBOX_WGS84['west'], BBOX_WGS84['south'],
                    BBOX_WGS84['east'], BBOX_WGS84['north'])
    rivers = rivers[rivers.geometry.intersects(bbox_poly)].copy()
    rivers['geometry'] = rivers.geometry.intersection(bbox_poly)
    rivers = rivers[~rivers.geometry.is_empty].copy()
    print(f"  After bbox clip: {len(rivers)} segments")

    # Filter: keep only named rivers and significant streams
    # DIBAVOD NAZ_TOK field contains river names
    if 'NAZ_TOK' in rivers.columns:
        named = rivers[rivers['NAZ_TOK'].notna() & (rivers['NAZ_TOK'] != '')].copy()
        unnamed = rivers[rivers['NAZ_TOK'].isna() | (rivers['NAZ_TOK'] == '')].copy()
        print(f"  Named rivers: {len(named)}, unnamed streams: {len(unnamed)}")

        # Key rivers to always include
        key_rivers = ['Luznice', 'Nezarka', 'Stropnice', 'Zlata stoka', 'Nova reka']
        # Note: we KEEP Zlata stoka and Nova reka for now -- they'll be flagged as artificial

        # Mark artificial channels (R2 decision: ponds didn't exist ~7000 BCE)
        artificial_patterns = ['stoka', 'kanal', 'strouha', 'odpad', 'privad']
        named['is_artificial'] = named['NAZ_TOK'].apply(
            lambda x: any(p in str(x).lower() for p in artificial_patterns)
        )
        art_count = named['is_artificial'].sum()
        print(f"  Flagged {art_count} artificial channel segments")

        # For ~7000 BCE: remove artificial channels
        natural = named[~named['is_artificial']].copy()
        print(f"  Natural river segments: {len(natural)}")
        rivers_out = natural
    else:
        rivers_out = rivers

    # Add properties for KB schema
    rivers_out = rivers_out.copy()
    rivers_out['terrain_subtype_id'] = 'tst_cz_010'
    rivers_out['source'] = 'DIBAVOD A02 (natural rivers only)'
    rivers_out['certainty'] = 'INFERENCE'

    print(f"  Final river network: {len(rivers_out)} segments")
    return rivers_out


# ---------------------------------------------------------------------------
# Step 5: Process wetlands from DIBAVOD
# ---------------------------------------------------------------------------

def process_wetlands():
    """Load DIBAVOD wetlands (A06), clip to bbox."""
    print("\n" + "=" * 60)
    print("Step 5: Wetlands from DIBAVOD A06")
    print("=" * 60)

    a06_path = os.path.join(RAW_CZ, 'dibavod', 'A06', 'A06_Bazina_mocal.shp')
    if not os.path.exists(a06_path):
        print(f"  WARNING: {a06_path} not found, skipping wetlands")
        return None

    print(f"  Loading {a06_path}...")
    wetlands = gpd.read_file(a06_path)
    print(f"  Loaded {len(wetlands)} wetland features (nationwide)")

    if wetlands.crs and wetlands.crs.to_epsg() != 4326:
        wetlands = wetlands.to_crs('EPSG:4326')

    bbox_poly = box(BBOX_WGS84['west'], BBOX_WGS84['south'],
                    BBOX_WGS84['east'], BBOX_WGS84['north'])
    wetlands = wetlands[wetlands.geometry.intersects(bbox_poly)].copy()
    wetlands['geometry'] = wetlands.geometry.intersection(bbox_poly)
    wetlands = wetlands[~wetlands.geometry.is_empty].copy()
    print(f"  After bbox clip: {len(wetlands)} wetland features")

    return wetlands


# ---------------------------------------------------------------------------
# Step 6: Process AMCR archaeological sites
# ---------------------------------------------------------------------------

def process_sites():
    """Load AMCR mesolithic sites for Trebonsko."""
    print("\n" + "=" * 60)
    print("Step 6: Archaeological sites (AMCR)")
    print("=" * 60)

    amcr_path = os.path.join(RAW_CZ, 'amcr', 'amcr_mezolit_trebonsko.geojson')
    if not os.path.exists(amcr_path):
        print(f"  WARNING: {amcr_path} not found, skipping sites")
        return None

    sites = gpd.read_file(amcr_path)
    print(f"  Loaded {len(sites)} mesolithic sites")

    # Clip to strict bbox
    bbox_poly = box(BBOX_WGS84['west'], BBOX_WGS84['south'],
                    BBOX_WGS84['east'], BBOX_WGS84['north'])
    in_bbox = sites[sites.geometry.within(bbox_poly)].copy()
    print(f"  In strict bbox: {len(in_bbox)} sites")

    # Also keep sites within ~20km of Svarcenberk (wider context)
    svarcenberk_pt = Point(SVARCENBERK['lon'], SVARCENBERK['lat'])
    near = sites[sites.geometry.distance(svarcenberk_pt) < 0.25].copy()

    # Merge bbox + near, deduplicate
    combined = pd.concat([in_bbox, near]).drop_duplicates(
        subset=['ident_cely'] if 'ident_cely' in sites.columns else None
    )
    all_sites = gpd.GeoDataFrame(combined, crs='EPSG:4326')

    print(f"  Total sites (bbox + ~20km Svarcenberk): {len(all_sites)}")
    return all_sites


# ---------------------------------------------------------------------------
# Step 7: DEM elevation enrichment
# ---------------------------------------------------------------------------

def enrich_with_dem(terrain_gdf):
    """Sample DEM elevation for terrain polygon centroids."""
    print("\n" + "=" * 60)
    print("Step 7: DEM elevation enrichment")
    print("=" * 60)

    dem_path = os.path.join(RAW_CZ, 'dem', 'trebonsko_dmr5g_10m.tif')
    if not os.path.exists(dem_path):
        print(f"  WARNING: DEM not found, skipping elevation enrichment")
        return terrain_gdf

    print(f"  Loading DEM...")
    with rasterio.open(dem_path) as dem:
        dem_crs = dem.crs
        dem_data = dem.read(1)
        dem_transform = dem.transform
        print(f"  DEM: {dem_data.shape[1]}x{dem_data.shape[0]} px, CRS: {dem_crs}")

        # Sample centroid elevation for each terrain polygon
        # Need to reproject centroids from WGS84 to S-JTSK for DEM sampling
        try:
            from pyproj import Transformer
            # DEM may have LOCAL_CS instead of proper EPSG -- force S-JTSK
            dem_crs_str = 'EPSG:5514'
            transformer = Transformer.from_crs('EPSG:4326', dem_crs_str, always_xy=True)

            elevations = []
            for idx, row in terrain_gdf.iterrows():
                centroid = row.geometry.centroid
                x_sjtsk, y_sjtsk = transformer.transform(centroid.x, centroid.y)
                # Convert to pixel coordinates
                col = int((x_sjtsk - dem_transform[2]) / dem_transform[0])
                row_px = int((y_sjtsk - dem_transform[5]) / dem_transform[4])
                if 0 <= row_px < dem_data.shape[0] and 0 <= col < dem_data.shape[1]:
                    elevations.append(float(dem_data[row_px, col]))
                else:
                    elevations.append(None)

            terrain_gdf = terrain_gdf.copy()
            terrain_gdf['elevation_m'] = elevations
            valid = [e for e in elevations if e is not None]
            if valid:
                print(f"  Elevation range: {min(valid):.1f} - {max(valid):.1f} m")
            print(f"  Sampled {len(valid)}/{len(elevations)} centroids")

        except ImportError:
            print("  WARNING: pyproj not available, skipping DEM enrichment")

    return terrain_gdf


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------

def export_terrain(terrain_gdf, out_path):
    """Export terrain features as GeoJSON."""
    print(f"\n  Exporting terrain features to {out_path}...")

    features = []
    for idx, row in terrain_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        # Normalize to Polygon/MultiPolygon
        if geom.geom_type == 'GeometryCollection':
            polys = [g for g in geom.geoms if g.geom_type in ('Polygon', 'MultiPolygon')]
            if not polys:
                continue
            geom = unary_union(polys)

        props = {
            'id': row.get('id', f'tf_cz_{idx:04d}'),
            'terrain_subtype_id': row['terrain_subtype_id'],
            'substrate': row.get('substrate', ''),
            'hydrology': row.get('hydrology', ''),
            'certainty': row.get('certainty', 'INFERENCE'),
            'source': row.get('source', 'CGS'),
            'anchor_site': False,
            'notes': None
        }
        if 'elevation_m' in row and row['elevation_m'] is not None:
            elev = row['elevation_m']
            if not (isinstance(elev, float) and np.isnan(elev)):
                props['elevation_m'] = round(elev, 1)

        features.append({
            'type': 'Feature',
            'geometry': mapping(geom),
            'properties': props
        })

    # Add Svarcenberk anchor
    features.append({
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [SVARCENBERK['lon'], SVARCENBERK['lat']]
        },
        'properties': {
            'id': 'tf_cz_svarcenberk',
            'terrain_subtype_id': SVARCENBERK['terrain_subtype'],
            'substrate': 'organic_lacustrine_sediment',
            'hydrology': 'permanent_standing_water',
            'certainty': SVARCENBERK['certainty'],
            'source': SVARCENBERK['source'],
            'anchor_site': True,
            'name': SVARCENBERK['name'],
            'notes': 'Paleolake 450x700m, sediments 11m + 3m peat, 9130-8630 cal BCE'
        }
    })

    geojson = {
        'type': 'FeatureCollection',
        'name': 'terrain_features_cz',
        'features': features
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=None)

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  Saved: {len(features)} features ({size_mb:.1f} MB)")


def export_rivers(rivers_gdf, out_path):
    """Export river network as GeoJSON."""
    print(f"\n  Exporting rivers to {out_path}...")

    features = []
    for idx, row in rivers_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        props = {
            'id': f'rv_cz_{idx:04d}',
            'name': str(row.get('NAZ_TOK', '')) if row.get('NAZ_TOK') else None,
            'terrain_subtype_id': 'tst_cz_010',
            'certainty': row.get('certainty', 'INFERENCE'),
            'source': row.get('source', 'DIBAVOD A02')
        }
        features.append({
            'type': 'Feature',
            'geometry': mapping(geom),
            'properties': props
        })

    geojson = {
        'type': 'FeatureCollection',
        'name': 'rivers_cz',
        'features': features
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=None)

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  Saved: {len(features)} river segments ({size_mb:.1f} MB)")


def export_sites(sites_gdf, out_path):
    """Export archaeological sites as GeoJSON."""
    print(f"\n  Exporting sites to {out_path}...")

    features = []
    for idx, row in sites_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        props = {
            'id': f'site_cz_{idx:04d}',
            'ident_cely': row.get('ident_cely', ''),
            'katastr': row.get('katastr', ''),
            'source': 'AMCR digiarchiv',
            'certainty': 'DIRECT'
        }
        features.append({
            'type': 'Feature',
            'geometry': mapping(geom),
            'properties': props
        })

    geojson = {
        'type': 'FeatureCollection',
        'name': 'sites_cz',
        'features': features
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=None)

    print(f"  Saved: {len(features)} sites")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Terrain classification for Trebonsko')
    parser.add_argument('--skip-dem', action='store_true', help='Skip DEM enrichment')
    parser.add_argument('--only', choices=['cgs', 'rivers', 'paleolakes', 'sites', 'dem'],
                        help='Run only specific step')
    args = parser.parse_args()

    print("=" * 60)
    print("Mezolit2 -- Terrain Classification (Trebonsko)")
    print("=" * 60)
    print(f"Bbox: N{BBOX_WGS84['north']} S{BBOX_WGS84['south']} "
          f"W{BBOX_WGS84['west']} E{BBOX_WGS84['east']}")
    print(f"Anchor: Svarcenberk ({SVARCENBERK['lat']}N, {SVARCENBERK['lon']}E)")
    print(f"Output: {OUT_DIR}")
    print()

    os.makedirs(OUT_DIR, exist_ok=True)

    # Step 1: CGS geology classification
    if args.only and args.only != 'cgs':
        print("Skipping CGS geology (--only flag)")
        terrain_gdf = None
    else:
        terrain_gdf = classify_cgs_geology()

    # Step 2: Dissolve and simplify
    if terrain_gdf is not None:
        terrain_gdf = dissolve_and_simplify(terrain_gdf)

    # Step 3: Paleolakes overlay
    if terrain_gdf is not None and (not args.only or args.only == 'paleolakes'):
        terrain_gdf = overlay_paleolakes(terrain_gdf)

    # Step 4: Rivers
    if not args.only or args.only == 'rivers':
        rivers_gdf = process_rivers()
    else:
        rivers_gdf = None

    # Step 5: Wetlands
    if not args.only or args.only == 'cgs':
        wetlands_gdf = process_wetlands()
    else:
        wetlands_gdf = None

    # Step 6: Archaeological sites
    if not args.only or args.only == 'sites':
        try:
            import pandas as pd
            sites_gdf = process_sites()
        except Exception as e:
            print(f"  Sites processing failed: {e}")
            sites_gdf = None
    else:
        sites_gdf = None

    # Step 7: DEM enrichment
    if terrain_gdf is not None and not args.skip_dem and (not args.only or args.only == 'dem'):
        terrain_gdf = enrich_with_dem(terrain_gdf)

    # Export
    print("\n" + "=" * 60)
    print("EXPORT")
    print("=" * 60)

    if terrain_gdf is not None:
        export_terrain(terrain_gdf, os.path.join(OUT_DIR, 'terrain_features_cz.geojson'))

    if rivers_gdf is not None:
        export_rivers(rivers_gdf, os.path.join(OUT_DIR, 'rivers_cz.geojson'))

    if sites_gdf is not None:
        export_sites(sites_gdf, os.path.join(OUT_DIR, 'sites_cz.geojson'))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if terrain_gdf is not None:
        tst_counts = terrain_gdf['terrain_subtype_id'].value_counts()
        print("\n  Terrain subtypes:")
        for tst, count in tst_counts.items():
            print(f"    {tst}: {count} polygons")
    if rivers_gdf is not None:
        print(f"\n  Rivers: {len(rivers_gdf)} segments")
    if wetlands_gdf is not None:
        print(f"  Wetlands: {len(wetlands_gdf)} features")
    if sites_gdf is not None:
        print(f"  Archaeological sites: {len(sites_gdf)}")

    print("\n  Next step: python 05_kb_rules_cz.py")


if __name__ == '__main__':
    main()

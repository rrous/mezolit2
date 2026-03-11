"""
Generate terrain_subtype polygons from Copernicus DEM + slope analysis.

Classification logic uses elevation bands + slope from the DEM to assign
terrain_subtype IDs matching schema_examples_v04.json definitions.

Input:  data/raw/dem/ (Copernicus DEM GeoTIFF tiles)
Output: data/processed/terrain_features.geojson
        data/processed/rivers_yorkshire.geojson

Usage:
    python 04_terrain.py
"""

import os
import sys
import json
import numpy as np

try:
    import rasterio
    from rasterio.merge import merge
    from rasterio.features import shapes, rasterize
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from shapely.geometry import shape, mapping, box
    from shapely.ops import unary_union
    import geopandas as gpd
    import fiona
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install -r requirements.txt")
    sys.exit(1)

# Yorkshire bounding box (WGS84)
YORKSHIRE_BBOX = {
    'west': -2.5, 'east': 0.1,
    'south': 53.5, 'north': 54.7
}

# Star Carr / Lake Flixton — coordinates from ADS postglacial_2013 map
# ADS landscape center: 54.214°N, -0.403°W
# Lake Flixton water level: ~24m aOD (Taylor & Alison 2018)
STAR_CARR = {
    'lat': 54.214, 'lon': -0.403,
    'radius_deg': 0.008,  # ~800m radius for Lake Flixton basin
    'terrain_subtype': 'tst_001'
}

# ADS GML data paths
ADS_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'ads')

# Site-to-lakescape-role mapping (Milner et al. 2018)
# Site names match ADS GML 'SiteName' attribute exactly
SITE_ROLE_MAP = {
    'Star Carr':                 'primary_camp',
    'Flixton Island':            'island_site',
    "Barry's Island":            'island_site',
    'No Name Hill':              'shore_camp',
    'Seamer Carr Site B':        'shore_camp',
    'Seamer Carr Site C':        'shore_camp',
    'Seamer Carr Site D':        'shore_camp',
    'Seamer Carr Site K':        'shore_camp',
    'Seamer Carr Site L':        'shore_camp',
    'Rabbit Hill':               'shore_camp',
    'Cayton Carr':               'shore_camp',
    'Manham Hill':               'shore_camp',
    'Ling Lane':                 'find_scatter',
    'VPD':                       'find_scatter',
    'VPE':                       'find_scatter',
    'Flixton School House Farm': 'find_scatter',
    'Flixton School Field':      'find_scatter',
    'Flixton 9':                 'find_scatter',
    'Lingholm Farm Field A':     'find_scatter',
    'Lingholm Farm Field B':     'find_scatter',
}

# Wolds chalk detection — DEM-based escarpment (replaces fixed longitude boundary)
WOLDS_DROP_M = 15            # Minimum meters above context to count as elevated plateau
WOLDS_HARD_WEST_LON = -1.0   # Geological hard western limit for chalk
WOLDS_MAX_ELEV = 250         # Upper limit — excludes North York Moors sandstone
WOLDS_MIN_ELEV = 50          # Lower limit — excludes Vale of York lowlands

# Minimum polygon area in degrees² (~0.5 km² at 54°N)
MIN_POLYGON_AREA = 0.00005

# Simplification tolerance (~20m)
SIMPLIFY_TOLERANCE = 0.0002

# Progressive simplification for large polygons (~50m)
LARGE_POLYGON_AREA = 0.001  # ~100 km² in deg²
LARGE_SIMPLIFY_TOLERANCE = 0.0005

# Smart hole thresholds (in degrees² at ~54°N)
HOLE_NOISE_MAX = 0.000005      # < 0.5 ha — pure DEM noise, remove
HOLE_GLADE_MAX = 0.00005       # 0.5–5 ha — potential forest glade, keep as feature
# > 5 ha — keep as hole (geologically relevant)

# Forest terrain subtypes where glades can occur
FOREST_TERRAIN_TYPES = {3, 5, 6}  # tst_003 (limestone), tst_005 (chalk), tst_006 (upland peat)

# Max number of glade features to create (cap against excessive DEM noise)
MAX_GLADE_FEATURES = 500

# River floodplain reclassification — adaptive widths
RIVER_BUFFER_NARROW_M = 150     # Minimum buffer (steep valleys/gorges)
RIVER_BUFFER_MEDIUM_M = 400     # Medium buffer (moderate terrain)
RIVER_BUFFER_WIDE_M = 800       # Maximum buffer (flat lowlands like Vale of York)
RIVER_FLOODPLAIN_MAX_ELEV = 200 # Hard elevation cap for any floodplain

# Star Carr paleochannel reconstruction
PALEO_HALF_LON = 0.06    # ~7.8 km E-W sub-area
PALEO_HALF_LAT = 0.05    # ~11 km N-S sub-area
PALEO_FLOW_PERCENTILE = 96   # top 4% of flow accumulation = channel pixels
PALEO_MIN_CHANNEL_CELLS = 15 # minimum cells per channel segment

RAW_DEM_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'dem')
RAW_RIVERS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'rivers')
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')


def load_and_merge_dem():
    """Load and merge DEM tiles covering Yorkshire."""
    print("Loading DEM tiles...")
    tif_files = []
    for f in os.listdir(RAW_DEM_DIR):
        if f.endswith(('.tif', '.tiff')):
            tif_files.append(os.path.join(RAW_DEM_DIR, f))

    if not tif_files:
        print(f"ERROR: No DEM tiles found in {RAW_DEM_DIR}")
        sys.exit(1)

    print(f"  Found {len(tif_files)} tiles")

    if len(tif_files) == 1:
        return rasterio.open(tif_files[0]), tif_files[0]

    # Merge multiple tiles
    datasets = [rasterio.open(f) for f in tif_files]
    mosaic, out_transform = merge(datasets)
    for ds in datasets:
        ds.close()

    # Save merged
    merged_path = os.path.join(OUT_DIR, 'dem_merged.tif')
    os.makedirs(OUT_DIR, exist_ok=True)
    with rasterio.open(
        merged_path, 'w',
        driver='GTiff',
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        count=1,
        dtype=mosaic.dtype,
        crs=datasets[0].crs if datasets else 'EPSG:4326',
        transform=out_transform
    ) as dst:
        dst.write(mosaic)

    print(f"  Merged DEM: {mosaic.shape[1]}x{mosaic.shape[2]} pixels")
    return rasterio.open(merged_path), merged_path


def compute_slope(dem_data, transform):
    """Compute slope in degrees from DEM."""
    print("Computing slope...")
    # Pixel size in meters (approximate at 54°N)
    pixel_size_x = abs(transform[0]) * 111320 * np.cos(np.radians(54))
    pixel_size_y = abs(transform[4]) * 110540

    # Gradient using numpy
    dy, dx = np.gradient(dem_data, pixel_size_y, pixel_size_x)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)

    print(f"  Slope range: {slope_deg.min():.1f}° to {slope_deg.max():.1f}°")
    return slope_deg


def classify_terrain(elevation, slope, transform):
    """
    Classify each pixel into terrain_subtype based on elevation + slope.

    Classification priority (higher priority = checked first):
    1. tst_008: coastal tidal (-3 to 3m, flat)
    2. tst_004: fenland basin (<15m, flat)
    3. tst_002: river floodplain (<50m, very_low slope)
    4. tst_001: glacial lake basin (<100m, flat, near water) — mostly manual
    5. tst_005: chalk downland (50-300m, east Yorkshire Wolds)
    6. tst_003: upland limestone (150-500m, non-chalk)
    7. tst_006: upland peat basin (300-720m)
    8. tst_007: sea cliff (coastal, steep)
    """
    print("Classifying terrain subtypes...")

    # Initialize with 0 (unclassified)
    classified = np.zeros_like(elevation, dtype=np.uint8)

    # Map terrain_subtype IDs to numeric codes
    # tst_001=1, tst_002=2, ..., tst_008=8
    TST = {
        'glacial_lake': 1,   # tst_001
        'floodplain': 2,     # tst_002
        'limestone': 3,      # tst_003
        'fenland': 4,        # tst_004
        'chalk': 5,          # tst_005
        'upland_peat': 6,    # tst_006
        'sea_cliff': 7,      # tst_007
        'tidal': 8,          # tst_008
    }

    # Generate longitude grid
    rows, cols = elevation.shape
    col_indices = np.arange(cols)
    lons = transform[2] + col_indices * transform[0]
    lon_grid = np.broadcast_to(lons, (rows, cols))

    # === Detect Wolds chalk plateau from DEM ===
    # Multi-scale approach: check elevation context at multiple distances
    # to capture both the escarpment edge AND the interior plateau
    pixel_lon_m = abs(transform[0]) * 111320 * np.cos(np.radians(54))

    elevation_band = (
        (elevation >= WOLDS_MIN_ELEV) & (elevation < WOLDS_MAX_ELEV) &
        (lon_grid > WOLDS_HARD_WEST_LON)
    )

    chalk_seed = np.zeros(elevation.shape, dtype=bool)
    for km in [5, 10, 15, 20, 25]:
        W = max(1, int(km * 1000 / pixel_lon_m))

        # Western context: pixels elevated above terrain to the west
        padded_w = np.pad(elevation, ((0, 0), (W, 0)), mode='edge')
        cum_w = np.cumsum(padded_w, axis=1)
        west_mean = (cum_w[:, W:] - cum_w[:, :-W]) / W
        chalk_seed |= (elevation - west_mean > WOLDS_DROP_M)

        # Eastern context: catches the gentle eastern dip slope
        # Restricted to lon > -0.5 to avoid detecting Pennines
        padded_e = np.pad(elevation, ((0, 0), (0, W)), mode='edge')
        cum_e = np.cumsum(padded_e, axis=1)
        east_mean = (cum_e[:, W:W + cols] - cum_e[:, :cols]) / W
        chalk_seed |= ((elevation - east_mean > WOLDS_DROP_M) & (lon_grid > -0.5))

    chalk_mask = chalk_seed & elevation_band
    chalk_pixels = np.sum(chalk_mask)
    print(f"  Wolds chalk: {chalk_pixels:,} px detected from DEM (multi-scale)")

    # Classification rules (bottom-up priority)

    # Default: upland limestone for moderate elevation
    mask = (elevation >= 150) & (elevation < 500) & (slope >= 2)
    classified[mask] = TST['limestone']

    # Upland peat basin (300-720m)
    mask = elevation >= 300
    classified[mask] = TST['upland_peat']

    # Re-apply limestone for 150-300m where not upland
    mask = (elevation >= 150) & (elevation < 300) & (slope >= 2)
    classified[mask] = TST['limestone']

    # Chalk downland — DEM-detected Wolds plateau
    classified[chalk_mask] = TST['chalk']

    # River floodplain (<50m, gentle slope)
    mask = (elevation >= 0) & (elevation < 50) & (slope < 2)
    classified[mask] = TST['floodplain']

    # Fenland basin (<15m, very flat)
    mask = (elevation >= 0) & (elevation < 15) & (slope < 0.5)
    classified[mask] = TST['fenland']

    # Tidal estuary/mudflat (-8 to 5m, flat) — wider zone for realistic intertidal
    mask = (elevation >= -8) & (elevation <= 5) & (slope < 1.5)
    classified[mask] = TST['tidal']

    # Sea cliff (coastal, steep, near sea level)
    mask = (elevation >= 0) & (elevation < 100) & (slope >= 15)
    classified[mask] = TST['sea_cliff']

    # === Gap filling: classify remaining land pixels (elevation >= -8m) ===
    # Gaps arise from elevation/slope combinations not covered by specific rules
    SEA_FLOOR = -8  # below this = deep sea (matches tidal lower bound)
    land_gaps = (classified == 0) & (elevation >= SEA_FLOOR)
    gap_count = int(np.sum(land_gaps))
    if gap_count > 0:
        # Slopes near sea level → tidal
        classified[land_gaps & (elevation < 5) & (slope >= 1.5)] = TST['tidal']
        land_gaps = (classified == 0) & (elevation >= SEA_FLOOR)
        classified[land_gaps & (elevation < 50)] = TST['floodplain']
        classified[land_gaps & chalk_mask] = TST['chalk']
        land_gaps = (classified == 0) & (elevation >= SEA_FLOOR)
        classified[land_gaps & (elevation >= 50) & (elevation < 300)] = TST['limestone']
        classified[land_gaps & (elevation >= 300)] = TST['upland_peat']
        filled = gap_count - int(np.sum((classified == 0) & (elevation >= SEA_FLOOR)))
        print(f"  Gap filling: filled {filled:,} land pixels")

    # Anything below SEA_FLOOR is deep sea (unclassified = 0)
    classified[elevation < SEA_FLOOR] = 0

    # Count pixels per class
    for name, code in TST.items():
        count = np.sum(classified == code)
        pct = count / classified.size * 100
        print(f"  tst_{code:03d} ({name}): {count:,} px ({pct:.1f}%)")

    unclassified = np.sum(classified == 0)
    print(f"  Unclassified/sea: {unclassified:,} px ({unclassified/classified.size*100:.1f}%)")

    return classified


TST_ID_MAP = {
    1: 'tst_001', 2: 'tst_002', 3: 'tst_003', 4: 'tst_004',
    5: 'tst_005', 6: 'tst_006', 7: 'tst_007', 8: 'tst_008',
}


def process_holes(polygon, tst_code):
    """
    Smart hole management: remove noise, extract glades, keep geology.

    Returns: (cleaned_polygon, list_of_glade_polygons)
    """
    from shapely.geometry import Polygon

    if polygon.geom_type != 'Polygon':
        return polygon, []

    exterior = polygon.exterior
    kept_holes = []
    glade_polys = []
    removed_noise = 0
    is_forest = tst_code in FOREST_TERRAIN_TYPES

    for interior in polygon.interiors:
        hole = Polygon(interior)
        hole_area = hole.area

        if hole_area < HOLE_NOISE_MAX:
            # Pure noise — fill it (don't keep as hole)
            removed_noise += 1
            continue
        elif hole_area < HOLE_GLADE_MAX and is_forest:
            # Medium hole in forest terrain — extract as glade feature
            glade_polys.append(hole)
            # Remove hole from parent (fill it)
            removed_noise += 1
            continue
        else:
            # Large hole — keep as-is (geological feature or non-forest)
            kept_holes.append(interior)

    cleaned = Polygon(exterior, kept_holes)
    return cleaned, glade_polys


def reclassify_river_corridors(classified, elevation, slope, transform):
    """
    Reclassify terrain near rivers as tst_002 (floodplain).
    Uses adaptive buffer width: wider in flat lowlands, narrower in steep valleys.
    Operates on the classified raster BEFORE polygonization.
    """
    print("Reclassifying river corridors as floodplain...")

    if not os.path.exists(RAW_RIVERS_DIR):
        print("  WARNING: No river data directory. Skipping.")
        return classified

    # Find river file
    river_file = None
    for f in os.listdir(RAW_RIVERS_DIR):
        if f.endswith('.gpkg'):
            river_file = os.path.join(RAW_RIVERS_DIR, f)
            break
        elif f.endswith('.shp'):
            river_file = os.path.join(RAW_RIVERS_DIR, f)

    if not river_file:
        print("  WARNING: No river data found. Skipping.")
        return classified

    # Read rivers
    layer = 'watercourse_link' if river_file.endswith('.gpkg') else None
    gdf = gpd.read_file(river_file, layer=layer)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # Clip to Yorkshire bbox
    clip_box = box(
        YORKSHIRE_BBOX['west'], YORKSHIRE_BBOX['south'],
        YORKSHIRE_BBOX['east'], YORKSHIRE_BBOX['north']
    )
    gdf = gdf.clip(clip_box)
    gdf = gdf[gdf.geometry.geom_type.isin(['LineString', 'MultiLineString'])]

    if len(gdf) == 0:
        print("  WARNING: No rivers in bbox. Skipping.")
        return classified

    # Helper: rasterize a buffer zone
    def rasterize_buffer(buffer_m):
        buffer_deg = buffer_m / 88000.0
        buffered = gdf.geometry.buffer(buffer_deg)
        merged = unary_union(buffered.values)
        if merged.geom_type == 'Polygon':
            sl = [(mapping(merged), 1)]
        elif merged.geom_type == 'MultiPolygon':
            sl = [(mapping(g), 1) for g in merged.geoms]
        else:
            return np.zeros(classified.shape, dtype=np.uint8)
        return rasterize(sl, out_shape=classified.shape,
                         transform=transform, fill=0, dtype=np.uint8)

    # Create three adaptive buffer zones
    print(f"  Creating adaptive buffers for {len(gdf)} river segments...")
    print(f"    Narrow: {RIVER_BUFFER_NARROW_M}m, Medium: {RIVER_BUFFER_MEDIUM_M}m, Wide: {RIVER_BUFFER_WIDE_M}m")
    buf_narrow = rasterize_buffer(RIVER_BUFFER_NARROW_M)
    buf_medium = rasterize_buffer(RIVER_BUFFER_MEDIUM_M)
    buf_wide = rasterize_buffer(RIVER_BUFFER_WIDE_M)

    # Adaptive reclassification: wider corridors in flatter, lower terrain
    TST_FLOODPLAIN = 2  # tst_002
    not_sea = classified != 0
    above_water = elevation >= 0

    reclassify_mask = (
        above_water & not_sea & (
            # Flat lowlands (Vale of York): wide 800m corridor
            ((buf_wide == 1) & (slope < 1.0) & (elevation < 50)) |
            # Moderate terrain: medium 400m corridor
            ((buf_medium == 1) & (slope < 2.5) & (elevation < 100)) |
            # All terrain: narrow 150m corridor
            ((buf_narrow == 1) & (elevation < RIVER_FLOODPLAIN_MAX_ELEV))
        )
    )

    count_before = np.sum(classified == TST_FLOODPLAIN)
    classified[reclassify_mask] = TST_FLOODPLAIN
    count_after = np.sum(classified == TST_FLOODPLAIN)

    pixels_reclassified = count_after - count_before
    print(f"  Reclassified {pixels_reclassified:,} pixels to tst_002 (floodplain)")
    print(f"  tst_002 total: {count_after:,} px ({count_after / classified.size * 100:.1f}%)")

    return classified


def polygonize_terrain(classified, transform):
    """Convert classified raster to polygons."""
    print("Polygonizing terrain classes...")

    all_features = []
    glade_features = []
    feature_id = 0
    total_holes_removed = 0
    total_glades_extracted = 0

    for geom, value in shapes(classified.astype(np.int32), transform=transform):
        value = int(value)
        if value == 0:  # Skip sea/unclassified
            continue

        poly = shape(geom)

        # Skip tiny polygons
        if poly.area < MIN_POLYGON_AREA:
            continue

        # Simplify: progressive tolerance based on polygon size
        tolerance = SIMPLIFY_TOLERANCE
        if poly.area > LARGE_POLYGON_AREA:
            tolerance = LARGE_SIMPLIFY_TOLERANCE
        poly = poly.simplify(tolerance, preserve_topology=True)

        if not poly.is_valid:
            poly = poly.buffer(0)

        if poly.is_empty:
            continue

        # Smart hole management
        poly, glades = process_holes(poly, value)

        if not poly.is_valid:
            poly = poly.buffer(0)

        tst_id = TST_ID_MAP.get(value)
        if not tst_id:
            continue

        feature_id += 1
        all_features.append({
            'type': 'Feature',
            'properties': {
                'id': f'tf_{feature_id:04d}',
                'terrain_subtype_id': tst_id,
                'anchor_site': False,
                'notes': None,
                'certainty': 'INFERENCE',
                'source': 'Copernicus DEM GLO-30; elevation band classification'
            },
            'geometry': mapping(poly)
        })

        # Collect glade features (capped later)
        for glade_poly in glades:
            total_glades_extracted += 1
            glade_features.append({
                'tst_id': tst_id,
                'polygon': glade_poly,
                'parent_id': f'tf_{feature_id:04d}'
            })

    # Cap glades to MAX_GLADE_FEATURES, pick random sample if too many
    if len(glade_features) > MAX_GLADE_FEATURES:
        import random
        random.seed(42)
        glade_features = random.sample(glade_features, MAX_GLADE_FEATURES)
        print(f"  Capped glades: {total_glades_extracted} found, kept {MAX_GLADE_FEATURES}")

    # Add glade features with auto_glade flag
    for gf in glade_features:
        glade_poly = gf['polygon']
        glade_poly = glade_poly.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        if not glade_poly.is_valid:
            glade_poly = glade_poly.buffer(0)
        if glade_poly.is_empty:
            continue

        feature_id += 1
        all_features.append({
            'type': 'Feature',
            'properties': {
                'id': f'tf_{feature_id:04d}',
                'terrain_subtype_id': gf['tst_id'],
                'anchor_site': False,
                'notes': 'auto_glade',
                'certainty': 'INFERENCE',
                'source': 'DEM micro-relief; auto-detected forest clearing'
            },
            'geometry': mapping(glade_poly)
        })

    print(f"  Generated {len(all_features)} terrain polygons "
          f"(incl. {len(glade_features)} glade features)")
    return all_features


def load_ads_lake():
    """
    Load authoritative Lake Flixton polygon from ADS GML data.
    Source: Palmer et al. 2015; Taylor & Alison 2018; ADS postglacial_2013.
    Returns Shapely polygon or None if data unavailable.
    """
    ads_path = os.path.join(ADS_DATA_DIR, 'lake2_wgs84.gml')
    if not os.path.exists(ads_path):
        print("  ADS lake GML not found — will try DEM fallback")
        return None

    try:
        gdf = gpd.read_file(ads_path)
    except Exception as e:
        print(f"  WARNING: Cannot read ADS GML: {e}")
        return None

    if len(gdf) == 0:
        print("  WARNING: ADS GML contains no features")
        return None

    # GML may contain multiple features (main lake + small satellites);
    # merge and keep the largest polygon
    from shapely.ops import unary_union
    merged = unary_union(gdf.geometry)
    if merged.geom_type == 'MultiPolygon':
        lake_poly = max(merged.geoms, key=lambda g: g.area)
    elif merged.geom_type == 'Polygon':
        lake_poly = merged
    else:
        print(f"  WARNING: Unexpected geometry type: {merged.geom_type}")
        return None

    # Simplify to match pipeline conventions (~20m tolerance)
    lake_poly = lake_poly.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
    if not lake_poly.is_valid:
        lake_poly = lake_poly.buffer(0)

    bounds = lake_poly.bounds
    ew = (bounds[2] - bounds[0]) * 65.0
    ns = (bounds[3] - bounds[1]) * 111.0
    area = lake_poly.area * 65.0 * 111.0
    n_verts = len(list(lake_poly.exterior.coords))
    print(f"  ADS lake loaded: {ew:.2f}x{ns:.2f} km, area={area:.2f} km2, "
          f"vertices={n_verts}")

    return lake_poly


def extract_lake_24m_contour(dem_path, clon, clat):
    """
    Fallback: extract Lake Flixton from 24m aOD contour (Taylor & Alison 2018).
    Copernicus DEM uses EGM2008 geoid; ODN offset in Yorkshire ≈ +0.8m.
    """
    from shapely.geometry import Point
    import rasterio as rio
    from rasterio.features import shapes as rio_shapes

    # 24m aOD ≈ 24.8m in EGM2008 (Copernicus DEM)
    LAKE_LEVEL_EGM2008 = 24.8

    HALF_LON = 0.05   # ~3.25 km at 54°N
    HALF_LAT = 0.025  # ~2.8 km

    with rio.open(dem_path) as src:
        window = rio.windows.from_bounds(
            clon - HALF_LON, clat - HALF_LAT,
            clon + HALF_LON, clat + HALF_LAT,
            src.transform
        )
        dem_clip = src.read(1, window=window)
        clip_transform = src.window_transform(window)

    center_point = Point(clon, clat)
    basin_mask = (dem_clip <= LAKE_LEVEL_EGM2008).astype(np.uint8)

    # Find polygon nearest to / containing center
    candidate = None
    for geom, value in rio_shapes(basin_mask.astype(np.int32),
                                   transform=clip_transform):
        if value != 1:
            continue
        poly = shape(geom)
        if not poly.is_valid or poly.area < 0.000001:
            continue
        if poly.contains(center_point):
            candidate = poly
            break
        if candidate is None and poly.distance(center_point) < 0.008:
            candidate = poly

    if candidate is None:
        print("  WARNING: No 24m contour basin found near Star Carr")
        return None

    # Simplify pixel staircase
    smoothed = candidate.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
    if not smoothed.is_valid:
        smoothed = smoothed.buffer(0)

    # Handle MultiPolygon — keep largest
    if smoothed.geom_type == 'MultiPolygon':
        smoothed = max(smoothed.geoms, key=lambda g: g.area)

    bounds = smoothed.bounds
    ew = (bounds[2] - bounds[0]) * 65.0
    ns = (bounds[3] - bounds[1]) * 111.0
    area = smoothed.area * 65.0 * 111.0
    n_verts = len(list(smoothed.exterior.coords))
    print(f"  DEM 24m contour lake: {ew:.2f}x{ns:.2f} km, area={area:.2f} km2, "
          f"vertices={n_verts}")

    return smoothed


def load_ads_sites():
    """
    Load 20 archaeological sites from ADS GML data.
    Returns list of GeoJSON Feature dicts, or empty list if unavailable.
    """
    ads_path = os.path.join(ADS_DATA_DIR, 'sites_wgs84.gml')
    if not os.path.exists(ads_path):
        print("  ADS sites GML not found — skipping site export")
        return []

    try:
        gdf = gpd.read_file(ads_path)
    except Exception as e:
        print(f"  WARNING: Cannot read ADS sites GML: {e}")
        return []

    features = []
    unmatched = []
    for _, row in gdf.iterrows():
        # Try common attribute names for the site name
        site_name = None
        for col in ['SiteName', 'Name', 'name', 'SITENAME', 'sitename']:
            if col in row.index and row[col]:
                site_name = str(row[col]).strip()
                break
        if not site_name:
            site_name = f"Unknown site {len(features)}"

        role = SITE_ROLE_MAP.get(site_name)
        if role is None:
            unmatched.append(site_name)
            role = 'find_scatter'  # default

        poly = row.geometry
        if poly is None or poly.is_empty:
            continue

        # Simplify
        poly = poly.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        if not poly.is_valid:
            poly = poly.buffer(0)

        site_id = site_name.lower().replace(' ', '_').replace("'", '')
        features.append({
            'type': 'Feature',
            'properties': {
                'id': f'site_{site_id}',
                'name': site_name,
                'lakescape_role': role,
                'certainty': 'DIRECT',
                'source': 'ADS postglacial_2013; Milner et al. 2018'
            },
            'geometry': mapping(poly)
        })

    if unmatched:
        print(f"  WARNING: {len(unmatched)} sites not in SITE_ROLE_MAP: {unmatched}")
    print(f"  Loaded {len(features)} archaeological sites from ADS")
    return features


def add_star_carr_anchor(features, dem_path=None):
    """
    Add Star Carr / Lake Flixton as anchor polygon.
    Priority: 1) ADS GML, 2) DEM 24m contour, 3) synthetic ellipse.
    """
    print("Adding Star Carr anchor site...")

    clon = STAR_CARR['lon']
    clat = STAR_CARR['lat']

    # Priority 1: ADS authoritative polygon
    lake_poly = load_ads_lake()
    if lake_poly:
        method = 'ads_gml'
        source = 'Palmer et al. 2015; Taylor & Alison 2018; ADS postglacial_2013'
        certainty = 'DIRECT'
    else:
        # Priority 2: DEM 24m aOD contour
        if dem_path:
            lake_poly = extract_lake_24m_contour(dem_path, clon, clat)
        if lake_poly:
            method = 'dem_24m'
            source = 'Taylor & Alison 2018; 24m aOD contour from Copernicus DEM'
            certainty = 'INDIRECT'
        else:
            # Priority 3: Synthetic fallback
            print("  Falling back to synthetic polygon")
            from shapely.geometry import Polygon as ShapelyPolygon
            import random
            random.seed(42)
            angles = np.linspace(0, 2 * np.pi, 30, endpoint=False)
            verts = [(clon + 0.018 * np.cos(a) + random.gauss(0, 0.0003),
                      clat + 0.005 * np.sin(a) + random.gauss(0, 0.0002))
                     for a in angles]
            verts.append(verts[0])
            lake_poly = ShapelyPolygon(verts)
            if not lake_poly.is_valid:
                lake_poly = lake_poly.buffer(0)
            method = 'synthetic'
            source = 'Clark 1954; Mellars & Dark 1998; Milner et al. 2018'
            certainty = 'INFERENCE'

    # Remove overlapping terrain polygons
    filtered = []
    for f in features:
        poly = shape(f['geometry'])
        if poly.intersects(lake_poly):
            diff = poly.difference(lake_poly)
            if not diff.is_empty and diff.area > MIN_POLYGON_AREA:
                f['geometry'] = mapping(diff)
                filtered.append(f)
        else:
            filtered.append(f)

    filtered.append({
        'type': 'Feature',
        'properties': {
            'id': 'tf_star_carr',
            'name': 'Lake Flixton (Star Carr)',
            'terrain_subtype_id': 'tst_001',
            'anchor_site': True,
            'certainty': certainty,
            'notes': f'method={method}',
            'source': source
        },
        'geometry': mapping(lake_poly)
    })

    print(f"  Added Star Carr / Lake Flixton (tst_001, {certainty}, method={method})")
    return filtered


def load_coastline():
    """Load 6200 BCE coastline polygon from GeoJSON."""
    coast_path = os.path.join(OUT_DIR, 'coastline_6200bce.geojson')
    if not os.path.exists(coast_path):
        print("  WARNING: coastline_6200bce.geojson not found, using bbox only")
        return None

    with open(coast_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    geom = shape(data['features'][0]['geometry'])
    # GeometryCollection → extract polygons and merge
    if geom.geom_type == 'GeometryCollection':
        from shapely.ops import unary_union as _union
        polys = [g for g in geom.geoms
                 if g.geom_type in ('Polygon', 'MultiPolygon')]
        geom = _union(polys)

    print(f"  Loaded coastline: {geom.geom_type}, area={geom.area * 65 * 111:.0f} km2")
    return geom


def clip_to_yorkshire(features):
    """Clip terrain features to Yorkshire bbox AND coastline (land only).
    Also adds a sea polygon for the area outside the coastline."""
    print("Clipping to Yorkshire (coastline + bbox)...")
    clip_box = box(
        YORKSHIRE_BBOX['west'], YORKSHIRE_BBOX['south'],
        YORKSHIRE_BBOX['east'], YORKSHIRE_BBOX['north']
    )

    # Load coastline — clip terrain to land area
    coastline = load_coastline()
    if coastline is not None:
        land_clip = coastline.intersection(clip_box)
    else:
        land_clip = clip_box

    clipped = []
    for f in features:
        poly = shape(f['geometry'])
        intersection = poly.intersection(land_clip)
        if intersection.is_empty:
            continue
        # Glade features are intentionally small — don't apply normal area filter
        is_glade = f['properties'].get('notes') == 'auto_glade'
        min_area = HOLE_NOISE_MAX if is_glade else MIN_POLYGON_AREA
        if intersection.area > min_area:
            f['geometry'] = mapping(intersection)
            clipped.append(f)

    glade_count = sum(1 for f in clipped if f['properties'].get('notes') == 'auto_glade')
    print(f"  {len(clipped)} terrain polygons after land clip (incl. {glade_count} glades)")

    # Add sea polygon (bbox minus coastline)
    if coastline is not None:
        sea = clip_box.difference(land_clip)
        if not sea.is_empty:
            sea_simplified = sea.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
            if not sea_simplified.is_valid:
                sea_simplified = sea_simplified.buffer(0)
            clipped.append({
                'type': 'Feature',
                'properties': {
                    'id': 'tf_sea',
                    'terrain_subtype_id': None,
                    'anchor_site': False,
                    'notes': 'open_sea',
                    'terrain_type': 'sea',
                    'certainty': 'INDIRECT',
                    'source': 'GEBCO 2023; sea level -25m (Shennan et al. 2018)'
                },
                'geometry': mapping(sea_simplified)
            })
            sea_area = sea.area * 65 * 111
            print(f"  Added sea polygon: {sea_area:.0f} km2")

    return clipped


def generate_paleochannels(dem_path):
    """
    Generate paleochannel network from DEM flow accumulation around Star Carr.
    Uses D8 flow direction + sorted-order accumulation.
    Returns list of GeoJSON LineString features + bounding box polygon.
    """
    from heapq import heappush, heappop
    from shapely.geometry import LineString

    clon, clat = STAR_CARR['lon'], STAR_CARR['lat']
    print(f"  Generating paleochannels from DEM (center={clat:.3f}N, {clon:.3f}E)...")

    with rasterio.open(dem_path) as src:
        window = rasterio.windows.from_bounds(
            clon - PALEO_HALF_LON, clat - PALEO_HALF_LAT,
            clon + PALEO_HALF_LON, clat + PALEO_HALF_LAT,
            src.transform
        )
        dem = src.read(1, window=window).astype(np.float32)
        ct = src.window_transform(window)

    rows, cols = dem.shape
    print(f"    Sub-area: {rows}x{cols} pixels ({rows*cols:,} cells)")

    # --- 1. Fill sinks (priority flood, Wang & Liu 2006) ---
    filled = dem.copy()
    visited = np.zeros((rows, cols), dtype=bool)
    pq = []

    # Seed border cells
    for i in range(rows):
        for j in [0, cols - 1]:
            heappush(pq, (float(dem[i, j]), i, j))
            visited[i, j] = True
    for j in range(cols):
        for i in [0, rows - 1]:
            if not visited[i, j]:
                heappush(pq, (float(dem[i, j]), i, j))
                visited[i, j] = True

    n8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    sinks_filled = 0
    while pq:
        elev, i, j = heappop(pq)
        for di, dj in n8:
            ni, nj = i + di, j + dj
            if 0 <= ni < rows and 0 <= nj < cols and not visited[ni, nj]:
                visited[ni, nj] = True
                if filled[ni, nj] < elev:
                    filled[ni, nj] = elev
                    sinks_filled += 1
                heappush(pq, (max(float(filled[ni, nj]), elev), ni, nj))

    print(f"    Sinks filled: {sinks_filled:,}")

    # --- 2. D8 flow accumulation (sorted-order, highest-first) ---
    flat = filled.ravel()
    order = np.argsort(flat)[::-1]  # highest elevation first

    # Pre-compute flow direction for each cell (index into flat neighbor)
    flow_target = np.full(rows * cols, -1, dtype=np.int32)
    for idx in order:
        i, j = divmod(int(idx), cols)
        max_drop = 0.0
        best = -1
        for di, dj in n8:
            ni, nj = i + di, j + dj
            if 0 <= ni < rows and 0 <= nj < cols:
                drop = filled[i, j] - filled[ni, nj]
                if drop > max_drop:
                    max_drop = drop
                    best = ni * cols + nj
        flow_target[idx] = best

    # Accumulate: pass flow from highest to lowest
    acc = np.ones(rows * cols, dtype=np.int32)
    for idx in order:
        t = flow_target[idx]
        if t >= 0:
            acc[t] += acc[idx]

    acc_2d = acc.reshape(rows, cols)
    threshold = np.percentile(acc_2d[acc_2d > 1], PALEO_FLOW_PERCENTILE)
    channel_mask = acc_2d >= threshold
    n_channel = int(np.sum(channel_mask))
    print(f"    Flow accumulation: threshold={threshold:.0f}, channel pixels={n_channel:,}")

    # --- 3. Trace channels to LineStrings ---
    # Follow flow_target from each channel pixel to build connected paths
    # Start from channel pixels with high accumulation, trace downstream
    channel_starts = []
    for idx in order:
        i, j = divmod(int(idx), cols)
        if not channel_mask[i, j]:
            continue
        # Is this a start? (no upstream channel pixel flows to it, or it's a confluence)
        # Simpler: start from local maxima of accumulation within channels
        is_start = True
        for di, dj in n8:
            ni, nj = i + di, j + dj
            if 0 <= ni < rows and 0 <= nj < cols:
                if channel_mask[ni, nj] and flow_target[ni * cols + nj] == idx:
                    # Someone flows into this cell
                    if acc_2d[ni, nj] >= threshold:
                        is_start = False
                        break
        if is_start:
            channel_starts.append(idx)

    # Trace from each start following flow_target
    used = np.zeros(rows * cols, dtype=bool)
    segments = []
    for start_idx in channel_starts:
        path = []
        idx = start_idx
        while idx >= 0 and not used[idx]:
            i, j = divmod(int(idx), cols)
            if not channel_mask[i, j] and len(path) > 0:
                break
            used[idx] = True
            # Convert to geographic coords
            x = ct[2] + j * ct[0] + ct[0] / 2
            y = ct[5] + i * ct[4] + ct[4] / 2
            path.append((x, y))
            idx = flow_target[idx]

        if len(path) >= PALEO_MIN_CHANNEL_CELLS:
            segments.append(path)

    print(f"    Traced {len(segments)} channel segments "
          f"(from {len(channel_starts)} start points)")

    # Convert to GeoJSON features
    features = []
    for seg_idx, coords in enumerate(segments):
        line = LineString(coords)
        if not line.is_valid or line.length < 0.0005:
            continue
        features.append({
            'type': 'Feature',
            'properties': {
                'id': f'paleo_{seg_idx:04d}',
                'name': None,
                'permanence': 'permanent',
                'certainty': 'INFERENCE',
                'source': 'DEM flow accumulation; paleochannel reconstruction ~6200 BCE'
            },
            'geometry': mapping(line)
        })

    sub_area = box(
        clon - PALEO_HALF_LON, clat - PALEO_HALF_LAT,
        clon + PALEO_HALF_LON, clat + PALEO_HALF_LAT
    )
    print(f"    Output: {len(features)} paleochannel features")
    return features, sub_area


def process_rivers(dem_path=None):
    """Process OS Open Rivers — clip to Yorkshire, reproject to WGS84.
    In Star Carr sub-area, replace modern rivers with DEM-derived paleochannels."""
    print("\nProcessing rivers...")

    if not os.path.exists(RAW_RIVERS_DIR):
        print(f"  WARNING: Rivers directory not found: {RAW_RIVERS_DIR}")
        print("  Skipping rivers. Download OS Open Rivers first.")
        return None

    # Find GeoPackage or Shapefile
    river_file = None
    for f in os.listdir(RAW_RIVERS_DIR):
        if f.endswith('.gpkg'):
            river_file = os.path.join(RAW_RIVERS_DIR, f)
            break
        elif f.endswith('.shp'):
            river_file = os.path.join(RAW_RIVERS_DIR, f)

    if not river_file:
        print("  WARNING: No river data file found (.gpkg or .shp)")
        return None

    print(f"  Reading {os.path.basename(river_file)}...")
    # OS Open Rivers gpkg has two layers: hydro_node (points) and watercourse_link (lines)
    layer = 'watercourse_link' if river_file.endswith('.gpkg') else None
    gdf = gpd.read_file(river_file, layer=layer)

    # Reproject from BNG (EPSG:27700) to WGS84 (EPSG:4326)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        print(f"  Reprojecting from {gdf.crs} to EPSG:4326...")
        gdf = gdf.to_crs(epsg=4326)

    # Clip to Yorkshire bbox
    clip_box = box(
        YORKSHIRE_BBOX['west'], YORKSHIRE_BBOX['south'],
        YORKSHIRE_BBOX['east'], YORKSHIRE_BBOX['north']
    )
    gdf = gdf.clip(clip_box)

    # clip() can produce Points at bbox boundaries — keep only line geometries
    gdf = gdf[gdf.geometry.geom_type.isin(['LineString', 'MultiLineString'])]

    print(f"  {len(gdf)} river segments in Yorkshire")

    # Generate paleochannels for Star Carr sub-area
    paleo_features = []
    paleo_area = None
    if dem_path:
        try:
            paleo_features, paleo_area = generate_paleochannels(dem_path)
        except Exception as e:
            print(f"  WARNING: Paleochannel generation failed: {e}")

    # Convert to GeoJSON features, excluding modern rivers in paleo sub-area
    features = []
    excluded = 0
    for idx, row in gdf.iterrows():
        # If in Star Carr paleo area, skip modern rivers
        if paleo_area is not None:
            geom = row.geometry
            if paleo_area.contains(geom) or paleo_area.intersects(geom):
                # Check if >50% of the river segment is inside paleo area
                try:
                    inside_frac = geom.intersection(paleo_area).length / geom.length
                    if inside_frac > 0.5:
                        excluded += 1
                        continue
                except Exception:
                    pass

        name = row.get('name', row.get('NAME', ''))
        permanence = 'permanent'
        certainty = 'INDIRECT'

        features.append({
            'type': 'Feature',
            'properties': {
                'id': f'river_{idx:05d}',
                'name': name if name else None,
                'permanence': permanence,
                'certainty': certainty,
                'source': 'OS Open Rivers (OGL)'
            },
            'geometry': mapping(row.geometry)
        })

    if excluded > 0:
        print(f"  Replaced {excluded} modern river segments with {len(paleo_features)} paleochannels")

    # Add paleochannel features
    features.extend(paleo_features)

    return {
        'type': 'FeatureCollection',
        'features': features
    }


def save_geojson(data, filename):
    """Save GeoJSON to processed directory."""
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, filename)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  Saved: {filename} ({size_mb:.1f} MB)")
    return out_path


def main():
    print("=" * 60)
    print("Mezolit2 — Terrain Classification & River Processing")
    print("=" * 60)

    # Step 1: Load DEM
    dem_src, dem_path = load_and_merge_dem()

    with rasterio.open(dem_path) as src:
        elevation = src.read(1)
        transform = src.transform

        # Clip DEM to extended Yorkshire bbox
        # (if DEM covers larger area, this speeds up processing)

        # Step 2: Compute slope
        slope = compute_slope(elevation, transform)

        # Step 3: Classify terrain
        classified = classify_terrain(elevation, slope, transform)

        # Step 3b: Reclassify river corridors as floodplain (adaptive width)
        classified = reclassify_river_corridors(classified, elevation, slope, transform)

    # Step 4: Polygonize (with smart holes + progressive simplification)
    features = polygonize_terrain(classified, transform)

    # Step 5: Clip to Yorkshire
    features = clip_to_yorkshire(features)

    # Step 6: Add Star Carr anchor (ADS → DEM 24m → synthetic)
    features = add_star_carr_anchor(features, dem_path=dem_path)

    # Step 6b: Export archaeological sites from ADS
    sites = load_ads_sites()
    if sites:
        sites_geojson = {
            'type': 'FeatureCollection',
            'features': sites
        }
        save_geojson(sites_geojson, 'sites.geojson')

    # Step 7: Save terrain features
    terrain_geojson = {
        'type': 'FeatureCollection',
        'features': features
    }
    save_geojson(terrain_geojson, 'terrain_features.geojson')

    # Step 8: Process rivers (with paleochannels in Star Carr area)
    rivers_geojson = process_rivers(dem_path=dem_path)
    if rivers_geojson:
        save_geojson(rivers_geojson, 'rivers_yorkshire.geojson')

    print(f"\nDone! Terrain: {len(features)} polygons"
          f"{f', Sites: {len(sites)}' if sites else ''}")
    print("Next step: python 05_kb_rules.py")


if __name__ == '__main__':
    main()

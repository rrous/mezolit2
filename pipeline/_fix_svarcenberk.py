"""One-off script: reconstruct Švarcenberk paleolake with fractal shoreline."""
import sys, os, json, math
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
np.random.seed(42)

import rasterio
import geopandas as gpd
from pyproj import Transformer
from scipy import ndimage
from shapely.geometry import Point, mapping, Polygon, shape
from rasterio.features import shapes as rio_shapes, geometry_mask

to_jtsk = Transformer.from_crs('EPSG:4326', 'EPSG:5514', always_xy=True)
to_wgs  = Transformer.from_crs('EPSG:5514', 'EPSG:4326', always_xy=True)

BASE = os.path.dirname(__file__)
RAW  = os.path.join(BASE, '..', 'data', 'raw', 'cz')

SV_LAT, SV_LON = 49.148, 14.707
TARGET_HA = 37.8
cx_jtsk, cy_jtsk = to_jtsk.transform(SV_LON, SV_LAT)

# --- Load CGS niva polygon containing Švarcenberk center ---
cgs = gpd.read_file(os.path.join(RAW, 'cgs', 'geologicka_mapa50.geojson'))
if cgs.crs and cgs.crs.to_epsg() != 4326:
    cgs = cgs.to_crs('EPSG:4326')

niva_poly = None
for _, row in cgs.iterrows():
    if 'nivní' in str(row.get('hor_karto', '')).lower():
        if row.geometry.contains(Point(SV_LON, SV_LAT)):
            niva_poly = row.geometry
            break

if niva_poly is None:
    print("ERROR: niva polygon not found")
    sys.exit(1)
print(f"Niva polygon: {niva_poly.area * 111320 * 72815 / 10000:.0f} ha")

# --- DEM: find level that gives ~38 ha depression at center ---
dem_path = os.path.join(RAW, 'dem', 'trebonsko_dmr5g_10m.tif')
with rasterio.open(dem_path) as src:
    dem = src.read(1)
    transform = src.transform
    row_c, col_c = src.index(cx_jtsk, cy_jtsk)
    center_elev = dem[row_c, col_c]
    print(f"Center: row={row_c} col={col_c} elev={center_elev:.1f}m")

    niva_jtsk = Polygon([to_jtsk.transform(x, y)
                         for x, y in niva_poly.exterior.coords])
    niva_mask = geometry_mask([mapping(niva_jtsk)],
                              out_shape=dem.shape, transform=transform,
                              invert=True)

    # Scan levels to find best match for target area
    best_level, best_diff = center_elev, 999
    for delta in np.arange(-0.5, 2.0, 0.05):
        level = center_elev + delta
        mask = (dem <= level) & niva_mask
        labeled, _ = ndimage.label(mask)
        lbl = labeled[row_c, col_c]
        if lbl == 0:
            continue
        area_ha = np.sum(labeled == lbl) * 100 / 10000
        diff = abs(area_ha - TARGET_HA)
        if diff < best_diff:
            best_diff = diff
            best_level = level
            best_area = area_ha

    print(f"Best level: {best_level:.2f}m (+{best_level-center_elev:.2f}m), "
          f"area={best_area:.1f}ha (target {TARGET_HA})")

    # Extract component
    mask = (dem <= best_level) & niva_mask
    labeled, _ = ndimage.label(mask)
    lbl = labeled[row_c, col_c]
    component = (labeled == lbl).astype(np.uint8)

    # Morphological smoothing (erode 2px + dilate 2px)
    eroded = ndimage.binary_erosion(component, iterations=2)
    smoothed = ndimage.binary_dilation(eroded, iterations=2).astype(np.uint8)
    labeled2, _ = ndimage.label(smoothed)
    lbl2 = labeled2[row_c, col_c]
    if lbl2 > 0:
        smoothed = (labeled2 == lbl2).astype(np.uint8)
    print(f"After morphological smoothing: {np.sum(smoothed)*100/10000:.1f}ha")

    # Vectorize
    polys = list(rio_shapes(smoothed, mask=smoothed == 1, transform=transform))
    coords_jtsk = polys[0][0]['coordinates'][0]
    coords_wgs = [to_wgs.transform(x, y) for x, y in coords_jtsk]
    raw_poly = Polygon(coords_wgs)

    # Simplify (tolerance ~12m)
    lake = raw_poly.simplify(0.00012, preserve_topology=True)
    print(f"Simplified: {len(lake.exterior.coords)} vertices")


# --- FRACTAL MIDPOINT DISPLACEMENT ---
def fractal_perturb(polygon, iterations=3, amplitude=0.00012, decay=0.55):
    """Add fractal detail to polygon boundary via midpoint displacement.

    Each iteration doubles the vertex count by inserting midpoints with
    random perpendicular displacement.  Amplitude decays per iteration
    to produce self-similar shoreline texture.
    """
    coords = list(polygon.exterior.coords)[:-1]

    for it in range(iterations):
        amp = amplitude * (decay ** it)
        new_coords = []
        for i in range(len(coords)):
            p1 = coords[i]
            p2 = coords[(i + 1) % len(coords)]
            new_coords.append(p1)

            mid_x = (p1[0] + p2[0]) / 2
            mid_y = (p1[1] + p2[1]) / 2
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            edge_len = math.sqrt(dx * dx + dy * dy)
            if edge_len < 1e-8:
                new_coords.append((mid_x, mid_y))
                continue

            perp_x = -dy / edge_len
            perp_y =  dx / edge_len
            displacement = np.random.normal(0, amp * 0.7)
            new_coords.append((mid_x + perp_x * displacement,
                               mid_y + perp_y * displacement))
        coords = new_coords

    coords.append(coords[0])
    result = Polygon(coords)
    if not result.is_valid:
        result = result.buffer(0)
        if result.geom_type == 'MultiPolygon':
            result = max(result.geoms, key=lambda g: g.area)
    return result


lake_fractal = fractal_perturb(lake, iterations=3, amplitude=0.00012, decay=0.55)
lake_final = lake_fractal.simplify(0.00003, preserve_topology=True)

# --- Stats ---
area_ha = lake_final.area * 111320 * 72815 / 10000
n_verts = len(lake_final.exterior.coords)
circ = 4 * math.pi * lake_final.area / (lake_final.length ** 2)
centroid = lake_final.centroid

coords_xy = [((lon - centroid.x) * 72815, (lat - centroid.y) * 111320)
             for lon, lat in lake_final.exterior.coords[:-1]]
turns = []
for i in range(len(coords_xy)):
    p0 = coords_xy[(i - 1) % len(coords_xy)]
    p1 = coords_xy[i]
    p2 = coords_xy[(i + 1) % len(coords_xy)]
    v1 = (p1[0] - p0[0], p1[1] - p0[1])
    v2 = (p2[0] - p1[0], p2[1] - p1[1])
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    dot   = v1[0] * v2[0] + v1[1] * v2[1]
    if abs(dot) > 0.001:
        turns.append(abs(math.atan2(cross, dot)) * 180 / math.pi)

print(f"\n{'='*50}")
print(f"FINAL Švarcenberk paleolake")
print(f"{'='*50}")
print(f"  Centroid:    {centroid.y:.5f}N, {centroid.x:.5f}E")
print(f"  Offset:      {(centroid.y-SV_LAT)*111320:.0f}m N, "
      f"{(centroid.x-SV_LON)*72815:.0f}m E")
print(f"  Area:        {area_ha:.1f} ha (target {TARGET_HA})")
print(f"  Vertices:    {n_verts}")
print(f"  Circularity: {circ:.3f}  (old ellipse: 0.767)")
print(f"  Turn angles: mean={sum(turns)/len(turns):.1f}° "
      f"max={max(turns):.1f}° stdev={np.std(turns):.1f}°")
print(f"  (old ellipse: mean=5.7° max=12.3° stdev=1.6°)")

# --- Update paleolakes_cz.geojson ---
pl_path = os.path.join(RAW, 'paleolakes_cz.geojson')
with open(pl_path, encoding='utf-8') as f:
    pl = json.load(f)

for feat in pl['features']:
    if feat['properties'].get('name') == 'Svarcenberk':
        feat['geometry'] = mapping(lake_final)
        feat['properties']['area_ha'] = round(area_ha, 1)
        feat['properties']['source'] = (
            'DEM depression + CGS niva + fractal perturbation; '
            'Pokorny et al. 2010')
        feat['properties']['note'] = (
            'Natural shoreline reconstructed from DEM depression within CGS '
            'alluvial floodplain, with fractal midpoint displacement for '
            'realistic shoreline texture. Paleolake ~7000 BCE.')
        break

with open(pl_path, 'w', encoding='utf-8') as f:
    json.dump(pl, f, ensure_ascii=False)
print(f"\n  Saved {pl_path}")

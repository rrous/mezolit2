"""
Reconstruct Yorkshire coastline at ~6200 BCE from GEBCO bathymetry.

Extracts -25m contour (sea level ~6200 BCE per Shennan et al. 2018)
and generates a land polygon for the reconstructed coastline.

Input:  data/raw/gebco/ (GEBCO 2023 GeoTIFF or NetCDF)
Output: data/processed/coastline_6200bce.geojson

Usage:
    python 03_coastline.py
"""

import os
import sys
import json
import numpy as np

try:
    import rasterio
    from rasterio.features import shapes
    from shapely.geometry import shape, mapping, MultiPolygon
    from shapely.ops import unary_union
    import geopandas as gpd
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install -r requirements.txt")
    sys.exit(1)

# Configuration
SEA_LEVEL_OFFSET_M = -25.0  # ~6200 BCE sea level (Shennan et al. 2018)
YORKSHIRE_BBOX = (-3.0, 52.5, 1.5, 55.5)  # Extended bbox for coastline context
SIMPLIFY_TOLERANCE = 0.001  # ~100m at this latitude — preserves natural shapes
MIN_AREA_DEG2 = 0.0001  # Remove tiny islands

RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'gebco')
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')


def find_gebco_file():
    """Find GEBCO data file (GeoTIFF or NetCDF)."""
    if not os.path.exists(RAW_DIR):
        print(f"ERROR: Directory not found: {RAW_DIR}")
        print("Download GEBCO data first — see 02_download.md")
        sys.exit(1)

    for f in os.listdir(RAW_DIR):
        if f.endswith(('.tif', '.tiff')):
            return os.path.join(RAW_DIR, f)

    # Try NetCDF
    for f in os.listdir(RAW_DIR):
        if f.endswith('.nc'):
            print("NetCDF format detected. Converting to GeoTIFF first...")
            return convert_netcdf_to_geotiff(os.path.join(RAW_DIR, f))

    print(f"ERROR: No GEBCO data found in {RAW_DIR}")
    print("Expected: .tif or .nc file")
    sys.exit(1)


def convert_netcdf_to_geotiff(nc_path):
    """Convert GEBCO NetCDF to GeoTIFF using rasterio (no external GDAL binary needed)."""
    tif_path = nc_path.replace('.nc', '.tif')
    with rasterio.open(nc_path) as src:
        data = src.read(1)
        profile = src.profile.copy()
        profile.update(driver='GTiff', count=1)
        with rasterio.open(tif_path, 'w', **profile) as dst:
            dst.write(data, 1)
    print(f"Converted to GeoTIFF: {os.path.basename(tif_path)}")
    return tif_path


def extract_land_polygon(gebco_path):
    """Extract land polygon at specified sea level offset."""
    print(f"Reading GEBCO data from {os.path.basename(gebco_path)}...")

    with rasterio.open(gebco_path) as src:
        # Read the full dataset
        elevation = src.read(1)
        transform = src.transform

        # Create binary mask: 1 = land (above sea level), 0 = sea
        land_mask = (elevation >= SEA_LEVEL_OFFSET_M).astype(np.uint8)

        print(f"  Grid size: {elevation.shape}")
        print(f"  Elevation range: {elevation.min():.0f}m to {elevation.max():.0f}m")
        print(f"  Sea level threshold: {SEA_LEVEL_OFFSET_M}m")
        print(f"  Land pixels: {land_mask.sum():,} / {land_mask.size:,}")

        # Polygonize the land mask
        print("Polygonizing land areas...")
        land_polygons = []
        for geom, value in shapes(land_mask, transform=transform):
            if value == 1:  # Land
                poly = shape(geom)
                if poly.is_valid and poly.area > MIN_AREA_DEG2:
                    land_polygons.append(poly)

    print(f"  Found {len(land_polygons)} land polygons")

    # Merge into single multipolygon
    print("Merging polygons...")
    merged = unary_union(land_polygons)

    # Clip to extended Yorkshire bbox
    from shapely.geometry import box
    clip_box = box(*YORKSHIRE_BBOX)
    clipped = merged.intersection(clip_box)

    # Simplify while preserving topology
    print(f"Simplifying (tolerance={SIMPLIFY_TOLERANCE}°)...")
    simplified = clipped.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)

    # Ensure MultiPolygon
    if simplified.geom_type == 'Polygon':
        simplified = MultiPolygon([simplified])

    print(f"  Final polygon count: {len(simplified.geoms)}")
    return simplified


def save_geojson(coastline_geom):
    """Save coastline as GeoJSON FeatureCollection."""
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, 'coastline_6200bce.geojson')

    feature = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "id": "coast_6200bce",
                "name": "Rekonstruované pobřeží Yorkshire ~6200 BCE",
                "sea_level_offset_m": SEA_LEVEL_OFFSET_M,
                "certainty": "INDIRECT",
                "source": "GEBCO 2023; Shennan et al. 2018",
                "status": "VALID"
            },
            "geometry": mapping(coastline_geom)
        }]
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(feature, f, ensure_ascii=False)

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"\nSaved: {out_path} ({size_mb:.1f} MB)")
    return out_path


def main():
    print("=" * 60)
    print("Mezolit2 — Coastline Reconstruction ~6200 BCE")
    print("=" * 60)

    gebco_path = find_gebco_file()
    coastline = extract_land_polygon(gebco_path)
    out_path = save_geojson(coastline)

    print(f"\nDone! Coastline saved to {out_path}")
    print("Next step: python 04_terrain.py")


if __name__ == '__main__':
    main()

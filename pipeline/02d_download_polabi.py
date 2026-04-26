"""
Download Czech data sources for Polabí region (~6200 BCE landscape model).

Downloads:
  1. ČÚZK DMR 5G (DEM 25m) via ArcGIS ImageServer -> GeoTIFF
     (native 2m resampled to 25m per polabi_implementace.md §1; EU-DEM alternative documented in §2.1)
  2. DIBAVOD hydrology:
     - A01 (1412) — Vodní tok, tokový model (stream network)
     - A02 (1413) — Vodní tok, jemné úseky (fine stream segments)
     - A05 (1416) — Vodní nádrže (water bodies)
     - A06 (1417) — Bažina, močál (swamps, marshes)
     - A07 (1418) — Hydrologické členění, povodí IV. řádu (watersheds)
  3. ČGS geologická mapa 1:50 000 via REST query -> GeoJSON
  4. AOPK VMB biotopové mapování via REST query -> GeoJSON

Bbox: SW 49.70°N, 14.45°E -> NE 50.30°N, 15.75°E (~101 × 78 km, ~7900 km²)

Output: data/raw/polabi/

Usage:
    python 02d_download_polabi.py              # download all
    python 02d_download_polabi.py --only dem   # only DMR 5G
    python 02d_download_polabi.py --only dib   # only DIBAVOD
    python 02d_download_polabi.py --only geo   # only ČGS geology
    python 02d_download_polabi.py --only vmb   # only AOPK VMB
    python 02d_download_polabi.py --verify     # verify existing downloads only
    python 02d_download_polabi.py --dem-resolution 25  # override DEM resolution (default 25m)

References: docs/polabi_implementace.md §1 (bbox), §2 (data sources).
"""

import argparse
import io
import json
import math
import os
import sys
import time
import zipfile
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows consoles (cp1250 breaks on ° × ² — etc.)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# ── Config ────────────────────────────────────────────────────────────────────

# Polabí bounding box (WGS84) per polabi_implementace.md §1
BBOX_WGS84 = {"south": 49.70, "north": 50.30, "west": 14.45, "east": 15.75}

# S-JTSK (EPSG:5514) enveloping bbox — computed via pyproj from all 4 WGS84 corners
# SW (49.70N, 14.45E) -> x=-746630, y=-1085985
# SE (49.70N, 15.75E) -> x=-653621, y=-1097928
# NW (50.30N, 14.45E) -> x=-737558, y=-1019874
# NE (50.30N, 15.75E) -> x=-645695, y=-1031667
# Envelope (rounded outward):
BBOX_SJTSK = {"xmin": -747000, "ymin": -1098000, "xmax": -645000, "ymax": -1019000}
# Effective area ≈ 102 × 79 km ≈ 8058 km²

# Output directory
OUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "polabi"

# API endpoints
DMR5G_URL = "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"
CGS_GEO_URL = "https://mapy.geology.cz/arcgis/rest/services/Geologie/geologicka_mapa50/MapServer/2/query"
DIBAVOD_BASE = "https://www.dibavod.cz"
VMB_URL = "https://gis.nature.cz/arcgis/rest/services/Biotopy/PrirBiotopHabitat/MapServer"

# DIBAVOD file IDs — Polabí needs stream network (A01), fine segments (A02),
# water bodies (A05), swamps (A06), watersheds (A07).
# IDs confirmed from https://www.dibavod.cz/index.php?id=27 (2026-04)
DIBAVOD_FILES = {
    "A01": {"id": 1412, "name": "dib_A01_VodniTokTokovyModel", "desc": "Vodní tok — tokový model (centerlines)"},
    "A02": {"id": 1413, "name": "dib_A02_VodniTokJemneUseky",  "desc": "Vodní tok — jemné úseky (1:50 000)"},
    "A05": {"id": 1416, "name": "dib_A05_VodniNadrze",         "desc": "Vodní nádrže (water bodies)"},
    "A06": {"id": 1417, "name": "dib_A06_BazinaMocal",         "desc": "Bažina, močál"},
    "A07": {"id": 1418, "name": "dib_A07_PovodiIVRadu",        "desc": "Hydrologické členění — povodí IV. řádu"},
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def bbox_wgs84_str():
    b = BBOX_WGS84
    return f"N{b['north']} S{b['south']} W{b['west']} E{b['east']}"


def ensure_dir(subdir: str) -> Path:
    d = OUT_DIR / subdir
    d.mkdir(parents=True, exist_ok=True)
    return d


def file_exists_skip(filepath: Path) -> bool:
    if filepath.exists() and filepath.stat().st_size > 100:
        size = filepath.stat().st_size
        unit = "KB" if size < 1024 * 1024 else "MB"
        val = size / 1024 if unit == "KB" else size / 1024 / 1024
        print(f"  Already exists: {filepath.name} ({val:.1f} {unit}) — skipping")
        return True
    return False


# ── 1. DMR 5G (DEM) ──────────────────────────────────────────────────────────

def download_dem(dem_resolution: int = 25) -> Path:
    """Download DMR 5G DEM via ArcGIS ImageServer exportImage.

    Native resolution is 2 m; we resample server-side to `dem_resolution`
    (default 25 m per polabi_implementace.md §1).
    For ~8 000 km² at 25 m: ~12.6 M px -> ~50 MB GeoTIFF.

    Tiling: ImageServer maxImageWidth=15 000 in theory but large exports
    return HTTP 500 in practice, so we use 2 000×2 000 tiles and merge.
    """
    out_dir = ensure_dir("dem")
    out_file = out_dir / f"polabi_dmr5g_{dem_resolution}m.tif"

    if file_exists_skip(out_file):
        return out_file

    b = BBOX_SJTSK
    width_m = abs(b["xmax"] - b["xmin"])
    height_m = abs(b["ymax"] - b["ymin"])
    width_px = int(width_m / dem_resolution)
    height_px = int(height_m / dem_resolution)

    print(f"  DMR 5G: {width_m/1000:.0f}×{height_m/1000:.0f} km -> {width_px}×{height_px} px @ {dem_resolution} m")

    max_w, max_h = 2000, 2000
    tiles_x = math.ceil(width_px / max_w)
    tiles_y = math.ceil(height_px / max_h)
    total_tiles = tiles_x * tiles_y

    if total_tiles == 1:
        return _download_dem_tile(out_file, b, width_px, height_px)

    print(f"  Image too large for single request ({width_px}×{height_px})")
    print(f"  Downloading {total_tiles} tiles ({tiles_x}×{tiles_y})...")

    tile_dir = out_dir / "tiles"
    tile_dir.mkdir(exist_ok=True)
    tile_paths = []

    x_step = width_m / tiles_x
    y_step = height_m / tiles_y

    for ty in range(tiles_y):
        for tx in range(tiles_x):
            tile_xmin = b["xmin"] + tx * x_step
            tile_xmax = b["xmin"] + (tx + 1) * x_step
            tile_ymin = b["ymin"] + ty * y_step
            tile_ymax = b["ymin"] + (ty + 1) * y_step

            tw = min(max_w, int((tile_xmax - tile_xmin) / dem_resolution))
            th = min(max_h, int((tile_ymax - tile_ymin) / dem_resolution))

            tile_bbox = {"xmin": tile_xmin, "ymin": tile_ymin,
                         "xmax": tile_xmax, "ymax": tile_ymax}

            tile_file = tile_dir / f"tile_{tx}_{ty}.tif"
            tile_idx = ty * tiles_x + tx + 1
            print(f"  Tile {tile_idx}/{total_tiles}: {tw}×{th} px")

            if not file_exists_skip(tile_file):
                _download_dem_tile(tile_file, tile_bbox, tw, th)

            if tile_file.exists():
                tile_paths.append(tile_file)

            time.sleep(0.5)  # be polite to ČÚZK

    if len(tile_paths) == total_tiles:
        print(f"\n  Merging {total_tiles} tiles...")
        _merge_tiles(tile_paths, out_file)
    else:
        print(f"\n  WARNING: Only {len(tile_paths)}/{total_tiles} tiles downloaded")
        print(f"  Tiles saved in {tile_dir}")

    return out_file


def _download_dem_tile(out_file: Path, bbox: dict, width: int, height: int) -> Path:
    """Download a single DEM tile from ImageServer."""
    params = {
        "bbox": f"{bbox['xmin']},{bbox['ymin']},{bbox['xmax']},{bbox['ymax']}",
        "bboxSR": 5514,
        "imageSR": 5514,
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation",
        "f": "image",
    }

    try:
        resp = requests.get(f"{DMR5G_URL}/exportImage", params=params,
                            stream=True, timeout=180)
    except requests.exceptions.ConnectionError as e:
        print(f"  ERROR: Cannot connect to ČÚZK: {e}")
        return out_file

    if resp.status_code != 200:
        print(f"  ERROR: HTTP {resp.status_code}")
        print(f"  {resp.text[:300]}")
        return out_file

    ct = resp.headers.get("content-type", "")
    if "json" in ct or "html" in ct or "xml" in ct:
        print(f"  ERROR: Expected TIFF but got {ct}")
        print(f"  {resp.text[:300]}")
        return out_file

    total = int(resp.headers.get("content-length", 0))
    with open(out_file, "wb") as f:
        downloaded = 0
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
            if total and not HAS_TQDM:
                pct = downloaded / total * 100
                print(f"\r    {downloaded/1024/1024:.1f} / {total/1024/1024:.1f} MB ({pct:.0f}%)",
                      end="", flush=True)
        if total and not HAS_TQDM:
            print()

    size_mb = out_file.stat().st_size / 1024 / 1024
    print(f"  Saved: {out_file.name} ({size_mb:.1f} MB)")

    with open(out_file, "rb") as f:
        magic = f.read(4)
    if magic[:2] not in (b"II", b"MM"):
        print(f"  WARNING: File may not be a valid GeoTIFF (magic: {magic})")

    return out_file


def _merge_tiles(tile_paths: list, out_file: Path):
    """Merge DEM tiles into single GeoTIFF using rasterio."""
    try:
        import rasterio
        from rasterio.merge import merge

        datasets = [rasterio.open(p) for p in tile_paths]
        merged, transform = merge(datasets)
        profile = datasets[0].profile.copy()
        profile.update(
            width=merged.shape[2],
            height=merged.shape[1],
            transform=transform,
        )
        for ds in datasets:
            ds.close()

        with rasterio.open(out_file, "w", **profile) as dst:
            dst.write(merged)

        size_mb = out_file.stat().st_size / 1024 / 1024
        print(f"  Merged: {out_file.name} ({size_mb:.1f} MB)")
    except ImportError:
        print("  WARNING: rasterio not available — tiles not merged")
        print("  Install rasterio and run again, or merge manually in QGIS")


# ── 2. DIBAVOD ────────────────────────────────────────────────────────────────

def download_dibavod() -> list:
    """Download DIBAVOD shapefiles (A01, A02, A05, A06, A07).

    DIBAVOD is a national dataset (not bbox-filtered at download time);
    spatial cropping to Polabí bbox happens in 04_terrain_polabi.py.
    """
    out_dir = ensure_dir("dibavod")
    downloaded = []

    for code, info in DIBAVOD_FILES.items():
        zip_file = out_dir / f"{info['name']}.zip"
        shp_dir = out_dir / code

        if shp_dir.exists() and any(shp_dir.glob("*.shp")):
            print(f"  Already exists: {code}/ — skipping")
            downloaded.append(shp_dir)
            continue

        if file_exists_skip(zip_file):
            # Re-attempt extraction
            try:
                shp_dir.mkdir(exist_ok=True)
                with zipfile.ZipFile(zip_file, "r") as zf:
                    zf.extractall(shp_dir)
                shp_files = list(shp_dir.glob("*.shp"))
                print(f"  Extracted from existing ZIP: {len(shp_files)} SHP in {code}/")
                downloaded.append(shp_dir)
            except zipfile.BadZipFile:
                print(f"  ERROR: {zip_file.name} is not a valid ZIP — re-downloading")
                zip_file.unlink()
            else:
                continue

        print(f"  Downloading {code}: {info['desc']}")
        url = f"{DIBAVOD_BASE}/download.php?id_souboru={info['id']}"

        try:
            resp = requests.get(url, timeout=180, allow_redirects=True, stream=True)
        except requests.exceptions.ConnectionError as e:
            print(f"  ERROR: Cannot connect to DIBAVOD: {e}")
            continue

        if resp.status_code != 200:
            print(f"  ERROR: HTTP {resp.status_code}")
            continue

        ct = resp.headers.get("content-type", "")
        if "zip" not in ct and "octet" not in ct:
            print(f"  WARNING: Unexpected content-type: {ct}")
            redirect_url = f"{DIBAVOD_BASE}/data/download/{info['name']}.zip"
            print(f"  Trying direct URL: {redirect_url}")
            try:
                resp = requests.get(redirect_url, timeout=180, stream=True)
            except requests.exceptions.ConnectionError:
                print(f"  ERROR: Direct URL also failed")
                continue

        total = int(resp.headers.get("content-length", 0))
        with open(zip_file, "wb") as f:
            dl = 0
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                dl += len(chunk)
                if total and not HAS_TQDM:
                    print(f"\r    {dl/1024/1024:.1f} / {total/1024/1024:.1f} MB",
                          end="", flush=True)
            if total and not HAS_TQDM:
                print()

        size_mb = zip_file.stat().st_size / 1024 / 1024
        print(f"  Saved: {zip_file.name} ({size_mb:.1f} MB)")

        try:
            shp_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(zip_file, "r") as zf:
                zf.extractall(shp_dir)
            shp_files = list(shp_dir.glob("*.shp"))
            print(f"  Extracted: {len(shp_files)} SHP files in {code}/")
            downloaded.append(shp_dir)
        except zipfile.BadZipFile:
            print(f"  ERROR: Invalid ZIP — possibly HTML error page")
            zip_file.unlink()

        time.sleep(0.5)

    return downloaded


# ── 3. ČGS geological map ────────────────────────────────────────────────────

def download_cgs_geology() -> Path:
    """Download ČGS 1:50k geological polygons via REST query (paginated)."""
    out_dir = ensure_dir("cgs")
    out_file = out_dir / "geologicka_mapa50.geojson"

    if file_exists_skip(out_file):
        return out_file

    b = BBOX_WGS84
    geometry = f"{b['west']},{b['south']},{b['east']},{b['north']}"

    all_features = []
    offset = 0
    batch_size = 1000

    print(f"  Querying ČGS geological map 1:50 000...")

    while True:
        params = {
            "where": "1=1",
            "geometry": geometry,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "outSR": 4326,
            "outFields": "*",
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            "f": "geojson",
        }

        try:
            resp = requests.get(CGS_GEO_URL, params=params, timeout=60)
        except requests.exceptions.ConnectionError as e:
            print(f"  ERROR: Cannot connect to ČGS: {e}")
            break

        if resp.status_code != 200:
            print(f"  ERROR: HTTP {resp.status_code}")
            break

        data = resp.json()

        if "error" in data:
            print(f"  ERROR: {data['error']}")
            break

        features = data.get("features", [])
        all_features.extend(features)
        print(f"    Batch {offset // batch_size + 1}: {len(features)} features (total: {len(all_features)})")

        if len(features) < batch_size:
            break

        offset += batch_size
        time.sleep(0.3)

    if all_features:
        geojson = {"type": "FeatureCollection", "features": all_features}
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)

        size_mb = out_file.stat().st_size / 1024 / 1024
        print(f"  Saved: {out_file.name} ({size_mb:.1f} MB, {len(all_features)} features)")
    else:
        print("  ERROR: No features downloaded")

    return out_file


# ── 4. AOPK VMB biotope map ──────────────────────────────────────────────────

def download_vmb() -> Path:
    """Download AOPK VMB biotope polygons via REST query (paginated).

    Uses layer 1 (aktualizace 2007-2026) which is more current than layer 0.
    """
    out_dir = ensure_dir("vmb")
    out_file = out_dir / "vmb_biotopy.geojson"

    if file_exists_skip(out_file):
        return out_file

    b = BBOX_WGS84
    geometry = f"{b['west']},{b['south']},{b['east']},{b['north']}"

    all_features = []
    offset = 0
    batch_size = 1000
    layer = 1

    print(f"  Querying AOPK VMB biotope polygons (layer {layer})...")

    while True:
        params = {
            "where": "1=1",
            "geometry": geometry,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "outSR": 4326,
            "outFields": "*",
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            "f": "geojson",
        }

        query_url = f"{VMB_URL}/{layer}/query"

        try:
            resp = requests.get(query_url, params=params, timeout=180)
        except requests.exceptions.ConnectionError as e:
            print(f"  ERROR: Cannot connect to AOPK: {e}")
            break

        if resp.status_code != 200:
            print(f"  ERROR: HTTP {resp.status_code}")
            break

        data = resp.json()

        if "error" in data:
            print(f"  ERROR: {data['error']}")
            break

        features = data.get("features", [])
        all_features.extend(features)
        print(f"    Batch {offset // batch_size + 1}: {len(features)} features (total: {len(all_features)})")

        if len(features) < batch_size:
            break

        offset += batch_size
        time.sleep(0.3)

    if all_features:
        geojson = {"type": "FeatureCollection", "features": all_features}
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)

        size_mb = out_file.stat().st_size / 1024 / 1024
        print(f"  Saved: {out_file.name} ({size_mb:.1f} MB, {len(all_features)} features)")
    else:
        print("  ERROR: No features downloaded")

    return out_file


# ── Verification ──────────────────────────────────────────────────────────────

def verify_downloads() -> dict:
    """Print a summary of all downloaded Polabí data."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    results = {}

    # DEM
    dem_candidates = list((OUT_DIR / "dem").glob("polabi_dmr5g_*m.tif")) if (OUT_DIR / "dem").exists() else []
    if dem_candidates:
        dem_path = dem_candidates[0]
        try:
            import rasterio
            with rasterio.open(dem_path) as ds:
                print(f"\n  DEM: {dem_path.name}")
                print(f"    Shape: {ds.width}×{ds.height} px")
                print(f"    CRS: {ds.crs}")
                print(f"    Bounds: {ds.bounds}")
                print(f"    NoData: {ds.nodata}")
                band = ds.read(1)
                import numpy as np
                valid = band[band != (ds.nodata if ds.nodata is not None else -9999)]
                if valid.size > 0:
                    print(f"    Elevation: {valid.min():.1f} — {valid.max():.1f} m (mean {valid.mean():.1f})")
                    results["DEM"] = f"OK ({ds.width}×{ds.height}, {valid.min():.0f}-{valid.max():.0f} m)"
                else:
                    print(f"    WARNING: no valid pixels")
                    results["DEM"] = "WARN (no valid pixels)"
        except ImportError:
            print("\n  DEM: rasterio not available — skipping validation")
            results["DEM"] = "SKIP (no rasterio)"
        except Exception as e:
            print(f"\n  DEM: ERROR — {e}")
            results["DEM"] = f"ERROR: {e}"
    else:
        print("\n  DEM: not downloaded")
        results["DEM"] = "MISSING"

    # DIBAVOD
    dib_dir = OUT_DIR / "dibavod"
    if dib_dir.exists():
        for code, info in DIBAVOD_FILES.items():
            sub = dib_dir / code
            shps = list(sub.glob("*.shp")) if sub.exists() else []
            if shps:
                try:
                    import geopandas as gpd
                    gdf = gpd.read_file(shps[0])
                    print(f"\n  DIBAVOD {code}: {shps[0].name}")
                    print(f"    Features: {len(gdf)}")
                    print(f"    CRS: {gdf.crs}")
                    print(f"    Columns: {list(gdf.columns)[:8]}...")
                    results[f"DIBAVOD {code}"] = f"OK ({len(gdf)} features)"
                except ImportError:
                    print(f"\n  DIBAVOD {code}: SHP exists (no geopandas)")
                    results[f"DIBAVOD {code}"] = "OK (no gpd)"
                except Exception as e:
                    print(f"\n  DIBAVOD {code}: ERROR — {e}")
                    results[f"DIBAVOD {code}"] = f"ERROR: {e}"
            else:
                zips = list(dib_dir.glob(f"*{info['name']}*.zip"))
                if zips:
                    print(f"\n  DIBAVOD {code}: ZIP exists but not extracted")
                    results[f"DIBAVOD {code}"] = "ZIP only"
                else:
                    print(f"\n  DIBAVOD {code}: not downloaded")
                    results[f"DIBAVOD {code}"] = "MISSING"
    else:
        for code in DIBAVOD_FILES:
            results[f"DIBAVOD {code}"] = "MISSING"

    # GeoJSON files
    for name, path in [
        ("ČGS geologie", OUT_DIR / "cgs" / "geologicka_mapa50.geojson"),
        ("AOPK VMB",     OUT_DIR / "vmb" / "vmb_biotopy.geojson"),
    ]:
        if path.exists():
            try:
                import geopandas as gpd
                gdf = gpd.read_file(path)
                bounds = gdf.total_bounds
                print(f"\n  {name}: {path.name}")
                print(f"    Features: {len(gdf)}")
                print(f"    Columns: {list(gdf.columns)[:8]}...")
                print(f"    Bounds: [{bounds[0]:.4f}, {bounds[1]:.4f}] -> [{bounds[2]:.4f}, {bounds[3]:.4f}]")
                if hasattr(gdf, "crs") and gdf.crs:
                    print(f"    CRS: {gdf.crs}")

                b = BBOX_WGS84
                in_bbox = (bounds[0] >= b["west"] - 0.5 and bounds[2] <= b["east"] + 0.5 and
                           bounds[1] >= b["south"] - 0.5 and bounds[3] <= b["north"] + 0.5)
                print(f"    Bbox check: {'OK' if in_bbox else 'WARNING — extends beyond expected bbox'}")

                results[name] = f"OK ({len(gdf)} features)"
            except ImportError:
                with open(path, "r") as f:
                    data = json.load(f)
                n = len(data.get("features", []))
                print(f"\n  {name}: {path.name} ({n} features, no geopandas for full validation)")
                results[name] = f"OK ({n} features, no gpd)"
            except Exception as e:
                print(f"\n  {name}: ERROR — {e}")
                results[name] = f"ERROR: {e}"
        else:
            print(f"\n  {name}: not downloaded")
            results[name] = "MISSING"

    # Summary
    print("\n" + "-" * 60)
    print("SUMMARY")
    print("-" * 60)
    for name, status in results.items():
        icon = "[OK]" if status.startswith("OK") else ("[??]" if "SKIP" in status or "ZIP" in status else "[!!]")
        print(f"  {icon} {name}: {status}")

    ok = sum(1 for s in results.values() if s.startswith("OK"))
    print(f"\n  {ok}/{len(results)} sources verified OK")

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download Czech data sources for Polabí (Mezolit2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--only", choices=["dem", "dib", "geo", "vmb"],
                        help="Download only one source")
    parser.add_argument("--verify", action="store_true",
                        help="Verify existing downloads only (no download)")
    parser.add_argument("--dem-resolution", type=int, default=25,
                        help="DEM resampling resolution in meters (default: 25)")
    args = parser.parse_args()

    print("=" * 60)
    print("Mezolit2 — Czech Data Sources Download (Polabí)")
    print("=" * 60)
    print(f"Bbox    : {bbox_wgs84_str()}  (~101x78 km, ~7900 km2)")
    print(f"Output  : {OUT_DIR}")
    print()

    if args.verify:
        verify_downloads()
        return

    sources = {
        "dem": ("1. ČÚZK DMR 5G (DEM @ 25 m)",    lambda: download_dem(args.dem_resolution)),
        "dib": ("2. DIBAVOD hydrologie (A01/A02/A05/A06/A07)", download_dibavod),
        "geo": ("3. ČGS geologická mapa 1:50k",   download_cgs_geology),
        "vmb": ("4. AOPK VMB biotopy",            download_vmb),
    }

    if args.only:
        items = {args.only: sources[args.only]}
    else:
        items = sources

    for key, (label, func) in items.items():
        print(f"\n{'-' * 60}")
        print(f"{label}")
        print(f"{'-' * 60}")
        try:
            func()
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    verify_downloads()

    print(f"\nNext step: pipeline transformation (04_terrain_polabi.py — viz docs/polabi_implementace.md §3)")


if __name__ == "__main__":
    main()

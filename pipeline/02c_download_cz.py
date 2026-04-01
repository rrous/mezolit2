"""
Download Czech data sources for Třeboňsko region (~7000 BCE landscape model).

Downloads:
  1. ČÚZK DMR 5G (DEM 2m) via ArcGIS ImageServer ->GeoTIFF
  2. ČGS geologická mapa 1:50 000 via REST query ->GeoJSON
  3. ČGS ložiska surovin via REST query ->GeoJSON
  4. DIBAVOD říční síť (A02) + vodní plochy (A05) + bažiny (A06) ->SHP (ZIP)
  5. AOPK VMB biotopové mapování via REST query ->GeoJSON

Bbox: SW 48.93°N, 14.53°E ->NE 49.22°N, 14.95°E (~930 km²)
Anchor: Švarcenberk (49.148°N, 14.707°E)

Output: data/raw/cz/

Usage:
    python 02c_download_cz.py              # download all
    python 02c_download_cz.py --only dem   # only DMR 5G
    python 02c_download_cz.py --only geo   # only ČGS geology
    python 02c_download_cz.py --only min   # only ČGS minerals
    python 02c_download_cz.py --only dib   # only DIBAVOD
    python 02c_download_cz.py --only vmb   # only AOPK VMB
    python 02c_download_cz.py --verify     # verify existing downloads only
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

import re
import xml.etree.ElementTree as ET

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

# Třeboňsko bounding box (WGS84)
BBOX_WGS84 = {"south": 48.93, "north": 49.22, "west": 14.53, "east": 14.95}

# S-JTSK (EPSG:5514) bbox --computed via pyproj from WGS84 corners
# SW (48.93N, 14.53E) -> x=-752461, y=-1171616
# NE (49.22N, 14.95E) -> x=-717786, y=-1143701
# Svarcenberk (49.148N, 14.707E) -> x=-736396, y=-1149320
BBOX_SJTSK = {"xmin": -753000, "ymin": -1172000, "xmax": -717000, "ymax": -1143000}

# Output directory
OUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "cz"

# API endpoints
DMR5G_URL = "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"
CGS_GEO_URL = "https://mapy.geology.cz/arcgis/rest/services/Geologie/geologicka_mapa50/MapServer/2/query"
CGS_MIN_URL = "https://mapy.geology.cz/arcgis/rest/services/Suroviny/loziska_zdroje/MapServer/0/query"
DIBAVOD_BASE = "https://www.dibavod.cz"
VMB_URL = "https://gis.nature.cz/arcgis/rest/services/Biotopy/PrirBiotopHabitat/MapServer"
AMCR_OAI_URL = "https://api.aiscr.cz/2.2/oai"

# AMCR period codes relevant to mesolithic (from heslo:obdobi vocabulary)
AMCR_PERIOD_IDS = {
    "HES-000275": "mezolit",            # -9600 to -5601
    "HES-000284": "paleolit-mezolit",   # -1000000 to -5601
    "HES-000264": "pozdni paleolit",    # -10000 to -8001
}

# DIBAVOD file IDs (from download page /index.php?id=27)
DIBAVOD_FILES = {
    "A02": {"id": 1413, "name": "dib_A02_VodniTokJemneUseky", "desc": "Vodní tok --jemné úseky (1:50 000)"},
    "A05": {"id": 1416, "name": "dib_A05_VodniNadrze", "desc": "Vodní nádrže"},
    "A06": {"id": 1417, "name": "dib_A06_BazinaMocal", "desc": "Bažina, močál"},
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
        print(f"  Already exists: {filepath.name} ({val:.1f} {unit}) --skipping")
        return True
    return False


# ── 1. DMR 5G (DEM) ──────────────────────────────────────────────────────────

def download_dem(dem_resolution: int = 5) -> Path:
    """Download DMR 5G DEM via ArcGIS ImageServer exportImage.

    Native resolution is 2m but we resample to `dem_resolution` (default 5m)
    for manageability. For ~930 km² at 5m: ~37M pixels ->~150 MB GeoTIFF.
    """
    out_dir = ensure_dir("dem")
    out_file = out_dir / f"trebonsko_dmr5g_{dem_resolution}m.tif"

    if file_exists_skip(out_file):
        return out_file

    b = BBOX_SJTSK
    width_m = abs(b["xmax"] - b["xmin"])
    height_m = abs(b["ymax"] - b["ymin"])
    width_px = int(width_m / dem_resolution)
    height_px = int(height_m / dem_resolution)

    print(f"  DMR 5G: {width_m/1000:.0f}×{height_m/1000:.0f} km ->{width_px}×{height_px} px @ {dem_resolution}m")

    # ImageServer has maxImageWidth=15000, maxImageHeight=4100
    # but large exports fail with HTTP 500, so use conservative tile size
    max_w, max_h = 2000, 2000
    tiles_x = math.ceil(width_px / max_w)
    tiles_y = math.ceil(height_px / max_h)
    total_tiles = tiles_x * tiles_y

    if total_tiles == 1:
        # Single request
        return _download_dem_tile(out_file, b, width_px, height_px)
    else:
        # Need tiling --download strips and combine with rasterio
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
                            stream=True, timeout=120)
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

    # Validate TIFF magic
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
        print("  WARNING: rasterio not available --tiles not merged")
        print("  Install rasterio and run again, or merge manually in QGIS")


# ── 2. ČGS geological map ────────────────────────────────────────────────────

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
        geojson = {
            "type": "FeatureCollection",
            "features": all_features,
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)

        size_mb = out_file.stat().st_size / 1024 / 1024
        print(f"  Saved: {out_file.name} ({size_mb:.1f} MB, {len(all_features)} features)")
    else:
        print("  ERROR: No features downloaded")

    return out_file


# ── 3. ČGS mineral deposits ──────────────────────────────────────────────────

def download_cgs_minerals() -> Path:
    """Download ČGS mineral deposits via REST query."""
    out_dir = ensure_dir("cgs")
    out_file = out_dir / "loziska_surovin.geojson"

    if file_exists_skip(out_file):
        return out_file

    b = BBOX_WGS84
    geometry = f"{b['west']},{b['south']},{b['east']},{b['north']}"

    print(f"  Querying ČGS mineral deposits...")

    params = {
        "where": "1=1",
        "geometry": geometry,
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "outSR": 4326,
        "outFields": "*",
        "returnGeometry": "true",
        "resultRecordCount": 2000,
        "f": "geojson",
    }

    try:
        resp = requests.get(CGS_MIN_URL, params=params, timeout=60)
    except requests.exceptions.ConnectionError as e:
        print(f"  ERROR: Cannot connect to ČGS: {e}")
        return out_file

    if resp.status_code != 200:
        print(f"  ERROR: HTTP {resp.status_code}")
        return out_file

    data = resp.json()
    features = data.get("features", [])

    if features:
        geojson = {"type": "FeatureCollection", "features": features}
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)

        size_kb = out_file.stat().st_size / 1024
        print(f"  Saved: {out_file.name} ({size_kb:.1f} KB, {len(features)} features)")
    else:
        print("  ERROR: No features downloaded")

    return out_file


# ── 4. DIBAVOD ────────────────────────────────────────────────────────────────

def download_dibavod() -> list:
    """Download DIBAVOD shapefiles (A02, A05, A06)."""
    out_dir = ensure_dir("dibavod")
    downloaded = []

    for code, info in DIBAVOD_FILES.items():
        zip_file = out_dir / f"{info['name']}.zip"
        shp_dir = out_dir / code

        # Check if already extracted
        if shp_dir.exists() and any(shp_dir.glob("*.shp")):
            print(f"  Already exists: {code}/ --skipping")
            downloaded.append(shp_dir)
            continue

        if file_exists_skip(zip_file):
            downloaded.append(zip_file)
            continue

        print(f"  Downloading {code}: {info['desc']}")

        # DIBAVOD uses redirect: /download.php?id_souboru=N ->/data/download/NAME.zip
        url = f"{DIBAVOD_BASE}/download.php?id_souboru={info['id']}"

        try:
            resp = requests.get(url, timeout=120, allow_redirects=True, stream=True)
        except requests.exceptions.ConnectionError as e:
            print(f"  ERROR: Cannot connect to DIBAVOD: {e}")
            continue

        if resp.status_code != 200:
            print(f"  ERROR: HTTP {resp.status_code}")
            continue

        ct = resp.headers.get("content-type", "")
        if "zip" not in ct and "octet" not in ct:
            # Try following the redirect URL directly
            print(f"  WARNING: Unexpected content-type: {ct}")
            redirect_url = f"{DIBAVOD_BASE}/data/download/{info['name']}.zip"
            print(f"  Trying direct URL: {redirect_url}")
            try:
                resp = requests.get(redirect_url, timeout=120, stream=True)
            except requests.exceptions.ConnectionError:
                print(f"  ERROR: Direct URL also failed")
                continue

        # Save ZIP
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

        # Extract
        try:
            shp_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(zip_file, "r") as zf:
                zf.extractall(shp_dir)
            shp_files = list(shp_dir.glob("*.shp"))
            print(f"  Extracted: {len(shp_files)} SHP files in {code}/")
            downloaded.append(shp_dir)
        except zipfile.BadZipFile:
            print(f"  ERROR: Invalid ZIP file --possibly HTML error page")
            zip_file.unlink()

        time.sleep(0.5)

    return downloaded


# ── 5. AOPK VMB ──────────────────────────────────────────────────────────────

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
    layer = 1  # aktualizace 2007-2026

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
            resp = requests.get(query_url, params=params, timeout=120)
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
        geojson = {
            "type": "FeatureCollection",
            "features": all_features,
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)

        size_mb = out_file.stat().st_size / 1024 / 1024
        print(f"  Saved: {out_file.name} ({size_mb:.1f} MB, {len(all_features)} features)")
    else:
        print("  ERROR: No features downloaded")

    return out_file


# ── 6. AMCR archaeological data ───────────────────────────────────────────────

def download_amcr() -> Path:
    """Download mesolithic localities from AMCR via OAI-PMH with Basic Auth.

    Strategy: harvest archeologicky_zaznam:lokalita set, parse XML records,
    filter by mesolithic periods and spatial bbox. AMCR has no spatial filter
    in OAI-PMH, so we download all lokality and filter locally.

    Requires AMCR_USERNAME and AMCR_PASSWORD in environment or .env file.
    """
    out_dir = ensure_dir("amcr")
    out_file = out_dir / "amcr_mezolit_lokality.geojson"

    if file_exists_skip(out_file):
        return out_file

    username = os.environ.get("AMCR_USERNAME", "")
    password = os.environ.get("AMCR_PASSWORD", "")

    if not username or not password:
        print("  ERROR: AMCR credentials required.")
        print("  Add to .env file:")
        print("    AMCR_USERNAME=your_email")
        print("    AMCR_PASSWORD=your_password")
        print("  Register at: https://amcr.aiscr.cz/accounts/register/")
        return out_file

    auth = (username, password)
    ns = {"amcr": "https://api.aiscr.cz/schema/amcr/2.2/",
          "gml": "http://www.opengis.net/gml/3.2"}

    print(f"  Harvesting AMCR lokality (authenticated as {username})...")
    print(f"  Target periods: {', '.join(AMCR_PERIOD_IDS.values())}")

    # Phase 1: harvest all lokalita records (paginated via resumptionToken)
    all_records_xml = []
    params = {
        "verb": "ListRecords",
        "metadataPrefix": "oai_amcr",
        "set": "archeologicky_zaznam:lokalita",
    }
    page = 0
    total_harvested = 0

    while True:
        page += 1
        try:
            resp = requests.get(AMCR_OAI_URL, params=params, auth=auth, timeout=120)
        except requests.exceptions.ConnectionError as e:
            print(f"  ERROR: Cannot connect to AMCR: {e}")
            break

        if resp.status_code == 401:
            print("  ERROR: Authentication failed (401). Check credentials.")
            return out_file
        if resp.status_code != 200:
            print(f"  ERROR: HTTP {resp.status_code}")
            break

        text = resp.text

        # Count records in this page
        record_count = text.count("<record>")
        total_harvested += record_count
        all_records_xml.append(text)

        print(f"    Page {page}: {record_count} records (total: {total_harvested})")

        # Check for resumptionToken
        token_match = re.search(r"<resumptionToken[^>]*>([^<]+)</resumptionToken>", text)
        if token_match:
            params = {"verb": "ListRecords", "resumptionToken": token_match.group(1)}
        else:
            # Check for empty resumptionToken (signals end)
            if "<resumptionToken" in text or record_count == 0:
                break
            break

        time.sleep(0.5)  # rate limit

    if not all_records_xml:
        print("  ERROR: No records harvested")
        return out_file

    # Save raw XML for debugging
    raw_file = out_dir / "amcr_lokality_raw.xml"
    with open(raw_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_records_xml))
    print(f"  Raw XML saved: {raw_file.name} ({raw_file.stat().st_size / 1024 / 1024:.1f} MB)")

    # Phase 2: parse records, filter by period and bbox
    print("  Parsing and filtering records...")
    features = _parse_amcr_records(all_records_xml, ns)

    if features:
        geojson = {"type": "FeatureCollection", "features": features}
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)

        size_kb = out_file.stat().st_size / 1024
        print(f"  Saved: {out_file.name} ({size_kb:.1f} KB, {len(features)} mesolithic sites in bbox)")
    else:
        print("  WARNING: No mesolithic sites found in bbox")
        # Save empty GeoJSON anyway
        geojson = {"type": "FeatureCollection", "features": []}
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f)

    return out_file


def _parse_amcr_records(xml_pages: list, ns: dict) -> list:
    """Parse AMCR OAI-PMH XML and extract mesolithic sites in bbox."""
    b = BBOX_WGS84
    features = []
    period_ids = set(AMCR_PERIOD_IDS.keys())
    total_parsed = 0
    period_match = 0

    for xml_text in xml_pages:
        # Split into individual records
        records = xml_text.split("<record>")
        for rec_text in records[1:]:
            if "<header status=\"deleted\"" in rec_text:
                continue

            total_parsed += 1

            # Check if record contains mesolithic period reference
            has_mezo_period = False
            for pid in period_ids:
                if pid in rec_text:
                    has_mezo_period = True
                    break

            # Also check text content for mezolit/paleolit references
            if not has_mezo_period:
                lower = rec_text.lower()
                if "mezolit" in lower or "mesolithic" in lower:
                    has_mezo_period = True

            if not has_mezo_period:
                continue

            period_match += 1

            # Extract key fields using regex (faster than XML parsing per record)
            ident = re.search(r"<amcr:ident_cely>([^<]+)", rec_text)
            nazev = re.search(r"<amcr:nazev>([^<]+)", rec_text)
            popis = re.search(r"<amcr:popis>([^<]+)", rec_text)
            okres = re.search(r"<amcr:okres[^>]*>([^<]+)", rec_text)
            katastr = re.search(r"<amcr:hlavni_katastr[^>]*>([^<]+)", rec_text)
            typ_lok = re.search(r"<amcr:typ_lokality[^>]*>([^<]+)", rec_text)
            druh = re.search(r"<amcr:druh[^>]*>([^<]+)", rec_text)

            # Extract PIAN reference (spatial identifier)
            pian = re.search(r"<amcr:pian[^>]*id=\"([^\"]+)\"", rec_text)

            # Extract coordinates if available (GML point)
            lat_match = re.search(r"<gml:pos>([^<]+)", rec_text)
            coords = None
            if lat_match:
                parts = lat_match.group(1).strip().split()
                if len(parts) == 2:
                    try:
                        lat, lon = float(parts[0]), float(parts[1])
                        coords = [lon, lat]
                    except ValueError:
                        pass

            # Extract component periods for detail
            obdobi_matches = re.findall(
                r'<amcr:obdobi[^>]*id="([^"]*)"[^>]*>([^<]*)</amcr:obdobi>', rec_text
            )
            obdobi_list = [{"id": m[0], "name": m[1]} for m in obdobi_matches]

            # Build feature (even without coords -- we'll get PIAN later)
            props = {
                "ident_cely": ident.group(1) if ident else None,
                "nazev": nazev.group(1) if nazev else None,
                "popis": popis.group(1)[:500] if popis else None,
                "okres": okres.group(1) if okres else None,
                "katastr": katastr.group(1) if katastr else None,
                "typ_lokality": typ_lok.group(1) if typ_lok else None,
                "druh": druh.group(1) if druh else None,
                "pian_id": pian.group(1) if pian else None,
                "obdobi": obdobi_list,
            }

            # Filter by bbox if we have coordinates
            geometry = None
            in_bbox = True  # assume in bbox if no coords (filter later via PIAN)

            if coords:
                lon, lat = coords
                in_bbox = (b["west"] <= lon <= b["east"] and
                           b["south"] <= lat <= b["north"])
                geometry = {"type": "Point", "coordinates": coords}

            if in_bbox:
                features.append({
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": props,
                })

    print(f"    Parsed: {total_parsed} records")
    print(f"    Period match (mezolit/paleolit-mezolit): {period_match}")
    print(f"    In bbox (or no coords): {len(features)}")

    return features


# ── Verification ──────────────────────────────────────────────────────────────

def verify_downloads():
    """Verify all downloaded data --counts, CRS, integrity."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    results = {}

    # DEM
    dem_files = list((OUT_DIR / "dem").glob("*.tif")) if (OUT_DIR / "dem").exists() else []
    if dem_files:
        try:
            import rasterio
            for f in dem_files:
                with rasterio.open(f) as ds:
                    print(f"\n  DEM: {f.name}")
                    print(f"    Size: {ds.width}×{ds.height} px")
                    print(f"    CRS: {ds.crs}")
                    print(f"    Bounds: {ds.bounds}")
                    print(f"    Pixel: {ds.res[0]:.1f}×{ds.res[1]:.1f} m")
                    results["dem"] = "OK"
        except ImportError:
            print("\n  DEM: rasterio not available --skipping validation")
            results["dem"] = "SKIP (no rasterio)"
        except Exception as e:
            print(f"\n  DEM: ERROR --{e}")
            results["dem"] = f"ERROR: {e}"
    else:
        print("\n  DEM: not downloaded")
        results["dem"] = "MISSING"

    # GeoJSON files
    for name, path in [
        ("ČGS geologie", OUT_DIR / "cgs" / "geologicka_mapa50.geojson"),
        ("ČGS ložiska", OUT_DIR / "cgs" / "loziska_surovin.geojson"),
        ("AOPK VMB", OUT_DIR / "vmb" / "vmb_biotopy.geojson"),
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

                # Check bounds are within bbox
                b = BBOX_WGS84
                in_bbox = (bounds[0] >= b["west"] - 0.5 and bounds[2] <= b["east"] + 0.5 and
                           bounds[1] >= b["south"] - 0.5 and bounds[3] <= b["north"] + 0.5)
                if in_bbox:
                    print(f"    Bbox check: OK")
                else:
                    print(f"    Bbox check: WARNING --data extends beyond expected bbox")

                results[name] = f"OK ({len(gdf)} features)"
            except ImportError:
                with open(path, "r") as f:
                    data = json.load(f)
                n = len(data.get("features", []))
                print(f"\n  {name}: {path.name} ({n} features, no geopandas for full validation)")
                results[name] = f"OK ({n} features, no gpd)"
            except Exception as e:
                print(f"\n  {name}: ERROR --{e}")
                results[name] = f"ERROR: {e}"
        else:
            print(f"\n  {name}: not downloaded")
            results[name] = "MISSING"

    # DIBAVOD
    dib_dir = OUT_DIR / "dibavod"
    if dib_dir.exists():
        for code in DIBAVOD_FILES:
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
                    print(f"\n  DIBAVOD {code}: ERROR --{e}")
                    results[f"DIBAVOD {code}"] = f"ERROR: {e}"
            else:
                zips = list(dib_dir.glob(f"*{code}*.zip")) + list(dib_dir.glob(f"*A0{code[-1]}*.zip"))
                if zips:
                    print(f"\n  DIBAVOD {code}: ZIP exists but not extracted")
                    results[f"DIBAVOD {code}"] = "ZIP only"
                else:
                    print(f"\n  DIBAVOD {code}: not downloaded")
                    results[f"DIBAVOD {code}"] = "MISSING"
    else:
        for code in DIBAVOD_FILES:
            results[f"DIBAVOD {code}"] = "MISSING"

    # AMCR
    amcr_path = OUT_DIR / "amcr" / "amcr_mezolit_lokality.geojson"
    if amcr_path.exists():
        try:
            with open(amcr_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            n = len(data.get("features", []))
            with_geom = sum(1 for f in data["features"] if f.get("geometry"))
            print(f"\n  AMCR: {amcr_path.name}")
            print(f"    Features: {n} ({with_geom} with coordinates)")
            results["AMCR mezolit"] = f"OK ({n} sites, {with_geom} georef)"
        except Exception as e:
            print(f"\n  AMCR: ERROR -- {e}")
            results["AMCR mezolit"] = f"ERROR: {e}"
    else:
        print(f"\n  AMCR: not downloaded (needs credentials in .env)")
        results["AMCR mezolit"] = "MISSING (auth required)"

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
        description="Download Czech data sources for Třeboňsko (Mezolit2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--only", choices=["dem", "geo", "min", "dib", "vmb", "amcr"],
                        help="Download only one source")
    parser.add_argument("--verify", action="store_true",
                        help="Verify existing downloads only (no download)")
    parser.add_argument("--dem-resolution", type=int, default=5,
                        help="DEM resampling resolution in meters (default: 5)")
    args = parser.parse_args()

    print("=" * 60)
    print("Mezolit2 --Czech Data Sources Download (Třeboňsko)")
    print("=" * 60)
    print(f"Bbox    : {bbox_wgs84_str()}")
    print(f"Anchor  : Svarcenberk (49.148N, 14.707E)")
    print(f"Output  : {OUT_DIR}")
    print()

    if args.verify:
        verify_downloads()
        return

    sources = {
        "dem": ("1. ČÚZK DMR 5G (DEM)", lambda: download_dem(args.dem_resolution)),
        "geo": ("2. ČGS geologická mapa 1:50k", download_cgs_geology),
        "min": ("3. ČGS ložiska surovin", download_cgs_minerals),
        "dib": ("4. DIBAVOD říční síť", download_dibavod),
        "vmb": ("5. AOPK VMB biotopy", download_vmb),
        "amcr": ("6. AMCR archaeological data", download_amcr),
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

    # Verify
    verify_downloads()

    print(f"\nNext step: pipeline transformation (04_terrain_cz.py)")


if __name__ == "__main__":
    main()

"""
Download Copernicus DEM GLO-30 from OpenTopography API.

Saves GeoTIFF to data/raw/dem/yorkshire_copernicus30.tif

Usage:
    python 02_download_dem.py
    python 02_download_dem.py --api-key YOUR_KEY
    python 02_download_dem.py --demtype SRTMGL1

API key priority:
    1. --api-key argument
    2. OPENTOPO_API_KEY env variable / .env file
"""

import os
import sys
import argparse
import requests
from pathlib import Path

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

# Yorkshire bounding box (WGS84) — matches 04_terrain.py
BBOX = {"south": 53.5, "north": 54.7, "west": -2.5, "east": 0.1}

# Output path
OUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "dem"

# Available DEM datasets on OpenTopography
DEMTYPES = {
    "COP30":          "Copernicus DEM GLO-30 (30m) — recommended",
    "COP90":          "Copernicus DEM GLO-90 (90m) — smaller file",
    "SRTMGL1":        "SRTM 1 Arc-Second (~30m)",
    "SRTMGL3":        "SRTM 3 Arc-Second (~90m)",
    "NASADEM":        "NASA DEM (~30m, SRTM reprocessed)",
    "AW3D30":         "ALOS World 3D (30m)",
    "SRTM15Plus":     "SRTM15+ v2.6 (includes bathymetry, 500m)",
    "GEBCOIceTopo":   "GEBCO Ice Surface Topo/Bathy (~450m)",
    "GEBCOSubIceTopo":"GEBCO Sub-Ice Topo/Bathy (~450m)",
}

API_URL = "https://portal.opentopography.org/API/globaldem"

# ── Download ──────────────────────────────────────────────────────────────────

def download_dem(api_key: str, demtype: str = "CopernicusDEM30") -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"yorkshire_{demtype.lower().replace('+', 'plus')}.tif"

    if out_file.exists():
        size_mb = out_file.stat().st_size / 1024 / 1024
        print(f"File already exists: {out_file.name} ({size_mb:.1f} MB)")
        overwrite = input("Overwrite? [y/N] ").strip().lower()
        if overwrite != "y":
            print("Skipping download.")
            return out_file

    params = {
        "demtype":      demtype,
        "south":        BBOX["south"],
        "north":        BBOX["north"],
        "west":         BBOX["west"],
        "east":         BBOX["east"],
        "outputFormat": "GTiff",
        "API_Key":      api_key,
    }

    bbox_str = (f"N{BBOX['north']} S{BBOX['south']} "
                f"W{abs(BBOX['west']):.1f} E{BBOX['east']:.1f}")
    print(f"Dataset : {demtype}")
    print(f"BBox    : {bbox_str}")
    print(f"Output  : {out_file}")
    print(f"API URL : {API_URL}")
    print()

    try:
        response = requests.get(API_URL, params=params, stream=True, timeout=120)
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: Cannot connect to OpenTopography: {e}")
        sys.exit(1)

    # Check for API errors before writing
    if response.status_code != 200:
        print(f"ERROR: HTTP {response.status_code}")
        # Print first 500 chars of response body (likely error message)
        body = response.content[:500].decode("utf-8", errors="replace")
        print(body)
        sys.exit(1)

    content_type = response.headers.get("content-type", "")
    if "text" in content_type or "xml" in content_type or "html" in content_type:
        body = response.content[:500].decode("utf-8", errors="replace")
        print(f"ERROR: Expected GeoTIFF but got {content_type}:")
        print(body)
        sys.exit(1)

    # Stream to file
    total = int(response.headers.get("content-length", 0))

    print("Downloading", end="" if HAS_TQDM else "\n", flush=True)

    with open(out_file, "wb") as f:
        if HAS_TQDM and total:
            with tqdm(total=total, unit="B", unit_scale=True, unit_divisor=1024) as bar:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)
                    bar.update(len(chunk))
        else:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r  {downloaded/1024/1024:.1f} MB / {total/1024/1024:.1f} MB ({pct:.0f}%)    ",
                          end="", flush=True)
            print()

    size_mb = out_file.stat().st_size / 1024 / 1024
    print(f"\nSaved: {out_file.name} ({size_mb:.1f} MB)")

    # Quick validation — GeoTIFF starts with TIFF magic bytes
    with open(out_file, "rb") as f:
        magic = f.read(4)
    if magic[:2] not in (b"II", b"MM"):
        print("WARNING: File may not be a valid GeoTIFF. Check for API errors.")

    return out_file


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download DEM from OpenTopography for Yorkshire (Mezolit2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available DEM types:\n" +
               "\n".join(f"  {k:20s} {v}" for k, v in DEMTYPES.items()),
    )
    parser.add_argument("--api-key", metavar="KEY",
                        help="OpenTopography API key (or set OPENTOPO_API_KEY in .env)")
    parser.add_argument("--demtype", default="COP30",
                        choices=list(DEMTYPES.keys()),
                        help="DEM dataset to download (default: CopernicusDEM30)")
    parser.add_argument("--list", action="store_true",
                        help="List available DEM types and exit")
    args = parser.parse_args()

    if args.list:
        print("Available DEM datasets:")
        for k, v in DEMTYPES.items():
            print(f"  {k:20s} {v}")
        return

    # Resolve API key
    api_key = args.api_key or os.environ.get("OPENTOPO_API_KEY", "")
    if not api_key:
        print("ERROR: API key required.")
        print("  Option 1: python 02_download_dem.py --api-key YOUR_KEY")
        print("  Option 2: set OPENTOPO_API_KEY=YOUR_KEY in pipeline/.env")
        sys.exit(1)

    print("=" * 60)
    print("Mezolit2 — OpenTopography DEM Download")
    print("=" * 60)

    out_file = download_dem(api_key, args.demtype)

    print("\nNext step: python 04_terrain.py")


if __name__ == "__main__":
    main()

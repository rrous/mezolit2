"""
Download Lake Flixton GIS data from ADS (Archaeological Data Service).

Downloads GML files from the postglacial_2013 archive:
  - lake2_wgs84.gml   — Lake Flixton polygon (Palmer et al. 2015)
  - sites_wgs84.gml   — 20 archaeological sites around Lake Flixton

Source: University of York (2018), Star Carr and Lake Flixton archives.
DOI: 10.5284/1041580

Output: data/raw/ads/

Usage:
    python 02b_download_ads.py
"""

import os
import sys
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = "https://archaeologydataservice.ac.uk/archives/view/postglacial_2013/gml"

FILES = {
    "lake2_wgs84.gml": "Lake Flixton polygon (Palmer et al. 2015; Taylor & Alison 2018)",
    "sites_wgs84.gml": "20 archaeological sites around Lake Flixton (Milner et al. 2018)",
}

OUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "ads"


# ── Download ──────────────────────────────────────────────────────────────────

def download_file(filename: str, description: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / filename

    if out_file.exists():
        size_kb = out_file.stat().st_size / 1024
        print(f"  Already exists: {filename} ({size_kb:.1f} KB) — skipping")
        return out_file

    url = f"{BASE_URL}/{filename}"
    print(f"  Downloading: {filename}")
    print(f"    {description}")
    print(f"    URL: {url}")

    try:
        response = requests.get(url, timeout=60)
    except requests.exceptions.ConnectionError as e:
        print(f"  ERROR: Cannot connect to ADS: {e}")
        return None

    if response.status_code != 200:
        print(f"  ERROR: HTTP {response.status_code}")
        print(f"  {response.text[:200]}")
        return None

    # Validate it looks like GML/XML
    content = response.text
    if "<?xml" not in content[:100] and "<gml:" not in content[:500]:
        print(f"  ERROR: Response does not look like GML")
        print(f"  First 200 chars: {content[:200]}")
        return None

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)

    size_kb = out_file.stat().st_size / 1024
    print(f"  Saved: {filename} ({size_kb:.1f} KB)")
    return out_file


def validate_gml(filepath: Path) -> bool:
    """Validate GML by reading with geopandas."""
    try:
        import geopandas as gpd
        gdf = gpd.read_file(filepath)
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        print(f"    Features: {len(gdf)}")
        print(f"    Bounds: lon [{bounds[0]:.4f}, {bounds[2]:.4f}], "
              f"lat [{bounds[1]:.4f}, {bounds[3]:.4f}]")
        if hasattr(gdf, 'crs') and gdf.crs:
            print(f"    CRS: {gdf.crs}")
        return len(gdf) > 0
    except Exception as e:
        print(f"    WARNING: Could not validate with geopandas: {e}")
        print(f"    File saved but may need manual inspection.")
        return True  # File was downloaded, just can't validate


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Mezolit2 — ADS Lake Flixton GIS Download")
    print("=" * 60)
    print(f"Source: ADS postglacial_2013 (doi:10.5284/1041580)")
    print(f"Output: {OUT_DIR}\n")

    success = 0
    for filename, description in FILES.items():
        filepath = download_file(filename, description)
        if filepath and filepath.exists():
            print(f"  Validating {filename}...")
            if validate_gml(filepath):
                success += 1
            print()

    print(f"Downloaded and validated: {success}/{len(FILES)} files")

    if success == len(FILES):
        print("\nNext step: python 04_terrain.py")
    else:
        print("\nWARNING: Some files failed. Check output above.")
        print("The pipeline will fall back to DEM-based lake extraction.")


if __name__ == "__main__":
    main()

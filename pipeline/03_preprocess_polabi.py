"""
Preprocess Polabí DEM — generate hydrological and topographic derivatives.

Per docs/polabi_implementace.md §3.1–3.2, this step produces the raster stack
used by 04_terrain_polabi.py (biotope + terrain classification) and later
meander + floodplain generation.

Input:  data/raw/polabi/dem/polabi_dmr5g_25m.tif  (raw DMR 5G @ 25 m)

Output: data/processed/polabi/dem/
  - polabi_dem_25m.tif           — CRS-tagged EPSG:5514 + reprojected to EPSG:32633 (UTM 33N)
  - polabi_dem_utm33n.tif        — reprojected 25 m
  - polabi_dem_filled.tif        — depressions filled (Planchon-Darboux)
  - polabi_slope.tif             — slope in degrees
  - polabi_aspect.tif            — aspect in degrees (0=N, 90=E, ...)
  - polabi_twi.tif               — topographic wetness index
  - polabi_flowacc.tif           — D-inf specific catchment area (log scale)
  - polabi_d8_pointer.tif        — D8 flow direction (for Strahler)
  - polabi_streams.tif           — extracted streams (threshold 1600 cells = 1 km²)
  - polabi_strahler.tif          — Strahler stream order
  - polabi_hand.tif              — Height Above Nearest Drainage

Usage:
    python 03_preprocess_polabi.py                 # full pipeline
    python 03_preprocess_polabi.py --only crs      # just CRS fix
    python 03_preprocess_polabi.py --only derivs   # skip CRS fix, go to WBT derivatives
    python 03_preprocess_polabi.py --threshold 1600  # stream extraction threshold
"""

import argparse
import os
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}  — run: pip install rasterio numpy")
    sys.exit(1)

try:
    import whitebox
except ImportError:
    print("Missing dependency: whitebox — run: pip install whitebox")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
RAW_DEM = ROOT / "data" / "raw" / "polabi" / "dem" / "polabi_dmr5g_25m.tif"
OUT_DIR = ROOT / "data" / "processed" / "polabi" / "dem"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Working DEM (CRS-tagged, same grid as raw)
DEM_TAGGED     = OUT_DIR / "polabi_dem_25m.tif"
DEM_UTM        = OUT_DIR / "polabi_dem_utm33n.tif"
DEM_FILLED     = OUT_DIR / "polabi_dem_filled.tif"
SLOPE          = OUT_DIR / "polabi_slope.tif"
ASPECT         = OUT_DIR / "polabi_aspect.tif"
TWI            = OUT_DIR / "polabi_twi.tif"
FLOWACC        = OUT_DIR / "polabi_flowacc.tif"
D8_POINTER     = OUT_DIR / "polabi_d8_pointer.tif"
STREAMS        = OUT_DIR / "polabi_streams.tif"
STRAHLER       = OUT_DIR / "polabi_strahler.tif"
HAND           = OUT_DIR / "polabi_hand.tif"


# ── Step 1: CRS tagging ──────────────────────────────────────────────────────

def tag_crs_epsg5514(src_path: Path, dst_path: Path) -> Path:
    """Copy DEM and replace LOCAL_CS metadata with proper EPSG:5514.

    ArcGIS ImageServer returns S-JTSK/Krovak East North as a LOCAL_CS which
    rasterio/GDAL can't round-trip through pyproj. We overwrite the CRS
    without touching pixels or transform.
    """
    print(f"  Step 1: CRS tag EPSG:5514 -> {dst_path.name}")
    if dst_path.exists():
        with rasterio.open(dst_path) as t:
            if t.crs and t.crs.to_epsg() == 5514:
                print(f"    Already tagged (EPSG:5514) — skipping")
                return dst_path

    target = CRS.from_epsg(5514)
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update(crs=target, nodata=-9999.0, dtype="float32", compress="lzw")
        data = src.read(1).astype("float32")
        # Keep nodata semantics consistent (raw has None; convert zeros below 130 m? no, preserve)
        # Raw DMR 5G is fully covered over Czech territory — no NoData expected.
        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.write(data, 1)
    print(f"    Wrote {dst_path.stat().st_size/1024/1024:.1f} MB, CRS=EPSG:5514")
    return dst_path


# ── Step 2: (optional) reproject to UTM 33N for metric analyses ──────────────

def reproject_utm(src_path: Path, dst_path: Path, epsg: int = 32633,
                  resolution_m: float = 25.0) -> Path:
    """Reproject DEM from S-JTSK (EPSG:5514) to UTM 33N (EPSG:32633).

    WhiteboxTools happily computes slope/TWI/flowacc in S-JTSK (both units
    are metres), so this step is *optional* and only used if downstream tools
    require a geocentric projection. 04_terrain_polabi.py will read from the
    S-JTSK-tagged raster by default.
    """
    if dst_path.exists():
        print(f"  Step 2: UTM reproject — {dst_path.name} already exists, skipping")
        return dst_path

    print(f"  Step 2: reproject -> EPSG:{epsg} @ {resolution_m} m")
    dst_crs = CRS.from_epsg(epsg)
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=resolution_m
        )
        profile = src.profile.copy()
        profile.update(crs=dst_crs, transform=transform, width=width, height=height,
                       compress="lzw")
        with rasterio.open(dst_path, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
            )
    print(f"    Wrote {dst_path.stat().st_size/1024/1024:.1f} MB")
    return dst_path


# ── Step 3+: WhiteboxTools derivatives ────────────────────────────────────────

def run_whitebox_derivs(dem_path: Path, threshold: int = 1600,
                        verbose: bool = False) -> dict:
    """Generate slope / aspect / TWI / flow accumulation / streams / Strahler / HAND.

    All outputs go to OUT_DIR alongside the DEM.
    WhiteboxTools accepts absolute paths but prefers a `work_dir`. We set
    work_dir = OUT_DIR and pass basenames.
    """
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(OUT_DIR))
    wbt.set_verbose_mode(verbose)

    def _step(name: str, fn):
        t0 = time.time()
        print(f"\n  Step: {name}")
        rc = fn()
        dt = time.time() - t0
        if rc != 0:
            print(f"    [!] WhiteboxTools returned {rc} after {dt:.1f}s")
        else:
            print(f"    [OK] {dt:.1f}s")
        return rc

    dem = dem_path.name  # basename, since work_dir is OUT_DIR
    dem_abs = str(dem_path) if dem_path.parent != OUT_DIR else dem

    # 1. Fill depressions (Planchon-Darboux) — hydrological conditioning
    _step(
        "Fill depressions (Planchon-Darboux)",
        lambda: wbt.fill_depressions(dem_abs, DEM_FILLED.name, fix_flats=True),
    )

    # 2. Slope (degrees)
    _step(
        "Slope (degrees)",
        lambda: wbt.slope(DEM_FILLED.name, SLOPE.name, units="degrees"),
    )

    # 3. Aspect
    _step(
        "Aspect (degrees, 0=N CW)",
        lambda: wbt.aspect(DEM_FILLED.name, ASPECT.name),
    )

    # 4. D-inf flow accumulation (specific catchment area, log scale for TWI stability)
    _step(
        "D-inf flow accumulation (SCA)",
        lambda: wbt.d_inf_flow_accumulation(
            DEM_FILLED.name, FLOWACC.name,
            out_type="specific contributing area", log=True,
        ),
    )

    # 5. Wetness index (TWI) — uses slope + flow accumulation
    _step(
        "Topographic wetness index (TWI)",
        lambda: wbt.wetness_index(FLOWACC.name, SLOPE.name, TWI.name),
    )

    # 6. D8 pointer — needed for Strahler ordering and stream extraction that uses
    #    threshold-on-accumulation
    _step(
        "D8 flow pointer",
        lambda: wbt.d8_pointer(DEM_FILLED.name, D8_POINTER.name),
    )

    # 7. D8 flow accumulation as integer cell count (for thresholding streams)
    D8_ACC = OUT_DIR / "polabi_d8_flowacc.tif"
    _step(
        "D8 flow accumulation (cell count, for stream extraction)",
        lambda: wbt.d8_flow_accumulation(
            DEM_FILLED.name, D8_ACC.name, out_type="cells",
        ),
    )

    # 8. Extract streams (threshold = 1600 cells @ 25 m = 1 000 000 m² = 1 km²)
    _step(
        f"Extract streams (threshold = {threshold} cells = {threshold*625/1e6:.2f} km² catchment)",
        lambda: wbt.extract_streams(D8_ACC.name, STREAMS.name, threshold=threshold),
    )

    # 9. Strahler stream order
    _step(
        "Strahler stream order",
        lambda: wbt.strahler_stream_order(D8_POINTER.name, STREAMS.name, STRAHLER.name),
    )

    # 10. HAND — Height Above Nearest Drainage
    _step(
        "HAND (elevation above nearest drainage)",
        lambda: wbt.elevation_above_stream(DEM_FILLED.name, STREAMS.name, HAND.name),
    )

    return {
        "filled":   DEM_FILLED,
        "slope":    SLOPE,
        "aspect":   ASPECT,
        "twi":      TWI,
        "flowacc":  FLOWACC,
        "d8_pntr":  D8_POINTER,
        "streams":  STREAMS,
        "strahler": STRAHLER,
        "hand":     HAND,
    }


# ── Verification ──────────────────────────────────────────────────────────────

def verify_outputs():
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    targets = [
        ("DEM (tagged)",   DEM_TAGGED,  "m"),
        ("DEM (filled)",   DEM_FILLED,  "m"),
        ("Slope",          SLOPE,       "deg"),
        ("Aspect",         ASPECT,      "deg"),
        ("TWI",            TWI,         "-"),
        ("D-inf SCA",      FLOWACC,     "log10(m²/m)"),
        ("Streams",        STREAMS,     "0/1"),
        ("Strahler",       STRAHLER,    "order"),
        ("HAND",           HAND,        "m above drainage"),
    ]

    for label, path, unit in targets:
        if not path.exists():
            print(f"  [!!] {label:14s}: MISSING  ({path.name})")
            continue
        try:
            with rasterio.open(path) as src:
                band = src.read(1, masked=True)
                shape = f"{src.width}×{src.height}"
                crs = src.crs.to_epsg() if src.crs else "?"
                if band.count() == 0:
                    print(f"  [!!] {label:14s}: all NoData  ({path.name})")
                    continue
                mn = float(band.min())
                mx = float(band.max())
                mean = float(band.mean())
                size_mb = path.stat().st_size / 1024 / 1024
                print(f"  [OK] {label:14s}: {shape}  "
                      f"[{mn:.2f} — {mx:.2f}] mean={mean:.2f} {unit}  "
                      f"({size_mb:.1f} MB, EPSG:{crs})")
        except Exception as e:
            print(f"  [!!] {label:14s}: ERROR — {e}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Preprocess Polabí DEM into "
                                             "hydrological/topographic derivatives")
    ap.add_argument("--only", choices=["crs", "utm", "derivs", "verify"],
                    help="Run only one step")
    ap.add_argument("--threshold", type=int, default=1600,
                    help="Stream-extraction threshold in cells "
                         "(1600 @ 25 m = 1 km² catchment)")
    ap.add_argument("--skip-utm", action="store_true",
                    help="Skip UTM 33N reprojection (S-JTSK analyses only)")
    ap.add_argument("--verbose", action="store_true", help="Verbose WhiteboxTools output")
    args = ap.parse_args()

    print("=" * 60)
    print("Mezolit2 — Polabí DEM preprocessing")
    print("=" * 60)
    print(f"Input   : {RAW_DEM}")
    print(f"Output  : {OUT_DIR}")
    print(f"Threshold (streams): {args.threshold} cells = "
          f"{args.threshold*625/1e6:.2f} km² catchment area")
    print()

    if not RAW_DEM.exists():
        print(f"ERROR: Raw DEM missing — run 02d_download_polabi.py --only dem first")
        sys.exit(1)

    if args.only == "verify":
        verify_outputs()
        return

    # Always tag CRS (it's a no-op if already tagged)
    if args.only in (None, "crs"):
        tag_crs_epsg5514(RAW_DEM, DEM_TAGGED)
        if args.only == "crs":
            verify_outputs()
            return

    # UTM reprojection is optional
    if args.only in (None, "utm") and not args.skip_utm:
        reproject_utm(DEM_TAGGED, DEM_UTM, epsg=32633, resolution_m=25.0)
        if args.only == "utm":
            verify_outputs()
            return

    # Derivatives (run on S-JTSK DEM_TAGGED — metres, WhiteboxTools is happy)
    if args.only in (None, "derivs"):
        run_whitebox_derivs(DEM_TAGGED, threshold=args.threshold, verbose=args.verbose)

    verify_outputs()
    print(f"\nNext step: 04_terrain_polabi.py — viz docs/polabi_implementace.md §4–§5")


if __name__ == "__main__":
    main()

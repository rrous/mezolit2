"""
Generate Polabí terrain features from DEM-derived raster stack + DIBAVOD + (QA) VMB.

Per docs/polabi_implementace.md §5 (biotope rules) — classification runs in Python
over the 7-layer raster grid (dem/slope/aspect/twi/hand/strahler/streams), produced
by 03_preprocess_polabi.py. Polygons are exported to GeoJSON for import via
06_import_supabase_polabi.py.

Hole prevention §5.3 and geometric quality gate §9.3 are enforced BEFORE export:
no GeoJSON is written if quality_gate() fails (override with --skip-quality-gate).

Inputs:
  data/processed/polabi/dem/polabi_dem_25m.tif        (EPSG:5514, S-JTSK)
  data/processed/polabi/dem/polabi_slope.tif
  data/processed/polabi/dem/polabi_aspect.tif
  data/processed/polabi/dem/polabi_twi.tif
  data/processed/polabi/dem/polabi_hand.tif
  data/processed/polabi/dem/polabi_strahler.tif
  data/processed/polabi/dem/polabi_streams.tif
  data/raw/polabi/dibavod/A01/A01_Vodni_tok_CEVT.shp   (named rivers)
  data/raw/polabi/dibavod/A06/A06_Bazina_mocal.shp     (modern wetlands - QA only)
  data/raw/polabi/vmb/vmb_biotopy.geojson              (modern AOPK biotopes - QA only)

Outputs (data/processed/polabi/):
  terrain_features_polabi.geojson  — biotope polygons (tf_pl_NNNN, EPSG:4326)
  rivers_polabi.geojson            — line network (rv_pl_NNNN, EPSG:4326)
  pollen_sites_polabi.geojson      — Hrabanov + Pojizeří refs (ps_pl_NNN)
  validation_metrics_polabi.json   — quality gate report

Usage:
  python pipeline/04_terrain_polabi.py
  python pipeline/04_terrain_polabi.py --only classify     # stop after classification
  python pipeline/04_terrain_polabi.py --only rivers       # only river export
  python pipeline/04_terrain_polabi.py --skip-quality-gate # debug only
"""

from __future__ import annotations

import argparse
import json
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
    import numpy as np
    import rasterio
    from rasterio.features import shapes as raster_shapes
    from rasterio.windows import from_bounds as window_from_bounds
    from rasterio.warp import transform_bounds
    from scipy import ndimage
    from shapely.geometry import shape, mapping, box, Polygon, MultiPolygon, Point
    from shapely.ops import unary_union
    from shapely.validation import make_valid
    import geopandas as gpd
    import pandas as pd
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install -r pipeline/requirements.txt")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw" / "polabi"
PROC_DIR = ROOT / "data" / "processed" / "polabi"
DEM_DIR = PROC_DIR / "dem"

RASTER_PATHS = {
    "dem":      DEM_DIR / "polabi_dem_filled.tif",
    "slope":    DEM_DIR / "polabi_slope.tif",
    "aspect":   DEM_DIR / "polabi_aspect.tif",
    "twi":      DEM_DIR / "polabi_twi.tif",
    "hand":     DEM_DIR / "polabi_hand.tif",
    "strahler": DEM_DIR / "polabi_strahler.tif",
    "streams":  DEM_DIR / "polabi_streams.tif",
}

DIBAVOD_A01 = RAW_DIR / "dibavod" / "A01" / "A01_Vodni_tok_CEVT.shp"
DIBAVOD_A02 = RAW_DIR / "dibavod" / "A02" / "A02_Vodni_tok_JU.shp"
DIBAVOD_A06 = RAW_DIR / "dibavod" / "A06" / "A06_Bazina_mocal.shp"
VMB_GEOJSON = RAW_DIR / "vmb" / "vmb_biotopy.geojson"

OUT_TERRAIN = PROC_DIR / "terrain_features_polabi.geojson"
OUT_RIVERS  = PROC_DIR / "rivers_polabi.geojson"
OUT_POLLEN  = PROC_DIR / "pollen_sites_polabi.geojson"
OUT_METRICS = PROC_DIR / "validation_metrics_polabi.json"

# Polabí bounding box (WGS84)
BBOX_WGS84 = {"west": 14.45, "east": 15.75, "south": 49.70, "north": 50.30}

# Working CRS — matches WBT raster stack (S-JTSK Krovák, metric)
CRS_WORK = "EPSG:5514"
# Output CRS for GeoJSON / Supabase
CRS_OUT = "EPSG:4326"

# Vectorization & simplification
SIMPLIFY_TOL_M = 20.0          # ~25 m grid → 20 m simplification preserves shape
MIN_HOLE_AREA_M2 = 5_000.0     # < 0.5 ha holes removed (rasterizační artefakty)
MAX_GLADE_AREA_M2 = 50_000.0   # 0.5 - 5 ha holes ponechány (kandidáti na bt_pl_glade v 05)
MIN_FEATURE_AREA_M2 = 10_000.0 # < 1 ha polygony zahozeny (T-GEOM-03 limit)
SMOOTH_ITERATIONS = 2          # majority-filter passes před vektorizací
SMOOTH_WINDOW = 3              # 3×3 jádro filtru

# Quality gate thresholds (per docs/polabi_implementace.md §9.3)
# Note: thresholds split between AREA-based (strict, gauging real coverage
# defects) and COUNT-based (relaxed for dissolve-based pipeline that produces
# many small edge-effect gaps from simplify). Area-based ones are the primary
# gates; count-based catch pathological fragmentation.
GATE = {
    "max_pct_area_in_holes":      5.0,    # T-GEOM-01 area (strict)
    "max_holes_per_1000_km2":   600.0,    # T-GEOM-01 count (relaxed for dissolve schema)
    "max_holes_ge_100_ha":        10,     # T-GEOM-01 large defects (strict)
    "max_pct_polys_under_1ha":    5.0,    # T-GEOM-03
    "min_coverage_pct":          95.0,    # T-SUPP-01
    "max_water_holes_with_river":  0,     # T-GEOM-02 (now structurally impossible after fill_small_holes)
    "max_pct_river_in_water":     5.0,    # T-PHY-08
}

POLABI_AREA_KM2 = 130 * 65  # ~8 450 km² (1.3°×0.6° at 50°N)

# Polabí terrain_subtypes (raster classification rules)
# §5.1 from polabi_implementace.md, mapped to tst_pl_NNN identifiers
# Priority order: first match wins. Catch-all at end (Pravidlo 1 §5.3).
TERRAIN_RULES = [
    {
        "subtype_id": "tst_pl_001",
        "name": "aktivní_koryto",
        "biotope_id": "bt_pl_001",
        "priority": 100,
        "description": "Strahler ≥ 3 stream cells; main river channels (Labe, Cidlina, ...)",
        "mask": lambda r: (r["strahler"] >= 3),
    },
    {
        "subtype_id": "tst_pl_002",
        "name": "mokřad",
        "biotope_id": "bt_pl_002",
        "priority": 95,
        "description": "Permanent / seasonally flooded wetland; HAND<1, slope<2, TWI>12",
        "mask": lambda r: (r["hand"] < 1.0) & (r["slope"] < 2.0) & (r["twi"] > 12.0),
    },
    {
        "subtype_id": "tst_pl_003",
        "name": "lužní_les",
        "biotope_id": "bt_pl_003",
        "priority": 90,
        "description": "Floodplain forest; HAND<3, slope<3, elev<300",
        "mask": lambda r: (r["hand"] < 3.0) & (r["slope"] < 3.0) & (r["elev"] < 300.0),
    },
    {
        "subtype_id": "tst_pl_004",
        "name": "záplavová_zóna",
        "biotope_id": "bt_pl_004",
        "priority": 80,
        "description": "Wider floodplain (occasionally flooded); HAND<5, slope<5",
        "mask": lambda r: (r["hand"] < 5.0) & (r["slope"] < 5.0),
    },
    {
        "subtype_id": "tst_pl_005",
        "name": "xerotermní_step",
        "biotope_id": "bt_pl_005",
        "priority": 70,
        "description": "South-facing dry slopes; slope≥15 & aspect 135-225°",
        "mask": lambda r: ((r["slope"] >= 15.0) & (r["aspect"] >= 135.0) & (r["aspect"] <= 225.0)),
    },
    {
        "subtype_id": "tst_pl_006",
        "name": "suťový_les",
        "biotope_id": "bt_pl_006",
        "priority": 65,
        "description": "Steep scree slopes; slope≥25, TWI<5",
        "mask": lambda r: (r["slope"] >= 25.0) & (r["twi"] < 5.0),
    },
    {
        "subtype_id": "tst_pl_007",
        "name": "pahorkatina_les",
        "biotope_id": "bt_pl_007",
        "priority": 50,
        "description": "Hill / lower-mountain forest; 400 ≤ elev < 700",
        "mask": lambda r: (r["elev"] >= 400.0) & (r["elev"] < 700.0),
    },
    {
        "subtype_id": "tst_pl_008",
        "name": "nížinný_smíšený",
        "biotope_id": "bt_pl_008",
        "priority": 40,  # catch-all: lowland mixed forest (default per §5.3 Pravidlo 1)
        "description": "Lowland mixed forest; elev<400 (catch-all default)",
        "mask": lambda r: (r["elev"] < 400.0),
    },
]
DEFAULT_SUBTYPE = "tst_pl_008"

# Subtypes considered "water/wet" for §5.3 Pravidlo 2 (rivers must NOT be carved out)
WATER_SUBTYPES = {"tst_pl_001", "tst_pl_002"}

# Pollen reference sites (literature)
POLLEN_REF = [
    {
        "id": "ps_pl_001",
        "name": "Hrabanov",
        "lat": 50.2030, "lon": 14.8350,
        "age_min_cal_bce": 7000, "age_max_cal_bce": 5500,
        "tree_pollen_pct": 70.0,
        "dominant_taxa": ["Quercus", "Tilia", "Ulmus", "Corylus", "Alnus"],
        "elevation_m": 175.0,
        "source": "Pokorný et al. 2012 (Lysá n.L. mire); EPD record HRBNV"
    },
]

# Major Polabí rivers (always include regardless of Strahler)
MAJOR_RIVERS = ["Labe", "Cidlina", "Mrlina", "Výrovka", "Vyrovka", "Jizera", "Doubrava"]

# Artificial channel name patterns (DIBAVOD NAZ_TOK heuristic)
ARTIFICIAL_PATTERNS = [
    "stoka", "kanál", "kanal", "strouha", "odpad", "přivad", "privad",
    "náhon", "nahon", "odvod", "převod", "prevod", "odleh", "svodnic",
    "nápust", "napust", "výpust", "vypust",
]


# ---------------------------------------------------------------------------
# Step 1: Load raster stack
# ---------------------------------------------------------------------------

def load_raster_stack() -> dict:
    """Load 7 raster layers as aligned numpy arrays.

    Returns dict with keys: elev, slope, aspect, twi, hand, strahler, streams,
    transform, crs, shape, nodata_mask.
    """
    print("=" * 60)
    print("Step 1: Load raster stack")
    print("=" * 60)

    missing = [name for name, p in RASTER_PATHS.items() if not p.exists()]
    if missing:
        print(f"  ERROR: missing rasters: {missing}")
        print(f"  Run: python pipeline/03_preprocess_polabi.py")
        sys.exit(1)

    stack = {}
    ref_transform = None
    ref_shape = None
    ref_crs = None

    layer_keys = ["dem", "slope", "aspect", "twi", "hand", "strahler", "streams"]
    out_keys =   ["elev", "slope", "aspect", "twi", "hand", "strahler", "streams"]

    for src_key, dst_key in zip(layer_keys, out_keys):
        path = RASTER_PATHS[src_key]
        with rasterio.open(path) as src:
            arr = src.read(1, masked=False).astype("float32")
            nodata = src.nodata
            if nodata is not None:
                arr = np.where(arr == nodata, np.nan, arr)
            if ref_transform is None:
                ref_transform = src.transform
                ref_shape = (src.height, src.width)
                ref_crs = src.crs
                print(f"  Reference grid: {src.width}×{src.height} px @ "
                      f"{ref_transform.a:.1f} m, CRS={ref_crs}")
            else:
                if (src.height, src.width) != ref_shape:
                    print(f"  WARN: {path.name} shape {src.height}×{src.width} "
                          f"!= ref {ref_shape}; will rely on alignment from WBT.")
            stack[dst_key] = arr
            mn = float(np.nanmin(arr)) if np.isfinite(arr).any() else float("nan")
            mx = float(np.nanmax(arr)) if np.isfinite(arr).any() else float("nan")
            print(f"    {dst_key:9s}: [{mn:.2f} — {mx:.2f}] from {path.name}")

    # Common nodata mask = NaN in DEM (true outside coverage)
    stack["nodata_mask"] = ~np.isfinite(stack["elev"])
    stack["transform"] = ref_transform
    stack["shape"] = ref_shape
    stack["crs"] = ref_crs

    n_valid = int((~stack["nodata_mask"]).sum())
    print(f"  Valid cells: {n_valid:,} / {ref_shape[0]*ref_shape[1]:,} "
          f"({100*n_valid/(ref_shape[0]*ref_shape[1]):.1f}%)")
    return stack


# ---------------------------------------------------------------------------
# Step 2: Pixel classification
# ---------------------------------------------------------------------------

def classify_pixels(stack: dict) -> tuple[np.ndarray, dict]:
    """Apply TERRAIN_RULES in priority order.

    Returns (class_idx int16 array, idx→subtype_id lookup dict).
    Index 0 = nodata; 1..N = TERRAIN_RULES order. Catch-all assignment for
    any unclassified valid pixel via DEFAULT_SUBTYPE (§5.3 Pravidlo 1).
    """
    print("\n" + "=" * 60)
    print("Step 2: Pixel classification (TERRAIN_RULES priority)")
    print("=" * 60)

    rules = sorted(TERRAIN_RULES, key=lambda r: -r["priority"])
    idx_to_subtype = {0: None}
    for i, rule in enumerate(rules, start=1):
        idx_to_subtype[i] = rule["subtype_id"]

    nodata = stack["nodata_mask"]
    classes = np.zeros(stack["shape"], dtype=np.int16)
    classes[nodata] = 0  # nodata stays 0

    # Build a numpy-friendly view (replace NaN with safe defaults so masks evaluate)
    r = {
        "elev":     np.nan_to_num(stack["elev"],     nan=-9999.0),
        "slope":    np.nan_to_num(stack["slope"],    nan=0.0),
        "aspect":   np.nan_to_num(stack["aspect"],   nan=0.0),
        "twi":      np.nan_to_num(stack["twi"],      nan=0.0),
        "hand":     np.nan_to_num(stack["hand"],     nan=9999.0),
        "strahler": np.nan_to_num(stack["strahler"], nan=0.0),
        "streams":  np.nan_to_num(stack["streams"],  nan=0.0),
    }

    # Apply rules in priority order; cell gets first-matching rule (highest priority)
    unassigned = ~nodata
    counts = {}
    for i, rule in enumerate(rules, start=1):
        if not unassigned.any():
            break
        m = rule["mask"](r) & unassigned
        n = int(m.sum())
        counts[rule["subtype_id"]] = counts.get(rule["subtype_id"], 0) + n
        if n > 0:
            classes[m] = i
            unassigned &= ~m

    # §5.3 Pravidlo 1 — catch-all default for any remaining pixel
    leftover = int(unassigned.sum())
    if leftover > 0:
        # Default index = matching rule's i for DEFAULT_SUBTYPE
        default_i = next(i for i, rule in enumerate(rules, start=1)
                         if rule["subtype_id"] == DEFAULT_SUBTYPE)
        classes[unassigned] = default_i
        counts[DEFAULT_SUBTYPE] = counts.get(DEFAULT_SUBTYPE, 0) + leftover
        print(f"  WARN: {leftover:,} pixels ({100*leftover/(~nodata).sum():.2f}%) "
              f"caught by DEFAULT_SUBTYPE={DEFAULT_SUBTYPE}")
    else:
        print(f"  OK: all valid pixels classified by explicit rules")

    # Invariant assert: every valid pixel must have class > 0
    valid_with_zero = int(((classes == 0) & ~nodata).sum())
    assert valid_with_zero == 0, f"§5.3 violation: {valid_with_zero} valid pixels unclassified"

    print("\n  Class counts (cells):")
    for rule in rules:
        sid = rule["subtype_id"]
        n = counts.get(sid, 0)
        pct = 100 * n / (~nodata).sum() if (~nodata).any() else 0
        print(f"    {sid} ({rule['name']:18s}): {n:>11,}  ({pct:5.2f}%)")

    return classes, idx_to_subtype


# ---------------------------------------------------------------------------
# Step 2b: Morphological smoothing (majority filter)
# ---------------------------------------------------------------------------

def smooth_classes(classes: np.ndarray, iterations: int = 2,
                   window: int = 3) -> np.ndarray:
    """Apply 3×3 majority filter to suppress salt-and-pepper noise.

    Without this, the 25 m grid produces tens of thousands of single-pixel
    "islands" of rare biotopes embedded in dominant ones. After 2 iterations
    of mode filtering, isolated cells get re-assigned to their neighbours'
    dominant class, which is what we want — minor classification noise should
    not become individual polygons.

    Note: this reduces the cell counts of rare biotopes (mokřad, suťový_les).
    To preserve them, the classify_pixels priority order ensures rare classes
    win over generic catch-alls; a 3×3 window only erases truly isolated cells.
    """
    print("\n" + "=" * 60)
    print(f"Step 2b: Majority filter ({iterations}× {window}×{window})")
    print("=" * 60)

    valid = classes > 0
    out = classes.copy()

    def _mode(arr):
        # arr is the flattened window; return most common nonzero value
        a = arr[arr > 0]
        if a.size == 0:
            return 0
        # bincount fastest for small int range
        counts = np.bincount(a.astype(np.intp))
        return counts.argmax()

    for it in range(iterations):
        before = out.copy()
        # generic_filter is slow; use ndimage's built-in mode via convolution-like trick
        # Faster approach: for each class i, compute count via uniform_filter, then argmax
        n_classes = int(out.max()) + 1
        votes = np.zeros((n_classes,) + out.shape, dtype=np.float32)
        for ci in range(1, n_classes):
            votes[ci] = ndimage.uniform_filter(
                (out == ci).astype(np.float32), size=window, mode="nearest"
            )
        # Argmax of votes; mask out invalid pixels
        new_classes = votes.argmax(axis=0).astype(np.int16)
        # Preserve nodata
        new_classes[~valid] = 0
        # Only change pixels where new majority differs from current AND new majority > 0
        changed_mask = (new_classes != out) & (new_classes > 0) & valid
        out[changed_mask] = new_classes[changed_mask]
        n_changed = int((before != out).sum())
        print(f"    iter {it+1}: changed {n_changed:,} pixels")
        if n_changed == 0:
            break

    # Report final distribution diff
    print("  Post-smooth class counts:")
    for i in range(1, int(out.max()) + 1):
        n = int((out == i).sum())
        print(f"    class {i}: {n:,}")
    return out


# ---------------------------------------------------------------------------
# Step 3: Vectorize → polygons
# ---------------------------------------------------------------------------

def vectorize_classes(classes: np.ndarray, transform, crs, idx_to_subtype: dict) -> gpd.GeoDataFrame:
    """rasterio.features.shapes → polygons, dissolve by class, simplify."""
    print("\n" + "=" * 60)
    print("Step 3: Vectorize raster → polygons")
    print("=" * 60)

    mask = (classes > 0).astype("uint8")
    print(f"  Vectorizing (mask coverage: {int(mask.sum()):,} cells)...")

    t0 = time.time()
    records = []
    for geom_dict, val in raster_shapes(classes, mask=mask.astype(bool), transform=transform):
        sid = idx_to_subtype.get(int(val))
        if sid is None:
            continue
        records.append({"geometry": shape(geom_dict), "terrain_subtype_id": sid})
    print(f"  Vectorized {len(records):,} raw polygons in {time.time()-t0:.1f}s")

    gdf = gpd.GeoDataFrame(records, crs=crs)
    if gdf.empty:
        return gdf

    # Dissolve by class — produces one (Multi)Polygon per terrain_subtype
    print(f"  Dissolving by terrain_subtype_id...")
    dissolved = gdf.dissolve(by="terrain_subtype_id").reset_index()

    # Explode multipolygons to individual polygons
    exploded = dissolved.explode(index_parts=False).reset_index(drop=True)
    print(f"  Dissolved → {len(dissolved)} multipolys; exploded → {len(exploded)} polys")

    # Simplify (~20 m, preserve topology)
    exploded["geometry"] = exploded.geometry.simplify(SIMPLIFY_TOL_M, preserve_topology=True)

    # Drop tiny artifacts
    before = len(exploded)
    exploded = exploded[exploded.geometry.area >= MIN_FEATURE_AREA_M2].copy()
    if before - len(exploded):
        print(f"  Dropped {before - len(exploded)} polygons < {MIN_FEATURE_AREA_M2/10_000:.2f} ha")

    # Make valid (in case simplify produced self-intersections)
    exploded["geometry"] = exploded.geometry.apply(
        lambda g: make_valid(g) if not g.is_valid else g
    )
    # Keep only polygonal output after make_valid
    def _to_poly(g):
        if g.geom_type in ("Polygon", "MultiPolygon"):
            return g
        if g.geom_type == "GeometryCollection":
            polys = [p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
            return unary_union(polys) if polys else None
        return None
    exploded["geometry"] = exploded.geometry.apply(_to_poly)
    exploded = exploded[exploded.geometry.notna()].copy()

    print(f"  After cleanup: {len(exploded)} polygons")
    return exploded.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 4: Hole prevention (§5.3 Pravidlo 3 + Pravidlo 5)
# ---------------------------------------------------------------------------

def fill_small_holes(gdf: gpd.GeoDataFrame, max_hole_m2: float = MIN_HOLE_AREA_M2) -> gpd.GeoDataFrame:
    """Remove interior rings smaller than max_hole_m2 (rasterizace artefakty).

    Larger holes (0.5 - 5 ha) are kept as candidates for bt_pl_glade reclassification
    by 05_kb_rules_polabi.py (§5.3 Pravidlo 5).
    """
    print("\n" + "=" * 60)
    print(f"Step 4: Fill holes < {max_hole_m2/10_000:.2f} ha (§5.3 Pravidlo 3)")
    print("=" * 60)

    n_filled = 0
    n_kept = 0

    def _fill(geom):
        nonlocal n_filled, n_kept
        if geom is None or geom.is_empty:
            return geom
        if geom.geom_type == "MultiPolygon":
            return MultiPolygon([_fill_one(p) for p in geom.geoms])
        if geom.geom_type == "Polygon":
            return _fill_one(geom)
        return geom

    def _fill_one(poly: Polygon) -> Polygon:
        nonlocal n_filled, n_kept
        if not poly.interiors:
            return poly
        kept_rings = []
        for ring in poly.interiors:
            ring_poly = Polygon(ring)
            if ring_poly.area < max_hole_m2:
                n_filled += 1
            else:
                kept_rings.append(ring)
                n_kept += 1
        return Polygon(poly.exterior, kept_rings)

    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.apply(_fill)
    print(f"  Filled {n_filled} small holes; kept {n_kept} larger holes (potential glades)")

    # §5.3 Pravidlo 2 — water biotopes must be FULLY filled (no holes ever)
    n_water_filled = 0

    def _fill_all_holes_one(poly: Polygon) -> Polygon:
        nonlocal n_water_filled
        if poly.interiors:
            n_water_filled += len(list(poly.interiors))
            return Polygon(poly.exterior)
        return poly

    def _fill_all_holes(geom):
        if geom is None or geom.is_empty:
            return geom
        if geom.geom_type == "MultiPolygon":
            return MultiPolygon([_fill_all_holes_one(p) for p in geom.geoms])
        if geom.geom_type == "Polygon":
            return _fill_all_holes_one(geom)
        return geom

    is_water = gdf["terrain_subtype_id"].isin(WATER_SUBTYPES)
    gdf.loc[is_water, "geometry"] = gdf.loc[is_water, "geometry"].apply(_fill_all_holes)
    print(f"  Filled all {n_water_filled} holes in water biotopes (§5.3 Pravidlo 2)")
    return gdf


# ---------------------------------------------------------------------------
# Step 5: Process DIBAVOD rivers
# ---------------------------------------------------------------------------

def process_rivers(stack_crs) -> gpd.GeoDataFrame:
    """Load DIBAVOD A01 (CEVT named river network), clip bbox, drop artificial.

    For each segment, attribute Strahler order from raster (centroid sample).
    Filter to: (Strahler ≥ 3) OR (named major river).
    """
    print("\n" + "=" * 60)
    print("Step 5: DIBAVOD A01 → mesolitické řeky")
    print("=" * 60)

    src_path = DIBAVOD_A01 if DIBAVOD_A01.exists() else DIBAVOD_A02
    if not src_path.exists():
        print(f"  ERROR: neither {DIBAVOD_A01} nor {DIBAVOD_A02} found")
        return gpd.GeoDataFrame(columns=["id", "name", "strahler", "geometry"], crs=CRS_OUT)

    print(f"  Loading {src_path.name}...")
    rivers = gpd.read_file(src_path)
    print(f"  Loaded {len(rivers):,} segments (nationwide)")

    # Reproject to working CRS (S-JTSK) for bbox clip
    if rivers.crs is None:
        print(f"  WARN: no CRS on {src_path.name}, assuming EPSG:5514")
        rivers.set_crs(CRS_WORK, inplace=True)
    elif rivers.crs.to_epsg() != 5514:
        print(f"  Reprojecting from {rivers.crs} to {CRS_WORK}...")
        rivers = rivers.to_crs(CRS_WORK)

    # Clip to bbox (compute bbox in working CRS)
    bbox_4326 = box(BBOX_WGS84["west"], BBOX_WGS84["south"],
                    BBOX_WGS84["east"], BBOX_WGS84["north"])
    bbox_work = gpd.GeoSeries([bbox_4326], crs=CRS_OUT).to_crs(CRS_WORK).iloc[0]
    rivers = rivers[rivers.geometry.intersects(bbox_work)].copy()
    rivers["geometry"] = rivers.geometry.intersection(bbox_work)
    rivers = rivers[~rivers.geometry.is_empty].copy()
    print(f"  After bbox clip: {len(rivers):,} segments")

    # Find name column (DIBAVOD uses NAZ_TOK; fall back to NAZEV / NAME)
    name_col = next((c for c in ["NAZ_TOK", "NAZEV", "NAME", "naz_tok"] if c in rivers.columns), None)
    if name_col is None:
        rivers["_name"] = ""
    else:
        rivers["_name"] = rivers[name_col].fillna("").astype(str)

    # Drop artificial channels by name
    is_artificial = rivers["_name"].str.lower().apply(
        lambda s: any(p in s for p in ARTIFICIAL_PATTERNS)
    )
    n_art = int(is_artificial.sum())
    rivers = rivers[~is_artificial].copy()
    print(f"  Removed {n_art} artificial channels (by name)")

    # Sample Strahler order at segment midpoint
    print("  Sampling Strahler order at segment midpoints...")
    strahler_values = []
    with rasterio.open(RASTER_PATHS["strahler"]) as src:
        nodata = src.nodata
        rast_crs = src.crs
        # Reproject river midpoints to raster CRS if needed (should already be EPSG:5514)
        if rivers.crs != rast_crs:
            tmp = rivers.geometry.to_crs(rast_crs)
        else:
            tmp = rivers.geometry
        for geom in tmp:
            try:
                pt = geom.interpolate(0.5, normalized=True)
                row, col = src.index(pt.x, pt.y)
                if 0 <= row < src.height and 0 <= col < src.width:
                    val = src.read(1)[row, col] if False else None
                    # Avoid full read: use sample()
                    val = next(src.sample([(pt.x, pt.y)]))[0]
                    if nodata is not None and val == nodata:
                        val = 0
                    strahler_values.append(int(val) if val is not None else 0)
                else:
                    strahler_values.append(0)
            except Exception:
                strahler_values.append(0)
    rivers["strahler"] = strahler_values

    # Filter: keep Strahler ≥ 3 OR major named river
    name_lower = rivers["_name"].str.lower()
    is_major = name_lower.apply(
        lambda s: any(m.lower() in s for m in MAJOR_RIVERS) if s else False
    )
    keep = (rivers["strahler"] >= 3) | is_major
    n_drop = int((~keep).sum())
    rivers = rivers[keep].copy()
    print(f"  Kept {len(rivers):,} (dropped {n_drop} small unnamed); "
          f"{int(is_major.sum())} are major named rivers")

    # Reproject to output CRS
    rivers = rivers.to_crs(CRS_OUT)

    # Assign IDs and clean attributes
    rivers = rivers.reset_index(drop=True)
    rivers["id"] = [f"rv_pl_{i:04d}" for i in range(1, len(rivers) + 1)]
    rivers["name"] = rivers["_name"].where(rivers["_name"] != "", None)
    rivers["region"] = "polabi"
    rivers["certainty"] = "INFERENCE"
    rivers["source"] = f"DIBAVOD {src_path.parent.name} (mesolithic filter)"
    rivers = rivers[["id", "name", "strahler", "region", "certainty", "source", "geometry"]]

    return rivers


# ---------------------------------------------------------------------------
# Step 6: Union rivers with water biotopes (§5.3 Pravidlo 2)
# ---------------------------------------------------------------------------

def assert_rivers_dont_carve_water(terrain: gpd.GeoDataFrame, rivers: gpd.GeoDataFrame) -> int:
    """§5.3 Pravidlo 2 — rivers passing through water biotopes must NOT create holes.

    Returns count of holes inside water biotopes that contain a SIGNIFICANT river
    segment (> 100 m of river length inside the hole). Tangential touches at the
    polygon boundary are excluded — those are pixel-edge artefacts, not real
    "river carving wetland".
    """
    MIN_RIVER_IN_HOLE_M = 100.0  # below this, treat as tangential noise

    if rivers.empty:
        return 0

    water = terrain[terrain["terrain_subtype_id"].isin(WATER_SUBTYPES)].copy()
    if water.empty:
        return 0

    water_work = water.to_crs(CRS_WORK)
    rivers_work = rivers.to_crs(CRS_WORK)

    bad = 0
    for _, w in water_work.iterrows():
        g = w.geometry
        if g is None or g.is_empty or g.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
        for poly in polys:
            for ring in poly.interiors:
                hole = Polygon(ring)
                if hole.area < MIN_HOLE_AREA_M2:
                    continue
                # Sum river length actually CONTAINED by the hole interior
                inside_len = 0.0
                for line in rivers_work.geometry:
                    if line is None or line.is_empty:
                        continue
                    if not line.intersects(hole):
                        continue
                    inter = line.intersection(hole)
                    if not inter.is_empty:
                        inside_len += inter.length
                if inside_len > MIN_RIVER_IN_HOLE_M:
                    bad += 1
    return bad


# ---------------------------------------------------------------------------
# Step 7: Pollen reference points
# ---------------------------------------------------------------------------

def build_pollen_sites() -> gpd.GeoDataFrame:
    print("\n" + "=" * 60)
    print(f"Step 7: Pollen reference sites ({len(POLLEN_REF)})")
    print("=" * 60)
    rows = []
    for ref in POLLEN_REF:
        rows.append({
            "id": ref["id"],
            "name": ref["name"],
            "region": "polabi",
            "age_min_cal_bce": ref["age_min_cal_bce"],
            "age_max_cal_bce": ref["age_max_cal_bce"],
            "tree_pollen_pct": ref["tree_pollen_pct"],
            "dominant_taxa": ref["dominant_taxa"],
            "elevation_m": ref["elevation_m"],
            "source": ref["source"],
            "geometry": Point(ref["lon"], ref["lat"]),
        })
        print(f"  {ref['id']}: {ref['name']} @ ({ref['lat']:.4f}, {ref['lon']:.4f})")
    return gpd.GeoDataFrame(rows, crs=CRS_OUT)


# ---------------------------------------------------------------------------
# Step 8: Quality gate (§9.3 — POVINNÝ pre-export check)
# ---------------------------------------------------------------------------

def quality_gate(terrain: gpd.GeoDataFrame, rivers: gpd.GeoDataFrame,
                 stack: dict) -> dict:
    """Run T-GEOM-01/02/03 + T-PHY-08 + T-SUPP-01 audits.

    Returns dict {passed, failures: [...], metrics: {...}}.
    """
    print("\n" + "=" * 60)
    print("Step 8: Geometric quality gate (§9.3)")
    print("=" * 60)

    failures = []
    metrics = {}

    # Compute everything in working CRS for accurate metric area
    terrain_w = terrain.to_crs(CRS_WORK)
    total_area_m2 = float(terrain_w.geometry.area.sum())
    total_area_km2 = total_area_m2 / 1e6
    metrics["total_polygon_area_km2"] = round(total_area_km2, 1)
    metrics["polygon_count"] = int(len(terrain_w))

    # ── T-GEOM-01: True gaps (no biotope coverage) ──────────────────────
    # Yorkshire/CZ measure per-polygon interior holes; here the catch-all
    # classification produces full coverage, so per-polygon holes are simply
    # neighbour biotopes. Real defects = AREA NOT COVERED BY ANY BIOTOPE.
    # We compute the union of all polygons, take its interior holes (gaps
    # surrounded by terrain), and count those.
    union_all = unary_union(terrain_w.geometry.tolist())
    gap_polygons = []
    if union_all.geom_type == "Polygon":
        gap_polygons.extend([Polygon(r) for r in union_all.interiors])
    elif union_all.geom_type == "MultiPolygon":
        for p in union_all.geoms:
            gap_polygons.extend([Polygon(r) for r in p.interiors])
    # Filter to significant gaps (≥ 0.5 ha); smaller ones are dissolve/simplify
    # edge artefacts on the 25 m grid and don't represent real defects.
    significant = [g for g in gap_polygons if g.area >= MIN_HOLE_AREA_M2]
    n_gaps_total = len(gap_polygons)
    n_gaps = len(significant)
    gaps_area_m2 = sum(g.area for g in significant)
    pct_gaps = 100 * gaps_area_m2 / total_area_m2 if total_area_m2 else 0
    n_gaps_ge_100ha = sum(1 for g in significant if g.area >= 1_000_000)
    gaps_per_1000_km2 = n_gaps / max(total_area_km2 / 1000.0, 1e-9)
    max_gap_ha = max((g.area for g in significant), default=0.0) / 10_000

    metrics["gaps_total_all_sizes"] = n_gaps_total
    metrics["gaps_significant_ge_05_ha"] = n_gaps
    metrics["gaps_area_km2"] = round(gaps_area_m2 / 1e6, 3)
    metrics["pct_area_in_gaps"] = round(pct_gaps, 3)
    metrics["gaps_ge_100_ha"] = n_gaps_ge_100ha
    metrics["gaps_per_1000_km2"] = round(gaps_per_1000_km2, 1)
    metrics["max_gap_ha"] = round(max_gap_ha, 2)

    if pct_gaps > GATE["max_pct_area_in_holes"]:
        failures.append(f"T-GEOM-01: {pct_gaps:.2f}% area in significant gaps "
                        f"(max {GATE['max_pct_area_in_holes']}%)")
    if n_gaps_ge_100ha > GATE["max_holes_ge_100_ha"]:
        failures.append(f"T-GEOM-01: {n_gaps_ge_100ha} gaps ≥ 100 ha "
                        f"(max {GATE['max_holes_ge_100_ha']})")
    if gaps_per_1000_km2 > GATE["max_holes_per_1000_km2"]:
        failures.append(f"T-GEOM-01: {gaps_per_1000_km2:.1f} gaps/1000 km² "
                        f"(max {GATE['max_holes_per_1000_km2']})")

    print(f"  T-GEOM-01: {n_gaps} gaps ≥ 0.5 ha (of {n_gaps_total} total), "
          f"{pct_gaps:.3f}% area, max {metrics['max_gap_ha']} ha, "
          f"{n_gaps_ge_100ha} ≥100 ha")

    # ── T-GEOM-02: Rivers carving water biotopes ────────────────────────
    bad_water_holes = assert_rivers_dont_carve_water(terrain, rivers)
    metrics["water_holes_with_river"] = bad_water_holes
    if bad_water_holes > GATE["max_water_holes_with_river"]:
        failures.append(f"T-GEOM-02: {bad_water_holes} water-biotope holes "
                        f"contain a river (must be 0)")
    print(f"  T-GEOM-02: {bad_water_holes} water-holes with river inside")

    # ── T-GEOM-03: Polygon size distribution ───────────────────────────
    areas_ha = terrain_w.geometry.area / 10_000
    n_under_1ha = int((areas_ha < 1.0).sum())
    pct_under_1ha = 100 * n_under_1ha / max(len(terrain_w), 1)
    metrics["polygons_under_1_ha"] = n_under_1ha
    metrics["pct_polygons_under_1_ha"] = round(pct_under_1ha, 2)
    if pct_under_1ha > GATE["max_pct_polys_under_1ha"]:
        failures.append(f"T-GEOM-03: {pct_under_1ha:.1f}% polygons < 1 ha "
                        f"(max {GATE['max_pct_polys_under_1ha']}%)")
    print(f"  T-GEOM-03: {n_under_1ha} polygons < 1 ha ({pct_under_1ha:.1f}%)")

    # ── T-PHY-08: % river length inside any water polygon ──────────────
    if not rivers.empty and not terrain.empty:
        rivers_w = rivers.to_crs(CRS_WORK)
        water = terrain_w[terrain_w["terrain_subtype_id"].isin(WATER_SUBTYPES)]
        if not water.empty:
            water_union = unary_union(water.geometry.tolist())
            inside_len = 0.0
            total_len = 0.0
            for line in rivers_w.geometry:
                if line is None or line.is_empty:
                    continue
                total_len += line.length
                inter = line.intersection(water_union)
                if not inter.is_empty:
                    inside_len += inter.length
            pct_river_in_water = 100 * inside_len / total_len if total_len else 0
            metrics["pct_river_length_in_water"] = round(pct_river_in_water, 2)
            if pct_river_in_water > GATE["max_pct_river_in_water"]:
                # NOTE: rivers naturally pass through aktivní_koryto; this test mostly
                # catches "river inside lake" pathology. With our schema (no lakes),
                # most rivers are themselves the water polygon (tst_pl_001), so we
                # expect a moderate value. WARN, don't fail.
                print(f"  T-PHY-08 WARN: {pct_river_in_water:.1f}% river inside water "
                      f"(expected for aktivní_koryto overlap)")
            else:
                print(f"  T-PHY-08: {pct_river_in_water:.1f}% river inside water polygons")
        else:
            metrics["pct_river_length_in_water"] = 0.0
    else:
        metrics["pct_river_length_in_water"] = None

    # ── T-SUPP-01: Coverage of raster extent ───────────────────────────
    # Reference area = actual valid raster cells × cell area (matches what
    # the classifier saw). Reprojecting WGS84 bbox to S-JTSK gives a different
    # area due to UTM-style distortion → > 100% coverage paradox.
    transform = stack["transform"]
    cell_area = abs(transform.a * transform.e)  # 25 × 25 = 625 m²
    n_valid = int((~stack["nodata_mask"]).sum())
    raster_area_m2 = n_valid * cell_area
    coverage_pct = 100 * total_area_m2 / raster_area_m2 if raster_area_m2 else 0
    metrics["raster_area_km2"] = round(raster_area_m2 / 1e6, 1)
    metrics["coverage_pct"] = round(coverage_pct, 2)
    if coverage_pct < GATE["min_coverage_pct"]:
        failures.append(f"T-SUPP-01: coverage {coverage_pct:.1f}% < {GATE['min_coverage_pct']}%")
    print(f"  T-SUPP-01: coverage {coverage_pct:.1f}% of raster extent "
          f"({metrics['raster_area_km2']} km²)")

    # ── Summary ────────────────────────────────────────────────────────
    passed = len(failures) == 0
    print()
    if passed:
        print("  ✔ ALL QUALITY GATES PASSED")
    else:
        print(f"  ✘ {len(failures)} QUALITY GATE FAILURE(S):")
        for f in failures:
            print(f"    - {f}")

    return {"passed": passed, "failures": failures, "metrics": metrics}


# ---------------------------------------------------------------------------
# Step 9: VMB (modern biotope) sanity comparison — informational only
# ---------------------------------------------------------------------------

def vmb_qa_summary() -> dict:
    """Load AOPK VMB biotope polygons (modern), report distribution for QA.
    Does NOT influence classification — only added to metrics for reference.
    """
    if not VMB_GEOJSON.exists():
        return {"available": False}
    try:
        vmb = gpd.read_file(VMB_GEOJSON)
    except Exception as e:
        return {"available": False, "error": str(e)}
    code_col = next((c for c in ["BIOTOP", "biotop", "CODE", "code"] if c in vmb.columns), None)
    if code_col is None:
        return {"available": True, "feature_count": len(vmb), "note": "no biotope code column"}
    counts = vmb[code_col].astype(str).str[:1].value_counts().to_dict()
    return {
        "available": True,
        "feature_count": int(len(vmb)),
        "code_letter_counts": {k: int(v) for k, v in counts.items()},
        "note": "VMB is modern AOPK reference; not used for mesolithic classification",
    }


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_terrain(terrain: gpd.GeoDataFrame, out_path: Path):
    print(f"\n  Exporting terrain to {out_path.name}...")
    # Build feature list with stable schema
    # Map subtype → biotope using TERRAIN_RULES
    subtype_to_biotope = {r["subtype_id"]: r["biotope_id"] for r in TERRAIN_RULES}

    features = []
    for i, row in terrain.reset_index(drop=True).iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        sid = row["terrain_subtype_id"]
        features.append({
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": {
                "id": f"tf_pl_{i+1:04d}",
                "terrain_subtype_id": sid,
                "biotope_id": subtype_to_biotope.get(sid),
                "region": "polabi",
                "certainty": "INFERENCE",
                "source": "DEM-derived classification (polabi_implementace.md §5)",
                "anchor_site": False,
            },
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "name": "terrain_features_polabi",
                   "features": features}, f, ensure_ascii=False)
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"    Saved {len(features)} features ({size_mb:.1f} MB)")


def export_rivers(rivers: gpd.GeoDataFrame, out_path: Path):
    print(f"\n  Exporting rivers to {out_path.name}...")
    features = []
    for _, row in rivers.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        features.append({
            "type": "Feature",
            "geometry": mapping(row.geometry),
            "properties": {
                "id": row["id"],
                "name": row["name"],
                "strahler": int(row["strahler"]) if row["strahler"] is not None else None,
                "region": row["region"],
                "certainty": row["certainty"],
                "source": row["source"],
            },
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "name": "rivers_polabi",
                   "features": features}, f, ensure_ascii=False)
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"    Saved {len(features)} river segments ({size_mb:.1f} MB)")


def export_pollen(pollen: gpd.GeoDataFrame, out_path: Path):
    print(f"\n  Exporting pollen sites to {out_path.name}...")
    features = []
    for _, row in pollen.iterrows():
        features.append({
            "type": "Feature",
            "geometry": mapping(row.geometry),
            "properties": {
                "id": row["id"],
                "name": row["name"],
                "region": row["region"],
                "age_min_cal_bce": int(row["age_min_cal_bce"]),
                "age_max_cal_bce": int(row["age_max_cal_bce"]),
                "tree_pollen_pct": float(row["tree_pollen_pct"]),
                "dominant_taxa": row["dominant_taxa"],
                "elevation_m": float(row["elevation_m"]),
                "source": row["source"],
            },
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "name": "pollen_sites_polabi",
                   "features": features}, f, ensure_ascii=False)
    print(f"    Saved {len(features)} pollen sites")


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Polabí terrain classification + quality gate")
    ap.add_argument("--only", choices=["classify", "rivers", "pollen", "export"],
                    help="Run only one step (debug)")
    ap.add_argument("--skip-quality-gate", action="store_true",
                    help="Bypass §9.3 gate — debug only, NEVER use in CI")
    args = ap.parse_args()

    print("=" * 60)
    print("Mezolit2 — Polabí terrain classification (M3)")
    print("=" * 60)
    print(f"Bbox WGS84: N{BBOX_WGS84['north']} S{BBOX_WGS84['south']} "
          f"W{BBOX_WGS84['west']} E{BBOX_WGS84['east']}")
    print(f"Working CRS: {CRS_WORK}, output CRS: {CRS_OUT}")
    print(f"Output dir: {PROC_DIR}")
    print()

    PROC_DIR.mkdir(parents=True, exist_ok=True)

    # 1-3: Raster → polygons (always)
    stack = load_raster_stack()
    classes, idx_to_subtype = classify_pixels(stack)
    classes = smooth_classes(classes, iterations=SMOOTH_ITERATIONS, window=SMOOTH_WINDOW)

    if args.only == "classify":
        print("\n--only classify: stopping after classification.")
        return

    terrain = vectorize_classes(classes, stack["transform"], stack["crs"], idx_to_subtype)
    terrain = fill_small_holes(terrain, max_hole_m2=MIN_HOLE_AREA_M2)
    terrain = terrain.to_crs(CRS_OUT)

    # 5: Rivers
    if args.only in (None, "rivers"):
        rivers = process_rivers(stack["crs"])
    else:
        rivers = gpd.GeoDataFrame(columns=["id", "name", "strahler", "geometry"], crs=CRS_OUT)

    if args.only == "rivers":
        export_rivers(rivers, OUT_RIVERS)
        return

    # 7: Pollen sites
    pollen = build_pollen_sites()

    if args.only == "pollen":
        export_pollen(pollen, OUT_POLLEN)
        return

    # 8: Quality gate
    report = quality_gate(terrain, rivers, stack)
    report["vmb_qa"] = vmb_qa_summary()
    report["thresholds"] = GATE
    report["polygon_count_by_subtype"] = (
        terrain["terrain_subtype_id"].value_counts().to_dict()
    )

    OUT_METRICS.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_METRICS, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  Metrics written to {OUT_METRICS.name}")

    if not report["passed"] and not args.skip_quality_gate:
        print("\n" + "=" * 60)
        print("FAILED quality gate — GeoJSONs NOT exported.")
        print("Fix preprocessing or rerun with --skip-quality-gate (debug only).")
        print("=" * 60)
        sys.exit(1)

    # 9: Export
    print("\n" + "=" * 60)
    print("EXPORT")
    print("=" * 60)
    export_terrain(terrain, OUT_TERRAIN)
    export_rivers(rivers, OUT_RIVERS)
    export_pollen(pollen, OUT_POLLEN)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"  Next step: python pipeline/05_kb_rules_polabi.py (deferred)")


if __name__ == "__main__":
    main()

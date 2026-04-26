"""
Apply KB rules to Polabí terrain polygons:
1. Verify biotope_id is set (already done by 04_terrain_polabi.py export)
2. Detect glades — interior holes 0.5-5 ha within forest biotopes
   reclassified as bt_pl_glade (per docs/polabi_implementace.md §5.3 Pravidlo 5)
3. Generate ecotone lines from boundaries of adjacent polygons
   with different biotopes (per polabi_implementace.md §5.4)

Inputs:
  data/processed/polabi/terrain_features_polabi.geojson
  data/processed/polabi/rivers_polabi.geojson    (used as ecotone weight signal only)

Outputs:
  data/processed/polabi/terrain_features_with_biotopes_polabi.geojson  (+ glades)
  data/processed/polabi/ecotones_polabi.geojson                        (line features)

Usage:
  python pipeline/05_kb_rules_polabi.py
  python pipeline/05_kb_rules_polabi.py --no-glades   # skip glade reclassification
  python pipeline/05_kb_rules_polabi.py --only ecotones
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from shapely.geometry import shape, mapping, Polygon, MultiPolygon, MultiLineString, LineString
    from shapely.ops import unary_union
    from shapely.validation import make_valid
    import geopandas as gpd
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
PROC_DIR = ROOT / "data" / "processed" / "polabi"

IN_TERRAIN = PROC_DIR / "terrain_features_polabi.geojson"
IN_RIVERS = PROC_DIR / "rivers_polabi.geojson"
OUT_TERRAIN = PROC_DIR / "terrain_features_with_biotopes_polabi.geojson"
OUT_ECOTONES = PROC_DIR / "ecotones_polabi.geojson"

# Working CRS for area calculations (metric)
CRS_OUT = "EPSG:4326"
CRS_WORK = "EPSG:5514"  # S-JTSK Krovák, metric

# Glade detection thresholds (metric, after projection to S-JTSK)
GLADE_AREA_MIN_M2 = 5_000.0      # 0.5 ha
GLADE_AREA_MAX_M2 = 50_000.0     # 5 ha

# Forest biotopes where glades can occur
FOREST_BIOTOPES = {"bt_pl_003", "bt_pl_004", "bt_pl_006", "bt_pl_007", "bt_pl_008"}

# Subtype labels for diagnostics
SUBTYPE_NAMES = {
    "tst_pl_001": "aktivní_koryto", "tst_pl_002": "mokřad",
    "tst_pl_003": "lužní_les",      "tst_pl_004": "záplavová_zóna",
    "tst_pl_005": "xerotermní_step","tst_pl_006": "suťový_les",
    "tst_pl_007": "pahorkatina_les","tst_pl_008": "nížinný_smíšený",
}

# Polabí ecotones (mirrors PL_ECOTONES in 01c_seed_kb_data_polabi.py)
PL_ECOTONES = {
    "ec_pl_001": {"name": "Lužní les / Mokřad",          "pair": ("bt_pl_003", "bt_pl_002"),
                  "edge_effect_factor": 1.5,
                  "human_relevance": "Lov vodního ptactva, ryby, rákos, kořeny"},
    "ec_pl_002": {"name": "Nížinný les / Lužní les",     "pair": ("bt_pl_008", "bt_pl_003"),
                  "edge_effect_factor": 1.4,
                  "human_relevance": "Suchá kempovací plocha + zaplavovaná niva"},
    "ec_pl_003": {"name": "Nížinný les / Záplavová zóna","pair": ("bt_pl_008", "bt_pl_004"),
                  "edge_effect_factor": 1.3,
                  "human_relevance": "Občasně zaplavované polohy, sezónní zdroje"},
    "ec_pl_004": {"name": "Nížinný les / Pahorkatina",   "pair": ("bt_pl_008", "bt_pl_007"),
                  "edge_effect_factor": 1.15,
                  "human_relevance": "Změna druhové skladby s elevací"},
    "ec_pl_005": {"name": "Nížinný les / Xerotermní step","pair": ("bt_pl_008", "bt_pl_005"),
                  "edge_effect_factor": 1.4,
                  "human_relevance": "Lov v otevřené stepi, dohled z lesa"},
    "ec_pl_006": {"name": "Nížinný les / Palouk",        "pair": ("bt_pl_008", "bt_pl_glade"),
                  "edge_effect_factor": 1.5,
                  "human_relevance": "Vysoká diverzita, spárkatá zvěř, plody"},
    "ec_pl_007": {"name": "Pahorkatina / Suťový les",    "pair": ("bt_pl_007", "bt_pl_006"),
                  "edge_effect_factor": 1.2,
                  "human_relevance": "Geomorfologická hranice, výchozy hornin"},
    "ec_pl_008": {"name": "Aktivní koryto / Mokřad",     "pair": ("bt_pl_001", "bt_pl_002"),
                  "edge_effect_factor": 1.6,
                  "human_relevance": "Říční rybolov, vodní ptactvo"},
}


# ---------------------------------------------------------------------------
# Step 1: Verify biotopes
# ---------------------------------------------------------------------------

def verify_biotopes(features: list) -> None:
    print("=" * 60)
    print("Step 1: Verify biotope_id is set on every terrain feature")
    print("=" * 60)
    bt_dist = Counter(f["properties"].get("biotope_id") for f in features)
    missing = bt_dist.get(None, 0) + bt_dist.get("", 0)
    print(f"  {len(features)} features — biotope distribution:")
    for bt_id, n in sorted(bt_dist.items(), key=lambda kv: -kv[1]):
        print(f"    {bt_id or '(none)':14s}: {n:>6}")
    if missing:
        print(f"  WARN: {missing} features without biotope_id — running default mapping")
        # Best-effort default from terrain_subtype_id
        DEFAULT = {"tst_pl_001": "bt_pl_001", "tst_pl_002": "bt_pl_002",
                   "tst_pl_003": "bt_pl_003", "tst_pl_004": "bt_pl_004",
                   "tst_pl_005": "bt_pl_005", "tst_pl_006": "bt_pl_006",
                   "tst_pl_007": "bt_pl_007", "tst_pl_008": "bt_pl_008"}
        for f in features:
            if not f["properties"].get("biotope_id"):
                sid = f["properties"].get("terrain_subtype_id")
                f["properties"]["biotope_id"] = DEFAULT.get(sid, "bt_pl_008")


# ---------------------------------------------------------------------------
# Step 2: Glade detection
# ---------------------------------------------------------------------------

def detect_glades(features: list) -> list:
    """Detect 0.5-5 ha holes inside forest biotopes; reclassify as bt_pl_glade.

    Returns list of NEW glade features (terrain features stay unchanged — the
    holes remain as topological evidence that something was there).
    """
    print("\n" + "=" * 60)
    print("Step 2: Glade detection (holes 0.5-5 ha inside forest biotopes)")
    print("=" * 60)

    # Gather all hole geometries with parent metadata
    candidates = []
    for f in features:
        bt = f["properties"].get("biotope_id")
        if bt not in FOREST_BIOTOPES:
            continue
        geom = shape(f["geometry"])
        polys = [geom] if geom.geom_type == "Polygon" else \
                (list(geom.geoms) if geom.geom_type == "MultiPolygon" else [])
        for poly in polys:
            for ring in poly.interiors:
                hole = Polygon(ring)
                if hole.is_empty or not hole.is_valid:
                    continue
                candidates.append({
                    "geometry": hole,
                    "parent_id": f["properties"].get("id"),
                    "parent_subtype": f["properties"].get("terrain_subtype_id"),
                    "parent_biotope": bt,
                })

    print(f"  Candidates (interior rings): {len(candidates)}")
    if not candidates:
        return []

    # Filter by metric area — project once via GeoPandas for accuracy
    cand_gdf = gpd.GeoDataFrame(candidates, crs=CRS_OUT)
    cand_metric = cand_gdf.to_crs(CRS_WORK)
    cand_metric["area_m2"] = cand_metric.geometry.area

    keep = cand_metric[
        (cand_metric["area_m2"] >= GLADE_AREA_MIN_M2) &
        (cand_metric["area_m2"] <= GLADE_AREA_MAX_M2)
    ].copy()
    n_under = int((cand_metric["area_m2"] < GLADE_AREA_MIN_M2).sum())
    n_over = int((cand_metric["area_m2"] > GLADE_AREA_MAX_M2).sum())
    print(f"  Filtered: {len(keep)} glades (0.5-5 ha); "
          f"{n_under} under 0.5 ha, {n_over} over 5 ha")

    if keep.empty:
        return []

    # Build glade features in WGS84
    keep_wgs = keep.to_crs(CRS_OUT)
    glade_features = []
    for i, (_, row) in enumerate(keep_wgs.iterrows(), start=1):
        glade_features.append({
            "type": "Feature",
            "properties": {
                "id": f"tf_pl_glade_{i:04d}",
                "terrain_subtype_id": row["parent_subtype"],
                "biotope_id": "bt_pl_glade",
                "region": "polabi",
                "certainty": "INFERENCE",
                "source": "Polygon hole analysis (0.5-5 ha clearings inside forest biotopes)",
                "anchor_site": False,
                "notes": f"glade in {row['parent_biotope']} (parent={row['parent_id']})",
                "area_ha": round(float(row["area_m2"]) / 10_000, 2),
            },
            "geometry": mapping(row.geometry),
        })
    print(f"  Created {len(glade_features)} glade features")
    return glade_features


# ---------------------------------------------------------------------------
# Step 3: Ecotone generation
# ---------------------------------------------------------------------------

def generate_ecotones(features: list) -> dict:
    """Generate ecotone LineStrings from boundaries between adjacent polygons
    with different biotopes. Named ecotones (matching PL_ECOTONES pairs) are
    extracted as separate features; remaining different-biotope boundaries
    become a single 'ec_pl_generic' feature.
    """
    print("\n" + "=" * 60)
    print("Step 3: Ecotone generation (polygon adjacency analysis)")
    print("=" * 60)

    if not features:
        return {"type": "FeatureCollection", "name": "ecotones_polabi", "features": []}

    # Build lookup: frozenset of biotope pair -> ecotone_id
    pair_to_eco = {frozenset(eco["pair"]): eid for eid, eco in PL_ECOTONES.items()}

    gdf = gpd.GeoDataFrame.from_features(features, crs=CRS_OUT)
    # Filter to polygonal features with a biotope_id
    gdf = gdf[gdf["biotope_id"].notna() & (gdf.geometry.type.isin(["Polygon", "MultiPolygon"]))].copy()
    gdf = gdf.reset_index(drop=True)
    sindex = gdf.sindex

    raw_named = defaultdict(list)   # eco_id -> [LineString…]
    raw_generic = []                # [LineString…]
    pair_counts = Counter()
    processed_pairs = set()

    for idx, row in gdf.iterrows():
        possible = list(sindex.intersection(row.geometry.bounds))
        for nidx in possible:
            if nidx == idx:
                continue
            if (idx, nidx) in processed_pairs or (nidx, idx) in processed_pairs:
                continue
            processed_pairs.add((idx, nidx))

            neighbor = gdf.iloc[nidx]
            if not neighbor.get("biotope_id"):
                continue
            if row["biotope_id"] == neighbor["biotope_id"]:
                continue
            if not row.geometry.intersects(neighbor.geometry):
                continue

            try:
                inter = row.geometry.intersection(neighbor.geometry)
                if inter.is_empty:
                    continue
                # Convert to lines
                if inter.geom_type in ("Polygon", "MultiPolygon"):
                    inter = inter.boundary
                elif inter.geom_type == "GeometryCollection":
                    parts = [g for g in inter.geoms
                             if g.geom_type in ("LineString", "MultiLineString")]
                    if not parts:
                        continue
                    inter = unary_union(parts)
                if inter.is_empty or inter.geom_type == "Point":
                    continue
                if inter.geom_type == "LineString":
                    inter = MultiLineString([inter])
                elif inter.geom_type != "MultiLineString":
                    continue
            except Exception:
                continue

            bt_pair = frozenset([row["biotope_id"], neighbor["biotope_id"]])
            pair_counts[bt_pair] += 1

            if bt_pair in pair_to_eco:
                raw_named[pair_to_eco[bt_pair]].append(inter)
            else:
                raw_generic.append(inter)

    # Build named ecotone features
    print("  Pair tally (top 10):")
    for pair, n in pair_counts.most_common(10):
        named_id = pair_to_eco.get(pair, "(generic)")
        a, b = sorted(pair)
        print(f"    {a} ↔ {b}: {n} segments → {named_id}")

    eco_features = []
    for eco_id, geoms in raw_named.items():
        eco = PL_ECOTONES[eco_id]
        merged = unary_union(geoms)
        if merged.geom_type == "LineString":
            merged = MultiLineString([merged])
        elif merged.geom_type == "GeometryCollection":
            ls = [g for g in merged.geoms if g.geom_type in ("LineString", "MultiLineString")]
            if not ls:
                continue
            merged = unary_union(ls)
            if merged.geom_type == "LineString":
                merged = MultiLineString([merged])
        if merged.is_empty or merged.geom_type != "MultiLineString":
            continue
        eco_features.append({
            "type": "Feature",
            "properties": {
                "id": eco_id,
                "name": eco["name"],
                "biotope_a_id": eco["pair"][0],
                "biotope_b_id": eco["pair"][1],
                "edge_effect_factor": eco["edge_effect_factor"],
                "human_relevance": eco["human_relevance"],
                "region": "polabi",
                "certainty": "INFERENCE",
                "source": "Polygon adjacency analysis on terrain_features_polabi",
            },
            "geometry": mapping(merged),
        })

    # Generic ecotone — single feature for everything else
    if raw_generic:
        merged = unary_union(raw_generic)
        if merged.geom_type == "LineString":
            merged = MultiLineString([merged])
        elif merged.geom_type == "GeometryCollection":
            ls = [g for g in merged.geoms if g.geom_type in ("LineString", "MultiLineString")]
            if ls:
                merged = unary_union(ls)
                if merged.geom_type == "LineString":
                    merged = MultiLineString([merged])
        if not merged.is_empty and merged.geom_type == "MultiLineString":
            generic_pairs = sorted({tuple(sorted(p)) for p in pair_counts.keys()
                                    if p not in pair_to_eco})
            eco_features.append({
                "type": "Feature",
                "properties": {
                    "id": "ec_pl_generic",
                    "name": "Obecný ekoton (zbylé biotopové hranice)",
                    "biotope_a_id": "multiple",
                    "biotope_b_id": "multiple",
                    "edge_effect_factor": 1.2,
                    "human_relevance": "Ostatní biotopové hranice — indikátor diverzity",
                    "region": "polabi",
                    "certainty": "INFERENCE",
                    "source": "Polygon adjacency (catch-all for unnamed pairs)",
                    "biotope_pairs": [list(p) for p in generic_pairs],
                },
                "geometry": mapping(merged),
            })

    # Report
    print(f"\n  Generated {len(eco_features)} ecotone features:")
    found_ids = {f["properties"]["id"] for f in eco_features}
    for eco_id, eco in PL_ECOTONES.items():
        ok = "OK" if eco_id in found_ids else "MISSING (no adjacency)"
        print(f"    {eco_id}: {eco['name']:32s} — {ok}")
    if "ec_pl_generic" in found_ids:
        print(f"    ec_pl_generic: catch-all generic ecotone")

    return {"type": "FeatureCollection", "name": "ecotones_polabi", "features": eco_features}


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------

def save_geojson(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    size_mb = path.stat().st_size / 1024 / 1024
    print(f"  Saved: {path.name} ({size_mb:.2f} MB, {len(data.get('features', []))} features)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Polabí KB rules (glades + ecotones)")
    ap.add_argument("--no-glades", action="store_true", help="Skip glade reclassification")
    ap.add_argument("--only", choices=["glades", "ecotones"], help="Run only one step")
    args = ap.parse_args()

    print("=" * 60)
    print("Mezolit2 — Polabí KB rules application")
    print("=" * 60)

    if not IN_TERRAIN.exists():
        print(f"ERROR: {IN_TERRAIN} not found. Run 04_terrain_polabi.py first.")
        sys.exit(1)

    with open(IN_TERRAIN, encoding="utf-8") as f:
        terrain = json.load(f)
    print(f"Loaded {len(terrain['features'])} terrain features\n")

    # Step 1: verify biotopes
    verify_biotopes(terrain["features"])

    # Step 2: glades
    if not args.no_glades and (args.only is None or args.only == "glades"):
        glades = detect_glades(terrain["features"])
        if glades:
            terrain["features"].extend(glades)
            print(f"  Total features after glades: {len(terrain['features'])}")

    if args.only == "glades":
        save_geojson(terrain, OUT_TERRAIN)
        return

    # Step 3: ecotones
    ecotones_fc = {"type": "FeatureCollection", "name": "ecotones_polabi", "features": []}
    if args.only is None or args.only == "ecotones":
        ecotones_fc = generate_ecotones(terrain["features"])

    # Save outputs
    print("\n" + "=" * 60)
    print("EXPORT")
    print("=" * 60)
    save_geojson(terrain, OUT_TERRAIN)
    save_geojson(ecotones_fc, OUT_ECOTONES)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print("  Next step: python pipeline/06_import_supabase_polabi.py")


if __name__ == "__main__":
    main()

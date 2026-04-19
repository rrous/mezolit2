#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mezolit2 -- Trebonsko Map Validation Tests
==========================================
Implements feasible tests from MAP_VALIDATION_TESTS_v02.md against
processed CZ GeoJSON data + raw source layers.

Usage: python pipeline/run_validation_tests_cz.py
"""

import json
import os
import sys
import time
import math
import warnings
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import rowcol
from shapely.geometry import shape, Point, MultiPolygon, LineString, box
from shapely.ops import unary_union
import fiona
import geopandas as gpd
from pyproj import Transformer

warnings.filterwarnings("ignore")

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# -- Paths -----------------------------------------------------------------
BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "data" / "processed" / "cz"
RAW = BASE / "data" / "raw" / "cz"
DEM_PATH = RAW / "dem" / "trebonsko_dmr5g_10m.tif"

# Trebonsko bbox (WGS84)
BBOX = box(14.53, 48.93, 14.95, 49.22)

# -- CRS transformers (WGS84 <-> S-JTSK / Krovak East North EPSG:5514) ----
to_jtsk = Transformer.from_crs("EPSG:4326", "EPSG:5514", always_xy=True)
to_wgs = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)

# Trebonsko bbox in S-JTSK for DIBAVOD queries
bbox_jtsk_bl = to_jtsk.transform(14.53, 48.93)
bbox_jtsk_tr = to_jtsk.transform(14.95, 49.22)
BBOX_JTSK = (min(bbox_jtsk_bl[0], bbox_jtsk_tr[0]),
             min(bbox_jtsk_bl[1], bbox_jtsk_tr[1]),
             max(bbox_jtsk_bl[0], bbox_jtsk_tr[0]),
             max(bbox_jtsk_bl[1], bbox_jtsk_tr[1]))


# -- Helpers ---------------------------------------------------------------
def load_geojson(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def geojson_to_shapes(geojson):
    """Return list of (properties, shapely_geometry) tuples."""
    result = []
    for feat in geojson["features"]:
        geom = shape(feat["geometry"]) if feat["geometry"] else None
        result.append((feat["properties"], geom))
    return result


def haversine_m(lon1, lat1, lon2, lat2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def sample_dem(dem, coords_lonlat):
    """Sample DEM at (lon, lat) WGS84 points. Reprojects to S-JTSK internally."""
    elevations = []
    for lon, lat in coords_lonlat:
        try:
            x_jtsk, y_jtsk = to_jtsk.transform(lon, lat)
            r, c = rowcol(dem.transform, x_jtsk, y_jtsk)
            if 0 <= r < dem.height and 0 <= c < dem.width:
                val = dem.read(1, window=((r, r+1), (c, c+1)))[0, 0]
                if val != dem.nodata and val > -9000:
                    elevations.append(float(val))
                else:
                    elevations.append(None)
            else:
                elevations.append(None)
        except Exception:
            elevations.append(None)
    return elevations


# -- Test Results Container ------------------------------------------------
class TestResult:
    def __init__(self, test_id, name, category, status, score=None,
                 details="", n_tested=0, n_passed=0, n_failed=0, n_skipped=0):
        self.test_id = test_id
        self.name = name
        self.category = category
        self.status = status  # PASS / FAIL / WARN / SKIP / INFO
        self.score = score
        self.details = details
        self.n_tested = n_tested
        self.n_passed = n_passed
        self.n_failed = n_failed
        self.n_skipped = n_skipped

    def to_dict(self):
        d = {
            "test_id": self.test_id,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "details": self.details,
        }
        if self.score is not None:
            d["score"] = round(self.score, 3)
        if self.n_tested:
            d["n_tested"] = self.n_tested
            d["n_passed"] = self.n_passed
            d["n_failed"] = self.n_failed
        if self.n_skipped:
            d["n_skipped"] = self.n_skipped
        return d


results = []

# =========================================================================
# Load Data
# =========================================================================
print("Loading data...")
t0 = time.time()

terrain = load_geojson(PROC / "terrain_features_cz.geojson")
terrain_bio = load_geojson(PROC / "terrain_features_with_biotopes_cz.geojson")
rivers_gj = load_geojson(PROC / "rivers_cz.geojson")
ecotones_gj = load_geojson(PROC / "ecotones_cz.geojson")
sites_gj = load_geojson(PROC / "sites_cz.geojson")
paleolakes = load_geojson(RAW / "paleolakes_cz.geojson")

terrain_shapes = geojson_to_shapes(terrain)
terrain_bio_shapes = geojson_to_shapes(terrain_bio)
river_shapes = geojson_to_shapes(rivers_gj)
ecotone_shapes = geojson_to_shapes(ecotones_gj)
site_shapes = geojson_to_shapes(sites_gj)
paleolake_shapes = geojson_to_shapes(paleolakes)

dem = rasterio.open(DEM_PATH)

# Load VMB (already WGS84)
vmb_gdf = gpd.read_file(RAW / "vmb" / "vmb_biotopy.geojson")
print(f"  VMB: {len(vmb_gdf)} polygons")

# Load CGS geology (check CRS)
cgs_gdf = gpd.read_file(RAW / "cgs" / "geologicka_mapa50.geojson")
if cgs_gdf.crs and cgs_gdf.crs.to_epsg() != 4326:
    cgs_gdf = cgs_gdf.to_crs("EPSG:4326")
print(f"  CGS: {len(cgs_gdf)} polygons")

# Load DIBAVOD (S-JTSK EPSG:5514) -> reproject to WGS84
print("  Loading DIBAVOD (S-JTSK -> WGS84)...")
dibavod_rivers = gpd.read_file(RAW / "dibavod" / "A02" / "A02_Vodni_tok_JU.shp",
                                bbox=BBOX_JTSK)
if len(dibavod_rivers) > 0:
    dibavod_rivers = dibavod_rivers.to_crs("EPSG:4326")
print(f"  DIBAVOD rivers (bbox): {len(dibavod_rivers)}")

dibavod_water = gpd.read_file(RAW / "dibavod" / "A05" / "A05_Vodni_nadrze.shp",
                               bbox=BBOX_JTSK)
if len(dibavod_water) > 0:
    dibavod_water = dibavod_water.to_crs("EPSG:4326")
print(f"  DIBAVOD water (bbox): {len(dibavod_water)}")

dibavod_marsh = gpd.read_file(RAW / "dibavod" / "A06" / "A06_Bazina_mocal.shp",
                               bbox=BBOX_JTSK)
if len(dibavod_marsh) > 0:
    dibavod_marsh = dibavod_marsh.to_crs("EPSG:4326")
print(f"  DIBAVOD marsh (bbox): {len(dibavod_marsh)}")

# Load mineral deposits
loziska = load_geojson(RAW / "cgs" / "loziska_surovin.geojson")

print(f"Data loaded in {time.time()-t0:.1f}s\n")


# =========================================================================
# T-PHY-01: Ricni spad (River gradient)
# =========================================================================
print("T-PHY-01: Ricni spad ...")
try:
    tolerance = 0.5  # m
    n_tested = 0
    n_fail = 0
    fail_details = []

    for props, geom in river_shapes:
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == "LineString":
            coords = list(geom.coords)
        elif geom.geom_type == "MultiLineString":
            coords = []
            for line in geom.geoms:
                coords.extend(list(line.coords))
        else:
            continue

        if len(coords) < 2:
            continue

        start = coords[0]   # upstream (source)
        end = coords[-1]    # downstream (mouth)

        elevs = sample_dem(dem, [(start[0], start[1]), (end[0], end[1])])
        if elevs[0] is None or elevs[1] is None:
            continue

        n_tested += 1
        elev_start, elev_end = elevs[0], elevs[1]

        # Water flows downhill: start should be >= end
        if elev_end > elev_start + tolerance:
            n_fail += 1
            if len(fail_details) < 5:
                fail_details.append(
                    f"  {props.get('name','?')} ({props['id']}): "
                    f"start={elev_start:.1f}m -> end={elev_end:.1f}m "
                    f"(reverse: +{elev_end-elev_start:.1f}m)"
                )

    pct_pass = ((n_tested - n_fail) / n_tested * 100) if n_tested else 0
    status = "PASS" if n_fail == 0 else ("WARN" if pct_pass > 90 else "FAIL")
    detail = f"{n_tested - n_fail}/{n_tested} segments OK ({pct_pass:.1f}%)"
    if fail_details:
        detail += "\nReversed segments:\n" + "\n".join(fail_details)

    results.append(TestResult("T-PHY-01", "Ricni spad", "PHY", status,
                              score=pct_pass/100, details=detail,
                              n_tested=n_tested, n_passed=n_tested-n_fail, n_failed=n_fail))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-PHY-01", "Ricni spad", "PHY", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-PHY-02: Mokrad v depresi (Wetland in depression)
# =========================================================================
print("T-PHY-02: Mokrad v depresi ...")
try:
    radius_m = 500
    elevation_excess_max = 5  # m
    # VMB wetland codes: M*, R*, V*
    wetland_mask = vmb_gdf["BIOTOP_SEZ"].str.match(r"^[MRV]", na=False)
    wetlands = vmb_gdf[wetland_mask].copy()

    n_tested = 0
    n_fail = 0
    fail_details = []

    for idx, row in wetlands.iterrows():
        try:
            centroid = row.geometry.centroid
            lon, lat = centroid.x, centroid.y
        except Exception:
            continue

        # Get center elevation
        center_elev = sample_dem(dem, [(lon, lat)])[0]
        if center_elev is None:
            continue

        # Sample surrounding points (~500m radius in WGS84 degrees)
        dlat = radius_m / 111_000
        dlon = radius_m / (111_000 * math.cos(math.radians(lat)))
        surround = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                surround.append((lon + dx*dlon, lat + dy*dlat))

        surround_elevs = sample_dem(dem, surround)
        valid_surr = [e for e in surround_elevs if e is not None]
        if len(valid_surr) < 3:
            continue

        mean_surround = np.mean(valid_surr)
        n_tested += 1

        if center_elev > mean_surround + elevation_excess_max:
            n_fail += 1
            if len(fail_details) < 5:
                fail_details.append(
                    f"  {row.get('BIOTOP_SEZ','?')}: center={center_elev:.1f}m, "
                    f"surround={mean_surround:.1f}m (+{center_elev-mean_surround:.1f}m)"
                )

    pct_pass = ((n_tested - n_fail) / n_tested * 100) if n_tested else 0
    status = "PASS" if n_fail == 0 else ("WARN" if pct_pass > 95 else "FAIL")
    detail = f"{n_tested - n_fail}/{n_tested} wetlands in depressions ({pct_pass:.1f}%)"
    if fail_details:
        detail += "\nAnomalies:\n" + "\n".join(fail_details)

    results.append(TestResult("T-PHY-02", "Mokrad v depresi", "PHY", status,
                              score=pct_pass/100, details=detail,
                              n_tested=n_tested, n_passed=n_tested-n_fail, n_failed=n_fail))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-PHY-02", "Mokrad v depresi", "PHY", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-PHY-06: Sklon vs. mokrad (Slope vs wetland)
# =========================================================================
print("T-PHY-06: Sklon vs. mokrad ...")
try:
    max_slope_deg = 5
    wetland_mask = vmb_gdf["BIOTOP_SEZ"].str.match(r"^[MRV]", na=False)
    wetlands = vmb_gdf[wetland_mask].copy()

    n_tested = 0
    n_fail = 0
    fail_details = []

    for idx, row in wetlands.iterrows():
        try:
            centroid = row.geometry.centroid
            lon, lat = centroid.x, centroid.y
        except Exception:
            continue

        # Sample DEM at 3 points for slope estimate (~10m step)
        step_m = 10
        step_lat = step_m / 111_000
        step_lon = step_m / (111_000 * math.cos(math.radians(lat)))

        elevs = sample_dem(dem, [
            (lon, lat),
            (lon + step_lon, lat),
            (lon, lat + step_lat)
        ])

        if None in elevs:
            continue

        n_tested += 1
        dx = (elevs[1] - elevs[0]) / step_m
        dy = (elevs[2] - elevs[0]) / step_m
        slope_deg = math.degrees(math.atan(math.sqrt(dx**2 + dy**2)))

        if slope_deg > max_slope_deg:
            n_fail += 1
            if len(fail_details) < 5:
                fail_details.append(
                    f"  {row.get('BIOTOP_SEZ','?')}: slope={slope_deg:.1f} deg"
                )

    pct_pass = ((n_tested - n_fail) / n_tested * 100) if n_tested else 0
    status = "PASS" if pct_pass >= 95 else ("WARN" if pct_pass >= 85 else "FAIL")
    detail = f"{n_tested - n_fail}/{n_tested} wetlands on flat ground ({pct_pass:.1f}%)"
    if fail_details:
        detail += "\nSteep wetlands:\n" + "\n".join(fail_details)

    results.append(TestResult("T-PHY-06", "Sklon vs. mokrad", "PHY", status,
                              score=pct_pass/100, details=detail,
                              n_tested=n_tested, n_passed=n_tested-n_fail, n_failed=n_fail))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-PHY-06", "Sklon vs. mokrad", "PHY", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-PHY-07: Paleojezero elevace (Paleolake elevation)
# =========================================================================
print("T-PHY-07: Paleojezero elevace ...")
try:
    svarcenberk = None
    for props, geom in paleolake_shapes:
        if props.get("name") == "Svarcenberk" and geom:
            svarcenberk = (props, geom)
            break

    if svarcenberk:
        props, geom = svarcenberk
        centroid = geom.centroid
        dem_elev = sample_dem(dem, [(centroid.x, centroid.y)])[0]
        reported_elev = props.get("elevation_m")

        parts = []
        if dem_elev is not None:
            parts.append(f"DEM centroid={dem_elev:.1f}m")
        if reported_elev is not None:
            parts.append(f"pipeline elevation={reported_elev}m")
        detail = "Svarcenberk: " + ", ".join(parts)

        if dem_elev is not None and reported_elev is not None:
            diff = abs(dem_elev - reported_elev)
            detail += f", diff={diff:.1f}m"

        # Published level from Pokorny ~410-415m asl
        detail += "\nNote: Pokorny et al. 2010 -- published level ~410-415m asl"

        if dem_elev is not None:
            in_range = 407 <= dem_elev <= 418
            detail += f"\nDEM value {dem_elev:.1f}m is {'within' if in_range else 'OUTSIDE'} expected range 407-418m"
            status = "PASS" if in_range else "WARN"
            score = max(0, 1.0 - abs(dem_elev - 412.5) / 10)
        else:
            status = "WARN"
            score = 0.5
            detail += "\nDEM sampling failed at centroid"
    else:
        status = "SKIP"
        score = None
        detail = "Svarcenberk paleolake not found in data"

    results.append(TestResult("T-PHY-07", "Paleojezero elevace", "PHY", status,
                              score=score, details=detail, n_tested=1 if svarcenberk else 0))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-PHY-07", "Paleojezero elevace", "PHY", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-ECO-01: Dostupnost vody z lokality (Water proximity)
# =========================================================================
print("T-ECO-01: Dostupnost vody z lokality ...")
try:
    threshold_m = 500

    # Build water geometry from processed rivers + DIBAVOD water bodies
    # Separate lines and polygons to avoid LinearIterator errors
    water_lines = []
    water_polys = []
    for props, geom in river_shapes:
        if geom and not geom.is_empty:
            water_lines.append(geom)

    for _, row in dibavod_rivers.iterrows():
        if row.geometry and not row.geometry.is_empty:
            if row.geometry.geom_type in ("Polygon", "MultiPolygon"):
                water_polys.append(row.geometry)
            else:
                water_lines.append(row.geometry)

    for _, row in dibavod_water.iterrows():
        if row.geometry and not row.geometry.is_empty:
            water_polys.append(row.geometry)

    water_line_union = unary_union(water_lines) if water_lines else None
    water_poly_union = unary_union(water_polys) if water_polys else None

    n_tested = 0
    n_pass = 0
    site_details = []
    distances = []

    for props, geom in site_shapes:
        if geom is None:
            continue
        pt = geom.centroid if geom.geom_type != "Point" else geom

        # Find nearest water (check lines and polygons separately)
        dists = []
        if water_line_union:
            near_l = water_line_union.interpolate(water_line_union.project(pt))
            dists.append(haversine_m(pt.x, pt.y, near_l.x, near_l.y))
        if water_poly_union:
            # For polygons, use distance to boundary
            d_poly = pt.distance(water_poly_union)
            dists.append(d_poly * 111_000 * math.cos(math.radians(pt.y)))
        dist_m = min(dists) if dists else float("inf")

        n_tested += 1
        distances.append(dist_m)

        if dist_m <= threshold_m:
            n_pass += 1
            status_s = "OK"
        else:
            status_s = "FAR"

        site_details.append(
            f"  {props.get('id','?')}: {dist_m:.0f}m to water [{status_s}]"
        )

    pct = (n_pass / n_tested * 100) if n_tested else 0
    mean_dist = np.mean(distances) if distances else 0
    status = "PASS" if pct >= 80 else ("WARN" if pct >= 50 else "FAIL")
    score = pct / 100
    detail = (f"{n_pass}/{n_tested} sites within {threshold_m}m of water ({pct:.0f}%), "
              f"mean distance={mean_dist:.0f}m")
    detail += "\n" + "\n".join(site_details)

    results.append(TestResult("T-ECO-01", "Dostupnost vody", "ECO", status,
                              score=score, details=detail,
                              n_tested=n_tested, n_passed=n_pass, n_failed=n_tested-n_pass))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-ECO-01", "Dostupnost vody", "ECO", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-ECO-02: Ekotonova poloha lokality (Ecotone proximity)
# =========================================================================
print("T-ECO-02: Ekotonova poloha lokality ...")
try:
    ecotone_buffer_m = 200

    # Build ecotone lines from processed ecotones
    eco_lines = []
    for props, geom in ecotone_shapes:
        if geom and not geom.is_empty:
            eco_lines.append(geom)

    # Also use terrain feature boundaries as ecotones (different substrate = ecotone)
    terrain_boundaries = []
    for feat in terrain["features"]:
        if feat["geometry"]:
            geom = shape(feat["geometry"])
            if geom.boundary and not geom.boundary.is_empty:
                terrain_boundaries.append(geom.boundary)

    all_eco = eco_lines + terrain_boundaries[:100]  # limit for performance

    if all_eco:
        eco_union = unary_union(all_eco)

        n_tested = 0
        n_near = 0
        site_eco_details = []

        for props, geom in site_shapes:
            if geom is None:
                continue
            pt = geom.centroid if geom.geom_type != "Point" else geom

            nearest = eco_union.interpolate(eco_union.project(pt))
            dist_m = haversine_m(pt.x, pt.y, nearest.x, nearest.y)

            n_tested += 1
            near = dist_m <= ecotone_buffer_m
            if near:
                n_near += 1
            site_eco_details.append(
                f"  {props.get('id','?')}: {dist_m:.0f}m to ecotone [{'OK' if near else 'FAR'}]"
            )

        # Random comparison
        n_random = 500
        rng = np.random.default_rng(42)
        rand_pts = [Point(rng.uniform(14.53, 14.95), rng.uniform(48.93, 49.22))
                    for _ in range(n_random)]
        n_rand_near = 0
        for pt in rand_pts:
            near_pt = eco_union.interpolate(eco_union.project(pt))
            d = haversine_m(pt.x, pt.y, near_pt.x, near_pt.y)
            if d <= ecotone_buffer_m:
                n_rand_near += 1
        pct_random = n_rand_near / n_random * 100

        pct_sites = (n_near / n_tested * 100) if n_tested else 0
        ratio = (pct_sites / pct_random) if pct_random > 0 else float("inf")

        # With generic ecotones covering most of the area, both sites and random
        # points are near ecotones. The test checks relative preference.
        # With only 12 sites, statistical power is very low.
        status = "PASS" if ratio >= 1.5 else ("WARN" if ratio >= 0.8 else "FAIL")
        score = min(1.0, ratio / 1.5)
        detail = (f"Sites near ecotone: {pct_sites:.0f}% ({n_near}/{n_tested}), "
                  f"random baseline: {pct_random:.0f}%, ratio: {ratio:.2f}x")
        if n_tested < 20:
            detail += f"\nNote: only {n_tested} sites -- low statistical power for preference test"
        detail += "\n" + "\n".join(site_eco_details)
    else:
        status = "SKIP"
        score = None
        detail = "No ecotone geometries available"
        n_tested = 0

    results.append(TestResult("T-ECO-02", "Ekotonova poloha", "ECO", status,
                              score=score, details=detail,
                              n_tested=n_tested if all_eco else 0))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-ECO-02", "Ekotonova poloha", "ECO", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-ECO-08: Vegetacni zonace (Elevation zonation)
# =========================================================================
print("T-ECO-08: Vegetacni zonace ...")
try:
    # Trebonsko is 400-550m. The standard lowland_max=300m doesn't apply.
    # Instead we test: wetland/riparian biotopes should be at LOWER elevations
    # within the local range, and forest biotopes at higher.

    # Get elevation stats for different biotope groups
    wetland_mask = vmb_gdf["BIOTOP_SEZ"].str.match(r"^[MRV]", na=False)
    forest_mask = vmb_gdf["BIOTOP_SEZ"].str.match(r"^L[3-9]", na=False)
    riparian_mask = vmb_gdf["BIOTOP_SEZ"].str.match(r"^L2", na=False)

    groups = {
        "wetland (M*,R*,V*)": vmb_gdf[wetland_mask],
        "riparian (L2*)": vmb_gdf[riparian_mask],
        "upland forest (L3-9*)": vmb_gdf[forest_mask],
    }

    group_elevs = {}
    for name, gdf in groups.items():
        elevs = []
        sample = gdf.head(200)
        for _, row in sample.iterrows():
            try:
                c = row.geometry.centroid
                e = sample_dem(dem, [(c.x, c.y)])[0]
                if e is not None:
                    elevs.append(e)
            except Exception:
                continue
        group_elevs[name] = elevs

    detail_lines = ["Biotope group elevation stats:"]
    for name, elevs in group_elevs.items():
        if elevs:
            detail_lines.append(
                f"  {name}: mean={np.mean(elevs):.0f}m, "
                f"median={np.median(elevs):.0f}m, "
                f"range=[{min(elevs):.0f}-{max(elevs):.0f}]m (n={len(elevs)})"
            )

    # Check: wetland/riparian mean < upland forest mean
    w_elev = group_elevs.get("wetland (M*,R*,V*)", [])
    r_elev = group_elevs.get("riparian (L2*)", [])
    f_elev = group_elevs.get("upland forest (L3-9*)", [])

    lowland = w_elev + r_elev
    if lowland and f_elev:
        mean_low = np.mean(lowland)
        mean_high = np.mean(f_elev)
        correct_order = mean_low <= mean_high
        detail_lines.append(f"\nWetland+riparian mean: {mean_low:.0f}m vs Forest mean: {mean_high:.0f}m")
        detail_lines.append(f"Zonation order correct: {correct_order}")

        if correct_order:
            diff = mean_high - mean_low
            score = min(1.0, diff / 30)  # 30m difference = perfect
            status = "PASS" if diff >= 10 else "WARN"
        else:
            score = 0.2
            status = "WARN"
    else:
        status = "INFO"
        score = 0.5
        detail_lines.append("\nInsufficient data for zonation comparison")

    detail_lines.append(f"\nNote: Trebonsko elevation range ~400-550m (mid-elevation basin)")

    detail = "\n".join(detail_lines)
    n_tested = sum(len(v) for v in group_elevs.values())

    results.append(TestResult("T-ECO-08", "Vegetacni zonace", "ECO", status,
                              score=score, details=detail, n_tested=n_tested))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-ECO-08", "Vegetacni zonace", "ECO", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-ECO-12: Ekoton existence na VMB hranicich
# =========================================================================
print("T-ECO-12: Ekoton existence ...")
try:
    n_ecotones = len(ecotone_shapes)
    n_with_geom = sum(1 for _, g in ecotone_shapes if g and not g.is_empty)

    n_valid = 0
    eco_detail_lines = []
    for props, geom in ecotone_shapes:
        a = props.get("biotope_a_id")
        b = props.get("biotope_b_id")
        # Generic ecotone has "multiple" for both — also valid
        has_pair = (a and b and a != b) or (a == "multiple")
        has_geom = geom is not None and not geom.is_empty
        if has_pair and has_geom:
            n_valid += 1
        eco_detail_lines.append(
            f"  {props.get('id','?')}: {a} <-> {b} geom={'OK' if has_geom else 'MISSING'}"
        )

    pct = (n_valid / n_ecotones * 100) if n_ecotones else 0
    status = "PASS" if pct >= 80 else ("WARN" if pct >= 50 else "FAIL")
    score = pct / 100
    detail = f"{n_valid}/{n_ecotones} ecotones valid (distinct biotope pair + geometry)"
    detail += "\n" + "\n".join(eco_detail_lines)

    results.append(TestResult("T-ECO-12", "Ekoton existence", "ECO", status,
                              score=score, details=detail,
                              n_tested=n_ecotones, n_passed=n_valid, n_failed=n_ecotones-n_valid))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-ECO-12", "Ekoton existence", "ECO", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-GEO-01: Geologie vs. terrain klasifikace
# =========================================================================
print("T-GEO-01: Geologie vs. terrain klasifikace ...")
try:
    substrate_to_cgs = {
        "crystalline_basement": ["krystalinikum", "moldanubikum", "metamorfit",
                                  "granit", "rula", "migmatit"],
        "cretaceous_sandstone": ["krid", "kret", "piskovec", "svrchni krida", "cenoman"],
        "cretaceous_claystone": ["krid", "kret", "jilovec", "jil"],
        "aeolian_sand": ["eolick", "vate pisky", "diluvialni pisky"],
        "neogene_lacustrine": ["neog", "miocen", "tretihor", "tercier"],
        "peat_organic": ["raselin", "slatina", "organick", "sediment nezpevneny"],
        "alluvial_floodplain": ["aluvialn", "niv", "ricni", "fluvialn"],
        "glacial_lake_basin": ["jezer", "limn", "glacial", "lake"],
    }

    n_tested = 0
    n_match = 0
    mismatch_details = []

    terrain_gdf = gpd.GeoDataFrame.from_features(terrain["features"])
    terrain_gdf.set_crs("EPSG:4326", inplace=True)

    sample_indices = np.random.default_rng(42).choice(
        len(terrain_gdf), size=min(150, len(terrain_gdf)), replace=False)

    for i in sample_indices:
        row = terrain_gdf.iloc[i]
        substrate = row.get("substrate", "")
        if not substrate or substrate not in substrate_to_cgs:
            continue

        try:
            centroid = row.geometry.centroid
            candidates = cgs_gdf[cgs_gdf.intersects(centroid)]
            if len(candidates) == 0:
                continue

            n_tested += 1
            expected_keywords = substrate_to_cgs[substrate]

            cgs_row = candidates.iloc[0]
            # Normalize text: remove diacritics isn't easy, just lowercase
            cgs_text = " ".join(str(v).lower() for v in [
                cgs_row.get("oblast", ""), cgs_row.get("geneze", ""),
                cgs_row.get("hor_karto", ""), cgs_row.get("soustava", ""),
                cgs_row.get("utvar", ""), cgs_row.get("hor_typ", "")
            ] if v)

            matched = any(kw.lower() in cgs_text for kw in expected_keywords)
            if matched:
                n_match += 1
            else:
                if len(mismatch_details) < 5:
                    mismatch_details.append(
                        f"  {row.get('id','?')} substrate={substrate} "
                        f"vs CGS: {str(cgs_row.get('hor_karto','?'))[:60]}"
                    )
        except Exception:
            continue

    pct = (n_match / n_tested * 100) if n_tested else 0
    status = "PASS" if pct >= 70 else ("WARN" if pct >= 50 else "FAIL")
    score = pct / 100
    detail = f"{n_match}/{n_tested} terrain features match CGS geology ({pct:.1f}%)"
    if mismatch_details:
        detail += "\nMismatches:\n" + "\n".join(mismatch_details)

    results.append(TestResult("T-GEO-01", "Geologie vs. terrain", "GEO", status,
                              score=score, details=detail,
                              n_tested=n_tested, n_passed=n_match, n_failed=n_tested-n_match))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-GEO-01", "Geologie vs. terrain", "GEO", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-GEO-04: Kvarterni sedimenty v jezernich panvich
# =========================================================================
print("T-GEO-04: Kvarternich sedimenty v panvich ...")
try:
    lake_features = [f for f in terrain["features"]
                     if f["properties"].get("terrain_subtype_id") in ("tst_cz_009",)]

    n_tested = 0
    n_quaternary = 0
    q_details = []

    for feat in lake_features[:50]:
        geom = shape(feat["geometry"])
        centroid = geom.centroid

        try:
            candidates = cgs_gdf[cgs_gdf.intersects(centroid)]
            if len(candidates) == 0:
                continue

            n_tested += 1
            cgs_row = candidates.iloc[0]
            cgs_text = " ".join(str(v).lower() for v in [
                cgs_row.get("oblast", ""), cgs_row.get("utvar", ""),
                cgs_row.get("geneze", ""), cgs_row.get("hor_karto", ""),
                cgs_row.get("hor_typ", "")
            ] if v)

            is_quaternary = any(kw in cgs_text for kw in [
                "kvartern", "kvarter", "kvart", "holocen", "pleistocen",
                "aluvial", "raselin", "organick", "jezer", "limn",
                "fluvial", "ricni", "niv", "sediment nezpevn",
                "slatina", "pisk", "diluvial"
            ])

            if is_quaternary:
                n_quaternary += 1
            else:
                if len(q_details) < 5:
                    q_details.append(
                        f"  {feat['properties']['id']}: CGS: "
                        f"oblast={cgs_row.get('oblast','?')}, "
                        f"geneze={str(cgs_row.get('geneze','?'))[:40]}, "
                        f"hor_karto={str(cgs_row.get('hor_karto','?'))[:40]}"
                    )
        except Exception:
            continue

    pct = (n_quaternary / n_tested * 100) if n_tested else 0
    status = "PASS" if pct >= 80 else ("WARN" if pct >= 60 else "FAIL")
    score = pct / 100
    detail = f"{n_quaternary}/{n_tested} lake basin features on Quaternary sediments ({pct:.1f}%)"
    if q_details:
        detail += "\nNon-Quaternary:\n" + "\n".join(q_details)

    results.append(TestResult("T-GEO-04", "Kvarternich sedimenty v panvich", "GEO", status,
                              score=score, details=detail,
                              n_tested=n_tested, n_passed=n_quaternary, n_failed=n_tested-n_quaternary))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-GEO-04", "Kvarternich sedimenty v panvich", "GEO", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-ARCH-04: Nadmorska vyska lokalit (Site elevation distribution)
# =========================================================================
print("T-ARCH-04: Nadmorska vyska lokalit ...")
try:
    site_elevs = []
    site_elev_details = []
    for props, geom in site_shapes:
        if geom is None:
            continue
        pt = geom.centroid if geom.geom_type != "Point" else geom
        elev = sample_dem(dem, [(pt.x, pt.y)])[0]
        if elev is not None:
            site_elevs.append(elev)
            site_elev_details.append(f"  {props.get('id','?')}: {elev:.0f}m")

    # Random elevation sample
    n_random = 1000
    rng = np.random.default_rng(42)
    rand_coords = [(rng.uniform(14.53, 14.95), rng.uniform(48.93, 49.22))
                    for _ in range(n_random)]
    rand_elevs = [e for e in sample_dem(dem, rand_coords) if e is not None]

    if site_elevs and rand_elevs:
        mean_site = np.mean(site_elevs)
        mean_rand = np.mean(rand_elevs)

        detail = (f"Sites: mean={mean_site:.0f}m (n={len(site_elevs)}), "
                  f"Random: mean={mean_rand:.0f}m (n={len(rand_elevs)})")
        detail += f"\nSite-Random mean diff: {mean_site - mean_rand:+.0f}m"
        detail += f"\nSite elevations: min={min(site_elevs):.0f}m, max={max(site_elevs):.0f}m"
        detail += "\n" + "\n".join(site_elev_details)

        if mean_site <= mean_rand:
            score = 1.0
            status = "PASS"
        else:
            score = max(0, 1.0 - (mean_site - mean_rand) / 100)
            status = "WARN" if score > 0.5 else "FAIL"
    else:
        status = "WARN"
        score = 0.5
        detail = f"Insufficient data: {len(site_elevs)} site elevations, {len(rand_elevs)} random"

    results.append(TestResult("T-ARCH-04", "Nadmorska vyska lokalit", "ARCH", status,
                              score=score, details=detail,
                              n_tested=len(site_elevs)))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-ARCH-04", "Nadmorska vyska lokalit", "ARCH", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-ARCH-02: Surovinovy dosah (Raw material access)
# =========================================================================
print("T-ARCH-02: Surovinovy dosah ...")
try:
    primary_km = 30
    extended_km = 80

    deposit_pts = []
    for feat in loziska["features"]:
        geom = feat.get("geometry")
        if geom:
            deposit_pts.append(shape(geom))

    n_tested = 0
    n_primary = 0
    n_extended = 0
    mat_details = []

    for props, geom in site_shapes:
        if geom is None:
            continue
        pt = geom.centroid if geom.geom_type != "Point" else geom

        min_dist_km = float("inf")
        for dep_pt in deposit_pts:
            d = haversine_m(pt.x, pt.y, dep_pt.centroid.x, dep_pt.centroid.y) / 1000
            min_dist_km = min(min_dist_km, d)

        n_tested += 1
        if min_dist_km <= primary_km:
            n_primary += 1
            n_extended += 1
            label = "PRIMARY"
        elif min_dist_km <= extended_km:
            n_extended += 1
            label = "EXTENDED"
        else:
            label = "FAR"

        mat_details.append(
            f"  {props.get('id','?')}: nearest deposit={min_dist_km:.1f}km [{label}]"
        )

    pct_primary = (n_primary / n_tested * 100) if n_tested else 0
    pct_extended = (n_extended / n_tested * 100) if n_tested else 0

    status = "PASS" if pct_extended >= 80 else ("WARN" if pct_extended >= 50 else "FAIL")
    score = pct_extended / 100
    detail = (f"Primary (<{primary_km}km): {n_primary}/{n_tested} ({pct_primary:.0f}%), "
              f"Extended (<{extended_km}km): {n_extended}/{n_tested} ({pct_extended:.0f}%)")
    detail += "\n" + "\n".join(mat_details)

    results.append(TestResult("T-ARCH-02", "Surovinovy dosah", "ARCH", status,
                              score=score, details=detail,
                              n_tested=n_tested, n_passed=n_extended, n_failed=n_tested-n_extended))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-ARCH-02", "Surovinovy dosah", "ARCH", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-ECO-07: Ricni koridor -- kontinuita
# =========================================================================
print("T-ECO-07: Ricni koridor ...")
try:
    # Check riparian/floodplain presence along rivers
    # Include: alluvial_floodplain (tst_cz_006), riparian gallery (bt_cz_010),
    # floodplain forest (bt_cz_006), and aeolian sand near rivers (tst_cz_007)
    riparian_feats = [f for f in terrain_bio["features"]
                      if f["properties"].get("biotope_id") in ("bt_cz_010", "bt_cz_006")
                      or f["properties"].get("terrain_subtype_id") in ("tst_cz_006",)
                      or f["properties"].get("notes") == "riparian_zone"]

    n_rivers = len(river_shapes)
    n_with_floodplain = 0

    if riparian_feats:
        rip_shapes = [shape(f["geometry"]) for f in riparian_feats if f["geometry"]]
        rip_union = unary_union(rip_shapes)

        # Also include DIBAVOD marshes as riparian zone
        marsh_geoms = []
        for _, row in dibavod_marsh.iterrows():
            if row.geometry and not row.geometry.is_empty:
                marsh_geoms.append(row.geometry)

        if marsh_geoms:
            riparian_union = unary_union(rip_shapes + marsh_geoms)
        else:
            riparian_union = rip_union

        for props, geom in river_shapes:
            if geom and not geom.is_empty:
                if geom.intersects(riparian_union):
                    n_with_floodplain += 1

    pct = (n_with_floodplain / n_rivers * 100) if n_rivers else 0
    status = "PASS" if pct >= 70 else ("WARN" if pct >= 40 else "FAIL")
    score = pct / 100
    detail = (f"{n_with_floodplain}/{n_rivers} rivers intersect riparian/floodplain zone ({pct:.1f}%)")
    detail += f"\nRiparian/floodplain features: {len(riparian_feats)}"
    detail += f"\nDIBAVOD marshes in bbox: {len(dibavod_marsh)}"

    results.append(TestResult("T-ECO-07", "Ricni koridor", "ECO", status,
                              score=score, details=detail,
                              n_tested=n_rivers, n_passed=n_with_floodplain,
                              n_failed=n_rivers-n_with_floodplain))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-ECO-07", "Ricni koridor", "ECO", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-GEO-03: Hydrologie substratu vs. VMB
# =========================================================================
print("T-GEO-03: Hydrologie substratu vs. VMB ...")
try:
    # Permeable substrates that shouldn't host permanent wetlands
    # mixed_permeability is OK (sandstone with impermeable interbeds can host wetlands)
    permeable_substrates = {"well_drained"}

    n_tested = 0
    n_conflict = 0
    conflict_details = []

    wetland_mask = vmb_gdf["BIOTOP_SEZ"].str.match(r"^[MRV]", na=False)
    wetland_centroids = vmb_gdf[wetland_mask].geometry.centroid

    terrain_gdf_bio = gpd.GeoDataFrame.from_features(terrain_bio["features"])
    terrain_gdf_bio.set_crs("EPSG:4326", inplace=True)

    # Create spatial index
    terrain_sindex = terrain_gdf_bio.sindex

    for idx, centroid in wetland_centroids.iloc[:300].items():
        try:
            # Use spatial index for faster lookup
            possible = list(terrain_sindex.intersection(centroid.bounds))
            if not possible:
                continue
            candidates = terrain_gdf_bio.iloc[possible]
            actual = candidates[candidates.intersects(centroid)]
            if len(actual) == 0:
                continue

            n_tested += 1
            hydro = actual.iloc[0].get("hydrology", "")

            if hydro in permeable_substrates:
                n_conflict += 1
                if len(conflict_details) < 5:
                    substrate = actual.iloc[0].get("substrate", "?")
                    conflict_details.append(
                        f"  Wetland at ({centroid.x:.3f},{centroid.y:.3f}): "
                        f"hydrology={hydro}, substrate={substrate}"
                    )
        except Exception:
            continue

    pct_ok = ((n_tested - n_conflict) / n_tested * 100) if n_tested else 0
    tolerance_pct = 5
    status = "PASS" if (100 - pct_ok) <= tolerance_pct else ("WARN" if pct_ok >= 80 else "FAIL")
    score = pct_ok / 100
    detail = (f"{n_tested - n_conflict}/{n_tested} wetlands on compatible substrate ({pct_ok:.1f}%), "
              f"conflicts: {n_conflict}")
    if conflict_details:
        detail += "\n" + "\n".join(conflict_details)

    results.append(TestResult("T-GEO-03", "Hydrologie vs. VMB", "GEO", status,
                              score=score, details=detail,
                              n_tested=n_tested, n_passed=n_tested-n_conflict, n_failed=n_conflict))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-GEO-03", "Hydrologie vs. VMB", "GEO", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-ECO-05: Rybi habitat (Fish habitat near sites)
# =========================================================================
print("T-ECO-05: Rybi habitat ...")
try:
    max_water_distance_m = 300

    water_geoms_all = []
    for _, row in dibavod_water.iterrows():
        if row.geometry and not row.geometry.is_empty:
            water_geoms_all.append(row.geometry)

    n_tested = 0
    n_near_water = 0
    fish_details = []

    if water_geoms_all:
        water_geom = unary_union(water_geoms_all)

        for props, geom in site_shapes:
            if geom is None:
                continue
            pt = geom.centroid if geom.geom_type != "Point" else geom

            # Use boundary distance for polygons
            d_deg = pt.distance(water_geom)
            dist_m = d_deg * 111_000 * math.cos(math.radians(pt.y))

            n_tested += 1
            near = dist_m <= max_water_distance_m
            if near:
                n_near_water += 1
            fish_details.append(
                f"  {props.get('id','?')}: {dist_m:.0f}m to water body [{'OK' if near else 'FAR'}]"
            )

    pct = (n_near_water / n_tested * 100) if n_tested else 0
    status = "PASS" if pct >= 50 else ("WARN" if pct >= 30 else "INFO")
    score = pct / 100
    detail = (f"{n_near_water}/{n_tested} sites within {max_water_distance_m}m "
              f"of water bodies ({pct:.0f}%)")
    detail += "\nNote: Trebonsko pond landscape -- high water body density expected"
    detail += "\n" + "\n".join(fish_details)

    results.append(TestResult("T-ECO-05", "Rybi habitat", "ECO", status,
                              score=score, details=detail,
                              n_tested=n_tested, n_passed=n_near_water, n_failed=n_tested-n_near_water))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-ECO-05", "Rybi habitat", "ECO", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-PHY-08: Reka vs. vodni plocha (rivers crossing paleolakes)
# =========================================================================
print("T-PHY-08: Reka vs. vodni plocha ...")
try:
    # Rivers should NOT pass through paleolakes -- in mesolithic there were no
    # artificial ponds/channels. A river enters a lake and exits it, but does
    # not run across it. We flag rivers with >20% of their length inside a
    # paleolake polygon as anomalies.
    # Exception: DEM-reconstructed rivers (source contains 'DEM flow') are
    # EXPECTED inside sediment/peat paleolakes — they represent reconstructed
    # valley-bottom channels. Only flag DIBAVOD-sourced rivers.
    CROSSING_THRESHOLD = 0.20  # 20% of river length inside lake = problem

    lake_geoms = [shape(f["geometry"]) for f in paleolakes["features"]
                  if f["geometry"]]
    if lake_geoms:
        lake_union = unary_union(lake_geoms)

        n_rivers_total = 0
        n_crossing = 0
        n_dem_ok = 0
        crossing_details = []

        for props, geom in river_shapes:
            if not geom or geom.is_empty:
                continue
            # Skip DEM-reconstructed rivers — they are intentionally in paleolakes
            source = props.get("source", "") or ""
            if "DEM flow" in source:
                n_dem_ok += 1
                continue
            n_rivers_total += 1
            if geom.intersects(lake_union):
                inter = geom.intersection(lake_union)
                ratio = inter.length / geom.length if geom.length > 0 else 0
                if ratio > CROSSING_THRESHOLD:
                    n_crossing += 1
                    name = props.get("name", "?")
                    rid = props.get("id", "?")
                    length_m = geom.length * 111_000  # rough deg->m
                    crossing_details.append(
                        f"  {rid} ({name}): {ratio:.0%} inside paleolake, "
                        f"~{length_m:.0f}m total")

        pct_ok = ((n_rivers_total - n_crossing) / n_rivers_total * 100
                  ) if n_rivers_total else 100
        status = "PASS" if pct_ok >= 95 else ("WARN" if pct_ok >= 80 else "FAIL")
        score = pct_ok / 100

        detail = (f"{n_crossing}/{n_rivers_total} DIBAVOD rivers cross paleolakes "
                  f"(>{CROSSING_THRESHOLD:.0%} inside) -- {pct_ok:.1f}% OK")
        detail += f"\nDEM-reconstructed rivers (skipped): {n_dem_ok}"
        if crossing_details:
            detail += "\nAnomalies (top 15):\n"
            detail += "\n".join(crossing_details[:15])

        results.append(TestResult("T-PHY-08", "Reka vs. vodni plocha", "PHY",
                                  status, score=score, details=detail,
                                  n_tested=n_rivers_total,
                                  n_passed=n_rivers_total - n_crossing,
                                  n_failed=n_crossing))
    else:
        results.append(TestResult("T-PHY-08", "Reka vs. vodni plocha", "PHY",
                                  "SKIP", details="No paleolake geometries"))
    print(f"  {status}: {n_crossing} DIBAVOD rivers crossing paleolakes")
except Exception as e:
    results.append(TestResult("T-PHY-08", "Reka vs. vodni plocha", "PHY",
                              "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-PHY-09: Detekce umělých kanálů (artificial channel detection)
# =========================================================================
print("T-PHY-09: Umele kanaly ...")
try:
    # Artificial channels built for fishpond management (16th century+)
    # should not exist in mesolithic landscape. Detection heuristic:
    # 1. River name contains known artificial keywords (Odlehčovač, Nová řeka,
    #    Stoková, Nápustka, Strouha, Kanál, Svodnice, Výpust)
    # 2. River geometry is suspiciously straight (low sinuosity < 1.05)
    #    AND runs through or adjacent to multiple paleolakes/ponds
    ARTIFICIAL_KEYWORDS = [
        "odleh", "nápust", "výpust", "stokov", "kanál", "kanal",
        "nová řeka", "nova reka", "strouha", "svodnic", "přivaděč",
        "privadec", "odvod", "náhon", "nahon",
    ]

    n_total = 0
    n_artificial = 0
    n_dem_skipped = 0
    artificial_details = []

    for props, geom in river_shapes:
        if not geom or geom.is_empty:
            continue
        # Skip DEM-reconstructed rivers — their low sinuosity is from raster
        # resolution, not artificial origin
        source = props.get("source", "") or ""
        if "DEM flow" in source:
            n_dem_skipped += 1
            continue
        n_total += 1

        name = (props.get("name") or "").lower()
        rid = props.get("id", "?")
        is_artificial = False
        reason = ""

        # Check 1: name-based detection
        for kw in ARTIFICIAL_KEYWORDS:
            if kw in name:
                is_artificial = True
                reason = f"name contains '{kw}'"
                break

        # Check 2: sinuosity-based detection (only for rivers >200m)
        if not is_artificial and geom.length * 111_000 > 200:
            # sinuosity = actual length / straight-line distance
            # Handle both LineString and MultiLineString
            if geom.geom_type == "LineString":
                coords = list(geom.coords)
            elif geom.geom_type == "MultiLineString":
                coords = list(geom.geoms[0].coords) + list(geom.geoms[-1].coords)
            else:
                coords = []
            if len(coords) >= 2:
                start = Point(coords[0])
                end = Point(coords[-1])
                straight = start.distance(end)
                if straight > 0:
                    sinuosity = geom.length / straight
                    # Very straight AND crosses paleolake = likely artificial
                    if sinuosity < 1.05 and lake_geoms:
                        inter = geom.intersection(lake_union)
                        in_lake_ratio = (inter.length / geom.length
                                         if geom.length > 0 else 0)
                        if in_lake_ratio > 0.3:
                            is_artificial = True
                            reason = (f"sinuosity={sinuosity:.2f}, "
                                      f"{in_lake_ratio:.0%} in paleolake")

        if is_artificial:
            n_artificial += 1
            length_m = geom.length * 111_000
            artificial_details.append(
                f"  {rid} ({props.get('name','?')}): {reason}, "
                f"~{length_m:.0f}m")

    pct_ok = ((n_total - n_artificial) / n_total * 100) if n_total else 100
    # This is informational -- artificial channels are a data quality issue
    # to be fixed in the pipeline, not a hard fail
    status = "PASS" if n_artificial == 0 else (
        "WARN" if n_artificial <= 10 else "FAIL")
    score = pct_ok / 100

    detail = (f"{n_artificial}/{n_total} DIBAVOD rivers flagged as likely artificial "
              f"channels")
    detail += f"\nDEM-reconstructed rivers (skipped): {n_dem_skipped}"
    if artificial_details:
        detail += "\nFlagged (top 20):\n"
        detail += "\n".join(artificial_details[:20])

    results.append(TestResult("T-PHY-09", "Umele kanaly", "PHY",
                              status, score=score, details=detail,
                              n_tested=n_total,
                              n_passed=n_total - n_artificial,
                              n_failed=n_artificial))
    print(f"  {status}: {n_artificial} likely artificial channels")
except Exception as e:
    results.append(TestResult("T-PHY-09", "Umele kanaly", "PHY",
                              "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# T-SUPP-01: Terrain coverage & integrity
# =========================================================================
print("T-SUPP-01: Terrain coverage & integrity ...")
try:
    all_terrain = [shape(f["geometry"]) for f in terrain["features"] if f["geometry"]]
    terrain_union = unary_union(all_terrain)

    bbox_area = BBOX.area
    covered = terrain_union.intersection(BBOX).area
    coverage_pct = (covered / bbox_area * 100)

    subtype_counts = Counter(f["properties"]["terrain_subtype_id"]
                             for f in terrain["features"])
    subtype_areas = defaultdict(float)
    for f in terrain["features"]:
        if f["geometry"]:
            subtype_areas[f["properties"]["terrain_subtype_id"]] += shape(f["geometry"]).area

    detail = f"Terrain coverage: {coverage_pct:.1f}% of bbox"
    detail += f"\nTotal features: {len(terrain['features'])}"
    detail += f"\nBiotope-assigned features: {len(terrain_bio['features'])}"
    detail += f"\nRivers: {len(rivers_gj['features'])}"
    detail += f"\nEcotones: {len(ecotones_gj['features'])}"
    detail += f"\nSites: {len(sites_gj['features'])}"
    detail += f"\nPaleolakes: {len(paleolakes['features'])}"
    detail += "\n\nSubtype distribution:"
    for sid in sorted(subtype_counts.keys()):
        detail += f"\n  {sid}: {subtype_counts[sid]} features"

    status = "PASS" if coverage_pct >= 80 else ("WARN" if coverage_pct >= 50 else "FAIL")
    score = min(1.0, coverage_pct / 100)

    results.append(TestResult("T-SUPP-01", "Terrain coverage", "SUPP", status,
                              score=score, details=detail,
                              n_tested=len(terrain["features"])))
    print(f"  {status}: {detail.split(chr(10))[0]}")
except Exception as e:
    results.append(TestResult("T-SUPP-01", "Terrain coverage", "SUPP", "ERROR", details=str(e)))
    print(f"  ERROR: {e}")


# =========================================================================
# SKIPPED TESTS (with reasons)
# =========================================================================
skipped_tests = [
    ("T-PHY-03", "Jezero bez povodi", "PHY",
     "Vyzaduje flow accumulation raster -- nutny preprocessing DEM (neni v processed data)"),
    ("T-PHY-04", "Ricni sit vs. substrat", "PHY",
     "Trebonsko = piskovce, ne kras -> nizke riziko false positive"),
    ("T-PHY-05", "Biotopova hranice vs. teren", "PHY",
     "Oba parametry SPECULATION -- test zatim nekalibrovan"),
    ("T-GEO-05", "DEM kontrolni body", "GEO",
     "control_points=[] (TODO) -- chybi geodeticke body pro Trebonsko"),
    ("T-ECO-03", "Habitat jelena", "ECO",
     "Vyzaduje AMCR data s faunalni kategorii (jeleni kosti) -- v datech neni fauna flag"),
    ("T-ECO-06", "Liska v dosahu", "ECO",
     "Vyzaduje AMCR data s dolozenou liskou -- v datech neni"),
    ("T-ECO-09", "Bobri habitat", "ECO",
     "Vyzaduje vypocet spadu toku z DEM + identifikaci luznich biotopu"),
    ("T-ECO-10", "Tukovy problem", "ECO",
     "Zavisi na ACTIVITY_GRAPH + KB vrstve 4-5 -- zatim neexistuje"),
    ("T-ECO-11", "Celorocni pokryti", "ECO",
     "Zavisi na ACTIVITY_GRAPH + RESOURCE data -- zatim neexistuje"),
    ("T-ARCH-01", "Catchment uplnost", "ARCH",
     "Zavisi na ACTIVITY_GRAPH -- zatim neexistuje"),
    ("T-ARCH-03", "Vyhledova poloha", "ARCH",
     "Vyzaduje viewshed analyzu (DEM line-of-sight)"),
    ("T-ARCH-05", "Biotop vs. sezona", "ARCH",
     "Zavisi na KB sezonnich modifikatorech -- zatim neexistuji"),
    ("T-ARCH-06", "Hustota vs. produktivita", "ARCH",
     "Zavisi na T-ARCH-07 (detekcni bias) + KB produktivity"),
    ("T-ARCH-07", "Detekcni bias", "ARCH",
     "Vyzaduje AMCR pocet akci per grid bunku -- v aktualnim exportu neni"),
    ("T-ARCH-08", "Proxy populace", "ARCH",
     "Zavisi na KB vrstve 4-5 + izotopove literature"),
    ("T-ARCH-09", "Shlukovani lokalit", "ARCH",
     "Zavisi na T-ARCH-07 + vyzaduje scipy (neni nainstalovano)"),
    ("T-GEO-02", "Flint vs. geologie", "GEO",
     "Vyzaduje KB vocabulary s flint_availability per substrat -- nedefinovano pro CZ"),
    ("T-ECO-04", "Produktivita vs. jelen", "ECO",
     "Zavisi na KB vrstve 4 (populace) -- zatim neexistuje"),
]

for tid, name, cat, reason in skipped_tests:
    results.append(TestResult(tid, name, cat, "SKIP", details=reason))

# =========================================================================
# Generate Report
# =========================================================================
dem.close()

print("\n" + "="*70)
print("VALIDATION REPORT -- Trebonsko (CZ)")
print("="*70)

results.sort(key=lambda r: r.test_id)

status_counts = Counter(r.status for r in results)
run_results = [r for r in results if r.status not in ("SKIP", "ERROR")]

print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"Total tests defined: 33")
print(f"Tests executed: {len(run_results)}")
print(f"Tests skipped: {status_counts.get('SKIP', 0)}")
print(f"")
print(f"  PASS: {status_counts.get('PASS', 0)}")
print(f"  WARN: {status_counts.get('WARN', 0)}")
print(f"  FAIL: {status_counts.get('FAIL', 0)}")
print(f"  INFO: {status_counts.get('INFO', 0)}")
print(f"  ERROR: {status_counts.get('ERROR', 0)}")

if run_results:
    scores = [r.score for r in run_results if r.score is not None]
    if scores:
        print(f"\nAggregate score: {np.mean(scores):.3f} (mean of {len(scores)} scored tests)")

for cat in ["PHY", "ECO", "ARCH", "GEO", "SUPP"]:
    cat_results = [r for r in results if r.category == cat]
    if not cat_results:
        continue
    print(f"\n{'---'*23}")
    cat_names = {"PHY": "Fyzikalni", "ECO": "Ekologicke", "ARCH": "Archeologicke",
                 "GEO": "Geologicke", "SUPP": "Doplnkove"}
    print(f"  {cat_names.get(cat, cat)} testy")
    print(f"{'---'*23}")
    for r in cat_results:
        icon = {"PASS": "[OK]", "WARN": "[!!]", "FAIL": "[XX]", "SKIP": "[--]",
                "INFO": "[ii]", "ERROR": "[ER]"}
        score_str = f" [{r.score:.2f}]" if r.score is not None else ""
        print(f"  {icon.get(r.status, '[??]')} {r.test_id}: {r.name} -- {r.status}{score_str}")
        if r.status != "SKIP":
            for line in r.details.split("\n")[:3]:
                print(f"      {line}")
        else:
            print(f"      Reason: {r.details[:100]}")

# Save JSON report
report = {
    "meta": {
        "region": "Trebonsko (CZ)",
        "date": datetime.now().isoformat(),
        "tests_total": 33,
        "tests_executed": len(run_results),
        "tests_skipped": status_counts.get("SKIP", 0),
    },
    "summary": dict(status_counts),
    "aggregate_score": round(np.mean(scores), 3) if scores else None,
    "results": [r.to_dict() for r in results],
}

report_path = PROC / "validation_report_cz.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n{'='*70}")
print(f"Report saved: {report_path}")
print(f"{'='*70}")

"""
Generate Polabí archaeological_sites GeoJSON from published literature.

Why this script exists:
  AMCR OAI-PMH `lokalita` endpoint returns mesolithic records WITHOUT direct
  geometry (only PIAN spatial-unit references). Resolving PIANs to coordinates
  requires harvesting the entire `pian` set (hundreds of MB) and joining —
  a separate task deferred to M4. In the meantime, this script provides a
  curated reference subset based on standard Czech Mesolithic literature.

Output:
  data/processed/polabi/sites_polabi.geojson  (Point geometries, EPSG:4326)
  → consumed by 06_import_supabase_polabi.py → archaeological_sites table

Coordinates note:
  Published Czech Mesolithic literature typically reports findspots at
  cadastral-area resolution, not GPS. Coordinates here are CENTROIDS of the
  cadastral village/town referenced in the source; certainty is INFERENCE.
  For research-grade work, consult the AMCR digiarchiv directly.

Sources:
  - Vencl, S. (ed.) 1990, 2006: Mezolit Severních Čech / Mezolit jižních Čech
  - Sklenář, K. 1992: Archeologické nálezy v Čechách do roku 1870
  - Pokorný, P. et al. 2010, 2012: Hrabanov pylový profil
  - Lečbych, M. 2018: Polabské mezolitické naleziště (recent overview)

Usage:
    python pipeline/02f_polabi_archaeological_literature.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "processed" / "polabi" / "sites_polabi.geojson"

# Polabí bbox (must match 04_terrain_polabi.py)
BBOX_WGS84 = {"south": 49.70, "north": 50.30, "west": 14.45, "east": 15.75}


# ---------------------------------------------------------------------------
# Curated literature reference set
# ---------------------------------------------------------------------------
#
# Format:
#   id           — stable identifier with "as_pl_lit_" prefix (literature subset)
#   name         — locality name
#   lat, lon     — centroid of cadastral area / known findspot
#   period       — typically "mezolit" or "epipaleolit/mezolit"
#   site_type    — class of evidence (rozptyl_štípaná, sídliště, depo)
#   notes        — short context from cited source
#   source       — bibliographic reference
#
# Decision rules:
#   1. Only sites WITH some published evidence in the cited works
#   2. Coordinates rounded to 4 decimals (~10 m) — accuracy of cadastral centre
#   3. All marked INFERENCE certainty (cadastral-level only, not GPS)
#   4. If the same locality appears in multiple sources, prefer Vencl 2006

POLABI_SITES = [
    {
        "id": "as_pl_lit_001",
        "name": "Velim",
        "lat": 50.0670, "lon": 15.1110,
        "period": "epipaleolit/mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Multi-perioda lokalita Velim-Skalka; mezolitická složka v ranně-holocenních terasách",
        "source": "Vencl, S. 2006: Mezolit jižních Čech (přesah do středočeské oblasti); Sklenář 1992",
    },
    {
        "id": "as_pl_lit_002",
        "name": "Sadská",
        "lat": 50.1350, "lon": 14.9890,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Povrchové sběry kamenných artefaktů z Polabské nížiny v okolí Sadské",
        "source": "Vencl 2006; Lečbych 2018",
    },
    {
        "id": "as_pl_lit_003",
        "name": "Hradišťko u Sadské",
        "lat": 50.1180, "lon": 15.0190,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Sběry mikrolitů na štěrkové terase Labe",
        "source": "Vencl 2006",
    },
    {
        "id": "as_pl_lit_004",
        "name": "Toušeň",
        "lat": 50.1800, "lon": 14.6870,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Niva Labe; mezolitické artefakty z písčin terasy",
        "source": "Sklenář 1992; Vencl 2006",
    },
    {
        "id": "as_pl_lit_005",
        "name": "Brandýs nad Labem",
        "lat": 50.1830, "lon": 14.6650,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Mezolitická vrstva v nivě Labe; písčité terasy",
        "source": "Sklenář 1992",
    },
    {
        "id": "as_pl_lit_006",
        "name": "Konětopy",
        "lat": 50.2260, "lon": 14.5670,
        "period": "mezolit",
        "site_type": "sídliště",
        "notes": "Mezolitické sídliště na písčitém ostrohu nad nivou Labe",
        "source": "Vencl 2006; Lečbych 2018",
    },
    {
        "id": "as_pl_lit_007",
        "name": "Lysá nad Labem (Hrabanov vicinity)",
        "lat": 50.2050, "lon": 14.8330,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Mezolitické nálezy v okolí Hrabanovského pylového profilu (boreal/atlantic)",
        "source": "Pokorný et al. 2012; Vencl 2006",
    },
    {
        "id": "as_pl_lit_008",
        "name": "Nymburk-Drahelice",
        "lat": 50.1830, "lon": 15.0450,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Sběry mikrolitů z písčité terasy Labe u Nymburka",
        "source": "Vencl 2006; AMCR digiarchiv",
    },
    {
        "id": "as_pl_lit_009",
        "name": "Záboří nad Labem",
        "lat": 49.9910, "lon": 15.3460,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Mezolitická vrstva v nivě Labe východně od Kolína",
        "source": "Sklenář 1992; Vencl 2006",
    },
    {
        "id": "as_pl_lit_010",
        "name": "Kostelec nad Labem",
        "lat": 50.2190, "lon": 14.5870,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Mezolitické nálezy v nivě Labe u Kostelce",
        "source": "Sklenář 1992",
    },
    {
        "id": "as_pl_lit_011",
        "name": "Poděbrady-Polabec",
        "lat": 50.1410, "lon": 15.1130,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Mezolitické sběry na terase Labe u Poděbrad (oblast Polabec)",
        "source": "Vencl 2006",
    },
    {
        "id": "as_pl_lit_012",
        "name": "Český Brod (okolí)",
        "lat": 50.0750, "lon": 14.8600,
        "period": "mezolit",
        "site_type": "rozptyl_štípaná",
        "notes": "Mezolitické nálezy v jižním okraji Polabské nížiny u Českého Brodu",
        "source": "Sklenář 1992",
    },
]


# ---------------------------------------------------------------------------
# Build & save GeoJSON
# ---------------------------------------------------------------------------

def in_bbox(lat: float, lon: float) -> bool:
    return (BBOX_WGS84["west"] <= lon <= BBOX_WGS84["east"] and
            BBOX_WGS84["south"] <= lat <= BBOX_WGS84["north"])


def main():
    print("=" * 60)
    print("Mezolit2 — Polabí archaeological_sites (literature)")
    print("=" * 60)
    print(f"  Bbox: {BBOX_WGS84}")
    print(f"  Output: {OUT}")
    print()

    features = []
    skipped_outside = 0
    for s in POLABI_SITES:
        if not in_bbox(s["lat"], s["lon"]):
            print(f"  WARN: {s['id']} ({s['name']}) at "
                  f"({s['lat']}, {s['lon']}) outside bbox — skipped")
            skipped_outside += 1
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            "properties": {
                "id": s["id"],
                "name": s["name"],
                "region": "polabi",
                "period": s["period"],
                "site_type": s["site_type"],
                "elevation_m": None,        # could be enriched from DEM later
                "distance_to_water_m": None, # could be enriched from rivers later
                "ident_cely": None,         # not from AMCR
                "katastr": None,
                "certainty": "INFERENCE",   # cadastral-level only, see notes
                "source": s["source"],
                "notes": s["notes"],
            },
        })
        print(f"  OK: {s['id']:18s} {s['name']:34s} ({s['lat']:.4f}, {s['lon']:.4f})")

    print(f"\n  Included: {len(features)} sites; skipped outside bbox: {skipped_outside}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "type": "FeatureCollection",
            "name": "sites_polabi",
            "features": features,
        }, f, ensure_ascii=False, indent=2)
    size_kb = OUT.stat().st_size / 1024
    print(f"  Saved: {OUT.name} ({size_kb:.1f} KB)")
    print()
    print("Next: re-run pipeline/06_import_supabase_polabi.py to load into archaeological_sites table")


if __name__ == "__main__":
    main()

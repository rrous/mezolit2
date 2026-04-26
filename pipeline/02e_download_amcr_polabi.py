"""
Download AMCR (Archaeological Map of Czech Republic) mesolithic localities for Polabí.

This is the missing AMCR step from 02d_download_polabi.py — adds the 6th data source
(after DEM / DIBAVOD / CGS / VMB) so that archaeological_sites can be populated.

Reuses download_amcr() + _parse_amcr_records() from 02c by import + bbox override.

Output: data/raw/polabi/amcr/amcr_mezolit_lokality.geojson
        data/raw/polabi/amcr/amcr_lokality_raw.xml

Requires AMCR_USERNAME + AMCR_PASSWORD in .env (already present per Mezolit2 memory).

Usage:
    python pipeline/02e_download_amcr_polabi.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# ── Polabí target ────────────────────────────────────────────────────────────
POLABI_BBOX = {"south": 49.70, "north": 50.30, "west": 14.45, "east": 15.75}
POLABI_RAW_DIR = ROOT / "data" / "raw" / "polabi"
POLABI_AMCR_DIR = POLABI_RAW_DIR / "amcr"


def _import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    print("=" * 60)
    print("Mezolit2 — AMCR download (Polabí)")
    print("=" * 60)
    print(f"  BBox: {POLABI_BBOX}")
    print(f"  Output: {POLABI_AMCR_DIR}")

    # Load 02c module so we can call its download_amcr() with overrides
    cz_mod = _import_module(ROOT / "pipeline" / "02c_download_cz.py",
                            "_cz_download_module")

    # Override 02c's globals to point at Polabí paths/bbox
    cz_mod.BBOX_WGS84 = POLABI_BBOX
    cz_mod.OUT_DIR = POLABI_RAW_DIR
    POLABI_AMCR_DIR.mkdir(parents=True, exist_ok=True)

    # ensure_dir helper in 02c does (OUT_DIR / name).mkdir(...) — overriding
    # OUT_DIR makes everything land under data/raw/polabi/
    out_path = cz_mod.download_amcr()
    print(f"\n  Result: {out_path}")
    if out_path.exists():
        import json
        with open(out_path, encoding="utf-8") as f:
            gj = json.load(f)
        print(f"  Features: {len(gj['features'])}")
        if gj["features"]:
            with_geom = sum(1 for f in gj["features"] if f.get("geometry"))
            no_geom = len(gj["features"]) - with_geom
            print(f"    with coords: {with_geom}")
            print(f"    no coords (PIAN-only): {no_geom}")
            # Sample
            for f in gj["features"][:3]:
                p = f["properties"]
                print(f"    - {p.get('ident_cely')}: {p.get('katastr')} "
                      f"({p.get('typ_lokality') or '?'})")

    print("\nNext: rerun 04_terrain_polabi.py (will pick up sites if process step added)")
    print("      OR add sites→GeoJSON step + rerun 06_import_supabase_polabi.py")


if __name__ == "__main__":
    main()

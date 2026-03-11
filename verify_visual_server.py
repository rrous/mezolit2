#!/usr/bin/env python3
"""
Mezolit2 — Lokální API + HTTP server pro verify_visual.html

API endpointy:
  GET /api/{vrstva}?bbox=W,S,E,N   — GeoJSON filtrovaný viditelným bboxem
  Vrstvy: terrain, biotopes, rivers, coastline, ecotones, sites

Použití:
    python verify_visual_server.py
    python verify_visual_server.py --port 9000

Stiskni Ctrl+C pro zastavení serveru.
"""

import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import webbrowser
from urllib.parse import urlparse, parse_qs

# ── Výchozí port ──────────────────────────────────────────────────────────────
DEFAULT_PORT = 8765

# ── Kořen projektu (adresář tohoto skriptu) ───────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ── Mapování vrstva → GeoJSON soubor ─────────────────────────────────────────
GEOJSON_PATHS = {
    'terrain':   'data/processed/terrain_features.geojson',
    'biotopes':  'data/processed/terrain_features_with_biotopes.geojson',
    'rivers':    'data/processed/rivers_yorkshire.geojson',
    'coastline': 'data/processed/coastline_6200bce.geojson',
    'ecotones':  'data/processed/ecotones.geojson',
    'sites':     'data/processed/sites.geojson',
}

# ── In-memory cache (načítá každý soubor jen jednou) ─────────────────────────
_CACHE: dict = {}


def _load_geojson(layer: str) -> dict:
    """Načte a cachuje GeoJSON soubor pro danou vrstvu."""
    if layer not in _CACHE:
        path = os.path.join(PROJECT_ROOT, GEOJSON_PATHS[layer])
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _CACHE[layer] = data
        n = len(data.get('features', []))
        print(f'  [cache] {layer}: {n} features načteno z {GEOJSON_PATHS[layer]}')
    return _CACHE[layer]


def _iter_coords(geom: dict):
    """Yield all (x, y) souřadnice z GeoJSON geometrie."""
    t = geom.get('type', '')
    coords = geom.get('coordinates')
    if not coords:
        if t == 'GeometryCollection':
            for g in geom.get('geometries', []):
                yield from _iter_coords(g)
        return
    if t == 'Point':
        yield coords[:2]
    elif t in ('MultiPoint', 'LineString'):
        for c in coords:
            yield c[:2]
    elif t in ('MultiLineString', 'Polygon'):
        for ring in coords:
            for c in ring:
                yield c[:2]
    elif t == 'MultiPolygon':
        for poly in coords:
            for ring in poly:
                for c in ring:
                    yield c[:2]


def _feature_bbox(feature: dict):
    """Vrátí (minx, miny, maxx, maxy) pro feature, nebo None."""
    geom = feature.get('geometry')
    if not geom:
        return None
    try:
        xs, ys = [], []
        for x, y in _iter_coords(geom):
            xs.append(x)
            ys.append(y)
        if not xs:
            return None
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def _overlaps(fb: tuple, qb: tuple) -> bool:
    """True pokud se feature bbox fb překrývá s query bbox qb. Oba = (minx,miny,maxx,maxy)."""
    return not (fb[2] < qb[0] or qb[2] < fb[0] or fb[3] < qb[1] or qb[3] < fb[1])


# ── HTTP handler ───────────────────────────────────────────────────────────────

class ApiHandler(http.server.SimpleHTTPRequestHandler):
    """Handler — loguje chyby + obsluhuje /api/ endpointy."""

    def log_message(self, fmt, *args):
        status = str(args[1]) if len(args) > 1 else ''
        if not status.startswith(('2', '3')):
            super().log_message(fmt, *args)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/'):
            self._handle_api(parsed)
        else:
            super().do_GET()

    def _handle_api(self, parsed: 'ParseResult'):
        layer = parsed.path[5:].rstrip('/')   # strip '/api/'
        if layer not in GEOJSON_PATHS:
            self.send_error(404, f'Neznámá vrstva: {layer}. Dostupné: {", ".join(GEOJSON_PATHS)}')
            return

        # Parsuj bbox: W,S,E,N  →  (minx, miny, maxx, maxy)
        qs = parse_qs(parsed.query)
        bbox = None
        if 'bbox' in qs:
            try:
                w, s, e, n = (float(v) for v in qs['bbox'][0].split(','))
                bbox = (w, s, e, n)
            except (ValueError, IndexError):
                bbox = None

        # Načti data
        try:
            data = _load_geojson(layer)
        except FileNotFoundError:
            self.send_error(404, f'Datový soubor pro vrstvu "{layer}" nenalezen')
            return

        # Filtruj podle bbox
        features = data.get('features', [])
        if bbox:
            filtered = []
            for f in features:
                fb = _feature_bbox(f)
                if fb is None or _overlaps(fb, bbox):
                    filtered.append(f)
            features = filtered

        # Odpověď
        body = json.dumps({'type': 'FeatureCollection', 'features': features},
                          ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Mezolit2 — API + viewer server')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f'Port (výchozí: {DEFAULT_PORT})')
    parser.add_argument('--no-browser', action='store_true',
                        help='Neotvírej prohlížeč automaticky')
    args = parser.parse_args()

    port = args.port
    url = f'http://localhost:{port}/verify_visual.html'

    os.chdir(PROJECT_ROOT)

    try:
        httpd = socketserver.TCPServer(('', port), ApiHandler)
    except OSError as e:
        print(f'[!] Port {port} je obsazený: {e}')
        print(f'    Zkus: python verify_visual_server.py --port {port + 1}')
        sys.exit(1)

    httpd.allow_reuse_address = True

    # Pre-cache velké vrstvy
    print('━' * 58)
    print('  Mezolit2 — Vizuální verifikace + API  (v7)')
    print(f'  Viewer: {url}')
    print(f'  API:    http://localhost:{port}/api/{{vrstva}}?bbox=W,S,E,N')
    print(f'  Vrstvy: {", ".join(GEOJSON_PATHS)}')
    print('  Zastav: Ctrl+C')
    print('━' * 58)

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n\nServer zastaven.')
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()

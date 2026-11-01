"""Isolated UI-test API. Synthetic data only; never connects to the project DB.

Pair with Vite --mode ui-test and GIS_DEV_API_TARGET=http://127.0.0.1:8015.
The frontend must display its prominent synthetic-data banner.
"""
import json
import math
from copy import deepcopy
from time import sleep
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


def feature(pk, name, category, geometry):
    return {"type": "Feature", "id": pk, "geometry": geometry, "properties": {
        "name": name, "area_id": 1, "area_name": "TEST boundary - synthetic", "category_id": category,
        "category_name": "TEST public park" if category == 1 else "TEST community garden", "area_size": "1.2500",
        "facilities": "TEST benches; not real facilities", "description": "Synthetic browser-test record. Not a real park.",
        "latitude": None, "longitude": None,
    }}


PARKS = [feature(1, "TEST Alpha park", 1, {"type": "Point", "coordinates": [101.60, 3.08]}),
         feature(2, "TEST Beta garden", 2, {"type": "Point", "coordinates": [101.64, 3.11]}),
         feature(3, "TEST Polygon park", 1, {"type": "Polygon", "coordinates": [
             [[101.55, 3.10], [101.58, 3.10], [101.58, 3.12], [101.55, 3.12], [101.55, 3.10]]]}),
         feature(4, 'TEST <img src=x onerror="alert(1)"> literal text', 2, {"type": "Point", "coordinates": [101.62, 3.04]})]
BOUNDARY = {"type": "Feature", "id": 1, "properties": {"area_name": "TEST boundary - synthetic", "area_type": "test"},
            "geometry": {"type": "Polygon", "coordinates": [
                [[101.50, 3.00], [101.70, 3.00], [101.70, 3.17], [101.50, 3.17], [101.50, 3.00]]]}}


def intersects(feature, bbox):
    coordinates = feature["geometry"]["coordinates"]
    points = [coordinates] if feature["geometry"]["type"] == "Point" else coordinates[0]
    xs, ys = zip(*points)
    west, south, east, north = bbox
    return min(xs) <= east and max(xs) >= west and min(ys) <= north and max(ys) >= south


def nearby_records(longitude, latitude, radius):
    records = []
    for original in PARKS:
        record = deepcopy(original)
        geometry = record['geometry']
        x, y = geometry['coordinates'] if geometry['type'] == 'Point' else (
            min(101.58, max(101.55, longitude)), min(3.12, max(3.10, latitude)))
        distance = math.hypot((x - longitude) * 111000 * math.cos(math.radians(latitude)), (y - latitude) * 111000)
        if distance <= radius:
            record['properties']['distance_m'] = distance
            records.append(record)
    return sorted(records, key=lambda record: (record['properties']['distance_m'], record['id']))


def coverage_fixture(longitude, latitude, radius):
    # Deliberately synthetic circle/area fixtures for UI states, NOT PostGIS QA.
    bands = []
    for distance in sorted({500, 1000, 2000, radius}):
        ring = [[longitude + distance * math.cos(n * math.pi / 64) / (111000 * math.cos(math.radians(latitude))),
                 latitude + distance * math.sin(n * math.pi / 64) / 111000] for n in range(128)]
        ring.append(ring[0])
        bands.append({'type': 'Feature', 'id': distance, 'geometry': {'type': 'Polygon', 'coordinates': [ring]},
                      'properties': {'radius_m': distance, 'selected': distance == radius, 'coverage_area_m2': math.pi * distance ** 2}})
    records = nearby_records(longitude, latitude, radius)
    points = sum(record['geometry']['type'] == 'Point' for record in records)
    polygons = len(records) - points
    zone_area = math.pi * radius ** 2
    measured = polygons > 0 or not records
    # Fixed test-only footprint measure; never a measured park area.
    area_m2 = min(zone_area / 4, 12500) if polygons else 0
    return {'method': 'distance_buffer', 'radius_m': radius,
        'coverage': {'type': 'FeatureCollection', 'features': bands},
        'metrics': {'population_covered': None, 'population_percentage': None, 'population_status': 'unavailable',
            'green_spaces_reached': len(records), 'change_from_500_m': len(records) - len(nearby_records(longitude, latitude, 500)),
            'total_accessible_area_ha': area_m2 / 10000 if measured else None,
            'accessible_area_percentage': area_m2 / zone_area * 100 if measured else None,
            'coverage_area_ha': zone_area / 10000, 'point_records_without_footprint': points,
            'area_status': 'complete' if not points else 'partial' if measured else 'unavailable'},
        'green_spaces': {'type': 'FeatureCollection', 'features': records, 'count': len(records), 'limited': False},
        'limitations': ['Synthetic UI fixture only. Not PostGIS or actual park measurements.']}


def dashboard_fixture(area, category):
    # Illustrative numbers for UI states ONLY, not spatial measurements.
    areas = [{'area_id': 1, 'area_name': 'TEST Petaling', 'area_type': 'District'},
             {'area_id': 2, 'area_name': 'TEST West', 'area_type': 'Test zone'},
             {'area_id': 3, 'area_name': 'TEST East', 'area_type': 'Test zone'}]
    categories = [{'category_id': 1, 'category_name': 'TEST public park'},
                  {'category_id': 2, 'category_name': 'TEST community garden'},
                  {'category_id': 3, 'category_name': 'TEST empty category'},
                  {'category_id': 777, 'category_name': 'TEST service failure'},
                  {'category_id': 888, 'category_name': 'TEST delayed response'}]
    selected = [p for p in PARKS if category is None or p['properties']['category_id'] == category]
    def metrics(area_id):
        records = [p for p in selected if area_id == 1 or (p['id'] in (1, 3) if area_id == 2 else p['id'] in (2, 4))]
        points = sum(p['geometry']['type'] == 'Point' for p in records)
        zone = 1000 if area_id == 1 else 500
        percent = 60 if selected else 0
        return {'space_count': len(records), 'point_count': points,
            'green_area_ha': None if records and points == len(records) else 1.25 if records else 0,
            'area_status': 'complete' if not points else 'unavailable' if points == len(records) else 'partial',
            'zone_area_ha': zone, 'covered_land_ha': zone * percent / 100, 'coverage_percentage': percent,
            'population_covered': None, 'population_gap': None, 'planning_gaps': None, 'baseline_change_percentage': None}
    summary_id = area or 1
    displayed = [p for p in selected if summary_id == 1 or (p['id'] in (1, 3) if summary_id == 2 else p['id'] in (2, 4))]
    return {'filters': {'area': area, 'category': category}, 'radius_m': 1000, 'coverage_basis': 'land_area_within_park_buffers',
        'options': {'areas': areas, 'categories': categories}, 'summary': metrics(summary_id),
        'areas': [{**a, **metrics(a['area_id'])} for a in areas if area is None or a['area_id'] == area],
        'categories': [{**c, 'space_count': sum(p['properties']['category_id'] == c['category_id'] for p in displayed)}
                       for c in categories if category is None or c['category_id'] == category],
        'priority_areas': [], 'priority_status': 'unavailable'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == '/api/public/dashboard/':
            try:
                area = int(query['area'][0]) if 'area' in query else None
                category = int(query['category'][0]) if 'category' in query else None
            except ValueError:
                return self.send_json({'error': 'Invalid synthetic filter'}, 400)
            if category == 777:
                return self.send_json({'error': 'Deliberate synthetic dashboard failure'}, 503)
            if category == 888:
                sleep(1)
            return self.send_json(dashboard_fixture(area, category))
        if parsed.path == '/api/public/nearby/options/':
            return self.send_json({'csrf_token': 'synthetic-test-only', 'radii_m': [500, 1000, 2000],
                'min_radius_m': 100, 'max_radius_m': 10000, 'street_address_lookup': False})
        if query.get("q") == ["UI_TEST_ERROR"]:
            return self.send_json({"error": "Deliberate UI-test error"}, 503)
        if parsed.path == "/api/public/map-options/":
            return self.send_json({"categories": [
                {"category_id": 1, "category_name": "TEST public park", "green_space_count": 2},
                {"category_id": 2, "category_name": "TEST community garden", "green_space_count": 2},
            ], "green_space_count": 4, "administrative_area_count": 1})
        if parsed.path in {"/api/public/green-spaces/", "/api/public/administrative-areas/"}:
            records = list(PARKS) if "green-spaces" in parsed.path else [BOUNDARY]
            if query.get("q"):
                records = [item for item in records if query["q"][0].casefold() in item["properties"]["name"].casefold()]
            if query.get("category"):
                records = [item for item in records if str(item["properties"]["category_id"]) == query["category"][0]]
            if query.get("bbox"):
                records = [item for item in records if intersects(item, map(float, query["bbox"][0].split(",")))]
            return self.send_json({"type": "FeatureCollection", "features": records, "count": len(records),
                                   "page": 1, "page_size": 200, "has_next": False})
        for item in PARKS:
            if parsed.path == f'/api/public/green-spaces/{item["id"]}/':
                return self.send_json(item)
        return self.send_json({"error": "Not found in test fixture"}, 404)

    def do_POST(self):
        # Synthetic UI fixtures only. This is NOT a substitute for PostGIS,
        # its geography/CSRF tests, or production distance calculations.
        size = int(self.headers.get('Content-Length', 0))
        if size > 2048:
            return self.send_json({'error': 'Too large'}, 413)
        try:
            data = json.loads(self.rfile.read(size))
            if self.path == '/api/public/locations/search/':
                results = []
                for record in PARKS:
                    if data['q'].casefold() not in record['properties']['name'].casefold():
                        continue
                    geometry = record['geometry']
                    x, y = geometry['coordinates'] if geometry['type'] == 'Point' else [101.565, 3.11]
                    results.append({'id': record['id'], 'label': record['properties']['name'], 'longitude': x,
                                    'latitude': y, 'source': 'administrator_place'})
                return self.send_json({'results': results, 'has_more': False, 'street_address_lookup': False})
            if self.path in {'/api/public/nearby/', '/api/public/accessibility/'}:
                radius = int(data['radius_m'])
                if radius == 777:
                    return self.send_json({'error': 'Synthetic test error', 'code': 'database_unavailable'}, 503)
                longitude, latitude = float(data['longitude']), float(data['latitude'])
                if self.path == '/api/public/accessibility/':
                    if radius == 888:
                        sleep(1)  # Exercise stale-request cancellation via the UI.
                    return self.send_json(coverage_fixture(longitude, latitude, radius))
                records = nearby_records(longitude, latitude, radius)
                return self.send_json({'type': 'FeatureCollection', 'features': records, 'count': len(records),
                    'page': 1, 'page_size': 200, 'has_next': False, 'radius_m': radius,
                    'distance_method': 'spheroidal_straight_line_to_geometry'})
        except (KeyError, TypeError, ValueError):
            return self.send_json({'error': 'Invalid synthetic query', 'code': 'invalid_query'}, 400)
        return self.send_json({'error': 'Not found in test fixture'}, 404)

    def send_json(self, payload, status=200):
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except ConnectionError:
            pass  # Expected when the UI cancels a superseded test request.


if __name__ == "__main__":
    print("SYNTHETIC UI TEST API ONLY: http://127.0.0.1:8015", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8015), Handler).serve_forever()

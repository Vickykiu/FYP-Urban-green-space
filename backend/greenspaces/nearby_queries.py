"""Strict, database-independent input validation for public location queries."""
import math
from dataclasses import dataclass

MIN_RADIUS_M = 100
MAX_RADIUS_M = 10000


def coordinate(value, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f'{label} must be a finite coordinate.')
    if isinstance(value, str) and (not value.strip() or len(value) > 32):
        raise ValueError(f'{label} must be a finite coordinate.')
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f'{label} must be a finite coordinate.') from exc
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f'{label} must be between {minimum} and {maximum}.')
    return number


@dataclass(frozen=True)
class NearbyQuery:
    latitude: float
    longitude: float
    radius_m: int
    page: int


def parse_nearby(payload):
    if not isinstance(payload, dict) or set(payload) - {'latitude', 'longitude', 'radius_m', 'page'}:
        raise ValueError('Send latitude, longitude, radius_m, and optional page only.')
    latitude = coordinate(payload.get('latitude'), 'latitude', -90, 90)
    longitude = coordinate(payload.get('longitude'), 'longitude', -180, 180)
    radius = coordinate(payload.get('radius_m'), 'radius_m', MIN_RADIUS_M, MAX_RADIUS_M)
    page = coordinate(payload.get('page', 1), 'page', 1, 10000)
    if radius != int(radius) or page != int(page):
        raise ValueError('radius_m and page must be whole numbers.')
    return NearbyQuery(latitude, longitude, int(radius), int(page))


def parse_place_search(payload):
    if not isinstance(payload, dict) or set(payload) != {'q'} or not isinstance(payload['q'], str):
        raise ValueError('Send a place name in q.')
    query = payload['q'].strip()
    if not 2 <= len(query) <= 150 or any(ord(c) < 32 for c in query):
        raise ValueError('Enter a place name between 2 and 150 characters.')
    return query

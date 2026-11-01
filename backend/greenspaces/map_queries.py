"""Validated public-map parameters, independent of GIS native libraries."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MapQuery:
    page: int = 1
    bbox: tuple | None = None
    category: int | None = None
    search: str = ""


def positive_integer(value, label, maximum=2147483647):
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal() or len(value) > 10:
        raise ValueError(f"{label} must be a positive integer.")
    number = int(value)
    if not 1 <= number <= maximum:
        raise ValueError(f"{label} must be between 1 and {maximum}.")
    return number


def parse_map_query(params, allow_search=True):
    allowed = {"bbox", "page", "q", "category"} if allow_search else {"bbox", "page"}
    if set(params) - allowed:
        raise ValueError("Unsupported map query parameter.")
    if hasattr(params, "getlist") and any(len(params.getlist(key)) != 1 for key in params):
        raise ValueError("Supply each map query parameter only once.")
    page = positive_integer(params.get("page", "1"), "page", maximum=10000)
    bbox = None
    if "bbox" in params:
        try:
            bbox = tuple(float(part) for part in params["bbox"].split(","))
        except (ValueError, AttributeError) as exc:
            raise ValueError("bbox must contain west,south,east,north coordinates.") from exc
        if len(bbox) != 4 or not all(math.isfinite(value) for value in bbox):
            raise ValueError("bbox must contain four finite coordinates.")
        west, south, east, north = bbox
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("Use a valid WGS84 bounding box; west < east and south < north.")
    category = positive_integer(params["category"], "category") if params.get("category") else None
    search = params.get("q", "").strip()
    if len(search) > 150:
        raise ValueError("Search text must not exceed 150 characters.")
    return MapQuery(page=page, bbox=bbox, category=category, search=search)

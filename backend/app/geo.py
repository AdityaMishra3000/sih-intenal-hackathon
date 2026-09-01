"""Demo GIS helpers for the SIH grievance MVP.

All POIs, ward boundaries and routing labels in this module are DEMO DATA FOR
HACKATHON MVP use.  They are deliberately offline and must not be presented as
official PMC jurisdiction or administrative boundaries.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any, Mapping

EARTH_RADIUS_M = 6_371_008.8
SENSITIVE_POI_TYPES = {"school", "hospital", "anganwadi", "fire_station", "railway_station", "bus_depot"}

# Recognisable Pune landmarks with intentionally approximate demo coordinates.
DEMO_POIS: tuple[dict[str, Any], ...] = (
    {"name": "Savitribai Phule Pune University", "type": "school", "lat": 18.5521, "lng": 73.8255},
    {"name": "Fergusson College", "type": "school", "lat": 18.5204, "lng": 73.8415},
    {"name": "Sassoon General Hospital", "type": "hospital", "lat": 18.5284, "lng": 73.8745},
    {"name": "Deenanath Mangeshkar Hospital", "type": "hospital", "lat": 18.5053, "lng": 73.8353},
    {"name": "Pune Railway Station", "type": "railway_station", "lat": 18.5287, "lng": 73.8748},
    {"name": "Shivajinagar Bus Depot", "type": "bus_depot", "lat": 18.5308, "lng": 73.8474},
    {"name": "Swargate Bus Depot", "type": "bus_depot", "lat": 18.5018, "lng": 73.8636},
    {"name": "Kothrud Fire Station", "type": "fire_station", "lat": 18.5078, "lng": 73.8077},
    {"name": "Deccan Police Station", "type": "police_station", "lat": 18.5175, "lng": 73.8428},
    {"name": "Koregaon Park Police Station", "type": "police_station", "lat": 18.5367, "lng": 73.8936},
    {"name": "Mahatma Phule Mandai", "type": "public_market", "lat": 18.5136, "lng": 73.8568},
    {"name": "Yerawada Community Anganwadi", "type": "anganwadi", "lat": 18.5528, "lng": 73.8803},
    {"name": "Aundh Community Health Centre", "type": "community_facility", "lat": 18.5601, "lng": 73.8077},
    {"name": "Kalyani Nagar Public School", "type": "school", "lat": 18.5484, "lng": 73.9025},
    {"name": "Hadapsar Community Clinic", "type": "hospital", "lat": 18.5015, "lng": 73.9264},
)
# Backward-compatible alias for callers that used the original demo constant.
POIS = DEMO_POIS

# DEMO ward geometries: (south latitude, north latitude, west longitude, east longitude).
WARD_BOXES: tuple[tuple[str, float, float, float, float], ...] = (
    ("Ward 12", 18.5000, 18.5205, 73.7950, 73.8250),
    ("Ward 18", 18.5200, 18.5410, 73.8250, 73.8550),
    ("Ward 21", 18.5000, 18.5220, 73.8550, 73.8860),
    ("Ward 27", 18.5220, 18.5470, 73.8550, 73.8900),
    ("Ward 32", 18.5400, 18.5700, 73.7900, 73.9200),
)

# Demo Routing: labels are useful for a prototype but are not official assignments.
ROUTING: dict[tuple[str, str], dict[str, Any]] = {
    ("pwd", "pothole"): {"department": "PMC Road Maintenance Division", "base_sla_hours": 48},
    ("pwd", "road_damage"): {"department": "PMC Road Maintenance Division", "base_sla_hours": 72},
    ("pwd", "tree_fallen"): {"department": "PMC Road Maintenance Division", "base_sla_hours": 12},
    ("water", "water_leak"): {"department": "PMC Water Supply Department", "base_sla_hours": 24},
    ("water", "no_water_supply"): {"department": "PMC Water Supply Department", "base_sla_hours": 24},
    ("water", "sewage_overflow"): {"department": "PMC Sewerage Department", "base_sla_hours": 12},
    ("power", "streetlight_out"): {"department": "MSEDCL Ward Office", "base_sla_hours": 72},
    ("power", "power_outage"): {"department": "MSEDCL Ward Office", "base_sla_hours": 12},
    ("swm", "garbage_uncollected"): {"department": "PMC Solid Waste Management", "base_sla_hours": 48},
    ("health", "mosquito_breeding"): {"department": "PMC Health Department", "base_sla_hours": 48},
    ("health", "stray_animals"): {"department": "PMC Health Department", "base_sla_hours": 48},
    ("traffic", "illegal_parking"): {"department": "Traffic Police / PMC Traffic Cell", "base_sla_hours": 24},
}
FALLBACK_ROUTE = {"department": "General Municipal Grievance Cell", "base_sla_hours": 72}
# Public alias used by other modules; labels are DEMO routing defaults only.
DEFAULT_ROUTING = ROUTING


class RouteResult(dict[str, Any]):
    """Route mapping that also preserves legacy ``department, sla = route`` use."""

    def __iter__(self):
        yield self["department"]
        yield self["sla_hours"]

    def __getitem__(self, key: Any) -> Any:
        if key == 0:
            return super().__getitem__("department")
        if key == 1:
            return super().__getitem__("sla_hours")
        return super().__getitem__(key)


def _field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    try:
        return value[key]  # sqlite3.Row and mapping-like objects
    except (KeyError, IndexError, TypeError):
        return getattr(value, key, default)


def _coordinate(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a numeric coordinate") from exc
    if not (-90 <= result <= 90 if name == "lat" else -180 <= result <= 180):
        raise ValueError(f"{name} is outside its valid range")
    return result


def _point(value: Any, longitude: Any | None = None) -> tuple[float, float]:
    """Read a latitude/longitude pair from numbers, a mapping, tuple or object."""
    if longitude is not None:
        return _coordinate(value, "lat"), _coordinate(longitude, "lng")
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return _coordinate(value[0], "lat"), _coordinate(value[1], "lng")
    return _coordinate(_field(value, "lat"), "lat"), _coordinate(_field(value, "lng", _field(value, "lon")), "lng")


def haversine(lat1: Any, lng1: Any = None, lat2: Any = None, lng2: Any = None) -> float:
    """Return great-circle distance in metres, validating every coordinate.

    Use either ``haversine(lat1, lng1, lat2, lng2)`` or
    ``haversine(point_a, point_b)`` where points are pairs, mappings or objects.
    """
    if lat2 is None and lng2 is None:
        a_lat, a_lng = _point(lat1)
        b_lat, b_lng = _point(lng1)
    else:
        a_lat, a_lng = _point(lat1, lng1)
        b_lat, b_lng = _point(lat2, lng2)
    delta_lat, delta_lng = radians(b_lat - a_lat), radians(b_lng - a_lng)
    a = sin(delta_lat / 2) ** 2 + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(delta_lng / 2) ** 2
    return EARTH_RADIUS_M * 2 * asin(sqrt(a))


def nearest_poi(lat: Any, lng: Any) -> dict[str, Any]:
    """Return the nearest offline DEMO DATA FOR HACKATHON MVP POI."""
    point = _point(lat, lng)
    poi = min(DEMO_POIS, key=lambda candidate: haversine(point, candidate))
    return {"name": str(poi["name"]), "type": str(poi["type"]), "distance_m": round(haversine(point, poi), 1)}


def ward_of(lat: Any, lng: Any) -> str:
    """Return the containing DEMO ward, or ``Outside Demo Area``."""
    point_lat, point_lng = _point(lat, lng)
    for ward, south, north, west, east in WARD_BOXES:
        if south <= point_lat <= north and west <= point_lng <= east:
            return ward
    return "Outside Demo Area"


def get_route(category_l1: Any, category_l2: Any, priority_label: Any = "P2") -> RouteResult:
    """Return a route mapping and a deterministic priority-adjusted SLA.

    ``RouteResult`` supports dictionary access required by P4 and legacy tuple
    unpacking used by the already-integrated complaint pipeline.
    """
    category_l1, category_l2 = str(category_l1 or "other").lower(), str(category_l2 or "other").lower()
    route = DEFAULT_ROUTING.get((category_l1, category_l2), FALLBACK_ROUTE)
    base = int(route["base_sla_hours"])
    multiplier = {"P0": 0.15, "P1": 0.5, "P2": 1.0, "P3": 1.5}.get(str(priority_label).upper(), 1.0)
    hours = max(1, int(round(base * multiplier)))
    # A P0 receives an emergency SLA no longer than two hours where possible.
    if str(priority_label).upper() == "P0":
        hours = min(hours, 2)
    return RouteResult(department=str(route["department"]), base_sla_hours=base, sla_hours=hours)

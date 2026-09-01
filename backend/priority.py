"""Explainable, deterministic priority scoring for grievance issues."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import log
from typing import Any, Mapping

from .geo import SENSITIVE_POI_TYPES, get_route, nearest_poi, ward_of

try:  # The shared P1 contract is used when it is present in the assembled app.
    from .contracts import PriorityResult
except ImportError:  # Keeps this P4 module runnable while teammates integrate P1.
    @dataclass
    class PriorityResult:  # type: ignore[no-redef]
        score: int
        label: str
        factors: dict[str, float]
        why: str
        department: str
        ward: str
        sla_hours: int


W = {"severity": 30, "poi_proximity": 20, "reports": 20, "category_base": 20, "age": 10}
CATEGORY_WEIGHT = {
    "sewage_overflow": 1.00, "tree_fallen": 0.90, "power_outage": 0.85,
    "water_leak": 0.75, "no_water_supply": 0.70, "road_damage": 0.65,
    "pothole": 0.55, "streetlight_out": 0.45, "garbage_uncollected": 0.60,
    "mosquito_breeding": 0.75, "stray_animals": 0.60, "illegal_parking": 0.35,
    "other": 0.30,
}


def _field(value: Any, key: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(key, default)
    try:
        return value[key]
    except (KeyError, IndexError, TypeError):
        return getattr(value, key, default)


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    """Parse common SQLite/ISO timestamps, returning ``None`` for invalid input."""
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str) and value.strip():
        try:
            result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    result = datetime.strptime(value.strip(), fmt)
                    break
                except ValueError:
                    result = None
            if result is None:
                return None
    else:
        return None
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def _base_sla(category_l1: str, category_l2: str) -> int:
    return max(1, int(get_route(category_l1, category_l2, "P2")["base_sla_hours"]))


def _label(score: int) -> str:
    if score >= 75:
        return "P0"
    if score >= 55:
        return "P1"
    if score >= 32:
        return "P2"
    return "P3"


def _why(contributions: dict[str, float], severity: float, reports: int, poi: dict[str, Any] | None) -> str:
    ranked = sorted(contributions, key=contributions.get, reverse=True)
    parts: list[str] = []
    for factor in ranked:
        if contributions[factor] <= 0 or len(parts) == 3:
            continue
        if factor == "severity":
            parts.append("high reported severity" if severity >= 0.7 else "severity score")
        elif factor == "poi_proximity" and poi and poi["type"] in SENSITIVE_POI_TYPES:
            parts.append(f"{str(poi['type']).replace('_', ' ')} {int(round(poi['distance_m']))}m away")
        elif factor == "reports":
            parts.append(f"{reports} citizen report{'s' if reports != 1 else ''}")
        elif factor == "category_base":
            parts.append("higher-risk service category")
        elif factor == "age":
            parts.append("issue is approaching its base SLA")
    return " · ".join(parts) if parts else "insufficient risk signals; standard handling applies"


def score_issue(issue: Any, enrichment: Any = None) -> PriorityResult:
    """Score a dict, SQLite row or object using transparent rule-based factors.

    The age factor uses a route's *base* SLA to avoid a circular dependency;
    the final SLA is adjusted only after the resulting priority is known.
    """
    category_l1 = str(_field(enrichment, "category_l1", _field(issue, "category_l1", "other")) or "other").lower()
    category_l2 = str(_field(enrichment, "category_l2", _field(issue, "category_l2", "other")) or "other").lower()
    severity = _clamp(_field(enrichment, "severity", _field(issue, "severity", 0.0)))
    reports = max(0, int(_number(_field(issue, "report_count", 1), 1)))
    report_factor = min(log(reports + 1) / log(11), 1.0)

    poi: dict[str, Any] | None = None
    proximity = 0.0
    try:
        poi = nearest_poi(_field(issue, "lat"), _field(issue, "lng"))
        distance = float(poi["distance_m"])
        proximity = 1.0 if distance < 100 else 0.6 if distance < 300 else 0.2 if distance < 600 else 0.0
    except (TypeError, ValueError):
        pass

    created = _parse_datetime(_field(issue, "created_at"))
    if created:
        hours_open = max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 3600)
        age_factor = _clamp(hours_open / _base_sla(category_l1, category_l2))
    else:
        age_factor = 0.0

    contributions = {
        "severity": round(W["severity"] * severity, 2),
        "poi_proximity": round(W["poi_proximity"] * proximity, 2),
        "reports": round(W["reports"] * report_factor, 2),
        "category_base": round(W["category_base"] * CATEGORY_WEIGHT.get(category_l2, CATEGORY_WEIGHT["other"]), 2),
        "age": round(W["age"] * age_factor, 2),
    }
    score = int(round(sum(contributions.values())))
    label = _label(score)
    route = get_route(category_l1, category_l2, label)
    department, sla_hours = str(route["department"]), int(route["sla_hours"])
    try:
        ward = ward_of(_field(issue, "lat"), _field(issue, "lng"))
    except (TypeError, ValueError):
        ward = "Outside Demo Area"
    return PriorityResult(score=score, label=label, factors=contributions,
                          why=_why(contributions, severity, reports, poi),
                          department=department, ward=ward, sla_hours=sla_hours)


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    cases = [
        {"category_l1": "pwd", "category_l2": "pothole", "severity": .2, "report_count": 1, "lat": 18.48, "lng": 73.78},
        {"category_l1": "pwd", "category_l2": "pothole", "severity": .2, "report_count": 5, "lat": 18.48, "lng": 73.78},
        {"category_l1": "water", "category_l2": "sewage_overflow", "severity": .95, "report_count": 5, "lat": 18.5204, "lng": 73.8415},
        {"category_l1": "power", "category_l2": "power_outage", "severity": .4, "report_count": 2, "created_at": (now.replace(year=now.year - 1)).isoformat(), "lat": 18.53, "lng": 73.86},
        {},
    ]
    results = [score_issue(case) for case in cases]
    assert results[0].label in {"P2", "P3"}
    assert results[1].score > results[0].score
    assert results[2].label in {"P0", "P1"}
    assert results[3].factors["age"] > 0 and results[4].department and results[4].ward
    print("priority self-tests passed")

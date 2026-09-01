"""Small, explainable grid hotspot and dashboard analytics helpers."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Any, Iterable, Mapping

# Local Pune approximation: 0.0018° latitude and 0.00195° longitude are roughly
# 200 m near Pune.  This is DEMO DATA FOR HACKATHON MVP use; longitude scale
# varies with latitude and this is not a nationwide geographic index.
LAT_CELL_DEG = 0.0018
LNG_CELL_DEG = 0.00195
ORIGIN_LAT = 18.4500
ORIGIN_LNG = 73.7500


def _field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    try:
        return value[key]
    except (KeyError, IndexError, TypeError):
        return getattr(value, key, default)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def _cell(lat: float, lng: float) -> tuple[int, int]:
    return int((lat - ORIGIN_LAT) // LAT_CELL_DEG), int((lng - ORIGIN_LNG) // LNG_CELL_DEG)


def compute_hotspots(issues: Iterable[Any], now: datetime | None = None) -> list[dict[str, Any]]:
    """Return statistically notable 200m-ish grid/category hotspot aggregates.

    Z-scores are calculated only across cells in the same category.  Empty,
    single-cell and zero-variance populations receive z=0 to avoid fake signal.
    """
    current_time = now or datetime.now(timezone.utc)
    current_time = current_time.replace(tzinfo=timezone.utc) if current_time.tzinfo is None else current_time.astimezone(timezone.utc)
    bins: dict[tuple[int, int, str], dict[str, Any]] = {}
    for issue in issues:
        lat, lng = _number(_field(issue, "lat"), float("nan")), _number(_field(issue, "lng"), float("nan"))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        category = str(_field(issue, "category_l2", "other") or "other")
        row, col = _cell(lat, lng)
        key = (row, col, category)
        item = bins.setdefault(key, {"lat_sum": 0.0, "lng_sum": 0.0, "issue_count": 0, "total_reports": 0,
                                     "priority_sum": 0.0, "current_7d_count": 0, "previous_7d_count": 0})
        item["lat_sum"] += lat
        item["lng_sum"] += lng
        item["issue_count"] += 1
        item["total_reports"] += max(0, int(_number(_field(issue, "report_count", 1), 1)))
        item["priority_sum"] += _number(_field(issue, "priority_score", 0))
        created = _date(_field(issue, "created_at"))
        if created:
            age = current_time - created
            if timedelta(0) <= age <= timedelta(days=7):
                item["current_7d_count"] += 1
            elif timedelta(days=7) < age <= timedelta(days=14):
                item["previous_7d_count"] += 1

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (row, col, category), item in bins.items():
        count = item["issue_count"]
        current, previous = item["current_7d_count"], item["previous_7d_count"]
        trend = round(((current - previous) / previous) * 100, 1) if previous else (100.0 if current else 0.0)
        record = {
            "cell_id": f"pune-{row}-{col}", "category": category,
            "center_lat": round(item["lat_sum"] / count, 6), "center_lng": round(item["lng_sum"] / count, 6),
            "issue_count": count, "total_reports": item["total_reports"],
            "mean_priority": round(item["priority_sum"] / count, 1), "z_score": 0.0,
            "trend_pct": trend, "current_7d_count": current, "previous_7d_count": previous,
        }
        groups[category].append(record)

    qualified: list[dict[str, Any]] = []
    for category_cells in groups.values():
        counts = [record["issue_count"] for record in category_cells]
        if len(counts) > 1:
            mean = sum(counts) / len(counts)
            variance = sum((count - mean) ** 2 for count in counts) / len(counts)
            stdev = sqrt(variance)
            if stdev:
                for record in category_cells:
                    record["z_score"] = round((record["issue_count"] - mean) / stdev, 3)
        qualified.extend(record for record in category_cells if record["issue_count"] >= 2 and record["z_score"] > 1.5)
    return sorted(qualified, key=lambda record: (-record["z_score"], -record["total_reports"]))


def analytics_stats(complaints: Iterable[Any], issues: Iterable[Any]) -> dict[str, Any]:
    """Calculate genuine dashboard aggregate metrics from supplied records."""
    complaint_list, issue_list = list(complaints), list(issues)
    total, unique = len(complaint_list), len(issue_list)
    collapsed = max(0, total - unique)
    labels = Counter(str(_field(issue, "priority_label", "P3") or "P3").upper() for issue in issue_list)
    category = Counter(str(_field(issue, "category_l2", "other") or "other") for issue in issue_list)
    department = Counter(str(_field(issue, "department", "Unassigned") or "Unassigned") for issue in issue_list)
    open_issues = sum(1 for issue in issue_list if str(_field(issue, "status", "OPEN") or "OPEN").upper() not in {"RESOLVED", "CLOSED"})
    return {"total_complaints": total, "unique_issues": unique, "duplicates_collapsed": collapsed,
            "duplicate_collapse_pct": round((collapsed / total) * 100, 1) if total else 0.0,
            "open_issues": open_issues, "p0": labels["P0"], "p1": labels["P1"], "p2": labels["P2"], "p3": labels["P3"],
            "by_category": dict(sorted(category.items())), "by_department": dict(sorted(department.items()))}


if __name__ == "__main__":
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert compute_hotspots([], now) == []
    assert compute_hotspots([{"lat": 18.52, "lng": 73.84, "category_l2": "pothole"}], now) == []
    issues = ([{"lat": 18.52 + i * .0001, "lng": 73.84, "category_l2": "pothole", "report_count": 2,
                "priority_score": 50, "created_at": now.isoformat()} for i in range(5)] +
              [{"lat": 18.53 + i * .003, "lng": 73.86, "category_l2": "pothole", "report_count": 1,
                "priority_score": 30, "created_at": now.isoformat()} for i in range(4)])
    hotspots = compute_hotspots(issues, now)
    assert hotspots and hotspots[0]["z_score"] > 1.5
    stats = analytics_stats(range(7), issues)
    assert stats["total_complaints"] == 7 and stats["unique_issues"] == len(issues)
    print("hotspot self-tests passed")

import json
import math
from datetime import datetime, timezone


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def safe_json_loads(value, default=None):
    if value is None:
        return {} if default is None else default
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {} if default is None else default


def rolling_average(values):
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def haversine_km(point_a, point_b):
    lat1 = math.radians(point_a["latitude"])
    lon1 = math.radians(point_a["longitude"])
    lat2 = math.radians(point_b["latitude"])
    lon2 = math.radians(point_b["longitude"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371.0 * (2 * math.atan2(math.sqrt(value), math.sqrt(1 - value)))


def polyline_total_distance(points):
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        total += haversine_km(points[index], points[index + 1])
    return total


def interpolate_polyline(points, progress):
    if not points:
        return {"latitude": 0.0, "longitude": 0.0}
    if len(points) == 1:
        return points[0]

    capped_progress = clamp(progress, 0.0, 1.0)
    segment_lengths = []
    total_length = 0.0
    for index in range(len(points) - 1):
        segment_length = haversine_km(points[index], points[index + 1])
        segment_lengths.append(segment_length)
        total_length += segment_length

    if total_length == 0:
        return points[0]

    target_distance = total_length * capped_progress
    traveled = 0.0
    for index, segment_length in enumerate(segment_lengths):
        if traveled + segment_length >= target_distance:
            ratio = (target_distance - traveled) / segment_length if segment_length else 0
            start = points[index]
            end = points[index + 1]
            return {
                "latitude": start["latitude"] + (end["latitude"] - start["latitude"]) * ratio,
                "longitude": start["longitude"] + (end["longitude"] - start["longitude"]) * ratio,
            }
        traveled += segment_length
    return points[-1]


def nearest_hub(current_point, hubs):
    return min(hubs, key=lambda hub: haversine_km(current_point, hub))


def build_reroute_points(current_point, hub):
    midpoint = {
        "latitude": round((current_point["latitude"] + hub["latitude"]) / 2 + 0.22, 6),
        "longitude": round((current_point["longitude"] + hub["longitude"]) / 2 - 0.18, 6),
    }
    return [current_point, midpoint, {"latitude": hub["latitude"], "longitude": hub["longitude"]}]


def severity_rank(severity):
    order = {"critical": 3, "high": 2, "warning": 1, "info": 0}
    return order.get((severity or "").lower(), 0)


def risk_band(risk_score):
    if risk_score >= 80:
        return "Critical"
    if risk_score >= 55:
        return "Elevated"
    if risk_score >= 30:
        return "Watch"
    return "Nominal"

from __future__ import annotations

import math


def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(a_lat)
    phi2 = math.radians(b_lat)
    d_phi = math.radians(b_lat - a_lat)
    d_lambda = math.radians(b_lon - a_lon)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(h))


def point_to_route_km(lat: float, lon: float, route: list[dict[str, float]]) -> float:
    if not route:
        return float("inf")
    return min(haversine_km(lat, lon, point["lat"], point["lon"]) for point in route)


def severity_from_distance(distance_km: float, range_km: float) -> str:
    if distance_km <= range_km * 0.45:
        return "critical"
    if distance_km <= range_km * 0.75:
        return "high"
    if distance_km <= range_km:
        return "medium"
    return "low"


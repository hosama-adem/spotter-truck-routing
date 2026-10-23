"""Routing provider interface and OpenRouteService client.

Spike decision (see README Decisions): ORS `driving-hgv` is the provider.
Native `alternative_routes` only work for trips ≤ 100 km on the public API,
so long-haul OD pairs always use via-point requests to surface three corridors.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

EARTH_RADIUS_M = 6_371_000.0
METERS_PER_MILE = 1609.344

# Public ORS host after api.openrouteservice.org deprecation (shutdown Nov 2026).
ORS_BASE_URL = "https://api.heigit.org/openrouteservice"
ORS_PROFILE = "driving-hgv"
ORS_ALTERNATIVES_MAX_DISTANCE_M = 100_000
ORS_DIRECTIONS_MAX_DISTANCE_M = 6_000_000


@dataclass(frozen=True, slots=True)
class LatLon:
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class RouteOption:
    """One corridor from the routing provider, before weather/risk."""

    id: str
    distance_m: float
    duration_s: float
    geometry: list[tuple[float, float]]  # (lon, lat) GeoJSON order
    via: LatLon | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "distance_mi": round(self.distance_m / METERS_PER_MILE, 1),
            "duration_s": round(self.duration_s, 1),
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon, lat] for lon, lat in self.geometry],
            },
        }


class RoutingProvider(Protocol):
    def fetch_routes(self, origin: LatLon, destination: LatLon) -> list[RouteOption]:
        """Return exactly three truck routes, or raise on hard failure."""


def haversine_m(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def midpoint(a: LatLon, b: LatLon) -> LatLon:
    return LatLon(lat=(a.lat + b.lat) / 2, lon=(a.lon + b.lon) / 2)


def offset_perpendicular(
    a: LatLon,
    b: LatLon,
    *,
    offset_m: float,
    side: int,
) -> LatLon:
    """Offset the A→B midpoint perpendicular to the great-circle bearing.

    ``side`` is +1 (left of travel) or -1 (right of travel).
    """
    if side not in (-1, 1):
        raise ValueError("side must be +1 or -1")

    mid = midpoint(a, b)
    bearing = math.atan2(
        math.sin(math.radians(b.lon - a.lon)) * math.cos(math.radians(b.lat)),
        math.cos(math.radians(a.lat)) * math.sin(math.radians(b.lat))
        - math.sin(math.radians(a.lat))
        * math.cos(math.radians(b.lat))
        * math.cos(math.radians(b.lon - a.lon)),
    )
    perp = bearing + side * (math.pi / 2)
    lat1 = math.radians(mid.lat)
    lon1 = math.radians(mid.lon)
    ang = offset_m / EARTH_RADIUS_M
    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang)
        + math.cos(lat1) * math.sin(ang) * math.cos(perp)
    )
    lon2 = lon1 + math.atan2(
        math.sin(perp) * math.sin(ang) * math.cos(lat1),
        math.cos(ang) - math.sin(lat1) * math.sin(lat2),
    )
    return LatLon(lat=math.degrees(lat2), lon=((math.degrees(lon2) + 540) % 360) - 180)


def via_point_candidates(
    origin: LatLon,
    destination: LatLon,
    *,
    offset_mi: float = 40.0,
) -> list[LatLon | None]:
    """Direct corridor plus left/right mid-route vias for three distinct options."""
    offset_m = offset_mi * METERS_PER_MILE
    return [
        None,
        offset_perpendicular(origin, destination, offset_m=offset_m, side=1),
        offset_perpendicular(origin, destination, offset_m=offset_m, side=-1),
    ]


def decode_polyline(encoded: str, *, precision: int = 5) -> list[tuple[float, float]]:
    """Decode an ORS/Google encoded polyline into (lon, lat) pairs."""
    coordinates: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lon = 0
    factor = 10**precision

    while index < len(encoded):
        for coordinate in (0, 1):
            shift = 0
            result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if coordinate == 0:
                lat += delta
            else:
                lon += delta
        coordinates.append((lon / factor, lat / factor))

    return coordinates


class OpenRouteServiceProvider:
    """Live ORS client. Prefer via-points for OD pairs longer than 100 km."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = ORS_BASE_URL,
        profile: str = ORS_PROFILE,
        timeout_s: float = 30.0,
        via_offset_mi: float = 40.0,
    ) -> None:
        if not api_key:
            raise ValueError("ORS_API_KEY is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._profile = profile
        self._timeout_s = timeout_s
        self._via_offset_mi = via_offset_mi

    def fetch_routes(self, origin: LatLon, destination: LatLon) -> list[RouteOption]:
        distance_m = haversine_m(origin, destination)
        if distance_m > ORS_DIRECTIONS_MAX_DISTANCE_M:
            raise RuntimeError(
                f"OD pair is {distance_m / 1000:.0f} km; ORS public max is "
                f"{ORS_DIRECTIONS_MAX_DISTANCE_M / 1000:.0f} km"
            )

        if distance_m <= ORS_ALTERNATIVES_MAX_DISTANCE_M:
            routes = self._fetch_with_alternatives(origin, destination)
            if len(routes) >= 3:
                return routes[:3]

        routes = self._fetch_with_via_points(origin, destination)
        if len(routes) < 3:
            raise RuntimeError(
                f"Routing provider returned {len(routes)} route(s); need exactly 3"
            )
        return routes[:3]

    def _fetch_with_alternatives(
        self,
        origin: LatLon,
        destination: LatLon,
    ) -> list[RouteOption]:
        body = {
            "coordinates": [
                [origin.lon, origin.lat],
                [destination.lon, destination.lat],
            ],
            "instructions": False,
            "geometry": True,
            "alternative_routes": {
                "target_count": 3,
                "share_factor": 0.6,
                "weight_factor": 1.4,
            },
        }
        payload = self._post_directions(body)
        return self._parse_json_routes(payload)

    def _fetch_with_via_points(
        self,
        origin: LatLon,
        destination: LatLon,
    ) -> list[RouteOption]:
        routes: list[RouteOption] = []
        vias = via_point_candidates(
            origin,
            destination,
            offset_mi=self._via_offset_mi,
        )
        for index, via in enumerate(vias):
            coordinates = [[origin.lon, origin.lat]]
            if via is not None:
                coordinates.append([via.lon, via.lat])
            coordinates.append([destination.lon, destination.lat])
            payload = self._post_directions(
                {
                    "coordinates": coordinates,
                    "instructions": False,
                    "geometry": True,
                }
            )
            route_id = chr(ord("A") + index)
            parsed = self._parse_json_routes(payload, id_prefix=route_id, via=via)
            if parsed:
                routes.append(parsed[0])
        if not routes:
            raise RuntimeError("ORS returned no routes for via-point requests")
        return routes

    def _post_directions(self, body: dict) -> dict:
        url = f"{self._base_url}/v2/directions/{self._profile}"
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ORS HTTP {exc.code}: {detail}") from exc

    def _parse_json_routes(
        self,
        payload: dict,
        *,
        id_prefix: str | None = None,
        via: LatLon | None = None,
    ) -> list[RouteOption]:
        routes: list[RouteOption] = []
        for index, route in enumerate(payload.get("routes", [])):
            summary = route.get("summary", {})
            geometry = route.get("geometry")
            if isinstance(geometry, str):
                coords = decode_polyline(geometry)
            elif isinstance(geometry, dict) and geometry.get("coordinates"):
                coords = [
                    (float(lon), float(lat)) for lon, lat in geometry["coordinates"]
                ]
            else:
                coords = []
            route_id = id_prefix or chr(ord("A") + index)
            routes.append(
                RouteOption(
                    id=route_id,
                    distance_m=float(summary.get("distance", 0.0)),
                    duration_s=float(summary.get("duration", 0.0)),
                    geometry=coords,
                    via=via,
                )
            )
        return routes

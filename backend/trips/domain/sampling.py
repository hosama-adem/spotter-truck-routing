"""Checkpoint sampling and ETA interpolation (pure — no I/O).

PRD RT-2 / RT-3 / IN-4: place checkpoints every 10 / 25 / 50 miles, always
include origin and destination, and derive each ETA from provider step
durations (not a flat constant speed).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

METERS_PER_MILE = 1609.344
EARTH_RADIUS_M = 6_371_000.0
ALLOWED_INTERVALS_MI = frozenset({10, 25, 50})


@dataclass(frozen=True, slots=True)
class RouteLeg:
    """One routing-provider step: distance traveled and time taken."""

    distance_m: float
    duration_s: float


@dataclass(frozen=True, slots=True)
class Checkpoint:
    mile: float
    lat: float
    lon: float
    eta: datetime  # always UTC

    def as_dict(self) -> dict:
        return {
            "mile": self.mile,
            "lat": self.lat,
            "lon": self.lon,
            "eta": self.eta.isoformat().replace("+00:00", "Z"),
        }


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def cumulative_distances_m(geometry: Sequence[tuple[float, float]]) -> list[float]:
    """Cumulative meters along a (lon, lat) polyline, starting at 0."""
    if len(geometry) < 2:
        raise ValueError("geometry must contain at least two coordinates")

    distances = [0.0]
    for (lon1, lat1), (lon2, lat2) in zip(geometry, geometry[1:], strict=False):
        distances.append(distances[-1] + haversine_m(lon1, lat1, lon2, lat2))
    return distances


def interpolate_point(
    geometry: Sequence[tuple[float, float]],
    distances_m: Sequence[float],
    target_m: float,
) -> tuple[float, float]:
    """Return (lon, lat) at ``target_m`` along the polyline."""
    total = distances_m[-1]
    if target_m <= 0:
        return geometry[0]
    if target_m >= total:
        return geometry[-1]

    for index in range(1, len(distances_m)):
        if distances_m[index] >= target_m:
            start_m = distances_m[index - 1]
            end_m = distances_m[index]
            span = end_m - start_m
            fraction = 0.0 if span <= 0 else (target_m - start_m) / span
            lon1, lat1 = geometry[index - 1]
            lon2, lat2 = geometry[index]
            return (
                lon1 + (lon2 - lon1) * fraction,
                lat1 + (lat2 - lat1) * fraction,
            )
    return geometry[-1]


def duration_at_distance_s(
    legs: Sequence[RouteLeg],
    target_m: float,
    *,
    route_distance_m: float,
) -> float:
    """Interpolate cumulative duration at ``target_m`` along the route.

    Leg distances are mapped onto the geometry length so a small mismatch
    between provider step sums and polyline length still yields a smooth ETA.
    """
    if not legs:
        raise ValueError("legs must not be empty")
    if any(leg.distance_m < 0 or leg.duration_s < 0 for leg in legs):
        raise ValueError("leg distance and duration must be non-negative")

    total_leg_m = sum(leg.distance_m for leg in legs)
    total_leg_s = sum(leg.duration_s for leg in legs)
    if route_distance_m <= 0:
        return 0.0
    if total_leg_m <= 0:
        # Degenerate steps: fall back to zero progress / full time at the end.
        return 0.0 if target_m <= 0 else total_leg_s

    # Map geometry meters onto the leg distance axis.
    mapped_m = (target_m / route_distance_m) * total_leg_m
    if mapped_m <= 0:
        return 0.0
    if mapped_m >= total_leg_m:
        return total_leg_s

    walked = 0.0
    elapsed = 0.0
    for leg in legs:
        next_walked = walked + leg.distance_m
        if mapped_m <= next_walked:
            span = leg.distance_m
            fraction = 0.0 if span <= 0 else (mapped_m - walked) / span
            return elapsed + leg.duration_s * fraction
        walked = next_walked
        elapsed += leg.duration_s
    return total_leg_s


def checkpoint_miles(total_mi: float, interval_mi: int) -> list[float]:
    """Mile markers including origin and destination."""
    if interval_mi not in ALLOWED_INTERVALS_MI:
        raise ValueError("checkpoint_interval_mi must be one of 10, 25, or 50")
    if total_mi < 0:
        raise ValueError("total distance must be non-negative")

    miles = [0.0]
    cursor = float(interval_mi)
    # Guard float drift so we do not emit a marker essentially at the destination.
    while cursor < total_mi - 1e-6:
        miles.append(cursor)
        cursor += interval_mi
    if total_mi > 0 and (not miles or abs(miles[-1] - total_mi) > 1e-6):
        miles.append(total_mi)
    return miles


def sample_checkpoints(
    geometry: Sequence[tuple[float, float]],
    legs: Sequence[RouteLeg],
    *,
    departure_time: datetime,
    interval_mi: int,
) -> list[Checkpoint]:
    """Sample checkpoints every ``interval_mi`` miles with interpolated ETAs.

    ``geometry`` is a (lon, lat) polyline. ``departure_time`` must be timezone-aware;
    returned ETAs are always UTC.
    """
    if departure_time.tzinfo is None:
        raise ValueError("departure_time must be timezone-aware")
    if interval_mi not in ALLOWED_INTERVALS_MI:
        raise ValueError("checkpoint_interval_mi must be one of 10, 25, or 50")

    distances_m = cumulative_distances_m(geometry)
    route_distance_m = distances_m[-1]
    total_mi = route_distance_m / METERS_PER_MILE
    departure_utc = departure_time.astimezone(UTC)

    checkpoints: list[Checkpoint] = []
    for mile in checkpoint_miles(total_mi, interval_mi):
        target_m = mile * METERS_PER_MILE
        # Clamp to the polyline so the final marker lands on the true destination.
        target_m = min(target_m, route_distance_m)
        lon, lat = interpolate_point(geometry, distances_m, target_m)
        duration_s = duration_at_distance_s(
            legs,
            target_m,
            route_distance_m=route_distance_m,
        )
        checkpoints.append(
            Checkpoint(
                mile=round(mile, 4),
                lat=lat,
                lon=lon,
                eta=departure_utc + timedelta(seconds=duration_s),
            )
        )

    # Guarantee destination coordinates even when mile rounding drifts.
    if checkpoints:
        dest_lon, dest_lat = geometry[-1]
        last = checkpoints[-1]
        checkpoints[-1] = Checkpoint(
            mile=round(total_mi, 4),
            lat=dest_lat,
            lon=dest_lon,
            eta=last.eta,
        )
        first = checkpoints[0]
        origin_lon, origin_lat = geometry[0]
        checkpoints[0] = Checkpoint(
            mile=0.0,
            lat=origin_lat,
            lon=origin_lon,
            eta=first.eta,
        )

    return checkpoints

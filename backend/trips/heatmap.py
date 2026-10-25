"""Corridor weather-risk heatmap — 49 hourly frames, compact arrays."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from django.core.cache import cache

from trips.domain.corridor import MAX_GRID_POINTS, sample_corridor_grid
from trips.domain.risk import classify_checkpoint
from trips.providers.weather import WeatherQuery, WeatherSample

HEATMAP_HOURS = 49
HEATMAP_CACHE_TTL_S = 30 * 60
HEATMAP_CACHE_PREFIX = "heatmap:v1"


class WeatherClient(Protocol):
    def forecast_at(self, queries: list[WeatherQuery]) -> list[WeatherSample]: ...


@dataclass(frozen=True, slots=True)
class HeatmapInput:
    geometry: list[tuple[float, float]]  # (lon, lat)
    departure_time: datetime
    load_weight_lb: float


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _cache_key(plan: HeatmapInput, point_count: int) -> str:
    """Stable key from rounded corridor, departure hour, and load."""
    departure_utc = plan.departure_time.astimezone(UTC).replace(
        minute=0, second=0, microsecond=0
    )
    step = max(1, len(plan.geometry) // 32)
    rounded = [[round(lon, 3), round(lat, 3)] for lon, lat in plan.geometry[::step]]
    if plan.geometry:
        rounded.append(
            [round(plan.geometry[-1][0], 3), round(plan.geometry[-1][1], 3)]
        )
    payload = {
        "g": rounded,
        "n": point_count,
        "t": departure_utc.isoformat(),
        "w": round(plan.load_weight_lb, 1),
    }
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()[:24]
    return f"{HEATMAP_CACHE_PREFIX}:{digest}"


def build_heatmap(
    plan: HeatmapInput,
    *,
    weather: WeatherClient,
    cache_backend: Any = cache,
    cache_ttl_s: int = HEATMAP_CACHE_TTL_S,
    max_points: int = MAX_GRID_POINTS,
) -> dict[str, Any]:
    """Return PRD §7 heatmap payload; cache the full response."""
    if plan.departure_time.tzinfo is None:
        raise ValueError("departure_time must be timezone-aware")
    if len(plan.geometry) < 2:
        raise ValueError("geometry must contain at least two coordinates")

    points = sample_corridor_grid(plan.geometry, max_points=max_points)
    key = _cache_key(plan, len(points))
    cached = cache_backend.get(key)
    if cached is not None:
        return cached

    departure_utc = plan.departure_time.astimezone(UTC)
    hours = [
        departure_utc + timedelta(hours=offset) for offset in range(HEATMAP_HOURS)
    ]

    queries = [
        WeatherQuery(lat=lat, lon=lon, eta=hour)
        for hour in hours
        for lon, lat in points
    ]
    samples = weather.forecast_at(queries)
    if len(samples) != len(queries):
        raise RuntimeError("Weather provider returned the wrong number of samples.")

    risk: list[list[int]] = []
    sample_index = 0
    for _ in hours:
        row: list[int] = []
        for _ in points:
            sample = samples[sample_index]
            sample_index += 1
            assessment = classify_checkpoint(
                wind_mph=sample.wind_mph,
                rain_in_hr=sample.rain_in_hr,
                snow_in_hr=sample.snow_in_hr,
                load_weight_lb=plan.load_weight_lb,
            )
            row.append(int(assessment.level))
        risk.append(row)

    payload = {
        "start_time": _iso(departure_utc),
        "hours": HEATMAP_HOURS,
        "points": [[lon, lat] for lon, lat in points],
        "risk": risk,
    }
    cache_backend.set(key, payload, cache_ttl_s)
    return payload

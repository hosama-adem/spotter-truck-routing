"""Open-Meteo weather client — batched, cached, keyless.

PRD WX-1 / WX-2 / §8: hourly wind (mph), rain+showers (in/hr), snowfall (in),
nearest hour to each checkpoint ETA, ≤100 points per HTTP call, cache ~30 min.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from django.core.cache import cache

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
MAX_BATCH_SIZE = 100
CACHE_TTL_SECONDS = 30 * 60
COORD_QUANTUM = 0.1  # ~0.1° rounding for cache keys


@dataclass(frozen=True, slots=True)
class WeatherQuery:
    lat: float
    lon: float
    eta: datetime


@dataclass(frozen=True, slots=True)
class WeatherSample:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float
    hour: datetime  # UTC hour that was selected

    def as_dict(self) -> dict[str, float]:
        return {
            "wind_mph": self.wind_mph,
            "gust_mph": self.gust_mph,
            "rain_in_hr": self.rain_in_hr,
            "snow_in_hr": self.snow_in_hr,
        }


class WeatherProvider(Protocol):
    def forecast_at(self, queries: Sequence[WeatherQuery]) -> list[WeatherSample]:
        """Return one sample per query, same order."""


def round_coord(value: float, quantum: float = COORD_QUANTUM) -> float:
    """Round a coordinate to the cache grid (default 0.1°)."""
    return round(round(value / quantum) * quantum, 1)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("eta must be timezone-aware")
    return value.astimezone(UTC)


def nearest_hour_index(times: Sequence[datetime], target: datetime) -> int:
    """Index of the forecast hour closest to ``target`` (both timezone-aware)."""
    if not times:
        raise ValueError("times must not be empty")
    target_utc = ensure_utc(target)
    best_index = 0
    best_delta = abs(times[0] - target_utc)
    for index, moment in enumerate(times[1:], start=1):
        delta = abs(moment - target_utc)
        if delta < best_delta:
            best_index = index
            best_delta = delta
    return best_index


def location_cache_key(lat: float, lon: float) -> str:
    return f"wx:v1:{round_coord(lat):.1f}:{round_coord(lon):.1f}"


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_hourly_series(payload: dict) -> dict[str, Any]:
    """Normalize one Open-Meteo location payload into a cacheable series."""
    hourly = payload.get("hourly") or {}
    raw_times = hourly.get("time") or []
    if not raw_times:
        raise ValueError("Open-Meteo response missing hourly.time")

    times = [datetime.fromisoformat(stamp).replace(tzinfo=UTC) for stamp in raw_times]
    wind = hourly.get("wind_speed_10m") or [0.0] * len(times)
    gust = hourly.get("wind_gusts_10m") or [0.0] * len(times)
    rain = hourly.get("rain") or [0.0] * len(times)
    showers = hourly.get("showers") or [0.0] * len(times)
    snow = hourly.get("snowfall") or [0.0] * len(times)

    return {
        "times": times,
        "wind_mph": [_as_float(v) for v in wind],
        "gust_mph": [_as_float(v) for v in gust],
        "rain": [_as_float(v) for v in rain],
        "showers": [_as_float(v) for v in showers],
        "snow_in_hr": [_as_float(v) for v in snow],
    }


def sample_from_series(series: dict[str, Any], eta: datetime) -> WeatherSample:
    index = nearest_hour_index(series["times"], eta)
    rain_in_hr = series["rain"][index] + series["showers"][index]
    return WeatherSample(
        wind_mph=series["wind_mph"][index],
        gust_mph=series["gust_mph"][index],
        rain_in_hr=rain_in_hr,
        snow_in_hr=series["snow_in_hr"][index],
        hour=series["times"][index],
    )


def chunked(items: Sequence[Any], size: int) -> list[list[Any]]:
    return [list(items[index : index + size]) for index in range(0, len(items), size)]


HttpGetter = Callable[[str], dict | list]


def default_http_get(url: str) -> dict | list:
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Open-Meteo HTTP {exc.code}: {detail}") from exc


class OpenMeteoWeatherClient:
    """Batched Open-Meteo forecast client with Django cache."""

    def __init__(
        self,
        *,
        http_get: HttpGetter | None = None,
        cache_backend: Any = cache,
        cache_ttl_s: int = CACHE_TTL_SECONDS,
        max_batch: int = MAX_BATCH_SIZE,
        base_url: str = OPEN_METEO_URL,
    ) -> None:
        self._http_get = http_get or default_http_get
        self._cache = cache_backend
        self._cache_ttl_s = cache_ttl_s
        self._max_batch = max_batch
        self._base_url = base_url.rstrip("/")

    def forecast_at(self, queries: Sequence[WeatherQuery]) -> list[WeatherSample]:
        if not queries:
            return []

        for query in queries:
            ensure_utc(query.eta)

        series_by_key: dict[str, dict[str, Any]] = {}
        missing_coords: list[tuple[float, float]] = []
        seen_missing: set[str] = set()

        for query in queries:
            key = location_cache_key(query.lat, query.lon)
            if key in series_by_key:
                continue
            cached = self._cache.get(key)
            if cached is not None:
                series_by_key[key] = cached
                continue
            rounded = (round_coord(query.lat), round_coord(query.lon))
            if key not in seen_missing:
                missing_coords.append(rounded)
                seen_missing.add(key)

        if missing_coords:
            for batch in chunked(missing_coords, self._max_batch):
                fetched = self._fetch_batch(batch)
                for (lat, lon), series in zip(batch, fetched, strict=True):
                    key = location_cache_key(lat, lon)
                    self._cache.set(key, series, self._cache_ttl_s)
                    series_by_key[key] = series

        return [
            sample_from_series(series_by_key[location_cache_key(query.lat, query.lon)], query.eta)
            for query in queries
        ]

    def _fetch_batch(self, coords: Sequence[tuple[float, float]]) -> list[dict[str, Any]]:
        if not coords:
            return []

        # Cover typical trip horizons; callers can still pick any hour in range.
        start = datetime.now(tz=UTC).date()
        end = start + timedelta(days=7)
        params = {
            "latitude": ",".join(f"{lat:.1f}" for lat, _ in coords),
            "longitude": ",".join(f"{lon:.1f}" for _, lon in coords),
            "hourly": HOURLY_VARS,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "UTC",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
        url = f"{self._base_url}?{urllib.parse.urlencode(params)}"
        payload = self._http_get(url)

        if isinstance(payload, dict):
            locations = [payload]
        elif isinstance(payload, list):
            locations = payload
        else:
            raise RuntimeError("Unexpected Open-Meteo response type")

        if len(locations) != len(coords):
            raise RuntimeError(
                f"Open-Meteo returned {len(locations)} locations for {len(coords)} requests"
            )
        return [parse_hourly_series(item) for item in locations]

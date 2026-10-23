"""Geocoding provider for trip origin/destination autocomplete.

Uses HeiGIT Pelias (`api.heigit.org/pelias/v1`) with the same `ORS_API_KEY`
as routing. Response shape matches PRD §7: `{label, lat, lon}`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

PELIAS_BASE_URL = "https://api.heigit.org/pelias/v1"
DEFAULT_RESULT_LIMIT = 5


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    label: str
    lat: float
    lon: float

    def as_dict(self) -> dict[str, str | float]:
        return {"label": self.label, "lat": self.lat, "lon": self.lon}


class GeocodeProvider(Protocol):
    def autocomplete(self, query: str, *, limit: int = DEFAULT_RESULT_LIMIT) -> list[GeocodeResult]:
        """Return up to ``limit`` place suggestions for ``query``."""


def parse_pelias_features(
    payload: dict,
    *,
    limit: int = DEFAULT_RESULT_LIMIT,
) -> list[GeocodeResult]:
    """Map a Pelias FeatureCollection into PRD geocode rows."""
    results: list[GeocodeResult] = []
    for feature in payload.get("features", []):
        if len(results) >= limit:
            break
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        label = (properties.get("label") or properties.get("name") or "").strip()
        if not label:
            continue
        try:
            lon = float(coordinates[0])
            lat = float(coordinates[1])
        except (TypeError, ValueError):
            continue
        results.append(GeocodeResult(label=label, lat=lat, lon=lon))
    return results


class PeliasGeocoder:
    """Live HeiGIT Pelias autocomplete client."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = PELIAS_BASE_URL,
        timeout_s: float = 15.0,
    ) -> None:
        if not api_key:
            raise ValueError("ORS_API_KEY is required for geocoding")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def autocomplete(
        self,
        query: str,
        *,
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> list[GeocodeResult]:
        params = urllib.parse.urlencode({"text": query, "size": max(1, limit)})
        url = f"{self._base_url}/autocomplete?{params}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": self._api_key,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Pelias HTTP {exc.code}: {detail}") from exc
        return parse_pelias_features(payload, limit=limit)

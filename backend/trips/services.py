"""Trip planning orchestration — wires providers + domain modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from trips.domain.ranking import RankedCheckpoint, RouteForRanking, rank_routes
from trips.domain.risk import classify_checkpoint
from trips.domain.sampling import RouteLeg, sample_checkpoints
from trips.providers.routing import METERS_PER_MILE, LatLon, RouteOption
from trips.providers.weather import WeatherQuery, WeatherSample


class RoutingClient(Protocol):
    def fetch_routes(self, origin: LatLon, destination: LatLon) -> list[RouteOption]: ...


class WeatherClient(Protocol):
    def forecast_at(self, queries: list[WeatherQuery]) -> list[WeatherSample]: ...


@dataclass(frozen=True, slots=True)
class PlanInput:
    origin: LatLon
    destination: LatLon
    departure_time: datetime
    load_weight_lb: float
    checkpoint_interval_mi: int


def _legs_for_route(route: RouteOption) -> list[RouteLeg]:
    """ORS currently returns totals; treat the corridor as one timed leg.

    Sampling still interpolates ETA by distance along the geometry. When the
    routing provider later exposes step durations, swap them in here.
    """
    return [RouteLeg(distance_m=route.distance_m, duration_s=route.duration_s)]


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def plan_trip(
    plan: PlanInput,
    *,
    router: RoutingClient,
    weather: WeatherClient,
) -> dict[str, Any]:
    routes = router.fetch_routes(plan.origin, plan.destination)
    if len(routes) != 3:
        raise RuntimeError(f"Expected 3 routes, got {len(routes)}.")

    sampled: list[tuple[RouteOption, list]] = []
    for route in routes:
        checkpoints = sample_checkpoints(
            route.geometry,
            _legs_for_route(route),
            departure_time=plan.departure_time,
            interval_mi=plan.checkpoint_interval_mi,
        )
        sampled.append((route, checkpoints))

    weather_queries = [
        WeatherQuery(lat=point.lat, lon=point.lon, eta=point.eta)
        for _, checkpoints in sampled
        for point in checkpoints
    ]
    weather_samples = weather.forecast_at(weather_queries)
    if len(weather_samples) != len(weather_queries):
        raise RuntimeError("Weather provider returned the wrong number of samples.")

    sample_index = 0
    enriched_by_id: dict[str, dict[str, Any]] = {}
    ranking_inputs: list[RouteForRanking] = []

    for route, checkpoints in sampled:
        enriched_checkpoints: list[dict[str, Any]] = []
        ranked_checkpoints: list[RankedCheckpoint] = []

        for point in checkpoints:
            sample = weather_samples[sample_index]
            sample_index += 1
            risk = classify_checkpoint(
                wind_mph=sample.wind_mph,
                rain_in_hr=sample.rain_in_hr,
                snow_in_hr=sample.snow_in_hr,
                load_weight_lb=plan.load_weight_lb,
            )
            enriched_checkpoints.append(
                {
                    "mile": point.mile,
                    "lat": point.lat,
                    "lon": point.lon,
                    "eta": _iso(point.eta),
                    "weather": sample.as_dict(),
                    "risk": risk.as_dict(),
                }
            )
            ranked_checkpoints.append(
                RankedCheckpoint(mile=point.mile, level=risk.level)
            )

        ranking_inputs.append(
            RouteForRanking(
                id=route.id,
                duration_s=route.duration_s,
                checkpoints=ranked_checkpoints,
            )
        )
        arrival_time = checkpoints[-1].eta if checkpoints else plan.departure_time
        enriched_by_id[route.id] = {
            "route": route,
            "checkpoints": enriched_checkpoints,
            "arrival_time": arrival_time,
        }

    ranking = rank_routes(ranking_inputs)
    response_routes: list[dict[str, Any]] = []

    for rank, summary in enumerate(ranking.routes, start=1):
        bundle = enriched_by_id[summary.id]
        route: RouteOption = bundle["route"]
        response_routes.append(
            {
                "id": route.id,
                "rank": rank,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat] for lon, lat in route.geometry],
                },
                "summary": {
                    "distance_mi": round(route.distance_m / METERS_PER_MILE, 1),
                    "duration_s": round(route.duration_s, 1),
                    "arrival_time": _iso(bundle["arrival_time"]),
                    "miles_by_level": summary.miles_by_level,
                    "avg_risk": summary.avg_risk,
                    "max_level": summary.max_level.name,
                },
                "checkpoints": bundle["checkpoints"],
            }
        )

    return {
        "recommended_route_id": ranking.recommended_route_id,
        "recommendation_reason": ranking.recommendation_reason,
        "routes": response_routes,
    }

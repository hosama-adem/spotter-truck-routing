from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIClient

from trips.providers.routing import METERS_PER_MILE, RouteOption
from trips.providers.weather import WeatherSample


def _northbound_geometry(*, total_mi: float = 100.0) -> list[tuple[float, float]]:
    start_lat, start_lon = 40.0, -90.0
    end_lat = start_lat + (total_mi * METERS_PER_MILE / 111_320.0)
    return [(start_lon, start_lat), (start_lon, end_lat)]


def _route(route_id: str, *, total_mi: float, duration_s: float) -> RouteOption:
    return RouteOption(
        id=route_id,
        distance_m=total_mi * METERS_PER_MILE,
        duration_s=duration_s,
        geometry=_northbound_geometry(total_mi=total_mi),
    )


def _weather_sample(wind: float = 10.0, rain: float = 0.0) -> WeatherSample:
    return WeatherSample(
        wind_mph=wind,
        gust_mph=wind + 5,
        rain_in_hr=rain,
        snow_in_hr=0.0,
        hour=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )


def _valid_payload(**overrides):
    payload = {
        "origin": {"lat": 41.88, "lon": -87.63, "label": "Chicago, IL"},
        "destination": {"lat": 39.74, "lon": -104.99, "label": "Denver, CO"},
        "departure_time": "2026-06-01T06:00:00-05:00",
        "load_weight_lb": 42000,
        "checkpoint_interval_mi": 25,
    }
    payload.update(overrides)
    return payload


def test_plan_requires_body_fields():
    response = APIClient().post("/api/trips/plan", {}, format="json")

    assert response.status_code == 400
    assert "origin" in response.data
    assert "destination" in response.data
    assert "departure_time" in response.data
    assert "load_weight_lb" in response.data


def test_plan_rejects_bad_load_and_interval():
    response = APIClient().post(
        "/api/trips/plan",
        _valid_payload(load_weight_lb=0, checkpoint_interval_mi=30),
        format="json",
    )

    assert response.status_code == 400
    assert "load_weight_lb" in response.data
    assert "checkpoint_interval_mi" in response.data


def test_plan_rejects_naive_departure_time():
    response = APIClient().post(
        "/api/trips/plan",
        _valid_payload(departure_time="2026-06-01T06:00:00"),
        format="json",
    )

    assert response.status_code == 400
    assert "departure_time" in response.data


def test_plan_happy_path_matches_prd_shape(settings):
    settings.ORS_API_KEY = "test-key"
    mock_router = MagicMock()
    mock_router.fetch_routes.return_value = [
        _route("A", total_mi=100.0, duration_s=10 * 3600),
        _route("B", total_mi=100.0, duration_s=11 * 3600),
        _route("C", total_mi=100.0, duration_s=12 * 3600),
    ]

    def fake_forecast(queries):
        # Make route A severe in the middle so B (all calm if we vary) — keep it simple:
        # all calm weather → ranking falls to duration → A wins.
        return [_weather_sample(wind=10.0) for _ in queries]

    mock_weather = MagicMock()
    mock_weather.forecast_at.side_effect = fake_forecast

    with (
        patch("trips.views._router", return_value=mock_router),
        patch("trips.views._weather", return_value=mock_weather),
    ):
        response = APIClient().post(
            "/api/trips/plan",
            _valid_payload(),
            format="json",
        )

    assert response.status_code == 200
    body = response.data
    assert body["recommended_route_id"] == "A"
    assert body["recommendation_reason"]
    assert len(body["routes"]) == 3

    first = body["routes"][0]
    assert first["id"] == "A"
    assert first["rank"] == 1
    assert first["geometry"]["type"] == "LineString"
    assert "coordinates" in first["geometry"]
    summary = first["summary"]
    assert summary["distance_mi"] == 100.0
    assert summary["duration_s"] == 36000.0
    assert "arrival_time" in summary
    assert set(summary["miles_by_level"]) >= {
        "LOW",
        "MODERATE",
        "HIGH",
        "SEVERE",
        "NO_TRAVEL",
    }
    assert "avg_risk" in summary
    assert "max_level" in summary

    checkpoints = first["checkpoints"]
    assert len(checkpoints) >= 2
    point = checkpoints[0]
    assert set(point) >= {"mile", "lat", "lon", "eta", "weather", "risk"}
    assert set(point["weather"]) == {
        "wind_mph",
        "gust_mph",
        "rain_in_hr",
        "snow_in_hr",
    }
    assert set(point["risk"]) == {"level", "score", "drivers"}
    assert checkpoints[0]["mile"] == 0.0
    assert checkpoints[-1]["mile"] == pytest.approx(100.0, rel=0.02)

    mock_router.fetch_routes.assert_called_once()
    mock_weather.forecast_at.assert_called_once()


def test_plan_prefers_safer_route_over_faster(settings):
    settings.ORS_API_KEY = "test-key"
    mock_router = MagicMock()
    mock_router.fetch_routes.return_value = [
        _route("A", total_mi=100.0, duration_s=8 * 3600),
        _route("B", total_mi=100.0, duration_s=10 * 3600),
        _route("C", total_mi=100.0, duration_s=11 * 3600),
    ]

    def fake_forecast(queries):
        # Queries are grouped by route A, then B, then C.
        per_route = len(queries) // 3
        samples = []
        for index, _query in enumerate(queries):
            route_index = index // max(per_route, 1)
            offset = index % max(per_route, 1)
            # Route A: severe wind on interior checkpoints.
            if route_index == 0 and 0 < offset < per_route - 1:
                samples.append(_weather_sample(wind=50.0))
            else:
                samples.append(_weather_sample(wind=10.0))
        return samples

    mock_weather = MagicMock()
    mock_weather.forecast_at.side_effect = fake_forecast

    with (
        patch("trips.views._router", return_value=mock_router),
        patch("trips.views._weather", return_value=mock_weather),
    ):
        response = APIClient().post(
            "/api/trips/plan",
            _valid_payload(load_weight_lb=20_000),
            format="json",
        )

    assert response.status_code == 200
    assert response.data["recommended_route_id"] == "B"
    assert response.data["routes"][0]["id"] == "B"


def test_plan_provider_failure_returns_502(settings):
    settings.ORS_API_KEY = "test-key"
    mock_router = MagicMock()
    mock_router.fetch_routes.side_effect = RuntimeError("ORS HTTP 500: boom")

    with patch("trips.views._router", return_value=mock_router):
        response = APIClient().post(
            "/api/trips/plan",
            _valid_payload(),
            format="json",
        )

    assert response.status_code == 502
    assert "ORS" in response.data["detail"]


def test_plan_missing_api_key_returns_503(settings):
    settings.ORS_API_KEY = ""

    response = APIClient().post(
        "/api/trips/plan",
        _valid_payload(),
        format="json",
    )

    assert response.status_code == 503

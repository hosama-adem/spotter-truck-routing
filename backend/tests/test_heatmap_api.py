from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from django.core.cache import caches
from rest_framework.test import APIClient

from trips.domain.corridor import MAX_GRID_POINTS
from trips.domain.sampling import METERS_PER_MILE
from trips.heatmap import HEATMAP_HOURS, HeatmapInput, build_heatmap
from trips.providers.weather import WeatherSample


def _northbound(*, total_mi: float = 100.0) -> list[list[float]]:
    start_lat, start_lon = 40.0, -90.0
    end_lat = start_lat + (total_mi * METERS_PER_MILE / 111_320.0)
    return [[start_lon, start_lat], [start_lon, end_lat]]


def _valid_payload(**overrides):
    payload = {
        "departure_time": "2026-06-01T06:00:00-05:00",
        "load_weight_lb": 42000,
        "geometry": {
            "type": "LineString",
            "coordinates": _northbound(total_mi=100.0),
        },
    }
    payload.update(overrides)
    return payload


def _weather_sample(*, wind: float = 10.0) -> WeatherSample:
    return WeatherSample(
        wind_mph=wind,
        gust_mph=wind + 5,
        rain_in_hr=0.0,
        snow_in_hr=0.0,
        hour=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )


def test_heatmap_requires_fields():
    response = APIClient().post("/api/weather/heatmap", {}, format="json")

    assert response.status_code == 400
    assert "departure_time" in response.data
    assert "load_weight_lb" in response.data
    assert "geometry" in response.data


def test_heatmap_rejects_naive_departure_time():
    response = APIClient().post(
        "/api/weather/heatmap",
        _valid_payload(departure_time="2026-06-01T06:00:00"),
        format="json",
    )

    assert response.status_code == 400
    assert "departure_time" in response.data


def test_heatmap_rejects_bad_geometry_type():
    response = APIClient().post(
        "/api/weather/heatmap",
        _valid_payload(
            geometry={"type": "Point", "coordinates": [[-90.0, 40.0], [-90.0, 41.0]]}
        ),
        format="json",
    )

    assert response.status_code == 400
    assert "geometry" in response.data


def test_heatmap_happy_path_shape(monkeypatch, settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "heatmap-api-happy",
        }
    }
    caches["default"].clear()

    weather = MagicMock()

    def forecast_at(queries):
        return [_weather_sample(wind=10.0 if i % 7 else 40.0) for i, _ in enumerate(queries)]

    weather.forecast_at.side_effect = forecast_at
    monkeypatch.setattr("trips.views._weather", lambda: weather)

    response = APIClient().post(
        "/api/weather/heatmap",
        _valid_payload(),
        format="json",
    )

    assert response.status_code == 200
    body = response.data
    assert body["hours"] == HEATMAP_HOURS
    assert body["start_time"].endswith("Z") or "+" in body["start_time"]
    assert 2 <= len(body["points"]) <= MAX_GRID_POINTS
    assert len(body["risk"]) == HEATMAP_HOURS
    assert all(len(row) == len(body["points"]) for row in body["risk"])
    assert all(0 <= cell <= 4 for row in body["risk"] for cell in row)
    assert weather.forecast_at.called


def test_heatmap_weather_failure_returns_502(monkeypatch, settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "heatmap-api-fail",
        }
    }
    caches["default"].clear()

    weather = MagicMock()
    weather.forecast_at.side_effect = RuntimeError("Open-Meteo down")
    monkeypatch.setattr("trips.views._weather", lambda: weather)

    response = APIClient().post(
        "/api/weather/heatmap",
        _valid_payload(departure_time="2026-07-04T08:00:00-05:00"),
        format="json",
    )

    assert response.status_code == 502
    assert "Open-Meteo" in response.data["detail"]


def test_build_heatmap_cache_hit(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "heatmap-cache-test",
        }
    }
    cache_backend = caches["default"]
    cache_backend.clear()

    weather = MagicMock()
    weather.forecast_at.side_effect = lambda queries: [
        _weather_sample() for _ in queries
    ]

    geometry = [(lon, lat) for lon, lat in _northbound(total_mi=50.0)]
    plan = HeatmapInput(
        geometry=geometry,
        departure_time=datetime(2026, 6, 1, 11, 0, tzinfo=UTC),
        load_weight_lb=42000,
    )

    first = build_heatmap(plan, weather=weather, cache_backend=cache_backend)
    second = build_heatmap(plan, weather=weather, cache_backend=cache_backend)

    assert first == second
    assert weather.forecast_at.call_count == 1
    assert first["hours"] == HEATMAP_HOURS
    assert len(first["risk"]) == HEATMAP_HOURS


def test_build_heatmap_caps_long_corridor():
    weather = MagicMock()
    weather.forecast_at.side_effect = lambda queries: [
        _weather_sample() for _ in queries
    ]
    # ~2000 mi northbound line
    geometry = [(lon, lat) for lon, lat in _northbound(total_mi=2000.0)]
    plan = HeatmapInput(
        geometry=geometry,
        departure_time=datetime(2026, 6, 1, 11, 0, tzinfo=UTC),
        load_weight_lb=20000,
    )

    payload = build_heatmap(
        plan,
        weather=weather,
        cache_backend=MagicMock(get=lambda *_: None, set=lambda *_: None),
    )

    assert len(payload["points"]) <= MAX_GRID_POINTS
    assert len(payload["risk"][0]) == len(payload["points"])
    # 49 hours × N points
    assert weather.forecast_at.call_args[0][0]
    assert len(weather.forecast_at.call_args[0][0]) == HEATMAP_HOURS * len(
        payload["points"]
    )


def test_build_heatmap_hour_zero_is_departure():
    weather = MagicMock()
    captured: list = []

    def forecast_at(queries):
        captured.extend(queries)
        return [_weather_sample() for _ in queries]

    weather.forecast_at.side_effect = forecast_at
    departure = datetime(2026, 6, 1, 15, 30, tzinfo=UTC)
    geometry = [(lon, lat) for lon, lat in _northbound(total_mi=25.0)]

    payload = build_heatmap(
        HeatmapInput(geometry=geometry, departure_time=departure, load_weight_lb=1000),
        weather=weather,
        cache_backend=MagicMock(get=lambda *_: None, set=lambda *_: None),
    )

    assert payload["start_time"] == "2026-06-01T15:30:00Z"
    first_hour_etas = {q.eta for q in captured[: len(payload["points"])]}
    assert first_hour_etas == {departure}
    last_batch_start = captured[-len(payload["points"])].eta
    assert last_batch_start == departure + timedelta(hours=HEATMAP_HOURS - 1)

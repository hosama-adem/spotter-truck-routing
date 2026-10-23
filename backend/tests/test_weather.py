from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from trips.providers.weather import (
    MAX_BATCH_SIZE,
    OpenMeteoWeatherClient,
    WeatherQuery,
    WeatherSample,
    chunked,
    nearest_hour_index,
    parse_hourly_series,
    round_coord,
    sample_from_series,
)


def _hourly_payload(*, start: datetime, hours: int = 6) -> dict:
    times = [(start + timedelta(hours=index)).strftime("%Y-%m-%dT%H:%M") for index in range(hours)]
    return {
        "hourly": {
            "time": times,
            "wind_speed_10m": [10.0 + index for index in range(hours)],
            "wind_gusts_10m": [15.0 + index for index in range(hours)],
            "rain": [0.01 * index for index in range(hours)],
            "showers": [0.02 * index for index in range(hours)],
            "snowfall": [0.0] * hours,
        }
    }


def test_round_coord_to_tenth_degree():
    assert round_coord(41.88) == pytest.approx(41.9)
    assert round_coord(-87.63) == pytest.approx(-87.6)


def test_nearest_hour_picks_closest_timestamp():
    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    times = [start + timedelta(hours=index) for index in range(5)]
    target = start + timedelta(hours=2, minutes=40)

    assert nearest_hour_index(times, target) == 3  # 03:00 is closer than 02:00


def test_rain_is_rain_plus_showers():
    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    series = parse_hourly_series(_hourly_payload(start=start, hours=3))
    sample = sample_from_series(series, start + timedelta(hours=2))

    assert sample.rain_in_hr == pytest.approx(0.02 * 2 + 0.01 * 2)
    assert sample.wind_mph == pytest.approx(12.0)
    assert sample.gust_mph == pytest.approx(17.0)
    assert sample.snow_in_hr == 0.0


def test_chunked_respects_batch_limit():
    items = list(range(250))
    batches = chunked(items, MAX_BATCH_SIZE)

    assert len(batches) == 3
    assert len(batches[0]) == 100
    assert len(batches[1]) == 100
    assert len(batches[2]) == 50


def test_forecast_batches_unique_locations_in_one_http_call(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "weather-batch-test",
        }
    }
    from django.core.cache import caches

    cache_backend = caches["default"]
    cache_backend.clear()

    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    http_get = MagicMock(
        return_value=[
            _hourly_payload(start=start),
            _hourly_payload(start=start),
        ]
    )
    client = OpenMeteoWeatherClient(http_get=http_get, cache_backend=cache_backend)

    queries = [
        WeatherQuery(lat=41.88, lon=-87.63, eta=start + timedelta(hours=1)),
        WeatherQuery(lat=39.74, lon=-104.99, eta=start + timedelta(hours=2)),
        # Same 0.1° cell as the first query — should not add another HTTP location.
        WeatherQuery(lat=41.92, lon=-87.58, eta=start + timedelta(hours=1)),
    ]
    samples = client.forecast_at(queries)

    assert http_get.call_count == 1
    url = http_get.call_args.args[0]
    assert "wind_speed_unit=mph" in url
    assert "precipitation_unit=inch" in url
    assert "latitude=41.9,39.7" in url or "latitude=41.9%2C39.7" in url
    assert len(samples) == 3
    assert isinstance(samples[0], WeatherSample)


def test_forecast_cache_hit_skips_second_http_call(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "weather-cache-test",
        }
    }
    from django.core.cache import caches

    cache_backend = caches["default"]
    cache_backend.clear()

    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    http_get = MagicMock(return_value=_hourly_payload(start=start))
    client = OpenMeteoWeatherClient(http_get=http_get, cache_backend=cache_backend)
    query = WeatherQuery(lat=41.88, lon=-87.63, eta=start + timedelta(hours=1))

    first = client.forecast_at([query])
    second = client.forecast_at([query])

    assert http_get.call_count == 1
    assert first[0].wind_mph == second[0].wind_mph


def test_large_batch_splits_http_calls(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "weather-split-test",
        }
    }
    from django.core.cache import caches

    cache_backend = caches["default"]
    cache_backend.clear()

    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)

    def fake_get(url: str):
        # Count commas in latitude list → number of points in this request.
        query = url.split("?", 1)[1]
        lat_param = next(part for part in query.split("&") if part.startswith("latitude="))
        count = lat_param.count("%2C") + lat_param.count(",") + 1
        return [_hourly_payload(start=start) for _ in range(count)]

    http_get = MagicMock(side_effect=fake_get)
    client = OpenMeteoWeatherClient(
        http_get=http_get,
        cache_backend=cache_backend,
        max_batch=100,
    )
    queries = [
        WeatherQuery(lat=40.0 + index * 0.2, lon=-90.0, eta=start + timedelta(hours=1))
        for index in range(150)
    ]

    samples = client.forecast_at(queries)

    assert len(samples) == 150
    assert http_get.call_count == 2


def test_weather_sample_as_dict_matches_prd_shape():
    sample = WeatherSample(
        wind_mph=18.0,
        gust_mph=27.0,
        rain_in_hr=0.02,
        snow_in_hr=0.0,
        hour=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )
    assert sample.as_dict() == {
        "wind_mph": 18.0,
        "gust_mph": 27.0,
        "rain_in_hr": 0.02,
        "snow_in_hr": 0.0,
    }

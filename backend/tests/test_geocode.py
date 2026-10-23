from unittest.mock import MagicMock, patch

from rest_framework.test import APIClient

from trips.providers.geocode import GeocodeResult, parse_pelias_features


def test_parse_pelias_features_maps_label_lat_lon_and_caps_at_limit():
    payload = {
        "features": [
            {
                "geometry": {"coordinates": [-87.63, 41.88]},
                "properties": {"label": "Chicago, IL, USA"},
            },
            {
                "geometry": {"coordinates": [-87.9, 41.9]},
                "properties": {"name": "Chicago Heights"},
            },
            {
                "geometry": {"coordinates": [-88.0, 42.0]},
                "properties": {"label": "Extra place"},
            },
        ]
    }

    results = parse_pelias_features(payload, limit=2)

    assert results == [
        GeocodeResult(label="Chicago, IL, USA", lat=41.88, lon=-87.63),
        GeocodeResult(label="Chicago Heights", lat=41.9, lon=-87.9),
    ]


def test_parse_pelias_features_skips_incomplete_rows():
    payload = {
        "features": [
            {"geometry": {"coordinates": [-87.63]}, "properties": {"label": "Bad"}},
            {"geometry": {"coordinates": [-87.63, 41.88]}, "properties": {}},
            {
                "geometry": {"coordinates": [-104.99, 39.74]},
                "properties": {"label": "Denver, CO, USA"},
            },
        ]
    }

    assert parse_pelias_features(payload) == [
        GeocodeResult(label="Denver, CO, USA", lat=39.74, lon=-104.99)
    ]


def test_geocode_requires_q():
    response = APIClient().get("/api/geocode")

    assert response.status_code == 400
    assert "q" in response.data["detail"].lower()


def test_geocode_rejects_blank_q():
    response = APIClient().get("/api/geocode", {"q": "   "})

    assert response.status_code == 400


def test_geocode_returns_mapped_results(settings):
    settings.ORS_API_KEY = "test-key"
    mock_geocoder = MagicMock()
    mock_geocoder.autocomplete.return_value = [
        GeocodeResult(label="Chicago, IL, USA", lat=41.88, lon=-87.63),
    ]

    with patch("trips.views._geocoder", return_value=mock_geocoder):
        response = APIClient().get("/api/geocode", {"q": "Chicago"})

    assert response.status_code == 200
    assert response.data == [{"label": "Chicago, IL, USA", "lat": 41.88, "lon": -87.63}]
    mock_geocoder.autocomplete.assert_called_once_with("Chicago", limit=5)


def test_geocode_empty_provider_results_are_ok(settings):
    settings.ORS_API_KEY = "test-key"
    mock_geocoder = MagicMock()
    mock_geocoder.autocomplete.return_value = []

    with patch("trips.views._geocoder", return_value=mock_geocoder):
        response = APIClient().get("/api/geocode", {"q": "zzzz-no-match"})

    assert response.status_code == 200
    assert response.data == []


def test_geocode_missing_api_key_returns_503(settings):
    settings.ORS_API_KEY = ""

    response = APIClient().get("/api/geocode", {"q": "Chicago"})

    assert response.status_code == 503


def test_geocode_provider_failure_returns_502(settings):
    settings.ORS_API_KEY = "test-key"
    mock_geocoder = MagicMock()
    mock_geocoder.autocomplete.side_effect = RuntimeError("Pelias HTTP 500: boom")

    with patch("trips.views._geocoder", return_value=mock_geocoder):
        response = APIClient().get("/api/geocode", {"q": "Chicago"})

    assert response.status_code == 502
    assert "Pelias" in response.data["detail"]

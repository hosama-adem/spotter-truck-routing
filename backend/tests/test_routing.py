import math
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIClient

from trips.providers.routing import (
    METERS_PER_MILE,
    LatLon,
    OpenRouteServiceProvider,
    RouteOption,
    decode_polyline,
    haversine_m,
    offset_perpendicular,
    via_point_candidates,
)

CHICAGO = LatLon(lat=41.88, lon=-87.63)
DENVER = LatLon(lat=39.74, lon=-104.99)


def _sample_route(route_id: str) -> RouteOption:
    return RouteOption(
        id=route_id,
        distance_m=1_609_344.0,
        duration_s=3600.0,
        geometry=[(-87.63, 41.88), (-104.99, 39.74)],
    )


def test_chicago_denver_is_long_haul_over_alternatives_cap():
    assert haversine_m(CHICAGO, DENVER) > 100_000


def test_via_point_candidates_are_direct_left_and_right():
    vias = via_point_candidates(CHICAGO, DENVER, offset_mi=40)

    assert vias[0] is None
    assert vias[1] is not None and vias[2] is not None
    assert vias[1] != vias[2]


def test_perpendicular_offsets_are_roughly_symmetric():
    left = offset_perpendicular(CHICAGO, DENVER, offset_m=40 * METERS_PER_MILE, side=1)
    right = offset_perpendicular(CHICAGO, DENVER, offset_m=40 * METERS_PER_MILE, side=-1)
    mid = LatLon(
        lat=(CHICAGO.lat + DENVER.lat) / 2,
        lon=(CHICAGO.lon + DENVER.lon) / 2,
    )

    left_m = haversine_m(mid, left)
    right_m = haversine_m(mid, right)
    assert math.isclose(left_m, right_m, rel_tol=0.05)
    assert 35 * METERS_PER_MILE < left_m < 45 * METERS_PER_MILE


def test_decode_polyline_known_google_example():
    points = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert len(points) == 3
    assert points[0] == (-120.2, 38.5)
    assert points[1][0] == pytest.approx(-120.95)
    assert points[1][1] == pytest.approx(40.7)


def test_route_option_as_dict_uses_geojson_and_miles():
    payload = _sample_route("A").as_dict()

    assert payload["id"] == "A"
    assert payload["distance_mi"] == 1000.0
    assert payload["duration_s"] == 3600.0
    assert payload["geometry"]["type"] == "LineString"
    assert payload["geometry"]["coordinates"][0] == [-87.63, 41.88]


def test_long_haul_uses_via_points_not_alternatives():
    provider = OpenRouteServiceProvider("test-key")
    via_routes = [_sample_route("A"), _sample_route("B"), _sample_route("C")]

    with (
        patch.object(provider, "_fetch_with_alternatives") as alternatives,
        patch.object(provider, "_fetch_with_via_points", return_value=via_routes) as vias,
    ):
        routes = provider.fetch_routes(CHICAGO, DENVER)

    alternatives.assert_not_called()
    vias.assert_called_once()
    assert [route.id for route in routes] == ["A", "B", "C"]


def test_short_haul_falls_back_when_alternatives_are_thin():
    provider = OpenRouteServiceProvider("test-key")
    short_origin = LatLon(lat=49.41461, lon=8.681495)
    short_dest = LatLon(lat=49.420318, lon=8.687872)
    via_routes = [_sample_route("A"), _sample_route("B"), _sample_route("C")]

    with (
        patch.object(provider, "_fetch_with_alternatives", return_value=[_sample_route("A")]),
        patch.object(provider, "_fetch_with_via_points", return_value=via_routes) as vias,
    ):
        routes = provider.fetch_routes(short_origin, short_dest)

    vias.assert_called_once()
    assert len(routes) == 3


def test_routes_api_requires_coordinates():
    response = APIClient().get("/api/routes")

    assert response.status_code == 400
    assert "origin_lat" in response.data["detail"]


def test_routes_api_rejects_invalid_latitude(settings):
    settings.ORS_API_KEY = "test-key"
    response = APIClient().get(
        "/api/routes",
        {
            "origin_lat": "99",
            "origin_lon": "-87.63",
            "dest_lat": "39.74",
            "dest_lon": "-104.99",
        },
    )

    assert response.status_code == 400
    assert "origin_lat" in response.data["detail"]


def test_routes_api_returns_three_routes(settings):
    settings.ORS_API_KEY = "test-key"
    mock_router = MagicMock()
    mock_router.fetch_routes.return_value = [
        _sample_route("A"),
        _sample_route("B"),
        _sample_route("C"),
    ]

    with patch("trips.views._router", return_value=mock_router):
        response = APIClient().get(
            "/api/routes",
            {
                "origin_lat": "41.88",
                "origin_lon": "-87.63",
                "dest_lat": "39.74",
                "dest_lon": "-104.99",
            },
        )

    assert response.status_code == 200
    assert len(response.data["routes"]) == 3
    assert response.data["routes"][0]["id"] == "A"
    assert response.data["routes"][0]["geometry"]["type"] == "LineString"
    mock_router.fetch_routes.assert_called_once()


def test_routes_api_provider_failure_returns_502(settings):
    settings.ORS_API_KEY = "test-key"
    mock_router = MagicMock()
    mock_router.fetch_routes.side_effect = RuntimeError("ORS HTTP 500: boom")

    with patch("trips.views._router", return_value=mock_router):
        response = APIClient().get(
            "/api/routes",
            {
                "origin_lat": "41.88",
                "origin_lon": "-87.63",
                "dest_lat": "39.74",
                "dest_lon": "-104.99",
            },
        )

    assert response.status_code == 502
    assert "ORS" in response.data["detail"]


def test_routes_api_missing_key_returns_503(settings):
    settings.ORS_API_KEY = ""

    response = APIClient().get(
        "/api/routes",
        {
            "origin_lat": "41.88",
            "origin_lon": "-87.63",
            "dest_lat": "39.74",
            "dest_lon": "-104.99",
        },
    )

    assert response.status_code == 503

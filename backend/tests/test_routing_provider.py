import math

import pytest

from trips.providers.routing import (
    LatLon,
    decode_polyline,
    haversine_m,
    offset_perpendicular,
    via_point_candidates,
)

CHICAGO = LatLon(lat=41.88, lon=-87.63)
DENVER = LatLon(lat=39.74, lon=-104.99)


def test_chicago_denver_is_long_haul_over_alternatives_cap():
    # ORS public API caps alternative_routes at 100 km.
    assert haversine_m(CHICAGO, DENVER) > 100_000


def test_via_point_candidates_are_left_direct_and_right():
    vias = via_point_candidates(CHICAGO, DENVER, offset_mi=40)

    assert vias[0] is None
    assert vias[1] is not None and vias[2] is not None
    assert vias[1] != vias[2]

    mid_lat = (CHICAGO.lat + DENVER.lat) / 2
    assert abs(vias[1].lat - mid_lat) < 1.5
    assert abs(vias[2].lat - mid_lat) < 1.5


def test_perpendicular_offsets_are_roughly_symmetric():
    left = offset_perpendicular(CHICAGO, DENVER, offset_m=40 * 1609.344, side=1)
    right = offset_perpendicular(CHICAGO, DENVER, offset_m=40 * 1609.344, side=-1)
    mid = LatLon(
        lat=(CHICAGO.lat + DENVER.lat) / 2,
        lon=(CHICAGO.lon + DENVER.lon) / 2,
    )

    left_m = haversine_m(mid, left)
    right_m = haversine_m(mid, right)
    assert math.isclose(left_m, right_m, rel_tol=0.05)
    assert 35 * 1609.344 < left_m < 45 * 1609.344


def test_decode_polyline_known_google_example():
    # Classic encoded polyline → (lon, lat) for our GeoJSON geometry shape.
    points = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert len(points) == 3
    assert points[0] == (-120.2, 38.5)
    assert points[1][0] == pytest.approx(-120.95)
    assert points[1][1] == pytest.approx(40.7)

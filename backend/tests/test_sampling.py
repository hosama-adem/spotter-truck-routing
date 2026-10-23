from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from trips.domain.sampling import (
    METERS_PER_MILE,
    Checkpoint,
    RouteLeg,
    checkpoint_miles,
    cumulative_distances_m,
    duration_at_distance_s,
    sample_checkpoints,
)


def _northbound_geometry(*, total_mi: float, segments: int = 20) -> list[tuple[float, float]]:
    """Build a northbound polyline whose haversine length is ~``total_mi``."""
    start_lat, start_lon = 40.0, -90.0
    target_m = total_mi * METERS_PER_MILE
    # 1° latitude ≈ 111_320 m near mid-latitudes.
    end_lat = start_lat + (target_m / 111_320.0)
    step = (end_lat - start_lat) / segments
    return [(start_lon, start_lat + index * step) for index in range(segments + 1)]


def _uniform_legs(total_mi: float, *, hours: float, pieces: int = 4) -> list[RouteLeg]:
    total_m = total_mi * METERS_PER_MILE
    total_s = hours * 3600.0
    return [
        RouteLeg(distance_m=total_m / pieces, duration_s=total_s / pieces)
        for _ in range(pieces)
    ]


def test_checkpoint_miles_interval_25_on_100_mi_line():
    assert checkpoint_miles(100.0, 25) == [0.0, 25.0, 50.0, 75.0, 100.0]


def test_checkpoint_miles_includes_partial_last_segment():
    assert checkpoint_miles(90.0, 25) == [0.0, 25.0, 50.0, 75.0, 90.0]


def test_checkpoint_miles_supports_10_and_50():
    assert checkpoint_miles(50.0, 10) == [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
    assert checkpoint_miles(100.0, 50) == [0.0, 50.0, 100.0]


def test_checkpoint_miles_rejects_invalid_interval():
    with pytest.raises(ValueError, match="10, 25, or 50"):
        checkpoint_miles(100.0, 30)


def test_sample_checkpoints_100_mi_every_25():
    geometry = _northbound_geometry(total_mi=100.0)
    legs = _uniform_legs(100.0, hours=10.0)
    departure = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    checkpoints = sample_checkpoints(
        geometry,
        legs,
        departure_time=departure,
        interval_mi=25,
    )

    miles = [point.mile for point in checkpoints]
    assert miles[0] == 0.0
    assert miles[-1] == pytest.approx(100.0, rel=0.02)
    assert [round(m) for m in miles] == [0, 25, 50, 75, 100]
    assert checkpoints[0].lat == geometry[0][1]
    assert checkpoints[0].lon == geometry[0][0]
    assert checkpoints[-1].lat == geometry[-1][1]
    assert checkpoints[-1].lon == geometry[-1][0]


def test_etas_are_monotonic_and_not_flat_with_uneven_legs():
    geometry = _northbound_geometry(total_mi=100.0)
    # Slow first half, fast second half — constant-speed would be linear.
    half_m = 50.0 * METERS_PER_MILE
    legs = [
        RouteLeg(distance_m=half_m, duration_s=8 * 3600),
        RouteLeg(distance_m=half_m, duration_s=2 * 3600),
    ]
    departure = datetime(2026, 6, 1, 6, 0, tzinfo=UTC)

    checkpoints = sample_checkpoints(
        geometry,
        legs,
        departure_time=departure,
        interval_mi=25,
    )

    etas = [point.eta for point in checkpoints]
    assert etas == sorted(etas)
    assert etas[0] == departure
    assert etas[-1] == departure + timedelta(hours=10)

    # Midpoint should be near the end of the slow half (~8h), not 5h.
    mid = next(point for point in checkpoints if round(point.mile) == 50)
    assert mid.eta == pytest.approx(departure + timedelta(hours=8), abs=timedelta(minutes=20))


def test_duration_interpolation_inside_a_leg():
    legs = [
        RouteLeg(distance_m=100.0, duration_s=100.0),
        RouteLeg(distance_m=100.0, duration_s=300.0),
    ]
    assert duration_at_distance_s(legs, 50.0, route_distance_m=200.0) == pytest.approx(50.0)
    assert duration_at_distance_s(legs, 150.0, route_distance_m=200.0) == pytest.approx(250.0)


def test_sample_checkpoints_rejects_naive_datetime():
    geometry = _northbound_geometry(total_mi=10.0)
    legs = _uniform_legs(10.0, hours=1.0)

    with pytest.raises(ValueError, match="timezone-aware"):
        sample_checkpoints(
            geometry,
            legs,
            departure_time=datetime(2026, 6, 1, 12, 0),
            interval_mi=10,
        )


def test_etas_survive_dst_spring_forward_in_local_zone():
    # America/Chicago springs forward 2026-03-08 02:00 → 03:00 local.
    geometry = _northbound_geometry(total_mi=100.0)
    legs = _uniform_legs(100.0, hours=5.0)
    chicago = ZoneInfo("America/Chicago")
    departure_local = datetime(2026, 3, 8, 0, 30, tzinfo=chicago)

    checkpoints = sample_checkpoints(
        geometry,
        legs,
        departure_time=departure_local,
        interval_mi=25,
    )

    assert all(point.eta.tzinfo == UTC for point in checkpoints)
    assert checkpoints[0].eta == departure_local.astimezone(UTC)
    # Five hours of *route* time later — wall clock skips an hour locally,
    # but UTC elapsed time is still five hours.
    assert checkpoints[-1].eta == checkpoints[0].eta + timedelta(hours=5)
    assert checkpoints[-1].eta == datetime(2026, 3, 8, 11, 30, tzinfo=UTC)


def test_short_route_still_includes_origin_and_destination():
    geometry = _northbound_geometry(total_mi=8.0, segments=4)
    legs = _uniform_legs(8.0, hours=0.5, pieces=2)
    departure = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)

    checkpoints = sample_checkpoints(
        geometry,
        legs,
        departure_time=departure,
        interval_mi=25,
    )

    assert len(checkpoints) == 2
    assert checkpoints[0].mile == 0.0
    assert checkpoints[-1].mile == pytest.approx(8.0, rel=0.05)


def test_checkpoint_as_dict_uses_zulu_eta():
    point = Checkpoint(
        mile=25.0,
        lat=41.0,
        lon=-88.0,
        eta=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )
    assert point.as_dict() == {
        "mile": 25.0,
        "lat": 41.0,
        "lon": -88.0,
        "eta": "2026-06-01T12:00:00Z",
    }


def test_cumulative_distances_require_two_points():
    with pytest.raises(ValueError, match="at least two"):
        cumulative_distances_m([(0.0, 0.0)])

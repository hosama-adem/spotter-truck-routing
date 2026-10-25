from trips.domain.corridor import MAX_GRID_POINTS, sample_corridor_grid
from trips.domain.sampling import METERS_PER_MILE


def _northbound(*, total_mi: float) -> list[tuple[float, float]]:
    start_lat, start_lon = 40.0, -90.0
    end_lat = start_lat + (total_mi * METERS_PER_MILE / 111_320.0)
    return [(start_lon, start_lat), (start_lon, end_lat)]


def test_corridor_grid_includes_endpoints():
    geometry = _northbound(total_mi=100.0)
    points = sample_corridor_grid(geometry, max_points=11)

    assert points[0] == geometry[0]
    assert points[-1] == geometry[-1]
    assert len(points) == 11


def test_corridor_grid_respects_hard_cap():
    geometry = _northbound(total_mi=2000.0)
    points = sample_corridor_grid(geometry, max_points=MAX_GRID_POINTS)

    assert len(points) <= MAX_GRID_POINTS
    assert len(points) == MAX_GRID_POINTS

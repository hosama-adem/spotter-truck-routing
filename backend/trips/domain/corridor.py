"""Corridor grid sampling for the weather heatmap (pure — no I/O).

PRD §7 / §11: cap the corridor at ~300 points so 49 hourly frames stay fast.
"""

from __future__ import annotations

from collections.abc import Sequence

from trips.domain.sampling import (
    METERS_PER_MILE,
    cumulative_distances_m,
    interpolate_point,
)

MAX_GRID_POINTS = 300
# Prefer ~1 mi spacing on short corridors; long trips still hard-cap at 300.
DEFAULT_SPACING_M = METERS_PER_MILE


def sample_corridor_grid(
    geometry: Sequence[tuple[float, float]],
    *,
    max_points: int = MAX_GRID_POINTS,
    spacing_m: float = DEFAULT_SPACING_M,
) -> list[tuple[float, float]]:
    """Evenly sample a (lon, lat) polyline into ≤ ``max_points`` grid cells.

    Always includes the first and last vertices when the line has length.
    """
    if max_points < 1:
        raise ValueError("max_points must be at least 1")
    if len(geometry) < 2:
        raise ValueError("geometry must contain at least two coordinates")

    distances_m = cumulative_distances_m(geometry)
    total_m = distances_m[-1]
    if total_m <= 0:
        lon, lat = geometry[0]
        return [(lon, lat)]

    by_spacing = int(total_m / spacing_m) + 1
    count = min(max_points, max(2, by_spacing))

    points: list[tuple[float, float]] = []
    for index in range(count):
        target_m = 0.0 if count == 1 else total_m * index / (count - 1)
        points.append(interpolate_point(geometry, distances_m, target_m))

    # Snap endpoints to the true vertices.
    points[0] = geometry[0]
    points[-1] = geometry[-1]
    return points

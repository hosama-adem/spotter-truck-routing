from trips.domain.ranking import (
    RankedCheckpoint,
    RouteForRanking,
    miles_by_level,
    rank_routes,
)
from trips.domain.risk import RiskLevel


def _route(
    route_id: str,
    *,
    duration_s: float,
    points: list[tuple[float, RiskLevel]],
) -> RouteForRanking:
    return RouteForRanking(
        id=route_id,
        duration_s=duration_s,
        checkpoints=[
            RankedCheckpoint(mile=mile, level=level) for mile, level in points
        ],
    )


def test_segment_uses_worse_endpoint_level():
    miles = miles_by_level(
        [
            RankedCheckpoint(0.0, RiskLevel.LOW),
            RankedCheckpoint(50.0, RiskLevel.SEVERE),
            RankedCheckpoint(100.0, RiskLevel.LOW),
        ]
    )

    assert miles["SEVERE"] == 100.0
    assert miles["LOW"] == 0.0


def test_fewer_severe_miles_beats_faster_route():
    safe = _route(
        "B",
        duration_s=10 * 3600,
        points=[
            (0.0, RiskLevel.LOW),
            (50.0, RiskLevel.LOW),
            (100.0, RiskLevel.LOW),
        ],
    )
    risky_but_fast = _route(
        "A",
        duration_s=8 * 3600,
        points=[
            (0.0, RiskLevel.LOW),
            (50.0, RiskLevel.SEVERE),
            (100.0, RiskLevel.LOW),
        ],
    )

    result = rank_routes([risky_but_fast, safe])

    assert result.recommended_route_id == "B"
    assert result.routes[0].id == "B"
    assert result.routes[0].miles_by_level["SEVERE"] == 0.0
    assert result.routes[1].miles_by_level["SEVERE"] == 100.0
    assert "severe" in result.recommendation_reason.lower()
    assert "Route B" in result.recommendation_reason


def test_severe_tie_breaks_on_high_miles():
    # Both end with 25 severe miles; A has 25 high miles, B has 75.
    fewer_high = _route(
        "A",
        duration_s=9 * 3600,
        points=[
            (0.0, RiskLevel.LOW),
            (50.0, RiskLevel.LOW),
            (75.0, RiskLevel.HIGH),
            (100.0, RiskLevel.SEVERE),
        ],
    )
    more_high = _route(
        "B",
        duration_s=9 * 3600,
        points=[
            (0.0, RiskLevel.LOW),
            (25.0, RiskLevel.HIGH),
            (75.0, RiskLevel.HIGH),
            (100.0, RiskLevel.SEVERE),
        ],
    )

    result = rank_routes([more_high, fewer_high])

    assert result.recommended_route_id == "A"
    assert result.routes[0].miles_by_level["SEVERE"] == result.routes[1].miles_by_level[
        "SEVERE"
    ]
    assert (
        result.routes[0].miles_by_level["HIGH"]
        < result.routes[1].miles_by_level["HIGH"]
    )


def test_full_risk_tie_prefers_shorter_duration():
    slower = _route(
        "A",
        duration_s=11 * 3600,
        points=[
            (0.0, RiskLevel.LOW),
            (50.0, RiskLevel.MODERATE),
            (100.0, RiskLevel.LOW),
        ],
    )
    faster = _route(
        "B",
        duration_s=10 * 3600,
        points=[
            (0.0, RiskLevel.LOW),
            (50.0, RiskLevel.MODERATE),
            (100.0, RiskLevel.LOW),
        ],
    )

    result = rank_routes([slower, faster])

    assert result.recommended_route_id == "B"
    assert result.routes[0].sort_key[:4] == result.routes[1].sort_key[:4]
    assert result.routes[0].duration_s < result.routes[1].duration_s
    assert "shorter duration" in result.recommendation_reason.lower()


def test_any_no_travel_miles_lose_to_severe_only_route():
    with_no_travel = _route(
        "A",
        duration_s=8 * 3600,
        points=[
            (0.0, RiskLevel.LOW),
            (10.0, RiskLevel.NO_TRAVEL),
            (100.0, RiskLevel.LOW),
        ],
    )
    severe_only = _route(
        "B",
        duration_s=12 * 3600,
        points=[
            (0.0, RiskLevel.LOW),
            (50.0, RiskLevel.SEVERE),
            (100.0, RiskLevel.LOW),
        ],
    )

    result = rank_routes([with_no_travel, severe_only])

    assert result.recommended_route_id == "B"
    assert result.routes[0].miles_by_level["NO_TRAVEL"] == 0.0
    assert result.routes[1].miles_by_level["NO_TRAVEL"] > 0.0
    assert "no-travel" in result.recommendation_reason.lower()


def test_ranking_result_as_dict_includes_ranks():
    routes = [
        _route(
            "A",
            duration_s=10 * 3600,
            points=[(0.0, RiskLevel.LOW), (100.0, RiskLevel.LOW)],
        ),
        _route(
            "B",
            duration_s=11 * 3600,
            points=[(0.0, RiskLevel.LOW), (100.0, RiskLevel.LOW)],
        ),
    ]

    payload = rank_routes(routes).as_dict()

    assert payload["recommended_route_id"] == "A"
    assert payload["routes"][0]["rank"] == 1
    assert payload["routes"][1]["rank"] == 2
    assert payload["recommendation_reason"]

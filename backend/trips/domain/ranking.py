"""Route ranking and recommendation reason (pure — no I/O).

PRD §6 / RC-1: segment risk = worse endpoint; mile-weighted average;
lexicographic sort (no_travel, severe, high, avg_risk, duration).
"""

from __future__ import annotations

from dataclasses import dataclass

from trips.domain.risk import RiskLevel

LEVEL_NAMES = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


@dataclass(frozen=True, slots=True)
class RankedCheckpoint:
    mile: float
    level: RiskLevel


@dataclass(frozen=True, slots=True)
class RouteForRanking:
    id: str
    duration_s: float
    checkpoints: list[RankedCheckpoint]


@dataclass(frozen=True, slots=True)
class RouteRiskSummary:
    id: str
    duration_s: float
    miles_by_level: dict[str, float]
    avg_risk: float
    max_level: RiskLevel
    sort_key: tuple[float, float, float, float, float]

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "duration_s": self.duration_s,
            "miles_by_level": dict(self.miles_by_level),
            "avg_risk": self.avg_risk,
            "max_level": self.max_level.name,
        }


@dataclass(frozen=True, slots=True)
class RankingResult:
    recommended_route_id: str
    recommendation_reason: str
    routes: list[RouteRiskSummary]  # sorted best → worst, rank implied by order

    def as_dict(self) -> dict:
        return {
            "recommended_route_id": self.recommended_route_id,
            "recommendation_reason": self.recommendation_reason,
            "routes": [
                {**route.as_dict(), "rank": index}
                for index, route in enumerate(self.routes, start=1)
            ],
        }


def empty_miles_by_level() -> dict[str, float]:
    return {level.name: 0.0 for level in LEVEL_NAMES}


def miles_by_level(checkpoints: list[RankedCheckpoint]) -> dict[str, float]:
    """Assign each segment the worse endpoint level; sum miles per level."""
    totals = empty_miles_by_level()
    if len(checkpoints) < 2:
        return totals

    ordered = sorted(checkpoints, key=lambda point: point.mile)
    for left, right in zip(ordered, ordered[1:], strict=False):
        segment_mi = max(0.0, right.mile - left.mile)
        if segment_mi <= 0:
            continue
        level = max(left.level, right.level)
        totals[level.name] += segment_mi
    return totals


def average_risk(miles: dict[str, float]) -> float:
    total_mi = sum(miles.values())
    if total_mi <= 0:
        return 0.0
    weighted = sum(RiskLevel[name] * value for name, value in miles.items())
    return weighted / total_mi


def max_level_from_miles(miles: dict[str, float]) -> RiskLevel:
    present = [RiskLevel[name] for name, value in miles.items() if value > 0]
    return max(present) if present else RiskLevel.LOW


def summarize_route(route: RouteForRanking) -> RouteRiskSummary:
    miles = miles_by_level(route.checkpoints)
    avg = average_risk(miles)
    return RouteRiskSummary(
        id=route.id,
        duration_s=route.duration_s,
        miles_by_level={name: round(value, 4) for name, value in miles.items()},
        avg_risk=round(avg, 6),
        max_level=max_level_from_miles(miles),
        sort_key=(
            miles[RiskLevel.NO_TRAVEL.name],
            miles[RiskLevel.SEVERE.name],
            miles[RiskLevel.HIGH.name],
            avg,
            route.duration_s,
        ),
    )


def _format_miles(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 0.05:
        return str(rounded)
    return f"{value:.1f}"


def _format_duration_delta(seconds: float) -> str:
    minutes = abs(seconds) / 60.0
    if minutes < 1:
        return "under a minute"
    rounded = int(round(minutes))
    return f"{rounded} min"


def build_recommendation_reason(
    winner: RouteRiskSummary,
    runner_up: RouteRiskSummary | None,
) -> str:
    if runner_up is None:
        return f"Route {winner.id} recommended: only available route."

    w_nt = winner.miles_by_level[RiskLevel.NO_TRAVEL.name]
    r_nt = runner_up.miles_by_level[RiskLevel.NO_TRAVEL.name]
    w_sev = winner.miles_by_level[RiskLevel.SEVERE.name]
    r_sev = runner_up.miles_by_level[RiskLevel.SEVERE.name]
    w_high = winner.miles_by_level[RiskLevel.HIGH.name]
    r_high = runner_up.miles_by_level[RiskLevel.HIGH.name]
    duration_delta = winner.duration_s - runner_up.duration_s

    if w_nt < r_nt:
        focus = (
            f"{_format_miles(w_nt)} no-travel mi vs {_format_miles(r_nt)} "
            f"on Route {runner_up.id}"
        )
    elif w_sev < r_sev:
        focus = (
            f"{_format_miles(w_sev)} severe mi vs {_format_miles(r_sev)} "
            f"on Route {runner_up.id}"
        )
    elif w_high < r_high:
        focus = (
            f"{_format_miles(w_high)} high-risk mi vs {_format_miles(r_high)} "
            f"on Route {runner_up.id}"
        )
    elif winner.avg_risk < runner_up.avg_risk:
        focus = (
            f"lower average risk ({winner.avg_risk:.2f} vs {runner_up.avg_risk:.2f} "
            f"on Route {runner_up.id})"
        )
    else:
        focus = f"same risk profile as Route {runner_up.id}, shorter duration"

    if duration_delta > 0:
        tradeoff = f"; only {_format_duration_delta(duration_delta)} slower"
    elif duration_delta < 0:
        tradeoff = f"; {_format_duration_delta(duration_delta)} faster"
    else:
        tradeoff = "; same duration"

    return f"Route {winner.id} recommended: {focus}{tradeoff}."


def rank_routes(routes: list[RouteForRanking]) -> RankingResult:
    if not routes:
        raise ValueError("routes must not be empty")

    summaries = [summarize_route(route) for route in routes]
    summaries.sort(key=lambda item: item.sort_key)

    winner = summaries[0]
    runner_up = summaries[1] if len(summaries) > 1 else None
    reason = build_recommendation_reason(winner, runner_up)

    return RankingResult(
        recommended_route_id=winner.id,
        recommendation_reason=reason,
        routes=summaries,
    )

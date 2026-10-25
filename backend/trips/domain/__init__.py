"""Pure trip logic: sampling, risk, ranking, corridor grid. No I/O."""

from trips.domain.corridor import MAX_GRID_POINTS, sample_corridor_grid
from trips.domain.ranking import (
    RankedCheckpoint,
    RankingResult,
    RouteForRanking,
    rank_routes,
)
from trips.domain.risk import RiskAssessment, RiskLevel, classify_checkpoint
from trips.domain.sampling import (
    ALLOWED_INTERVALS_MI,
    Checkpoint,
    RouteLeg,
    sample_checkpoints,
)

__all__ = [
    "ALLOWED_INTERVALS_MI",
    "Checkpoint",
    "MAX_GRID_POINTS",
    "RankedCheckpoint",
    "RankingResult",
    "RiskAssessment",
    "RiskLevel",
    "RouteForRanking",
    "RouteLeg",
    "classify_checkpoint",
    "rank_routes",
    "sample_checkpoints",
    "sample_corridor_grid",
]

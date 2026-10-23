"""Checkpoint risk classification with load rules (pure — no I/O).

PRD §5 / RK-1 / RK-2: ordinal levels, wind/rain/snow thresholds, load rules
that can only raise wind, final level = max of the three.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    level: RiskLevel
    score: int
    drivers: list[str]

    def as_dict(self) -> dict:
        return {
            "level": self.level.name,
            "score": self.score,
            "drivers": list(self.drivers),
        }


def classify_wind(wind_mph: float) -> RiskLevel:
    if wind_mph < 25:
        return RiskLevel.LOW
    if wind_mph < 35:
        return RiskLevel.MODERATE
    if wind_mph < 45:
        return RiskLevel.HIGH
    if wind_mph < 55:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_rain(rain_in_hr: float) -> RiskLevel:
    if rain_in_hr < 0.10:
        return RiskLevel.LOW
    if rain_in_hr < 0.25:
        return RiskLevel.MODERATE
    if rain_in_hr < 0.50:
        return RiskLevel.HIGH
    if rain_in_hr <= 1.00:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_snow(snow_in_hr: float) -> RiskLevel:
    if snow_in_hr < 0.5:
        return RiskLevel.LOW
    if snow_in_hr < 1.0:
        return RiskLevel.MODERATE
    if snow_in_hr < 2.0:
        return RiskLevel.HIGH
    if snow_in_hr <= 3.0:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def apply_load_rules(
    wind_level: RiskLevel,
    *,
    wind_mph: float,
    load_weight_lb: float,
) -> tuple[RiskLevel, bool]:
    """Raise wind level per PRD load rules. Returns (level, raised?)."""
    raised = wind_level

    if wind_mph >= 55:
        raised = RiskLevel.NO_TRAVEL
    elif 45 <= wind_mph < 55 and load_weight_lb > 30_000:
        raised = RiskLevel.NO_TRAVEL
    elif 35 <= wind_mph < 45 and load_weight_lb > 40_000:
        raised = RiskLevel.SEVERE if raised < RiskLevel.SEVERE else raised

    return raised, raised > wind_level


def classify_checkpoint(
    *,
    wind_mph: float,
    rain_in_hr: float,
    snow_in_hr: float,
    load_weight_lb: float,
) -> RiskAssessment:
    """Classify one checkpoint; drivers list why the final level was chosen."""
    wind_base = classify_wind(wind_mph)
    wind_level, load_raised = apply_load_rules(
        wind_base,
        wind_mph=wind_mph,
        load_weight_lb=load_weight_lb,
    )
    rain_level = classify_rain(rain_in_hr)
    snow_level = classify_snow(snow_in_hr)
    final = max(wind_level, rain_level, snow_level)

    drivers: list[str] = []
    if wind_level == final:
        drivers.append("wind")
        if load_raised:
            drivers.append("load")
    if rain_level == final:
        drivers.append("rain")
    if snow_level == final:
        drivers.append("snow")

    return RiskAssessment(level=final, score=int(final), drivers=drivers)

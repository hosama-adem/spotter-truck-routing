import pytest

from trips.domain.risk import RiskLevel, classify_checkpoint


@pytest.mark.parametrize(
    ("wind_mph", "expected"),
    [
        (24.9, RiskLevel.LOW),
        (25, RiskLevel.MODERATE),
        (34.9, RiskLevel.MODERATE),
        (35, RiskLevel.HIGH),
        (44.9, RiskLevel.HIGH),
        (45, RiskLevel.SEVERE),
        (54.9, RiskLevel.SEVERE),
        (55, RiskLevel.NO_TRAVEL),
    ],
)
def test_wind_thresholds(wind_mph: float, expected: RiskLevel):
    result = classify_checkpoint(
        wind_mph=wind_mph,
        rain_in_hr=0.0,
        snow_in_hr=0.0,
        load_weight_lb=20_000,
    )
    assert result.level == expected
    assert result.score == int(expected)
    assert "wind" in result.drivers


@pytest.mark.parametrize(
    ("rain_in_hr", "expected"),
    [
        (0.09, RiskLevel.LOW),
        (0.10, RiskLevel.MODERATE),
        (0.25, RiskLevel.HIGH),
        (0.50, RiskLevel.SEVERE),
        (1.00, RiskLevel.SEVERE),
        (1.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_rain_thresholds(rain_in_hr: float, expected: RiskLevel):
    result = classify_checkpoint(
        wind_mph=10.0,
        rain_in_hr=rain_in_hr,
        snow_in_hr=0.0,
        load_weight_lb=20_000,
    )
    assert result.level == expected
    if expected != RiskLevel.LOW:
        assert "rain" in result.drivers


@pytest.mark.parametrize(
    ("snow_in_hr", "expected"),
    [
        (0.49, RiskLevel.LOW),
        (0.5, RiskLevel.MODERATE),
        (1.0, RiskLevel.HIGH),
        (2.0, RiskLevel.SEVERE),
        (3.0, RiskLevel.SEVERE),
        (3.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_snow_thresholds(snow_in_hr: float, expected: RiskLevel):
    result = classify_checkpoint(
        wind_mph=10.0,
        rain_in_hr=0.0,
        snow_in_hr=snow_in_hr,
        load_weight_lb=20_000,
    )
    assert result.level == expected
    if expected != RiskLevel.LOW:
        assert "snow" in result.drivers


def test_load_rule_wind_50_at_30000_stays_severe():
    result = classify_checkpoint(
        wind_mph=50.0,
        rain_in_hr=0.0,
        snow_in_hr=0.0,
        load_weight_lb=30_000,
    )
    assert result.level == RiskLevel.SEVERE
    assert result.drivers == ["wind"]


def test_load_rule_wind_50_over_30000_becomes_no_travel():
    result = classify_checkpoint(
        wind_mph=50.0,
        rain_in_hr=0.0,
        snow_in_hr=0.0,
        load_weight_lb=30_001,
    )
    assert result.level == RiskLevel.NO_TRAVEL
    assert result.drivers == ["wind", "load"]


def test_load_rule_wind_40_at_40000_stays_high():
    result = classify_checkpoint(
        wind_mph=40.0,
        rain_in_hr=0.0,
        snow_in_hr=0.0,
        load_weight_lb=40_000,
    )
    assert result.level == RiskLevel.HIGH
    assert result.drivers == ["wind"]


def test_load_rule_wind_40_over_40000_becomes_severe():
    result = classify_checkpoint(
        wind_mph=40.0,
        rain_in_hr=0.0,
        snow_in_hr=0.0,
        load_weight_lb=40_001,
    )
    assert result.level == RiskLevel.SEVERE
    assert result.drivers == ["wind", "load"]


def test_final_level_is_max_of_conditions():
    result = classify_checkpoint(
        wind_mph=10.0,
        rain_in_hr=0.6,
        snow_in_hr=0.0,
        load_weight_lb=20_000,
    )
    assert result.level == RiskLevel.SEVERE
    assert result.drivers == ["rain"]


def test_wind_55_is_no_travel_for_any_load():
    light = classify_checkpoint(
        wind_mph=55.0,
        rain_in_hr=0.0,
        snow_in_hr=0.0,
        load_weight_lb=1,
    )
    heavy = classify_checkpoint(
        wind_mph=55.0,
        rain_in_hr=0.0,
        snow_in_hr=0.0,
        load_weight_lb=80_000,
    )
    assert light.level == RiskLevel.NO_TRAVEL
    assert heavy.level == RiskLevel.NO_TRAVEL
    assert light.drivers == ["wind"]


def test_as_dict_matches_prd_checkpoint_risk_shape():
    result = classify_checkpoint(
        wind_mph=50.0,
        rain_in_hr=0.0,
        snow_in_hr=0.0,
        load_weight_lb=30_001,
    )
    assert result.as_dict() == {
        "level": "NO_TRAVEL",
        "score": 4,
        "drivers": ["wind", "load"],
    }

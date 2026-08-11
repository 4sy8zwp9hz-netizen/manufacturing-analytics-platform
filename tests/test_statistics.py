import pytest

from manufacturing_analytics.domain.statistics import calculate_pareto, calculate_yield


def test_weighted_yield_uses_aggregate_counts() -> None:
    assert calculate_yield(180, 200) == 0.9
    assert calculate_yield(0, 0) == 0.0
    with pytest.raises(ValueError):
        calculate_yield(11, 10)


def test_pareto_sorts_and_calculates_contribution() -> None:
    result = calculate_pareto(
        [
            {"category": "Open", "count": 20},
            {"category": "Particle", "count": 50},
            {"category": "Scratch", "count": 30},
        ]
    )

    assert [row.category for row in result] == ["Particle", "Scratch", "Open"]
    assert [row.percentage for row in result] == [50.0, 30.0, 20.0]
    assert [row.cumulative_percentage for row in result] == [50.0, 80.0, 100.0]


def test_pareto_rejects_negative_counts() -> None:
    with pytest.raises(ValueError):
        calculate_pareto([{"category": "Impossible", "count": -1}])

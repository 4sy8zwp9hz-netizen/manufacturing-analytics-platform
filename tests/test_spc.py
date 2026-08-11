import pytest

from manufacturing_analytics.domain.spc import (
    IndividualsLimits,
    evaluate_control_rules,
    individuals_limits,
    moving_ranges,
    validate_rational_subgroup,
)


def test_moving_ranges_and_individuals_limits() -> None:
    values = [1.0, 2.0, 4.0, 3.0]
    assert moving_ranges(values) == [1.0, 2.0, 1.0]

    limits = individuals_limits(values)
    assert limits.center_line == 2.5
    assert limits.average_moving_range == pytest.approx(4 / 3)
    assert limits.upper_control_limit > limits.center_line
    assert limits.moving_range_upper_limit == pytest.approx(3.267 * 4 / 3)


def test_control_rules_return_point_evidence() -> None:
    values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 4.0]
    records = [
        {"measurement_id": index + 1, "measured_value": value} for index, value in enumerate(values)
    ]
    limits = IndividualsLimits(0.0, -3.0, 3.0, 1.0, 3.267)
    violations = evaluate_control_rules(records, limits)

    assert {violation.rule_code for violation in violations} == {"RULE_1", "RULE_2", "RULE_3"}
    assert all(violation.evidence_indices for violation in violations)
    assert any(violation.measurement_id == 9 for violation in violations)


def test_rational_subgroup_validation_rejects_arbitrary_grouping() -> None:
    validate_rational_subgroup("INDIVIDUALS")
    validate_rational_subgroup(
        "XBAR_S_LOT_TOOL",
        ("lot_id", "tool_id", "product_code", "operation_code", "characteristic_id"),
    )
    with pytest.raises(ValueError):
        validate_rational_subgroup("INDIVIDUALS", ("adjacent_rows",))
    with pytest.raises(ValueError):
        validate_rational_subgroup("XBAR_S_LOT_TOOL", ("lot_id",))

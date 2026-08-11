"""Statistical process-control calculations for time-ordered measurements."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any


@dataclass(frozen=True)
class IndividualsLimits:
    center_line: float
    lower_control_limit: float
    upper_control_limit: float
    average_moving_range: float
    moving_range_upper_limit: float


@dataclass(frozen=True)
class RuleViolation:
    rule_code: str
    rule_name: str
    point_index: int
    measurement_id: int
    evidence_indices: tuple[int, ...]
    evidence: str


def moving_ranges(values: list[float]) -> list[float]:
    if len(values) < 2:
        return []
    return [abs(current - previous) for previous, current in zip(values, values[1:], strict=False)]


def individuals_limits(values: list[float]) -> IndividualsLimits:
    """Estimate I/MR limits using MR-bar/d2, where d2=1.128 for ranges of two."""
    if len(values) < 2:
        raise ValueError("Individuals limits require at least two time-ordered values")
    center = fmean(values)
    average_range = fmean(moving_ranges(values))
    sigma = average_range / 1.128
    return IndividualsLimits(
        center_line=center,
        lower_control_limit=center - 3 * sigma,
        upper_control_limit=center + 3 * sigma,
        average_moving_range=average_range,
        moving_range_upper_limit=3.267 * average_range,
    )


def validate_rational_subgroup(method: str, grouping_fields: tuple[str, ...] = ()) -> None:
    """Reject implicit adjacent-row grouping and require an engineering definition."""
    if method == "INDIVIDUALS":
        if grouping_fields:
            raise ValueError("Individuals charts do not use subgroup fields")
        return
    if method == "XBAR_S_LOT_TOOL":
        required = {"lot_id", "tool_id", "product_code", "operation_code", "characteristic_id"}
        if not required.issubset(grouping_fields):
            raise ValueError(
                "Xbar-S requires same-lot, tool, product, operation, and characteristic"
            )
        return
    raise ValueError(f"Unsupported subgroup method: {method}")


def evaluate_control_rules(
    records: list[dict[str, Any]], limits: IndividualsLimits
) -> list[RuleViolation]:
    """Evaluate three transparent rules against time-ordered Individuals values."""
    values = [float(record["measured_value"]) for record in records]
    violations: list[RuleViolation] = []
    for index, (record, value) in enumerate(zip(records, values, strict=True)):
        if value < limits.lower_control_limit or value > limits.upper_control_limit:
            violations.append(
                RuleViolation(
                    "RULE_1",
                    "Point beyond an Individuals control limit",
                    index,
                    int(record["measurement_id"]),
                    (index,),
                    f"Value {value:.3f} is outside [{limits.lower_control_limit:.3f}, "
                    f"{limits.upper_control_limit:.3f}].",
                )
            )
        if index >= 7:
            window = values[index - 7 : index + 1]
            if all(value > limits.center_line for value in window) or all(
                value < limits.center_line for value in window
            ):
                violations.append(
                    RuleViolation(
                        "RULE_2",
                        "Eight-point run on one side of center",
                        index,
                        int(record["measurement_id"]),
                        tuple(range(index - 7, index + 1)),
                        "Eight consecutive values are on the same side of the center line.",
                    )
                )
        if index >= 5:
            window = values[index - 5 : index + 1]
            increasing = all(left < right for left, right in zip(window, window[1:], strict=False))
            decreasing = all(left > right for left, right in zip(window, window[1:], strict=False))
            if increasing or decreasing:
                direction = "increasing" if increasing else "decreasing"
                violations.append(
                    RuleViolation(
                        "RULE_3",
                        "Six-point monotonic trend",
                        index,
                        int(record["measurement_id"]),
                        tuple(range(index - 5, index + 1)),
                        f"Six consecutive values are strictly {direction}.",
                    )
                )
    return violations

"""Reusable statistical calculations independent of SQL and presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParetoItem:
    category: str
    count: int
    percentage: float
    cumulative_percentage: float


def calculate_yield(good_units: int, total_units: int) -> float:
    """Return weighted yield as a fraction, or zero for an empty cohort."""
    if good_units < 0 or total_units < 0 or good_units > total_units:
        raise ValueError("Yield counts must satisfy 0 <= good_units <= total_units")
    return 0.0 if total_units == 0 else good_units / total_units


def calculate_pareto(rows: list[dict[str, Any]]) -> list[ParetoItem]:
    """Sort category counts and calculate contribution and cumulative percentages."""
    normalized = sorted(
        ((str(row["category"]), int(row["count"])) for row in rows),
        key=lambda item: (-item[1], item[0]),
    )
    if any(count < 0 for _, count in normalized):
        raise ValueError("Pareto counts cannot be negative")
    total = sum(count for _, count in normalized)
    cumulative = 0
    results: list[ParetoItem] = []
    for category, count in normalized:
        cumulative += count
        results.append(
            ParetoItem(
                category=category,
                count=count,
                percentage=round((count / total * 100) if total else 0.0, 2),
                cumulative_percentage=round((cumulative / total * 100) if total else 0.0, 2),
            )
        )
    return results

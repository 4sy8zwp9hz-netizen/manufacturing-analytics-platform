"""Operational-flow calculations kept independent from SQL and presentation."""

from __future__ import annotations

from datetime import datetime
from statistics import fmean, median


def elapsed_minutes(start: str, end: str) -> float:
    value = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    return value.total_seconds() / 60


def summarize_durations(values: list[float]) -> dict[str, float]:
    if not values:
        return {"average": 0.0, "median": 0.0, "maximum": 0.0}
    return {
        "average": round(fmean(values), 2),
        "median": round(median(values), 2),
        "maximum": round(max(values), 2),
    }

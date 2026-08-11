"""Manufacturing-event completeness, sequence, latency, and freshness checks."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def evaluate_event_quality(
    events: list[dict[str, Any]],
    expected_operations: tuple[str, ...],
    maximum_arrival_delay: timedelta = timedelta(hours=1),
) -> set[str]:
    issue_types: set[str] = set()
    operations = [str(event["operation_code"]) for event in events]
    if set(expected_operations) - set(operations):
        issue_types.add("MISSING_PROCESS_EVENT")
    source_keys = [str(event["source_event_key"]) for event in events]
    if len(source_keys) != len(set(source_keys)):
        issue_types.add("DUPLICATE_SOURCE_EVENT")
    ordered = sorted(events, key=lambda event: int(event["sequence_number"]))
    timestamps = [datetime.fromisoformat(str(event["event_timestamp"])) for event in ordered]
    if any(
        current < previous for previous, current in zip(timestamps, timestamps[1:], strict=False)
    ):
        issue_types.add("IMPOSSIBLE_SEQUENCE")
    if any(
        datetime.fromisoformat(str(event["arrival_timestamp"]))
        - datetime.fromisoformat(str(event["event_timestamp"]))
        > maximum_arrival_delay
        for event in events
    ):
        issue_types.add("DELAYED_EVENT")
    return issue_types


def freshness(
    watermark_timestamp: str, observed_timestamp: str, expected_max_lag_minutes: int
) -> dict[str, Any]:
    watermark = datetime.fromisoformat(watermark_timestamp)
    observed = datetime.fromisoformat(observed_timestamp)
    lag_minutes = (observed - watermark).total_seconds() / 60
    return {
        "lag_minutes": round(lag_minutes, 1),
        "status": "STALE" if lag_minutes > expected_max_lag_minutes else "CURRENT",
    }

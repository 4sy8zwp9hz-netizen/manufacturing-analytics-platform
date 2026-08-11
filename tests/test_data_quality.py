from datetime import timedelta

from manufacturing_analytics.domain.data_quality import evaluate_event_quality, freshness


def test_event_quality_detects_completeness_sequence_duplicate_and_delay() -> None:
    events = [
        {
            "operation_code": "OP-A",
            "sequence_number": 1,
            "source_event_key": "DUPLICATE",
            "event_timestamp": "2026-01-01T02:00:00+00:00",
            "arrival_timestamp": "2026-01-01T04:00:00+00:00",
        },
        {
            "operation_code": "OP-B",
            "sequence_number": 2,
            "source_event_key": "DUPLICATE",
            "event_timestamp": "2026-01-01T01:00:00+00:00",
            "arrival_timestamp": "2026-01-01T01:05:00+00:00",
        },
    ]
    issues = evaluate_event_quality(events, ("OP-A", "OP-B", "OP-C"), timedelta(hours=1))
    assert issues == {
        "MISSING_PROCESS_EVENT",
        "DUPLICATE_SOURCE_EVENT",
        "IMPOSSIBLE_SEQUENCE",
        "DELAYED_EVENT",
    }


def test_freshness_uses_source_specific_lag_objective() -> None:
    current = freshness("2026-02-01T11:55:00+00:00", "2026-02-01T12:00:00+00:00", 10)
    stale = freshness("2026-02-01T10:00:00+00:00", "2026-02-01T12:00:00+00:00", 60)
    assert current == {"lag_minutes": 5.0, "status": "CURRENT"}
    assert stale == {"lag_minutes": 120.0, "status": "STALE"}

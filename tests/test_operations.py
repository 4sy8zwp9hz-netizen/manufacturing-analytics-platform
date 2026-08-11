from manufacturing_analytics.domain.operations import elapsed_minutes, summarize_durations


def test_cycle_and_queue_time_calculations() -> None:
    assert elapsed_minutes("2026-01-01T01:00:00+00:00", "2026-01-01T01:42:00+00:00") == 42
    assert elapsed_minutes("2026-01-01T02:00:00+00:00", "2026-01-01T01:30:00+00:00") == -30
    assert summarize_durations([10, 20, 30]) == {
        "average": 20.0,
        "median": 20,
        "maximum": 30,
    }

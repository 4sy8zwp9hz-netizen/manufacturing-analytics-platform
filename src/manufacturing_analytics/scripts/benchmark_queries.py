"""Repeatable local timing baseline for the Phase 2 analytics queries."""

from __future__ import annotations

from collections import defaultdict
from statistics import median

from manufacturing_analytics.analytics.models import AnalyticsFilters
from manufacturing_analytics.analytics.process_service import ProcessAnalyticsService
from manufacturing_analytics.analytics.service import AnalyticsService
from manufacturing_analytics.config import get_settings
from manufacturing_analytics.data.analytics_repository import AnalyticsRepository
from manufacturing_analytics.data.database import Database
from manufacturing_analytics.data.process_repository import ProcessRepository
from manufacturing_analytics.services.bootstrap import ensure_demo_data


def main(iterations: int = 20) -> None:
    settings = get_settings()
    database = Database(settings.database_path)
    ensure_demo_data(database, settings)
    service = AnalyticsService(AnalyticsRepository(database))
    process_service = ProcessAnalyticsService(ProcessRepository(database))

    for _ in range(iterations):
        service.yield_overview(AnalyticsFilters())
        service.pareto(AnalyticsFilters())
        service.lot_investigation("LOT-0101")
        service.wafer_investigation("WFR-00001")
        process_service.process_monitor("ETCH_DEPTH", AnalyticsFilters())
        process_service.operations_flow(AnalyticsFilters())
        process_service.data_quality()

    grouped: dict[str, list[float]] = defaultdict(list)
    for timing in service.timings:
        grouped[timing.query_name].append(timing.duration_ms)
    for timing in process_service.timings:
        grouped[timing.query_name].append(timing.duration_ms)

    print("Query | Samples | Median ms | Approx. p95 ms")
    print("--- | ---: | ---: | ---:")
    for name, durations in sorted(grouped.items()):
        ordered = sorted(durations)
        p95_index = min(len(ordered) - 1, round((len(ordered) - 1) * 0.95))
        print(f"{name} | {len(durations)} | {median(durations):.3f} | {ordered[p95_index]:.3f}")


if __name__ == "__main__":
    main()

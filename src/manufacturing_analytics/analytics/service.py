"""Manufacturing metric definitions and investigation workflow orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any, TypeVar

from manufacturing_analytics.analytics.models import AnalyticsFilters, QueryTiming, YieldKpis
from manufacturing_analytics.data.analytics_repository import AnalyticsRepository
from manufacturing_analytics.domain.statistics import calculate_pareto, calculate_yield

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


class AnalyticsService:
    """Define metrics, combine queries, and record lightweight performance baselines."""

    DISTRIBUTION_BINS = (
        ("<85%", 0, 85),
        ("85–90%", 85, 90),
        ("90–93%", 90, 93),
        ("93–95%", 93, 95),
        ("95–97%", 95, 97),
        ("≥97%", 97, 101),
    )

    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository
        self.timings: list[QueryTiming] = []

    def _timed(self, name: str, query: Callable[[], T]) -> T:
        started = perf_counter()
        result = query()
        duration_ms = (perf_counter() - started) * 1000
        self.timings.append(QueryTiming(name, duration_ms))
        self.timings = self.timings[-1000:]
        LOGGER.info("analytics_query name=%s duration_ms=%.3f", name, duration_ms)
        return result

    def yield_overview(self, filters: AnalyticsFilters) -> dict[str, Any]:
        raw_kpis = self._timed("yield_kpis", lambda: self.repository.kpis(filters))
        kpis = YieldKpis(
            overall_yield=calculate_yield(raw_kpis["good_die"], raw_kpis["total_die"]),
            wafer_count=raw_kpis["wafer_count"],
            lot_count=raw_kpis["lot_count"],
            work_order_count=raw_kpis["work_order_count"],
        )
        wafer_yields = self._timed(
            "yield_distribution_source", lambda: self.repository.wafer_yields(filters)
        )
        distribution = [
            {
                "category": label,
                "count": sum(lower <= row["yield_percent"] < upper for row in wafer_yields),
            }
            for label, lower, upper in self.DISTRIBUTION_BINS
        ]
        comparison_operation = filters.operation_code or "OP-400"
        return {
            "kpis": kpis,
            "trend": self._timed("yield_trend", lambda: self.repository.yield_trend(filters)),
            "distribution": distribution,
            "lots": self._timed(
                "lot_yield_comparison", lambda: self.repository.grouped_yield(filters, "lot")
            ),
            "products": self._timed(
                "product_yield_comparison",
                lambda: self.repository.grouped_yield(filters, "product"),
            ),
            "tools": self._timed(
                "tool_yield_comparison",
                lambda: self.repository.tool_yield(filters, comparison_operation),
            ),
            "comparison_operation": comparison_operation,
        }

    def pareto(self, filters: AnalyticsFilters) -> list[Any]:
        rows = self._timed("defect_pareto", lambda: self.repository.defect_counts(filters))
        return calculate_pareto(rows)

    def wafer_index(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        return self._timed("wafer_index", lambda: self.repository.wafer_index(filters))

    def lot_investigation(self, lot_id: str) -> dict[str, Any] | None:
        summary = self._timed("lot_detail", lambda: self.repository.lot_detail(lot_id))
        if summary is None:
            return None
        filters = AnalyticsFilters(lot_id=lot_id)
        return {
            "summary": summary,
            "wafers": self._timed("lot_wafers", lambda: self.repository.lot_wafers(lot_id)),
            "genealogy": self._timed(
                "lot_genealogy", lambda: self.repository.lot_genealogy(lot_id)
            ),
            "pareto": self.pareto(filters),
        }

    def wafer_investigation(self, wafer_id: str) -> dict[str, Any] | None:
        summary = self._timed("wafer_detail", lambda: self.repository.wafer_detail(wafer_id))
        if summary is None:
            return None
        return {
            "summary": summary,
            "map": self._timed("wafer_map", lambda: self.repository.wafer_map(wafer_id)),
            "genealogy": self._timed(
                "wafer_genealogy", lambda: self.repository.wafer_genealogy(wafer_id)
            ),
            "defects": self._timed(
                "wafer_defects", lambda: self.repository.wafer_defects(wafer_id)
            ),
        }

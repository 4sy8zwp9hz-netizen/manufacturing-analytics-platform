"""Yield-platform use cases over one immutable analytical generation."""

from __future__ import annotations

from math import prod

from manufacturing_analytics.data.platform_repository import PlatformRepository


class YieldPlatformService:
    def __init__(self, repository: PlatformRepository) -> None:
        self.repository = repository

    def dashboard(
        self, filters: dict[str, str | None], time_grain: str = "month"
    ) -> dict[str, object]:
        stages = self.repository.stage_metrics(filters)
        production_rates = [
            stage["yield_rate"] for stage in stages if stage["yield_rate"] is not None
        ]
        trend = self.repository.trend(filters, time_grain)
        return {
            "metadata": self.repository.metadata(),
            "stages": stages,
            "rolled_yield": prod(production_rates) if production_rates else 0.0,
            "trend": [
                {**row, "yield_rate": row["good"] / row["denominator"]}
                for row in trend
                if row["denominator"]
            ],
            "failures": self.repository.failures(filters),
            "wafers": self.repository.wafers(filters),
            "options": self.repository.options(),
            "time_grain": time_grain,
        }

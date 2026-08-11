"""Typed inputs and outputs shared by analytics workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode


@dataclass(frozen=True)
class AnalyticsFilters:
    date_from: date | None = None
    date_to: date | None = None
    product_code: str | None = None
    work_order_id: str | None = None
    lot_id: str | None = None
    operation_code: str | None = None
    tool_id: str | None = None

    def __post_init__(self) -> None:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Start date must not be after end date")

    def as_query_params(self) -> dict[str, str]:
        values = {
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "product_code": self.product_code,
            "work_order_id": self.work_order_id,
            "lot": self.lot_id,
            "operation_code": self.operation_code,
            "tool_id": self.tool_id,
        }
        return {key: value for key, value in values.items() if value}

    @property
    def query_string(self) -> str:
        return urlencode(self.as_query_params())


@dataclass(frozen=True)
class YieldKpis:
    overall_yield: float
    wafer_count: int
    lot_count: int
    work_order_count: int


@dataclass(frozen=True)
class QueryTiming:
    query_name: str
    duration_ms: float

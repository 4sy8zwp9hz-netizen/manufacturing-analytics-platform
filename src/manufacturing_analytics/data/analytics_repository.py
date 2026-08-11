"""Parameterized SQL queries supporting manufacturing investigations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from manufacturing_analytics.analytics.models import AnalyticsFilters
from manufacturing_analytics.data.database import Database


class AnalyticsRepository:
    """Keep filter-aware SQL out of HTTP routes and analytics calculations."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _filter_sql(
        filters: AnalyticsFilters,
        *,
        yield_alias: str = "y",
        wafer_alias: str = "w",
        lot_alias: str = "l",
        work_order_alias: str = "wo",
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        mapping = (
            (filters.date_from, f"date({yield_alias}.measured_timestamp) >= ?"),
            (filters.date_to, f"date({yield_alias}.measured_timestamp) <= ?"),
            (filters.product_code, f"{work_order_alias}.product_code = ?"),
            (filters.work_order_id, f"{work_order_alias}.work_order_id = ?"),
            (filters.lot_id, f"{lot_alias}.lot_id = ?"),
        )
        for value, clause in mapping:
            if value is not None:
                clauses.append(clause)
                parameters.append(value.isoformat() if hasattr(value, "isoformat") else value)
        if filters.operation_code and filters.tool_id:
            clauses.append(
                f"EXISTS (SELECT 1 FROM wafer_operations fwp WHERE fwp.wafer_id = "
                f"{wafer_alias}.wafer_id AND fwp.operation_code = ? AND fwp.tool_id = ?)"
            )
            parameters.extend((filters.operation_code, filters.tool_id))
        elif filters.operation_code:
            clauses.append(
                f"EXISTS (SELECT 1 FROM wafer_operations fwo WHERE fwo.wafer_id = "
                f"{wafer_alias}.wafer_id AND fwo.operation_code = ?)"
            )
            parameters.append(filters.operation_code)
        elif filters.tool_id:
            clauses.append(
                f"EXISTS (SELECT 1 FROM wafer_operations fwt WHERE fwt.wafer_id = "
                f"{wafer_alias}.wafer_id AND fwt.tool_id = ?)"
            )
            parameters.append(filters.tool_id)
        return (" AND " + " AND ".join(clauses) if clauses else "", parameters)

    def kpis(self, filters: AnalyticsFilters) -> dict[str, Any]:
        where, parameters = self._filter_sql(filters)
        return self.database.fetch_all(
            f"""
            SELECT COALESCE(SUM(y.good_die), 0) AS good_die,
                   COALESCE(SUM(y.total_die), 0) AS total_die,
                   COUNT(DISTINCT w.wafer_id) AS wafer_count,
                   COUNT(DISTINCT l.lot_id) AS lot_count,
                   COUNT(DISTINCT wo.work_order_id) AS work_order_count
            FROM yield_results y
            JOIN wafers w ON w.wafer_id = y.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            WHERE 1 = 1 {where}
            """,
            parameters,
        )[0]

    def yield_trend(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, parameters = self._filter_sql(filters)
        return self.database.fetch_all(
            f"""
            SELECT date(y.measured_timestamp) AS period,
                   ROUND(SUM(y.good_die) * 100.0 / SUM(y.total_die), 2) AS yield_percent,
                   COUNT(*) AS wafer_count
            FROM yield_results y
            JOIN wafers w ON w.wafer_id = y.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            WHERE 1 = 1 {where}
            GROUP BY date(y.measured_timestamp)
            ORDER BY period
            """,
            parameters,
        )

    def wafer_yields(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, parameters = self._filter_sql(filters)
        return self.database.fetch_all(
            f"""
            SELECT y.yield_rate * 100 AS yield_percent
            FROM yield_results y
            JOIN wafers w ON w.wafer_id = y.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            WHERE 1 = 1 {where}
            ORDER BY y.yield_rate
            """,
            parameters,
        )

    def wafer_index(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, parameters = self._filter_sql(filters)
        return self.database.fetch_all(
            f"""
            SELECT w.wafer_id, w.wafer_number, l.lot_id, wo.product_code,
                   ROUND(y.yield_rate * 100, 2) AS yield_percent,
                   y.good_die, y.total_die
            FROM yield_results y
            JOIN wafers w ON w.wafer_id = y.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            WHERE 1 = 1 {where}
            ORDER BY y.yield_rate, w.wafer_id
            """,
            parameters,
        )

    def grouped_yield(self, filters: AnalyticsFilters, dimension: str) -> list[dict[str, Any]]:
        dimensions = {
            "lot": ("l.lot_id", "l.lot_id"),
            "product": ("wo.product_code", "wo.product_code"),
            "work_order": ("wo.work_order_id", "wo.work_order_id"),
        }
        if dimension not in dimensions:
            raise ValueError(f"Unsupported yield dimension: {dimension}")
        expression, group_by = dimensions[dimension]
        where, parameters = self._filter_sql(filters)
        return self.database.fetch_all(
            f"""
            SELECT {expression} AS category,
                   ROUND(SUM(y.good_die) * 100.0 / SUM(y.total_die), 2) AS yield_percent,
                   COUNT(DISTINCT w.wafer_id) AS wafer_count
            FROM yield_results y
            JOIN wafers w ON w.wafer_id = y.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            WHERE 1 = 1 {where}
            GROUP BY {group_by}
            ORDER BY yield_percent, category
            """,
            parameters,
        )

    def tool_yield(
        self, filters: AnalyticsFilters, comparison_operation: str
    ) -> list[dict[str, Any]]:
        where, parameters = self._filter_sql(filters)
        tool_clause = " AND process.tool_id = ?" if filters.tool_id else ""
        tool_parameters: list[Any] = [comparison_operation]
        if filters.tool_id:
            tool_parameters.append(filters.tool_id)
        tool_parameters.extend(parameters)
        return self.database.fetch_all(
            f"""
            SELECT process.tool_id AS category,
                   ROUND(SUM(y.good_die) * 100.0 / SUM(y.total_die), 2) AS yield_percent,
                   COUNT(DISTINCT w.wafer_id) AS wafer_count
            FROM wafer_operations process
            JOIN wafers w ON w.wafer_id = process.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            JOIN yield_results y ON y.wafer_id = w.wafer_id
            WHERE process.operation_code = ? {tool_clause} {where}
            GROUP BY process.tool_id
            ORDER BY yield_percent, process.tool_id
            """,
            tool_parameters,
        )

    def defect_counts(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, parameters = self._filter_sql(filters)
        return self.database.fetch_all(
            f"""
            SELECT dc.defect_name AS category, SUM(idf.defect_count) AS count
            FROM inspection_defects idf
            JOIN defect_categories dc ON dc.defect_code = idf.defect_code
            JOIN inspections i ON i.inspection_id = idf.inspection_id
            JOIN wafers w ON w.wafer_id = i.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            JOIN yield_results y ON y.wafer_id = w.wafer_id
            WHERE 1 = 1 {where}
            GROUP BY dc.defect_name
            ORDER BY count DESC, category
            """,
            parameters,
        )

    def filter_options(self) -> dict[str, list[dict[str, Any]]]:
        queries: dict[str, tuple[str, Sequence[Any]]] = {
            "products": (
                "SELECT DISTINCT product_code AS value FROM work_orders ORDER BY value",
                (),
            ),
            "work_orders": ("SELECT work_order_id AS value FROM work_orders ORDER BY value", ()),
            "lots": ("SELECT lot_id AS value FROM lots ORDER BY value", ()),
            "operations": (
                "SELECT operation_code AS value, operation_name AS label FROM operations "
                "ORDER BY sequence_number",
                (),
            ),
            "tools": (
                "SELECT tool_id AS value, display_name AS label FROM tools ORDER BY tool_id",
                (),
            ),
        }
        return {
            name: self.database.fetch_all(sql, params) for name, (sql, params) in queries.items()
        }

    def lot_detail(self, lot_id: str) -> dict[str, Any] | None:
        rows = self.database.fetch_all(
            """
            SELECT l.lot_id, l.status, l.start_timestamp, l.completion_timestamp,
                   wo.work_order_id, wo.product_code, COUNT(DISTINCT w.wafer_id) AS wafer_count,
                   SUM(y.good_die) AS good_die, SUM(y.total_die) AS total_die,
                   ROUND(SUM(y.good_die) * 100.0 / SUM(y.total_die), 2) AS yield_percent
            FROM lots l
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            JOIN wafers w ON w.lot_id = l.lot_id
            JOIN yield_results y ON y.wafer_id = w.wafer_id
            WHERE l.lot_id = ?
            GROUP BY l.lot_id, l.status, l.start_timestamp, l.completion_timestamp,
                     wo.work_order_id, wo.product_code
            """,
            (lot_id,),
        )
        return rows[0] if rows else None

    def lot_wafers(self, lot_id: str) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            """
            SELECT w.wafer_id, w.wafer_number, ROUND(y.yield_rate * 100, 2) AS yield_percent,
                   y.good_die, y.total_die, COALESCE(SUM(i.defect_count), 0) AS defect_count
            FROM wafers w
            JOIN yield_results y ON y.wafer_id = w.wafer_id
            LEFT JOIN inspections i ON i.wafer_id = w.wafer_id
            WHERE w.lot_id = ?
            GROUP BY w.wafer_id, w.wafer_number, y.yield_rate, y.good_die, y.total_die
            ORDER BY w.wafer_number
            """,
            (lot_id,),
        )

    def lot_genealogy(self, lot_id: str) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            """
            SELECT o.operation_code, o.operation_name, wo.tool_id,
                   COUNT(*) AS wafer_count, MIN(wo.start_timestamp) AS first_start,
                   MAX(wo.end_timestamp) AS last_end
            FROM wafer_operations wo
            JOIN operations o ON o.operation_code = wo.operation_code
            JOIN wafers w ON w.wafer_id = wo.wafer_id
            WHERE w.lot_id = ?
            GROUP BY o.operation_code, o.operation_name, o.sequence_number, wo.tool_id
            ORDER BY o.sequence_number, wo.tool_id
            """,
            (lot_id,),
        )

    def wafer_detail(self, wafer_id: str) -> dict[str, Any] | None:
        rows = self.database.fetch_all(
            """
            SELECT w.wafer_id, w.wafer_number, w.diameter_mm, w.status,
                   l.lot_id, wo.work_order_id, wo.product_code,
                   y.yield_result_id, y.good_die, y.total_die,
                   ROUND(y.yield_rate * 100, 2) AS yield_percent
            FROM wafers w
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            JOIN yield_results y ON y.wafer_id = w.wafer_id
            WHERE w.wafer_id = ?
            """,
            (wafer_id,),
        )
        return rows[0] if rows else None

    def wafer_map(self, wafer_id: str) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            """
            SELECT x_coordinate, y_coordinate, passed, test_bin, test_category
            FROM die_results WHERE wafer_id = ?
            ORDER BY y_coordinate, x_coordinate
            """,
            (wafer_id,),
        )

    def wafer_genealogy(self, wafer_id: str) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            """
            SELECT o.operation_code, o.operation_name, wo.tool_id,
                   wo.start_timestamp, wo.end_timestamp, wo.result
            FROM wafer_operations wo
            JOIN operations o ON o.operation_code = wo.operation_code
            WHERE wo.wafer_id = ?
            ORDER BY wo.sequence_number
            """,
            (wafer_id,),
        )

    def wafer_defects(self, wafer_id: str) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            """
            SELECT i.inspection_timestamp, i.operation_code, i.tool_id,
                   dc.defect_name AS category, idf.defect_count AS count
            FROM inspections i
            JOIN inspection_defects idf ON idf.inspection_id = i.inspection_id
            JOIN defect_categories dc ON dc.defect_code = idf.defect_code
            WHERE i.wafer_id = ?
            ORDER BY i.inspection_timestamp, idf.defect_count DESC
            """,
            (wafer_id,),
        )

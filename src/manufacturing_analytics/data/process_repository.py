"""SQL access for SPC, operational-flow, and data-quality investigations."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from manufacturing_analytics.analytics.models import AnalyticsFilters
from manufacturing_analytics.data.analytics_repository import AnalyticsRepository
from manufacturing_analytics.data.database import Database


class ProcessRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def characteristics(self) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            """
            SELECT characteristic_id AS value, characteristic_name AS label,
                   operation_code, unit, lower_spec_limit, upper_spec_limit
            FROM measurement_characteristics ORDER BY characteristic_name
            """
        )

    @staticmethod
    def _process_filter_sql(
        filters: AnalyticsFilters,
        timestamp_expression: str,
        operation_expression: str,
        tool_expression: str,
    ) -> tuple[str, list[Any]]:
        cohort = replace(
            filters,
            date_from=None,
            date_to=None,
            operation_code=None,
            tool_id=None,
        )
        where, parameters = AnalyticsRepository._filter_sql(cohort)
        clauses = []
        if filters.date_from:
            clauses.append(f"date({timestamp_expression}) >= ?")
            parameters.append(filters.date_from.isoformat())
        if filters.date_to:
            clauses.append(f"date({timestamp_expression}) <= ?")
            parameters.append(filters.date_to.isoformat())
        if filters.operation_code:
            clauses.append(f"{operation_expression} = ?")
            parameters.append(filters.operation_code)
        if filters.tool_id:
            clauses.append(f"{tool_expression} = ?")
            parameters.append(filters.tool_id)
        if clauses:
            where += " AND " + " AND ".join(clauses)
        return where, parameters

    def measurements(
        self, characteristic_id: str, filters: AnalyticsFilters
    ) -> list[dict[str, Any]]:
        where, parameters = self._process_filter_sql(
            filters,
            "pm.measured_timestamp",
            "pm.operation_code",
            "pm.tool_id",
        )
        return self.database.fetch_all(
            f"""
            SELECT pm.measurement_id, pm.wafer_id, pm.operation_code, pm.tool_id,
                   pm.measured_timestamp, pm.source_arrival_timestamp, pm.measured_value,
                   l.lot_id, wo.product_code, wo.work_order_id,
                   mc.characteristic_name, mc.unit,
                   mc.lower_spec_limit, mc.upper_spec_limit
            FROM process_measurements pm
            JOIN measurement_characteristics mc
              ON mc.characteristic_id = pm.characteristic_id
            JOIN wafers w ON w.wafer_id = pm.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            JOIN yield_results y ON y.wafer_id = w.wafer_id
            WHERE pm.characteristic_id = ? {where}
            ORDER BY pm.measured_timestamp, pm.measurement_id
            """,
            [characteristic_id, *parameters],
        )

    def operation_events(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, parameters = self._process_filter_sql(
            filters,
            "process.end_timestamp",
            "process.operation_code",
            "process.tool_id",
        )
        return self.database.fetch_all(
            f"""
            SELECT process.wafer_operation_id, process.wafer_id, process.operation_code,
                   o.operation_name, process.tool_id, process.sequence_number,
                   process.start_timestamp, process.end_timestamp,
                   (julianday(process.end_timestamp) - julianday(process.start_timestamp))
                       * 1440.0 AS cycle_minutes,
                   l.lot_id, wo.product_code
            FROM wafer_operations process
            JOIN operations o ON o.operation_code = process.operation_code
            JOIN wafers w ON w.wafer_id = process.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            JOIN yield_results y ON y.wafer_id = w.wafer_id
            WHERE 1 = 1 {where}
            ORDER BY process.wafer_id, process.sequence_number
            """,
            parameters,
        )

    def throughput(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, parameters = self._process_filter_sql(
            filters,
            "process.end_timestamp",
            "process.operation_code",
            "process.tool_id",
        )
        return self.database.fetch_all(
            f"""
            SELECT date(process.end_timestamp) AS period, process.operation_code,
                   process.tool_id, COUNT(*) AS completed_wafers
            FROM wafer_operations process
            JOIN wafers w ON w.wafer_id = process.wafer_id
            JOIN lots l ON l.lot_id = w.lot_id
            JOIN work_orders wo ON wo.work_order_id = l.work_order_id
            JOIN yield_results y ON y.wafer_id = w.wafer_id
            WHERE 1 = 1 {where}
            GROUP BY date(process.end_timestamp), process.operation_code, process.tool_id
            ORDER BY period, process.operation_code, process.tool_id
            """,
            parameters,
        )

    def quality_issues(self) -> list[dict[str, Any]]:
        return self.database.fetch_all(
            "SELECT * FROM data_quality_issues ORDER BY severity, issue_type, issue_id"
        )

    def watermarks(self) -> list[dict[str, Any]]:
        return self.database.fetch_all("SELECT * FROM source_watermarks ORDER BY source_name")

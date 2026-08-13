"""Read-only queries against the latest published analytical generation."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any

from manufacturing_analytics.pipeline.generation_store import GenerationStore


class PlatformRepository:
    def __init__(self, store: GenerationStore) -> None:
        self.store = store

    @contextmanager
    def connect(self):
        path = self.store.current_path()
        if path is None:
            raise RuntimeError("No published analytical generation is available")
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def metadata(self) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM generation_metadata").fetchone()
            result = dict(row)
            result["watermarks"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM source_watermarks ORDER BY source_name"
                )
            ]
            result["issues"] = connection.execute(
                "SELECT COUNT(*) FROM transformation_issues"
            ).fetchone()[0]
            result["issue_rows"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM transformation_issues ORDER BY issue_id LIMIT 200"
                )
            ]
            result["row_counts"] = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
                for table in ("canonical_wafers", "stage_population", "analytical_lineage")
            }
            return result

    @staticmethod
    def _where(filters: dict[str, str | None]) -> tuple[str, list[str]]:
        clauses, values = [], []
        mapping = {
            "product": "w.product_code",
            "work_order": "w.canonical_work_order_id",
            "wafer": "w.canonical_wafer_id",
            "period": "w.analytical_period",
        }
        for name, column in mapping.items():
            if filters.get(name):
                clauses.append(f"{column} = ?")
                values.append(str(filters[name]))
        return (" AND " + " AND ".join(clauses) if clauses else "", values)

    def stage_metrics(self, filters: dict[str, str | None]) -> list[dict[str, Any]]:
        where, values = self._where(filters)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT p.stage_code, p.population_unit,
                       SUM(p.is_denominator) denominator,
                       SUM(CASE WHEN p.is_denominator = 1 THEN p.is_good ELSE 0 END) good,
                       SUM(CASE WHEN p.is_denominator = 0 THEN 1 ELSE 0 END) excluded
                FROM stage_population p
                JOIN canonical_wafers w ON w.canonical_wafer_id = p.canonical_wafer_id
                WHERE p.stage_code != 'QUALIFICATION' {where}
                GROUP BY p.stage_code, p.population_unit
                ORDER BY CASE p.stage_code
                    WHEN 'PROCESS_COMPLETION' THEN 1 WHEN 'WAFER_INSPECTION' THEN 2
                    WHEN 'CHIP_TEST' THEN 3 WHEN 'SORTING' THEN 4 ELSE 9 END
                """,  # noqa: S608
                values,
            ).fetchall()
        return [
            {
                **dict(row),
                "yield_rate": (row["good"] / row["denominator"]) if row["denominator"] else None,
            }
            for row in rows
        ]

    def trend(
        self, filters: dict[str, str | None], time_grain: str = "month"
    ) -> list[dict[str, Any]]:
        where, values = self._where(filters)
        period_expression = {
            "date": "substr(p.event_timestamp, 1, 10)",
            "week": "strftime('%Y-W%W', p.event_timestamp)",
            "month": "substr(p.event_timestamp, 1, 7)",
        }.get(time_grain)
        if period_expression is None:
            raise ValueError("time_grain must be date, week, or month")
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    f"""
                    SELECT {period_expression} period,
                           SUM(CASE WHEN p.is_denominator = 1 THEN p.is_good ELSE 0 END) good,
                           SUM(p.is_denominator) denominator
                    FROM stage_population p JOIN canonical_wafers w
                      ON w.canonical_wafer_id = p.canonical_wafer_id
                    WHERE p.stage_code = 'CHIP_TEST' {where}
                    GROUP BY period ORDER BY period
                    """,  # noqa: S608
                    values,
                )
            ]

    def failures(self, filters: dict[str, str | None]) -> list[dict[str, Any]]:
        where, values = self._where(filters)
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    f"""
                    SELECT p.failure_family, COUNT(*) failure_count
                    FROM stage_population p JOIN canonical_wafers w
                      ON w.canonical_wafer_id = p.canonical_wafer_id
                    WHERE p.is_denominator = 1 AND p.is_good = 0
                      AND p.failure_family IS NOT NULL {where}
                    GROUP BY p.failure_family ORDER BY failure_count DESC, p.failure_family
                    """,  # noqa: S608
                    values,
                )
            ]

    def wafers(self, filters: dict[str, str | None]) -> list[dict[str, Any]]:
        where, values = self._where(filters)
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    f"""
                    SELECT w.*,
                           SUM(CASE
                               WHEN p.stage_code='CHIP_TEST' AND p.is_denominator=1
                               THEN p.is_good ELSE 0 END) chip_good,
                           SUM(CASE
                               WHEN p.stage_code='CHIP_TEST'
                               THEN p.is_denominator ELSE 0 END) chip_total
                    FROM canonical_wafers w LEFT JOIN stage_population p
                      ON p.canonical_wafer_id=w.canonical_wafer_id
                    WHERE 1=1 {where}
                    GROUP BY w.canonical_wafer_id
                    ORDER BY CASE WHEN chip_total > 0
                                  THEN chip_good * 1.0 / chip_total ELSE 2 END,
                             w.canonical_wafer_id
                    """,  # noqa: S608
                    values,
                )
            ]

    def options(self) -> dict[str, list[str]]:
        with self.connect() as connection:
            return {
                key: [
                    row[0]
                    for row in connection.execute(
                        f"SELECT DISTINCT {column} FROM canonical_wafers ORDER BY {column}"
                    )
                ]  # noqa: S608
                for key, column in {
                    "products": "product_code",
                    "work_orders": "canonical_work_order_id",
                    "wafers": "canonical_wafer_id",
                    "periods": "analytical_period",
                }.items()
            }

    def population(self, stage: str, filters: dict[str, str | None]) -> list[dict[str, Any]]:
        where, values = self._where(filters)
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    f"""
                    SELECT p.*, w.product_code, w.canonical_lot_id, w.canonical_work_order_id
                    FROM stage_population p JOIN canonical_wafers w
                      ON w.canonical_wafer_id=p.canonical_wafer_id
                    WHERE p.stage_code=? {where}
                    ORDER BY p.event_timestamp, p.unit_key
                    """,  # noqa: S608
                    [stage, *values],
                )
            ]

    def wafer_trace(self, wafer_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            wafer = connection.execute(
                "SELECT * FROM canonical_wafers WHERE canonical_wafer_id=?", (wafer_id,)
            ).fetchone()
            if wafer is None:
                return None
            rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT p.*, l.source_system, l.source_table, l.source_record_key,
                           l.reconciliation_method, l.transformation_note
                    FROM stage_population p JOIN analytical_lineage l
                      ON l.analytical_record_id=p.analytical_record_id
                    WHERE p.canonical_wafer_id=? ORDER BY p.event_timestamp, p.stage_code
                    LIMIT 500
                    """,
                    (wafer_id,),
                )
            ]
            return {"wafer": dict(wafer), "records": rows}

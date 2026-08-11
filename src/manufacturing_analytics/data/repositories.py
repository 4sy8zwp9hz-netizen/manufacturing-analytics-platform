"""Read-oriented queries expressed in manufacturing language."""

from dataclasses import dataclass

from manufacturing_analytics.data.database import Database


@dataclass(frozen=True)
class ManufacturingSummary:
    work_orders: int
    lots: int
    wafers: int
    tools: int
    average_yield: float


class ManufacturingRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def summary(self) -> ManufacturingSummary:
        row = self.database.fetch_all(
            """
            SELECT
                (SELECT COUNT(*) FROM work_orders) AS work_orders,
                (SELECT COUNT(*) FROM lots) AS lots,
                (SELECT COUNT(*) FROM wafers) AS wafers,
                (SELECT COUNT(*) FROM tools) AS tools,
                COALESCE((SELECT AVG(yield_rate) FROM yield_results), 0.0) AS average_yield
            """
        )[0]
        return ManufacturingSummary(**row)

    def recent_lots(self, limit: int = 5) -> list[dict[str, object]]:
        return self.database.fetch_all(
            """
            SELECT l.lot_id, w.product_code, l.status, COUNT(f.wafer_id) AS wafer_count,
                   ROUND(AVG(y.yield_rate) * 100, 2) AS average_yield_percent
            FROM lots AS l
            JOIN work_orders AS w ON w.work_order_id = l.work_order_id
            JOIN wafers AS f ON f.lot_id = l.lot_id
            LEFT JOIN yield_results AS y ON y.wafer_id = f.wafer_id
            GROUP BY l.lot_id, w.product_code, l.status, l.start_timestamp
            ORDER BY l.start_timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )


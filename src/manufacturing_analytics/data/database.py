"""SQLite connection and transactional dataset loading."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
LOAD_ORDER = (
    "work_orders",
    "lots",
    "wafers",
    "operations",
    "tools",
    "wafer_operations",
    "defect_categories",
    "inspections",
    "inspection_defects",
    "yield_results",
)


class Database:
    """Small database boundary that keeps SQLite details out of domain code."""

    def __init__(self, path: Path | str) -> None:
        self.path = str(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def replace_dataset(self, dataset: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        """Replace generated data atomically while preserving the schema."""
        with self.connect() as connection:
            for table in reversed(LOAD_ORDER):
                connection.execute(f"DELETE FROM {table}")  # noqa: S608 - allowlisted names
            for table in LOAD_ORDER:
                records = dataset.get(table, ())
                if not records:
                    continue
                columns = tuple(records[0].keys())
                placeholders = ", ".join("?" for _ in columns)
                column_names = ", ".join(columns)
                sql = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"  # noqa: S608
                values = (tuple(record[column] for column in columns) for record in records)
                connection.executemany(sql, values)

    def scalar(self, query: str, parameters: Sequence[Any] = ()) -> Any:
        with self.connect() as connection:
            row = connection.execute(query, parameters).fetchone()
            return None if row is None else row[0]

    def fetch_all(
        self, query: str, parameters: Sequence[Any] = ()
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

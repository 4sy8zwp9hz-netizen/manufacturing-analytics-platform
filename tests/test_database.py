from pathlib import Path

import pytest

from manufacturing_analytics.data.database import Database
from manufacturing_analytics.data.repositories import ManufacturingRepository
from manufacturing_analytics.domain.synthetic import GenerationConfig, SyntheticDataGenerator


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    database.initialize()
    dataset = SyntheticDataGenerator(
        GenerationConfig(seed=101, work_order_count=1, lots_per_work_order=2, wafers_per_lot=3)
    ).generate()
    database.replace_dataset(dataset)
    return database


def test_dataset_round_trip_and_foreign_keys(database: Database) -> None:
    assert database.scalar("SELECT COUNT(*) FROM wafers") == 6
    assert database.scalar("SELECT COUNT(*) FROM die_results") == 6 * 317
    assert database.scalar("PRAGMA foreign_key_check") is None


def test_repository_returns_manufacturing_summary(database: Database) -> None:
    summary = ManufacturingRepository(database).summary()

    assert summary.work_orders == 1
    assert summary.lots == 2
    assert summary.wafers == 6
    assert summary.tools == 12
    assert 0.75 <= summary.average_yield <= 1.0


def test_replace_dataset_is_idempotent(database: Database) -> None:
    dataset = SyntheticDataGenerator(
        GenerationConfig(seed=101, work_order_count=1, lots_per_work_order=2, wafers_per_lot=3)
    ).generate()
    database.replace_dataset(dataset)
    assert database.scalar("SELECT COUNT(*) FROM wafers") == 6

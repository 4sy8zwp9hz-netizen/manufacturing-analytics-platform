from pathlib import Path

import pytest

from manufacturing_analytics.analytics.models import AnalyticsFilters
from manufacturing_analytics.analytics.process_service import ProcessAnalyticsService
from manufacturing_analytics.data.database import Database
from manufacturing_analytics.data.process_repository import ProcessRepository
from manufacturing_analytics.domain.synthetic import GenerationConfig, SyntheticDataGenerator


@pytest.fixture
def process_analytics(tmp_path: Path) -> ProcessAnalyticsService:
    database = Database(tmp_path / "process.db")
    database.initialize()
    dataset = SyntheticDataGenerator(
        GenerationConfig(seed=20260811, work_order_count=4, lots_per_work_order=3, wafers_per_lot=5)
    ).generate()
    database.replace_dataset(dataset)
    return ProcessAnalyticsService(ProcessRepository(database))


def test_tool_stratification_reveals_synthetic_offset_and_rules(
    process_analytics: ProcessAnalyticsService,
) -> None:
    model = process_analytics.process_monitor("ETCH_DEPTH", AnalyticsFilters())
    tools = {row["tool_id"]: row for row in model["strata"]}

    assert tools["ETCH-02"]["mean"] > tools["ETCH-01"]["mean"] + 1.0
    assert tools["ETCH-02"]["rule_violations"] > 0
    assert model["violations"]
    assert model["specification"]["lower"] != model["limits"]["lower_control_limit"]


def test_process_filter_applies_to_measurement_tool(
    process_analytics: ProcessAnalyticsService,
) -> None:
    model = process_analytics.process_monitor("ETCH_DEPTH", AnalyticsFilters(tool_id="ETCH-02"))
    assert model["records"]
    assert {row["tool_id"] for row in model["records"]} == {"ETCH-02"}


def test_operations_and_quality_workflows(process_analytics: ProcessAnalyticsService) -> None:
    operations = process_analytics.operations_flow(AnalyticsFilters())
    quality = process_analytics.data_quality()

    assert operations["event_count"] == 359
    assert operations["wafer_count"] == 60
    assert (
        next(row for row in operations["routes"] if row["wafer_id"] == "WFR-00019")["event_count"]
        == 5
    )
    assert sum(row["completed_wafers"] for row in operations["throughput_by_tool"]) == 359
    assert quality["open_count"] == 6
    assert quality["stale_count"] == 1

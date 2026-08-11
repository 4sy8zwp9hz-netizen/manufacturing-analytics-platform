from pathlib import Path

import pytest

from manufacturing_analytics.analytics.models import AnalyticsFilters
from manufacturing_analytics.analytics.service import AnalyticsService
from manufacturing_analytics.data.analytics_repository import AnalyticsRepository
from manufacturing_analytics.data.database import Database
from manufacturing_analytics.domain.synthetic import GenerationConfig, SyntheticDataGenerator


@pytest.fixture
def analytics(tmp_path: Path) -> AnalyticsService:
    database = Database(tmp_path / "analytics.db")
    database.initialize()
    dataset = SyntheticDataGenerator(
        GenerationConfig(seed=20260811, work_order_count=4, lots_per_work_order=3, wafers_per_lot=5)
    ).generate()
    database.replace_dataset(dataset)
    return AnalyticsService(AnalyticsRepository(database))


def test_overview_metrics_and_filter_behavior(analytics: AnalyticsService) -> None:
    all_results = analytics.yield_overview(AnalyticsFilters())
    product_results = analytics.yield_overview(AnalyticsFilters(product_code="SYN-100"))
    missing_results = analytics.yield_overview(AnalyticsFilters(product_code="NOT-A-PRODUCT"))

    assert all_results["kpis"].wafer_count == 60
    assert all_results["kpis"].lot_count == 12
    assert product_results["kpis"].wafer_count == 30
    assert {row["category"] for row in product_results["products"]} == {"SYN-100"}
    assert missing_results["kpis"].overall_yield == 0.0


def test_tool_filter_and_comparison_surface_embedded_signal(analytics: AnalyticsService) -> None:
    filtered = analytics.yield_overview(AnalyticsFilters(tool_id="ETCH-02"))
    comparison = analytics.yield_overview(AnalyticsFilters())["tools"]
    yields = {row["category"]: row["yield_percent"] for row in comparison}

    assert 0 < filtered["kpis"].wafer_count < 60
    assert yields["ETCH-02"] < yields["ETCH-01"]

    incompatible = analytics.yield_overview(
        AnalyticsFilters(operation_code="OP-400", tool_id="TEST-01")
    )
    assert incompatible["kpis"].wafer_count == 0


def test_pareto_and_query_timing_are_service_owned(analytics: AnalyticsService) -> None:
    pareto = analytics.pareto(AnalyticsFilters(lot_id="LOT-0101"))

    assert pareto
    assert pareto[-1].cumulative_percentage == 100.0
    assert all(pareto[index].count >= pareto[index + 1].count for index in range(len(pareto) - 1))
    assert any(timing.query_name == "defect_pareto" for timing in analytics.timings)
    assert all(timing.duration_ms >= 0 for timing in analytics.timings)


def test_drill_down_models_and_not_found(analytics: AnalyticsService) -> None:
    lot = analytics.lot_investigation("LOT-0101")
    wafer = analytics.wafer_investigation("WFR-00001")

    assert lot is not None and len(lot["wafers"]) == 5
    assert wafer is not None and len(wafer["map"]) == 317
    assert len(wafer["genealogy"]) == 6
    assert analytics.lot_investigation("MISSING") is None
    assert analytics.wafer_investigation("MISSING") is None

from __future__ import annotations

from manufacturing_analytics.application import create_dash_app
from manufacturing_analytics.yield_analytics import DashboardFilters


def test_summary_table_preserves_engineering_row_hierarchy(services) -> None:
    rows, columns, periods = services.analytics.summary_table(DashboardFilters())
    assert periods
    assert [row["stage_code"] for row in rows][-1] == "FINAL_CHIP_YIELD"
    assert rows[-1]["section"] == "Chip Total"
    assert "cohort" in rows[-1]["assumption"].lower()
    assert columns[0]["id"] == "section"


def test_selected_cell_drives_pareto_trend_scatter_and_traceability(services) -> None:
    filters = DashboardFilters()
    rows, _, periods = services.analytics.summary_table(filters)
    row_index = next(i for i, row in enumerate(rows) if row["stage_code"] == "CHIP_INSPECTION")
    selection = services.analytics.resolve_selection(
        {"row": row_index, "column_id": periods[-1]}, rows
    )
    assert selection is not None
    assert services.analytics.pareto_figure(selection, filters).data
    assert services.analytics.trend_figure(selection, filters).data
    scatter = services.analytics.wafer_scatter_figure(selection, filters)
    assert scatter.data
    records = services.analytics.population_records(selection, filters)
    assert records and records[0]["source_record_id"]
    assert records[0]["transformation_rule"]


def test_targeted_detail_follows_selected_stage(services) -> None:
    chip, chip_label = services.analytics.targeted_detail("CHIP_INSPECTION", "PHY-00001")
    sorting, sorting_label = services.analytics.targeted_detail("SORTING", "PHY-00001")
    assert len(chip) == services.settings.chips_per_wafer
    assert len(sorting) == services.settings.chips_per_wafer * 6
    assert "chip-detail" in chip_label
    assert "Sorting" in sorting_label


def test_dash_application_exposes_real_workflow_and_health(services) -> None:
    app = create_dash_app(services)
    client = app.server.test_client()
    response = client.get("/")
    health = client.get("/health")

    assert response.status_code == 200
    assert services.settings.title.encode() in response.data
    assert health.status_code == 200
    assert health.json["generation_id"] == services.snapshots.get().generation_id

    layout_text = str(app.layout)
    for component_id in (
        "yield-table",
        "enhance-button",
        "pareto-figure",
        "trend-figure",
        "wafer-scatter-figure",
        "population-table",
        "targeted-detail-table",
    ):
        assert component_id in layout_text

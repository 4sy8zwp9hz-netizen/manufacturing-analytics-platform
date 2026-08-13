from pathlib import Path

from fastapi.testclient import TestClient

from manufacturing_analytics.main import create_app


def test_landing_page_and_health_check(tmp_path: Path) -> None:
    app = create_app(tmp_path / "app.db")
    with TestClient(app) as client:
        response = client.get("/")
        health = client.get("/health")

    assert response.status_code == 200
    assert "Trace yield from metric to source" in response.text
    assert health.json()["status"] == "ok"
    assert health.json()["generation_id"].startswith("gen-")


def test_unknown_analytics_page_returns_404(tmp_path: Path) -> None:
    app = create_app(tmp_path / "app.db")
    with TestClient(app) as client:
        response = client.get("/analytics/not-a-page")
    assert response.status_code == 404


def test_yield_overview_filters_and_drill_down_routes(tmp_path: Path) -> None:
    app = create_app(tmp_path / "phase2.db")
    with TestClient(app) as client:
        overview = client.get("/analytics/yield-overview?product_code=SYN-100")
        lot = client.get("/lots/LOT-0101?product_code=SYN-100")
        wafer = client.get("/wafers/WFR-00001?product_code=SYN-100")
        pareto = client.get("/analytics/pareto-analysis?lot=LOT-0101")

    assert overview.status_code == 200 and "Lot performance" in overview.text
    assert "Open lot" in overview.text
    assert lot.status_code == 200 and "Individual results" in lot.text
    assert wafer.status_code == 200 and wafer.text.count('class="die ') == 317
    assert pareto.status_code == 200 and "Cumulative" in pareto.text


def test_invalid_filters_and_missing_entities(tmp_path: Path) -> None:
    app = create_app(tmp_path / "invalid.db")
    with TestClient(app) as client:
        invalid_date = client.get("/analytics/yield-overview?date_from=not-a-date")
        reversed_range = client.get(
            "/analytics/yield-overview?date_from=2026-02-01&date_to=2026-01-01"
        )
        missing_lot = client.get("/lots/LOT-MISSING")
        missing_wafer = client.get("/wafers/WFR-MISSING")

    assert invalid_date.status_code == 422
    assert reversed_range.status_code == 422
    assert missing_lot.status_code == 404
    assert missing_wafer.status_code == 404


def test_phase_three_routes_and_local_chart_asset(tmp_path: Path) -> None:
    app = create_app(tmp_path / "phase3.db")
    with TestClient(app) as client:
        spc = client.get("/analytics/process-spc?characteristic=ETCH_DEPTH")
        operations = client.get("/analytics/manufacturing-operations")
        quality = client.get("/analytics/data-quality")
        chart_asset = client.get("/static/vendor/chart.umd.min.js")

    assert spc.status_code == 200 and "Control limits ≠ specification limits" in spc.text
    assert "cdn.jsdelivr" not in spc.text
    assert operations.status_code == 200 and "OBSERVED THROUGHPUT" in operations.text
    assert quality.status_code == 200 and "Watermarks" in quality.text
    assert chart_asset.status_code == 200 and len(chart_asset.content) > 100_000


def test_yield_platform_population_lineage_and_export_routes(tmp_path: Path) -> None:
    app = create_app(tmp_path / "platform.db")
    with TestClient(app) as client:
        dashboard = client.get("/analytics/yield-dashboard?product=ORION-A&time_grain=week")
        population = client.get("/platform/population?stage=CHIP_TEST&product=ORION-A")
        export = client.get("/platform/population?stage=CHIP_TEST&format=csv")
        wafer = client.get("/platform/wafers/WAF-000001")
        generation = client.get("/platform/generation")

    assert dashboard.status_code == 200 and "Rolled production yield" in dashboard.text
    assert "Chip-test yield by week" in dashboard.text
    assert "Inspect every denominator" in dashboard.text
    assert population.status_code == 200 and "DENOMINATOR INSPECTION" in population.text
    assert export.status_code == 200 and export.headers["content-type"].startswith("text/csv")
    assert wafer.status_code == 200 and "SOURCE TRACE" in wafer.text
    assert generation.status_code == 200 and "Source watermarks" in generation.text
    assert "Warnings and quarantines" in generation.text

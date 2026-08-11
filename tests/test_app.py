from pathlib import Path

from fastapi.testclient import TestClient

from manufacturing_analytics.main import create_app


def test_landing_page_and_health_check(tmp_path: Path) -> None:
    app = create_app(tmp_path / "app.db")
    with TestClient(app) as client:
        response = client.get("/")
        health = client.get("/health")

    assert response.status_code == 200
    assert "From factory context" in response.text
    assert health.json() == {"status": "ok"}


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

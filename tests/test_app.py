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


"""Application composition root."""

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from manufacturing_analytics.analytics.service import AnalyticsService
from manufacturing_analytics.config import get_settings
from manufacturing_analytics.data.analytics_repository import AnalyticsRepository
from manufacturing_analytics.data.database import Database
from manufacturing_analytics.data.repositories import ManufacturingRepository
from manufacturing_analytics.logging_config import configure_logging
from manufacturing_analytics.services.bootstrap import ensure_demo_data
from manufacturing_analytics.web.routes import router

WEB_ROOT = Path(__file__).with_name("web")


def create_app(database_path: Path | str | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = Database(database_path or settings.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ensure_demo_data(database, settings)
        app.state.database = database
        app.state.repository = ManufacturingRepository(database)
        app.state.analytics = AnalyticsService(AnalyticsRepository(database))
        yield

    application = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
    application.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")
    application.include_router(router)
    return application


app = create_app()


def run() -> None:
    uvicorn.run("manufacturing_analytics.main:app", host="127.0.0.1", port=8000, reload=True)

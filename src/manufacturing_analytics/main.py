"""Application composition root."""

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from manufacturing_analytics.analytics.platform_service import YieldPlatformService
from manufacturing_analytics.analytics.process_service import ProcessAnalyticsService
from manufacturing_analytics.analytics.service import AnalyticsService
from manufacturing_analytics.config import get_settings
from manufacturing_analytics.data.analytics_repository import AnalyticsRepository
from manufacturing_analytics.data.database import Database
from manufacturing_analytics.data.platform_repository import PlatformRepository
from manufacturing_analytics.data.process_repository import ProcessRepository
from manufacturing_analytics.data.repositories import ManufacturingRepository
from manufacturing_analytics.logging_config import configure_logging
from manufacturing_analytics.services.bootstrap import ensure_demo_data
from manufacturing_analytics.services.platform_bootstrap import ensure_platform_data
from manufacturing_analytics.web.routes import router

WEB_ROOT = Path(__file__).with_name("web")


def create_app(database_path: Path | str | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = Database(database_path or settings.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ensure_demo_data(database, settings)
        platform_root = Path(database.path).parent / "yield_platform"
        generation_store, refresh_pipeline = ensure_platform_data(platform_root)
        app.state.database = database
        app.state.repository = ManufacturingRepository(database)
        app.state.analytics = AnalyticsService(AnalyticsRepository(database))
        app.state.process_analytics = ProcessAnalyticsService(ProcessRepository(database))
        app.state.generation_store = generation_store
        app.state.refresh_pipeline = refresh_pipeline
        app.state.yield_platform = YieldPlatformService(PlatformRepository(generation_store))
        yield

    application = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)
    application.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")
    application.include_router(router)
    return application


app = create_app()


def run() -> None:
    uvicorn.run("manufacturing_analytics.main:app", host="127.0.0.1", port=8000, reload=True)

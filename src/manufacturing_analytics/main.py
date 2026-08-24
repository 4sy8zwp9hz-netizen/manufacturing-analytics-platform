"""Run the synthetic Yield Dashboard through the production-style Waitress server."""

from __future__ import annotations

import logging

from waitress import serve

from manufacturing_analytics.application import create_dash_app
from manufacturing_analytics.bootstrap import build_services, start_background_services
from manufacturing_analytics.logging_config import configure_logging


def create_app():
    services = build_services()
    return create_dash_app(services)


def run() -> None:
    services = build_services()
    configure_logging(services.settings.log_level)
    start_background_services(services)
    app = create_dash_app(services)
    logging.getLogger(__name__).info(
        "Serving %s at http://%s:%s",
        services.settings.title,
        services.settings.host,
        services.settings.port,
    )
    serve(
        app.server,
        host=services.settings.host,
        port=services.settings.port,
        threads=services.settings.waitress_threads,
    )


if __name__ == "__main__":
    run()

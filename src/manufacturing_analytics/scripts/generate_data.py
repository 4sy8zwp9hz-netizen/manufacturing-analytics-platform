"""CLI for rebuilding the local synthetic SQLite dataset."""

import logging

from manufacturing_analytics.config import get_settings
from manufacturing_analytics.data.database import Database
from manufacturing_analytics.domain.synthetic import GenerationConfig, SyntheticDataGenerator
from manufacturing_analytics.logging_config import configure_logging


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = Database(settings.database_path)
    database.initialize()
    config = GenerationConfig(
        seed=settings.seed,
        work_order_count=settings.work_order_count,
        lots_per_work_order=settings.lots_per_work_order,
        wafers_per_lot=settings.wafers_per_lot,
    )
    database.replace_dataset(SyntheticDataGenerator(config).generate())
    logging.getLogger(__name__).info("Synthetic database written to %s", settings.database_path)


if __name__ == "__main__":
    main()

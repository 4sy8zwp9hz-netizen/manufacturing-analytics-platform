"""Bootstrap the local demo dataset when no generated data exists."""

import logging

from manufacturing_analytics.config import Settings
from manufacturing_analytics.data.database import Database
from manufacturing_analytics.domain.synthetic import GenerationConfig, SyntheticDataGenerator

LOGGER = logging.getLogger(__name__)


def ensure_demo_data(database: Database, settings: Settings) -> bool:
    """Initialize and populate an empty database. Return True when data was generated."""
    database.initialize()
    if database.scalar("SELECT COUNT(*) FROM wafers"):
        return False

    LOGGER.info("Generating deterministic synthetic manufacturing dataset")
    generator = SyntheticDataGenerator(
        GenerationConfig(
            seed=settings.seed,
            work_order_count=settings.work_order_count,
            lots_per_work_order=settings.lots_per_work_order,
            wafers_per_lot=settings.wafers_per_lot,
        )
    )
    database.replace_dataset(generator.generate())
    return True


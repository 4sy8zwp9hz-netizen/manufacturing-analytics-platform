"""Typed application configuration loaded from TOML and environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    log_level: str
    database_path: Path
    seed: int
    work_order_count: int
    lots_per_work_order: int
    wafers_per_lot: int


@lru_cache(maxsize=1)
def get_settings(config_path: Path | None = None) -> Settings:
    """Load settings once; environment variables override local defaults."""
    path = config_path or PROJECT_ROOT / "config" / "default.toml"
    with path.open("rb") as config_file:
        values = tomllib.load(config_file)

    application = values["application"]
    database = values["database"]
    synthetic = values["synthetic_data"]
    database_path = Path(os.getenv("MAP_DATABASE_PATH", database["path"]))
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path

    return Settings(
        app_name=application["name"],
        environment=os.getenv("MAP_ENVIRONMENT", application["environment"]),
        log_level=os.getenv("MAP_LOG_LEVEL", application["log_level"]),
        database_path=database_path,
        seed=int(synthetic["seed"]),
        work_order_count=int(synthetic["work_order_count"]),
        lots_per_work_order=int(synthetic["lots_per_work_order"]),
        wafers_per_lot=int(synthetic["wafers_per_lot"]),
    )


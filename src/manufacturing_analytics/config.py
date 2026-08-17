"""Small JSON configuration boundary mirroring the production application's pattern."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    title: str
    environment: str
    log_level: str
    host: str
    port: int
    waitress_threads: int
    refresh_seconds: int
    generation_poll_seconds: int
    storage_root: Path
    retain_generations: int
    schema_version: int
    seed: int
    work_order_count: int
    wafers_per_work_order: int
    chips_per_wafer: int
    start_date: str
    sorting_preload_seconds: int
    sorting_background_delay_seconds: float
    default_period: str
    default_weeks: int
    default_product_family: str
    top_pareto_items: int
    rules: dict[str, Any]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


@lru_cache(maxsize=4)
def get_settings(config_path: Path | None = None) -> Settings:
    """Load configuration once; environment variables override deployment values."""
    path = config_path or PROJECT_ROOT / "config" / "default.json"
    values = _load_json(path)
    rules = _load_json(PROJECT_ROOT / "config" / "yield_rules.json")
    application = values["application"]
    storage = values["storage"]
    synthetic = values["synthetic_data"]
    refresh = values["refresh"]
    display = values["display"]
    root = Path(os.getenv("MAP_STORAGE_ROOT", storage["root"]))
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return Settings(
        title=application["title"],
        environment=application["environment"],
        log_level=str(application["log_level"]),
        host=os.getenv("MAP_HOST", application["host"]),
        port=int(os.getenv("MAP_PORT", application["port"])),
        waitress_threads=int(application["waitress_threads"]),
        refresh_seconds=int(application["refresh_seconds"]),
        generation_poll_seconds=int(application["generation_poll_seconds"]),
        storage_root=root,
        retain_generations=int(storage["retain_generations"]),
        schema_version=int(storage["schema_version"]),
        seed=int(synthetic["seed"]),
        work_order_count=int(synthetic["work_order_count"]),
        wafers_per_work_order=int(synthetic["wafers_per_work_order"]),
        chips_per_wafer=int(synthetic["chips_per_wafer"]),
        start_date=str(synthetic["start_date"]),
        sorting_preload_seconds=int(refresh["sorting_preload_seconds"]),
        sorting_background_delay_seconds=float(refresh["sorting_background_delay_seconds"]),
        default_period=str(display["default_period"]),
        default_weeks=int(display["default_weeks"]),
        default_product_family=str(display["default_product_family"]),
        top_pareto_items=int(display["top_pareto_items"]),
        rules=rules,
    )

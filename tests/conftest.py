from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from manufacturing_analytics.bootstrap import ApplicationServices, build_services
from manufacturing_analytics.config import get_settings


@pytest.fixture
def services(tmp_path: Path) -> ApplicationServices:
    settings = replace(
        get_settings(),
        storage_root=tmp_path / "yield-runtime",
        seed=314159,
        work_order_count=4,
        wafers_per_work_order=5,
        chips_per_wafer=25,
        retain_generations=2,
        sorting_background_delay_seconds=0.0,
    )
    built = build_services(settings, ensure_ready=False)
    built.refresh.refresh()
    return built

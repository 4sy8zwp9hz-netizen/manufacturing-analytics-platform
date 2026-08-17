"""Composition root for the clean-room Yield application."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from manufacturing_analytics.config import Settings, get_settings
from manufacturing_analytics.runtime import (
    GenerationWatcher,
    RefreshCoordinator,
    SnapshotManager,
    SortingPreload,
)
from manufacturing_analytics.sources import SyntheticManufacturingSource, SyntheticSourceConfig
from manufacturing_analytics.storage import ParquetGenerationStore, TargetedDetailRepository
from manufacturing_analytics.transforms import YieldTransformer
from manufacturing_analytics.yield_analytics import YieldAnalytics


@dataclass(frozen=True)
class ApplicationServices:
    settings: Settings
    source: SyntheticManufacturingSource
    store: ParquetGenerationStore
    snapshots: SnapshotManager
    sorting_preload: SortingPreload
    refresh: RefreshCoordinator
    details: TargetedDetailRepository
    analytics: YieldAnalytics


def build_services(
    settings: Settings | None = None, *, ensure_ready: bool = True
) -> ApplicationServices:
    configured = settings or get_settings()
    source = SyntheticManufacturingSource(
        SyntheticSourceConfig(
            seed=configured.seed,
            work_order_count=configured.work_order_count,
            wafers_per_work_order=configured.wafers_per_work_order,
            chips_per_wafer=configured.chips_per_wafer,
            start_date=configured.start_date,
        )
    )
    store = ParquetGenerationStore(
        configured.storage_root,
        schema_version=configured.schema_version,
        retain_generations=configured.retain_generations,
    )
    snapshots = SnapshotManager()
    sorting_preload = SortingPreload(store)
    coordinator = RefreshCoordinator(
        source, YieldTransformer(configured.rules), store, snapshots, sorting_preload
    )
    details = TargetedDetailRepository(store)
    analytics = YieldAnalytics(snapshots, details, sorting_preload)
    services = ApplicationServices(
        configured,
        source,
        store,
        snapshots,
        sorting_preload,
        coordinator,
        details,
        analytics,
    )
    if ensure_ready:
        coordinator.ensure_ready()
    return services


def start_background_services(services: ApplicationServices) -> list[threading.Thread]:
    """Start server-owned refresh, hot-reload, and separate Sorting cycles."""
    stop = threading.Event()
    watcher = GenerationWatcher(services.store, services.snapshots)
    logger = logging.getLogger(__name__)

    def generation_watch_loop() -> None:
        while not stop.wait(services.settings.generation_poll_seconds):
            if watcher.check_once():
                generation_id = services.snapshots.get().generation_id
                services.sorting_preload.refresh_async(generation_id)

    def scheduled_refresh_loop() -> None:
        while not stop.wait(services.settings.refresh_seconds):
            try:
                services.refresh.refresh(
                    preload_delay_seconds=(services.settings.sorting_background_delay_seconds)
                )
            except Exception:
                logger.exception("Scheduled refresh failed; active generation retained")

    def sorting_refresh_loop() -> None:
        while not stop.wait(services.settings.sorting_preload_seconds):
            services.sorting_preload.refresh(services.snapshots.get().generation_id)

    threads = [
        threading.Thread(
            target=generation_watch_loop,
            name="yield-generation-watch",
            daemon=True,
        ),
        threading.Thread(
            target=scheduled_refresh_loop,
            name="yield-scheduled-refresh",
            daemon=True,
        ),
        threading.Thread(
            target=sorting_refresh_loop,
            name="sorting-refresh-cycle",
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    return threads

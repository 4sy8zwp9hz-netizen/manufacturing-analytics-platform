"""Refresh, in-memory publication, preload, and generation-watch services."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from manufacturing_analytics.sources import ManufacturingSource
from manufacturing_analytics.storage import Generation, ParquetGenerationStore
from manufacturing_analytics.transforms import YieldTransformer

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Snapshot:
    generation_id: str
    published_at: str
    loaded_at: datetime
    datasets: dict[str, pd.DataFrame]
    statistics: dict[str, Any]


class SnapshotManager:
    """Atomically expose one complete common analytical population to callbacks."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshot: Snapshot | None = None

    def get(self) -> Snapshot:
        with self._lock:
            if self._snapshot is None:
                raise RuntimeError("The first analytical snapshot is not ready")
            return self._snapshot

    def publish(self, generation: Generation) -> Snapshot:
        snapshot = Snapshot(
            generation_id=generation.generation_id,
            published_at=str(generation.manifest["published_at"]),
            loaded_at=datetime.now(UTC),
            datasets=generation.datasets,
            statistics=dict(generation.manifest.get("statistics", {})),
        )
        with self._lock:
            self._snapshot = snapshot
        return snapshot


class SortingPreload:
    """Separate expensive-analysis preload, independent from common snapshot publication."""

    def __init__(self, store: ParquetGenerationStore) -> None:
        self.store = store
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._summary = pd.DataFrame()
        self._status: dict[str, Any] = {
            "state": "waiting",
            "generation_id": None,
            "message": "Sorting parameter preload is waiting for the first generation.",
            "updated_at": None,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def summary(self) -> pd.DataFrame:
        with self._lock:
            return self._summary.copy()

    def wait_until_idle(self, timeout_seconds: float = 10.0) -> bool:
        """Wait for the current background preload without starting new work."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.status()["state"] != "loading":
                return True
            time.sleep(0.01)
        return False

    def refresh(self, generation_id: str, *, fail: bool = False) -> None:
        if not self._refresh_lock.acquire(blocking=False):
            return
        try:
            with self._lock:
                self._status.update(
                    state="loading",
                    message="Sorting parameter detail is loading on its separate cycle.",
                )
            if fail:
                raise RuntimeError("Injected Sorting preload failure")
            generation = self.store.load_current(include_targeted=True)
            detail = generation.datasets["targeted_sorting_parameter_detail"]
            summary = (
                detail.groupby("parameter", as_index=False)
                .agg(total=("passed", "size"), good=("passed", "sum"))
                .assign(yield_rate=lambda frame: frame["good"] / frame["total"])
                .sort_values("yield_rate")
            )
            with self._lock:
                self._summary = summary
                self._status = {
                    "state": "ready",
                    "generation_id": generation_id,
                    "message": f"Sorting preload ready: {len(detail):,} parameter rows.",
                    "updated_at": datetime.now(UTC).isoformat(),
                }
        except Exception as exc:
            LOGGER.exception("Sorting preload failed; previous preload retained")
            with self._lock:
                self._status.update(
                    state="failed",
                    message=f"Sorting preload failed; previous results retained: {exc}",
                    updated_at=datetime.now(UTC).isoformat(),
                )
        finally:
            self._refresh_lock.release()

    def refresh_async(self, generation_id: str, delay_seconds: float = 0.0) -> threading.Thread:
        def worker() -> None:
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            self.refresh(generation_id)

        thread = threading.Thread(target=worker, name="sorting-parameter-preload", daemon=True)
        thread.start()
        return thread


class RefreshCoordinator:
    """Run source extraction and Pandas ETL before publishing a new snapshot."""

    def __init__(
        self,
        source: ManufacturingSource,
        transformer: YieldTransformer,
        store: ParquetGenerationStore,
        snapshots: SnapshotManager,
        sorting_preload: SortingPreload,
    ) -> None:
        self.source = source
        self.transformer = transformer
        self.store = store
        self.snapshots = snapshots
        self.sorting_preload = sorting_preload
        self._refresh_lock = threading.Lock()
        self._status_lock = threading.RLock()
        self._status: dict[str, Any] = {
            "state": "waiting",
            "message": "Waiting for the first refresh.",
            "last_error": None,
        }

    def status(self) -> dict[str, Any]:
        with self._status_lock:
            return dict(self._status)

    def _set_status(self, **values: Any) -> None:
        with self._status_lock:
            self._status.update(values)

    def ensure_ready(self) -> Snapshot:
        try:
            generation = self.store.load_current()
        except FileNotFoundError:
            return self.refresh()
        snapshot = self.snapshots.publish(generation)
        self._set_status(
            state="ready",
            message=f"Loaded known-good generation {snapshot.generation_id}.",
            generation_id=snapshot.generation_id,
        )
        self.sorting_preload.refresh_async(snapshot.generation_id)
        return snapshot

    def refresh(
        self,
        *,
        fail_after: str | None = None,
        preload_delay_seconds: float = 0.0,
    ) -> Snapshot:
        if not self._refresh_lock.acquire(blocking=False):
            return self.snapshots.get()
        previous: Snapshot | None
        try:
            try:
                previous = self.snapshots.get()
            except RuntimeError:
                previous = None
            self._set_status(state="refreshing", message="Refreshing source data and ETL...")
            raw = self.source.extract_common()
            if fail_after == "extract":
                raise RuntimeError("Injected refresh failure after extraction")
            prepared = self.transformer.transform(raw)
            if fail_after == "transform":
                raise RuntimeError("Injected refresh failure after transformation")
            physical_ids = prepared.datasets["wafer_summary"]["physical_wafer_id"].tolist()
            chip_detail = self.source.extract_targeted("chip_detail", physical_ids)
            sorting_detail = self.source.extract_targeted("sorting_parameter_detail", physical_ids)
            prepared.datasets["targeted_chip_detail"] = self.transformer.transform_targeted(
                chip_detail, raw["identity_aliases"], "chip_detail"
            )
            prepared.datasets["targeted_sorting_parameter_detail"] = (
                self.transformer.transform_targeted(
                    sorting_detail, raw["identity_aliases"], "sorting_parameter_detail"
                )
            )
            storage_failure = fail_after if fail_after in {"write", "validate"} else None
            manifest = self.store.publish(
                prepared.datasets, prepared.statistics, fail_after=storage_failure
            )
            generation = self.store.load_current()
            snapshot = self.snapshots.publish(generation)
            self._set_status(
                state="ready",
                message=(
                    f"Generation {snapshot.generation_id} published | "
                    f"{snapshot.statistics.get('physical_wafers', 0):,} physical wafers"
                ),
                generation_id=snapshot.generation_id,
                published_at=manifest["published_at"],
                last_error=None,
            )
            self.sorting_preload.refresh_async(
                snapshot.generation_id, delay_seconds=preload_delay_seconds
            )
            return snapshot
        except Exception as exc:
            LOGGER.exception("Refresh failed; previous known-good snapshot retained")
            self._set_status(
                state="failed",
                message="Refresh failed; previous known-good data remains active.",
                last_error=str(exc),
                generation_id=previous.generation_id if previous else None,
            )
            raise
        finally:
            self._refresh_lock.release()

    def refresh_async(self, *, preload_delay_seconds: float = 0.0) -> threading.Thread:
        def worker() -> None:
            try:
                self.refresh(preload_delay_seconds=preload_delay_seconds)
            except Exception:
                return

        thread = threading.Thread(target=worker, name="yield-refresh", daemon=True)
        thread.start()
        return thread


class GenerationWatcher:
    """Hot-load a newly published generation without restarting the web server."""

    def __init__(self, store: ParquetGenerationStore, snapshots: SnapshotManager) -> None:
        self.store = store
        self.snapshots = snapshots

    def check_once(self) -> bool:
        generation_id = self.store.current_generation_id()
        try:
            active_id = self.snapshots.get().generation_id
        except RuntimeError:
            active_id = None
        if not generation_id or generation_id == active_id:
            return False
        try:
            self.snapshots.publish(self.store.load_current())
            return True
        except Exception:
            LOGGER.exception("Generation hot reload failed; active snapshot retained")
            return False

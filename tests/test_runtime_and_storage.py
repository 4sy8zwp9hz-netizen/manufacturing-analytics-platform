from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from manufacturing_analytics.runtime import GenerationWatcher, SnapshotManager


def test_parquet_generation_has_manifest_and_excludes_targeted_data_from_memory(services) -> None:
    generation = services.store.load_current()
    assert generation.manifest["status"] == "VALIDATED"
    assert (generation.path / "manifest.json").is_file()
    assert "yield_fact" in generation.datasets
    assert "targeted_chip_detail" not in generation.datasets
    assert "targeted_sorting_parameter_detail" not in generation.datasets
    assert generation.manifest["datasets"]["targeted_chip_detail"]["load_policy"] == "targeted"


@pytest.mark.parametrize("failure_stage", ["extract", "transform", "write", "validate"])
def test_failed_refresh_retains_previous_generation(services, failure_stage: str) -> None:
    previous = services.snapshots.get().generation_id
    pointer = services.store.current_generation_id()

    with pytest.raises(RuntimeError, match="Injected refresh failure"):
        services.refresh.refresh(fail_after=failure_stage)

    assert services.snapshots.get().generation_id == previous
    assert services.store.current_generation_id() == pointer
    assert services.refresh.status()["state"] == "failed"
    assert not list(services.store.generations_root.glob(".*.building"))


def test_successful_refresh_atomically_changes_generation(services) -> None:
    previous = services.snapshots.get().generation_id
    current = services.refresh.refresh()
    assert current.generation_id != previous
    assert services.store.current_generation_id() == current.generation_id
    assert len(list(services.store.generations_root.iterdir())) <= 2


def test_generation_watcher_hot_loads_external_publication(services) -> None:
    independent_snapshots = SnapshotManager()
    independent_snapshots.publish(services.store.load_current())
    previous = independent_snapshots.get().generation_id

    services.refresh.refresh()
    watcher = GenerationWatcher(services.store, independent_snapshots)

    assert watcher.check_once()
    assert independent_snapshots.get().generation_id != previous
    assert independent_snapshots.get().generation_id == services.store.current_generation_id()


def test_targeted_repository_reads_one_wafer_not_the_full_detail_population(services) -> None:
    generation = services.store.load_current(include_targeted=True)
    full = generation.datasets["targeted_chip_detail"]
    scoped = services.details.chip_detail(["PHY-00001"])

    assert len(scoped) == services.settings.chips_per_wafer
    assert len(scoped) < len(full)
    assert scoped["physical_wafer_id"].eq("PHY-00001").all()
    assert services.details.last_scope_size == 1


def test_sorting_preload_has_independent_last_good_behavior(services) -> None:
    generation_id = services.snapshots.get().generation_id
    assert services.sorting_preload.wait_until_idle()
    services.sorting_preload.refresh(generation_id)
    before = services.sorting_preload.summary()
    services.sorting_preload.refresh(generation_id, fail=True)

    assert not before.empty
    pd.testing.assert_frame_equal(before, services.sorting_preload.summary())
    assert services.sorting_preload.status()["state"] == "failed"
    assert "retained" in services.sorting_preload.status()["message"]


def test_corrupt_pointer_falls_back_to_retained_valid_generation(services) -> None:
    previous = services.store.resolve_current_path()
    services.store.current_pointer.write_text("not-json", encoding="utf-8")
    assert services.store.resolve_current_path() == previous


def test_generation_files_are_parquet_not_sqlite(services) -> None:
    generation = services.store.load_current(include_targeted=True)
    assert list(generation.path.glob("*.parquet"))
    assert not list(Path(services.settings.storage_root).rglob("*.sqlite*"))

"""Immutable Parquet generations and targeted-detail access."""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

COMMON_DATASETS = {
    "yield_fact",
    "failure_fact",
    "wafer_summary",
    "final_component_fact",
    "lineage",
    "identity_audit",
    "filter_domains",
    "prebuilt_trend",
    "prebuilt_pareto",
}
TARGETED_DATASETS = {"targeted_chip_detail", "targeted_sorting_parameter_detail"}
REQUIRED_DATASETS = COMMON_DATASETS | TARGETED_DATASETS


@dataclass(frozen=True)
class Generation:
    generation_id: str
    path: Path
    manifest: dict[str, Any]
    datasets: dict[str, pd.DataFrame]


class ParquetGenerationStore:
    """Publish complete generations while preserving the previous known-good one."""

    def __init__(self, root: Path, *, schema_version: int = 1, retain_generations: int = 3) -> None:
        self.root = Path(root).resolve()
        self.schema_version = int(schema_version)
        self.retain_generations = max(2, int(retain_generations))
        self.generations_root = self.root / "generations"
        self.current_pointer = self.root / "CURRENT.json"
        self.generations_root.mkdir(parents=True, exist_ok=True)
        self._writer_lock = threading.Lock()

    def current_generation_id(self) -> str | None:
        try:
            payload = json.loads(self.current_pointer.read_text(encoding="utf-8"))
            generation_id = str(payload.get("generation_id") or "").strip()
            return generation_id or None
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _generation_path(self, generation_id: str) -> Path:
        return self.generations_root / generation_id

    def publish(
        self,
        datasets: dict[str, pd.DataFrame],
        statistics: dict[str, Any],
        *,
        fail_after: str | None = None,
    ) -> dict[str, Any]:
        missing = REQUIRED_DATASETS.difference(datasets)
        if missing:
            raise ValueError(f"Generation is missing required datasets: {sorted(missing)}")
        with self._writer_lock:
            now = datetime.now(UTC)
            generation_id = f"{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
            temporary = self.generations_root / f".{generation_id}.building"
            final = self._generation_path(generation_id)
            temporary.mkdir(parents=False, exist_ok=False)
            try:
                manifest_datasets: dict[str, dict[str, Any]] = {}
                for name, frame in datasets.items():
                    filename = f"{name}.parquet"
                    frame.to_parquet(temporary / filename, index=False, compression="zstd")
                    manifest_datasets[name] = {
                        "file": filename,
                        "rows": int(len(frame)),
                        "columns": list(frame.columns),
                        "load_policy": "targeted" if name in TARGETED_DATASETS else "common",
                    }
                if fail_after == "write":
                    raise RuntimeError("Injected refresh failure after Parquet write")
                manifest = {
                    "schema_version": self.schema_version,
                    "generation_id": generation_id,
                    "published_at": now.isoformat(),
                    "status": "VALIDATED",
                    "datasets": manifest_datasets,
                    "statistics": statistics,
                }
                self._write_json(temporary / "manifest.json", manifest)
                self.validate_path(temporary)
                if fail_after == "validate":
                    raise RuntimeError("Injected refresh failure after validation")
                os.replace(temporary, final)
                pointer_next = self.root / "CURRENT.next.json"
                self._write_json(pointer_next, {"generation_id": generation_id})
                os.replace(pointer_next, self.current_pointer)
                self._cleanup_old_generations()
                return manifest
            except Exception:
                if temporary.exists():
                    shutil.rmtree(temporary)
                raise

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def validate_path(self, path: Path) -> dict[str, Any]:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("schema_version") != self.schema_version:
            raise ValueError("Parquet generation schema version is incompatible")
        if manifest.get("status") != "VALIDATED":
            raise ValueError("Parquet generation was not validated")
        missing = REQUIRED_DATASETS.difference(manifest.get("datasets", {}))
        if missing:
            raise ValueError(f"Manifest is missing datasets: {sorted(missing)}")
        for name, metadata in manifest["datasets"].items():
            parquet_path = path / metadata["file"]
            if not parquet_path.is_file():
                raise ValueError(f"Dataset file is missing: {name}")
            if int(metadata["rows"]) < 0:
                raise ValueError(f"Dataset row count is invalid: {name}")
        if int(manifest["datasets"]["yield_fact"]["rows"]) == 0:
            raise ValueError("Validated generation cannot contain an empty yield population")
        return manifest

    def resolve_current_path(self) -> Path:
        generation_id = self.current_generation_id()
        if generation_id:
            candidate = self._generation_path(generation_id)
            try:
                self.validate_path(candidate)
                return candidate
            except (FileNotFoundError, ValueError, json.JSONDecodeError):
                pass
        # A damaged pointer must not make every retained known-good generation unusable.
        candidates = sorted(
            (path for path in self.generations_root.iterdir() if path.is_dir()), reverse=True
        )
        for candidate in candidates:
            try:
                self.validate_path(candidate)
                return candidate
            except (FileNotFoundError, ValueError, json.JSONDecodeError):
                continue
        raise FileNotFoundError("No valid analytical generation is available")

    def load_current(self, *, include_targeted: bool = False) -> Generation:
        path = self.resolve_current_path()
        manifest = self.validate_path(path)
        datasets: dict[str, pd.DataFrame] = {}
        for name, metadata in manifest["datasets"].items():
            if not include_targeted and metadata.get("load_policy") == "targeted":
                continue
            datasets[name] = pd.read_parquet(path / metadata["file"])
        return Generation(manifest["generation_id"], path, manifest, datasets)

    def read_targeted(
        self,
        dataset: str,
        physical_wafer_ids: Sequence[str],
    ) -> pd.DataFrame:
        if dataset not in TARGETED_DATASETS:
            raise ValueError(f"Dataset is not configured for targeted access: {dataset}")
        if not physical_wafer_ids:
            return pd.DataFrame()
        path = self.resolve_current_path()
        manifest = self.validate_path(path)
        parquet_path = path / manifest["datasets"][dataset]["file"]
        return pd.read_parquet(
            parquet_path,
            filters=[("physical_wafer_id", "in", list(dict.fromkeys(physical_wafer_ids)))],
        )

    def _cleanup_old_generations(self) -> None:
        generations = sorted(
            (path for path in self.generations_root.iterdir() if path.is_dir()), reverse=True
        )
        for path in generations[self.retain_generations :]:
            resolved = path.resolve()
            if resolved.parent != self.generations_root.resolve() or path.name.startswith("."):
                continue
            shutil.rmtree(resolved)


class TargetedDetailRepository:
    """Read only the detail population selected by the investigation workflow."""

    def __init__(self, store: ParquetGenerationStore) -> None:
        self.store = store
        self.query_count = 0
        self.last_scope_size = 0

    def chip_detail(self, physical_wafer_ids: Sequence[str]) -> pd.DataFrame:
        return self._read("targeted_chip_detail", physical_wafer_ids)

    def sorting_parameters(self, physical_wafer_ids: Sequence[str]) -> pd.DataFrame:
        return self._read("targeted_sorting_parameter_detail", physical_wafer_ids)

    def _read(self, dataset: str, physical_wafer_ids: Sequence[str]) -> pd.DataFrame:
        self.query_count += 1
        self.last_scope_size = len(set(physical_wafer_ids))
        return self.store.read_targeted(dataset, physical_wafer_ids)

"""Immutable analytical generations with atomic known-good publication."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


class GenerationStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.current_pointer = self.root / "CURRENT"

    def building_path(self, generation_id: str) -> Path:
        return self.root / f"{generation_id}.building.sqlite"

    def final_path(self, generation_id: str) -> Path:
        return self.root / f"{generation_id}.sqlite"

    def current_generation_id(self) -> str | None:
        if not self.current_pointer.exists():
            return None
        value = self.current_pointer.read_text(encoding="utf-8").strip()
        return value or None

    def current_path(self) -> Path | None:
        generation_id = self.current_generation_id()
        if generation_id is None:
            return None
        path = self.final_path(generation_id)
        return path if path.exists() else None

    def publish(self, generation_id: str, building_path: Path) -> Path:
        """Publish only a completed database, then atomically switch the reader pointer."""
        final_path = self.final_path(generation_id)
        os.replace(building_path, final_path)
        temporary_pointer = self.root / "CURRENT.next"
        temporary_pointer.write_text(generation_id, encoding="utf-8")
        os.replace(temporary_pointer, self.current_pointer)
        return final_path

    def validate(self, path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError(f"Analytical generation integrity check failed: {integrity}")
            metadata = connection.execute(
                "SELECT publication_status FROM generation_metadata"
            ).fetchone()
            if metadata is None or metadata[0] != "VALIDATED":
                raise ValueError("Analytical generation did not reach VALIDATED status")
            if connection.execute("SELECT COUNT(*) FROM canonical_wafers").fetchone()[0] == 0:
                raise ValueError("Analytical generation has no canonical wafers")
        finally:
            connection.close()

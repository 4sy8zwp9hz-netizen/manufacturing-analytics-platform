"""Deterministic, intentionally heterogeneous synthetic source systems."""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class SourceGenerationConfig:
    seed: int = 20260813
    work_orders: int = 4
    lots_per_work_order: int = 3
    wafers_per_lot: int = 5
    die_grid_size: int = 7


SOURCE_SCHEMAS = {
    "genealogy": """
        CREATE TABLE identity_aliases (
            source_record_id TEXT, alias_type TEXT, alias_value TEXT,
            canonical_work_order TEXT, canonical_lot TEXT, canonical_wafer TEXT,
            product_code TEXT, reconciliation_note TEXT
        );
    """,
    "mes": """
        CREATE TABLE process_history (
            source_row_id INTEGER PRIMARY KEY, event_key TEXT, work_order_ref TEXT,
            lot_ref TEXT, wafer_number INTEGER, substrate_serial TEXT,
            process_label TEXT, event_timestamp TEXT, arrival_timestamp TEXT,
            event_status TEXT, population_label TEXT
        );
    """,
    "wafer_inspection": """
        CREATE TABLE wafer_observations (
            source_row_id INTEGER PRIMARY KEY, inspection_record_id TEXT,
            substrate_ref TEXT, inspection_time_text TEXT, arrival_timestamp TEXT,
            revision INTEGER, inspected_sites INTEGER, failed_sites INTEGER,
            defect_label TEXT, record_status TEXT
        );
    """,
    "chip_test": """
        CREATE TABLE chip_measurements (
            source_row_id INTEGER PRIMARY KEY, measurement_key TEXT, device_id TEXT,
            wafer_alias TEXT, x_position INTEGER, y_position INTEGER,
            test_timestamp TEXT, arrival_timestamp TEXT, revision INTEGER,
            result_code TEXT, failure_code TEXT
        );
    """,
    "sorting": """
        CREATE TABLE sort_results (
            source_row_id INTEGER PRIMARY KEY, sort_record_id TEXT,
            order_number TEXT, wafer_sequence INTEGER, device_id TEXT,
            measured_at TEXT, parameter_name TEXT, parameter_value REAL,
            lower_limit REAL, upper_limit REAL
        );
    """,
    "qualification": """
        CREATE TABLE qualification_results (
            source_row_id INTEGER PRIMARY KEY, qualification_id TEXT,
            lot_number TEXT, wafer_sequence INTEGER, completed_date TEXT,
            stress_group TEXT, sample_size INTEGER, passing_count INTEGER,
            population_label TEXT
        );
    """,
}


class SyntheticSourceFactory:
    """Create isolated source files; no source resembles an analytical warehouse."""

    def __init__(self, root: Path, config: SourceGenerationConfig | None = None) -> None:
        self.root = root
        self.config = config or SourceGenerationConfig()
        self.random = random.Random(self.config.seed)

    def create(self, replace: bool = False) -> dict[str, Path]:
        self.root.mkdir(parents=True, exist_ok=True)
        paths = {name: self.root / f"{name}.sqlite" for name in SOURCE_SCHEMAS}
        if not replace and all(path.exists() for path in paths.values()):
            return paths
        for name, path in paths.items():
            path.unlink(missing_ok=True)
            connection = sqlite3.connect(path)
            try:
                connection.executescript(SOURCE_SCHEMAS[name])
                connection.commit()
            finally:
                connection.close()
        records = self._records()
        for name, tables in records.items():
            connection = sqlite3.connect(paths[name])
            try:
                for table, rows in tables.items():
                    if not rows:
                        continue
                    columns = tuple(rows[0])
                    placeholders = ", ".join("?" for _ in columns)
                    connection.executemany(
                        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",  # noqa: S608
                        (tuple(row[column] for column in columns) for row in rows),
                    )
                connection.commit()
            finally:
                connection.close()
        return paths

    def _records(self) -> dict[str, dict[str, list[dict[str, object]]]]:
        data = {name: {} for name in SOURCE_SCHEMAS}
        data["genealogy"]["identity_aliases"] = []
        data["mes"]["process_history"] = []
        data["wafer_inspection"]["wafer_observations"] = []
        data["chip_test"]["chip_measurements"] = []
        data["sorting"]["sort_results"] = []
        data["qualification"]["qualification_results"] = []
        base = datetime(2026, 1, 5, 8, tzinfo=UTC)
        source_ids = {name: 1 for name in SOURCE_SCHEMAS if name != "genealogy"}
        global_wafer = 1
        for order_index in range(1, self.config.work_orders + 1):
            work_order = f"WO-{order_index:03d}"
            product = "ORION-A" if order_index % 2 else "ORION-B"
            for lot_index in range(1, self.config.lots_per_work_order + 1):
                lot = f"LOT-{order_index:03d}-{lot_index:02d}"
                lot_start = base + timedelta(days=(order_index - 1) * 21 + lot_index * 4)
                for wafer_number in range(1, self.config.wafers_per_lot + 1):
                    order_wafer_sequence = (
                        lot_index - 1
                    ) * self.config.wafers_per_lot + wafer_number
                    wafer = f"WAF-{global_wafer:06d}"
                    substrate = f"SUB-{700000 + global_wafer}"
                    inspection_alias = f"WI-{lot}-{wafer_number:02d}"
                    aliases = (
                        ("SUBSTRATE_SERIAL", substrate, "exact alias"),
                        ("INSPECTION_ALIAS", inspection_alias, "exact alias"),
                        (
                            "ORDER_WAFER",
                            f"{work_order}|{order_wafer_sequence}",
                            "composite order + wafer sequence",
                        ),
                        ("LOT_WAFER", f"{lot}|{wafer_number}", "composite lot + wafer"),
                    )
                    for alias_type, alias_value, note in aliases:
                        alias_number = len(data["genealogy"]["identity_aliases"]) + 1
                        data["genealogy"]["identity_aliases"].append(
                            {
                                "source_record_id": f"ID-{alias_number:07d}",
                                "alias_type": alias_type,
                                "alias_value": alias_value,
                                "canonical_work_order": work_order,
                                "canonical_lot": lot,
                                "canonical_wafer": wafer,
                                "product_code": product,
                                "reconciliation_note": note,
                            }
                        )
                    incomplete = global_wafer % 17 == 0
                    processes = ("COAT", "ETCH-A", "FINAL TEST")
                    for sequence, process in enumerate(processes):
                        if incomplete and sequence == 2:
                            continue
                        source_id = source_ids["mes"]
                        timestamp = lot_start + timedelta(hours=sequence * 8, minutes=wafer_number)
                        process_label = (
                            "ETCH ALPHA"
                            if process == "ETCH-A" and global_wafer % 3 == 0
                            else process
                        )
                        data["mes"]["process_history"].append(
                            {
                                "source_row_id": source_id,
                                "event_key": f"EV-{global_wafer:06d}-{sequence}",
                                "work_order_ref": work_order,
                                "lot_ref": lot,
                                "wafer_number": wafer_number,
                                "substrate_serial": None if global_wafer % 19 == 0 else substrate,
                                "process_label": process_label,
                                "event_timestamp": timestamp.isoformat(),
                                "arrival_timestamp": (timestamp + timedelta(minutes=8)).isoformat(),
                                "event_status": "COMPLETE",
                                "population_label": "PRODUCTION",
                            }
                        )
                        source_ids["mes"] += 1
                    inspection_time = lot_start + timedelta(hours=18)
                    failed_sites = 3 + global_wafer % 8
                    inspection_record = {
                        "source_row_id": source_ids["wafer_inspection"],
                        "inspection_record_id": f"INSP-{global_wafer:06d}",
                        "substrate_ref": inspection_alias,
                        "inspection_time_text": inspection_time.strftime("%Y/%m/%d %H:%M"),
                        "arrival_timestamp": (inspection_time + timedelta(minutes=20)).isoformat(),
                        "revision": 1,
                        "inspected_sites": 100,
                        "failed_sites": failed_sites + (2 if global_wafer % 11 == 0 else 0),
                        "defect_label": "surface spot" if global_wafer % 4 else "edge mark",
                        "record_status": "VALID",
                    }
                    data["wafer_inspection"]["wafer_observations"].append(inspection_record)
                    source_ids["wafer_inspection"] += 1
                    if global_wafer == 7:
                        duplicate = dict(inspection_record)
                        duplicate["source_row_id"] = source_ids["wafer_inspection"]
                        data["wafer_inspection"]["wafer_observations"].append(duplicate)
                        source_ids["wafer_inspection"] += 1
                    if global_wafer % 11 == 0:
                        revised = dict(inspection_record)
                        revised.update(
                            source_row_id=source_ids["wafer_inspection"],
                            revision=2,
                            failed_sites=failed_sites,
                            arrival_timestamp=(inspection_time + timedelta(hours=6)).isoformat(),
                        )
                        data["wafer_inspection"]["wafer_observations"].append(revised)
                        source_ids["wafer_inspection"] += 1
                    for x in range(self.config.die_grid_size):
                        for y in range(self.config.die_grid_size):
                            device = f"DEV-{substrate}-{x:02d}{y:02d}"
                            fail_probability = 0.025 + (0.12 if global_wafer % 13 == 0 else 0)
                            passed = self.random.random() >= fail_probability
                            result = {
                                "source_row_id": source_ids["chip_test"],
                                "measurement_key": f"CT-{global_wafer:06d}-{x:02d}-{y:02d}",
                                "device_id": device,
                                "wafer_alias": substrate,
                                "x_position": x,
                                "y_position": y,
                                "test_timestamp": (lot_start + timedelta(hours=27)).isoformat(),
                                "arrival_timestamp": (
                                    lot_start
                                    + timedelta(hours=27, minutes=10)
                                    + (timedelta(days=2) if global_wafer % 23 == 0 else timedelta())
                                ).isoformat(),
                                "revision": 1,
                                "result_code": "P" if passed else "F",
                                "failure_code": None if passed else ("E7" if x in {0, 6} else "C2"),
                            }
                            data["chip_test"]["chip_measurements"].append(result)
                            source_ids["chip_test"] += 1
                            sort_value = self.random.gauss(50, 2.1) + (
                                5 if global_wafer % 13 == 0 else 0
                            )
                            data["sorting"]["sort_results"].append(
                                {
                                    "source_row_id": source_ids["sorting"],
                                    "sort_record_id": f"SORT-{global_wafer:06d}-{x:02d}-{y:02d}",
                                    "order_number": work_order,
                                    "wafer_sequence": order_wafer_sequence,
                                    "device_id": device,
                                    "measured_at": (lot_start + timedelta(hours=31)).isoformat(),
                                    "parameter_name": "SYNTHETIC_RESPONSE",
                                    "parameter_value": round(sort_value, 3),
                                    "lower_limit": 44.0,
                                    "upper_limit": 56.0,
                                }
                            )
                            source_ids["sorting"] += 1
                    data["qualification"]["qualification_results"].append(
                        {
                            "source_row_id": source_ids["qualification"],
                            "qualification_id": f"QUAL-{global_wafer:06d}",
                            "lot_number": lot,
                            "wafer_sequence": wafer_number,
                            "completed_date": (lot_start + timedelta(days=7)).date().isoformat(),
                            "stress_group": "FICTIONAL_STRESS_A",
                            "sample_size": 12,
                            "passing_count": 12 if global_wafer % 14 else 11,
                            "population_label": "QUALIFICATION",
                        }
                    )
                    source_ids["qualification"] += 1
                    global_wafer += 1
        # Explicit unresolved and ambiguous teaching cases do not contaminate production metrics.
        data["genealogy"]["identity_aliases"].extend(
            [
                {
                    "source_record_id": "ID-AMB-1",
                    "alias_type": "SUBSTRATE_SERIAL",
                    "alias_value": "AMBIGUOUS-SUBSTRATE",
                    "canonical_work_order": "WO-001",
                    "canonical_lot": "LOT-001-01",
                    "canonical_wafer": "WAF-000001",
                    "product_code": "ORION-A",
                    "reconciliation_note": "fictional ambiguous alias",
                },
                {
                    "source_record_id": "ID-AMB-2",
                    "alias_type": "SUBSTRATE_SERIAL",
                    "alias_value": "AMBIGUOUS-SUBSTRATE",
                    "canonical_work_order": "WO-002",
                    "canonical_lot": "LOT-002-01",
                    "canonical_wafer": "WAF-000016",
                    "product_code": "ORION-B",
                    "reconciliation_note": "fictional ambiguous alias",
                },
            ]
        )
        data["wafer_inspection"]["wafer_observations"].append(
            {
                "source_row_id": source_ids["wafer_inspection"],
                "inspection_record_id": "INSP-UNRESOLVED",
                "substrate_ref": "UNKNOWN-SUBSTRATE",
                "inspection_time_text": "2026/01/31 12:00",
                "arrival_timestamp": "2026-01-31T12:30:00+00:00",
                "revision": 1,
                "inspected_sites": 100,
                "failed_sites": 9,
                "defect_label": "unknown mark",
                "record_status": "VALID",
            }
        )
        return data


class SourceAdapter:
    """Source-specific extraction boundary with an explicit watermark."""

    def __init__(
        self, name: str, path: Path, table: str, watermark_column: str | None = None
    ) -> None:
        self.name, self.path, self.table = name, path, table
        self.watermark_column = watermark_column

    def extract(self) -> list[dict[str, object]]:
        connection = sqlite3.connect(self.path)
        try:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(f"SELECT * FROM {self.table}")]  # noqa: S608
        finally:
            connection.close()

    def watermark(self, rows: list[dict[str, object]] | None = None) -> dict[str, object]:
        rows = self.extract() if rows is None else rows
        values = [str(row[self.watermark_column]) for row in rows] if self.watermark_column else []
        return {
            "source_name": self.name,
            "row_count": len(rows),
            "source_file": self.path.name,
            "watermark_value": max(values) if values else "STATIC_SNAPSHOT",
        }


def source_adapters(paths: dict[str, Path]) -> dict[str, SourceAdapter]:
    tables = {
        "genealogy": ("identity_aliases", None),
        "mes": ("process_history", "arrival_timestamp"),
        "wafer_inspection": ("wafer_observations", "arrival_timestamp"),
        "chip_test": ("chip_measurements", "arrival_timestamp"),
        "sorting": ("sort_results", "measured_at"),
        "qualification": ("qualification_results", "completed_date"),
    }
    return {
        name: SourceAdapter(name, paths[name], table, watermark)
        for name, (table, watermark) in tables.items()
    }

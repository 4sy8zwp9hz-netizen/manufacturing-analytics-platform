"""Extract, reconcile, transform, validate, and publish analytical generations."""

from __future__ import annotations

import sqlite3
import tomllib
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from manufacturing_analytics.pipeline.generation_store import GenerationStore
from manufacturing_analytics.pipeline.identity import IdentityResolution, IdentityResolver
from manufacturing_analytics.pipeline.sources import SourceAdapter

SCHEMA_PATH = Path(__file__).with_name("analytical_schema.sql")
RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "transformation_rules.toml"


class RefreshPipeline:
    def __init__(self, adapters: dict[str, SourceAdapter], store: GenerationStore) -> None:
        self.adapters = adapters
        self.store = store

    def refresh(self, fail_after: str | None = None) -> dict[str, object]:
        generation_id = datetime.now(UTC).strftime("gen-%Y%m%dT%H%M%S-") + uuid4().hex[:8]
        started = datetime.now(UTC)
        timings: dict[str, float] = {}
        building = self.store.building_path(generation_id)
        try:
            mark = perf_counter()
            extracted = {name: adapter.extract() for name, adapter in self.adapters.items()}
            timings["extract_ms"] = self._elapsed(mark)
            self._fail_if("extract", fail_after)

            mark = perf_counter()
            resolver = IdentityResolver(extracted["genealogy"])
            resolved = self._reconcile(extracted, resolver)
            timings["identity_ms"] = self._elapsed(mark)
            self._fail_if("identity", fail_after)

            mark = perf_counter()
            rules = self._load_rules()
            analytical = self._transform(extracted, resolved, rules)
            timings["transform_ms"] = self._elapsed(mark)
            self._fail_if("transform", fail_after)

            mark = perf_counter()
            self._write_generation(building, generation_id, started, analytical)
            timings["analytical_generation_ms"] = self._elapsed(mark)
            self._fail_if("load", fail_after)

            mark = perf_counter()
            self.store.validate(building)
            timings["validation_ms"] = self._elapsed(mark)
            self._fail_if("validation", fail_after)

            mark = perf_counter()
            final_path = self.store.publish(generation_id, building)
            timings["publication_ms"] = self._elapsed(mark)
            return {
                "generation_id": generation_id,
                "path": final_path,
                "timings": timings,
                "row_counts": {key: len(value) for key, value in analytical.items()},
                "warning_count": len(analytical["issues"]),
            }
        except Exception:
            building.unlink(missing_ok=True)
            raise

    @staticmethod
    def _fail_if(stage: str, requested: str | None) -> None:
        if stage == requested:
            raise RuntimeError(f"Injected refresh failure after {stage}")

    @staticmethod
    def _elapsed(mark: float) -> float:
        return round((perf_counter() - mark) * 1000, 3)

    @staticmethod
    def _load_rules() -> dict[str, object]:
        with RULES_PATH.open("rb") as rule_file:
            return tomllib.load(rule_file)

    def _reconcile(
        self, extracted: dict[str, list[dict[str, object]]], resolver: IdentityResolver
    ) -> dict[str, list[tuple[dict[str, object], IdentityResolution]]]:
        methods = {
            "mes": resolver.resolve_mes,
            "wafer_inspection": resolver.resolve_inspection,
            "chip_test": resolver.resolve_chip,
            "sorting": resolver.resolve_sorting,
            "qualification": resolver.resolve_qualification,
        }
        return {
            source: [(row, methods[source](row)) for row in extracted[source]] for source in methods
        }

    def _transform(
        self,
        extracted: dict[str, list[dict[str, object]]],
        resolved: dict[str, list[tuple[dict[str, object], IdentityResolution]]],
        rules: dict[str, object],
    ) -> dict[str, list[dict[str, object]]]:
        process_families = rules["process_families"]
        failure_families = rules["failure_families"]
        required_final = rules["production_rules"]["required_final_process_family"]
        wafers: dict[str, dict[str, object]] = {}
        mes_families: dict[str, set[str]] = defaultdict(set)
        issues: list[dict[str, object]] = []
        population: list[dict[str, object]] = []
        lineage: list[dict[str, object]] = []

        for row, identity in resolved["mes"]:
            if not self._resolved(identity, "mes", row["source_row_id"], issues):
                continue
            if not row.get("substrate_serial"):
                self._issue(
                    issues,
                    "mes",
                    str(row["source_row_id"]),
                    "FALLBACK_IDENTITY",
                    "RESOLVED",
                    "Missing substrate serial; lot + wafer composite used",
                )
            wafer = identity.canonical_wafer or ""
            family = process_families.get(str(row["process_label"]), "UNMAPPED_PROCESS")
            mes_families[wafer].add(family)
            wafers.setdefault(
                wafer,
                self._wafer_row(identity, str(row["event_timestamp"]), completed=False),
            )
        for wafer, row in wafers.items():
            complete = required_final in mes_families[wafer]
            row["completion_status"] = "COMPLETE" if complete else "INCOMPLETE"
            row["production_eligible"] = int(complete)
            record_id = f"PROCESS_COMPLETION:{wafer}"
            self._add_population(
                population,
                lineage,
                record_id,
                wafer,
                "PROCESS_COMPLETION",
                "WAFER",
                wafer,
                True,
                complete,
                None if complete else "INCOMPLETE_ROUTE",
                None,
                str(row["analytical_period"]) + "-01T00:00:00+00:00",
                "mes",
                "process_history",
                wafer,
                "MES events reconciled and normalized to configured process families",
                reconciliation_method="MES alias/composite reconciliation",
            )

        latest_inspections: dict[str, tuple[dict[str, object], IdentityResolution]] = {}
        for row, identity in resolved["wafer_inspection"]:
            key = str(row["inspection_record_id"])
            previous = latest_inspections.get(key)
            if previous is not None:
                issue_type = (
                    "REVISED_RECORD"
                    if int(row["revision"]) > int(previous[0]["revision"])
                    else "DUPLICATE_RECORD"
                )
                self._issue(
                    issues,
                    "wafer_inspection",
                    key,
                    issue_type,
                    "SUPERSEDED",
                    "Latest valid revision retained",
                )
            if previous is None or int(row["revision"]) >= int(previous[0]["revision"]):
                latest_inspections[key] = (row, identity)
        for key, (row, identity) in latest_inspections.items():
            if not self._resolved(identity, "wafer_inspection", key, issues):
                continue
            wafer = identity.canonical_wafer or ""
            eligible = bool(wafers.get(wafer, {}).get("production_eligible"))
            good = int(row["failed_sites"]) <= int(
                rules["production_rules"]["wafer_inspection_max_failed_sites"]
            )
            timestamp = (
                datetime.strptime(str(row["inspection_time_text"]), "%Y/%m/%d %H:%M")
                .replace(tzinfo=UTC)
                .isoformat()
            )
            self._add_population(
                population,
                lineage,
                f"WAFER_INSPECTION:{key}",
                wafer,
                "WAFER_INSPECTION",
                "WAFER",
                key,
                eligible,
                good,
                None if good else failure_families.get(str(row["defect_label"]), "UNCLASSIFIED"),
                None if eligible else "INCOMPLETE_ROUTE",
                timestamp,
                "wafer_inspection",
                "wafer_observations",
                key,
                f"revision {row['revision']} retained; wafer-grain denominator",
                reconciliation_method=identity.method,
            )

        late_wafers: set[str] = set()
        for row, identity in resolved["chip_test"]:
            key = str(row["measurement_key"])
            if not self._resolved(identity, "chip_test", key, issues):
                continue
            acquired = datetime.fromisoformat(str(row["test_timestamp"]))
            arrived = datetime.fromisoformat(str(row["arrival_timestamp"]))
            late_threshold = timedelta(hours=int(rules["production_rules"]["late_arrival_hours"]))
            wafer_alias = str(row["wafer_alias"])
            if arrived - acquired > late_threshold and wafer_alias not in late_wafers:
                self._issue(
                    issues,
                    "chip_test",
                    wafer_alias,
                    "LATE_ARRIVAL",
                    "INCLUDED_IN_CURRENT_GENERATION",
                    f"Arrival lag {arrived - acquired} exceeded {late_threshold}",
                )
                late_wafers.add(wafer_alias)
            wafer = identity.canonical_wafer or ""
            eligible = bool(wafers.get(wafer, {}).get("production_eligible"))
            good = row["result_code"] == "P"
            self._add_population(
                population,
                lineage,
                f"CHIP_TEST:{key}",
                wafer,
                "CHIP_TEST",
                "DIE",
                key,
                eligible,
                good,
                None if good else failure_families.get(str(row["failure_code"]), "UNCLASSIFIED"),
                None if eligible else "INCOMPLETE_ROUTE",
                str(row["test_timestamp"]),
                "chip_test",
                "chip_measurements",
                key,
                "latest die result mapped to canonical wafer; die-grain denominator",
                reconciliation_method=identity.method,
                x=int(row["x_position"]),
                y=int(row["y_position"]),
            )

        for row, identity in resolved["sorting"]:
            key = str(row["sort_record_id"])
            if not self._resolved(identity, "sorting", key, issues):
                continue
            wafer = identity.canonical_wafer or ""
            eligible = bool(wafers.get(wafer, {}).get("production_eligible"))
            good = (
                float(row["lower_limit"])
                <= float(row["parameter_value"])
                <= float(row["upper_limit"])
            )
            self._add_population(
                population,
                lineage,
                f"SORTING:{key}",
                wafer,
                "SORTING",
                "DIE",
                key,
                eligible,
                good,
                None if good else "PARAMETER_OUT_OF_RANGE",
                None if eligible else "INCOMPLETE_ROUTE",
                str(row["measured_at"]),
                "sorting",
                "sort_results",
                key,
                "configured inclusive parameter limits applied at die grain",
                reconciliation_method=identity.method,
            )

        for row, identity in resolved["qualification"]:
            key = str(row["qualification_id"])
            if not self._resolved(identity, "qualification", key, issues):
                continue
            wafer = identity.canonical_wafer or ""
            self._add_population(
                population,
                lineage,
                f"QUALIFICATION:{key}",
                wafer,
                "QUALIFICATION",
                "SAMPLE",
                key,
                False,
                int(row["passing_count"]) == int(row["sample_size"]),
                None
                if int(row["passing_count"]) == int(row["sample_size"])
                else "QUALIFICATION_FAILURE",
                "NON_PRODUCTION_POPULATION",
                str(row["completed_date"]) + "T00:00:00+00:00",
                "qualification",
                "qualification_results",
                key,
                "retained as context; explicitly excluded from production yield",
                reconciliation_method=identity.method,
            )
        return {
            "wafers": list(wafers.values()),
            "population": population,
            "lineage": lineage,
            "issues": issues,
            "watermarks": [
                adapter.watermark(extracted[name]) for name, adapter in self.adapters.items()
            ],
        }

    @staticmethod
    def _wafer_row(
        identity: IdentityResolution, timestamp: str, completed: bool
    ) -> dict[str, object]:
        return {
            "canonical_wafer_id": identity.canonical_wafer,
            "canonical_lot_id": identity.canonical_lot,
            "canonical_work_order_id": identity.canonical_work_order,
            "product_code": identity.product_code,
            "analytical_period": timestamp[:7],
            "completion_status": "COMPLETE" if completed else "INCOMPLETE",
            "production_eligible": int(completed),
        }

    @staticmethod
    def _resolved(
        identity: IdentityResolution, source: str, key: object, issues: list[dict[str, object]]
    ) -> bool:
        if identity.status == "RESOLVED":
            return True
        RefreshPipeline._issue(
            issues,
            source,
            str(key),
            f"{identity.status}_IDENTITY",
            "QUARANTINED",
            identity.source_identity,
        )
        return False

    @staticmethod
    def _issue(
        issues: list[dict[str, object]],
        source: str,
        key: str,
        issue_type: str,
        disposition: str,
        detail: str,
    ) -> None:
        issues.append(
            {
                "source_system": source,
                "source_record_key": key,
                "issue_type": issue_type,
                "disposition": disposition,
                "detail": detail,
            }
        )

    @staticmethod
    def _add_population(
        population: list[dict[str, object]],
        lineage: list[dict[str, object]],
        record_id: str,
        wafer: str,
        stage: str,
        unit: str,
        unit_key: str,
        denominator: bool,
        good: bool,
        failure: str | None,
        exclusion: str | None,
        timestamp: str,
        source: str,
        source_table: str,
        source_key: str,
        note: str,
        reconciliation_method: str = "canonical identity lookup",
        x: int | None = None,
        y: int | None = None,
    ) -> None:
        population.append(
            {
                "analytical_record_id": record_id,
                "canonical_wafer_id": wafer,
                "stage_code": stage,
                "population_unit": unit,
                "unit_key": unit_key,
                "is_denominator": int(denominator),
                "is_good": int(good),
                "failure_family": failure,
                "exclusion_reason": exclusion,
                "event_timestamp": timestamp,
                "x_coordinate": x,
                "y_coordinate": y,
            }
        )
        lineage.append(
            {
                "analytical_record_id": record_id,
                "source_system": source,
                "source_table": source_table,
                "source_record_key": source_key,
                "reconciliation_method": reconciliation_method,
                "transformation_note": note,
            }
        )

    def _write_generation(
        self,
        path: Path,
        generation_id: str,
        started: datetime,
        analytical: dict[str, list[dict[str, object]]],
    ) -> None:
        path.unlink(missing_ok=True)
        connection = sqlite3.connect(path)
        try:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO generation_metadata VALUES (?, ?, ?, ?, ?)",
                (
                    generation_id,
                    started.isoformat(),
                    datetime.now(UTC).isoformat(),
                    "VALIDATED",
                    len(analytical["issues"]),
                ),
            )
            self._insert(connection, "source_watermarks", analytical["watermarks"])
            self._insert(connection, "canonical_wafers", analytical["wafers"])
            self._insert(connection, "stage_population", analytical["population"])
            self._insert(connection, "analytical_lineage", analytical["lineage"])
            self._insert(connection, "transformation_issues", analytical["issues"])
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _insert(connection: sqlite3.Connection, table: str, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        columns = tuple(rows[0])
        values = ", ".join("?" for _ in columns)
        connection.executemany(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values})",  # noqa: S608
            (tuple(row[column] for column in columns) for row in rows),
        )


class ScheduledRefresh:
    """Small scheduler seam; a production deployment would invoke it from a worker."""

    def __init__(self, pipeline: RefreshPipeline, interval: timedelta = timedelta(hours=1)) -> None:
        self.pipeline = pipeline
        self.interval = interval
        self.last_attempt: datetime | None = None

    def run_if_due(self, now: datetime | None = None) -> dict[str, object] | None:
        current = now or datetime.now(UTC)
        if self.last_attempt is not None and current - self.last_attempt < self.interval:
            return None
        self.last_attempt = current
        return self.pipeline.refresh()

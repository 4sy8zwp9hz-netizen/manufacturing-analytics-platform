"""Clean-room manufacturing data sources.

The runnable demo uses :class:`SyntheticManufacturingSource`.  The optional
SQL Server class documents the production-inspired boundary without embedding
any employer SQL, schema names, connection details, or credentials.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import pandas as pd

COMMON_DATASETS = (
    "identity_aliases",
    "wafer_inventory",
    "wafer_inspection",
    "process_results",
    "chip_inspection_summary",
    "sorting_summary",
    "qualification_results",
)


class ManufacturingSource(Protocol):
    """Data-access contract used by the transformation and refresh layer."""

    def extract_common(self) -> dict[str, pd.DataFrame]: ...

    def extract_targeted(self, dataset: str, physical_wafer_ids: Sequence[str]) -> pd.DataFrame: ...


@dataclass(frozen=True)
class SyntheticSourceConfig:
    seed: int = 20260814
    work_order_count: int = 8
    wafers_per_work_order: int = 12
    chips_per_wafer: int = 81
    start_date: str = "2026-01-05"

    def validate(self) -> None:
        if self.work_order_count < 1 or self.wafers_per_work_order < 4:
            raise ValueError("Synthetic data needs at least one work order and four wafers")
        side = int(self.chips_per_wafer**0.5)
        if side * side != self.chips_per_wafer:
            raise ValueError("chips_per_wafer must be a perfect square")


class SyntheticManufacturingSource:
    """Reproducible heterogeneous source records supporting the real workflow."""

    FAILURE_FAMILIES = (
        "Edge Signature",
        "Surface Mark",
        "Pattern Gap",
        "Contact Loss",
        "Parameter Drift",
    )
    PROCESS_STAGES = (
        ("SURFACE_PREPARATION", "Surface Preparation"),
        ("PATTERN_SEPARATION", "Pattern Separation"),
        ("PROTECTIVE_FINISH", "Protective Finish"),
        ("DEVICE_FORMATION", "Device Formation"),
    )
    SORTING_PARAMETERS = (
        ("PWR-A", 0.0, 4.8, 2.35),
        ("RESP-B", 8.0, 13.5, 10.7),
        ("LEAK-C", 0.0, 1.3, 0.52),
        ("ALIGN-D", -2.2, 2.2, 0.0),
        ("GAIN-E", 17.0, 25.0, 21.0),
        ("NOISE-F", 0.0, 3.5, 1.45),
    )

    def __init__(self, config: SyntheticSourceConfig) -> None:
        config.validate()
        self.config = config
        self._frames = self._generate()
        self.targeted_query_count = 0

    def extract_common(self) -> dict[str, pd.DataFrame]:
        """Return independent copies of data commonly prepared during refresh."""
        return {name: self._frames[name].copy() for name in COMMON_DATASETS}

    def extract_targeted(self, dataset: str, physical_wafer_ids: Sequence[str]) -> pd.DataFrame:
        """Simulate a source query restricted to an already-known wafer population."""
        if dataset not in {"chip_detail", "sorting_parameter_detail"}:
            raise ValueError(f"Unsupported targeted dataset: {dataset}")
        self.targeted_query_count += 1
        wanted = set(physical_wafer_ids)
        aliases = self._frames["identity_aliases"]
        source_kind = "CHIP" if dataset == "chip_detail" else "SORTING"
        source_aliases = set(
            aliases.loc[
                aliases["physical_wafer_id"].isin(wanted) & aliases["source_kind"].eq(source_kind),
                "source_alias",
            ]
        )
        alias_column = "chip_wafer_ref" if dataset == "chip_detail" else "sorting_wafer_ref"
        return (
            self._frames[dataset]
            .loc[self._frames[dataset][alias_column].isin(source_aliases)]
            .copy()
        )

    @staticmethod
    def _stamp(value: datetime) -> str:
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _source_alias(kind: str, index: int, lot: str, wafer_number: int) -> str:
        if kind == "MES":
            return f"{lot}/{wafer_number:02d}"
        if kind == "INSPECTION":
            return f"INSP-{index:05d}"
        if kind == "CHIP":
            return f"SUB {700000 + index}"
        if kind == "SORTING":
            return f"SORT_{700000 + index}"
        return f"QUAL-{lot}-{wafer_number:02d}"

    def _generate(self) -> dict[str, pd.DataFrame]:
        rng = random.Random(self.config.seed)
        start = datetime.fromisoformat(self.config.start_date).replace(tzinfo=UTC)
        records: dict[str, list[dict[str, Any]]] = {
            "identity_aliases": [],
            "wafer_inventory": [],
            "wafer_inspection": [],
            "process_results": [],
            "chip_inspection_summary": [],
            "sorting_summary": [],
            "qualification_results": [],
            "chip_detail": [],
            "sorting_parameter_detail": [],
        }
        wafer_index = 0
        side = int(self.config.chips_per_wafer**0.5)
        coordinates = range(-(side // 2), side // 2 + 1)

        for order_index in range(1, self.config.work_order_count + 1):
            work_order = f"WO-FX-{order_index:04d}"
            lot = f"LOT-FX-{order_index:03d}"
            product = "NOVA-A" if order_index % 2 else "NOVA-B"
            wafer_size = "100 mm" if order_index % 3 else "150 mm"
            order_start = start + timedelta(days=(order_index - 1) * 9)
            for wafer_number in range(1, self.config.wafers_per_work_order + 1):
                wafer_index += 1
                physical = f"PHY-{wafer_index:05d}"
                aliases = {
                    kind: self._source_alias(kind, wafer_index, lot, wafer_number)
                    for kind in ("MES", "INSPECTION", "CHIP", "SORTING", "QUALIFICATION")
                }
                event_date = order_start + timedelta(hours=wafer_number * 3)
                for kind, alias in aliases.items():
                    records["identity_aliases"].append(
                        {
                            "source_kind": kind,
                            "source_alias": alias,
                            "normalized_alias": alias.replace(" ", "").replace("_", "-").upper(),
                            "physical_wafer_id": physical,
                            "work_order": work_order,
                            "lot_id": lot,
                            "wafer_number": wafer_number,
                            "product_family": product,
                            "wafer_size": wafer_size,
                        }
                    )
                records["wafer_inventory"].append(
                    {
                        "mes_wafer_ref": aliases["MES"],
                        "work_order_ref": work_order,
                        "lot_ref": lot,
                        "wafer_number": wafer_number,
                        "product_family": product,
                        "wafer_size": wafer_size,
                        "completed_at": self._stamp(event_date + timedelta(hours=26)),
                    }
                )

                wafer_shift = rng.gauss(0, 0.012)
                edge_risk = 0.07 if wafer_index % 17 == 0 else 0.0
                inspection_total = 25
                inspection_failures = max(0, round(rng.gauss(1.2 + edge_risk * 20, 1.0)))
                records["wafer_inspection"].append(
                    {
                        "inspection_wafer_ref": aliases["INSPECTION"],
                        "record_id": f"WI-{wafer_index:05d}",
                        "inspection_at": self._stamp(event_date + timedelta(hours=7)),
                        "sites_inspected": inspection_total,
                        "sites_good": inspection_total - min(inspection_total, inspection_failures),
                        "failure_family": self.FAILURE_FAMILIES[
                            wafer_index % len(self.FAILURE_FAMILIES)
                        ]
                        if inspection_failures
                        else "",
                        "revision": 1,
                    }
                )

                stage_passes: dict[str, bool] = {}
                for stage_offset, (stage_code, _) in enumerate(self.PROCESS_STAGES, start=1):
                    risk = 0.018 + max(0, order_index - 5) * 0.005
                    if stage_code == "PROTECTIVE_FINISH" and wafer_index % 13 == 0:
                        risk += 0.20
                    passed = rng.random() >= risk
                    stage_passes[stage_code] = passed
                    records["process_results"].append(
                        {
                            "mes_wafer_ref": aliases["MES"],
                            "record_id": f"PR-{wafer_index:05d}-{stage_offset}",
                            "stage_code": stage_code,
                            "completed_at": self._stamp(
                                event_date + timedelta(hours=8 + stage_offset * 3)
                            ),
                            "tool_family": f"CELL-{(wafer_index + stage_offset) % 4 + 1}",
                            "passed": passed,
                            "failure_family": self.FAILURE_FAMILIES[
                                (wafer_index + stage_offset) % len(self.FAILURE_FAMILIES)
                            ]
                            if not passed
                            else "",
                        }
                    )

                chip_good = 0
                chip_failures: dict[str, int] = {}
                for chip_number, (x, y) in enumerate(
                    ((x, y) for y in coordinates for x in coordinates), start=1
                ):
                    radial = (x * x + y * y) ** 0.5
                    fail_probability = (
                        0.028 + max(0, radial - 3.0) * edge_risk + max(0, -wafer_shift)
                    )
                    if product == "NOVA-B":
                        fail_probability += 0.008
                    passed = rng.random() >= fail_probability
                    family = ""
                    if not passed:
                        family = self.FAILURE_FAMILIES[(chip_number + wafer_index) % 5]
                        chip_failures[family] = chip_failures.get(family, 0) + 1
                    chip_good += int(passed)
                    records["chip_detail"].append(
                        {
                            "chip_record_id": f"CH-{wafer_index:05d}-{chip_number:03d}-R1",
                            "chip_wafer_ref": aliases["CHIP"],
                            "chip_number": chip_number,
                            "x": x,
                            "y": y,
                            "passed": passed,
                            "failure_family": family,
                            "tested_at": self._stamp(event_date + timedelta(hours=24)),
                            "revision": 1,
                        }
                    )
                    for parameter, lower, upper, center in self.SORTING_PARAMETERS:
                        drift = 0.45 if parameter == "RESP-B" and order_index >= 6 else 0.0
                        spread = (upper - lower) / 4
                        value = center + drift + rng.gauss(0, spread)
                        records["sorting_parameter_detail"].append(
                            {
                                "parameter_record_id": (
                                    f"SP-{wafer_index:05d}-{chip_number:03d}-{parameter}"
                                ),
                                "sorting_wafer_ref": aliases["SORTING"],
                                "chip_number": chip_number,
                                "parameter": parameter,
                                "value": round(value, 4),
                                "lower_limit": lower,
                                "upper_limit": upper,
                                "passed": lower <= value <= upper,
                                "measured_at": self._stamp(event_date + timedelta(hours=25)),
                            }
                        )

                records["chip_inspection_summary"].append(
                    {
                        "chip_wafer_ref": aliases["CHIP"],
                        "record_id": f"CIS-{wafer_index:05d}",
                        "tested_at": self._stamp(event_date + timedelta(hours=24)),
                        "total_chips": self.config.chips_per_wafer,
                        "good_chips": chip_good,
                        "dominant_failure": max(chip_failures, key=chip_failures.get)
                        if chip_failures
                        else "",
                        "revision": 1,
                    }
                )
                sorting_total = self.config.chips_per_wafer
                sorting_loss = max(0, round(rng.gauss(2.0 + (2 if order_index >= 6 else 0), 1.4)))
                sorting_good = max(0, sorting_total - sorting_loss)
                records["sorting_summary"].append(
                    {
                        "sorting_wafer_ref": aliases["SORTING"],
                        "record_id": f"SORT-{wafer_index:05d}",
                        "channel": "A",
                        "process_completed_at": self._stamp(event_date + timedelta(hours=25)),
                        "record_generated_at": self._stamp(event_date + timedelta(hours=27)),
                        "total_chips": sorting_total,
                        "good_chips": sorting_good,
                        "failure_family": "Parameter Drift" if sorting_loss else "",
                    }
                )
                qualification_pass = wafer_index % 19 != 0
                records["qualification_results"].append(
                    {
                        "qualification_wafer_ref": aliases["QUALIFICATION"],
                        "record_id": f"QUAL-{wafer_index:05d}",
                        "channel": "A",
                        "qualified_at": self._stamp(event_date + timedelta(hours=26)),
                        "passed": qualification_pass,
                        "revision": 1,
                    }
                )

        # Fictional edge cases make reconciliation and revision handling observable.
        records["identity_aliases"].extend(
            [
                {
                    **records["identity_aliases"][0],
                    "source_kind": "INSPECTION",
                    "source_alias": "AMB-FX",
                    "normalized_alias": "AMB-FX",
                },
                {
                    **records["identity_aliases"][5],
                    "source_kind": "INSPECTION",
                    "source_alias": "AMB-FX",
                    "normalized_alias": "AMB-FX",
                },
            ]
        )
        records["wafer_inspection"].append(
            {
                "inspection_wafer_ref": "AMB-FX",
                "record_id": "WI-AMBIGUOUS",
                "inspection_at": self._stamp(start + timedelta(days=2)),
                "sites_inspected": 25,
                "sites_good": 10,
                "failure_family": "Surface Mark",
                "revision": 1,
            }
        )
        records["wafer_inspection"].append(
            {
                "inspection_wafer_ref": "UNKNOWN-FX",
                "record_id": "WI-UNRESOLVED",
                "inspection_at": self._stamp(start + timedelta(days=2)),
                "sites_inspected": 25,
                "sites_good": 8,
                "failure_family": "Pattern Gap",
                "revision": 1,
            }
        )
        revised = dict(records["chip_inspection_summary"][2])
        revised["record_id"] = f"{revised['record_id']}-R2"
        revised["revision"] = 2
        revised["good_chips"] = min(revised["total_chips"], revised["good_chips"] + 2)
        records["chip_inspection_summary"].append(revised)
        return {name: pd.DataFrame(rows) for name, rows in records.items()}


class SqlServerManufacturingSource:
    """Optional clean-room SQL Server adapter showing the real access pattern.

    The query text uses fictional public-demo names.  It is intentionally not
    used by the runnable portfolio and contains no production connection data.
    """

    COMMON_QUERY = """
        SELECT SourceWaferRef, WorkOrderRef, EventTime, ResultCode
        FROM demo.ManufacturingEvent
        WHERE EventTime >= ? AND EventTime < ?
    """
    TARGETED_QUERY = """
        SELECT SourceWaferRef, UnitNumber, ParameterCode, MeasuredValue
        FROM demo.SortingParameterResult
        WHERE WorkOrderRef = ? AND SourceWaferRef IN ({placeholders})
    """

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string

    def _connect(self) -> Any:
        try:
            import pyodbc
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError("Install the 'sqlserver' extra to use SQL Server") from exc
        return pyodbc.connect(self.connection_string, timeout=15)

    def read_parameterized(self, sql: str, params: Sequence[Any]) -> pd.DataFrame:
        with self._connect() as connection:
            return pd.read_sql(sql, connection, params=list(params))

    def extract_common(self) -> dict[str, pd.DataFrame]:  # pragma: no cover
        raise NotImplementedError(
            "Map each fictional source query to the common DataFrame contract for a deployment."
        )

    def extract_targeted(
        self, dataset: str, physical_wafer_ids: Sequence[str]
    ) -> pd.DataFrame:  # pragma: no cover
        raise NotImplementedError(
            "Resolve the scoped physical-wafer population to source keys before querying."
        )

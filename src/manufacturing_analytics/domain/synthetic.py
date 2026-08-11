"""Reproducible, fictional semiconductor manufacturing data generation."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class GenerationConfig:
    seed: int = 20260811
    work_order_count: int = 4
    lots_per_work_order: int = 3
    wafers_per_lot: int = 5

    def validate(self) -> None:
        for name in ("work_order_count", "lots_per_work_order", "wafers_per_lot"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")


class SyntheticDataGenerator:
    """Build a coherent fictional dataset without external source data."""

    OPERATION_SPECS = (
        ("OP-100", "Incoming Clean", "CLEAN"),
        ("OP-200", "Thin Film Deposition", "DEPOSITION"),
        ("OP-300", "Photolithography", "LITHOGRAPHY"),
        ("OP-400", "Plasma Etch", "ETCH"),
        ("OP-500", "Metrology Inspection", "METROLOGY"),
        ("OP-600", "Electrical Wafer Test", "TEST"),
    )
    DEFECT_SPECS = (
        ("PARTICLE", "Particle", "Foreign-material signature"),
        ("SCRATCH", "Scratch", "Linear handling signature"),
        ("BRIDGE", "Bridge", "Adjacent-feature connection"),
        ("OPEN", "Open", "Incomplete feature connection"),
        ("EDGE", "Edge Exclusion", "Wafer-edge process signature"),
    )
    CHARACTERISTIC_SPECS = (
        (
            "FILM_UNIFORMITY",
            "OP-200",
            "Fictional Film Uniformity",
            "synthetic units",
            100.0,
            94.0,
            106.0,
        ),
        ("LINE_WIDTH", "OP-300", "Fictional Line Width", "synthetic units", 50.0, 45.0, 55.0),
        ("ETCH_DEPTH", "OP-400", "Fictional Etch Depth", "synthetic units", 80.0, 74.0, 88.0),
    )

    def __init__(self, config: GenerationConfig) -> None:
        config.validate()
        self.config = config
        self.random = random.Random(config.seed)

    def generate(self) -> dict[str, list[dict[str, Any]]]:
        """Return table-shaped records with deterministic keys and relationships."""
        data: dict[str, list[dict[str, Any]]] = {
            name: []
            for name in (
                "work_orders",
                "lots",
                "wafers",
                "operations",
                "tools",
                "wafer_operations",
                "defect_categories",
                "inspections",
                "inspection_defects",
                "yield_results",
                "die_results",
                "measurement_characteristics",
                "process_measurements",
                "data_quality_issues",
                "source_watermarks",
            )
        }
        self._add_reference_data(data)
        start = datetime(2026, 1, 5, 6, tzinfo=UTC)
        wafer_id = 1
        event_id = 1
        inspection_id = 1
        yield_id = 1
        measurement_id = 1

        for work_order_index in range(1, self.config.work_order_count + 1):
            work_order_id = f"WO-{work_order_index:04d}"
            data["work_orders"].append(
                {
                    "work_order_id": work_order_id,
                    "product_code": f"SYN-{(work_order_index - 1) % 2 + 1}00",
                    "planned_quantity": self.config.lots_per_work_order
                    * self.config.wafers_per_lot,
                    "priority": ("STANDARD", "EXPEDITE")[work_order_index % 4 == 0],
                    "release_timestamp": self._iso(start + timedelta(days=work_order_index * 3)),
                    "status": "COMPLETE",
                }
            )
            for lot_index in range(1, self.config.lots_per_work_order + 1):
                lot_id = f"LOT-{work_order_index:02d}{lot_index:02d}"
                lot_start = start + timedelta(days=work_order_index * 3 + lot_index)
                lot_shift = self.random.gauss(0, 0.012)
                data["lots"].append(
                    {
                        "lot_id": lot_id,
                        "work_order_id": work_order_id,
                        "route_code": "SYNTHETIC-6-STEP",
                        "start_timestamp": self._iso(lot_start),
                        "completion_timestamp": self._iso(lot_start + timedelta(hours=34)),
                        "status": "COMPLETE",
                    }
                )
                for wafer_number in range(1, self.config.wafers_per_lot + 1):
                    wafer_key = f"WFR-{wafer_id:05d}"
                    data["wafers"].append(
                        {
                            "wafer_id": wafer_key,
                            "lot_id": lot_id,
                            "wafer_number": wafer_number,
                            "diameter_mm": 300,
                            "status": "COMPLETE",
                        }
                    )
                    wafer_noise = self.random.gauss(0, 0.008)
                    process_tool_effect = 0.0
                    for sequence, operation in enumerate(self.OPERATION_SPECS, start=1):
                        operation_code, _, tool_group = operation
                        tool_number = self.random.randint(1, 2)
                        tool_id = f"{tool_group[:4]}-{tool_number:02d}"
                        if tool_id == "ETCH-02":
                            process_tool_effect -= 0.018
                        event_start = lot_start + timedelta(
                            hours=sequence * 5, minutes=wafer_number * 3
                        )
                        if wafer_id == 29 and operation_code == "OP-400":
                            event_start -= timedelta(hours=6)
                        if wafer_id == 19 and operation_code == "OP-300":
                            continue
                        data["wafer_operations"].append(
                            {
                                "wafer_operation_id": event_id,
                                "wafer_id": wafer_key,
                                "operation_code": operation_code,
                                "tool_id": tool_id,
                                "sequence_number": sequence,
                                "start_timestamp": self._iso(event_start),
                                "end_timestamp": self._iso(event_start + timedelta(minutes=42)),
                                "result": "PASS",
                            }
                        )
                        event_id += 1

                        characteristic = self._characteristic_for_operation(operation_code)
                        if characteristic and not (
                            wafer_id == 17 and characteristic[0] == "LINE_WIDTH"
                        ):
                            measured_timestamp = event_start + timedelta(minutes=44)
                            arrival_delay = (
                                timedelta(hours=5) if wafer_id % 29 == 0 else timedelta(minutes=5)
                            )
                            data["process_measurements"].append(
                                {
                                    "measurement_id": measurement_id,
                                    "wafer_id": wafer_key,
                                    "operation_code": operation_code,
                                    "tool_id": tool_id,
                                    "characteristic_id": characteristic[0],
                                    "measured_timestamp": self._iso(measured_timestamp),
                                    "source_arrival_timestamp": self._iso(
                                        measured_timestamp + arrival_delay
                                    ),
                                    "measured_value": self._measurement_value(
                                        characteristic[0], wafer_id, tool_id
                                    ),
                                }
                            )
                            measurement_id += 1

                        if operation_code in {"OP-500", "OP-600"}:
                            defect_total = max(0, round(self.random.gauss(5, 2)))
                            data["inspections"].append(
                                {
                                    "inspection_id": inspection_id,
                                    "wafer_id": wafer_key,
                                    "operation_code": operation_code,
                                    "tool_id": tool_id,
                                    "inspection_timestamp": self._iso(
                                        event_start + timedelta(minutes=45)
                                    ),
                                    "sites_inspected": 317,
                                    "defect_count": defect_total,
                                }
                            )
                            self._allocate_defects(data, inspection_id, defect_total)
                            inspection_id += 1

                    target_yield = min(
                        0.995,
                        max(0.72, 0.965 + lot_shift + wafer_noise + process_tool_effect),
                    )
                    pattern = self._pattern_for_wafer(wafer_id)
                    die_rows = self._generate_die_results(
                        wafer_id=wafer_key,
                        yield_result_id=yield_id,
                        target_yield=target_yield,
                        pattern=pattern,
                    )
                    total_die = len(die_rows)
                    good_die = sum(row["passed"] for row in die_rows)
                    data["yield_results"].append(
                        {
                            "yield_result_id": yield_id,
                            "wafer_id": wafer_key,
                            "operation_code": "OP-600",
                            "measured_timestamp": self._iso(lot_start + timedelta(hours=31)),
                            "total_die": total_die,
                            "good_die": good_die,
                            "yield_rate": round(good_die / total_die, 4),
                        }
                    )
                    data["die_results"].extend(die_rows)
                    wafer_id += 1
                    yield_id += 1
        self._add_data_quality_examples(data)
        return data

    def _add_reference_data(self, data: dict[str, list[dict[str, Any]]]) -> None:
        for sequence, (code, name, tool_group) in enumerate(self.OPERATION_SPECS, start=1):
            data["operations"].append(
                {
                    "operation_code": code,
                    "operation_name": name,
                    "sequence_number": sequence,
                    "tool_group": tool_group,
                }
            )
            for tool_number in range(1, 3):
                data["tools"].append(
                    {
                        "tool_id": f"{tool_group[:4]}-{tool_number:02d}",
                        "tool_group": tool_group,
                        "display_name": f"Synthetic {tool_group.title()} Tool {tool_number}",
                        "status": "AVAILABLE",
                    }
                )
        for code, name, description in self.DEFECT_SPECS:
            data["defect_categories"].append(
                {"defect_code": code, "defect_name": name, "description": description}
            )
        for (
            characteristic_id,
            operation_code,
            name,
            unit,
            _,
            lower,
            upper,
        ) in self.CHARACTERISTIC_SPECS:
            data["measurement_characteristics"].append(
                {
                    "characteristic_id": characteristic_id,
                    "operation_code": operation_code,
                    "characteristic_name": name,
                    "unit": unit,
                    "lower_spec_limit": lower,
                    "upper_spec_limit": upper,
                }
            )

    def _characteristic_for_operation(self, operation_code: str) -> tuple[Any, ...] | None:
        return next(
            (item for item in self.CHARACTERISTIC_SPECS if item[1] == operation_code),
            None,
        )

    def _measurement_value(self, characteristic: str, wafer_number: int, tool_id: str) -> float:
        if characteristic == "FILM_UNIFORMITY":
            sigma = 1.8 if tool_id == "DEPO-02" and wafer_number >= 35 else 0.65
            value = 100.0 + (0.55 if tool_id == "DEPO-02" else 0.0) + self.random.gauss(0, sigma)
        elif characteristic == "LINE_WIDTH":
            shift = 1.5 if 25 <= wafer_number <= 40 else 0.0
            value = 50.0 + shift + self.random.gauss(0, 0.45)
            if wafer_number == 47:
                value += 5.2
        else:
            drift = max(0, wafer_number - 25) * 0.10 if tool_id == "ETCH-02" else 0.0
            offset = 1.15 if tool_id == "ETCH-02" else 0.0
            value = 80.0 + offset + drift + self.random.gauss(0, 0.32)
            if wafer_number == 52:
                value += 4.8
        return round(value, 4)

    def _add_data_quality_examples(self, data: dict[str, list[dict[str, Any]]]) -> None:
        detected = "2026-02-01T12:00:00+00:00"
        examples = (
            (
                "MISSING_PROCESS_EVENT",
                "HIGH",
                "WAFER",
                "WFR-00019",
                "Expected route event OP-300 is absent.",
            ),
            (
                "DUPLICATE_SOURCE_EVENT",
                "MEDIUM",
                "WAFER",
                "WFR-00023",
                "A repeated fictional source event key was quarantined.",
            ),
            (
                "IMPOSSIBLE_SEQUENCE",
                "HIGH",
                "WAFER",
                "WFR-00029",
                "OP-400 timestamp precedes completion of OP-300.",
            ),
            (
                "MISSING_MEASUREMENT",
                "MEDIUM",
                "WAFER",
                "WFR-00017",
                "Expected LINE_WIDTH result is absent.",
            ),
            (
                "DELAYED_EVENT",
                "LOW",
                "WAFER",
                "WFR-00029",
                "Measurement arrived five hours after acquisition.",
            ),
            (
                "STALE_SOURCE",
                "HIGH",
                "SOURCE",
                "SYNTHETIC_INSPECTION_FEED",
                "Watermark exceeds its fictional freshness objective.",
            ),
        )
        for issue_id, (issue_type, severity, entity_type, entity_id, evidence) in enumerate(
            examples, start=1
        ):
            data["data_quality_issues"].append(
                {
                    "issue_id": issue_id,
                    "issue_type": issue_type,
                    "severity": severity,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "detected_timestamp": detected,
                    "evidence": evidence,
                }
            )
        data["source_watermarks"].extend(
            (
                {
                    "source_name": "SYNTHETIC_EVENT_FEED",
                    "watermark_timestamp": "2026-02-01T11:56:00+00:00",
                    "observed_timestamp": detected,
                    "expected_max_lag_minutes": 15,
                    "row_count": len(data["wafer_operations"]),
                },
                {
                    "source_name": "SYNTHETIC_MEASUREMENT_FEED",
                    "watermark_timestamp": "2026-02-01T11:52:00+00:00",
                    "observed_timestamp": detected,
                    "expected_max_lag_minutes": 20,
                    "row_count": len(data["process_measurements"]),
                },
                {
                    "source_name": "SYNTHETIC_INSPECTION_FEED",
                    "watermark_timestamp": "2026-01-31T08:00:00+00:00",
                    "observed_timestamp": detected,
                    "expected_max_lag_minutes": 60,
                    "row_count": len(data["inspections"]),
                },
            )
        )

    def _allocate_defects(
        self, data: dict[str, list[dict[str, Any]]], inspection_id: int, total: int
    ) -> None:
        counts = {code: 0 for code, _, _ in self.DEFECT_SPECS}
        weights = (0.36, 0.18, 0.16, 0.18, 0.12)
        for _ in range(total):
            code = self.random.choices(list(counts), weights=weights, k=1)[0]
            counts[code] += 1
        for code, count in counts.items():
            if count:
                data["inspection_defects"].append(
                    {"inspection_id": inspection_id, "defect_code": code, "defect_count": count}
                )

    @staticmethod
    def _pattern_for_wafer(wafer_number: int) -> str:
        if wafer_number % 13 == 0:
            return "LOCAL_CLUSTER"
        if wafer_number % 11 == 0:
            return "EDGE_DEGRADATION"
        if wafer_number % 7 == 0:
            return "RANDOM_LOSS"
        return "UNIFORM"

    def _generate_die_results(
        self,
        wafer_id: str,
        yield_result_id: int,
        target_yield: float,
        pattern: str,
    ) -> list[dict[str, Any]]:
        """Generate a circular 21x21 map with deterministic fictional spatial effects."""
        coordinates = [
            (x, y) for y in range(-10, 11) for x in range(-10, 11) if x * x + y * y <= 100
        ]
        cluster_x = self.random.randint(-5, 5)
        cluster_y = self.random.randint(-5, 5)
        rows: list[dict[str, Any]] = []
        for x, y in coordinates:
            radius = math.sqrt(x * x + y * y) / 10
            failure_probability = 1 - target_yield
            failure_bin = "BIN_2_RANDOM"

            if pattern == "EDGE_DEGRADATION" and radius >= 0.72:
                failure_probability = min(0.72, failure_probability + 0.34)
                failure_bin = "BIN_3_EDGE"
            elif pattern == "LOCAL_CLUSTER" and (x - cluster_x) ** 2 + (y - cluster_y) ** 2 <= 10:
                failure_probability = min(0.82, failure_probability + 0.52)
                failure_bin = "BIN_4_CLUSTER"
            elif pattern == "RANDOM_LOSS":
                failure_probability = min(0.35, failure_probability + 0.07)

            passed = int(self.random.random() >= failure_probability)
            rows.append(
                {
                    "die_result_id": len(rows) + 1 + (yield_result_id - 1) * len(coordinates),
                    "wafer_id": wafer_id,
                    "yield_result_id": yield_result_id,
                    "x_coordinate": x,
                    "y_coordinate": y,
                    "passed": passed,
                    "test_bin": "BIN_1_PASS" if passed else failure_bin,
                    "test_category": "SYNTHETIC_ELECTRICAL_TEST",
                }
            )
        return rows

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.isoformat(timespec="seconds")


def expected_wafer_count(config: GenerationConfig) -> int:
    """Make record-count expectations explicit for tests and operational checks."""
    return math.prod((config.work_order_count, config.lots_per_work_order, config.wafers_per_lot))

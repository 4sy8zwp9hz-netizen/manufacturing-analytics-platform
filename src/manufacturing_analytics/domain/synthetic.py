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
            )
        }
        self._add_reference_data(data)
        start = datetime(2026, 1, 5, 6, tzinfo=UTC)
        wafer_id = 1
        event_id = 1
        inspection_id = 1
        yield_id = 1

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

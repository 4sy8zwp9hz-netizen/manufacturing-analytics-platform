"""SPC, operational-flow, and data-quality orchestration."""

from __future__ import annotations

from dataclasses import asdict
from itertools import groupby
from statistics import fmean
from typing import Any

from manufacturing_analytics.analytics.models import AnalyticsFilters
from manufacturing_analytics.analytics.service import AnalyticsService
from manufacturing_analytics.data.process_repository import ProcessRepository
from manufacturing_analytics.domain.data_quality import freshness
from manufacturing_analytics.domain.operations import elapsed_minutes, summarize_durations
from manufacturing_analytics.domain.spc import (
    evaluate_control_rules,
    individuals_limits,
    moving_ranges,
    validate_rational_subgroup,
)


class ProcessAnalyticsService(AnalyticsService):
    def __init__(self, repository: ProcessRepository) -> None:
        self.process_repository = repository
        self.timings = []

    def process_monitor(
        self,
        characteristic_id: str,
        filters: AnalyticsFilters,
        subgroup_method: str = "INDIVIDUALS",
    ) -> dict[str, Any]:
        validate_rational_subgroup(subgroup_method)
        records = self._timed(
            "process_measurements",
            lambda: self.process_repository.measurements(characteristic_id, filters),
        )
        if len(records) < 2:
            return {"records": records, "limits": None, "violations": [], "strata": []}
        values = [float(record["measured_value"]) for record in records]
        limits = individuals_limits(values)
        violations = self._enrich_violations(records, evaluate_control_rules(records, limits))
        strata = []
        by_tool: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            by_tool.setdefault(str(record["tool_id"]), []).append(record)
        for tool_id, tool_records in by_tool.items():
            tool_values = [float(row["measured_value"]) for row in tool_records]
            tool_limits = individuals_limits(tool_values) if len(tool_values) >= 2 else None
            tool_violations = (
                evaluate_control_rules(tool_records, tool_limits) if tool_limits else []
            )
            strata.append(
                {
                    "tool_id": tool_id,
                    "count": len(tool_records),
                    "mean": round(fmean(tool_values), 3),
                    "rule_violations": len(tool_violations),
                }
            )
        return {
            "records": records,
            "moving_ranges": moving_ranges(values),
            "limits": asdict(limits),
            "violations": violations,
            "strata": sorted(strata, key=lambda row: row["tool_id"]),
            "specification": {
                "lower": records[0]["lower_spec_limit"],
                "upper": records[0]["upper_spec_limit"],
                "unit": records[0]["unit"],
                "name": records[0]["characteristic_name"],
            },
        }

    @staticmethod
    def _enrich_violations(
        records: list[dict[str, Any]], violations: list[Any]
    ) -> list[dict[str, Any]]:
        output = []
        for violation in violations:
            point = records[violation.point_index]
            output.append(
                {
                    **asdict(violation),
                    "wafer_id": point["wafer_id"],
                    "tool_id": point["tool_id"],
                    "measured_timestamp": point["measured_timestamp"],
                    "measured_value": point["measured_value"],
                }
            )
        return output

    def operations_flow(self, filters: AnalyticsFilters) -> dict[str, Any]:
        events = self._timed(
            "operation_flow_events", lambda: self.process_repository.operation_events(filters)
        )
        by_operation: dict[tuple[str, str], list[float]] = {}
        queue_by_operation: dict[str, list[float]] = {}
        route_by_wafer: list[dict[str, Any]] = []
        for wafer_id, iterator in groupby(events, key=lambda row: row["wafer_id"]):
            wafer_events = list(iterator)
            for event in wafer_events:
                key = (event["operation_code"], event["operation_name"])
                by_operation.setdefault(key, []).append(float(event["cycle_minutes"]))
            for previous, current in zip(wafer_events, wafer_events[1:], strict=False):
                queue = elapsed_minutes(previous["end_timestamp"], current["start_timestamp"])
                queue_by_operation.setdefault(current["operation_code"], []).append(queue)
            if wafer_events:
                route_by_wafer.append(
                    {
                        "wafer_id": wafer_id,
                        "lot_id": wafer_events[0]["lot_id"],
                        "product_code": wafer_events[0]["product_code"],
                        "route_hours": round(
                            elapsed_minutes(
                                wafer_events[0]["start_timestamp"],
                                wafer_events[-1]["end_timestamp"],
                            )
                            / 60,
                            2,
                        ),
                        "event_count": len(wafer_events),
                    }
                )
        operation_summary = []
        for (code, name), durations in by_operation.items():
            operation_summary.append(
                {
                    "operation_code": code,
                    "operation_name": name,
                    **summarize_durations(durations),
                    "average_queue_minutes": summarize_durations(queue_by_operation.get(code, []))[
                        "average"
                    ],
                    "event_count": len(durations),
                }
            )
        throughput = self._timed(
            "operation_throughput", lambda: self.process_repository.throughput(filters)
        )
        throughput_by_tool: dict[tuple[str, str], int] = {}
        for row in throughput:
            key = (str(row["operation_code"]), str(row["tool_id"]))
            throughput_by_tool[key] = throughput_by_tool.get(key, 0) + int(row["completed_wafers"])
        return {
            "operations": operation_summary,
            "routes": sorted(route_by_wafer, key=lambda row: -row["route_hours"]),
            "throughput": throughput,
            "throughput_by_tool": [
                {"operation_code": key[0], "tool_id": key[1], "completed_wafers": count}
                for key, count in sorted(throughput_by_tool.items())
            ],
            "event_count": len(events),
            "wafer_count": len(route_by_wafer),
            "route_summary": summarize_durations(
                [float(row["route_hours"]) for row in route_by_wafer]
            ),
        }

    def data_quality(self) -> dict[str, Any]:
        issues = self._timed("data_quality_issues", self.process_repository.quality_issues)
        watermarks = self._timed("source_watermarks", self.process_repository.watermarks)
        enriched = []
        for watermark in watermarks:
            state = freshness(
                watermark["watermark_timestamp"],
                watermark["observed_timestamp"],
                watermark["expected_max_lag_minutes"],
            )
            enriched.append({**watermark, **state})
        return {
            "issues": issues,
            "watermarks": enriched,
            "open_count": len(issues),
            "high_count": sum(issue["severity"] == "HIGH" for issue in issues),
            "stale_count": sum(source["status"] == "STALE" for source in enriched),
        }

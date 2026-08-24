"""Pandas transformations that turn source-shaped records into engineering populations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Resolution:
    status: str
    physical_wafer_id: str | None
    method: str


class PhysicalWaferResolver:
    """Resolve exact and normalized source aliases while rejecting ambiguity."""

    def __init__(self, aliases: pd.DataFrame) -> None:
        self._exact = self._index(aliases, "source_alias")
        self._normalized = self._index(aliases, "normalized_alias")

    @staticmethod
    def normalize(value: Any) -> str:
        return str(value or "").strip().replace(" ", "").replace("_", "-").upper()

    @staticmethod
    def _index(frame: pd.DataFrame, column: str) -> dict[tuple[str, str], set[str]]:
        index: dict[tuple[str, str], set[str]] = {}
        for row in frame.to_dict("records"):
            key = (str(row["source_kind"]), str(row[column]))
            index.setdefault(key, set()).add(str(row["physical_wafer_id"]))
        return index

    def resolve(self, source_kind: str, source_alias: Any) -> Resolution:
        alias = str(source_alias or "").strip()
        exact = self._exact.get((source_kind, alias), set())
        if len(exact) == 1:
            return Resolution("RESOLVED", next(iter(exact)), "exact alias")
        if len(exact) > 1:
            return Resolution("AMBIGUOUS", None, "exact alias")
        normalized = self._normalized.get((source_kind, self.normalize(alias)), set())
        if len(normalized) == 1:
            return Resolution("RESOLVED", next(iter(normalized)), "normalized alias")
        if len(normalized) > 1:
            return Resolution("AMBIGUOUS", None, "normalized alias")
        return Resolution("UNRESOLVED", None, "no alias match")


@dataclass(frozen=True)
class PreparedData:
    datasets: dict[str, pd.DataFrame]
    statistics: dict[str, Any]


class YieldTransformer:
    """Build traceable, source-aware yield facts from heterogeneous raw frames."""

    def __init__(self, rules: dict[str, Any]) -> None:
        self.rules = rules
        self.row_config = {row["stage_code"]: row for row in rules.get("display_rows", [])}

    def transform(self, raw: dict[str, pd.DataFrame]) -> PreparedData:
        aliases = raw["identity_aliases"].copy()
        resolver = PhysicalWaferResolver(aliases)
        wafer_master = (
            aliases.sort_values(["physical_wafer_id", "source_kind"])
            .drop_duplicates("physical_wafer_id")[
                [
                    "physical_wafer_id",
                    "work_order",
                    "lot_id",
                    "wafer_number",
                    "product_family",
                    "wafer_size",
                ]
            ]
            .reset_index(drop=True)
        )
        master = wafer_master.set_index("physical_wafer_id").to_dict("index")
        facts: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        lineage: list[dict[str, Any]] = []
        identity_audit: list[dict[str, Any]] = []

        def resolved_rows(
            frame: pd.DataFrame, source_kind: str, alias_column: str, record_column: str
        ) -> pd.DataFrame:
            work = frame.copy()
            resolutions = [resolver.resolve(source_kind, value) for value in work[alias_column]]
            work["identity_status"] = [item.status for item in resolutions]
            work["physical_wafer_id"] = [item.physical_wafer_id for item in resolutions]
            work["identity_method"] = [item.method for item in resolutions]
            for row in work.to_dict("records"):
                identity_audit.append(
                    {
                        "source_kind": source_kind,
                        "source_record_id": str(row[record_column]),
                        "source_alias": str(row[alias_column]),
                        "identity_status": row["identity_status"],
                        "physical_wafer_id": row["physical_wafer_id"],
                        "identity_method": row["identity_method"],
                    }
                )
            return work.loc[work["identity_status"].eq("RESOLVED")].copy()

        def add_fact(
            *,
            stage_code: str,
            physical_wafer_id: str,
            event_time: Any,
            numerator: float,
            denominator: float,
            failure_family: str,
            source_kind: str,
            source_record_id: str,
            rule: str,
            identity_method: str,
        ) -> None:
            if physical_wafer_id not in master or denominator <= 0:
                return
            config = self.row_config[stage_code]
            metadata = master[physical_wafer_id]
            record_id = f"YF-{len(facts) + 1:07d}"
            fact = {
                "yield_record_id": record_id,
                "section": config["section"],
                "stage_code": stage_code,
                "stage_label": config["label"],
                "display_order": int(config["order"]),
                "physical_wafer_id": physical_wafer_id,
                **metadata,
                "event_time": pd.Timestamp(event_time),
                "numerator": float(numerator),
                "denominator": float(denominator),
                "yield_rate": float(numerator) / float(denominator),
                "failure_family": str(failure_family or ""),
            }
            facts.append(fact)
            loss = max(0.0, float(denominator) - float(numerator))
            if loss:
                failures.append(
                    {
                        "yield_record_id": record_id,
                        "stage_code": stage_code,
                        "stage_label": config["label"],
                        "physical_wafer_id": physical_wafer_id,
                        "work_order": metadata["work_order"],
                        "product_family": metadata["product_family"],
                        "event_time": pd.Timestamp(event_time),
                        "failure_family": str(failure_family or "Unclassified Loss"),
                        "failure_quantity": loss,
                    }
                )
            lineage.append(
                {
                    "yield_record_id": record_id,
                    "source_kind": source_kind,
                    "source_record_id": source_record_id,
                    "identity_method": identity_method,
                    "transformation_rule": rule,
                }
            )

        inspection = resolved_rows(
            raw["wafer_inspection"], "INSPECTION", "inspection_wafer_ref", "record_id"
        )
        inspection = inspection.sort_values("revision").drop_duplicates(
            "inspection_wafer_ref", keep="last"
        )
        for row in inspection.to_dict("records"):
            add_fact(
                stage_code="WAFER_INSPECTION",
                physical_wafer_id=row["physical_wafer_id"],
                event_time=row["inspection_at"],
                numerator=row["sites_good"],
                denominator=row["sites_inspected"],
                failure_family=row["failure_family"],
                source_kind="INSPECTION",
                source_record_id=row["record_id"],
                rule="Latest inspection revision; site-weighted yield.",
                identity_method=row["identity_method"],
            )

        process = resolved_rows(raw["process_results"], "MES", "mes_wafer_ref", "record_id")
        process_by_wafer: dict[str, dict[str, dict[str, Any]]] = {}
        for row in process.to_dict("records"):
            stage = str(row["stage_code"])
            physical = str(row["physical_wafer_id"])
            process_by_wafer.setdefault(physical, {})[stage] = row
            if stage in self.row_config and stage != "DEVICE_FORMATION":
                add_fact(
                    stage_code=stage,
                    physical_wafer_id=physical,
                    event_time=row["completed_at"],
                    numerator=float(bool(row["passed"])),
                    denominator=1,
                    failure_family=row["failure_family"],
                    source_kind="MES",
                    source_record_id=row["record_id"],
                    rule="Completed process record classified at physical-wafer grain.",
                    identity_method=row["identity_method"],
                )

        chip = resolved_rows(raw["chip_inspection_summary"], "CHIP", "chip_wafer_ref", "record_id")
        chip = chip.sort_values("revision").drop_duplicates("chip_wafer_ref", keep="last")
        chip_by_wafer: dict[str, dict[str, Any]] = {}
        for row in chip.to_dict("records"):
            physical = str(row["physical_wafer_id"])
            chip_by_wafer[physical] = row
            add_fact(
                stage_code="CHIP_INSPECTION",
                physical_wafer_id=physical,
                event_time=row["tested_at"],
                numerator=row["good_chips"],
                denominator=row["total_chips"],
                failure_family=row["dominant_failure"],
                source_kind="CHIP",
                source_record_id=row["record_id"],
                rule="Latest chip-inspection revision; quantity-weighted chip population.",
                identity_method=row["identity_method"],
            )
            outlier_loss = 1 if int(physical.rsplit("-", 1)[-1]) % 11 == 0 else 0
            add_fact(
                stage_code="AUTO_OUTLIER",
                physical_wafer_id=physical,
                event_time=row["tested_at"],
                numerator=row["total_chips"] - outlier_loss,
                denominator=row["total_chips"],
                failure_family="Automated Rule Flag" if outlier_loss else "",
                source_kind="CHIP",
                source_record_id=row["record_id"],
                rule="Fictional automated rule applied to the prepared chip population.",
                identity_method=row["identity_method"],
            )

        sorting = resolved_rows(raw["sorting_summary"], "SORTING", "sorting_wafer_ref", "record_id")
        sorting_by_wafer: dict[str, dict[str, Any]] = {}
        for row in sorting.to_dict("records"):
            physical = str(row["physical_wafer_id"])
            sorting_by_wafer[physical] = row
            add_fact(
                stage_code="SORTING",
                physical_wafer_id=physical,
                event_time=row["process_completed_at"],
                numerator=row["good_chips"],
                denominator=row["total_chips"],
                failure_family=row["failure_family"],
                source_kind="SORTING",
                source_record_id=row["record_id"],
                rule="Use process completion date, not later source-generation timestamp.",
                identity_method=row["identity_method"],
            )

        qualification = resolved_rows(
            raw["qualification_results"],
            "QUALIFICATION",
            "qualification_wafer_ref",
            "record_id",
        )
        qualification = qualification.sort_values("revision").drop_duplicates(
            ["qualification_wafer_ref", "channel"], keep="last"
        )
        qualification_by_wafer: dict[str, dict[str, Any]] = {}
        for row in qualification.to_dict("records"):
            physical = str(row["physical_wafer_id"])
            qualification_by_wafer[physical] = row
            add_fact(
                stage_code="QUALIFICATION",
                physical_wafer_id=physical,
                event_time=row["qualified_at"],
                numerator=float(bool(row["passed"])),
                denominator=1,
                failure_family="Qualification Hold" if not row["passed"] else "",
                source_kind="QUALIFICATION",
                source_record_id=row["record_id"],
                rule="Qualification defines the physical-wafer final-yield cohort.",
                identity_method=row["identity_method"],
            )

        # Wafer total uses the same physical-wafer population and requires every wafer stage.
        wafer_stage_codes = {
            "WAFER_INSPECTION",
            "SURFACE_PREPARATION",
            "PATTERN_SEPARATION",
            "PROTECTIVE_FINISH",
        }
        fact_frame = pd.DataFrame(facts)
        for physical, group in fact_frame.loc[
            fact_frame["stage_code"].isin(wafer_stage_codes)
        ].groupby("physical_wafer_id"):
            if set(group["stage_code"]) != wafer_stage_codes:
                continue
            yield_value = float(group["yield_rate"].prod())
            add_fact(
                stage_code="WAFER_TOTAL",
                physical_wafer_id=str(physical),
                event_time=group["event_time"].max(),
                numerator=yield_value,
                denominator=1,
                failure_family="Combined Wafer Loss" if yield_value < 1 else "",
                source_kind="PREPARED",
                source_record_id=f"WAFER-TOTAL-{physical}",
                rule="Product of complete wafer-stage component yields.",
                identity_method="physical-wafer cohort",
            )

        # Device Formation is a chip-quantity interpretation of the process result.
        for physical, stages in process_by_wafer.items():
            formation = stages.get("DEVICE_FORMATION")
            chip_row = chip_by_wafer.get(physical)
            if formation is None or chip_row is None:
                continue
            total = float(chip_row["total_chips"])
            good = total if formation["passed"] else max(0.0, total - 9)
            add_fact(
                stage_code="DEVICE_FORMATION",
                physical_wafer_id=physical,
                event_time=formation["completed_at"],
                numerator=good,
                denominator=total,
                failure_family=formation["failure_family"],
                source_kind="MES",
                source_record_id=formation["record_id"],
                rule="Process completion classified against the chip population.",
                identity_method=formation["identity_method"],
            )

        # Establish the qualification cohort first, then require every component on that wafer.
        final_component_rows: list[dict[str, Any]] = []
        for physical, qual_row in qualification_by_wafer.items():
            chip_row = chip_by_wafer.get(physical)
            sorting_row = sorting_by_wafer.get(physical)
            formation = process_by_wafer.get(physical, {}).get("DEVICE_FORMATION")
            if chip_row is None or sorting_row is None or formation is None:
                continue
            total = float(chip_row["total_chips"])
            component_yields = {
                "chip_inspection": float(chip_row["good_chips"]) / total,
                "device_formation": 1.0 if formation["passed"] else (total - 9) / total,
                "sorting": float(sorting_row["good_chips"]) / float(sorting_row["total_chips"]),
                "qualification": float(bool(qual_row["passed"])),
            }
            final_yield = 1.0
            for value in component_yields.values():
                final_yield *= value
            final_good = round(total * final_yield)
            add_fact(
                stage_code="FINAL_CHIP_YIELD",
                physical_wafer_id=physical,
                event_time=qual_row["qualified_at"],
                numerator=final_good,
                denominator=total,
                failure_family="Final Component Loss" if final_good < total else "",
                source_kind="PREPARED",
                source_record_id=f"FINAL-{physical}",
                rule=(
                    "Qualification-cohort component product with complete physical-wafer "
                    "membership and quantity-weighted aggregation."
                ),
                identity_method="resolved physical-wafer cohort",
            )
            final_component_rows.append(
                {
                    "physical_wafer_id": physical,
                    "work_order": master[physical]["work_order"],
                    "product_family": master[physical]["product_family"],
                    "event_time": pd.Timestamp(qual_row["qualified_at"]),
                    "total_chips": total,
                    **component_yields,
                    "final_chip_yield": final_good / total,
                }
            )

        fact_frame = pd.DataFrame(facts).sort_values(
            ["display_order", "event_time", "physical_wafer_id"]
        )
        failure_frame = pd.DataFrame(failures)
        lineage_frame = pd.DataFrame(lineage)
        identity_frame = pd.DataFrame(identity_audit)
        components = pd.DataFrame(final_component_rows)
        wafer_summary = self._wafer_summary(wafer_master, fact_frame)
        prebuilt_trend = self._prebuilt_trend(fact_frame)
        prebuilt_pareto = self._prebuilt_pareto(failure_frame)
        filter_domains = pd.DataFrame(
            {
                "domain": ["product_family", "wafer_size"],
                "values_json": [
                    wafer_master["product_family"]
                    .drop_duplicates()
                    .sort_values()
                    .to_json(orient="values"),
                    wafer_master["wafer_size"]
                    .drop_duplicates()
                    .sort_values()
                    .to_json(orient="values"),
                ],
            }
        )
        datasets = {
            "yield_fact": fact_frame.reset_index(drop=True),
            "failure_fact": failure_frame.reset_index(drop=True),
            "wafer_summary": wafer_summary,
            "final_component_fact": components,
            "lineage": lineage_frame,
            "identity_audit": identity_frame,
            "filter_domains": filter_domains,
            "prebuilt_trend": prebuilt_trend,
            "prebuilt_pareto": prebuilt_pareto,
        }
        statistics = {
            "physical_wafers": int(wafer_master["physical_wafer_id"].nunique()),
            "yield_rows": int(len(fact_frame)),
            "final_cohort_wafers": int(len(components)),
            "ambiguous_records": int(identity_frame["identity_status"].eq("AMBIGUOUS").sum()),
            "unresolved_records": int(identity_frame["identity_status"].eq("UNRESOLVED").sum()),
        }
        return PreparedData(datasets=datasets, statistics=statistics)

    def transform_targeted(
        self, frame: pd.DataFrame, aliases: pd.DataFrame, dataset: str
    ) -> pd.DataFrame:
        resolver = PhysicalWaferResolver(aliases)
        if dataset == "chip_detail":
            source_kind, alias_column = "CHIP", "chip_wafer_ref"
        elif dataset == "sorting_parameter_detail":
            source_kind, alias_column = "SORTING", "sorting_wafer_ref"
        else:
            raise ValueError(f"Unsupported targeted dataset: {dataset}")
        work = frame.copy()
        resolutions = [resolver.resolve(source_kind, value) for value in work[alias_column]]
        work["physical_wafer_id"] = [item.physical_wafer_id for item in resolutions]
        work["identity_status"] = [item.status for item in resolutions]
        return work.loc[work["identity_status"].eq("RESOLVED")].reset_index(drop=True)

    @staticmethod
    def _wafer_summary(master: pd.DataFrame, facts: pd.DataFrame) -> pd.DataFrame:
        pivot = facts.pivot_table(
            index="physical_wafer_id",
            columns="stage_code",
            values="yield_rate",
            aggfunc="first",
        ).reset_index()
        return master.merge(pivot, on="physical_wafer_id", how="left")

    @staticmethod
    def _prebuilt_trend(facts: pd.DataFrame) -> pd.DataFrame:
        work = facts.copy()
        work["period"] = work["event_time"].dt.tz_localize(None).dt.to_period("W").astype(str)
        return (
            work.groupby(["stage_code", "stage_label", "period"], as_index=False)
            .agg(numerator=("numerator", "sum"), denominator=("denominator", "sum"))
            .assign(yield_rate=lambda frame: frame["numerator"] / frame["denominator"])
        )

    @staticmethod
    def _prebuilt_pareto(failures: pd.DataFrame) -> pd.DataFrame:
        if failures.empty:
            return pd.DataFrame(
                columns=["stage_code", "stage_label", "failure_family", "failure_quantity"]
            )
        return (
            failures.groupby(["stage_code", "stage_label", "failure_family"], as_index=False)[
                "failure_quantity"
            ]
            .sum()
            .sort_values(["stage_code", "failure_quantity"], ascending=[True, False])
        )

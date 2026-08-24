from __future__ import annotations

import pandas as pd

from manufacturing_analytics.sources import SyntheticManufacturingSource, SyntheticSourceConfig
from manufacturing_analytics.transforms import PhysicalWaferResolver, YieldTransformer


def test_identity_resolution_is_explicit_for_exact_ambiguous_and_unknown() -> None:
    source = SyntheticManufacturingSource(
        SyntheticSourceConfig(
            seed=11, work_order_count=1, wafers_per_work_order=4, chips_per_wafer=25
        )
    )
    resolver = PhysicalWaferResolver(source.extract_common()["identity_aliases"])

    assert resolver.resolve("CHIP", "SUB 700001").status == "RESOLVED"
    assert resolver.resolve("INSPECTION", "AMB-FX").status == "AMBIGUOUS"
    assert resolver.resolve("INSPECTION", "NOT-THERE").status == "UNRESOLVED"


def test_transform_builds_distinct_grains_and_traceable_populations(services) -> None:
    datasets = services.snapshots.get().datasets
    facts = datasets["yield_fact"]
    lineage = datasets["lineage"]
    audit = datasets["identity_audit"]

    assert {
        "WAFER_INSPECTION",
        "SURFACE_PREPARATION",
        "PATTERN_SEPARATION",
        "PROTECTIVE_FINISH",
        "AUTO_OUTLIER",
        "WAFER_TOTAL",
        "CHIP_INSPECTION",
        "DEVICE_FORMATION",
        "SORTING",
        "QUALIFICATION",
        "FINAL_CHIP_YIELD",
    } == set(facts["stage_code"])
    assert len(lineage) == len(facts)
    assert audit["identity_status"].eq("AMBIGUOUS").sum() == 1
    assert audit["identity_status"].eq("UNRESOLVED").sum() == 1

    wafer = facts.loc[facts["stage_code"].eq("SURFACE_PREPARATION")].iloc[0]
    chip = facts.loc[facts["stage_code"].eq("CHIP_INSPECTION")].iloc[0]
    assert wafer["denominator"] == 1
    assert chip["denominator"] == services.settings.chips_per_wafer


def test_final_chip_yield_uses_complete_qualification_cohort_and_component_product(
    services,
) -> None:
    datasets = services.snapshots.get().datasets
    components = datasets["final_component_fact"]
    facts = datasets["yield_fact"]
    final = facts.loc[facts["stage_code"].eq("FINAL_CHIP_YIELD")].set_index("physical_wafer_id")

    assert (
        len(components)
        == services.settings.work_order_count * services.settings.wafers_per_work_order
    )
    failed_qualification = components.loc[components["qualification"].eq(0)]
    assert not failed_qualification.empty
    for row in components.to_dict("records"):
        expected = (
            row["chip_inspection"] * row["device_formation"] * row["sorting"] * row["qualification"]
        )
        actual = final.loc[row["physical_wafer_id"], "yield_rate"]
        assert abs(actual - round(row["total_chips"] * expected) / row["total_chips"]) < 1e-12

    qualification_lineage = datasets["lineage"].loc[
        datasets["lineage"]["transformation_rule"].str.contains("cohort", case=False)
    ]
    assert not qualification_lineage.empty


def test_latest_revised_chip_summary_is_used() -> None:
    source = SyntheticManufacturingSource(
        SyntheticSourceConfig(
            seed=71, work_order_count=1, wafers_per_work_order=4, chips_per_wafer=25
        )
    )
    raw = source.extract_common()
    prepared = YieldTransformer(
        {
            "display_rows": [
                {"section": "Wafer", "stage_code": "WAFER_INSPECTION", "label": "WI", "order": 1},
                {
                    "section": "Wafer",
                    "stage_code": "SURFACE_PREPARATION",
                    "label": "SP",
                    "order": 2,
                },
                {"section": "Wafer", "stage_code": "PATTERN_SEPARATION", "label": "PS", "order": 3},
                {"section": "Wafer", "stage_code": "PROTECTIVE_FINISH", "label": "PF", "order": 4},
                {"section": "Wafer", "stage_code": "AUTO_OUTLIER", "label": "AO", "order": 5},
                {"section": "Wafer", "stage_code": "WAFER_TOTAL", "label": "WT", "order": 6},
                {"section": "Chip", "stage_code": "CHIP_INSPECTION", "label": "CI", "order": 7},
                {"section": "Chip", "stage_code": "DEVICE_FORMATION", "label": "DF", "order": 8},
                {"section": "Chip", "stage_code": "SORTING", "label": "S", "order": 9},
                {"section": "Chip", "stage_code": "QUALIFICATION", "label": "Q", "order": 10},
                {"section": "Chip", "stage_code": "FINAL_CHIP_YIELD", "label": "F", "order": 11},
            ]
        }
    ).transform(raw)
    revised = raw["chip_inspection_summary"].sort_values("revision").iloc[-1]
    physical = "PHY-00003"
    fact = (
        prepared.datasets["yield_fact"]
        .loc[
            prepared.datasets["yield_fact"]["stage_code"].eq("CHIP_INSPECTION")
            & prepared.datasets["yield_fact"]["physical_wafer_id"].eq(physical)
        ]
        .iloc[0]
    )
    assert fact["numerator"] == revised["good_chips"]
    assert pd.notna(fact["event_time"])

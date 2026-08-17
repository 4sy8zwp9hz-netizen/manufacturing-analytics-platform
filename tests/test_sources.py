from __future__ import annotations

from pandas.testing import assert_frame_equal

from manufacturing_analytics.sources import SyntheticManufacturingSource, SyntheticSourceConfig


def test_synthetic_source_is_reproducible_and_source_shaped() -> None:
    config = SyntheticSourceConfig(
        seed=42, work_order_count=2, wafers_per_work_order=4, chips_per_wafer=25
    )
    first = SyntheticManufacturingSource(config)
    second = SyntheticManufacturingSource(config)
    for name, frame in first.extract_common().items():
        assert_frame_equal(frame, second.extract_common()[name])

    common = first.extract_common()
    aliases = common["identity_aliases"]
    assert set(aliases["source_kind"]) == {
        "MES",
        "INSPECTION",
        "CHIP",
        "SORTING",
        "QUALIFICATION",
    }
    assert common["chip_inspection_summary"]["revision"].max() == 2
    assert "physical_wafer_id" not in common["chip_inspection_summary"]


def test_targeted_source_query_reads_only_requested_population() -> None:
    source = SyntheticManufacturingSource(
        SyntheticSourceConfig(
            seed=9, work_order_count=2, wafers_per_work_order=4, chips_per_wafer=25
        )
    )
    detail = source.extract_targeted("chip_detail", ["PHY-00002"])
    sorting = source.extract_targeted("sorting_parameter_detail", ["PHY-00002"])

    assert len(detail) == 25
    assert len(sorting) == 25 * len(source.SORTING_PARAMETERS)
    assert detail["chip_wafer_ref"].nunique() == 1
    assert source.targeted_query_count == 2

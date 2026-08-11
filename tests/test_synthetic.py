from manufacturing_analytics.domain.synthetic import (
    GenerationConfig,
    SyntheticDataGenerator,
    expected_wafer_count,
)


def test_generation_is_reproducible() -> None:
    config = GenerationConfig(seed=42, work_order_count=2, lots_per_work_order=2, wafers_per_lot=3)
    assert SyntheticDataGenerator(config).generate() == SyntheticDataGenerator(config).generate()


def test_generation_preserves_counts_and_relationships() -> None:
    config = GenerationConfig(seed=7, work_order_count=2, lots_per_work_order=3, wafers_per_lot=4)
    dataset = SyntheticDataGenerator(config).generate()

    assert len(dataset["work_orders"]) == 2
    assert len(dataset["lots"]) == 6
    assert len(dataset["wafers"]) == expected_wafer_count(config)
    assert len(dataset["yield_results"]) == len(dataset["wafers"])
    assert len(dataset["wafer_operations"]) == len(dataset["wafers"]) * 6
    assert len(dataset["die_results"]) == len(dataset["wafers"]) * 317

    wafer_ids = {row["wafer_id"] for row in dataset["wafers"]}
    assert {row["wafer_id"] for row in dataset["yield_results"]} <= wafer_ids
    assert all(0 <= row["yield_rate"] <= 1 for row in dataset["yield_results"])


def test_coordinate_results_match_wafer_yield() -> None:
    dataset = SyntheticDataGenerator(
        GenerationConfig(seed=23, work_order_count=1, lots_per_work_order=3, wafers_per_lot=5)
    ).generate()
    results_by_wafer = {row["wafer_id"]: row for row in dataset["yield_results"]}

    for wafer in dataset["wafers"]:
        dies = [row for row in dataset["die_results"] if row["wafer_id"] == wafer["wafer_id"]]
        coordinates = {(row["x_coordinate"], row["y_coordinate"]) for row in dies}
        yield_result = results_by_wafer[wafer["wafer_id"]]

        assert len(dies) == len(coordinates) == 317
        assert all(x * x + y * y <= 100 for x, y in coordinates)
        assert sum(row["passed"] for row in dies) == yield_result["good_die"]
        assert all(row["yield_result_id"] == yield_result["yield_result_id"] for row in dies)


def test_edge_pattern_is_spatially_discoverable() -> None:
    dataset = SyntheticDataGenerator(
        GenerationConfig(seed=23, work_order_count=1, lots_per_work_order=3, wafers_per_lot=5)
    ).generate()
    dies = [row for row in dataset["die_results"] if row["wafer_id"] == "WFR-00011"]
    edge = [row for row in dies if row["x_coordinate"] ** 2 + row["y_coordinate"] ** 2 >= 64]
    center = [row for row in dies if row["x_coordinate"] ** 2 + row["y_coordinate"] ** 2 < 36]

    edge_failure_rate = 1 - sum(row["passed"] for row in edge) / len(edge)
    center_failure_rate = 1 - sum(row["passed"] for row in center) / len(center)
    assert edge_failure_rate > center_failure_rate + 0.15


def test_invalid_generation_size_is_rejected() -> None:
    try:
        SyntheticDataGenerator(GenerationConfig(wafers_per_lot=0))
    except ValueError as error:
        assert "wafers_per_lot" in str(error)
    else:
        raise AssertionError("Expected invalid configuration to raise ValueError")

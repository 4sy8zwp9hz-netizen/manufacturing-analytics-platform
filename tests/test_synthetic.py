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

    wafer_ids = {row["wafer_id"] for row in dataset["wafers"]}
    assert {row["wafer_id"] for row in dataset["yield_results"]} <= wafer_ids
    assert all(0 <= row["yield_rate"] <= 1 for row in dataset["yield_results"])


def test_invalid_generation_size_is_rejected() -> None:
    try:
        SyntheticDataGenerator(GenerationConfig(wafers_per_lot=0))
    except ValueError as error:
        assert "wafers_per_lot" in str(error)
    else:
        raise AssertionError("Expected invalid configuration to raise ValueError")


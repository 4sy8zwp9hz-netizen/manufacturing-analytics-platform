"""Benchmark refresh stages separately from published-generation dashboard queries."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from statistics import median
from time import perf_counter

from manufacturing_analytics.analytics.platform_service import YieldPlatformService
from manufacturing_analytics.data.platform_repository import PlatformRepository
from manufacturing_analytics.pipeline.generation_store import GenerationStore
from manufacturing_analytics.pipeline.refresh import RefreshPipeline
from manufacturing_analytics.pipeline.sources import (
    SourceGenerationConfig,
    SyntheticSourceFactory,
    source_adapters,
)


def benchmark(config: SourceGenerationConfig, query_iterations: int = 20) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="map-benchmark-") as directory:
        root = Path(directory)
        source_mark = perf_counter()
        paths = SyntheticSourceFactory(root / "sources", config).create()
        source_generation_ms = (perf_counter() - source_mark) * 1000
        store = GenerationStore(root / "generations")
        result = RefreshPipeline(source_adapters(paths), store).refresh()
        service = YieldPlatformService(PlatformRepository(store))
        query_times = []
        for _ in range(query_iterations):
            mark = perf_counter()
            service.dashboard({"product": "ORION-A"})
            query_times.append((perf_counter() - mark) * 1000)
        ordered = sorted(query_times)
        return {
            "configuration": config,
            "source_generation_ms": round(source_generation_ms, 3),
            "refresh_timings_ms": result["timings"],
            "row_counts": result["row_counts"],
            "dashboard_query_median_ms": round(median(query_times), 3),
            "dashboard_query_p95_ms": round(ordered[int(len(ordered) * 0.95) - 1], 3),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-orders", type=int, default=12)
    parser.add_argument("--lots-per-work-order", type=int, default=4)
    parser.add_argument("--wafers-per-lot", type=int, default=10)
    parser.add_argument("--die-grid-size", type=int, default=15)
    arguments = parser.parse_args()
    result = benchmark(
        SourceGenerationConfig(
            work_orders=arguments.work_orders,
            lots_per_work_order=arguments.lots_per_work_order,
            wafers_per_lot=arguments.wafers_per_lot,
            die_grid_size=arguments.die_grid_size,
        )
    )
    print("Pipeline benchmark (synthetic, local, directional)")
    print(result)


if __name__ == "__main__":
    main()

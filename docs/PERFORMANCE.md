# Performance evidence

The platform separates refresh cost from interaction cost. Measurements are local and directional, not service-level objectives.

## Benchmark mode

```bash
python -m manufacturing_analytics.scripts.benchmark_pipeline
```

Defaults: 12 work orders × 4 lots × 10 wafers, with a 15×15 die grid. The August 2026 Windows/Python 3.12 run produced:

- 480 canonical wafers
- 217,440 stage-population rows
- 217,440 lineage rows
- 139 deterministic warnings/dispositions summarized at the relevant wafer or source-record grain

## Measured pipeline stages

| Stage | Time ms |
| --- | ---: |
| Synthetic source creation | 1,680.200 |
| Source extraction | 525.762 |
| Identity reconciliation | 495.105 |
| Manufacturing transformation | 709.632 |
| Analytical generation write | 4,014.173 |
| Validation | 1,278.386 |
| Atomic publication | 5.747 |

The dashboard query, including stage metrics, trend, failure Pareto, filter options, and wafer summaries, measured 521.789 ms median and 565.340 ms approximate p95 over 20 warm iterations.

## What the result supports

A dashboard request is materially cheaper than reconstructing the analytical generation from six sources. More importantly, it has no source-system load and reads a consistent generation. The benchmark supports scheduled transformation and prepared analytical storage.

It does **not** prove that an additional application cache is needed. At this scale, a roughly half-second broad dashboard query is acceptable for a local portfolio workload. The first optimization should be query-plan/index measurement and selectively precomputed aggregates—not an unmeasured cache.

## Scaling interpretation

The benchmark is configurable:

```bash
python -m manufacturing_analytics.scripts.benchmark_pipeline \
  --work-orders 24 --lots-per-work-order 6 --wafers-per-lot 20 --die-grid-size 21
```

At larger volumes, evaluate:

1. batched/streaming extraction rather than loading every source row in memory;
2. vectorized or SQL-based transformations where profiling identifies cost;
3. Parquet/DuckDB for columnar stage scans and partitioned generations;
4. precomputed aggregates by the demonstrated filter dimensions;
5. lineage storage partitioning and pagination;
6. concurrent-reader and generation-retention behavior.

The older normalized-query benchmark remains available in `benchmark_queries.py` for the supporting Phase 1–3 modules, but it is no longer the flagship performance story.

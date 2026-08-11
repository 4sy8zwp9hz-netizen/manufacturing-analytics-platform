# Analytics performance baseline

Phase 2 instruments repository calls to establish evidence before adding caching or precomputation.

## Representative dataset

The default deterministic configuration generates:

| Record | Count |
| --- | ---: |
| Work orders | 4 |
| Lots | 12 |
| Wafers / yield results | 60 |
| Wafer-operation events | 360 |
| Inspections | 120 |
| Coordinate-level die results | 19,020 |

## Local baseline

The figures below came from 20 warm iterations on the project’s Windows development environment using Python 3.12 and SQLite. They are directional, not a service-level objective; hardware, filesystem cache, and concurrent load will change them.

| Query | Median ms | Approx. p95 ms |
| --- | ---: | ---: |
| Yield KPI | 0.696 | 0.793 |
| Yield trend | 0.616 | 0.662 |
| Lot yield comparison | 0.630 | 0.673 |
| Tool yield comparison | 0.735 | 0.840 |
| Defect Pareto | 0.846 | 1.079 |
| Lot detail | 0.690 | 1.132 |
| Wafer map | 0.897 | 1.028 |

Reproduce the baseline with:

```bash
python -m manufacturing_analytics.scripts.benchmark_queries
```

## Optimization candidates

No cache is justified at the current scale. With millions of wafers or high request concurrency, the first candidates would be filtered yield aggregates, the exposure-to-final-yield comparison, and defect aggregation. Coordinate maps are selective by indexed wafer ID and should remain direct reads unless payload or remote-database latency becomes material.

Future work should define freshness requirements before choosing cache keys or refresh intervals. Precomputed tables need lineage to a source watermark; cache invalidation needs one clear owner; background refresh must be idempotent and observable.

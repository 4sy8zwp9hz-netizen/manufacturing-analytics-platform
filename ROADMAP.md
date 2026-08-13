# Roadmap

The project now progresses as a manufacturing yield data platform. SPC and operations remain supporting capabilities, not the central product identity.

## 1. Foundation — complete

- Maintainable Python package, configuration, logging, tests, CI, and documentation
- Deterministic synthetic work orders, lots, wafers, dies, operations, and inspections
- Wafer maps, yield trends, Pareto, and parameterized data access

## 2. Multi-source manufacturing data — complete

- Six isolated fictional source systems with heterogeneous schemas and grains
- Deliberate duplicates, revisions, late data, missing IDs, naming differences, and exclusions
- Explicit canonical identity and genealogy reconciliation

## 3. ETL and analytical model — complete

- Source-specific extraction boundaries
- Configuration-driven manufacturing transformations
- Stage-specific denominators, failure families, exclusions, and completion logic
- Canonical wafer and population records with row-level source lineage
- Validation findings and quarantines

## 4. Yield investigation application — complete

- Flagship multi-stage Yield Dashboard
- Month/product/work-order/wafer filters
- Trend, Pareto, stage population inspection, CSV export, and wafer lineage drill-down
- Supporting wafer map, SPC, operations, and data-quality labs retained

## 5. Refresh and performance architecture — portfolio implementation complete

- Immutable generations and atomic current-generation pointer
- Failed-refresh fallback to previous known-good data
- Testable scheduled-refresh seam
- Source watermarks, row counts, warnings, and publication metadata
- Configurable staged benchmark with measured results

Future scale work: incremental extraction, idempotency keys, refresh locks, generation retention, partitioned Parquet/DuckDB evaluation, and precomputed filter cubes only where benchmarks justify them.

## 6. Deployment and platform operations — next

- Container image and environment-specific configuration
- Dedicated refresh worker/scheduler
- Structured metrics, traces, alerting, and refresh run history
- Retry/dead-letter policies and operational runbooks
- Authentication/authorization for source lineage and exports
- Concurrency, load, recovery, and schema-migration testing

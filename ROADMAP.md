# Roadmap

## Phase 1 — Foundation (complete)

- Layered Python package, configuration, logging, and application factory
- Normalized synthetic manufacturing schema and deterministic generator
- Transactional SQLite data layer and automated tests
- Responsive landing shell and architecture documentation

## Phase 2 — Yield investigation (complete)

- Coordinate-level pass/fail results with reproducible spatial patterns
- Filtered Yield Overview with explicit metric definitions
- Yield trend, distribution, lot, product, and tool comparisons
- Lot-to-wafer drill-down with preserved investigation context
- Interactive SVG wafer map, process genealogy, and inspection context
- Filter-aware defect Pareto with tested contribution calculations
- Dedicated analytics service/repository boundary and query timing
- Behavioral tests for generation, filters, queries, routes, and errors

## Phase 3 — Process monitoring and operations (complete)

- Deterministic continuous measurements with shifts, drift, variation, offsets, and outlier behavior
- Individuals / Moving Range charts with rational-subgroup validation
- Control limits kept visually and conceptually separate from specification limits
- Tested point, run, and trend rule evaluation with exact evidence windows
- Tool/product/time stratification and manufacturing-genealogy drill-down
- Cycle, queue, route elapsed, and observed-throughput analysis
- Data-quality findings, source watermarks, and freshness indicators
- Locally bundled Chart.js assets and tabular/textual evidence

## Phase 4 — Performance and refresh

- Production-scale benchmark data and documented performance budgets
- Precomputed aggregate tables for demonstrated expensive queries
- Cache-aside reads with explicit keys, TTLs, and invalidation ownership
- Idempotent background refresh jobs with locking and retry policy
- Source watermarks and freshness metadata surfaced in the UI

## Phase 5 — Deployment and operations

- PostgreSQL adapter and versioned schema migrations
- Container image, non-root runtime, health/readiness endpoints
- CI for formatting, tests, dependency and container checks
- Metrics, traces, structured JSON logs, and alerting guidance
- Threat model, secrets strategy, backup/restore exercise, and runbook

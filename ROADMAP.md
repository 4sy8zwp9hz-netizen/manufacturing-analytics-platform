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

## Phase 3 — Process monitoring and operations

- SPC charts with configurable subgrouping and rational sampling guidance
- Control-limit calculation separated from engineering specification limits
- Tested Western Electric/Nelson-style rule evaluation with clear assumptions
- Tool and operation comparisons with product/time stratification
- Manufacturing genealogy timeline with cycle-time and queue-time analysis
- Data-quality diagnostics, missing-event handling, and freshness indicators
- Accessible chart alternatives and locally bundled front-end assets

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


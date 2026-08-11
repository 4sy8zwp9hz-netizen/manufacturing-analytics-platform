# Roadmap

## Phase 1 — Foundation (current)

- Layered Python package, configuration, logging, and application factory
- Normalized synthetic manufacturing schema and deterministic generator
- Transactional SQLite data layer and summary repository
- Responsive landing page with placeholder analytics navigation
- Generator, persistence, repository, and HTTP smoke tests
- Architecture, data-model, and development documentation

## Phase 2 — Yield and wafer investigation

- Yield overview with time, product, lot, operation, and tool filters
- Lot-to-wafer drill-down with preserved filter context
- Interactive wafer maps backed by generated die-coordinate results
- Defect Pareto with cumulative-percentage analysis
- Tested analytics-query service and clear metric definitions
- Query timing instrumentation and accessibility checks for charts

## Phase 3 — Process monitoring and operations

- SPC charts with configurable subgrouping and control-rule evaluation
- Tool and operation comparison views with careful cohort selection
- Manufacturing genealogy timeline for each wafer
- Data-quality diagnostics, late-data handling, and richer error states
- Configuration-driven routes, thresholds, and metric definitions

## Phase 4 — Performance and refresh

- Precomputed aggregate tables for expensive dashboard queries
- Cache-aside reads with explicit keys, TTLs, and invalidation ownership
- Idempotent background refresh jobs with locking and retry policy
- Freshness metadata surfaced in the user interface
- Workload tests and documented performance budgets

## Phase 5 — Deployment and operations

- PostgreSQL adapter and versioned schema migrations
- Container image, non-root runtime, health/readiness endpoints
- CI for formatting, linting, tests, dependency checks, and image builds
- Metrics, traces, structured JSON logs, and alerting guidance
- Threat model, secrets strategy, backup/restore exercise, and runbook


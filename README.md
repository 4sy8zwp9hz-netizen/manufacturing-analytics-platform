# Manufacturing Analytics Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-007b75.svg)](LICENSE)

A production-style Python investigation tool for semiconductor manufacturing analytics using **entirely synthetic data**.

> **Clean-room portfolio project:** no proprietary source code, company schemas, table names, credentials, business rules, or production data are used or referenced. Every identifier, relationship, distribution, spatial pattern, and process effect is fictional.

## The manufacturing problem

A yield number is only the start of an investigation. An engineer needs to define the affected cohort, identify degraded lots, compare individual wafers, inspect spatial signatures, trace operation and tool history, and use defects as supporting context.

This project implements that connected path:

```text
Yield signal → filtered cohort → lot → wafer map → process genealogy → tool comparison → defect Pareto
```

Phase 3 extends that coherent workflow from yield investigation into process behavior, SPC evidence, operational flow, and data trust. Filter and service models keep every page aligned on explicit cohorts and definitions.

## Investigation experience

### Yield Overview

![Yield Overview showing KPIs, filters, trend, distribution, and lot comparison](docs/screenshots/yield-overview.png)

Weighted yield, cohort counts, time trend, wafer distribution, lot and product comparisons, and operation-aware tool comparison. Product, work-order, lot, date, operation, and tool filters use parameterized analytics queries.

### Lot investigation

![Lot investigation showing individual wafers and process genealogy](docs/screenshots/lot-investigation.png)

Selecting a lot preserves the investigation context and exposes individual wafer yield, inspection counts, operation/tool history, and the lot defect mix.

### Wafer map

![Interactive coordinate-level pass/fail wafer map](docs/screenshots/wafer-map.png)

Each wafer contains 317 unique coordinate results. The interactive SVG map exposes pass/fail status and fictional test bin while the adjacent genealogy connects the wafer to the tools used.

### Defect Pareto

![Defect Pareto with contribution and cumulative percentage](docs/screenshots/pareto-analysis.png)

The filter-aware Pareto combines classified defect counts, percentage contribution, and cumulative percentage. Statistical calculations live in the domain layer and have focused unit tests.

### Process / SPC

![Individuals and Moving Range process-monitoring workflow](docs/screenshots/process-spc.png)

Time-ordered continuous measurements, explicit behavior-based control limits, separate engineering specification limits, moving ranges, tool stratification, and point-level evidence for three documented SPC rules.

### Manufacturing Operations

![Manufacturing cycle, queue, route, and throughput investigation](docs/screenshots/manufacturing-operations.png)

Cycle time, queue time, route elapsed time, observed completions, and wafer/lot drill-down are calculated directly from fictional event timestamps. Utilization is deliberately omitted because no capacity calendar exists.

### Data Quality

![Data-quality findings and source watermarks](docs/screenshots/data-quality.png)

Missing, duplicate, delayed, out-of-sequence, missing-measurement, and stale-source scenarios are visible alongside source-specific freshness objectives and watermarks.

## Investigation Walkthrough

One fictional walkthrough using the configured seed:

1. Open **Yield Overview** and note the weighted baseline and wafer-yield distribution.
2. Compare lots and open `LOT-0103`, a cohort containing visibly lower-yield wafers.
3. Select `WFR-00011`; the wafer map makes its edge-heavy failure signature visually apparent.
4. Review the wafer genealogy, then return to the overview and compare tools at `OP-400`.
5. Observe that the synthetic `ETCH-02` cohort trends lower than `ETCH-01`, then use product, time, and lot filters to see whether the association persists.
6. Check the Pareto and inspection context to prioritize follow-up—not to declare root cause.

This sequence supports a hypothesis about a fictional process/tool relationship. It does **not** prove causation. A real investigation would check confounding, sampling, metrology, maintenance history, temporal ordering, repeatability, and designed experiments.

## SPC Investigation Walkthrough

1. Open **Process / SPC** for fictional etch depth. The aggregate series remains mostly inside its broad fictional specifications and can initially look reasonable.
2. Compare the tool strata: `ETCH-02` has a higher mean and substantially more rule signals than `ETCH-01`.
3. Filter to `ETCH-02`. The time-ordered series exposes its deterministic offset and gradual drift without mixing the more stable tool into the estimate.
4. Review the triggered rule, its exact evidence window, wafer, timestamp, and value. No opaque process-health score is used.
5. Open the affected wafer and lot to inspect manufacturing genealogy and neighboring evidence.
6. Treat the result as a process signal requiring engineering investigation—not automatic proof that the tool caused the measurement behavior.

A real response would validate the measurement system, sampling plan, maintenance and recipe history, material/product mix, autocorrelation, and the appropriateness of the Phase I limit-estimation window.

## Architecture

- **Domain:** deterministic process behavior, I/MR limits, control rules, operations math, freshness, yield, and Pareto calculations
- **Data:** relational schema, process measurements, watermarks, transactions, parameterized analytics SQL, and indexes
- **Analytics:** canonical cohorts, SPC/operations/quality workflows, metric definitions, and timing
- **Services:** safe local bootstrap of reproducible generated data
- **Web:** HTTP validation, status codes, context serialization, and presentation
- **Composition:** explicit startup wiring and application lifecycle

Routes contain no SQL; templates calculate no manufacturing statistics. See [ARCHITECTURE.md](ARCHITECTURE.md), [DATA_MODEL.md](docs/DATA_MODEL.md), and [PERFORMANCE.md](docs/PERFORMANCE.md).

## Technology stack

| Concern | Choice | Rationale |
| --- | --- | --- |
| Runtime | Python 3.11+ | Type hints, `tomllib`, broad deployment support |
| Web | FastAPI + Jinja2 | Testable application factory without a frontend build system |
| Charts | Locally bundled Chart.js 4 | Reproducible interactive comparisons without third-party runtime requests |
| Wafer map | Server-rendered SVG | Coordinate-native, inspectable, and lightweight interaction |
| Storage | SQLite + explicit SQL | Zero-service setup and transparent relational/query design |
| Tests | pytest + HTTPX | Isolated behavior and end-to-end route validation |
| Quality | Ruff | Consolidated linting and import checks |
| CI | GitHub Actions | Python 3.11/3.12 lint, tests, and generator exercise |

## Synthetic data model

```text
Work order → lot → wafer → operation/tool history
                    ├── inspection → classified defects
                    ├── yield result → coordinate-level die results
                    └── process measurement → characteristic + specification
Source watermark → freshness state
Quality finding → affected wafer/source + evidence
```

The generator embeds deterministic spatial signatures plus stable variation, tool offset, mean shift, drift, increased variation, and an isolated process outlier. Aggregate yield is calculated from coordinate results, preventing disagreement between the KPI and wafer map.

## Quick start

```bash
python -m venv .venv
```

Activate the environment, then:

```bash
python -m pip install -e ".[dev]"
python -m manufacturing_analytics.scripts.generate_data
uvicorn manufacturing_analytics.main:app --reload
```

Open <http://127.0.0.1:8000/analytics/yield-overview>.

Run quality checks and the timing baseline:

```bash
pytest --cov=manufacturing_analytics --cov-report=term-missing
ruff check .
python -m manufacturing_analytics.scripts.benchmark_queries
```

## Metric definitions

| Metric | Definition |
| --- | --- |
| Weighted yield | Sum of passing die ÷ sum of tested die in the filtered cohort |
| Wafer count | Distinct wafers with a final synthetic yield result |
| Lot/work-order count | Distinct parent entities represented by filtered wafers |
| Tool comparison | Final wafer yield grouped by tool exposure at one operation |
| Defect contribution | Category count ÷ all classified inspection defects in the cohort |
| Individuals limits | Center ± 3 × MR̄/1.128 for time-ordered individual values |
| Specification limits | Fictional externally defined engineering requirements, never control limits |
| Cycle time | Event end timestamp − event start timestamp |
| Queue time | Next event start − previous event end for one wafer |
| Freshness | Observation timestamp − published source watermark |

The time filter uses the final yield timestamp. Tool comparisons are screening views and do not control automatically for product, time, route, or other confounders.

## Configuration

Defaults live in `config/default.toml`. `MAP_ENVIRONMENT`, `MAP_DATABASE_PATH`, and `MAP_LOG_LEVEL` provide operational overrides. Generator size and seed remain explicit, checked-in inputs. Generated databases are ignored because they are reproducible artifacts.

## Testing strategy

Tests validate deterministic process and coordinate output, control limits, moving ranges, three SPC rules and evidence, rational subgroup validation, tool drift/stratification, cycle and queue calculations, event completeness and ordering, source freshness, relational integrity, filters, drill-down models, local assets, HTTP errors, and rendered routes.

## Tradeoffs and limitations

- SQLite optimizes local reproducibility, not concurrent analytical workloads.
- Chart.js is pinned and bundled locally with its license; an internet-facing deployment should still apply a Content Security Policy.
- Server-rendered SVG is ideal for 317 sites but dense maps may need canvas/WebGL or aggregation.
- Tool comparisons show association and can be confounded; they are not causal models.
- Inspection defects provide investigation context but are not asserted to cause electrical failures.
- In-process timing establishes a baseline but is not distributed observability.
- I/MR limits assume a meaningful time order and use moving ranges of two; autocorrelation, non-normality, mixed distributions, or unstable Phase I data can make the limits misleading.
- No cache or precomputed table is added because measured local queries remain near one millisecond.

## Repository layout

```text
config/                         Checked-in defaults
docs/                           Model, performance, and screenshots
src/manufacturing_analytics/
  analytics/                    Filters, metrics, workflows, timing
  data/                         Schema, database adapter, analytics queries
  domain/                       Synthetic behavior, SPC rules, quality, operations math
  scripts/                      Generation and benchmark commands
  services/                     Application use cases
  web/                          Routes, templates, and static assets
tests/                          Behavioral unit and HTTP tests
```

See [ROADMAP.md](ROADMAP.md) for scale testing, background refresh, caching, and deployment phases.

## License

MIT. The code and synthetic dataset are provided for education and portfolio review.

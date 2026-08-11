# Manufacturing Analytics Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-006d68.svg)](LICENSE)

A production-style Python foundation for exploring semiconductor manufacturing analytics with **entirely synthetic data**.

> **Clean-room portfolio project:** no proprietary source code, company schemas, table names, credentials, business rules, or production data are used or referenced. Every identifier, relationship, distribution, and process effect in this repository is fictional and exists only to support software-engineering demonstrations.

## The manufacturing problem

Yield questions rarely live in one table. An engineer investigating a low-yield wafer needs to connect the customer or production request to its lot, trace each wafer through process operations and tools, compare inspection signatures, rank defect modes, and determine whether the signal is isolated or part of a trend.

This project models that investigation path:

```text
Work order → lot → wafer → operation history → tool → inspection → defect → yield
```

Phase 1 builds the trustworthy foundation for that journey: a coherent data model, reproducible data generation, explicit SQL, an application shell, and automated tests. It intentionally stops before presenting placeholder charts as finished analytics.

## What is implemented

- Deterministic synthetic work orders, lots, wafers, route operations, tools, inspections, defect classifications, and wafer-level yield
- A normalized SQLite schema with foreign keys, checks, uniqueness constraints, and analysis-oriented indexes
- Transactional dataset replacement and a repository layer for application queries
- A FastAPI/Jinja application shell with a landing summary and navigation for:
  - Yield Overview
  - Wafer Analysis
  - Pareto Analysis
  - Process / SPC
  - Manufacturing Operations
- TOML configuration with environment overrides
- Central logging, application health check, and safe local bootstrap
- Automated generator, database, repository, and HTTP smoke tests
- GitHub Actions quality checks across supported Python versions

## Architecture

The code uses a small layered architecture:

- **Domain:** manufacturing concepts and deterministic generation behavior
- **Data:** schema, SQLite transactions, and manufacturing-oriented queries
- **Services:** application workflows such as local dataset bootstrap
- **Web:** HTTP routes and presentation templates
- **Composition:** startup wiring and lifecycle management

Dependencies point inward: delivery and persistence details do not leak into the generator. See [ARCHITECTURE.md](ARCHITECTURE.md) for the rationale and [docs/DATA_MODEL.md](docs/DATA_MODEL.md) for the entity relationships.

## Technology stack

| Concern | Choice | Why |
| --- | --- | --- |
| Runtime | Python 3.11+ | Type hints, `tomllib`, broad deployment support |
| Web | FastAPI + Jinja2 | Clear application factory and routes without a front-end build chain |
| Local storage | SQLite + explicit SQL | Zero-service setup and visible relational design |
| Server | Uvicorn | Standard ASGI development/runtime path |
| Tests | pytest + HTTPX | Focused fixtures and application-level smoke testing |
| Quality | Ruff | Fast, consolidated linting and import checks |
| Packaging | `pyproject.toml` + Hatchling | Modern metadata and editable installs |
| CI | GitHub Actions | Repeats lint, tests, and data generation on Python 3.11 and 3.12 |

## Quick start

```bash
python -m venv .venv
```

Activate the environment, then install and run:

```bash
python -m pip install -e ".[dev]"
python -m manufacturing_analytics.scripts.generate_data
uvicorn manufacturing_analytics.main:app --reload
```

Open <http://127.0.0.1:8000>. The application also bootstraps the database on first startup, so the explicit generation command is optional. It is shown because reproducible data preparation should be visible and separately runnable.

Run the checks:

```bash
pytest
ruff check .
```

On systems with Make, `make install`, `make data`, `make run`, `make test`, and `make lint` provide shortcuts.

## Configuration

Defaults live in `config/default.toml`. These environment variables can override operational settings:

| Variable | Purpose | Default |
| --- | --- | --- |
| `MAP_ENVIRONMENT` | Runtime environment label | `development` |
| `MAP_DATABASE_PATH` | SQLite database location | `data/manufacturing_analytics.db` |
| `MAP_LOG_LEVEL` | Python logging level | `INFO` |

Generator scale and seed are explicit in TOML. Generated databases are ignored by Git because they are reproducible build artifacts.

## Engineering concepts demonstrated

The repository is intended to make engineering judgment discussable, not just to accumulate features. It demonstrates normalized data modeling, referential integrity, deterministic fixtures, transaction boundaries, dependency direction, configuration precedence, application lifecycle management, health checks, isolated tests, responsive server-rendered UI, and documentation of tradeoffs.

The roadmap extends those foundations into drill-down analytics, wafer maps, Pareto analysis, SPC, caching, precomputation, refresh jobs, observability, migrations, containers, and CI. See [ROADMAP.md](ROADMAP.md).

## Important limitations

- The process route and statistical effects are simplified teaching constructs, not a digital twin of a fab.
- Yield is currently one aggregate result per wafer; die coordinates arrive in Phase 2.
- SQLite favors local reproducibility over concurrent analytical workloads.
- The initial UI establishes information architecture but does not yet claim production-ready analytics.
- Background jobs, caches, and precomputed tables are architectural roadmap items, not premature Phase 1 abstractions.

## Repository layout

```text
config/                         Checked-in defaults
docs/                           Data-model documentation
src/manufacturing_analytics/
  data/                         Schema, database adapter, repositories
  domain/                       Synthetic manufacturing behavior
  scripts/                      Reproducible command-line tasks
  services/                     Application use cases
  web/                          Routes, templates, and static assets
  main.py                       Composition root
tests/                          Fast, isolated automated tests
```

## License

MIT. The synthetic dataset and code are provided for education and portfolio review.

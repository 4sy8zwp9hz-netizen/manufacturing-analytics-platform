# Truthfulness Audit

This document classifies the major public claims so architecture, demo accommodations, and future
ideas cannot be confused.

| Public claim | Classification | Evidence in this repository |
| --- | --- | --- |
| The original architecture used SQL Server and `pyodbc` | Direct analogue of completed work | Optional clean-room boundary in `sources.py`; documented from verified private implementation |
| Source queries were parameterized and source specific | Direct analogue of completed work | Fictional parameterized examples and source contract; no private SQL copied |
| Pandas resolved manufacturing populations | Direct analogue of completed work | `transforms.py` |
| The application used Dash and Plotly | Direct analogue of completed work | `application.py`, `yield_analytics.py` |
| The application was server hosted with Waitress | Direct analogue of completed work | `main.py` |
| Shared JSON controlled application/engineering behavior | Direct analogue of completed work | `config/*.json` |
| Common data was cached/preloaded on the server | Direct analogue of completed work | `SnapshotManager`, common generation loader |
| Specialized data had separate refresh/preload behavior | Direct analogue of completed work | `SortingPreload` and separate server loop |
| Very large detail was retrieved for a narrowed population | Direct analogue of completed work | `TargetedDetailRepository`; public substitute uses Parquet filters |
| Parquet generations and prepared Yield facts were implemented | Direct analogue of completed work | `ParquetGenerationStore` |
| Failed refreshes retained usable data | Direct analogue of completed work | refresh coordinator, generation fallback, injected-failure tests |
| New generations could be loaded without server restart | Direct analogue of completed work | `GenerationWatcher` |
| The Yield app ultimately integrated into an application portal | Direct analogue of completed work | portal-ready URL-prefix factory; broader portal documented, not recreated |
| The public demo connects to manufacturing SQL Server | **Not claimed** | Synthetic adapter is the default and only runnable data source |
| Synthetic source values reflect production data | **Not claimed** | Deterministic fictional generator only |
| Public targeted Parquet read is identical to production targeted SQL | Public-demo accommodation | It demonstrates population-first narrowing without a private database |
| Every private application is recreated in this repository | **Not claimed** | Related applications are evolution references only |
| Enterprise network configuration was personally administered | **Not claimed** | Documentation states collaboration with IT |
| Upstream MES/database changes were personally implemented | **Not claimed** | Documentation distinguishes requirements/integration from team ownership |
| Distributed caches, cloud, containers, or microservices are implemented | **Not claimed / excluded** | No such dependency or architecture exists |
| A complete public SQL Server deployment is available | Future design | Optional adapter boundary intentionally remains deployment-specific |

## Removed previous inaccuracies

| Previous public representation | Resolution |
| --- | --- |
| FastAPI/Jinja flagship UI | Removed; replaced with Dash/Plotly |
| Bundled Chart.js UI | Removed |
| Six SQLite source systems | Removed |
| Immutable SQLite database generations | Removed; replaced with Parquet generations and in-memory snapshot publication |
| `.building.sqlite` and plain-text `CURRENT` story | Removed |
| Qualification excluded as non-production context | Removed; qualification now defines and contributes to the final physical-wafer cohort |
| Generic rolled-stage Yield | Removed; replaced with explicit stage grains and complete component rules |
| DuckDB/Parquet described only as hypothetical future work | Corrected; Parquet is implemented, DuckDB is not added |
| Generic page-per-feature SaaS screenshots | Removed and recaptured from the corrected running application |
| PostgreSQL/Redis/cloud-style roadmap drift | Removed |

## Remaining uncertainty

- The repository does not verify whether a particular external Windows scheduled task is currently
  registered on the private host; it verifies the refresh controller and launch support code.
- Exact pre-baseline dates for early SQL, packaging, and desktop stages are not provable from the
  available git history, so documentation gives sequence without invented dates.
- Private production timing values are not published because no safely attributable measurement was
  available for this clean-room repository.
- Staged/private supporting applications are not described as generally deployed without clear
  implementation evidence.

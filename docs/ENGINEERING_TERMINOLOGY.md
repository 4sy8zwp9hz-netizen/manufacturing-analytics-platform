# Engineering Terminology Learned Through Practice

This document answers: **“What formal software concepts describe work I had already learned to do?”**

| What I naturally did | Software-engineering term | Why it mattered |
| --- | --- | --- |
| Turned source records into the population required by an engineering question | ETL / analytical transformation | Source data did not directly represent the metric |
| Kept wafer, chip, process, and measurement rows distinct | Data grain | Prevented invalid joins and denominators |
| Defined exactly which records were eligible for one calculation | Analytical population / cohort | Made Yield reproducible and explainable |
| Mapped different source identifiers to one physical wafer | Entity resolution / canonical identity | Allowed cross-source analysis without silently merging ambiguity |
| Loaded common data once so every click did not query SQL | Caching / preloading | Reduced interaction latency and database load |
| Built common charts and table ranges before the user clicked | Precomputation / eager computation | Moved repeatable work out of the interaction path |
| Loaded specialized analysis only when requested | Lazy loading | Avoided unnecessary startup work |
| Gave Sorting its own refresh cycle | Workload isolation / independent refresh cadence | One unusually expensive source no longer controlled every other path |
| Limited SQL using work orders and wafers already in scope | Query scoping / predicate reduction | Reduced rows scanned and transferred |
| Used temporary SQL keys to join a narrowed population | Set-based query optimization | Avoided row-by-row queries and parameter-limit problems |
| Kept the current dataset when refresh failed | Last-known-good / fault-tolerant refresh | Preserved availability during source or transformation failures |
| Published only a complete prepared generation | Atomic publication | Prevented users from observing partial data |
| Kept completed generations unchanged | Immutable generation | Simplified consistency, validation, and rollback reasoning |
| Swapped a complete in-memory object under a lock | Snapshot publication | Kept callbacks on one consistent population |
| Put changing engineering rules in JSON | Configuration-driven behavior | Allowed controlled changes without rewriting UI code |
| Kept summary results linked to their contributing rows | Data lineage / traceability | Let engineers explain why a number was counted |
| Separated SQL/transformation work from Dash rendering | Separation of concerns | Allowed each part to change for its own reason |
| Mounted several Dash apps behind one Flask entry point | WSGI composition / application portal | Provided centralized access without rewriting every app |
| Moved shared applications to a server | Client/server architecture / centralized hosting | Removed per-user processing and update duplication |
| Added logs, health checks, watchdogs, and restart paths | Operational ownership / observability | Made software supportable after deployment |
| Packaged and versioned applications for other engineers | Release management / software distribution | Kept users on supported versions |

These terms are useful in interviews only when tied back to the actual problem and decision. Saying
“lazy loading” is less meaningful than explaining why a high-volume dataset was intentionally kept
off the startup path.

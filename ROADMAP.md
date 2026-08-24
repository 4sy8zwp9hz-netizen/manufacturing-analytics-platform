# Roadmap

The major clean-room alignment is complete. This roadmap contains only refinements that follow from
the verified architecture; it is not a plan to add fashionable infrastructure.

## Completed alignment

- Dash/Plotly table-first Yield workflow
- Synthetic substitute for source-shaped manufacturing records
- Pandas identity, revision, date, population, and cohort transformation
- Wafer and chip grains with quantity-weighted final Yield
- Parquet generations, manifests, compatibility validation, and atomic publication
- Common in-memory snapshot plus last-known-good behavior
- Separate Sorting preload and targeted physical-wafer detail
- Scheduled refresh loops and generation hot reload
- Waitress server and portal-ready application factory
- Traceability, export, failure injection, tests, lint, and current screenshots
- Architecture, data flow, evolution, performance, deployment, calculation, and terminology docs

## Next fidelity refinements

1. Add more synthetic equivalents of supported process families only after mapping each to a real
   workflow and confirming that the terminology is safe.
2. Expand selected-period navigation and exclusion controls to more closely mirror the mature
   Enhance workflow.
3. Add a clean-room Excel export with summary, period, raw-population, and lineage sheets.
4. Add an optional fake-connector integration test that proves parameter binding and scoped-key SQL
   construction without requiring SQL Server.
5. Add screenshot regression checks for layout dimensions and required workflow elements.
6. Add public synthetic benchmarks with machine/runtime metadata and clearly separate them from any
   private production outcome.

## Explicitly out of scope

PostgreSQL, Redis, DuckDB, Docker, Kubernetes, cloud infrastructure, microservices, and AI features
are not planned merely to make the repository appear more advanced. A future technology belongs
here only if it reflects completed experience, is required for the public demonstration, or is
clearly labeled as exploration.

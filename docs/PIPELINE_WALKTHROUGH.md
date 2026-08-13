# One wafer through the platform

This walkthrough follows fictional wafer `WAF-000001`. All identifiers and rules are synthetic.

## 1. MES process history

The MES source records three process events using substrate `SUB-700001`, work order `WO-001`, lot `LOT-001-01`, and wafer number `1`. One configured rule maps source labels into the canonical families `SURFACE_PREPARATION`, `PATTERN_TRANSFER`, and `FINAL_VERIFICATION`. Presence of the final family makes the wafer complete and production-eligible.

## 2. Wafer inspection

Wafer inspection does not use `SUB-700001`. It reports alias `WI-LOT-001-01-01`, a non-ISO timestamp, an inspection record ID, revision number, inspected-site count, failed-site count, and source defect label.

## 3. Chip inspection/test

Chip test emits one row per device coordinate. It knows `SUB-700001` and device IDs but not the canonical wafer ID. Results use compact `P`/`F` codes and source failure codes.

## 4. Sorting

Sorting identifies the wafer with composite `WO-001|1` and contains die-level parameter measurements. The ETL applies fictional inclusive limits of 44–56 synthetic units.

## 5. Identity reconciliation

The genealogy source maps:

- `SUBSTRATE_SERIAL|SUB-700001`
- `INSPECTION_ALIAS|WI-LOT-001-01-01`
- `ORDER_WAFER|WO-001|1`
- `LOT_WAFER|LOT-001-01|1`

to the same canonical work order, lot, and wafer. A unique match resolves. No match is quarantined. More than one canonical wafer is ambiguous and is also quarantined. If MES lacks a substrate serial, the resolver deliberately falls back to lot + wafer.

## 6. Manufacturing transformations

The refresh then:

1. normalizes process and date conventions;
2. decides route completion;
3. retains the latest inspection revision;
4. applies the wafer-inspection acceptance threshold;
5. translates chip-test failure codes into canonical failure families;
6. applies sorting limits at die grain;
7. assigns the analytical month;
8. excludes incomplete downstream populations;
9. retains qualification as non-production context.

## 7. Canonical records

The generation contains one canonical wafer plus four production-stage populations:

- one process-completion wafer row;
- one wafer-inspection wafer row;
- 49 chip-test die rows in the default 7×7 teaching grid;
- 49 sorting die rows.

Qualification produces a contextual sample row with `NON_PRODUCTION_POPULATION`; it does not enter rolled production yield.

## 8. Lineage

Every analytical row receives an `analytical_lineage` record. A failed chip-test die can therefore be traced from failure-family Pareto → chip-test population → canonical wafer → source system/table/key, with the applied transformation note beside it.

## 9. Validation and publication

The refresh writes a unique building database, records watermarks/counts/issues, commits it, and validates SQLite integrity, publication state, and canonical population. Only then does it rename the file and atomically switch `CURRENT`. An injected failure leaves the preceding pointer untouched; tests assert that readers still return the old generation.

## 10. Dashboard investigation

The Yield Dashboard opens only `CURRENT` in read-only mode. A user can filter by month/product/work order/wafer, compare stage-specific yields, inspect trend and Pareto, open the exact denominator, export it, then open `WAF-000001` to see source lineage. No step queries the six source files.

# Performance Evolution

This document explains how performance constraints shaped the data-access and runtime design.

## The first performance problem

The early priority was correctness: retrieve the necessary production data and calculate useful
engineering populations. As the application covered more stages and users, broad source queries,
startup work, and click-time aggregation became visible limitations.

The solution was iterative rather than one cache added at the end.

## Solution sequence

| Observed problem | Earlier behavior | Change | Why it helped |
| --- | --- | --- | --- |
| Expensive operational view | Broad retrieval | First identify relevant work orders/wafers, then query the narrowed keys | Reduced source scanning and transfer |
| Repeated source work | Callbacks rebuilt source populations | Load a shared server snapshot | Normal filtering stopped querying SQL |
| Repeated aggregation | Common views rebuilt after selection | Prebuild reusable periods, trends, and Pareto inputs | Moved work before interaction |
| Slow specialized path | Specialized analysis shared startup path | Lazy or background preparation | Preserved usable startup behavior |
| Unusually expensive Sorting data | Same cadence as common data | Dedicated preload and refresh cycle | Isolated the slow workload |
| Large detail population | Load everything “just in case” | Population-scoped retrieval | Read only data needed for one investigation |
| Visible blank/loading behavior | Page replaced while work completed | Retain the current view and show a thin progress state | Improved perceived and actual continuity |
| Alias mapping repeated | Rebuild identity work | Cache exact/normalized physical-wafer indexes | Avoided repeated reconciliation cost |
| Historical growth | Rebuild the complete prepared history | Reconcile incremental and corrected records where the source contract allowed it | Reduced unnecessary source and transformation work |
| Pipeline logic changed | Reuse an older cache that still looked structurally valid | Version prepared-data contracts and rebuild incompatible state | Prevented stale logic from surviving a release |
| Large reusable results | Allow in-process caches to grow without a clear limit | Bound cache entries and retain only useful reusable state | Controlled the service memory envelope |
| Concurrent browser polling and refresh | Overlapping work could rebuild or publish the same expensive result | Add refresh locks, completed-state publication, and polling guards | Reduced races and duplicate work |
| Large scoped key sets | Issue many small reads or one unbounded request | Batch parameterized retrieval at the appropriate source boundary | Balanced round trips, query size, and source load |

The public application directly demonstrates scoped detail reads, common snapshots, separate
preload behavior, refresh locking, atomic publication, and last-known-good retention. The later
incremental-refresh, pipeline-compatibility, batching, polling, and memory rows document verified
production evolution at a safe level; they are not presented as synthetic performance benchmarks
or one-for-one copies of private code.

## Common, expensive-common, and detail workloads

The mature decision rule is:

> Move work out of user interaction when reuse justifies it, but do not preload data whose scale
> makes that wasteful.

The public implementation makes that rule testable:

- common facts are loaded into the in-memory snapshot;
- Sorting parameter summaries are prepared independently;
- raw chip/parameter detail is filtered by selected physical wafer at Parquet read time.

Tests verify that one-wafer detail retrieval returns fewer rows than the persisted full population
and records a scope size of one.

## Evidence boundaries

No private production timing is published because no safely attributable measurement was available
for this clean-room repository. Qualitative historical outcomes are therefore described without
invented seconds or percentages.

Any timing produced by this public project would measure a small synthetic workload on the machine
running it. Such a number must be labeled **public synthetic benchmark**, never presented as an
employer-production result.

## Decision framework

The approach can be summarized as:

1. identify which operation was slow;
2. establish its population and reuse frequency;
3. decide whether to narrow, cache, prebuild, defer, or separate it;
4. keep source load and user latency as different concerns;
5. preserve traceability and failure behavior while optimizing.

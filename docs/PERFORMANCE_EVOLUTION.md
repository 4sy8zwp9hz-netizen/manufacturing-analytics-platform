# Performance Evolution

This document answers: **“Tell me about a performance problem and how you approached it.”**

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

## Interview framing

A strong explanation is:

1. identify which operation was slow;
2. establish its population and reuse frequency;
3. decide whether to narrow, cache, prebuild, defer, or separate it;
4. keep source load and user latency as different concerns;
5. preserve traceability and failure behavior while optimizing.

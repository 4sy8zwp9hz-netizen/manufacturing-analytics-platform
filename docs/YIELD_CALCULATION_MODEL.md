# Yield Calculation Model

This document answers: **“Where does manufacturing knowledge enter the software?”**

## Raw records are not the metric

Each Yield row answers a different question and can use a different grain, population, date, and
denominator. The code first creates a traceable row-level fact and only then aggregates it.

```text
source record
    ↓ identity + revision + date interpretation
physical-wafer analytical record
    ↓ population and completeness rules
stage numerator / denominator
    ↓ quantity-weighted aggregation
displayed Yield cell
```

## Fictional row model

| Public row | Grain | Numerator | Denominator | Reporting date |
| --- | --- | --- | --- | --- |
| Incoming Wafer Inspection | inspection site | good sites | inspected sites | inspection time |
| Surface Preparation | physical wafer | passed wafers | completed wafers | process completion |
| Pattern Separation | physical wafer | passed wafers | completed wafers | process completion |
| Protective Finish | physical wafer | passed wafers | completed wafers | process completion |
| Automated Outlier | chip | chips not flagged | prepared chips | chip-test time |
| Wafer Total | physical wafer | component product | complete wafer-stage cohort | latest component time |
| Chip Inspection | chip | good chips | inspected chips | latest-revision test time |
| Device Formation | chip | eligible good chips | eligible chips | process completion |
| Sorting Yield | chip | good sorted chips | inspected chips | process completion, not record creation |
| Qualification | physical wafer | qualified wafers | evaluated wafers | qualification time |
| Final Chip Yield | chip within physical-wafer cohort | component-product good quantity | inspected chip quantity | qualification-cohort time |

The stage names and rules are fictional analogues. They demonstrate categories of reasoning without
reproducing private terminology or thresholds.

## Physical-wafer identity

The synthetic sources refer to the same wafer with MES, inspection, chip, Sorting, and qualification
aliases. Resolution proceeds as:

1. exact source-specific alias;
2. normalized alias if enabled;
3. explicit `AMBIGUOUS` if more than one physical wafer matches;
4. explicit `UNRESOLVED` if no match exists.

Ambiguous and unresolved records are not silently placed into final cohorts. The identity audit
preserves their disposition.

## Revision handling

The chip inspection source contains a fictional revised result. The transformation selects the
highest revision for the source wafer before generating the stage fact. Keeping both versions in
the raw synthetic data makes the transformation visible and testable.

## Final Chip Yield

The public model mirrors the verified architectural rule category:

1. establish physical wafers represented in qualification;
2. require Chip Inspection, Device Formation, Sorting, and Qualification for that same wafer;
3. do not treat a missing component as 100%;
4. calculate component yields at the physical-wafer level;
5. multiply the component yields;
6. convert the result to good chip quantity;
7. aggregate good and total quantities across wafers.

For wafer `w`:

```text
Y_final(w) = Y_chip_inspection(w)
           × Y_device_formation(w)
           × Y_sorting(w)
           × Y_qualification(w)
```

For a displayed population `W`:

```text
Displayed Yield = Σ good_chip_quantity(w) / Σ total_chip_quantity(w), for w in W
```

This is quantity weighting—not an average of wafer percentages.

## Traceability

Each prepared Yield fact has a lineage record containing:

- fictional source domain;
- fictional source record key;
- identity method;
- transformation explanation.

The UI preserves the path:

```text
Yield cell -> stage population -> failure family -> physical wafer -> source-derived rows
```

That path is essential because a manufacturing metric must be explainable to an engineer reviewing
the result.

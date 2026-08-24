# Screenshot Mapping and Acceptance Record

All images were captured by [`tools/capture_screenshots.py`](../tools/capture_screenshots.py) from
the running synthetic Dash application. No private screenshot, image editor, or generated image was
used.

| Public screenshot | Private workflow reference | Workflow represented | Sanitized changes |
| --- | --- | --- | --- |
| [`yield-summary.png`](screenshots/yield-summary.png) | Production Yield matrix | Product/work-order/date filtering, row hierarchy, period cells, selected-cell entry point | Fictional products, stages, dates, values, identifiers, and subtitle |
| [`yield-enhance.png`](screenshots/yield-enhance.png) | Selected-cell Enhance view | Selected-period Pareto, full-range trend, KPI context, physical-wafer scatter | Fictional failure families, wafers, periods, quantities, and calculations |
| [`physical-wafer-scatter.png`](screenshots/physical-wafer-scatter.png) | Physical-wafer Yield scatter | Compare wafer variation and select one wafer for detail | Fictional physical-wafer IDs and Yield values |
| [`targeted-wafer-detail.png`](screenshots/targeted-wafer-detail.png) | Wafer-level detail investigation | Population-first retrieval of one wafer's chip records | Fictional chip numbers, coordinates, results, failures, and timestamps |
| [`sorting-parameter-analysis.png`](screenshots/sorting-parameter-analysis.png) | Sorting parameter preload/Enhance workflow | Separately refreshed parameter Yield summary | Fictional parameter codes, limits, values, and result population |

## Acceptance comparison

The private UI code was inspected for information hierarchy and interaction behavior. The public
version preserves:

- compact blue-gray production styling;
- a table-first summary rather than a generic KPI homepage;
- section and total-row hierarchy;
- horizontal period cells with day/week/month/quarter/year controls;
- selected-cell emphasis followed by an explicit Enhance action;
- Pareto, full-range trend, physical-wafer scatter, and export in the drilldown;
- restrained borders, small typography, and high information density;
- thin loading/progress treatment that preserves the current screen;
- server-side data with lightweight browser state.

Required clean-room differences are fictional names/data, independently written layout/CSS, and the
absence of private navigation, infrastructure, access-control, or configuration details.

## Reproduce the screenshots

Install the development dependencies and Chromium, run the server, then capture:

```powershell
python -m playwright install chromium
python -m manufacturing_analytics.main
python tools/capture_screenshots.py
```

The script selects actual table cells and opens the actual Enhance callback path before capture.

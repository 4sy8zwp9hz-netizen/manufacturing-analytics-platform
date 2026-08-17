"""In-memory analytical views and population-scoped detail retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from manufacturing_analytics.runtime import SnapshotManager, SortingPreload
from manufacturing_analytics.storage import TargetedDetailRepository

PERIOD_MODES = ("Day", "Week", "Month", "Quarter", "Year")


def add_period(frame: pd.DataFrame, mode: str) -> tuple[pd.DataFrame, str]:
    if mode not in PERIOD_MODES:
        raise ValueError(f"Unsupported period mode: {mode}")
    work = frame.copy()
    values = pd.to_datetime(work["event_time"], utc=True)
    if mode == "Day":
        work["period"] = values.dt.strftime("%Y-%m-%d")
    elif mode == "Week":
        work["period"] = values.dt.tz_localize(None).dt.to_period("W-SUN").astype(str)
    elif mode == "Month":
        work["period"] = values.dt.strftime("%Y-%m")
    elif mode == "Quarter":
        work["period"] = values.dt.tz_localize(None).dt.to_period("Q").astype(str)
    else:
        work["period"] = values.dt.strftime("%Y")
    return work, "period"


@dataclass(frozen=True)
class DashboardFilters:
    product_family: str = "All"
    work_order: str = "All"
    wafer_size: str = "All"
    start_date: str | None = None
    end_date: str | None = None
    period_mode: str = "Week"


class YieldAnalytics:
    """Compose dashboard views from the currently published in-memory snapshot."""

    ASSUMPTIONS = {
        "WAFER_INSPECTION": "Good inspected sites / inspected sites",
        "SURFACE_PREPARATION": "Completed physical wafers passing the stage",
        "PATTERN_SEPARATION": "Completed physical wafers passing the stage",
        "PROTECTIVE_FINISH": "Completed physical wafers passing the stage",
        "AUTO_OUTLIER": "Prepared chip population after automated screening",
        "WAFER_TOTAL": "Product of complete wafer-stage component yields",
        "CHIP_INSPECTION": "Latest-revision good chips / inspected chips",
        "DEVICE_FORMATION": "Process result applied to eligible chip quantity",
        "SORTING": "Good sorted chips / inspected chips; process completion date",
        "QUALIFICATION": "Qualified physical wafers / evaluated physical wafers",
        "FINAL_CHIP_YIELD": "Complete qualification cohort; component product",
    }

    def __init__(
        self,
        snapshots: SnapshotManager,
        details: TargetedDetailRepository,
        sorting_preload: SortingPreload,
    ) -> None:
        self.snapshots = snapshots
        self.details = details
        self.sorting_preload = sorting_preload

    def filter_options(self) -> dict[str, list[str]]:
        facts = self.snapshots.get().datasets["yield_fact"]
        return {
            "product_family": sorted(facts["product_family"].dropna().unique().tolist()),
            "work_order": sorted(facts["work_order"].dropna().unique().tolist()),
            "wafer_size": sorted(facts["wafer_size"].dropna().unique().tolist()),
        }

    def date_bounds(self) -> tuple[date, date]:
        times = pd.to_datetime(self.snapshots.get().datasets["yield_fact"]["event_time"], utc=True)
        return times.min().date(), times.max().date()

    def _filtered(self, name: str, filters: DashboardFilters) -> pd.DataFrame:
        frame = self.snapshots.get().datasets[name].copy()
        for column, value in (
            ("product_family", filters.product_family),
            ("work_order", filters.work_order),
            ("wafer_size", filters.wafer_size),
        ):
            if column in frame and value and value != "All":
                frame = frame.loc[frame[column].eq(value)]
        if "event_time" in frame:
            event_time = pd.to_datetime(frame["event_time"], utc=True)
            if filters.start_date:
                frame = frame.loc[event_time >= pd.Timestamp(filters.start_date, tz="UTC")]
                event_time = pd.to_datetime(frame["event_time"], utc=True)
            if filters.end_date:
                end = pd.Timestamp(filters.end_date, tz="UTC") + pd.Timedelta(days=1)
                frame = frame.loc[event_time < end]
        return frame.copy()

    def summary_table(
        self, filters: DashboardFilters, *, max_periods: int = 12
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str]]:
        facts, _ = add_period(self._filtered("yield_fact", filters), filters.period_mode)
        if facts.empty:
            columns = [
                {"name": "Section", "id": "section"},
                {"name": "Process Step", "id": "stage_label"},
                {"name": "Population / Assumption", "id": "assumption"},
            ]
            return [], columns, []
        periods = sorted(facts["period"].dropna().unique().tolist())[-max_periods:]
        grouped = (
            facts.loc[facts["period"].isin(periods)]
            .groupby(
                ["section", "stage_code", "stage_label", "display_order", "period"],
                as_index=False,
            )
            .agg(numerator=("numerator", "sum"), denominator=("denominator", "sum"))
        )
        grouped["yield_rate"] = grouped["numerator"] / grouped["denominator"]
        rows: list[dict[str, Any]] = []
        for keys, group in grouped.groupby(
            ["section", "stage_code", "stage_label", "display_order"], sort=False
        ):
            section, stage_code, stage_label, display_order = keys
            row: dict[str, Any] = {
                "section": section,
                "stage_code": stage_code,
                "stage_label": stage_label,
                "display_order": int(display_order),
                "assumption": self.ASSUMPTIONS.get(stage_code, "Prepared engineering population"),
            }
            by_period = group.set_index("period")
            for period in periods:
                if period in by_period.index:
                    item = by_period.loc[period]
                    if isinstance(item, pd.DataFrame):
                        numerator = item["numerator"].sum()
                        denominator = item["denominator"].sum()
                    else:
                        numerator = item["numerator"]
                        denominator = item["denominator"]
                    row[period] = f"{100 * numerator / denominator:.1f}%"
                else:
                    row[period] = "—"
            rows.append(row)
        rows.sort(key=lambda item: item["display_order"])
        columns = [
            {"name": "Section", "id": "section"},
            {"name": "Process Step", "id": "stage_label"},
            {"name": "Population / Assumption", "id": "assumption"},
            *({"name": period, "id": period} for period in periods),
        ]
        return rows, columns, periods

    def resolve_selection(
        self, active_cell: dict[str, Any] | None, rows: list[dict[str, Any]] | None
    ) -> dict[str, Any] | None:
        if not active_cell or not rows:
            return None
        row_index = int(active_cell.get("row", -1))
        if not 0 <= row_index < len(rows):
            return None
        column_id = str(active_cell.get("column_id") or "")
        if column_id in {"section", "stage_code", "stage_label", "assumption", "display_order"}:
            return None
        row = rows[row_index]
        return {
            "stage_code": row["stage_code"],
            "stage_label": row["stage_label"],
            "section": row["section"],
            "period": column_id,
            "display_value": row.get(column_id, "—"),
        }

    def selected_population(
        self, selection: dict[str, Any], filters: DashboardFilters
    ) -> pd.DataFrame:
        facts, _ = add_period(self._filtered("yield_fact", filters), filters.period_mode)
        return facts.loc[
            facts["stage_code"].eq(selection["stage_code"])
            & facts["period"].eq(selection["period"])
        ].copy()

    def pareto_figure(
        self, selection: dict[str, Any], filters: DashboardFilters, top_n: int = 8
    ) -> go.Figure:
        failures, _ = add_period(self._filtered("failure_fact", filters), filters.period_mode)
        scoped = failures.loc[
            failures["stage_code"].eq(selection["stage_code"])
            & failures["period"].eq(selection["period"])
        ]
        grouped = (
            scoped.groupby("failure_family", as_index=False)["failure_quantity"]
            .sum()
            .sort_values("failure_quantity", ascending=False)
            .head(top_n)
        )
        if grouped.empty:
            return self.empty_figure("No failure population for the selected cell")
        grouped["cumulative"] = (
            grouped["failure_quantity"].cumsum() / grouped["failure_quantity"].sum()
        )
        figure = go.Figure()
        figure.add_bar(
            x=grouped["failure_family"],
            y=grouped["failure_quantity"],
            marker_color="#2f6da8",
            name="Failure quantity",
        )
        figure.add_scatter(
            x=grouped["failure_family"],
            y=100 * grouped["cumulative"],
            yaxis="y2",
            mode="lines+markers",
            line={"color": "#c23b33", "width": 2},
            name="Cumulative %",
        )
        figure.update_layout(
            title=f"Selected-Period Failure Pareto | {selection['period']}",
            yaxis={"title": "Failure quantity"},
            yaxis2={"title": "Cumulative %", "overlaying": "y", "side": "right", "range": [0, 105]},
        )
        return self._style(figure)

    def trend_figure(self, selection: dict[str, Any], filters: DashboardFilters) -> go.Figure:
        facts, _ = add_period(self._filtered("yield_fact", filters), filters.period_mode)
        scoped = facts.loc[facts["stage_code"].eq(selection["stage_code"])]
        grouped = scoped.groupby("period", as_index=False).agg(
            numerator=("numerator", "sum"), denominator=("denominator", "sum")
        )
        grouped["yield_rate"] = 100 * grouped["numerator"] / grouped["denominator"]
        figure = go.Figure(
            go.Scatter(
                x=grouped["period"],
                y=grouped["yield_rate"],
                mode="lines+markers",
                line={"color": "#2f6da8", "width": 2.4},
                marker={"size": 7},
                name="Overall",
            )
        )
        figure.update_layout(
            title="Full Date-Range Yield Trend", yaxis={"title": "Yield %", "range": [0, 102]}
        )
        return self._style(figure)

    def wafer_scatter_figure(
        self, selection: dict[str, Any], filters: DashboardFilters
    ) -> go.Figure:
        population = self.selected_population(selection, filters).sort_values("event_time")
        if population.empty:
            return self.empty_figure("No physical wafers in the selected population")
        figure = go.Figure(
            go.Scatter(
                x=population["physical_wafer_id"],
                y=100 * population["yield_rate"],
                mode="markers",
                marker={
                    "size": 10,
                    "color": 100 * population["yield_rate"],
                    "colorscale": [[0, "#c23b33"], [0.55, "#e2a23a"], [1, "#2f6da8"]],
                    "cmin": max(0, 100 * population["yield_rate"].min() - 1),
                    "cmax": 100,
                    "line": {"color": "#ffffff", "width": 0.8},
                },
                customdata=population[["physical_wafer_id", "work_order", "lot_id"]],
                hovertemplate=(
                    "Physical wafer: %{customdata[0]}<br>Work order: %{customdata[1]}"
                    "<br>Lot: %{customdata[2]}<br>Yield: %{y:.2f}%<extra></extra>"
                ),
            )
        )
        figure.update_layout(
            title="Physical-Wafer Yield Scatter — select a wafer for detail",
            yaxis={"title": "Yield %", "range": [0, 102]},
            xaxis={"title": "Physical wafer", "tickangle": -45},
        )
        return self._style(figure)

    def population_records(
        self, selection: dict[str, Any], filters: DashboardFilters
    ) -> list[dict[str, Any]]:
        population = self.selected_population(selection, filters)
        lineage = self.snapshots.get().datasets["lineage"]
        joined = population.merge(lineage, on="yield_record_id", how="left")
        columns = [
            "physical_wafer_id",
            "work_order",
            "lot_id",
            "product_family",
            "numerator",
            "denominator",
            "yield_rate",
            "failure_family",
            "source_kind",
            "source_record_id",
            "transformation_rule",
        ]
        result = joined[columns].copy()
        result["yield_rate"] = (100 * result["yield_rate"]).round(2)
        return result.sort_values("yield_rate").to_dict("records")

    def targeted_detail(self, stage_code: str, physical_wafer_id: str) -> tuple[pd.DataFrame, str]:
        if stage_code == "SORTING":
            frame = self.details.sorting_parameters([physical_wafer_id])
            columns = [
                "physical_wafer_id",
                "chip_number",
                "parameter",
                "value",
                "lower_limit",
                "upper_limit",
                "passed",
            ]
            return frame[columns], "Targeted Sorting parameter retrieval"
        frame = self.details.chip_detail([physical_wafer_id])
        columns = [
            "physical_wafer_id",
            "chip_number",
            "x",
            "y",
            "passed",
            "failure_family",
            "tested_at",
        ]
        return frame[columns], "Targeted chip-detail retrieval"

    def sorting_preload_figure(self) -> go.Figure:
        summary = self.sorting_preload.summary()
        if summary.empty:
            return self.empty_figure(self.sorting_preload.status()["message"])
        figure = go.Figure(
            go.Bar(
                x=summary["parameter"],
                y=100 * summary["yield_rate"],
                marker_color="#536f8d",
                text=(100 * summary["yield_rate"]).map(lambda value: f"{value:.1f}%"),
                textposition="outside",
            )
        )
        figure.update_layout(
            title="Separately Preloaded Sorting Parameter Yield",
            yaxis={"title": "Parameter yield %", "range": [0, 105]},
        )
        return self._style(figure)

    @staticmethod
    def _style(figure: go.Figure) -> go.Figure:
        figure.update_layout(
            template="plotly_white",
            margin={"l": 52, "r": 45, "t": 48, "b": 48},
            font={"family": "Segoe UI, Arial, sans-serif", "size": 12, "color": "#243247"},
            title={"font": {"size": 15, "color": "#1f2d3d"}, "x": 0.02},
            legend={"orientation": "h", "y": 1.08, "x": 1, "xanchor": "right"},
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            hovermode="closest",
        )
        figure.update_xaxes(showgrid=False, linecolor="#dbe2ea")
        figure.update_yaxes(gridcolor="#e9eef4", zeroline=False, linecolor="#dbe2ea")
        return figure

    @staticmethod
    def empty_figure(message: str) -> go.Figure:
        figure = go.Figure()
        figure.add_annotation(
            text=message,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"color": "#6b7888", "size": 13},
        )
        figure.update_xaxes(visible=False)
        figure.update_yaxes(visible=False)
        return YieldAnalytics._style(figure)

    def truth_metadata(self) -> str:
        snapshot = self.snapshots.get()
        return json.dumps(
            {
                "generation_id": snapshot.generation_id,
                "published_at": snapshot.published_at,
                "statistics": snapshot.statistics,
            },
            indent=2,
        )

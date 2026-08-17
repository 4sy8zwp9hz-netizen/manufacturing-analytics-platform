"""Dash/Plotly production-style Yield Dashboard shell."""

from __future__ import annotations

from typing import Any

import pandas as pd
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update

from manufacturing_analytics.bootstrap import ApplicationServices
from manufacturing_analytics.yield_analytics import PERIOD_MODES, DashboardFilters


def _options(values: list[str], include_all: bool = True) -> list[dict[str, str]]:
    options = [{"label": value, "value": value} for value in values]
    return ([{"label": "All", "value": "All"}] + options) if include_all else options


def _filters(
    product: str,
    work_order: str,
    wafer_size: str,
    start_date: str | None,
    end_date: str | None,
    period_mode: str,
) -> DashboardFilters:
    return DashboardFilters(
        product_family=product or "All",
        work_order=work_order or "All",
        wafer_size=wafer_size or "All",
        start_date=start_date,
        end_date=end_date,
        period_mode=period_mode or "Week",
    )


def create_dash_app(
    services: ApplicationServices,
    *,
    url_base_pathname: str = "/",
) -> Dash:
    prefix = "/" + url_base_pathname.strip("/") + "/" if url_base_pathname != "/" else "/"
    dash_kwargs: dict[str, Any] = {
        "name": __name__,
        "title": services.settings.title,
        "suppress_callback_exceptions": True,
        "assets_folder": "assets",
    }
    if prefix != "/":
        dash_kwargs.update(
            requests_pathname_prefix=prefix,
            routes_pathname_prefix=prefix,
        )
    app = Dash(**dash_kwargs)
    options = services.analytics.filter_options()
    min_date, max_date = services.analytics.date_bounds()

    app.layout = html.Div(
        className="page-shell",
        children=[
            dcc.Location(id="yield-url", refresh=False),
            dcc.Store(id="snapshot-version", data=services.snapshots.get().generation_id),
            dcc.Store(id="selected-cell"),
            dcc.Store(id="view-mode", data="summary"),
            dcc.Interval(
                id="snapshot-poll",
                interval=services.settings.generation_poll_seconds * 1000,
                n_intervals=0,
            ),
            dcc.Download(id="population-download"),
            html.Div(
                className="top-shell",
                children=[
                    html.Div(
                        className="app-header",
                        children=[
                            html.Div(
                                className="brand-block",
                                children=[
                                    html.Div("Synthetic Production Yield", className="brand-title"),
                                    html.Div(
                                        "Clean-room manufacturing intelligence",
                                        className="brand-subtitle",
                                    ),
                                ],
                            ),
                            html.Div(
                                [
                                    html.Span("Yield Review", className="active-view-label"),
                                    html.Span(
                                        "Prepared data + scoped detail",
                                        className="architecture-label",
                                    ),
                                ],
                                className="header-context",
                            ),
                            html.Div(id="refresh-status", className="refresh-status"),
                        ],
                    ),
                    html.Div(
                        className="control-strip",
                        children=[
                            html.Div(
                                [
                                    html.Span("Product", className="inline-label"),
                                    dcc.Dropdown(
                                        id="product-filter",
                                        options=_options(options["product_family"]),
                                        value="All",
                                        clearable=False,
                                        className="compact-dropdown",
                                    ),
                                ],
                                className="inline-control",
                            ),
                            html.Div(
                                [
                                    html.Span("Work order", className="inline-label"),
                                    dcc.Dropdown(
                                        id="work-order-filter",
                                        options=_options(options["work_order"]),
                                        value="All",
                                        clearable=False,
                                        className="compact-dropdown wide",
                                    ),
                                ],
                                className="inline-control",
                            ),
                            html.Div(
                                [
                                    html.Span("Wafer size", className="inline-label"),
                                    dcc.Dropdown(
                                        id="wafer-size-filter",
                                        options=_options(options["wafer_size"]),
                                        value="All",
                                        clearable=False,
                                        className="compact-dropdown",
                                    ),
                                ],
                                className="inline-control",
                            ),
                            html.Div(
                                [
                                    html.Span("Date range", className="inline-label"),
                                    dcc.DatePickerRange(
                                        id="date-filter",
                                        min_date_allowed=min_date,
                                        max_date_allowed=max_date,
                                        start_date=min_date,
                                        end_date=max_date,
                                        display_format="YYYY-MM-DD",
                                    ),
                                ],
                                className="inline-control date-control",
                            ),
                            dcc.RadioItems(
                                id="period-mode",
                                options=[{"label": mode, "value": mode} for mode in PERIOD_MODES],
                                value=services.settings.default_period,
                                className="period-selector",
                                inline=True,
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        id="selection-status", children="Select a period cell"
                                    ),
                                    html.Button(
                                        "Enhance",
                                        id="enhance-button",
                                        className="enhance-button",
                                        disabled=True,
                                    ),
                                    html.Button(
                                        "Refresh data",
                                        id="refresh-button",
                                        className="refresh-button",
                                    ),
                                ],
                                className="action-area",
                            ),
                        ],
                    ),
                    html.Div(id="linear-refresh-indicator", className="linear-refresh-indicator"),
                ],
            ),
            html.Div(
                id="summary-screen",
                className="summary-screen",
                children=[
                    html.Div(
                        className="summary-note",
                        children=[
                            html.Span(
                                "Each row has its own engineering population and denominator.",
                                className="summary-note-primary",
                            ),
                            html.Span(id="sorting-status", className="sorting-status"),
                        ],
                    ),
                    dcc.Loading(
                        type="default",
                        parent_className="table-loading-region",
                        children=dash_table.DataTable(
                            id="yield-table",
                            data=[],
                            columns=[],
                            hidden_columns=["stage_code", "display_order"],
                            active_cell=None,
                            cell_selectable=True,
                            page_action="none",
                            fixed_rows={"headers": True},
                            style_table={
                                "height": "100%",
                                "overflowX": "auto",
                                "overflowY": "auto",
                            },
                            style_data={"cursor": "pointer"},
                        ),
                    ),
                ],
            ),
            html.Div(
                id="drilldown-screen",
                className="drilldown-screen",
                style={"display": "none"},
                children=[
                    html.Div(
                        className="drilldown-header",
                        children=[
                            html.Button("Back to Yield", id="back-button", className="back-button"),
                            html.H3(id="drilldown-title", children="Enhanced Yield Investigation"),
                            html.Div(
                                "Selected cell → population → failures → wafer → source rows",
                                className="trace-path",
                            ),
                        ],
                    ),
                    html.Div(
                        className="drilldown-content",
                        children=[
                            html.Div(id="drilldown-kpis", className="kpi-strip"),
                            html.Div(
                                className="chart-grid",
                                children=[
                                    html.Div(
                                        dcc.Loading(dcc.Graph(id="pareto-figure")),
                                        className="analysis-panel selected-period-loading-region",
                                    ),
                                    html.Div(
                                        dcc.Graph(id="trend-figure"), className="analysis-panel"
                                    ),
                                ],
                            ),
                            html.Div(
                                className="analysis-panel",
                                children=[
                                    dcc.Loading(dcc.Graph(id="wafer-scatter-figure")),
                                    html.Div(
                                        "Select a physical wafer to retrieve only its "
                                        "high-volume detail.",
                                        className="panel-help",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="chart-grid lower-grid",
                                children=[
                                    html.Div(
                                        [
                                            dcc.Graph(id="sorting-preload-figure"),
                                            html.Div(
                                                id="sorting-preload-note", className="panel-help"
                                            ),
                                        ],
                                        className="analysis-panel",
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.H4("Selected population and lineage"),
                                                    html.Button(
                                                        "Export population",
                                                        id="export-button",
                                                        className="export-button",
                                                    ),
                                                ],
                                                className="panel-title-row",
                                            ),
                                            dash_table.DataTable(
                                                id="population-table",
                                                data=[],
                                                columns=[],
                                                page_size=10,
                                                style_table={"overflowX": "auto"},
                                            ),
                                        ],
                                        className="analysis-panel population-panel",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="analysis-panel detail-panel",
                                children=[
                                    html.H4("Population-scoped high-volume detail"),
                                    html.Div(id="targeted-detail-status", className="panel-help"),
                                    dash_table.DataTable(
                                        id="targeted-detail-table",
                                        data=[],
                                        columns=[],
                                        page_size=12,
                                        style_table={"overflowX": "auto"},
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    @app.server.get("/health")
    def health() -> dict[str, Any]:
        snapshot = services.snapshots.get()
        return {
            "status": "ok",
            "generation_id": snapshot.generation_id,
            "refresh": services.refresh.status()["state"],
            "sorting_preload": services.sorting_preload.status()["state"],
        }

    @app.callback(
        Output("snapshot-version", "data"),
        Output("refresh-status", "children"),
        Output("sorting-status", "children"),
        Output("linear-refresh-indicator", "className"),
        Input("snapshot-poll", "n_intervals"),
    )
    def poll_status(_: int) -> tuple[str, str, str, str]:
        snapshot = services.snapshots.get()
        refresh = services.refresh.status()
        sorting = services.sorting_preload.status()
        refresh_text = f"{refresh['message']} | active {snapshot.generation_id}" + (
            f" | warning: {refresh['last_error']}" if refresh.get("last_error") else ""
        )
        indicator = (
            "linear-refresh-indicator active"
            if refresh["state"] == "refreshing"
            else "linear-refresh-indicator"
        )
        return snapshot.generation_id, refresh_text, sorting["message"], indicator

    @app.callback(
        Output("yield-table", "data"),
        Output("yield-table", "columns"),
        Output("yield-table", "style_cell_conditional"),
        Output("yield-table", "style_data_conditional"),
        Input("snapshot-version", "data"),
        Input("product-filter", "value"),
        Input("work-order-filter", "value"),
        Input("wafer-size-filter", "value"),
        Input("date-filter", "start_date"),
        Input("date-filter", "end_date"),
        Input("period-mode", "value"),
    )
    def render_summary(
        _: str,
        product: str,
        work_order: str,
        wafer_size: str,
        start_date: str,
        end_date: str,
        period_mode: str,
    ) -> tuple[
        list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]]
    ]:
        rows, columns, _periods = services.analytics.summary_table(
            _filters(product, work_order, wafer_size, start_date, end_date, period_mode),
            max_periods=services.settings.default_weeks,
        )
        cell_styles = [
            {
                "if": {"column_id": "section"},
                "width": "145px",
                "textAlign": "left",
                "fontWeight": 700,
            },
            {
                "if": {"column_id": "stage_label"},
                "width": "210px",
                "textAlign": "left",
                "fontWeight": 650,
            },
            {
                "if": {"column_id": "assumption"},
                "width": "310px",
                "textAlign": "left",
                "fontSize": 11,
                "color": "#5f6d7d",
            },
        ]
        row_styles = [
            {
                "if": {"filter_query": "{stage_code} = 'WAFER_TOTAL'"},
                "backgroundColor": "#edf3f8",
                "fontWeight": 700,
            },
            {
                "if": {"filter_query": "{stage_code} = 'FINAL_CHIP_YIELD'"},
                "backgroundColor": "#dce9f5",
                "fontWeight": 750,
                "borderTop": "2px solid #5f83a5",
            },
            {
                "if": {"filter_query": "{stage_code} = 'QUALIFICATION'"},
                "backgroundColor": "#f6f4ed",
            },
            {
                "if": {"state": "active"},
                "backgroundColor": "#dbeafe",
                "border": "2px solid #2563eb",
            },
        ]
        return rows, columns, cell_styles, row_styles

    @app.callback(
        Output("selected-cell", "data"),
        Output("selection-status", "children"),
        Output("enhance-button", "disabled"),
        Input("yield-table", "active_cell"),
        State("yield-table", "data"),
    )
    def select_cell(
        active_cell: dict[str, Any] | None, rows: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, str, bool]:
        selected = services.analytics.resolve_selection(active_cell, rows)
        if selected is None:
            return None, "Select a period cell", True
        return (
            selected,
            f"{selected['stage_label']} | {selected['period']} | {selected['display_value']}",
            False,
        )

    @app.callback(
        Output("summary-screen", "style"),
        Output("drilldown-screen", "style"),
        Output("view-mode", "data"),
        Input("enhance-button", "n_clicks"),
        Input("back-button", "n_clicks"),
        State("selected-cell", "data"),
        prevent_initial_call=True,
    )
    def change_view(
        _enhance: int | None, _back: int | None, selected: dict[str, Any] | None
    ) -> tuple[dict[str, str], dict[str, str], str]:
        if ctx.triggered_id == "enhance-button" and selected:
            return {"display": "none"}, {"display": "flex"}, "drilldown"
        return {"display": "flex"}, {"display": "none"}, "summary"

    @app.callback(
        Output("drilldown-title", "children"),
        Output("drilldown-kpis", "children"),
        Output("pareto-figure", "figure"),
        Output("trend-figure", "figure"),
        Output("wafer-scatter-figure", "figure"),
        Output("sorting-preload-figure", "figure"),
        Output("sorting-preload-note", "children"),
        Output("population-table", "data"),
        Output("population-table", "columns"),
        Input("selected-cell", "data"),
        Input("snapshot-version", "data"),
        State("product-filter", "value"),
        State("work-order-filter", "value"),
        State("wafer-size-filter", "value"),
        State("date-filter", "start_date"),
        State("date-filter", "end_date"),
        State("period-mode", "value"),
    )
    def render_drilldown(
        selected: dict[str, Any] | None,
        _: str,
        product: str,
        work_order: str,
        wafer_size: str,
        start_date: str,
        end_date: str,
        period_mode: str,
    ) -> tuple[Any, ...]:
        if not selected:
            empty = services.analytics.empty_figure("Select a yield period cell")
            return (
                "Enhanced Yield Investigation",
                [],
                empty,
                empty,
                empty,
                services.analytics.sorting_preload_figure(),
                services.sorting_preload.status()["message"],
                [],
                [],
            )
        filters = _filters(product, work_order, wafer_size, start_date, end_date, period_mode)
        population = services.analytics.selected_population(selected, filters)
        numerator = population["numerator"].sum()
        denominator = population["denominator"].sum()
        yield_rate = 100 * numerator / denominator if denominator else 0.0
        kpis = [
            html.Div(
                [html.Span("Selected yield"), html.Strong(f"{yield_rate:.2f}%")],
                className="kpi-card",
            ),
            html.Div(
                [
                    html.Span("Physical wafers"),
                    html.Strong(f"{population['physical_wafer_id'].nunique():,}"),
                ],
                className="kpi-card",
            ),
            html.Div(
                [html.Span("Good / total"), html.Strong(f"{numerator:,.0f} / {denominator:,.0f}")],
                className="kpi-card",
            ),
            html.Div(
                [html.Span("Selected period"), html.Strong(selected["period"])],
                className="kpi-card",
            ),
        ]
        records = services.analytics.population_records(selected, filters)
        columns = (
            [{"name": name.replace("_", " ").title(), "id": name} for name in records[0]]
            if records
            else []
        )
        sorting_status = services.sorting_preload.status()
        return (
            f"{selected['stage_label']} | {selected['period']}",
            kpis,
            services.analytics.pareto_figure(selected, filters, services.settings.top_pareto_items),
            services.analytics.trend_figure(selected, filters),
            services.analytics.wafer_scatter_figure(selected, filters),
            services.analytics.sorting_preload_figure(),
            sorting_status["message"],
            records,
            columns,
        )

    @app.callback(
        Output("targeted-detail-table", "data"),
        Output("targeted-detail-table", "columns"),
        Output("targeted-detail-status", "children"),
        Input("wafer-scatter-figure", "clickData"),
        State("selected-cell", "data"),
        prevent_initial_call=True,
    )
    def load_targeted_detail(
        click_data: dict[str, Any] | None, selected: dict[str, Any] | None
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], str]:
        if not click_data or not selected:
            return [], [], "Select one physical wafer in the scatter plot."
        wafer = str(click_data["points"][0]["customdata"][0])
        frame, label = services.analytics.targeted_detail(selected["stage_code"], wafer)
        records = frame.head(500).to_dict("records")
        columns = [{"name": name.replace("_", " ").title(), "id": name} for name in frame.columns]
        return (
            records,
            columns,
            f"{label}: {len(frame):,} rows for {wafer}; no unrelated wafer detail was read.",
        )

    @app.callback(
        Output("population-download", "data"),
        Input("export-button", "n_clicks"),
        State("population-table", "data"),
        State("selected-cell", "data"),
        prevent_initial_call=True,
    )
    def export_population(
        clicks: int | None,
        records: list[dict[str, Any]],
        selected: dict[str, Any] | None,
    ) -> Any:
        if not clicks or not records or not selected:
            return no_update
        filename = f"synthetic_{selected['stage_code'].lower()}_{selected['period']}.csv"
        return dcc.send_data_frame(pd.DataFrame(records).to_csv, filename, index=False)

    @app.callback(
        Output("refresh-button", "children"),
        Input("refresh-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def request_refresh(clicks: int | None) -> str:
        if not clicks:
            return "Refresh data"
        services.refresh.refresh_async(
            preload_delay_seconds=services.settings.sorting_background_delay_seconds
        )
        return "Refresh requested"

    return app

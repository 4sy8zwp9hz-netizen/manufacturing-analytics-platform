"""HTTP routes for the connected manufacturing investigation workflow."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from manufacturing_analytics.analytics.models import AnalyticsFilters
from manufacturing_analytics.analytics.process_service import ProcessAnalyticsService
from manufacturing_analytics.analytics.service import AnalyticsService
from manufacturing_analytics.data.analytics_repository import AnalyticsRepository

TEMPLATES = Jinja2Templates(directory=Path(__file__).with_name("templates"))
router = APIRouter()
PLACEHOLDER_PAGES = {}


def analytics_filters(
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    product_code: Annotated[str | None, Query()] = None,
    work_order_id: Annotated[str | None, Query()] = None,
    selected_lot: Annotated[str | None, Query(alias="lot")] = None,
    operation_code: Annotated[str | None, Query()] = None,
    tool_id: Annotated[str | None, Query()] = None,
) -> AnalyticsFilters:
    try:
        return AnalyticsFilters(
            date_from=date_from,
            date_to=date_to,
            product_code=product_code,
            work_order_id=work_order_id,
            lot_id=selected_lot,
            operation_code=operation_code,
            tool_id=tool_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _analytics(request: Request) -> AnalyticsService:
    return request.app.state.analytics


def _options(request: Request) -> dict[str, list[dict[str, object]]]:
    repository: AnalyticsRepository = _analytics(request).repository
    return repository.filter_options()


def _process_analytics(request: Request) -> ProcessAnalyticsService:
    return request.app.state.process_analytics


def _platform_filters(
    product: str | None = None,
    work_order: str | None = None,
    wafer: str | None = None,
    period: str | None = None,
) -> dict[str, str | None]:
    return {"product": product, "work_order": work_order, "wafer": wafer, "period": period}


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    filters = _platform_filters()
    return TEMPLATES.TemplateResponse(
        request=request,
        name="index.html",
        context={"model": request.app.state.yield_platform.dashboard(filters), "filters": filters},
    )


@router.get("/analytics/yield-dashboard", response_class=HTMLResponse)
def yield_dashboard(
    request: Request,
    product: str | None = None,
    work_order: str | None = None,
    wafer: str | None = None,
    period: str | None = None,
    time_grain: str = "month",
) -> HTMLResponse:
    filters = _platform_filters(product, work_order, wafer, period)
    if time_grain not in {"date", "week", "month"}:
        raise HTTPException(status_code=422, detail="time_grain must be date, week, or month")
    return TEMPLATES.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "model": request.app.state.yield_platform.dashboard(filters, time_grain),
            "filters": filters,
        },
    )


@router.get("/platform/population", response_class=HTMLResponse)
def analytical_population(
    request: Request,
    stage: str,
    product: str | None = None,
    work_order: str | None = None,
    wafer: str | None = None,
    period: str | None = None,
    format: str | None = None,
) -> Response:
    filters = _platform_filters(product, work_order, wafer, period)
    rows = request.app.state.yield_platform.repository.population(stage, filters)
    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{stage.lower()}-population.csv"'
            },
        )
    return TEMPLATES.TemplateResponse(
        request=request,
        name="analytical_population.html",
        context={"stage": stage, "rows": rows, "filters": filters},
    )


@router.get("/platform/wafers/{wafer_id}", response_class=HTMLResponse)
def platform_wafer_trace(request: Request, wafer_id: str) -> HTMLResponse:
    model = request.app.state.yield_platform.repository.wafer_trace(wafer_id)
    if model is None:
        return TEMPLATES.TemplateResponse(
            request=request,
            name="not_found.html",
            context={"entity": "canonical wafer", "identifier": wafer_id},
            status_code=404,
        )
    return TEMPLATES.TemplateResponse(
        request=request, name="platform_wafer.html", context={"model": model}
    )


@router.get("/platform/generation", response_class=HTMLResponse)
def generation_detail(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request=request,
        name="generation_detail.html",
        context={"metadata": request.app.state.yield_platform.repository.metadata()},
    )


@router.get("/analytics/yield-overview", response_class=HTMLResponse)
def yield_overview(
    request: Request,
    filters: Annotated[AnalyticsFilters, Depends(analytics_filters)],
) -> HTMLResponse:
    model = _analytics(request).yield_overview(filters)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="yield_overview.html",
        context={"model": model, "filters": filters, "options": _options(request)},
    )


@router.get("/analytics/wafer-analysis", response_class=HTMLResponse)
def wafer_analysis(
    request: Request,
    filters: Annotated[AnalyticsFilters, Depends(analytics_filters)],
) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request=request,
        name="wafer_analysis.html",
        context={
            "wafers": _analytics(request).wafer_index(filters),
            "filters": filters,
            "options": _options(request),
        },
    )


@router.get("/analytics/pareto-analysis", response_class=HTMLResponse)
def pareto_analysis(
    request: Request,
    filters: Annotated[AnalyticsFilters, Depends(analytics_filters)],
) -> HTMLResponse:
    pareto = _analytics(request).pareto(filters)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="pareto.html",
        context={
            "pareto": pareto,
            "pareto_chart": [asdict(item) for item in pareto],
            "filters": filters,
            "options": _options(request),
        },
    )


@router.get("/lots/{lot_id}", response_class=HTMLResponse)
def lot_detail(
    request: Request,
    lot_id: str,
    filters: Annotated[AnalyticsFilters, Depends(analytics_filters)],
) -> HTMLResponse:
    model = _analytics(request).lot_investigation(lot_id)
    if model is None:
        return TEMPLATES.TemplateResponse(
            request=request,
            name="not_found.html",
            context={"entity": "lot", "identifier": lot_id},
            status_code=404,
        )
    return TEMPLATES.TemplateResponse(
        request=request,
        name="lot_detail.html",
        context={"model": model, "filters": filters},
    )


@router.get("/wafers/{wafer_id}", response_class=HTMLResponse)
def wafer_detail(
    request: Request,
    wafer_id: str,
    filters: Annotated[AnalyticsFilters, Depends(analytics_filters)],
) -> HTMLResponse:
    model = _analytics(request).wafer_investigation(wafer_id)
    if model is None:
        return TEMPLATES.TemplateResponse(
            request=request,
            name="not_found.html",
            context={"entity": "wafer", "identifier": wafer_id},
            status_code=404,
        )
    return TEMPLATES.TemplateResponse(
        request=request,
        name="wafer_detail.html",
        context={"model": model, "filters": filters},
    )


@router.get("/analytics/process-spc", response_class=HTMLResponse)
def process_spc(
    request: Request,
    filters: Annotated[AnalyticsFilters, Depends(analytics_filters)],
    characteristic: Annotated[str, Query()] = "ETCH_DEPTH",
    subgroup_method: Annotated[str, Query()] = "INDIVIDUALS",
) -> HTMLResponse:
    service = _process_analytics(request)
    try:
        model = service.process_monitor(characteristic, filters, subgroup_method)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    options = _options(request)
    options["characteristics"] = service.process_repository.characteristics()
    return TEMPLATES.TemplateResponse(
        request=request,
        name="process_spc.html",
        context={
            "model": model,
            "filters": filters,
            "options": options,
            "characteristic": characteristic,
            "subgroup_method": subgroup_method,
        },
    )


@router.get("/analytics/manufacturing-operations", response_class=HTMLResponse)
def manufacturing_operations(
    request: Request,
    filters: Annotated[AnalyticsFilters, Depends(analytics_filters)],
) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request=request,
        name="manufacturing_operations.html",
        context={
            "model": _process_analytics(request).operations_flow(filters),
            "filters": filters,
            "options": _options(request),
        },
    )


@router.get("/analytics/data-quality", response_class=HTMLResponse)
def data_quality(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request=request,
        name="data_quality.html",
        context={"model": _process_analytics(request).data_quality()},
    )


@router.get("/analytics/{page}", response_class=HTMLResponse)
def placeholder(request: Request, page: str) -> HTMLResponse:
    title, description = PLACEHOLDER_PAGES.get(
        page, ("Analytics", "This module is planned for a future phase.")
    )
    return TEMPLATES.TemplateResponse(
        request=request,
        name="placeholder.html",
        context={"title": title, "description": description},
        status_code=200 if page in PLACEHOLDER_PAGES else 404,
    )


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    request.app.state.database.scalar("SELECT 1")
    generation_id = request.app.state.generation_store.current_generation_id()
    return {"status": "ok", "generation_id": generation_id or "unavailable"}

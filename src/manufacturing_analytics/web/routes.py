"""HTTP routes for the connected manufacturing investigation workflow."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from manufacturing_analytics.analytics.models import AnalyticsFilters
from manufacturing_analytics.analytics.service import AnalyticsService
from manufacturing_analytics.data.analytics_repository import AnalyticsRepository
from manufacturing_analytics.data.repositories import ManufacturingRepository

TEMPLATES = Jinja2Templates(directory=Path(__file__).with_name("templates"))
router = APIRouter()
PLACEHOLDER_PAGES = {
    "process-spc": ("Process / SPC", "Monitor process stability and control limits."),
    "manufacturing-operations": (
        "Manufacturing Operations",
        "Explore route cycle time, queue time, and tool utilization.",
    ),
}


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


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    repository: ManufacturingRepository = request.app.state.repository
    return TEMPLATES.TemplateResponse(
        request=request,
        name="index.html",
        context={"summary": repository.summary(), "lots": repository.recent_lots()},
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
    return {"status": "ok"}

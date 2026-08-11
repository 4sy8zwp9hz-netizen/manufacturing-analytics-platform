"""Page routes for the initial application shell."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from manufacturing_analytics.data.repositories import ManufacturingRepository

TEMPLATES = Jinja2Templates(directory=Path(__file__).with_name("templates"))
router = APIRouter()
PAGES = {
    "yield-overview": ("Yield Overview", "Track wafer and lot yield over time."),
    "wafer-analysis": ("Wafer Analysis", "Investigate spatial patterns and wafer maps."),
    "pareto-analysis": ("Pareto Analysis", "Rank synthetic defect categories by impact."),
    "process-spc": ("Process / SPC", "Monitor process stability and control limits."),
    "manufacturing-operations": (
        "Manufacturing Operations",
        "Explore lots, routes, operations, and tool history.",
    ),
}


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    repository: ManufacturingRepository = request.app.state.repository
    return TEMPLATES.TemplateResponse(
        request=request,
        name="index.html",
        context={"summary": repository.summary(), "lots": repository.recent_lots()},
    )


@router.get("/analytics/{page}", response_class=HTMLResponse)
def placeholder(request: Request, page: str) -> HTMLResponse:
    title, description = PAGES.get(
        page, ("Analytics", "This module is planned for a future phase.")
    )
    return TEMPLATES.TemplateResponse(
        request=request,
        name="placeholder.html",
        context={"title": title, "description": description},
        status_code=200 if page in PAGES else 404,
    )


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    request.app.state.database.scalar("SELECT 1")
    return {"status": "ok"}

"""Capture README screenshots from a running local Dash application."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "docs" / "screenshots"


def select_stage(page, label: str) -> None:
    row = page.locator("#yield-table tr").filter(has_text=label).first
    row.locator("td").last.click()
    page.locator("#enhance-button").click()
    page.locator("#drilldown-screen").wait_for(state="visible")
    page.locator("#pareto-figure .main-svg").first.wait_for(state="visible")


def main() -> None:
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 950}, device_scale_factor=1)
        page.goto("http://127.0.0.1:8050", wait_until="networkidle")
        page.locator("#yield-table tr").filter(has_text="Chip Inspection").first.wait_for()
        page.set_viewport_size({"width": 1600, "height": 650})
        page.screenshot(path=SCREENSHOTS / "yield-summary.png", full_page=True)

        page.set_viewport_size({"width": 1600, "height": 950})
        page.locator("#product-filter").click()
        page.get_by_text("NOVA-A", exact=True).click()
        page.wait_for_timeout(500)
        select_stage(page, "Chip Inspection")
        page.screenshot(path=SCREENSHOTS / "yield-enhance.png", full_page=True)
        scatter_panel = page.locator("#wafer-scatter-figure").locator("xpath=..")
        scatter_panel.screenshot(path=SCREENSHOTS / "physical-wafer-scatter.png")
        point = page.locator("#wafer-scatter-figure .point").first
        point_box = point.bounding_box()
        if point_box is None:
            raise RuntimeError("Physical-wafer scatter point is not visible")
        page.mouse.click(
            point_box["x"] + point_box["width"] / 2,
            point_box["y"] + point_box["height"] / 2,
        )
        page.locator("#targeted-detail-status").filter(has_text="rows for").wait_for()
        detail_panel = page.locator("#targeted-detail-table").locator("xpath=..")
        detail_panel.screenshot(path=SCREENSHOTS / "targeted-wafer-detail.png")

        page.locator("#back-button").click()
        page.locator("#summary-screen").wait_for(state="visible")
        select_stage(page, "Sorting Yield")
        page.locator("#sorting-preload-figure").locator("xpath=..").screenshot(
            path=SCREENSHOTS / "sorting-parameter-analysis.png"
        )
        browser.close()


if __name__ == "__main__":
    main()

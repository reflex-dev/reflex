"""AG Grid regressions driven through the installed reflex_app pytest fixture."""

import csv
import io
import json
import re

import pytest
from playwright.sync_api import Locator, Page, expect

from reflex_enterprise.testing import ReflexApp


@pytest.fixture(autouse=True)
def browser_errors(page: Page):
    """Fail on runtime exceptions and AG Grid configuration/version errors."""
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            errors.append(message.text)
            if message.type in {"error", "warning"}
            and re.search(r"AG (Grid|Charts):", message.text)
            else None
        ),
    )
    yield
    # Unlicensed enterprise features emit a separate license banner; no key is
    # needed to exercise them locally. Configuration/version errors still fail.
    assert not errors, "\n".join(errors)


def cell(page: Page, row: int, column: str) -> Locator:
    # Row/column attributes survive the v36 scrolling and pinning DOM changes.
    return page.locator(f'.ag-row[row-index="{row}"] [col-id="{column}"]')


@pytest.fixture
def inventory(reflex_app: ReflexApp, page: Page) -> Page:
    page.goto(reflex_app.url)
    expect(page.locator("#ready")).to_have_text("true", timeout=30_000)
    expect(cell(page, 0, "name")).to_have_text("Alpha")
    return page


def test_render_sort_filter_and_paginate(inventory: Page):
    page = inventory
    expect(cell(page, 0, "quantity")).to_have_text("3 units")
    expect(page.locator('.ag-row[row-index="t-0"] [col-id="name"]')).to_have_text(
        "Pinned"
    )
    page.get_by_role("button", name="Next Page", exact=True).click()
    expect(cell(page, 2, "name")).to_have_text("Gamma")
    page.get_by_role("button", name="First Page", exact=True).click()
    page.locator('.ag-header-cell[col-id="quantity"] .ag-header-cell-text').click()
    expect(cell(page, 0, "name")).to_have_text("Beta")
    expect(cell(page, 1, "name")).to_have_text("Delta")

    page.locator('.ag-floating-filter[col-id="name"] input').fill("Alpha")
    expect(cell(page, 0, "name")).to_have_text("Alpha")
    expect(page.locator('.ag-row[row-index="1"]')).to_have_count(0)
    expect(page.locator("#filter-event")).to_contain_text('"col_ids": ["name"]')


def test_edit_event_and_state_update(inventory: Page):
    page = inventory
    quantity = cell(page, 0, "quantity")
    quantity.dblclick()
    quantity.locator("input").fill("7")
    quantity.locator("input").press("Enter")
    expect(page.locator("#edit")).to_contain_text('"newValue": 7')
    assert json.loads(page.locator("#edit").inner_text()) == {
        "rowIndex": 0,
        "field": "quantity",
        "newValue": 7,
        "node_id": "a",
    }
    expect(quantity).to_have_text("7 units")
    page.get_by_role("button", name="Replace rows", exact=True).click()
    expect(cell(page, 0, "name")).to_have_text("Echo")
    expect(cell(page, 0, "quantity")).to_have_text("9 units")
    expect(page.locator('.ag-row[row-index="1"]')).to_have_count(0)


def test_selection_events_and_python_api(inventory: Page):
    page = inventory
    page.locator('.ag-row[row-index="0"]').get_by_role("checkbox").check()
    expect(page.locator("#selected")).to_have_text('["a"]')
    page.get_by_role("button", name="Select all", exact=True).click()
    expect(page.locator("#selected")).to_have_text('["a", "b", "c", "d"]')
    page.get_by_role("button", name="Deselect all", exact=True).click()
    expect(page.locator("#selected")).to_have_text("[]")
    page.get_by_role("button", name="Select Beta", exact=True).click()
    expect(page.locator("#selected")).to_have_text('["b"]')
    expect(page.locator('.ag-row[row-index="1"]')).to_have_attribute(
        "aria-selected", "true"
    )


@pytest.mark.parametrize("suppressed", [False, True])
def test_no_matching_rows_overlay(reflex_app: ReflexApp, page: Page, suppressed: bool):
    page.goto(f"{reflex_app.url}/suppress-overlay" if suppressed else reflex_app.url)
    expect(page.locator("#ready")).to_have_text("true", timeout=30_000)
    page.get_by_placeholder("Quick filter").fill("missing")
    expect(page.locator('.ag-row[row-index="0"]')).to_have_count(0)
    overlay = page.get_by_text("No Matching Rows", exact=True)
    if suppressed:
        expect(overlay).not_to_be_visible()
    else:
        expect(overlay).to_be_visible()
    page.get_by_placeholder("Quick filter").fill("")
    expect(cell(page, 0, "name")).to_have_text("Alpha")


def test_loading_overlay_api(inventory: Page):
    page = inventory
    page.get_by_role("button", name="Show loading", exact=True).click()
    expect(page.get_by_text("Loading...", exact=True)).to_be_visible()
    page.get_by_role("button", name="Hide loading", exact=True).click()
    expect(page.get_by_text("Loading...", exact=True)).not_to_be_visible()
    expect(cell(page, 0, "name")).to_have_text("Alpha")


@pytest.mark.parametrize("theme", ["quartz", "alpine", "balham", "material"])
def test_legacy_themes(inventory: Page, theme: str):
    page = inventory
    page.locator("#theme").click()
    page.get_by_role("option", name=theme, exact=True).click()
    themed_grid = page.locator(f'[class*="ag-theme-{theme}"]').first
    expect(themed_grid).to_be_visible()
    # Check actual stylesheet layout, not just the presence of a theme class.
    expect(cell(page, 0, "name")).to_be_visible()
    assert (
        cell(page, 0, "name").evaluate("el => el.getBoundingClientRect().height") > 20
    )
    assert themed_grid.evaluate(
        "el => getComputedStyle(el).getPropertyValue('--ag-row-height').trim()"
    )


def test_csv_export(inventory: Page):
    page = inventory
    with page.expect_download() as download:
        page.get_by_role("button", name="Export CSV", exact=True).click()
    downloaded = download.value.path()
    assert downloaded is not None
    rows = list(csv.reader(io.StringIO(downloaded.read_text(encoding="utf-8-sig"))))
    assert any("Alpha" in row and "3 units" in row for row in rows)
    assert any("Delta" in row and "2 units" in row for row in rows)


def test_enterprise_grouping(reflex_app: ReflexApp, page: Page):
    page.goto(f"{reflex_app.url}/grouping")
    expect(cell(page, 0, "ag-Grid-AutoColumn")).to_contain_text("Tools")
    expect(cell(page, 0, "quantity")).to_have_text("4")
    cell(page, 0, "ag-Grid-AutoColumn").locator(".ag-group-contracted").click()
    expect(cell(page, 1, "name")).to_have_text("Alpha")
    expect(cell(page, 2, "name")).to_have_text("Beta")


def test_integrated_chart(reflex_app: ReflexApp, page: Page):
    page.goto(f"{reflex_app.url}/charts")
    expect(cell(page, 0, "name")).to_have_text("Alpha")
    page.get_by_role("button", name="Create chart", exact=True).click()
    expect(page.locator(".ag-chart canvas").first).to_be_visible(timeout=15_000)
    # A populated chart exposes its series to assistive technology.
    expect(
        page.locator(".ag-chart").get_by_role(
            "figure", name="chart, 1 series", exact=True
        )
    ).to_be_visible()


@pytest.mark.parametrize("route", ["infinite", "server-side"])
def test_remote_datasources(reflex_app: ReflexApp, page: Page, route: str):
    page.goto(f"{reflex_app.url}/{route}")
    expect(cell(page, 0, "name")).to_have_text("Alpha", timeout=30_000)
    page.get_by_role("button", name="Next Page", exact=True).click()
    expect(cell(page, 2, "name")).to_have_text("Gamma")
    page.get_by_role("button", name="First Page", exact=True).click()
    page.locator('.ag-header-cell[col-id="quantity"] .ag-header-cell-text').click()
    expect(cell(page, 0, "name")).to_have_text("Beta")
    expect(cell(page, 1, "name")).to_have_text("Delta")

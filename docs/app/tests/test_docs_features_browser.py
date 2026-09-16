"""Browser regressions for imported docs features; set REFLEX_DOCS_PREVIEW_URL."""

import os

import pytest
from playwright.sync_api import Page, expect

PREVIEW_URL = os.environ.get("REFLEX_DOCS_PREVIEW_URL", "")
pytestmark = pytest.mark.skipif(
    not PREVIEW_URL, reason="Requires a running docs preview"
)


def test_agent_file_links_respect_docs_mount(page: Page):
    """The router adds the docs prefix exactly once to agent-file links."""
    page.goto(f"{PREVIEW_URL}/docs/getting-started/introduction/")
    expect(page.locator('a[href="/docs/llms.txt"]')).to_have_count(1)
    page.get_by_role("button", name="Copy page options").click()
    link = page.get_by_role("link", name="llms-full.txt", exact=False)
    expect(link).to_have_attribute("href", "/docs/llms-full.txt")
    response = page.request.get(f"{PREVIEW_URL}/docs/llms-full.txt")
    assert response.status == 200
    assert "# Reflex Documentation" in response.text()


@pytest.mark.parametrize("width", [375, 1440])
def test_ai_overview_choices_and_landing_actions(page: Page, width: int):
    """Both homepage actions and AI workflow choices navigate using one docs prefix."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/")
    page.get_by_role("link", name="Build with AI", exact=True).last.click()
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/ai/")
    for label, destination in (
        ("Use Reflex Build", "/docs/ai/overview/what-is-reflex-build/"),
        ("Bring your own agent", "/docs/ai/integrations/agent-toolkit/"),
    ):
        page.goto(f"{PREVIEW_URL}/docs/ai/")
        choice = page.get_by_role("link", name=label, exact=True)
        expect(choice).to_have_attribute("href", destination)
        choice.focus()
        page.keyboard.press("Enter")
        expect(page).to_have_url(f"{PREVIEW_URL}{destination}")
    page.goto(f"{PREVIEW_URL}/docs/")
    page.get_by_role("link", name="Explore Framework", exact=True).click()
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/getting-started/introduction/")


def test_integration_cards_have_single_link_and_hydrate(page: Page):
    """Cards avoid nested interactive markup and keep their filter working."""
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{PREVIEW_URL}/docs/ai/integrations/overview/", wait_until="networkidle")
    cards = page.locator("a.group").filter(has_text="Learn more")
    total = cards.count()
    assert total > 0
    expect(cards.locator("a, button")).to_have_count(0)
    page.get_by_role("button", name="Authentication", exact=True).click()
    expect(cards.filter(visible=True)).not_to_have_count(total)
    assert not errors


@pytest.mark.parametrize("width", [375, 1440])
def test_treemap_preview_loads_with_reserved_space(page: Page, width: int):
    """Bundled preview artwork loads inside a stable aspect-ratio card."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/library/graphing/charts/")
    image = page.locator('img[src*="/charts/light/treemap.svg"]')
    image.scroll_into_view_if_needed()
    expect(image).to_be_visible()
    page.wait_for_function(
        "[...document.images].some(el => el.src.includes('/charts/light/treemap.svg') && el.complete && el.naturalWidth > 0)"
    )
    assert (
        image.locator("..").evaluate("el => getComputedStyle(el).aspectRatio")
        == "320 / 232"
    )


@pytest.mark.parametrize("width", [1024, 1440])
def test_ai_overview_keeps_desktop_content_gutters(page: Page, width: int):
    """Hiding breadcrumbs must not leave the article against the sidebar."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/ai/")
    article = page.locator("main article")
    expect(article).to_be_visible()
    padding = article.locator("../..").evaluate(
        "element => parseFloat(getComputedStyle(element).paddingLeft)"
    )
    assert padding >= 32
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_sidebar_category_icons_align_with_section_headings(page: Page):
    """Top-level category icons share the section heading's left edge."""
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/ai/")
    sidebar = page.locator("#sidebar-container")
    heading = sidebar.get_by_role("heading", name="Overview", exact=True)
    expect(heading).to_be_visible()
    heading_x = heading.bounding_box()["x"]
    for name in ("Build with AI", "AI Builder", "Agent Toolkit"):
        icon = (
            sidebar
            .get_by_role("link", name=f"Navigate to {name}", exact=True)
            .locator("svg")
            .first
        )
        assert abs(icon.bounding_box()["x"] - heading_x) <= 1


def test_sidebar_offsets_follow_navbar_and_announcement(page: Page):
    """The sidebar begins below the navbar with and without the announcement."""
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/ai/")
    sidebar = page.locator("main > .sticky.left-0")
    expect(sidebar).to_be_visible()
    for dismiss in (False, True):
        if dismiss:
            page.get_by_role("button", name="Dismiss announcement").click()
            expect(
                page.get_by_role("button", name="Dismiss announcement")
            ).to_have_count(0)
        header_bottom = page.locator("header").evaluate(
            "element => element.getBoundingClientRect().bottom"
        )
        expect(sidebar).to_have_css("top", f"{header_bottom:g}px")
        sidebar_top = sidebar.evaluate(
            "element => parseFloat(getComputedStyle(element).top)"
        )
        height = sidebar.evaluate("element => element.getBoundingClientRect().height")
        assert abs(height + sidebar_top - 1000) <= 1


@pytest.mark.parametrize("width", [375, 1440])
def test_sidebar_announces_current_page(page: Page, width: int):
    """Only the current leaf is announced as the current page."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/getting-started/installation/")
    if width < 1024:
        page.get_by_role("button", name="Open documentation navigation").click()
        sidebar = page.get_by_role("dialog")
    else:
        sidebar = page.locator("main > .sticky.left-0")
    expect(
        sidebar.get_by_role("link", name="Installation", exact=True)
    ).to_have_attribute("aria-current", "page")
    expect(sidebar.locator('a[aria-current="page"]')).to_have_count(1)
    expect(
        sidebar.get_by_role("link", name="Introduction", exact=True)
    ).not_to_have_attribute("aria-current", "page")

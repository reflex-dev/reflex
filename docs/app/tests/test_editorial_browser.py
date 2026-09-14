"""Production-browser checks: set REFLEX_DOCS_PREVIEW_URL to the app origin."""

import os

import pytest
from playwright.sync_api import Page, expect

PREVIEW_URL = os.environ.get("REFLEX_DOCS_PREVIEW_URL", "")
pytestmark = pytest.mark.skipif(
    not PREVIEW_URL, reason="Requires a running docs preview"
)


@pytest.mark.parametrize("width", [320, 375, 768, 1440])
@pytest.mark.parametrize("route", ["/docs/", "/docs/getting-started/introduction/"])
def test_editorial_header_stays_in_viewport(page: Page, width: int, route: str):
    """Centered page containers must not offset or clip the fixed navigation."""
    page.set_viewport_size({"width": width, "height": 1000})
    response = page.goto(f"{PREVIEW_URL}{route}", wait_until="networkidle")
    assert response.status == 200
    header = page.locator("header")
    expect(header).to_be_visible()
    bounds = header.bounding_box()
    assert bounds["x"] == 0
    assert bounds["width"] == width
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(page.get_by_role("heading", level=1).first).to_be_visible()


def test_editorial_banner_dismissal_search_and_navigation(page: Page):
    """Dismissal reclaims header space; keyboard search and docs links still work."""
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    page.get_by_role("button", name="Close banner").click()
    expect(page.locator("[data-docs-announcement]")).to_have_count(0)
    assert page.locator("header").bounding_box()["y"] == 0
    page.get_by_role("button", name="Search", exact=False).first.click()
    expect(page.get_by_role("dialog").first).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)
    page.get_by_role("link", name="Get Started", exact=True).first.click()
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/getting-started/introduction/")
    assert page.locator("header").bounding_box()["y"] == 0


def test_editorial_dark_mode_keeps_readable_surfaces(browser):
    """System dark mode switches both neutral text and surface colors."""
    context = browser.new_context(color_scheme="dark")
    page = context.new_page()
    try:
        page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
        expect(page.locator("[data-docs-announcement]")).to_have_css(
            "color", "rgb(255, 255, 255)"
        )
        expect(page.locator("header")).to_have_css(
            "background-color", "rgb(24, 24, 24)"
        )
        expect(page.get_by_role("heading", level=1)).to_have_css(
            "color", "rgb(245, 245, 245)"
        )
    finally:
        context.close()


def test_mobile_menu_meets_the_header(page: Page):
    """The open drawer must follow the rendered header without a content gap."""
    page.set_viewport_size({"width": 375, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    page.get_by_role("button", name="Open sidebar").click()
    expect(page.get_by_role("dialog")).to_be_visible()
    page.wait_for_function(
        "Math.abs(document.querySelector('[role=dialog]').getBoundingClientRect().y - document.querySelector('header').getBoundingClientRect().bottom) < 1",
        timeout=5000,
    )
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)


@pytest.mark.parametrize("width", [375, 1440])
def test_editorial_footer_preserves_links_and_email_validation(page: Page, width: int):
    """Footer links keep their destinations and empty signup stays in the browser."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    footer = page.locator(".docs-footer")
    expect(footer.get_by_role("link", name="Blog", exact=True)).to_have_attribute(
        "href", "/blog/"
    )
    expect(
        footer.get_by_role("link", name="Documentation", exact=True)
    ).to_have_attribute("href", "/docs/")
    email = footer.get_by_label("Stay up to date with Reflex")
    expect(email).to_have_attribute("name", "input_email")
    footer.get_by_role("button", name="Get Updates", exact=True).click()
    assert email.evaluate("input => input.validity.valueMissing")
    expect(email).to_be_focused()
    expect(footer.get_by_role("status")).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

    footer.get_by_role("button", name="Toggle dark color mode", exact=True).click()
    expect(
        footer.get_by_role("button", name="Toggle dark color mode")
    ).to_have_attribute("aria-pressed", "true")
    expect(page.locator("header")).to_have_css("background-color", "rgb(24, 24, 24)")
    expect(page.locator(".docs-cta-art [fill='var(--background)']").first).to_have_css(
        "fill", "rgb(24, 24, 24)"
    )


def test_editorial_closing_actions_keep_native_navigation_and_dialog(page: Page):
    """The closing CTA supports its link and booking dialog without nested buttons."""
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    cta = page.locator(".docs-cta")
    trial = cta.get_by_role("link", name="Try for free", exact=True)
    expect(trial).to_have_attribute("href", "https://build.reflex.dev/")
    expect(trial.locator("button")).to_have_count(0)
    cta.get_by_role("button", name="Book a Demo", exact=True).click()
    expect(page.get_by_role("dialog", include_hidden=True)).to_have_count(1)
    expect(page.get_by_role("dialog")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)

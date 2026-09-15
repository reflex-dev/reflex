"""Production-browser checks: set REFLEX_DOCS_PREVIEW_URL to the app origin."""

import os
from typing import Literal

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
    hero = page.locator(".docs-hero")
    hero.get_by_role("link", name="Build with AI", exact=True).click()
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/ai/")
    page.go_back(wait_until="networkidle")
    hero.get_by_role("link", name="Explore Framework", exact=True).click()
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/getting-started/introduction/")
    expect(page.locator("header")).to_be_visible()
    assert page.locator("header").bounding_box()["y"] == 0


@pytest.mark.parametrize("width", [375, 1440])
def test_docs_logo_returns_to_overview(page: Page, width: int):
    """The shared logo returns readers to the docs overview from an article."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(
        f"{PREVIEW_URL}/docs/ai/overview/what-is-reflex-build/",
        wait_until="networkidle",
    )
    logo = page.locator("header a").filter(has=page.locator('img[alt="Docs Logo"]'))
    expect(logo).to_have_attribute("href", "/docs/")
    logo.focus()
    page.keyboard.press("Enter")
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/")
    expect(page.locator(".docs-hero")).to_be_visible()


def test_header_selection_matches_the_docs_route(page: Page):
    """The docs base path selects Overview and client navigation updates selection."""
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    header = page.locator("header")
    overview = header.get_by_role("link", name="Overview", exact=True)
    expect(overview).to_have_css("font-weight", "450")
    expect(overview.locator("..")).to_have_css("box-shadow", "none")
    expect(header.locator('[aria-current="page"]')).to_have_text("Overview")
    for label, path in [
        ("Framework", "/docs/getting-started/introduction/"),
        ("Build with AI", "/docs/ai/"),
        ("Cloud", "/docs/hosting/deploy-quick-start/"),
        ("Overview", "/docs/"),
    ]:
        header.get_by_role("link", name=label, exact=True).click()
        expect(page).to_have_url(f"{PREVIEW_URL}{path}")
        expect(header.locator('[aria-current="page"]')).to_have_text(label)


@pytest.mark.parametrize("width", [375, 1024, 1440])
def test_navbar_search_position_and_shortcuts(page: Page, width: int):
    """Search precedes GitHub and advertises the keyboard shortcut on desktop."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/enterprise/components/", wait_until="networkidle")
    search = page.get_by_role("button", name="Search Reflex", exact=True)
    expect(search).to_be_visible()
    shortcut = search.locator("kbd")
    if width >= 1024:
        expect(shortcut).to_be_visible()
        expect(shortcut).to_contain_text("K")
    else:
        expect(shortcut).not_to_be_visible()
    if width >= 1280:
        github = page.get_by_role("link", name="View Reflex on GitHub", exact=False)
        assert (
            search.bounding_box()["x"] + search.bounding_box()["width"]
            < github.bounding_box()["x"]
        )
    for key in ("Meta+k", "Control+k"):
        page.keyboard.press(key)
        expect(page.get_by_role("dialog")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog")).to_have_count(0)
    search.click()
    expect(page.get_by_role("dialog")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [375, 1440])
def test_ai_overview_offers_build_and_agent_paths(page: Page, width: int):
    """The AI choice page keeps both workflows readable and links to their guides."""
    page.set_viewport_size({"width": width, "height": 1000})
    for label, destination in (
        ("Use Reflex Build", "/docs/ai/overview/what-is-reflex-build/"),
        ("Bring your own agent", "/docs/ai/integrations/agent-toolkit/"),
    ):
        response = page.goto(f"{PREVIEW_URL}/docs/ai/", wait_until="networkidle")
        assert response.status == 200
        expect(
            page.get_by_role("heading", level=1, name="Build with AI", exact=True)
        ).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if width < 1024:
            page.get_by_role("button", name="Open documentation navigation").click()
            navigation = page.get_by_role("dialog")
        else:
            navigation = page.locator(".docs-left-sidebar")
        expect(navigation).to_be_visible()
        expect(
            navigation.get_by_role("link", name="Navigate to Overview", exact=True)
        ).to_have_attribute("aria-current", "true")
        expect(
            navigation.get_by_role("link", name="Navigate to Reflex Build", exact=True)
        ).to_have_attribute("href", "/docs/ai/overview/what-is-reflex-build/")
        expect(
            navigation.get_by_role("link", name="Navigate to Agent Toolkit", exact=True)
        ).to_have_attribute("href", "/docs/ai/integrations/agent-toolkit/")
        if width < 1024:
            page.keyboard.press("Escape")
            expect(navigation).not_to_be_visible()
        choice = page.get_by_role("link", name=label, exact=True)
        expect(choice).to_have_attribute("href", destination)
        choice.focus()
        page.keyboard.press("Enter")
        expect(page).to_have_url(f"{PREVIEW_URL}{destination}")
        expect(page.get_by_role("heading", level=1)).to_be_visible()


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
    email = footer.get_by_label("Email address", exact=True)
    expect(email).to_have_attribute("name", "input_email")
    footer.get_by_role("button", name="Subscribe", exact=True).click()
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


@pytest.mark.parametrize("width", [375, 1440])
def test_article_footer_feedback_and_theme_controls(page: Page, width: int):
    """The article footer keeps its links, feedback, and mode controls usable."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(
        f"{PREVIEW_URL}/docs/getting-started/introduction/", wait_until="networkidle"
    )
    footer = page.locator(".docs-page-footer")
    expect(footer.get_by_role("link", name="Blog", exact=True)).to_have_attribute(
        "href", "/blog/"
    )
    expect(footer.get_by_role("link", name="Edit this page")).to_have_attribute(
        "href",
        "https://github.com/reflex-dev/reflex/edit/main/docs/getting_started/introduction.md",
    )
    expect(footer.get_by_role("link", name="Raise an issue")).to_be_visible()
    footer.get_by_role("button", name="Yes", exact=True).click()
    expect(page.get_by_placeholder("Write a comment…")).to_be_visible()
    expect(footer.get_by_role("button", name="Yes", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    page.keyboard.press("Escape")
    expect(page.get_by_placeholder("Write a comment…")).to_have_count(0)
    dark = footer.get_by_role("button", name="Toggle dark color mode")
    dark.click()
    expect(dark).to_have_attribute("aria-pressed", "true")
    expect(dark).to_have_css("background-color", "rgb(32, 32, 32)")
    expect(footer.get_by_role("link", name="Introduction", exact=True)).to_have_css(
        "color", "rgb(245, 245, 245)"
    )
    footer.get_by_role("button", name="Toggle light color mode").click()
    expect(dark).to_have_attribute("aria-pressed", "false")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [375, 1440])
def test_sidebar_groups_and_current_page_navigation(page: Page, width: int):
    """Styled sidebar rows preserve disclosure, keyboard access, and selection."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(
        f"{PREVIEW_URL}/docs/getting-started/installation/", wait_until="networkidle"
    )
    if width < 1024:
        page.get_by_role("button", name="Open documentation navigation").click()
        sidebar = page.get_by_role("dialog")
    else:
        sidebar = page.locator(".docs-left-sidebar")

    current = sidebar.locator('.docs-sidebar-leaf[aria-current="page"]')
    expect(current).to_have_text("Installation")
    group = sidebar.locator("summary").filter(has_text="Getting Started")
    group.click()
    expect(current).not_to_be_visible()
    group.press("Enter")
    expect(current).to_be_visible()
    group.press("Tab")
    expect(current).to_be_focused()
    sidebar.get_by_role("link", name="Basics", exact=True).click()
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/getting-started/basics/")

    if width < 1024:
        expect(page.get_by_role("dialog")).to_have_count(0)
        page.get_by_role("button", name="Open documentation navigation").click()
    expect(sidebar.locator('.docs-sidebar-leaf[aria-current="page"]')).to_have_text(
        "Basics"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize(
    "route",
    [
        "/docs/library/",
        "/docs/api-reference/app/",
        "/docs/getting-started/installation/",
    ],
)
def test_nested_article_headings_share_the_editorial_type(page: Page, route: str):
    """Cards, API content, and nested tab panels use the article heading scale."""
    page.goto(f"{PREVIEW_URL}{route}", wait_until="networkidle")
    headings = page.locator(
        ".docs-prose :is(h1,h2,h3,h4):not([data-docs-example] *):visible"
    )
    assert headings.count() > 1
    for heading in headings.all():
        expect(heading).to_have_css("font-weight", "450")


def test_article_theme_preserves_live_example_styles_and_events(page: Page):
    """Editorial type must not overwrite the rendered counter's own heading style."""
    page.goto(
        f"{PREVIEW_URL}/docs/getting-started/introduction/", wait_until="networkidle"
    )
    demo = (
        page
        .locator("[data-docs-example]")
        .filter(has=page.get_by_role("button", name="Increment", exact=True))
        .first
    )
    value = demo.get_by_role("heading")
    expect(value).to_have_css("font-weight", "700")
    for label, accent in [("Increment", "grass"), ("Decrement", "ruby")]:
        expect(demo.get_by_role("button", name=label, exact=True)).to_have_attribute(
            "data-accent-color", accent
        )
    before = int(value.inner_text())
    demo.get_by_role("button", name="Increment", exact=True).click()
    expect(value).to_have_text(str(before + 1))


def test_mobile_header_links_and_booking_form(page: Page):
    """Mobile docs destinations match desktop; opening booking closes the drawer."""
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    page.get_by_role("button", name="Open sidebar").click()
    menu = page.get_by_role("navigation", name="Documentation navigation")
    expect(menu).to_be_visible()
    for label, href in {
        "Overview": "/docs/",
        "Build with AI": "/docs/ai/",
        "Framework": "/docs/getting-started/introduction/",
        "Cloud": "/docs/hosting/deploy-quick-start/",
        "XY": "/docs/xy/",
    }.items():
        expect(menu.get_by_role("link", name=label, exact=True)).to_have_attribute(
            "href", href
        )
    page.get_by_role("dialog").get_by_role("button", name="Book a Demo").click()
    booking = page.locator('[data-slot="dialog-popup"]:has(#docs-booking_user_email)')
    expect(booking).to_be_visible()
    expect(page.get_by_role("dialog", include_hidden=True)).to_have_count(1)
    expect(booking.get_by_role("heading", name="Book a Demo")).to_have_css(
        "font-weight", "450"
    )
    email = booking.locator("#docs-booking_user_email")
    email.fill("preview@example.com")
    expect(email).to_have_value("preview@example.com")
    page.wait_for_function(
        """() => {
            const box = document.querySelector('[data-slot="dialog-popup"]').getBoundingClientRect();
            return box.top >= 0 && box.bottom <= innerHeight && box.right <= innerWidth;
        }"""
    )
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_gallery_sort_menu_supports_keyboard_selection(page: Page):
    """The gallery sort trigger remains usable after adopting shared controls."""
    page.goto(f"{PREVIEW_URL}/docs/custom-components/", wait_until="networkidle")
    trigger = page.get_by_role("button", name="Sort", exact=True)
    trigger.focus()
    trigger.press("Enter")
    recent = page.get_by_role("menuitem", name="Recent")
    expect(recent).to_be_visible()
    recent.focus()
    recent.press("Enter")
    expect(page.get_by_role("button", name="Sort: Recent", exact=True)).to_be_visible()
    expect(page.get_by_role("menuitem", name="Recent")).to_have_count(0)


def test_missing_page_uses_docs_shell_and_recovery_link(page: Page):
    """A missing route keeps docs navigation and a working route back to overview."""
    page.goto(f"{PREVIEW_URL}/docs/404/", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Page not found")).to_be_visible()
    expect(page.locator(".docs-navbar")).to_be_visible()
    expect(page.locator(".docs-footer")).to_be_visible()
    page.get_by_role("link", name="Back to docs", exact=True).click()
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/")


def test_integration_catalog_hydrates_and_filters(page: Page):
    """Integration cards keep valid link markup and accessible category filters."""
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{PREVIEW_URL}/docs/ai/integrations/overview/", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Integrations", level=1)).to_be_visible()
    assert not errors
    cards = page.locator(".docs-integration-card:visible")
    all_count = cards.count()
    page.get_by_role("button", name="Authentication", exact=True).click()
    expect(page.get_by_role("button", name="Authentication")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert 0 < cards.count() < all_count
    expect(cards.locator("a, button")).to_have_count(0)
    page.get_by_role("button", name="Request integration", exact=True).click()
    expect(page.get_by_placeholder("Requested integration...")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_low_level_form_example_has_valid_inline_result_markup(page: Page):
    """Inline submitted values must not cause the browser to repair nested paragraphs."""
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{PREVIEW_URL}/docs/library/forms/form/low/", wait_until="networkidle")
    expect(page.get_by_text("Username submitted:", exact=False)).to_be_visible()
    assert not errors


@pytest.mark.parametrize("width", [375, 1440])
def test_framework_tabs_switch_diagrams_and_keep_docs_links(page: Page, width: int):
    """Every framework tab reveals one illustration and its matching docs link."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    section = page.get_by_role("region", name="Framework", exact=True)
    for title, link, href in [
        (
            "How It Works",
            "Read the introduction",
            "/docs/getting-started/introduction/",
        ),
        ("Components", "Browse all components", "/docs/library/"),
        ("Auth", "Explore authentication", "/docs/enterprise/auth/overview/"),
        ("Database", "Explore databases", "/docs/database/overview/"),
    ]:
        tab = section.get_by_role("tab", name=title, exact=True)
        tab.click()
        expect(tab).to_have_attribute("aria-selected", "true")
        panel = section.get_by_role("tabpanel")
        expect(panel).to_have_count(1)
        expect(panel.locator("svg").first).to_be_visible()
        expect(panel.get_by_role("link", name=link)).to_have_attribute("href", href)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    section.get_by_role("tab", name="How It Works", exact=True).focus()
    page.keyboard.press("ArrowDown")
    expect(section.get_by_role("tab", name="Components", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    page.keyboard.press("Tab")
    expect(
        section.get_by_role("tabpanel", name="Components", exact=True)
    ).to_be_focused()
    page.keyboard.press("Tab")
    browse = section.get_by_role("link", name="Browse all components")
    expect(browse).to_be_focused()
    page.keyboard.press("Enter")
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/library/")


@pytest.mark.parametrize("width", [375, 1440])
@pytest.mark.parametrize("color_scheme", ["light", "dark"])
def test_framework_counter_is_live_and_windows_do_not_overlap(
    page: Page, width: int, color_scheme: Literal["light", "dark"]
):
    """The diagram exposes a real counter without covering its Python example."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.emulate_media(color_scheme=color_scheme)
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    section = page.get_by_role("region", name="Framework", exact=True)
    panel = section.get_by_role("tabpanel", name="How It Works", exact=True)
    button = panel.get_by_role("button", name="Increment", exact=False)
    expect(button).to_be_visible()
    count = panel.get_by_role("status", name="Counter value")
    expect(count).to_have_text("0")
    button.click()
    expect(count).to_have_text("1")
    button.click()
    expect(count).to_have_text("2")
    button.focus()
    page.keyboard.press("Space")
    expect(count).to_have_text("3")
    source = panel.locator(".docs-framework-live-code").bounding_box()
    app = panel.locator(".docs-framework-live-app").bounding_box()
    assert source["y"] + source["height"] < app["y"]
    assert panel.locator("pre").evaluate("el => el.scrollWidth <= el.clientWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    section.get_by_role("tab", name="Components", exact=True).click()
    section.get_by_role("tab", name="How It Works", exact=True).click()
    expect(count).to_have_text("3")


@pytest.mark.parametrize("width", [320, 375, 1440])
@pytest.mark.parametrize("color_scheme", ["light", "dark"])
def test_cloud_diagram_preserves_guides_without_overlapping(
    page: Page, width: int, color_scheme: Literal["light", "dark"]
):
    """The hosting diagram keeps every guide accessible at both layout sizes."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.emulate_media(color_scheme=color_scheme)
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    section = page.get_by_role("region", name="Cloud", exact=True)
    expect(section.get_by_role("heading", name="Your application")).to_be_visible()
    assert section.locator(".docs-cloud-hub").evaluate(
        "el => [...el.querySelectorAll('*')].every(node => node.scrollWidth <= node.clientWidth + 1)"
    )
    for title, href in [
        ("Deployment", "/docs/hosting/deploy-quick-start/"),
        ("Secret Management", "/docs/hosting/secrets-environment-vars/"),
        ("Observability", "/docs/hosting/logs/"),
        ("Custom Headers and Advanced Options", "/docs/hosting/deploy-quick-start/"),
    ]:
        link = section.get_by_role("link", name=title, exact=True)
        expect(link).to_have_attribute("href", href)
        link.focus()
        expect(link).to_be_focused()
        bounds = link.bounding_box()
        hub = section.locator(".docs-cloud-hub").bounding_box()
        assert (
            bounds["x"] + bounds["width"] <= hub["x"]
            or bounds["x"] >= hub["x"] + hub["width"]
            or bounds["y"] + bounds["height"] <= hub["y"]
            or bounds["y"] >= hub["y"] + hub["height"]
        )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    section.get_by_role("link", name="Deployment", exact=True).click()
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/hosting/deploy-quick-start/")


def test_agent_file_links_respect_docs_mount(page: Page):
    """The router adds the docs prefix exactly once to agent-file links."""
    page.goto(f"{PREVIEW_URL}/docs/getting-started/introduction/")
    expect(page.locator('a[href="/docs/llms.txt"]').first).to_have_count(1)
    page.get_by_role("button", name="Copy page options").click()
    link = page.get_by_role("link", name="llms-full.txt", exact=False)
    expect(link).to_have_attribute("href", "/docs/llms-full.txt")
    response = page.request.get(f"{PREVIEW_URL}/docs/llms-full.txt")
    assert response.status == 200
    assert "# Reflex Documentation" in response.text()

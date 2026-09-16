"""Browser regressions for imported docs features; set REFLEX_DOCS_PREVIEW_URL."""

import os
from urllib.parse import quote

import pytest
from playwright.sync_api import Page, expect

PREVIEW_URL = os.environ.get("REFLEX_DOCS_PREVIEW_URL", "")
pytestmark = pytest.mark.skipif(
    not PREVIEW_URL, reason="Requires a running docs preview"
)


@pytest.mark.parametrize("width", [390, 768, 1440])
def test_docs_reading_typography_is_consistent(page: Page, width: int):
    """Prose, inline links, and reference headings share the reading styles."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/getting-started/introduction/")
    paragraph = (
        page.locator("p").filter(has_text="State holds the app's mutable data").first
    )
    expect(paragraph).to_have_css("font-weight", "450")
    expect(paragraph).to_have_css("color", "rgb(24, 24, 24)")
    link = paragraph.locator("a").first
    for property_name in ("font-size", "font-weight", "line-height", "letter-spacing"):
        expected = link.evaluate(
            "(el, name) => getComputedStyle(el.parentElement).getPropertyValue(name)",
            property_name,
        )
        expect(link).to_have_css(property_name, expected)
    heading_size = "32px" if width >= 1024 else "24px"
    expect(page.get_by_role("heading", name="Goals", exact=True)).to_have_css(
        "font-size", heading_size
    )
    page.goto(f"{PREVIEW_URL}/docs/api-reference/app/")
    expect(page.get_by_role("heading", name="Fields", exact=True)).to_have_css(
        "font-size", heading_size
    )


def test_sidebar_labels_match_reading_text_color(page: Page):
    """Navigation labels share the body foreground while section captions recede."""
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/getting-started/introduction/")
    expect(
        page.get_by_role("link", name="Navigate to Components").locator("h3")
    ).to_have_css("color", "rgb(24, 24, 24)")
    expect(page.locator("summary").filter(has_text="Getting Started")).to_have_css(
        "color", "rgb(24, 24, 24)"
    )
    expect(
        page.get_by_role("link", name="Installation", exact=True).locator("p")
    ).to_have_css("color", "rgb(24, 24, 24)")
    expect(page.get_by_role("heading", name="Onboarding", exact=True)).to_have_css(
        "color", "rgb(89, 89, 89)"
    )


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("/getting-started/introduction/", "docs/getting_started/introduction.md"),
        ("/getting-started/installation/", "docs/getting_started/installation.md"),
        ("/library/data-display/avatar/", "docs/library/data-display/avatar.md"),
        ("/library/", "docs/app/reflex_docs/pages/docs/library.py"),
        ("/api-reference/app/", "reflex/app.py"),
        ("/api-reference/config/", "packages/reflex-base/src/reflex_base/config.py"),
        (
            "/hosting/cli/deploy/",
            "packages/reflex-hosting-cli/src/reflex_cli/v2/deploy.py",
        ),
        ("/hosting/cli/apps/", "packages/reflex-hosting-cli/src/reflex_cli/v2/apps.py"),
        ("/ai/", "docs/app/reflex_docs/pages/ai_landing.py"),
        ("/ai/overview/best-practices/", "docs/ai_builder/overview/best_practices.md"),
        ("/enterprise/components/", "docs/enterprise/components.md"),
        ("/changelog/", "CHANGELOG.md"),
        ("/overview/", "docs/app/reflex_docs/pages/docs/cloud.py"),
    ],
)
def test_edit_page_navigates_to_source(page: Page, path: str, source: str):
    """Footer actions navigate to the exact source without the docs basename."""
    ref = quote(os.environ.get("DOCS_GITHUB_REF") or "main", safe="")
    expected = f"https://github.com/reflex-dev/reflex/edit/{ref}/{source}"
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs{path}")
    edit = page.get_by_role("link", name="Edit this page", exact=True)
    expect(edit).to_have_attribute("href", expected)
    # Verify browser navigation without depending on GitHub login or rate limits.
    page.route("https://github.com/**", lambda route: route.fulfill(body="GitHub"))
    edit.click()
    expect(page).to_have_url(expected)


def test_packaged_changelog_has_no_misleading_edit_link(page: Page):
    """An installed changelog without public source retains its issue action."""
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/changelog/reflex-enterprise/")
    expect(
        page.get_by_role("heading", name="reflex-enterprise Changelog", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("link", name="Edit this page", exact=True)).to_have_count(0)
    expect(page.get_by_role("link", name="Raise an issue", exact=True)).to_have_count(1)


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


def test_sidebar_category_labels_align_with_section_headings(page: Page):
    """Text-only AI categories share the section heading's left edge."""
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/ai/")
    sidebar = page.locator("#sidebar-container")
    heading = sidebar.get_by_role("heading", name="Overview", exact=True)
    expect(heading).to_be_visible()
    heading_x = heading.bounding_box()["x"]
    for name in ("Build with AI", "AI Builder", "Agent Toolkit"):
        link = sidebar.get_by_role("link", name=f"Navigate to {name}", exact=True)
        expect(link.locator("svg")).to_have_count(0)
        assert abs(link.locator("h3").bounding_box()["x"] - heading_x) <= 1


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


def test_single_page_sidebar_links_keep_neutral_hover_color(page: Page):
    """Direct sidebar links must not inherit the old purple anchor hover color."""
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/ai/integrations/database/")
    page.add_style_tag(content="* { transition: none !important; }")
    sidebar = page.locator("#sidebar-container")
    for label in ("Databases", "Webhooks", "Files"):
        link = sidebar.get_by_role("link", name=label, exact=True)
        link.hover()
        expect(link.locator("p")).to_have_css("color", "rgb(24, 24, 24)")


@pytest.mark.parametrize("width", [390, 1440])
def test_single_page_sidebar_link_has_selected_background(page: Page, width: int):
    """The active direct link has a neutral highlight that follows navigation."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/ai/webhooks/")
    if width < 1024:
        page.get_by_role("button", name="Open documentation navigation").click()
        sidebar = page.get_by_role("dialog")
    else:
        sidebar = page.locator("#sidebar-container")
    selected = sidebar.get_by_role("link", name="Webhooks", exact=True)
    expect(selected).to_have_attribute("aria-current", "page")
    expect(selected).to_have_css("background-color", "rgb(246, 246, 246)")
    expect(selected.locator("p")).to_have_css("color", "rgb(24, 24, 24)")
    inactive = sidebar.get_by_role("link", name="Files", exact=True)
    expect(inactive).to_have_css("background-color", "rgba(0, 0, 0, 0)")
    inactive.click()
    if width < 1024:
        page.get_by_role("button", name="Open documentation navigation").click()
    expect(sidebar.get_by_role("link", name="Files", exact=True)).to_have_css(
        "background-color", "rgb(246, 246, 246)"
    )
    expect(sidebar.get_by_role("link", name="Webhooks", exact=True)).to_have_css(
        "background-color", "rgba(0, 0, 0, 0)"
    )


def test_sidebar_click_preserves_scroll_position(page: Page):
    """Selecting a visible page must not recenter the scrollable sidebar."""
    page.set_viewport_size({"width": 1440, "height": 700})
    page.goto(f"{PREVIEW_URL}/docs/ai/files/", wait_until="networkidle")
    sidebar = page.locator("#sidebar-container")
    target = sidebar.get_by_role("link", name="Webhooks", exact=True)
    before = target.evaluate("""el => {
        const scroller = el.closest('[class*="overflow-y-scroll"]');
        scroller.scrollTop = 0;
        return scroller.scrollTop;
    }""")
    target.click()
    expect(target).to_have_attribute("aria-current", "page")
    target.evaluate("""el => new Promise(resolve => {
        const scroller = el.closest('[class*="overflow-y-scroll"]');
        let previous = scroller.scrollTop;
        let stableFrames = 0;
        function check() {
            const current = scroller.scrollTop;
            stableFrames = current === previous ? stableFrames + 1 : 0;
            previous = current;
            if (stableFrames >= 3) resolve();
            else requestAnimationFrame(check);
        }
        requestAnimationFrame(check);
    })""")
    after = target.evaluate(
        "el => el.closest('[class*=\"overflow-y-scroll\"]').scrollTop"
    )
    assert abs(after - before) <= 1


def test_unknown_route_serves_docs_recovery_page(page: Page):
    """Unknown URLs render the registered docs recovery page and stay unindexed."""
    page.goto(f"{PREVIEW_URL}/docs/not-a-real-docs-page/")
    expect(
        page.get_by_role("heading", name="Page not found", exact=True)
    ).to_be_visible()
    expect(page.get_by_role("link", name="Back to docs", exact=True)).to_have_attribute(
        "href", "/docs/"
    )
    expect(page.locator('meta[name="robots"]')).to_have_attribute("content", "noindex")

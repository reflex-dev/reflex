"""Production-browser checks: set REFLEX_DOCS_PREVIEW_URL to the app origin."""

import os

import pytest
from playwright.sync_api import Page, expect

PREVIEW_URL = os.environ.get("REFLEX_DOCS_PREVIEW_URL", "")
pytestmark = pytest.mark.skipif(
    not PREVIEW_URL, reason="Requires a running docs preview"
)


@pytest.mark.parametrize("width", [390, 1440])
def test_spline_preview_waits_for_visibility_and_idle(page: Page, width: int):
    """Load the 3D preview only near the viewport, after the browser becomes idle."""
    page.set_viewport_size({"width": width, "height": 600})
    page.add_init_script("""
        window.previewIdleCallbacks = new Map();
        let nextId = 0;
        window.requestIdleCallback = callback => {
            const id = ++nextId;
            window.previewIdleCallbacks.set(id, callback);
            return id;
        };
        window.cancelIdleCallback = id => window.previewIdleCallbacks.delete(id);
    """)
    scripts = []
    scenes = []
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "request",
        lambda request: (
            scripts.append(request.url)
            if request.resource_type == "script" and request.url.startswith(PREVIEW_URL)
            else None
        ),
    )
    page.on(
        "request",
        lambda request: (
            scenes.append(request.url) if "scene.splinecode" in request.url else None
        ),
    )
    page.goto(f"{PREVIEW_URL}/docs/wrapping-react/overview/", wait_until="networkidle")
    preview = page.locator(".docs-demo-preview").first
    pending = "window.previewIdleCallbacks.size"
    # Beyond the viewport and the observer's 200px margin.
    assert preview.bounding_box()["y"] >= 800
    assert page.evaluate(pending) == 0
    initial_scripts = len(scripts)

    preview.scroll_into_view_if_needed()
    page.wait_for_function(f"{pending} > 0")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function(f"{pending} === 0")

    preview.scroll_into_view_if_needed()
    page.wait_for_function(f"{pending} > 0")
    tabs = page.locator('[role="tablist"]').first
    tabs.get_by_role("tab", name="Code", exact=True).click()
    page.wait_for_function(f"{pending} === 0")
    expect(
        page.get_by_text("class Spline(rx.NoSSRComponent):", exact=False)
    ).to_be_visible()
    tabs.get_by_role("tab", name="View", exact=True).click()
    preview.scroll_into_view_if_needed()
    page.wait_for_function(f"{pending} > 0")
    assert scenes == []
    assert len(scripts) == initial_scripts

    with page.expect_response("**/scene.splinecode") as scene:
        page.evaluate("""() => {
            for (const [id, callback] of window.previewIdleCallbacks) {
                window.previewIdleCallbacks.delete(id);
                callback({didTimeout: false, timeRemaining: () => 50});
            }
        }""")
    assert scene.value.ok
    expect(page.locator(".docs-demo-preview canvas")).to_be_visible()
    # The deferred import fetched the wrapper's chunk only after the idle callback.
    assert len(scripts) > initial_scripts

    # A loaded preview remounts without waiting for idle time again.
    tabs.get_by_role("tab", name="Code", exact=True).click()
    tabs.get_by_role("tab", name="View", exact=True).click()
    expect(page.locator(".docs-demo-preview canvas")).to_be_visible()
    assert page.evaluate(pending) == 0
    assert errors == []


@pytest.mark.parametrize("idle_callback", [True, False])
def test_spline_preview_loads_automatically(page: Page, idle_callback: bool):
    """Scrolling loads the preview with native idle callbacks or their fallback."""
    page.set_viewport_size({"width": 390, "height": 600})
    if not idle_callback:
        page.add_init_script("delete window.requestIdleCallback")
    page.goto(f"{PREVIEW_URL}/docs/wrapping-react/overview/", wait_until="networkidle")
    expect(page.locator(".docs-demo-preview canvas")).to_have_count(0)
    with page.expect_response("**/scene.splinecode") as scene:
        page.locator(".docs-demo-preview").first.scroll_into_view_if_needed()
    assert scene.value.ok
    expect(page.locator(".docs-demo-preview canvas")).to_be_visible()


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


def test_article_theme_preserves_live_example_styles_and_events(page: Page):
    """Editorial type must not overwrite the rendered counter's own heading style."""
    page.goto(
        f"{PREVIEW_URL}/docs/getting-started/introduction/", wait_until="networkidle"
    )
    demo = page.get_by_role("button", name="Increment", exact=True).locator("..")
    value = demo.get_by_role("heading")
    expect(value).to_have_css("font-weight", "700")
    for label, accent in [("Increment", "grass"), ("Decrement", "ruby")]:
        expect(demo.get_by_role("button", name=label, exact=True)).to_have_attribute(
            "data-accent-color", accent
        )
    before = int(value.inner_text())
    demo.get_by_role("button", name="Increment", exact=True).click()
    expect(value).to_have_text(str(before + 1))


@pytest.mark.parametrize("width", [320, 390])
def test_wide_demo_starts_inside_its_scroll_container(page: Page, width: int):
    """A fixed-width example must not lose its left edge on a narrow screen."""
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{PREVIEW_URL}/docs/library/media/video/", wait_until="networkidle")
    preview = page.locator(".docs-demo-preview")
    video = preview.locator("youtube-video")
    expect(video).to_be_attached()
    assert video.bounding_box()["x"] >= preview.bounding_box()["x"]
    assert preview.evaluate("el => el.scrollWidth > el.clientWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [320, 390])
def test_long_component_names_wrap_inside_the_reading_column(page: Page, width: int):
    """API identifiers must not create a second horizontal page scroller."""
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(
        f"{PREVIEW_URL}/docs/library/overlay/dropdown-menu/", wait_until="networkidle"
    )
    column = page.locator(".docs-reading-column")
    assert column.evaluate("el => el.scrollWidth <= el.clientWidth")
    assert page.locator(".docs-heading").evaluate_all(
        "els => els.every(el => el.getBoundingClientRect().right <= innerWidth - 20)"
    )


def test_low_level_form_example_has_valid_inline_result_markup(page: Page):
    """Inline submitted values must not cause the browser to repair nested paragraphs."""
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{PREVIEW_URL}/docs/library/forms/form/low/", wait_until="networkidle")
    expect(page.get_by_text("Username submitted:", exact=False)).to_be_visible()
    assert not errors


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


@pytest.mark.parametrize("width", [320, 375, 768, 1024, 1279, 1280, 1440])
def test_navbar_controls_fit_and_search_opens(page: Page, width: int):
    """Keep every visible navbar control inside the viewport at both breakpoints."""
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    header = page.locator("header")
    overview = header.get_by_role("link", name="Overview", exact=True)
    menu = header.get_by_label("Toggle navigation menu")
    if width < 1280:
        expect(overview).not_to_be_visible()
        expect(menu).to_be_visible()
        menu.click()
        expect(menu.locator("..")).to_have_attribute("open", "")
        navigation = page.get_by_role("navigation", name="Documentation navigation")
        expect(navigation).to_have_css("position", "fixed")
        bounds = navigation.bounding_box()
        assert bounds["x"] == 0
        assert bounds["width"] == width
        assert (
            bounds["y"] == header.bounding_box()["y"] + header.bounding_box()["height"]
        )
        for label, href in (
            ("Overview", "/docs/"),
            ("Build with AI", "/docs/ai/"),
            ("Framework", "/docs/getting-started/introduction/"),
            ("Cloud", "/docs/hosting/deploy-quick-start/"),
            ("XY", "/docs/xy/"),
        ):
            link = navigation.get_by_role("link", name=label, exact=True)
            expect(link).to_be_visible()
            expect(link).to_have_attribute("href", href)
        menu.click()
    else:
        expect(overview).to_be_visible()
        expect(menu).not_to_be_visible()
    for control in header.locator("a:visible, button:visible, summary:visible").all():
        bounds = control.bounding_box()
        assert bounds["x"] >= 0
        assert bounds["x"] + bounds["width"] <= width + 1
    search = page.get_by_role("button", name="Search Reflex", exact=True)
    if width < 1280:
        expect(search.locator("svg")).to_have_css("width", "16px")
    search.click()
    expect(page.get_by_role("dialog")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_announcement_dismissal_and_search_shortcuts(page: Page):
    """Dismissal reclaims header space and both search shortcuts open the dialog."""
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    page.get_by_role("button", name="Dismiss announcement").click()
    expect(page.locator("[data-announcement]")).not_to_be_visible()
    expect(page.locator("header")).to_have_css("background-image", "none")
    assert page.locator("header").bounding_box()["y"] == 0
    for key in ("Meta+k", "Control+k"):
        page.keyboard.press(key)
        expect(page.get_by_role("dialog")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog")).to_have_count(0)


@pytest.mark.parametrize("width", [375, 1440])
def test_footer_links_newsletter_and_theme(page: Page, width: int):
    """Marketing footer links, native email validation, and theme controls work."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    footer = page.locator("footer")
    expect(footer.get_by_role("link", name="Blog", exact=False)).to_have_attribute(
        "href", "https://reflex.dev/blog/"
    )
    email = footer.get_by_label("Email address", exact=True)
    footer.get_by_role("button", name="Subscribe to updates", exact=True).click()
    assert email.evaluate("el => el.validity.valueMissing")
    expect(email).to_be_focused()
    before = page.locator("header").evaluate(
        "el => getComputedStyle(el).backgroundColor"
    )
    dark = footer.get_by_role("button", name="Toggle dark color mode", exact=True)
    dark.click()
    expect(dark).to_have_attribute("aria-pressed", "true")
    expect(page.locator("header")).not_to_have_css("background-color", before)
    expect(page.locator("header")).to_have_css("background-image", "none")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [375, 1024, 1440, 1920])
def test_landing_content_matches_footer_gutters(page: Page, width: int):
    """The hero, closing CTA, and marketing footer share their content edges."""
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    edges = page.locator(".docs-hero, .docs-cta, footer > div").evaluate_all(
        "els => els.map(el => {const r=el.getBoundingClientRect(), s=getComputedStyle(el); return [r.left+parseFloat(s.paddingLeft), r.right-parseFloat(s.paddingRight)];})"
    )
    assert len(edges) == 3
    for left, right in edges[1:]:
        assert abs(left - edges[0][0]) <= 1
        assert abs(right - edges[0][1]) <= 1


def test_cta_and_framework_links_keep_native_destinations(page: Page):
    """The current framework cards and closing actions expose working native links."""
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    cta = page.locator(".docs-cta")
    expect(cta.get_by_role("link", name="Try for free", exact=True)).to_have_attribute(
        "href", "https://build.reflex.dev/"
    )
    expect(cta.get_by_role("link", name="Book a Demo", exact=True)).to_have_attribute(
        "href", "https://reflex.dev/demo/"
    )
    link = page.get_by_role("link", name="Data Display", exact=True)
    expect(link).to_have_attribute("href", "/docs/library/data-display/")
    link.focus()
    page.keyboard.press("Enter")
    expect(page).to_have_url(f"{PREVIEW_URL}/docs/library/data-display/")
    expect(page.get_by_role("heading", level=1)).to_be_visible()


def test_navbar_announces_selected_section(page: Page):
    """The selected navbar section stays accessible after client navigation."""
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{PREVIEW_URL}/docs/", wait_until="networkidle")
    header = page.locator("header")
    for label, path in (
        ("Overview", "/docs/"),
        ("Framework", "/docs/getting-started/introduction/"),
        ("Build with AI", "/docs/ai/"),
    ):
        header.get_by_role("link", name=label, exact=True).click()
        expect(page).to_have_url(f"{PREVIEW_URL}{path}")
        expect(header.locator('a[aria-current="page"]')).to_have_text(label)

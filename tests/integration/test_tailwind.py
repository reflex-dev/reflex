"""Test case for disabling tailwind in the config."""

import functools

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

PARAGRAPH_TEXT = "Tailwind Is Cool"
PARAGRAPH_CLASS_NAME = "text-red-500"
TEXT_RED_500_COLOR_v3 = ["rgba(239, 68, 68, 1)", "rgb(239, 68, 68)"]
TEXT_RED_500_COLOR_v4 = ["oklch(0.637 0.237 25.331)"]


def TailwindApp(
    tailwind_version: int = 0,
    paragraph_text: str = PARAGRAPH_TEXT,
    paragraph_class_name: str = PARAGRAPH_CLASS_NAME,
):
    """App with tailwind optionally disabled.

    Args:
        tailwind_version: Tailwind version to use. If 0, tailwind is disabled.
        paragraph_text: Text for the paragraph.
        paragraph_class_name: Tailwind class_name for the paragraph.
    """
    from pathlib import Path

    import reflex as rx

    class UnusedState(rx.State):
        pass

    def index():
        return rx.el.div(
            rx.text(paragraph_text, class_name=paragraph_class_name),
            rx.el.p(paragraph_text, class_name=paragraph_class_name),
            rx.text(paragraph_text, as_="p", class_name=paragraph_class_name),
            rx.el.div("Test external stylesheet", class_name="external"),
            id="p-content",
        )

    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(exist_ok=True)
    stylesheet = assets / "test_styles.css"
    stylesheet.write_text(".external { color: rgba(0, 0, 255, 0.5) }")
    app = rx.App(
        style={"font_family": "monospace"},
        stylesheets=[stylesheet.name],
        enable_state=False,
    )
    app.add_page(index)
    if not tailwind_version:
        config = rx.config.get_config()
        config.plugins = []
    elif tailwind_version == 3:
        config = rx.config.get_config()
        config.plugins = [rx.plugins.TailwindV3Plugin()]
    elif tailwind_version == 4:
        config = rx.config.get_config()
        config.plugins = [rx.plugins.TailwindV4Plugin()]


@pytest.fixture(
    params=[0, 3, 4], ids=["tailwind_disabled", "tailwind_v3", "tailwind_v4"]
)
def tailwind_version(request) -> int:
    """Tailwind version fixture.

    Args:
        request: pytest request fixture.

    Returns:
        Tailwind version to use. 0 for disabled, 3 for v3, 4 for v4.
    """
    return request.param


@pytest.fixture(scope="module")
def _tailwind_app_factory(tmp_path_factory):
    """Factory fixture that creates AppHarness instances keyed by tailwind version.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture.

    Yields:
        A callable taking a tailwind_version and returning an AppHarness.
    """
    harnesses: dict[int, AppHarness] = {}
    contexts = []

    def _get(version: int) -> AppHarness:
        if version in harnesses:
            return harnesses[version]
        ctx = AppHarness.create(
            root=tmp_path_factory.mktemp(
                "tailwind_" + ("disabled" if version == 0 else str(version))
            ),
            app_source=functools.partial(TailwindApp, tailwind_version=version),
            app_name="tailwind_" + ("disabled" if version == 0 else str(version)),
        )
        harness = ctx.__enter__()
        contexts.append(ctx)
        harnesses[version] = harness
        return harness

    try:
        yield _get
    finally:
        for ctx in contexts:
            ctx.__exit__(None, None, None)


@pytest.fixture
def tailwind_app(_tailwind_app_factory, tailwind_version) -> AppHarness:
    """Start TailwindApp app at tmp_path via AppHarness with tailwind disabled via config.

    Args:
        _tailwind_app_factory: factory returning per-version harnesses.
        tailwind_version: Whether tailwind is disabled for the app.

    Returns:
        running AppHarness instance
    """
    return _tailwind_app_factory(tailwind_version)


def test_tailwind_app(tailwind_app: AppHarness, tailwind_version: int, page: Page):
    """Test that the app can compile without tailwind.

    Args:
        tailwind_app: AppHarness instance.
        tailwind_version: Tailwind version to use. If 0, tailwind is disabled.
        page: Playwright Page fixture.
    """
    assert tailwind_app.app_instance is not None
    assert tailwind_app.backend is not None
    assert tailwind_app.frontend_url is not None

    page.goto(tailwind_app.frontend_url)

    # Assert the app is stateless.
    with pytest.raises(ValueError) as errctx:
        _ = tailwind_app.app_instance.state_manager
    errctx.match("The state manager has not been initialized.")

    # Assert content is visible (and not some error)
    content = page.locator("#p-content")
    expect(content).to_be_visible()
    paragraphs = content.locator("p")
    expect(paragraphs).to_have_count(3)
    for i in range(3):
        p = paragraphs.nth(i)
        expect(p).to_have_text(PARAGRAPH_TEXT)
        font_family = p.evaluate("el => getComputedStyle(el).fontFamily")
        assert font_family == "monospace"
        color = p.evaluate("el => getComputedStyle(el).color")
        if not tailwind_version:
            # expect default color, not "text-red-500" from tailwind utility class
            assert color not in TEXT_RED_500_COLOR_v3
        elif tailwind_version == 3:
            # expect "text-red-500" from tailwind utility class
            assert color in TEXT_RED_500_COLOR_v3
        elif tailwind_version == 4:
            # expect "text-red-500" from tailwind utility class
            assert color in TEXT_RED_500_COLOR_v4

    # Assert external stylesheet is applying rules
    external = page.locator(".external")
    expect(external).to_have_count(1)
    for i in range(external.count()):
        ext_div = external.nth(i)
        ext_color = ext_div.evaluate("el => getComputedStyle(el).color")
        assert ext_color == "rgba(0, 0, 255, 0.5)"

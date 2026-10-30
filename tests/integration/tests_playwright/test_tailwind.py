"""Test case for disabling tailwind in the config."""

import functools
import re
from collections.abc import Generator

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
        tailwind_version: If 0, tailwind is disabled.
        paragraph_text: Text for the paragraph.
        paragraph_class_name: Tailwind class for the paragraph.
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

    assets = Path.cwd() / "assets"
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
    """Select which Tailwind configuration to test.

    Args:
        request: The pytest request fixture.

    Returns:
        The Tailwind version, with 0 meaning disabled.
    """
    return request.param


@pytest.fixture
def tailwind_app(tmp_path, tailwind_version: int) -> Generator[AppHarness, None, None]:
    """Start the Tailwind app with the selected configuration.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=functools.partial(TailwindApp, tailwind_version=tailwind_version),
        app_name="tailwind_"
        + ("disabled" if tailwind_version == 0 else str(tailwind_version)),
    ) as harness:
        yield harness


def test_tailwind_app(
    tailwind_app: AppHarness, tailwind_version: int, page: Page
) -> None:
    """Verify disabled and enabled Tailwind styles in the browser."""
    assert tailwind_app.app_instance is not None
    assert tailwind_app.backend is not None

    with pytest.raises(ValueError, match="The state manager has not been initialized"):
        _ = tailwind_app.app_instance.state_manager

    assert tailwind_app.frontend_url is not None
    page.goto(tailwind_app.frontend_url)
    content = page.locator("#p-content")
    paragraphs = content.locator("p")
    expect(paragraphs).to_have_count(3)

    expected_colors = {
        0: None,
        3: TEXT_RED_500_COLOR_v3,
        4: TEXT_RED_500_COLOR_v4,
    }[tailwind_version]
    for paragraph in paragraphs.all():
        expect(paragraph).to_have_text(PARAGRAPH_TEXT)
        expect(paragraph).to_have_css("font-family", "monospace")
        if expected_colors is None:
            color = paragraph.evaluate("element => getComputedStyle(element).color")
            assert color not in TEXT_RED_500_COLOR_v3
        else:
            expect(paragraph).to_have_css(
                "color",
                re.compile("|".join(re.escape(color) for color in expected_colors)),
            )

    external = page.locator(".external")
    expect(external).to_have_count(1)
    expect(external).to_have_css("color", "rgba(0, 0, 255, 0.5)")

"""Test case for disabling tailwind in the config."""

import functools
from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

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


@pytest.fixture
def tailwind_app(tmp_path, tailwind_version) -> Generator[AppHarness, None, None]:
    """Start TailwindApp app at tmp_path via AppHarness with tailwind disabled via config.

    Args:
        tmp_path: pytest tmp_path fixture
        tailwind_version: Whether tailwind is disabled for the app.

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=functools.partial(TailwindApp, tailwind_version=tailwind_version),
        app_name="tailwind_"
        + ("disabled" if tailwind_version == 0 else str(tailwind_version)),
    ) as harness:
        yield harness


def test_tailwind_app(tailwind_app: AppHarness, tailwind_version: bool):
    """Test that the app can compile without tailwind.

    Args:
        tailwind_app: AppHarness instance.
        tailwind_version: Tailwind version to use. If 0, tailwind is disabled.
    """
    assert tailwind_app.app_instance is not None
    assert tailwind_app.backend is not None

    driver = tailwind_app.frontend()

    # Assert the app is stateless.
    with pytest.raises(ValueError) as errctx:
        _ = tailwind_app.app_instance.state_manager
    errctx.match("The state manager has not been initialized.")

    # Assert content is visible (and not some error)
    content = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "p-content")
    )
    paragraphs = content.find_elements(By.TAG_NAME, "p")
    assert len(paragraphs) == 3
    for p in paragraphs:
        assert tailwind_app.poll_for_content(p, exp_not_equal="") == PARAGRAPH_TEXT
        assert p.value_of_css_property("font-family") == "monospace"
        if not tailwind_version:
            # expect default color, not "text-red-500" from tailwind utility class
            assert p.value_of_css_property("color") not in TEXT_RED_500_COLOR_v3
        elif tailwind_version == 3:
            # expect "text-red-500" from tailwind utility class
            assert p.value_of_css_property("color") in TEXT_RED_500_COLOR_v3
        elif tailwind_version == 4:
            # expect "text-red-500" from tailwind utility class
            assert p.value_of_css_property("color") in TEXT_RED_500_COLOR_v4

    # Assert external stylesheet is applying rules
    external = driver.find_elements(By.CLASS_NAME, "external")
    assert len(external) == 1
    for ext_div in external:
        assert ext_div.value_of_css_property("color") == "rgba(0, 0, 255, 0.5)"

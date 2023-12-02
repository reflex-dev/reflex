"""Test case for disabling tailwind in the config."""

import functools
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

PARAGRAPH_TEXT = "Tailwind Is Cool"
PARAGRAPH_CLASS_NAME = "text-red-500"
GLOBAL_PARAGRAPH_COLOR = "rgba(0, 0, 242, 1)"


def TailwindApp(
    tailwind_disabled: bool = False,
    paragraph_text: str = PARAGRAPH_TEXT,
    paragraph_class_name: str = PARAGRAPH_CLASS_NAME,
    global_paragraph_color: str = GLOBAL_PARAGRAPH_COLOR,
):
    """App with tailwind optionally disabled.

    Args:
        tailwind_disabled: Whether tailwind is disabled for the app.
        paragraph_text: Text for the paragraph.
        paragraph_class_name: Tailwind class_name for the paragraph.
        global_paragraph_color: Color for the paragraph set in global app styles.
    """
    import reflex as rx
    import reflex.components.radix.themes as rdxt

    def index():
        return rx.el.div(
            rx.text(paragraph_text, class_name=paragraph_class_name),
            rx.el.p(paragraph_text, class_name=paragraph_class_name),
            rdxt.text(paragraph_text, as_="p", class_name=paragraph_class_name),
        )

    app = rx.App(style={"p": {"color": global_paragraph_color}})
    app.add_page(index)
    if tailwind_disabled:
        config = rx.config.get_config()
        config.tailwind = None
    app.compile()


@pytest.fixture(params=[False, True], ids=["tailwind_enabled", "tailwind_disabled"])
def tailwind_disabled(request) -> bool:
    """Tailwind disabled fixture.

    Args:
        request: pytest request fixture.

    Returns:
        True if tailwind is disabled, False otherwise.
    """
    return request.param


@pytest.fixture()
def tailwind_app(tmp_path, tailwind_disabled) -> Generator[AppHarness, None, None]:
    """Start TailwindApp app at tmp_path via AppHarness with tailwind disabled via config.

    Args:
        tmp_path: pytest tmp_path fixture
        tailwind_disabled: Whether tailwind is disabled for the app.

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=functools.partial(TailwindApp, tailwind_disabled=tailwind_disabled),  # type: ignore
        app_name="tailwind_disabled_app" if tailwind_disabled else "tailwind_app",
    ) as harness:
        yield harness


def test_tailwind_app(tailwind_app: AppHarness, tailwind_disabled: bool):
    """Test that the app can compile without tailwind.

    Args:
        tailwind_app: AppHarness instance.
        tailwind_disabled: Whether tailwind is disabled for the app.
    """
    assert tailwind_app.app_instance is not None
    assert tailwind_app.backend is not None

    driver = tailwind_app.frontend()

    # Assert the app is stateless.
    with pytest.raises(ValueError) as errctx:
        _ = tailwind_app.app_instance.state_manager
    errctx.match("The state manager has not been initialized.")

    # Assert content is visible (and not some error)
    paragraphs = driver.find_elements(By.TAG_NAME, "p")
    assert len(paragraphs) == 3
    for p in paragraphs:
        assert tailwind_app.poll_for_content(p, exp_not_equal="") == PARAGRAPH_TEXT
        if tailwind_disabled:
            # expect "blue" color from global stylesheet, not "text-red-500" from tailwind utility class
            assert p.value_of_css_property("color") == GLOBAL_PARAGRAPH_COLOR
        else:
            # expect "text-red-500" from tailwind utility class
            assert p.value_of_css_property("color") == "rgba(239, 68, 68, 1)"

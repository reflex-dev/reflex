"""Integration tests for the rx.ui component library."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def UIComponentsApp():
    """An app exercising rx.ui components and their client-side behavior."""
    import reflex as rx

    def index():
        return rx.el.div(
            rx.ui.button("Primary Action", id="btn-primary"),
            rx.ui.button(
                "Open Dialog",
                id="dialog-trigger",
                on_click=rx.ui.dialog.open("demo-dialog"),
            ),
            rx.ui.dialog(
                rx.ui.dialog.header(
                    rx.ui.dialog.title("Dialog Title"),
                    rx.ui.dialog.description("Dialog description."),
                ),
                rx.ui.button(
                    "Close Dialog",
                    id="dialog-close",
                    on_click=rx.ui.dialog.close("demo-dialog"),
                ),
                id="demo-dialog",
            ),
            rx.ui.tabs(
                rx.ui.tabs.list(
                    rx.ui.tabs.trigger("Tab One", value="one", id="trigger-one"),
                    rx.ui.tabs.trigger("Tab Two", value="two", id="trigger-two"),
                ),
                rx.ui.tabs.content("Panel one content", value="one", id="panel-one"),
                rx.ui.tabs.content("Panel two content", value="two", id="panel-two"),
                id="demo-tabs",
            ),
            rx.ui.accordion(
                rx.ui.accordion.item(
                    rx.ui.accordion.trigger("First question"),
                    rx.ui.accordion.content("First answer"),
                    id="acc-item-1",
                ),
                rx.ui.accordion.item(
                    rx.ui.accordion.trigger("Second question"),
                    rx.ui.accordion.content("Second answer"),
                    id="acc-item-2",
                ),
                id="demo-accordion",
            ),
            rx.ui.checkbox(id="demo-checkbox"),
            rx.ui.switch(id="demo-switch"),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def ui_components_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Create an AppHarness for the UI components app.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        A harness running the UI components app.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("ui_components_app"),
        app_source=UIComponentsApp,
    ) as harness:
        yield harness


def test_theme_styles_are_applied(ui_components_app: AppHarness, page: Page):
    """The implicit theme stylesheet loads and Tailwind utilities resolve.

    Args:
        ui_components_app: The app harness.
        page: A Playwright page.
    """
    assert ui_components_app.frontend_url is not None
    page.goto(ui_components_app.frontend_url)

    button = page.locator("#btn-primary")
    expect(button).to_be_visible()
    assert button.get_attribute("data-slot") == "button"

    primary_token = page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--primary')"
    )
    assert primary_token.strip(), "theme token --primary should be defined"

    background = button.evaluate("(el) => getComputedStyle(el).backgroundColor")
    assert background not in ("rgba(0, 0, 0, 0)", "transparent", "")


def test_dialog_opens_and_closes_client_side(ui_components_app: AppHarness, page: Page):
    """The native dialog opens, closes, and dismisses without server events.

    Args:
        ui_components_app: The app harness.
        page: A Playwright page.
    """
    assert ui_components_app.frontend_url is not None
    page.goto(ui_components_app.frontend_url)

    dialog = page.locator("#demo-dialog")
    expect(dialog).not_to_be_visible()

    page.click("#dialog-trigger")
    expect(dialog).to_be_visible()
    expect(page.get_by_text("Dialog Title")).to_be_visible()
    assert dialog.evaluate("(el) => el.open") is True

    # A click inside the dialog box (its padding) must not dismiss it.
    dialog.click(position={"x": 5, "y": 5})
    expect(dialog).to_be_visible()

    page.click("#dialog-close")
    expect(dialog).not_to_be_visible()

    # Reopen and dismiss with ESC (native dialog behavior).
    page.click("#dialog-trigger")
    expect(dialog).to_be_visible()
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()


def test_tabs_switch_client_side(ui_components_app: AppHarness, page: Page):
    """Uncontrolled tabs switch panels with client state and keyboard nav.

    Args:
        ui_components_app: The app harness.
        page: A Playwright page.
    """
    assert ui_components_app.frontend_url is not None
    page.goto(ui_components_app.frontend_url)

    panel_one = page.locator("#panel-one")
    panel_two = page.locator("#panel-two")
    expect(panel_one).to_be_visible()
    expect(panel_two).not_to_be_visible()

    page.click("#trigger-two")
    expect(panel_two).to_be_visible()
    expect(panel_one).not_to_be_visible()
    assert page.locator("#trigger-two").get_attribute("data-state") == "active"

    # Arrow keys move focus and activate the previous tab.
    page.keyboard.press("ArrowLeft")
    expect(panel_one).to_be_visible()
    expect(panel_two).not_to_be_visible()


def test_accordion_is_exclusive(ui_components_app: AppHarness, page: Page):
    """Opening one accordion item closes the other via native grouping.

    Args:
        ui_components_app: The app harness.
        page: A Playwright page.
    """
    assert ui_components_app.frontend_url is not None
    page.goto(ui_components_app.frontend_url)

    item_1 = page.locator("#acc-item-1")
    item_2 = page.locator("#acc-item-2")

    page.get_by_text("First question").click()
    expect(page.get_by_text("First answer")).to_be_visible()
    assert item_1.evaluate("(el) => el.open") is True

    page.get_by_text("Second question").click()
    expect(page.get_by_text("Second answer")).to_be_visible()
    assert item_2.evaluate("(el) => el.open") is True
    assert item_1.evaluate("(el) => el.open") is False


def test_native_form_controls_toggle(ui_components_app: AppHarness, page: Page):
    """Styled checkbox and switch remain functional native inputs.

    Args:
        ui_components_app: The app harness.
        page: A Playwright page.
    """
    assert ui_components_app.frontend_url is not None
    page.goto(ui_components_app.frontend_url)

    checkbox = page.locator("#demo-checkbox")
    checkbox.check()
    expect(checkbox).to_be_checked()

    switch = page.locator("#demo-switch")
    assert switch.get_attribute("role") == "switch"
    switch.click()
    expect(switch).to_be_checked()

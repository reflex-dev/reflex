from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def DefaultLightModeApp():
    from reflex_base.style import color_mode

    import reflex as rx

    app = rx.App(theme=rx.theme(appearance="light"))

    @app.add_page
    def index():
        return rx.text(color_mode)


def DefaultDarkModeApp():
    from reflex_base.style import color_mode

    import reflex as rx

    app = rx.App(theme=rx.theme(appearance="dark"))

    @app.add_page
    def index():
        return rx.text(color_mode)


def DefaultSystemModeApp():
    from reflex_base.style import color_mode

    import reflex as rx

    app = rx.App()

    @app.add_page
    def index():
        return rx.text(color_mode)


def ColorToggleApp():
    from reflex_base.style import color_mode, resolved_color_mode, set_color_mode

    import reflex as rx

    app = rx.App(theme=rx.theme(appearance="light"))

    @app.add_page
    def index():
        return rx.box(
            rx.segmented_control.root(
                rx.segmented_control.item(
                    rx.icon(tag="monitor", size=20),
                    value="system",
                ),
                rx.segmented_control.item(
                    rx.icon(tag="sun", size=20),
                    value="light",
                ),
                rx.segmented_control.item(
                    rx.icon(tag="moon", size=20),
                    value="dark",
                ),
                on_change=set_color_mode,  # pyright: ignore[reportArgumentType]
                variant="classic",
                radius="large",
                value=color_mode,
            ),
            rx.text(color_mode, id="current_color_mode"),
            rx.text(resolved_color_mode, id="resolved_color_mode"),
            rx.text(rx.color_mode_cond("LightMode", "DarkMode"), id="color_mode_cond"),
        )


@pytest.fixture
def light_mode_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start DefaultLightMode app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("appearance_app"),
        app_source=DefaultLightModeApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def dark_mode_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start DefaultDarkMode app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("appearance_app"),
        app_source=DefaultDarkModeApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def system_mode_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start DefaultSystemMode app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("appearance_app"),
        app_source=DefaultSystemModeApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def color_toggle_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start ColorToggle app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("appearance_app"),
        app_source=ColorToggleApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_appearance_light_mode(light_mode_app: AppHarness, page: Page):
    assert light_mode_app.frontend_url is not None
    page.goto(light_mode_app.frontend_url)

    expect(page.get_by_text("light")).to_be_visible()


def test_appearance_dark_mode(dark_mode_app: AppHarness, page: Page):
    assert dark_mode_app.frontend_url is not None
    page.goto(dark_mode_app.frontend_url)

    expect(page.get_by_text("dark")).to_be_visible()


def test_appearance_system_mode(system_mode_app: AppHarness, page: Page):
    assert system_mode_app.frontend_url is not None
    page.goto(system_mode_app.frontend_url)

    expect(page.get_by_text("system")).to_be_visible()


def SegmentedControlManyItemsApp():
    import reflex as rx

    class SegmentedState(rx.State):
        options: list[str] = [str(i) for i in range(1, 12)]
        control: str = "1"

        @rx.event
        def set_control(self, value: str | list[str]):
            self.control = value if isinstance(value, str) else value[0]

    app = rx.App(theme=rx.theme(appearance="light"))

    @app.add_page
    def index():
        return rx.box(
            rx.segmented_control.root(
                rx.foreach(
                    SegmentedState.options,
                    lambda label: rx.segmented_control.item(label, value=label),
                ),
                on_change=SegmentedState.set_control,
                value=SegmentedState.control,
                id="segmented_control",
            ),
            rx.text(SegmentedState.control, id="selected_value"),
        )


@pytest.fixture
def segmented_control_many_items_app(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    with AppHarness.create(
        root=tmp_path_factory.mktemp("segmented_many"),
        app_source=SegmentedControlManyItemsApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_segmented_control_indicator_with_11_items(
    segmented_control_many_items_app: AppHarness, page: Page
):
    assert segmented_control_many_items_app.frontend_url is not None
    page.goto(segmented_control_many_items_app.frontend_url)

    selected_value = page.locator("id=selected_value")
    expect(selected_value).to_have_text("1")

    last_item = page.get_by_role("radio").nth(10)
    last_item.click()
    expect(selected_value).to_have_text("11")

    indicator = page.locator("#segmented_control .rt-SegmentedControlIndicator")
    expect(indicator).to_be_visible()

    # Radix runs a CSS transform transition on selection change; await every
    # in-flight animation so the bounding box reflects the final position.
    indicator.evaluate("el => Promise.all(el.getAnimations().map(a => a.finished))")

    indicator_box = indicator.bounding_box()
    last_item_box = last_item.bounding_box()
    assert indicator_box is not None
    assert last_item_box is not None

    assert indicator_box["width"] > 0, (
        f"indicator width is {indicator_box['width']}; indicator CSS failed to "
        "apply for the 11th item (Radix Themes 3.3.0 only ships nth-child rules "
        "for up to 10 items)"
    )
    assert abs(indicator_box["x"] - last_item_box["x"]) < 2, (
        f"indicator x={indicator_box['x']} does not align with 11th item "
        f"x={last_item_box['x']}"
    )


def test_appearance_color_toggle(color_toggle_app: AppHarness, page: Page):
    assert color_toggle_app.frontend_url is not None
    page.goto(color_toggle_app.frontend_url)

    # Radio buttons locators.
    radio_system = page.get_by_role("radio").nth(0)
    radio_light = page.get_by_role("radio").nth(1)
    radio_dark = page.get_by_role("radio").nth(2)

    # Text locators to check.
    current_color_mode = page.locator("id=current_color_mode")
    resolved_color_mode = page.locator("id=resolved_color_mode")
    color_mode_cond = page.locator("id=color_mode_cond")
    root_body = page.locator('div[data-is-root-theme="true"]')

    # Background colors.
    dark_background = "rgb(17, 17, 19)"  # value based on dark native appearance, can change depending on the browser
    light_background = "rgb(255, 255, 255)"

    # check initial state
    expect(current_color_mode).to_have_text("light")
    expect(resolved_color_mode).to_have_text("light")
    expect(color_mode_cond).to_have_text("LightMode")
    expect(root_body).to_have_css("background-color", light_background)

    # click dark mode
    radio_dark.click()
    expect(current_color_mode).to_have_text("dark")
    expect(resolved_color_mode).to_have_text("dark")
    expect(color_mode_cond).to_have_text("DarkMode")
    expect(root_body).to_have_css("background-color", dark_background)

    # click light mode
    radio_light.click()
    expect(current_color_mode).to_have_text("light")
    expect(resolved_color_mode).to_have_text("light")
    expect(color_mode_cond).to_have_text("LightMode")
    expect(root_body).to_have_css("background-color", light_background)
    page.reload()
    expect(root_body).to_have_css("background-color", light_background)

    # click system mode
    radio_system.click()
    expect(current_color_mode).to_have_text("system")
    expect(resolved_color_mode).to_have_text("light")
    expect(color_mode_cond).to_have_text("LightMode")
    expect(root_body).to_have_css("background-color", light_background)

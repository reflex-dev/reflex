"""Browser regression tests for the Contact Sales dialog on mobile."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def DemoFormApp():
    """Render the shared sales dialog with a trigger."""
    from importlib import reload

    from reflex_components_internal.blocks.demo_form import demo_form_dialog
    from reflex_components_internal.components.icons import others

    import reflex as rx

    # AppHarness clears memo registrations but leaves package modules cached.
    reload(others)

    def index():
        """Return the sales dialog.

        Returns:
            The dialog and its trigger.
        """
        return demo_form_dialog(trigger=rx.el.button("Contact sales"))

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def demo_form_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the sales dialog app in dev and production modes.

    Args:
        app_harness_env: Harness class for the current environment.
        tmp_path_factory: Temporary directory factory.

    Yields:
        The running app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("demo_form"), app_source=DemoFormApp
    ) as harness:
        yield harness


@pytest.mark.parametrize("viewport_height", [400, 664])
def test_mobile_fields_scroll_with_header_and_submit_visible(
    demo_form_app: AppHarness, page: Page, viewport_height: int
) -> None:
    """Scroll to the last field without losing the dialog title or Submit.

    Args:
        demo_form_app: The running sales dialog app.
        page: Browser page.
        viewport_height: Mobile viewport height in pixels.
    """
    assert demo_form_app.frontend_url is not None
    page.set_viewport_size({"width": 390, "height": viewport_height})
    page.goto(demo_form_app.frontend_url)
    page.get_by_role("button", name="Contact sales", exact=True).click()

    dialog = page.get_by_role("dialog")
    header = dialog.get_by_role("heading", name="Book a Demo")
    submit = dialog.get_by_role("button", name="Submit", exact=True)
    last_field = dialog.locator('select[name="technical_level"]')

    expect(dialog).to_be_in_viewport(ratio=1)
    expect(header).to_be_in_viewport(ratio=1)
    expect(submit).to_be_in_viewport(ratio=1)
    expect(last_field).not_to_be_in_viewport()

    dialog.hover()
    page.mouse.wheel(0, 10000)

    expect(last_field).to_be_in_viewport(ratio=1)
    expect(header).to_be_in_viewport(ratio=1)
    expect(submit).to_be_in_viewport(ratio=1)
    last_field.select_option("Technical")
    expect(last_field).to_have_value("Technical")

"""Browser coverage for defaults configured on generated component state classes."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness, AppHarnessProd
from tests.integration.test_component_state import ComponentStateApp


@pytest.fixture(scope="module", params=[AppHarness, AppHarnessProd])
def configured_component_state_app(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Generator[AppHarness, None, None]:
    """Run the existing component-state app in development and production.

    Args:
        request: The harness parameter.
        tmp_path_factory: The temporary app directory factory.

    Yields:
        The running app harness.
    """
    with request.param.create(
        root=tmp_path_factory.mktemp("component_state_defaults"),
        app_source=ComponentStateApp,
    ) as harness:
        yield harness


def test_component_state_configured_defaults(
    configured_component_state_app: AppHarness, page: Page
):
    """Configured defaults render, update, reset, and remain per-component.

    Args:
        configured_component_state_app: The running component-state app.
        page: The browser page.
    """
    assert configured_component_state_app.frontend_url is not None
    page.goto(configured_component_state_app.frontend_url)
    expect(page.locator("#count-a")).to_have_text("0")
    expect(page.locator("#count-b")).to_have_text("0")
    expect(page.locator("#count-configured")).to_have_text("10")
    expect(page.locator("#label-configured")).to_have_text("Configured")

    page.locator("#button-configured").click()
    expect(page.locator("#count-configured")).to_have_text("11")
    expect(page.locator("#label-configured")).to_have_text("Count 11")
    expect(page.locator("#count-a")).to_have_text("0")
    expect(page.locator("#count-b")).to_have_text("0")

    page.locator("#reset-configured").click()
    expect(page.locator("#count-configured")).to_have_text("10")
    expect(page.locator("#label-configured")).to_have_text("Configured")
    page.locator("#button-a").click()
    expect(page.locator("#count-a")).to_have_text("1")
    expect(page.locator("#count-configured")).to_have_text("10")

"""Integration tests for the Moment component."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver


def MomentApp():
    """Create an app that exercises the react-moment 2.x prop changes."""
    import reflex as rx

    app = rx.App()

    class State(rx.State):
        """State used to wait for the browser connection before asserting output."""

    @app.add_page
    def index():
        return rx.vstack(
            rx.el.input(
                id="token",
                value=State.router.session.client_token,
                is_read_only=True,
            ),
            rx.moment(
                "2026-08-30",
                format="YYYY-MM-DD",
                parse=["YYYY-MM-DD"],
                trim="large",
                id="moment",
            ),
            rx.moment(
                date="2026-08-30T05:30:00",
                duration="2026-08-30T00:00:00",
                format="h [hrs] m [min]",
                id="moment-duration",
            ),
        )


@pytest.fixture(scope="module")
def moment_app(
    tmp_path_factory, app_harness_env: type[AppHarness]
) -> Generator[AppHarness, None, None]:
    """Start the Moment integration app.

    Yields:
        The running Moment app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("moment"), app_source=MomentApp
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def driver(moment_app: AppHarness) -> Generator[WebDriver, None, None]:
    """Open the Moment integration app in a browser.

    Yields:
        The browser driver connected to the Moment app.
    """
    driver = moment_app.frontend()
    try:
        token = AppHarness.poll_for_or_raise_timeout(
            lambda: driver.find_element(By.ID, "token")
        )
        AppHarness.poll_for_or_raise_timeout(lambda: token.get_attribute("value"))
        yield driver
    finally:
        driver.quit()


def test_moment_2_props_render(driver: WebDriver) -> None:
    """Changed react-moment 2.x props should render without a client error."""
    moment = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "moment")
    )
    AppHarness.expect(lambda: moment.text == "2026-08-30")
    moment_duration = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "moment-duration")
    )
    AppHarness.expect(lambda: moment_duration.text == "5 hrs 30 min")

"""Integration test for @radix-ui/themes integration."""

from __future__ import annotations

import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from nextpy.core.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver


def RadixThemesApp():
    """App using radix-themes components."""
    import nextpy as xt
    import nextpy.components.radix.themes as rdxt

    class State(xt.State):
        v: str = ""
        checked: bool = False

    def index() -> xt.Component:
        return rdxt.box(
            rdxt.text_field(
                id="token", value=State.router.session.client_token, read_only=True
            ),
            rdxt.text_field(id="tf-bare", value=State.v, on_change=State.set_v),  # type: ignore
            rdxt.text_field_root(
                rdxt.text_field_slot("🧸"),
                rdxt.text_field(id="tf-slotted", value=State.v, on_change=State.set_v),  # type: ignore
            ),
            rdxt.flex(
                rdxt.switch(
                    id="switch1",
                    checked=State.checked,
                    on_checked_change=State.set_checked,  # type: ignore
                ),
                xt.cond(
                    State.checked,
                    rdxt.text("💡", id="bulb"),
                    rdxt.text("🌙", id="moon"),
                ),
                direction="row",
                gap="2",
            ),
            rdxt.button("This is a button", size="4", variant="solid", color="plum"),
            rdxt.grid(
                *[
                    rdxt.box(rdxt.text(f"Cell {i}"), width="10vw", height="10vw")
                    for i in range(1, 10)
                ],
                columns="3",
            ),
            rdxt.container(
                rdxt.section(
                    rdxt.heading("Section 1"),
                    rdxt.text(
                        "text one with ",
                        rdxt.kbd("K"),
                        rdxt.kbd("E"),
                        rdxt.kbd("Y"),
                        "s",
                    ),
                ),
                rdxt.section(
                    rdxt.heading("Section 2", size="2"),
                    rdxt.code("Inline code yo"),
                ),
                rdxt.section(
                    rdxt.heading("Section 3"),
                    rdxt.link("Link to google", href="https://google.com"),
                    rdxt.strong("Strong text"),
                    rdxt.em("Emphasized text"),
                    rdxt.blockquote("Blockquote text"),
                    rdxt.quote("Inline quote"),
                ),
            ),
            p="5",
        )

    app = xt.App(
        state=State,
        theme=rdxt.theme(rdxt.theme_panel(), accent_color="grass"),
    )
    app.add_page(index)
    app.compile()


@pytest.fixture(scope="session")
def radix_themes_app(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start BackgroundTask app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp(f"radix_themes_app"),
        app_source=RadixThemesApp,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(radix_themes_app: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the radix_themes_app app.

    Args:
        radix_themes_app: harness for BackgroundTask app

    Yields:
        WebDriver instance.
    """
    assert radix_themes_app.app_instance is not None, "app is not running"
    driver = radix_themes_app.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture()
def token(radix_themes_app: AppHarness, driver: WebDriver) -> str:
    """Get a function that returns the active token.

    Args:
        radix_themes_app: harness for BackgroundTask app.
        driver: WebDriver instance.

    Returns:
        The token for the connected client
    """
    assert radix_themes_app.app_instance is not None
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = radix_themes_app.poll_for_value(token_input, timeout=DEFAULT_TIMEOUT * 2)
    assert token is not None

    return token


def test_radix_themes_app(
    radix_themes_app: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that background tasks work as expected.

    Args:
        radix_themes_app: harness for BackgroundTask app.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    assert radix_themes_app.app_instance is not None

    tf_bare = driver.find_element(By.ID, "tf-bare")
    tf_slotted = driver.find_element(By.ID, "tf-slotted")
    switch = driver.find_element(By.ID, "switch1")

    tf_bare.send_keys("hello")
    assert radix_themes_app.poll_for_value(tf_slotted) == "hello"
    tf_slotted.send_keys(Keys.ARROW_LEFT, Keys.ARROW_LEFT, Keys.ARROW_LEFT, "y je")
    assert (
        radix_themes_app.poll_for_value(tf_bare, exp_not_equal="hello") == "hey jello"
    )

    driver.find_element(By.ID, "moon")
    switch.click()
    time.sleep(0.5)
    driver.find_element(By.ID, "bulb")
    with pytest.raises(Exception):
        driver.find_element(By.ID, "moon")
    switch.click()
    time.sleep(0.5)
    driver.find_element(By.ID, "moon")
    with pytest.raises(Exception):
        driver.find_element(By.ID, "bulb")

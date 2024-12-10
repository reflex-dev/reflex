"""Integration tests for minified state names."""

from __future__ import annotations

from functools import partial
from typing import Generator, Optional, Type

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from reflex.config import environment
from reflex.testing import AppHarness, AppHarnessProd


def MinifiedStatesApp(minify: bool | None) -> None:
    """A test app for minified state names.

    Args:
        minify: whether to minify state names
    """
    import reflex as rx

    class MinifiedState(rx.State):
        """State for the MinifiedStatesApp app."""

        pass

    app = rx.App()

    def index():
        return rx.vstack(
            rx.input(
                value=MinifiedState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            rx.text(f"minify: {minify}", id="minify"),
            rx.text(MinifiedState.get_name(), id="state_name"),
            rx.text(MinifiedState.get_full_name(), id="state_full_name"),
        )

    app.add_page(index)


@pytest.fixture(
    params=[
        pytest.param(False),
        pytest.param(True),
        pytest.param(None),
    ],
)
def minify_state_env(
    request: pytest.FixtureRequest,
) -> Generator[Optional[bool], None, None]:
    """Set the environment variable to minify state names.

    Args:
        request: pytest fixture request

    Yields:
        minify_states: whether to minify state names
    """
    minify_states: Optional[bool] = request.param
    environment.REFLEX_MINIFY_STATES.set(minify_states)
    yield minify_states
    environment.REFLEX_MINIFY_STATES.set(None)


@pytest.fixture
def test_app(
    app_harness_env: Type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
    minify_state_env: Optional[bool],
) -> Generator[AppHarness, None, None]:
    """Start MinifiedStatesApp app at tmp_path via AppHarness.

    Args:
        app_harness_env: either AppHarness (dev) or AppHarnessProd (prod)
        tmp_path_factory: pytest tmp_path_factory fixture
        minify_state_env: need to request this fixture to set env before the app starts

    Yields:
        running AppHarness instance

    """
    name = f"testminifiedstates_{app_harness_env.__name__.lower()}"
    with app_harness_env.create(
        root=tmp_path_factory.mktemp(name),
        app_name=name,
        app_source=partial(MinifiedStatesApp, minify=minify_state_env),  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(test_app: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the test_app app.

    Args:
        test_app: harness for MinifiedStatesApp app

    Yields:
        WebDriver instance.

    """
    assert test_app.app_instance is not None, "app is not running"
    driver = test_app.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def test_minified_states(
    test_app: AppHarness,
    driver: WebDriver,
    minify_state_env: Optional[bool],
) -> None:
    """Test minified state names.

    Args:
        test_app: harness for MinifiedStatesApp
        driver: WebDriver instance.
        minify_state_env: whether state minification is enabled by env var.

    """
    assert test_app.app_instance is not None, "app is not running"

    is_prod = isinstance(test_app, AppHarnessProd)

    # default to minifying in production
    should_minify: bool = is_prod

    # env overrides default
    if minify_state_env is not None:
        should_minify = minify_state_env

    # get a reference to the connected client
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = test_app.poll_for_value(token_input)
    assert token

    state_name_text = driver.find_element(By.ID, "state_name")
    assert state_name_text
    state_name = state_name_text.text

    state_full_name_text = driver.find_element(By.ID, "state_full_name")
    assert state_full_name_text
    _ = state_full_name_text.text

    assert test_app.app_module
    module_state_prefix = test_app.app_module.__name__.replace(".", "___")

    if should_minify:
        assert len(state_name) == 1
    else:
        assert state_name == f"{module_state_prefix}____minified_state"

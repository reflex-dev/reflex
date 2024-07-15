"""Test computed vars."""

from __future__ import annotations

import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver


def ComputedVars():
    """Test app for computed vars."""
    import reflex as rx

    class StateMixin(rx.State, mixin=True):
        pass

    class State(StateMixin, rx.State):
        count: int = 0

        # cached var with dep on count
        @rx.var(cache=True, interval=15)
        def count1(self) -> int:
            return self.count

        # cached backend var with dep on count
        @rx.var(cache=True, interval=15, backend=True)
        def count1_backend(self) -> int:
            return self.count

        # same as above but implicit backend with `_` prefix
        @rx.var(cache=True, interval=15)
        def _count1_backend(self) -> int:
            return self.count

        # explicit disabled auto_deps
        @rx.var(interval=15, cache=True, auto_deps=False)
        def count3(self) -> int:
            # this will not add deps, because auto_deps is False
            print(self.count1)

            return self.count

        # explicit dependency on count var
        @rx.var(cache=True, deps=["count"], auto_deps=False)
        def depends_on_count(self) -> int:
            return self.count

        # explicit dependency on count1 var
        @rx.var(cache=True, deps=[count1], auto_deps=False)
        def depends_on_count1(self) -> int:
            return self.count

        @rx.var(deps=[count3], auto_deps=False, cache=True)
        def depends_on_count3(self) -> int:
            return self.count

        def increment(self):
            self.count += 1

        def mark_dirty(self):
            self._mark_dirty()

    assert State.backend_vars == {}

    def index() -> rx.Component:
        return rx.center(
            rx.vstack(
                rx.input(
                    id="token",
                    value=State.router.session.client_token,
                    is_read_only=True,
                ),
                rx.button("Increment", on_click=State.increment, id="increment"),
                rx.button("Do nothing", on_click=State.mark_dirty, id="mark_dirty"),
                rx.text("count:"),
                rx.text(State.count, id="count"),
                rx.text("count1:"),
                rx.text(State.count1, id="count1"),
                rx.text("count1_backend:"),
                rx.text(State.count1_backend, id="count1_backend"),
                rx.text("_count1_backend:"),
                rx.text(State._count1_backend, id="_count1_backend"),
                rx.text("count3:"),
                rx.text(State.count3, id="count3"),
                rx.text("depends_on_count:"),
                rx.text(
                    State.depends_on_count,
                    id="depends_on_count",
                ),
                rx.text("depends_on_count1:"),
                rx.text(
                    State.depends_on_count1,
                    id="depends_on_count1",
                ),
                rx.text("depends_on_count3:"),
                rx.text(
                    State.depends_on_count3,
                    id="depends_on_count3",
                ),
            ),
        )

    # raise Exception(State.count3._deps(objclass=State))
    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def computed_vars(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start ComputedVars app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp(f"computed_vars"),
        app_source=ComputedVars,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(computed_vars: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the computed_vars app.

    Args:
        computed_vars: harness for ComputedVars app

    Yields:
        WebDriver instance.
    """
    assert computed_vars.app_instance is not None, "app is not running"
    driver = computed_vars.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture()
def token(computed_vars: AppHarness, driver: WebDriver) -> str:
    """Get a function that returns the active token.

    Args:
        computed_vars: harness for ComputedVars app.
        driver: WebDriver instance.

    Returns:
        The token for the connected client
    """
    assert computed_vars.app_instance is not None
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = computed_vars.poll_for_value(token_input, timeout=DEFAULT_TIMEOUT * 2)
    assert token is not None

    return token


@pytest.mark.asyncio
async def test_computed_vars(
    computed_vars: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that computed vars are working as expected.

    Args:
        computed_vars: harness for ComputedVars app.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    assert computed_vars.app_instance is not None

    state_name = computed_vars.get_state_name("_state")
    full_state_name = computed_vars.get_full_state_name(["_state"])
    token = f"{token}_{full_state_name}"
    state = (await computed_vars.get_state(token)).substates[state_name]
    assert state is not None
    assert state.count1_backend == 0
    assert state._count1_backend == 0

    # test that backend var is not rendered
    count1_backend = driver.find_element(By.ID, "count1_backend")
    assert count1_backend
    assert count1_backend.text == ""
    _count1_backend = driver.find_element(By.ID, "_count1_backend")
    assert _count1_backend
    assert _count1_backend.text == ""

    count = driver.find_element(By.ID, "count")
    assert count
    assert count.text == "0"

    count1 = driver.find_element(By.ID, "count1")
    assert count1
    assert count1.text == "0"

    count3 = driver.find_element(By.ID, "count3")
    assert count3
    assert count3.text == "0"

    depends_on_count = driver.find_element(By.ID, "depends_on_count")
    assert depends_on_count
    assert depends_on_count.text == "0"

    depends_on_count1 = driver.find_element(By.ID, "depends_on_count1")
    assert depends_on_count1
    assert depends_on_count1.text == "0"

    depends_on_count3 = driver.find_element(By.ID, "depends_on_count3")
    assert depends_on_count3
    assert depends_on_count3.text == "0"

    increment = driver.find_element(By.ID, "increment")
    assert increment.is_enabled()

    mark_dirty = driver.find_element(By.ID, "mark_dirty")
    assert mark_dirty.is_enabled()

    mark_dirty.click()

    increment.click()
    assert computed_vars.poll_for_content(count, timeout=2, exp_not_equal="0") == "1"
    assert computed_vars.poll_for_content(count1, timeout=2, exp_not_equal="0") == "1"
    assert (
        computed_vars.poll_for_content(depends_on_count, timeout=2, exp_not_equal="0")
        == "1"
    )
    state = (await computed_vars.get_state(token)).substates[state_name]
    assert state is not None
    assert state.count1_backend == 1
    assert count1_backend.text == ""
    assert state._count1_backend == 1
    assert _count1_backend.text == ""

    mark_dirty.click()
    with pytest.raises(TimeoutError):
        _ = computed_vars.poll_for_content(count3, timeout=5, exp_not_equal="0")

    time.sleep(10)
    assert count3.text == "0"
    assert depends_on_count3.text == "0"
    mark_dirty.click()
    assert computed_vars.poll_for_content(count3, timeout=2, exp_not_equal="0") == "1"
    assert depends_on_count3.text == "1"

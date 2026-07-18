"""Ensure that Event Chains are properly queued and handled between frontend and backend."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver
from tests.integration.utils import (
    poll_assert_event_order,
    poll_assert_relative_event_order,
)

MANY_EVENTS = 50


def EventChain():
    """App with chained event handlers."""
    import asyncio
    import time

    import reflex as rx

    # repeated here since the outer global isn't exported into the App module
    MANY_EVENTS = 50

    class State(rx.State):
        event_order: list[str] = []
        interim_value: str = ""
        cond_input: str = ""

        @rx.event
        def event_no_args(self):
            self.event_order.append("event_no_args")

        @rx.event
        def event_arg(self, arg):
            self.event_order.append(f"event_arg:{arg}")

        @rx.event
        def event_arg_repr_type(self, arg):
            self.event_order.append(f"event_arg_repr:{arg!r}_{type(arg).__name__}")

        @rx.event
        def event_nested_1(self):
            self.event_order.append("event_nested_1")
            yield State.event_nested_2
            yield State.event_arg("nested_1")

        @rx.event
        def event_nested_2(self):
            self.event_order.append("event_nested_2")
            yield State.event_nested_3
            yield rx.console_log("event_nested_2")
            yield State.event_arg("nested_2")

        @rx.event
        def event_nested_3(self):
            self.event_order.append("event_nested_3")
            yield State.event_no_args
            yield State.event_arg("nested_3")

        @rx.event
        def on_load_return_chain(self):
            self.event_order.append("on_load_return_chain")
            return [State.event_arg(1), State.event_arg(2), State.event_arg(3)]

        @rx.event
        def on_load_yield_chain(self):
            self.event_order.append("on_load_yield_chain")
            yield State.event_arg(4)
            yield State.event_arg(5)
            yield State.event_arg(6)

        @rx.event
        def click_return_event(self):
            self.event_order.append("click_return_event")
            return State.event_no_args

        @rx.event
        def click_return_events(self):
            self.event_order.append("click_return_events")
            return [
                State.event_arg(7),
                rx.console_log("click_return_events"),
                State.event_arg(8),
                State.event_arg(9),
            ]

        @rx.event
        def click_yield_chain(self):
            self.event_order.append("click_yield_chain:0")
            yield State.event_arg(10)
            self.event_order.append("click_yield_chain:1")
            yield rx.console_log("click_yield_chain")
            yield State.event_arg(11)
            self.event_order.append("click_yield_chain:2")
            yield State.event_arg(12)
            self.event_order.append("click_yield_chain:3")

        @rx.event
        def click_yield_many_events(self):
            self.event_order.append("click_yield_many_events")
            for ix in range(MANY_EVENTS):
                yield State.event_arg(ix)
                yield rx.console_log(f"many_events_{ix}")
            self.event_order.append("click_yield_many_events_done")

        @rx.event
        def click_yield_nested(self):
            self.event_order.append("click_yield_nested")
            yield State.event_nested_1
            yield State.event_arg("yield_nested")

        @rx.event
        def redirect_return_chain(self):
            self.event_order.append("redirect_return_chain")
            yield rx.redirect("/on-load-return-chain")

        @rx.event
        def redirect_yield_chain(self):
            self.event_order.append("redirect_yield_chain")
            yield rx.redirect("/on-load-yield-chain")

        @rx.event
        def click_return_int_type(self):
            self.event_order.append("click_return_int_type")
            return State.event_arg_repr_type(1)

        @rx.event
        def click_return_dict_type(self):
            self.event_order.append("click_return_dict_type")
            return State.event_arg_repr_type({"a": 1})

        @rx.event
        async def click_yield_interim_value_async(self):
            self.interim_value = "interim"
            yield
            await asyncio.sleep(0.5)
            self.interim_value = "final"

        @rx.event
        def click_yield_interim_value(self):
            self.interim_value = "interim"
            yield
            time.sleep(0.5)
            self.interim_value = "final"

        @rx.event
        def set_cond_input(self, value: str):
            self.cond_input = value

    # Frontend FunctionVar branch: writes a label into a DOM data-attribute.
    mark_dom_fn = rx.vars.FunctionStringVar.create(
        "((label) => { "
        "const el = document.getElementById('mixed_cond_marker');"
        "if (el) { el.setAttribute('data-value', label); }"
        "})"
    ).to(rx.EventChain)

    app = rx.App()

    common_elements = rx.vstack(
        rx.input(
            value=State.router.session.client_token, is_read_only=True, id="token"
        ),
        rx.vstack(
            rx.foreach(State.event_order, lambda x: rx.text(x)), id="event_order"
        ),
        rx.input(value=State.is_hydrated, is_read_only=True, id="is_hydrated"),
    )

    @app.add_page
    def index():
        return rx.fragment(
            common_elements,
            rx.input(value=State.interim_value, is_read_only=True, id="interim_value"),
            rx.button(
                "Return Event",
                id="return_event",
                on_click=State.click_return_event,
            ),
            rx.button(
                "Return Events",
                id="return_events",
                on_click=State.click_return_events,
            ),
            rx.button(
                "Yield Chain",
                id="yield_chain",
                on_click=State.click_yield_chain,
            ),
            rx.button(
                "Yield Many events",
                id="yield_many_events",
                on_click=State.click_yield_many_events,
            ),
            rx.button(
                "Yield Nested",
                id="yield_nested",
                on_click=State.click_yield_nested,
            ),
            rx.button(
                "Redirect Yield Chain",
                id="redirect_yield_chain",
                on_click=State.redirect_yield_chain,
            ),
            rx.button(
                "Redirect Return Chain",
                id="redirect_return_chain",
                on_click=State.redirect_return_chain,
            ),
            rx.button(
                "Click Int Type",
                id="click_int_type",
                on_click=lambda: State.event_arg_repr_type(1),
            ),
            rx.button(
                "Click Dict Type",
                id="click_dict_type",
                on_click=lambda: State.event_arg_repr_type({"a": 1}),
            ),
            rx.button(
                "Return Chain Int Type",
                id="return_int_type",
                on_click=State.click_return_int_type,
            ),
            rx.button(
                "Return Chain Dict Type",
                id="return_dict_type",
                on_click=State.click_return_dict_type,
            ),
            rx.button(
                "Click Yield Interim Value (Async)",
                id="click_yield_interim_value_async",
                on_click=State.click_yield_interim_value_async,
            ),
            rx.button(
                "Click Yield Interim Value",
                id="click_yield_interim_value",
                on_click=State.click_yield_interim_value,
            ),
            rx.input(
                value=State.cond_input,
                on_change=State.set_cond_input,
                id="cond_input",
            ),
            rx.box(
                State.cond_input,
                id="mixed_cond_marker",
                custom_attrs={"data-value": ""},
            ),
            rx.button(
                "Mixed Cond",
                id="mixed_cond_btn",
                on_click=lambda: rx.cond(
                    State.cond_input == "fn",
                    mark_dom_fn.partial("fn_branch"),
                    State.event_arg("ev_branch"),
                ),
            ),
        )

    def on_load_return_chain():
        return rx.fragment(
            rx.text("return"),
            common_elements,
        )

    def on_load_yield_chain():
        return rx.fragment(
            rx.text("yield"),
            common_elements,
        )

    def on_mount_return_chain():
        return rx.fragment(
            rx.text(
                "return",
                on_mount=State.on_load_return_chain,
                on_unmount=lambda: State.event_arg("unmount"),
            ),
            common_elements,
            rx.button("Unmount", on_click=rx.redirect("/"), id="unmount"),
        )

    def on_mount_yield_chain():
        return rx.fragment(
            rx.text(
                "yield",
                on_mount=[
                    State.on_load_yield_chain,
                    lambda: State.event_arg("mount"),
                ],
                on_unmount=State.event_no_args,
            ),
            common_elements,
            rx.button("Unmount", on_click=rx.redirect("/"), id="unmount"),
        )

    app.add_page(on_load_return_chain, on_load=State.on_load_return_chain)
    app.add_page(on_load_yield_chain, on_load=State.on_load_yield_chain)
    app.add_page(on_mount_return_chain)
    app.add_page(on_mount_yield_chain)


@pytest.fixture(scope="module")
def event_chain(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start EventChain app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    os.environ["REFLEX_REACT_STRICT_MODE"] = "0"
    with AppHarness.create(
        root=tmp_path_factory.mktemp("event_chain"),
        app_source=EventChain,
    ) as harness:
        yield harness


@pytest.fixture
def driver(event_chain: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the event_chain app.

    Args:
        event_chain: harness for EventChain app

    Yields:
        WebDriver instance.
    """
    assert event_chain.app_instance is not None, "app is not running"
    driver = event_chain.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture(scope="module")
def event_chain_strict(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start EventChain app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    os.environ["REFLEX_REACT_STRICT_MODE"] = "1"
    with AppHarness.create(
        root=tmp_path_factory.mktemp("event_chain_strict"),
        app_source=EventChain,
        app_name="event_chain_strict",
    ) as harness:
        yield harness


@pytest.fixture
def driver_strict(event_chain_strict: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the event_chain_strict app.

    Args:
        event_chain_strict: harness for EventChain app

    Yields:
        WebDriver instance.
    """
    assert event_chain_strict.app_instance is not None, "app is not running"
    driver = event_chain_strict.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def assert_token(event_chain: AppHarness, driver: WebDriver) -> str:
    """Get the token associated with backend state.

    Args:
        event_chain: harness for EventChain app.
        driver: WebDriver instance.

    Returns:
        The token visible in the driver browser.
    """
    assert event_chain.app_instance is not None
    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )

    # wait for the backend connection to send the token
    token = event_chain.poll_for_value(token_input)
    assert token is not None

    state_name = event_chain.get_full_state_name(["_state"])
    return f"{token}_{state_name}"


@pytest.mark.parametrize(
    ("button_id", "exp_event_order"),
    [
        ("return_event", ["click_return_event", "event_no_args"]),
        (
            "return_events",
            ["click_return_events", "event_arg:7", "event_arg:8", "event_arg:9"],
        ),
        (
            "yield_chain",
            [
                "click_yield_chain:0",
                "click_yield_chain:1",
                "click_yield_chain:2",
                "click_yield_chain:3",
                "event_arg:10",
                "event_arg:11",
                "event_arg:12",
            ],
        ),
        (
            "yield_many_events",
            [
                "click_yield_many_events",
                "click_yield_many_events_done",
                *[f"event_arg:{ix}" for ix in range(MANY_EVENTS)],
            ],
        ),
        (
            "yield_nested",
            [
                "click_yield_nested",
                "event_nested_1",
                "event_arg:yield_nested",
                "event_nested_2",
                "event_arg:nested_1",
                "event_nested_3",
                "event_arg:nested_2",
                "event_no_args",
                "event_arg:nested_3",
            ],
        ),
        (
            "redirect_return_chain",
            [
                "redirect_return_chain",
                "on_load_return_chain",
                "event_arg:1",
                "event_arg:2",
                "event_arg:3",
            ],
        ),
        (
            "redirect_yield_chain",
            [
                "redirect_yield_chain",
                "on_load_yield_chain",
                "event_arg:4",
                "event_arg:5",
                "event_arg:6",
            ],
        ),
        (
            "click_int_type",
            ["event_arg_repr:1_int"],
        ),
        (
            "click_dict_type",
            ["event_arg_repr:{'a': 1}_dict"],
        ),
        (
            "return_int_type",
            ["click_return_int_type", "event_arg_repr:1_int"],
        ),
        (
            "return_dict_type",
            ["click_return_dict_type", "event_arg_repr:{'a': 1}_dict"],
        ),
    ],
)
def test_event_chain_click(
    event_chain: AppHarness,
    driver: WebDriver,
    button_id: str,
    exp_event_order: list[str],
):
    """Click the button, assert that the events are handled in the correct order.

    Args:
        event_chain: AppHarness for the event_chain app
        driver: selenium WebDriver open to the app
        button_id: the ID of the button to click
        exp_event_order: the expected events recorded in the State
    """
    assert_token(event_chain, driver)
    btn = driver.find_element(By.ID, button_id)
    btn.click()

    poll_assert_event_order(driver, exp_event_order)


@pytest.mark.parametrize(
    ("uri", "exp_event_order"),
    [
        (
            "/on-load-return-chain",
            [
                "on_load_return_chain",
                "event_arg:1",
                "event_arg:2",
                "event_arg:3",
            ],
        ),
        (
            "/on-load-yield-chain",
            [
                "on_load_yield_chain",
                "event_arg:4",
                "event_arg:5",
                "event_arg:6",
            ],
        ),
    ],
)
def test_event_chain_on_load(
    event_chain: AppHarness,
    driver: WebDriver,
    uri: str,
    exp_event_order: list[str],
):
    """Load the URI, assert that the events are handled in the correct order.

    Args:
        event_chain: AppHarness for the event_chain app
        driver: selenium WebDriver open to the app
        uri: the page to load
        exp_event_order: the expected events recorded in the State
    """
    assert event_chain.frontend_url is not None
    driver.get(event_chain.frontend_url.removesuffix("/") + uri)
    assert_token(event_chain, driver)

    poll_assert_event_order(driver, exp_event_order)
    assert (
        event_chain.poll_for_value(
            driver.find_element(By.ID, "is_hydrated"), exp_not_equal="false"
        )
        == "true"
    )


@pytest.mark.parametrize(
    ("uri", "expected_counts", "ordering_rules"),
    [
        (
            "/on-mount-return-chain",
            {
                "on_load_return_chain": 1,
                "event_arg:1": 1,
                "event_arg:2": 1,
                "event_arg:3": 1,
                "event_arg:unmount": 1,
            },
            [
                # on_load before chain and unmount
                (("on_load_return_chain", 0), ("event_arg:1", 0)),
                (("on_load_return_chain", 0), ("event_arg:unmount", 0)),
                # Chain in order
                (("event_arg:1", 0), ("event_arg:2", 0)),
                (("event_arg:2", 0), ("event_arg:3", 0)),
            ],
        ),
        (
            "/on-mount-yield-chain",
            {
                "on_load_yield_chain": 1,
                "event_arg:4": 1,
                "event_arg:5": 1,
                "event_arg:6": 1,
                "event_arg:mount": 1,
                "event_no_args": 1,
            },
            [
                # on_load before chain and mount
                (("on_load_yield_chain", 0), ("event_arg:4", 0)),
                (("on_load_yield_chain", 0), ("event_arg:mount", 0)),
                # Chain in order
                (("event_arg:4", 0), ("event_arg:5", 0)),
                (("event_arg:5", 0), ("event_arg:6", 0)),
                # mount before event_no_args
                (("event_arg:mount", 0), ("event_no_args", 0)),
            ],
        ),
    ],
)
def test_event_chain_on_mount(
    event_chain: AppHarness,
    driver: WebDriver,
    uri: str,
    expected_counts: dict[str, int],
    ordering_rules: list,
):
    """Load the URI, assert that the events are handled in the correct order.

    These pages use `on_mount` and `on_unmount`, which get fired twice in dev mode
    due to react StrictMode being used.

    In prod mode, these events are only fired once.

    Args:
        event_chain: AppHarness for the event_chain app
        driver: selenium WebDriver open to the app
        uri: the page to load
        expected_counts: mapping of event name to expected occurrence count
        ordering_rules: relative ordering constraints between event occurrences
    """
    assert event_chain.frontend_url is not None
    driver.get(event_chain.frontend_url.removesuffix("/") + uri)

    unmount_button = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "unmount")
    )
    assert_token(event_chain, driver)
    unmount_button.click()

    poll_assert_relative_event_order(driver, expected_counts, ordering_rules)


@pytest.mark.parametrize(
    ("uri", "expected_counts", "ordering_rules"),
    [
        (
            "/on-mount-return-chain",
            {
                "on_load_return_chain": 2,
                "event_arg:1": 2,
                "event_arg:2": 2,
                "event_arg:3": 2,
                "event_arg:unmount": 2,
            },
            [
                # First on_load before first chain and first unmount
                (("on_load_return_chain", 0), ("event_arg:1", 0)),
                (("on_load_return_chain", 0), ("event_arg:unmount", 0)),
                # First chain in order
                (("event_arg:1", 0), ("event_arg:2", 0)),
                (("event_arg:2", 0), ("event_arg:3", 0)),
                # First unmount before second on_load
                (("event_arg:unmount", 0), ("on_load_return_chain", 1)),
                # Second on_load before second chain and second unmount
                (("on_load_return_chain", 1), ("event_arg:1", 1)),
                (("on_load_return_chain", 1), ("event_arg:unmount", 1)),
                # Second chain in order
                (("event_arg:1", 1), ("event_arg:2", 1)),
                (("event_arg:2", 1), ("event_arg:3", 1)),
            ],
        ),
        (
            "/on-mount-yield-chain",
            {
                "on_load_yield_chain": 2,
                "event_arg:4": 2,
                "event_arg:5": 2,
                "event_arg:6": 2,
                "event_arg:mount": 2,
                "event_no_args": 2,
            },
            [
                # First on_load before first chain and first mount
                (("on_load_yield_chain", 0), ("event_arg:4", 0)),
                (("on_load_yield_chain", 0), ("event_arg:mount", 0)),
                # First chain in order
                (("event_arg:4", 0), ("event_arg:5", 0)),
                (("event_arg:5", 0), ("event_arg:6", 0)),
                # First mount before first event_no_args
                (("event_arg:mount", 0), ("event_no_args", 0)),
                # First event_no_args before second on_load
                (("event_no_args", 0), ("on_load_yield_chain", 1)),
                # Second on_load before second chain and second mount
                (("on_load_yield_chain", 1), ("event_arg:4", 1)),
                (("on_load_yield_chain", 1), ("event_arg:mount", 1)),
                # Second chain in order
                (("event_arg:4", 1), ("event_arg:5", 1)),
                (("event_arg:5", 1), ("event_arg:6", 1)),
                # Second mount before second event_no_args
                (("event_arg:mount", 1), ("event_no_args", 1)),
            ],
        ),
    ],
)
def test_event_chain_on_mount_strict(
    event_chain_strict: AppHarness,
    driver_strict: WebDriver,
    uri: str,
    expected_counts: dict[str, int],
    ordering_rules: list,
):
    """Run the test_event_chain_on_mount test with strict mode enabled.

    Args:
        event_chain_strict: AppHarness for the event_chain app with strict mode enabled
        driver_strict: selenium WebDriver open to the app with strict mode enabled
        uri: the page to load
        expected_counts: mapping of event name to expected occurrence count
        ordering_rules: relative ordering constraints between event occurrences
    """
    test_event_chain_on_mount(
        event_chain=event_chain_strict,
        driver=driver_strict,
        uri=uri,
        expected_counts=expected_counts,
        ordering_rules=ordering_rules,
    )


@pytest.mark.parametrize(
    "button_id",
    [
        "click_yield_interim_value_async",
        "click_yield_interim_value",
    ],
)
def test_yield_state_update(event_chain: AppHarness, driver: WebDriver, button_id: str):
    """Click the button, assert that the interim value is set, then final value is set.

    Args:
        event_chain: AppHarness for the event_chain app
        driver: selenium WebDriver open to the app
        button_id: the ID of the button to click
    """
    assert_token(event_chain, driver)
    interim_value_input = driver.find_element(By.ID, "interim_value")

    btn = driver.find_element(By.ID, button_id)
    btn.click()
    assert (
        event_chain.poll_for_value(interim_value_input, exp_not_equal="") == "interim"
    )
    assert (
        event_chain.poll_for_value(interim_value_input, exp_not_equal="interim")
        == "final"
    )


def test_mixed_cond_event_lambda(event_chain: AppHarness, driver: WebDriver):
    """Verify a lambda returning rx.cond with a FunctionVar branch and an EventSpec branch.

    Each branch is exercised end-to-end: the FunctionVar branch updates a DOM
    data-attribute via a frontend-only function, and the EventSpec branch
    dispatches a backend event handler.

    Args:
        event_chain: AppHarness for the event_chain app
        driver: selenium WebDriver open to the app
    """
    assert_token(event_chain, driver)
    cond_input = driver.find_element(By.ID, "cond_input")
    marker = driver.find_element(By.ID, "mixed_cond_marker")
    btn = driver.find_element(By.ID, "mixed_cond_btn")

    # Default cond_input ("") -> EventSpec branch fires the backend handler.
    btn.click()
    poll_assert_event_order(driver, ["event_arg:ev_branch"])
    assert marker.get_attribute("data-value") == ""

    # Switch to the FunctionVar branch and click again.
    cond_input.send_keys("fn")
    assert event_chain.poll_for_content(marker, exp_not_equal="") == "fn"
    btn.click()
    AppHarness._poll_for(lambda: marker.get_attribute("data-value") == "fn_branch")
    assert marker.get_attribute("data-value") == "fn_branch"
    # Backend event order is unchanged because only the frontend function ran.
    poll_assert_event_order(driver, ["event_arg:ev_branch"])

"""Ensure stopPropagation and preventDefault work as expected."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine, Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from reflex.testing import AppHarness, WebDriver


def TestEventAction():
    """App for testing event_actions."""
    from typing import Any

    import reflex as rx

    class EventActionState(rx.State):
        order: list[str]

        def on_click(self, ev):
            self.order.append(f"on_click:{ev}")

        @rx.event
        def on_click2(self):
            self.order.append("on_click2")

        def on_click_throttle(self):
            self.order.append("on_click_throttle")

        def on_click_debounce(self):
            self.order.append("on_click_debounce")

        @rx.event
        def on_submit(self, form_data: dict[str, Any]):
            self.order.append("on_submit")

    class EventFiringComponent(rx.Component):
        """A component that fires onClick event without passing DOM event."""

        tag = "EventFiringComponent"

        def _get_custom_code(self) -> str | None:
            return """
                function EventFiringComponent(props) {
                    return jsx(
                        "div",
                        {"id":props.id,"onClick":(e) => props.onClick("foo")},
                        "Event Firing Component",
                    )
                }"""

        @classmethod
        def get_event_triggers(cls):
            return {"on_click": rx.event.no_args_event_spec}

    def index():
        return rx.vstack(
            rx.input(
                value=EventActionState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            rx.button("No events", id="btn-no-events"),
            rx.button(
                "Stop Prop Only",
                id="btn-stop-prop-only",
                on_click=rx.stop_propagation,
            ),
            rx.button(
                "Click event",
                on_click=EventActionState.on_click("no_event_actions"),  # pyright: ignore [reportCallIssue]
                id="btn-click-event",
            ),
            rx.button(
                "Click stop propagation",
                on_click=EventActionState.on_click("stop_propagation").stop_propagation,  # pyright: ignore [reportCallIssue]
                id="btn-click-stop-propagation",
            ),
            rx.button(
                "Click stop propagation2",
                on_click=EventActionState.on_click2.stop_propagation,
                id="btn-click-stop-propagation2",
            ),
            rx.button(
                "Click event 2",
                on_click=EventActionState.on_click2,
                id="btn-click-event2",
            ),
            rx.link(
                "Link",
                href="?link",
                on_click=EventActionState.on_click("link_no_event_actions"),  # pyright: ignore [reportCallIssue]
                id="link",
            ),
            rx.link(
                "Link Stop Propagation",
                href="?link-stop-propagation",
                on_click=EventActionState.on_click(  # pyright: ignore [reportCallIssue]
                    "link_stop_propagation"
                ).stop_propagation,
                id="link-stop-propagation",
            ),
            rx.link(
                "Link Prevent Default Only",
                href="/invalid",
                on_click=rx.prevent_default,
                id="link-prevent-default-only",
            ),
            rx.link(
                "Link Prevent Default",
                href="/invalid",
                on_click=EventActionState.on_click(  # pyright: ignore [reportCallIssue]
                    "link_prevent_default"
                ).prevent_default,
                id="link-prevent-default",
            ),
            rx.link(
                "Link Both",
                href="/invalid",
                on_click=EventActionState.on_click(  # pyright: ignore [reportCallIssue]
                    "link_both"
                ).stop_propagation.prevent_default,
                id="link-stop-propagation-prevent-default",
            ),
            EventFiringComponent.create(
                id="custom-stop-propagation",
                on_click=EventActionState.on_click(  # pyright: ignore [reportCallIssue]
                    "custom-stop-propagation"
                ).stop_propagation,
            ),
            EventFiringComponent.create(
                id="custom-prevent-default",
                on_click=EventActionState.on_click(  # pyright: ignore [reportCallIssue]
                    "custom-prevent-default"
                ).prevent_default,
            ),
            rx.button(
                "Throttle",
                id="btn-throttle",
                on_click=lambda: EventActionState.on_click_throttle.throttle(  # pyright: ignore [reportFunctionMemberAccess]
                    200
                ).stop_propagation,
            ),
            rx.button(
                "Debounce",
                id="btn-debounce",
                on_click=EventActionState.on_click_debounce.debounce(  # pyright: ignore [reportFunctionMemberAccess]
                    200
                ).stop_propagation,
            ),
            rx.list(  # pyright: ignore [reportAttributeAccessIssue]
                rx.foreach(
                    EventActionState.order,
                    rx.list_item,
                ),
            ),
            on_click=EventActionState.on_click("outer"),  # pyright: ignore [reportCallIssue]
        ), rx.form(
            rx.dialog.root(
                rx.dialog.trigger(
                    rx.button("Open Dialog", type="button", id="btn-dialog"),
                    on_click=rx.stop_propagation,
                ),
                rx.dialog.content(
                    rx.dialog.close(
                        rx.form(
                            rx.button("Submit", id="btn-submit"),
                            on_submit=EventActionState.on_submit.stop_propagation,  # pyright: ignore [reportCallIssue]
                        ),
                    ),
                ),
            ),
            on_submit=EventActionState.on_submit,  # pyright: ignore [reportCallIssue]
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def event_action(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start TestEventAction app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("event_action"),
        app_source=TestEventAction,
    ) as harness:
        yield harness


@pytest.fixture
def driver(event_action: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the event_action app.

    Args:
        event_action: harness for TestEventAction app

    Yields:
        WebDriver instance.
    """
    assert event_action.app_instance is not None, "app is not running"
    driver = event_action.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture
def token(event_action: AppHarness, driver: WebDriver) -> str:
    """Get the token associated with backend state.

    Args:
        event_action: harness for TestEventAction app.
        driver: WebDriver instance.

    Returns:
        The token visible in the driver browser.
    """
    assert event_action.app_instance is not None
    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )

    # wait for the backend connection to send the token
    token = event_action.poll_for_value(token_input)
    assert token is not None

    return token


@pytest.fixture
def poll_for_order(
    event_action: AppHarness, token: str
) -> Callable[[list[str]], Coroutine[None, None, None]]:
    """Poll for the order list to match the expected order.

    Args:
        event_action: harness for TestEventAction app.
        token: The token visible in the driver browser.

    Returns:
        An async function that polls for the order list to match the expected order.
    """
    state_name = event_action.get_state_name("_event_action_state")
    state_full_name = event_action.get_full_state_name(["_event_action_state"])

    async def _poll_for_order(exp_order: list[str]):
        async def _backend_state():
            return await event_action.get_state(f"{token}_{state_full_name}")

        async def _check():
            return (await _backend_state()).substates[state_name].order == exp_order

        await AppHarness._poll_for_async(_check)
        assert (await _backend_state()).substates[state_name].order == exp_order

    return _poll_for_order


@pytest.mark.parametrize(
    ("element_id", "exp_order"),
    [
        ("btn-no-events", ["on_click:outer"]),
        ("btn-stop-prop-only", []),
        ("btn-click-event", ["on_click:no_event_actions", "on_click:outer"]),
        ("btn-click-stop-propagation", ["on_click:stop_propagation"]),
        ("btn-click-stop-propagation2", ["on_click2"]),
        ("btn-click-event2", ["on_click2", "on_click:outer"]),
        ("link", ["on_click:link_no_event_actions", "on_click:outer"]),
        ("link-stop-propagation", ["on_click:link_stop_propagation"]),
        ("link-prevent-default", ["on_click:link_prevent_default", "on_click:outer"]),
        ("link-prevent-default-only", ["on_click:outer"]),
        ("link-stop-propagation-prevent-default", ["on_click:link_both"]),
        (
            "custom-stop-propagation",
            ["on_click:custom-stop-propagation", "on_click:outer"],
        ),
        (
            "custom-prevent-default",
            ["on_click:custom-prevent-default", "on_click:outer"],
        ),
    ],
)
@pytest.mark.usefixtures("token")
@pytest.mark.asyncio
async def test_event_actions(
    driver: WebDriver,
    poll_for_order: Callable[[list[str]], Coroutine[None, None, None]],
    element_id: str,
    exp_order: list[str],
):
    """Click links and buttons and assert on fired events.

    Args:
        driver: WebDriver instance.
        poll_for_order: function that polls for the order list to match the expected order.
        element_id: The id of the element to click.
        exp_order: The expected order of events.
    """
    el = driver.find_element(By.ID, element_id)
    assert el

    prev_url = driver.current_url

    el.click()
    if "on_click:outer" not in exp_order:
        # really make sure the outer event is not fired
        await asyncio.sleep(0.5)
    await poll_for_order(exp_order)

    if element_id.startswith("link") and "prevent-default" not in element_id:
        assert driver.current_url != prev_url
    else:
        assert driver.current_url == prev_url


@pytest.mark.usefixtures("token")
@pytest.mark.asyncio
async def test_event_actions_throttle_debounce(
    driver: WebDriver,
    poll_for_order: Callable[[list[str]], Coroutine[None, None, None]],
):
    """Click buttons with debounce and throttle and assert on fired events.

    Args:
        driver: WebDriver instance.
        poll_for_order: function that polls for the order list to match the expected order.
    """
    btn_throttle = driver.find_element(By.ID, "btn-throttle")
    assert btn_throttle
    btn_debounce = driver.find_element(By.ID, "btn-debounce")
    assert btn_debounce

    exp_events = 10
    throttle_duration = exp_events * 0.2  # 200ms throttle
    throttle_start = time.time()
    while time.time() - throttle_start < throttle_duration:
        btn_throttle.click()
        btn_debounce.click()

    try:
        await poll_for_order(["on_click_throttle"] * exp_events + ["on_click_debounce"])
    except AssertionError:
        # Sometimes the last event gets throttled due to race, this is okay.
        await poll_for_order(
            ["on_click_throttle"] * (exp_events - 1) + ["on_click_debounce"]
        )


@pytest.mark.usefixtures("token")
@pytest.mark.asyncio
async def test_event_actions_dialog_form_in_form(
    driver: WebDriver,
    poll_for_order: Callable[[list[str]], Coroutine[None, None, None]],
):
    """Click links and buttons and assert on fired events.

    Args:
        driver: WebDriver instance.
        poll_for_order: function that polls for the order list to match the expected order.
    """
    open_dialog_id = "btn-dialog"
    submit_button_id = "btn-submit"
    wait = WebDriverWait(driver, 10)

    driver.find_element(By.ID, open_dialog_id).click()
    el = wait.until(EC.element_to_be_clickable((By.ID, submit_button_id)))
    el.click()  # pyright: ignore[reportAttributeAccessIssue]
    el.send_keys(Keys.ESCAPE)  # pyright: ignore[reportAttributeAccessIssue]

    btn_no_events = wait.until(EC.element_to_be_clickable((By.ID, "btn-no-events")))
    btn_no_events.click()
    await poll_for_order(["on_submit", "on_click:outer"])

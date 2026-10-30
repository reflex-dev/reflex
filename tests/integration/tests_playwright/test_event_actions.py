"""Ensure stopPropagation and preventDefault work as expected."""

from __future__ import annotations

import time
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness
from tests.integration.utils import poll_assert_event_order


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
                on_click=lambda: (
                    EventActionState.on_click_throttle.throttle(  # pyright: ignore [reportFunctionMemberAccess]
                        200
                    ).stop_propagation
                ),
            ),
            rx.button(
                "Debounce",
                id="btn-debounce",
                on_click=EventActionState.on_click_debounce.debounce(  # pyright: ignore [reportFunctionMemberAccess]
                    200
                ).stop_propagation,
            ),
            rx.vstack(
                rx.foreach(
                    EventActionState.order,
                    rx.text,
                ),
                id="event_order",
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
def event_page(event_action: AppHarness, page: Page) -> Page:
    """Open the app and wait for a connected browser session.

    Returns:
        The connected Playwright page.
    """
    assert event_action.frontend_url is not None
    page.goto(event_action.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    return page


@pytest.fixture
def token(event_page: Page) -> str:
    """Get the token associated with backend state.

    Args:
        event_page: Playwright page.

    Returns:
        The token visible in the driver browser.
    """
    return event_page.locator("#token").input_value()


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
def test_event_actions(
    event_page: Page,
    element_id: str,
    exp_order: list[str],
):
    """Click links and buttons and assert on fired events.

    Args:
        event_page: Playwright page.
        element_id: The id of the element to click.
        exp_order: The expected order of events.
    """
    el = event_page.locator(f"#{element_id}")
    prev_url = event_page.url

    el.click()
    if "on_click:outer" not in exp_order:
        # really make sure the outer event is not fired
        event_page.wait_for_timeout(500)
    poll_assert_event_order(event_page, exp_order)

    if element_id.startswith("link") and "prevent-default" not in element_id:
        expect(event_page).not_to_have_url(prev_url)
    else:
        expect(event_page).to_have_url(prev_url)


def test_event_actions_throttle_debounce(
    event_page: Page,
):
    """Click buttons with debounce and throttle and assert on fired events.

    Args:
        event_page: Playwright page.
    """
    btn_throttle = event_page.locator("#btn-throttle")
    btn_debounce = event_page.locator("#btn-debounce")

    exp_events = 10
    throttle_duration = exp_events * 0.2  # 200ms throttle
    throttle_start = time.time()
    while time.time() - throttle_start < throttle_duration:
        btn_throttle.click()
        btn_debounce.click()

    # Wait until the debounce event shows up
    expect(event_page.locator("#event_order p").last).to_have_text("on_click_debounce")

    # This test is inherently racy, so ensure the `on_click_throttle` event is fired approximately the expected number of times.
    final_event_order = event_page.locator("#event_order p").all_text_contents()
    n_on_click_throttle_received = final_event_order.count("on_click_throttle")
    print(
        f"Expected ~{exp_events} on_click_throttle events, received {n_on_click_throttle_received}"
    )
    assert exp_events - 2 <= n_on_click_throttle_received <= exp_events + 1
    assert final_event_order == ["on_click_throttle"] * n_on_click_throttle_received + [
        "on_click_debounce"
    ]


@pytest.mark.usefixtures("token")
def test_event_actions_dialog_form_in_form(
    event_page: Page,
):
    """Click links and buttons and assert on fired events.

    Args:
        event_page: Playwright page.
    """
    open_dialog_id = "btn-dialog"
    submit_button_id = "btn-submit"
    event_page.locator(f"#{open_dialog_id}").click()
    submit_button = event_page.locator(f"#{submit_button_id}")
    expect(submit_button).to_be_visible()
    submit_button.click()
    submit_button.press("Escape")
    event_page.locator("#btn-no-events").click()
    poll_assert_event_order(event_page, ["on_submit", "on_click:outer"])

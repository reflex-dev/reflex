"""Test that per-component state scaffold works and operates independently."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from . import utils


def ComponentStateApp():
    """App using per component state."""
    from typing import Generic, TypeVar

    import reflex as rx

    E = TypeVar("E")

    class MultiCounter(rx.ComponentState, Generic[E]):
        """ComponentState style."""

        count: int = 0
        _be: E
        _be_int: int
        _be_str: str = "42"

        @rx.event
        def increment(self):
            self.count += 1
            self._be = self.count  # pyright: ignore [reportAttributeAccessIssue]

        @rx.event
        def assert_be(self, value: E):
            assert self._backend_vars != self.backend_vars
            assert self._be == int(value)  # pyright: ignore [reportAttributeAccessIssue, reportArgumentType]

        @rx.event
        def assert_be_none(self):
            assert self._backend_vars == self.backend_vars
            assert self._be is None  # pyright: ignore [reportAttributeAccessIssue]

        @rx.event
        def assert_be_int(self, value: int):
            assert self._be_int == value  # pyright: ignore [reportAttributeAccessIssue]

        @rx.event
        def assert_be_str(self, value: str):
            assert self._be_str == value  # pyright: ignore [reportAttributeAccessIssue]

        @classmethod
        def get_component(cls, *children, **props):
            eid = props.get("id", "default")
            return rx.vstack(
                *children,
                rx.heading(cls.count, id=f"count-{eid}"),
                rx.button(
                    "Increment",
                    on_click=cls.increment,
                    id=f"button-{eid}",
                ),
                rx.form(
                    rx.input(id=f"{eid}-assert-be-value", name="be_value"),
                    rx.button(
                        "Assert _be",
                        id=f"{eid}-assert-be",
                    ),
                    on_submit=lambda fd: cls.assert_be(fd.to(dict)["be_value"]),  # pyright: ignore [reportAttributeAccessIssue]
                    reset_on_submit=True,
                ),
                rx.button(
                    "Assert _be_none",
                    id=f"{eid}-assert-be-none",
                    on_click=cls.assert_be_none,
                ),
                rx.button(
                    "Assert _be_int == 0",
                    id=f"{eid}-assert-be-int",
                    on_click=cls.assert_be_int(0),
                ),
                rx.button(
                    "Assert _be_str == '42'",
                    id=f"{eid}-assert-be-str",
                    on_click=cls.assert_be_str("42"),
                ),
                **props,
            )

    def multi_counter_func(id: str = "default") -> rx.Component:
        """Local-substate style.

        Args:
            id: identifier for this instance

        Returns:
            A new instance of the component with its own state.
        """

        class _Counter(rx.State):
            count: int = 0

            @rx.event
            def increment(self):
                self.count += 1

        return rx.vstack(
            rx.heading(_Counter.count, id=f"count-{id}"),
            rx.button(
                "Increment",
                on_click=_Counter.increment,
                id=f"button-{id}",
            ),
            State=_Counter,
        )

    app = rx.App()  # noqa: F841

    @rx.page()
    def index():
        mc_a = MultiCounter.create(id="a")
        mc_b = MultiCounter.create(id="b")
        mc_c = multi_counter_func(id="c")
        mc_d = multi_counter_func(id="d")
        assert mc_a.State != mc_b.State
        assert mc_c.State != mc_d.State
        return rx.vstack(
            mc_a,
            mc_b,
            mc_c,
            mc_d,
            rx.button(
                "Inc A",
                on_click=mc_a.State.increment,  # pyright: ignore [reportAttributeAccessIssue, reportOptionalMemberAccess]
                id="inc-a",
            ),
            rx.text(
                mc_a.State.get_name() if mc_a.State is not None else "",
                id="a_state_name",
            ),
            rx.text(
                mc_b.State.get_name() if mc_b.State is not None else "",
                id="b_state_name",
            ),
        )


@pytest.fixture(scope="module")
def component_state_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start ComponentStateApp app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("component_state_app"),
        app_source=ComponentStateApp,
    ) as harness:
        yield harness


def test_component_state_app(component_state_app: AppHarness, page: Page):
    """Increment counters independently.

    Args:
        component_state_app: harness for ComponentStateApp app
        page: Playwright page.
    """
    assert component_state_app.frontend_url is not None
    page.goto(component_state_app.frontend_url)

    ss = utils.SessionStorage(page)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"

    count_a = page.locator("#count-a")
    count_b = page.locator("#count-b")
    button_a = page.locator("#button-a")
    button_b = page.locator("#button-b")
    button_inc_a = page.locator("#inc-a")

    # Check that backend vars in mixins are okay
    page.locator("#a-assert-be-none").click()
    page.locator("#a-assert-be-int").click()
    page.locator("#a-assert-be-str").click()

    expect(count_a).to_have_text("0")

    button_a.click()
    expect(count_a).to_have_text("1")

    button_a.click()
    expect(count_a).to_have_text("2")

    button_inc_a.click()
    expect(count_a).to_have_text("3")

    page.locator("#a-assert-be-value").fill("3")
    page.locator("#a-assert-be").click()
    page.locator("#b-assert-be-none").click()

    expect(count_b).to_have_text("0")

    button_b.click()
    expect(count_b).to_have_text("1")

    button_b.click()
    expect(count_b).to_have_text("2")

    page.locator("#b-assert-be-value").fill("2")
    page.locator("#b-assert-be").click()

    # Check locally-defined substate style
    count_c = page.locator("#count-c")
    count_d = page.locator("#count-d")
    button_c = page.locator("#button-c")
    button_d = page.locator("#button-d")

    expect(count_c).to_have_text("0")
    expect(count_d).to_have_text("0")
    button_c.click()
    expect(count_c).to_have_text("1")
    expect(count_d).to_have_text("0")
    button_c.click()
    expect(count_c).to_have_text("2")
    expect(count_d).to_have_text("0")
    button_d.click()
    expect(count_c).to_have_text("2")
    expect(count_d).to_have_text("1")

"""Test that per-component state scaffold works and operates independently."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness, AppHarnessProd


def ComponentStateApp():
    """App using per-component state."""
    from typing import Generic, TypeVar

    import reflex as rx

    E = TypeVar("E")

    class MultiCounter(rx.ComponentState, Generic[E]):
        """ComponentState style."""

        count: int = 0
        label: rx.Field[str] = rx.field("")
        _be: E
        _be_int: int
        _be_str: str = "42"

        @rx.event
        def increment(self):
            """Increment this component's counter and update its label."""
            self.count += 1
            self.label = f"Count {self.count}"
            self._be = self.count  # pyright: ignore [reportAttributeAccessIssue]

        @rx.event
        def reset_counter(self):
            """Restore this component's configured defaults."""
            self.reset()

        @rx.event
        def assert_be(self, value: E):
            assert self._be == int(value)  # pyright: ignore [reportAttributeAccessIssue, reportArgumentType]

        @rx.event
        def assert_be_none(self):
            assert self._be is None  # pyright: ignore [reportAttributeAccessIssue]

        @rx.event
        def assert_be_int(self, value: int):
            assert self._be_int == value  # pyright: ignore [reportAttributeAccessIssue]

        @rx.event
        def assert_be_str(self, value: str):
            assert self._be_str == value  # pyright: ignore [reportAttributeAccessIssue]

        @classmethod
        def get_component(cls, *children, **props):
            """Configure defaults and return this component's controls.

            Args:
                children: Additional child components.
                props: Component props, including initial count and label.

            Returns:
                The counter and its controls.
            """
            eid = props.get("id", "default")
            cls.__fields__["count"].set_default(props.pop("initial_count", 0))
            cls.__fields__["label"].set_default(props.pop("initial_label", ""))
            return rx.vstack(
                *children,
                rx.heading(cls.count, id=f"count-{eid}"),
                rx.text(cls.label, id=f"label-{eid}"),
                rx.button("Increment", on_click=cls.increment, id=f"button-{eid}"),
                rx.button("Reset", on_click=cls.reset_counter, id=f"reset-{eid}"),
                rx.form(
                    rx.input(id=f"{eid}-assert-be-value", name="be_value"),
                    rx.button("Assert _be", id=f"{eid}-assert-be"),
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
        """Create a component with its own locally defined substate.

        Args:
            id: Identifier for this instance.

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
            rx.button("Increment", on_click=_Counter.increment, id=f"button-{id}"),
            State=_Counter,
        )

    app = rx.App()  # noqa: F841

    @rx.page()
    def index():
        """Render independent counters and a configured counter.

        Returns:
            The counter test page.
        """
        mc_a = MultiCounter.create(id="a")
        mc_b = MultiCounter.create(id="b")
        mc_c = multi_counter_func(id="c")
        mc_d = multi_counter_func(id="d")
        configured = MultiCounter.create(
            id="configured", initial_count=10, initial_label="Configured"
        )
        assert mc_a.State != mc_b.State
        assert mc_c.State != mc_d.State
        return rx.vstack(
            mc_a,
            mc_b,
            mc_c,
            mc_d,
            configured,
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


@pytest.fixture
def component_state_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start the ComponentState app.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=ComponentStateApp,
    ) as harness:
        yield harness


def test_component_state_app(component_state_app: AppHarness, page: Page) -> None:
    """Verify component and local substates update independently."""
    assert component_state_app.app_instance is not None, "app is not running"
    assert component_state_app.frontend_url is not None
    page.goto(component_state_app.frontend_url)
    page.wait_for_function("() => sessionStorage.getItem('token') !== null")

    count_a = page.locator("#count-a")
    count_b = page.locator("#count-b")
    button_a = page.locator("#button-a")
    button_b = page.locator("#button-b")

    page.locator("#a-assert-be-none").click()
    page.locator("#a-assert-be-int").click()
    page.locator("#a-assert-be-str").click()
    expect(count_a).to_have_text("0")

    button_a.click()
    expect(count_a).to_have_text("1")
    button_a.click()
    expect(count_a).to_have_text("2")
    page.locator("#inc-a").click()
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


@pytest.fixture(scope="module", params=[AppHarness, AppHarnessProd])
def configured_component_state_app(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Generator[AppHarness, None, None]:
    """Run the component-state app in development and production.

    Args:
        request: The app harness class selected for this case.
        tmp_path_factory: Factory for isolated app directories.

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
) -> None:
    """Configured defaults render, update, reset, and remain per-component."""
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

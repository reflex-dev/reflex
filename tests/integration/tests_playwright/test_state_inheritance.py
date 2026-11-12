"""Test state inheritance."""

from __future__ import annotations

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def StateInheritance():
    """Test that state inheritance works as expected."""
    import reflex as rx

    class ChildMixin(rx.State, mixin=True):
        child_mixin: str = "child_mixin"

        @rx.var
        def computed_child_mixin(self) -> str:
            return "computed_child_mixin"

    class Mixin(ChildMixin, mixin=True):
        mixin: str = "mixin"

        @rx.var
        def computed_mixin(self) -> str:
            return "computed_mixin"

        @rx.event
        def on_click_mixin(self):
            return rx.call_script("alert('clicked')")

    class OtherMixin(rx.State, mixin=True):
        other_mixin: str = "other_mixin"
        other_mixin_clicks: int = 0

        @rx.var
        def computed_other_mixin(self) -> str:
            return self.other_mixin

        @rx.event
        def on_click_other_mixin(self):
            self.other_mixin_clicks += 1
            self.other_mixin = (
                f"{type(self).__name__}.clicked.{self.other_mixin_clicks}"
            )

    class Base1(Mixin, rx.State):
        _base1: str = "_base1"
        base1: str = "base1"

        @rx.var
        def computed_basevar(self) -> str:
            return "computed_basevar1"

        @rx.var
        def computed_backend_vars_base1(self) -> str:
            return self._base1

    class Base2(rx.State):
        _base2: str = "_base2"
        base2: str = "base2"

        @rx.var
        def computed_basevar(self) -> str:
            return "computed_basevar2"

        @rx.var
        def computed_backend_vars_base2(self) -> str:
            return self._base2

    class Child1(Base1, OtherMixin):
        pass

    class Child2(Base2, Mixin, OtherMixin):
        pass

    class Child3(Child2):
        _child3: str = "_child3"
        child3: str = "child3"

        @rx.var
        def computed_childvar(self) -> str:
            return "computed_childvar"

        @rx.var
        def computed_backend_vars_child3(self) -> str:
            return f"{self._base2}.{self._child3}"

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(
                id="token", value=Base1.router.session.client_token, is_read_only=True
            ),
            # Base 1 (Mixin, ChildMixin)
            rx.heading(Base1.computed_mixin, id="base1-computed_mixin"),
            rx.heading(Base1.computed_basevar, id="base1-computed_basevar"),
            rx.heading(Base1.computed_child_mixin, id="base1-computed-child-mixin"),
            rx.heading(Base1.base1, id="base1-base1"),
            rx.heading(Base1.child_mixin, id="base1-child-mixin"),
            rx.button(
                "Base1.on_click_mixin",
                on_click=Base1.on_click_mixin,
                id="base1-mixin-btn",
            ),
            rx.heading(
                Base1.computed_backend_vars_base1, id="base1-computed_backend_vars"
            ),
            # Base 2 (no mixins)
            rx.heading(Base2.computed_basevar, id="base2-computed_basevar"),
            rx.heading(Base2.base2, id="base2-base2"),
            rx.heading(
                Base2.computed_backend_vars_base2, id="base2-computed_backend_vars"
            ),
            # Child 1 (Mixin, ChildMixin, OtherMixin)
            rx.heading(Child1.computed_basevar, id="child1-computed_basevar"),
            rx.heading(Child1.computed_mixin, id="child1-computed_mixin"),
            rx.heading(Child1.computed_other_mixin, id="child1-other-mixin"),
            rx.heading(Child1.computed_child_mixin, id="child1-computed-child-mixin"),
            rx.heading(Child1.base1, id="child1-base1"),
            rx.heading(Child1.other_mixin, id="child1-other-mixin-value"),
            rx.heading(Child1.child_mixin, id="child1-child-mixin"),
            rx.button(
                "Child1.on_click_other_mixin",
                on_click=Child1.on_click_other_mixin,
                id="child1-other-mixin-btn",
            ),
            # Child 2 (Mixin, ChildMixin, OtherMixin)
            rx.heading(Child2.computed_basevar, id="child2-computed_basevar"),
            rx.heading(Child2.computed_mixin, id="child2-computed_mixin"),
            rx.heading(Child2.computed_other_mixin, id="child2-other-mixin"),
            rx.heading(Child2.computed_child_mixin, id="child2-computed-child-mixin"),
            rx.heading(Child2.base2, id="child2-base2"),
            rx.heading(Child2.other_mixin, id="child2-other-mixin-value"),
            rx.heading(Child2.child_mixin, id="child2-child-mixin"),
            rx.button(
                "Child2.on_click_mixin",
                on_click=Child2.on_click_mixin,
                id="child2-mixin-btn",
            ),
            rx.button(
                "Child2.on_click_other_mixin",
                on_click=Child2.on_click_other_mixin,
                id="child2-other-mixin-btn",
            ),
            # Child 3 (Mixin, ChildMixin, OtherMixin)
            rx.heading(Child3.computed_basevar, id="child3-computed_basevar"),
            rx.heading(Child3.computed_mixin, id="child3-computed_mixin"),
            rx.heading(Child3.computed_other_mixin, id="child3-other-mixin"),
            rx.heading(Child3.computed_childvar, id="child3-computed_childvar"),
            rx.heading(Child3.computed_child_mixin, id="child3-computed-child-mixin"),
            rx.heading(Child3.child3, id="child3-child3"),
            rx.heading(Child3.base2, id="child3-base2"),
            rx.heading(Child3.other_mixin, id="child3-other-mixin-value"),
            rx.heading(Child3.child_mixin, id="child3-child-mixin"),
            rx.button(
                "Child3.on_click_mixin",
                on_click=Child3.on_click_mixin,
                id="child3-mixin-btn",
            ),
            rx.button(
                "Child3.on_click_other_mixin",
                on_click=Child3.on_click_other_mixin,
                id="child3-other-mixin-btn",
            ),
            rx.heading(
                Child3.computed_backend_vars_child3, id="child3-computed_backend_vars"
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def state_inheritance(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start StateInheritance app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("state_inheritance"),
        app_source=StateInheritance,
    ) as harness:
        yield harness


@pytest.fixture
def opened_page(state_inheritance: AppHarness, page: Page) -> Page:
    """Open the state inheritance app in the Playwright page.

    Args:
        state_inheritance: harness for StateInheritance app.
        page: Playwright page.

    Returns:
        The page after the app is loaded.
    """
    assert state_inheritance.app_instance is not None, "app is not running"
    assert state_inheritance.frontend_url is not None
    page.goto(state_inheritance.frontend_url)
    return page


@pytest.fixture
def token(opened_page: Page) -> str:
    """Get a function that returns the active token.

    Args:
        opened_page: Playwright page.

    Returns:
        The token for the connected client
    """
    token_input = opened_page.locator("#token")
    expect(token_input).to_have_value(re.compile(r".+"), timeout=30_000)
    return token_input.input_value()


def test_state_inheritance(
    state_inheritance: AppHarness,
    opened_page: Page,
    token: str,
):
    """Test that background tasks work as expected.

    Args:
        state_inheritance: harness for StateInheritance app.
        opened_page: Playwright page.
        token: The token for the connected client.
    """
    assert state_inheritance.app_instance is not None

    # Initial State values Test
    # Base 1
    initial_values = {
        "base1-computed_mixin": "computed_mixin",
        "base1-computed_basevar": "computed_basevar1",
        "base1-computed-child-mixin": "computed_child_mixin",
        "base1-base1": "base1",
        "base1-computed_backend_vars": "_base1",
        "base1-child-mixin": "child_mixin",
        "base2-computed_basevar": "computed_basevar2",
        "base2-base2": "base2",
        "base2-computed_backend_vars": "_base2",
        "child1-computed_basevar": "computed_basevar1",
        "child1-computed_mixin": "computed_mixin",
        "child1-other-mixin": "other_mixin",
        "child1-computed-child-mixin": "computed_child_mixin",
        "child1-base1": "base1",
        "child1-other-mixin-value": "other_mixin",
        "child1-child-mixin": "child_mixin",
        "child2-computed_basevar": "computed_basevar2",
        "child2-computed_mixin": "computed_mixin",
        "child2-other-mixin": "other_mixin",
        "child2-computed-child-mixin": "computed_child_mixin",
        "child2-base2": "base2",
        "child2-other-mixin-value": "other_mixin",
        "child2-child-mixin": "child_mixin",
        "child3-computed_basevar": "computed_basevar2",
        "child3-computed_mixin": "computed_mixin",
        "child3-other-mixin": "other_mixin",
        "child3-computed_childvar": "computed_childvar",
        "child3-computed-child-mixin": "computed_child_mixin",
        "child3-child3": "child3",
        "child3-base2": "base2",
        "child3-other-mixin-value": "other_mixin",
        "child3-child-mixin": "child_mixin",
        "child3-computed_backend_vars": "_base2._child3",
    }
    for element_id, expected in initial_values.items():
        expect(opened_page.locator(f"#{element_id}")).to_have_text(expected)

    # Mixins may return browser dialogs; dismiss each and verify its message.
    for element_id in ("base1-mixin-btn", "child2-mixin-btn", "child3-mixin-btn"):
        with opened_page.expect_event("dialog") as dialog_info:
            opened_page.locator(f"#{element_id}").click()
        dialog = dialog_info.value
        assert dialog.message == "clicked"
        dialog.accept()

    opened_page.locator("#child1-other-mixin-btn").click()
    expect(opened_page.locator("#child1-other-mixin")).to_have_text("Child1.clicked.1")
    expect(opened_page.locator("#child1-other-mixin-value")).to_have_text(
        "Child1.clicked.1"
    )

    opened_page.locator("#child2-other-mixin-btn").click()
    for element_id in (
        "child2-other-mixin-value",
        "child2-other-mixin",
        "child3-other-mixin-value",
        "child3-other-mixin",
    ):
        expect(opened_page.locator(f"#{element_id}")).to_have_text("Child2.clicked.1")

    opened_page.locator("#child3-other-mixin-btn").click()
    for element_id in (
        "child2-other-mixin-value",
        "child2-other-mixin",
        "child3-other-mixin-value",
        "child3-other-mixin",
    ):
        expect(opened_page.locator(f"#{element_id}")).to_have_text("Child2.clicked.2")

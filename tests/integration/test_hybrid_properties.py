"""Test hybrid properties."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from .utils import poll_for_token


def HybridProperties():
    """Test app for hybrid properties."""
    from dataclasses import dataclass

    import reflex as rx
    from reflex.experimental import hybrid_property
    from reflex.vars import Var

    @dataclass
    class Info:
        """A nested dataclass exposing a hybrid property."""

        a: str
        b: str

        @hybrid_property
        def a_b(self) -> str:
            """Combine the two fields, usable on both frontend and backend.

            Returns:
                str: The two fields joined with a dash.
            """
            return f"{self.a} - {self.b}"

    class State(rx.State):
        first_name: str = "John"
        last_name: str = "Doe"
        info: Info = Info(a="a", b="b")

        @property
        def python_full_name(self) -> str:
            """A normal python property to showcase the current behavior. This renders to smth like `<property object at 0x723b334e5940>`.

            Returns:
                str: The full name of the person.
            """
            return f"{self.first_name} {self.last_name}"

        @hybrid_property
        def full_name(self) -> str:
            """A simple hybrid property which uses the same code for both frontend and backend.

            Returns:
                str: The full name of the person.
            """
            return f"{self.first_name} {self.last_name}"

        @hybrid_property
        def has_last_name(self) -> str:
            """A more complex hybrid property which uses different code for frontend and backend.

            Returns:
                str: "yes" if the person has a last name, "no" otherwise.
            """
            return "yes" if self.last_name else "no"

        @has_last_name.var
        def _has_last_name_var(cls) -> Var[str]:
            """The frontend code for the `has_last_name` hybrid property.

            Returns:
                Var[str]: The value of the hybrid property.
            """
            return rx.cond(cls.last_name, "yes", "no")

        @rx.var
        def full_name_backend(self) -> str:
            """Expose the backend value of the `full_name` hybrid property.

            Returns:
                str: The full name as evaluated by the backend property getter.
            """
            return self.full_name

        @rx.var
        def has_last_name_backend(self) -> str:
            """Expose the backend value of the `has_last_name` hybrid property.

            Returns:
                str: The has_last_name value as evaluated by the backend property getter.
            """
            return self.has_last_name

        @rx.event
        def update_last_name(self, value: str):
            """Update the last_name field.

            Args:
                value: The new last name value.
            """
            self.last_name = value

        @rx.event
        def update_info_a(self, value: str):
            """Update the `a` field of the nested info dataclass.

            Args:
                value: The new value for `info.a`.
            """
            self.info = Info(a=value, b=self.info.b)

    def index() -> rx.Component:
        return rx.center(
            rx.vstack(
                rx.el.input(
                    id="token",
                    value=State.router.session.client_token,
                    is_read_only=True,
                ),
                rx.text(
                    f"python_full_name: {State.python_full_name}", id="python_full_name"
                ),
                rx.text(f"full_name: {State.full_name}", id="full_name"),
                rx.text(
                    f"full_name_backend: {State.full_name_backend}",
                    id="full_name_backend",
                ),
                rx.text(f"has_last_name: {State.has_last_name}", id="has_last_name"),
                rx.text(
                    f"has_last_name_backend: {State.has_last_name_backend}",
                    id="has_last_name_backend",
                ),
                rx.el.input(
                    value=State.last_name,
                    on_change=State.update_last_name,
                    id="set_last_name",
                ),
                rx.text(f"info_a_b: {State.info.a_b}", id="info_a_b"),
                rx.el.input(
                    value=State.info.a,
                    on_change=State.update_info_a,
                    id="set_info_a",
                ),
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def hybrid_properties(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start HybridProperties app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("hybrid_properties"),
        app_source=HybridProperties,
    ) as harness:
        yield harness


def test_hybrid_properties(hybrid_properties: AppHarness, page: Page):
    """Check hybrid property values on the frontend and backend after changes.

    Args:
        hybrid_properties: The running app.
        page: Playwright page.
    """
    assert hybrid_properties.frontend_url is not None
    page.goto(hybrid_properties.frontend_url)
    poll_for_token(page)
    info = page.locator("#info_a_b")
    expect(info).to_have_text("info_a_b: a - b")
    page.locator("#set_info_a").fill("")
    expect(info).to_have_text("info_a_b: - b")
    page.locator("#set_info_a").fill("z")
    expect(info).to_have_text("info_a_b: z - b")
    expect(page.locator("#full_name")).to_have_text("full_name: John Doe")
    expect(page.locator("#full_name_backend")).to_have_text(
        "full_name_backend: John Doe"
    )
    expect(page.locator("#python_full_name")).to_contain_text("<property object at 0x")
    expect(page.locator("#has_last_name")).to_have_text("has_last_name: yes")
    expect(page.locator("#has_last_name_backend")).to_have_text(
        "has_last_name_backend: yes"
    )
    page.locator("#set_last_name").fill("")
    expect(page.locator("#has_last_name")).to_have_text("has_last_name: no")
    expect(page.locator("#has_last_name_backend")).to_have_text(
        "has_last_name_backend: no"
    )
    expect(page.locator("#full_name")).to_have_text("full_name: John")
    expect(page.locator("#full_name_backend")).to_have_js_property(
        "textContent", "full_name_backend: John "
    )

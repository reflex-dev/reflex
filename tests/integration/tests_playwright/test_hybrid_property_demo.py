"""Integration demo exercising the hybrid property improvements end to end.

Covers, in one app: a setter driven from an event handler, a var function bound
under a name of its own, a var function declared a ``classmethod``, a var
function returning ``None``, a hybrid property inherited from a mixin under a
name the state annotates, and a hybrid property reached through an object var.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def HybridPropertyDemo():
    """App exercising the hybrid property improvements."""
    from dataclasses import dataclass

    import reflex as rx
    from reflex.experimental import hybrid_property
    from reflex.vars import Var

    @dataclass
    class Info:
        """A nested dataclass reached through an object var."""

        a: str
        b: str

        @hybrid_property
        def a_b(self) -> str:
            """Join the two fields on both sides.

            Returns:
                The two fields joined with a dash.
            """
            return f"{self.a} - {self.b}"

    class LabelMixin:
        """A plain mixin contributing a hybrid property."""

        @hybrid_property
        def label(self) -> str:
            """A label defined away from the state.

            Returns:
                The mixin's label.
            """
            return "from-mixin"

    class DemoState(LabelMixin, rx.State):
        # annotating the inherited property's name must not shadow the descriptor
        label: str  # pyright: ignore[reportIncompatibleVariableOverride]

        first: str = "Ada"
        last: str = "Lovelace"
        info: Info = Info(a="a", b="b")
        _audit: list[str] = []

        @hybrid_property
        def full_name(self) -> str:
            """Same code on both sides.

            Returns:
                The full name.
            """
            return f"{self.first} {self.last}"

        @full_name.setter
        def _set_full_name(self, value: str) -> None:
            """Split an assigned full name back into its parts.

            Args:
                value: The full name to assign.
            """
            self.first, self.last = value.split(" ", 1)
            self._audit.append(value)

        @full_name.deleter
        def _del_full_name(self) -> None:
            """Clear both name parts."""
            self.first = self.last = ""

        @hybrid_property
        def has_last(self) -> str:
            """Backend answer for whether a last name is set.

            Returns:
                "yes" or "no".
            """
            return "yes" if self.last else "no"

        @has_last.var
        @classmethod
        def _has_last_var(cls) -> Var[str]:
            """Frontend answer, bound back onto ``has_last``.

            Returns:
                A var resolving to "yes" or "no".
            """
            return rx.cond(cls.last, "yes", "no")

        @hybrid_property
        def initials(self) -> str:  # pyright: ignore[reportRedeclaration]
            """Backend initials.

            Returns:
                The two initials.
            """
            return f"{self.first[:1]}{self.last[:1]}"

        @initials.var
        @classmethod
        def initials(cls) -> Var[str]:
            """Frontend initials, under the property's own name.

            Returns:
                A var resolving to the initials.
            """
            return cls.first[0:1] + cls.last[0:1]  # pyright: ignore[reportReturnType]

        @hybrid_property
        def unavailable(self) -> str:
            """Has a backend value but declares no frontend one.

            Returns:
                A server-only string.
            """
            return "server-only"

        @unavailable.var
        @classmethod
        def _unavailable_var(cls) -> Var[str] | None:
            """Declare that there is no frontend value.

            Returns:
                None, always.
            """
            return None

        @rx.var
        def full_name_backend(self) -> str:
            """Expose the backend getter to the page.

            Returns:
                The backend-evaluated full name.
            """
            return self.full_name

        @rx.var
        def has_last_backend(self) -> str:
            """Expose the backend getter to the page.

            Returns:
                The backend-evaluated has_last.
            """
            return self.has_last

        @rx.var
        def unavailable_backend(self) -> str:
            """Expose the backend-only property to the page.

            Returns:
                The server-only value.
            """
            return self.unavailable

        @rx.var
        def audit_log(self) -> str:
            """Expose the backend var the setter appends to.

            Returns:
                The comma-joined audit entries.
            """
            return ",".join(self._audit)

        @rx.event
        def rename(self):
            """Assign through the hybrid property's setter."""
            self.full_name = "Grace Hopper"

        @rx.event
        def clear_name(self):
            """Delete through the hybrid property's deleter."""
            del self.full_name

        @rx.event
        def bump_info(self):
            """Replace the nested dataclass."""
            self.info = Info(a="z", b=self.info.b)

    def index() -> rx.Component:
        # `unavailable` has no frontend value, so class access is None
        assert DemoState.unavailable is None

        return rx.vstack(
            rx.el.input(
                id="token",
                value=DemoState.router.session.client_token,
                is_read_only=True,
            ),
            rx.text(DemoState.label, id="label"),
            rx.text(f"{DemoState.full_name}", id="full_name"),
            rx.text(DemoState.full_name_backend, id="full_name_backend"),
            rx.text(DemoState.has_last, id="has_last"),
            rx.text(DemoState.has_last_backend, id="has_last_backend"),
            rx.text(DemoState.initials, id="initials"),
            rx.text(DemoState.unavailable_backend, id="unavailable_backend"),
            rx.text(DemoState.info.a_b, id="info_a_b"),
            rx.text(DemoState.audit_log, id="audit_log"),
            rx.button("rename", on_click=DemoState.rename, id="rename"),
            rx.button("clear", on_click=DemoState.clear_name, id="clear"),
            rx.button("bump", on_click=DemoState.bump_info, id="bump"),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def hybrid_property_demo(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the demo app via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture.

    Yields:
        The running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("hybrid_property_demo"),
        app_source=HybridPropertyDemo,
    ) as harness:
        yield harness


def test_hybrid_property_demo(hybrid_property_demo: AppHarness, page: Page):
    """Drive the demo app and assert every hybrid property behaves as declared.

    Args:
        hybrid_property_demo: harness for the demo app.
        page: Playwright page.
    """
    assert hybrid_property_demo.frontend_url is not None
    page.goto(hybrid_property_demo.frontend_url)
    # wait for the backend connection before asserting on state-derived text
    expect(page.locator("#token")).not_to_have_value("")

    # a hybrid property inherited from a mixin under an annotated name
    expect(page.locator("#label")).to_have_text("from-mixin")

    # same code on both sides
    expect(page.locator("#full_name")).to_have_text("Ada Lovelace")
    expect(page.locator("#full_name_backend")).to_have_text("Ada Lovelace")

    # var function bound back from a name of its own
    expect(page.locator("#has_last")).to_have_text("yes")
    expect(page.locator("#has_last_backend")).to_have_text("yes")

    # var function redeclaring the property's name
    expect(page.locator("#initials")).to_have_text("AL")

    # a property with no frontend value still serves the backend
    expect(page.locator("#unavailable_backend")).to_have_text("server-only")

    # hybrid property through an object var
    expect(page.locator("#info_a_b")).to_have_text("a - b")

    # the setter runs on assignment inside an event handler
    page.locator("#rename").click()
    expect(page.locator("#full_name")).to_have_text("Grace Hopper")
    expect(page.locator("#full_name_backend")).to_have_text("Grace Hopper")
    expect(page.locator("#initials")).to_have_text("GH")
    # ... and its writes to a backend var landed
    expect(page.locator("#audit_log")).to_have_text("Grace Hopper")

    # the object var re-renders when the nested dataclass changes
    page.locator("#bump").click()
    expect(page.locator("#info_a_b")).to_have_text("z - b")

    # the deleter runs on `del`
    page.locator("#clear").click()
    expect(page.locator("#has_last")).to_have_text("no")
    expect(page.locator("#has_last_backend")).to_have_text("no")

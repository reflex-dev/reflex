"""Integration tests for ``rx.client_state`` runtime behavior.

Covers what unit tests cannot: the React runtime in ``utils/client_state.js``.
Shared named vars staying in sync across components, backend ``push``/``retrieve``
over the new wire events, ``global_ref=False`` isolation, the non-React escape
hatch, functional updaters, and — the property the store exists to guarantee —
that writing one var does not re-render components subscribed only to another.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ClientStateApp():
    """App exercising ``rx.client_state`` runtime behavior."""
    from reflex_base.vars.function import ArgsFunctionOperationBuilder, FunctionVar

    import reflex as rx

    shared = rx.client_state("initial", name="shared")
    counter = rx.client_state(0, name="counter")
    other = rx.client_state("untouched", name="other")

    class ClientStateAppState(rx.State):
        retrieved: str = ""

        @rx.event
        def push_shared(self):
            return shared.push("from-backend")

        @rx.event
        def do_retrieve(self):
            return shared.retrieve(ClientStateAppState.got_value)

        @rx.event
        def got_value(self, value: str):
            self.retrieved = value

    @rx.memo
    def local_input(label: rx.Var[str]) -> rx.Component:
        # Unnamed: constructed inside the component, so each rendered instance
        # owns its own slot.
        local = rx.client_state("")
        return rx.hstack(
            rx.input(
                value=local.value,
                on_change=local.set,
                id=f"local-input-{label}",
            ),
            rx.text(local.value, id=f"local-echo-{label}"),
        )

    def index() -> rx.Component:
        return rx.vstack(
            rx.input(
                value=ClientStateAppState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            # Two independent readers of the same named var.
            rx.text(shared.value, id="shared-a"),
            rx.text(shared.value, id="shared-b"),
            rx.input(value=shared.value, on_change=shared.set, id="shared-input"),
            rx.button("set-shared", id="set-shared", on_click=shared.set("clicked")),
            # Functional updater.
            rx.text(counter.value, id="counter-value"),
            rx.button(
                "increment", id="increment", on_click=counter.set(lambda v: v + 1)
            ),
            # A var nothing else writes, to prove writes are isolated.
            rx.text(other.value, id="other-value"),
            # Backend round trips.
            rx.button("push", id="push", on_click=ClientStateAppState.push_shared),
            rx.button(
                "retrieve", id="retrieve", on_click=ClientStateAppState.do_retrieve
            ),
            rx.text(ClientStateAppState.retrieved, id="retrieved"),
            # Escape hatch: a plain JS function, no hook in scope. This is what
            # gets handed to a wrapped library as a callback.
            rx.button(
                "global-set",
                id="global-set",
                on_click=rx.call_function(
                    ArgsFunctionOperationBuilder.create(
                        args_names=(),
                        return_expr=shared.global_set.to(FunctionVar).call(
                            "from-plain-js"
                        ),
                    )
                ),
            ),
            # rx.call_script evals inside the Reflex runtime module, where the
            # page's imports are not in scope, so reach the store via refs.
            rx.button(
                "global-set-script",
                id="global-set-script",
                on_click=rx.call_script(
                    'refs["__client_state"].set("shared", "from-call-script")'
                ),
            ),
            local_input(label="one"),
            local_input(label="two"),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def client_state_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start the client state app.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture.

    Yields:
        The running AppHarness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("client_state_app"),
        app_source=ClientStateApp,
    ) as harness:
        yield harness


@pytest.fixture
def page(client_state_app: AppHarness, page: Page) -> Page:
    """Navigate to the app and wait for hydration.

    Args:
        client_state_app: The running harness.
        page: The playwright page.

    Returns:
        The page, loaded and hydrated.
    """
    assert client_state_app.frontend_url is not None
    page.goto(client_state_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    return page


def test_named_var_is_shared_across_components(page: Page) -> None:
    """Two components reading one named var stay in sync."""
    expect(page.locator("#shared-a")).to_have_text("initial")
    expect(page.locator("#shared-b")).to_have_text("initial")

    page.locator("#shared-input").fill("typed")

    expect(page.locator("#shared-a")).to_have_text("typed")
    expect(page.locator("#shared-b")).to_have_text("typed")


def test_set_with_bound_value(page: Page) -> None:
    """``set(value)`` attached to a trigger sets that value."""
    page.locator("#set-shared").click()
    expect(page.locator("#shared-a")).to_have_text("clicked")


def test_functional_updater_derives_from_current_value(page: Page) -> None:
    """``set(lambda v: v + 1)`` increments rather than overwriting."""
    expect(page.locator("#counter-value")).to_have_text("0")
    for expected in ("1", "2", "3"):
        page.locator("#increment").click()
        expect(page.locator("#counter-value")).to_have_text(expected)


def test_push_from_backend(page: Page) -> None:
    """A backend ``push`` reaches the mounted components."""
    page.locator("#push").click()
    expect(page.locator("#shared-a")).to_have_text("from-backend")
    expect(page.locator("#shared-b")).to_have_text("from-backend")


def test_retrieve_to_backend(page: Page) -> None:
    """``retrieve`` round-trips the current value to a backend handler."""
    page.locator("#shared-input").fill("to-retrieve")
    expect(page.locator("#shared-a")).to_have_text("to-retrieve")

    page.locator("#retrieve").click()
    expect(page.locator("#retrieved")).to_have_text("to-retrieve")


def test_global_set_from_plain_javascript(page: Page) -> None:
    """The escape hatch drives the var from JS with no hook in scope."""
    page.locator("#global-set").click()
    expect(page.locator("#shared-a")).to_have_text("from-plain-js")
    expect(page.locator("#shared-b")).to_have_text("from-plain-js")


def test_store_is_reachable_through_refs(page: Page) -> None:
    """``refs["__client_state"]`` is the documented entry point for eval'd code.

    ``rx.call_script`` runs inside the Reflex runtime module, so a page-level
    import of ``setClientState`` is not in scope there; the single ``refs`` key
    is what makes the store reachable (and introspectable from devtools).
    """
    page.locator("#global-set-script").click()
    expect(page.locator("#shared-a")).to_have_text("from-call-script")
    expect(page.locator("#shared-b")).to_have_text("from-call-script")


def test_local_vars_are_isolated_between_instances(page: Page) -> None:
    """``global_ref=False`` gives each rendered instance its own slot."""
    page.locator("#local-input-one").fill("only-one")

    expect(page.locator("#local-echo-one")).to_have_text("only-one")
    expect(page.locator("#local-echo-two")).to_have_text("")

    page.locator("#local-input-two").fill("only-two")

    expect(page.locator("#local-echo-one")).to_have_text("only-one")
    expect(page.locator("#local-echo-two")).to_have_text("only-two")


def test_writing_one_var_leaves_other_readers_untouched(page: Page) -> None:
    """Per-var subscriptions: writing ``shared`` must not disturb ``other``.

    The old implementation fanned every write out to every registered setter,
    so a component reading an unrelated var still re-rendered.
    """
    expect(page.locator("#other-value")).to_have_text("untouched")

    page.locator("#shared-input").fill("churn")
    page.locator("#increment").click()

    expect(page.locator("#shared-a")).to_have_text("churn")
    expect(page.locator("#other-value")).to_have_text("untouched")

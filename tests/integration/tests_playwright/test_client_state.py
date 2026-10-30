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
    suffixed = rx.client_state("", name="suffixed")
    # Never rendered: only backend handlers touch it.
    hidden = rx.client_state("", name="hidden")
    # Unnamed, used by a memo and by the page after it: the page owns it.
    lifted = rx.client_state(0)
    # Unnamed, used at page level on two pages.
    page_local = rx.client_state(0)

    class ClientStateAppState(rx.State):
        retrieved: str = ""
        retrieved_hidden: str = ""

        @rx.event
        def push_hidden(self):
            return hidden.push("secret")

        @rx.event
        def retrieve_hidden(self):
            return hidden.retrieve(ClientStateAppState.got_hidden)

        @rx.event
        def got_hidden(self, value: str):
            self.retrieved_hidden = value

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

    @rx.memo
    def lifted_card() -> rx.Component:
        return rx.text(lifted.value, class_name="lifted-card")

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
            # A trigger argument used inside a compound value.
            rx.input(
                on_change=lambda value: suffixed.set(value.to(str) + "!"),
                id="suffix-input",
            ),
            rx.text(suffixed.value, id="suffix-value"),
            # Backend round trips.
            rx.button("push", id="push", on_click=ClientStateAppState.push_shared),
            rx.button(
                "retrieve", id="retrieve", on_click=ClientStateAppState.do_retrieve
            ),
            rx.text(ClientStateAppState.retrieved, id="retrieved"),
            rx.button(
                "push-hidden",
                id="push-hidden",
                on_click=ClientStateAppState.push_hidden,
            ),
            rx.button(
                "retrieve-hidden",
                id="retrieve-hidden",
                on_click=ClientStateAppState.retrieve_hidden,
            ),
            rx.text(ClientStateAppState.retrieved_hidden, id="retrieved-hidden"),
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
            # The cards render before the page-level reader of the same var.
            lifted_card(),
            lifted_card(),
            rx.text(lifted.value, id="lifted-page"),
            rx.button("lift", id="lift", on_click=lifted.set(100)),
            rx.text(page_local.value, id="page-local"),
            rx.button(
                "page-local-inc",
                id="page-local-inc",
                on_click=page_local.set(lambda v: v + 1),
            ),
            rx.link("other", href="/other", id="to-other"),
        )

    def other_page() -> rx.Component:
        return rx.vstack(
            rx.text(page_local.value, id="other-page-local"),
            rx.link("home", href="/", id="to-home"),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(other_page, route="/other")


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


def test_set_with_a_value_computed_from_the_trigger_arg(page: Page) -> None:
    """``set(value + "!")`` reads the trigger's argument, not a closed-over one."""
    page.locator("#suffix-input").fill("typed")
    expect(page.locator("#suffix-value")).to_have_text("typed!")


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


def test_backend_only_var_round_trips(page: Page) -> None:
    """A var no component renders still holds what the backend pushes."""
    page.locator("#push-hidden").click()
    page.locator("#retrieve-hidden").click()
    expect(page.locator("#retrieved-hidden")).to_have_text("secret")


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


def test_page_owns_a_var_its_memos_also_use(page: Page) -> None:
    """The page body uses ``lifted``, so the memo instances below it share its slot.

    The cards render before the page-level reader, so the owner must not depend
    on render order.
    """
    page.locator("#lift").click()

    expect(page.locator("#lifted-page")).to_have_text("100")
    expect(page.locator(".lifted-card")).to_have_text(["100", "100"])


def test_local_page_var_does_not_cross_pages(page: Page) -> None:
    """An unnamed var used at page level belongs to that page, like ``useState``."""
    page.locator("#page-local-inc").click()
    page.locator("#page-local-inc").click()
    expect(page.locator("#page-local")).to_have_text("2")

    page.locator("#to-other").click()
    expect(page.locator("#other-page-local")).to_have_text("0")

    page.locator("#to-home").click()
    expect(page.locator("#page-local")).to_have_text("0")


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


def ClientStateLateMountApp():
    """App exercising a consumer that mounts after the value has moved."""
    import asyncio

    import reflex as rx

    flag = rx.client_state("", name="flag")
    # Only ever written from the frontend; the reader mounts afterwards.
    shared = rx.client_state("initial", name="shared")
    # Only ever written by backend pushes, before any component reads it.
    pushed = rx.client_state("initial", name="pushed")

    class LateMountState(rx.State):
        mounted: bool = False
        show: bool = False
        default_text: str = "from backend"

        @rx.event
        def reveal(self):
            self.show = True

        @rx.event
        def push_value(self):
            return pushed.push("pushed")

        @rx.event
        def push_none(self):
            return pushed.push(None)

        @rx.event(background=True)
        async def go(self):
            async with self:
                self.mounted = False
            yield flag.push("busy")
            await asyncio.sleep(0.2)
            async with self:
                self.mounted = True
            await asyncio.sleep(0.2)
            yield flag.push("")

    def index() -> rx.Component:
        return rx.el.div(
            rx.input(
                value=LateMountState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.el.button("go", on_click=LateMountState.go, id="go"),
            rx.el.div(flag.value, id="always"),
            rx.cond(LateMountState.mounted, rx.el.div(flag.value, id="late")),
        )

    # Seeded from backend state, with a sibling that only ever sets it.
    backend_default = rx.client_state(LateMountState.default_text, name="seeded")

    def setter_first() -> rx.Component:
        return rx.el.div(
            rx.input(
                value=LateMountState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.el.button("set", on_click=shared.set("clicked"), id="setter"),
            rx.el.button("reset", on_click=shared.set("initial"), id="resetter"),
            rx.el.button("reveal", on_click=LateMountState.reveal, id="reveal"),
            rx.cond(LateMountState.show, rx.el.div(shared.value, id="late-reader")),
        )

    def push_before_mount() -> rx.Component:
        return rx.el.div(
            rx.input(
                value=LateMountState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.el.button("push", on_click=LateMountState.push_value, id="pusher"),
            rx.el.button(
                "push none", on_click=LateMountState.push_none, id="none-pusher"
            ),
            rx.el.button("reveal", on_click=LateMountState.reveal, id="reveal"),
            rx.cond(LateMountState.show, rx.el.div(pushed.value, id="pushed-reader")),
        )

    def backend_default_page() -> rx.Component:
        return rx.el.div(
            rx.input(
                value=LateMountState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.input(value=backend_default.value, read_only=True, id="backend-reader"),
            rx.el.button("set", on_click=backend_default.set("changed"), id="setter"),
        )

    app = rx.App()
    app.add_page(index, route="/")
    app.add_page(setter_first, route="/setter-first")
    app.add_page(backend_default_page, route="/backend-default")
    app.add_page(push_before_mount, route="/push-before-mount")


def _script_errors(page: Page) -> list[str]:
    """Record errors raised by scripts the backend runs on the page.

    The frontend catches these and only logs them, so they never reach
    ``pageerror``.

    Args:
        page: Playwright page.

    Returns:
        A list that is appended to as errors are logged.
    """
    errors: list[str] = []
    page.on(
        "console",
        lambda message: (
            errors.append(message.text)
            if message.text.startswith((
                "_call_script",
                "_call_function",
                "_client_state",
            ))
            else None
        ),
    )
    return errors


def _page_errors(page: Page) -> list[str]:
    """Record uncaught frontend errors raised on the page.

    Args:
        page: Playwright page.

    Returns:
        A list that is appended to as errors occur.
    """
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors


@pytest.fixture(scope="module")
def client_state_late_mount_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the late-mount app.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("client_state_late_mount_app"),
        app_source=ClientStateLateMountApp,
    ) as harness:
        yield harness


def test_late_mounted_consumer_reads_the_current_value(
    client_state_late_mount_app: AppHarness, page: Page
) -> None:
    """A consumer mounting after a push reads the live value, not the default.

    Ported from reflex-dev/reflex#6824 (issue #6823). Under the old design every
    consumer held its own ``useState(default)``, so one that mounted after a
    push initialized to the default and then *stayed* there: pushing the value
    back to the default was a no-op for its setter, leaving it permanently out
    of sync. There is now one slot per name, and a late consumer binds to it
    rather than seeding a copy, so this holds by construction.

    Args:
        client_state_late_mount_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_late_mount_app.frontend_url is not None
    page.goto(client_state_late_mount_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    expect(page.locator("#always")).to_have_text("")
    expect(page.locator("#late")).to_have_count(0)

    page.click("#go")

    # The late consumer appears already holding the pushed value ...
    expect(page.locator("#always")).to_have_text("busy")
    expect(page.locator("#late")).to_have_text("busy")
    # ... and follows the push back to the default.
    expect(page.locator("#always")).to_have_text("")
    expect(page.locator("#late")).to_have_text("")


def test_setter_works_before_any_reader_mounts(
    client_state_late_mount_app: AppHarness, page: Page
) -> None:
    """A setter-only component owns its slot binding; no reader needs to exist.

    Ported from reflex-dev/reflex#7286. The old setter referenced a function a
    *reader's* ``useState`` hook defined, so with the reader behind a cond the
    click threw. The setter now carries its own ``useClientState`` hook.

    Args:
        client_state_late_mount_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_late_mount_app.frontend_url is not None
    errors = _page_errors(page)
    page.goto(
        client_state_late_mount_app.frontend_url.removesuffix("/") + "/setter-first"
    )
    expect(page.locator("#token")).not_to_have_value("")
    expect(page.locator("#late-reader")).to_have_count(0)

    page.click("#setter")
    page.click("#reveal")
    expect(page.locator("#late-reader")).to_have_text("clicked")
    assert errors == []


def test_setter_only_sibling_with_backend_default(
    client_state_late_mount_app: AppHarness, page: Page
) -> None:
    """A var seeded from backend state works with a setter-only sibling.

    Ported from reflex-dev/reflex#7286: the default's state context hook has to
    travel with the setter, or its memo body references the state without
    declaring it.

    Args:
        client_state_late_mount_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_late_mount_app.frontend_url is not None
    errors = _page_errors(page)
    page.goto(
        client_state_late_mount_app.frontend_url.removesuffix("/") + "/backend-default"
    )
    expect(page.locator("#token")).not_to_have_value("")

    expect(page.locator("#backend-reader")).to_have_value("from backend")
    page.click("#setter")
    expect(page.locator("#backend-reader")).to_have_value("changed")
    assert errors == []


def test_late_reader_follows_a_set_back_to_the_default(
    client_state_late_mount_app: AppHarness, page: Page
) -> None:
    """A reader that mounts after a frontend set still follows a set back to the default.

    Ported from reflex-dev/reflex#7407. Under the old design the late reader's
    ``useState`` started from the default, and React skips a state update equal to
    the current state, so setting the default again left it showing the stale
    value. A late consumer here binds to the one existing slot instead.

    Args:
        client_state_late_mount_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_late_mount_app.frontend_url is not None
    errors = _page_errors(page)
    page.goto(
        client_state_late_mount_app.frontend_url.removesuffix("/") + "/setter-first"
    )
    expect(page.locator("#token")).not_to_have_value("")

    page.click("#setter")
    page.click("#reveal")
    expect(page.locator("#late-reader")).to_have_text("clicked")
    page.click("#resetter")
    expect(page.locator("#late-reader")).to_have_text("initial")
    assert errors == []


@pytest.mark.parametrize(
    ("pusher", "expected"),
    [("#pusher", "pushed"), ("#none-pusher", "")],
    ids=["value", "none"],
)
def test_push_before_any_reader_mounts(
    client_state_late_mount_app: AppHarness, page: Page, pusher: str, expected: str
) -> None:
    """A backend push lands before any component using the var has mounted.

    Ported from reflex-dev/reflex#7407. The store claims the slot on write, so
    the first consumer to mount binds to the pushed value rather than seeding the
    default -- and a pushed ``None`` is a value, not a missing slot.

    Args:
        client_state_late_mount_app: Running app harness.
        page: Playwright page.
        pusher: The button that pushes.
        expected: The text the late reader shows.
    """
    assert client_state_late_mount_app.frontend_url is not None
    errors = _page_errors(page)
    script_errors = _script_errors(page)
    page.goto(
        client_state_late_mount_app.frontend_url.removesuffix("/")
        + "/push-before-mount"
    )
    expect(page.locator("#token")).not_to_have_value("")
    expect(page.locator("#pushed-reader")).to_have_count(0)

    page.click(pusher)
    page.click("#reveal")
    expect(page.locator("#pushed-reader")).to_have_text(expected)
    assert errors == []
    assert script_errors == []

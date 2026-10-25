"""Integration tests for reporting state deltas the frontend cannot process.

A delta whose substate has no dispatch function in the compiled frontend means
the frontend and backend disagree about the state tree. The frontend reports it
back over the ``client_error`` socket event so the failure is visible in the
backend logs instead of being dropped silently, skips that substate, and keeps
processing events.

A frontend compiled for another state tree is also detected when it connects:
it sends the hash of its tree, and the backend answers a mismatch with the
``state_mismatch`` event. In prod the page reloads once per cooldown window and
otherwise shows a "new version available" banner, unless the app cancels the
``reflex:state-mismatch`` window event; in dev it only warns.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Generator

import pytest
from playwright.sync_api import ConsoleMessage, Page, expect
from reflex_base.registry import RegistrationContext

from reflex.state import State, StateUpdate, _frontend_schema, all_base_state_classes
from reflex.testing import AppHarness, AppHarnessProd

# Substate name with no dispatch function in the compiled frontend.
GHOST_SUBSTATE = "reflex___state____state____ghost_state"

# The banner the frontend shows when a reload already happened inside the cooldown.
NEW_VERSION_BANNER = "#reflex-new-version-banner"
# sessionStorage key of the last automatic reload, shared with reloads on error.
LAST_RELOADED_KEY = "reflex_last_reloaded_on_error"
NAVIGATION_TYPE = "performance.getEntriesByType('navigation')[0].type"


def ClientErrorApp():
    """App that can emit a state delta the frontend cannot process."""
    import reflex as rx
    from reflex.state import StateUpdate

    ghost_substate = "reflex___state____state____ghost_state"

    class ClientErrorState(rx.State):
        counter: int = 0

        @rx.event
        def bump(self):
            self.counter += 1

        @rx.event
        async def send_unprocessable_delta(self):
            assert app.event_namespace is not None
            await app.event_namespace.emit_update(
                StateUpdate(delta={ghost_substate: {"value": 1}}),
                self.router.session.client_token,
            )

    @rx.page("/")
    def index():
        return rx.box(
            rx.text(ClientErrorState.counter, id="counter"),
            rx.input(
                value=ClientErrorState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button("bump", on_click=ClientErrorState.bump, id="bump-btn"),
            rx.button(
                "break",
                on_click=ClientErrorState.send_unprocessable_delta,
                id="break-btn",
            ),
        )

    @rx.page("/handled")
    def handled():
        return rx.fragment(
            rx.script(
                "window.addEventListener('reflex:state-mismatch', (event) => {"
                " event.preventDefault(); window.__state_mismatch = event.detail; });"
            ),
            index(),
        )

    app = rx.App()


@pytest.fixture(scope="module")
def client_error_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the ClientErrorApp.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("client_error_app"),
        app_source=ClientErrorApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_unprocessable_delta_is_reported_to_backend(
    client_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
):
    """An unprocessable delta reaches the backend's frontend exception handler.

    Args:
        client_error_app: Running AppHarness instance.
        page: Playwright page fixture.
        monkeypatch: pytest fixture for patching the exception handler.
    """
    assert client_error_app.frontend_url is not None
    assert client_error_app.app_instance is not None
    page.goto(client_error_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # The socket works before the mismatch.
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")

    reports: list[str] = []
    monkeypatch.setattr(
        client_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )

    page.click("#break-btn")

    assert AppHarness._poll_for(lambda: reports), (
        "backend was not told about the unprocessable delta"
    )
    report = reports[0]
    assert GHOST_SUBSTATE in report
    assert "no dispatch function" in report
    assert "rebuild" in report.lower()


def test_unprocessable_delta_does_not_stop_events(
    client_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
):
    """A mismatch is reported without reloading the page or blocking events.

    Args:
        client_error_app: Running AppHarness instance.
        page: Playwright page fixture.
        monkeypatch: pytest fixture for patching the exception handler.
    """
    assert client_error_app.frontend_url is not None
    assert client_error_app.app_instance is not None
    page.goto(client_error_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    reports: list[str] = []
    monkeypatch.setattr(
        client_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )

    page.click("#break-btn")
    assert AppHarness._poll_for(lambda: reports), (
        "backend was not told about the unprocessable delta"
    )

    # No automatic reload: the page's original navigation entry is still live.
    assert (
        page.evaluate("() => performance.getEntriesByType('navigation')[0].type")
        == "navigate"
    )

    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")


def test_unknown_substate_in_hydrate_delta(
    client_error_app: AppHarness, page: Page, monkeypatch: pytest.MonkeyPatch
):
    """The page hydrates when the hydrate delta names an unknown substate.

    Args:
        client_error_app: Running AppHarness instance.
        page: Playwright page fixture.
        monkeypatch: pytest fixture for patching outgoing updates.
    """
    assert client_error_app.frontend_url is not None
    assert client_error_app.app_instance is not None
    namespace = client_error_app.app_instance.event_namespace
    assert namespace is not None
    emit_update = namespace.emit_update
    reports: list[str] = []
    monkeypatch.setattr(
        client_error_app.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )

    async def emit_with_unknown_substate(update: StateUpdate, token: str) -> None:
        """Add an unknown substate to every outgoing update.

        Args:
            update: The outgoing state update.
            token: The client token.
        """
        delta = {GHOST_SUBSTATE: {"value": 1}, **update.delta}
        await emit_update(dataclasses.replace(update, delta=delta), token)

    monkeypatch.setattr(namespace, "emit_update", emit_with_unknown_substate)
    page.goto(client_error_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    assert AppHarness._poll_for(lambda: reports)
    assert GHOST_SUBSTATE in reports[0]


@pytest.fixture(scope="module")
def client_error_app_env(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the ClientErrorApp in dev and in prod mode.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("client_error_app_env"),
        app_name=f"client_error_app_{app_harness_env.__name__.lower()}",
        app_source=ClientErrorApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def mismatch_reports(
    client_error_app_env: AppHarness, monkeypatch: pytest.MonkeyPatch
) -> Generator[list[str], None, None]:
    """Give the backend a state the compiled frontend lacks.

    Args:
        client_error_app_env: Running AppHarness instance.
        monkeypatch: pytest fixture for patching the exception handler.

    Yields:
        The frontend exceptions reported to the backend.
    """
    assert client_error_app_env.app_instance is not None
    reports: list[str] = []
    monkeypatch.setattr(
        client_error_app_env.app_instance,
        "frontend_exception_handler",
        lambda exc: reports.append(str(exc)),
    )

    class ClientErrorExtraState(State):
        extra: int = 0

    try:
        yield reports
    finally:
        context = RegistrationContext.get()
        context.get_substates(State).discard(ClientErrorExtraState)
        context.base_states.pop(ClientErrorExtraState.get_full_name(), None)
        for name, registered in list(context.event_handlers.items()):
            if ClientErrorExtraState in registered.states:
                del context.event_handlers[name]
        all_base_state_classes.pop(ClientErrorExtraState.get_full_name(), None)
        State.get_class_substate.cache_clear()
        _frontend_schema.cache_clear()


def _is_mismatch_warning(msg: ConsoleMessage) -> bool:
    """Whether a console message is the frontend's state mismatch warning.

    Args:
        msg: The console message.

    Returns:
        True for the mismatch warning.
    """
    return msg.type == "warning" and "another version of the app" in msg.text


def test_matching_schema_shows_nothing(client_error_app_env: AppHarness, page: Page):
    """A frontend compiled for the backend's state tree connects without a word.

    Args:
        client_error_app_env: Running AppHarness instance.
        page: Playwright page fixture.
    """
    assert client_error_app_env.frontend_url is not None
    warnings: list[str] = []
    page.on(
        "console",
        lambda msg: warnings.append(msg.text) if _is_mismatch_warning(msg) else None,
    )
    page.goto(client_error_app_env.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")

    # Console events reach the test while it waits inside Playwright.
    page.wait_for_timeout(500)
    assert page.evaluate(NAVIGATION_TYPE) == "navigate"
    expect(page.locator(NEW_VERSION_BANNER)).to_have_count(0)
    assert page.evaluate(f"sessionStorage.getItem('{LAST_RELOADED_KEY}')") is None
    assert warnings == []


def test_state_mismatch_prompts_reload(
    client_error_app_env: AppHarness, page: Page, mismatch_reports: list[str]
):
    """A frontend compiled without a state the backend has is told to reload.

    The backend gains a state after the frontend was compiled, as a redeploy
    does for a page kept open. In prod the page reloads once; the reload lands
    on the same mismatch, so the banner with a reload button shows and no
    further reload happens inside the cooldown. In dev only a warning is
    logged. The hydrate still reaches the page, so the delta for the unknown
    state is reported through the frontend exception handler as before.

    Args:
        client_error_app_env: Running AppHarness instance.
        page: Playwright page fixture.
        mismatch_reports: The frontend exceptions reported to the backend.
    """
    assert client_error_app_env.frontend_url is not None
    if isinstance(client_error_app_env, AppHarnessProd):
        page.goto(client_error_app_env.frontend_url)
        # The first mismatch reloads the page at once.
        page.wait_for_function(f"{NAVIGATION_TYPE} === 'reload'")
        # The reload hits the same mismatch inside the cooldown: a banner.
        banner = page.locator(NEW_VERSION_BANNER)
        expect(banner).to_be_visible()
        expect(banner).to_contain_text("new version")
        page.evaluate("() => { window.__same_document = true; }")
        page.wait_for_timeout(1500)
        assert page.evaluate("() => window.__same_document") is True
        expect(page.locator(NEW_VERSION_BANNER)).to_have_count(1)
        # The button reloads and restarts the cooldown.
        banner.get_by_role("button", name="Reload").click()
        page.wait_for_function("() => window.__same_document === undefined")
        expect(page.locator(NEW_VERSION_BANNER)).to_be_visible()
    else:
        with page.expect_console_message(_is_mismatch_warning):
            page.goto(client_error_app_env.frontend_url)
        page.wait_for_timeout(1000)
        assert page.evaluate(NAVIGATION_TYPE) == "navigate"
        expect(page.locator(NEW_VERSION_BANNER)).to_have_count(0)
    # The unknown-substate fallback stays in place next to the detection.
    assert AppHarness._poll_for(lambda: mismatch_reports)
    assert "no dispatch function" in mismatch_reports[0]


def test_state_mismatch_handled_by_app(
    client_error_app_env: AppHarness, page: Page, mismatch_reports: list[str]
):
    """An app that cancels the mismatch window event keeps the page as it is.

    In prod the page dispatches ``reflex:state-mismatch`` before it reloads or
    shows the banner; the page's listener calls preventDefault(), so neither
    happens and the page keeps working. In dev the event is not dispatched and
    the page only warns, as without a listener.

    Args:
        client_error_app_env: Running AppHarness instance.
        page: Playwright page fixture.
        mismatch_reports: The frontend exceptions reported to the backend.
    """
    assert client_error_app_env.frontend_url is not None
    url = f"{client_error_app_env.frontend_url.rstrip('/')}/handled"
    if isinstance(client_error_app_env, AppHarnessProd):
        page.goto(url)
        page.wait_for_function("() => window.__state_mismatch !== undefined")
        detail = page.evaluate("() => window.__state_mismatch")
        assert detail["frontend"]
        assert detail["backend"]
        assert detail["frontend"] != detail["backend"]
    else:
        with page.expect_console_message(_is_mismatch_warning):
            page.goto(url)
        assert page.evaluate("() => window.__state_mismatch") is None
    expect(page.locator("#token")).not_to_have_value("")
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")
    assert page.evaluate(NAVIGATION_TYPE) == "navigate"
    expect(page.locator(NEW_VERSION_BANNER)).to_have_count(0)
    assert page.evaluate(f"sessionStorage.getItem('{LAST_RELOADED_KEY}')") is None
    assert AppHarness._poll_for(lambda: mismatch_reports)

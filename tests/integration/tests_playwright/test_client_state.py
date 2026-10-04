"""Integration tests for ``rx._x.client_state`` shared between sibling components."""

from collections.abc import Generator

import pytest
from playwright.sync_api import ConsoleMessage, Page, expect

from reflex.testing import AppHarness


def ClientStateApp():
    """App sharing a global client state var between sibling components."""
    import reflex as rx

    pushed = rx._x.client_state(default="initial")

    class ClientStateAppState(rx.State):
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

    shared = rx._x.client_state(default="initial")
    backend_default = rx._x.client_state(default=ClientStateAppState.default_text)

    def index():
        return rx.box(
            rx.button("set", on_click=shared.set_value("clicked"), id="setter"),
            rx.button("reset", on_click=shared.set_value("initial"), id="resetter"),
            rx.button("reveal", on_click=ClientStateAppState.reveal, id="reveal"),
            rx.cond(
                ClientStateAppState.show,
                rx.text(shared.value, id="late-reader"),
            ),
            rx.text(ClientStateAppState.router.session.client_token, id="token"),
        )

    def siblings():
        return rx.box(
            rx.text(shared.value, id="reader"),
            rx.button("set", on_click=shared.set_value("clicked"), id="setter"),
        )

    def backend_default_page():
        return rx.box(
            rx.input(
                value=backend_default.value,
                placeholder=ClientStateAppState.default_text,
                read_only=True,
                id="backend-reader",
            ),
            rx.button(
                "set", on_click=backend_default.set_value("changed"), id="setter"
            ),
        )

    def push_before_mount():
        return rx.box(
            rx.button("push", on_click=ClientStateAppState.push_value, id="pusher"),
            rx.button(
                "push none", on_click=ClientStateAppState.push_none, id="none-pusher"
            ),
            rx.button("reveal", on_click=ClientStateAppState.reveal, id="reveal"),
            rx.cond(
                ClientStateAppState.show,
                rx.text(pushed.value, id="pushed-reader"),
            ),
            rx.text(ClientStateAppState.router.session.client_token, id="token"),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(siblings)
    app.add_page(backend_default_page, route="/backend-default")
    app.add_page(push_before_mount, route="/push-before-mount")


@pytest.fixture(scope="module")
def client_state_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the client state app under an AppHarness.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("client_state"),
        app_source=ClientStateApp,
    ) as harness:
        yield harness


def _collect_page_errors(page: Page) -> list[str]:
    """Record uncaught frontend errors raised on the page.

    Args:
        page: Playwright page.

    Returns:
        A list that is appended to as errors occur.
    """
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors


def _collect_script_errors(page: Page) -> list[str]:
    """Record errors raised by scripts the backend runs on the page.

    The frontend catches these and only logs them, so they never reach
    ``pageerror``.

    Args:
        page: Playwright page.

    Returns:
        A list that is appended to as errors are logged.
    """
    errors: list[str] = []

    def on_console(message: ConsoleMessage) -> None:
        if message.text.startswith(("_call_script", "_call_function")):
            errors.append(message.text)

    page.on("console", on_console)
    return errors


def test_sibling_setter_updates_reader(
    client_state_app: AppHarness, page: Page
) -> None:
    """A sibling button setting the client state updates the sibling reader.

    Args:
        client_state_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_app.frontend_url is not None
    errors = _collect_page_errors(page)
    page.goto(client_state_app.frontend_url.removesuffix("/") + "/siblings")

    expect(page.locator("#reader")).to_have_text("initial")
    page.click("#setter")
    expect(page.locator("#reader")).to_have_text("clicked")
    assert errors == []


def test_setter_works_before_reader_mounts(
    client_state_app: AppHarness, page: Page
) -> None:
    """The setter works even when no component reading the value is mounted.

    Args:
        client_state_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_app.frontend_url is not None
    errors = _collect_page_errors(page)
    page.goto(client_state_app.frontend_url)
    expect(page.locator("#token")).not_to_be_empty()

    page.click("#setter")
    page.click("#reveal")
    expect(page.locator("#late-reader")).to_have_text("clicked")
    assert errors == []


def test_late_reader_follows_set_back_to_default(
    client_state_app: AppHarness, page: Page
) -> None:
    """A reader that mounts after a set still follows setting the default again.

    React skips a state update equal to the current state, so the late reader's
    ``useState`` must start from the shared value rather than the default, or
    setting the value back to the default leaves it showing the stale value.

    Args:
        client_state_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_app.frontend_url is not None
    errors = _collect_page_errors(page)
    page.goto(client_state_app.frontend_url)
    expect(page.locator("#token")).not_to_be_empty()

    page.click("#setter")
    page.click("#reveal")
    expect(page.locator("#late-reader")).to_have_text("clicked")
    page.click("#resetter")
    expect(page.locator("#late-reader")).to_have_text("initial")
    assert errors == []


def test_push_before_reader_mounts(client_state_app: AppHarness, page: Page) -> None:
    """A backend push lands even when no component using the value is mounted.

    Nothing defines the setter until such a component mounts, so the push has to
    keep the value for the first one to mount instead of failing with
    ``refs._client_state_set... is not a function``.

    Args:
        client_state_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_app.frontend_url is not None
    errors = _collect_page_errors(page)
    script_errors = _collect_script_errors(page)
    page.goto(client_state_app.frontend_url.removesuffix("/") + "/push-before-mount")
    expect(page.locator("#token")).not_to_be_empty()

    page.click("#pusher")
    page.click("#reveal")
    expect(page.locator("#pushed-reader")).to_have_text("pushed")
    assert errors == []
    assert script_errors == []


def test_push_none_before_reader_mounts(
    client_state_app: AppHarness, page: Page
) -> None:
    """A ``None`` pushed before the reader mounts is kept, not replaced by the default.

    Args:
        client_state_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_app.frontend_url is not None
    errors = _collect_page_errors(page)
    script_errors = _collect_script_errors(page)
    page.goto(client_state_app.frontend_url.removesuffix("/") + "/push-before-mount")
    expect(page.locator("#token")).not_to_be_empty()

    page.click("#none-pusher")
    page.click("#reveal")
    expect(page.locator("#pushed-reader")).to_have_text("")
    assert errors == []
    assert script_errors == []


def test_setter_with_backend_default(client_state_app: AppHarness, page: Page) -> None:
    """A setter-only sibling works when the default comes from backend state.

    Args:
        client_state_app: Running app harness.
        page: Playwright page.
    """
    assert client_state_app.frontend_url is not None
    errors = _collect_page_errors(page)
    page.goto(client_state_app.frontend_url.removesuffix("/") + "/backend-default")

    expect(page.locator("#backend-reader")).to_have_value("from backend")
    page.click("#setter")
    expect(page.locator("#backend-reader")).to_have_value("changed")
    assert errors == []

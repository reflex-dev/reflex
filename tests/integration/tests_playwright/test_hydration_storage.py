"""Browser regressions for client-storage writes during hydration and assigned defaults."""

import re
from collections.abc import Callable, Generator

import pytest
from playwright.sync_api import Page, WebSocketRoute, expect

from reflex.testing import AppHarness, AppHarnessProd


def HydrationStorageApp():
    """Create an app with mismatched defaults and hydration-time storage writes."""
    import uuid

    import reflex as rx
    from reflex.constants.state import FIELD_MARKER

    class StorageState(rx.State):
        local: str = rx.LocalStorage("local-default", name="hydrate-local")
        session: str = rx.SessionStorage("session-default", name="hydrate-session")
        cookie: str = rx.Cookie("cookie-default", name="hydrate-cookie")
        nonce: rx.Field[str] = rx.field(default_factory=lambda: uuid.uuid4().hex)

        @rx.var
        def checked(self) -> str:
            """Clear rejected values in each storage type.

            Returns:
                The current values for display.
            """
            if self.local == "bad":
                self.local = ""
            if self.session == "bad":
                self.session = ""
            if self.cookie == "bad":
                self.cookie = ""
            return f"{self.local}|{self.session}|{self.cookie}"

        @rx.event
        def load(self):
            """Provide an on-load event for the second page."""

    class ReconcileState(rx.State):
        token_hash: str = rx.LocalStorage("", name="hydrate-token-hash")

        @rx.state._override_base_method
        def get_delta(self):
            """Replace a stale token hash, as auth plugins reconcile theirs.

            Returns:
                The delta, with a stale token hash replaced.
            """
            delta = super().get_delta()
            subdelta = delta.get(self.get_full_name(), {})
            if subdelta.get("token_hash" + FIELD_MARKER) == "stale":
                subdelta["token_hash" + FIELD_MARKER] = "fresh"
            return delta

    class AssignedStorageState(rx.State):
        local: str = rx.LocalStorage("declared", name="assigned-local")
        session: str = rx.SessionStorage("declared", name="assigned-session")
        cookie: str = rx.Cookie("declared", name="assigned-cookie")
        factory: rx.Field[str] = rx.field(
            default_factory=lambda: rx.LocalStorage("declared", name="assigned-factory")
        )

        @rx.event
        def change(self):
            """Change the values the browser stores."""
            self.local = "changed"
            self.session = "changed"
            self.cookie = "changed"
            self.factory = "changed"

    AssignedStorageState.local = "assigned"
    AssignedStorageState.session = "assigned"
    AssignedStorageState.cookie = "assigned"
    AssignedStorageState.factory = "assigned"

    class PreferenceState(rx.ComponentState):
        pref: str = rx.LocalStorage("declared", name="assigned-pref")

        @rx.event
        def change(self):
            """Change the preference the browser stores."""
            self.pref = "changed"

        @classmethod
        def get_component(cls, initial: str) -> rx.Component:
            """Configure the preference default for this component.

            Args:
                initial: The preference's default value.

            Returns:
                The preference and a button changing it.
            """
            cls.pref = initial
            return rx.box(
                rx.text(cls.pref, id="assigned-pref"),
                rx.button("Change", on_click=cls.change, id="change-pref"),
            )

    class SyncState(rx.State):
        value: str = rx.LocalStorage("", name="hydrate-sync", sync=True)

        @rx.event
        def set_value(self, value: str):
            """Store a value that other tabs pick up.

            Args:
                value: The value to store.
            """
            self.value = value

    class ReplaceState(rx.State):
        value: str = rx.LocalStorage("", name="hydrate-replace", sync=True)
        _keep: bool = False

        @rx.event
        def keep_sent(self):
            """Store the value the override replaced at boot, now unreplaced."""
            self._keep = True
            self.value = "sent"

        @rx.state._override_base_method
        def get_delta(self):
            """Replace the stored value until a handler stores it on purpose.

            Returns:
                The delta, with the value replaced.
            """
            delta = super().get_delta()
            subdelta = delta.get(self.get_full_name(), {})
            if not self._keep and subdelta.get("value" + FIELD_MARKER) == "sent":
                subdelta["value" + FIELD_MARKER] = "replaced"
            return delta

    def synced():
        """Display a browser storage var synced across tabs.

        Returns:
            The page component.
        """
        return rx.box(
            rx.text(SyncState.value, id="sync-value"),
            rx.button("Old", on_click=SyncState.set_value("old"), id="set-old"),
            rx.button("New", on_click=SyncState.set_value("new"), id="set-new"),
            rx.text(ReplaceState.value, id="replace-value"),
            rx.button("Keep", on_click=ReplaceState.keep_sent, id="keep-sent"),
            rx.text(rx.cond(rx.State.is_hydrated, "true", "false"), id="hydrated"),
        )

    def index():
        """Display hydration and normalized storage values.

        Returns:
            The page component.
        """
        return rx.box(
            rx.text(StorageState.checked, id="checked"),
            rx.text(rx.cond(rx.State.is_hydrated, "true", "false"), id="hydrated"),
            rx.text(ReconcileState.token_hash, id="token-hash"),
        )

    def assigned():
        """Display browser storage vars whose defaults are assigned to their class.

        Returns:
            The page component.
        """
        return rx.box(
            rx.text(AssignedStorageState.local, id="assigned-local"),
            rx.text(AssignedStorageState.session, id="assigned-session"),
            rx.text(AssignedStorageState.cookie, id="assigned-cookie"),
            rx.text(AssignedStorageState.factory, id="assigned-factory"),
            rx.button("Change", on_click=AssignedStorageState.change, id="change"),
            PreferenceState.create(initial="assigned"),
            rx.text(rx.cond(rx.State.is_hydrated, "true", "false"), id="hydrated"),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(index, route="/loaded", on_load=StorageState.load)
    app.add_page(assigned, route="/assigned")
    app.add_page(synced, route="/synced")


@pytest.fixture(scope="module", params=[AppHarness, AppHarnessProd])
def hydration_storage_app(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Generator[AppHarness, None, None]:
    """Run the same storage app in development and production.

    Args:
        request: The harness parameter.
        tmp_path_factory: The temporary directory factory.

    Yields:
        The running app harness.
    """
    with request.param.create(
        root=tmp_path_factory.mktemp("hydration_storage"),
        app_source=HydrationStorageApp,
    ) as harness:
        yield harness


@pytest.mark.parametrize("route", ["", "loaded"])
def test_hydration_storage(hydration_storage_app: AppHarness, page: Page, route: str):
    """Defaults stay absent, and computed-var corrections persist after reload.

    Args:
        hydration_storage_app: The running app.
        page: A fresh browser page.
        route: The page with or without on-load handlers.
    """
    assert hydration_storage_app.frontend_url is not None
    page.goto(f"{hydration_storage_app.frontend_url.rstrip('/')}/{route}")
    expect(page.locator("#hydrated")).to_have_text("true")
    expect(page.locator("#checked")).to_have_text(
        "local-default|session-default|cookie-default"
    )
    assert page.evaluate("localStorage.getItem('hydrate-local')") is None
    assert page.evaluate("sessionStorage.getItem('hydrate-session')") is None
    assert not any(
        cookie.get("name") == "hydrate-cookie" for cookie in page.context.cookies()
    )

    page.evaluate("""() => {
        localStorage.setItem('hydrate-local', 'bad');
        sessionStorage.setItem('hydrate-session', 'bad');
        document.cookie = 'hydrate-cookie=bad; path=/';
    }""")
    page.reload()
    expect(page.locator("#hydrated")).to_have_text("true")
    expect(page.locator("#checked")).to_have_text("||")
    page.wait_for_function("""() =>
        localStorage.getItem('hydrate-local') === '' &&
        sessionStorage.getItem('hydrate-session') === '' &&
        document.cookie.split('; ').includes('hydrate-cookie=')
    """)
    page.reload()
    expect(page.locator("#hydrated")).to_have_text("true")
    expect(page.locator("#checked")).to_have_text("||")


@pytest.mark.parametrize("route", ["", "loaded"])
def test_hydration_reconciles_storage_in_get_delta(
    hydration_storage_app: AppHarness, page: Page, route: str
):
    """A get_delta override reconciles the client storage a page boots with.

    Args:
        hydration_storage_app: The running app.
        page: A fresh browser page.
        route: The page with or without on-load handlers.
    """
    assert hydration_storage_app.frontend_url is not None
    page.goto(f"{hydration_storage_app.frontend_url.rstrip('/')}/{route}")
    expect(page.locator("#hydrated")).to_have_text("true")
    assert page.evaluate("localStorage.getItem('hydrate-token-hash')") is None

    page.evaluate("localStorage.setItem('hydrate-token-hash', 'stale')")
    page.reload()
    expect(page.locator("#hydrated")).to_have_text("true")
    expect(page.locator("#token-hash")).to_have_text("fresh")
    page.wait_for_function("localStorage.getItem('hydrate-token-hash') === 'fresh'")


# The browser storage vars of the assigned page, by element id suffix.
VARS = ("local", "session", "cookie", "factory", "pref")


def test_assigned_storage_default_persists(
    hydration_storage_app: AppHarness, page: Page
):
    """A plain default assigned to a browser storage var keeps it in the browser.

    Args:
        hydration_storage_app: The running app.
        page: A fresh browser page.
    """
    assert hydration_storage_app.frontend_url is not None
    url = f"{hydration_storage_app.frontend_url.rstrip('/')}/assigned"
    page.goto(url)
    expect(page.locator("#hydrated")).to_have_text("true")
    for var in VARS:
        expect(page.locator(f"#assigned-{var}")).to_have_text("assigned")

    page.locator("#change").click()
    page.locator("#change-pref").click()
    page.wait_for_function("""() =>
        localStorage.getItem('assigned-local') === 'changed' &&
        sessionStorage.getItem('assigned-session') === 'changed' &&
        localStorage.getItem('assigned-pref') === 'changed' &&
        localStorage.getItem('assigned-factory') === 'changed' &&
        document.cookie.split('; ').includes('assigned-cookie=changed')
    """)

    # A new tab starts a new session, which reads the values from the browser.
    other = page.context.new_page()
    other.goto(url)
    expect(other.locator("#hydrated")).to_have_text("true")
    # Session storage belongs to its tab, so the new tab starts from the default.
    for var in VARS:
        expected = "assigned" if var == "session" else "changed"
        expect(other.locator(f"#assigned-{var}")).to_have_text(expected)

    # Reloading the tab keeps its session storage.
    page.reload()
    expect(page.locator("#hydrated")).to_have_text("true")
    for var in VARS:
        expect(page.locator(f"#assigned-{var}")).to_have_text("changed")
    assert page.evaluate("sessionStorage.getItem('assigned-session')") == "changed"


# Records every localStorage write of the synced var.
RECORD_SYNC_WRITES = """
window.syncWrites = [];
const setItem = Storage.prototype.setItem;
Storage.prototype.setItem = function (key, value) {
    if (key === "hydrate-sync") {
        window.syncWrites.push(value);
    }
    return setItem.call(this, key, value);
};
"""

# Stores a synced value as another tab would, optionally without its storage event.
OTHER_TAB_STORES = """
window.otherTabStores = (value, notify = true) => {
    localStorage.setItem('hydrate-sync', value);
    if (notify) {
        window.dispatchEvent(new StorageEvent('storage', {
            key: 'hydrate-sync', newValue: value, storageArea: localStorage,
        }));
    }
};
"""


def wait_until(page: Page, condition: Callable[[], bool]):
    """Wait for a condition while Playwright keeps dispatching websocket messages.

    Args:
        page: The page whose event loop dispatches the messages.
        condition: The condition to wait for.

    Raises:
        TimeoutError: If the condition does not hold within 10 seconds.
    """
    for _ in range(100):
        if condition():
            return
        page.wait_for_timeout(100)
    msg = "Condition not met within 10 seconds."
    raise TimeoutError(msg)


class EventSocket:
    """Records a page's event messages and holds back the server's replies on request."""

    def __init__(self, page: Page, hold: bool = False):
        """Route the page's event websocket through this object.

        Args:
            page: The page whose websocket to route.
            hold: Whether to hold back the replies from the start.
        """
        self.page = page
        self.sent: list[str] = []
        self.held: list[str | bytes] | None = [] if hold else None
        self.route: WebSocketRoute | None = None
        page.route_web_socket(re.compile(r".*/_event"), self._connect)

    def _connect(self, route: WebSocketRoute):
        """Forward the page's messages and the server's, except held replies.

        Args:
            route: The intercepted websocket.
        """
        server = route.connect_to_server()
        self.route = route

        def to_server(message: str | bytes):
            self.sent.append(str(message))
            server.send(message)

        def to_page(message: str | bytes):
            if self.held is not None and '"event"' in str(message):
                self.held.append(message)
            else:
                route.send(message)

        route.on_message(to_server)
        server.on_message(to_page)

    def wait_sent(self, *parts: str):
        """Wait until the page sent a message containing all the parts.

        Args:
            parts: The substrings of the message.
        """
        wait_until(
            self.page,
            lambda: any(all(part in m for part in parts) for m in self.sent),
        )

    def hold(self):
        """Hold back the server's replies from now on."""
        self.held = []

    def release(self):
        """Deliver the held replies in order and stop holding them back."""
        assert self.route is not None
        assert self.held is not None
        held, self.held = self.held, None
        for message in held:
            self.route.send(message)


def test_synced_storage_echo_keeps_newer_value(
    hydration_storage_app: AppHarness, page: Page
):
    """A booting tab does not write back a synced value another tab changed meanwhile.

    The second tab boots with the stored value while its websocket replies are
    held back; the first tab then stores a newer value. Once the replies arrive,
    the second tab must not write the value it booted with over the newer one,
    which would also echo it back to the first tab through a storage event.

    Args:
        hydration_storage_app: The running app.
        page: A fresh browser page.
    """
    assert hydration_storage_app.frontend_url is not None
    url = f"{hydration_storage_app.frontend_url.rstrip('/')}/synced"
    page.goto(url)
    expect(page.locator("#hydrated")).to_have_text("true")
    page.locator("#set-old").click()
    page.wait_for_function("localStorage.getItem('hydrate-sync') === 'old'")

    other = page.context.new_page()
    other.add_init_script(RECORD_SYNC_WRITES)
    socket = EventSocket(other, hold=True)
    other.goto(url)
    # The boot event is sent once the page's effects, storage listener included, ran.
    socket.wait_sent("hydrate_and_load", '"old"')

    page.locator("#set-new").click()
    page.wait_for_function("localStorage.getItem('hydrate-sync') === 'new'")
    socket.wait_sent("update_vars_internal", '"new"')

    socket.release()
    expect(other.locator("#hydrated")).to_have_text("true")
    expect(other.locator("#sync-value")).to_have_text("new")
    expect(page.locator("#sync-value")).to_have_text("new")
    other.wait_for_timeout(500)
    assert "old" not in other.evaluate("window.syncWrites")
    assert page.evaluate("localStorage.getItem('hydrate-sync')") == "new"


def test_synced_storage_event_sends_stored_value(
    hydration_storage_app: AppHarness, page: Page
):
    """A late storage event syncs the value stored now, not the value in the event.

    A tab can get the event of another tab's write after a later write, so the
    event's ``newValue`` may already be stale.

    Args:
        hydration_storage_app: The running app.
        page: A fresh browser page.
    """
    assert hydration_storage_app.frontend_url is not None
    page.add_init_script(RECORD_SYNC_WRITES)
    page.goto(f"{hydration_storage_app.frontend_url.rstrip('/')}/synced")
    expect(page.locator("#hydrated")).to_have_text("true")
    page.evaluate("""() => {
        localStorage.setItem('hydrate-sync', 'stored');
        window.syncWrites.length = 0;
        window.dispatchEvent(new StorageEvent('storage', {
            key: 'hydrate-sync', oldValue: '', newValue: 'late',
            storageArea: localStorage,
        }));
    }""")
    expect(page.locator("#sync-value")).to_have_text("stored")
    page.wait_for_timeout(500)
    assert "late" not in page.evaluate("window.syncWrites")
    assert page.evaluate("localStorage.getItem('hydrate-sync')") == "stored"


@pytest.mark.parametrize("notified", [True, False])
def test_synced_storage_echo_crossed_by_another_tab_is_not_written(
    hydration_storage_app: AppHarness, page: Page, notified: bool
):
    """An echo of a value another tab replaced after it was sent is not written back.

    The tab may get the echo before the storage event of the newer value.

    Args:
        hydration_storage_app: The running app.
        page: A fresh browser page.
        notified: Whether the tab got the newer value's storage event before the echo.
    """
    assert hydration_storage_app.frontend_url is not None
    page.add_init_script(RECORD_SYNC_WRITES)
    page.add_init_script(OTHER_TAB_STORES)
    page.goto(f"{hydration_storage_app.frontend_url.rstrip('/')}/synced")
    expect(page.locator("#hydrated")).to_have_text("true")
    # Another tab stores "sent", then "newer" before the echo of "sent" arrives.
    page.evaluate(f"""() => {{
        window.otherTabStores('sent');
        window.otherTabStores('newer', {str(notified).lower()});
        window.syncWrites.length = 0;
    }}""")
    if not notified:
        expect(page.locator("#sync-value")).to_have_text("sent")
        page.evaluate("window.otherTabStores('newer')")
    expect(page.locator("#sync-value")).to_have_text("newer")
    page.wait_for_timeout(500)
    assert "sent" not in page.evaluate("window.syncWrites")
    assert page.evaluate("localStorage.getItem('hydrate-sync')") == "newer"


def test_synced_storage_echo_after_own_write_is_written(
    hydration_storage_app: AppHarness, page: Page
):
    """An echo is written over a value the tab itself stored after sending it.

    The backend applies a tab's events in order, so the echo of a value sent
    after a handler's event is newer than the value of the handler's reply.

    Args:
        hydration_storage_app: The running app.
        page: A fresh browser page.
    """
    assert hydration_storage_app.frontend_url is not None
    page.add_init_script(OTHER_TAB_STORES)
    socket = EventSocket(page)
    page.goto(f"{hydration_storage_app.frontend_url.rstrip('/')}/synced")
    expect(page.locator("#hydrated")).to_have_text("true")

    socket.hold()
    page.locator("#set-old").click()
    socket.wait_sent("set_value", '"old"')
    page.evaluate("window.otherTabStores('sent')")
    socket.wait_sent("update_vars_internal", '"sent"')

    socket.release()
    expect(page.locator("#sync-value")).to_have_text("sent")
    page.wait_for_timeout(500)
    assert page.evaluate("localStorage.getItem('hydrate-sync')") == "sent"


def test_replaced_storage_echo_does_not_hide_later_change(
    hydration_storage_app: AppHarness, page: Page
):
    """A value sent at boot whose echo was replaced is written when a handler sets it.

    Args:
        hydration_storage_app: The running app.
        page: A fresh browser page.
    """
    assert hydration_storage_app.frontend_url is not None
    page.goto(f"{hydration_storage_app.frontend_url.rstrip('/')}/synced")
    expect(page.locator("#hydrated")).to_have_text("true")
    page.evaluate("localStorage.setItem('hydrate-replace', 'sent')")
    page.reload()
    expect(page.locator("#hydrated")).to_have_text("true")
    expect(page.locator("#replace-value")).to_have_text("replaced")
    page.wait_for_function("localStorage.getItem('hydrate-replace') === 'replaced'")

    page.locator("#keep-sent").click()
    expect(page.locator("#replace-value")).to_have_text("sent")
    page.wait_for_function("localStorage.getItem('hydrate-replace') === 'sent'")
    page.wait_for_timeout(500)
    expect(page.locator("#replace-value")).to_have_text("sent")

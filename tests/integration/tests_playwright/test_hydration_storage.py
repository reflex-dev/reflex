"""Browser regressions for client-storage writes during hydration and assigned defaults."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

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

    fields = AssignedStorageState.__fields__
    fields["local"].default = rx.LocalStorage("assigned", name="assigned-local")
    fields["session"].default = rx.SessionStorage("assigned", name="assigned-session")
    fields["cookie"].default = rx.Cookie("assigned", name="assigned-cookie")
    # A storage value as the default takes precedence over the declared factory.
    fields["factory"].default = rx.LocalStorage("assigned", name="assigned-factory")

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
            cls.__fields__["pref"].default = rx.LocalStorage(
                initial, name="assigned-pref"
            )
            return rx.box(
                rx.text(cls.pref, id="assigned-pref"),
                rx.button("Change", on_click=cls.change, id="change-pref"),
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
    """A browser storage default set through its field keeps the var in the browser.

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

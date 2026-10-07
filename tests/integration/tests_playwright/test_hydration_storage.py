"""Browser regressions for client-storage writes during hydration and assigned defaults."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness, AppHarnessProd


def HydrationStorageApp():
    """Create an app with mismatched defaults and hydration-time storage writes."""
    import uuid

    import reflex as rx

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

    class AssignedStorageState(rx.State):
        local: str = rx.LocalStorage("declared", name="assigned-local")
        cookie: str = rx.Cookie("declared", name="assigned-cookie")

        @rx.event
        def change(self):
            """Change the values the browser stores."""
            self.local = "changed"
            self.cookie = "changed"

    AssignedStorageState.local = "assigned"
    AssignedStorageState.cookie = "assigned"

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

    def index():
        """Display hydration and normalized storage values.

        Returns:
            The page component.
        """
        return rx.box(
            rx.text(StorageState.checked, id="checked"),
            rx.text(rx.cond(rx.State.is_hydrated, "true", "false"), id="hydrated"),
        )

    def assigned():
        """Display browser storage vars whose defaults are assigned to their class.

        Returns:
            The page component.
        """
        return rx.box(
            rx.text(AssignedStorageState.local, id="assigned-local"),
            rx.text(AssignedStorageState.cookie, id="assigned-cookie"),
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
    for var in ("local", "cookie", "pref"):
        expect(page.locator(f"#assigned-{var}")).to_have_text("assigned")

    page.locator("#change").click()
    page.locator("#change-pref").click()
    page.wait_for_function("""() =>
        localStorage.getItem('assigned-local') === 'changed' &&
        localStorage.getItem('assigned-pref') === 'changed' &&
        document.cookie.split('; ').includes('assigned-cookie=changed')
    """)

    # A new tab starts a new session, which reads the values from the browser.
    other = page.context.new_page()
    other.goto(url)
    expect(other.locator("#hydrated")).to_have_text("true")
    for var in ("local", "cookie", "pref"):
        expect(other.locator(f"#assigned-{var}")).to_have_text("changed")

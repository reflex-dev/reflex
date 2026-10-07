"""Browser regressions for the first-load hydration of prerendered pages."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness, AppHarnessProd


def HydrationStorageApp():
    """Create an app with hydration-time storage writes and an untouched substate."""
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

    class UntouchedState(rx.State):
        """A substate the boot hydrate leaves at its compiled default."""

        label: str = "untouched"

    class ReflexGlobalProbe(rx.Component):
        """Reads ``window.__reflex`` while rendering, as a prop formatter would.

        A child shows the value only after mounting, the way a client-rendered
        widget consumes such a prop, so the prerendered HTML matches the first
        client render.
        """

        tag = "ReflexGlobalProbe"

        value: rx.Var[str]

        def add_imports(self) -> dict[str, list[str]]:
            """Import the hooks used by the probe.

            Returns:
                The import dict for the React hooks.
            """
            return {"react": ["useEffect", "useState"]}

        def add_custom_code(self) -> list[str]:
            """Define the probe component in the emitting module.

            Returns:
                The custom code defining ``ReflexGlobalProbe``.
            """
            return [
                """
                function ReflexGlobalView({ text }) {
                  const [mounted, setMounted] = useState(false);
                  useEffect(() => setMounted(true), []);
                  return jsx("span", { id: "reflex-global" }, mounted ? text : "");
                }
                function ReflexGlobalProbe({ value }) {
                  const seen =
                    typeof window === "undefined" ? "undefined" : typeof window.__reflex;
                  return jsx(ReflexGlobalView, { text: `${value}|${seen}` });
                }
                """
            ]

    def index():
        """Display hydration and normalized storage values.

        Returns:
            The page component.
        """
        return rx.box(
            rx.text(StorageState.checked, id="checked"),
            rx.text(rx.cond(rx.State.is_hydrated, "true", "false"), id="hydrated"),
        )

    def reflex_global():
        """Read window.__reflex while rendering a consumer of an unchanged substate.

        Returns:
            The page component.
        """
        return rx.box(
            ReflexGlobalProbe.create(value=UntouchedState.label),
            rx.text(rx.cond(rx.State.is_hydrated, "true", "false"), id="hydrated"),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(index, route="/loaded", on_load=StorageState.load)
    app.add_page(reflex_global, route="/reflex-global")


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


def test_window_reflex_available_at_first_render(
    hydration_storage_app: AppHarness, page: Page
):
    """A render-time reader of window.__reflex sees it on a full page load.

    The boot hydrate only sends substates that differ from their compiled
    defaults, so a consumer of an untouched substate renders exactly once.

    Args:
        hydration_storage_app: The running app.
        page: A fresh browser page.
    """
    assert hydration_storage_app.frontend_url is not None
    page.goto(f"{hydration_storage_app.frontend_url.rstrip('/')}/reflex-global")
    expect(page.locator("#hydrated")).to_have_text("true")
    expect(page.locator("#reflex-global")).to_have_text("untouched|object")
